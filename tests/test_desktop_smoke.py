from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import os
from pathlib import Path
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

try:
    import PySide6  # noqa: F401
except ModuleNotFoundError as exc:
    if exc.name != "PySide6":
        raise
    HAVE_QT = False
else:
    # Once PySide6 is installed, import or UI construction errors must fail the
    # test suite instead of silently converting every desktop test to a skip.
    from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QToolButton

    from eclipse.desktop.app import create_application
    from eclipse.desktop.context import AppContext
    from eclipse.desktop.main_window import NAV_ITEMS, MainWindow

    HAVE_QT = True


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
        "tokenizer": {
            "available": True,
            "source": "gguf_metadata",
            "tokenizer_model_type": "gpt2",
            "model_label": "gpt2",
            "pre_tokenizer_type": "llama-bpe",
            "vocab_size": 4,
            "vocab_size_evidence": "observed",
            "vocab_size_source": "gguf:tokenizer.ggml.tokens",
            "vocab_size_candidates": [
                {"source": "gguf:tokenizer.ggml.tokens", "count": 4, "evidence": "observed"},
                {"source": "tokenizer_config.json:vocab_size", "count": 8, "evidence": "declared"},
            ],
            "special_tokens": {
                "bos": {
                    "content": None,
                    "id": 1,
                    "id_evidence": "declared",
                    "content_evidence": "unknown",
                    "source": "gguf metadata",
                }
            },
            "chat_templates": {
                "count": 1,
                "sources": [
                    {
                        "name": "default",
                        "origin": "tokenizer.chat_template",
                        "kind": "gguf_metadata",
                        "preview": "{{ messages }}",
                    }
                ],
                "default": {
                    "name": "default",
                    "origin": "tokenizer.chat_template",
                    "kind": "gguf_metadata",
                    "evidence": "documented_loader_precedence",
                },
            },
            "fields": [
                {
                    "key": "tokenizer.ggml.tokens",
                    "value_type": "array",
                    "element_type": "string",
                    "count": 4,
                    "preview": ["a", "b", "<s>", "</s>"],
                    "evidence": "observed",
                }
            ],
            "warnings": [],
        },
        "warnings": ["Example warning from the inspector."],
        "evidence": {
            "parameters": "observed",
            "storage_bytes": "derived",
            "architecture": "observed_metadata",
            "tokenizer": "observed",
        },
        "inspection": {
            "mode": "static_read_only",
            "tensor_payload_bytes_read": 0,
            "tensor_payloads_loaded": False,
            "source_modified": False,
        },
    }


def widget_texts(widget: object) -> list[str]:
    labels = [label.text() for label in widget.findChildren(QLabel)]
    tools = [button.text() for button in widget.findChildren(QToolButton)]
    push = [button.text() for button in widget.findChildren(QPushButton)]
    return labels + tools + push


