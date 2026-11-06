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


def meta_uint32(key: str, value: int) -> bytes:
    return gguf_string(key) + struct.pack("<II", 4, value)


def build_gguf(
    tensors: list[tuple[str, tuple[int, ...], int, int]],
    extra_metadata: list[bytes] | None = None,
) -> bytes:
    metadata = [meta_string("general.architecture", "llama"), *(extra_metadata or [])]
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

    def test_gguf_architecture_facts_are_extracted_with_sources(self) -> None:
        details = [
            ("llama.block_count", 32),
            ("llama.embedding_length", 4096),
            ("llama.attention.head_count", 32),
            ("llama.attention.head_count_kv", 8),
            ("llama.attention.key_length", 128),
            ("llama.attention.value_length", 128),
            ("llama.context_length", 32768),
            ("llama.feed_forward_length", 14336),
        ]
        metadata = [meta_uint32(key, value) for key, value in details]
        path = self.write("model.gguf", build_gguf([("blk.0.weight", (4, 8), 0, 0)], metadata))
        atlas = build_model_atlas(path)
        architecture = atlas["architecture"]["details"]
        self.assertEqual(architecture["layer_count"]["value"], 32)
        self.assertEqual(architecture["hidden_size"]["value"], 4096)
        self.assertEqual(architecture["attention_heads"]["value"], 32)
        self.assertEqual(architecture["kv_heads"]["value"], 8)
        self.assertEqual(architecture["key_head_dimension"]["value"], 128)
        self.assertEqual(architecture["value_head_dimension"]["value"], 128)
        self.assertEqual(architecture["context_length"]["value"], 32768)
        self.assertEqual(architecture["layer_count"]["evidence"], "observed")
        self.assertEqual(architecture["layer_count"]["source"], "llama.block_count")

    def test_hf_architecture_details_use_bounded_text_config_scalars(self) -> None:
        config = {
            "model_type": "multimodal-wrapper",
            "architectures": ["ExampleForConditionalGeneration"],
            "text_config": {
                "model_type": "llama",
                "num_hidden_layers": 32,
                "hidden_size": 4096,
                "num_attention_heads": 32,
                "num_key_value_heads": 8,
                "head_dim": 128,
                "max_position_embeddings": 65536,
                "num_local_experts": 8,
                "num_experts_per_tok": 2,
                "unrelated_large_value": "do not copy this field",
            },
        }
        self.write("config.json", json.dumps(config).encode("utf-8"))
        self.write("model.safetensors", build_safetensors(SINGLE, bytes(16)))
        atlas = build_model_atlas(self.root)
        details = atlas["architecture"]["details"]
        self.assertEqual(atlas["architecture"]["architecture"], "multimodal-wrapper")
        self.assertEqual(details["layer_count"]["value"], 32)
        self.assertEqual(details["hidden_size"]["value"], 4096)
        self.assertEqual(details["kv_heads"]["value"], 8)
        self.assertEqual(details["key_head_dimension"]["value"], 128)
        self.assertEqual(details["context_length"]["value"], 65536)
        self.assertEqual(details["expert_count"]["value"], 8)
        self.assertEqual(details["experts_per_token"]["value"], 2)
        self.assertEqual(details["layer_count"]["source"], "config.json:text_config:num_hidden_layers")
        self.assertEqual(details["layer_count"]["evidence"], "declared")

    def test_hf_architecture_aliases_are_read_as_declared_facts(self) -> None:
        config = {
            "model_type": "legacy-config",
            "n_layer": 24,
            "n_embd": 3072,
            "n_head": 24,
            "n_head_kv": 8,
            "head_dim": 128,
            "max_seq_len": 16384,
            "n_inner": 8192,
        }
        self.write("config.json", json.dumps(config).encode("utf-8"))
        self.write("model.safetensors", build_safetensors(SINGLE, bytes(16)))
        atlas = build_model_atlas(self.root)
        details = atlas["architecture"]["details"]
        self.assertEqual(details["layer_count"]["value"], 24)
        self.assertEqual(details["hidden_size"]["value"], 3072)
        self.assertEqual(details["attention_heads"]["value"], 24)
        self.assertEqual(details["kv_heads"]["value"], 8)
        self.assertEqual(details["key_head_dimension"]["value"], 128)
        self.assertEqual(details["value_head_dimension"]["value"], 128)
        self.assertEqual(details["context_length"]["value"], 16384)
        self.assertEqual(details["intermediate_size"]["value"], 8192)
        self.assertEqual(details["layer_count"]["evidence"], "declared")
        self.assertEqual(details["layer_count"]["source"], "config.json:n_layer")

    def test_conflicting_hf_architecture_aliases_remain_unknown(self) -> None:
        config = {
            "model_type": "conflicting-config",
            "num_hidden_layers": 32,
            "n_layer": 24,
            "hidden_size": 4096,
            "num_attention_heads": 32,
        }
        self.write("config.json", json.dumps(config).encode("utf-8"))
        self.write("model.safetensors", build_safetensors(SINGLE, bytes(16)))
        atlas = build_model_atlas(self.root)
        fact = atlas["architecture"]["details"]["layer_count"]
        self.assertIsNone(fact["value"])
        self.assertEqual(fact["evidence"], "unknown")
        self.assertIn("Conflicting architecture declarations", fact["reason"])
        self.assertIn("num_hidden_layers=32", fact["reason"])
        self.assertIn("n_layer=24", fact["reason"])

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
