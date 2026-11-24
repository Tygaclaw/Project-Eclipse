"""Unit coverage for the static model/backend support matrix.

``evaluate_model_support`` and ``evaluate_controls`` in
``eclipse.runtime.backends`` produce the evidence-labelled compatibility report
behind the ``runtime-support`` CLI. The CLI path is covered by
``tests/test_app_cli.py``; these tests exercise the report's dimensions directly
so unsupported and unknown results can never be silently presented as supported.
The report is a declaration comparison only, so ``runtime_verified`` must stay
``False``.
"""

from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import unittest

from eclipse.runtime.backends import (
    BackendError,
    BackendUnsupported,
    BackendCapabilities,
    backend_capabilities,
    evaluate_controls,
    evaluate_model_support,
    support_matrix_report,
)


def capabilities(**overrides) -> BackendCapabilities:
    values = {
        "key": "test_backend",
        "display_name": "Test Backend",
        "connection_modes": ("managed_process",),
        "formats": ("gguf",),
        "architectures": ("llama",),
        "quantizations": ("F16", "Q4_K_M"),
        "devices": ("cpu",),
        "placement_modes": ("cpu",),
        "streaming": True,
        "tool_calling": False,
        "context_control": True,
        "kv_cache_dtypes": ("f16",),
        "parallel_slots": False,
        "telemetry": ("stream_timing",),
        "ownership": "eclipse",
    }
    values.update(overrides)
    return BackendCapabilities(**values)


def atlas(
    *,
    source_kind: str | None = "gguf",
    architecture: str | None = "llama",
    counts: dict | None = None,
) -> dict:
    return {
        "source_kind": source_kind,
        "architecture": {"architecture": architecture, "evidence": "observed"},
        "summary": {
            "distribution": {
                "label": "ggml_type",
                "counts": counts if counts is not None else {"F16": 4},
            }
        },
    }


def host(*, gpu_vendor: str | None = None) -> dict:
    gpus = []
    if gpu_vendor is not None:
        gpus.append({"vendor": gpu_vendor, "name": "Test GPU"})
    return {"gpus": gpus}


class FormatDimensionTests(unittest.TestCase):
    def test_supported_format_is_declared_and_not_runtime_verified(self) -> None:
        result = evaluate_model_support(capabilities(), atlas(), host())
        self.assertEqual(result["format"], "eclipse_runtime_support")
        self.assertEqual(result["dimensions"]["format"]["status"], "declared_supported")
        self.assertEqual(result["overall_status"], "declared_compatible_not_runtime_verified")
        self.assertFalse(result["runtime_verified"])

    def test_unsupported_format_dominates_overall(self) -> None:
        result = evaluate_model_support(capabilities(formats=("safetensors",)), atlas(), host())
        self.assertEqual(result["dimensions"]["format"]["status"], "unsupported")
        self.assertEqual(result["overall_status"], "unsupported")

    def test_missing_source_kind_is_unknown(self) -> None:
        result = evaluate_model_support(capabilities(), atlas(source_kind=None), host())
        self.assertEqual(result["dimensions"]["format"]["status"], "unknown")
        self.assertIsNone(result["dimensions"]["format"]["model_format"])


class ArchitectureDimensionTests(unittest.TestCase):
    def test_supported_unsupported_and_unknown(self) -> None:
        supported = evaluate_model_support(capabilities(), atlas(), host())
        self.assertEqual(supported["dimensions"]["architecture"]["status"], "declared_supported")

        unsupported = evaluate_model_support(
            capabilities(architectures=("mistral",)), atlas(), host()
        )
        self.assertEqual(unsupported["dimensions"]["architecture"]["status"], "unsupported")

        undeclared = evaluate_model_support(capabilities(architectures=None), atlas(), host())
        self.assertEqual(undeclared["dimensions"]["architecture"]["status"], "unknown")

        absent = evaluate_model_support(capabilities(), atlas(architecture=None), host())
        self.assertEqual(absent["dimensions"]["architecture"]["status"], "unknown")


class QuantizationDimensionTests(unittest.TestCase):
    def test_supported_unsupported_and_unknown(self) -> None:
        supported = evaluate_model_support(capabilities(), atlas(), host())
        self.assertEqual(supported["dimensions"]["quantization"]["status"], "declared_supported")

        unsupported = evaluate_model_support(
            capabilities(quantizations=("F16",)), atlas(counts={"Q4_K": 4}), host()
        )
        self.assertEqual(unsupported["dimensions"]["quantization"]["status"], "unsupported")
        self.assertEqual(unsupported["dimensions"]["quantization"]["unsupported_types"], ["Q4_K"])

        undeclared = evaluate_model_support(capabilities(quantizations=None), atlas(), host())
        self.assertEqual(undeclared["dimensions"]["quantization"]["status"], "unknown")

        none_observed = evaluate_model_support(capabilities(), atlas(counts={}), host())
        self.assertEqual(none_observed["dimensions"]["quantization"]["status"], "unknown")


