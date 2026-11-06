"""Presentation helpers for Model Atlas values.

These functions only format values that the Atlas already reports. They do not
derive model facts, estimate performance, or fill gaps with guesses.
"""

from __future__ import annotations

from typing import Any, Mapping

_BYTE_UNITS = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB")

_EVIDENCE_TEXT = {
    "observed": "Observed",
    "observed_metadata": "Observed metadata",
    "observed_header": "Observed header",
    "derived": "Derived",
    "partial": "Partial",
    "estimated": "Estimated",
    "hypothesized": "Hypothesized",
    "published": "Published",
    "unknown": "Unknown",
}

_SOURCE_KIND_TEXT = {
    "gguf": "GGUF file",
    "safetensors": "Safetensors file",
    "huggingface_folder": "Hugging Face model folder",
}


def human_bytes(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return "Unknown"
    amount = float(value)
    unit = _BYTE_UNITS[0]
    for candidate in _BYTE_UNITS:
        unit = candidate
        if amount < 1024.0 or candidate == _BYTE_UNITS[-1]:
            break
        amount /= 1024.0
    if unit == "B":
        return f"{int(amount)} B"
    return f"{amount:.2f} {unit}"


def human_count(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return "Unknown"
    return f"{value:,}"


def evidence_text(label: Any) -> str:
    if not isinstance(label, str):
        return "Unknown"
    return _EVIDENCE_TEXT.get(label, label.replace("_", " ").strip().title() or "Unknown")


def source_kind_text(kind: Any) -> str:
    if not isinstance(kind, str):
        return "Unknown source"
    return _SOURCE_KIND_TEXT.get(kind, kind.replace("_", " ").strip().title())


def distribution_rows(distribution: Any) -> list[tuple[str, int, float]]:
    if not isinstance(distribution, Mapping):
        return []
    counts = distribution.get("counts")
    if not isinstance(counts, Mapping):
        return []
    cleaned: list[tuple[str, int]] = []
    for label, count in counts.items():
        if isinstance(label, str) and isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            cleaned.append((label, count))
    total = sum(count for _, count in cleaned)
    if total <= 0:
        return []
    cleaned.sort(key=lambda item: (-item[1], item[0]))
    return [(label, count, count / total) for label, count in cleaned]


def completeness_text(value: Any) -> str:
    return "Complete" if value is True else "Partial or unknown"