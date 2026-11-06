from __future__ import annotations

import unittest

from eclipse.model_intelligence.feasibility import (
    FeasibilityError,
    FeasibilityRequest,
    GiB,
    MiB,
    plan_model_feasibility,
)


def atlas(
    *,
    weight_bytes: int = 8 * GiB,
    complete: bool = True,
    details: dict | None = None,
) -> dict:
    return {
        "format": "eclipse_model_atlas",
        "atlas_version": 1,
        "source_kind": "gguf",
        "source_name": "test-model.gguf",
        "architecture": {
            "architecture": "test",
            "details": details or {
                "layer_count": {"value": 32, "evidence": "observed"},
                "kv_heads": {"value": 8, "evidence": "observed"},
                "key_head_dimension": {"value": 128, "evidence": "observed"},
                "value_head_dimension": {"value": 128, "evidence": "observed"},
                "context_length": {"value": 8192, "evidence": "observed"},
            },
        },
        "summary": {
            "total_storage_bytes": weight_bytes,
            "total_storage_is_complete": complete,
            "storage_evidence": "derived",
        },
    }


def host(*, ram_available: int = 12 * GiB, gpu_free: int | None = 6 * GiB) -> dict:
    gpu = []
    if gpu_free is not None:
        gpu = [{
            "name": "NVIDIA Test GPU",
            "memory_total_bytes": 8 * GiB,
            "memory_free_bytes": gpu_free,
            "memory_used_bytes": 8 * GiB - gpu_free,
        }]
    return {
        "schema_version": 1,
        "captured_at": "2026-11-06T00:00:00+00:00",
        "system_memory": {
            "physical_total_bytes": 48 * GiB,
            "available_bytes": ram_available,
            "evidence": "observed",
        },
        "gpus": gpu,
        "gpu_discovery": {
            "status": "available" if gpu else "unavailable",
            "evidence": "observed" if gpu else "unknown",
        },
        "storage": {
            "volume": "E:\\",
            "total_bytes": 1_000 * GiB,
            "free_bytes": 500 * GiB,
            "evidence": "observed",
        },
    }


