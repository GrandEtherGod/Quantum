from __future__ import annotations

import base64
import difflib
import functools
import json
import os
import re
import stat
import sys
import threading
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import CodePetError, ProposalStateError, StaleProposalError, WorkspaceBoundaryError
from .runner import IsolatedTestRunner, RunnerPolicy
from .utils import canonical_json, sha256_hex, utc_now


GENESIS_HASH = "0" * 64


def synchronized(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._operation_lock:
            return method(self, *args, **kwargs)
    return wrapper


class CodePetWorkspace:
    """File-native, review-gated coding workflow scoped to one workspace.

    Proposals use complete replacement content instead of accepting raw patch or
    shell syntax. The approval hash binds the exact operations and test profiles.
    """

    IGNORED = {".git", ".runtime", ".venv", "node_modules", "__pycache__", ".codepet"}
    PROTECTED_PARTS = {".git", ".codepet", ".ssh"}
    PROTECTED_NAMES = {".env", ".env.local", "id_rsa", "id_ed25519"}
    PROTECTED_SUFFIXES = {".pem", ".p12", ".pfx", ".key"}
    MAX_FILES = 5000
    MAX_FILE_BYTES = 2_000_000
    MAX_OPERATIONS = 50
    MAX_PROPOSAL_BYTES = 5_000_000
    MAX_TEST_OUTPUT = 64_000
    MAX_TIMEOUT_SECONDS = 300
    TEST_PROFILES = {
        "workspace-integrity": None,
        "python-compile": (sys.executable, "-m", "compileall", "-q", "."),
        "python-unittest": (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"),
        "python-pytest": (sys.executable, "-m", "pytest", "-q"),
        "npm-test": ("npm", "test", "--", "--runInBand"),
    }
    SECRET_PATTERNS = (
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        re.compile(r"(?i)(?:api[_-]?key|secret|token)\s*[=:]\s*['\"][^'\"\n]{12,}['\"]"),
    )

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        if not self.root.exists() or not self.root.is_dir():
            raise CodePetError(f"Workspace is not a directory: {self.root}")
        self.meta = self.root / ".codepet"
        self._operation_lock = threading.RLock()

    def _inside(self, path: Path) -> Path:
        resolved = path.resolve(strict=False)
        if resolved != self.root and self.root not in resolved.parents:
            raise WorkspaceBoundaryError("Path escapes the workspace boundary")
        return resolved

    @staticmethod
    def _atomic_write(path: Path, content: bytes, mode: int | None = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.parent / f".codepet-write-{uuid.uuid4().hex}"
        try:
            with temporary.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            if mode is not None:
                os.chmod(temporary, mode)
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _write_json(self, path: Path, value: dict[str, Any]) -> None:
        self._atomic_write(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    @synchronized
    def initialize(self) -> dict[str, Any]:
        directories = [
            self.meta,
            self.meta / "goals",
            self.meta / "journal",
            self.meta / "plans",
            self.meta / "observations",
            self.meta / "snapshots",
            self.meta / "test-results",
            self.meta / "skills",
        ]
        for directory in directories:
            self._inside(directory).mkdir(parents=True, exist_ok=True)
        defaults = {
            "PET.md": "# CodePet\n\nA review-gated coding companion. Inspection and proposals are allowed; writes and tests require an approval bound to the exact change hash.\n",
            "MEMORY.md": "# Curated Memory\n\nStore durable project facts with sources. Never copy secrets, raw provider payloads, or private transcripts.\n",
            "STATUS.md": "# Status\n\nInitialized. No autonomous task is active.\n",
            "config.json": json.dumps(
                {
                    "schema_version": 2,
                    "mode": "review_gated",
                    "network": False,
                    "auto_apply": False,
                    "max_files": self.MAX_FILES,
                    "max_operations": self.MAX_OPERATIONS,
                    "test_profiles": sorted(self.TEST_PROFILES),
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
        }
        created = []
        for name, content in defaults.items():
            path = self.meta / name
            if not path.exists():
                self._atomic_write(path, content.encode("utf-8"))
                created.append(str(path.relative_to(self.root)))
        self._journal("workspace_initialized", {"created": created, "schema_version": 2})
        return {"workspace": str(self.root), "created": created, "mode": "review_gated"}

    @property
    def journal_path(self) -> Path:
        return self.meta / "journal" / "events.jsonl"

    def verify_journal(self) -> dict[str, Any]:
        if not self.journal_path.exists():
            return {"valid": True, "checked": 0, "root": GENESIS_HASH}
        expected_previous = GENESIS_HASH
        checked = 0
        with self.journal_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    return {"valid": False, "checked": checked, "failed_line": line_number, "reason": "invalid_json"}
                body = {key: value for key, value in entry.items() if key != "event_hash"}
                if body.get("previous_hash") != expected_previous:
                    return {"valid": False, "checked": checked, "failed_line": line_number, "reason": "previous_hash_mismatch"}
                expected_hash = sha256_hex(expected_previous + canonical_json(body))
                if entry.get("event_hash") != expected_hash:
                    return {"valid": False, "checked": checked, "failed_line": line_number, "reason": "event_hash_mismatch"}
                expected_previous = expected_hash
                checked += 1
        return {"valid": True, "checked": checked, "root": expected_previous}

    def _journal(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        verification = self.verify_journal()
        if not verification["valid"]:
            raise CodePetError(f"CodePet journal integrity failed: {verification['reason']}")
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "sequence": verification["checked"] + 1,
            "event_id": str(uuid.uuid4()),
            "at": utc_now(),
            "event_type": event_type,
            "payload": payload,
            "previous_hash": verification["root"],
        }
        entry = {**body, "event_hash": sha256_hex(verification["root"] + canonical_json(body))}
        with self.journal_path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(entry) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return entry

    def _iter_files(self) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        for directory, names, filenames in os.walk(self.root, followlinks=False):
            base = Path(directory)
            names[:] = sorted(
                name for name in names
                if name not in self.IGNORED and not (base / name).is_symlink()
            )
            for filename in sorted(filenames):
                path = base / filename
                if path.is_symlink() or not path.is_file():
                    continue
                file_stat = path.stat()
                if file_stat.st_size > self.MAX_FILE_BYTES:
                    continue
                files.append(
                    {
                        "path": path.relative_to(self.root).as_posix(),
                        "bytes": file_stat.st_size,
                        "sha256": sha256_hex(path.read_bytes()),
                    }
                )
                if len(files) >= self.MAX_FILES:
                    return files
        return files

    @synchronized
    def scan(self) -> dict[str, Any]:
        if not self.meta.exists():
            self.initialize()
        files = self._iter_files()
        truncated = len(files) >= self.MAX_FILES
        stable = {"schema_version": 2, "workspace": self.root.name, "files": files, "truncated": truncated}
        manifest = {**stable, "created_at": utc_now(), "manifest_hash": sha256_hex(canonical_json(stable))}
        path = self.meta / "observations" / "workspace_manifest.json"
        self._write_json(path, manifest)
        self._journal("workspace_scanned", {"file_count": len(files), "manifest_hash": manifest["manifest_hash"], "truncated": truncated})
        return {
            "manifest": str(path),
            "files": files,
            "file_count": len(files),
            "truncated": truncated,
            "manifest_hash": manifest["manifest_hash"],
        }

    def _normalize_relative_path(self, value: Any) -> str:
        if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
            raise WorkspaceBoundaryError("Operation path must be a non-empty POSIX relative path")
        pure = PurePosixPath(value)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise WorkspaceBoundaryError(f"Unsafe operation path: {value!r}")
        if any(part in self.PROTECTED_PARTS for part in pure.parts):
            raise WorkspaceBoundaryError(f"Protected path cannot be modified: {value!r}")
        if pure.name in self.PROTECTED_NAMES or pure.suffix.lower() in self.PROTECTED_SUFFIXES:
            raise WorkspaceBoundaryError(f"Secret-bearing path cannot be modified: {value!r}")
        target = self.root.joinpath(*pure.parts)
        cursor = self.root
        for part in pure.parts[:-1]:
            cursor = cursor / part
            if cursor.exists() and cursor.is_symlink():
                raise WorkspaceBoundaryError(f"Symlink ancestor is not allowed: {value!r}")
        if target.exists() and target.is_symlink():
            raise WorkspaceBoundaryError(f"Symlink targets are not allowed: {value!r}")
        self._inside(target)
        return pure.as_posix()

    def _read_existing_text(self, relative: str) -> tuple[str, str, int]:
        target = self.root / relative
        if not target.exists() or not target.is_file():
            raise CodePetError(f"Expected regular file does not exist: {relative}")
        if target.stat().st_size > self.MAX_FILE_BYTES:
            raise CodePetError(f"File exceeds the editable size limit: {relative}")
        content = target.read_bytes()
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CodePetError(f"Only UTF-8 text files may be edited: {relative}") from exc
        return text, sha256_hex(content), stat.S_IMODE(target.stat().st_mode)

    def _scan_secrets(self, content: str, relative: str) -> None:
        for pattern in self.SECRET_PATTERNS:
            if pattern.search(content):
                raise CodePetError(f"Potential secret detected in proposed content for {relative}")

    def validate_prompt(self, text: Any, *, name: str = "text", max_length: int = 20_000) -> str:
        if not isinstance(text, str) or not text.strip():
            raise CodePetError(f"{name} must be non-empty text")
        value = text.strip()
        if len(value) > max_length:
            raise CodePetError(f"{name} exceeds the length limit")
        self._scan_secrets(value, name)
        return value

    def read_context(self, paths: list[str], *, max_total_bytes: int = 200_000) -> list[dict[str, str]]:
        """Read an explicit, public-safe context selection for a model provider."""
        if not isinstance(paths, list) or len(paths) > 30:
            raise CodePetError("At most 30 explicit context paths may be selected")
        result = []
        total = 0
        for value in paths:
            relative = self._normalize_relative_path(value)
            content, content_hash, _ = self._read_existing_text(relative)
            self._scan_secrets(content, relative)
            total += len(content.encode("utf-8"))
            if total > max_total_bytes:
                raise CodePetError("Selected provider context exceeds the byte limit")
            result.append({"path": relative, "sha256": content_hash, "content": content})
        return result

    def _prepare_operations(self, operations: Any) -> tuple[list[dict[str, Any]], str]:
        if not isinstance(operations, list) or not operations:
            raise CodePetError("A concrete proposal requires at least one operation")
        if len(operations) > self.MAX_OPERATIONS:
            raise CodePetError(f"A proposal may contain at most {self.MAX_OPERATIONS} operations")
        prepared: list[dict[str, Any]] = []
        seen: set[str] = set()
        diff_parts: list[str] = []
        total_bytes = 0
        for raw in operations:
            if not isinstance(raw, dict):
                raise CodePetError("Every operation must be an object")
            unknown_fields = sorted(set(raw) - {"operation", "path", "content", "expected_sha256"})
            if unknown_fields:
                raise CodePetError(f"Unsupported operation fields: {unknown_fields}")
            operation = raw.get("operation")
            if operation not in {"create", "modify", "delete"}:
                raise CodePetError("operation must be create, modify, or delete")
            relative = self._normalize_relative_path(raw.get("path"))
            if relative in seen:
                raise CodePetError(f"Duplicate operation path: {relative}")
            seen.add(relative)
            target = self.root / relative
            old_text = ""
            old_hash: str | None = None
            old_mode: int | None = None
            if operation == "create":
                if target.exists():
                    raise CodePetError(f"Create target already exists: {relative}")
            else:
                old_text, old_hash, old_mode = self._read_existing_text(relative)
                self._scan_secrets(old_text, relative)
                supplied_hash = raw.get("expected_sha256")
                if supplied_hash is not None and supplied_hash != old_hash:
                    raise StaleProposalError(f"Expected hash does not match {relative}")
            if operation == "delete":
                new_text = ""
                content: str | None = None
            else:
                content = raw.get("content")
                if not isinstance(content, str):
                    raise CodePetError(f"{operation} operation requires UTF-8 text content")
                total_bytes += len(content.encode("utf-8"))
                if total_bytes > self.MAX_PROPOSAL_BYTES:
                    raise CodePetError("Proposed replacement content exceeds the proposal limit")
                self._scan_secrets(content, relative)
                new_text = content
                if operation == "modify" and new_text == old_text:
                    raise CodePetError(f"Modify operation has no content change: {relative}")
            diff_parts.extend(
                difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    new_text.splitlines(keepends=True),
                    fromfile=f"a/{relative}" if operation != "create" else "/dev/null",
                    tofile=f"b/{relative}" if operation != "delete" else "/dev/null",
                )
            )
            prepared.append(
                {
                    "operation": operation,
                    "path": relative,
                    "content": content,
                    "expected_sha256": old_hash,
                    "expected_mode": old_mode,
                    "result_sha256": sha256_hex(content.encode("utf-8")) if content is not None else None,
                }
            )
        return prepared, "".join(diff_parts)

    def _validate_tests(self, tests: Any) -> list[str]:
        if tests is None:
            return ["workspace-integrity"]
        if not isinstance(tests, list) or not tests or any(not isinstance(item, str) for item in tests):
            raise CodePetError("tests must be a non-empty list of profile names")
        unknown = sorted(set(tests) - self.TEST_PROFILES.keys())
        if unknown:
            raise CodePetError(f"Unknown test profiles: {unknown}")
        return list(dict.fromkeys(tests))

    @staticmethod
    def _enforce_test_coverage(operations: list[dict[str, Any]], tests: list[str]) -> None:
        suffixes = {PurePosixPath(item["path"]).suffix.lower() for item in operations}
        if ".py" in suffixes and not {"python-compile", "python-unittest", "python-pytest"}.intersection(tests):
            raise CodePetError("Python changes require a Python compile or test profile")
        if suffixes.intersection({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}) and "npm-test" not in tests:
            raise CodePetError("JavaScript or TypeScript changes require the npm-test profile")

    @staticmethod
    def _change_body(proposal: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": proposal["schema_version"],
            "proposal_id": proposal["proposal_id"],
            "base_manifest_hash": proposal["base_manifest_hash"],
            "operations": proposal["operations"],
            "tests": proposal["tests"],
        }

    @synchronized
    def create_proposal(
        self,
        task: str,
        operations: list[dict[str, Any]],
        *,
        tests: list[str] | None = None,
        rationale: str = "",
        risks: list[str] | None = None,
        source: str = "operator",
    ) -> dict[str, Any]:
        task = self.validate_prompt(task, name="task")
        if source not in {"operator", "deterministic_provider", "external_provider"}:
            raise CodePetError("Unknown proposal source")
        if not isinstance(rationale, str):
            raise CodePetError("rationale must be text")
        if len(rationale) > 20_000:
            raise CodePetError("rationale exceeds the length limit")
        if rationale:
            self._scan_secrets(rationale, "rationale")
        if risks is not None and (
            not isinstance(risks, list)
            or len(risks) > 20
            or any(not isinstance(item, str) or len(item) > 1_000 for item in risks)
        ):
            raise CodePetError("risks must be a list of at most 20 short strings")
        for risk in risks or []:
            self._scan_secrets(risk, "risk")
        scan = self.scan()
        prepared, diff = self._prepare_operations(operations)
        proposal_id = str(uuid.uuid4())
        validated_tests = self._validate_tests(tests)
        self._enforce_test_coverage(prepared, validated_tests)
        proposal = {
            "schema_version": 2,
            "proposal_id": proposal_id,
            "created_at": utc_now(),
            "task": task,
            "task_hash": sha256_hex(task),
            "source": source,
            "base_manifest_hash": scan["manifest_hash"],
            "operations": prepared,
            "tests": validated_tests,
            "rationale": rationale.strip() if isinstance(rationale, str) else "",
            "risks": list(risks or []),
            "diff": diff,
            "state": "awaiting_review",
            "authority": {"inspect": True, "write": False, "execute_tests": False, "network": False},
            "approval": None,
        }
        proposal["change_hash"] = sha256_hex(canonical_json(self._change_body(proposal)))
        path = self.meta / "plans" / f"{proposal_id}.json"
        self._write_json(path, proposal)
        self._journal(
            "proposal_created",
            {
                "proposal_id": proposal_id,
                "task_hash": proposal["task_hash"],
                "change_hash": proposal["change_hash"],
                "paths": [item["path"] for item in prepared],
                "tests": proposal["tests"],
                "source": source,
            },
        )
        return {"proposal": str(path), **proposal}

    @synchronized
    def propose(self, task: str) -> dict[str, Any]:
        """Create a non-executable task brief for compatibility with v0.2."""
        task = self.validate_prompt(task, name="task")
        scan = self.scan()
        proposal_id = str(uuid.uuid4())
        proposal = {
            "schema_version": 2,
            "proposal_id": proposal_id,
            "created_at": utc_now(),
            "task": task,
            "task_hash": sha256_hex(task),
            "base_manifest_hash": scan["manifest_hash"],
            "operations": [],
            "tests": [],
            "diff": "",
            "state": "awaiting_review",
            "authority": {"inspect": True, "write": False, "execute_tests": False, "network": False},
            "approval": None,
            "required_next_step": "Create a concrete typed proposal before approval or application.",
        }
        proposal["change_hash"] = sha256_hex(canonical_json(self._change_body(proposal)))
        path = self.meta / "plans" / f"{proposal_id}.json"
        self._write_json(path, proposal)
        self._journal("task_brief_created", {"proposal_id": proposal_id, "task_hash": proposal["task_hash"]})
        return {"proposal": str(path), **proposal}

    def _proposal_path(self, proposal_id: str) -> Path:
        try:
            canonical_id = str(uuid.UUID(proposal_id))
        except (ValueError, AttributeError) as exc:
            raise CodePetError("proposal_id must be a UUID") from exc
        return self.meta / "plans" / f"{canonical_id}.json"

    def load_proposal(self, proposal_id: str) -> dict[str, Any]:
        path = self._proposal_path(proposal_id)
        if not path.exists():
            raise CodePetError(f"Unknown proposal: {proposal_id}")
        with path.open("r", encoding="utf-8") as handle:
            proposal = json.load(handle)
        expected = sha256_hex(canonical_json(self._change_body(proposal)))
        if proposal.get("change_hash") != expected:
            raise CodePetError("Proposal change hash is invalid")
        return proposal

    def list_proposals(self) -> list[dict[str, Any]]:
        if not (self.meta / "plans").exists():
            return []
        result = []
        for path in sorted((self.meta / "plans").glob("*.json")):
            proposal = self.load_proposal(path.stem)
            result.append(
                {
                    "proposal_id": proposal["proposal_id"],
                    "created_at": proposal["created_at"],
                    "task": proposal["task"],
                    "state": proposal["state"],
                    "change_hash": proposal["change_hash"],
                }
            )
        return result

    def _assert_fresh(self, proposal: dict[str, Any]) -> None:
        current = self.scan()["manifest_hash"]
        if current != proposal["base_manifest_hash"]:
            raise StaleProposalError("Workspace changed after proposal creation; prepare a new proposal")
        for operation in proposal["operations"]:
            target = self.root / self._normalize_relative_path(operation["path"])
            if operation["operation"] == "create":
                if target.exists():
                    raise StaleProposalError(f"Create target appeared after proposal: {operation['path']}")
            else:
                if not target.exists() or sha256_hex(target.read_bytes()) != operation["expected_sha256"]:
                    raise StaleProposalError(f"File changed after proposal: {operation['path']}")

    @synchronized
    def approve(self, proposal_id: str, *, actor: str, human_approved: bool) -> dict[str, Any]:
        if human_approved is not True:
            raise ProposalStateError("Approval requires an explicit affirmative flag")
        if not actor.strip():
            raise ProposalStateError("Approval requires an attributable actor")
        proposal = self.load_proposal(proposal_id)
        if proposal["state"] != "awaiting_review":
            raise ProposalStateError(f"Proposal cannot be approved from state {proposal['state']}")
        if not proposal["operations"]:
            raise ProposalStateError("A task brief without concrete operations cannot be approved")
        self._assert_fresh(proposal)
        proposal["state"] = "approved"
        proposal["approval"] = {"actor": actor.strip(), "approved_at": utc_now(), "change_hash": proposal["change_hash"]}
        proposal["authority"] = {"inspect": True, "write": True, "execute_tests": True, "network": False}
        self._write_json(self._proposal_path(proposal_id), proposal)
        self._journal("proposal_approved", {"proposal_id": proposal_id, "change_hash": proposal["change_hash"], "actor": actor.strip()})
        return proposal

    @synchronized
    def reject(self, proposal_id: str, *, actor: str, reason: str) -> dict[str, Any]:
        proposal = self.load_proposal(proposal_id)
        if proposal["state"] not in {"awaiting_review", "approved"}:
            raise ProposalStateError(f"Proposal cannot be rejected from state {proposal['state']}")
        proposal["state"] = "rejected"
        proposal["authority"] = {"inspect": True, "write": False, "execute_tests": False, "network": False}
        proposal["rejection"] = {"actor": actor.strip() or "operator", "reason": reason.strip(), "rejected_at": utc_now()}
        self._write_json(self._proposal_path(proposal_id), proposal)
        self._journal("proposal_rejected", {"proposal_id": proposal_id, "change_hash": proposal["change_hash"], "reason_hash": sha256_hex(reason)})
        return proposal

    def _create_snapshot(self, proposal: dict[str, Any]) -> dict[str, Any]:
        snapshot_id = str(uuid.uuid4())
        records = []
        for operation in proposal["operations"]:
            relative = self._normalize_relative_path(operation["path"])
            target = self.root / relative
            if target.exists():
                raw = target.read_bytes()
                records.append(
                    {
                        "path": relative,
                        "existed": True,
                        "content_b64": base64.b64encode(raw).decode("ascii"),
                        "sha256": sha256_hex(raw),
                        "mode": stat.S_IMODE(target.stat().st_mode),
                    }
                )
            else:
                records.append({"path": relative, "existed": False, "content_b64": None, "sha256": None, "mode": None})
        snapshot = {
            "schema_version": 1,
            "snapshot_id": snapshot_id,
            "proposal_id": proposal["proposal_id"],
            "change_hash": proposal["change_hash"],
            "created_at": utc_now(),
            "files": records,
        }
        snapshot["snapshot_hash"] = sha256_hex(canonical_json(snapshot))
        self._write_json(self.meta / "snapshots" / f"{snapshot_id}.json", snapshot)
        return snapshot

    def _restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        expected = sha256_hex(canonical_json({key: value for key, value in snapshot.items() if key != "snapshot_hash"}))
        if snapshot.get("snapshot_hash") != expected:
            raise CodePetError("Rollback snapshot hash is invalid")
        for record in snapshot["files"]:
            relative = self._normalize_relative_path(record["path"])
            target = self.root / relative
            if record["existed"]:
                raw = base64.b64decode(record["content_b64"], validate=True)
                if sha256_hex(raw) != record["sha256"]:
                    raise CodePetError(f"Rollback snapshot content is corrupt: {relative}")
                self._atomic_write(target, raw, record["mode"])
            elif target.exists():
                if target.is_symlink() or not target.is_file():
                    raise WorkspaceBoundaryError(f"Unsafe rollback target: {relative}")
                target.unlink()
                parent = target.parent
                while parent != self.root and parent != self.meta:
                    try:
                        parent.rmdir()
                    except OSError:
                        break
                    parent = parent.parent

    def _apply_operations(self, proposal: dict[str, Any]) -> None:
        for operation in proposal["operations"]:
            relative = self._normalize_relative_path(operation["path"])
            target = self.root / relative
            if operation["operation"] == "create":
                if target.exists():
                    raise StaleProposalError(f"Create target appeared before write: {relative}")
            elif not target.exists() or sha256_hex(target.read_bytes()) != operation["expected_sha256"]:
                raise StaleProposalError(f"File changed immediately before write: {relative}")
            if operation["operation"] == "delete":
                target.unlink()
                continue
            content = operation["content"].encode("utf-8")
            mode = operation["expected_mode"] if operation["operation"] == "modify" else 0o644
            self._atomic_write(target, content, mode)
            if sha256_hex(target.read_bytes()) != operation["result_sha256"]:
                raise CodePetError(f"Post-write verification failed: {relative}")

    @staticmethod
    def _test_environment() -> dict[str, str]:
        allowed = {"PATH", "LANG", "LC_ALL", "TERM", "SYSTEMROOT", "WINDIR"}
        environment = {key: value for key, value in os.environ.items() if key in allowed}
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["CODEPET_NETWORK_POLICY"] = "disabled_by_contract_not_os_enforced"
        return environment

    def _redact_test_output(self, output: str) -> str:
        redacted = output
        for pattern in self.SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted

    def test_runner_capabilities(self) -> dict[str, object]:
        runner = IsolatedTestRunner(
            self.root,
            files=[item["path"] for item in self._iter_files()],
            environment=self._test_environment(),
            output_limit=self.MAX_TEST_OUTPUT,
            redactor=self._redact_test_output,
        )
        return runner.capabilities()

    def _run_tests(
        self,
        profiles: list[str],
        timeout_seconds: int,
        *,
        require_network_isolation: bool,
    ) -> list[dict[str, Any]]:
        if not 1 <= timeout_seconds <= self.MAX_TIMEOUT_SECONDS:
            raise CodePetError(f"timeout_seconds must be in [1, {self.MAX_TIMEOUT_SECONDS}]")
        files = [item["path"] for item in self._iter_files()]
        runner = IsolatedTestRunner(
            self.root,
            files=files,
            environment=self._test_environment(),
            output_limit=self.MAX_TEST_OUTPUT,
            redactor=self._redact_test_output,
        )
        capabilities = runner.capabilities()
        if require_network_isolation and not capabilities["network_os_enforced"]:
            raise CodePetError("OS-enforced network isolation was required but is unavailable")
        policy = RunnerPolicy(timeout_seconds=timeout_seconds)
        results = []
        for profile in profiles:
            command = self.TEST_PROFILES[profile]
            if command is None:
                verification = self.verify_journal()
                results.append({"profile": profile, "passed": verification["valid"], "exit_code": 0 if verification["valid"] else 1, "output": canonical_json(verification), **capabilities})
                continue
            results.append(runner.run(profile, command, policy))
        return results

    def _update_companion_records(self, proposal: dict[str, Any], result: dict[str, Any]) -> None:
        status = "\n".join(
            [
                "# Status",
                "",
                f"Last proposal: `{proposal['proposal_id']}`",
                f"State: **{proposal['state']}**",
                f"Completed: {result['completed_at']}",
                f"Change hash: `{proposal['change_hash']}`",
                f"Result hash: `{result['result_hash']}`",
                f"Tests: {', '.join(item['profile'] for item in result['tests']) or 'none'}",
                "",
                "No autonomous task is active.",
                "",
            ]
        )
        self._atomic_write(self.meta / "STATUS.md", status.encode("utf-8"))
        if result["passed"]:
            memory_path = self.meta / "MEMORY.md"
            existing = memory_path.read_text(encoding="utf-8") if memory_path.exists() else "# Curated Memory\n"
            task_summary = " ".join(proposal["task"].splitlines())
            entry = "\n".join(
                [
                    "",
                    f"## Applied {result['completed_at']}",
                    f"- Task: {task_summary}",
                    f"- Paths: {', '.join(item['path'] for item in proposal['operations'])}",
                    f"- Change hash: `{proposal['change_hash']}`",
                    "- Evidence: approved typed proposal with passing named tests.",
                    "",
                ]
            )
            if len((existing + entry).encode("utf-8")) <= 500_000:
                self._atomic_write(memory_path, (existing.rstrip() + entry).encode("utf-8"))

    @synchronized
    def apply(
        self,
        proposal_id: str,
        *,
        actor: str,
        timeout_seconds: int = 120,
        require_network_isolation: bool = False,
    ) -> dict[str, Any]:
        proposal = self.load_proposal(proposal_id)
        if proposal["state"] != "approved":
            raise ProposalStateError(f"Proposal cannot be applied from state {proposal['state']}")
        approval = proposal.get("approval") or {}
        if approval.get("change_hash") != proposal["change_hash"]:
            raise ProposalStateError("Approval is not bound to the current change hash")
        if require_network_isolation and not self.test_runner_capabilities()["network_os_enforced"]:
            raise CodePetError("OS-enforced network isolation was required but is unavailable")
        self._assert_fresh(proposal)
        snapshot = self._create_snapshot(proposal)
        self._journal("proposal_apply_started", {"proposal_id": proposal_id, "change_hash": proposal["change_hash"], "snapshot_id": snapshot["snapshot_id"], "actor": actor.strip() or "operator"})
        failure: str | None = None
        results: list[dict[str, Any]] = []
        try:
            self._apply_operations(proposal)
            results = self._run_tests(
                proposal["tests"],
                timeout_seconds,
                require_network_isolation=require_network_isolation,
            )
            if not all(item["passed"] for item in results):
                failure = "one or more test profiles failed"
                self._restore_snapshot(snapshot)
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"
            self._restore_snapshot(snapshot)
        result_document = {
            "proposal_id": proposal_id,
            "change_hash": proposal["change_hash"],
            "snapshot_id": snapshot["snapshot_id"],
            "completed_at": utc_now(),
            "passed": failure is None,
            "failure": failure,
            "tests": results,
            "rollback_scope": "affected_files",
            "network_policy": "required_os_isolation" if require_network_isolation else "disabled_by_contract_best_effort",
        }
        result_document["result_hash"] = sha256_hex(canonical_json(result_document))
        self._write_json(self.meta / "test-results" / f"{proposal_id}.json", result_document)
        proposal["state"] = "applied" if failure is None else "rolled_back"
        proposal["completed_at"] = result_document["completed_at"]
        proposal["result_hash"] = result_document["result_hash"]
        proposal["snapshot_id"] = snapshot["snapshot_id"]
        proposal["authority"] = {"inspect": True, "write": False, "execute_tests": False, "network": False}
        self._write_json(self._proposal_path(proposal_id), proposal)
        self._update_companion_records(proposal, result_document)
        self._journal(
            "proposal_applied" if failure is None else "proposal_rolled_back",
            {
                "proposal_id": proposal_id,
                "change_hash": proposal["change_hash"],
                "snapshot_id": snapshot["snapshot_id"],
                "result_hash": result_document["result_hash"],
                "test_profiles": proposal["tests"],
                "failure": failure,
            },
        )
        return {"proposal": proposal, "result": result_document}

    def verify(self) -> dict[str, Any]:
        journal = self.verify_journal()
        proposals_valid = True
        invalid_proposals = []
        plan_dir = self.meta / "plans"
        paths = sorted(plan_dir.glob("*.json")) if plan_dir.exists() else []
        for path in paths:
            try:
                self.load_proposal(path.stem)
            except (CodePetError, KeyError, json.JSONDecodeError) as exc:
                proposals_valid = False
                invalid_proposals.append({"proposal_id": path.stem, "reason": str(exc)})
        return {
            "valid": journal["valid"] and proposals_valid,
            "workspace": str(self.root),
            "journal": journal,
            "proposals_valid": proposals_valid,
            "invalid_proposals": invalid_proposals,
            "test_runner": self.test_runner_capabilities(),
            "boundary": "File containment, temporary workspace-copy execution, resource limits when available, and command allowlisting are enforced. Inspect test_runner for host network/filesystem isolation status.",
        }
