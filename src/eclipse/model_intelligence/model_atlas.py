"""Evidence-labelled Model Atlas aggregation.

Composes the existing read-only inspectors into one machine-readable summary
for a GGUF file, a Safetensors file, or a Hugging Face model folder. No tensor
payload bytes are read and no model code is executed. Every reported value
carries an explicit evidence label so callers can tell observed, derived and
unknown data apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .gguf import GGUFError, InspectionLimits, inspect_gguf
from .hf_folder import HFFolderError, HFFolderLimits, inspect_hf_folder
from .safetensors import SafetensorsError, SafetensorsLimits, inspect_safetensors
from .tokenizer import (
    TokenizerError,
    TokenizerLimits,
    inspect_tokenizer,
    summarize_gguf_tokenizer,
)

_GGUF_SUFFIX = ".gguf"
_SAFETENSORS_SUFFIX = ".safetensors"

_STATIC_INSPECTION = {
    "mode": "static_read_only",
    "tensor_payload_bytes_read": 0,
    "tensor_payloads_loaded": False,
    "source_modified": False,
}


class ModelAtlasError(Exception):
    """Base class for expected Model Atlas failures."""


class ModelAtlasFormatError(ModelAtlasError):
    """The input is not a supported model file or folder."""


@dataclass(frozen=True, slots=True)
class ModelAtlasLimits:
    """Per-format limits used while building one Model Atlas report."""

    gguf: InspectionLimits = field(default_factory=InspectionLimits)
    safetensors: SafetensorsLimits = field(default_factory=SafetensorsLimits)
    folder: HFFolderLimits = field(default_factory=HFFolderLimits)
    tokenizer: TokenizerLimits = field(default_factory=TokenizerLimits)
    max_shards: int = 4096

    def __post_init__(self) -> None:
        if not isinstance(self.max_shards, int) or self.max_shards < 0:
            raise ValueError("max_shards must be a non-negative integer")
        if not isinstance(self.gguf, InspectionLimits):
            raise ValueError("gguf must be an InspectionLimits instance")
        if not isinstance(self.safetensors, SafetensorsLimits):
            raise ValueError("safetensors must be a SafetensorsLimits instance")
        if not isinstance(self.folder, HFFolderLimits):
            raise ValueError("folder must be an HFFolderLimits instance")
        if not isinstance(self.tokenizer, TokenizerLimits):
            raise ValueError("tokenizer must be a TokenizerLimits instance")




_ARCHITECTURE_DETAIL_KEYS = (
    "layer_count",
    "hidden_size",
    "attention_heads",
    "kv_heads",
    "key_head_dimension",
    "value_head_dimension",
    "context_length",
    "intermediate_size",
    "expert_count",
    "experts_per_token",
    "shared_expert_count",
)


def _architecture_fact(
    value: Any,
    source: str | None,
    *,
    evidence: str = "observed",
) -> dict[str, Any]:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return {"value": value, "evidence": evidence, "source": source}
    return {"value": None, "evidence": "unknown", "source": None}


def _hf_declared_fact(
    config: dict[str, Any],
    aliases: tuple[str, ...],
    source_prefix: str,
) -> dict[str, Any]:
    """Resolve bounded, explicitly declared architecture integers.

    Multiple aliases with conflicting values remain unknown; no key silently
    wins just because it appears earlier in a preference list.
    """
    present = [
        (key, config[key])
        for key in aliases
        if key in config
        and isinstance(config[key], int)
        and not isinstance(config[key], bool)
        and config[key] > 0
    ]
    if not present:
        return _architecture_fact(None, None)

    if len({value for _, value in present}) > 1:
        declarations = ", ".join(
            f"{source_prefix}:{key}={value}" for key, value in present
        )
        return {
            "value": None,
            "evidence": "unknown",
            "source": None,
            "reason": "Conflicting architecture declarations: " + declarations,
        }

    key, value = present[0]
    return _architecture_fact(
        value,
        f"{source_prefix}:{key}",
        evidence="declared",
    )


def _empty_architecture_details() -> dict[str, dict[str, Any]]:
    return {
        name: _architecture_fact(None, None)
        for name in _ARCHITECTURE_DETAIL_KEYS
    }


def _gguf_architecture_details(
    metadata: dict[str, Any],
    architecture: Any,
) -> dict[str, dict[str, Any]]:
    if not isinstance(architecture, str) or not architecture:
        return _empty_architecture_details()
    suffixes = {
        "layer_count": "block_count",
        "hidden_size": "embedding_length",
        "attention_heads": "attention.head_count",
        "kv_heads": "attention.head_count_kv",
        "key_head_dimension": "attention.key_length",
        "value_head_dimension": "attention.value_length",
        "context_length": "context_length",
        "intermediate_size": "feed_forward_length",
        "expert_count": "expert_count",
        "experts_per_token": "expert_used_count",
        "shared_expert_count": "shared_expert_count",
    }
    result: dict[str, dict[str, Any]] = {}
    for label, suffix in suffixes.items():
        key = f"{architecture}.{suffix}"
        result[label] = _architecture_fact(metadata.get(key), key)
    return result


def _hf_architecture_details(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source_config = config
    source_prefix = "config.json"
    nested = config.get("text_config")
    if isinstance(nested, dict):
        # Text-only architecture details are preferred for multimodal model
        # folders when the top-level config is only a wrapper.
        source_config = nested
        source_prefix = "config.json:text_config"

    aliases = {
        "layer_count": ("num_hidden_layers", "n_layer", "n_layers"),
        "hidden_size": ("hidden_size", "n_embd", "d_model"),
        "attention_heads": ("num_attention_heads", "n_head", "num_heads"),
        "kv_heads": ("num_key_value_heads", "num_kv_heads", "n_head_kv"),
        "key_head_dimension": ("head_dim", "key_head_dim"),
        "value_head_dimension": ("head_dim", "value_head_dim"),
        "context_length": (
            "max_position_embeddings",
            "max_sequence_length",
            "max_seq_len",
            "n_positions",
            "seq_length",
        ),
        "intermediate_size": ("intermediate_size", "n_inner", "d_ff"),
        "expert_count": ("num_local_experts", "num_experts", "n_expert"),
        "experts_per_token": ("num_experts_per_tok", "num_experts_per_token"),
        "shared_expert_count": ("num_shared_experts",),
    }
    return {
        label: _hf_declared_fact(source_config, keys, source_prefix)
        for label, keys in aliases.items()
    }


def _detect_kind(path: Path) -> str:
    if path.is_dir():
        return "huggingface_folder"
    suffix = path.suffix.lower()
    if suffix == _GGUF_SUFFIX:
        return "gguf"
    if suffix == _SAFETENSORS_SUFFIX:
        return "safetensors"
    raise ModelAtlasFormatError(
        f"Unsupported input: expected a directory, a {_GGUF_SUFFIX} file or a {_SAFETENSORS_SUFFIX} file"
    )


def _summarize_tensors(
    tensors: list[dict[str, Any]],
    *,
    kind_key: str,
) -> dict[str, Any]:
    total_parameters = 0
    total_storage = 0
    complete = True
    counts: dict[str, int] = {}
    for tensor in tensors:
        element_count = tensor.get("element_count")
        if isinstance(element_count, int):
            total_parameters += element_count
        label = tensor.get(kind_key)
        if isinstance(label, str):
            counts[label] = counts.get(label, 0) + 1
        storage = tensor.get("storage_bytes")
        if storage is None:
            complete = False
        elif isinstance(storage, int):
            total_storage += storage
    return {
        "tensor_count": len(tensors),
        "total_parameters": total_parameters,
        "total_storage_bytes": total_storage,
        "total_storage_is_complete": complete,
        "counts": dict(sorted(counts.items())),
    }


def _tokenizer_section_from_folder(path: Path, limits: ModelAtlasLimits) -> tuple[dict[str, Any], list[str]]:
    try:
        report = inspect_tokenizer(path, limits.tokenizer)
    except TokenizerError as exc:
        message = f"Tokenizer inspection was unavailable: {exc}"
        return (
            {
                "available": False,
                "source": "huggingface_folder",
                "error": str(exc),
                "warnings": [message],
            },
            [message],
        )

    section = dict(report["tokenizer"])
    has_data = bool(report["assets"]) or report["chat_templates"]["count"] > 0
    section.update(
        {
            "available": has_data,
            "source": "huggingface_folder",
            "assets": report["assets"],
            "chat_templates": report["chat_templates"],
            "evidence": report["evidence"],
            "warnings": list(report["warnings"]),
        }
    )
    return section, list(report["warnings"])


def _atlas_from_gguf(path: Path, limits: ModelAtlasLimits) -> dict[str, Any]:
    report = inspect_gguf(path, limits.gguf)
    summary = _summarize_tensors(report["tensors"], kind_key="type_name")
    tokenizer = summarize_gguf_tokenizer(report["metadata"], limits.tokenizer)
    return {
        "source_kind": "gguf",
        "source_name": report["source_file_name"],
        "architecture": {
            "architecture": report["model"]["architecture"],
            "name": report["model"]["name"],
            "evidence": report["model"]["evidence"],
            "details": _gguf_architecture_details(
                report["metadata"], report["model"]["architecture"]
            ),
        },
        "summary": {
            "tensor_count": summary["tensor_count"],
            "total_parameters": summary["total_parameters"],
            "total_storage_bytes": report["tensor_storage"]["total_bytes"],
            "total_storage_is_complete": report["tensor_storage"]["total_is_complete"],
            "distribution": {"label": "ggml_type", "counts": summary["counts"]},
            "parameters_evidence": "observed",
            "storage_evidence": "derived",
        },
        "tokenizer": tokenizer,
        "components": {
            "gguf": {
                "format": report["format"],
                "version": report["version"],
                "endianness": report["endianness"],
                "file_size_bytes": report["file_size_bytes"],
                "registry_revision": report["tensor_storage"]["registry_revision"],
            }
        },
        "warnings": list(report["warnings"]),
    }


def _atlas_from_safetensors(path: Path, limits: ModelAtlasLimits) -> dict[str, Any]:
    report = inspect_safetensors(path, limits.safetensors)
    summary = _summarize_tensors(report["tensors"], kind_key="dtype")
    return {
        "source_kind": "safetensors",
        "source_name": report["source_file_name"],
        "architecture": {
            "architecture": None,
            "name": None,
            "evidence": "unknown",
            "details": _empty_architecture_details(),
        },
        "summary": {
            "tensor_count": summary["tensor_count"],
            "total_parameters": summary["total_parameters"],
            "total_storage_bytes": report["total_tensor_storage_bytes"],
            "total_storage_is_complete": summary["total_storage_is_complete"],
            "distribution": {"label": "safetensors_dtype", "counts": summary["counts"]},
            "parameters_evidence": "observed",
            "storage_evidence": "observed",
        },
        "tokenizer": {
            "available": False,
            "source": "unknown",
            "note": (
                "A standalone Safetensors file does not carry tokenizer assets. Choose the "
                "model folder to inspect its tokenizer and chat templates."
            ),
            "warnings": [],
        },
        "components": {
            "safetensors": {
                "file_size_bytes": report["file_size_bytes"],
                "header_length_bytes": report["header_length_bytes"],
                "data_region_bytes": report["data_region_bytes"],
            }
        },
        "warnings": list(report["warnings"]),
    }


def _atlas_from_folder(path: Path, limits: ModelAtlasLimits) -> dict[str, Any]:
    folder = inspect_hf_folder(path, limits.folder)
    discovered_shards = [shard["name"] for shard in folder["safetensors"]["shards"]]
    index = folder["safetensors"]["index"]
    index_is_valid = isinstance(index, dict) and "error" not in index

    # When a valid index exists, it defines the model's shard set. Do not count
    # unrelated or stale .safetensors files as model weights.
    if index_is_valid:
        available = set(discovered_shards)
        shard_names = [
            name for name in index["referenced_shards"] if name in available
        ]
        missing_shards = list(index["missing_shards"])
        index_coverage_is_complete = not missing_shards
    else:
        # Without a readable index, a lone standard model.safetensors file can
        # still be inspected completely. Multiple files have no proven mapping.
        shard_names = discovered_shards
        missing_shards = []
        index_coverage_is_complete = index is None and len(shard_names) == 1

    if len(shard_names) > limits.max_shards:
        raise ModelAtlasError(
            f"Folder has {len(shard_names):,} referenced Safetensors shards; limit is {limits.max_shards:,}"
        )

    tensors: list[dict[str, Any]] = []
    inspected_shards: list[dict[str, Any]] = []
    shard_errors: list[dict[str, str]] = []
    for name in shard_names:
        try:
            report = inspect_safetensors(path / name, limits.safetensors)
        except SafetensorsError as exc:
            shard_errors.append({"shard": name, "error": str(exc)})
            continue
        tensors.extend(report["tensors"])
        inspected_shards.append(
            {
                "name": name,
                "tensor_count": report["tensor_count"],
                "storage_bytes": report["total_tensor_storage_bytes"],
            }
        )

    summary = _summarize_tensors(tensors, kind_key="dtype")
    complete = (
        summary["total_storage_is_complete"]
        and not shard_errors
        and index_coverage_is_complete
    )
    config = folder["config"] or {}
    architecture = config.get("model_type")
    architectures = config.get("architectures") if isinstance(config.get("architectures"), list) else None
    if architecture is None and architectures:
        architecture = architectures[0]

    warnings = list(folder["warnings"])
    if shard_errors:
        warnings.append(
            "Could not inspect "
            f"{len(shard_errors)} Safetensors shard(s): "
            + ", ".join(error["shard"] for error in shard_errors[:10])
            + (" ..." if len(shard_errors) > 10 else "")
        )

    declared_total = index.get("declared_total_size_bytes") if index_is_valid else None
    if complete and declared_total is not None and declared_total != summary["total_storage_bytes"]:
        warnings.append(
            "Observed Safetensors tensor-data bytes "
            f"({summary['total_storage_bytes']:,}) differ from the index metadata.total_size "
            f"({declared_total:,})"
        )
        complete = False

    tokenizer, tokenizer_warnings = _tokenizer_section_from_folder(path, limits)
    warnings.extend(tokenizer_warnings)

    return {
        "source_kind": "huggingface_folder",
        "source_name": folder["folder_name"],
        "architecture": {
            "architecture": architecture,
            "name": architecture,
            "evidence": "observed" if architecture is not None else "unknown",
            "details": _hf_architecture_details(config),
        },
        "summary": {
            "tensor_count": summary["tensor_count"],
            "total_parameters": summary["total_parameters"],
            "total_storage_bytes": summary["total_storage_bytes"],
            "total_storage_is_complete": complete,
            "distribution": {"label": "safetensors_dtype", "counts": summary["counts"]},
            "parameters_evidence": "observed",
            "storage_evidence": "observed",
        },
        "tokenizer": tokenizer,
        "components": {
            "folder": {
                "shard_count": (
                    index["referenced_shard_count"]
                    if index_is_valid
                    else len(discovered_shards)
                ),
                "available_shard_count": len(discovered_shards),
                "missing_shard_count": len(missing_shards),
                "inspected_shard_count": len(inspected_shards),
                "shards": inspected_shards,
                "index": index,
            }
        },
        "warnings": warnings,
    }


def build_model_atlas(
    path: str | Path,
    limits: ModelAtlasLimits | None = None,
) -> dict[str, Any]:
    """Build a single evidence-labelled atlas for a model file or folder."""

    source = Path(path)
    limits = limits or ModelAtlasLimits()
    try:
        kind = _detect_kind(source)
    except OSError as exc:
        raise ModelAtlasFormatError(f"Cannot access input: {exc}") from exc

    try:
        if kind == "gguf":
            body = _atlas_from_gguf(source, limits)
        elif kind == "safetensors":
            body = _atlas_from_safetensors(source, limits)
        else:
            body = _atlas_from_folder(source, limits)
    except (GGUFError, HFFolderError, SafetensorsError) as exc:
        raise ModelAtlasError(str(exc)) from exc

    tokenizer_section = body.get("tokenizer")
    tokenizer_label = (
        "observed" if isinstance(tokenizer_section, dict) and tokenizer_section.get("available") is True else "unknown"
    )

    return {
        "format": "eclipse_model_atlas",
        "atlas_version": 1,
        **body,
        "evidence": {
            "parameters": body["summary"]["parameters_evidence"],
            "storage_bytes": body["summary"]["storage_evidence"],
            "architecture": body["architecture"]["evidence"],
            "tokenizer": tokenizer_label,
        },
        "inspection": dict(_STATIC_INSPECTION),
    }
