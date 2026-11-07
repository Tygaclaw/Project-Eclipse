"""A small thread-safe event bus shared by the Core and the desktop shell.

The bus carries progress, tool, lifecycle and telemetry events. Subscribers
never change core behaviour: a failing or slow listener cannot break a run.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
from typing import Any, Callable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class Event:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)


Handler = Callable[[Event], None]


class EventBus:
    """Named events with optional catch-all subscribers and bounded history."""

    def __init__(self, history_limit: int = 500) -> None:
        if history_limit < 0:
            raise ValueError("history_limit cannot be negative")
        self._lock = threading.RLock()
        self._handlers: dict[str | None, list[Handler]] = {}
        self._history: deque[Event] = deque(maxlen=history_limit or 1)

    def subscribe(self, name: str | None, handler: Handler) -> Callable[[], None]:
        """Subscribe to one event name, or to every event when name is None."""

        if not callable(handler):
            raise TypeError("handler must be callable")
        with self._lock:
            self._handlers.setdefault(name, []).append(handler)

        def unsubscribe() -> None:
            with self._lock:
                handlers = self._handlers.get(name)
                if handlers and handler in handlers:
                    handlers.remove(handler)

        return unsubscribe

    def emit(self, event_name: str, /, **payload: Any) -> Event:
        event = Event(name=event_name, payload=dict(payload))
        with self._lock:
            handlers = list(self._handlers.get(event_name, ())) + list(
                self._handlers.get(None, ())
            )
            self._history.append(event)
        for handler in handlers:
            try:
                handler(event)
            except Exception:  # noqa: BLE001 - listeners must not break a run
                continue
        return event

    def history(self, name: str | None = None) -> list[Event]:
        with self._lock:
            events = list(self._history)
        if name is None:
            return events
        return [event for event in events if event.name == name]
