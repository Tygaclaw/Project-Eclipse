from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import unittest

from eclipse.core.runtime import (
    BackendCapabilities,
    ControlSupport,
    DeviceSupport,
    RuntimeContractError,
    evaluate_controls,
    evaluate_model_support,
)


CPU_DEVICE = DeviceSupport(kind="cpu", api="cpu")
CUDA_DEVICE = DeviceSupport(kind="gpu", api="cuda")


def capabilities(**overrides) -> BackendCapabilities:
    values = {
        "backend_id": "test-backend",
        "display_name": "Test Backend",
        "integration_status": "integrated",
        "model_formats": frozenset({"gguf"}),
        "architectures": frozenset({"llama"}),
        "quantization_types": frozenset({"f16", "q4_k"}),
        "devices": (CPU_DEVICE,),
        "placement_modes": frozenset({"cpu_only"}),
        "controls": {
            "context_length": ControlSupport(supported=True, requires_restart=True),
            "gpu_layer_offload": ControlSupport(supported=False),
        },
        "telemetry": frozenset({"process_state"}),
        "max_context_tokens": 32768,
    }
    values.update(overrides)
    return BackendCapabilities(**values)


def atlas(
    *,
    source_kind: str = "gguf",
    architecture: str | None = "llama",
    counts: dict | None = None,
) -> dict:
    return {
        "format": "eclipse_model_atlas",
        "atlas_version": 1,
        "source_kind": source_kind,
        "source_name": "test-model.gguf",
        "architecture": {"architecture": architecture, "evidence": "observed"},
        "summary": {
            "distribution": {"label": "ggml_type", "counts": counts if counts is not None else {"F16": 4}},
        },
    }


def host(*, gpu_vendor: str | None = None) -> dict:
    gpus = []
    if gpu_vendor is not None:
        gpus.append({"vendor": gpu_vendor, "name": "Test GPU"})
    return {"schema_version": 1, "gpus": gpus}


class CapabilityContractTests(unittest.TestCase):
    def test_to_dict_and_from_dict_round_trip(self) -> None:
        original = capabilities()
        restored = BackendCapabilities.from_dict(original.to_dict())
        self.assertEqual(restored, original)
        self.assertEqual(restored.controls["context_length"].requires_restart, True)
        self.assertEqual(restored.architectures, frozenset({"llama"}))

    def test_from_dict_normalizes_case_and_accepts_boolean_control(self) -> None:
        restored = BackendCapabilities.from_dict(
            {
                "backend_id": "b",
                "display_name": "B",
                "model_formats": ["GGUF"],
                "architectures": ["LLaMA"],
                "devices": [{"kind": "GPU", "api": "Vulkan"}],
                "placement_modes": ["Hybrid"],
                "controls": {"flash_attention": True},
                "telemetry": ["VRAM_Usage"],
            }
        )
        self.assertEqual(restored.model_formats, frozenset({"gguf"}))
        self.assertEqual(restored.architectures, frozenset({"llama"}))
        self.assertEqual(restored.devices[0].api, "vulkan")
        self.assertEqual(restored.controls["flash_attention"], ControlSupport(supported=True))

    def test_from_dict_rejects_unknown_fields(self) -> None:
        with self.assertRaises(RuntimeContractError) as caught:
            BackendCapabilities.from_dict(
                {"backend_id": "b", "display_name": "B", "mystery": 1}
            )
        self.assertIn("unknown capability field", str(caught.exception))

    def test_from_dict_rejects_non_list_devices(self) -> None:
        with self.assertRaises(RuntimeContractError):
            BackendCapabilities.from_dict({"backend_id": "b", "display_name": "B", "devices": "cpu"})

    def test_requires_at_least_one_device_and_format_and_placement(self) -> None:
        with self.assertRaises(RuntimeContractError):
            capabilities(devices=())
        with self.assertRaises(RuntimeContractError):
            capabilities(model_formats=frozenset())
        with self.assertRaises(RuntimeContractError):
            capabilities(placement_modes=frozenset())

    def test_rejects_invalid_tokens(self) -> None:
        with self.assertRaises(RuntimeContractError):
            capabilities(model_formats=frozenset({"onnx"}))
        with self.assertRaises(RuntimeContractError):
            capabilities(placement_modes=frozenset({"magic"}))
        with self.assertRaises(RuntimeContractError):
            capabilities(telemetry=frozenset({"vibes"}))
        with self.assertRaises(RuntimeContractError):
            capabilities(controls={"warp_drive": ControlSupport()})

    def test_rejects_invalid_identity_and_status(self) -> None:
        with self.assertRaises(RuntimeContractError):
            capabilities(backend_id="  ")
        with self.assertRaises(RuntimeContractError):
            capabilities(display_name="")
        with self.assertRaises(RuntimeContractError):
            capabilities(integration_status="maybe")

    def test_rejects_invalid_max_context(self) -> None:
        with self.assertRaises(RuntimeContractError):
            capabilities(max_context_tokens=0)
        with self.assertRaises(RuntimeContractError):
            capabilities(max_context_tokens=True)

    def test_device_validation(self) -> None:
        with self.assertRaises(RuntimeContractError):
            DeviceSupport(kind="cpu", api="cuda")
        with self.assertRaises(RuntimeContractError):
            DeviceSupport(kind="gpu", api="cpu")
        with self.assertRaises(RuntimeContractError):
            DeviceSupport(kind="tpu", api="cuda")
        with self.assertRaises(RuntimeContractError):
            DeviceSupport(kind="gpu", api="cuda", evidence="guessed")


