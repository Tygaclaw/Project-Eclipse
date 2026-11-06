from __future__ import annotations

import contextlib
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from eclipse import __main__ as cli


class FeasibilityCliTests(unittest.TestCase):
    def run_cli(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_inspect_host_emits_json_snapshot(self) -> None:
        class Snapshot:
            def to_dict(self):
                return {
                    "schema_version": 1,
                    "system_memory": {"physical_total_bytes": 48 * 1024**3},
                    "gpus": [],
                    "warnings": [],
                }

        with patch.object(cli, "detect_host_hardware", return_value=Snapshot()) as detect:
            code, stdout, stderr = self.run_cli(["inspect-host", "--storage-path", "E:\\Models", "--compact"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["schema_version"], 1)
        detect.assert_called_once_with("E:\\Models")

    def test_plan_feasibility_emits_atlas_derived_report(self) -> None:
        atlas = {"format": "eclipse_model_atlas", "source_kind": "gguf"}
        host = SimpleNamespace(to_dict=lambda: {"system_memory": {}, "gpus": []})
        result = {
            "format": "eclipse_model_feasibility",
            "execution_feasibility": {"status": "not_validated"},
            "warnings": ["Static estimate only."],
        }
        with (
            patch.object(cli, "build_model_atlas", return_value=atlas) as build,
            patch.object(cli, "detect_host_hardware", return_value=host) as detect,
            patch.object(cli, "plan_model_feasibility", return_value=result) as plan,
        ):
            code, stdout, stderr = self.run_cli([
                "plan-feasibility",
                "D:\\Models\\test.gguf",
                "--context-tokens", "16384",
                "--kv-cache-dtype", "bf16",
                "--sequence-slots", "2",
                "--ram-reserve-mib", "4096",
                "--vram-reserve-mib", "512",
                "--compact",
            ])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), result)
        build.assert_called_once_with("D:\\Models\\test.gguf")
        detect.assert_called_once_with("D:\\Models\\test.gguf")
        request = plan.call_args.args[2]
        self.assertEqual(request.context_tokens, 16384)
        self.assertEqual(request.kv_cache_dtype, "bf16")
        self.assertEqual(request.sequence_slots, 2)
        self.assertEqual(request.system_ram_reserve_bytes, 4096 * 1024**2)
        self.assertEqual(request.gpu_vram_reserve_bytes, 512 * 1024**2)

    def test_plan_feasibility_defaults_to_declared_context(self) -> None:
        host = {"system_memory": {}, "gpus": []}
        with (
            patch.object(cli, "build_model_atlas", return_value={"format": "eclipse_model_atlas"}),
            patch.object(cli, "detect_host_hardware", return_value=host),
            patch.object(cli, "plan_model_feasibility", return_value={"ok": True}) as plan,
        ):
            code, stdout, _ = self.run_cli(["plan-feasibility", "model.gguf", "--compact"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout)["ok"])
        self.assertIsNone(plan.call_args.args[2].context_tokens)

    def test_plan_feasibility_reports_inspection_error_without_traceback(self) -> None:
        with patch.object(cli, "build_model_atlas", side_effect=cli.ModelAtlasError("bad model")):
            code, stdout, stderr = self.run_cli(["plan-feasibility", "bad.gguf"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("feasibility planning failed", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_context_must_be_positive(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            cli.main(["plan-feasibility", "model.gguf", "--context-tokens", "0"])
        self.assertEqual(caught.exception.code, 2)

    def test_reserves_cannot_be_negative(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            cli.main(["plan-feasibility", "model.gguf", "--ram-reserve-mib", "-1"])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
