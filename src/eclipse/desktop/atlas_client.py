"""Safe desktop-to-Python boundary for Model Atlas inspection.

The desktop UI never re-implements checkpoint parsing. It invokes the existing
``eclipse build-atlas`` command as a separate process with an argument list (no
shell), captures bounded stdout/stderr, supports cancellation and a timeout,
and validates the returned JSON before the UI uses it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Mapping, Sequence

DEFAULT_TIMEOUT_SECONDS = 180.0
DEFAULT_MAX_OUTPUT_BYTES = 16 * 1024 * 1024
_POLL_INTERVAL_SECONDS = 0.05
_STREAM_CHUNK_BYTES = 65_536
_ERROR_TEXT_LIMIT = 2_000
_REQUIRED_TOP_LEVEL = (
    "format",
    "atlas_version",
    "source_kind",
    "source_name",
    "architecture",
    "summary",
    "components",
    "warnings",
    "evidence",
    "inspection",
)
_REQUIRED_SUMMARY = (
    "tensor_count",
    "total_parameters",
    "total_storage_bytes",
    "total_storage_is_complete",
    "distribution",
    "parameters_evidence",
    "storage_evidence",
)


class AtlasClientError(Exception):
    """Base class for expected Atlas boundary failures."""


class AtlasCancelledError(AtlasClientError):
    """The user cancelled the inspection."""


class AtlasTimeoutError(AtlasClientError):
    """The inspection exceeded its configured time limit."""


class AtlasOutputError(AtlasClientError):
    """The backend output was missing, oversized, or not a valid Atlas."""


def _source_directory() -> Path | None:
    if getattr(sys, "frozen", False):
        return None
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "eclipse").is_dir():
        return candidate
    return None


def default_backend_command(path: str, executable: str | None = None) -> list[str]:
    """Return the backend command as a list of separate arguments."""

    python = executable or sys.executable
    if getattr(sys, "frozen", False):
        return [python, "--atlas-backend", path, "--compact"]
    return [python, "-m", "eclipse", "build-atlas", path, "--compact"]


def _default_environment() -> dict[str, str]:
    environment = dict(os.environ)
    source = _source_directory()
    if source is not None:
        existing = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = str(source) + (os.pathsep + existing if existing else "")
    return environment


class _StreamReader:
    def __init__(self, stream: Any, limit: int) -> None:
        self._stream = stream
        self._limit = limit
        self._chunks: list[bytes] = []
        self._stored = 0
        self.total_bytes = 0
        self.overflow = False
        self._thread = threading.Thread(target=self._read, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _read(self) -> None:
        try:
            while True:
                chunk = self._stream.read(_STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                self.total_bytes += len(chunk)
                if self._stored < self._limit:
                    take = chunk[: self._limit - self._stored]
                    if take:
                        self._chunks.append(take)
                        self._stored += len(take)
                if self.total_bytes > self._limit:
                    self.overflow = True
        except (OSError, ValueError):
            return

    def join(self, timeout: float = 5.0) -> None:
        self._thread.join(timeout)

    def bytes(self) -> bytes:
        return b"".join(self._chunks)


class AtlasClient:
    """Run the existing Atlas backend with a bounded, cancellable boundary."""

    def __init__(
        self,
        *,
        executable: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
        command_factory: Callable[[str], Sequence[str]] | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be greater than zero")
        self._executable = executable
        self._timeout_seconds = float(timeout_seconds)
        self._max_output_bytes = int(max_output_bytes)
        self._command_factory = command_factory or (
            lambda path: default_backend_command(path, executable)
        )
        self._environment = _default_environment()
        if environment:
            self._environment.update({str(key): str(value) for key, value in environment.items()})

    def build(
        self,
        path: str | os.PathLike[str],
        *,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        source = os.fspath(path)
        if not isinstance(source, str) or not source:
            raise AtlasClientError("No model source was provided")

        command = list(self._command_factory(source))
        if not command or not all(isinstance(part, str) for part in command):
            raise AtlasClientError("The Atlas backend command is invalid")

        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                env=self._environment,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            raise AtlasClientError(f"Could not start the Model Atlas backend: {exc}") from exc

        stdout_reader = _StreamReader(process.stdout, self._max_output_bytes)
        stderr_reader = _StreamReader(process.stderr, _ERROR_TEXT_LIMIT)
        stdout_reader.start()
        stderr_reader.start()

        deadline = time.monotonic() + self._timeout_seconds
        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    self._stop(process)
                    raise AtlasCancelledError("Inspection cancelled")
                if process.poll() is not None:
                    break
                if time.monotonic() >= deadline:
                    self._stop(process)
                    raise AtlasTimeoutError(
                        f"Inspection exceeded the {self._timeout_seconds:.0f}-second time limit"
                    )
                time.sleep(_POLL_INTERVAL_SECONDS)
        finally:
            stdout_reader.join()
            stderr_reader.join()
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass

        stdout_bytes = stdout_reader.bytes()
        stderr_text = stderr_reader.bytes().decode("utf-8", errors="replace").strip()
        return_code = process.returncode

        if stdout_reader.overflow:
            raise AtlasOutputError(
                f"Model Atlas output exceeded the {self._max_output_bytes:,}-byte limit"
            )

        if return_code != 0:
            detail = stderr_text[: _ERROR_TEXT_LIMIT] if stderr_text else "The backend returned no error message"
            raise AtlasClientError(detail)

        if not stdout_bytes:
            raise AtlasOutputError("The Model Atlas backend returned no data")

        try:
            document = json.loads(stdout_bytes.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AtlasOutputError("The Model Atlas backend returned invalid JSON") from exc

        return validate_atlas_document(document)

    @staticmethod
    def _stop(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                return


def validate_atlas_document(document: Any) -> dict[str, Any]:
    """Validate the Atlas contract and the read-only safety invariants."""

    if not isinstance(document, dict):
        raise AtlasOutputError("The Model Atlas document must be a JSON object")
    missing = [key for key in _REQUIRED_TOP_LEVEL if key not in document]
    if missing:
        raise AtlasOutputError("The Model Atlas document is missing: " + ", ".join(missing))
    if document.get("format") != "eclipse_model_atlas":
        raise AtlasOutputError("The Model Atlas document has an unexpected format")
    if document.get("atlas_version") != 1:
        raise AtlasOutputError("The Model Atlas document has an unsupported version")

    summary = document.get("summary")
    if not isinstance(summary, dict):
        raise AtlasOutputError("The Model Atlas summary must be an object")
    missing_summary = [key for key in _REQUIRED_SUMMARY if key not in summary]
    if missing_summary:
        raise AtlasOutputError("The Model Atlas summary is missing: " + ", ".join(missing_summary))

    inspection = document.get("inspection")
    if not isinstance(inspection, dict):
        raise AtlasOutputError("The Model Atlas inspection record must be an object")
    if inspection.get("tensor_payloads_loaded") is not False:
        raise AtlasOutputError("The Model Atlas reported loaded tensor payloads")
    if inspection.get("tensor_payload_bytes_read") != 0:
        raise AtlasOutputError("The Model Atlas reported reading tensor payload bytes")
    if inspection.get("source_modified") is not False:
        raise AtlasOutputError("The Model Atlas reported a modified source")

    if not isinstance(document.get("warnings"), list):
        raise AtlasOutputError("The Model Atlas warnings must be a list")
    if not isinstance(document.get("evidence"), dict):
        raise AtlasOutputError("The Model Atlas evidence record must be an object")

    return document