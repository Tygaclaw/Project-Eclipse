"""Qt bridge that turns a core approval callback into a user decision.

The core runs work on a worker thread and blocks until an answer arrives. The
bridge emits a Qt signal, the window asks the user, and the waiting thread is
released. A missing answer means deny, never allow.
"""

from __future__ import annotations

import threading
from typing import Any

from PySide6.QtCore import QObject, Signal


class ApprovalBridge(QObject):
    requested = Signal(str, str, str, object)

    def __init__(self, parent: QObject | None = None, timeout_seconds: float = 300.0) -> None:
        super().__init__(parent)
        self.timeout_seconds = timeout_seconds

    def approve(self, action: str, target: str, detail: str) -> bool:
        holder: dict[str, Any] = {"event": threading.Event(), "allowed": False}
        self.requested.emit(action, target, detail, holder)
        if not holder["event"].wait(self.timeout_seconds):
            return False
        return bool(holder["allowed"])

    @staticmethod
    def resolve(holder: Any, allowed: bool) -> None:
        if not isinstance(holder, dict):
            return
        holder["allowed"] = bool(allowed)
        event = holder.get("event")
        if isinstance(event, threading.Event):
            event.set()
