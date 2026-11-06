from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

try:
    from PySide6.QtWidgets import (
        QApplication,
        QLineEdit,
        QPlainTextEdit,
        QPushButton,
        QTextEdit,
    )

    from eclipse.desktop.app import create_application
    from eclipse.desktop.main_window import NAV_ITEMS, MainWindow

    HAVE_QT = True
except Exception:
    HAVE_QT = False


def sample_atlas() -> dict[str, object]:
    return {
        "format": "eclipse_model_atlas",
        "atlas_version": 1,
        "source_kind": "gguf",
        "source_name": "sample-model.gguf",
        "architecture": {"architecture": "llama", "name": "Sample", "evidence": "observed_metadata"},
        "summary": {
            "tensor_count": 2,
            "total_parameters": 4096,
            "total_storage_bytes": 16384,
            "total_storage_is_complete": True,
            "distribution": {"label": "ggml_type", "counts": {"f32": 1, "q4_k": 1}},
            "parameters_evidence": "observed",
            "storage_evidence": "derived",
        },
        "components": {
            "gguf": {
                "format": "GGUF",
                "version": 3,
                "endianness": "little",
                "file_size_bytes": 32768,
                "registry_revision": "test-revision",
            }
        },
        "warnings": ["Example warning from the inspector."],
        "evidence": {
            "parameters": "observed",
            "storage_bytes": "derived",
            "architecture": "observed_metadata",
        },
        "inspection": {
            "mode": "static_read_only",
            "tensor_payload_bytes_read": 0,
            "tensor_payloads_loaded": False,
            "source_modified": False,
        },
    }


def widget_texts(widget: object) -> list[str]:
    from PySide6.QtWidgets import QLabel, QToolButton

    labels = [label.text() for label in widget.findChildren(QLabel)]
    tools = [button.text() for button in widget.findChildren(QToolButton)]
    return labels + tools


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class DesktopSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_application(["eclipse-desktop-tests"])

    def make_window(self) -> MainWindow:
        window = MainWindow()
        self.addCleanup(window.close)
        return window

    def test_application_theme_uses_navy_and_cyan(self) -> None:
        stylesheet = self.app.styleSheet()
        self.assertIn("#070c15", stylesheet)
        self.assertIn("#39d8ea", stylesheet)

    def test_three_primary_workspaces_are_present(self) -> None:
        window = self.make_window()
        self.assertEqual(window.nav.count(), 3)
        self.assertEqual(
            [window.nav.item(index).text() for index in range(3)],
            list(NAV_ITEMS),
        )
        self.assertEqual(window.stack.count(), 3)

    def test_navigation_switches_between_real_screens(self) -> None:
        window = self.make_window()
        self.assertIs(window.stack.currentWidget(), window.model_workspace)
        window.navigate(1)
        self.assertEqual(window.nav.currentRow(), 1)
        self.assertIs(window.stack.currentWidget(), window.capability_workspace)
        window.navigate(2)
        self.assertEqual(window.nav.currentRow(), 2)
        self.assertIs(window.stack.currentWidget(), window.agent_workspace)

    def test_capability_workspace_is_honest(self) -> None:
        window = self.make_window()
        text = " ".join(widget_texts(window.capability_workspace))
        self.assertIn("Not yet implemented", text)
        self.assertIn("does not simulate progress", text)

    def test_agent_workspace_has_no_chat_input_or_send_button(self) -> None:
        window = self.make_window()
        agent = window.agent_workspace
        self.assertEqual(agent.findChildren(QLineEdit), [])
        self.assertEqual(agent.findChildren(QTextEdit), [])
        self.assertEqual(agent.findChildren(QPlainTextEdit), [])
        self.assertEqual(agent.findChildren(QPushButton), [])
        text = " ".join(widget_texts(agent))
        self.assertIn("No model adapter connected", text)

    def test_model_workspace_starts_with_empty_state_and_disabled_inspect(self) -> None:
        window = self.make_window()
        workspace = window.model_workspace
        text = " ".join(widget_texts(workspace))
        self.assertIn("No model inspected yet", text)
        self.assertFalse(workspace._inspect_button.isEnabled())
        self.assertTrue(workspace._choose_file_button.isEnabled())
        self.assertFalse(workspace._progress.isVisible())

    def test_model_workspace_renders_the_required_atlas_sections(self) -> None:
        window = self.make_window()
        workspace = window.model_workspace
        workspace.apply_atlas(sample_atlas())
        self.app.processEvents()
        text = " ".join(widget_texts(workspace))
        for heading in (
            "Model & architecture",
            "Parameters and storage",
            "Type / dtype distribution",
            "Warnings",
            "Evidence labels",
            "Inspection safety",
            "Advanced technical details",
        ):
            self.assertIn(heading, text)
        self.assertIn("sample-model.gguf", text)
        self.assertIn("Observed", text)
        self.assertIn("Derived", text)
        self.assertIn("Show technical details", text)

    def test_window_starts_and_closes_cleanly(self) -> None:
        window = self.make_window()
        window.show()
        self.app.processEvents()
        self.assertTrue(window.isVisible())
        window.close()
        self.app.processEvents()
        self.assertFalse(window.isVisible())


if __name__ == "__main__":
    unittest.main()