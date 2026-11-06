from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from eclipse import __main__ as cli

VALID_MANIFEST = {
    "backend_id": "llama-cpp-declared",
    "display_name": "llama.cpp (declared contract)",
    "integration_status": "not_integrated",
    "model_formats": ["gguf"],
    "architectures": ["llama"],
    "quantization_types": ["f16", "q4_k"],
    "devices": [{"kind": "cpu", "api": "cpu"}, {"kind": "gpu", "api": "vulkan"}],
    "placement_modes": ["cpu_only", "hybrid"],
    "controls": {"context_length": {"supported": True, "requires_restart": True}},
    "telemetry": ["process_state"],
}


def atlas() -> dict:
    return {
        "format": "eclipse_model_atlas",
        "atlas_version": 1,
        "source_kind": "gguf",
        "architecture": {"architecture": "llama", "evidence": "observed"},
        "summary": {"distribution": {"counts": {"F16": 2}}},
    }


class RuntimeSupportCliTests(unittest.TestCase):
    def run_cli(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def write_manifest(self, payload) -> Path:
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        with handle:
            json.dump(payload, handle)
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        return Path(handle.name)

    def test_runtime_support_emits_matrix(self) -> None:
        manifest = self.write_manifest(VALID_MANIFEST)
        host = SimpleNamespace(to_dict=lambda: {"gpus": [{"vendor": "nvidia"}]})
        with (
            patch.object(cli, "build_model_atlas", return_value=atlas()),
            patch.object(cli, "detect_host_hardware", return_value=host),
        ):
            code, stdout, stderr = self.run_cli([
                "runtime-support",
                "D:\\Models\\test.gguf",
                "--capabilities", str(manifest),
                "--placement", "hybrid",
                "--control", "context_length",
                "--compact",
            ])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["format"], "eclipse_runtime_support")
        self.assertEqual(payload["backend"]["backend_id"], "llama-cpp-declared")
        self.assertEqual(payload["dimensions"]["architecture"]["status"], "declared_supported")
        self.assertEqual(payload["dimensions"]["placement"]["status"], "declared_supported")
        self.assertIn("context_length", payload["controls"])
        self.assertFalse(payload["runtime_verified"])

    def test_runtime_support_reports_invalid_manifest_without_traceback(self) -> None:
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        with handle:
            handle.write("{not json")
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        code, stdout, stderr = self.run_cli([
            "runtime-support", "model.gguf", "--capabilities", handle.name,
        ])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("runtime support check failed", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_runtime_support_missing_manifest_file(self) -> None:
        code, stdout, stderr = self.run_cli([
            "runtime-support", "model.gguf", "--capabilities", "does-not-exist.json",
        ])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("cannot read capability manifest", stderr)

    def test_runtime_support_reports_atlas_error(self) -> None:
        manifest = self.write_manifest(VALID_MANIFEST)
        with patch.object(cli, "build_model_atlas", side_effect=cli.ModelAtlasError("bad model")):
            code, stdout, stderr = self.run_cli([
                "runtime-support", "bad.gguf", "--capabilities", str(manifest),
            ])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("runtime support check failed", stderr)

    def test_capabilities_argument_is_required(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            cli.main(["runtime-support", "model.gguf"])
        self.assertEqual(caught.exception.code, 2)

    def test_invalid_placement_choice_exits(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            cli.main([
                "runtime-support", "model.gguf",
                "--capabilities", "x.json",
                "--placement", "magic",
            ])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
