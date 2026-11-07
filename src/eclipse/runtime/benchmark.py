"""Repeatable, measured generation benchmark.

This is deliberately a small harness rather than a model-quality score. It runs
the same prompt through the already-loaded runtime, keeps every measured sample,
and reports median/variance alongside the conditions. Missing measurements stay
``None``; a failed or partial run is never reported as successful.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import statistics
from typing import Any, Mapping, Sequence

from .client import CancellationToken, ChatError, ChatMessage

DEFAULT_PROMPT = "Reply with one short sentence confirming you are ready."


@dataclass
class BenchmarkSample:
    index: int
    metrics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "status": "failed" if self.error else "ok",
            "error": self.error,
            "metrics": dict(self.metrics),
        }


def _summary(values: Sequence[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    if not clean:
        return {
            "count": 0,
            "min": None,
            "median": None,
            "mean": None,
            "max": None,
            "stdev": None,
            "evidence": "unknown",
        }
    return {
        "count": len(clean),
        "min": round(min(clean), 4),
        "median": round(statistics.median(clean), 4),
        "mean": round(statistics.fmean(clean), 4),
        "max": round(max(clean), 4),
        "stdev": round(statistics.stdev(clean), 4) if len(clean) > 1 else 0.0,
        "evidence": "observed",
    }


def run_benchmark(
    runtime: Any,
    *,
    prompt: str = DEFAULT_PROMPT,
    runs: int = 3,
    warmup: int = 1,
    max_tokens: int = 32,
    temperature: float = 0.0,
    cancel: CancellationToken | None = None,
) -> dict[str, Any]:
    """Run measured generations and persist one benchmark summary record."""

    if runs < 1:
        raise ValueError("runs must be at least one")
    if warmup < 0:
        raise ValueError("warmup must be zero or greater")
    if max_tokens < 1:
        raise ValueError("max_tokens must be positive")
    if not 0.0 <= float(temperature) <= 2.0:
        raise ValueError("temperature must be between 0 and 2")
    prompt = str(prompt).strip()
    if not prompt:
        raise ValueError("prompt must not be empty")

    # Warm-up requests are intentionally excluded from the samples. They still
    # exercise the real runtime and are recorded as ordinary generations.
    for _ in range(warmup):
        for _chunk in runtime.stream_chat(
            [ChatMessage(role="user", content=prompt)],
            temperature=temperature,
            max_tokens=max_tokens,
            cancel=cancel,
        ):
            pass

    samples: list[BenchmarkSample] = []
    errors: list[str] = []
    for index in range(1, runs + 1):
        try:
            for _chunk in runtime.stream_chat(
                [ChatMessage(role="user", content=prompt)],
                temperature=temperature,
                max_tokens=max_tokens,
                cancel=cancel,
            ):
                pass
            metrics = dict(getattr(runtime, "last_generation_metrics", {}) or {})
            if not metrics:
                raise ChatError("The runtime did not expose measured generation metrics")
            samples.append(BenchmarkSample(index=index, metrics=metrics))
        except ChatError as exc:
            errors.append(f"run {index}: {exc}")
            samples.append(BenchmarkSample(index=index, error=str(exc)))
            break

    observed = [sample.metrics for sample in samples if sample.error is None]
    summary = {
        "time_to_first_token_seconds": _summary(
            [item.get("time_to_first_token_seconds") for item in observed]
        ),
        "tokens_per_second": _summary([item.get("tokens_per_second") for item in observed]),
        "total_seconds": _summary([item.get("total_seconds") for item in observed]),
        "completion_tokens": _summary([item.get("completion_tokens") for item in observed]),
    }
    if not observed:
        status = "failed"
    elif errors or len(observed) != runs:
        status = "partial"
    else:
        status = "ok"

    spec = getattr(runtime, "spec", None)
    status_snapshot = runtime.status
    result = {
        "format": "eclipse_runtime_benchmark",
        "version": 1,
        "status": status,
        "evidence": "observed" if observed else "unknown",
        "conditions": {
            "prompt": prompt,
            "runs_requested": runs,
            "warmup_runs": warmup,
            "max_tokens": max_tokens,
            "temperature": float(temperature),
            "model_id": status_snapshot.model_id,
            "model_name": status_snapshot.model_name,
            "backend": status_snapshot.backend,
            "requested_context": status_snapshot.requested_context,
            "observed_context": status_snapshot.observed_context,
            "profile": spec.to_payload() if spec is not None else None,
        },
        "samples": [sample.to_dict() for sample in samples],
        "summary": summary,
        "errors": errors,
        "note": (
            "Wall-clock measurements on this machine and backend only. "
            "This is not a cross-model quality score or a promise of performance."
        ),
    }
    recorded = runtime.store.record_run(
        kind="benchmark",
        model_id=status_snapshot.model_id,
        metrics=result,
        status=status,
        notes="Repeated measured generation benchmark; warm-up excluded from samples.",
    )
    result["run_id"] = recorded["id"]
    return result