class SupportMatrixTests(unittest.TestCase):
    def test_supported_format_when_integrated_is_declared_compatible(self) -> None:
        result = evaluate_model_support(capabilities(), atlas(), host())
        self.assertEqual(result["dimensions"]["format"]["status"], "declared_supported")
        self.assertEqual(result["overall_status"], "declared_compatible_not_runtime_verified")
        self.assertFalse(result["runtime_verified"])

    def test_unsupported_format_dominates_overall(self) -> None:
        result = evaluate_model_support(
            capabilities(model_formats=frozenset({"safetensors"})), atlas(), host()
        )
        self.assertEqual(result["dimensions"]["format"]["status"], "unsupported")
        self.assertEqual(result["overall_status"], "unsupported")

    def test_unknown_format_is_reported_unknown(self) -> None:
        result = evaluate_model_support(capabilities(), atlas(source_kind="unknown_kind"), host())
        self.assertEqual(result["dimensions"]["format"]["status"], "unknown")
        self.assertIsNone(result["model"]["model_format"])

    def test_not_integrated_backend_never_reports_declared_compatible(self) -> None:
        result = evaluate_model_support(
            capabilities(integration_status="not_integrated"), atlas(), host()
        )
        self.assertEqual(result["overall_status"], "not_integrated")

    def test_architecture_supported_unsupported_and_unknown(self) -> None:
        supported = evaluate_model_support(capabilities(), atlas(), host())
        self.assertEqual(supported["dimensions"]["architecture"]["status"], "declared_supported")

        unsupported = evaluate_model_support(
            capabilities(architectures=frozenset({"mistral"})), atlas(), host()
        )
        self.assertEqual(unsupported["dimensions"]["architecture"]["status"], "unsupported")

        undeclared = evaluate_model_support(
            capabilities(architectures=None), atlas(), host()
        )
        self.assertEqual(undeclared["dimensions"]["architecture"]["status"], "unknown")

        absent = evaluate_model_support(capabilities(), atlas(architecture=None), host())
        self.assertEqual(absent["dimensions"]["architecture"]["status"], "unknown")

    def test_quantization_supported_unsupported_and_unknown(self) -> None:
        supported = evaluate_model_support(capabilities(), atlas(), host())
        self.assertEqual(supported["dimensions"]["quantization"]["status"], "declared_supported")

        unsupported = evaluate_model_support(
            capabilities(quantization_types=frozenset({"f16"})),
            atlas(counts={"Q4_K": 4}),
            host(),
        )
        self.assertEqual(unsupported["dimensions"]["quantization"]["status"], "unsupported")
        self.assertEqual(
            unsupported["dimensions"]["quantization"]["unsupported_types"], ["q4_k"]
        )

        unknown = evaluate_model_support(capabilities(quantization_types=None), atlas(), host())
        self.assertEqual(unknown["dimensions"]["quantization"]["status"], "unknown")

        none_observed = evaluate_model_support(capabilities(), atlas(counts={}), host())
        self.assertEqual(none_observed["dimensions"]["quantization"]["status"], "unknown")

    def test_cpu_device_is_declared_supported(self) -> None:
        result = evaluate_model_support(capabilities(), atlas(), host())
        self.assertEqual(result["dimensions"]["devices"]["status"], "declared_supported")

    def test_cuda_device_with_nvidia_hardware_is_unvalidated(self) -> None:
        result = evaluate_model_support(
            capabilities(devices=(CUDA_DEVICE,)), atlas(), host(gpu_vendor="nvidia")
        )
        self.assertEqual(
            result["dimensions"]["devices"]["status"], "hardware_present_backend_unvalidated"
        )
        self.assertEqual(result["overall_status"], "unknown")

    def test_cuda_device_without_nvidia_is_unsupported(self) -> None:
        result = evaluate_model_support(
            capabilities(devices=(CUDA_DEVICE,)), atlas(), host(gpu_vendor="amd")
        )
        self.assertEqual(result["dimensions"]["devices"]["status"], "unsupported")
        self.assertEqual(result["overall_status"], "unsupported")

    def test_vulkan_device_with_gpu_is_unknown(self) -> None:
        result = evaluate_model_support(
            capabilities(devices=(DeviceSupport(kind="gpu", api="vulkan"),)),
            atlas(),
            host(gpu_vendor="nvidia"),
        )
        self.assertEqual(result["dimensions"]["devices"]["status"], "unknown")

    def test_missing_host_snapshot_leaves_gpu_unknown(self) -> None:
        result = evaluate_model_support(capabilities(devices=(CUDA_DEVICE,)), atlas(), None)
        self.assertEqual(result["dimensions"]["devices"]["status"], "unknown")

    def test_placement_mode_checks(self) -> None:
        supported = evaluate_model_support(
            capabilities(placement_modes=frozenset({"cpu_only", "hybrid"})),
            atlas(),
            host(),
            placement_mode="hybrid",
        )
        self.assertEqual(supported["dimensions"]["placement"]["status"], "declared_supported")

        unsupported = evaluate_model_support(
            capabilities(placement_modes=frozenset({"cpu_only"})),
            atlas(),
            host(),
            placement_mode="gpu_offload",
        )
        self.assertEqual(unsupported["dimensions"]["placement"]["status"], "unsupported")

    def test_controls_report_supported_unsupported_and_restart(self) -> None:
        controls = evaluate_controls(
            capabilities(),
            {"context_length": 8192, "gpu_layer_offload": 33, "warp_drive": 1},
        )
        self.assertEqual(controls["context_length"]["status"], "declared_supported")
        self.assertTrue(controls["context_length"]["requires_restart"])
        self.assertEqual(controls["gpu_layer_offload"]["status"], "unsupported")
        self.assertEqual(controls["warp_drive"]["status"], "unknown")

    def test_evaluate_model_support_includes_controls(self) -> None:
        result = evaluate_model_support(
            capabilities(), atlas(), host(), requested_controls={"context_length": 4096}
        )
        self.assertIn("context_length", result["controls"])

    def test_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(RuntimeContractError):
            evaluate_model_support(capabilities(), {"format": "not_atlas"}, host())
        with self.assertRaises(RuntimeContractError):
            evaluate_model_support("not a backend", atlas(), host())
        with self.assertRaises(RuntimeContractError):
            evaluate_model_support(capabilities(), atlas(), host="not a snapshot")
        with self.assertRaises(RuntimeContractError):
            evaluate_controls(capabilities(), "not a mapping")


if __name__ == "__main__":
    unittest.main()
