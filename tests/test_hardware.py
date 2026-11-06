from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eclipse.core import hardware


class HardwareDiscoveryTests(unittest.TestCase):
    def test_parses_nvidia_smi_csv_memory_values(self) -> None:
        output = (
            "0, NVIDIA GeForce RTX 2060 SUPER, 8192, 6144, 2048, 555.99\n"
            "1, NVIDIA Test GPU, 16384, 12000, 4384, 555.99\n"
        )
        devices = hardware._parse_nvidia_smi_output(output)
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0].name, "NVIDIA GeForce RTX 2060 SUPER")
        self.assertEqual(devices[0].memory_total_bytes, 8192 * hardware.MiB)
        self.assertEqual(devices[0].memory_free_bytes, 6144 * hardware.MiB)
        self.assertEqual(devices[0].memory_used_bytes, 2048 * hardware.MiB)
        self.assertEqual(devices[0].driver_version, "555.99")
        self.assertEqual(devices[0].evidence, "observed")

    def test_nvidia_smi_unknown_values_remain_unknown(self) -> None:
        devices = hardware._parse_nvidia_smi_output(
            "0, Example GPU, N/A, N/A, N/A, 555.99\n"
        )
        self.assertIsNone(devices[0].memory_total_bytes)
        self.assertIsNone(devices[0].memory_free_bytes)
        self.assertIsNone(devices[0].memory_used_bytes)

    def test_rejects_unexpected_nvidia_csv_columns(self) -> None:
        with self.assertRaises(ValueError):
            hardware._parse_nvidia_smi_output("0, Example GPU, 8192\n")

    def test_nvidia_discovery_unavailable_is_unknown_not_zero(self) -> None:
        with patch.object(hardware, "_nvidia_smi_candidates", return_value=[]):
            devices, summary, warning = hardware._query_nvidia_gpus()
        self.assertEqual(devices, ())
        self.assertEqual(summary["status"], "unavailable")
        self.assertEqual(summary["evidence"], "unknown")
        self.assertIn("remain unknown", warning or "")

    def test_nvidia_query_failure_does_not_invent_a_gpu(self) -> None:
        class Completed:
            returncode = 1
            stdout = ""
            stderr = "not available"

        with (
            patch.object(hardware, "_nvidia_smi_candidates", return_value=["nvidia-smi"]),
            patch.object(hardware.subprocess, "run", return_value=Completed()),
        ):
            devices, summary, warning = hardware._query_nvidia_gpus()
        self.assertEqual(devices, ())
        self.assertEqual(summary["status"], "error")
        self.assertIn("remain unknown", warning or "")

    def test_nvidia_query_uses_no_shell_and_has_timeout(self) -> None:
        class Completed:
            returncode = 0
            stdout = "0, Example GPU, 8192, 6144, 2048, 555.99\n"
            stderr = ""

        with (
            patch.object(hardware, "_nvidia_smi_candidates", return_value=["nvidia-smi"]),
            patch.object(hardware.subprocess, "run", return_value=Completed()) as run,
        ):
            devices, summary, warning = hardware._query_nvidia_gpus(timeout_seconds=1.5)
        self.assertEqual(len(devices), 1)
        self.assertEqual(summary["status"], "available")
        self.assertIsNone(warning)
        kwargs = run.call_args.kwargs
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["timeout"], 1.5)
        self.assertIs(kwargs["stdin"], hardware.subprocess.DEVNULL)

    def test_nvidia_lookup_tries_next_location_when_first_cannot_launch(self) -> None:
        class Completed:
            returncode = 0
            stdout = "0, Example GPU, 8192, 6144, 2048, 555.99\n"
            stderr = ""

        with (
            patch.object(
                hardware,
                "_nvidia_smi_candidates",
                return_value=["missing-location", "working-location"],
            ),
            patch.object(
                hardware.subprocess,
                "run",
                side_effect=[FileNotFoundError("missing"), Completed()],
            ) as run,
        ):
            devices, summary, warning = hardware._query_nvidia_gpus()
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].args[0][0], "missing-location")
        self.assertEqual(run.call_args_list[1].args[0][0], "working-location")
        self.assertEqual(len(devices), 1)
        self.assertEqual(summary["status"], "available")
        self.assertIsNone(warning)

    def test_nvidia_lookup_reports_error_when_no_location_can_launch(self) -> None:
        with (
            patch.object(
                hardware, "_nvidia_smi_candidates", return_value=["one", "two"]
            ),
            patch.object(
                hardware.subprocess, "run", side_effect=FileNotFoundError("missing")
            ) as run,
        ):
            devices, summary, warning = hardware._query_nvidia_gpus()
        self.assertEqual(run.call_count, 2)
        self.assertEqual(devices, ())
        self.assertEqual(summary["status"], "error")
        self.assertIn("remain unknown", warning or "")
        self.assertIn("FileNotFoundError", warning or "")

    def test_nvidia_timeout_stops_the_search_instead_of_waiting_twice(self) -> None:
        with (
            patch.object(
                hardware, "_nvidia_smi_candidates", return_value=["one", "two"]
            ),
            patch.object(
                hardware.subprocess,
                "run",
                side_effect=hardware.subprocess.TimeoutExpired(cmd="x", timeout=1),
            ) as run,
        ):
            devices, summary, warning = hardware._query_nvidia_gpus()
        self.assertEqual(run.call_count, 1)
        self.assertEqual(devices, ())
        self.assertEqual(summary["status"], "error")
        self.assertIn("TimeoutExpired", warning or "")

    def test_nvidia_tool_that_ran_but_failed_is_not_retried_elsewhere(self) -> None:
        class Failed:
            returncode = 9
            stdout = ""
            stderr = ""

        with (
            patch.object(
                hardware, "_nvidia_smi_candidates", return_value=["one", "two"]
            ),
            patch.object(hardware.subprocess, "run", return_value=Failed()) as run,
        ):
            devices, summary, _warning = hardware._query_nvidia_gpus()
        self.assertEqual(run.call_count, 1)
        self.assertEqual(devices, ())
        self.assertEqual(summary["status"], "error")

    def test_windows_memory_snapshot_uses_measured_values(self) -> None:
        with patch.object(hardware, "_windows_memory", return_value=(48 * 1024**3, 29 * 1024**3)):
            with patch.object(hardware.os, "name", "nt"):
                result = hardware._memory_snapshot()
        self.assertEqual(result["physical_total_bytes"], 48 * 1024**3)
        self.assertEqual(result["available_bytes"], 29 * 1024**3)
        self.assertEqual(result["evidence"], "observed")

    def test_memory_failure_returns_unknown_and_warning(self) -> None:
        with patch.object(hardware, "_posix_memory", side_effect=OSError("hidden path")):
            with patch.object(hardware.os, "name", "posix"):
                result = hardware._memory_snapshot()
        self.assertIsNone(result["physical_total_bytes"])
        self.assertIsNone(result["available_bytes"])
        self.assertEqual(result["evidence"], "unknown")
        self.assertNotIn("hidden path", result["warning"])

    def test_storage_snapshot_does_not_emit_full_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "private"
            directory.mkdir()
            model_path = directory / "model.gguf"
            model_path.write_bytes(b"")
            with patch.object(hardware.shutil, "disk_usage") as disk_usage:
                disk_usage.return_value = type(
                    "Usage", (), {"total": 100, "used": 40, "free": 60}
                )()
                storage, warning = hardware._storage_snapshot(model_path)
        self.assertIsNone(warning)
        self.assertEqual(storage["volume"], model_path.anchor)
        self.assertNotIn(str(model_path), str(storage))
        self.assertNotIn("private", str(storage))

    def test_detect_snapshot_serializes_without_sensitive_path(self) -> None:
        with (
            patch.object(hardware, "_memory_snapshot", return_value={
                "physical_total_bytes": 48 * 1024**3,
                "available_bytes": 24 * 1024**3,
                "evidence": "observed",
                "source": "test",
            }),
            patch.object(hardware, "_query_nvidia_gpus", return_value=((), {
                "status": "unavailable", "source": None, "evidence": "unknown"
            }, None)),
            patch.object(hardware, "_storage_snapshot", return_value=({
                "volume": "E:\\", "total_bytes": 1000, "used_bytes": 500,
                "free_bytes": 500, "evidence": "observed", "source": "test",
                "device_type": None, "device_type_evidence": "unknown",
            }, None)),
        ):
            snapshot = hardware.detect_host_hardware(r"E:\Sensitive\Model.gguf")
        result = snapshot.to_dict()
        encoded = str(result)
        self.assertIn("schema_version", result)
        self.assertNotIn("Sensitive", encoded)
        self.assertEqual(result["system_memory"]["physical_total_bytes"], 48 * 1024**3)
        self.assertEqual(result["gpu_discovery"]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
