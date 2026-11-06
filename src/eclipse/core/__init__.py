"""Shared ECLIPSE Core services."""

from .hardware import GPUDevice, HostSnapshot, detect_host_hardware

__all__ = ["GPUDevice", "HostSnapshot", "detect_host_hardware"]
