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
    ModelAtlasLimits,
    TokenizerError,
    TokenizerFormatError,
    TokenizerLimits,
    TokenizerResourceLimitError,
    build_model_atlas,
    inspect_tokenizer,
    summarize_gguf_tokenizer,
)


class TokenizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_json(self, name: str, value: object) -> Path:
        path = self.root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def write_text(self, name: str, value: str) -> Path:
        path = self.root / name
        path.write_text(value, encoding="utf-8")
        return path

    def test_reports_assets_and_tokenizer_facts(self) -> None:
        self.write_json(
            "tokenizer_config.json",
            {
                "tokenizer_class": "LlamaTokenizerFast",
                "model_max_length": 131072,
                "bos_token": "<s>",
                "eos_token": "</s>",
                "padding_side": "right",
                "chat_template": "{{ messages }}",
            },
        )
        self.write_json(
            "tokenizer.json",
            {
                "version": "1.0",
                "added_tokens": [{"id": 0, "content": "<s>", "special": True}],
                "model": {"type": "BPE", "vocab": {"a": 0, "b": 1, "<s>": 2}},
                "pre_tokenizer": {"type": "ByteLevel"},
                "decoder": {"type": "ByteLevel"},
                "normalizer": {"type": "NFC"},
            },
        )
        self.write_json("special_tokens_map.json", {"bos_token": "<s>", "eos_token": "</s>"})
        self.write_text("vocab.txt", "a\nb\nc\n")
        (self.root / "tokenizer.model").write_bytes(b"\x00\x01" * 16)

        report = inspect_tokenizer(self.root)
        self.assertEqual(report["format"], "eclipse_tokenizer_inspection")
        self.assertEqual(report["tokenizer"]["class"], "LlamaTokenizerFast")
        self.assertEqual(report["tokenizer"]["tokenizer_model_type"], "BPE")
        self.assertEqual(report["tokenizer"]["pre_tokenizer_type"], "ByteLevel")
        self.assertEqual(report["tokenizer"]["decoder_type"], "ByteLevel")
        self.assertEqual(report["tokenizer"]["normalizer_type"], "NFC")
        self.assertEqual(report["tokenizer"]["max_length"], 131072)
        self.assertEqual(report["tokenizer"]["padding_side"], "right")
        self.assertEqual(report["tokenizer"]["vocab_size"], 3)
        self.assertEqual(report["tokenizer"]["vocab_size_source"], "tokenizer.json:model.vocab")
        self.assertEqual(report["tokenizer"]["added_token_count"], 1)
        self.assertEqual(report["tokenizer"]["special_tokens"]["bos"]["content"], "<s>")
        self.assertFalse(report["inspection"]["templates_rendered"])
        self.assertFalse(report["inspection"]["jinja_imported"])
        self.assertEqual(report["inspection"]["tensor_payload_bytes_read"], 0)

        kinds = {entry["name"]: entry["kind"] for entry in report["assets"]}
        self.assertEqual(kinds["tokenizer.model"], "sentencepiece_model")
        self.assertEqual(kinds["vocab.txt"], "text")

    def test_standalone_jinja_is_the_documented_default(self) -> None:
        self.write_json("tokenizer_config.json", {"chat_template": "embedded {{ messages }}"})
        self.write_text("chat_template.jinja", "standalone {{ messages }}")
        report = inspect_tokenizer(self.root)
        templates = report["chat_templates"]
        self.assertEqual(templates["count"], 2)
        self.assertEqual(templates["default"]["kind"], "standalone_jinja")
        self.assertEqual(templates["default"]["evidence"], "documented_loader_precedence")
        kinds = {source["kind"] for source in templates["sources"]}
        self.assertEqual(kinds, {"standalone_jinja", "embedded_tokenizer_config"})

    def test_additional_named_templates_are_collected(self) -> None:
        self.write_json("tokenizer_config.json", {"chat_template": "embedded"})
        directory = self.root / "additional_chat_templates"
        directory.mkdir()
        (directory / "tool_use.jinja").write_text("tools {{ tools }}", encoding="utf-8")
        (directory / "ignore.txt").write_text("not a template", encoding="utf-8")
        report = inspect_tokenizer(self.root)
        names = {(source["name"], source["kind"]) for source in report["chat_templates"]["sources"]}
        self.assertIn(("tool_use", "additional_named_jinja"), names)
        self.assertIn("tool_use.jinja", report["additional_chat_template_files"])

    def test_legacy_chat_template_json_is_used(self) -> None:
        self.write_json("chat_template.json", {"chat_template": "legacy {{ messages }}"})
        report = inspect_tokenizer(self.root)
        self.assertEqual(report["chat_templates"]["count"], 1)
        self.assertEqual(
            report["chat_templates"]["sources"][0]["kind"], "legacy_chat_template_json"
        )

    def test_conflicting_template_sources_are_reported(self) -> None:
        self.write_json("tokenizer_config.json", {"chat_template": "one"})
        self.write_text("chat_template.jinja", "two")
        report = inspect_tokenizer(self.root)
        conflicts = report["chat_templates"]["conflicts"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["name"], "default")
        self.assertTrue(any("Conflicting chat-template" in warning for warning in report["warnings"]))

    def test_empty_folder_is_an_honest_empty_state(self) -> None:
        report = inspect_tokenizer(self.root)
        self.assertEqual(report["assets"], [])
        self.assertEqual(report["chat_templates"]["count"], 0)
        self.assertIsNone(report["tokenizer"]["vocab_size"])
        self.assertEqual(report["evidence"]["chat_templates"], "unknown")

    def test_invalid_json_is_reported_not_fatal(self) -> None:
        self.write_text("tokenizer_config.json", "{ not valid json")
        report = inspect_tokenizer(self.root)
        self.assertTrue(any("not valid UTF-8 JSON" in warning for warning in report["warnings"]))

    def test_symlinks_are_not_followed(self) -> None:
        target = self.write_text("actual.jinja", "{{ messages }}")
        link = self.root / "chat_template.jinja"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not supported on this platform")
        report = inspect_tokenizer(self.root)
        self.assertEqual(report["chat_templates"]["count"], 0)
        self.assertTrue(any("Symbolic links were not followed" in warning for warning in report["warnings"]))

    def test_template_over_limit_is_skipped(self) -> None:
        self.write_text("chat_template.jinja", "x" * 5000)
        report = inspect_tokenizer(self.root, TokenizerLimits(max_template_bytes=1024))
        self.assertEqual(report["chat_templates"]["count"], 0)
        self.assertTrue(any("exceeds the" in warning for warning in report["warnings"]))

    def test_template_preview_is_bounded(self) -> None:
        self.write_text("chat_template.jinja", "a" * 100)
        report = inspect_tokenizer(self.root, TokenizerLimits(max_template_preview_bytes=10))
        template = report["chat_templates"]["sources"][0]
        self.assertTrue(template["preview_truncated"])
        self.assertEqual(len(template["preview"].encode("utf-8")), 10)

    def test_rejects_non_directory(self) -> None:
        path = self.write_text("tokenizer.json", "{}")
        with self.assertRaises(TokenizerFormatError):
            inspect_tokenizer(path)

    def test_rejects_missing_path(self) -> None:
        with self.assertRaises(TokenizerError):
            inspect_tokenizer(self.root / "does-not-exist")

    def test_rejects_bad_limits(self) -> None:
        with self.assertRaises(ValueError):
            TokenizerLimits(max_entries=-1)
        with self.assertRaises(ValueError):
            TokenizerLimits(max_json_bytes=0)

    def test_entry_limit_is_enforced(self) -> None:
        for index in range(5):
            self.write_text(f"file-{index}.txt", "x")
        with self.assertRaises(TokenizerResourceLimitError):
            inspect_tokenizer(self.root, TokenizerLimits(max_entries=2))


