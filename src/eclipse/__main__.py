"""ECLIPSE command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys

from eclipse.core import PLACEMENT_MODES, detect_host_hardware
from eclipse.core.runtime import (
    RuntimeContractError,
    evaluate_model_support,
    load_capabilities,
)
from eclipse.model_intelligence import (
    FeasibilityError,
    FeasibilityRequest,
    plan_model_feasibility,
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
        description="ECLIPSE model intelligence, capability and agent tools.",
    )
    parser.add_argument(
        "--home",
        help="override the ECLIPSE application data directory (or set ECLIPSE_HOME)",
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

    host = commands.add_parser(
        "inspect-host",
        help="report currently observable host hardware and available memory",
    )
    host.add_argument("--storage-path", help="optional model file/folder path used to identify its storage volume")
    host.add_argument("--compact", action="store_true", help="emit compact JSON")

    feasibility = commands.add_parser(
        "plan-feasibility",
        help="estimate model weight and KV-cache memory against current host resources",
    )
    feasibility.add_argument("path", help="path to a supported GGUF, Safetensors file or model folder")
    feasibility.add_argument("--context-tokens", type=int, help="requested context; defaults to the model-declared value")
    feasibility.add_argument("--kv-cache-dtype", choices=("f16", "bf16", "f32"), default="f16")
    feasibility.add_argument("--sequence-slots", type=int, default=1)
    feasibility.add_argument("--ram-reserve-mib", type=int, default=8192)
    feasibility.add_argument("--vram-reserve-mib", type=int, default=768)
    feasibility.add_argument("--compact", action="store_true", help="emit compact JSON")

    runtime = commands.add_parser(
        "runtime-support",
        help="compare a model against a declared inference-backend capability manifest",
    )
    runtime.add_argument("path", help="path to a supported GGUF, Safetensors file or model folder")
    runtime.add_argument(
        "--capabilities",
        required=True,
        help="path to a JSON backend capability manifest",
    )
    runtime.add_argument(
        "--placement",
        choices=sorted(PLACEMENT_MODES),
        help="optional requested placement mode to check",
    )
    runtime.add_argument(
        "--control",
        action="append",
        default=[],
        help="requested control name to check (repeatable)",
    )
    runtime.add_argument("--compact", action="store_true", help="emit compact JSON")

    from eclipse.app_cli import register_commands

    register_commands(commands)

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



def _run_inspect_host(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        report = detect_host_hardware(args.storage_path).to_dict()
    except (OSError, ValueError) as exc:
        print(f"ECLIPSE: hardware discovery failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2, allow_nan=False))
    return 0


def _run_plan_feasibility(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    for option in ("sequence_slots",):
        if getattr(args, option) <= 0:
            parser.error(f"--{option.replace('_', '-')} must be greater than zero")
    for option in ("ram_reserve_mib", "vram_reserve_mib"):
        if getattr(args, option) < 0:
            parser.error(f"--{option.replace('_', '-')} cannot be negative")
    if args.context_tokens is not None and args.context_tokens <= 0:
        parser.error("--context-tokens must be greater than zero")

    request = FeasibilityRequest(
        context_tokens=args.context_tokens,
        kv_cache_dtype=args.kv_cache_dtype,
        sequence_slots=args.sequence_slots,
        system_ram_reserve_bytes=args.ram_reserve_mib * 1024 * 1024,
        gpu_vram_reserve_bytes=args.vram_reserve_mib * 1024 * 1024,
    )
    try:
        atlas = build_model_atlas(args.path)
        host = detect_host_hardware(args.path)
        report = plan_model_feasibility(atlas, host, request)
    except (FeasibilityError, ModelAtlasError, OSError, ValueError) as exc:
        print(f"ECLIPSE: feasibility planning failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=None if args.compact else 2, allow_nan=False))
    return 0


def _run_runtime_support(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        capabilities = load_capabilities(args.capabilities)
        atlas = build_model_atlas(args.path)
        host = detect_host_hardware(args.path)
        requested_controls = {name: None for name in args.control}
        report = evaluate_model_support(
            capabilities,
            atlas,
            host,
            placement_mode=args.placement,
            requested_controls=requested_controls,
        )
    except (RuntimeContractError, ModelAtlasError, OSError, ValueError) as exc:
        print(
            f"ECLIPSE: runtime support check failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
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
    from eclipse.app_cli import dispatch

    app_result = dispatch(args)
    if app_result is not None:
        return app_result
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
    if args.command == "inspect-host":
        return _run_inspect_host(args, parser)
    if args.command == "plan-feasibility":
        return _run_plan_feasibility(args, parser)
    if args.command == "runtime-support":
        return _run_runtime_support(args, parser)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
