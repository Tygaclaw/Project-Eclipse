"""Windows-first, read-only host hardware discovery.

The snapshot records only what the operating system and supported vendor
utilities report. NVIDIA VRAM discovery uses nvidia-smi when available; its
presence does not imply CUDA, Vulkan, or model-backend compatibility.
"""

from __future__ import annotations

import csv
import ctypes
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any

MiB = 1024 * 1024


@dataclass(frozen=True, slots=True)
class GPUDevice:
    """One GPU as reported by a supported host query."""

    index: int | None
    vendor: str
    name: str | None
    memory_total_bytes: int | None
    memory_free_bytes: int | None
    memory_used_bytes: int | None
    driver_version: str | None
    source: str
    evidence: str = "observed"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class HostSnapshot:
    """A privacy-conscious snapshot of resources available at capture time."""

    captured_at: str
    operating_system: dict[str, Any]
    processor: dict[str, Any]
    system_memory: dict[str, Any]
    gpus: tuple[GPUDevice, ...]
    gpu_discovery: dict[str, Any]
    storage: dict[str, Any] | None
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "captured_at": self.captured_at,
            "operating_system": dict(self.operating_system),
            "processor": dict(self.processor),
            "system_memory": dict(self.system_memory),
            "gpus": [gpu.to_dict() for gpu in self.gpus],
            "gpu_discovery": dict(self.gpu_discovery),
            "storage": dict(self.storage) if self.storage is not None else None,
            "warnings": list(self.warnings),
        }


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _windows_memory() -> tuple[int, int]:
    """Return physical and currently available RAM using a Windows API."""

    if os.name != "nt":
        raise OSError("Windows memory API is unavailable on this platform")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    function = kernel32.GlobalMemoryStatusEx
    function.argtypes = [ctypes.POINTER(_MemoryStatusEx)]
    function.restype = ctypes.c_int
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    if not function(ctypes.byref(status)):
        error = ctypes.get_last_error()
        raise OSError(error, "GlobalMemoryStatusEx failed")
    return int(status.ullTotalPhys), int(status.ullAvailPhys)


def _posix_memory() -> tuple[int, int]:
    """Return RAM totals through sysconf where the platform exposes them."""

    page_size = int(os.sysconf("SC_PAGE_SIZE"))
    total_pages = int(os.sysconf("SC_PHYS_PAGES"))
    available_pages = int(os.sysconf("SC_AVPHYS_PAGES"))
    if page_size <= 0 or total_pages <= 0 or available_pages < 0:
        raise OSError("The operating system returned invalid memory totals")
    return page_size * total_pages, page_size * available_pages


def _memory_snapshot() -> dict[str, Any]:
    try:
        total, available = _windows_memory() if os.name == "nt" else _posix_memory()
        if total <= 0 or available < 0 or available > total:
            raise OSError("The operating system returned inconsistent memory totals")
        return {
            "physical_total_bytes": total,
            "available_bytes": available,
            "evidence": "observed",
            "source": "GlobalMemoryStatusEx" if os.name == "nt" else "os.sysconf",
        }
    except (OSError, AttributeError, ValueError) as exc:
        return {
            "physical_total_bytes": None,
            "available_bytes": None,
            "evidence": "unknown",
            "source": None,
            "warning": f"System RAM could not be queried: {type(exc).__name__}",
        }


