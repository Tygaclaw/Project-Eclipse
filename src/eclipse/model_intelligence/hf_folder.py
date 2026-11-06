"""Bounded, read-only Hugging Face model-folder inspection.

Discovers the small control files that describe a local Hugging Face
checkpoint (``config.json`` and ``model.safetensors.index.json``) together
with the Safetensors shard files they reference. Only these small text files
are read, and only up to configured byte limits. Tensor payloads are never
read, mapped or decoded.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any


class HFFolderError(Exception):
    """Base class for expected Hugging Face folder inspection failures."""


class HFFolderFormatError(HFFolderError):
    """The folder contents are truncated, malformed, or unsupported."""


class HFFolderResourceLimitError(HFFolderError):
    """The folder contents exceed a configured parser safety limit."""


@dataclass(frozen=True, slots=True)
class HFFolderLimits:
    """Hard limits for untrusted Hugging Face model folders."""

    max_entries: int = 100_000
    max_config_bytes: int = 8 * 1024 * 1024
    max_index_bytes: int = 256 * 1024 * 1024
    max_weight_map_entries: int = 1_000_000
    max_name_bytes: int = 65_536

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for name in ("max_config_bytes", "max_index_bytes", "max_name_bytes"):
            if getattr(self, name) == 0:
                raise ValueError(f"{name} must be greater than zero")


_CONFIG_SCALAR_KEYS = (
    "model_type",
    "torch_dtype",
    "num_hidden_layers",
    "n_layer",
    "n_layers",
    "hidden_size",
    "n_embd",
    "d_model",
    "intermediate_size",
    "n_inner",
    "d_ff",
    "num_attention_heads",
    "n_head",
    "num_heads",
    "num_key_value_heads",
    "num_kv_heads",
    "n_head_kv",
    "head_dim",
    "key_head_dim",
    "value_head_dim",
    "vocab_size",
    "max_position_embeddings",
    "max_sequence_length",
    "max_seq_len",
    "n_positions",
    "seq_length",
    "tie_word_embeddings",
    "num_local_experts",
    "num_experts",
    "num_experts_per_tok",
    "num_experts_per_token",
    "num_shared_experts",
    "n_expert",
)

_CONFIG_PRESENCE_KEYS = ("text_config", "vision_config", "quantization_config")

_CONFIG_FILE = "config.json"
_INDEX_FILE = "model.safetensors.index.json"
_SAFETENSORS_SUFFIX = ".safetensors"


def _read_bounded_text(path: Path, max_bytes: int) -> tuple[str | None, str | None]:
    # Read at most max_bytes + 1 so a file changed after inspection cannot
    # bypass the memory limit between a stat() call and read_bytes().
    try:
        with path.open("rb") as handle:
            data = handle.read(max_bytes + 1)
    except OSError as exc:
        return None, f"{path.name} could not be read: {exc}"
    if len(data) > max_bytes:
        return None, f"{path.name} exceeds the {max_bytes:,}-byte read limit"
    try:
        return data.decode("utf-8", errors="strict"), None
    except UnicodeDecodeError:
        return None, f"{path.name} is not valid UTF-8"


def _summarize_config(
    config: dict[str, Any],
    *,
    include_text_config: bool = True,
) -> dict[str, Any]:
    """Retain only whitelisted architecture scalars from bounded config JSON."""

    summary: dict[str, Any] = {}
    for key in _CONFIG_SCALAR_KEYS:
        value = config.get(key)
        if isinstance(value, bool):
            summary[key] = value
        elif isinstance(value, (int, str)) and not isinstance(value, bool):
            summary[key] = value
    architectures = config.get("architectures")
    if isinstance(architectures, list):
        summary["architectures"] = [
            item[:256] for item in architectures[:16]
            if isinstance(item, str)
        ]
    for key in _CONFIG_PRESENCE_KEYS:
        summary[f"has_{key}"] = key in config
    quantization = config.get("quantization_config")
    if isinstance(quantization, dict) and isinstance(quantization.get("quant_method"), str):
        summary["quantization_method"] = quantization["quant_method"][:128]
    nested = config.get("text_config")
    if include_text_config and isinstance(nested, dict):
        # Keep one bounded level of text-only architecture facts; do not copy
        # the full multimodal configuration tree into the Atlas.
        summary["text_config"] = _summarize_config(
            nested,
            include_text_config=False,
        )
    return summary


def _validate_shard_name(name: str) -> None:
    if not name or name in {".", ".."}:
        raise HFFolderFormatError("Safetensors index contains an empty shard file name")
    separators = {"/", "\\", os.sep}
    if os.altsep:
        separators.add(os.altsep)
    if any(separator in name for separator in separators):
        raise HFFolderFormatError(
            f"Safetensors index shard {name!r} uses a path separator; only flat file names are supported"
        )
    if Path(name).is_absolute():
        raise HFFolderFormatError(f"Safetensors index shard {name!r} must be a relative file name")


def _parse_index(
    text: str,
    *,
    files: dict[str, int],
    limits: HFFolderLimits,
) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HFFolderFormatError(f"{_INDEX_FILE} is not valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise HFFolderFormatError(f"{_INDEX_FILE} must be a JSON object")

    weight_map = parsed.get("weight_map")
    if not isinstance(weight_map, dict):
        raise HFFolderFormatError(f"{_INDEX_FILE} weight_map must be an object")
    if len(weight_map) > limits.max_weight_map_entries:
        raise HFFolderResourceLimitError(
            f"{_INDEX_FILE} weight_map has {len(weight_map):,} entries; limit is {limits.max_weight_map_entries:,}"
        )

    referenced: set[str] = set()
    for tensor_name, shard in weight_map.items():
        if not isinstance(tensor_name, str) or not isinstance(shard, str):
            raise HFFolderFormatError(f"{_INDEX_FILE} weight_map must map tensor names to shard file names")
        if len(tensor_name.encode("utf-8")) > limits.max_name_bytes:
            raise HFFolderResourceLimitError(
                f"Tensor name in {_INDEX_FILE} exceeds {limits.max_name_bytes:,} bytes"
            )
        _validate_shard_name(shard)
        referenced.add(shard)

    declared_total: int | None = None
    metadata = parsed.get("metadata")
    if isinstance(metadata, dict):
        total_size = metadata.get("total_size")
        if isinstance(total_size, int) and not isinstance(total_size, bool):
            declared_total = total_size

    present = set(files)
    missing = sorted(referenced - present)
    available_shards = {name for name in files if name.endswith(_SAFETENSORS_SUFFIX)}
    unreferenced = sorted(available_shards - referenced)

    return {
        "file_name": _INDEX_FILE,
        "tensor_count": len(weight_map),
        "referenced_shard_count": len(referenced),
        "referenced_shards": sorted(referenced),
        "declared_total_size_bytes": declared_total,
        "missing_shards": missing,
        "unreferenced_shards": unreferenced,
    }


def inspect_hf_folder(
    path: str | os.PathLike[str],
    limits: HFFolderLimits | None = None,
) -> dict[str, Any]:
    """Summarize a local Hugging Face model folder without loading weights."""

    base = Path(path)
    limits = limits or HFFolderLimits()
    try:
        stat = base.stat()
    except OSError as exc:
        raise HFFolderError(f"Cannot access input folder: {exc}") from exc
    if not base.is_dir():
        raise HFFolderFormatError("Input path is not a directory")

    files: dict[str, int] = {}
    directories: list[str] = []
    symlinks: list[str] = []
    other: list[str] = []
    warnings: list[str] = []
    entry_count = 0

    try:
        # Keep the scan lazy. Materializing list(os.scandir(...)) first would
        # allocate memory for every directory entry before enforcing max_entries.
        with os.scandir(base) as entries:
            for entry in entries:
                entry_count += 1
                if entry_count > limits.max_entries:
                    raise HFFolderResourceLimitError(
                        f"Folder has more than {limits.max_entries:,} entries"
                    )
                if len(entry.name.encode("utf-8")) > limits.max_name_bytes:
                    raise HFFolderResourceLimitError(
                        f"Folder entry name exceeds {limits.max_name_bytes:,} bytes"
                    )
                if entry.is_symlink():
                    symlinks.append(entry.name)
                elif entry.is_dir(follow_symlinks=False):
                    directories.append(entry.name)
                elif entry.is_file(follow_symlinks=False):
                    try:
                        files[entry.name] = entry.stat(follow_symlinks=False).st_size
                    except OSError as exc:
                        warnings.append(f"Could not read the size of {entry.name!r}: {exc}")
                else:
                    other.append(entry.name)
    except OSError as exc:
        raise HFFolderError(f"Cannot list input folder: {exc}") from exc

    config_summary: dict[str, Any] | None = None
    config_error: str | None = None
    if _CONFIG_FILE in files:
        text, reason = _read_bounded_text(base / _CONFIG_FILE, limits.max_config_bytes)
        if reason is not None:
            config_error = reason
            warnings.append(f"Did not parse {_CONFIG_FILE}: {reason}")
        else:
            try:
                parsed_config = json.loads(text or "")
            except json.JSONDecodeError as exc:
                raise HFFolderFormatError(f"{_CONFIG_FILE} is not valid JSON: {exc.msg}") from exc
            if not isinstance(parsed_config, dict):
                raise HFFolderFormatError(f"{_CONFIG_FILE} must be a JSON object")
            config_summary = _summarize_config(parsed_config)

    safetensors_shards = sorted(name for name in files if name.endswith(_SAFETENSORS_SUFFIX))
    total_shard_bytes = sum(files[name] for name in safetensors_shards)

    index_summary: dict[str, Any] | None = None
    if _INDEX_FILE in files:
        text, reason = _read_bounded_text(base / _INDEX_FILE, limits.max_index_bytes)
        if reason is not None:
            index_summary = {"file_name": _INDEX_FILE, "error": reason}
            warnings.append(f"Did not parse {_INDEX_FILE}: {reason}")
        else:
            index_summary = _parse_index(text or "", files=files, limits=limits)
            missing = index_summary["missing_shards"]
            if missing:
                warnings.append(
                    "Safetensors index references shard files that are not present: "
                    + ", ".join(missing[:10])
                    + (" ..." if len(missing) > 10 else "")
                )
            unreferenced = index_summary["unreferenced_shards"]
            if unreferenced:
                warnings.append(
                    "Safetensors files are present but not referenced by the index: "
                    + ", ".join(unreferenced[:10])
                    + (" ..." if len(unreferenced) > 10 else "")
                )
            # The index's metadata.total_size describes tensor-data bytes,
            # not the complete shard files (which also contain headers). Reconcile
            # it only after each Safetensors header has been inspected.

    if not safetensors_shards:
        warnings.append("No .safetensors files were found in the folder")
    if _CONFIG_FILE not in files:
        warnings.append(f"{_CONFIG_FILE} was not found in the folder")
    if symlinks:
        warnings.append(
            "Symbolic links were not followed: "
            + ", ".join(sorted(symlinks)[:10])
            + (" ..." if len(symlinks) > 10 else "")
        )
    if other:
        warnings.append(
            "Non-regular entries were skipped: "
            + ", ".join(sorted(other)[:10])
            + (" ..." if len(other) > 10 else "")
        )

    return {
        "format": "huggingface_folder",
        "folder_name": base.name or str(base),
        "entry_count": entry_count,
        "file_count": len(files),
        "directory_count": len(directories),
        "symlink_count": len(symlinks),
        "files": [{"name": name, "size_bytes": files[name]} for name in sorted(files)],
        "directories": sorted(directories),
        "symlinks": sorted(symlinks),
        "config": config_summary,
        "config_error": config_error,
        "safetensors": {
            "shard_count": len(safetensors_shards),
            "shards": [{"name": name, "size_bytes": files[name]} for name in safetensors_shards],
            "total_bytes": total_shard_bytes,
            "index": index_summary,
        },
        "evidence": {
            "file_sizes": "observed",
            "config_fields": "observed" if config_summary is not None else "unknown",
            "index_weight_map": (
                "observed"
                if index_summary is not None and "error" not in index_summary
                else "unknown"
            ),
            "shard_total_bytes": "observed",
        },
        "inspection": {
            "mode": "static_read_only",
            "tensor_payload_bytes_read": 0,
            "tensor_payloads_loaded": False,
            "source_modified": False,
        },
        "warnings": warnings,
    }
