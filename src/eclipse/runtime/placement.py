"""Executable CPU/GPU/hybrid placement planning for the managed backend.

The feasibility planner answers "can this model's weights and KV cache fit in
memory at all". This module goes one step further: it derives a concrete
llama.cpp repeating-layer offload count from the model facts in the atlas and
a host snapshot, and reports the exact command-line fragment that applies it.

Everything here is an estimate. The backend decides the real allocation and
ECLIPSE never reports a planned placement as measured or verified. When the
facts or the host readings needed for a decision are missing the plan says so
and declines to emit an executable layer count instead of guessing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

GiB = 1024**3
MiB = 1024**2

#: The only placement intents a user can request.
PLACEMENT_INTENTS = ("auto", "cpu", "gpu", "hybrid")

#: KV-cache element cost. llama.cpp quantizes the KV cache in 32-element
#: blocks, so q8_0 stores 32 elements in 34 bytes (2-byte scale + 32 values)
#: and q4_0 in 18 bytes (2-byte scale + 16 packed bytes). These are block
#: layouts, not measured allocations.
_KV_ELEMENT_BYTES: dict[str, tuple[float, str]] = {
    "f16": (2.0, "f16 KV elements are two bytes each."),
    "bf16": (2.0, "bf16 KV elements are two bytes each."),
    "f32": (4.0, "f32 KV elements are four bytes each."),
    "q8_0": (34 / 32, "q8_0 KV blocks store 32 elements in 34 bytes."),
    "q4_0": (18 / 32, "q4_0 KV blocks store 32 elements in 18 bytes."),
}

STATUS_UNKNOWN_MODEL = "unknown_missing_model_facts"
STATUS_UNKNOWN_HOST = "unknown_host_budget"
STATUS_CPU_ONLY = "planned_cpu_only"
STATUS_CPU_ONLY_NO_GPU = "planned_cpu_only_no_gpu_observed"
STATUS_GPU_FULL = "planned_gpu_full_offload"
STATUS_HYBRID = "planned_hybrid"
STATUS_EXCEEDS = "exceeds_known_budget"

_PLANNED_STATUSES = (STATUS_CPU_ONLY, STATUS_CPU_ONLY_NO_GPU, STATUS_GPU_FULL, STATUS_HYBRID)

_LAYER_ASSUMPTION = (
    "Per-layer cost is the complete checkpoint tensor storage divided by the "
    "repeating-layer count. Real layers differ (embeddings, output head, MoE "
    "experts and attention shapes are not uniform), so the backend-reported "
    "allocation remains the authority."
)


class PlacementError(ValueError):
    """Invalid placement planning input."""


@dataclass(frozen=True, slots=True)
class PlacementRequest:
    """User-adjustable inputs for one executable placement plan."""

    context_tokens: int | None = None
    kv_cache_dtype: str = "f16"
    sequence_slots: int = 1
    system_ram_reserve_bytes: int = 8 * GiB
    gpu_vram_reserve_bytes: int = 768 * MiB
    allocation_overhead_fraction: float = 0.05
    mode: str = "auto"
    max_gpu_layers: int | None = None

    def __post_init__(self) -> None:
        if self.context_tokens is not None and (
            isinstance(self.context_tokens, bool)
            or not isinstance(self.context_tokens, int)
            or self.context_tokens <= 0
        ):
            raise PlacementError("context_tokens must be a positive integer or None")
        if self.kv_cache_dtype not in _KV_ELEMENT_BYTES:
            raise PlacementError(
                "kv_cache_dtype must be one of: " + ", ".join(sorted(_KV_ELEMENT_BYTES))
            )
        if (
            isinstance(self.sequence_slots, bool)
            or not isinstance(self.sequence_slots, int)
            or self.sequence_slots <= 0
        ):
            raise PlacementError("sequence_slots must be a positive integer")
        for name in ("system_ram_reserve_bytes", "gpu_vram_reserve_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise PlacementError(f"{name} must be a non-negative integer")
        overhead = self.allocation_overhead_fraction
        if (
            isinstance(overhead, bool)
            or not isinstance(overhead, (int, float))
            or not 0.0 <= float(overhead) <= 0.5
        ):
            raise PlacementError("allocation_overhead_fraction must be between 0 and 0.5")
        if self.mode not in PLACEMENT_INTENTS:
            raise PlacementError(
                "mode must be one of: " + ", ".join(PLACEMENT_INTENTS)
            )
        if self.max_gpu_layers is not None and (
            isinstance(self.max_gpu_layers, bool)
            or not isinstance(self.max_gpu_layers, int)
            or self.max_gpu_layers < 0
        ):
            raise PlacementError("max_gpu_layers must be a non-negative integer or None")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _snapshot(host: Mapping[str, Any] | Any | None) -> Mapping[str, Any]:
    if host is None:
        return {}
    if hasattr(host, "to_dict"):
        payload = host.to_dict()
    else:
        payload = host
    if not isinstance(payload, Mapping):
        raise PlacementError("host must be a host snapshot or a mapping")
    return payload


def _details(atlas: Mapping[str, Any]) -> Mapping[str, Any]:
    architecture = atlas.get("architecture")
    if not isinstance(architecture, Mapping):
        return {}
    details = architecture.get("details")
    return details if isinstance(details, Mapping) else {}


def _fact(details: Mapping[str, Any], name: str) -> dict[str, Any]:
    fact = details.get(name)
    if isinstance(fact, Mapping):
        value = fact.get("value")
        if _is_int(value) and value > 0:
            return {
                "value": int(value),
                "evidence": fact.get("evidence") or "observed",
                "source": fact.get("source"),
            }
        return {"value": None, "evidence": "unknown", "source": fact.get("source")}
    return {"value": None, "evidence": "unknown", "source": None}


def _weight_facts(atlas: Mapping[str, Any]) -> dict[str, Any]:
    summary = atlas.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    value = summary.get("total_storage_bytes")
    complete = summary.get("total_storage_is_complete") is True
    evidence = summary.get("storage_evidence")
    usable = _is_int(value) and value > 0 and complete
    return {
        "bytes": int(value) if usable else None,
        "complete": complete,
        "evidence": evidence if evidence in {"observed", "derived"} else "unknown",
        "usable": usable,
    }


def _usable_ram(snapshot: Mapping[str, Any], reserve: int) -> dict[str, Any]:
    memory = snapshot.get("system_memory")
    memory = memory if isinstance(memory, Mapping) else {}
    available = memory.get("available_bytes")
    if not _is_int(available) or available < 0:
        return {
            "available_before_reserve_bytes": None,
            "reserve_bytes": reserve,
            "usable_bytes": None,
            "evidence": "unknown",
        }
    return {
        "available_before_reserve_bytes": int(available),
        "reserve_bytes": reserve,
        "usable_bytes": max(0, int(available) - reserve),
        "evidence": "observed",
    }


def _selected_gpu(snapshot: Mapping[str, Any], reserve: int) -> dict[str, Any]:
    raw = snapshot.get("gpus")
    gpus = [gpu for gpu in raw if isinstance(gpu, Mapping)] if isinstance(raw, list) else []
    observed = [
        gpu
        for gpu in gpus
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
        "memory_total_bytes": int(total) if _is_int(total) and total > 0 else None,
        "free_before_reserve_bytes": free,
        "reserve_bytes": reserve,
        "usable_bytes": max(0, free - reserve),
        "evidence": "observed",
        "selection": "Largest single GPU by observed free VRAM; VRAM pools are not aggregated.",
    }


def _kv_total(
    details: Mapping[str, Any],
    request: PlacementRequest,
) -> dict[str, Any]:
    declared_context = _fact(details, "context_length")["value"]
    context = request.context_tokens if request.context_tokens is not None else declared_context
    context_source = (
        "user_requested"
        if request.context_tokens is not None
        else "model_declared"
        if declared_context is not None
        else "unknown"
    )
    layers = _fact(details, "layer_count")["value"]
    kv_heads = _fact(details, "kv_heads")["value"]
    key_dim = _fact(details, "key_head_dimension")["value"]
    value_dim = _fact(details, "value_head_dimension")["value"]
    per_element, dtype_basis = _KV_ELEMENT_BYTES[request.kv_cache_dtype]
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
    base = {
        "dtype": request.kv_cache_dtype,
        "bytes_per_element": per_element,
        "dtype_basis": dtype_basis,
        "context_tokens": context,
        "context_source": context_source,
        "declared_context_limit_tokens": declared_context,
        "sequence_slots": request.sequence_slots,
        "formula": (
            "layers × context × KV heads × (key head dimension + value head "
            "dimension) × bytes per element × sequence slots"
        ),
        "assumes_full_attention_kv_on_every_layer": True,
    }
    if missing:
        return {
            **base,
            "bytes": None,
            "evidence": "unknown",
            "missing_architecture_facts": missing,
        }
    assert layers is not None and context is not None
    assert kv_heads is not None and key_dim is not None and value_dim is not None
    total = (
        layers
        * context
        * kv_heads
        * (key_dim + value_dim)
        * per_element
        * request.sequence_slots
    )
    return {
        **base,
        "bytes": int(math.ceil(total)),
        "evidence": "estimated",
        "requested_context_exceeds_declared_limit": (
            declared_context is not None and context > declared_context
        ),
    }


def _shortfall(required: int, available: int) -> dict[str, Any]:
    return {
        "required_bytes": required,
        "available_bytes": available,
        "shortfall_bytes": max(0, required - available),
    }


def plan_placement(
    atlas: Mapping[str, Any],
    host: Mapping[str, Any] | Any | None,
    request: PlacementRequest | None = None,
) -> dict[str, Any]:
    """Derive an executable CPU/GPU/hybrid layer assignment.

    The returned ``assignment.gpu_layers`` is either an explicit non-negative
    integer that can be passed to ``llama-server --n-gpu-layers`` or ``None``
    when the available facts do not justify a decision.
    """

    if not isinstance(atlas, Mapping):
        raise PlacementError("A model atlas mapping is required")
    request = request or PlacementRequest()
    snapshot = _snapshot(host)
    details = _details(atlas)
    layers_fact = _fact(details, "layer_count")
    layers = layers_fact["value"]
    weights = _weight_facts(atlas)
    kv = _kv_total(details, request)
    ram = _usable_ram(snapshot, request.system_ram_reserve_bytes)
    gpu = _selected_gpu(snapshot, request.gpu_vram_reserve_bytes)
    overhead = 1.0 + float(request.allocation_overhead_fraction)

    warnings: list[str] = [
        "Estimated placement only. ECLIPSE does not measure the real allocation here "
        "and does not know whether this backend build supports GPU offload.",
        "The backend remains the authority: a planned layer count is not a successful load "
        "and is not a tokens/second prediction.",
        "Only one GPU is planned (the largest observed free VRAM). Multi-GPU tensor "
        "splitting is not implemented.",
        "CPU-side process memory, tokenizer buffers, compute graph workspaces and "
        "non-repeating tensors kept on the CPU are not modelled.",
    ]
    if request.mode in {"gpu", "hybrid", "auto"} and gpu["evidence"] != "observed":
        warnings.append("No GPU free-VRAM reading was available, so GPU placement cannot be planned.")
    if kv["bytes"] is None:
        warnings.append(
            "KV-cache cost is unknown because one or more architecture facts are missing; "
            "no layer count is emitted."
        )
    if not weights["usable"]:
        warnings.append(
            "Complete checkpoint tensor storage is not available, so per-layer weight cost "
            "is unknown and no layer count is emitted."
        )
    if kv.get("requested_context_exceeds_declared_limit"):
        warnings.append(
            "The requested context exceeds the model-declared limit; the backend may clamp "
            "or reject it, which would change the real allocation."
        )
    if request.max_gpu_layers is not None:
        warnings.append(
            f"GPU offload is capped at {request.max_gpu_layers} layer(s) by the request."
        )

    base: dict[str, Any] = {
        "format": "eclipse_placement_plan",
        "placement_version": 1,
        "backend": "llamacpp_server",
        "model": {
            "source_kind": atlas.get("source_kind"),
            "source_name": atlas.get("source_name"),
            "architecture": (
                atlas.get("architecture", {}).get("architecture")
                if isinstance(atlas.get("architecture"), Mapping)
                else None
            ),
        },
        "request": {
            "mode": request.mode,
            "context_tokens": kv["context_tokens"],
            "context_source": kv["context_source"],
            "kv_cache_dtype": request.kv_cache_dtype,
            "sequence_slots": request.sequence_slots,
            "system_ram_reserve_bytes": request.system_ram_reserve_bytes,
            "gpu_vram_reserve_bytes": request.gpu_vram_reserve_bytes,
            "allocation_overhead_fraction": float(request.allocation_overhead_fraction),
            "max_gpu_layers": request.max_gpu_layers,
        },
        "input_evidence": {
            "layer_count": layers_fact,
            "weight_storage": {
                "bytes": weights["bytes"],
                "evidence": weights["evidence"] if weights["usable"] else "unknown",
                "complete": weights["complete"],
            },
            "kv_cache": {
                "bytes": kv["bytes"],
                "evidence": kv["evidence"],
                "missing_architecture_facts": kv.get("missing_architecture_facts"),
            },
        },
        "budgets": {
            "system_memory": ram,
            "selected_gpu": gpu,
            "allocation_overhead_fraction": float(request.allocation_overhead_fraction),
            "unmodelled_overhead_bytes": None,
            "unmodelled_overhead_evidence": "unknown",
        },
        "warnings": warnings,
        "runtime_verified": False,
    }

    per_layer: dict[str, Any] = {
        "weight_bytes": None,
        "kv_cache_bytes": None,
        "total_bytes": None,
        "assumption": _LAYER_ASSUMPTION,
        "uniform_average": True,
        "evidence": "unknown",
    }
    if weights["usable"] and kv["bytes"] is not None and layers:
        layer_weight = weights["bytes"] / layers
        layer_kv = kv["bytes"] / layers
        per_layer.update(
            {
                "weight_bytes": int(math.ceil(layer_weight)),
                "kv_cache_bytes": int(math.ceil(layer_kv)),
                "total_bytes": int(math.ceil(layer_weight + layer_kv)),
                "evidence": "derived",
            }
        )
    base["per_layer_estimate"] = per_layer

    if layers is None or not weights["usable"] or kv["bytes"] is None or per_layer["weight_bytes"] is None:
        return {
            **base,
            "status": STATUS_UNKNOWN_MODEL,
            "assignment": _unknown_assignment(layers),
            "executable": _no_executable("The model facts needed for a layer split are missing."),
        }

    assert layers > 0
    layer_weight = float(per_layer["weight_bytes"])
    layer_kv = float(per_layer["kv_cache_bytes"]) if per_layer["kv_cache_bytes"] else 0.0
    kv_total = int(kv["bytes"])
    weights_total = int(weights["bytes"])
    include_kv_on_gpu = True

    max_layers = layers if request.max_gpu_layers is None else min(layers, request.max_gpu_layers)

    def costs(n: int) -> tuple[int, int]:
        gpu_resident = n * (layer_weight + (layer_kv if include_kv_on_gpu else 0.0))
        cpu_resident = (
            (weights_total - n * layer_weight)
            + (kv_total - (n * layer_kv if include_kv_on_gpu else 0.0))
        )
        return (
            int(math.ceil(max(0.0, gpu_resident) * overhead)),
            int(math.ceil(max(0.0, cpu_resident) * overhead)),
        )

    vram_usable = gpu["usable_bytes"]
    ram_usable = ram["usable_bytes"]
    gpu_known = _is_int(vram_usable)
    ram_known = _is_int(ram_usable)

    def fits(n: int) -> tuple[bool, int, int]:
        gpu_bytes, cpu_bytes = costs(n)
        if not gpu_known or not ram_known:
            return False, gpu_bytes, cpu_bytes
        assert isinstance(vram_usable, int) and isinstance(ram_usable, int)
        return gpu_bytes <= vram_usable and cpu_bytes <= ram_usable, gpu_bytes, cpu_bytes

    effective_mode = request.mode

    def candidate(mode: str, n: int) -> dict[str, Any] | None:
        ok, gpu_bytes, cpu_bytes = fits(n)
        if not ok:
            return None
        return {
            "mode": mode,
            "gpu_layers": n,
            "cpu_layers": layers - n,
            "estimated_peak_vram_bytes": gpu_bytes,
            "estimated_peak_ram_bytes": cpu_bytes,
        }

    if request.mode == "cpu":
        _, cpu_bytes = costs(0)
        if not ram_known:
            return {
                **base,
                "status": STATUS_UNKNOWN_HOST,
                "assignment": _unknown_assignment(layers),
                "executable": _no_executable("Available system RAM was not observed."),
            }
        assert isinstance(ram_usable, int)
        if cpu_bytes > ram_usable:
            return {
                **base,
                "status": STATUS_EXCEEDS,
                "assignment": _assignment(
                    mode="cpu",
                    gpu_layers=None,
                    layers=layers,
                    gpu_bytes=0,
                    cpu_bytes=cpu_bytes,
                    vram_usable=vram_usable,
                    ram_usable=ram_usable,
                    fits=False,
                ),
                "shortfall": {"system_memory": _shortfall(cpu_bytes, ram_usable)},
                "executable": _no_executable(
                    "The model's estimated CPU-resident memory exceeds usable RAM."
                ),
            }
        return {
            **base,
            "status": STATUS_CPU_ONLY,
            "assignment": _assignment(
                mode="cpu",
                gpu_layers=0,
                layers=layers,
                gpu_bytes=0,
                cpu_bytes=cpu_bytes,
                vram_usable=vram_usable,
                ram_usable=ram_usable,
                fits=True,
            ),
            "executable": _executable(0, layers, gpu["device_name"]),
        }

    if not ram_known:
        return {
            **base,
            "status": STATUS_UNKNOWN_HOST,
            "assignment": _unknown_assignment(layers),
            "executable": _no_executable("Available system RAM was not observed."),
        }
    assert isinstance(ram_usable, int)

    gpu_present = gpu["evidence"] == "observed"
    if not gpu_present:
        if request.mode in {"gpu", "hybrid"}:
            return {
                **base,
                "status": STATUS_UNKNOWN_HOST,
                "assignment": _unknown_assignment(layers),
                "executable": _no_executable(
                    "GPU free VRAM was not observed, so a GPU layer split cannot be planned."
                ),
            }
        # Auto on a host with no observed GPU: an explicit CPU-only plan is
        # executable, unlike an "all layers" default that assumes a GPU.
        _, cpu_bytes = costs(0)
        if cpu_bytes > ram_usable:
            return {
                **base,
                "status": STATUS_EXCEEDS,
                "assignment": _assignment(
                    mode="cpu",
                    gpu_layers=None,
                    layers=layers,
                    gpu_bytes=0,
                    cpu_bytes=cpu_bytes,
                    vram_usable=vram_usable,
                    ram_usable=ram_usable,
                    fits=False,
                ),
                "shortfall": {"system_memory": _shortfall(cpu_bytes, ram_usable)},
                "executable": _no_executable(
                    "No GPU was observed and the estimated CPU-resident memory exceeds usable RAM."
                ),
            }
        warnings.append("No GPU was observed; auto selected CPU-only execution.")
        return {
            **base,
            "status": STATUS_CPU_ONLY_NO_GPU,
            "assignment": _assignment(
                mode="cpu",
                gpu_layers=0,
                layers=layers,
                gpu_bytes=0,
                cpu_bytes=cpu_bytes,
                vram_usable=vram_usable,
                ram_usable=ram_usable,
                fits=True,
            ),
            "executable": _executable(0, layers, None),
        }

    assert isinstance(vram_usable, int)

    if request.mode == "gpu":
        gpu_bytes, cpu_bytes = costs(max_layers)
        ok = gpu_bytes <= vram_usable and cpu_bytes <= ram_usable
        if ok and max_layers == layers:
            return {
                **base,
                "status": STATUS_GPU_FULL,
                "assignment": _assignment(
                    mode="gpu",
                    gpu_layers=layers,
                    layers=layers,
                    gpu_bytes=gpu_bytes,
                    cpu_bytes=cpu_bytes,
                    vram_usable=vram_usable,
                    ram_usable=ram_usable,
                    fits=True,
                ),
                "executable": _executable(layers, layers, gpu["device_name"]),
            }
        if ok and max_layers < layers:
            # A caller-requested cap prevented full offload; report the capped
            # hybrid plan honestly instead of claiming full offload.
            effective_mode = "hybrid"
            warnings.append(
                f"The requested GPU layer cap ({max_layers}) is below the model's "
                f"{layers} repeating layers, so this is a hybrid plan."
            )
            return {
                **base,
                "status": STATUS_HYBRID,
                "assignment": _assignment(
                    mode=effective_mode,
                    gpu_layers=max_layers,
                    layers=layers,
                    gpu_bytes=gpu_bytes,
                    cpu_bytes=cpu_bytes,
                    vram_usable=vram_usable,
                    ram_usable=ram_usable,
                    fits=True,
                ),
                "executable": _executable(max_layers, layers, gpu["device_name"]),
            }
        best = None
        for n in range(max_layers, 0, -1):
            found = candidate("hybrid", n)
            if found is not None:
                best = found
                break
        shortfalls = {
            "gpu_memory": _shortfall(gpu_bytes, vram_usable),
            "system_memory": _shortfall(cpu_bytes, ram_usable),
        }
        return {
            **base,
            "status": STATUS_EXCEEDS,
            "assignment": _assignment(
                mode="gpu",
                gpu_layers=None,
                layers=layers,
                gpu_bytes=gpu_bytes,
                cpu_bytes=cpu_bytes,
                vram_usable=vram_usable,
                ram_usable=ram_usable,
                fits=False,
            ),
            "shortfall": shortfalls,
            "fallback_assignment": best,
            "executable": _no_executable(
                "Full GPU offload does not fit the observed budget for this profile."
            ),
            "warnings": warnings
            + [
                "Full offload exceeds the observed budget; use hybrid placement or a smaller "
                "context, KV-cache type or quantized model."
            ],
        }

    # auto and hybrid: prefer the most GPU offload that satisfies both budgets.
    best_fit: dict[str, Any] | None = None
    for n in range(max_layers, -1, -1):
        found = candidate("gpu" if n == layers else "hybrid", n)
        if found is not None:
            best_fit = found
            break

    if best_fit is None:
        gpu_bytes, cpu_bytes = costs(0)
        return {
            **base,
            "status": STATUS_EXCEEDS,
            "assignment": _assignment(
                mode="cpu",
                gpu_layers=None,
                layers=layers,
                gpu_bytes=gpu_bytes,
                cpu_bytes=cpu_bytes,
                vram_usable=vram_usable,
                ram_usable=ram_usable,
                fits=False,
            ),
            "shortfall": {
                "gpu_memory": _shortfall(gpu_bytes, vram_usable),
                "system_memory": _shortfall(cpu_bytes, ram_usable),
            },
            "executable": _no_executable(
                "Even CPU-only residency exceeds the observed RAM budget for this profile."
            ),
            "warnings": warnings
            + [
                "No layer assignment fits the observed RAM and VRAM budget at this context. "
                "Reduce context, use a smaller quantization or a smaller model."
            ],
        }

    n = int(best_fit["gpu_layers"])
    status = STATUS_GPU_FULL if n == layers else STATUS_CPU_ONLY if n == 0 else STATUS_HYBRID
    return {
        **base,
        "status": status,
        "assignment": _assignment(
            mode=effective_mode if n > 0 else "cpu",
            gpu_layers=n,
            layers=layers,
            gpu_bytes=int(best_fit["estimated_peak_vram_bytes"]),
            cpu_bytes=int(best_fit["estimated_peak_ram_bytes"]),
            vram_usable=vram_usable,
            ram_usable=ram_usable,
            fits=True,
        ),
        "executable": _executable(n, layers, gpu["device_name"]),
    }


def _unknown_assignment(layers: int | None) -> dict[str, Any]:
    return {
        "mode": "unknown",
        "gpu_layers": None,
        "cpu_layers": None,
        "total_layers": layers,
        "gpu_layer_range": None,
        "estimated_peak_vram_bytes": None,
        "estimated_peak_ram_bytes": None,
        "vram_usable_bytes": None,
        "ram_usable_bytes": None,
        "fits_known_budget": None,
        "evidence": "unknown",
        "note": "No executable layer assignment was derived.",
    }


def _assignment(
    *,
    mode: str,
    gpu_layers: int | None,
    layers: int,
    gpu_bytes: int | None,
    cpu_bytes: int | None,
    vram_usable: Any,
    ram_usable: Any,
    fits: bool | None,
) -> dict[str, Any]:
    if gpu_layers is None:
        layer_range = None
    elif gpu_layers == 0:
        layer_range = "no repeating layers on the GPU"
    else:
        # llama.cpp offloads the last N repeating layers when given -ngl N.
        layer_range = f"last {gpu_layers} of {layers} repeating layers on the GPU"
    return {
        "mode": mode,
        "gpu_layers": gpu_layers,
        "cpu_layers": None if gpu_layers is None else layers - gpu_layers,
        "total_layers": layers,
        "gpu_layer_range": layer_range,
        "gpu_layer_order": "llama.cpp offloads the final N repeating layers for -ngl N.",
        "estimated_peak_vram_bytes": gpu_bytes,
        "estimated_peak_ram_bytes": cpu_bytes,
        "vram_usable_bytes": vram_usable if _is_int(vram_usable) else None,
        "ram_usable_bytes": ram_usable if _is_int(ram_usable) else None,
        "fits_known_budget": fits,
        "evidence": "estimated",
        "note": "Uniform per-layer estimate. The backend-reported allocation is authoritative.",
    }


def _executable(gpu_layers: int, layers: int, device_name: Any) -> dict[str, Any]:
    return {
        "argv_fragment": ["--n-gpu-layers", str(gpu_layers)],
        "applies_to": "llama-server launched by ECLIPSE",
        "gpu_layers": gpu_layers,
        "total_layers": layers,
        "device": device_name if isinstance(device_name, str) else None,
        "requires_gpu_build": gpu_layers > 0,
        "runtime_verified": False,
        "note": (
            "Apply with the execution profile. A successful launch and the backend's own "
            "reported placement are separate evidence this plan does not provide."
        ),
    }


def _no_executable(reason: str) -> dict[str, Any]:
    return {
        "argv_fragment": [],
        "applies_to": "llama-server launched by ECLIPSE",
        "gpu_layers": None,
        "total_layers": None,
        "device": None,
        "requires_gpu_build": None,
        "runtime_verified": False,
        "note": reason,
    }


def summarize_placement(plan: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Compact, persistable evidence for one plan."""

    if not isinstance(plan, Mapping):
        return None
    assignment = plan.get("assignment") if isinstance(plan.get("assignment"), Mapping) else {}
    return {
        "format": plan.get("format"),
        "status": plan.get("status"),
        "requested_mode": (plan.get("request") or {}).get("mode"),
        "effective_mode": assignment.get("mode"),
        "gpu_layers": assignment.get("gpu_layers"),
        "total_layers": assignment.get("total_layers"),
        "estimated_peak_vram_bytes": assignment.get("estimated_peak_vram_bytes"),
        "estimated_peak_ram_bytes": assignment.get("estimated_peak_ram_bytes"),
        "fits_known_budget": assignment.get("fits_known_budget"),
        "runtime_verified": False,
    }


