"""Inference adapters, lifecycle management, profiles and telemetry."""

from .backends import (
    BackendCapabilities,
    BackendError,
    BackendUnavailable,
    BackendUnsupported,
    SUPPORT_MATRIX,
    backend_capabilities,
    support_matrix_report,
)
from .client import (
    CancellationToken,
    ChatCancelled,
    ChatError,
    ChatMessage,
    OpenAICompatibleClient,
    StreamChunk,
    ToolCall,
    ping_endpoint,
)
from .llamacpp import (
    LlamaCppAdapter,
    LlamaCppError,
    LlamaCppServer,
    LlamaCppStartError,
    find_server_binary,
)
from .manager import (
    STATE_LABELS,
    LoadResult,
    RuntimeManager,
    RuntimeState,
    RuntimeStatus,
)
from .profiles import (
    INTENTS,
    ProfileSpec,
    intent_choices,
    resolve_profile,
    validate_profile,
)
from .telemetry import ResourceSampler, StreamMetrics, process_snapshot

__all__ = [
    "BackendCapabilities",
    "BackendError",
    "BackendUnavailable",
    "BackendUnsupported",
    "CancellationToken",
    "ChatCancelled",
    "ChatError",
    "ChatMessage",
    "INTENTS",
    "LlamaCppAdapter",
    "LlamaCppError",
    "LlamaCppServer",
    "LlamaCppStartError",
    "LoadResult",
    "OpenAICompatibleClient",
    "ProfileSpec",
    "ResourceSampler",
    "RuntimeManager",
    "RuntimeState",
    "RuntimeStatus",
    "STATE_LABELS",
    "SUPPORT_MATRIX",
    "StreamChunk",
    "StreamMetrics",
    "ToolCall",
    "backend_capabilities",
    "find_server_binary",
    "intent_choices",
    "ping_endpoint",
    "process_snapshot",
    "resolve_profile",
    "support_matrix_report",
    "validate_profile",
]
