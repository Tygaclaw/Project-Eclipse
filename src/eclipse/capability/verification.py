"""Independent verification: real commands, real exit codes, honest evidence.

Verification never asks a model whether it succeeded. It runs the project's
compile and test commands, records the exact output, and reports a failure as a
failure. Checks are scoped to the workspace and go through the permission
broker.
"""

from __future__ import annotations

from pathlib import Path
import json
import sys
from typing import Any, Sequence

from eclipse.core.security import Action, PermissionBroker
from .tools import run_command


class VerificationError(Exception):
    """Verification could not run at all."""


def default_checks(workspace_root: str | Path) -> list[list[str]]:
    root = Path(workspace_root)
    checks: list[list[str]] = []
    python_files = [
        path for path in root.rglob("*.py") if ".venv" not in path.parts and "node_modules" not in path.parts
    ]
    if python_files:
        checks.append([sys.executable, "-m", "compileall", "-q", "."])
    if (root / "tests").is_dir() and any((root / "tests").glob("test_*.py")):
        checks.append([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    package_json = root / "package.json"
    if package_json.is_file():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {}
        scripts = payload.get("scripts") if isinstance(payload, dict) else None
        if isinstance(scripts, dict):
            if "build" in scripts:
                checks.append(["npm", "run", "build"])
            elif "test" in scripts:
                checks.append(["npm", "test"])
    if (root / "pyproject.toml").is_file() and (root / "src").is_dir():
        # The compile check already covers syntax; do not invent a linter.
        pass
    return checks


class VerificationEngine:
    """Run the workspace's real checks and keep their raw evidence."""

    def __init__(self, *, timeout_seconds: int = 600) -> None:
        self.timeout_seconds = max(10, int(timeout_seconds))

    def run(
        self,
        *,
        checks: Sequence[str] | None = None,
        broker: PermissionBroker,
        workspace_root: str | Path | None,
    ) -> list[dict[str, Any]]:
        if workspace_root is None:
            raise VerificationError("Verification needs an approved workspace")
        root = Path(workspace_root).resolve()
        if checks:
            commands = []
            for entry in checks:
                if isinstance(entry, str):
                    import shlex

                    commands.append(shlex.split(entry, posix=False))
                elif isinstance(entry, (list, tuple)):
                    commands.append([str(part) for part in entry])
            if not commands:
                raise VerificationError("No verification commands were provided")
        else:
            commands = default_checks(root)
        if not commands:
            return [
                {
                    "command": [],
                    "ok": False,
                    "exit_code": None,
                    "stdout": "",
                    "stderr": "No verification command was detected for this workspace.",
                    "evidence": "not_run",
                }
            ]

        reports: list[dict[str, Any]] = []
        for argv in commands:
            target = " ".join(argv)
            broker.require(Action.COMMAND, target, "Verification check")
            result = run_command(
                argv,
                cwd=root,
                timeout_seconds=self.timeout_seconds,
                max_output_chars=48 * 1024,
            )
            reports.append(
                {
                    "command": argv,
                    "ok": result.ok,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "duration_seconds": round(result.duration_seconds, 3),
                    "evidence": "observed",
                    "provenance": "verification_engine",
                }
            )
        return reports
