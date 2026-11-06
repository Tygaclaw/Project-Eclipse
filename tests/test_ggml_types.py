from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import unittest

from eclipse.model_intelligence import (
    GGML_TYPE_TRAITS_REVISION,
    GGML_TYPE_TRAITS_SOURCE,
    get_ggml_type,
    tensor_storage_bytes,
    type_name,
)


class GGMLTypeRegistryTests(unittest.TestCase):
    def test_revision_and_source_are_recorded(self) -> None:
        self.assertEqual(len(GGML_TYPE_TRAITS_REVISION), 40)
        self.assertIn(GGML_TYPE_TRAITS_REVISION, GGML_TYPE_TRAITS_SOURCE)

    def test_known_block_and_type_sizes(self) -> None:
        expected = {
            0: ("f32", 1, 4),
            1: ("f16", 1, 2),
            2: ("q4_0", 32, 18),
            3: ("q4_1", 32, 20),
            6: ("q5_0", 32, 22),
            7: ("q5_1", 32, 24),
            8: ("q8_0", 32, 34),
            9: ("q8_1", 32, 36),
            10: ("q2_k", 256, 84),
            11: ("q3_k", 256, 110),
            12: ("q4_k", 256, 144),
            13: ("q5_k", 256, 176),
            14: ("q6_k", 256, 210),
            15: ("q8_k", 256, 292),
            16: ("iq2_xxs", 256, 66),
            17: ("iq2_xs", 256, 74),
            18: ("iq3_xxs", 256, 98),
            19: ("iq1_s", 256, 50),
            20: ("iq4_nl", 32, 18),
            21: ("iq3_s", 256, 110),
            22: ("iq2_s", 256, 82),
            23: ("iq4_xs", 256, 136),
            24: ("i8", 1, 1),
            25: ("i16", 1, 2),
            26: ("i32", 1, 4),
            27: ("i64", 1, 8),
            28: ("f64", 1, 8),
            29: ("iq1_m", 256, 56),
            30: ("bf16", 1, 2),
            34: ("tq1_0", 256, 54),
            35: ("tq2_0", 256, 66),
            39: ("mxfp4", 32, 17),
            40: ("nvfp4", 64, 36),
            41: ("q1_0", 128, 18),
            42: ("q2_0", 64, 18),
            43: ("f8_e4m3", 1, 1),
        }
        for type_id, (name, block_size, type_size) in expected.items():
            ggml_type = get_ggml_type(type_id)
            self.assertIsNotNone(ggml_type, type_id)
            assert ggml_type is not None
            self.assertEqual(ggml_type.name, name, type_id)
            self.assertEqual(ggml_type.block_size, block_size, type_id)
            self.assertEqual(ggml_type.type_size, type_size, type_id)

    def test_unknown_type_is_not_guessed(self) -> None:
        self.assertIsNone(get_ggml_type(65500))
        self.assertEqual(type_name(65500), "unknown_65500")

    def test_removed_types_are_not_computable(self) -> None:
        for type_id in (4, 5, 31, 32, 33, 36, 37, 38):
            ggml_type = get_ggml_type(type_id)
            self.assertIsNotNone(ggml_type, type_id)
            assert ggml_type is not None
            self.assertFalse(ggml_type.is_computable, type_id)

    def test_tensor_storage_bytes_for_dense_type(self) -> None:
        self.assertEqual(tensor_storage_bytes(0, (4, 8)), (128, None))
        self.assertEqual(tensor_storage_bytes(1, (4, 8)), (64, None))

    def test_tensor_storage_bytes_for_quantized_type(self) -> None:
        self.assertEqual(tensor_storage_bytes(2, (32, 2)), (36, None))
        self.assertEqual(tensor_storage_bytes(10, (256, 4)), (336, None))

    def test_tensor_storage_bytes_rejects_undivisible_row(self) -> None:
        self.assertEqual(tensor_storage_bytes(2, (8, 2)), (None, "row_not_divisible_by_block"))

    def test_tensor_storage_bytes_unknown_type(self) -> None:
        self.assertEqual(tensor_storage_bytes(65500, (4,)), (None, "unknown_type"))
        self.assertEqual(tensor_storage_bytes(4, (4,)), (None, "removed_or_unsupported_type"))

    def test_bits_per_weight(self) -> None:
        q4_0 = get_ggml_type(2)
        assert q4_0 is not None
        self.assertAlmostEqual(q4_0.bits_per_weight, 4.5)
        self.assertIsNone(get_ggml_type(4).bits_per_weight)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
