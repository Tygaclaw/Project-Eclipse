"""Inference backend capability contracts and the static support matrix.

ECLIPSE does not implement its own kernels. It orchestrates maintained
backends through adapters, and every adapter declares exactly what it can do so
the UI never shows an unsupported control as if it worked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


class BackendError(Exception):
    """Base class for expected backend failures."""


class BackendUnavailable(BackendError):
    """The backend binary or endpoint is not available."""


class BackendUnsupported(BackendError):
    """The backend cannot support the requested model or setting."""


@dataclass(frozen=True, slots=True)
class BackendCapabilities:
    key: str
    display_name: str
    connection_modes: tuple[str, ...]
    formats: tuple[str, ...]
    architectures: tuple[str, ...] | None
    quantizations: tuple[str, ...] | None
    devices: tuple[str, ...]
    placement_modes: tuple[str, ...]
    streaming: bool
    tool_calling: bool
    context_control: bool
    kv_cache_dtypes: tuple[str, ...]
    parallel_slots: bool
    telemetry: tuple[str, ...]
    ownership: str
    notes: str = ""
    verified_against: str = ""

    def supports_format(self, source_kind: str) -> bool:
        return source_kind in self.formats

    def supports_architecture(self, architecture: str | None) -> bool:
        if self.architectures is None or not architecture:
            return True
        return architecture.lower() in {item.lower() for item in self.architectures}

    def supports_device(self, device: str) -> bool:
        return device in self.devices

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "connection_modes": list(self.connection_modes),
            "formats": list(self.formats),
            "architectures": list(self.architectures) if self.architectures else None,
            "quantizations": list(self.quantizations) if self.quantizations else None,
            "devices": list(self.devices),
            "placement_modes": list(self.placement_modes),
            "streaming": self.streaming,
            "tool_calling": self.tool_calling,
            "context_control": self.context_control,
            "kv_cache_dtypes": list(self.kv_cache_dtypes),
            "parallel_slots": self.parallel_slots,
            "telemetry": list(self.telemetry),
            "ownership": self.ownership,
            "notes": self.notes,
            "verified_against": self.verified_against,
        }


GGML_QUANTIZATIONS = (
    "F32",
    "F16",
    "BF16",
    "Q2_K",
    "Q3_K_S",
    "Q3_K_M",
    "Q3_K_L",
    "Q4_0",
    "Q4_1",
    "Q4_K_S",
    "Q4_K_M",
    "Q5_0",
    "Q5_1",
    "Q5_K_S",
    "Q5_K_M",
    "Q6_K",
    "Q8_0",
    "IQ4_NL",
    "IQ4_XS",
)

LLAMA_ARCHITECTURES = (
    "llama",
    "qwen2",
    "qwen2moe",
    "qwen2vl",
    "qwen3",
    "qwen3moe",
    "mistral",
    "mixtral",
    "gemma",
    "gemma2",
    "gemma3",
    "phi3",
    "phi4",
    "deepseek2",
    "deepseek3",
    "gpt2",
    "gptneox",
    "falcon",
    "mamba",
    "rwkv",
    "stablelm",
    "starcoder2",
    "command-r",
    "olmo",
    "internlm2",
    "minicpm",
)

LLAMA_CPP_CAPABILITIES = BackendCapabilities(
    key="llamacpp_server",
    display_name="llama.cpp server (managed process)",
    connection_modes=("managed_process",),
    formats=("gguf",),
    architectures=LLAMA_ARCHITECTURES,
    quantizations=GGML_QUANTIZATIONS,
    devices=("cpu", "cuda", "vulkan", "metal", "rocm"),
    placement_modes=("cpu", "gpu", "hybrid"),
    streaming=True,
    tool_calling=True,
    context_control=True,
    kv_cache_dtypes=("f16", "bf16", "q8_0", "q4_0"),
    parallel_slots=True,
    telemetry=("stream_timing", "process_resources", "host_memory", "gpu_memory"),
    ownership="eclipse",
    notes=(
        "Requires the llama-server executable from a llama.cpp build. Device "
        "support depends on how that build was compiled; ECLIPSE does not "
        "recompile or reconfigure an existing installation."
    ),
    verified_against="llama.cpp OpenAI-compatible /v1/chat/completions contract",
)

OPENAI_COMPATIBLE_CAPABILITIES = BackendCapabilities(
    key="openai_compatible",
    display_name="OpenAI-compatible endpoint (attach)",
    connection_modes=("attach",),
    formats=("gguf", "safetensors", "huggingface_folder", "remote"),
    architectures=None,
    quantizations=None,
    devices=("remote", "cpu", "cuda", "vulkan", "metal", "rocm"),
    placement_modes=("remote",),
    streaming=True,
    tool_calling=True,
    context_control=False,
    kv_cache_dtypes=(),
    parallel_slots=False,
    telemetry=("stream_timing",),
    ownership="external",
    notes=(
        "Connects to an already-running OpenAI-compatible server such as an "
        "existing llama.cpp, Ollama, LM Studio or hosted endpoint. ECLIPSE does "
        "not start, stop or reconfigure that server."
    ),
    verified_against="OpenAI chat-completions streaming contract",
)

SUPPORT_MATRIX: tuple[BackendCapabilities, ...] = (
    LLAMA_CPP_CAPABILITIES,
    OPENAI_COMPATIBLE_CAPABILITIES,
)


def backend_capabilities(key: str) -> BackendCapabilities:
    for backend in SUPPORT_MATRIX:
        if backend.key == key:
            return backend
    raise BackendUnsupported(f"Unknown inference backend: {key}")


def support_matrix_report() -> dict[str, Any]:
    return {
        "format": "eclipse_backend_support_matrix",
        "version": 2,
        "backends": [backend.to_dict() for backend in SUPPORT_MATRIX],
        "policy": (
            "A backend is only offered for a model when its declared format and "
            "architecture are supported. Actual loading is verified by the "
            "runtime; a static support claim is not a successful load."
        ),
    }


# Evidence-labelled statuses for the model-specific compatibility report.
STATUS_DECLARED_SUPPORTED = "declared_supported"
STATUS_UNSUPPORTED = "unsupported"
STATUS_UNKNOWN = "unknown"
STATUS_HARDWARE_PRESENT_UNVALIDATED = "hardware_present_backend_unvalidated"
PLACEMENT_MODES = ("cpu", "gpu", "hybrid", "remote")
CONTROL_NAMES = (
    "context_tokens",
    "gpu_layers",
    "threads",
    "parallel_slots",
    "kv_cache_dtype",
    "temperature",
    "max_tokens",
    "extra_args",
)


def _host_snapshot(host: Mapping[str, Any] | Any | None) -> Mapping[str, Any] | None:
    if host is None:
        return None
    if hasattr(host, "to_dict"):
        return host.to_dict()  # type: ignore[no-any-return]
    if not isinstance(host, Mapping):
        raise BackendError("host must be a HostSnapshot, a mapping or None")
    return host


def _model_facts(atlas: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(atlas, Mapping):
        raise BackendError("A model atlas mapping is required")
    source_kind = atlas.get("source_kind")
    architecture = None
    architecture_container = atlas.get("architecture")
    if isinstance(architecture_container, Mapping):
        value = architecture_container.get("architecture")
        if isinstance(value, str) and value.strip():
            architecture = value.strip().lower()
    observed_types: set[str] = set()
    summary = atlas.get("summary")
    if isinstance(summary, Mapping):
        distribution = summary.get("distribution")
        if isinstance(distribution, Mapping):
            counts = distribution.get("counts")
            if isinstance(counts, Mapping):
                for key in counts:
                    if isinstance(key, str) and key.strip():
                        observed_types.add(key.strip().upper())
    return {
        "source_kind": source_kind if isinstance(source_kind, str) else None,
        "architecture": architecture,
        "quantization_types": sorted(observed_types) or None,
    }


def _dimension(status: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, "reason": reason, **extra}


def _format_dimension(source_kind: str | None, capabilities: BackendCapabilities) -> dict[str, Any]:
    declared = list(capabilities.formats)
    if source_kind is None:
        return _dimension(STATUS_UNKNOWN, "The model source format was not identified.", model_format=None, declared_formats=declared)
    if source_kind in capabilities.formats:
        return _dimension(STATUS_DECLARED_SUPPORTED, "The backend declares this model format.", model_format=source_kind, declared_formats=declared)
    return _dimension(STATUS_UNSUPPORTED, "The backend does not declare this model format.", model_format=source_kind, declared_formats=declared)


def _architecture_dimension(architecture: str | None, capabilities: BackendCapabilities) -> dict[str, Any]:
    declared = sorted(capabilities.architectures) if capabilities.architectures is not None else None
    if architecture is None:
        return _dimension(STATUS_UNKNOWN, "The model architecture was not declared by the atlas.", architecture=None, declared_architectures=declared)
    if capabilities.architectures is None:
        return _dimension(STATUS_UNKNOWN, "The backend did not declare an architecture list.", architecture=architecture, declared_architectures=None)
    if architecture in {item.lower() for item in capabilities.architectures}:
        return _dimension(STATUS_DECLARED_SUPPORTED, "The backend declares this architecture.", architecture=architecture, declared_architectures=declared)
    return _dimension(STATUS_UNSUPPORTED, "The backend does not declare this architecture.", architecture=architecture, declared_architectures=declared)


def _quantization_dimension(observed: list[str] | None, capabilities: BackendCapabilities) -> dict[str, Any]:
    declared = sorted(capabilities.quantizations) if capabilities.quantizations is not None else None
    if not observed:
        return _dimension(STATUS_UNKNOWN, "No tensor types were observed in the atlas.", observed_types=None, declared_types=declared)
    if capabilities.quantizations is None:
        return _dimension(STATUS_UNKNOWN, "The backend did not declare a tensor-type list.", observed_types=observed, declared_types=None)
    supported = {item.upper() for item in capabilities.quantizations}
    unsupported = sorted(set(observed) - supported)
    if unsupported:
        return _dimension(STATUS_UNSUPPORTED, "The backend does not declare every observed tensor type.", observed_types=observed, declared_types=declared, unsupported_types=unsupported)
    return _dimension(STATUS_DECLARED_SUPPORTED, "The backend declares every observed tensor type.", observed_types=observed, declared_types=declared)


def _gpu_vendors(host: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(host, Mapping):
        return set()
    gpus = host.get("gpus")
    if not isinstance(gpus, list):
        return set()
    return {
        str(gpu.get("vendor")).strip().lower()
        for gpu in gpus
        if isinstance(gpu, Mapping) and gpu.get("vendor")
    }


def _devices_dimension(capabilities: BackendCapabilities, host: Mapping[str, Any] | None) -> dict[str, Any]:
    if "remote" in capabilities.devices:
        return _dimension(
            STATUS_DECLARED_SUPPORTED,
            "This backend connects to an endpoint that it does not own or place.",
            devices=[{"kind": "remote", "status": STATUS_DECLARED_SUPPORTED, "reason": "External endpoint connection."}],
        )
    if host is None:
        return _dimension(STATUS_UNKNOWN, "No host snapshot was supplied to confirm a device.", devices=[])
    vendors = _gpu_vendors(host)
    has_gpu = bool(vendors)
    devices: list[dict[str, Any]] = []
    if "cpu" in capabilities.devices:
        devices.append({"kind": "cpu", "status": STATUS_DECLARED_SUPPORTED, "reason": "CPU execution is declared."})
    for device in ("cuda", "rocm", "vulkan", "metal"):
        if device not in capabilities.devices:
            continue
        if device == "cuda":
            present = "nvidia" in vendors
            reason = "An NVIDIA GPU is present; backend kernel support is not runtime-verified." if present else "No NVIDIA GPU was observed."
        elif device == "rocm":
            present = "amd" in vendors
            reason = "An AMD GPU is present; backend kernel support is not runtime-verified." if present else "No AMD GPU was observed."
        elif device in {"vulkan", "metal"}:
            present = has_gpu
            reason = "A GPU is present; this discovery path does not confirm this API." if present else "No GPU was observed."
        else:  # pragma: no cover - kept for future device additions
            present = False
            reason = "Device support is unknown."
        status = STATUS_HARDWARE_PRESENT_UNVALIDATED if present else (STATUS_UNKNOWN if has_gpu else STATUS_UNSUPPORTED)
        devices.append({"kind": device, "status": status, "reason": reason})
    statuses = {item["status"] for item in devices}
    if STATUS_DECLARED_SUPPORTED in statuses:
        status = STATUS_DECLARED_SUPPORTED
        reason = "At least one declared device is present and usable by the contract."
    elif STATUS_HARDWARE_PRESENT_UNVALIDATED in statuses:
        status = STATUS_HARDWARE_PRESENT_UNVALIDATED
        reason = "GPU hardware is present but backend kernel support is not runtime-verified."
    elif STATUS_UNKNOWN in statuses:
        status = STATUS_UNKNOWN
        reason = "A declared device could not be confirmed or ruled out."
    else:
        status = STATUS_UNSUPPORTED
        reason = "No declared usable device was found."
    return _dimension(status, reason, devices=devices)


def _placement_dimension(mode: str | None, capabilities: BackendCapabilities) -> dict[str, Any] | None:
    if mode is None:
        return None
    requested = mode.strip().lower()
    declared = list(capabilities.placement_modes)
    if requested not in PLACEMENT_MODES:
        return _dimension(STATUS_UNKNOWN, "Unknown placement mode.", requested_mode=mode, declared_modes=declared)
    if requested in capabilities.placement_modes:
        return _dimension(STATUS_DECLARED_SUPPORTED, "The backend declares this placement mode.", requested_mode=requested, declared_modes=declared)
    return _dimension(STATUS_UNSUPPORTED, "The backend does not declare this placement mode.", requested_mode=requested, declared_modes=declared)


def evaluate_controls(
    capabilities: BackendCapabilities,
    requested_controls: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    requested = requested_controls or {}
    if not isinstance(requested, Mapping):
        raise BackendError("requested_controls must be a mapping")
    supported = {
        "context_tokens": capabilities.context_control,
        "gpu_layers": capabilities.key == "llamacpp_server",
        "threads": capabilities.key == "llamacpp_server",
        "parallel_slots": capabilities.parallel_slots,
        "kv_cache_dtype": bool(capabilities.kv_cache_dtypes),
        "temperature": True,
        "max_tokens": True,
        "extra_args": capabilities.key == "llamacpp_server",
    }
    result: dict[str, Any] = {}
    for raw_name, value in requested.items():
        name = str(raw_name).strip().lower()
        if name not in CONTROL_NAMES:
            result[name] = {"status": STATUS_UNKNOWN, "requested_value": value, "reason": "Unknown control name."}
        elif supported.get(name):
            result[name] = {"status": STATUS_DECLARED_SUPPORTED, "requested_value": value, "reason": "The backend declares this control."}
        else:
            result[name] = {"status": STATUS_UNSUPPORTED, "requested_value": value, "reason": "The backend does not declare this control."}
    return result


def evaluate_model_support(
    backend: str | BackendCapabilities,
    atlas: Mapping[str, Any],
    host: Mapping[str, Any] | Any | None = None,
    *,
    placement_mode: str | None = None,
    requested_controls: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare a model atlas and host snapshot against a backend declaration.

    This is a declaration comparison, not a successful-load claim. Runtime
    verification is always a separate, measured gate.
    """

    capabilities = backend if isinstance(backend, BackendCapabilities) else backend_capabilities(backend)
    facts = _model_facts(atlas)
    snapshot = _host_snapshot(host)
    dimensions = {
        "format": _format_dimension(facts["source_kind"], capabilities),
        "architecture": _architecture_dimension(facts["architecture"], capabilities),
        "quantization": _quantization_dimension(facts["quantization_types"], capabilities),
        "devices": _devices_dimension(capabilities, snapshot),
        "placement": _placement_dimension(placement_mode, capabilities),
    }
    controls = evaluate_controls(capabilities, requested_controls)
    statuses = [item["status"] for item in dimensions.values() if item]
    if STATUS_UNSUPPORTED in statuses:
        overall = "unsupported"
    elif STATUS_UNKNOWN in statuses or STATUS_HARDWARE_PRESENT_UNVALIDATED in statuses:
        overall = "unknown"
    else:
        overall = "declared_compatible_not_runtime_verified"
    return {
        "format": "eclipse_runtime_support",
        "version": 2,
        "backend": capabilities.to_dict(),
        "model": facts,
        "dimensions": dimensions,
        "controls": controls,
        "overall_status": overall,
        "runtime_verified": False,
        "warnings": [
            "Static declaration comparison only. It does not prove model loading, operator support or generation performance.",
            "A declared-supported result means the adapter lists the capability; runtime verification is separate.",
        ],
    }
