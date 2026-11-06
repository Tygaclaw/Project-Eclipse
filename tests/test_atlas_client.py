from __future__ import annotations

import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
import time
import unittest

from eclipse.desktop.atlas_client import (
    AtlasCancelledError,
    AtlasClient,
    AtlasClientError,
    AtlasOutputError,
    AtlasTimeoutError,
    default_backend_command,
    validate_atlas_document,
)


def gguf_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<Q", len(encoded)) + encoded


def meta_string(key: str, value: str) -> bytes:
    return gguf_string(key) + struct.pack("<I", 8) + gguf_string(value)


def build_gguf() -> bytes:
    metadata = [meta_string("general.architecture", "llama")]
    body = bytearray(b"GGUF")
    body += struct.pack("<IQQ", 3, 1, len(metadata))
    body += b"".join(metadata)
    body += gguf_string("blk.0.weight")
    body += struct.pack("<I", 2)
    body += struct.pack("<Q", 4) + struct.pack("<Q", 8)
    body += struct.pack("<IQ", 0, 0)
    body += b"\x00" * ((32 - (len(body) % 32)) % 32)
    body += b"\x00" * 128
    return bytes(body)


def minimal_atlas(**inspection_overrides: object) -> dict[str, object]:
    inspection = {
        "mode": "static_read_only",
        "tensor_payload_bytes_read": 0,
        "tensor_payloads_loaded": False,
        "source_modified": False,
    }
    inspection.update(inspection_overrides)
    return {
        "format": "eclipse_model_atlas",
        "atlas_version": 1,
        "source_kind": "gguf",
        "source_name": "model.gguf",
        "architecture": {"architecture": "llama", "name": None, "evidence": "observed_metadata"},
        "summary": {
            "tensor_count": 1,
            "total_parameters": 32,
            "total_storage_bytes": 128,
            "total_storage_is_complete": True,
            "distribution": {"label": "ggml_type", "counts": {"f32": 1}},
            "parameters_evidence": "observed",
            "storage_evidence": "derived",
        },
        "components": {"gguf": {"version": 3, "endianness": "little", "file_size_bytes": 512}},
        "warnings": [],
        "evidence": {"parameters": "observed", "storage_bytes": "derived", "architecture": "observed_metadata"},
        "inspection": inspection,
    }


class AtlasClientCommandTests(unittest.TestCase):
    def test_default_command_is_an_argument_list_without_shell_interpolation(self) -> None:
        path = "C:/Models/My Model/model.gguf"
        command = default_backend_command(path, executable="python.exe")
        self.assertIsInstance(command, list)
        self.assertIn(path, command)
        self.assertEqual(command[-2:], [path, "--compact"])
        self.assertEqual(command[:3], ["python.exe", "-m", "eclipse"])

    def test_rejects_empty_source(self) -> None:
        with self.assertRaises(AtlasClientError):
            AtlasClient(command_factory=lambda path: [sys.executable, "-c", "print('{}')"]).build("")

    def test_frozen_command_relaunches_the_packaged_executable(self) -> None:
        from unittest.mock import patch

        with patch("eclipse.desktop.atlas_client.sys.frozen", True, create=True):
            command = default_backend_command(r"C:\Models\model.gguf", executable=r"C:\App\ECLIPSE.exe")
        self.assertEqual(
            command,
            [r"C:\App\ECLIPSE.exe", "--atlas-backend", r"C:\Models\model.gguf", "--compact"],
        )

    def test_rejects_invalid_command_vector(self) -> None:
        client = AtlasClient(command_factory=lambda path: [sys.executable, "  "])
        with self.assertRaises(AtlasClientError):
            client.build("model.gguf")


class AtlasClientBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def script_client(self, script: str, **kwargs: object) -> AtlasClient:
        return AtlasClient(
            command_factory=lambda path: [sys.executable, "-c", script],
            timeout_seconds=kwargs.pop("timeout_seconds", 20.0),
            **kwargs,
        )

    def test_builds_a_validated_atlas_from_the_existing_backend(self) -> None:
        model = self.root / "model.gguf"
        model.write_bytes(build_gguf())
        atlas = AtlasClient(timeout_seconds=60.0).build(model)
        self.assertEqual(atlas["format"], "eclipse_model_atlas")
        self.assertEqual(atlas["source_kind"], "gguf")
        self.assertEqual(atlas["source_name"], "model.gguf")
        self.assertEqual(atlas["summary"]["tensor_count"], 1)
        self.assertFalse(atlas["inspection"]["tensor_payloads_loaded"])
        self.assertNotIn(str(self.root), json.dumps(atlas))

    def test_rejects_invalid_json(self) -> None:
        with self.assertRaises(AtlasOutputError):
            self.script_client("print('not json')").build("model.gguf")

    def test_rejects_wrong_document_shape(self) -> None:
        with self.assertRaises(AtlasOutputError):
            self.script_client("import json; print(json.dumps({'format': 'other'}))").build("model.gguf")

    def test_rejects_an_atlas_that_claims_to_load_tensor_payloads(self) -> None:
        document = minimal_atlas(tensor_payloads_loaded=True)
        with self.assertRaises(AtlasOutputError):
            validate_atlas_document(document)

    def test_rejects_an_atlas_that_reads_payload_bytes(self) -> None:
        document = minimal_atlas(tensor_payload_bytes_read=1)
        with self.assertRaises(AtlasOutputError):
            validate_atlas_document(document)

    def test_rejects_an_atlas_that_modifies_the_source(self) -> None:
        document = minimal_atlas(source_modified=True)
        with self.assertRaises(AtlasOutputError):
            validate_atlas_document(document)

    def test_accepts_the_validated_contract(self) -> None:
        self.assertIs(validate_atlas_document(minimal_atlas())["format"], "eclipse_model_atlas")

    def test_bounds_stdout(self) -> None:
        client = self.script_client("print('x' * 10000)", max_output_bytes=100)
        with self.assertRaises(AtlasOutputError):
            client.build("model.gguf")

    def test_reports_backend_stderr_on_failure(self) -> None:
        script = "import sys; print('invalid GGUF header', file=sys.stderr); sys.exit(2)"
        with self.assertRaises(AtlasClientError) as context:
            self.script_client(script).build("model.gguf")
        self.assertIn("invalid GGUF header", str(context.exception))

    def test_cancellation_stops_a_running_backend(self) -> None:
        client = self.script_client("import time; time.sleep(30)")
        cancel = threading.Event()
        timer = threading.Timer(0.2, cancel.set)
        timer.start()
        self.addCleanup(timer.cancel)
        started = time.monotonic()
        with self.assertRaises(AtlasCancelledError):
            client.build("model.gguf", cancel_event=cancel)
        self.assertLess(time.monotonic() - started, 10.0)

    def test_timeout_stops_a_running_backend(self) -> None:
        client = self.script_client("import time; time.sleep(30)", timeout_seconds=0.3)
        started = time.monotonic()
        with self.assertRaises(AtlasTimeoutError):
            client.build("model.gguf")
        self.assertLess(time.monotonic() - started, 10.0)

    def test_invalid_limits_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AtlasClient(timeout_seconds=0)
        with self.assertRaises(ValueError):
            AtlasClient(max_output_bytes=0)


if __name__ == "__main__":
    unittest.main()