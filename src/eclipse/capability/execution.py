"""Reusable multi-step tool loop used by the Agent and Capability Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Callable, Mapping, Sequence

from eclipse.runtime.client import (
    CancellationToken,
    ChatMessage,
    ToolCall,
)
from .tools import ToolResult

MAX_HISTORY_MESSAGES = 48


@dataclass(frozen=True, slots=True)
class ToolEvent:
    name: str
    arguments: dict[str, Any]
    result: ToolResult
    step: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "arguments": self.arguments,
            "step": self.step,
            "result": self.result.to_dict(),
        }


@dataclass
class LoopResult:
    text: str
    steps: int
    tool_events: list[ToolEvent] = field(default_factory=list)
    stopped_reason: str = "complete"
    messages: list[ChatMessage] = field(default_factory=list)
    repeats: int = 0

    @property
    def used_tools(self) -> bool:
        return bool(self.tool_events)


def _signature(name: str, arguments: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        encoded = str(arguments)
    return f"{name}:{encoded[:500]}"


def compact_history(messages: Sequence[ChatMessage], limit: int = MAX_HISTORY_MESSAGES) -> list[ChatMessage]:
    """Keep the system prompt and the most recent turns, noting truncation."""

    if len(messages) <= limit:
        return list(messages)
    system = [message for message in messages if message.role == "system"]
    rest = [message for message in messages if message.role != "system"]
    keep = rest[-(limit - len(system) - 1) :]
    note = ChatMessage(
        role="user",
        content="[Earlier conversation was compacted to keep the context bounded.]",
    )
    return system + [note] + keep


def run_tool_loop(
    *,
    runtime: Any,
    messages: Sequence[ChatMessage],
    tool_schemas: Sequence[Mapping[str, Any]],
    tool_caller: Callable[[str, Mapping[str, Any]], ToolResult],
    max_steps: int = 6,
    cancel: CancellationToken | None = None,
    on_delta: Callable[[str], None] | None = None,
    on_tool: Callable[[ToolEvent], None] | None = None,
    on_step: Callable[[int], None] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    loop_repeat_limit: int = 3,
) -> LoopResult:
    """Run a model with tools until it answers or the step budget is spent.

    Repeated identical tool calls are treated as a loop: the run stops with an
    honest reason instead of burning the remaining budget on the same action.
    """

    history = compact_history(list(messages))
    events: list[ToolEvent] = []
    signatures: dict[str, int] = {}
    final_text = ""
    repeats = 0
    completed = False
    steps_used = 0

    for step in range(1, max_steps + 1):
        steps_used = step
        if cancel is not None:
            cancel.raise_if_cancelled()
        if on_step is not None:
            on_step(step)
        parts: list[str] = []
        final_chunk = None
        for chunk in runtime.stream_chat(
            history,
            tools=tool_schemas or None,
            temperature=temperature,
            max_tokens=max_tokens,
            cancel=cancel,
            emit_deltas=False,
        ):
            if chunk.text:
                parts.append(chunk.text)
                if on_delta is not None:
                    on_delta(chunk.text)
            final_chunk = chunk
        text = "".join(parts)
        final_text = text
        if final_chunk is None:
            return LoopResult(
                text=text,
                steps=step,
                tool_events=events,
                stopped_reason="empty_stream",
                messages=history,
            )
        if not final_chunk.tool_calls:
            history.append(ChatMessage(role="assistant", content=text))
            completed = True
            break

        history.append(
            ChatMessage(role="assistant", content=text, tool_calls=final_chunk.tool_calls)
        )
        if on_delta is not None and text and not text.endswith("\n"):
            on_delta("\n")

        repeated_in_turn = False
        for call in final_chunk.tool_calls:
            if cancel is not None:
                cancel.raise_if_cancelled()
            arguments = call.arguments_dict()
            signature = _signature(call.name, arguments)
            signatures[signature] = signatures.get(signature, 0) + 1
            if signatures[signature] >= loop_repeat_limit:
                repeats += 1
                repeated_in_turn = True
            result = tool_caller(call.name, arguments)
            history.append(
                ChatMessage(
                    role="tool",
                    content=result.to_model_text(),
                    tool_call_id=call.id,
                    name=call.name,
                )
            )
            event = ToolEvent(name=call.name, arguments=arguments, result=result, step=step)
            events.append(event)
            if on_tool is not None:
                on_tool(event)
        history = compact_history(history)
        if repeated_in_turn:
            return LoopResult(
                text=final_text,
                steps=step,
                tool_events=events,
                stopped_reason="loop_detected",
                messages=history,
                repeats=repeats,
            )

    if not completed:
        return LoopResult(
            text=final_text,
            steps=max_steps,
            tool_events=events,
            stopped_reason="max_steps",
            messages=history,
            repeats=repeats,
        )
    return LoopResult(
        text=final_text,
        steps=steps_used,
        tool_events=events,
        stopped_reason="complete",
        messages=history,
        repeats=repeats,
    )


def tool_calls_as_dicts(calls: Sequence[ToolCall]) -> list[dict[str, Any]]:
    return [call.to_payload() for call in calls]
