"""Managed llama.cpp server adapter.

ECLIPSE owns the process it starts: it chooses a free loopback port, waits for
the server's health endpoint, reads the server's reported context, streams
generations, and terminates the process on stop, failure or application exit.
Attach mode never claims ownership of an external server.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import threading
import time
from typing import Any, Iterator, Mapping, Sequence
from urllib import error as urlerror
from urllib import request as urlrequest

from .backends import BackendUnavailable, BackendUnsupported
from .client import (
    CancellationToken,
    ChatError,
    ChatMessage,
    OpenAICompatibleClient,
    StreamChunk,
)

_HEALTH_POLL_SECONDS = 0.4
_HEALTH_TIMEOUT_SECONDS = 240.0
_LOG_TAIL_BYTES = 6000
_SERVER_BINARY_CANDIDATES = (
    "llama-server",
    "llama-server.exe",
    "llama_server",
    "server",
)


class LlamaCppError(ChatError):
    """The managed llama.cpp server failed."""


class LlamaCppStartError(LlamaCppError):
    """The process started but never became healthy."""


def find_server_binary(explicit: str | None = None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file():
            return path
        located = shutil.which(explicit)
        return Path(located) if located else None
    env = os.environ.get("ECLIPSE_LLAMA_SERVER")
    if env:
        path = Path(env).expanduser()
        if path.is_file():
            return path
    for name in _SERVER_BINARY_CANDIDATES:
        located = shutil.which(name)
        if located:
            return Path(located)
    return None


def find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def tail_text(path: Path, limit: int = _LOG_TAIL_BYTES) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > limit:
                handle.seek(size - limit)
            data = handle.read(limit)
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace").strip()


@dataclass(frozen=True, slots=True)
class ServerLaunch:
    argv: list[str]
    endpoint: str
    host: str
    port: int
    log_path: Path


class LlamaCppServer:
    """A single owned llama.cpp server process with truthful state."""

    def __init__(
        self,
        model_path: str | os.PathLike[str],
        *,
        executable: str | os.PathLike[str] | None = None,
        context_tokens: int = 8192,
        gpu_layers: int = -1,
        threads: int | None = None,
        parallel_slots: int = 1,
        kv_cache_dtype: str = "f16",
        extra_args: Sequence[str] = (),
        log_path: str | os.PathLike[str] | None = None,
        host: str = "127.0.0.1",
        port: int | None = None,
        startup_timeout_seconds: float = _HEALTH_TIMEOUT_SECONDS,
    ) -> None:
        self.model_path = Path(model_path).expanduser().resolve()
        self.binary = find_server_binary(str(executable) if executable else None)
        self.context_tokens = int(context_tokens)
        self.gpu_layers = int(gpu_layers)
        self.threads = threads
        self.parallel_slots = max(1, int(parallel_slots))
        self.kv_cache_dtype = kv_cache_dtype
        self.extra_args = [str(arg) for arg in extra_args]
        self.host = host
        self.port = int(port) if port else find_free_port(host)
        self.startup_timeout_seconds = max(5.0, float(startup_timeout_seconds))
        self.log_path = Path(log_path) if log_path else Path(f"eclipse-llamacpp-{self.port}.log")
        self._process: subprocess.Popen[bytes] | None = None
        self._log_handle: Any = None
        self._lock = threading.RLock()
        self._observed_context: int | None = None
        self._observed_model_name: str | None = None
        self._props: dict[str, Any] = {}

    @property
    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def pid(self) -> int | None:
        process = self._process
        return process.pid if process is not None and process.poll() is None else None

    @property
    def running(self) -> bool:
        process = self._process
        return process is not None and process.poll() is None

    @property
    def observed_context(self) -> int | None:
        return self._observed_context

    @property
    def observed_model_name(self) -> str | None:
        return self._observed_model_name

    @property
    def props(self) -> dict[str, Any]:
        return dict(self._props)

    def validate(self) -> None:
        if self.binary is None:
            raise BackendUnavailable(
                "llama-server was not found. Install a llama.cpp build that "
                "includes llama-server, set ECLIPSE_LLAMA_SERVER to its path, "
                "or connect to an existing OpenAI-compatible endpoint."
            )
        if not self.model_path.is_file():
            raise BackendUnavailable("The GGUF model file does not exist")
        if self.model_path.suffix.lower() != ".gguf":
            raise BackendUnsupported(
                "The managed llama.cpp adapter supports GGUF model files only"
            )
        if self.context_tokens <= 0:
            raise BackendUnsupported("Context size must be greater than zero")
        if self.parallel_slots < 1:
            raise BackendUnsupported("At least one parallel slot is required")
        if self.kv_cache_dtype not in {"f16", "bf16", "q8_0", "q4_0"}:
            raise BackendUnsupported(f"Unsupported KV-cache type: {self.kv_cache_dtype}")
        if self.gpu_layers < -1:
            raise BackendUnsupported("GPU layer count must be -1 (all) or a non-negative integer")

    def build_launch(self) -> ServerLaunch:
        self.validate()
        assert self.binary is not None
        argv = [
            str(self.binary),
            "-m",
            str(self.model_path),
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--ctx-size",
            str(self.context_tokens),
            "--n-gpu-layers",
            str(self.gpu_layers),
            "--parallel",
            str(self.parallel_slots),
            "--jinja",
        ]
        if self.threads:
            argv.extend(["--threads", str(max(1, int(self.threads)))])
        if self.kv_cache_dtype != "f16":
            argv.extend(["--cache-type-k", self.kv_cache_dtype, "--cache-type-v", self.kv_cache_dtype])
        argv.extend(self.extra_args)
        return ServerLaunch(
            argv=argv,
            endpoint=self.endpoint,
            host=self.host,
            port=self.port,
            log_path=self.log_path,
        )

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self.running:
                return self.describe()
            launch = self.build_launch()
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = self.log_path.open("ab")
            self._log_handle.write(
                f"\n=== ECLIPSE launch {time.strftime('%Y-%m-%dT%H:%M:%S')} ===\n".encode()
            )
            self._log_handle.flush()
            creationflags = 0
            start_new_session = False
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0
                )
            else:
                start_new_session = True
            try:
                self._process = subprocess.Popen(
                    launch.argv,
                    stdin=subprocess.DEVNULL,
                    stdout=self._log_handle,
                    stderr=subprocess.STDOUT,
                    shell=False,
                    creationflags=creationflags,
                    start_new_session=start_new_session,
                )
            except OSError as exc:
                self._close_log()
                raise BackendUnavailable(
                    f"Could not launch llama-server: {type(exc).__name__}"
                ) from exc

        try:
            self._wait_for_health()
        except Exception:
            self.stop()
            raise
        return self.describe()

    def _wait_for_health(self) -> None:
        deadline = time.monotonic() + self.startup_timeout_seconds
        last_error = "no response"
        while time.monotonic() < deadline:
            process = self._process
            if process is not None and process.poll() is not None:
                log = tail_text(self.log_path)
                raise LlamaCppStartError(
                    "llama-server exited during startup"
                    + (f": {log[-1200:]}" if log else "")
                )
            try:
                with urlrequest.urlopen(f"{self.endpoint}/health", timeout=3) as response:
                    body = response.read(64 * 1024).decode("utf-8", errors="replace")
                    if response.status == 200:
                        try:
                            parsed = json.loads(body)
                        except json.JSONDecodeError:
                            parsed = {}
                        status = parsed.get("status") if isinstance(parsed, dict) else None
                        if status in (None, "ok", "ready", "loaded"):
                            self._load_props()
                            return
                        last_error = f"health status {status}"
            except (urlerror.URLError, OSError, ValueError) as exc:
                last_error = type(exc).__name__
            time.sleep(_HEALTH_POLL_SECONDS)
        log = tail_text(self.log_path)
        raise LlamaCppStartError(
            f"llama-server did not become ready within {self.startup_timeout_seconds:.0f}s "
            f"({last_error})" + (f": {log[-1200:]}" if log else "")
        )

    def _load_props(self) -> None:
        try:
            with urlrequest.urlopen(f"{self.endpoint}/props", timeout=5) as response:
                payload = json.loads(response.read(1024 * 1024).decode("utf-8", errors="replace"))
        except (urlerror.URLError, OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        self._props = payload
        settings = payload.get("default_generation_settings")
        if isinstance(settings, dict):
            context = settings.get("n_ctx")
            if isinstance(context, int) and context > 0:
                self._observed_context = context
        for key in ("n_ctx", "context_length"):
            value = payload.get(key)
            if isinstance(value, int) and value > 0 and self._observed_context is None:
                self._observed_context = value
        model_path = payload.get("model_path")
        if isinstance(model_path, str) and model_path:
            self._observed_model_name = Path(model_path).name

    def describe(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "pid": self.pid,
            "owns_process": True,
            "binary": str(self.binary) if self.binary else None,
            "log_path": str(self.log_path),
            "requested_context": self.context_tokens,
            "observed_context": self._observed_context,
            "observed_model_name": self._observed_model_name,
            "parallel_slots": self.parallel_slots,
            "gpu_layers": self.gpu_layers,
            "kv_cache_dtype": self.kv_cache_dtype,
            "props": self.props,
        }

    def client(self) -> OpenAICompatibleClient:
        return OpenAICompatibleClient(self.endpoint, model="local-model", timeout_seconds=600)

    def stop(self, *, timeout_seconds: float = 20.0) -> dict[str, Any]:
        with self._lock:
            process = self._process
            if process is None:
                self._close_log()
                return {"stopped": True, "already_stopped": True, "pid": None}
            pid = process.pid
            if process.poll() is None:
                try:
                    if os.name == "nt":
                        process.terminate()
                    else:
                        os.killpg(os.getpgid(pid), signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    try:
                        process.terminate()
                    except OSError:
                        pass
                try:
                    process.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    try:
                        if os.name == "nt":
                            process.kill()
                        else:
                            os.killpg(os.getpgid(pid), signal.SIGKILL)
                    except (OSError, ProcessLookupError):
                        try:
                            process.kill()
                        except OSError:
                            pass
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        pass
            exit_code = process.poll()
            self._process = None
            self._close_log()
            return {
                "stopped": exit_code is not None,
                "already_stopped": False,
                "pid": pid,
                "exit_code": exit_code,
            }

    def _close_log(self) -> None:
        handle = self._log_handle
        self._log_handle = None
        if handle is not None:
            try:
                handle.flush()
                handle.close()
            except OSError:
                pass

    def shutdown(self) -> None:
        self.stop()


class LlamaCppAdapter:
    """Chat interface for a managed llama.cpp server."""

    def __init__(self, server: LlamaCppServer) -> None:
        self.server = server

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[Mapping[str, Any]] | None = None,
        temperature: float | None = 0.7,
        max_tokens: int | None = 1024,
        cancel: CancellationToken | None = None,
    ) -> Iterator[StreamChunk]:
        if not self.server.running:
            raise LlamaCppError("The llama.cpp server is not running")
        yield from self.server.client().stream_chat(
            messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            cancel=cancel,
            model="local-model",
        )
