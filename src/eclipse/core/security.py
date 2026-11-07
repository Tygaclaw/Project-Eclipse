"""Permission brokering, path scoping and secret redaction.

Every file or command action proposed by a model passes through this module.
Paths are resolved before use so ``..`` traversal, symlinks and Windows drive
changes cannot escape an approved workspace root. Approval is explicit: the
broker never silently upgrades a decision, and the default answer is deny.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import os
from pathlib import Path
import re
import shlex
import threading
from typing import Any, Callable, Iterable, Sequence

MAX_READ_BYTES = 512 * 1024
MAX_WRITE_BYTES = 1024 * 1024
ALLOWED_COMMAND_PREFIXES = (
    "python",
    "python3",
    "py",
    "pytest",
    "git",
    "rg",
    "ls",
    "dir",
    "cat",
    "type",
    "node",
    "npm",
    "npx",
    "echo",
)


class SecurityError(Exception):
    """An action was refused by the security boundary."""


class PathEscapeError(SecurityError):
    """A requested path resolves outside every approved root."""


class ApprovalDenied(SecurityError):
    """The user (or policy) refused a consequential action."""


class ApprovalPending(SecurityError):
    """A consequential action needs approval but no approver is available."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def resolve_within(root: str | os.PathLike[str], candidate: str | os.PathLike[str]) -> Path:
    """Resolve ``candidate`` and require it to stay inside ``root``.

    The check runs on the fully resolved paths, so a symlink or hard-linked
    directory that points outside the workspace is rejected rather than
    followed. Non-existent paths are resolved through their existing parent.
    """

    base = Path(root).expanduser().resolve(strict=False)
    raw = Path(candidate).expanduser()
    joined = raw if raw.is_absolute() else base / raw
    resolved = joined.resolve(strict=False)
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise PathEscapeError(
            f"Path is outside the approved workspace: {resolved.name or '<root>'}"
        ) from exc
    return resolved


def contains_secret(text: str) -> bool:
    return _SECRET_PATTERN.search(text or "") is not None


_SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_\-]{12,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|AIza[0-9A-Za-z_\-]{20,}"
    r"|(?i:bearer)\s+[A-Za-z0-9._\-]{16,}"
    r"|(?i:api[_\-]?key)\s*[=:]\s*[^\s\"']{8,})"
)


def redact(text: str) -> str:
    """Remove likely credentials from log and diagnostic text."""

    if not text:
        return text
    return _SECRET_PATTERN.sub("[redacted-credential]", text)


class Action(str, Enum):
    READ = "read"
    WRITE = "write"
    COMMAND = "command"
    NETWORK = "network"


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class PermissionRecord:
    action: str
    target: str
    decision: str
    reason: str
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, str]:
        return {
            "action": self.action,
            "target": self.target,
            "decision": self.decision,
            "reason": self.reason,
            "created_at": self.created_at,
        }


Approver = Callable[[str, str, str], bool]


def _no_approver(action: str, target: str, detail: str) -> bool:
    raise ApprovalPending(
        f"{action} requires approval and no approver is connected"
    )