class FeasibilityPlannerTests(unittest.TestCase):
    def test_kv_cache_estimate_uses_architecture_and_requested_context(self) -> None:
        result = plan_model_feasibility(
            atlas(),
            host(),
            FeasibilityRequest(
                context_tokens=4096,
                kv_cache_dtype="f16",
                sequence_slots=1,
                system_ram_reserve_bytes=2 * GiB,
                gpu_vram_reserve_bytes=1 * GiB,
            ),
        )
        kv = result["requirements"]["kv_cache"]
        expected = 32 * 4096 * 8 * (128 + 128) * 2
        self.assertEqual(kv["bytes"], expected)
        self.assertEqual(kv["evidence"], "estimated")
        self.assertEqual(kv["context_source"], "user_requested")

    def test_model_declared_context_is_used_when_user_does_not_override(self) -> None:
        result = plan_model_feasibility(
            atlas(),
            host(),
            FeasibilityRequest(
                system_ram_reserve_bytes=0,
                gpu_vram_reserve_bytes=0,
            ),
        )
        kv = result["requirements"]["kv_cache"]
        self.assertEqual(kv["context_tokens"], 8192)
        self.assertEqual(kv["context_source"], "model_declared")

    def test_sequence_slots_multiply_kv_cache_estimate(self) -> None:
        one = plan_model_feasibility(
            atlas(), host(), FeasibilityRequest(context_tokens=4096, sequence_slots=1)
        )
        two = plan_model_feasibility(
            atlas(), host(), FeasibilityRequest(context_tokens=4096, sequence_slots=2)
        )
        self.assertEqual(
            two["requirements"]["kv_cache"]["bytes"],
            2 * one["requirements"]["kv_cache"]["bytes"],
        )

    def test_combined_resident_fit_can_pass_when_gpu_and_ram_individually_do_not(self) -> None:
        result = plan_model_feasibility(
            atlas(weight_bytes=10 * GiB),
            host(ram_available=10 * GiB, gpu_free=6 * GiB),
            FeasibilityRequest(
                context_tokens=4096,
                system_ram_reserve_bytes=2 * GiB,
                gpu_vram_reserve_bytes=1 * GiB,
            ),
        )
        capacity = result["capacity_assessment"]["weights_plus_kv_cache"]
        self.assertEqual(capacity["gpu_only"], "exceeds_known_budget")
        self.assertEqual(capacity["ram_only"], "exceeds_known_budget")
        self.assertEqual(capacity["combined_ram_and_single_gpu"], "fits_within_known_budget")
        self.assertEqual(
            result["capacity_assessment"]["memory_classification"],
            "estimated_resident_memory_fit",
        )

    def test_gpu_vram_pools_are_not_aggregated(self) -> None:
        snapshot = host(ram_available=16 * GiB, gpu_free=4 * GiB)
        snapshot["gpus"].append({
            "name": "Second GPU",
            "memory_total_bytes": 16 * GiB,
            "memory_free_bytes": 12 * GiB,
        })
        result = plan_model_feasibility(
            atlas(), snapshot,
            FeasibilityRequest(context_tokens=4096, system_ram_reserve_bytes=0, gpu_vram_reserve_bytes=0),
        )
        selected = result["host"]["selected_gpu"]
        self.assertEqual(selected["device_name"], "Second GPU")
        self.assertEqual(result["budgets"]["single_gpu_vram_usable_bytes"], 12 * GiB)
        self.assertNotEqual(result["budgets"]["single_gpu_vram_usable_bytes"], 16 * GiB)

    def test_missing_kv_architecture_facts_remain_unknown(self) -> None:
        details = {
            "layer_count": {"value": 32, "evidence": "observed"},
            "kv_heads": {"value": 8, "evidence": "observed"},
        }
        result = plan_model_feasibility(
            atlas(details=details), host(),
            FeasibilityRequest(context_tokens=4096),
        )
        self.assertIsNone(result["requirements"]["kv_cache"]["bytes"])
        self.assertEqual(result["capacity_assessment"]["memory_classification"], "unknown_kv_cache_cost")
        self.assertIn("key head dimension", result["requirements"]["kv_cache"]["missing_architecture_facts"])
        self.assertIn("value head dimension", result["requirements"]["kv_cache"]["missing_architecture_facts"])

    def test_incomplete_weight_storage_prevents_full_fit_claim(self) -> None:
        result = plan_model_feasibility(
            atlas(complete=False), host(),
            FeasibilityRequest(context_tokens=4096),
        )
        self.assertEqual(
            result["capacity_assessment"]["memory_classification"],
            "unknown_incomplete_weight_storage",
        )
        self.assertEqual(
            result["requirements"]["weight_storage"]["usable_for_full_model_estimate"],
            False,
        )

    def test_weights_alone_exceeding_combined_capacity_is_a_definite_lower_bound(self) -> None:
        result = plan_model_feasibility(
            atlas(weight_bytes=40 * GiB), host(ram_available=8 * GiB, gpu_free=2 * GiB),
            FeasibilityRequest(
                context_tokens=None,
                system_ram_reserve_bytes=0,
                gpu_vram_reserve_bytes=0,
            ),
        )
        self.assertEqual(
            result["capacity_assessment"]["memory_classification"],
            "exceeds_resident_capacity_even_before_kv_cache",
        )
        policy = result["execution_feasibility"]["performance_goal_policy"]
        self.assertIs(policy["applies_to_this_profile"], True)
        self.assertEqual(policy["primary_acceptance_goal"], "10+ sustained tokens/second")
        self.assertEqual(policy["preferred_stretch_goal"], "15–20+ sustained tokens/second")
        self.assertIsNone(result["execution_feasibility"]["tokens_per_second_prediction"])

    def test_partial_weight_lower_bound_can_prove_oversized_but_not_prove_fit(self) -> None:
        result = plan_model_feasibility(
            atlas(weight_bytes=40 * GiB, complete=False),
            host(ram_available=8 * GiB, gpu_free=2 * GiB),
            FeasibilityRequest(
                context_tokens=4096,
                system_ram_reserve_bytes=0,
                gpu_vram_reserve_bytes=0,
            ),
        )
        assessment = result["capacity_assessment"]
        self.assertEqual(
            assessment["memory_classification"],
            "exceeds_resident_capacity_even_before_kv_cache",
        )
        self.assertTrue(assessment["weights_only"]["is_lower_bound_only"])
        self.assertEqual(assessment["native_memory_candidate"], "oversized_for_requested_profile")

    def test_within_weight_capacity_has_no_oversized_model_speed_floor(self) -> None:
        result = plan_model_feasibility(
            atlas(weight_bytes=4 * GiB),
            host(ram_available=48 * GiB, gpu_free=8 * GiB),
            FeasibilityRequest(
                context_tokens=4096,
                system_ram_reserve_bytes=4 * GiB,
                gpu_vram_reserve_bytes=512 * MiB,
            ),
        )
        policy = result["execution_feasibility"]["performance_goal_policy"]
        self.assertIs(policy["applies_to_this_profile"], False)
        self.assertIsNone(policy["primary_acceptance_goal"])
        self.assertIn("No fixed throughput floor", policy["native_fit_policy"])
        self.assertEqual(
            result["capacity_assessment"]["native_memory_candidate"],
            "within_resident_capacity_candidate",
        )

    def test_kv_cache_can_make_requested_profile_oversized_when_weights_fit(self) -> None:
        result = plan_model_feasibility(
            atlas(weight_bytes=4 * GiB),
            host(ram_available=8 * GiB, gpu_free=2 * GiB),
            FeasibilityRequest(
                context_tokens=262144,
                system_ram_reserve_bytes=0,
                gpu_vram_reserve_bytes=0,
            ),
        )
        assessment = result["capacity_assessment"]
        self.assertEqual(
            assessment["weights_only"]["combined_ram_and_single_gpu"],
            "fits_within_known_budget",
        )
        self.assertEqual(
            assessment["weights_plus_kv_cache"]["combined_ram_and_single_gpu"],
            "exceeds_known_budget",
        )
        self.assertEqual(
            assessment["native_memory_candidate"],
            "oversized_for_requested_profile",
        )
        self.assertIs(
            result["execution_feasibility"]["performance_goal_policy"]["applies_to_this_profile"],
            True,
        )

    def test_incomplete_weight_storage_below_capacity_leaves_target_scope_unknown(self) -> None:
        result = plan_model_feasibility(
            atlas(weight_bytes=2 * GiB, complete=False),
            host(ram_available=48 * GiB, gpu_free=8 * GiB),
        )
        policy = result["execution_feasibility"]["performance_goal_policy"]
        self.assertIsNone(policy["applies_to_this_profile"])
        self.assertEqual(policy["evidence"], "unknown")

    def test_memory_reserves_are_removed_from_available_budgets(self) -> None:
        result = plan_model_feasibility(
            atlas(), host(ram_available=10 * GiB, gpu_free=4 * GiB),
            FeasibilityRequest(
                context_tokens=4096,
                system_ram_reserve_bytes=2 * GiB,
                gpu_vram_reserve_bytes=1 * GiB,
            ),
        )
        self.assertEqual(result["budgets"]["system_ram_usable_bytes"], 8 * GiB)
        self.assertEqual(result["budgets"]["single_gpu_vram_usable_bytes"], 3 * GiB)

    def test_context_beyond_declared_maximum_is_flagged_not_silently_clamped(self) -> None:
        result = plan_model_feasibility(
            atlas(), host(), FeasibilityRequest(context_tokens=16384)
        )
        self.assertTrue(
            result["requirements"]["kv_cache"]["requested_context_exceeds_declared_limit"]
        )
        self.assertTrue(any("exceeds the model-declared" in warning for warning in result["warnings"]))

    def test_backend_and_performance_are_never_guessed(self) -> None:
        result = plan_model_feasibility(atlas(), host(), FeasibilityRequest(context_tokens=4096))
        execution = result["execution_feasibility"]
        self.assertEqual(execution["status"], "not_validated")
        self.assertEqual(execution["backend_compatibility"], "unknown")
        self.assertIsNone(execution["tokens_per_second_prediction"])
        self.assertEqual(
            execution["performance_target_category"],
            "no_fixed_floor_for_within_capacity_candidate",
        )
        policy = execution["performance_goal_policy"]
        self.assertIs(policy["applies_to_this_profile"], False)
        self.assertIn("No fixed throughput floor", policy["native_fit_policy"])

    def test_invalid_atlas_and_request_are_rejected(self) -> None:
        with self.assertRaises(FeasibilityError):
            plan_model_feasibility({}, host())
        with self.assertRaises(ValueError):
            FeasibilityRequest(context_tokens=0)
        with self.assertRaises(ValueError):
            FeasibilityRequest(system_ram_reserve_bytes=-1)


if __name__ == "__main__":
    unittest.main()
