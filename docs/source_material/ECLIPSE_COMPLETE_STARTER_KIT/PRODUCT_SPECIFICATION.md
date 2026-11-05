# ECLIPSE Product Specification

## 1. Product statement

ECLIPSE is a single, Windows-first desktop application that combines two original technical workstreams—(A) model intelligence/inference engineering and (B) capability amplification around local AI—with a third everyday conversational Agent workspace. The three workspaces share one Core, registry, memory, hardware services, tool permissions, diagnostics and benchmarks.

The product must serve both beginners and advanced users. Beginners see clear workflows and plain-language status. Advanced users can inspect architecture details, tensor maps, runtime telemetry and experiment manifests when they choose to open those details.

## 2. Primary workspaces

### Workspace 1 — Model Intelligence & Inference Platform

Purpose: investigate, prepare, transform, optimize and run compatible AI models.

Capabilities:
- Import/open supported checkpoint formats and model folders.
- Static inspection without inference.
- Model Atlas and tensor inventory.
- Architecture discovery and unknown-field reporting.
- Hardware feasibility and compatibility estimates.
- Reversible/lossless preparation and integrity verification.
- Compression/transformation experiments.
- Model lineage/provenance and manifests.
- Predictive expert/weight prefetch research.
- Runtime/backend adapters and model profiles.
- Resource Manager/Guardian and safe stop.
- Benchmarks for speed, memory and quality.

### Workspace 2 — Capability Amplification & Knowledge System

Purpose: make connected local models more useful and reliable through externalized intelligence.

Capabilities:
- Capability Watchdog and fast/enhanced task paths.
- Task planning, acceptance criteria and dependency tracking.
- Research and version-correct documentation retrieval.
- Project understanding and context selection.
- Task-scoped tools and execution.
- Verification, recovery, loop detection and plan-drift handling.
- Verified correction memory and specialized skills.
- Obsidian integration and human-readable knowledge.
- Baseline comparisons and capability reports.

### Workspace 3 — ECLIPSE Agent

Purpose: provide the daily ChatGPT/Claude-like conversation and task execution experience.

Capabilities:
- Chat with any connected compatible model.
- Model picker and seamless adapter-level switching where possible.
- Streaming, conversation history, titles, search and organization.
- File/document/image inputs supported by the selected model/runtime.
- Project/workspace context.
- Persistent memory.
- Code creation/editing, sandboxed code execution and terminal tasks.
- Web research where tools and permission allow.
- GitHub operations.
- Multi-step task planning and progress reporting.
- Calls into Workspace 1 and Workspace 2.
- Artifact generation and verified completion reports.

Agent capability must be honestly bounded by the selected model, backend and enabled integrations. Do not claim parity with another product unless each capability exists and has been tested.

## 3. Shared ECLIPSE Core

Shared services include:
- Model registry and adapter interfaces.
- Model metadata/provenance and transformation lineage.
- Hardware profiler and resource budget manager.
- Context/retrieval service.
- Memory/knowledge service.
- Planning/orchestration service.
- Tool registry and permission broker.
- Sandboxed execution service.
- Verification and recovery service.
- Diagnostics/logging with secret redaction.
- Benchmark/evaluation harness.
- User preferences and theme/accessibility settings.

## 4. Internal model-engineering subsystems from the original Master Plan

The source PDF explicitly lists five major technical subsystems. Preserve all five:

1. Model Intelligence Laboratory — inspect models and discover architecture, tensor inventory, precision, routing structure and constraints without full inference.
2. Model Preparation and Optimization — prepare model packages and experiment with reproducible transformations, compression and optimization.
3. High-Speed Inference Engine — coordinate CPU, GPU, RAM, VRAM, SSD and supported runtimes.
4. Intelligence Preservation and Recovery — NECS research, correction/sidecar experiments, capability watchdog and verification. Keep model-level NECS separate from agent correction memory.
5. ECLIPSE Desktop and Resource Manager — Windows UI, profiles, resource controls, monitoring, logs and diagnostics.

## 5. Model Atlas evidence levels

Every Atlas field should identify whether it is:
- Observed directly from checkpoint metadata/headers.
- Derived mathematically from observed data.
- Taken from published model documentation.
- Estimated from a documented formula or hardware profile.
- Hypothesized/unknown.

Do not claim static metadata proves workload routing frequency, semantic expert specialization or model behavior unless suitable evidence exists.

## 6. Predictive runtime principle

Investigate predictive selection/prefetch of already-existing experts or weight blocks. The model's true router selection remains authoritative. Prediction can stage likely experts, but cannot substitute an unselected expert as though it were the model's actual decision. Measure useful prefetch value, cache hits, bytes moved, latency saved, quality equivalence and overhead.

For dense models, investigate layer streaming and prefetch. Keep the fast path focused on keeping the active hot working set in the fastest memory tier; SSD residency is not equivalent to VRAM/RAM residency.

## 7. Transformation lineage

Every derived model must retain:
- Source model identity and cryptographic hash.
- Source provenance/license.
- Transformation method and parameters.
- Tool/library versions.
- Calibration/teacher data details when applicable, with privacy checks.
- Output hash and manifest.
- File-level integrity validation.
- Evaluation results and quality trade-offs.
- Rollback path to the untouched source.

## 8. Non-goals and boundaries

- Do not promise impossible size reductions or zero-loss compression.
- Do not claim agent scaffolding literally increases model parameter count.
- Do not require large-model inference for static inspection.
- Do not treat NECS as proven or mandatory.
- Do not execute untrusted downloaded model code.
- Do not require paid APIs or cloud inference for the core product.
- Do not require Linux/WSL for core Windows workflows.
- Do not expose every technical metric on the default UI.
