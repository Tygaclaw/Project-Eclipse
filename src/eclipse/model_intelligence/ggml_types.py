"""Versioned GGML tensor-type registry for exact tensor storage sizes.

Source of truth: the GGML type-traits table and block definitions in the
upstream llama.cpp project. The numeric IDs below are the on-disk GGUF tensor
type IDs and are frozen for the stable range; newer IDs are appended.

Pinned upstream revision:
``GGML_TYPE_TRAITS_REVISION`` (see the constant) was reviewed before these
block/type sizes were encoded. Re-review the upstream table before changing this
module. A type that is absent here is reported as unknown rather than guessed.
"""

from __future__ import annotations

from dataclasses import dataclass

GGML_TYPE_TRAITS_REVISION = "67107ac34f62882d8b53ea41ad68010ea635b9be"
GGML_TYPE_TRAITS_SOURCE = (
    "https://github.com/ggml-org/llama.cpp/blob/"
    f"{GGML_TYPE_TRAITS_REVISION}/ggml/src/ggml.c"
)
GGML_BLOCK_SOURCE = (
    "https://github.com/ggml-org/llama.cpp/blob/"
    f"{GGML_TYPE_TRAITS_REVISION}/ggml/src/ggml-common.h"
)


@dataclass(frozen=True, slots=True)
class GGMLType:
    """Block size and encoded storage size for one GGUF tensor type."""

    type_id: int
    name: str
    block_size: int
    type_size: int
    quantized: bool

    @property
    def is_computable(self) -> bool:
        return self.block_size > 0 and self.type_size > 0

    @property
    def bits_per_weight(self) -> float | None:
        if not self.is_computable:
            return None
        return 8.0 * self.type_size / self.block_size


def _t(type_id: int, name: str, block_size: int, type_size: int, quantized: bool) -> GGMLType:
    return GGMLType(
        type_id=type_id,
        name=name,
        block_size=block_size,
        type_size=type_size,
        quantized=quantized,
    )


GGML_TYPES: dict[int, GGMLType] = {
    0: _t(0, "f32", 1, 4, False),
    1: _t(1, "f16", 1, 2, False),
    2: _t(2, "q4_0", 32, 18, True),
    3: _t(3, "q4_1", 32, 20, True),
    4: _t(4, "q4_2_removed", 0, 0, False),
    5: _t(5, "q4_3_removed", 0, 0, False),
    6: _t(6, "q5_0", 32, 22, True),
    7: _t(7, "q5_1", 32, 24, True),
    8: _t(8, "q8_0", 32, 34, True),
    9: _t(9, "q8_1", 32, 36, True),
    10: _t(10, "q2_k", 256, 84, True),
    11: _t(11, "q3_k", 256, 110, True),
    12: _t(12, "q4_k", 256, 144, True),
    13: _t(13, "q5_k", 256, 176, True),
    14: _t(14, "q6_k", 256, 210, True),
    15: _t(15, "q8_k", 256, 292, True),
    16: _t(16, "iq2_xxs", 256, 66, True),
    17: _t(17, "iq2_xs", 256, 74, True),
    18: _t(18, "iq3_xxs", 256, 98, True),
    19: _t(19, "iq1_s", 256, 50, True),
    20: _t(20, "iq4_nl", 32, 18, True),
    21: _t(21, "iq3_s", 256, 110, True),
    22: _t(22, "iq2_s", 256, 82, True),
    23: _t(23, "iq4_xs", 256, 136, True),
    24: _t(24, "i8", 1, 1, False),
    25: _t(25, "i16", 1, 2, False),
    26: _t(26, "i32", 1, 4, False),
    27: _t(27, "i64", 1, 8, False),
    28: _t(28, "f64", 1, 8, False),
    29: _t(29, "iq1_m", 256, 56, True),
    30: _t(30, "bf16", 1, 2, False),
    31: _t(31, "q4_0_4_4_removed", 0, 0, False),
    32: _t(32, "q4_0_4_8_removed", 0, 0, False),
    33: _t(33, "q4_0_8_8_removed", 0, 0, False),
    34: _t(34, "tq1_0", 256, 54, True),
    35: _t(35, "tq2_0", 256, 66, True),
    36: _t(36, "iq4_nl_4_4_removed", 0, 0, False),
    37: _t(37, "iq4_nl_4_8_removed", 0, 0, False),
    38: _t(38, "iq4_nl_8_8_removed", 0, 0, False),
    39: _t(39, "mxfp4", 32, 17, True),
    40: _t(40, "nvfp4", 64, 36, True),
    41: _t(41, "q1_0", 128, 18, True),
    42: _t(42, "q2_0", 64, 18, True),
    43: _t(43, "f8_e4m3", 1, 1, False),
}


def get_ggml_type(type_id: int) -> GGMLType | None:
    return GGML_TYPES.get(type_id)


def type_name(type_id: int) -> str:
    ggml_type = GGML_TYPES.get(type_id)
    return ggml_type.name if ggml_type else f"unknown_{type_id}"


def tensor_storage_bytes(type_id: int, dimensions: tuple[int, ...] | list[int]) -> tuple[int | None, str | None]:
    """Return the exact encoded byte count for a tensor, or a reason it is unknown.

    The count mirrors upstream ``ggml_nbytes``: quantized types store whole
    blocks, so the number of bytes is ``type_size * elements / block_size`` and
    the innermost dimension must be a multiple of the block size. The count is a
    derived value, not an observed file range.
    """

    ggml_type = GGML_TYPES.get(type_id)
    if ggml_type is None:
        return None, "unknown_type"
    if not ggml_type.is_computable:
        return None, "removed_or_unsupported_type"
    if not dimensions or any(dimension <= 0 for dimension in dimensions):
        return None, "invalid_dimensions"
    if ggml_type.block_size > 1 and dimensions[0] % ggml_type.block_size != 0:
        return None, "row_not_divisible_by_block"

    elements = 1
    for dimension in dimensions:
        elements *= dimension
    return elements // ggml_type.block_size * ggml_type.type_size, None
