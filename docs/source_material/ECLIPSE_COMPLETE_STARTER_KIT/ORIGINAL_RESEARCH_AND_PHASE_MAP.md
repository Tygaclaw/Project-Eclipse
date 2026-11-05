# Original Research and Phase Map

## 1. Important phase-count clarification

The supplied **ECLIPSE v3.0 Master Plan PDF** (25 pages) names:

- Phase 0 — Foundation and hardware profile.
- Phase 1 through Phase 9 — nine numbered core engineering/research stages.
- Phase 10 — Complete ECLIPSE Desktop.

The user's remembered “nine-phase” model-engineering plan therefore corresponds to **Phases 1–9**, bracketed by foundation Phase 0 and desktop completion Phase 10. This exact sequence is preserved below.

The later `ECLIPSE_Unified_Implementation_Handoff.md` expands the integrated roadmap to Phase 0 through Phase 11. That is a separate, more detailed software implementation roadmap, not a replacement for the original nine core stages.

The original Qwen capability discussion also contains a six-step initial approach. Keep it as historical process guidance; do not confuse it with the nine core model-engineering stages.

## 2. Original nine core stages (Master Plan v3.0)

### Phase 1 — Model Intelligence Laboratory

Implement bounded GGUF and Safetensors inspection, config/tokenizer reading, tensor inventory and the first Model Atlas. It must inspect a model too large to run. Peak memory must be bounded and findings must point to the relevant metadata/file offsets.

### Phase 2 — Feasibility and compatibility planner

Estimate storage, RAM/VRAM, KV cache, tensor types, supported operations and possible backends. Produce a plain-language feasibility report. Separate measured, derived and speculative values; do not invent tokens/second predictions.

### Phase 3 — Lossless preparation

Build indexes, manifests, alignment/layout preparation, checksums and safe output packages. Keep the original untouched. Validate reproducibility and file/numerical integrity.

### Phase 4 — First inference foundation

Integrate a proven engine for one supported model and a compatible backend. Test the correct Windows GPU path where supported, or CPU path as appropriate. Record correct output, operator support, speed/latency and resource use.

### Phase 5 — Fast-path optimization

Optimize memory budgets, placement, asynchronous movement, expert residency, prefetch and caching. Require sustained, repeatable gains with no memory thrashing or accuracy loss caused by routing substitution.

### Phase 6 — Runtime model intelligence

Add tracing only where a compatible backend provides reliable activation/router information. Produce observed routing/access statistics and workload profiles. Measure tracing overhead. Missing telemetry must not break basic inference.

### Phase 7 — Advanced compression

Test quantization, mixed precision, sensitivity analysis and structured sparsity. Produce a portfolio of size/speed/quality trade-offs. Compare every method to a baseline and never make unmeasured quality claims.

### Phase 8 — NECS and Capability Watchdog

Prototype optional Neural Error-Correction Sidecars and task-level enhanced verification. Sidecars are experimental; held-out tests must demonstrate actual gains and acceptable speed/memory costs. Keep NECS separate from verified agent correction memory.

### Phase 9 — Externalized intelligence

Add project memory, tools, execution harnesses and verification workflows. Deliver useful coding/debugging workflows with deterministic checks, logs and clear permission/file boundaries.

## 3. Bracketing stages from Master Plan v3.0

### Phase 0 — Foundation and hardware profile

The historical environment audit was completed on 2026-11-04. Do not repeat a generic audit. Record current hardware changes only when needed for a specific test or implementation decision.

### Phase 10 — Complete ECLIPSE Desktop

Polish the Windows UI, profiles, Resource Guardian, model library, import/export, crash recovery, diagnostics, documentation and installation/update/uninstall experience. This stage remains a final integrated acceptance gate, although UI architecture and UX must be planned from the start.

## 4. Expanded integrated roadmap (Unified Implementation Handoff)

This is the implementation roadmap that integrates the original model platform and Qwen capability-amplification system:

| Integrated phase | Scope | Historical state / note |
|---|---|---|
| 0 | Foundation and environment profile | Historical audit completed; targeted checks only when relevant. |
| 1 | Existing Qwen connection | Local model/API was already working; do not reinstall or repeat generic setup. |
| 2 | Baseline evaluation laboratory | A* completed; four other evaluation categories remain. |
| 3 | Static Model Intelligence Laboratory | Build bounded GGUF first, then Safetensors/HF inspection and Model Atlas. |
| 4 | Feasibility, compatibility and lossless preparation | Build reports, manifests, indexes, checksums and reversible preparation. |
| 5 | ECLIPSE agent core | Watchdog, planning, research/context, tools, execution, verification/recovery and correction memory. |
| 6 | Obsidian, persistent knowledge and skills | Scoped retrieval, AI Inbox, verified corrections/skills and human-readable vault. |
| 7 | Advanced reasoning and capability evaluation | Test-time compute scaling, role separation, task-specific skills and measured comparisons. |
| 8 | First inference foundation and fast-path optimization | Proven runtime/backend integration, memory budgets, placement, caching and prefetch. |
| 9 | Runtime model intelligence and advanced compression | Optional tracing, quantization, mixed precision, importance methods and sparsity. |
| 10 | NECS and advanced capability preservation | Experimental sidecars only if controlled testing proves value. |
| 11 | Complete ECLIPSE Desktop | Integrated Windows product, resource guardian, diagnostics, import/export, crash recovery, installation. |

## 5. Mapping the original and integrated roadmaps

- Original Master Phase 1 maps to Integrated Phase 3.
- Original Master Phase 2 and Phase 3 map to Integrated Phase 4.
- Original Master Phase 4 and 5 map to Integrated Phase 8.
- Original Master Phase 6 maps to Integrated Phase 9 (telemetry remains optional).
- Original Master Phase 7 maps to Integrated Phase 9.
- Original Master Phase 8 maps to Integrated Phase 10 plus parts of the verification/watchdog core.
- Original Master Phase 9 maps to Integrated Phases 5, 6 and 7.
- Original Master Phase 10 maps to Integrated Phase 11.
- Original Master Phase 0 and the old Qwen setup are historical foundations; do not repeat them as prerequisites.

The new project must also deliver the three-workspace user experience and the unified model registry/agent connection described in the latest product specification.

## 6. Historical six-step Qwen discussion sequence

The original Qwen discussion proposed:

1. Prove the tool connection.
2. Establish the baseline.
3. Build the ECLIPSE core.
4. Add advanced reasoning workflows.
5. Evaluate and improve.
6. Model-level optimization.

This is a useful high-level narrative for capability amplification, but it is not the nine-stage model-engineering sequence and should not replace the integrated Phase 0–11 roadmap.

## 7. Non-negotiable model-inspection constraint

The Model Intelligence Laboratory, Model Atlas, tensor inventory and initial feasibility analysis must work without full local model inference, activation hooks, runtime tracing or observing live expert calls on the user's PC. Those may be optional later features only where reliable telemetry or authorized external traces exist.
