"""Bounded, read-only GGUF metadata and tensor-index inspection.

The parser reads the GGUF header, metadata and tensor descriptors only. It does
not map, copy, decode, or execute tensor payloads. The implementation follows
the public GGUF file-format specification and keeps unknown tensor type IDs
explicit instead of guessing their layout.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import struct
from typing import Any, BinaryIO

from .ggml_types import GGML_TYPE_TRAITS_REVISION, get_ggml_type, tensor_storage_bytes, type_name


class GGUFError(Exception):
    """Base class for expected GGUF inspection failures."""


class GGUFFormatError(GGUFError):
    """The input is truncated, malformed, or unsupported."""


class GGUFResourceLimitError(GGUFError):
    """The input exceeds a configured parser safety limit."""


@dataclass(frozen=True, slots=True)
class InspectionLimits:
    """Hard limits for untrusted checkpoint metadata and tensor indexes."""

    max_header_bytes: int = 256 * 1024 * 1024
    max_tensors: int = 200_000
    max_metadata_entries: int = 200_000
    max_string_bytes: int = 1_048_576
    max_tensor_name_bytes: int = 64
    max_array_items: int = 10_000_000
    max_array_preview_items: int = 32
    max_tensor_dimensions: int = 4

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.max_header_bytes == 0 or self.max_string_bytes == 0:
            raise ValueError("header and string limits must be greater than zero")
        if self.max_tensor_dimensions == 0:
            raise ValueError("max_tensor_dimensions must be greater than zero")


_METADATA_TYPES: dict[int, tuple[str, str]] = {
    0: ("uint8", "B"),
    1: ("int8", "b"),
    2: ("uint16", "H"),
    3: ("int16", "h"),
    4: ("uint32", "I"),
    5: ("int32", "i"),
    6: ("float32", "f"),
    7: ("bool", "B"),
    10: ("uint64", "Q"),
    11: ("int64", "q"),
    12: ("float64", "d"),
}

def _align_up(value: int, alignment: int) -> int:
    return value + ((alignment - (value % alignment)) % alignment)


class _Reader:
    def __init__(self, handle: BinaryIO, file_size: int, endian: str, limits: InspectionLimits):
        self.handle = handle
        self.file_size = file_size
        self.endian = endian
        self.limits = limits
        self.offset = 0
        self.array_items_seen = 0

    def _check_header_limit(self, end: int) -> None:
        if end > self.limits.max_header_bytes:
            raise GGUFResourceLimitError(
                f"Header/index exceeds configured limit of {self.limits.max_header_bytes:,} bytes"
            )

    def read_exact(self, count: int, *, header: bool = True) -> bytes:
        if count < 0:
            raise GGUFFormatError("Negative byte count encountered")
        end = self.offset + count
        if end > self.file_size:
            raise GGUFFormatError(
                f"Unexpected end of file at byte {self.offset:,}; needed {count:,} more bytes"
            )
        if header:
            self._check_header_limit(end)
        data = self.handle.read(count)
        if len(data) != count:
            raise GGUFFormatError(f"Short read at byte {self.offset:,}")
        self.offset = end
        return data

    def skip_exact(self, count: int) -> None:
        if count < 0:
            raise GGUFFormatError("Negative skip length encountered")
        end = self.offset + count
        if end > self.file_size:
            raise GGUFFormatError(
                f"Declared data extends past end of file (byte {end:,}; file is {self.file_size:,} bytes)"
            )
        self._check_header_limit(end)
        self.handle.seek(end, os.SEEK_SET)
        self.offset = end

    def unpack(self, fmt: str) -> tuple[Any, ...]:
        size = struct.calcsize(self.endian + fmt)
        return struct.unpack(self.endian + fmt, self.read_exact(size))

    def read_string(self, *, max_bytes: int | None = None) -> str:
        (length,) = self.unpack("Q")
        allowed = self.limits.max_string_bytes if max_bytes is None else min(
            max_bytes, self.limits.max_string_bytes
        )
        if length > allowed:
            raise GGUFResourceLimitError(
                f"String length {length:,} exceeds configured limit of {allowed:,} bytes"
            )
        try:
            return self.read_exact(length).decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise GGUFFormatError(f"Invalid UTF-8 string at byte {self.offset - length:,}") from exc

    def read_metadata_scalar(self, type_id: int) -> tuple[str, Any]:
        if type_id == 8:
            return "string", self.read_string()
        if type_id == 9:
            raise GGUFFormatError("Nested metadata arrays are not supported by the GGUF specification")
        if type_id not in _METADATA_TYPES:
            raise GGUFFormatError(f"Unknown GGUF metadata value type ID: {type_id}")
        type_name, fmt = _METADATA_TYPES[type_id]
        (value,) = self.unpack(fmt)
        if type_id in (6, 12) and not math.isfinite(value):
            raise GGUFFormatError("Non-finite floating-point metadata value is not valid JSON data")
        if type_id == 7:
            if value not in (0, 1):
                raise GGUFFormatError(f"Invalid GGUF boolean value: {value}")
            value = bool(value)
        return type_name, value

    def read_metadata_value(self, type_id: int) -> Any:
        if type_id != 9:
            type_name, value = self.read_metadata_scalar(type_id)
            return value

        (element_type,) = self.unpack("I")
        (count,) = self.unpack("Q")
        if element_type == 9:
            raise GGUFFormatError("Nested metadata arrays are not supported")
        if element_type not in _METADATA_TYPES and element_type != 8:
            raise GGUFFormatError(f"Unknown GGUF metadata array element type ID: {element_type}")

        self.array_items_seen += count
        if self.array_items_seen > self.limits.max_array_items:
            raise GGUFResourceLimitError(
                f"Metadata arrays contain more than {self.limits.max_array_items:,} items in total"
            )

        preview_count = min(count, self.limits.max_array_preview_items)
        preview: list[Any] = []
        for _ in range(preview_count):
            _, value = self.read_metadata_scalar(element_type)
            preview.append(value)

        remaining = count - preview_count
        if remaining:
            if element_type == 8:
                # Strings are variable-length; inspect each length and seek over
                # bytes without materialising the full string array.
                for _ in range(remaining):
                    (length,) = self.unpack("Q")
                    if length > self.limits.max_string_bytes:
                        raise GGUFResourceLimitError(
                            f"Array string length {length:,} exceeds configured string limit"
                        )
                    self.skip_exact(length)
            else:
                _, fmt = _METADATA_TYPES[element_type]
                self.skip_exact(remaining * struct.calcsize(self.endian + fmt))

        element_name = "string" if element_type == 8 else _METADATA_TYPES[element_type][0]
        return {
            "kind": "array",
            "element_type": element_name,
            "count": count,
            "preview": preview,
            "preview_truncated": count > preview_count,
        }


def inspect_gguf(path: str | os.PathLike[str], limits: InspectionLimits | None = None) -> dict[str, Any]:
    """Read GGUF metadata and tensor descriptors without reading tensor payloads."""

    source = Path(path)
    limits = limits or InspectionLimits()
    try:
        stat = source.stat()
    except OSError as exc:
        raise GGUFError(f"Cannot access input file: {exc}") from exc
    if not source.is_file():
        raise GGUFFormatError("Input path is not a regular file")
    file_size = stat.st_size
    if file_size < 24:
        raise GGUFFormatError("File is too small to contain a GGUF header")

    try:
        handle = source.open("rb")
    except OSError as exc:
        raise GGUFError(f"Cannot open input file: {exc}") from exc

    with handle:
        magic = handle.read(4)
        if magic != b"GGUF":
            raise GGUFFormatError("Invalid GGUF magic; expected the four bytes 'GGUF'")
        version_bytes = handle.read(4)
        if len(version_bytes) != 4:
            raise GGUFFormatError("Truncated GGUF version field")
        little_version = int.from_bytes(version_bytes, "little")
        big_version = int.from_bytes(version_bytes, "big")
        if little_version in (2, 3):
            endian = "<"
            version = little_version
        elif big_version == 3:
            endian = ">"
            version = big_version
        else:
            raise GGUFFormatError(
                f"Unsupported GGUF version/byte order (little={little_version}, big={big_version}); expected v2 or v3"
            )

        reader = _Reader(handle, file_size, endian, limits)
        reader.offset = 8
        (tensor_count, metadata_count) = reader.unpack("QQ")
        if tensor_count > limits.max_tensors:
            raise GGUFResourceLimitError(
                f"Tensor count {tensor_count:,} exceeds configured limit of {limits.max_tensors:,}"
            )
        if metadata_count > limits.max_metadata_entries:
            raise GGUFResourceLimitError(
                f"Metadata entry count {metadata_count:,} exceeds configured limit of {limits.max_metadata_entries:,}"
            )

        metadata: dict[str, Any] = {}
        for _ in range(metadata_count):
            key_offset = reader.offset
            key = reader.read_string(max_bytes=65_535)
            try:
                key.encode("ascii", errors="strict")
            except UnicodeEncodeError as exc:
                raise GGUFFormatError(f"Metadata key at byte {key_offset:,} is not ASCII") from exc
            if key in metadata:
                raise GGUFFormatError(f"Duplicate metadata key: {key}")
            (value_type,) = reader.unpack("I")
            metadata[key] = reader.read_metadata_value(value_type)
            if reader.offset > limits.max_header_bytes:
                raise GGUFResourceLimitError("Metadata exceeds configured header/index limit")

        alignment_value = metadata.get("general.alignment", 32)
        if isinstance(alignment_value, bool) or not isinstance(alignment_value, int):
            raise GGUFFormatError("general.alignment must be an integer metadata value")
        if alignment_value < 8 or alignment_value % 8 != 0:
            raise GGUFFormatError("general.alignment must be a positive multiple of 8")
        alignment = alignment_value

        tensors: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for _ in range(tensor_count):
            name_start = reader.offset
            name = reader.read_string(max_bytes=limits.max_tensor_name_bytes)
            if not name:
                raise GGUFFormatError("Tensor names cannot be empty")
            if name in seen_names:
                raise GGUFFormatError(f"Duplicate tensor name: {name}")
            seen_names.add(name)

            (dimensions_count,) = reader.unpack("I")
            if not 1 <= dimensions_count <= limits.max_tensor_dimensions:
                raise GGUFFormatError(
                    f"Tensor {name!r} has unsupported dimension count {dimensions_count}; limit is {limits.max_tensor_dimensions}"
                )
            dimensions = tuple(reader.unpack("Q")[0] for _ in range(dimensions_count))
            if any(dimension == 0 for dimension in dimensions):
                raise GGUFFormatError(f"Tensor {name!r} has a zero-length dimension")

            (type_id,) = reader.unpack("I")
            (relative_offset,) = reader.unpack("Q")
            if relative_offset % alignment != 0:
                raise GGUFFormatError(
                    f"Tensor {name!r} offset {relative_offset:,} is not aligned to {alignment} bytes"
                )
            tensor_elements = 1
            for dimension in dimensions:
                tensor_elements *= dimension
                if tensor_elements > (1 << 63) - 1:
                    raise GGUFResourceLimitError(f"Tensor {name!r} element count is too large")

            ggml_type = get_ggml_type(type_id)
            storage_bytes, unknown_reason = tensor_storage_bytes(type_id, dimensions)
            tensors.append(
                {
                    "name": name,
                    "dimensions": list(dimensions),
                    "element_count": tensor_elements,
                    "type_id": type_id,
                    "type_name": type_name(type_id),
                    "block_size": ggml_type.block_size if ggml_type else None,
                    "type_size_bytes": ggml_type.type_size if ggml_type else None,
                    "relative_data_offset": relative_offset,
                    "descriptor_offset": name_start,
                    "storage_bytes": storage_bytes,
                    "storage_bytes_evidence": "derived" if storage_bytes is not None else "unknown",
                    "storage_bytes_unknown_reason": unknown_reason,
                }
            )
            if reader.offset > limits.max_header_bytes:
                raise GGUFResourceLimitError("Tensor index exceeds configured header/index limit")

        tensor_data_start = _align_up(reader.offset, alignment)
        if tensor_data_start > file_size:
            raise GGUFFormatError("Aligned tensor-data region starts beyond the end of the file")
        tensor_data_bytes = file_size - tensor_data_start
        total_tensor_storage_bytes = 0
        complete_tensor_storage = True
        oversized_tensors: list[str] = []
        for tensor in tensors:
            absolute_offset = tensor_data_start + tensor["relative_data_offset"]
            if absolute_offset >= file_size:
                raise GGUFFormatError(
                    f"Tensor {tensor['name']!r} points outside the tensor-data region"
                )
            tensor["file_data_offset"] = absolute_offset
            if tensor["storage_bytes"] is None:
                complete_tensor_storage = False
            else:
                total_tensor_storage_bytes += tensor["storage_bytes"]
                if absolute_offset + tensor["storage_bytes"] > file_size:
                    oversized_tensors.append(tensor["name"])

        architecture = metadata.get("general.architecture")
        model_name = metadata.get("general.name") or metadata.get("general.basename")
        unknown_types = sorted(
            {tensor["type_name"] for tensor in tensors if tensor["type_name"].startswith("unknown_")}
        )
        warnings: list[str] = []
        if unknown_types:
            warnings.append(
                "Unrecognized tensor type IDs were preserved without guessing their storage layout: "
                + ", ".join(unknown_types)
            )
        unknown_storage = [
            tensor["name"]
            for tensor in tensors
            if tensor["storage_bytes"] is None
        ]
        if unknown_storage:
            warnings.append(
                "Exact storage size could not be derived for tensors with unverified type or "
                f"layout: {', '.join(unknown_storage[:10])}"
                + (" …" if len(unknown_storage) > 10 else "")
            )
        if oversized_tensors:
            warnings.append(
                "Declared tensor storage extends past the end of the file (file may be truncated): "
                + ", ".join(oversized_tensors[:10])
                + (" …" if len(oversized_tensors) > 10 else "")
            )
        warnings.append(
            "Tensor storage sizes are derived from a versioned GGML type registry; no tensor "
            "payload bytes were read. Declared sizes were not verified against a full checkpoint."
        )

        return {
            "format": "GGUF",
            "version": version,
            "endianness": "little" if endian == "<" else "big",
            "source_file_name": source.name,
            "file_size_bytes": file_size,
            "header_and_index_bytes": reader.offset,
            "tensor_data_start": tensor_data_start,
            "tensor_data_region_bytes": tensor_data_bytes,
            "alignment_bytes": alignment,
            "model": {
                "architecture": architecture,
                "name": model_name,
                "evidence": "observed_metadata" if architecture or model_name else "unknown",
            },
            "metadata": metadata,
            "tensor_count": tensor_count,
            "tensors": tensors,
            "tensor_storage": {
                "registry_revision": GGML_TYPE_TRAITS_REVISION,
                "total_bytes": total_tensor_storage_bytes,
                "total_is_complete": complete_tensor_storage,
                "evidence": "derived" if complete_tensor_storage else "partial",
            },
            "inspection": {
                "mode": "static_read_only",
                "tensor_payload_bytes_read": 0,
                "tensor_payloads_loaded": False,
                "source_modified": False,
            },
            "warnings": warnings,
        }
