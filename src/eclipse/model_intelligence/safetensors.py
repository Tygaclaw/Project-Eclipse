"""Bounded, read-only Safetensors header inspection.

The parser reads only the 8-byte header length, the JSON header and the declared
tensor offsets. Tensor payload bytes are never read, mapped or decoded. Values
are validated against the safetensors specification before they are reported.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import struct
from typing import Any


class SafetensorsError(Exception):
    """Base class for expected Safetensors inspection failures."""


class SafetensorsFormatError(SafetensorsError):
    """The input is truncated, malformed, or unsupported."""


class SafetensorsResourceLimitError(SafetensorsError):
    """The input exceeds a configured parser safety limit."""


@dataclass(frozen=True, slots=True)
class SafetensorsLimits:
    """Hard limits for untrusted Safetensors headers and tensor indexes."""

    max_header_bytes: int = 100 * 1024 * 1024
    max_tensors: int = 200_000
    max_metadata_entries: int = 200_000
    max_name_bytes: int = 65_536
    max_shape_dimensions: int = 32

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.max_header_bytes == 0:
            raise ValueError("max_header_bytes must be greater than zero")
        if self.max_name_bytes == 0:
            raise ValueError("max_name_bytes must be greater than zero")
        if self.max_shape_dimensions == 0:
            raise ValueError("max_shape_dimensions must be greater than zero")


_DTYPE_BITS: dict[str, int] = {
    "BOOL": 8,
    "I8": 8,
    "U8": 8,
    "F8_E5M2": 8,
    "F8_E4M3": 8,
    "F8_E8M0": 8,
    "E8M0": 8,
    "U16": 16,
    "I16": 16,
    "F16": 16,
    "BF16": 16,
    "U32": 32,
    "I32": 32,
    "F32": 32,
    "U64": 64,
    "I64": 64,
    "F64": 64,
    "I4": 4,
    "U4": 4,
    "F4": 4,
    "F6_E2M3": 6,
    "F6_E3M2": 6,
}

_METADATA_KEY = "__metadata__"


def _require_str(value: Any, message: str) -> str:
    if not isinstance(value, str):
        raise SafetensorsFormatError(message)
    return value


def _require_int(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SafetensorsFormatError(message)
    return value


def _parse_tensor_entry(
    name: str,
    entry: Any,
    *,
    buffer_size: int,
    limits: SafetensorsLimits,
) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise SafetensorsFormatError(f"Tensor {name!r} header entry must be an object")

    dtype = _require_str(entry.get("dtype"), f"Tensor {name!r} dtype must be a string")
    shape_value = entry.get("shape")
    if not isinstance(shape_value, list):
        raise SafetensorsFormatError(f"Tensor {name!r} shape must be a list of integers")
    if len(shape_value) > limits.max_shape_dimensions:
        raise SafetensorsResourceLimitError(
            f"Tensor {name!r} has {len(shape_value)} dimensions; limit is {limits.max_shape_dimensions}"
        )
    shape: list[int] = []
    element_count = 1
    for dimension in shape_value:
        parsed = _require_int(dimension, f"Tensor {name!r} shape entries must be integers")
        if parsed < 0:
            raise SafetensorsFormatError(f"Tensor {name!r} has a negative dimension")
        shape.append(parsed)
        if parsed == 0:
            element_count = 0
        elif element_count:
            element_count *= parsed

    offsets_value = entry.get("data_offsets")
    if not isinstance(offsets_value, list) or len(offsets_value) != 2:
        raise SafetensorsFormatError(f"Tensor {name!r} data_offsets must contain exactly two integers")
    begin = _require_int(offsets_value[0], f"Tensor {name!r} data_offsets[0] must be an integer")
    end = _require_int(offsets_value[1], f"Tensor {name!r} data_offsets[1] must be an integer")
    if begin < 0 or end < 0:
        raise SafetensorsFormatError(f"Tensor {name!r} data_offsets cannot be negative")
    if begin > end:
        raise SafetensorsFormatError(f"Tensor {name!r} data_offsets start is after its end")
    if end > buffer_size:
        raise SafetensorsFormatError(
            f"Tensor {name!r} data_offsets end {end:,} exceeds the {buffer_size:,}-byte data region"
        )

    expected_bytes: int | None = None
    bits = _DTYPE_BITS.get(dtype)
    if bits is not None:
        total_bits = element_count * bits
        expected_bytes = total_bits // 8 if total_bits % 8 == 0 else None

    return {
        "name": name,
        "dtype": dtype,
        "shape": shape,
        "element_count": element_count,
        "data_offset_begin": begin,
        "data_offset_end": end,
        "storage_bytes": end - begin,
        "storage_bytes_evidence": "observed_header",
        "expected_bytes_from_shape": expected_bytes,
    }


def inspect_safetensors(
    path: str | os.PathLike[str],
    limits: SafetensorsLimits | None = None,
) -> dict[str, Any]:
    """Read a Safetensors header and tensor index without reading payload bytes."""

    source = Path(path)
    limits = limits or SafetensorsLimits()
    try:
        stat = source.stat()
    except OSError as exc:
        raise SafetensorsError(f"Cannot access input file: {exc}") from exc
    if not source.is_file():
        raise SafetensorsFormatError("Input path is not a regular file")
    file_size = stat.st_size
    if file_size < 8:
        raise SafetensorsFormatError("File is too small to contain a Safetensors header length")

    try:
        handle = source.open("rb")
    except OSError as exc:
        raise SafetensorsError(f"Cannot open input file: {exc}") from exc

    with handle:
        length_bytes = handle.read(8)
        if len(length_bytes) != 8:
            raise SafetensorsFormatError("Truncated Safetensors header length")
        header_length = struct.unpack("<Q", length_bytes)[0]
        if header_length == 0:
            raise SafetensorsFormatError("Safetensors header length must be greater than zero")
        if header_length > limits.max_header_bytes:
            raise SafetensorsResourceLimitError(
                f"Header length {header_length:,} exceeds configured limit of {limits.max_header_bytes:,} bytes"
            )
        data_region_start = 8 + header_length
        if data_region_start > file_size:
            raise SafetensorsFormatError(
                f"Header length {header_length:,} extends past the end of the file"
            )
        buffer_size = file_size - data_region_start

        header_bytes = handle.read(header_length)
        if len(header_bytes) != header_length:
            raise SafetensorsFormatError("Short read while loading the Safetensors header")

    try:
        header_text = header_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SafetensorsFormatError("Safetensors header is not valid UTF-8") from exc
    try:
        header = json.loads(header_text)
    except json.JSONDecodeError as exc:
        raise SafetensorsFormatError(f"Safetensors header is not valid JSON: {exc.msg}") from exc
    if not isinstance(header, dict):
        raise SafetensorsFormatError("Safetensors header must be a JSON object")

    metadata: dict[str, str] = {}
    if _METADATA_KEY in header:
        raw_metadata = header[_METADATA_KEY]
        if not isinstance(raw_metadata, dict):
            raise SafetensorsFormatError("Safetensors __metadata__ must be an object")
        if len(raw_metadata) > limits.max_metadata_entries:
            raise SafetensorsResourceLimitError(
                f"__metadata__ has {len(raw_metadata):,} entries; limit is {limits.max_metadata_entries:,}"
            )
        for key, value in raw_metadata.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise SafetensorsFormatError("Safetensors __metadata__ entries must map strings to strings")
            metadata[key] = value

    tensor_names = [name for name in header if name != _METADATA_KEY]
    if len(tensor_names) > limits.max_tensors:
        raise SafetensorsResourceLimitError(
            f"Tensor count {len(tensor_names):,} exceeds configured limit of {limits.max_tensors:,}"
        )

    tensors: list[dict[str, Any]] = []
    intervals: list[tuple[int, int, str]] = []
    warnings: list[str] = []
    for name in tensor_names:
        if len(name.encode("utf-8")) > limits.max_name_bytes:
            raise SafetensorsResourceLimitError(f"Tensor name exceeds {limits.max_name_bytes:,} bytes")
        parsed = _parse_tensor_entry(name, header[name], buffer_size=buffer_size, limits=limits)
        tensors.append(parsed)
        intervals.append((parsed["data_offset_begin"], parsed["data_offset_end"], name))

    intervals.sort()
    for previous, current in zip(intervals, intervals[1:]):
        if current[0] < previous[1]:
            raise SafetensorsFormatError(
                f"Tensor {current[2]!r} data offsets overlap tensor {previous[2]!r}"
            )

    unknown_dtypes = sorted({tensor["dtype"] for tensor in tensors if tensor["dtype"] not in _DTYPE_BITS})
    if unknown_dtypes:
        warnings.append(
            "Unrecognized tensor dtypes were reported by their observed byte range only: "
            + ", ".join(unknown_dtypes)
        )
    mismatches = [
        tensor["name"]
        for tensor in tensors
        if tensor["expected_bytes_from_shape"] is not None
        and tensor["expected_bytes_from_shape"] != tensor["storage_bytes"]
    ]
    if mismatches:
        warnings.append(
            "Declared header byte ranges do not match dtype × shape for: "
            + ", ".join(mismatches[:10])
            + (" …" if len(mismatches) > 10 else "")
        )

    return {
        "format": "safetensors",
        "source_file_name": source.name,
        "file_size_bytes": file_size,
        "header_length_bytes": header_length,
        "data_region_start": data_region_start,
        "data_region_bytes": buffer_size,
        "metadata": metadata,
        "tensor_count": len(tensors),
        "tensors": tensors,
        "total_tensor_storage_bytes": sum(tensor["storage_bytes"] for tensor in tensors),
        "inspection": {
            "mode": "static_read_only",
            "tensor_payload_bytes_read": 0,
            "tensor_payloads_loaded": False,
            "source_modified": False,
        },
        "warnings": warnings,
    }
