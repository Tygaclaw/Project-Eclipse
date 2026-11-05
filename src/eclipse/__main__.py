"""ECLIPSE command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys

from eclipse.model_intelligence import GGUFError, InspectionLimits, inspect_gguf


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
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


if __name__ == "__main__":
    raise SystemExit(main())
