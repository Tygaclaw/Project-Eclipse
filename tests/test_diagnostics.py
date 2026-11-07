from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import PySide6  # noqa: F401
except ModuleNotFoundError as exc:
    if exc.name != "PySide6":
        raise
    HAVE_QT = False
else:
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton, QScrollArea, QWidget

    from eclipse.desktop.diagnostics import InteractionRecorder, redact_text

    HAVE_QT = True


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class InteractionRecorderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication(["eclipse-diagnostics-tests"])

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.logs = Path(self.temp.name) / "logs"
        self.recorder = InteractionRecorder(self.application, self.logs)
        self.window = QWidget()
        self.window.setObjectName("DiagnosticsTestWindow")
        self.button = QPushButton("Run test", self.window)
        self.button.setObjectName("RunTestButton")
        self.input = QLineEdit(self.window)
        self.input.setObjectName("PrivateTextInput")
        self.window.resize(480, 240)
        self.button.setGeometry(10, 10, 120, 32)
        self.input.setGeometry(10, 60, 300, 32)
        self.window.show()
        self.application.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.recorder.close()
        self.temp.cleanup()

    def read_events(self) -> list[dict]:
        contents = "".join(path.read_text(encoding="utf-8") for path in self.recorder.log_paths)
        return [json.loads(line) for line in contents.splitlines() if line.strip()]

    def test_records_mouse_clicks_and_scroll_without_screen_coordinates(self) -> None:
        QTest.mouseClick(self.button, Qt.MouseButton.LeftButton)
        position = QPointF(5, 5)
        global_position = QPointF(self.window.mapToGlobal(QPoint(5, 5)))
        wheel = QWheelEvent(
            position,
            global_position,
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(self.window, wheel)
        events = self.read_events()
        event_names = [item["event"] for item in events]
        self.assertIn("mouse_press", event_names)
        self.assertIn("mouse_release", event_names)
        self.assertIn("scroll", event_names)
        serialized = json.dumps(events)
        self.assertIn("RunTestButton", serialized)
        self.assertNotIn("global_position", serialized)
        self.assertIn("wheel_angle_delta", serialized)

    def test_does_not_record_text_typed_into_input_controls(self) -> None:
        self.input.setFocus()
        QTest.keyClicks(self.input, "private-chat-message-never-store")
        self.application.processEvents()
        serialized = json.dumps(self.read_events())
        self.assertNotIn("private-chat-message-never-store", serialized)
        self.assertIn("PrivateTextInput", serialized)

    def test_errors_are_still_recorded_when_interaction_logging_is_paused(self) -> None:
        self.recorder.set_interactions_enabled(False)
        self.recorder.record("this_click_should_not_be_recorded")
        self.recorder.record_error("test_error", message="api_key=sk-abcdefghijklmnopqrstuv")
        events = self.read_events()
        event_names = [item["event"] for item in events]
        self.assertNotIn("this_click_should_not_be_recorded", event_names)
        error = next(item for item in events if item["event"] == "test_error")
        self.assertIn("[REDACTED]", error["details"]["message"])
        self.assertNotIn("sk-abcdefghijklmnopqrstuv", json.dumps(events))

    def test_secret_redaction_handles_tokens_and_bearer_headers(self) -> None:
        value = redact_text("Authorization: Bearer abcdefghijklmnop API_KEY=secret-value")
        self.assertNotIn("abcdefghijklmnop", value)
        self.assertNotIn("secret-value", value)


if __name__ == "__main__":
    unittest.main()
