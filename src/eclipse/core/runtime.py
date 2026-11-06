"""Inference backend capability contract and evidence-labelled support matrix.

An inference backend adapter (for example a future llama.cpp adapter) declares
what it supports through :class:`BackendCapabilities`. ECLIPSE then compares a
concrete Model Atlas and host snapshot against that declaration and returns a
static support matrix.

This module never launches a backend, loads weights or proves runtime behaviour.
A support result is a contract comparison, not a claim that a model will load,
generate, or run at a particular speed. ``runtime_verified`` is always
``False`` here; runtime evidence belongs to the lifecycle milestone that
actually starts a backend. Unsupported and unknown facts are reported as such
rather than guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping

RUNTIME_CONTRACT_VERSION = 1

MODEL_FORMATS = frozenset({"gguf", "safetensors", "huggingface_folder"})
_SOURCE_KIND_TO_FORMAT = {
    "gguf": "gguf",
    "safetensors": "safetensors",
    "huggingface_folder": "huggingface_folder",
}

DEVICE_KINDS = frozenset({"cpu", "gpu"})
DEVICE_APIS = frozenset({"cpu", "cuda", "vulkan", "rocm", "metal", "sycl"})
PLACEMENT_MODES = frozenset({"cpu_only", "gpu_offload", "hybrid", "automatic"})
INTEGRATION_STATUSES = frozenset({"not_integrated", "integrated"})
EVIDENCE_VALUES = frozenset({"declared", "published", "measured", "unknown"})

CONTROL_NAMES = frozenset(
    {
        "context_length",
        "batch_size",
        "parallel_sequences",
        "gpu_layer_offload",
        "kv_cache_dtype",
        "kv_cache_device",
        "cpu_threads",
        "flash_attention",
        "memory_map",
        "expert_offload",
        "weight_prefetch",
    }
)

TELEMETRY_NAMES = frozenset(
    {
        "process_state",
        "time_to_first_token",
        "prompt_processing",
        "generation_rate",
        "ram_usage",
        "vram_usage",
        "cpu_usage",
        "kv_cache_bytes",
        "loaded_gpu_layers",
    }
)

# Declared-compatible for a static check; independent runtime proof is separate.
STATUS_DECLARED_SUPPORTED = "declared_supported"
STATUS_UNSUPPORTED = "unsupported"
STATUS_UNKNOWN = "unknown"
_HARDWARE_PRESENT_UNVALIDATED = "hardware_present_backend_unvalidated"


class RuntimeContractError(ValueError):
    """The capability declaration or support-matrix input is invalid."""


def _require_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise RuntimeContractError(f"{name} must be a boolean")
    return value


def _require_evidence(value: Any, name: str) -> str:
    if not isinstance(value, str) or value.strip().lower() not in EVIDENCE_VALUES:
        raise RuntimeContractError(
            f"{name} must be one of: " + ", ".join(sorted(EVIDENCE_VALUES))
        )
    return value.strip().lower()


def _normalize_tokens(values: Any, name: str) -> frozenset[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple, set, frozenset)):
        raise RuntimeContractError(f"{name} must be a list of non-empty strings")
    tokens: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise RuntimeContractError(f"{name} must contain non-empty strings")
        tokens.add(value.strip().lower())
    return frozenset(tokens)


@dataclass(frozen=True, slots=True)
class DeviceSupport:
    """One CPU or GPU execution device an adapter declares it can use."""

    kind: str
    api: str
    evidence: str = "declared"
    notes: str | None = None

    def __post_init__(self) -> None:
        kind = str(self.kind).strip().lower()
        api = str(self.api).strip().lower()
        if kind not in DEVICE_KINDS:
            raise RuntimeContractError(f"device kind must be one of: {', '.join(sorted(DEVICE_KINDS))}")
        if api not in DEVICE_APIS:
            raise RuntimeContractError(f"device api must be one of: {', '.join(sorted(DEVICE_APIS))}")
        if kind == "cpu" and api != "cpu":
            raise RuntimeContractError("a cpu device must use the cpu api")
        if kind == "gpu" and api == "cpu":
            raise RuntimeContractError("a gpu device cannot use the cpu api")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "api", api)
        object.__setattr__(self, "evidence", _require_evidence(self.evidence, "device evidence"))
        if self.notes is not None:
            object.__setattr__(self, "notes", str(self.notes))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "api": self.api,
            "evidence": self.evidence,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DeviceSupport":
        if not isinstance(data, Mapping):
            raise RuntimeContractError("each device must be an object")
        return cls(
            kind=data.get("kind"),
            api=data.get("api"),
            evidence=data.get("evidence", "declared"),
            notes=data.get("notes"),
        )


@dataclass(frozen=True, slots=True)
class ControlSupport:
    """Whether an adapter declares support for one runtime control."""

    supported: bool = True
    requires_restart: bool = False
    evidence: str = "declared"
    notes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "supported", _require_bool(self.supported, "control supported"))
        object.__setattr__(
            self, "requires_restart", _require_bool(self.requires_restart, "control requires_restart")
        )
        object.__setattr__(self, "evidence", _require_evidence(self.evidence, "control evidence"))
        if self.notes is not None:
            object.__setattr__(self, "notes", str(self.notes))

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported": self.supported,
            "requires_restart": self.requires_restart,
            "evidence": self.evidence,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ControlSupport":
        if isinstance(data, bool):
            return cls(supported=data)
        if not isinstance(data, Mapping):
            raise RuntimeContractError("each control must be a boolean or an object")
        return cls(
            supported=data.get("supported", True),
            requires_restart=data.get("requires_restart", False),
            evidence=data.get("evidence", "declared"),
            notes=data.get("notes"),
        )


@dataclass(frozen=True, slots=True)
class BackendCapabilities:
    """A backend adapter's declared, testable support envelope.

    ``architectures`` and ``quantization_types`` use ``None`` to mean "not
    declared", which the evaluator reports as unknown rather than as supported.
    An empty set means "declares support for none".
    """

    backend_id: str
    display_name: str
    integration_status: str = "not_integrated"
    evidence: str = "declared"
    backend_version: str | None = None
    model_formats: frozenset[str] = field(default_factory=lambda: frozenset({"gguf"}))
    architectures: frozenset[str] | None = None
    quantization_types: frozenset[str] | None = None
    devices: tuple[DeviceSupport, ...] = ()
    placement_modes: frozenset[str] = field(default_factory=lambda: frozenset({"cpu_only"}))
    controls: Mapping[str, ControlSupport] = field(default_factory=dict)
    telemetry: frozenset[str] = field(default_factory=frozenset)
    max_context_tokens: int | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        backend_id = self.backend_id.strip() if isinstance(self.backend_id, str) else self.backend_id
        display_name = (
            self.display_name.strip() if isinstance(self.display_name, str) else self.display_name
        )
        if not isinstance(backend_id, str) or not backend_id:
            raise RuntimeContractError("backend_id must be a non-empty string")
        if not isinstance(display_name, str) or not display_name:
            raise RuntimeContractError("display_name must be a non-empty string")
        if not isinstance(self.integration_status, str) or (
            self.integration_status.strip().lower() not in INTEGRATION_STATUSES
        ):
            raise RuntimeContractError(
                "integration_status must be one of: " + ", ".join(sorted(INTEGRATION_STATUSES))
            )
        formats = _normalize_tokens(self.model_formats, "model_formats")
        if not formats:
            raise RuntimeContractError("model_formats must declare at least one format")
        unknown_formats = formats - MODEL_FORMATS
        if unknown_formats:
            raise RuntimeContractError(
                "unknown model format(s): " + ", ".join(sorted(unknown_formats))
            )
        architectures = self.architectures
        if architectures is not None:
            architectures = _normalize_tokens(architectures, "architectures")
        quantization = self.quantization_types
        if quantization is not None:
            quantization = _normalize_tokens(quantization, "quantization_types")
        devices = tuple(self.devices)
        if not devices:
            raise RuntimeContractError("devices must declare at least one CPU or GPU device")
        controls = dict(self.controls)
        normalized_controls: dict[str, ControlSupport] = {}
        for name, control in controls.items():
            if not isinstance(name, str) or name.strip().lower() not in CONTROL_NAMES:
                raise RuntimeContractError(f"unknown control name: {name!r}")
            if not isinstance(control, ControlSupport):
                raise RuntimeContractError(f"control {name!r} must be a ControlSupport")
            normalized_controls[name.strip().lower()] = control
        placement = _normalize_tokens(self.placement_modes, "placement_modes")
        if not placement:
            raise RuntimeContractError("placement_modes must declare at least one mode")
        unknown_placement = placement - PLACEMENT_MODES
        if unknown_placement:
            raise RuntimeContractError(
                "unknown placement mode(s): " + ", ".join(sorted(unknown_placement))
            )
        telemetry = _normalize_tokens(self.telemetry, "telemetry")
        unknown_telemetry = telemetry - TELEMETRY_NAMES
        if unknown_telemetry:
            raise RuntimeContractError(
                "unknown telemetry name(s): " + ", ".join(sorted(unknown_telemetry))
            )
        if self.max_context_tokens is not None and (
            isinstance(self.max_context_tokens, bool)
            or not isinstance(self.max_context_tokens, int)
            or self.max_context_tokens <= 0
        ):
            raise RuntimeContractError("max_context_tokens must be a positive integer or None")
        if self.notes is not None:
            object.__setattr__(
                self, "notes", tuple(str(note) for note in self.notes)
            )

        object.__setattr__(self, "backend_id", backend_id)
        object.__setattr__(self, "display_name", display_name)
        object.__setattr__(self, "integration_status", self.integration_status.strip().lower())
        object.__setattr__(self, "evidence", _require_evidence(self.evidence, "backend evidence"))
        object.__setattr__(self, "model_formats", formats)
        object.__setattr__(self, "architectures", architectures)
        object.__setattr__(self, "quantization_types", quantization)
        object.__setattr__(self, "devices", devices)
        object.__setattr__(self, "placement_modes", placement)
        object.__setattr__(self, "controls", normalized_controls)
        object.__setattr__(self, "telemetry", telemetry)
        if self.backend_version is not None:
            object.__setattr__(self, "backend_version", str(self.backend_version))

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "display_name": self.display_name,
            "integration_status": self.integration_status,
            "evidence": self.evidence,
            "backend_version": self.backend_version,
            "model_formats": sorted(self.model_formats),
            "architectures": (
                sorted(self.architectures) if self.architectures is not None else None
            ),
            "quantization_types": (
                sorted(self.quantization_types) if self.quantization_types is not None else None
            ),
            "devices": [device.to_dict() for device in self.devices],
            "placement_modes": sorted(self.placement_modes),
            "controls": {
                name: self.controls[name].to_dict() for name in sorted(self.controls)
            },
            "telemetry": sorted(self.telemetry),
            "max_context_tokens": self.max_context_tokens,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BackendCapabilities":
        if not isinstance(data, Mapping):
            raise RuntimeContractError("a backend capability manifest must be a JSON object")
        allowed = {
            "backend_id",
            "display_name",
            "integration_status",
            "evidence",
            "backend_version",
            "model_formats",
            "architectures",
            "quantization_types",
            "devices",
            "placement_modes",
            "controls",
            "telemetry",
            "max_context_tokens",
            "notes",
        }
        unknown_keys = set(data) - allowed
        if unknown_keys:
            raise RuntimeContractError(
                "unknown capability field(s): " + ", ".join(sorted(str(key) for key in unknown_keys))
            )
        raw_devices = data.get("devices")
        if isinstance(raw_devices, (str, bytes)) or not isinstance(raw_devices, (list, tuple)):
            raise RuntimeContractError("devices must be a list of device objects")
        devices = tuple(DeviceSupport.from_dict(item) for item in raw_devices)
        raw_controls = data.get("controls", {})
        if not isinstance(raw_controls, Mapping):
            raise RuntimeContractError("controls must be an object keyed by control name")
        controls = {
            name: ControlSupport.from_dict(value) for name, value in raw_controls.items()
        }
        return cls(
            backend_id=data.get("backend_id"),
            display_name=data.get("display_name"),
            integration_status=data.get("integration_status", "not_integrated"),
            evidence=data.get("evidence", "declared"),
            backend_version=data.get("backend_version"),
            model_formats=data.get("model_formats", ["gguf"]),
            architectures=data.get("architectures"),
            quantization_types=data.get("quantization_types"),
            devices=devices,
            placement_modes=data.get("placement_modes", ["cpu_only"]),
            controls=controls,
            telemetry=data.get("telemetry", []),
            max_context_tokens=data.get("max_context_tokens"),
            notes=tuple(data.get("notes", []) or ()),
        )


def load_capabilities(path: str | Path) -> BackendCapabilities:
    """Load a backend capability manifest from a JSON file."""

    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeContractError(f"cannot read capability manifest: {type(exc).__name__}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeContractError("capability manifest is not valid JSON") from exc
    return BackendCapabilities.from_dict(data)


def _model_facts(atlas: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(atlas, Mapping) or atlas.get("format") != "eclipse_model_atlas":
        raise RuntimeContractError("A valid eclipse_model_atlas document is required")
    source_kind = atlas.get("source_kind")
    model_format = _SOURCE_KIND_TO_FORMAT.get(source_kind)
    architecture = None
    architecture_container = atlas.get("architecture")
    if isinstance(architecture_container, Mapping):
        value = architecture_container.get("architecture")
        if isinstance(value, str) and value.strip():
            architecture = value.strip().lower()
    quantization_types: set[str] = set()
    summary = atlas.get("summary")
    if isinstance(summary, Mapping):
        distribution = summary.get("distribution")
        if isinstance(distribution, Mapping):
            counts = distribution.get("counts")
            if isinstance(counts, Mapping):
                for key in counts:
                    if isinstance(key, str) and key.strip():
                        quantization_types.add(key.strip().lower())
    return {
        "source_kind": source_kind,
        "model_format": model_format,
        "architecture": architecture,
        "quantization_types": sorted(quantization_types) or None,
    }


def _format_dimension(model_format: str | None, capabilities: BackendCapabilities) -> dict[str, Any]:
    declared = sorted(capabilities.model_formats)
    if model_format is None:
        return {
            "status": STATUS_UNKNOWN,
            "model_format": None,
            "declared_formats": declared,
            "reason": "The model source format was not identified from the atlas.",
        }
    if model_format in capabilities.model_formats:
        return {
            "status": STATUS_DECLARED_SUPPORTED,
            "model_format": model_format,
            "declared_formats": declared,
            "reason": "The backend declares support for this model format.",
        }
    return {
        "status": STATUS_UNSUPPORTED,
        "model_format": model_format,
        "declared_formats": declared,
        "reason": "The backend does not declare support for this model format.",
    }


def _architecture_dimension(
    architecture: str | None, capabilities: BackendCapabilities
) -> dict[str, Any]:
    declared = sorted(capabilities.architectures) if capabilities.architectures is not None else None
    if architecture is None:
        return {
            "status": STATUS_UNKNOWN,
            "architecture": None,
            "declared_architectures": declared,
            "reason": "The model architecture was not declared by the atlas.",
        }
    if capabilities.architectures is None:
        return {
            "status": STATUS_UNKNOWN,
            "architecture": architecture,
            "declared_architectures": None,
            "reason": "The backend did not declare an architecture support list.",
        }
    if architecture in capabilities.architectures:
        return {
            "status": STATUS_DECLARED_SUPPORTED,
            "architecture": architecture,
            "declared_architectures": declared,
            "reason": "The backend declares support for this architecture.",
        }
    return {
        "status": STATUS_UNSUPPORTED,
        "architecture": architecture,
        "declared_architectures": declared,
        "reason": "The backend does not declare support for this architecture.",
    }


def _quantization_dimension(
    observed: list[str] | None, capabilities: BackendCapabilities
) -> dict[str, Any]:
    declared = (
        sorted(capabilities.quantization_types)
        if capabilities.quantization_types is not None
        else None
    )
    if not observed:
        return {
            "status": STATUS_UNKNOWN,
            "observed_types": None,
            "declared_types": declared,
            "reason": "No tensor types or dtypes were observed in the atlas.",
        }
    if capabilities.quantization_types is None:
        return {
            "status": STATUS_UNKNOWN,
            "observed_types": observed,
            "declared_types": None,
            "reason": "The backend did not declare a tensor-type support list.",
        }
    unsupported = sorted(set(observed) - capabilities.quantization_types)
    if unsupported:
        return {
            "status": STATUS_UNSUPPORTED,
            "observed_types": observed,
            "declared_types": declared,
            "unsupported_types": unsupported,
            "reason": "The backend does not declare support for all observed tensor types.",
        }
    return {
        "status": STATUS_DECLARED_SUPPORTED,
        "observed_types": observed,
        "declared_types": declared,
        "reason": "The backend declares support for every observed tensor type.",
    }


def _gpu_vendors(snapshot: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(snapshot, Mapping):
        return set()
    raw_gpus = snapshot.get("gpus")
    if not isinstance(raw_gpus, list):
        return set()
    vendors: set[str] = set()
    for gpu in raw_gpus:
        if isinstance(gpu, Mapping):
            vendor = gpu.get("vendor")
            if isinstance(vendor, str) and vendor.strip():
                vendors.add(vendor.strip().lower())
    return vendors


def _device_status(device: DeviceSupport, snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    if device.api == "cpu":
        matched = True
        status = STATUS_DECLARED_SUPPORTED
        reason = "CPU execution is present and declared by the backend."
    elif snapshot is None:
        matched = None
        status = STATUS_UNKNOWN
        reason = "No host snapshot was supplied to confirm the required device."
    else:
        vendors = _gpu_vendors(snapshot)
        has_gpu = bool(vendors)
        if device.api == "cuda":
            matched = "nvidia" in vendors
            status = (
                _HARDWARE_PRESENT_UNVALIDATED
                if matched
                else STATUS_UNSUPPORTED
            )
            reason = (
                "An NVIDIA GPU was observed; backend kernel support is not yet runtime-verified."
                if matched
                else "No NVIDIA GPU was observed by host discovery."
            )
        elif device.api == "rocm":
            matched = "amd" in vendors
            status = _HARDWARE_PRESENT_UNVALIDATED if matched else STATUS_UNSUPPORTED
            reason = (
                "An AMD GPU was observed; backend kernel support is not yet runtime-verified."
                if matched
                else "No AMD GPU was observed by host discovery."
            )
        elif device.api == "vulkan":
            matched = None
            status = STATUS_UNKNOWN if has_gpu else STATUS_UNSUPPORTED
            reason = (
                "A GPU is present, but this discovery path does not enumerate Vulkan devices."
                if has_gpu
                else "No GPU was observed by host discovery."
            )
        elif device.api == "sycl":
            matched = None
            status = STATUS_UNKNOWN if has_gpu else STATUS_UNSUPPORTED
            reason = (
                "A GPU is present, but this discovery path does not confirm SYCL/Intel devices."
                if has_gpu
                else "No GPU was observed by host discovery."
            )
        else:  # metal: not enumerated by the Windows-first discovery path.
            matched = None
            status = STATUS_UNKNOWN
            reason = "This discovery path does not enumerate Metal devices."
    return {
        "kind": device.kind,
        "api": device.api,
        "status": status,
        "hardware_matched": matched,
        "declared_evidence": device.evidence,
        "reason": reason,
        "notes": device.notes,
    }


def _devices_dimension(
    capabilities: BackendCapabilities, snapshot: Mapping[str, Any] | None
) -> dict[str, Any]:
    devices = [_device_status(device, snapshot) for device in capabilities.devices]
    statuses = {device["status"] for device in devices}
    if STATUS_DECLARED_SUPPORTED in statuses:
        status = STATUS_DECLARED_SUPPORTED
        reason = "At least one declared device is present and usable by the contract."
    elif _HARDWARE_PRESENT_UNVALIDATED in statuses:
        status = _HARDWARE_PRESENT_UNVALIDATED
        reason = "Required GPU hardware is present but backend kernel support is not runtime-verified."
    elif STATUS_UNKNOWN in statuses:
        status = STATUS_UNKNOWN
        reason = "No declared device could be confirmed or ruled out from the host snapshot."
    else:
        status = STATUS_UNSUPPORTED
        reason = "Host discovery did not find any hardware the backend declares it can use."
    return {"status": status, "reason": reason, "devices": devices}


def _placement_dimension(
    placement_mode: str | None, capabilities: BackendCapabilities
) -> dict[str, Any] | None:
    if placement_mode is None:
        return None
    mode = placement_mode.strip().lower()
    declared = sorted(capabilities.placement_modes)
    if mode not in PLACEMENT_MODES:
        return {
            "status": STATUS_UNKNOWN,
            "requested_mode": placement_mode,
            "declared_modes": declared,
            "reason": "Unknown placement mode.",
        }
    if mode in capabilities.placement_modes:
        return {
            "status": STATUS_DECLARED_SUPPORTED,
            "requested_mode": mode,
            "declared_modes": declared,
            "reason": "The backend declares this placement mode.",
        }
    return {
        "status": STATUS_UNSUPPORTED,
        "requested_mode": mode,
        "declared_modes": declared,
        "reason": "The backend does not declare this placement mode.",
    }


def evaluate_controls(
    capabilities: BackendCapabilities,
    requested_controls: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Report which requested controls the adapter declares it can honour."""

    requested = requested_controls or {}
    if not isinstance(requested, Mapping):
        raise RuntimeContractError("requested_controls must be a mapping of control name to value")
    result: dict[str, Any] = {}
    for raw_name, value in requested.items():
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise RuntimeContractError("requested control names must be non-empty strings")
        name = raw_name.strip().lower()
        if name not in CONTROL_NAMES:
            result[raw_name] = {
                "status": STATUS_UNKNOWN,
                "requested_value": value,
                "reason": "Unknown control name; it is not part of the runtime contract.",
            }
            continue
        control = capabilities.controls.get(name)
        if control is None:
            result[name] = {
                "status": STATUS_UNSUPPORTED,
                "requested_value": value,
                "reason": "The backend did not declare this control; do not present it as available.",
            }
            continue
        result[name] = {
            "status": STATUS_DECLARED_SUPPORTED if control.supported else STATUS_UNSUPPORTED,
            "requested_value": value,
            "requires_restart": control.requires_restart,
            "evidence": control.evidence,
            "notes": control.notes,
        }
    return result