class PermissionBroker:
    """Policy plus an approval callback for consequential actions."""

    def __init__(
        self,
        roots: Iterable[str | os.PathLike[str]],
        *,
        allow_write: bool = True,
        allow_commands: bool = True,
        allow_network: bool = False,
        approver: Approver | None = None,
        command_timeout_seconds: int = 120,
        max_read_bytes: int = MAX_READ_BYTES,
        max_write_bytes: int = MAX_WRITE_BYTES,
    ) -> None:
        resolved = [Path(root).expanduser().resolve(strict=False) for root in roots]
        if not resolved:
            raise ValueError("At least one workspace root is required")
        self._roots = tuple(dict.fromkeys(resolved))
        self._allow_write = bool(allow_write)
        self._allow_commands = bool(allow_commands)
        self._allow_network = bool(allow_network)
        self._approver = approver or _no_approver
        self.command_timeout_seconds = max(1, int(command_timeout_seconds))
        self.max_read_bytes = max(1, int(max_read_bytes))
        self.max_write_bytes = max(1, int(max_write_bytes))
        self._lock = threading.RLock()
        self._records: list[PermissionRecord] = []
        self._approved: set[tuple[str, str]] = set()

    @property
    def roots(self) -> tuple[Path, ...]:
        return self._roots

    def set_approver(self, approver: Approver | None) -> None:
        with self._lock:
            self._approver = approver or _no_approver

    def records(self) -> list[PermissionRecord]:
        with self._lock:
            return list(self._records)

    def resolve(self, path: str | os.PathLike[str]) -> Path:
        errors: list[str] = []
        for root in self._roots:
            try:
                return resolve_within(root, path)
            except PathEscapeError as exc:
                errors.append(str(exc))
        raise PathEscapeError(
            "Path is outside every approved workspace root: "
            + (str(path)[:200] if path else "<empty>")
        )

    def _record(self, action: str, target: str, decision: str, reason: str) -> None:
        with self._lock:
            self._records.append(
                PermissionRecord(action=action, target=target[:400], decision=decision, reason=reason)
            )
            if len(self._records) > 500:
                del self._records[:200]

    def check(self, action: Action, target: str, detail: str = "") -> Decision:
        if action is Action.READ:
            return Decision.ALLOW
        if action is Action.WRITE:
            return Decision.ASK if self._allow_write else Decision.DENY
        if action is Action.COMMAND:
            return Decision.ASK if self._allow_commands else Decision.DENY
        if action is Action.NETWORK:
            return Decision.ASK if self._allow_network else Decision.DENY
        return Decision.DENY

    def require(
        self,
        action: Action,
        target: str,
        detail: str = "",
    ) -> None:
        """Raise unless this exact action/target is allowed now."""

        decision = self.check(action, target, detail)
        if decision is Decision.ALLOW:
            self._record(action.value, target, "allow", detail or "read-only access")
            return
        if decision is Decision.DENY:
            self._record(action.value, target, "deny", detail or "blocked by policy")
            raise ApprovalDenied(
                f"{action.value} is disabled by the current permission policy"
            )

        key = (action.value, target)
        with self._lock:
            already = key in self._approved
        if already:
            self._record(action.value, target, "allow", "previously approved")
            return

        try:
            approved = bool(self._approver(action.value, target, detail))
        except ApprovalPending:
            self._record(action.value, target, "pending", detail or "no approver")
            raise
        except Exception as exc:  # noqa: BLE001 - approver failure means deny
            self._record(action.value, target, "deny", f"approver error: {type(exc).__name__}")
            raise ApprovalDenied(
                "The approval handler failed, so the action was refused"
            ) from exc
        if not approved:
            self._record(action.value, target, "deny", detail or "user declined")
            raise ApprovalDenied(f"The user declined {action.value} on {target}")
        with self._lock:
            self._approved.add(key)
        self._record(action.value, target, "allow", detail or "user approved")

    def reset_approvals(self) -> None:
        with self._lock:
            self._approved.clear()


def validate_command(argv: Sequence[str]) -> list[str]:
    """Validate a command without a shell and return its argument list."""

    if isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence):
        raise SecurityError("Commands must be an argument list, never a shell string")
    cleaned = [str(part) for part in argv]
    if not cleaned or not cleaned[0].strip():
        raise SecurityError("Command is empty")
    if any("\x00" in part for part in cleaned):
        raise SecurityError("Command contains a NUL byte")
    if any(token in part for part in cleaned for token in ("|", "&&", ";", ">", "<", "`", "$(")):
        raise SecurityError("Shell operators are not supported in commands")
    executable = Path(cleaned[0]).name.lower()
    if executable not in ALLOWED_COMMAND_PREFIXES:
        raise SecurityError(f"Executable is not on the approved list: {executable}")
    return cleaned


def split_command(command: str | Sequence[str]) -> list[str]:
    if isinstance(command, str):
        if any(token in command for token in ("|", "&&", ";", ">", "<", "`", "$(")):
            raise SecurityError("Shell operators are not supported in commands")
        return validate_command(shlex.split(command, posix=os.name != "nt"))
    return validate_command(command)


@dataclass(frozen=True, slots=True)
class CommandResult:
    argv: list[str]
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    truncated: bool = False
    duration_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def to_dict(self) -> dict[str, Any]:
        return {
            "argv": list(self.argv),
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "truncated": self.truncated,
            "duration_seconds": round(self.duration_seconds, 3),
            "ok": self.ok,
        }
