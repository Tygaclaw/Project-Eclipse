"""The ECLIPSE Agent: real conversations on the shared runtime.

The agent is a normal chat experience with conversation history, model
selection, attachments, scoped context, tool use, explicit approvals and a
working Stop. It shares the runtime, memory, knowledge and permission systems
used by the other two workspaces.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import threading
from typing import Any, Callable, Mapping, Sequence

from eclipse.core.config import AppPaths
from eclipse.core.events import EventBus
from eclipse.core.security import PermissionBroker
from eclipse.core.storage import Store
from eclipse.runtime.client import CancellationToken, ChatError, ChatMessage
from eclipse.capability.execution import LoopResult, ToolEvent, run_tool_loop
from eclipse.capability.knowledge import KnowledgeBase
from eclipse.capability.memory import CorrectionMemory
from eclipse.capability.research import list_workspace_files
from eclipse.capability.tools import ToolRegistry
from eclipse.capability.verification import VerificationEngine

TEXT_SUFFIXES = {
    ".txt",
    ".md",
    ".py",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".csv",
    ".log",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".sql",
    ".sh",
    ".ps1",
    ".c",
    ".cpp",
    ".h",
    ".java",
    ".cs",
    ".rs",
    ".go",
}
MAX_ATTACHMENT_BYTES = 512 * 1024
AGENT_TOOLS = (
    "list_dir",
    "read_file",
    "search_text",
    "write_file",
    "run_command",
    "verify",
    "knowledge_search",
    "correction_lookup",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AgentError(Exception):
    """Base class for expected agent failures."""


class AgentService:
    """Conversation, context and tool orchestration for the Agent workspace."""

    def __init__(
        self,
        store: Store,
        runtime: Any,
        paths: AppPaths,
        *,
        events: EventBus | None = None,
        knowledge: KnowledgeBase | None = None,
        memory: CorrectionMemory | None = None,
        workspace_root: str | os.PathLike[str] | None = None,
        verifier: VerificationEngine | None = None,
    ) -> None:
        self.store = store
        self.runtime = runtime
        self.paths = paths
        self.events = events or EventBus()
        self.knowledge = knowledge
        self.memory = memory or CorrectionMemory(store)
        self.workspace_root = str(workspace_root) if workspace_root else None
        self.verifier = verifier or VerificationEngine()
        self._lock = threading.RLock()

    def set_workspace(self, root: str | os.PathLike[str] | None) -> None:
        self.workspace_root = str(root) if root else None

    # -- conversations ---------------------------------------------------

    def new_conversation(self, *, title: str = "New conversation", model_id: str | None = None) -> dict[str, Any]:
        conversation = self.store.create_conversation(title=title, model_id=model_id)
        self.events.emit("agent.conversation_created", conversation_id=conversation["id"])
        return conversation

    def conversations(self, query: str | None = None) -> list[dict[str, Any]]:
        return self.store.list_conversations(query)

    def conversation(self, conversation_id: str) -> dict[str, Any]:
        conversation = self.store.get_conversation(conversation_id)
        if conversation is None:
            raise AgentError("Unknown conversation")
        conversation["messages"] = self.store.list_messages(conversation_id)
        conversation["attachments"] = self.store.list_attachments(conversation_id)
        return conversation

    def delete_conversation(self, conversation_id: str) -> None:
        self.store.delete_conversation(conversation_id)
        self.events.emit("agent.conversation_deleted", conversation_id=conversation_id)

    def rename(self, conversation_id: str, title: str) -> None:
        if not title.strip():
            raise AgentError("A conversation title cannot be empty")
        self.store.update_conversation(conversation_id, title=title.strip()[:200])

    def set_model(self, conversation_id: str, model_id: str | None) -> None:
        self.store.update_conversation(conversation_id, model_id=model_id)

    def attach_file(self, conversation_id: str, path: str | os.PathLike[str]) -> dict[str, Any]:
        source = Path(path).expanduser().resolve()
        if not source.is_file():
            raise AgentError("The attachment does not exist")
        size = source.stat().st_size
        if size > 8 * 1024 * 1024:
            raise AgentError("Attachments above 8 MiB are not supported")
        directory = self.paths.data_dir / "attachments" / conversation_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / source.name
        if target.exists():
            target = directory / f"{source.stem}-{datetime.now().strftime('%H%M%S')}{source.suffix}"
        shutil.copy2(source, target)
        attachment = self.store.add_attachment(
            conversation_id=conversation_id,
            name=source.name,
            path=str(target),
            size_bytes=size,
            mime=_mime_for(source),
        )
        payload = {key: value for key, value in attachment.items() if key != "conversation_id"}
        self.events.emit("agent.attachment", conversation_id=conversation_id, **payload)
        return attachment

    # -- sending ---------------------------------------------------------

    def send(
        self,
        conversation_id: str,
        text: str,
        *,
        cancel: CancellationToken | None = None,
        approver: Callable[[str, str, str], bool] | None = None,
        emit_deltas: bool = True,
    ) -> dict[str, Any]:
        conversation = self.store.get_conversation(conversation_id)
        if conversation is None:
            raise AgentError("Unknown conversation")
        if not text.strip():
            raise AgentError("A message is required")
        cancel = cancel or CancellationToken()
        pending_attachments = [
            item for item in self.store.list_attachments(conversation_id) if not item.get("message_id")
        ]
        user_content = self._compose_user_message(text, pending_attachments)
        user_message = self.store.add_message(conversation_id, "user", text.strip())
        self.store.claim_attachments(conversation_id, user_message["id"])
        if conversation["title"] in {"New conversation", ""}:
            self.store.update_conversation(
                conversation_id, title=text.strip().splitlines()[0][:70]
            )

        history = self.store.list_messages(conversation_id, limit=40)
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=self._system_prompt(text, conversation))
        ]
        for message in history:
            role = message["role"]
            if role not in {"user", "assistant"}:
                continue
            content = message["content"]
            if message["id"] == user_message["id"]:
                content = user_content
            messages.append(ChatMessage(role=role, content=content))

        tools = self._tool_registry(approver)
        events = self.events
        tool_events: list[dict[str, Any]] = []

        def on_tool(event: ToolEvent) -> None:
            payload = event.to_dict()
            tool_events.append(payload)
            events.emit("agent.tool", conversation_id=conversation_id, **payload)

        def on_delta(delta: str) -> None:
            if emit_deltas:
                events.emit("agent.delta", conversation_id=conversation_id, text=delta)

        started = utc_now_iso()
        try:
            assert tools is not None
            loop = run_tool_loop(
                runtime=self.runtime,
                messages=messages,
                tool_schemas=tools.schemas(AGENT_TOOLS),
                tool_caller=tools.call,
                max_steps=int(self.runtime.settings.get("agent_max_steps", 6)),
                cancel=cancel,
                on_delta=on_delta,
                on_tool=on_tool,
            )
        except ChatError:
            self.store.add_message(
                conversation_id,
                "assistant",
                "I could not complete that request because the inference runtime is not available. "
                "Start a model in Model Intelligence and try again.",
                metadata={"error": True},
            )
            raise
        answer = loop.text.strip() or "(The model returned no text.)"
        metadata = {
            "steps": loop.steps,
            "stopped_reason": loop.stopped_reason,
            "tool_events": tool_events,
            "started_at": started,
            "finished_at": utc_now_iso(),
            "cancelled": cancel.cancelled,
        }
        message = self.store.add_message(
            conversation_id, "assistant", answer, metadata=metadata
        )
        self.events.emit(
            "agent.completed",
            conversation_id=conversation_id,
            message_id=message["id"],
            text=answer,
            stopped_reason=loop.stopped_reason,
        )
        return {
            "message": message,
            "conversation_id": conversation_id,
            "tool_events": tool_events,
            "stopped_reason": loop.stopped_reason,
            "steps": loop.steps,
        }

    # -- internals -------------------------------------------------------

    def _tool_registry(self, approver: Any) -> ToolRegistry:
        workspace = self.workspace_root
        if not workspace or not Path(workspace).exists():
            workspace = None
        roots = [workspace] if workspace else []
        if not roots:
            # Knowledge-only tools still work without a project workspace.
            broker = PermissionBroker(
                [self.paths.data_dir],
                allow_write=False,
                allow_commands=False,
                approver=approver,
            )
        else:
            broker = PermissionBroker(
                roots,
                allow_write=True,
                allow_commands=True,
                approver=approver,
                command_timeout_seconds=int(self.runtime.settings.get("command_timeout_seconds", 120)),
            )
        return ToolRegistry(
            broker,
            workspace,
            store=self.store,
            knowledge=self.knowledge,
            verifier=self.verifier,
            events=self.events,
        )

    def _compose_user_message(self, text: str, attachments: Sequence[Mapping[str, Any]]) -> str:
        if not attachments:
            return text
        blocks = [text]
        for attachment in attachments:
            path = Path(str(attachment.get("path") or ""))
            block = f"\n\n[Attachment: {attachment.get('name')}]"
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                try:
                    data = path.read_bytes()[:MAX_ATTACHMENT_BYTES]
                    content = data.decode("utf-8", errors="replace")
                    block += f"\n```\n{content}\n```"
                except OSError:
                    block += "\n(Unreadable attachment.)"
            else:
                block += (
                    "\n(The file is attached for reference. This model path cannot read "
                    "binary or image contents; only text attachments are included.)"
                )
            blocks.append(block)
        return "".join(blocks)

    def _system_prompt(self, text: str, conversation: Mapping[str, Any]) -> str:
        model_name = self.runtime.status.model_name or "no model loaded"
        workspace = self.workspace_root or "none attached"
        lines = [
            "You are ECLIPSE, a Windows-first personal AI assistant.",
            "Be direct, practical and honest. Never claim an action succeeded unless a tool returned that result.",
            f"Active model: {model_name}.",
            f"Approved project workspace: {workspace}.",
            "",
            "You can use tools for project files, commands, verification, knowledge and corrections.",
            "Read before you write. Keep changes scoped. If the user denies a tool, choose another approach.",
            "When tools are not available or the request is conversational, answer directly.",
        ]
        if bool(self.runtime.settings.get("memory_enabled", True)):
            block = self.memory.context_block(text)
            if block:
                lines.extend(["", block])
        if self.knowledge is not None and bool(self.runtime.settings.get("knowledge_enabled", True)):
            block = self.knowledge.context_block(text)
            if block:
                lines.extend(["", block])
        return "\n".join(lines)


def _mime_for(path: Path) -> str:
    import mimetypes

    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or ""