def _nvidia_smi_candidates() -> list[str]:
    candidates: list[str] = []
    found = shutil.which("nvidia-smi")
    if found:
        candidates.append(found)
    if os.name == "nt":
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        candidates.extend(
            [
                str(Path(program_files) / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe"),
                str(Path(system_root) / "System32" / "nvidia-smi.exe"),
            ]
        )
    return list(dict.fromkeys(candidates))


def _parse_nvidia_smi_output(output: str) -> tuple[GPUDevice, ...]:
    devices: list[GPUDevice] = []
    reader = csv.reader(io.StringIO(output), skipinitialspace=True)
    for row in reader:
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != 6:
            raise ValueError("NVIDIA query returned an unexpected column count")
        index_text, name, total_text, free_text, used_text, driver = (
            cell.strip() for cell in row
        )

        def parse_mib(value: str) -> int | None:
            if not value or value.upper() in {"N/A", "[N/A]", "NOT SUPPORTED"}:
                return None
            parsed = int(value)
            if parsed < 0:
                raise ValueError("NVIDIA query returned a negative memory value")
            return parsed * MiB

        index = int(index_text) if index_text.isdigit() else None
        devices.append(
            GPUDevice(
                index=index,
                vendor="nvidia",
                name=name or None,
                memory_total_bytes=parse_mib(total_text),
                memory_free_bytes=parse_mib(free_text),
                memory_used_bytes=parse_mib(used_text),
                driver_version=driver or None,
                source="nvidia-smi",
            )
        )
    return tuple(devices)


def _query_nvidia_gpus(
    *,
    executable: str | None = None,
    timeout_seconds: float = 3.0,
) -> tuple[tuple[GPUDevice, ...], dict[str, Any], str | None]:
    candidates = [executable] if executable else _nvidia_smi_candidates()
    if not candidates:
        return (
            (),
            {"status": "unavailable", "source": None, "evidence": "unknown"},
            "NVIDIA GPU telemetry is unavailable because nvidia-smi was not found; GPU memory and backend support remain unknown.",
        )

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result: subprocess.CompletedProcess[str] | None = None
    last_error: Exception | None = None
    # Try each known location in order, but only move on when a candidate
    # cannot be launched at all (for example the file does not exist). A
    # timeout stops the search so a hung driver tool is not waited on twice,
    # and a tool that ran but reported failure is not second-guessed.
    for candidate in candidates:
        command = [
            candidate,
            "--query-gpu=index,name,memory.total,memory.free,memory.used,driver_version",
            "--format=csv,noheader,nounits",
        ]
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
                shell=False,
                creationflags=creationflags,
            )
            break
        except subprocess.TimeoutExpired as exc:
            last_error = exc
            break
        except OSError as exc:
            last_error = exc
            continue
    if result is None:
        error_name = type(last_error).__name__ if last_error is not None else "OSError"
        return (
            (),
            {"status": "error", "source": "nvidia-smi", "evidence": "unknown"},
            f"NVIDIA GPU telemetry query did not complete: {error_name}. GPU memory and backend support remain unknown.",
        )

    if result.returncode != 0:
        return (
            (),
            {"status": "error", "source": "nvidia-smi", "evidence": "unknown"},
            "nvidia-smi did not return GPU information successfully; GPU memory and backend support remain unknown.",
        )
    try:
        devices = _parse_nvidia_smi_output(result.stdout)
    except (ValueError, csv.Error):
        return (
            (),
            {"status": "error", "source": "nvidia-smi", "evidence": "unknown"},
            "nvidia-smi returned data in an unrecognised format; GPU memory and backend support remain unknown.",
        )

    if not devices:
        return (
            (),
            {"status": "no_devices_reported", "source": "nvidia-smi", "evidence": "unknown"},
            "nvidia-smi did not report an NVIDIA GPU; other GPU vendors are not yet enumerated by this discovery path.",
        )
    return (
        devices,
        {"status": "available", "source": "nvidia-smi", "evidence": "observed"},
        None,
    )


def _operating_system_snapshot() -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": platform.system() or None,
        "release": platform.release() or None,
        "version": platform.version() or None,
        "machine": platform.machine() or None,
        "evidence": "observed",
    }
    if os.name == "nt" and hasattr(sys, "getwindowsversion"):
        try:
            version = sys.getwindowsversion()
            result["build"] = int(version.build)
            result["major_version"] = int(version.major)
            result["minor_version"] = int(version.minor)
        except (OSError, AttributeError, ValueError):
            result["build"] = None
    return result


def _processor_snapshot() -> dict[str, Any]:
    identifier = platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER")
    logical = os.cpu_count()
    return {
        "reported_identifier": identifier or None,
        "architecture": platform.machine() or None,
        "logical_processors": logical if isinstance(logical, int) and logical > 0 else None,
        "evidence": "observed",
        "note": "Processor model and logical processor count are OS-reported; core topology and clock behaviour are not inferred.",
    }


def _storage_snapshot(path: str | os.PathLike[str] | None) -> tuple[dict[str, Any] | None, str | None]:
    if path is None:
        return None, None
    try:
        target = Path(path).expanduser()
        if target.exists() and target.is_file():
            target = target.parent
        probe = target
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        usage = shutil.disk_usage(probe)
        return (
            {
                "volume": probe.anchor or None,
                "total_bytes": int(usage.total),
                "used_bytes": int(usage.used),
                "free_bytes": int(usage.free),
                "evidence": "observed",
                "source": "shutil.disk_usage",
                "device_type": None,
                "device_type_evidence": "unknown",
            },
            None,
        )
    except (OSError, ValueError) as exc:
        return None, f"Storage capacity for the selected model location could not be queried: {type(exc).__name__}"


def detect_host_hardware(
    storage_path: str | os.PathLike[str] | None = None,
    *,
    nvidia_smi_path: str | None = None,
    nvidia_timeout_seconds: float = 3.0,
) -> HostSnapshot:
    """Detect current OS/CPU/RAM and supported NVIDIA GPU/storage facts.

    This function never changes system settings, installs drivers, runs with
    elevated privileges, or infers CUDA/Vulkan/backend compatibility. Missing
    sensors are represented as unknown instead of as zero.
    """

    memory = _memory_snapshot()
    gpus, gpu_discovery, gpu_warning = _query_nvidia_gpus(
        executable=nvidia_smi_path,
        timeout_seconds=nvidia_timeout_seconds,
    )
    storage, storage_warning = _storage_snapshot(storage_path)
    warnings: list[str] = []
    if memory.get("warning"):
        warnings.append(str(memory["warning"]))
        memory.pop("warning", None)
    if gpu_warning:
        warnings.append(gpu_warning)
    if storage_warning:
        warnings.append(storage_warning)
    return HostSnapshot(
        captured_at=datetime.now(timezone.utc).isoformat(),
        operating_system=_operating_system_snapshot(),
        processor=_processor_snapshot(),
        system_memory=memory,
        gpus=gpus,
        gpu_discovery=gpu_discovery,
        storage=storage,
        warnings=tuple(warnings),
    )