@unittest.skipUnless(HAVE_QT, "PySide6 is not installed")
class DesktopSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_application(["eclipse-desktop-tests"])

    def make_window(self) -> MainWindow:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        context = AppContext(root=Path(temp.name) / "home")
        window = MainWindow(context)
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
        self.assertEqual(window.model_platform.tabs.count(), 2)

    def test_navigation_switches_between_real_screens(self) -> None:
        window = self.make_window()
        self.assertIs(window.stack.currentWidget(), window.model_platform)
        window.navigate(1)
        self.assertEqual(window.nav.currentRow(), 1)
        self.assertIs(window.stack.currentWidget(), window.capability_workspace)
        window.navigate(2)
        self.assertEqual(window.nav.currentRow(), 2)
        self.assertIs(window.stack.currentWidget(), window.agent_workspace)

    def test_capability_workspace_has_real_planning_and_knowledge_controls(self) -> None:
        window = self.make_window()
        workspace = window.capability_workspace
        self.assertEqual(workspace._tabs.count(), 4)
        self.assertEqual(
            [workspace._tabs.tabText(index) for index in range(4)],
            ["Plan & evidence", "Verification", "Knowledge", "Corrections"],
        )
        self.assertIsInstance(workspace._goal, QPlainTextEdit)
        self.assertTrue(workspace._create_button.isEnabled())
        self.assertFalse(workspace._run_button.isEnabled())
        text = " ".join(widget_texts(workspace))
        self.assertIn("Create plan", text)
        self.assertNotIn("Not yet implemented", text)
        self.assertIn("Workspace: none selected", text)

    def test_agent_workspace_has_a_working_composer(self) -> None:
        window = self.make_window()
        agent = window.agent_workspace
        self.assertIsInstance(agent._composer, QPlainTextEdit)
        self.assertIsInstance(agent._send_button, QPushButton)
        self.assertTrue(agent._send_button.isEnabled())
        self.assertFalse(agent._stop_button.isEnabled())
        self.assertIsNotNone(agent._conversation_id)
        self.assertGreaterEqual(agent._conversation_list.count(), 1)
        text = " ".join(widget_texts(agent))
        self.assertIn("Send", text)
        self.assertNotIn("No model adapter connected", text)
        self.assertIn("No model loaded", text)

    def test_theme_toggle_persists_the_choice(self) -> None:
        window = self.make_window()
        self.assertEqual(window.context.settings.get("theme"), "dark")
        self.assertIn("Switch to light theme", window._theme_button.text())
        window._theme_button.click()
        self.assertEqual(window.context.settings.get("theme"), "light")
        self.assertIn("Switch to dark theme", window._theme_button.text())
        self.assertIn("#f5f9fe", window.styleSheet())

    def test_model_workspace_starts_with_empty_state_and_disabled_inspect(self) -> None:
        window = self.make_window()
        workspace = window.model_workspace
        text = " ".join(widget_texts(workspace))
        self.assertIn("No model inspected yet", text)
        self.assertFalse(workspace._inspect_button.isEnabled())
        self.assertTrue(workspace._choose_file_button.isEnabled())
        self.assertFalse(workspace._progress.isVisible())

    def test_prepare_and_run_panel_is_available_and_starts_idle(self) -> None:
        window = self.make_window()
        panel = window.model_platform.runtime
        self.assertEqual(panel._backend_combo.count(), 2)
        self.assertIn("Load selected model", panel._start_button.text())
        self.assertIn("Not loaded", panel._state_label.text())
        self.assertIn("Save profile", panel._save_profile_button.text())
        self.assertIn("Restore last good", panel._restore_profile_button.text())
        self.assertIn("Benchmark", panel._benchmark_button.text())

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
            "Tokenizer and chat format",
            "Warnings",
            "Evidence labels",
            "Inspection safety",
            "Advanced technical details",
        ):
            self.assertIn(heading, text)
        self.assertIn("sample-model.gguf", text)
        self.assertIn("Observed", text)
        self.assertIn("Derived", text)
        self.assertIn("Declared", text)
        self.assertIn("Show technical details", text)
        self.assertIn("gguf:tokenizer.ggml.tokens", text)
        self.assertIn("tokenizer_config.json:vocab_size", text)
        self.assertIn("8", text)

    def test_memory_fit_controls_are_user_adjustable_and_require_an_atlas(self) -> None:
        window = self.make_window()
        workspace = window.model_workspace
        self.assertTrue(workspace._detect_hardware_button.isEnabled())
        self.assertFalse(workspace._check_fit_button.isEnabled())
        self.assertIsNone(workspace._context_combo.currentData())
        self.assertAlmostEqual(workspace._ram_reserve_spin.value(), 8.0)
        self.assertAlmostEqual(workspace._vram_reserve_spin.value(), 0.75)
        workspace.apply_atlas(sample_atlas())
        self.assertTrue(workspace._check_fit_button.isEnabled())

    def test_feasibility_result_renders_as_a_memory_estimate_not_runtime_success(self) -> None:
        window = self.make_window()
        workspace = window.model_workspace
        workspace.apply_atlas(sample_atlas())
        workspace._render_feasibility(
            {
                "host": {
                    "operating_system": {"name": "Windows", "release": "11", "evidence": "observed"},
                    "processor": {"reported_identifier": "Intel Core i7", "logical_processors": 12, "evidence": "observed"},
                    "system_memory": {
                        "physical_total_bytes": 48 * 1024**3,
                        "available_bytes": 20 * 1024**3,
                        "evidence": "observed",
                    },
                    "gpus": [
                        {
                            "name": "NVIDIA Example GPU",
                            "memory_total_bytes": 8 * 1024**3,
                            "memory_free_bytes": 6 * 1024**3,
                            "evidence": "observed",
                        },
                        {
                            "name": "Second Example GPU",
                            "memory_total_bytes": 16 * 1024**3,
                            "memory_free_bytes": 12 * 1024**3,
                            "evidence": "observed",
                        },
                    ],
                    "storage": {"free_bytes": 500 * 1024**3, "evidence": "observed"},
                    "warnings": [],
                },
                "plan": {
                    "requirements": {
                        "weight_storage": {"bytes": 16 * 1024**3, "evidence": "derived"},
                        "kv_cache": {
                            "bytes": 2 * 1024**3,
                            "evidence": "estimated",
                            "context_tokens": 32768,
                            "context_source": "model_declared",
                        },
                    },
                    "budgets": {
                        "system_ram_usable_bytes": 12 * 1024**3,
                        "single_gpu_vram_usable_bytes": 5 * 1024**3,
                        "combined_system_ram_and_single_gpu_bytes": 17 * 1024**3,
                    },
                    "capacity_assessment": {
                        "memory_classification": "estimated_resident_memory_fit",
                        "native_memory_candidate": "within_resident_capacity_candidate",
                        "evidence": "estimated",
                    },
                    "execution_feasibility": {
                        "performance_goal_policy": {
                            "applies_to_this_profile": False,
                            "native_fit_policy": "No fixed throughput floor.",
                        }
                    },
                    "host": {
                        "selected_gpu": {
                            "device_name": "Second Example GPU",
                            "evidence": "observed",
                        }
                    },
                    "warnings": ["Static memory estimate only."],
                },
            }
        )
        text = " ".join(widget_texts(workspace))
        self.assertIn("Memory fit estimate", text)
        self.assertIn("Estimated KV cache", text)
        self.assertIn("Not validated", text)
        self.assertIn("Second Example GPU", text)
        self.assertIn("Performance goal scope", text)
        self.assertIn("No fixed throughput floor", text)
        self.assertIn("Static memory estimate only.", text)
        self.assertNotIn("10+ sustained tokens/second", text)

    def test_oversized_candidate_displays_only_the_large_model_goals(self) -> None:
        window = self.make_window()
        workspace = window.model_workspace
        workspace.apply_atlas(sample_atlas())
        workspace._render_feasibility(
            {
                "host": {
                    "system_memory": {
                        "physical_total_bytes": 48 * 1024**3,
                        "available_bytes": 8 * 1024**3,
                    },
                    "gpus": [
                        {
                            "name": "Example GPU",
                            "memory_total_bytes": 8 * 1024**3,
                            "memory_free_bytes": 2 * 1024**3,
                        }
                    ],
                    "storage": {},
                    "warnings": [],
                },
                "plan": {
                    "requirements": {
                        "weight_storage": {"bytes": 40 * 1024**3, "evidence": "derived"},
                        "kv_cache": {"bytes": None, "evidence": "unknown", "context_source": "unknown"},
                    },
                    "budgets": {
                        "system_ram_usable_bytes": 8 * 1024**3,
                        "single_gpu_vram_usable_bytes": 2 * 1024**3,
                        "combined_system_ram_and_single_gpu_bytes": 10 * 1024**3,
                    },
                    "capacity_assessment": {
                        "memory_classification": "exceeds_resident_capacity_even_before_kv_cache",
                        "native_memory_candidate": "oversized_candidate",
                        "evidence": "estimated",
                    },
                    "execution_feasibility": {
                        "performance_goal_policy": {
                            "applies_to_this_profile": True,
                            "primary_acceptance_goal": "10+ sustained tokens/second",
                            "preferred_stretch_goal": "15–20+ sustained tokens/second",
                        }
                    },
                    "host": {
                        "selected_gpu": {
                            "device_name": "Example GPU",
                            "evidence": "observed",
                        }
                    },
                    "warnings": ["Static memory estimate only."],
                },
            }
        )
        text = " ".join(widget_texts(workspace))
        self.assertIn("Oversized model candidate", text)
        self.assertIn("10+ sustained tokens/second", text)
        self.assertIn("15–20+ sustained tokens/second", text)
        self.assertIn("not a predicted or measured result", text)

    def test_window_starts_and_closes_cleanly(self) -> None:
        window = self.make_window()
        window.show()
        self.app.processEvents()
        self.assertTrue(window.isVisible())
        window.close()
        self.app.processEvents()
        self.assertFalse(window.isVisible())
        window.context.shutdown()


if __name__ == "__main__":
    unittest.main()
