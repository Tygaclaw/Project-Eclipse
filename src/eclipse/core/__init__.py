"""Shared ECLIPSE Core services."""

from .hardware import GPUDevice, HostSnapshot, detect_host_hardware
from .runtime import (
    CONTROL_NAMES,
    MODEL_FORMATS,
    PLACEMENT_MODES,
    RUNTIME_CONTRACT_VERSION,
    BackendCapabilities,
    ControlSupport,
    DeviceSupport,
    RuntimeContractError,
    evaluate_controls,
    evaluate_model_support,
    load_capabilities,
)

__all__ = [
    "CONTROL_NAMES",
    "MODEL_FORMATS",
    "PLACEMENT_MODES",
    "RUNTIME_CONTRACT_VERSION",
    "BackendCapabilities",
    "ControlSupport",
    "DeviceSupport",
    "GPUDevice",
    "HostSnapshot",
    "RuntimeContractError",
    "detect_host_hardware",
    "evaluate_controls",
    "evaluate_model_support",
    "load_capabilities",
]
