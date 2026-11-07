from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import json
from pathlib import Path
import tempfile
import unittest

from eclipse.model_intelligence.preparation import (
    IntegrityError,
    PreparationError,
    PreparationUnavailable,
    build_inventory,
    hash_file,
    prepare_model,
    quantize_gguf,
    remove_prepared_package,
    verify_prepared_package,
)
from tests.test_model_atlas import build_gguf


def make_gguf(path: Path) -> Path:
    path.write_bytes(
        build_gguf([("blk.0.weight", (4, 8), 0, 0), ("blk.0.bias", (8,), 0, 128)])
    )
    return path


class PreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = make_gguf(self.root / "model.gguf")
        self.prepared = self.root / "prepared"

    def test_index_package_records_identity_and_lineage(self) -> None:
        package = prepare_model(self.source, self.prepared, mode="index")
        manifest = package.manifest
        self.assertEqual(manifest["format"], "eclipse_prepared_model")
        self.assertEqual(manifest["method"]["mode"], "index")
        self.assertEqual(manifest["files"][0]["sha256"], hash_file(self.source))
        self.assertEqual(manifest["identity"]["source_path"], str(self.source.resolve()))
        self.assertEqual(manifest["integrity"]["status"], "verified")
        self.assertFalse(manifest["source_modified"])
        self.assertTrue((package.directory / "manifest.json").is_file())
        self.assertEqual(self.source.read_bytes(), build_gguf([("blk.0.weight", (4, 8), 0, 0), ("blk.0.bias", (8,), 0, 128)]))

    def test_index_verification_detects_a_modified_source(self) -> None:
        package = prepare_model(self.source, self.prepared, mode="index")
        self.source.write_bytes(self.source.read_bytes() + b"tamper")
        with self.assertRaises(IntegrityError):
            verify_prepared_package(package.directory)

    def test_copy_package_verifies_every_copied_file(self) -> None:
        package = prepare_model(self.source, self.prepared, mode="copy")
        self.assertEqual(package.manifest["method"]["mode"], "copy")
        copied = package.directory / package.manifest["identity"]["output_root"]
        self.assertTrue(copied.is_file())
        self.assertEqual(hash_file(copied), hash_file(self.source))
        verified = verify_prepared_package(package.directory)
        self.assertEqual(verified.manifest["integrity"]["status"], "verified")

    def test_copy_verification_detects_corruption(self) -> None:
        package = prepare_model(self.source, self.prepared, mode="copy")
        copied = package.directory / package.manifest["identity"]["output_root"]
        copied.write_bytes(b"corrupt")
        with self.assertRaises(IntegrityError):
            verify_prepared_package(package.directory)

    def test_prepare_is_idempotent_for_identical_source(self) -> None:
        first = prepare_model(self.source, self.prepared, mode="index")
        second = prepare_model(self.source, self.prepared, mode="index")
        self.assertEqual(first.directory, second.directory)

    def test_inventory_hashes_all_folder_control_files(self) -> None:
        folder = self.root / "folder"
        folder.mkdir()
        (folder / "config.json").write_text('{"model_type": "llama"}', encoding="utf-8")
        (folder / "tokenizer_config.json").write_text('{"model_max_length": 128}', encoding="utf-8")
        inventory = build_inventory(folder)
        names = sorted(item["name"] for item in inventory)
        self.assertEqual(names, ["config.json", "tokenizer_config.json"])
        self.assertTrue(all(len(item["sha256"]) == 64 for item in inventory))

    def test_remove_refuses_outside_prepared_store(self) -> None:
        package = prepare_model(self.source, self.prepared, mode="index")
        with self.assertRaises(PreparationError):
            remove_prepared_package(package.directory, self.root / "elsewhere")

    def test_remove_deletes_only_the_derived_package(self) -> None:
        package = prepare_model(self.source, self.prepared, mode="copy")
        remove_prepared_package(package.directory, self.prepared)
        self.assertFalse(package.directory.exists())
        self.assertTrue(self.source.is_file())

    def test_quantize_is_unavailable_without_the_tool(self) -> None:
        from unittest.mock import patch

        with patch("eclipse.model_intelligence.preparation.find_quantize_tool", return_value=None):
            with self.assertRaises(PreparationUnavailable):
                quantize_gguf(self.source, self.prepared)

    def test_quantize_rejects_non_gguf_sources(self) -> None:
        other = self.root / "model.bin"
        other.write_bytes(b"x")
        with self.assertRaises(PreparationError):
            quantize_gguf(other, self.prepared)

    def test_manifest_json_is_plain_json(self) -> None:
        package = prepare_model(self.source, self.prepared, mode="index")
        payload = json.loads((package.directory / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["format"], "eclipse_prepared_model")


if __name__ == "__main__":
    unittest.main()
