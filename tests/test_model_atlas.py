from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from eclipse.model_intelligence import (
    ModelAtlasError,
    ModelAtlasFormatError,
    ModelAtlasLimits,
    build_model_atlas,
)


def gguf_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<Q", len(encoded)) + encoded


def meta_string(key: str, value: str) -> bytes:
    return gguf_string(key) + struct.pack("<I", 8) + gguf_string(value)


def build_gguf(tensors: list[tuple[str, tuple[int, ...], int, int]]) -> bytes:
    metadata = [meta_string("general.architecture", "llama")]
    body = bytearray(b"GGUF")
    body += struct.pack("<IQQ", 3, len(tensors), len(metadata))
    body += b"".join(metadata)
    for name, dims, type_id, offset in tensors:
        body += gguf_string(name)
        body += struct.pack("<I", len(dims))
        body += b"".join(struct.pack("<Q", value) for value in dims)
        body += struct.pack("<IQ", type_id, offset)
    body += b"\x00" * ((32 - (len(body) % 32)) % 32)
    body += b"\x00" * 512
    return bytes(body)


def build_safetensors(header: object, data: bytes = b"") -> bytes:
    encoded = json.dumps(header).encode("utf-8")
    return struct.pack("<Q", len(encoded)) + encoded + data


SINGLE = {"weight": {"dtype": "F32", "shape": [2, 2], "data_offsets": [0, 16]}}
SHARD_A = {"a": {"dtype": "F32", "shape": [2, 2], "data_offsets": [0, 16]}}
SHARD_B = {"b": {"dtype": "F16", "shape": [4], "data_offsets": [0, 8]}}


class ModelAtlasTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name: str, data: bytes) -> Path:
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_builds_atlas_from_gguf(self) -> None:
        path = self.write(
            "model.gguf",
            build_gguf([("blk.0.weight", (4, 8), 0, 0), ("blk.0.bias", (8,), 0, 128)]),
        )
        atlas = build_model_atlas(path)
        self.assertEqual(atlas["format"], "eclipse_model_atlas")
        self.assertEqual(atlas["source_kind"], "gguf")
        self.assertEqual(atlas["summary"]["tensor_count"], 2)
        self.assertEqual(atlas["summary"]["total_parameters"], 40)
        self.assertEqual(atlas["summary"]["total_storage_bytes"], 160)
        self.assertEqual(atlas["summary"]["distribution"]["label"], "ggml_type")
        self.assertEqual(atlas["summary"]["storage_evidence"], "derived")
        self.assertEqual(atlas["evidence"]["parameters"], "observed")
        self.assertEqual(atlas["architecture"]["architecture"], "llama")
        self.assertFalse(atlas["inspection"]["tensor_payloads_loaded"])

    def test_builds_atlas_from_safetensors(self) -> None:
        path = self.write("model.safetensors", build_safetensors(SINGLE, bytes(16)))
        atlas = build_model_atlas(path)
        self.assertEqual(atlas["source_kind"], "safetensors")
        self.assertEqual(atlas["summary"]["tensor_count"], 1)
        self.assertEqual(atlas["summary"]["total_parameters"], 4)
        self.assertEqual(atlas["summary"]["total_storage_bytes"], 16)
        self.assertEqual(atlas["summary"]["distribution"]["label"], "safetensors_dtype")
        self.assertEqual(atlas["summary"]["storage_evidence"], "observed")
        self.assertEqual(atlas["architecture"]["evidence"], "unknown")

    def test_builds_atlas_from_folder(self) -> None:
        config = {"model_type": "llama", "architectures": ["LlamaForCausalLM"]}
        self.write("config.json", json.dumps(config).encode("utf-8"))
        self.write("model-00001-of-00002.safetensors", build_safetensors(SHARD_A, bytes(16)))
        self.write("model-00002-of-00002.safetensors", build_safetensors(SHARD_B, bytes(8)))
        self.write(
            "model.safetensors.index.json",
            json.dumps(
                {
                    "metadata": {"total_size": 24},
                    "weight_map": {
                        "a": "model-00001-of-00002.safetensors",
                        "b": "model-00002-of-00002.safetensors",
                    },
                }
            ).encode("utf-8"),
        )
        atlas = build_model_atlas(self.root)
        self.assertEqual(atlas["source_kind"], "huggingface_folder")
        self.assertEqual(atlas["architecture"]["architecture"], "llama")
        self.assertEqual(atlas["summary"]["tensor_count"], 2)
        self.assertEqual(atlas["summary"]["total_parameters"], 8)
        self.assertEqual(atlas["summary"]["total_storage_bytes"], 24)
        self.assertTrue(atlas["summary"]["total_storage_is_complete"])
        self.assertEqual(atlas["components"]["folder"]["inspected_shard_count"], 2)
        self.assertFalse(
            any("differ from the index metadata.total_size" in warning for warning in atlas["warnings"])
        )

    def test_folder_with_missing_index_shard_is_incomplete(self) -> None:
        self.write("config.json", b'{"model_type": "llama"}')
        self.write("present.safetensors", build_safetensors(SINGLE, bytes(16)))
        self.write(
            "model.safetensors.index.json",
            json.dumps(
                {
                    "metadata": {"total_size": 20},
                    "weight_map": {
                        "weight": "present.safetensors",
                        "other": "missing.safetensors",
                    },
                }
            ).encode("utf-8"),
        )
        atlas = build_model_atlas(self.root)
        self.assertEqual(atlas["summary"]["total_storage_bytes"], 16)
        self.assertFalse(atlas["summary"]["total_storage_is_complete"])
        self.assertEqual(atlas["components"]["folder"]["missing_shard_count"], 1)

    def test_unreferenced_shard_is_not_counted_as_model_weights(self) -> None:
        self.write("config.json", b'{"model_type": "llama"}')
        self.write("referenced.safetensors", build_safetensors(SINGLE, bytes(16)))
        self.write("extra.safetensors", build_safetensors(SHARD_B, bytes(8)))
        self.write(
            "model.safetensors.index.json",
            json.dumps(
                {
                    "metadata": {"total_size": 16},
                    "weight_map": {"weight": "referenced.safetensors"},
                }
            ).encode("utf-8"),
        )
        atlas = build_model_atlas(self.root)
        self.assertEqual(atlas["summary"]["tensor_count"], 1)
        self.assertEqual(atlas["summary"]["total_storage_bytes"], 16)
        self.assertTrue(atlas["summary"]["total_storage_is_complete"])
        self.assertEqual(atlas["components"]["folder"]["inspected_shard_count"], 1)

    def test_folder_with_mismatched_declared_tensor_bytes_is_incomplete(self) -> None:
        self.write("config.json", b'{"model_type": "llama"}')
        self.write("model.safetensors", build_safetensors(SINGLE, bytes(16)))
        self.write(
            "model.safetensors.index.json",
            json.dumps(
                {
                    "metadata": {"total_size": 99},
                    "weight_map": {"weight": "model.safetensors"},
                }
            ).encode("utf-8"),
        )
        atlas = build_model_atlas(self.root)
        self.assertFalse(atlas["summary"]["total_storage_is_complete"])
        self.assertTrue(
            any("differ from the index metadata.total_size" in warning for warning in atlas["warnings"])
        )

    def test_folder_with_corrupt_shard_is_incomplete_and_warns(self) -> None:
        self.write("config.json", b'{"model_type": "llama"}')
        self.write("good.safetensors", build_safetensors(SINGLE, bytes(16)))
        self.write("bad.safetensors", b"xx")
        atlas = build_model_atlas(self.root)
        self.assertFalse(atlas["summary"]["total_storage_is_complete"])
        self.assertTrue(any("Could not inspect" in warning for warning in atlas["warnings"]))
        self.assertEqual(atlas["summary"]["tensor_count"], 1)

    def test_rejects_unsupported_input(self) -> None:
        path = self.write("model.bin", b"data")
        with self.assertRaisesRegex(ModelAtlasFormatError, "Unsupported input"):
            build_model_atlas(path)

    def test_rejects_folder_over_shard_limit(self) -> None:
        self.write("config.json", b"{}")
        self.write("a.safetensors", build_safetensors(SINGLE, bytes(16)))
        self.write("b.safetensors", build_safetensors(SINGLE, bytes(16)))
        with self.assertRaises(ModelAtlasError):
            build_model_atlas(self.root, ModelAtlasLimits(max_shards=1))

    def test_rejects_bad_limit(self) -> None:
        with self.assertRaises(ValueError):
            ModelAtlasLimits(max_shards=-1)

    def test_cli_emits_valid_json(self) -> None:
        path = self.write("model.safetensors", build_safetensors(SINGLE, bytes(16)))
        result = subprocess.run(
            [sys.executable, "-m", "eclipse", "build-atlas", str(path), "--compact"],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["format"], "eclipse_model_atlas")
        self.assertEqual(parsed["source_kind"], "safetensors")


if __name__ == "__main__":
    unittest.main()
