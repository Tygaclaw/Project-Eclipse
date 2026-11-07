"""Understandable execution profiles that resolve to explicit settings.

Intent labels are not performance promises. Each preset maps to concrete,
inspectable values, is validated against backend capabilities and the model's
declared context, and records the host snapshot it was created from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from typing import Any, Mapping

from eclipse.core.config import Settings
from .backends import BackendCapabilities, BackendUnsupported, backend_capabilities
from .placement import (
    PLACEMENT_INTENTS,
    STATUS_CPU_ONLY,
    STATUS_CPU_ONLY_NO_GPU,
    STATUS_GPU_FULL,
    STATUS_HYBRID,
    PlacementRequest,
    plan_placement,
    summarize_placement,
)

INTENTS = ("auto", "balanced", "fast", "quality", "custom")

_INTENT_DESCRIPTIONS = {
    "auto": "Choose a context and placement from the observed model and host facts.",
    "balanced": "A practical default for everyday chat and agent work.",
    "fast": "Shorter context and fewer tokens for quicker first responses.",
    "quality": "Use the full declared context when the host can afford it.",
    "custom": "Use the exact values you set; nothing is inferred.",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def intent_choices() -> list[dict[str, str]]:
    return [{"value": key, "label": key.title(), "description": _INTENT_DESCRIPTIONS[key]} for key in INTENTS]


@dataclass(frozen=True, slots=True)
class ProfileSpec:
    backend: str = "llamacpp_server"
    intent: str = "balanced"
    placement_mode: str = "auto"
    context_tokens: int = 8192
    gpu_layers: int = -1
    threads: int | None = None
    parallel_slots: int = 1
    kv_cache_dtype: str = "f16"
    temperature: float = 0.7
    max_tokens: int = 1024
    endpoint: str | None = None
    model_name: str | None = None
    binary: str | None = None
    extra_args: tuple[str, ...] = ()
    rationale: str = ""
    warnings: tuple[str, ...] = ()
    placement: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.intent not in INTENTS:
            raise ValueError(f"Unknown execution intent: {self.intent}")
        if self.placement_mode not in PLACEMENT_INTENTS:
            raise ValueError(f"Unknown placement mode: {self.placement_mode}")
        if self.context_tokens <= 0:
            raise ValueError("context_tokens must be positive")
        if self.gpu_layers < -1:
            raise ValueError("gpu_layers must be -1 or a non-negative integer")
        if self.parallel_slots < 1:
            raise ValueError("parallel_slots must be at least one")
        if not 0.0 <= float(self.temperature) <= 2.0:
            raise ValueError("temperature must be between 0 and 2")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        backend_capabilities(self.backend)

    def to_payload(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "intent": self.intent,
            "placement_mode": self.placement_mode,
            "context_tokens": int(self.context_tokens),
            "gpu_layers": int(self.gpu_layers),
            "threads": int(self.threads) if self.threads else None,
            "parallel_slots": int(self.parallel_slots),
            "kv_cache_dtype": self.kv_cache_dtype,
            "temperature": float(self.temperature),
            "max_tokens": int(self.max_tokens),
            "endpoint": self.endpoint,
            "model_name": self.model_name,
            "binary": self.binary,
            "extra_args": list(self.extra_args),
            "rationale": self.rationale,
            "warnings": list(self.warnings),
            "placement": self.placement,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ProfileSpec":
        return cls(
            backend=str(payload.get("backend") or "llamacpp_server"),
            intent=str(payload.get("intent") or "balanced"),
            placement_mode=str(payload.get("placement_mode") or "auto"),
            context_tokens=int(payload.get("context_tokens") or 8192),
            gpu_layers=int(payload.get("gpu_layers", -1)),
            threads=int(payload["threads"]) if payload.get("threads") else None,
            parallel_slots=int(payload.get("parallel_slots") or 1),
            kv_cache_dtype=str(payload.get("kv_cache_dtype") or "f16"),
            temperature=float(payload.get("temperature", 0.7)),
            max_tokens=int(payload.get("max_tokens") or 1024),
            endpoint=payload.get("endpoint") or None,
            model_name=payload.get("model_name") or None,
            binary=payload.get("binary") or None,
            extra_args=tuple(str(item) for item in payload.get("extra_args") or ()),
            rationale=str(payload.get("rationale") or ""),
            warnings=tuple(str(item) for item in payload.get("warnings") or ()),
            placement=(
                dict(payload["placement"])
                if isinstance(payload.get("placement"), Mapping)
                else None
            ),
        )


def _declared_context(atlas: Mapping[str, Any]) -> int | None:
    details = atlas.get("architecture", {}).get("details") if isinstance(atlas, Mapping) else None
    if isinstance(details, Mapping):
        fact = details.get("context_length")
        if isinstance(fact, Mapping) and isinstance(fact.get("value"), int):
            value = fact["value"]
            if value > 0:
                return int(value)
    return None


def _architecture(atlas: Mapping[str, Any]) -> str | None:
    if not isinstance(atlas, Mapping):
        return None
    architecture = atlas.get("architecture")
    if isinstance(architecture, Mapping) and isinstance(architecture.get("architecture"), str):
        return architecture["architecture"]
    return None


def validate_profile(
    spec: ProfileSpec,
    *,
    atlas: Mapping[str, Any] | None = None,
    capabilities: BackendCapabilities | None = None,
) -> list[str]:
    """Return warnings; raise on a genuinely unsupported request."""

    backend = capabilities or backend_capabilities(spec.backend)
    if atlas is not None:
        source_kind = atlas.get("source_kind")
        if spec.backend == "llamacpp_server" and source_kind != "gguf":
            raise BackendUnsupported(
                "The managed llama.cpp adapter supports GGUF models; inspect a "
                "GGUF build or attach an external server for other formats."
            )
        architecture = _architecture(atlas)
        if architecture and not backend.supports_architecture(architecture):
            raise BackendUnsupported(
                f"{backend.display_name} does not declare support for architecture '{architecture}'"
            )
    if backend.kv_cache_dtypes and spec.kv_cache_dtype not in backend.kv_cache_dtypes:
        raise BackendUnsupported(
            f"KV-cache type '{spec.kv_cache_dtype}' is not supported by {backend.display_name}"
        )
    warnings: list[str] = []
    declared = _declared_context(atlas) if atlas else None
    if declared is not None and spec.context_tokens > declared:
        warnings.append(
            f"Requested context {spec.context_tokens:,} exceeds the model-declared "
            f"{declared:,}; the backend may reject or clamp it."
        )
    if spec.parallel_slots > 1 and not backend.parallel_slots:
        warnings.append("This backend does not expose parallel slots; the setting is ignored.")
    if spec.backend == "openai_compatible" and not spec.endpoint:
        raise BackendUnsupported("An attach profile needs an endpoint URL")
    return warnings


def _cpu_count() -> int:
    return max(1, min(16, os.cpu_count() or 4))


def resolve_profile(
    *,
    intent: str = "balanced",
    backend: str = "llamacpp_server",
    atlas: Mapping[str, Any] | None = None,
    host: Mapping[str, Any] | None = None,
    settings: Settings | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> ProfileSpec:
    """Resolve an intent into explicit settings with a written rationale."""

    overrides = dict(overrides or {})
    if intent not in INTENTS:
        raise ValueError(f"Unknown execution intent: {intent}")
    capabilities = backend_capabilities(backend)
    declared = _declared_context(atlas) if atlas else None
    host = host or {}
    cpu_threads = _cpu_count()
    rationale: list[str] = []
    warnings: list[str] = []

    available_ram = None
    memory = host.get("system_memory")
    if isinstance(memory, Mapping) and isinstance(memory.get("available_bytes"), int):
        available_ram = memory["available_bytes"]

    if intent == "auto":
        desired = declared or 8192
        if available_ram is not None and available_ram < 12 * 1024**3:
            desired = min(desired, 4096)
            rationale.append("Auto chose a shorter context because available RAM is under 12 GiB.")
        else:
            desired = min(desired, 16384)
            rationale.append("Auto chose a context bounded by the declared limit and a 16K ceiling.")
        resolved_intent = "balanced"
        context = desired
        max_tokens = 1024
        parallel = 1
        temperature = 0.7
    elif intent == "fast":
        context = min(declared or 4096, 4096)
        max_tokens = 512
        parallel = 2 if capabilities.parallel_slots else 1
        temperature = 0.6
        resolved_intent = "fast"
        rationale.append("Fast favors a 4K context, a shorter reply budget and two slots when supported.")
    elif intent == "quality":
        context = declared or 32768
        max_tokens = 2048
        parallel = 1
        temperature = 0.4
        resolved_intent = "quality"
        rationale.append("Quality uses the model-declared context and a longer reply budget.")
    elif intent == "custom":
        context = int(overrides.get("context_tokens") or 8192)
        max_tokens = int(overrides.get("max_tokens") or 1024)
        parallel = int(overrides.get("parallel_slots") or 1)
        temperature = float(overrides.get("temperature", 0.7))
        resolved_intent = "custom"
        rationale.append("Custom uses the values exactly as entered.")
    else:
        context = min(declared or 8192, 8192)
        max_tokens = 1024
        parallel = 1
        temperature = 0.7
        resolved_intent = "balanced"
        rationale.append("Balanced uses an 8K context unless the model declares less.")

    if "context_tokens" in overrides:
        context = int(overrides["context_tokens"])
        rationale.append(
            f"The explicit {context:,}-token context override was used instead of the preset."
        )

    if settings is not None:
        configured_context = settings.get("max_context_tokens")
        if isinstance(configured_context, int) and configured_context > 0:
            if context > configured_context:
                context = configured_context
                rationale.append(
                    f"Context capped at the configured {configured_context:,}-token ceiling."
                )

    if declared is None:
        warnings.append("The model does not declare a context length; the requested value is unverified.")
    elif context > declared:
        warnings.append(
            f"Requested context {context:,} exceeds the declared {declared:,}."
        )

    threads = overrides.get("threads", None)
    if threads is None:
        threads = cpu_threads if backend == "llamacpp_server" else None
    kv_cache_dtype = str(overrides.get("kv_cache_dtype") or "f16")
    if kv_cache_dtype not in capabilities.kv_cache_dtypes and capabilities.kv_cache_dtypes:
        warnings.append(
            f"KV-cache type '{kv_cache_dtype}' is not declared by this backend; using f16."
        )
        kv_cache_dtype = capabilities.kv_cache_dtypes[0]

    placement_mode = str(overrides.get("placement_mode") or "auto")
    if placement_mode not in PLACEMENT_INTENTS:
        raise ValueError(f"Unknown placement mode: {placement_mode}")
    placement_plan: dict[str, Any] | None = None
    gpu_layers = int(overrides.get("gpu_layers", -1))
    if backend == "openai_compatible":
        gpu_layers = 0
    elif "gpu_layers" not in overrides and atlas:
        # Resolve the executable layer split from observed facts instead of
        # trusting an "all layers" default that may not fit the host at all.
        try:
            placement_plan = plan_placement(
                atlas,
                host,
                PlacementRequest(
                    context_tokens=context,
                    kv_cache_dtype=kv_cache_dtype,
                    sequence_slots=max(1, parallel),
                    mode=placement_mode,
                ),
            )
        except ValueError:
            placement_plan = None
        assignment = (placement_plan or {}).get("assignment") or {}
        planned_layers = assignment.get("gpu_layers")
        status = (placement_plan or {}).get("status")
        if isinstance(planned_layers, int) and status in {
            STATUS_CPU_ONLY,
            STATUS_CPU_ONLY_NO_GPU,
            STATUS_GPU_FULL,
            STATUS_HYBRID,
        }:
            gpu_layers = planned_layers
            total_layers = assignment.get("total_layers")
            rationale.append(
                f"The placement planner selected {gpu_layers} of {total_layers} repeating "
                f"layers on the GPU ({status})."
            )
        else:
            warnings.append(
                "Placement could not be planned from the available model and host facts; "
                "the existing all-layers default is kept and remains unverified."
            )

    spec = ProfileSpec(
        backend=backend,
        intent=resolved_intent if intent != "custom" else "custom",
        placement_mode=placement_mode,
        context_tokens=context,
        gpu_layers=gpu_layers,
        threads=int(threads) if threads else None,
        parallel_slots=max(1, parallel),
        kv_cache_dtype=kv_cache_dtype,
        temperature=temperature,
        max_tokens=max_tokens,
        endpoint=overrides.get("endpoint") or (settings.get("runtime_endpoint") if settings and backend == "openai_compatible" else None),
        model_name=overrides.get("model_name"),
        binary=overrides.get("binary") or None,
        extra_args=tuple(str(item) for item in overrides.get("extra_args") or ()),
        rationale=" ".join(rationale),
        warnings=tuple(warnings),
        placement=summarize_placement(placement_plan),
    )
    validate_profile(spec, atlas=atlas, capabilities=capabilities)
    return spec


# -- saved profiles and last-known-good restore -------------------------

# Placement summaries are evidence about a load, not a setting. They are
# deliberately excluded from the matching signature so the same effective
# settings found on a different host still resolve to one saved profile.
_PROFILE_KEYS = (
    "backend",
    "intent",
    "placement_mode",
    "context_tokens",
    "gpu_layers",
    "threads",
    "parallel_slots",
    "kv_cache_dtype",
    "temperature",
    "max_tokens",
    "endpoint",
    "model_name",
    "binary",
    "extra_args",
)


def _profile_signature(payload: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    values: list[tuple[str, Any]] = []
    for key in _PROFILE_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            value = tuple(value)
        values.append((key, value))
    return tuple(values)


def find_matching_profile(store: Any, model_id: str, spec: ProfileSpec) -> dict[str, Any] | None:
    """Find the stored profile with the same effective settings."""

    target = _profile_signature(spec.to_payload())
    for record in store.list_profiles(model_id):
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
        if _profile_signature(payload) == target:
            return record
    return None


def save_profile(
    store: Any,
    spec: ProfileSpec,
    *,
    model_id: str,
    name: str | None = None,
    mark_good: bool = False,
) -> dict[str, Any]:
    """Persist a resolved profile once; mark it last-known-good when requested."""

    existing = find_matching_profile(store, model_id, spec)
    if existing is not None:
        return store.mark_last_known_good(existing) if mark_good else existing
    record = store.add_profile(
        name=name or f"{spec.intent.title()} profile",
        intent=spec.intent,
        payload=spec.to_payload(),
        model_id=model_id,
        last_known_good=mark_good,
    )
    return record


def last_known_good_profile(store: Any, model_id: str | None = None) -> dict[str, Any] | None:
    for record in store.list_profiles(model_id):
        if record.get("last_known_good"):
            return record
    return None


def restore_profile(store: Any, profile_id: str, *, atlas: Mapping[str, Any] | None = None) -> ProfileSpec:
    """Load a saved profile and validate it before it is applied."""

    record = store.get_profile(profile_id)
    if record is None:
        raise ValueError(f"No saved profile has id '{profile_id}'")
    spec = ProfileSpec.from_payload(record.get("payload") or {})
    validate_profile(spec, atlas=atlas)
    return spec