def gguf_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<Q", len(encoded)) + encoded


def meta_string(key: str, value: str) -> bytes:
    return gguf_string(key) + struct.pack("<I", 8) + gguf_string(value)


def meta_u32(key: str, value: int) -> bytes:
    key_bytes = key.encode("utf-8")
    return struct.pack("<Q", len(key_bytes)) + key_bytes + struct.pack("<II", 4, value)


def meta_string_array(key: str, values: list[str]) -> bytes:
    key_bytes = key.encode("utf-8")
    out = struct.pack("<Q", len(key_bytes)) + key_bytes + struct.pack("<I", 9)
    out += struct.pack("<I", 8) + struct.pack("<Q", len(values))
    for value in values:
        encoded = value.encode("utf-8")
        out += struct.pack("<Q", len(encoded)) + encoded
    return out


class GgufTokenizerSummaryTests(unittest.TestCase):
    def test_summarizes_tokenizer_metadata(self) -> None:
        metadata = {
            "tokenizer.ggml.model": "gpt2",
            "tokenizer.ggml.pre": "llama-bpe",
            "tokenizer.ggml.bos_token_id": 1,
            "tokenizer.ggml.eos_token_id": 2,
            "tokenizer.ggml.unknown_token_id": 0,
            "tokenizer.ggml.tokens": {
                "kind": "array",
                "element_type": "string",
                "count": 4,
                "preview": ["a", "b", "<s>", "</s>"],
                "preview_truncated": False,
            },
            "tokenizer.chat_template": "{% for m in messages %}{{ m }}{% endfor %}",
        }
        summary = summarize_gguf_tokenizer(metadata)
        self.assertTrue(summary["available"])
        self.assertEqual(summary["source"], "gguf_metadata")
        self.assertEqual(summary["model_label"], "gpt2")
        self.assertEqual(summary["pre_tokenizer_label"], "llama-bpe")
        self.assertEqual(summary["vocab_size"], 4)
        self.assertEqual(summary["special_tokens"]["bos"]["id"], 1)
        self.assertEqual(summary["special_tokens"]["unk"]["id"], 0)
        self.assertEqual(summary["chat_templates"]["count"], 1)
        keys = {field["key"] for field in summary["fields"]}
        self.assertIn("tokenizer.ggml.tokens", keys)
        self.assertNotIn("tokenizer.chat_template", keys)

    def test_empty_metadata_reports_unavailable(self) -> None:
        summary = summarize_gguf_tokenizer({})
        self.assertFalse(summary["available"])
        self.assertEqual(summary["chat_templates"]["count"], 0)
        self.assertTrue(any("No tokenizer" in warning for warning in summary["warnings"]))


class TokenizerAtlasIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_folder_atlas_includes_tokenizer_section(self) -> None:
        (self.root / "config.json").write_text('{"model_type": "llama"}', encoding="utf-8")
        (self.root / "tokenizer_config.json").write_text(
            json.dumps({"tokenizer_class": "LlamaTokenizerFast"}), encoding="utf-8"
        )
        (self.root / "chat_template.jinja").write_text("{{ messages }}", encoding="utf-8")
        atlas = build_model_atlas(self.root)
        self.assertTrue(atlas["tokenizer"]["available"])
        self.assertEqual(atlas["tokenizer"]["source"], "huggingface_folder")
        self.assertEqual(atlas["evidence"]["tokenizer"], "observed")
        self.assertEqual(atlas["tokenizer"]["chat_templates"]["count"], 1)

    def test_safetensors_atlas_reports_tokenizer_unavailable(self) -> None:
        header = {"weight": {"dtype": "F32", "shape": [2, 2], "data_offsets": [0, 16]}}
        encoded = json.dumps(header).encode("utf-8")
        path = self.root / "model.safetensors"
        path.write_bytes(struct.pack("<Q", len(encoded)) + encoded + bytes(16))
        atlas = build_model_atlas(path)
        self.assertFalse(atlas["tokenizer"]["available"])
        self.assertEqual(atlas["evidence"]["tokenizer"], "unknown")

    def test_gguf_atlas_includes_tokenizer_metadata(self) -> None:
        metadata = [
            meta_string("general.architecture", "llama"),
            meta_string("tokenizer.ggml.model", "gpt2"),
            meta_string_array("tokenizer.ggml.tokens", ["a", "b"]),
            meta_string("tokenizer.chat_template", "{{ messages }}"),
        ]
        body = bytearray(b"GGUF")
        body += struct.pack("<IQQ", 3, 1, len(metadata))
        body += b"".join(metadata)
        body += gguf_string("w")
        body += struct.pack("<I", 1) + struct.pack("<Q", 2) + struct.pack("<IQ", 0, 0)
        body += b"\x00" * ((32 - (len(body) % 32)) % 32)
        body += b"\x00" * 256
        path = self.root / "model.gguf"
        path.write_bytes(bytes(body))
        atlas = build_model_atlas(path)
        self.assertTrue(atlas["tokenizer"]["available"])
        self.assertEqual(atlas["tokenizer"]["source"], "gguf_metadata")
        self.assertEqual(atlas["tokenizer"]["vocab_size"], 2)
        self.assertEqual(atlas["evidence"]["tokenizer"], "observed")

    def test_atlas_limits_accept_tokenizer_limits(self) -> None:
        with self.assertRaises(ValueError):
            ModelAtlasLimits(tokenizer="not-limits")  # type: ignore[arg-type]
        limits = ModelAtlasLimits(tokenizer=TokenizerLimits(max_entries=10))
        self.assertEqual(limits.tokenizer.max_entries, 10)


class TokenizerCliTests(unittest.TestCase):
    def test_cli_emits_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "tokenizer_config.json").write_text(
                json.dumps({"tokenizer_class": "LlamaTokenizerFast"}), encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, "-m", "eclipse", "inspect-tokenizer", str(root), "--compact"],
                cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["format"], "eclipse_tokenizer_inspection")
        self.assertEqual(parsed["tokenizer"]["class"], "LlamaTokenizerFast")


if __name__ == "__main__":
    unittest.main()
