"""Task-scoped tool registry with a real permission boundary.

Tools never receive raw shell strings, never leave the approved workspace, and
never write without a broker approval. Output is bounded so a huge file or log
cannot silently consume the whole context window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, Sequence

from eclipse.core.security import (
    Action,
    ApprovalDenied,
    ApprovalPending,
    CommandResult,
    PermissionBroker,
    SecurityError,
    split_command,
)
from .research import MAX_FILE_BYTES, _iter_text_files

MAX_TOOL_OUTPUT = 32 * 1024
MAX_SEARCH_RESULTS = 20


@dataclass(frozen=True, slots=True)
class ToolResult:
    tool: str
    ok: bool
    output: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_seconds: float = 0.0

    def to_model_text(self) -> str:
        payload = {
            "ok": self.ok,
            "output": self.output,
        }
        if self.error:
            payload["error"] = self.error
        return json.dumps(payload, ensure_ascii=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "ok": self.ok,
            "output": self.output,
            "data": self.data,
            "error": self.error,
            "duration_seconds": round(self.duration_seconds, 3),
        }


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    action: str = "read"
    handler: str = ""
    requires_workspace: bool = False

    def to_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="list_dir",
        description="List files and folders inside the approved workspace.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative directory, default ."}},
            "required": [],
            "additionalProperties": False,
        },
        action="read",
    ),
    ToolSpec(
        name="read_file",
        description="Read a UTF-8 text file inside the approved workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "max_bytes": {"type": "integer", "minimum": 1, "maximum": 262144},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        action="read",
    ),
    ToolSpec(
        name="search_text",
        description="Search text files in the workspace for a literal or regular expression.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "path": {"type": "string", "description": "Relative directory to search, default ."},
                "regex": {"type": "boolean", "default": False},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        action="read",
    ),
    ToolSpec(
        name="write_file",
        description=(
            "Create or replace a text file inside the approved workspace. "
            "Requires explicit user approval."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        action="write",
    ),
    ToolSpec(
        name="run_command",
        description=(
            "Run an approved executable with arguments in the workspace. "
            "No shell operators, bounded output and a timeout apply. Requires approval."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Argument list, e.g. ['python','-m','unittest','discover','-s','tests']",
                }
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        action="command",
    ),
    ToolSpec(
        name="verify",
        description="Run the workspace's compile and test checks and return raw output.",
        parameters={
            "type": "object",
            "properties": {"checks": {"type": "array", "items": {"type": "string"}}},
            "required": [],
            "additionalProperties": False,
        },
        action="command",
    ),
    ToolSpec(
        name="knowledge_search",
        description="Search the approved Obsidian knowledge vault for relevant notes.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        action="read",
    ),
    ToolSpec(
        name="correction_lookup",
        description="Look up verified corrections and open candidate lessons for a problem.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        action="read",
    ),
)


class ToolRegistry:
    """Execute tools by name under one workspace and permission broker."""

    def __init__(
        self,
        broker: PermissionBroker,
        workspace_root: str | os.PathLike[str] | None,
        *,
        store: Any | None = None,
        knowledge: Any | None = None,
        verifier: Any | None = None,
        events: Any | None = None,
        max_read_bytes: int = MAX_FILE_BYTES,
        max_output_chars: int = MAX_TOOL_OUTPUT,
    ) -> None:
        self.broker = broker
        self.workspace_root = Path(workspace_root).expanduser().resolve() if workspace_root else None
        self.store = store
        self.knowledge = knowledge
        self.verifier = verifier
        self.events = events
        self.max_read_bytes = max_read_bytes
        self.max_output_chars = max_output_chars

    def schemas(self, allowed: Sequence[str] | None = None) -> list[dict[str, Any]]:
        names = set(allowed) if allowed is not None else {spec.name for spec in TOOL_SPECS}
        schemas = []
        for spec in TOOL_SPECS:
            if spec.name not in names:
                continue
            if spec.name == "knowledge_search" and self.knowledge is None:
                continue
            if spec.name == "verify" and self.verifier is None:
                continue
            if spec.name == "correction_lookup" and self.store is None:
                continue
            if spec.requires_workspace and self.workspace_root is None:
                continue
            schemas.append(spec.to_openai_schema())
        return schemas

    def call(self, name: str, arguments: Mapping[str, Any] | None) -> ToolResult:
        started = time.monotonic()
        args = dict(arguments or {})
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return ToolResult(
                tool=name,
                ok=False,
                output="",
                error=f"Unknown or unavailable tool: {name}",
            )
        try:
            result = handler(args)  # type: ignore[misc]
        except ApprovalDenied as exc:
            result = ToolResult(tool=name, ok=False, output="", error=str(exc))
        except ApprovalPending as exc:
            result = ToolResult(
                tool=name,
                ok=False,
                output="",
                error=f"Approval required before this action can run: {exc}",
            )
        except (SecurityError, OSError, ValueError) as exc:
            result = ToolResult(tool=name, ok=False, output="", error=str(exc))
        except Exception as exc:  # noqa: BLE001 - tools must report, not crash a run
            result = ToolResult(
                tool=name,
                ok=False,
                output="",
                error=f"{type(exc).__name__}: {exc}",
            )
        duration = time.monotonic() - started
        final = ToolResult(
            tool=name,
            ok=result.ok,
            output=_clip(result.output, self.max_output_chars),
            data=result.data,
            error=result.error,
            duration_seconds=duration,
        )
        if self.events is not None:
            self.events.emit("tool.result", **final.to_dict())
        return final

    # -- path helpers ----------------------------------------------------

    def _resolve(self, value: Any) -> Path:
        if self.workspace_root is None:
            raise SecurityError("No workspace is attached to this task")
        relative = value if isinstance(value, str) and value.strip() else "."
        return self.broker.resolve(self.workspace_root / relative)

    # -- tools -----------------------------------------------------------

    def _tool_list_dir(self, args: Mapping[str, Any]) -> ToolResult:
        directory = self._resolve(args.get("path", "."))
        if not directory.is_dir():
            return ToolResult("list_dir", False, "", error="Not a directory")
        entries = []
        for path in sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            if path.name.startswith(".") and path.name not in {".github", ".eclipse"}:
                continue
            try:
                size = path.stat().st_size if path.is_file() else None
            except OSError:
                size = None
            entries.append(
                {
                    "name": path.name,
                    "type": "dir" if path.is_dir() else "file",
                    "size_bytes": size,
                }
            )
            if len(entries) >= 300:
                break
        return ToolResult(
            "list_dir",
            True,
            json.dumps(entries, ensure_ascii=False, indent=2),
            data={"entries": entries, "path": args.get("path", ".")},
        )

    def _tool_read_file(self, args: Mapping[str, Any]) -> ToolResult:
        path = self._resolve(args.get("path"))
        if not path.is_file():
            return ToolResult("read_file", False, "", error="File does not exist")
        requested = args.get("max_bytes", self.max_read_bytes)
        limit = min(int(requested) if isinstance(requested, int) else self.max_read_bytes, self.max_read_bytes)
        with path.open("rb") as handle:
            data = handle.read(limit + 1)
        truncated = len(data) > limit
        text = data[:limit].decode("utf-8", errors="replace")
        relative = str(path.relative_to(self.workspace_root)) if self.workspace_root else path.name
        return ToolResult(
            "read_file",
            True,
            text,
            data={
                "path": relative,
                "bytes": len(data[:limit]),
                "truncated": truncated or path.stat().st_size > limit,
            },
        )

    def _tool_search_text(self, args: Mapping[str, Any]) -> ToolResult:
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            return ToolResult("search_text", False, "", error="A query is required")
        base = self._resolve(args.get("path", "."))
        use_regex = bool(args.get("regex"))
        try:
            pattern = re.compile(query if use_regex else re.escape(query), re.IGNORECASE)
        except re.error as exc:
            return ToolResult("search_text", False, "", error=f"Invalid regular expression: {exc}")
        matches: list[dict[str, Any]] = []
        scanned = 0
        for path in _iter_text_files(base):
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for number, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    try:
                        relative = str(path.relative_to(self.workspace_root)) if self.workspace_root else path.name
                    except ValueError:
                        relative = path.name
                    matches.append(
                        {"path": relative, "line": number, "text": line.strip()[:300], "provenance": "workspace_scan"}
                    )
                    if len(matches) >= MAX_SEARCH_RESULTS:
                        break
            if len(matches) >= MAX_SEARCH_RESULTS:
                break
        return ToolResult(
            "search_text",
            True,
            json.dumps(matches, ensure_ascii=False, indent=2) if matches else "No matches found.",
            data={"matches": matches, "scanned_files": scanned},
        )

    def _tool_write_file(self, args: Mapping[str, Any]) -> ToolResult:
        path = self._resolve(args.get("path"))
        content = args.get("content")
        if not isinstance(content, str):
            return ToolResult("write_file", False, "", error="content must be a string")
        encoded = content.encode("utf-8")
        if len(encoded) > self.broker.max_write_bytes:
            return ToolResult(
                "write_file",
                False,
                "",
                error=f"Content exceeds the {self.broker.max_write_bytes:,}-byte write limit",
            )
        relative = str(path.relative_to(self.workspace_root)) if self.workspace_root else path.name
        if any(part == ".git" for part in path.parts):
            return ToolResult("write_file", False, "", error="Refusing to modify Git internals")
        existed = path.exists()
        self.broker.require(
            Action.WRITE,
            relative,
            f"{'Replace' if existed else 'Create'} {relative} ({len(encoded):,} bytes)",
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".eclipse-tmp")
        temporary.write_bytes(encoded)
        os.replace(temporary, path)
        return ToolResult(
            "write_file",
            True,
            f"Wrote {len(encoded):,} bytes to {relative}",
            data={"path": relative, "bytes": len(encoded), "created": not existed},
        )

    def _tool_run_command(self, args: Mapping[str, Any]) -> ToolResult:
        if self.workspace_root is None:
            raise SecurityError("No workspace is attached to this task")
        argv = split_command(args.get("command"))
        self.broker.require(Action.COMMAND, " ".join(argv), "Run a command in the project workspace")
        result = run_command(argv, cwd=self.workspace_root, timeout_seconds=self.broker.command_timeout_seconds)
        text = _format_command(result)
        return ToolResult(
            "run_command",
            result.ok,
            text,
            data=result.to_dict(),
            error=None if result.ok else f"Command exited with {result.exit_code}",
        )

    def _tool_verify(self, args: Mapping[str, Any]) -> ToolResult:
        if self.verifier is None:
            return ToolResult("verify", False, "", error="No verification engine is configured")
        checks = args.get("checks")
        reports = self.verifier.run(
            checks=[str(item) for item in checks] if isinstance(checks, list) else None,
            broker=self.broker,
            workspace_root=self.workspace_root,
        )
        ok = bool(reports) and all(report.get("ok") for report in reports)
        return ToolResult(
            "verify",
            ok,
            json.dumps(reports, ensure_ascii=False, indent=2),
            data={"checks": reports},
            error=None if ok else "One or more verification checks failed",
        )

    def _tool_knowledge_search(self, args: Mapping[str, Any]) -> ToolResult:
        if self.knowledge is None:
            return ToolResult("knowledge_search", False, "", error="No knowledge vault is connected")
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            return ToolResult("knowledge_search", False, "", error="A query is required")
        hits = self.knowledge.search(query, limit=8)
        return ToolResult(
            "knowledge_search",
            True,
            json.dumps(hits, ensure_ascii=False, indent=2) if hits else "No notes matched.",
            data={"hits": hits},
        )

    def _tool_correction_lookup(self, args: Mapping[str, Any]) -> ToolResult:
        if self.store is None:
            return ToolResult("correction_lookup", False, "", error="No correction memory is connected")
        query = str(args.get("query") or "")
        rows = self.store.list_corrections()
        terms = [term for term in re.findall(r"[a-zA-Z0-9_]{3,}", query.lower())]
        scored = []
        for row in rows:
            haystack = " ".join(
                str(row.get(key) or "")
                for key in ("title", "issue", "root_cause", "fix", "scope")
            ).lower()
            score = sum(haystack.count(term) for term in terms) if terms else 0
            if score or not terms:
                scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], item[1].get("created_at") or ""))
        hits = [
            {
                "id": row["id"],
                "title": row["title"],
                "status": row["status"],
                "root_cause": row["root_cause"],
                "fix": row["fix"],
                "scope": row["scope"],
                "evidence": row["evidence"],
            }
            for _, row in scored[:8]
        ]
        return ToolResult(
            "correction_lookup",
            True,
            json.dumps(hits, ensure_ascii=False, indent=2) if hits else "No corrections matched.",
            data={"hits": hits},
        )


def run_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    max_output_chars: int = MAX_TOOL_OUTPUT,
) -> CommandResult:
    started = time.monotonic()
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.lower().startswith(("eclipse_api", "openai", "anthropic"))
        and "KEY" not in key.upper()
        and "TOKEN" not in key.upper()
        and "SECRET" not in key.upper()
    }
    environment["PYTHONIOENCODING"] = "utf-8"
    try:
        completed = subprocess.run(
            list(argv),
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=timeout_seconds,
            env=environment,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            argv=list(argv),
            exit_code=None,
            stdout=_decode(exc.stdout, max_output_chars),
            stderr=f"Command timed out after {timeout_seconds}s",
            timed_out=True,
            duration_seconds=time.monotonic() - started,
        )
    except OSError as exc:
        return CommandResult(
            argv=list(argv),
            exit_code=None,
            stdout="",
            stderr=f"{type(exc).__name__}: {exc}",
            duration_seconds=time.monotonic() - started,
        )
    stdout = _decode(completed.stdout, max_output_chars)
    stderr = _decode(completed.stderr, max_output_chars)
    truncated = len(completed.stdout) + len(completed.stderr) > max_output_chars
    return CommandResult(
        argv=list(argv),
        exit_code=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        truncated=truncated,
        duration_seconds=time.monotonic() - started,
    )


def _decode(raw: bytes | None, limit: int) -> str:
    if not raw:
        return ""
    text = raw.decode("utf-8", errors="replace")
    if len(text) > limit:
        return text[:line_break(text, limit)] + f"\n... [truncated {len(text) - limit:,} characters]"
    return text


def line_break(text: str, limit: int) -> int:
    cut = text.rfind("\n", 0, limit)
    return cut if cut > limit // 2 else limit


def _format_command(result: CommandResult) -> str:
    header = f"$ {' '.join(result.argv)}\nexit code: {result.exit_code}"
    if result.timed_out:
        header += " (timed out)"
    parts = [header]
    if result.stdout:
        parts.append("stdout:\n" + result.stdout)
    if result.stderr:
        parts.append("stderr:\n" + result.stderr)
    if result.truncated:
        parts.append("[output truncated]")
    return "\n".join(parts)


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:line_break(text, limit)] + f"\n... [truncated {len(text) - limit:,} characters]"
