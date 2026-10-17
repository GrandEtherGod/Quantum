from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .errors import CodePetError


@dataclass(frozen=True)
class RunnerPolicy:
    timeout_seconds: int = 120
    memory_bytes: int = 1_073_741_824
    max_output_file_bytes: int = 52_428_800
    max_open_files: int = 256
    max_processes: int = 128


class IsolatedTestRunner:
    """Runs exact commands from a temporary workspace copy with resource limits.

    Bubblewrap is used when the host actually permits namespace creation. The
    fallback still separates test side effects and strips credentials, but it
    reports that host filesystem and network isolation are not enforced.
    """

    def __init__(
        self,
        workspace: Path,
        *,
        files: list[str],
        environment: dict[str, str],
        output_limit: int,
        redactor: Callable[[str], str],
    ):
        self.workspace = workspace
        self.files = files
        self.environment = environment
        self.output_limit = output_limit
        self.redactor = redactor
        self._bubblewrap = self._probe_bubblewrap()

    @staticmethod
    def _probe_bubblewrap() -> bool:
        executable = shutil.which("bwrap")
        if executable is None:
            return False
        try:
            result = subprocess.run(
                [executable, "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--unshare-net", "--die-with-parent", "/usr/bin/true"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def capabilities(self) -> dict[str, object]:
        return {
            "backend": "bubblewrap" if self._bubblewrap else "workspace_copy",
            "temporary_workspace_copy": True,
            "resource_limits": shutil.which("prlimit") is not None,
            "network_os_enforced": self._bubblewrap,
            "host_filesystem_write_isolated": self._bubblewrap,
            "host_filesystem_read_isolated": False,
        }

    def _copy_selected_workspace(self, destination: Path) -> None:
        for relative in self.files:
            source = self.workspace / relative
            if source.is_symlink() or not source.is_file():
                raise CodePetError(f"Test input changed or became unsafe: {relative}")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target, follow_symlinks=False)

    @staticmethod
    def _resource_prefix(policy: RunnerPolicy) -> list[str]:
        executable = shutil.which("prlimit")
        if executable is None:
            return []
        cpu_seconds = max(1, policy.timeout_seconds + 2)
        return [
            executable,
            f"--cpu={cpu_seconds}",
            f"--as={policy.memory_bytes}",
            f"--fsize={policy.max_output_file_bytes}",
            f"--nofile={policy.max_open_files}",
            f"--nproc={policy.max_processes}",
            "--",
        ]

    def _command(self, command: tuple[str, ...], sandbox: Path, policy: RunnerPolicy) -> tuple[list[str], Path]:
        limited = [*self._resource_prefix(policy), *command]
        if not self._bubblewrap:
            return limited, sandbox
        bubblewrap = shutil.which("bwrap")
        assert bubblewrap is not None
        wrapped = [
            bubblewrap,
            "--die-with-parent",
            "--new-session",
            "--unshare-net",
            "--ro-bind", "/", "/",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--tmpfs", "/root",
            "--tmpfs", "/home",
            "--bind", str(sandbox), "/work",
            "--chdir", "/work",
            *limited,
        ]
        return wrapped, self.workspace

    def run(self, profile: str, command: tuple[str, ...], policy: RunnerPolicy) -> dict[str, object]:
        with tempfile.TemporaryDirectory(prefix="codepet-test-") as directory:
            sandbox = Path(directory) / "workspace"
            sandbox.mkdir()
            self._copy_selected_workspace(sandbox)
            executable = command[0]
            if os.path.sep not in executable and shutil.which(executable) is None:
                return {
                    "profile": profile,
                    "passed": False,
                    "exit_code": None,
                    "output": f"Executable unavailable: {executable}",
                    **self.capabilities(),
                }
            argv, cwd = self._command(command, sandbox, policy)
            try:
                completed = subprocess.run(
                    argv,
                    cwd=cwd,
                    env=self.environment,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=policy.timeout_seconds,
                    shell=False,
                    check=False,
                )
                output = self.redactor(completed.stdout[-self.output_limit :])
                return {
                    "profile": profile,
                    "passed": completed.returncode == 0,
                    "exit_code": completed.returncode,
                    "output": output,
                    **self.capabilities(),
                }
            except subprocess.TimeoutExpired as exc:
                captured = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                return {
                    "profile": profile,
                    "passed": False,
                    "exit_code": None,
                    "output": self.redactor((captured + "\nTimed out")[-self.output_limit :]),
                    **self.capabilities(),
                }
