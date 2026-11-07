"""Inference backend capability contracts and the static support matrix.

ECLIPSE does not implement its own kernels. It orchestrates maintained
backends through adapters, and every adapter declares exactly what it can do so
the UI never shows an unsupported control as if it worked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
        "version": 1,
        "backends": [backend.to_dict() for backend in SUPPORT_MATRIX],
        "policy": (
            "A backend is only offered for a model when its declared format and "
            "architecture are supported. Actual loading is verified by the "
            "runtime; a static support claim is not a successful load."
        ),
    }
