"""Executable placement planning and reconciliation tests."""

from __future__ import annotations

from tests import _bootstrap  # noqa: F401

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from eclipse.runtime.placement import (
    PLACEMENT_INTENTS,
    PlacementError,
    PlacementRequest,
    plan_placement,
    reconcile_placement,
    summarize_placement,
)
from eclipse.runtime.profiles import ProfileSpec, resolve_profile
from tests.test_model_atlas import build_gguf

GiB = 1024**3
MiB = 1024**2


def atlas(
    *,
    weight_bytes: int = 8 * GiB,
    complete: bool = True,
    layers: int | None = 32,
) -> dict:
    return {
        "format": "eclipse_model_atlas",
        "atlas_version": 1,
        "source_kind": "gguf",
        "source_name": "placement-model.gguf",
        "architecture": {
            "architecture": "llama",
            "details": {
                "layer_count": {"value": layers, "evidence": "observed"},
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


def host(
    *,
    ram_available: int | None = 32 * GiB,
    gpu_free: int | None = 8 * GiB,
) -> dict:
    gpus = []
    if gpu_free is not None:
        gpus = [
            {
                "name": "Test GPU",
                "memory_total_bytes": 16 * GiB,
                "memory_free_bytes": gpu_free,
                "memory_used_bytes": max(0, 16 * GiB - gpu_free),
            }
        ]
    memory: dict = {"physical_total_bytes": 64 * GiB, "evidence": "observed"}
    if ram_available is not None:
        memory["available_bytes"] = ram_available
    else:
        memory["evidence"] = "unknown"
    return {
        "schema_version": 1,
        "captured_at": "2026-11-07T00:00:00+00:00",
        "system_memory": memory,
        "gpus": gpus,
        "gpu_discovery": {
            "status": "available" if gpus else "unavailable",
            "evidence": "observed" if gpus else "unknown",
        },
        "storage": {"free_bytes": 500 * GiB, "evidence": "observed"},
    }


class PlacementRequestTests(unittest.TestCase):
    def test_invalid_requests_are_rejected(self) -> None:
        with self.assertRaises(PlacementError):
            PlacementRequest(sequence_slots=0)
        with self.assertRaises(PlacementError):
            PlacementRequest(kv_cache_dtype="f8")
        with self.assertRaises(PlacementError):
            PlacementRequest(mode="turbo")
        with self.assertRaises(PlacementError):
            PlacementRequest(allocation_overhead_fraction=0.75)
        with self.assertRaises(PlacementError):
            PlacementRequest(max_gpu_layers=-2)
        with self.assertRaises(PlacementError):
            PlacementRequest(context_tokens=0)


class PlacementPlannerTests(unittest.TestCase):
    def test_full_gpu_offload_when_vram_fits(self) -> None:
        plan = plan_placement(atlas(), host(gpu_free=12 * GiB))
        self.assertEqual(plan["status"], "planned_gpu_full_offload")
        assignment = plan["assignment"]
        self.assertEqual(assignment["gpu_layers"], 32)
        self.assertEqual(assignment["cpu_layers"], 0)
        self.assertTrue(assignment["fits_known_budget"])
        self.assertEqual(plan["executable"]["argv_fragment"], ["--n-gpu-layers", "32"])
        self.assertFalse(plan["runtime_verified"])
        self.assertFalse(plan["executable"]["runtime_verified"])

    def test_hybrid_plan_uses_the_most_layers_that_fit_both_budgets(self) -> None:
        plan = plan_placement(atlas(), host(gpu_free=8 * GiB))
        self.assertEqual(plan["status"], "planned_hybrid")
        assignment = plan["assignment"]
        layers = assignment["gpu_layers"]
        self.assertIsInstance(layers, int)
        self.assertGreater(layers, 0)
        self.assertLess(layers, 32)
        self.assertLessEqual(assignment["estimated_peak_vram_bytes"], assignment["vram_usable_bytes"])
        self.assertLessEqual(assignment["estimated_peak_ram_bytes"], assignment["ram_usable_bytes"])
        self.assertEqual(plan["executable"]["gpu_layers"], layers)
        # One more layer must not fit the observed VRAM budget, otherwise the
        # planner did not choose the largest feasible split.
        vram_usable = assignment["vram_usable_bytes"]
        per_layer = plan["per_layer_estimate"]["total_bytes"]
        overhead = plan["request"]["allocation_overhead_fraction"]
        self.assertGreater((layers + 1) * per_layer * (1 + overhead), vram_usable)

    def test_cpu_mode_is_explicit_and_only_needs_ram(self) -> None:
        plan = plan_placement(atlas(), host(gpu_free=None), PlacementRequest(mode="cpu"))
        self.assertEqual(plan["status"], "planned_cpu_only")
        self.assertEqual(plan["assignment"]["gpu_layers"], 0)
        self.assertEqual(plan["executable"]["argv_fragment"], ["--n-gpu-layers", "0"])
        self.assertEqual(plan["assignment"]["estimated_peak_vram_bytes"], 0)

    def test_gpu_mode_reports_a_shortfall_and_a_hybrid_fallback(self) -> None:
        plan = plan_placement(atlas(), host(gpu_free=8 * GiB), PlacementRequest(mode="gpu"))
        self.assertEqual(plan["status"], "exceeds_known_budget")
        self.assertIsNone(plan["assignment"]["gpu_layers"])
        self.assertFalse(plan["assignment"]["fits_known_budget"])
        self.assertEqual(plan["executable"]["argv_fragment"], [])
        fallback = plan["fallback_assignment"]
        self.assertIsNotNone(fallback)
        self.assertGreater(fallback["gpu_layers"], 0)
        self.assertGreater(plan["shortfall"]["gpu_memory"]["shortfall_bytes"], 0)

    def test_auto_without_an_observed_gpu_is_cpu_only(self) -> None:
        plan = plan_placement(atlas(), host(gpu_free=None))
        self.assertEqual(plan["status"], "planned_cpu_only_no_gpu_observed")
        self.assertEqual(plan["assignment"]["gpu_layers"], 0)
        self.assertEqual(plan["executable"]["argv_fragment"], ["--n-gpu-layers", "0"])
        self.assertTrue(any("No GPU" in warning for warning in plan["warnings"]))

    def test_explicit_gpu_mode_without_an_observed_gpu_declines_to_plan(self) -> None:
        plan = plan_placement(atlas(), host(gpu_free=None), PlacementRequest(mode="gpu"))
        self.assertEqual(plan["status"], "unknown_host_budget")
        self.assertIsNone(plan["assignment"]["gpu_layers"])
        self.assertEqual(plan["executable"]["argv_fragment"], [])

    def test_missing_architecture_facts_produce_no_layer_count(self) -> None:
        plan = plan_placement(atlas(layers=None), host())
        self.assertEqual(plan["status"], "unknown_missing_model_facts")
        self.assertIsNone(plan["assignment"]["gpu_layers"])
        self.assertIsNone(plan["per_layer_estimate"]["weight_bytes"])
        self.assertEqual(plan["executable"]["argv_fragment"], [])

    def test_incomplete_weight_storage_produces_no_layer_count(self) -> None:
        plan = plan_placement(atlas(complete=False), host())
        self.assertEqual(plan["status"], "unknown_missing_model_facts")
        self.assertIsNone(plan["input_evidence"]["weight_storage"]["bytes"])

    def test_unobserved_ram_produces_no_layer_count(self) -> None:
        plan = plan_placement(atlas(), host(ram_available=None))
        self.assertEqual(plan["status"], "unknown_host_budget")
        self.assertIsNone(plan["assignment"]["gpu_layers"])

    def test_max_gpu_layers_caps_the_plan(self) -> None:
        plan = plan_placement(
            atlas(),
            host(gpu_free=12 * GiB),
            PlacementRequest(mode="auto", max_gpu_layers=8),
        )
        self.assertEqual(plan["status"], "planned_hybrid")
        self.assertEqual(plan["assignment"]["gpu_layers"], 8)

    def test_gpu_mode_respects_a_cap_and_reports_a_hybrid_plan(self) -> None:
        plan = plan_placement(
            atlas(),
            host(gpu_free=12 * GiB),
            PlacementRequest(mode="gpu", max_gpu_layers=8),
        )
        self.assertEqual(plan["status"], "planned_hybrid")
        self.assertEqual(plan["assignment"]["gpu_layers"], 8)
        self.assertTrue(any("cap" in warning for warning in plan["warnings"]))

    def test_quantized_kv_cache_lowers_the_estimate(self) -> None:
        f16 = plan_placement(atlas(), host(), PlacementRequest(kv_cache_dtype="f16"))
        q4 = plan_placement(atlas(), host(), PlacementRequest(kv_cache_dtype="q4_0"))
        f16_kv = f16["input_evidence"]["kv_cache"]["bytes"]
        q4_kv = q4["input_evidence"]["kv_cache"]["bytes"]
        self.assertIsNotNone(f16_kv)
        self.assertIsNotNone(q4_kv)
        self.assertLess(q4_kv, f16_kv)
        self.assertAlmostEqual(q4_kv / f16_kv, 18 / 64, places=3)

    def test_context_override_changes_the_estimate(self) -> None:
        short = plan_placement(atlas(), host(), PlacementRequest(context_tokens=4096))
        long = plan_placement(atlas(), host(), PlacementRequest(context_tokens=8192))
        self.assertGreater(
            long["input_evidence"]["kv_cache"]["bytes"],
            short["input_evidence"]["kv_cache"]["bytes"],
        )
        self.assertEqual(short["request"]["context_source"], "user_requested")


class PlacementReconciliationTests(unittest.TestCase):
    def test_reconciliation_compares_observed_ram_and_reports_vram_unavailable(self) -> None:
        plan = plan_placement(atlas(), host())
        estimate = plan["assignment"]["estimated_peak_ram_bytes"]
        result = reconcile_placement(
            plan,
            {
                "peak_process_resident_bytes": estimate - MiB,
                "minimum_host_available_bytes": 20 * GiB,
                "peak_gpu_memory_used_bytes": None,
                "sample_count": 4,
                "source": "test sampler",
            },
        )
        self.assertEqual(result["format"], "eclipse_placement_reconciliation")
        self.assertEqual(result["verdict"], "measured_no_larger_than_estimate")
        ram = result["dimensions"]["system_memory"]
        self.assertEqual(ram["verdict"], "observed_within_estimate")
        self.assertEqual(ram["evidence"], "observed")
        vram = result["dimensions"]["gpu_memory"]
        self.assertEqual(vram["verdict"], "unavailable")
        self.assertIsNone(vram["observed_peak_gpu_memory_used_bytes"])
        self.assertFalse(result["runtime_verified"])

    def test_reconciliation_flags_an_observed_excess(self) -> None:
        plan = plan_placement(atlas(), host())
        estimate = plan["assignment"]["estimated_peak_ram_bytes"]
        result = reconcile_placement(
            plan,
            {"peak_process_resident_bytes": estimate * 3, "sample_count": 2},
        )
        self.assertEqual(result["verdict"], "measured_above_estimate")
        self.assertEqual(
            result["dimensions"]["system_memory"]["verdict"], "observed_above_estimate"
        )
        self.assertGreater(result["dimensions"]["system_memory"]["excess_bytes"], 0)

    def test_reconciliation_without_a_plan_is_unavailable(self) -> None:
        result = reconcile_placement(None, {"peak_process_resident_bytes": 1024})
        self.assertEqual(result["verdict"], "unavailable")
        self.assertFalse(result["runtime_verified"])

    def test_summary_is_compact_and_never_verified(self) -> None:
        summary = summarize_placement(plan_placement(atlas(), host()))
        assert summary is not None
        self.assertEqual(summary["format"], "eclipse_placement_plan")
        self.assertFalse(summary["runtime_verified"])
        self.assertNotIn("warnings", summary)
        self.assertIsNone(summarize_placement(None))


class ProfilePlacementIntegrationTests(unittest.TestCase):
    def test_resolve_profile_uses_the_planner_when_no_layers_are_pinned(self) -> None:
        spec = resolve_profile(
            intent="balanced",
            backend="llamacpp_server",
            atlas=atlas(),
            host=host(),
        )
        self.assertIn(spec.gpu_layers, range(0, 33))
        self.assertIsNotNone(spec.placement)
        assert spec.placement is not None
        self.assertFalse(spec.placement["runtime_verified"])
        self.assertIn("placement planner", spec.rationale.lower())
        self.assertEqual(spec.placement["status"], "planned_hybrid")

    def test_auto_intent_without_a_gpu_resolves_to_zero_layers(self) -> None:
        spec = resolve_profile(
            intent="auto",
            backend="llamacpp_server",
            atlas=atlas(),
            host=host(gpu_free=None),
        )
        self.assertEqual(spec.gpu_layers, 0)
        self.assertEqual(spec.placement_mode, "auto")

    def test_an_explicit_layer_override_wins_over_the_planner(self) -> None:
        spec = resolve_profile(
            intent="balanced",
            backend="llamacpp_server",
            atlas=atlas(),
            host=host(),
            overrides={"gpu_layers": 3},
        )
        self.assertEqual(spec.gpu_layers, 3)
        self.assertIsNone(spec.placement)

    def test_placement_mode_is_validated_and_persisted(self) -> None:
        spec = resolve_profile(
            intent="balanced",
            backend="llamacpp_server",
            atlas=atlas(),
            host=host(),
            overrides={"placement_mode": "cpu"},
        )
        self.assertEqual(spec.placement_mode, "cpu")
        payload = spec.to_payload()
        self.assertEqual(payload["placement_mode"], "cpu")
        rebuilt = ProfileSpec.from_payload(payload)
        self.assertEqual(rebuilt.placement_mode, "cpu")
        self.assertEqual(rebuilt.gpu_layers, 0)
        with self.assertRaises(ValueError):
            resolve_profile(
                intent="balanced",
                backend="llamacpp_server",
                overrides={"placement_mode": "turbo"},
            )

    def test_old_profiles_without_placement_fields_still_load(self) -> None:
        legacy = ProfileSpec.from_payload(
            {
                "backend": "llamacpp_server",
                "intent": "balanced",
                "context_tokens": 2048,
                "gpu_layers": 0,
            }
        )
        self.assertEqual(legacy.placement_mode, "auto")
        self.assertIsNone(legacy.placement)


class PlacementCliTests(unittest.TestCase):
    def test_placement_command_emits_a_plan_document(self) -> None:
        from eclipse.__main__ import main

        with tempfile.TemporaryDirectory() as temp:
            model_path = Path(temp) / "model.gguf"
            model_path.write_bytes(build_gguf([("blk.0.weight", (4, 8), 0, 0)]))
            buffer = StringIO()
            with redirect_stdout(buffer):
                code = main(["--home", str(Path(temp) / "home"), "placement", str(model_path), "--compact"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["format"], "eclipse_placement_plan")
        self.assertFalse(payload["runtime_verified"])
        self.assertIn("assignment", payload)
        for mode in PLACEMENT_INTENTS:
            self.assertIn(mode, PLACEMENT_INTENTS)


if __name__ == "__main__":
    unittest.main()
