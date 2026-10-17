from __future__ import annotations

import json
import re
import uuid
from typing import Any

from .db import Database
from .errors import ConcurrentWrite, InvariantViolation
from .ledger import ChronoScribeLedger
from .utils import canonical_json, sha256_hex, utc_now
from .version import VERSION


DEFAULT_STATE: dict[str, Any] = {
    "system.phi_coupling": 0.6180339887,
    "system.ethics_lambda": 0.8,
    "system.max_recursion": 7,
    "system.guardrail_revision": 1,
    "runtime.version": VERSION,
    "memory.consolidation_threshold": 0.7,
    "policy.real_world_actuation": False,
}


class StateStore:
    """The only supported durable state mutation path (Invariant I1)."""

    def __init__(self, database: Database, ledger: ChronoScribeLedger):
        self.database = database
        self.ledger = ledger
        self._ensure_bootstrap()

    def _ensure_bootstrap(self) -> None:
        if self.get("system.kernel_id") is None:
            self.set("system.kernel_id", str(uuid.uuid4()), actor="bootstrap")
        for key, value in DEFAULT_STATE.items():
            if self.get(key) is None:
                self.set(key, value, actor="bootstrap")

    def get(self, key: str) -> tuple[Any, int] | None:
        row = self.database.connection.execute(
            "SELECT value_json, version FROM state WHERE key=?", (key,)
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["value_json"]), row["version"]

    def value(self, key: str, default: Any = None) -> Any:
        result = self.get(key)
        return result[0] if result is not None else default

    def all_state(self) -> dict[str, dict[str, Any]]:
        rows = self.database.connection.execute(
            "SELECT key, value_json, version, updated_at FROM state ORDER BY key"
        ).fetchall()
        return {
            row["key"]: {
                "value": json.loads(row["value_json"]),
                "version": row["version"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        }

    def set(
        self,
        key: str,
        value: Any,
        *,
        expected_version: int | None = None,
        actor: str = "system",
        session_id: str | None = None,
    ) -> int:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT value_json, version FROM state WHERE key=?", (key,)
            ).fetchone()
            old_value = json.loads(row["value_json"]) if row else None
            old_version = row["version"] if row else 0
            if expected_version is not None and old_version != expected_version:
                raise ConcurrentWrite(
                    f"State key {key!r} is version {old_version}, expected {expected_version}."
                )
            self._validate_transition(key, old_value, value)
            version = old_version + 1
            now = utc_now()
            event = self.ledger.append(
                "state_mutation",
                {
                    "key": key,
                    "old_value_hash": sha256_hex(canonical_json(old_value)),
                    "new_value": value,
                    "version": version,
                },
                actor=actor,
                session_id=session_id,
                connection=connection,
            )
            connection.execute(
                """
                INSERT INTO state(key, value_json, version, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json=excluded.value_json,
                    version=excluded.version,
                    updated_at=excluded.updated_at
                """,
                (key, canonical_json(value), version, now),
            )
            connection.execute(
                """
                INSERT INTO state_history(
                    key, old_value_json, new_value_json, version, event_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    canonical_json(old_value) if row else None,
                    canonical_json(value),
                    version,
                    event["event_id"],
                    now,
                ),
            )
        return version

    @staticmethod
    def _validate_transition(key: str, old_value: Any, new_value: Any) -> None:
        if key == "system.kernel_id" and old_value is not None and new_value != old_value:
            raise InvariantViolation("Kernel identity is immutable during ordinary transitions (I5).")
        if key == "runtime.version":
            if not isinstance(new_value, str) or not re.fullmatch(r"\d+\.\d+\.\d+", new_value):
                raise InvariantViolation("runtime.version must use numeric semantic versioning.")
            if old_value is not None:
                old_parts = tuple(int(part) for part in old_value.split("."))
                new_parts = tuple(int(part) for part in new_value.split("."))
                if new_parts < old_parts:
                    raise InvariantViolation("runtime.version cannot move backward through an ordinary transition.")
        if key == "system.phi_coupling":
            if not isinstance(new_value, (int, float)) or not 0.0 <= float(new_value) <= 1.0:
                raise InvariantViolation("phi_coupling must remain in [0, 1] (I2).")
        if key == "system.ethics_lambda":
            if not isinstance(new_value, (int, float)) or not 0.0 <= float(new_value) <= 1.0:
                raise InvariantViolation("ethics_lambda must remain in [0, 1].")
            if old_value is not None and float(new_value) < float(old_value):
                raise InvariantViolation("ethics_lambda cannot silently decrease (I4).")
        if key == "system.max_recursion":
            if not isinstance(new_value, int) or not 1 <= new_value <= 7:
                raise InvariantViolation("The runtime recursion cap must remain between 1 and 7.")
            if old_value is not None and new_value > old_value:
                raise InvariantViolation("The recursion safety bound cannot be loosened automatically.")
        if key == "system.guardrail_revision":
            if not isinstance(new_value, int) or new_value < 1:
                raise InvariantViolation("guardrail_revision must be a positive integer.")
            if old_value is not None and new_value < old_value:
                raise InvariantViolation("Guardrail revisions are monotonic (I4).")
        if key == "memory.consolidation_threshold":
            if not isinstance(new_value, (int, float)) or not 0.5 <= float(new_value) <= 1.0:
                raise InvariantViolation("Consolidation threshold must remain in [0.5, 1.0].")
        if key == "policy.real_world_actuation" and new_value is not False:
            raise InvariantViolation("Real-world actuation is outside this reference runtime boundary.")

    def digest(self) -> str:
        stable = {
            key: {"value": item["value"], "version": item["version"]}
            for key, item in self.all_state().items()
        }
        return sha256_hex(canonical_json(stable))

    def create_snapshot(self, *, actor: str = "system") -> dict[str, Any]:
        snapshot_id = str(uuid.uuid4())
        stable = self.all_state()
        state_root = self.digest()
        with self.database.transaction() as connection:
            event = self.ledger.append(
                "state_snapshot_created",
                {"snapshot_id": snapshot_id, "state_root": state_root},
                actor=actor,
                connection=connection,
            )
            connection.execute(
                "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?)",
                (snapshot_id, utc_now(), canonical_json(stable), state_root, event["seq"]),
            )
        return {"snapshot_id": snapshot_id, "state_root": state_root, "ledger_seq": event["seq"]}

    def rollback(self, snapshot_id: str, *, actor: str, human_approved: bool) -> dict[str, Any]:
        if not human_approved:
            raise InvariantViolation("Rollback requires explicit human approval.")
        row = self.database.connection.execute(
            "SELECT * FROM snapshots WHERE snapshot_id=?", (snapshot_id,)
        ).fetchone()
        if row is None:
            raise KeyError(snapshot_id)
        target = json.loads(row["state_json"])
        current = self.all_state()
        for key, item in target.items():
            old_value = current.get(key, {}).get("value")
            self._validate_transition(key, old_value, item["value"])
        pending_changes: list[tuple[str, str | None, Any, int]] = []
        for key, item in target.items():
            old_item = current.get(key)
            old_value_json = canonical_json(old_item["value"]) if old_item else None
            new_value_json = canonical_json(item["value"])
            if old_value_json != new_value_json:
                pending_changes.append(
                    (key, old_value_json, item["value"], (old_item["version"] if old_item else 0) + 1)
                )
        with self.database.transaction() as connection:
            changed = [item[0] for item in pending_changes]
            event = self.ledger.append(
                "state_rollback",
                {
                    "snapshot_id": snapshot_id,
                    "source_state_root": row["state_root"],
                    "changed_keys": changed,
                    "approval": "explicit_human",
                },
                actor=actor,
                connection=connection,
            )
            for key, old_value_json, new_value, version in pending_changes:
                connection.execute(
                    """
                    INSERT INTO state(key, value_json, version, updated_at) VALUES (?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,
                        version=excluded.version, updated_at=excluded.updated_at
                    """,
                    (key, canonical_json(new_value), version, utc_now()),
                )
                connection.execute(
                    "INSERT INTO state_history VALUES (NULL, ?, ?, ?, ?, ?, ?)",
                    (key, old_value_json, canonical_json(new_value), version, event["event_id"], utc_now()),
                )
        return {"snapshot_id": snapshot_id, "changed_keys": changed, "event_hash": event["event_hash"]}

    def assert_invariants(self) -> dict[str, Any]:
        findings: list[str] = []
        for key, item in self.all_state().items():
            try:
                self._validate_transition(key, item["value"], item["value"])
            except InvariantViolation as exc:
                findings.append(str(exc))
        return {"valid": not findings, "findings": findings, "state_root": self.digest()}
