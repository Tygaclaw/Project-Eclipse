"""ECLIPSE command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys

from eclipse.model_intelligence import (
    GGUFError,
    HFFolderError,
    HFFolderLimits,
    InspectionLimits,
    ModelAtlasError,
    ModelAtlasLimits,
    SafetensorsError,
    SafetensorsLimits,
    TokenizerError,
    TokenizerLimits,
    build_model_atlas,
    inspect_gguf,
    inspect_hf_folder,
    inspect_safetensors,
    inspect_tokenizer,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eclipse",
        description="ECLIPSE static model-inspection tools (no model inference).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    inspect = commands.add_parser(
        "inspect-gguf",
        help="read GGUF metadata and tensor descriptors without loading weights",
    )
    inspect.add_argument("file", help="path to a .gguf file")
    inspect.add_argument("--max-header-mib", type=int, default=256)
    inspect.add_argument("--max-tensors", type=int, default=200_000)
    inspect.add_argument("--max-metadata-entries", type=int, default=200_000)
    inspect.add_argument("--max-array-items", type=int, default=10_000_000)
    inspect.add_argument("--preview-items", type=int, default=32)
    inspect.add_argument("--compact", action="store_true", help="emit compact JSON")

    safetensors = commands.add_parser(
        "inspect-safetensors",
        help="read a Safetensors header and tensor index without loading weights",
    )
    safetensors.add_argument("file", help="path to a .safetensors file")
    safetensors.add_argument("--max-header-mib", type=int, default=100)
    safetensors.add_argument("--max-tensors", type=int, default=200_000)
    safetensors.add_argument("--max-metadata-entries", type=int, default=200_000)
    safetensors.add_argument("--compact", action="store_true", help="emit compact JSON")

    folder = commands.add_parser(
        "inspect-hf-folder",
        help="read Hugging Face folder control files and Safetensors shard index without loading weights",
    )
    folder.add_argument("folder", help="path to a local Hugging Face model folder")
    folder.add_argument("--max-config-mib", type=int, default=8)
    folder.add_argument("--max-index-mib", type=int, default=256)
    folder.add_argument("--max-entries", type=int, default=100_000)
    folder.add_argument("--max-weight-map-entries", type=int, default=1_000_000)
    folder.add_argument("--compact", action="store_true", help="emit compact JSON")

    tokenizer = commands.add_parser(
        "inspect-tokenizer",
        help="statically summarize tokenizer assets and chat templates in a model folder",
    )
    tokenizer.add_argument("folder", help="path to a local Hugging Face model folder")
    tokenizer.add_argument("--max-entries", type=int, default=100_000)
    tokenizer.add_argument("--max-json-mib", type=int, default=16, help="maximum bytes per JSON tokenizer asset, in MiB")
    tokenizer.add_argument("--max-total-json-mib", type=int, default=32, help="aggregate JSON tokenizer read budget, in MiB")
    tokenizer.add_argument("--max-text-mib", type=int, default=32)
    tokenizer.add_argument("--max-template-mib", type=int, default=4, help="maximum bytes per chat template, in MiB")
    tokenizer.add_argument("--max-total-template-mib", type=int, default=16, help="aggregate chat-template byte budget, in MiB")
    tokenizer.add_argument("--max-template-count", type=int, default=256, help="maximum templates inspected across all sources")
    tokenizer.add_argument("--max-token-entries", type=int, default=100_000, help="maximum added-token records examined for special-token IDs")
    tokenizer.add_argument("--max-token-preview-items", type=int, default=16)
    tokenizer.add_argument("--compact", action="store_true", help="emit compact JSON")

    atlas = commands.add_parser(
        "build-atlas",
        help="compose an evidence-labelled atlas for a GGUF file, Safetensors file or model folder",
    )
    atlas.add_argument("path", help="path to a .gguf file, a .safetensors file or a model folder")
    atlas.add_argument("--max-shards", type=int, default=4096)
    atlas.add_argument("--compact", action="store_true", help="emit compact JSON")

    return parser


def _run_gguf(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.max_header_mib <= 0:
        parser.error("--max-header-mib must be greater than zero")
    for option in ("max_tensors", "max_metadata_entries", "max_array_items", "preview_items"):
        if getattr(args, option) < 0:
            parser.error(f"--{option.replace('_', '-')} cannot be negative")
    limits = InspectionLimits(
        max_header_bytes=args.max_header_mib * 1024 * 1024,
        max_tensors=args.max_tensors,
        max_metadata_entries=args.max_metadata_entries,
        max_array_items=args.max_array_items,
        max_array_preview_items=args.preview_items,
    )
    try:
        report = inspect_gguf(args.file, limits)
    except (GGUFError, ValueError) as exc:
        print(f"ECLIPSE: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2, allow_nan=False))
    return 0


def _run_safetensors(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.max_header_mib <= 0:
        parser.error("--max-header-mib must be greater than zero")
    for option in ("max_tensors", "max_metadata_entries"):
        if getattr(args, option) < 0:
            parser.error(f"--{option.replace('_', '-')} cannot be negative")
    limits = SafetensorsLimits(
        max_header_bytes=args.max_header_mib * 1024 * 1024,
        max_tensors=args.max_tensors,
        max_metadata_entries=args.max_metadata_entries,
    )
    try:
        report = inspect_safetensors(args.file, limits)
    except (SafetensorsError, ValueError) as exc:
        print(f"ECLIPSE: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2, allow_nan=False))
    return 0


def _run_hf_folder(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    for option in ("max_config_mib", "max_index_mib"):
        if getattr(args, option) <= 0:
            parser.error(f"--{option.replace('_', '-')} must be greater than zero")
    for option in ("max_entries", "max_weight_map_entries"):
        if getattr(args, option) < 0:
            parser.error(f"--{option.replace('_', '-')} cannot be negative")
    limits = HFFolderLimits(
        max_entries=args.max_entries,
        max_config_bytes=args.max_config_mib * 1024 * 1024,
        max_index_bytes=args.max_index_mib * 1024 * 1024,
        max_weight_map_entries=args.max_weight_map_entries,
    )
    try:
        report = inspect_hf_folder(args.folder, limits)
    except (HFFolderError, ValueError) as exc:
        print(f"ECLIPSE: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2, allow_nan=False))
    return 0


def _run_tokenizer(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    for option in (
        "max_json_mib",
        "max_total_json_mib",
        "max_text_mib",
        "max_template_mib",
        "max_total_template_mib",
    ):
        if getattr(args, option) <= 0:
            parser.error(f"--{option.replace('_', '-')} must be greater than zero")
    for option in ("max_entries", "max_template_count", "max_token_entries", "max_token_preview_items"):
        if getattr(args, option) < 0:
            parser.error(f"--{option.replace('_', '-')} cannot be negative")
    limits = TokenizerLimits(
        max_entries=args.max_entries,
        max_json_bytes=args.max_json_mib * 1024 * 1024,
        max_total_json_bytes=args.max_total_json_mib * 1024 * 1024,
        max_text_bytes=args.max_text_mib * 1024 * 1024,
        max_template_bytes=args.max_template_mib * 1024 * 1024,
        max_total_template_bytes=args.max_total_template_mib * 1024 * 1024,
        max_template_count=args.max_template_count,
        max_token_entries=args.max_token_entries,
        max_token_preview_items=args.max_token_preview_items,
    )
    try:
        report = inspect_tokenizer(args.folder, limits)
    except (TokenizerError, ValueError) as exc:
        print(f"ECLIPSE: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2, allow_nan=False))
    return 0


def _run_build_atlas(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.max_shards < 0:
        parser.error("--max-shards cannot be negative")
    limits = ModelAtlasLimits(max_shards=args.max_shards)
    try:
        report = build_model_atlas(args.path, limits)
    except (ModelAtlasError, ValueError) as exc:
        print(f"ECLIPSE: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2, allow_nan=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "inspect-gguf":
        return _run_gguf(args, parser)
    if args.command == "inspect-safetensors":
        return _run_safetensors(args, parser)
    if args.command == "inspect-hf-folder":
        return _run_hf_folder(args, parser)
    if args.command == "inspect-tokenizer":
        return _run_tokenizer(args, parser)
    if args.command == "build-atlas":
        return _run_build_atlas(args, parser)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
