from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eclipse.model_intelligence import (
    HFFolderFormatError,
    HFFolderLimits,
    HFFolderResourceLimitError,
    inspect_hf_folder,
)

CONFIG = {
    "model_type": "llama",
    "architectures": ["LlamaForCausalLM"],
    "torch_dtype": "bfloat16",
    "num_hidden_layers": 32,
    "hidden_size": 4096,
    "quantization_config": {"quant_method": "awq"},
}


def index_document(weight_map: dict[str, str], total_size: int | None = None) -> bytes:
    document: dict[str, object] = {"metadata": {}, "weight_map": weight_map}
    if total_size is not None:
        document["metadata"] = {"total_size": total_size}
    return json.dumps(document).encode("utf-8")


class HFFolderInspectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name: str, data: bytes) -> Path:
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_inspects_folder_with_index(self) -> None:
        self.write("config.json", json.dumps(CONFIG).encode("utf-8"))
        self.write("model-00001-of-00002.safetensors", bytes(100))
        self.write("model-00002-of-00002.safetensors", bytes(50))
        self.write(
            "model.safetensors.index.json",
            index_document(
                {
                    "a": "model-00001-of-00002.safetensors",
                    "b": "model-00002-of-00002.safetensors",
                },
                total_size=150,
            ),
        )

        report = inspect_hf_folder(self.root)

        self.assertEqual(report["format"], "huggingface_folder")
        self.assertEqual(report["config"]["model_type"], "llama")
        self.assertEqual(report["config"]["architectures"], ["LlamaForCausalLM"])
        self.assertEqual(report["config"]["quantization_method"], "awq")
        self.assertTrue(report["config"]["has_quantization_config"])
        self.assertEqual(report["safetensors"]["shard_count"], 2)
        self.assertEqual(report["safetensors"]["total_bytes"], 150)
        index = report["safetensors"]["index"]
        self.assertEqual(index["tensor_count"], 2)
        self.assertEqual(index["referenced_shard_count"], 2)
        self.assertEqual(
            index["referenced_shards"],
            ["model-00001-of-00002.safetensors", "model-00002-of-00002.safetensors"],
        )
        self.assertEqual(index["declared_total_size_bytes"], 150)
        self.assertEqual(index["missing_shards"], [])
        self.assertEqual(index["unreferenced_shards"], [])
        self.assertEqual(report["evidence"]["index_weight_map"], "observed")
        self.assertFalse(report["inspection"]["tensor_payloads_loaded"])

    def test_warns_on_missing_referenced_shard(self) -> None:
        self.write("config.json", b"{}")
        self.write("model-00001-of-00002.safetensors", bytes(10))
        self.write(
            "model.safetensors.index.json",
            index_document(
                {
                    "a": "model-00001-of-00002.safetensors",
                    "b": "model-00002-of-00002.safetensors",
                }
            ),
        )
        report = inspect_hf_folder(self.root)
        self.assertEqual(
            report["safetensors"]["index"]["missing_shards"], ["model-00002-of-00002.safetensors"]
        )
        self.assertTrue(any("not present" in warning for warning in report["warnings"]))

    def test_warns_on_unreferenced_shard(self) -> None:
        self.write("config.json", b"{}")
        self.write("model-00001-of-00002.safetensors", bytes(10))
        self.write("model-extra.safetensors", bytes(5))
        self.write(
            "model.safetensors.index.json",
            index_document({"a": "model-00001-of-00002.safetensors"}),
        )
        report = inspect_hf_folder(self.root)
        self.assertEqual(
            report["safetensors"]["index"]["unreferenced_shards"], ["model-extra.safetensors"]
        )
        self.assertTrue(any("not referenced" in warning for warning in report["warnings"]))

    def test_does_not_compare_tensor_total_to_complete_shard_file_size(self) -> None:
        self.write("config.json", b"{}")
        self.write("model.safetensors", bytes(10))
        self.write(
            "model.safetensors.index.json",
            index_document({"a": "model.safetensors"}, total_size=99),
        )
        report = inspect_hf_folder(self.root)
        self.assertEqual(report["safetensors"]["index"]["declared_total_size_bytes"], 99)
        self.assertEqual(report["safetensors"]["total_bytes"], 10)
        self.assertFalse(
            any("differ from the index declared total_size" in warning for warning in report["warnings"])
        )

    def test_rejects_shard_name_with_separator(self) -> None:
        self.write("config.json", b"{}")
        self.write(
            "model.safetensors.index.json",
            index_document({"a": "../escape.safetensors"}),
        )
        with self.assertRaisesRegex(HFFolderFormatError, "path separator"):
            inspect_hf_folder(self.root)

    def test_rejects_invalid_config_json(self) -> None:
        self.write("config.json", b"not json")
        with self.assertRaisesRegex(HFFolderFormatError, "not valid JSON"):
            inspect_hf_folder(self.root)

    def test_rejects_index_without_weight_map(self) -> None:
        self.write("config.json", b"{}")
        self.write("model.safetensors.index.json", b'{"metadata": {}}')
        with self.assertRaisesRegex(HFFolderFormatError, "weight_map"):
            inspect_hf_folder(self.root)

    def test_oversized_config_is_reported_not_parsed(self) -> None:
        self.write("config.json", b"x" * 64)
        report = inspect_hf_folder(self.root, HFFolderLimits(max_config_bytes=8))
        self.assertIsNone(report["config"])
        self.assertIsNotNone(report["config_error"])
        self.assertEqual(report["evidence"]["config_fields"], "unknown")
        self.assertTrue(any("config.json" in warning for warning in report["warnings"]))

    def test_warns_when_no_safetensors_or_config(self) -> None:
        self.write("README.md", b"hello")
        report = inspect_hf_folder(self.root)
        self.assertEqual(report["safetensors"]["shard_count"], 0)
        self.assertTrue(any("No .safetensors files" in warning for warning in report["warnings"]))
        self.assertTrue(any("config.json was not found" in warning for warning in report["warnings"]))

    def test_rejects_non_directory(self) -> None:
        path = self.write("model.safetensors", bytes(8))
        with self.assertRaisesRegex(HFFolderFormatError, "not a directory"):
            inspect_hf_folder(path)

    def test_rejects_entry_limit(self) -> None:
        self.write("a", b"")
        self.write("b", b"")
        with self.assertRaises(HFFolderResourceLimitError):
            inspect_hf_folder(self.root, HFFolderLimits(max_entries=1))

    def test_entry_limit_stops_scanning_lazily(self) -> None:
        class FakeEntry:
            def __init__(self, name: str) -> None:
                self.name = name

            def is_symlink(self) -> bool:
                return False

            def is_dir(self, *, follow_symlinks: bool) -> bool:
                return False

            def is_file(self, *, follow_symlinks: bool) -> bool:
                return False

        class FakeScandir:
            def __init__(self) -> None:
                self.consumed = 0

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback) -> bool:
                return False

            def __iter__(self):
                return self

            def __next__(self):
                self.consumed += 1
                if self.consumed > 2:
                    raise AssertionError("scanner consumed entries past the configured limit")
                return FakeEntry(f"entry-{self.consumed}")

        scanner = FakeScandir()
        with patch("eclipse.model_intelligence.hf_folder.os.scandir", return_value=scanner):
            with self.assertRaises(HFFolderResourceLimitError):
                inspect_hf_folder(self.root, HFFolderLimits(max_entries=1))
        self.assertEqual(scanner.consumed, 2)

    def test_skips_symlinks(self) -> None:
        self.write("config.json", b"{}")
        target = self.write("real.safetensors", bytes(4))
        link = self.root / "link.safetensors"
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are not supported on this platform")
        report = inspect_hf_folder(self.root)
        self.assertIn("link.safetensors", report["symlinks"])
        self.assertNotIn("link.safetensors", {shard["name"] for shard in report["safetensors"]["shards"]})
        self.assertTrue(any("Symbolic links" in warning for warning in report["warnings"]))

    def test_no_payload_reads_and_flat_privacy(self) -> None:
        self.write("config.json", b"{}")
        shard = self.write("model.safetensors", bytes(2048))
        before = shard.read_bytes()
        report = inspect_hf_folder(self.root)
        self.assertEqual(shard.read_bytes(), before)
        self.assertEqual(report["inspection"]["tensor_payload_bytes_read"], 0)
        self.assertEqual(report["folder_name"], self.root.name)

    def test_cli_emits_valid_json(self) -> None:
        self.write("config.json", json.dumps(CONFIG).encode("utf-8"))
        self.write("model.safetensors", bytes(16))
        result = subprocess.run(
            [sys.executable, "-m", "eclipse", "inspect-hf-folder", str(self.root), "--compact"],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["format"], "huggingface_folder")
        self.assertEqual(parsed["config"]["model_type"], "llama")


if __name__ == "__main__":
    unittest.main()
