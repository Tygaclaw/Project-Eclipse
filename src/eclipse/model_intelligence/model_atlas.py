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


def _atlas_from_gguf(path: Path, limits: ModelAtlasLimits) -> dict[str, Any]:
    report = inspect_gguf(path, limits.gguf)
    summary = _summarize_tensors(report["tensors"], kind_key="type_name")
    return {
        "source_kind": "gguf",
        "source_name": report["source_file_name"],
        "architecture": {
            "architecture": report["model"]["architecture"],
            "name": report["model"]["name"],
            "evidence": report["model"]["evidence"],
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
        "architecture": {"architecture": None, "name": None, "evidence": "unknown"},
        "summary": {
            "tensor_count": summary["tensor_count"],
            "total_parameters": summary["total_parameters"],
            "total_storage_bytes": report["total_tensor_storage_bytes"],
            "total_storage_is_complete": summary["total_storage_is_complete"],
            "distribution": {"label": "safetensors_dtype", "counts": summary["counts"]},
            "parameters_evidence": "observed",
            "storage_evidence": "observed",
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
    shard_names = [shard["name"] for shard in folder["safetensors"]["shards"]]
    if len(shard_names) > limits.max_shards:
        raise ModelAtlasError(
            f"Folder has {len(shard_names):,} Safetensors shards; limit is {limits.max_shards:,}"
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
    complete = summary["total_storage_is_complete"] and not shard_errors
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

    return {
        "source_kind": "huggingface_folder",
        "source_name": folder["folder_name"],
        "architecture": {
            "architecture": architecture,
            "name": architecture,
            "evidence": "observed" if architecture is not None else "unknown",
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
        "components": {
            "folder": {
                "shard_count": len(shard_names),
                "inspected_shard_count": len(inspected_shards),
                "shards": inspected_shards,
                "index": folder["safetensors"]["index"],
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

    return {
        "format": "eclipse_model_atlas",
        "atlas_version": 1,
        **body,
        "evidence": {
            "parameters": body["summary"]["parameters_evidence"],
            "storage_bytes": body["summary"]["storage_evidence"],
            "architecture": body["architecture"]["evidence"],
        },
        "inspection": dict(_STATIC_INSPECTION),
    }
