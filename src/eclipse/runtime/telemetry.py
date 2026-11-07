"""Measured runtime telemetry.

Only values that were actually observed are reported. Unavailable sensors stay
``None`` with an explicit evidence label; nothing here invents zeroes or
predicted throughput.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import threading
import time
from typing import Any

from eclipse.core.hardware import _memory_snapshot  # noqa: PLC2701 - shared probe


@dataclass
class StreamMetrics:
    """Wall-clock measurements for one streaming generation."""

    started_at: float = field(default_factory=time.monotonic)
    first_token_at: float | None = None
    finished_at: float | None = None
    chunk_count: int = 0
    characters: int = 0
    usage_prompt_tokens: int | None = None
    usage_completion_tokens: int | None = None
    backend_timings: dict[str, Any] = field(default_factory=dict)
    finish_reason: str | None = None
    cancelled: bool = False

    def mark_delta(self, text: str) -> None:
        self.chunk_count += 1
        self.characters += len(text)
        if text and self.first_token_at is None:
            self.first_token_at = time.monotonic()

    def finish(self) -> None:
        if self.finished_at is None:
            self.finished_at = time.monotonic()

    @property
    def time_to_first_token_seconds(self) -> float | None:
        if self.first_token_at is None:
            return None
        return round(self.first_token_at - self.started_at, 4)

    @property
    def total_seconds(self) -> float | None:
        if self.finished_at is None:
            return None
        return round(self.finished_at - self.started_at, 4)

    @property
    def decode_seconds(self) -> float | None:
        if self.first_token_at is None or self.finished_at is None:
            return None
        return max(0.0, self.finished_at - self.first_token_at)

    def tokens_per_second(self) -> float | None:
        completion = self.usage_completion_tokens
        seconds = self.decode_seconds
        if completion is None or completion <= 0 or seconds is None or seconds <= 0:
            return None
        return round(completion / seconds, 2)

    def to_dict(self) -> dict[str, Any]:
        completion = self.usage_completion_tokens
        return {
            "time_to_first_token_seconds": self.time_to_first_token_seconds,
            "total_seconds": self.total_seconds,
            "decode_seconds": None if self.decode_seconds is None else round(self.decode_seconds, 4),
            "chunk_count": self.chunk_count,
            "characters": self.characters,
            "prompt_tokens": self.usage_prompt_tokens,
            "completion_tokens": completion,
            "tokens_per_second": self.tokens_per_second(),
            "tokens_per_second_evidence": (
                "observed" if self.tokens_per_second() is not None else "unknown"
            ),
            "token_count_evidence": (
                "observed" if completion is not None else "unknown"
            ),
            "finish_reason": self.finish_reason,
            "cancelled": self.cancelled,
            "backend_timings": dict(self.backend_timings),
            "measurement": "wall_clock_stream",
            "note": (
                "Tokens/second is derived from the backend-reported completion "
                "token count and the measured decode wall time. It is not a "
                "benchmark score across models."
            ),
        }


def process_snapshot(pid: int | None) -> dict[str, Any]:
    """Best-effort RSS for the backend process, honest when unavailable."""

    if not pid or pid <= 0:
        return {"pid": pid, "resident_bytes": None, "evidence": "unknown"}
    try:
        import psutil  # type: ignore[import-not-found]

        process = psutil.Process(pid)
        return {
            "pid": pid,
            "resident_bytes": int(process.memory_info().rss),
            "cpu_percent": float(process.cpu_percent(interval=None)),
            "evidence": "observed",
            "source": "psutil",
        }
    except Exception:  # noqa: BLE001 - optional dependency and short-lived procs
        pass
    statm = Path(f"/proc/{pid}/statm")
    if statm.is_file():
        try:
            pages = int(statm.read_text(encoding="ascii").split()[1])
            return {
                "pid": pid,
                "resident_bytes": pages * os.sysconf("SC_PAGE_SIZE"),
                "cpu_percent": None,
                "evidence": "observed",
                "source": "/proc/statm",
            }
        except (OSError, ValueError, IndexError):
            return {"pid": pid, "resident_bytes": None, "evidence": "unknown"}
    return {"pid": pid, "resident_bytes": None, "evidence": "unknown"}


def host_memory_snapshot() -> dict[str, Any]:
    memory = _memory_snapshot()
    return {
        "physical_total_bytes": memory.get("physical_total_bytes"),
        "available_bytes": memory.get("available_bytes"),
        "evidence": memory.get("evidence", "unknown"),
        "source": memory.get("source"),
    }


class ResourceSampler:
    """Sample process and host resources on a background thread."""

    def __init__(self, interval_seconds: float = 1.0) -> None:
        self.interval_seconds = max(0.2, float(interval_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._samples: list[dict[str, Any]] = []
        self._pid: int | None = None

    def start(self, pid: int | None) -> None:
        self._pid = pid
        self._stop.clear()
        self._samples.clear()
        self._thread = threading.Thread(target=self._run, name="eclipse-resource-sampler", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            sample = {
                "at": time.time(),
                "process": process_snapshot(self._pid),
                "host_memory": host_memory_snapshot(),
            }
            with self._lock:
                self._samples.append(sample)
                if len(self._samples) > 3600:
                    del self._samples[:1800]

    def stop(self) -> list[dict[str, Any]]:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
        with self._lock:
            return list(self._samples)

    def samples(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._samples)
