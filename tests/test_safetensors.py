from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from eclipse.model_intelligence import (
    SafetensorsFormatError,
    SafetensorsLimits,
    SafetensorsResourceLimitError,
    inspect_safetensors,
)


def build_safetensors(header: object, data: bytes = b"", header_pad: int = 0) -> bytes:
    encoded = json.dumps(header).encode("utf-8") + b" " * header_pad
    return struct.pack("<Q", len(encoded)) + encoded + data


TWO_TENSORS = {
    "__metadata__": {"format": "pt"},
    "weight": {"dtype": "F32", "shape": [2, 2], "data_offsets": [0, 16]},
    "bias": {"dtype": "F16", "shape": [4], "data_offsets": [16, 24]},
}


class SafetensorsInspectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, data: bytes) -> Path:
        path = self.root / "fixture.safetensors"
        path.write_bytes(data)
        return path

    def test_inspects_header_and_tensors(self) -> None:
        report = inspect_safetensors(self.write(build_safetensors(TWO_TENSORS, bytes(24))))
        self.assertEqual(report["format"], "safetensors")
        self.assertEqual(report["tensor_count"], 2)
        self.assertEqual(report["data_region_bytes"], 24)
        self.assertEqual(report["total_tensor_storage_bytes"], 24)
        weight = report["tensors"][0]
        self.assertEqual(weight["name"], "weight")
        self.assertEqual(weight["dtype"], "F32")
        self.assertEqual(weight["shape"], [2, 2])
        self.assertEqual(weight["element_count"], 4)
        self.assertEqual(weight["storage_bytes"], 16)
        self.assertEqual(weight["storage_bytes_evidence"], "observed_header")
        self.assertEqual(weight["expected_bytes_from_shape"], 16)

    def test_reports_metadata(self) -> None:
        report = inspect_safetensors(self.write(build_safetensors(TWO_TENSORS, bytes(24))))
        self.assertEqual(report["metadata"], {"format": "pt"})

    def test_allows_empty_tensor_set(self) -> None:
        report = inspect_safetensors(self.write(build_safetensors({})))
        self.assertEqual(report["tensor_count"], 0)
        self.assertEqual(report["total_tensor_storage_bytes"], 0)

    def test_allows_zero_element_tensor(self) -> None:
        header = {"empty": {"dtype": "F32", "shape": [0], "data_offsets": [0, 0]}}
        report = inspect_safetensors(self.write(build_safetensors(header)))
        self.assertEqual(report["tensors"][0]["element_count"], 0)
        self.assertEqual(report["tensors"][0]["storage_bytes"], 0)

    def test_no_payload_reads_and_path_privacy(self) -> None:
        path = self.write(build_safetensors(TWO_TENSORS, bytes(24)))
        before = path.read_bytes()
        report = inspect_safetensors(path)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(report["inspection"]["tensor_payload_bytes_read"], 0)
        self.assertFalse(report["inspection"]["tensor_payloads_loaded"])
        self.assertEqual(report["source_file_name"], path.name)
        self.assertNotIn(str(path.parent), json.dumps(report))

    def test_rejects_too_small_file(self) -> None:
        with self.assertRaisesRegex(SafetensorsFormatError, "too small"):
            inspect_safetensors(self.write(b"short"))

    def test_rejects_zero_header_length(self) -> None:
        with self.assertRaisesRegex(SafetensorsFormatError, "greater than zero"):
            inspect_safetensors(self.write(struct.pack("<Q", 0)))

    def test_rejects_header_length_past_eof(self) -> None:
        with self.assertRaisesRegex(SafetensorsFormatError, "past the end"):
            inspect_safetensors(self.write(struct.pack("<Q", 1000) + b"{}"))

    def test_rejects_header_over_limit(self) -> None:
        data = build_safetensors({"w": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}, bytes(4))
        with self.assertRaises(SafetensorsResourceLimitError):
            inspect_safetensors(self.write(data), SafetensorsLimits(max_header_bytes=8))

    def test_rejects_invalid_json(self) -> None:
        payload = b"not json"
        with self.assertRaisesRegex(SafetensorsFormatError, "not valid JSON"):
            inspect_safetensors(self.write(struct.pack("<Q", len(payload)) + payload))

    def test_rejects_non_object_header(self) -> None:
        payload = b"[1, 2]"
        with self.assertRaisesRegex(SafetensorsFormatError, "must be a JSON object"):
            inspect_safetensors(self.write(struct.pack("<Q", len(payload)) + payload))

    def test_rejects_missing_offsets(self) -> None:
        header = {"w": {"dtype": "F32", "shape": [1]}}
        with self.assertRaisesRegex(SafetensorsFormatError, "data_offsets"):
            inspect_safetensors(self.write(build_safetensors(header)))

    def test_rejects_non_string_dtype(self) -> None:
        header = {"w": {"dtype": 5, "shape": [1], "data_offsets": [0, 4]}}
        with self.assertRaisesRegex(SafetensorsFormatError, "dtype must be a string"):
            inspect_safetensors(self.write(build_safetensors(header, bytes(4))))

    def test_rejects_offsets_out_of_range(self) -> None:
        header = {"w": {"dtype": "F32", "shape": [1], "data_offsets": [0, 100]}}
        with self.assertRaisesRegex(SafetensorsFormatError, "exceeds"):
            inspect_safetensors(self.write(build_safetensors(header, bytes(4))))

    def test_rejects_reversed_offsets(self) -> None:
        header = {"w": {"dtype": "F32", "shape": [1], "data_offsets": [8, 4]}}
        with self.assertRaisesRegex(SafetensorsFormatError, "start is after"):
            inspect_safetensors(self.write(build_safetensors(header, bytes(16))))

    def test_rejects_negative_offsets(self) -> None:
        header = {"w": {"dtype": "F32", "shape": [1], "data_offsets": [-4, 4]}}
        with self.assertRaisesRegex(SafetensorsFormatError, "negative"):
            inspect_safetensors(self.write(build_safetensors(header, bytes(4))))

    def test_rejects_overlapping_offsets(self) -> None:
        header = {
            "a": {"dtype": "F32", "shape": [2], "data_offsets": [0, 8]},
            "b": {"dtype": "F32", "shape": [2], "data_offsets": [4, 12]},
        }
        with self.assertRaisesRegex(SafetensorsFormatError, "overlap"):
            inspect_safetensors(self.write(build_safetensors(header, bytes(12))))

    def test_rejects_bad_metadata_container(self) -> None:
        header = {"__metadata__": 5}
        with self.assertRaisesRegex(SafetensorsFormatError, "__metadata__"):
            inspect_safetensors(self.write(build_safetensors(header)))

    def test_rejects_tensor_count_limit(self) -> None:
        with self.assertRaises(SafetensorsResourceLimitError):
            inspect_safetensors(
                self.write(build_safetensors(TWO_TENSORS, bytes(24))),
                SafetensorsLimits(max_tensors=1),
            )

    def test_rejects_shape_dimension_limit(self) -> None:
        header = {"w": {"dtype": "F32", "shape": [1] * 5, "data_offsets": [0, 4]}}
        with self.assertRaises(SafetensorsResourceLimitError):
            inspect_safetensors(
                self.write(build_safetensors(header, bytes(4))),
                SafetensorsLimits(max_shape_dimensions=4),
            )

    def test_warns_when_shape_and_range_disagree(self) -> None:
        header = {"w": {"dtype": "F32", "shape": [2, 2], "data_offsets": [0, 8]}}
        report = inspect_safetensors(self.write(build_safetensors(header, bytes(8))))
        self.assertTrue(any("do not match" in warning for warning in report["warnings"]))

    def test_unknown_dtype_reports_observed_bytes_and_warns(self) -> None:
        header = {"w": {"dtype": "FROBNICATE", "shape": [4], "data_offsets": [0, 8]}}
        report = inspect_safetensors(self.write(build_safetensors(header, bytes(8))))
        tensor = report["tensors"][0]
        self.assertEqual(tensor["storage_bytes"], 8)
        self.assertIsNone(tensor["expected_bytes_from_shape"])
        self.assertTrue(any("Unrecognized tensor dtypes" in warning for warning in report["warnings"]))

    def test_cli_emits_valid_json(self) -> None:
        path = self.write(build_safetensors(TWO_TENSORS, bytes(24)))
        result = subprocess.run(
            [sys.executable, "-m", "eclipse", "inspect-safetensors", str(path), "--compact"],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["format"], "safetensors")
        self.assertEqual(parsed["tensor_count"], 2)


if __name__ == "__main__":
    unittest.main()