def _overall_status(
    dimensions: Mapping[str, Mapping[str, Any] | None],
    integration_status: str,
) -> str:
    statuses = [dimension["status"] for dimension in dimensions.values() if dimension]
    if STATUS_UNSUPPORTED in statuses:
        return "unsupported"
    if integration_status != "integrated":
        return "not_integrated"
    if STATUS_UNKNOWN in statuses or _HARDWARE_PRESENT_UNVALIDATED in statuses:
        return "unknown"
    return "declared_compatible_not_runtime_verified"


def evaluate_model_support(
    capabilities: BackendCapabilities,
    atlas: Mapping[str, Any],
    host: Mapping[str, Any] | Any | None = None,
    *,
    placement_mode: str | None = None,
    requested_controls: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare a model atlas and host snapshot against a capability contract.

    The result is a declaration comparison. It never claims that a model loads
    or generates; ``runtime_verified`` stays ``False`` until a lifecycle
    milestone records real backend evidence.
    """

    if not isinstance(capabilities, BackendCapabilities):
        raise RuntimeContractError("capabilities must be a BackendCapabilities instance")
    facts = _model_facts(atlas)
    if host is not None and hasattr(host, "to_dict"):
        snapshot: Mapping[str, Any] | None = host.to_dict()
    else:
        snapshot = host
    if snapshot is not None and not isinstance(snapshot, Mapping):
        raise RuntimeContractError("host must be a HostSnapshot, a mapping or None")

    dimensions = {
        "format": _format_dimension(facts["model_format"], capabilities),
        "architecture": _architecture_dimension(facts["architecture"], capabilities),
        "quantization": _quantization_dimension(facts["quantization_types"], capabilities),
        "devices": _devices_dimension(capabilities, snapshot),
        "placement": _placement_dimension(placement_mode, capabilities),
    }
    controls = evaluate_controls(capabilities, requested_controls)
    overall = _overall_status(dimensions, capabilities.integration_status)

    warnings = [
        "Static contract comparison only. It does not prove backend operator support, model loading, "
        "generation correctness or performance.",
        "A declared-supported result means the adapter lists the capability; runtime verification is a separate gate.",
    ]
    if capabilities.integration_status != "integrated":
        warnings.append(
            "The backend is declared as not integrated; no ECLIPSE-managed backend lifecycle exists for it yet."
        )
    if facts["model_format"] is None:
        warnings.append("The model source format could not be identified; format support is unknown.")
    if facts["architecture"] is None:
        warnings.append("The model architecture was not declared; architecture support is unknown.")
    if facts["quantization_types"] is None:
        warnings.append("No tensor types were observed; quantization support is unknown.")

    return {
        "format": "eclipse_runtime_support",
        "runtime_contract_version": RUNTIME_CONTRACT_VERSION,
        "backend": {
            "backend_id": capabilities.backend_id,
            "display_name": capabilities.display_name,
            "backend_version": capabilities.backend_version,
            "integration_status": capabilities.integration_status,
            "evidence": capabilities.evidence,
        },
        "model": {
            "source_kind": facts["source_kind"],
            "model_format": facts["model_format"],
            "architecture": facts["architecture"],
            "quantization_types": facts["quantization_types"],
        },
        "dimensions": dimensions,
        "controls": controls,
        "overall_status": overall,
        "runtime_verified": False,
        "notes": list(capabilities.notes),
        "warnings": warnings,
    }
