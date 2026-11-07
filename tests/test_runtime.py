"""Runtime tests against a real spawned HTTP server process."""

from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest

from eclipse.core.config import AppPaths, Settings
from eclipse.core.storage import Store
from eclipse.runtime import (
    BackendUnavailable,
    CancellationToken,
    ChatCancelled,
    ChatError,
    ChatMessage,
    LlamaCppServer,
    LlamaCppStartError,
    OpenAICompatibleClient,
    RuntimeManager,
    RuntimeState,
    find_free_port,
    find_server_binary,
    resolve_profile,
    run_benchmark,
)
from tests.test_model_atlas import build_gguf

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fake_server_script() -> Path:
    return FIXTURES / "fake_llama_server.py"


def process_is_alive(pid: int) -> bool:
    if os.name == "nt":
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
            check=False,
        )
        return str(pid) in completed.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.chmod(fake_server_script(), os.stat(fake_server_script()).st_mode | stat.S_IEXEC)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model_path = self.root / "model.gguf"
        self.model_path.write_bytes(build_gguf([("blk.0.weight", (4, 8), 0, 0)]))
        self.paths = AppPaths.discover(self.root / "home").ensure()
        self.settings = Settings(self.paths.settings_path)
        self.store = Store(self.paths.database_path)
        self.addCleanup(self.store.close)
        self.runtime = RuntimeManager(self.store, self.settings, self.paths)
        self.addCleanup(lambda: self.runtime.shutdown())

    def model_record(self, atlas: dict | None = None) -> dict:
        return {
            "id": "model_test",
            "name": "Fake model",
            "source_path": str(self.model_path),
            "source_kind": "gguf",
            "atlas": atlas or {},
        }

    def spec(self, **overrides) -> dict:
        base = {
            "backend": "llamacpp_server",
            "intent": "balanced",
            "context_tokens": 2048,
            "gpu_layers": 0,
            "threads": 1,
            "parallel_slots": 1,
            "kv_cache_dtype": "f16",
            "temperature": 0.2,
            "max_tokens": 64,
            "binary": str(fake_server_script()),
        }
        base.update(overrides)
        return base

    def start_managed(self) -> None:
        self.runtime.start(self.model_record(), self.spec())

    def test_client_streams_text_and_usage(self) -> None:
        self.start_managed()
        client = OpenAICompatibleClient(self.runtime.endpoint(), model="fake-model")
        text, final = client.chat([ChatMessage(role="user", content="hello")])
        self.assertEqual(text, "Hello from the fake server.")
        self.assertEqual(final.usage["completion_tokens"], 5)
        self.assertEqual(final.finish_reason, "stop")

    def test_client_assembles_streamed_tool_calls(self) -> None:
        self.start_managed()
        client = OpenAICompatibleClient(self.runtime.endpoint(), model="fake-model")
        chunks = list(
            client.stream_chat(
                [ChatMessage(role="user", content="TOOL please write a file")],
                tools=[{"type": "function", "function": {"name": "write_file", "parameters": {}}}],
            )
        )
        final = chunks[-1]
        self.assertEqual(len(final.tool_calls), 1)
        self.assertEqual(final.tool_calls[0].name, "write_file")
        self.assertEqual(final.tool_calls[0].arguments_dict()["path"], "created_by_agent.txt")

    def test_managed_lifecycle_reaches_ready_with_observed_context(self) -> None:
        self.start_managed()
        status = self.runtime.status
        self.assertEqual(status.state, RuntimeState.READY)
        self.assertTrue(status.owns_process)
        self.assertIsNotNone(status.pid)
        self.assertEqual(status.observed_context, 2048)
        self.assertIn(f":{status.endpoint.rsplit(':', 1)[1]}", status.endpoint)

    def test_generation_returns_measured_telemetry(self) -> None:
        self.start_managed()
        parts = [
            chunk.text
            for chunk in self.runtime.stream_chat([ChatMessage(role="user", content="hi")])
            if chunk.text
        ]
        self.assertEqual("".join(parts), "Hello from the fake server.")
        self.assertEqual(self.runtime.status.state, RuntimeState.READY)
        runs = self.store.list_runs()
        generation = [run for run in runs if run["kind"] == "generation"][0]
        metrics = generation["metrics"]
        self.assertIsNotNone(metrics["time_to_first_token_seconds"])
        self.assertEqual(metrics["completion_tokens"], 5)
        self.assertIsNotNone(metrics["tokens_per_second"])
        self.assertEqual(metrics["tokens_per_second_evidence"], "observed")

    def test_stop_terminates_the_owned_process_and_releases_state(self) -> None:
        self.start_managed()
        pid = self.runtime.status.pid
        self.assertIsNotNone(pid)
        result = self.runtime.stop()
        self.assertTrue(result["stopped"])
        self.assertEqual(self.runtime.status.state, RuntimeState.NOT_LOADED)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if not process_is_alive(pid):
                break
            time.sleep(0.05)
        else:
            self.fail("The managed process is still alive after stop")

    def test_missing_server_binary_fails_honestly(self) -> None:
        spec = self.spec(binary=str(self.root / "does-not-exist"))
        with self.assertRaises(Exception):
            self.runtime.start(self.model_record(), spec)
        self.assertEqual(self.runtime.status.state, RuntimeState.FAILED)
        self.assertIsNotNone(self.runtime.status.error)

    def test_startup_crash_is_reported_and_cleaned_up(self) -> None:
        crash = self.root / "crash-server.py"
        crash.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(3)\n", encoding="utf-8")
        os.chmod(crash, 0o755)
        spec = self.spec(binary=str(crash))
        with self.assertRaises(Exception):
            self.runtime.start(self.model_record(), spec)
        self.assertEqual(self.runtime.status.state, RuntimeState.FAILED)
        self.assertIsNone(self.runtime.status.pid)

    def test_cancellation_stops_the_stream(self) -> None:
        self.start_managed()
        cancel = CancellationToken()
        client = OpenAICompatibleClient(self.runtime.endpoint(), model="fake-model")
        stream = client.stream_chat([ChatMessage(role="user", content="hi")], cancel=cancel)
        next(stream)
        cancel.cancel()
        with self.assertRaises(ChatCancelled):
            list(stream)

    def test_attach_mode_does_not_own_the_external_server(self) -> None:
        port = find_free_port()
        process = subprocess.Popen(
            [sys.executable, str(fake_server_script()), "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.addCleanup(process.terminate)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                OpenAICompatibleClient(f"http://127.0.0.1:{port}", timeout_seconds=1).list_models()
                break
            except ChatError:
                time.sleep(0.1)
        else:
            self.fail("The external fake server did not become ready")
        self.runtime.start(
            {"id": "remote", "name": "External", "source_path": "", "source_kind": "remote", "atlas": {}},
            self.spec(backend="openai_compatible", endpoint=f"http://127.0.0.1:{port}", model_name="fake-model"),
        )
        self.assertEqual(self.runtime.status.state, RuntimeState.READY)
        self.assertFalse(self.runtime.status.owns_process)
        text = "".join(
            chunk.text
            for chunk in self.runtime.stream_chat([ChatMessage(role="user", content="hi")])
            if chunk.text
        )
        self.assertEqual(text, "Hello from the fake server.")
        self.runtime.stop()
        self.assertIsNone(process.poll(), "Attach mode must not stop the external server")

    def test_changed_settings_for_a_loaded_model_are_reported_not_silently_ignored(self) -> None:
        self.start_managed()
        pid = self.runtime.status.pid
        result = self.runtime.start(self.model_record(), self.spec(context_tokens=1024))
        self.assertEqual(result.status["state"], "ready")
        self.assertFalse(result.applied)
        self.assertEqual(self.runtime.status.pid, pid)
        self.assertEqual(self.runtime.status.observed_context, 2048)
        self.assertTrue(any("Restart" in warning for warning in result.warnings))
        unchanged = self.runtime.start(self.model_record(), self.spec())
        self.assertTrue(unchanged.applied)

    def test_profile_resolution_validates_against_capabilities(self) -> None:
        spec = resolve_profile(
            intent="balanced",
            backend="llamacpp_server",
            atlas={
                "source_kind": "gguf",
                "architecture": {"architecture": "llama", "details": {"context_length": {"value": 4096}}},
            },
            overrides={"context_tokens": 8192},
        )
        self.assertEqual(spec.context_tokens, 8192)
        self.assertTrue(any("exceeds" in warning for warning in spec.warnings))
        with self.assertRaises(Exception):
            resolve_profile(intent="balanced", backend="llamacpp_server", atlas={"source_kind": "safetensors"})

    def test_binary_discovery_accepts_an_explicit_executable(self) -> None:
        self.assertEqual(find_server_binary(str(fake_server_script())), fake_server_script())

    def test_python_script_launcher_uses_the_python_interpreter(self) -> None:
        server = LlamaCppServer(
            self.model_path,
            executable=fake_server_script(),
            port=find_free_port(),
        )
        launch = server.build_launch()
        self.assertEqual(launch.argv[:2], [sys.executable, str(fake_server_script())])

    def test_successful_generation_saves_a_last_known_good_profile(self) -> None:
        self.start_managed()
        list(self.runtime.stream_chat([ChatMessage(role="user", content="hi")]))
        profiles = self.store.list_profiles("model_test")
        self.assertEqual(len(profiles), 1)
        self.assertTrue(profiles[0]["last_known_good"])
        self.assertEqual(profiles[0]["intent"], "balanced")
        self.assertEqual(profiles[0]["payload"]["context_tokens"], 2048)
        self.assertEqual(self.runtime.diagnostics()["profile_id"], profiles[0]["id"])
        self.assertIsNotNone(self.runtime.last_generation_metrics["tokens_per_second"])

    def test_benchmark_reports_measured_median_and_variance(self) -> None:
        self.start_managed()
        result = run_benchmark(self.runtime, runs=2, warmup=1, max_tokens=16)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["samples"]), 2)
        self.assertEqual(result["summary"]["tokens_per_second"]["count"], 2)
        self.assertIsNotNone(result["summary"]["tokens_per_second"]["median"])
        self.assertIsNotNone(result["summary"]["time_to_first_token_seconds"]["median"])
        self.assertEqual(result["summary"]["tokens_per_second"]["stdev"] >= 0, True)
        self.assertIn("run_id", result)
        benchmark_runs = [run for run in self.store.list_runs() if run["kind"] == "benchmark"]
        self.assertEqual(len(benchmark_runs), 1)
        self.assertEqual(benchmark_runs[0]["status"], "ok")

    def test_last_known_good_profile_can_be_restored_after_stop(self) -> None:
        self.start_managed()
        list(self.runtime.stream_chat([ChatMessage(role="user", content="hi")]))
        self.runtime.stop()
        restored = self.runtime.restore_last_known_good(self.model_record())
        self.assertEqual(restored.status["state"], "ready")
        self.assertEqual(restored.spec["context_tokens"], 2048)
        self.assertEqual(self.runtime.status.observed_context, 2048)


if __name__ == "__main__":
    unittest.main()
