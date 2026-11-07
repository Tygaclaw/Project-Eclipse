"""Privacy-conscious UI interaction and application error recorder.

The recorder keeps a local JSONL trail of clicks, scrolling, navigation,
shortcuts and errors. It deliberately never records text typed into input
controls, clipboard contents, chat messages, file contents or screenshots.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import platform
import re
import sys
import threading
import traceback
import uuid
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, qInstallMessageHandler
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QTabBar,
    QTextEdit,
    QWidget,
)

from eclipse import __version__


_SECRET_PATTERNS = (
    # Match Bearer credentials before the generic key/value rule so the
    # credential following "Authorization: Bearer" cannot be left behind.
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|password|passwd|client[_ -]?secret|authorization)(\s*[:=]\s*)(?:Bearer\s+)?([^\s,;]+)"), r"\1\2[REDACTED]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"(https?://)([^/\s:@]+:[^/\s@]+@)"), r"\1[REDACTED]@"),
)


def redact_text(value: object, *, limit: int = 8_000) -> str:
    """Remove common credential formats before diagnostic text is persisted."""
    text = str(value)
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    if len(text) > limit:
        text = text[:limit] + "…[truncated]"
    return text


def _safe_details(value: Any, depth: int = 0) -> Any:
    """Convert event details to bounded JSON-safe values."""
    if depth > 4:
        return "[depth-limited]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        # Preserve useful exception/dialog detail while keeping every field bounded.
        return redact_text(value, limit=8_000)
    if isinstance(value, dict):
        return {
            str(key)[:80]: _safe_details(item, depth + 1)
            for key, item in list(value.items())[:30]
        }
    if isinstance(value, (list, tuple)):
        return [_safe_details(item, depth + 1) for item in value[:30]]
    return f"<{type(value).__name__}>"


class _DiagnosticLogHandler(logging.Handler):
    def __init__(self, recorder: "InteractionRecorder") -> None:
        super().__init__(level=logging.WARNING)
        self.recorder = recorder

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.recorder.record_error(
                "python_log",
                severity=record.levelname,
                logger=record.name,
                message=redact_text(record.getMessage(), limit=2_000),
            )
        except Exception:
            self.handleError(record)


class InteractionRecorder(QObject):
    """Capture useful UI actions and application failures in a local JSONL log."""

    MAX_FILE_BYTES = 5 * 1024 * 1024
    MAX_PARTS = 4
    MAX_LOG_FILES = 100
    MAX_TOTAL_BYTES = 100 * 1024 * 1024
    MAX_AGE_DAYS = 30

    _TEXT_INPUT_TYPES = (QLineEdit, QPlainTextEdit, QTextEdit, QAbstractSpinBox)

    def __init__(
        self,
        application: QApplication,
        logs_dir: str | os.PathLike[str],
        *,
        enabled: bool = True,
        app_version: str = __version__,
    ) -> None:
        super().__init__()
        if application is None:
            raise RuntimeError("A QApplication is required for UI diagnostics.")
        self.application = application
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = uuid.uuid4().hex
        self.started_at = datetime.now(timezone.utc)
        self._lock = threading.RLock()
        self._enabled = bool(enabled)
        self._closed = False
        self._part = 1
        self._base_name = (
            f"eclipse-ui-{self.started_at.strftime('%Y%m%d-%H%M%S')}-{self.session_id[:8]}"
        )
        self._limit_reached = False
        self._file_path = self._part_path(self._part)
        self._previous_sys_hook = sys.excepthook
        self._previous_thread_hook = getattr(threading, "excepthook", None)
        self._previous_qt_handler = None
        self._log_handler = _DiagnosticLogHandler(self)
        self._installed_sys_hook = self._handle_uncaught_exception
        self._installed_thread_hook = self._handle_thread_exception
        self._qt_handler = self._handle_qt_message

        self._prune_old_logs()
        self.application.installEventFilter(self)
        sys.excepthook = self._installed_sys_hook
        if hasattr(threading, "excepthook"):
            threading.excepthook = self._installed_thread_hook
        logging.getLogger().addHandler(self._log_handler)
        self._previous_qt_handler = qInstallMessageHandler(self._qt_handler)

        self.record(
            "session_start",
            {
                "app_version": app_version,
                "python_version": platform.python_version(),
                "qt_version": getattr(__import__("PySide6"), "__version__", "unknown"),
                "platform": sys.platform,
                "os_name": os.name,
                "interaction_logging_enabled": self._enabled,
            },
            force=True,
        )

    @property
    def interactions_enabled(self) -> bool:
        return self._enabled

    @property
    def log_paths(self) -> list[Path]:
        return sorted(self.logs_dir.glob(f"{self._base_name}-*.jsonl"))

    @property
    def current_log_path(self) -> Path:
        return self._file_path

    def set_interactions_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._enabled or self._closed:
            return
        self.record(
            "interaction_logging_resumed" if enabled else "interaction_logging_paused",
            {},
            force=True,
        )
        self._enabled = enabled

    def record(self, kind: str, details: dict[str, Any] | None = None, *, force: bool = False) -> None:
        """Write a structured event. Only recorder-owned event metadata is passed here."""
        if self._closed or (not force and not self._enabled):
            return
        event = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "elapsed_ms": int((datetime.now(timezone.utc) - self.started_at).total_seconds() * 1000),
            "session_id": self.session_id,
            "event": redact_text(kind, limit=100),
            "details": _safe_details(details or {}),
        }
        self._write_event(event)

    def record_error(self, kind: str, **details: Any) -> None:
        """Record errors even when ordinary interaction logging is paused."""
        if self._closed:
            return
        # record() applies the shared redaction and size bounds exactly once.
        self.record(kind, details, force=True)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if self._closed or not isinstance(watched, QWidget):
            return False
        try:
            event_type = event.type()
            # Message boxes are application-generated diagnostics, not ordinary
            # user input. Record them even when interaction logging is paused.
            if isinstance(watched, QMessageBox) and event_type == QEvent.Type.Show:
                self._record_message_box(watched)
                return False
            if not self._enabled:
                return False
            if event_type in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseButtonDblClick,
            ):
                name = {
                    QEvent.Type.MouseButtonPress: "mouse_press",
                    QEvent.Type.MouseButtonRelease: "mouse_release",
                    QEvent.Type.MouseButtonDblClick: "mouse_double_click",
                }[event_type]
                details = self._widget_details(watched)
                details["button"] = getattr(event.button(), "name", str(event.button()))
                position = event.position().toPoint()
                details["local_position"] = {"x": position.x(), "y": position.y()}
                if isinstance(watched, QMenu):
                    action = watched.actionAt(position)
                    if action is not None:
                        details["menu_action_index"] = watched.actions().index(action)
                        details["menu_action_id"] = action.objectName() or None
                if isinstance(watched, QTabBar):
                    details["tab_index"] = watched.tabAt(position)
                view = self._find_ancestor(watched, QAbstractItemView)
                if view is not None:
                    index = view.indexAt(view.viewport().mapFrom(watched, position))
                    if index.isValid():
                        details["item_row"] = index.row()
                        details["item_column"] = index.column()
                slider = self._find_ancestor(watched, QAbstractSlider)
                if slider is not None:
                    details["slider_value"] = slider.value()
                    details["slider_maximum"] = slider.maximum()
                button = self._find_ancestor(watched, QAbstractButton)
                if button is not None:
                    details["control_type"] = type(button).__name__
                    label = self._safe_control_label(button.text())
                    if label:
                        details["control_label"] = label
                combo = self._find_ancestor(watched, QComboBox)
                if combo is not None:
                    details["selected_index"] = combo.currentIndex()
                    details["option_count"] = combo.count()
                self.record(name, details)

            elif event_type == QEvent.Type.Wheel:
                details = self._widget_details(watched)
                angle = event.angleDelta()
                pixels = event.pixelDelta()
                details["wheel_angle_delta"] = {"x": angle.x(), "y": angle.y()}
                details["wheel_pixel_delta"] = {"x": pixels.x(), "y": pixels.y()}
                details["scroll_phase"] = getattr(event.phase(), "name", str(event.phase()))
                self.record("scroll", details)

            elif event_type == QEvent.Type.KeyPress and self._is_safe_shortcut_target(watched):
                key_name = self._safe_key_name(event)
                if key_name:
                    details = self._widget_details(watched)
                    details["key"] = key_name
                    self.record("keyboard_navigation_or_shortcut", details)

            elif event_type == QEvent.Type.FocusIn:
                details = self._widget_details(watched)
                details["focus_reason"] = getattr(event.reason(), "name", str(event.reason()))
                self.record("focus_in", details)

            elif event_type == QEvent.Type.ContextMenu:
                self.record("context_menu_open", self._widget_details(watched))

            elif event_type in (QEvent.Type.DragEnter, QEvent.Type.Drop):
                mime = event.mimeData() if hasattr(event, "mimeData") else None
                formats = mime.formats() if mime is not None else []
                details = self._widget_details(watched)
                details["mime_format_count"] = len(formats)
                details["mime_formats"] = [str(item) for item in formats[:10]]
                self.record("drag_drop", details)

        except Exception as exc:  # noqa: BLE001 - telemetry must never break the UI
            self.record_error(
                "diagnostic_event_filter_error",
                exception_type=type(exc).__name__,
                message=redact_text(exc, limit=1_000),
            )
        return False

    def _record_message_box(self, dialog: QMessageBox) -> None:
        """Record application-generated dialog text without reading input controls."""
        severity = {
            QMessageBox.Icon.NoIcon: "none",
            QMessageBox.Icon.Information: "information",
            QMessageBox.Icon.Warning: "warning",
            QMessageBox.Icon.Critical: "critical",
            QMessageBox.Icon.Question: "question",
        }.get(dialog.icon(), "unknown")
        self.record_error(
            "message_box_shown",
            severity=severity,
            title=redact_text(dialog.windowTitle(), limit=200),
            message=redact_text(dialog.text(), limit=2_000),
            informative_text=redact_text(dialog.informativeText(), limit=2_000),
            detailed_text=redact_text(dialog.detailedText(), limit=4_000),
        )

    @staticmethod
    def _find_ancestor(widget: QWidget, target_type: type) -> QWidget | None:
        current: QWidget | None = widget
        while current is not None:
            if isinstance(current, target_type):
                return current
            current = current.parentWidget()
        return None

    @staticmethod
    def _widget_details(widget: QWidget) -> dict[str, Any]:
        chain: list[dict[str, str]] = []
        current: QWidget | None = widget
        for _ in range(6):
            if current is None:
                break
            item = {"type": type(current).__name__}
            object_name = current.objectName()
            if object_name:
                item["object_name"] = redact_text(object_name, limit=100)
            chain.append(item)
            current = current.parentWidget()
        top = widget.window()
        return {
            "widget_path": chain,
            "window_type": type(top).__name__,
            "window_object_name": top.objectName() or None,
        }

    @staticmethod
    def _safe_control_label(label: str) -> str | None:
        candidate = redact_text(label.strip(), limit=80)
        if not candidate or len(candidate) > 80:
            return None
        if re.search(r"[/\\]|@|https?://|\b[A-Z]:", candidate, re.IGNORECASE):
            return None
        if candidate.startswith("[REDACTED"):
            return None
        return candidate

    @classmethod
    def _is_safe_shortcut_target(cls, widget: QWidget) -> bool:
        current: QWidget | None = widget
        while current is not None:
            if isinstance(current, cls._TEXT_INPUT_TYPES):
                return False
            if isinstance(current, QComboBox) and current.isEditable():
                return False
            current = current.parentWidget()
        return True

    @staticmethod
    def _safe_key_name(event: Any) -> str | None:
        modifiers = event.modifiers()
        command_modifiers = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        if modifiers & command_modifiers:
            sequence = QKeySequence(int(modifiers) | int(event.key()))
            name = sequence.toString(QKeySequence.SequenceFormat.PortableText)
            return redact_text(name, limit=40) if name else None
        safe_keys = {
            Qt.Key.Key_Escape,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Tab,
            Qt.Key.Key_Backtab,
            Qt.Key.Key_Backspace,
            Qt.Key.Key_Delete,
            Qt.Key.Key_Insert,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
            Qt.Key.Key_PageUp,
            Qt.Key.Key_PageDown,
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
            Qt.Key.Key_Space,
        }
        safe_keys.update(getattr(Qt.Key, f"Key_F{index}") for index in range(1, 13))
        if event.key() not in safe_keys:
            return None
        name = QKeySequence(int(event.key())).toString(QKeySequence.SequenceFormat.PortableText)
        return redact_text(name, limit=40) if name else None

    def _part_path(self, part: int) -> Path:
        return self.logs_dir / f"{self._base_name}-{part:02d}.jsonl"

    def _write_event(self, event: dict[str, Any]) -> None:
        try:
            line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
            encoded_size = len(line.encode("utf-8"))
            with self._lock:
                if self._limit_reached:
                    return
                try:
                    current_size = self._file_path.stat().st_size
                except FileNotFoundError:
                    current_size = 0
                if current_size + encoded_size > self.MAX_FILE_BYTES:
                    if self._part >= self.MAX_PARTS:
                        self._limit_reached = True
                        return
                    self._part += 1
                    self._file_path = self._part_path(self._part)
                with self._file_path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(line)
                    handle.flush()
        except OSError:
            # Diagnostics must never make the application unusable.
            return

    def _prune_old_logs(self) -> None:
        now = datetime.now(timezone.utc).timestamp()
        files = sorted(
            self.logs_dir.glob("eclipse-ui-*.jsonl"),
            key=lambda path: path.stat().st_mtime if path.exists() else 0,
        )
        for path in files:
            try:
                if now - path.stat().st_mtime > self.MAX_AGE_DAYS * 86400:
                    path.unlink(missing_ok=True)
            except OSError:
                pass
        files = sorted(
            self.logs_dir.glob("eclipse-ui-*.jsonl"),
            key=lambda path: path.stat().st_mtime if path.exists() else 0,
        )
        total = sum(path.stat().st_size for path in files if path.exists())
        while files and (len(files) > self.MAX_LOG_FILES or total > self.MAX_TOTAL_BYTES):
            oldest = files.pop(0)
            try:
                size = oldest.stat().st_size
                oldest.unlink(missing_ok=True)
                total -= size
            except OSError:
                continue

    def _handle_uncaught_exception(self, exc_type: type[BaseException], exc_value: BaseException, tb: Any) -> None:
        self.record_error(
            "unhandled_exception",
            exception_type=getattr(exc_type, "__name__", str(exc_type)),
            message=redact_text(exc_value, limit=2_000),
            traceback=redact_text("".join(traceback.format_exception(exc_type, exc_value, tb)), limit=8_000),
        )
        try:
            self._previous_sys_hook(exc_type, exc_value, tb)
        except Exception:
            pass

    def _handle_thread_exception(self, args: Any) -> None:
        self.record_error(
            "unhandled_thread_exception",
            thread_name=getattr(args.thread, "name", None),
            exception_type=getattr(args.exc_type, "__name__", str(args.exc_type)),
            message=redact_text(args.exc_value, limit=2_000),
            traceback=redact_text(
                "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
                limit=8_000,
            ),
        )
        if self._previous_thread_hook is not None:
            try:
                self._previous_thread_hook(args)
            except Exception:
                pass

    def _handle_qt_message(self, mode: Any, context: Any, message: str) -> None:
        self.record_error(
            "qt_message",
            severity=getattr(mode, "name", str(mode)),
            message=redact_text(message, limit=2_000),
            function=getattr(context, "function", None),
            line=getattr(context, "line", None),
        )
        if self._previous_qt_handler is not None:
            try:
                self._previous_qt_handler(mode, context, message)
            except Exception:
                pass

    def close(self) -> None:
        if self._closed:
            return
        self.record("session_end", {"interaction_logging_enabled": self._enabled}, force=True)
        self._closed = True
        try:
            self.application.removeEventFilter(self)
        except RuntimeError:
            pass
        logging.getLogger().removeHandler(self._log_handler)
        if sys.excepthook is self._installed_sys_hook:
            sys.excepthook = self._previous_sys_hook
        if hasattr(threading, "excepthook") and threading.excepthook is self._installed_thread_hook:
            threading.excepthook = self._previous_thread_hook
        qInstallMessageHandler(self._previous_qt_handler)
