from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from eclipse.__main__ import main
from tests.test_model_atlas import build_gguf


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.gguf = self.root / "model.gguf"
        self.gguf.write_bytes(build_gguf([("blk.0.weight", (4, 8), 0, 0)]))

    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(["--home", str(self.home), *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_registry_add_and_list(self) -> None:
        code, out, err = self.run_cli("registry-add", str(self.gguf), "--compact")
        self.assertEqual(code, 0, err)
        model = json.loads(out)
        self.assertEqual(model["source_kind"], "gguf")
        code, out, err = self.run_cli("registry-list", "--compact")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["count"], 1)

    def test_prepare_and_verify_package(self) -> None:
        code, out, err = self.run_cli("prepare", str(self.gguf), "--compact", "--register")
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["manifest"]["integrity"]["status"], "verified")
        self.assertIn("variant_id", payload)
        code, out, err = self.run_cli("verify-package", payload["package"]["directory_name"])
        # The directory name alone is not a full path; use the manifest directory.
        self.assertNotEqual(code, 0)
        code, out, err = self.run_cli(
            "verify-package", str(self.home / "prepared" / payload["package"]["directory_name"])
        )
        self.assertEqual(code, 0, err)

    def test_knowledge_propose_and_approve(self) -> None:
        code, out, err = self.run_cli(
            "knowledge", "propose", "--title", "CLI note", "--body", "Observed facts.", "--source", "test"
        )
        self.assertEqual(code, 0, err)
        note = json.loads(out)
        self.assertEqual(note["status"], "inbox")
        code, out, err = self.run_cli(
            "knowledge", "approve", note["id"], "--folder", "05 - Research",
            "--verification", "reviewed in test",
        )
        self.assertEqual(code, 0, err)
        approved = json.loads(out)
        self.assertIn("05 - Research", approved["approved_path"])
        code, out, err = self.run_cli("knowledge", "search", "CLI note", "--compact")
        self.assertEqual(code, 0, err)
        self.assertTrue(json.loads(out)["hits"])

    def test_corrections_require_evidence(self) -> None:
        code, out, err = self.run_cli(
            "corrections", "propose", "--title", "T", "--issue", "I",
            "--root-cause", "R", "--fix", "F", "--scope", "S",
        )
        self.assertEqual(code, 0, err)
        correction = json.loads(out)
        code, out, err = self.run_cli(
            "corrections", "promote", correction["id"], "--evidence", "short", "--regression", "x"
        )
        self.assertNotEqual(code, 0)
        code, out, err = self.run_cli(
            "corrections", "promote", correction["id"],
            "--evidence", "python -m unittest tests.test_app_cli -> OK (42 tests)",
            "--regression", "tests/test_app_cli.py",
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["status"], "verified")

    def test_app_status_and_detect_checks(self) -> None:
        workspace = self.root / "project"
        workspace.mkdir()
        (workspace / "app.py").write_text("x = 1\n", encoding="utf-8")
        code, out, err = self.run_cli("app-status", "--compact")
        self.assertEqual(code, 0, err)
        status = json.loads(out)
        self.assertIn("counts", status)
        self.assertIn("backends", status)
        code, out, err = self.run_cli("detect-checks", "--workspace", str(workspace), "--compact")
        self.assertEqual(code, 0, err)
        checks = json.loads(out)["checks"]
        self.assertTrue(checks)

    def test_task_new_creates_a_plan(self) -> None:
        workspace = self.root / "project"
        workspace.mkdir()
        (workspace / "app.py").write_text("x = 1\n", encoding="utf-8")
        code, out, err = self.run_cli(
            "task", "new", "Add a double function to app.py and verify it",
            "--workspace", str(workspace), "--compact",
        )
        self.assertEqual(code, 0, err)
        task = json.loads(out)
        self.assertEqual(task["status"], "planned")
        self.assertTrue(task["plan"]["objectives"])
        self.assertEqual(task["project_root"], str(workspace))

    def test_backends_command_lists_both_backends(self) -> None:
        code, out, err = self.run_cli("backends", "--compact")
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        keys = [backend["key"] for backend in payload["backends"]]
        self.assertEqual(keys, ["llamacpp_server", "openai_compatible"])

    def test_runtime_support_reports_a_static_matrix(self) -> None:
        code, out, err = self.run_cli(
            "runtime-support", str(self.gguf), "--backend", "llamacpp_server",
            "--placement", "hybrid", "--control", "context_tokens", "--compact",
        )
        self.assertEqual(code, 0, err)
        report = json.loads(out)
        self.assertEqual(report["format"], "eclipse_runtime_support")
        self.assertFalse(report["runtime_verified"])
        self.assertIn(report["overall_status"], {"unsupported", "unknown", "declared_compatible_not_runtime_verified"})
        self.assertEqual(report["dimensions"]["format"]["status"], "declared_supported")
        self.assertEqual(report["controls"]["context_tokens"]["status"], "declared_supported")

    def test_profiles_list_and_delete(self) -> None:
        from eclipse.core.config import AppPaths
        from eclipse.core.storage import Store

        paths = AppPaths.discover(self.home).ensure()
        store = Store(paths.database_path)
        record = store.add_profile(name="Saved", intent="balanced", payload={"context_tokens": 2048})
        store.close()
        code, out, err = self.run_cli("profiles", "list", "--compact")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["profiles"][0]["id"], record["id"])
        code, out, err = self.run_cli("profiles", "delete", record["id"])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["deleted"], record["id"])

    def test_quantize_without_tool_fails_cleanly(self) -> None:
        code, out, err = self.run_cli("quantize", str(self.gguf), "--type", "Q4_K_M")
        self.assertEqual(code, 2)
        self.assertIn("llama-quantize", err)


if __name__ == "__main__":
    unittest.main()
