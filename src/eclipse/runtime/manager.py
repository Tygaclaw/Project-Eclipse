"""Truthful inference lifecycle management and measured telemetry.

The manager owns at most one active runtime. It separates load, generate, stop
and unload, never turns a failed load into a fake Ready state, cleans up the
process it started, and stores measured generation telemetry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import os
from pathlib import Path
import threading
import time
from typing import Any, Iterator, Mapping, Sequence

from eclipse.core.config import AppPaths, Settings
from eclipse.core.events import EventBus
from eclipse.core.hardware import detect_host_hardware
from eclipse.core.storage import Store
from .backends import BackendError, BackendUnavailable, backend_capabilities, support_matrix_report
from .client import (
    CancellationToken,
    ChatCancelled,
    ChatError,
    ChatMessage,
    OpenAICompatibleClient,
    StreamChunk,
    ping_endpoint,
)
from .llamacpp import LlamaCppServer, tail_text
from .placement import (
    PlacementRequest,
    plan_placement,
    reconcile_placement,
    summarize_placement,
)
from .profiles import (
    ProfileSpec,
    find_matching_profile,
    last_known_good_profile,
    restore_profile,
    save_profile,
    validate_profile,
)
from .telemetry import ResourceSampler, StreamMetrics, process_snapshot


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RuntimeState(str, Enum):
    NOT_LOADED = "not_loaded"
    PREPARING = "preparing"
    STARTING = "starting"
    LOADING = "loading"
    READY = "ready"
    GENERATING = "generating"
    STOPPING = "stopping"
    UNLOADING = "unloading"
    RESTART_REQUIRED = "restart_required"
    FAILED = "failed"
    NEEDS_ATTENTION = "needs_attention"


STATE_LABELS = {
    RuntimeState.NOT_LOADED: "Not loaded",
    RuntimeState.PREPARING: "Preparing",
    RuntimeState.STARTING: "Starting",
    RuntimeState.LOADING: "Loading",
    RuntimeState.READY: "Ready",
    RuntimeState.GENERATING: "Generating",
    RuntimeState.STOPPING: "Stopping",
    RuntimeState.UNLOADING: "Unloading",
    RuntimeState.RESTART_REQUIRED: "Restart required",
    RuntimeState.FAILED: "Failed",
    RuntimeState.NEEDS_ATTENTION: "Needs attention",
}


@dataclass
class RuntimeStatus:
    state: RuntimeState = RuntimeState.NOT_LOADED
    detail: str = "No model is loaded."
    model_id: str | None = None
    model_name: str | None = None
    backend: str | None = None
    endpoint: str | None = None
    pid: int | None = None
    owns_process: bool = False
    requested_context: int | None = None
    observed_context: int | None = None
    error: str | None = None
    log_path: str | None = None
    since: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "label": STATE_LABELS[self.state],
            "detail": self.detail,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "backend": self.backend,
            "endpoint": self.endpoint,
            "pid": self.pid,
            "owns_process": self.owns_process,
            "requested_context": self.requested_context,
            "observed_context": self.observed_context,
            "context_accepted": self.observed_context,
            "error": self.error,
            "log_path": self.log_path,
            "since": self.since,
        }


@dataclass
class LoadResult:
    status: dict[str, Any]
    spec: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


class RuntimeManager:
    """One shared, observable inference runtime for all three workspaces."""

    def __init__(
        self,
        store: Store,
        settings: Settings,
        paths: AppPaths,
        *,
        events: EventBus | None = None,
    ) -> None:
        self.store = store
        self.settings = settings
        self.paths = paths
        self.events = events or EventBus()
        self._lock = threading.RLock()
        self._status = RuntimeStatus()
        self._spec: ProfileSpec | None = None
        self._client: OpenAICompatibleClient | None = None
        self._server: LlamaCppServer | None = None
        self._sampler: ResourceSampler | None = None
        self._load_metrics: dict[str, Any] = {}
        self._load_placement: dict[str, Any] | None = None
        self._profile_id: str | None = None
        self._last_generation_metrics: dict[str, Any] = {}
        self._generation_lock = threading.Lock()

    # -- introspection ---------------------------------------------------

    @property
    def status(self) -> RuntimeStatus:
        with self._lock:
            self._refresh_process_state()
            return RuntimeStatus(**self._status.__dict__)

    @property
    def spec(self) -> ProfileSpec | None:
        with self._lock:
            return self._spec

    def capabilities(self, backend: str | None = None) -> dict[str, Any]:
        if backend is None:
            return support_matrix_report()
        return backend_capabilities(backend).to_dict()

    def endpoint(self) -> str | None:
        with self._lock:
            return self._status.endpoint

    def placement_plan(
        self,
        model: Mapping[str, Any],
        request: PlacementRequest | None = None,
    ) -> dict[str, Any]:
        """Plan an executable layer split for a registered model.

        This is an estimate derived from stored model facts and the current host
        snapshot. It never starts a backend and never claims a verified placement.
        """

        atlas = dict(model.get("atlas")) if isinstance(model.get("atlas"), Mapping) else {}
        if model.get("source_kind") and not atlas.get("source_kind"):
            atlas["source_kind"] = model.get("source_kind")
        try:
            host = detect_host_hardware().to_dict()
        except Exception:  # noqa: BLE001 - host probing is advisory evidence
            host = {}
        spec = self._spec
        if request is None and spec is not None:
            request = PlacementRequest(
                context_tokens=spec.context_tokens,
                kv_cache_dtype=spec.kv_cache_dtype,
                sequence_slots=spec.parallel_slots,
                mode=spec.placement_mode,
            )
        return plan_placement(atlas, host, request)

    # -- state helpers ---------------------------------------------------

    def _set_state(
        self,
        state: RuntimeState,
        detail: str,
        *,
        error: str | None = None,
    ) -> None:
        with self._lock:
            self._status.state = state
            self._status.detail = detail
            self._status.error = error
            self._status.since = utc_now_iso()
            snapshot = self._status.to_dict()
        self.events.emit("runtime.state", **snapshot)

    def _refresh_process_state(self) -> None:
        server = self._server
        if server is None:
            return
        if self._status.state in {
            RuntimeState.READY,
            RuntimeState.GENERATING,
            RuntimeState.RESTART_REQUIRED,
        } and not server.running:
            self._status.state = RuntimeState.FAILED
            self._status.detail = "The managed llama-server process exited unexpectedly."
            self._status.error = "process exited"
            self._status.pid = None
            self._status.since = utc_now_iso()

    # -- lifecycle -------------------------------------------------------

    def start(
        self,
        model: Mapping[str, Any],
        spec_payload: Mapping[str, Any],
        *,
        prepared_path: str | None = None,
    ) -> LoadResult:
        """Load a model through the selected backend, or fail honestly."""

        spec = ProfileSpec.from_payload(spec_payload)
        atlas = dict(model.get("atlas")) if isinstance(model.get("atlas"), Mapping) else {}
        if model.get("source_kind") and not atlas.get("source_kind"):
            # A registered model's source kind is part of its identity even when
            # no inspection atlas has been stored yet.
            atlas["source_kind"] = model.get("source_kind")
        warnings = validate_profile(spec, atlas=atlas)
        if self._status.state in {RuntimeState.READY, RuntimeState.GENERATING}:
            if self._status.model_id == model.get("id"):
                return LoadResult(status=self.status.to_dict(), spec=spec.to_payload(), warnings=warnings)
            self.stop()

        with self._lock:
            self._status = RuntimeStatus(
                state=RuntimeState.PREPARING,
                detail="Validating the model and execution profile.",
                model_id=str(model.get("id") or "") or None,
                model_name=str(model.get("name") or "") or None,
                backend=spec.backend,
                requested_context=spec.context_tokens,
            )
            self._spec = spec
            self._client = None
            self._server = None
            self._profile_id = None
        self.events.emit("runtime.state", **self.status.to_dict())

        started_clock = time.monotonic()
        placement: dict[str, Any] | None = None
        if spec.backend == "llamacpp_server":
            try:
                placement = self.placement_plan(
                    model,
                    PlacementRequest(
                        context_tokens=spec.context_tokens,
                        kv_cache_dtype=spec.kv_cache_dtype,
                        sequence_slots=spec.parallel_slots,
                        mode=spec.placement_mode,
                    ),
                )
            except Exception:  # noqa: BLE001 - planning is advisory, never a load gate
                placement = None
        with self._lock:
            self._load_placement = placement
        try:
            if spec.backend == "llamacpp_server":
                result = self._start_managed(model, spec, prepared_path)
            elif spec.backend == "openai_compatible":
                result = self._start_attach(model, spec)
            else:
                raise BackendUnavailable(f"Unknown backend: {spec.backend}")
        except Exception as exc:  # noqa: BLE001 - every failure must be visible
            message = str(exc) or type(exc).__name__
            self._cleanup_after_failure()
            self._set_state(
                RuntimeState.FAILED,
                "The model could not be loaded.",
                error=message,
            )
            raise RuntimeError(message) from exc

        load_seconds = round(time.monotonic() - started_clock, 3)
        with self._lock:
            self._load_metrics = {
                "load_seconds": load_seconds,
                "backend": spec.backend,
                "requested_context": spec.context_tokens,
                "observed_context": result.get("observed_context"),
                "pid": result.get("pid"),
                "gpu_layers": spec.gpu_layers,
                "placement": summarize_placement(placement),
                "started_at": utc_now_iso(),
            }
        if self._sampler is None:
            self._sampler = ResourceSampler(interval_seconds=1.0)
        self._sampler.start(result.get("pid"))
        self._remember_profile(model)
        self.store.record_run(
            kind="model_load",
            model_id=self._status.model_id,
            profile_id=self._profile_id,
            metrics=dict(self._load_metrics),
            status="ok",
        )
        self._set_state(RuntimeState.READY, "Model loaded and accepting requests.")
        return LoadResult(status=self.status.to_dict(), spec=spec.to_payload(), warnings=warnings)

    def _remember_profile(self, model: Mapping[str, Any]) -> None:
        """Persist the effective profile after a successful load.

        Profile persistence must never turn a healthy model into a failed load,
        so storage errors are deliberately contained here.
        """

        with self._lock:
            spec = self._spec
            model_id = self._status.model_id
            model_name = self._status.model_name or "Model"
        if spec is None or not model_id:
            return
        try:
            record = find_matching_profile(self.store, model_id, spec)
            if record is None:
                record = save_profile(
                    self.store,
                    spec,
                    model_id=model_id,
                    name=f"{model_name} · {spec.intent}",
                )
            self._profile_id = str(record["id"])
        except Exception:  # noqa: BLE001 - persistence is advisory, not runtime state
            self._profile_id = None

    def save_current_profile(
        self,
        name: str | None = None,
        *,
        mark_good: bool = False,
    ) -> dict[str, Any] | None:
        """Save the profile of the currently loaded model, if there is one."""

        with self._lock:
            spec = self._spec
            model_id = self._status.model_id
            status = self._status.state
        if spec is None or not model_id or status not in {
            RuntimeState.READY,
            RuntimeState.GENERATING,
            RuntimeState.RESTART_REQUIRED,
        }:
            return None
        record = save_profile(
            self.store,
            spec,
            model_id=model_id,
            name=name,
            mark_good=mark_good,
        )
        self._profile_id = str(record["id"])
        return record

    def restore_last_known_good(
        self,
        model: Mapping[str, Any] | None = None,
    ) -> LoadResult:
        """Load the newest saved last-known-good profile for the selected model."""

        model_id = str(model.get("id") or "") if isinstance(model, Mapping) else None
        record = last_known_good_profile(self.store, model_id or None)
        if record is None:
            raise RuntimeError("No last-known-good profile has been recorded yet")
        target_model = model
        if target_model is None:
            target_model = self.store.get_model(str(record.get("model_id") or ""))
        if not target_model:
            raise RuntimeError("The model for the saved profile is no longer registered")
        atlas = dict(target_model.get("atlas") or {})
        if target_model.get("source_kind") and not atlas.get("source_kind"):
            atlas["source_kind"] = target_model["source_kind"]
        spec = restore_profile(self.store, str(record["id"]), atlas=atlas)
        return self.start(target_model, spec.to_payload())

    @property
    def last_generation_metrics(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._last_generation_metrics)

    def _start_managed(
        self,
        model: Mapping[str, Any],
        spec: ProfileSpec,
        prepared_path: str | None,
    ) -> dict[str, Any]:
        source = prepared_path or str(model.get("source_path") or "")
        if not source:
            raise BackendUnavailable("The registered model has no usable source path")
        resource_dir = self.paths.logs_dir / "runtime"
        resource_dir.mkdir(parents=True, exist_ok=True)
        log_path = resource_dir / f"llama-server-{os.getpid()}.log"
        with self._lock:
            self._status.state = RuntimeState.STARTING
            self._status.detail = "Launching the llama.cpp server."
        self.events.emit("runtime.state", **self.status.to_dict())
        server = LlamaCppServer(
            source,
            executable=spec.binary,
            context_tokens=spec.context_tokens,
            gpu_layers=spec.gpu_layers,
            threads=spec.threads,
            parallel_slots=spec.parallel_slots,
            kv_cache_dtype=spec.kv_cache_dtype,
            extra_args=spec.extra_args,
            log_path=log_path,
        )
        with self._lock:
            self._server = server
            self._status.pid = None
            self._status.log_path = str(log_path)
        with self._lock:
            self._status.state = RuntimeState.LOADING
            self._status.detail = "Waiting for the server health endpoint."
        self.events.emit("runtime.state", **self.status.to_dict())
        server.start()
        details = server.describe()
        client = server.client()
        with self._lock:
            self._client = client
            self._status.endpoint = details["endpoint"]
            self._status.pid = details["pid"]
            self._status.owns_process = True
            self._status.observed_context = details["observed_context"]
            self._status.log_path = details["log_path"]
        return details

    def _start_attach(self, model: Mapping[str, Any], spec: ProfileSpec) -> dict[str, Any]:
        endpoint = (spec.endpoint or "").strip()
        if not endpoint:
            raise BackendUnavailable("No endpoint URL was configured for attach mode")
        with self._lock:
            self._status.state = RuntimeState.STARTING
            self._status.detail = "Checking the external endpoint."
        self.events.emit("runtime.state", **self.status.to_dict())
        api_key = os.environ.get("ECLIPSE_API_KEY") or ""
        client = OpenAICompatibleClient(endpoint, api_key=api_key, model=spec.model_name or "")
        try:
            models = client.list_models()
        except ChatError as exc:
            raise BackendUnavailable(str(exc)) from exc
        if spec.model_name and models and spec.model_name not in models:
            raise BackendUnavailable(
                f"Endpoint is reachable but does not list model '{spec.model_name}'"
            )
        with self._lock:
            self._client = client
            self._status.endpoint = endpoint.rstrip("/")
            self._status.pid = None
            self._status.owns_process = False
            self._status.observed_context = None
        return {
            "endpoint": endpoint,
            "pid": None,
            "observed_context": None,
            "models": models,
        }

    def _cleanup_after_failure(self) -> None:
        with self._lock:
            server = self._server
            self._server = None
            self._client = None
            sampler = self._sampler
            self._sampler = None
            self._load_placement = None
        if server is not None:
            try:
                server.stop()
            except Exception:  # noqa: BLE001 - cleanup must continue
                pass
        if sampler is not None:
            sampler.stop()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            server = self._server
            sampler = self._sampler
            placement = self._load_placement
            previous = self._status.to_dict()
            if server is None and self._status.state in {RuntimeState.NOT_LOADED, RuntimeState.FAILED}:
                self._status = RuntimeStatus(detail="No model is loaded.")
                return {"status": self.status.to_dict(), "stopped": True, "already_stopped": True}
            self._status.state = RuntimeState.STOPPING
            self._status.detail = "Stopping the model process."
        self.events.emit("runtime.state", **self.status.to_dict())
        stopped: dict[str, Any] = {"stopped": True}
        profile_id = self._profile_id
        try:
            if server is not None:
                stopped = server.stop()
                log_tail = tail_text(Path(stopped.get("log_path") or self._status.log_path or ""), 2000) if self._status.log_path else ""
                if log_tail and "error" in log_tail.lower():
                    stopped["log_excerpt"] = log_tail
        finally:
            samples = sampler.stop() if sampler is not None else []
            resource_summary = _summarise_samples(samples)
            reconciliation = reconcile_placement(
                placement,
                {
                    "peak_process_resident_bytes": resource_summary.get(
                        "peak_process_resident_bytes"
                    ),
                    "minimum_host_available_bytes": resource_summary.get(
                        "minimum_host_available_bytes"
                    ),
                    "peak_gpu_memory_used_bytes": None,
                    "sample_count": resource_summary.get("sample_count"),
                    "source": "runtime resource sampler",
                },
            )
            with self._lock:
                self._server = None
                self._client = None
                self._sampler = None
                self._spec = None
                self._profile_id = None
                self._load_placement = None
                self._last_generation_metrics = {}
                self._status = RuntimeStatus(
                    state=RuntimeState.UNLOADING,
                    detail="Releasing runtime resources.",
                    model_id=previous.get("model_id"),
                    model_name=previous.get("model_name"),
                    backend=previous.get("backend"),
                )
            self.events.emit("runtime.state", **self.status.to_dict())
            self._status = RuntimeStatus(detail="No model is loaded.")
            self.events.emit("runtime.state", **self.status.to_dict())
        self.store.record_run(
            kind="model_stop",
            model_id=previous.get("model_id"),
            profile_id=profile_id,
            metrics={
                "resources": resource_summary,
                "placement": summarize_placement(placement),
                "placement_reconciliation": reconciliation,
                "stop": {key: value for key, value in stopped.items() if key != "log_excerpt"},
            },
            status="ok",
            notes=stopped.get("log_excerpt", ""),
        )
        return {"status": self.status.to_dict(), **stopped}

    def restart(self, model: Mapping[str, Any], spec_payload: Mapping[str, Any]) -> LoadResult:
        self.stop()
        return self.start(model, spec_payload)

    def shutdown(self) -> None:
        try:
            if self._server is not None:
                self.stop()
        except Exception:  # noqa: BLE001 - shutdown must not raise
            well = self._server
            if well is not None:
                try:
                    well.stop()
                except Exception:  # noqa: BLE001
                    pass

    def mark_restart_required(self, reason: str) -> None:
        with self._lock:
            if self._status.state is not RuntimeState.READY:
                return
            self._status.state = RuntimeState.RESTART_REQUIRED
            self._status.detail = reason
        self.events.emit("runtime.state", **self.status.to_dict())

    # -- generation ------------------------------------------------------

    def require_ready(self) -> None:
        with self._lock:
            self._refresh_process_state()
            state = self._status.state
            client = self._client
            spec = self._spec
        if client is None or spec is None:
            raise ChatError("No model is loaded. Start a model in Model Intelligence first.")
        if state not in {RuntimeState.READY, RuntimeState.GENERATING, RuntimeState.RESTART_REQUIRED}:
            raise ChatError(f"The runtime is not ready ({STATE_LABELS[state]}).")

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[Mapping[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        cancel: CancellationToken | None = None,
        emit_deltas: bool = True,
    ) -> Iterator[StreamChunk]:
        self.require_ready()
        with self._lock:
            client = self._client
            spec = self._spec
            assert client is not None and spec is not None
            if self._status.state is RuntimeState.READY:
                self._status.state = RuntimeState.GENERATING
                self._status.detail = "Generating a response."
                self._status.since = utc_now_iso()
                snapshot = self._status.to_dict()
            else:
                snapshot = None
        if snapshot:
            self.events.emit("runtime.state", **snapshot)

        metrics = StreamMetrics()
        created_run = None
        completed = False
        try:
            for chunk in client.stream_chat(
                messages,
                tools=tools,
                temperature=spec.temperature if temperature is None else temperature,
                max_tokens=spec.max_tokens if max_tokens is None else max_tokens,
                cancel=cancel,
                model=spec.model_name or None,
            ):
                if chunk.text:
                    metrics.mark_delta(chunk.text)
                    if emit_deltas:
                        self.events.emit("runtime.delta", text=chunk.text)
                if chunk.usage:
                    prompt = chunk.usage.get("prompt_tokens")
                    completion = chunk.usage.get("completion_tokens")
                    if isinstance(prompt, int):
                        metrics.usage_prompt_tokens = prompt
                    if isinstance(completion, int):
                        metrics.usage_completion_tokens = completion
                if chunk.timings:
                    metrics.backend_timings.update(chunk.timings)
                    prompt_n = chunk.timings.get("prompt_n")
                    predicted_n = chunk.timings.get("predicted_n")
                    if isinstance(prompt_n, int) and metrics.usage_prompt_tokens is None:
                        metrics.usage_prompt_tokens = prompt_n
                    if isinstance(predicted_n, int) and metrics.usage_completion_tokens is None:
                        metrics.usage_completion_tokens = predicted_n
                if chunk.finish_reason:
                    metrics.finish_reason = chunk.finish_reason
                yield chunk
            completed = True
            metrics.finish()
        except ChatCancelled:
            metrics.cancelled = True
            metrics.finish()
            raise
        except ChatError:
            metrics.cancelled = cancel is not None and cancel.cancelled
            metrics.finish()
            with self._lock:
                if self._server is not None and not self._server.running:
                    self._status.state = RuntimeState.FAILED
                    self._status.error = "The inference process exited during generation."
                    self._status.detail = "The managed process exited during generation."
                    self._status.pid = None
                    self.events.emit("runtime.state", **self._status.to_dict())
            raise
        finally:
            metrics.finish()
            payload = metrics.to_dict()
            resources = {
                "process": process_snapshot(self._status.pid),
                "samples": _summarise_samples(self._sampler.samples() if self._sampler else []),
            }
            with self._lock:
                self._last_generation_metrics = dict(payload)
                profile_id = self._profile_id
            created_run = self.store.record_run(
                kind="generation",
                model_id=self._status.model_id,
                profile_id=profile_id,
                metrics={**payload, "resources": resources},
                status="cancelled" if metrics.cancelled else "ok",
            )
            if completed and not metrics.cancelled and profile_id:
                try:
                    profile = self.store.get_profile(profile_id)
                    if profile is not None:
                        self.store.mark_last_known_good(profile)
                except Exception:  # noqa: BLE001 - telemetry/evidence persistence is advisory
                    pass
            self.events.emit(
                "runtime.metrics",
                metrics=payload,
                resources=resources,
                run_id=created_run["id"],
            )
            with self._lock:
                previous = self._status.model_id
                if self._status.state is RuntimeState.GENERATING:
                    self._status.state = RuntimeState.READY
                    self._status.detail = "Model loaded and accepting requests."
                    self._status.error = None
                    self._status.since = utc_now_iso()
                snapshot = self._status.to_dict() if previous else None
            if snapshot:
                self.events.emit("runtime.state", **snapshot)

    def recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.store.list_runs(limit=limit)

    def diagnostics(self) -> dict[str, Any]:
        status = self.status.to_dict()
        spec = self._spec
        log_excerpt = None
        if self._status.log_path:
            log_excerpt = tail_text(Path(self._status.log_path), 4000)
        return {
            "format": "eclipse_runtime_diagnostics",
            "status": status,
            "profile": spec.to_payload() if spec else None,
            "profile_id": self._profile_id,
            "load_metrics": dict(self._load_metrics),
            "placement": summarize_placement(self._load_placement),
            "log_excerpt": log_excerpt,
            "host": {
                "pid": os.getpid(),
                "platform": os.name,
            },
        }


def _summarise_samples(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {"sample_count": 0, "peak_process_resident_bytes": None, "minimum_host_available_bytes": None}
    resident = [
        sample["process"]["resident_bytes"]
        for sample in samples
        if isinstance(sample.get("process"), Mapping)
        and isinstance(sample["process"].get("resident_bytes"), int)
    ]
    available = [
        sample["host_memory"]["available_bytes"]
        for sample in samples
        if isinstance(sample.get("host_memory"), Mapping)
        and isinstance(sample["host_memory"].get("available_bytes"), int)
    ]
    return {
        "sample_count": len(samples),
        "peak_process_resident_bytes": max(resident) if resident else None,
        "minimum_host_available_bytes": min(available) if available else None,
        "evidence": "observed" if resident or available else "unknown",
    }
