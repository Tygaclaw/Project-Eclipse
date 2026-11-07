"""Streaming OpenAI-compatible chat client shared by inference adapters.

Implemented on the standard library only. Server-sent events are parsed
incrementally, tool-call fragments are assembled, and cancellation closes the
response so a Stop request takes effect promptly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import threading
import time
from typing import Any, Iterator, Mapping, Sequence
from urllib import error as urlerror
from urllib import request as urlrequest

DEFAULT_TIMEOUT_SECONDS = 300.0


class ChatError(Exception):
    """Base class for chat transport failures."""


class ChatCancelled(ChatError):
    """The caller cancelled the generation."""


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: tuple["ToolCall", ...] = ()

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        if self.name:
            payload["name"] = self.name
        if self.tool_calls:
            payload["tool_calls"] = [call.to_payload() for call in self.tool_calls]
        return payload


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: str
    raw_arguments: Any = None

    def arguments_dict(self) -> dict[str, Any]:
        if isinstance(self.raw_arguments, Mapping):
            return dict(self.raw_arguments)
        try:
            parsed = json.loads(self.arguments or "{}")
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.arguments or "{}"},
        }


@dataclass(slots=True)
class StreamChunk:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    timings: dict[str, Any] = field(default_factory=dict)
    done: bool = False


class CancellationToken:
    """A small cancellable flag safe to share between threads."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise ChatCancelled("Generation cancelled")


def _normalise_base_url(base_url: str) -> str:
    cleaned = base_url.strip().rstrip("/")
    if not cleaned:
        raise ChatError("An endpoint URL is required")
    if cleaned.endswith("/v1"):
        return cleaned
    return cleaned + "/v1"


def _iter_sse(response: Any, cancel: CancellationToken | None) -> Iterator[dict[str, Any]]:
    while True:
        if cancel is not None:
            cancel.raise_if_cancelled()
        line = response.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="replace").strip()
        if not text or text.startswith(":"):
            continue
        if not text.startswith("data:"):
            continue
        data = text[5:].strip()
        if data == "[DONE]":
            break
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            yield payload


class OpenAICompatibleClient:
    """One OpenAI-compatible chat endpoint with real streaming."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        model: str = "",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        self.base_url = _normalise_base_url(base_url)
        self.model = model
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self._api_key = api_key or ""
        self._extra_headers = dict(extra_headers or {})

    def headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": "ECLIPSE/0.2",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        headers.update(self._extra_headers)
        return headers

    def list_models(self) -> list[str]:
        url = f"{self.base_url}/models"
        request = urlrequest.Request(url, headers=self.headers(), method="GET")
        try:
            with urlrequest.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read(4 * 1024 * 1024).decode("utf-8", errors="replace"))
        except (urlerror.URLError, OSError, json.JSONDecodeError) as exc:
            raise ChatError(f"Could not list models: {type(exc).__name__}") from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return []
        names = []
        for item in data:
            if isinstance(item, Mapping) and isinstance(item.get("id"), str):
                names.append(item["id"])
        return names

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[Mapping[str, Any]] | None = None,
        temperature: float | None = 0.7,
        max_tokens: int | None = 1024,
        cancel: CancellationToken | None = None,
        model: str | None = None,
        stop: Sequence[str] | None = None,
    ) -> Iterator[StreamChunk]:
        payload: dict[str, Any] = {
            "model": model or self.model or "local-model",
            "messages": [message.to_payload() for message in messages],
            "stream": True,
        }
        if tools:
            payload["tools"] = list(tools)
            payload["tool_choice"] = "auto"
        if temperature is not None:
            payload["temperature"] = float(temperature)
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
        if stop:
            payload["stop"] = list(stop)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urlrequest.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers=self.headers(),
            method="POST",
        )
        try:
            response = urlrequest.urlopen(request, timeout=self.timeout_seconds)
        except urlerror.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read(4096).decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001 - diagnostics are best effort
                detail = ""
            raise ChatError(
                f"The endpoint rejected the request (HTTP {exc.code}): {detail[:500]}"
            ) from exc
        except (urlerror.URLError, OSError) as exc:
            raise ChatError(
                f"Could not reach the inference endpoint: {type(exc).__name__}"
            ) from exc

        pending_calls: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage: dict[str, Any] = {}
        timings: dict[str, Any] = {}
        try:
            with response:
                for event in _iter_sse(response, cancel):
                    if event.get("error"):
                        raise ChatError(str(event["error"])[:500])
                    if isinstance(event.get("usage"), Mapping):
                        usage = dict(event["usage"])  # type: ignore[arg-type]
                    if isinstance(event.get("timings"), Mapping):
                        timings = dict(event["timings"])  # type: ignore[arg-type]
                    choices = event.get("choices")
                    if not isinstance(choices, list) or not choices:
                        continue
                    choice = choices[0]
                    if not isinstance(choice, Mapping):
                        continue
                    delta = choice.get("delta")
                    if not isinstance(delta, Mapping):
                        delta = {}
                    text = delta.get("content")
                    if isinstance(text, list):
                        text = "".join(
                            part.get("text", "")
                            for part in text
                            if isinstance(part, Mapping)
                        )
                    text = text if isinstance(text, str) else ""
                    raw_calls = delta.get("tool_calls")
                    if isinstance(raw_calls, list):
                        for raw in raw_calls:
                            if not isinstance(raw, Mapping):
                                continue
                            index = raw.get("index", 0)
                            if not isinstance(index, int):
                                index = 0
                            slot = pending_calls.setdefault(
                                index, {"id": "", "name": "", "arguments": ""}
                            )
                            if isinstance(raw.get("id"), str) and raw["id"]:
                                slot["id"] = raw["id"]
                            function = raw.get("function")
                            if isinstance(function, Mapping):
                                if isinstance(function.get("name"), str):
                                    slot["name"] += function["name"]
                                if isinstance(function.get("arguments"), str):
                                    slot["arguments"] += function["arguments"]
                    if isinstance(choice.get("finish_reason"), str):
                        finish_reason = choice["finish_reason"]
                    if text:
                        yield StreamChunk(text=text, finish_reason=finish_reason)
        except ChatCancelled:
            raise
        except (OSError, ValueError) as exc:
            raise ChatError(f"The stream ended unexpectedly: {type(exc).__name__}") from exc
        finally:
            if cancel is not None and cancel.cancelled:
                try:
                    response.close()
                except Exception:  # noqa: BLE001
                    pass

        calls = tuple(
            ToolCall(
                id=slot["id"] or f"call_{index}",
                name=slot["name"] or "unknown",
                arguments=slot["arguments"] or "{}",
            )
            for index, slot in sorted(pending_calls.items())
            if slot["name"]
        )
        yield StreamChunk(
            tool_calls=calls,
            finish_reason=finish_reason,
            usage=usage,
            timings=timings,
            done=True,
        )

    def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> tuple[str, StreamChunk]:
        text_parts: list[str] = []
        final = StreamChunk(done=True)
        for chunk in self.stream_chat(messages, **kwargs):
            if chunk.text:
                text_parts.append(chunk.text)
            if chunk.done:
                final = chunk
        return "".join(text_parts), final


def ping_endpoint(base_url: str, *, api_key: str | None = None, timeout: float = 5.0) -> dict[str, Any]:
    """Check reachability without generating text."""

    started = time.monotonic()
    client = OpenAICompatibleClient(base_url, api_key=api_key, timeout_seconds=timeout)
    try:
        models = client.list_models()
    except ChatError as exc:
        return {
            "reachable": False,
            "error": str(exc),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "models": [],
        }
    return {
        "reachable": True,
        "error": None,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "models": models,
    }