def reconcile_placement(
    plan: Mapping[str, Any] | None,
    observed: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Compare a plan with measured resource samples without overclaiming.

    Only RAM/process samples and a peak GPU-memory reading are accepted. ECLIPSE
    does not currently sample per-process VRAM, so that dimension normally
    reports ``unavailable`` rather than a fabricated number.
    """

    observed = observed if isinstance(observed, Mapping) else {}
    summary = summarize_placement(plan)
    if summary is None:
        return {
            "format": "eclipse_placement_reconciliation",
            "version": 1,
            "verdict": "unavailable",
            "reason": "No placement plan was recorded for this load.",
            "runtime_verified": False,
        }

    peak_rss = observed.get("peak_process_resident_bytes")
    min_available = observed.get("minimum_host_available_bytes")
    peak_gpu = observed.get("peak_gpu_memory_used_bytes")
    estimated_ram = summary.get("estimated_peak_ram_bytes")
    estimated_vram = summary.get("estimated_peak_vram_bytes")

    ram: dict[str, Any] = {
        "estimated_peak_ram_bytes": estimated_ram,
        "observed_peak_process_resident_bytes": peak_rss if _is_int(peak_rss) else None,
        "observed_minimum_host_available_bytes": min_available if _is_int(min_available) else None,
        "verdict": "unavailable",
        "evidence": "unknown",
        "note": (
            "Process RSS is not the same as the planned allocation: llama.cpp may mmap "
            "weights and the operating system can share or reclaim pages."
        ),
    }
    if _is_int(estimated_ram) and _is_int(peak_rss) and estimated_ram > 0:
        tolerance = 1.10
        if peak_rss <= estimated_ram * tolerance:
            ram["verdict"] = "observed_within_estimate"
        else:
            ram["verdict"] = "observed_above_estimate"
            ram["excess_bytes"] = int(peak_rss - estimated_ram)
        ram["evidence"] = "observed"
        ram["observed_to_estimate_ratio"] = round(peak_rss / estimated_ram, 3)

    vram: dict[str, Any] = {
        "estimated_peak_vram_bytes": estimated_vram,
        "observed_peak_gpu_memory_used_bytes": peak_gpu if _is_int(peak_gpu) else None,
        "verdict": "unavailable",
        "evidence": "unknown",
        "note": (
            "ECLIPSE does not sample per-process GPU memory. Reconcile against the backend "
            "log, llama.cpp server output or an external GPU monitor."
        ),
    }
    if _is_int(estimated_vram) and _is_int(peak_gpu) and estimated_vram > 0:
        vram["verdict"] = (
            "observed_within_estimate"
            if peak_gpu <= estimated_vram * 1.10
            else "observed_above_estimate"
        )
        vram["evidence"] = "observed"
        vram["observed_to_estimate_ratio"] = round(peak_gpu / estimated_vram, 3)

    dimensions = (ram, vram)
    observed_dimensions = [item for item in dimensions if item["evidence"] == "observed"]
    if not observed_dimensions:
        verdict = "unavailable"
    elif any(item["verdict"] == "observed_above_estimate" for item in dimensions):
        verdict = "measured_above_estimate"
    else:
        verdict = "measured_no_larger_than_estimate"

    return {
        "format": "eclipse_placement_reconciliation",
        "version": 1,
        "verdict": verdict,
        "plan": summary,
        "dimensions": {"system_memory": ram, "gpu_memory": vram},
        "sample_source": observed.get("source") or "runtime resource sampler",
        "sample_count": observed.get("sample_count"),
        "runtime_verified": False,
        "note": (
            "This compares a recorded estimate with observed samples. It does not prove the "
            "backend accepted the planned layer count or that GPU inference ran."
        ),
    }
