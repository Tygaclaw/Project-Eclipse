"""Evidence-labelled memory feasibility planning.

This module estimates checkpoint-resident memory needs from Model Atlas facts
and a point-in-time host snapshot. It does not choose executable GPU layers,
predict tokens/second, or claim that an inference backend supports a model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

MiB = 1024 * 1024
GiB = 1024 * MiB

_KV_BYTES_PER_ELEMENT = {
    "f16": 2,
    "bf16": 2,
    "f32": 4,
}


class FeasibilityError(Exception):
    """Base class for invalid feasibility inputs."""


@dataclass(frozen=True, slots=True)
class FeasibilityRequest:
    """User-adjustable inputs used for one memory feasibility estimate."""

    context_tokens: int | None = None
    kv_cache_dtype: str = "f16"
    sequence_slots: int = 1
    system_ram_reserve_bytes: int = 8 * GiB
    gpu_vram_reserve_bytes: int = 768 * MiB

    def __post_init__(self) -> None:
        if self.context_tokens is not None and (
            isinstance(self.context_tokens, bool)
            or not isinstance(self.context_tokens, int)
            or self.context_tokens <= 0
        ):
            raise ValueError("context_tokens must be a positive integer or None")
        if self.kv_cache_dtype not in _KV_BYTES_PER_ELEMENT:
            raise ValueError(
                "kv_cache_dtype must be one of: " + ", ".join(sorted(_KV_BYTES_PER_ELEMENT))
            )
        if isinstance(self.sequence_slots, bool) or not isinstance(self.sequence_slots, int) or self.sequence_slots <= 0:
            raise ValueError("sequence_slots must be a positive integer")
        for name in ("system_ram_reserve_bytes", "gpu_vram_reserve_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _fact_value(details: Mapping[str, Any], name: str) -> int | None:
    fact = details.get(name)
    if not isinstance(fact, Mapping):
        return None
    value = fact.get("value")
    return value if _is_int(value) and value > 0 else None


def _available_ram(snapshot: Mapping[str, Any], reserve: int) -> dict[str, Any]:
    memory = snapshot.get("system_memory")
    memory = memory if isinstance(memory, Mapping) else {}
    available = memory.get("available_bytes")
    physical = memory.get("physical_total_bytes")
    if not _is_int(available) or available < 0:
        return {
            "physical_total_bytes": physical if _is_int(physical) and physical > 0 else None,
            "available_before_reserve_bytes": None,
            "reserve_bytes": reserve,
            "usable_bytes": None,
            "evidence": "unknown",
        }
    return {
        "physical_total_bytes": physical if _is_int(physical) and physical > 0 else None,
        "available_before_reserve_bytes": available,
        "reserve_bytes": reserve,
        "usable_bytes": max(0, available - reserve),
        "evidence": "observed",
    }


def _selected_gpu(snapshot: Mapping[str, Any], reserve: int) -> dict[str, Any]:
    raw_gpus = snapshot.get("gpus")
    gpus = [gpu for gpu in raw_gpus if isinstance(gpu, Mapping)] if isinstance(raw_gpus, list) else []
    # Never add separate GPU VRAM pools together. The first candidate is the
    # device with the largest observed free-memory reading.
    observed = [
        gpu for gpu in gpus
        if _is_int(gpu.get("memory_free_bytes")) and gpu["memory_free_bytes"] >= 0
    ]
    chosen = max(observed, key=lambda gpu: gpu["memory_free_bytes"]) if observed else None
    if chosen is None:
        return {
            "device_name": None,
            "memory_total_bytes": None,
            "free_before_reserve_bytes": None,
            "reserve_bytes": reserve,
            "usable_bytes": None,
            "evidence": "unknown",
            "selection": "No GPU with an observed free-VRAM reading was reported.",
        }
    free = int(chosen["memory_free_bytes"])
    total = chosen.get("memory_total_bytes")
    return {
        "device_name": chosen.get("name"),
        "memory_total_bytes": total if _is_int(total) and total > 0 else None,
        "free_before_reserve_bytes": free,
        "reserve_bytes": reserve,
        "usable_bytes": max(0, free - reserve),
        "evidence": "observed",
        "selection": "Largest single GPU by observed free VRAM; GPU pools are not aggregated.",
    }


def _fit_status(required: int | None, available: int | None) -> str:
    if required is None or available is None:
        return "unknown"
    return "fits_within_known_budget" if required <= available else "exceeds_known_budget"


def _architecture_details(atlas: Mapping[str, Any]) -> Mapping[str, Any]:
    architecture = atlas.get("architecture")
    if not isinstance(architecture, Mapping):
        return {}
    details = architecture.get("details")
    return details if isinstance(details, Mapping) else {}


def _weight_storage(atlas: Mapping[str, Any]) -> dict[str, Any]:
    summary = atlas.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    value = summary.get("total_storage_bytes")
    complete = summary.get("total_storage_is_complete") is True
    evidence = summary.get("storage_evidence")
    valid = _is_int(value) and value >= 0 and complete
    return {
        "bytes": int(value) if _is_int(value) and value >= 0 else None,
        "complete": complete,
        "evidence": evidence if evidence in {"observed", "derived"} else "unknown",
        "usable_for_full_model_estimate": valid,
        "note": (
            "Checkpoint tensor storage is used as a lower-bound estimate for resident weights. "
            "Runtime alignment, converted layouts and temporary workspaces are not included."
        ),
    }


def _kv_cache_estimate(
    details: Mapping[str, Any],
    request: FeasibilityRequest,
) -> dict[str, Any]:
    declared_context = _fact_value(details, "context_length")
    context = request.context_tokens if request.context_tokens is not None else declared_context
    context_source = (
        "user_requested"
        if request.context_tokens is not None
        else "model_declared"
        if declared_context is not None
        else "unknown"
    )
    layers = _fact_value(details, "layer_count")
    kv_heads = _fact_value(details, "kv_heads")
    key_dim = _fact_value(details, "key_head_dimension")
    value_dim = _fact_value(details, "value_head_dimension")
    bytes_per_element = _KV_BYTES_PER_ELEMENT[request.kv_cache_dtype]

    missing = [
        label
        for label, value in (
            ("context length", context),
            ("layer count", layers),
            ("key/value head count", kv_heads),
            ("key head dimension", key_dim),
            ("value head dimension", value_dim),
        )
        if value is None
    ]
    if missing:
        return {
            "bytes": None,
            "evidence": "unknown",
            "dtype": request.kv_cache_dtype,
            "bytes_per_element": bytes_per_element,
            "context_tokens": context,
            "context_source": context_source,
            "declared_context_limit_tokens": declared_context,
            "sequence_slots": request.sequence_slots,
            "formula": "layers × context × KV heads × (key head dimension + value head dimension) × bytes per element × sequence slots",
            "missing_architecture_facts": missing,
            "note": "KV-cache size is unknown until the missing architecture facts are available.",
        }

    estimate = (
        layers
        * context
        * kv_heads
        * (key_dim + value_dim)
        * bytes_per_element
        * request.sequence_slots
    )
    exceeds_declared = declared_context is not None and context > declared_context
    return {
        "bytes": estimate,
        "evidence": "estimated",
        "dtype": request.kv_cache_dtype,
        "bytes_per_element": bytes_per_element,
        "context_tokens": context,
        "context_source": context_source,
        "declared_context_limit_tokens": declared_context,
        "requested_context_exceeds_declared_limit": exceeds_declared,
        "sequence_slots": request.sequence_slots,
        "formula": "layers × context × KV heads × (key head dimension + value head dimension) × bytes per element × sequence slots",
        "inputs": {
            "layers": layers,
            "context_tokens": context,
            "kv_heads": kv_heads,
            "key_head_dimension": key_dim,
            "value_head_dimension": value_dim,
            "bytes_per_element": bytes_per_element,
            "sequence_slots": request.sequence_slots,
        },
        "note": "Architecture-derived estimate. Backend padding, block layout, batching details and allocator overhead are not included.",
    }


def plan_model_feasibility(
    atlas: Mapping[str, Any],
    host: Mapping[str, Any] | Any,
    request: FeasibilityRequest | None = None,
) -> dict[str, Any]:
    """Estimate whether known checkpoint and KV costs fit current RAM/VRAM.

    The result is a memory-capacity envelope, not an executable placement
    manifest. A supported backend must still validate model/quantization
    compatibility and actual runtime allocations.
    """

    if not isinstance(atlas, Mapping) or atlas.get("format") != "eclipse_model_atlas":
        raise FeasibilityError("A valid eclipse_model_atlas document is required")
    if hasattr(host, "to_dict"):
        snapshot = host.to_dict()
    else:
        snapshot = host
    if not isinstance(snapshot, Mapping):
        raise FeasibilityError("A host hardware snapshot is required")
    request = request or FeasibilityRequest()

    details = _architecture_details(atlas)
    weights = _weight_storage(atlas)
    kv = _kv_cache_estimate(details, request)
    ram = _available_ram(snapshot, request.system_ram_reserve_bytes)
    gpu = _selected_gpu(snapshot, request.gpu_vram_reserve_bytes)

    # An incomplete report can still give a useful lower bound: the bytes
    # already measured are known to exist. A lower bound below the budget,
    # however, cannot prove the full model will fit.
    weight_lower_bound_bytes = weights["bytes"]
    weight_bytes = (
        weight_lower_bound_bytes
        if weights["usable_for_full_model_estimate"]
        else None
    )
    kv_bytes = kv["bytes"]
    total_required = (
        weight_bytes + kv_bytes
        if weight_bytes is not None and kv_bytes is not None
        else None
    )
    total_available = (
        ram["usable_bytes"] + gpu["usable_bytes"]
        if _is_int(ram["usable_bytes"]) and _is_int(gpu["usable_bytes"])
        else None
    )

    ram_usable = ram["usable_bytes"]
    gpu_usable = gpu["usable_bytes"]
    weights_only = {
        "required_bytes": weight_lower_bound_bytes,
        "is_lower_bound_only": not weights["usable_for_full_model_estimate"],
        "ram_only": _fit_status(weight_lower_bound_bytes, ram_usable),
        "gpu_only": _fit_status(weight_lower_bound_bytes, gpu_usable),
        "combined_ram_and_single_gpu": _fit_status(weight_lower_bound_bytes, total_available),
    }
    full_resident = {
        "required_bytes": total_required,
        "ram_only": _fit_status(total_required, ram_usable),
        "gpu_only": _fit_status(total_required, gpu_usable),
        "combined_ram_and_single_gpu": _fit_status(total_required, total_available),
        "evidence": "estimated" if total_required is not None else "unknown",
    }

    # Known weight bytes that already exceed the combined resident envelope
    # are a decisive lower bound, even if some tensor types or shards remain
    # unknown. An incomplete report below budget cannot prove a fit.
    weights_exceed_envelope = (
        _fit_status(weight_lower_bound_bytes, total_available) == "exceeds_known_budget"
    )
    if weights_exceed_envelope:
        memory_class = "exceeds_resident_capacity_even_before_kv_cache"
    elif not weights["usable_for_full_model_estimate"]:
        memory_class = "unknown_incomplete_weight_storage"
    elif kv_bytes is None:
        memory_class = "unknown_kv_cache_cost"
    elif full_resident["combined_ram_and_single_gpu"] == "fits_within_known_budget":
        memory_class = "estimated_resident_memory_fit"
    elif full_resident["combined_ram_and_single_gpu"] == "exceeds_known_budget":
        memory_class = "exceeds_available_resident_ram_and_vram"
    else:
        memory_class = "unknown_available_memory"

    # Evaluate the requested profile, not weight storage in isolation. A
    # complete weight estimate plus a known KV estimate may exceed the
    # resident envelope even when the weights alone fit. Conversely, an
    # incomplete estimate below budget cannot prove that the model fits.
    full_estimate_exceeds_envelope = (
        weights["usable_for_full_model_estimate"]
        and kv_bytes is not None
        and full_resident["combined_ram_and_single_gpu"] == "exceeds_known_budget"
    )
    oversized_for_requested_profile = (
        weights_exceed_envelope or full_estimate_exceeds_envelope
    )
    if oversized_for_requested_profile:
        native_memory_candidate = "oversized_for_requested_profile"
        target_applies: bool | None = True
    elif (
        weights["usable_for_full_model_estimate"]
        and kv_bytes is not None
        and full_resident["combined_ram_and_single_gpu"] == "fits_within_known_budget"
    ):
        native_memory_candidate = "within_resident_capacity_candidate"
        target_applies = False
    else:
        native_memory_candidate = "unknown"
        target_applies = None

    performance_goal_policy = {
        "scope": "large_models_that_cannot_run_natively_only",
        "applies_to_this_profile": target_applies,
        "primary_acceptance_goal": (
            "10+ sustained tokens/second" if target_applies is True else None
        ),
        "preferred_stretch_goal": (
            "15–20+ sustained tokens/second" if target_applies is True else None
        ),
        "native_fit_policy": (
            "No fixed throughput floor. Preserve quality and optimize the best verified native performance."
            if target_applies is False
            else None
        ),
        "evidence": "estimated" if target_applies is not None else "unknown",
        "note": (
            "This is a static memory-capacity candidate only. It does not prove backend support, "
            "native runnability or speed, and it is never a tokens/second prediction."
        ),
    }

    storage = snapshot.get("storage")
    storage = storage if isinstance(storage, Mapping) else {}
    warnings: list[str] = [
        "Static memory estimate only. This result does not validate a backend, operator support, executable layer split, tokens/second, or output quality.",
        "Runtime workspaces, allocator overhead, temporary buffers and backend-specific alignment are not included as measured values.",
        "Separate GPU VRAM pools are not combined. The estimate uses the single GPU with the largest observed free-VRAM reading.",
        "SSD capacity is reported separately; cold storage is not counted as resident memory and per-token SSD streaming is not assumed to be practical.",
        "The 10+ primary and 15–20+ preferred throughput goals are only for large models classified as oversized candidates; models within the known resident-memory envelope have no fixed throughput floor.",
    ]
    if not weights["usable_for_full_model_estimate"]:
        warnings.append("Complete model tensor storage is not available, so full-model weight residency cannot be estimated.")
    if kv_bytes is None:
        warnings.append("KV-cache size is unknown because one or more required context or architecture facts are missing.")
    if kv.get("requested_context_exceeds_declared_limit"):
        warnings.append("The requested context exceeds the model-declared context limit; no runtime override support is assumed.")
    if gpu_usable is None:
        warnings.append("GPU free VRAM is unknown; GPU and combined memory-fit results remain unknown.")
    if weights_only["combined_ram_and_single_gpu"] == "exceeds_known_budget":
        warnings.append("Checkpoint weights alone exceed the currently usable RAM plus the selected GPU's VRAM, before KV cache and runtime overhead.")

    return {
        "format": "eclipse_model_feasibility",
        "feasibility_version": 1,
        "model": {
            "source_kind": atlas.get("source_kind"),
            "source_name": atlas.get("source_name"),
            "architecture": (
                atlas.get("architecture", {}).get("architecture")
                if isinstance(atlas.get("architecture"), Mapping)
                else None
            ),
        },
        "host": {
            "captured_at": snapshot.get("captured_at"),
            "operating_system": snapshot.get("operating_system"),
            "processor": snapshot.get("processor"),
            "system_memory": ram,
            "selected_gpu": gpu,
            "gpu_discovery": snapshot.get("gpu_discovery"),
            "storage": {
                "volume": storage.get("volume"),
                "total_bytes": storage.get("total_bytes"),
                "free_bytes": storage.get("free_bytes"),
                "evidence": storage.get("evidence", "unknown"),
                "device_type": storage.get("device_type"),
                "device_type_evidence": storage.get("device_type_evidence", "unknown"),
            },
        },
        "request": {
            "context_tokens": kv["context_tokens"],
            "context_source": kv["context_source"],
            "kv_cache_dtype": request.kv_cache_dtype,
            "sequence_slots": request.sequence_slots,
            "system_ram_reserve_bytes": request.system_ram_reserve_bytes,
            "gpu_vram_reserve_bytes": request.gpu_vram_reserve_bytes,
        },
        "requirements": {
            "weight_storage": weights,
            "kv_cache": kv,
            "known_resident_bytes_required": total_required,
            "known_resident_bytes_evidence": "estimated" if total_required is not None else "unknown",
        },
        "budgets": {
            "system_ram_usable_bytes": ram_usable,
            "single_gpu_vram_usable_bytes": gpu_usable,
            "combined_system_ram_and_single_gpu_bytes": total_available,
            "runtime_overhead_bytes": None,
            "runtime_overhead_evidence": "unknown",
        },
        "capacity_assessment": {
            "weights_only": weights_only,
            "weights_plus_kv_cache": full_resident,
            "memory_classification": memory_class,
            "native_memory_candidate": native_memory_candidate,
            "evidence": "estimated" if memory_class.startswith("estimated") or memory_class.startswith("exceeds") else "unknown",
        },
        "placement_envelope": {
            "mode": "capacity_only_not_layer_assignment",
            "gpu_first_weight_capacity_bytes": (
                max(0, gpu_usable - kv_bytes)
                if _is_int(gpu_usable) and _is_int(kv_bytes)
                else None
            ),
            "ram_capacity_bytes": ram_usable,
            "combined_resident_capacity_bytes": total_available,
            "exact_layer_or_expert_split": None,
            "backend_support": "unknown",
            "note": "This reports memory capacity only. An inference adapter must prove the supported layer/tensor placement and create the executable manifest.",
        },
        "execution_feasibility": {
            "status": "not_validated",
            "backend_compatibility": "unknown",
            "model_load_tested": False,
            "inference_tested": False,
            "performance_target_category": (
                "oversized_model_requested_profile_candidate_only"
                if target_applies is True
                else "no_fixed_floor_for_within_capacity_candidate"
                if target_applies is False
                else "not_assigned_unknown_capacity"
            ),
            "performance_goal_policy": performance_goal_policy,
            "tokens_per_second_prediction": None,
        },
        "warnings": warnings,
    }