class DeviceDimensionTests(unittest.TestCase):
    def test_cpu_is_declared_supported(self) -> None:
        result = evaluate_model_support(capabilities(devices=("cpu",)), atlas(), host())
        self.assertEqual(result["dimensions"]["devices"]["status"], "declared_supported")

    def test_cuda_with_nvidia_hardware_is_unvalidated(self) -> None:
        result = evaluate_model_support(
            capabilities(devices=("cuda",)), atlas(), host(gpu_vendor="nvidia")
        )
        self.assertEqual(
            result["dimensions"]["devices"]["status"], "hardware_present_backend_unvalidated"
        )
        self.assertEqual(result["overall_status"], "unknown")

    def test_cuda_without_any_gpu_is_unsupported(self) -> None:
        result = evaluate_model_support(capabilities(devices=("cuda",)), atlas(), host())
        self.assertEqual(result["dimensions"]["devices"]["status"], "unsupported")
        self.assertEqual(result["overall_status"], "unsupported")

    def test_cuda_with_non_nvidia_gpu_is_unknown(self) -> None:
        result = evaluate_model_support(
            capabilities(devices=("cuda",)), atlas(), host(gpu_vendor="amd")
        )
        self.assertEqual(result["dimensions"]["devices"]["status"], "unknown")

    def test_missing_host_snapshot_leaves_gpu_unknown(self) -> None:
        result = evaluate_model_support(capabilities(devices=("cuda",)), atlas(), None)
        self.assertEqual(result["dimensions"]["devices"]["status"], "unknown")

    def test_remote_backend_is_declared_supported(self) -> None:
        result = evaluate_model_support(capabilities(devices=("remote",)), atlas(), None)
        self.assertEqual(result["dimensions"]["devices"]["status"], "declared_supported")


class PlacementDimensionTests(unittest.TestCase):
    def test_supported_unsupported_and_unknown(self) -> None:
        supported = evaluate_model_support(
            capabilities(placement_modes=("cpu", "hybrid")),
            atlas(),
            host(),
            placement_mode="hybrid",
        )
        self.assertEqual(supported["dimensions"]["placement"]["status"], "declared_supported")

        unsupported = evaluate_model_support(
            capabilities(placement_modes=("cpu",)), atlas(), host(), placement_mode="gpu"
        )
        self.assertEqual(unsupported["dimensions"]["placement"]["status"], "unsupported")

        unknown = evaluate_model_support(
            capabilities(), atlas(), host(), placement_mode="magic"
        )
        self.assertEqual(unknown["dimensions"]["placement"]["status"], "unknown")

    def test_omitted_placement_is_not_evaluated(self) -> None:
        result = evaluate_model_support(capabilities(), atlas(), host())
        self.assertIsNone(result["dimensions"]["placement"])


class ControlTests(unittest.TestCase):
    def test_controls_are_validated_against_the_declaration(self) -> None:
        controls = evaluate_controls(
            capabilities(),
            {"context_tokens": 8192, "gpu_layers": 0, "kv_cache_dtype": "f16", "mystery": 1},
        )
        self.assertEqual(controls["context_tokens"]["status"], "declared_supported")
        self.assertEqual(controls["gpu_layers"]["status"], "unsupported")
        self.assertEqual(controls["kv_cache_dtype"]["status"], "declared_supported")
        self.assertEqual(controls["mystery"]["status"], "unknown")

    def test_llamacpp_declares_gpu_layers_and_extra_args(self) -> None:
        controls = evaluate_controls(
            backend_capabilities("llamacpp_server"), {"gpu_layers": 33, "extra_args": ["--x"]}
        )
        self.assertEqual(controls["gpu_layers"]["status"], "declared_supported")
        self.assertEqual(controls["extra_args"]["status"], "declared_supported")

    def test_controls_are_included_in_the_support_report(self) -> None:
        result = evaluate_model_support(
            capabilities(), atlas(), host(), requested_controls={"context_tokens": 4096}
        )
        self.assertIn("context_tokens", result["controls"])


class InputValidationTests(unittest.TestCase):
    def test_unknown_backend_key_is_rejected(self) -> None:
        with self.assertRaises(BackendUnsupported):
            evaluate_model_support("not-a-backend", atlas(), host())

    def test_non_mapping_atlas_is_rejected(self) -> None:
        with self.assertRaises(BackendError):
            evaluate_model_support(capabilities(), "not an atlas", host())

    def test_non_mapping_host_is_rejected(self) -> None:
        with self.assertRaises(BackendError):
            evaluate_model_support(capabilities(), atlas(), "not a snapshot")

    def test_non_mapping_requested_controls_are_rejected(self) -> None:
        with self.assertRaises(BackendError):
            evaluate_controls(capabilities(), "not a mapping")

    def test_unknown_backend_capabilities_lookup_is_rejected(self) -> None:
        with self.assertRaises(BackendUnsupported):
            backend_capabilities("no-such-backend")


class SupportMatrixReportTests(unittest.TestCase):
    def test_report_lists_both_configured_backends(self) -> None:
        report = support_matrix_report()
        self.assertEqual(report["format"], "eclipse_backend_support_matrix")
        keys = {backend["key"] for backend in report["backends"]}
        self.assertEqual(keys, {"llamacpp_server", "openai_compatible"})

    def test_openai_compatible_declares_unknown_architectures_and_quantizations(self) -> None:
        openai = backend_capabilities("openai_compatible")
        self.assertIsNone(openai.architectures)
        self.assertIsNone(openai.quantizations)
        result = evaluate_model_support(openai, atlas(), None)
        self.assertEqual(result["dimensions"]["architecture"]["status"], "unknown")
        self.assertEqual(result["dimensions"]["quantization"]["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
