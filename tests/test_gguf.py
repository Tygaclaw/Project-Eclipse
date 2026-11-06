from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eclipse.model_intelligence import (
    GGML_TYPE_TRAITS_REVISION,
    GGUFFormatError,
    GGUFResourceLimitError,
    InspectionLimits,
    inspect_gguf,
)


def gguf_string(value: str, endian: str = "<") -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack(endian + "Q", len(encoded)) + encoded


def meta_string(key: str, value: str, endian: str = "<") -> bytes:
    return gguf_string(key, endian) + struct.pack(endian + "I", 8) + gguf_string(value, endian)


def meta_uint32(key: str, value: int, endian: str = "<") -> bytes:
    return gguf_string(key, endian) + struct.pack(endian + "I", 4) + struct.pack(endian + "I", value)


def meta_bool(key: str, value: int, endian: str = "<") -> bytes:
    return gguf_string(key, endian) + struct.pack(endian + "I", 7) + struct.pack(endian + "B", value)


def meta_float32(key: str, value: float, endian: str = "<") -> bytes:
    return gguf_string(key, endian) + struct.pack(endian + "I", 6) + struct.pack(endian + "f", value)


def meta_string_array(key: str, values: list[str], endian: str = "<") -> bytes:
    data = gguf_string(key, endian) + struct.pack(endian + "I", 9)
    data += struct.pack(endian + "I", 8) + struct.pack(endian + "Q", len(values))
    return data + b"".join(gguf_string(value, endian) for value in values)


def build_gguf(
    *,
    version: int = 3,
    endian: str = "<",
    metadata: list[bytes] | None = None,
    tensors: list[tuple[str, tuple[int, ...], int, int]] | None = None,
    payload_bytes: int = 128,
) -> bytes:
    metadata = metadata if metadata is not None else [
        meta_string("general.architecture", "llama", endian),
        meta_uint32("general.alignment", 32, endian),
    ]
    tensors = tensors if tensors is not None else [("blk.0.weight", (4, 8), 0, 0)]
    body = bytearray(b"GGUF")
    body += struct.pack(endian + "IQQ", version, len(tensors), len(metadata))
    body += b"".join(metadata)
    for name, dims, type_id, offset in tensors:
        body += gguf_string(name, endian)
        body += struct.pack(endian + "I", len(dims))
        body += b"".join(struct.pack(endian + "Q", value) for value in dims)
        body += struct.pack(endian + "IQ", type_id, offset)
    alignment = 32
    body += b"\x00" * ((alignment - (len(body) % alignment)) % alignment)
    body += b"\x00" * payload_bytes
    return bytes(body)


class GGUFInspectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, data: bytes) -> Path:
        path = self.root / "fixture.gguf"
        path.write_bytes(data)
        return path

    def test_inspects_v3_header_metadata_and_tensor_index(self) -> None:
        report = inspect_gguf(self.write(build_gguf()))
        self.assertEqual(report["format"], "GGUF")
        self.assertEqual(report["version"], 3)
        self.assertEqual(report["model"]["architecture"], "llama")
        self.assertEqual(report["tensor_count"], 1)
        self.assertEqual(report["tensors"][0]["dimensions"], [4, 8])
        self.assertEqual(report["tensors"][0]["type_name"], "f32")
        self.assertEqual(report["tensors"][0]["relative_data_offset"], 0)

    def test_inspects_v2(self) -> None:
        report = inspect_gguf(self.write(build_gguf(version=2)))
        self.assertEqual(report["version"], 2)

    def test_inspects_big_endian_v3(self) -> None:
        report = inspect_gguf(self.write(build_gguf(version=3, endian=">")))
        self.assertEqual(report["endianness"], "big")
        self.assertEqual(report["model"]["architecture"], "llama")

    def test_reports_unknown_tensor_types_without_guessing(self) -> None:
        data = build_gguf(tensors=[("custom.weight", (4,), 65500, 0)])
        report = inspect_gguf(self.write(data))
        self.assertEqual(report["tensors"][0]["type_name"], "unknown_65500")
        self.assertTrue(any("without guessing" in warning for warning in report["warnings"]))

    def test_reports_no_tensor_payload_reads(self) -> None:
        report = inspect_gguf(self.write(build_gguf()))
        self.assertEqual(report["inspection"]["tensor_payload_bytes_read"], 0)
        self.assertFalse(report["inspection"]["tensor_payloads_loaded"])
        self.assertEqual(report["tensors"][0]["storage_bytes"], 128)
        self.assertEqual(report["tensors"][0]["storage_bytes_evidence"], "derived")

    def test_string_array_preview_is_bounded(self) -> None:
        metadata = [meta_string_array("tokenizer.tokens", ["one", "two", "three"]), meta_uint32("general.alignment", 32)]
        report = inspect_gguf(self.write(build_gguf(metadata=metadata)), InspectionLimits(max_array_preview_items=2))
        value = report["metadata"]["tokenizer.tokens"]
        self.assertEqual(value["count"], 3)
        self.assertEqual(value["preview"], ["one", "two"])
        self.assertTrue(value["preview_truncated"])

    def test_rejects_array_item_limit(self) -> None:
        metadata = [meta_string_array("tokenizer.tokens", ["a", "b", "c"]), meta_uint32("general.alignment", 32)]
        with self.assertRaises(GGUFResourceLimitError):
            inspect_gguf(self.write(build_gguf(metadata=metadata)), InspectionLimits(max_array_items=2))

    def test_rejects_bad_magic(self) -> None:
        with self.assertRaisesRegex(GGUFFormatError, "magic"):
            inspect_gguf(self.write(b"NOPE" + bytes(128)))

    def test_rejects_unsupported_version(self) -> None:
        with self.assertRaisesRegex(GGUFFormatError, "Unsupported GGUF version"):
            inspect_gguf(self.write(build_gguf(version=4)))

    def test_rejects_truncated_header(self) -> None:
        with self.assertRaises(GGUFFormatError):
            inspect_gguf(self.write(b"GGUF\x03\x00\x00\x00"))

    def test_rejects_excess_tensor_count_before_tensor_loop(self) -> None:
        raw = b"GGUF" + struct.pack("<IQQ", 3, 5, 0)
        with self.assertRaises(GGUFResourceLimitError):
            inspect_gguf(self.write(raw), InspectionLimits(max_tensors=4))

    def test_rejects_duplicate_metadata_keys(self) -> None:
        metadata = [meta_string("general.architecture", "llama"), meta_string("general.architecture", "other")]
        with self.assertRaisesRegex(GGUFFormatError, "Duplicate metadata key"):
            inspect_gguf(self.write(build_gguf(metadata=metadata)))

    def test_rejects_invalid_alignment(self) -> None:
        metadata = [meta_string("general.architecture", "llama"), meta_uint32("general.alignment", 7)]
        with self.assertRaisesRegex(GGUFFormatError, "multiple of 8"):
            inspect_gguf(self.write(build_gguf(metadata=metadata)))

    def test_rejects_unaligned_tensor_offset(self) -> None:
        data = build_gguf(tensors=[("weight", (4,), 0, 1)])
        with self.assertRaisesRegex(GGUFFormatError, "not aligned"):
            inspect_gguf(self.write(data))

    def test_rejects_tensor_offset_outside_data(self) -> None:
        data = build_gguf(tensors=[("weight", (4,), 0, 4096)])
        with self.assertRaisesRegex(GGUFFormatError, "outside the tensor-data region"):
            inspect_gguf(self.write(data))

    def test_rejects_zero_dimension(self) -> None:
        data = build_gguf(tensors=[("weight", (4, 0), 0, 0)])
        with self.assertRaisesRegex(GGUFFormatError, "zero-length dimension"):
            inspect_gguf(self.write(data))

    def test_rejects_duplicate_tensor_names(self) -> None:
        data = build_gguf(tensors=[("weight", (4,), 0, 0), ("weight", (4,), 0, 32)])
        with self.assertRaisesRegex(GGUFFormatError, "Duplicate tensor name"):
            inspect_gguf(self.write(data))

    def test_rejects_tensor_dimension_limit(self) -> None:
        data = build_gguf(tensors=[("weight", (1, 1, 1, 1, 1), 0, 0)])
        with self.assertRaisesRegex(GGUFFormatError, "dimension count"):
            inspect_gguf(self.write(data))

    def test_rejects_invalid_boolean_metadata(self) -> None:
        metadata = [meta_bool("general.test_flag", 2)]
        with self.assertRaisesRegex(GGUFFormatError, "Invalid GGUF boolean"):
            inspect_gguf(self.write(build_gguf(metadata=metadata, tensors=[])))

    def test_rejects_non_finite_float_metadata(self) -> None:
        metadata = [meta_float32("general.test_value", float("nan"))]
        with self.assertRaisesRegex(GGUFFormatError, "Non-finite floating-point"):
            inspect_gguf(self.write(build_gguf(metadata=metadata, tensors=[])))

    def test_enforces_metadata_count_limit(self) -> None:
        raw = b"GGUF" + struct.pack("<IQQ", 3, 0, 2)
        with self.assertRaises(GGUFResourceLimitError):
            inspect_gguf(self.write(raw), InspectionLimits(max_metadata_entries=1))

    def test_cli_emits_valid_json(self) -> None:
        path = self.write(build_gguf())
        result = subprocess.run(
            [sys.executable, "-m", "eclipse", "inspect-gguf", str(path), "--compact"],
            cwd=Path(__file__).resolve().parents[1],
            env={**__import__("os").environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["format"], "GGUF")
        self.assertEqual(parsed["tensor_count"], 1)

    def test_source_bytes_are_unchanged_and_path_is_not_reported(self) -> None:
        path = self.write(build_gguf())
        before = path.read_bytes()
        report = inspect_gguf(path)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(report["source_file_name"], path.name)
        self.assertNotIn(str(path.parent), json.dumps(report))

    def test_derives_exact_storage_bytes_for_quantized_tensor(self) -> None:
        data = build_gguf(tensors=[("w", (32,), 2, 0)])
        report = inspect_gguf(self.write(data))
        tensor = report["tensors"][0]
        self.assertEqual(tensor["storage_bytes"], 18)
        self.assertEqual(tensor["storage_bytes_evidence"], "derived")
        self.assertEqual(tensor["block_size"], 32)
        self.assertEqual(tensor["type_size_bytes"], 18)

    def test_derives_multi_block_storage_bytes(self) -> None:
        data = build_gguf(tensors=[("w", (256,), 12, 0)])
        report = inspect_gguf(self.write(data))
        self.assertEqual(report["tensors"][0]["storage_bytes"], 144)
        self.assertEqual(report["tensor_storage"]["total_bytes"], 144)
        self.assertTrue(report["tensor_storage"]["total_is_complete"])
        self.assertEqual(report["tensor_storage"]["registry_revision"], GGML_TYPE_TRAITS_REVISION)

    def test_unknown_tensor_type_leaves_storage_unknown(self) -> None:
        data = build_gguf(tensors=[("w", (4,), 65500, 0)])
        report = inspect_gguf(self.write(data))
        tensor = report["tensors"][0]
        self.assertIsNone(tensor["storage_bytes"])
        self.assertEqual(tensor["storage_bytes_evidence"], "unknown")
        self.assertEqual(tensor["storage_bytes_unknown_reason"], "unknown_type")
        self.assertTrue(any("could not be derived" in warning for warning in report["warnings"]))

    def test_undivisible_row_leaves_storage_unknown(self) -> None:
        data = build_gguf(tensors=[("w", (8, 2), 2, 0)])
        report = inspect_gguf(self.write(data))
        tensor = report["tensors"][0]
        self.assertIsNone(tensor["storage_bytes"])
        self.assertEqual(tensor["storage_bytes_unknown_reason"], "row_not_divisible_by_block")
        self.assertFalse(report["tensor_storage"]["total_is_complete"])

    def test_warns_when_declared_storage_exceeds_file(self) -> None:
        data = build_gguf(tensors=[("w", (4, 8), 0, 0)], payload_bytes=16)
        report = inspect_gguf(self.write(data))
        self.assertEqual(report["tensors"][0]["storage_bytes"], 128)
        self.assertTrue(any("past the end of the file" in warning for warning in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
