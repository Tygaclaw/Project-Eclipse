# Integrated ECLIPSE Implementation Roadmap

This roadmap combines the original model-engineering stages, the Qwen capability-amplification system and the new three-workspace desktop requirement. It is a dependency-aware build sequence, not permission to stop after a phase document.

## Workstreams

- **Workstream A — Model Intelligence & Inference Platform:** original model inspection, Atlas, feasibility, preparation, transformation, predictive loading, inference and resource management.
- **Workstream B — Capability Amplification & Knowledge System:** planning, research/context, tools, execution, verification, memory, Watchdog, skills and Obsidian.
- **Workstream C — ECLIPSE Agent and desktop experience:** everyday chat, task execution, model switching, project/file tools, GitHub and access to Workstreams A and B. The desktop UX is designed from day one and integrated throughout; Phase 11 is final productization, not the first time the UI is considered.

## Phase gates

### Phase 0 — Historical foundation (already established)

- Known Windows 11 hardware profile recorded.
- Existing Qwen3.5-9B Q4_K_M local model and API were reported working.
- 256K/262,144-token configuration recorded as preferred historical baseline; temporary 8K diagnostic run is not the preferred profile.
- Obsidian selected.
- A* evaluation completed.

**Gate:** Do not repeat generic audits or setup. Perform only narrow, relevant checks when a new feature requires them.

### Phase 1 — New project control plane and repository

- Verify GitHub connection/account/permissions.
- Create a new private repository, separate from `Tygaclaw/Project-Eclipse`.
- Create `README.md`, `STATUS.md`, `ARCHITECTURE.md`, `CONTINUATION.md`, `DECISIONS.md`, `TESTING.md`, `SECURITY.md`, compatibility and requirements records.
- Establish branches, commit conventions and CI.
- Choose a maintainable Windows-first technology stack using evidence and small technical spikes.

**Gate:** repository and baseline checks genuinely work; no historical repository modified.

### Phase 2 — Requirements, architecture and experience skeleton

- Reconcile all five source documents.
- Finalize the two original system workspaces and the Agent workspace.
- Define Core service interfaces and data contracts.
- Define model registry/adapter contracts, permissions, memory and execution boundaries.
- Establish the colour, typography, spacing, navigation and accessibility system.
- Build only the minimum navigable shell needed to validate architecture, not a huge empty UI scaffold.

**Gate:** architecture decision records, user journeys and an interactive shell with the three primary destinations; no fake functionality claims.

### Phase 3 — Static Model Intelligence Laboratory

- Bounded GGUF metadata/tensor inspection first.
- Safetensors headers/shard indexes and Hugging Face config/tokenizer support next.
- Model Atlas in human-readable and machine-readable formats.
- Evidence levels and source offsets.
- Bounded optional weight-statistics sampling.

**Gate:** inspect a real model too large to execute locally; memory remains bounded; tensors/shards reconcile; original files untouched.

### Phase 4 — Feasibility, compatibility and lossless preparation

- Architecture-aware VRAM/RAM/KV estimates.
- Backend/operator compatibility matrix.
- Plain-language deployment assessment.
- Lossless indexing/manifests/checksums and prepared packages.

**Gate:** clear observed/derived/estimated/unknown labels; integrity validates; no unsupported performance claims.

### Phase 5 — First model runtime and registry

- Integrate one proven supported backend/model path.
- Add model registry lifecycle and adapter interfaces.
- Preserve llama.cpp as a candidate and the historical Qwen configuration.
- Implement safe launch, stop/unload and reproducible run records.

**Gate:** actual inference on a compatible test target; output and resource use recorded; model switching contract works.

### Phase 6 — Capability amplification core

- Capability Watchdog and task routing.
- Planning with dependencies and acceptance criteria.
- Research/context retrieval.
- Task-scoped tool selection.
- Execution and project mapping.
- Verification, recovery, loop detection and correction memory.

**Gate:** real multi-step tool task succeeds with objective checks and evidence-backed completion; safe execution boundaries work.

### Phase 7 — Obsidian, memory and skills

- Scoped vault read/retrieval.
- AI Inbox for proposed material.
- Verified correction/skill promotion.
- Dashboard note and specialized skills.

**Gate:** retrieval is relevant and scoped; approved notes are never silently changed/deleted; only verified lessons become trusted knowledge.

### Phase 8 — Advanced reasoning and benchmarks

- Conditional test-time compute scaling.
- Task-aware planner/implementer/reviewer/tester roles (same-model roles are not represented as separate independent models).
- Specialized skills loaded only when useful.
- Complete four remaining evaluation categories.
- Compare raw Qwen, basic tool loop and full ECLIPSE.

**Gate:** measurable gains and documented costs; no regression or fake success.

### Phase 9 — Fast-path inference and predictive memory management

- CPU/GPU/RAM/VRAM/SSD placement and budgets.
- Async movement, cache, expert residency and prefetch.
- Predictive expert/layer loading where supported.
- Router selection remains authoritative.
- Resource Guardian and safe stop.

**Gate:** sustained repeatable latency/speed or resource improvement; correct outputs; no memory thrash; predictor value measured by actual useful latency/bytes/cost.

### Phase 10 — Advanced compression, runtime intelligence and NECS research

- Quantization/mixed precision/sensitivity/sparsity.
- Optional runtime telemetry where reliable backend support exists.
- Optional NECS sidecars only after repeatable compression regressions and held-out benefit.
- Transformation lineage and quality preservation.

**Gate:** every transformation reproducible and benchmarked against the source; telemetry overhead measured; NECS remains optional or is abandoned with negative results documented.

### Phase 11 — Complete ECLIPSE desktop and release

- Finish three primary workspaces and shared Core integration.
- Agent chat, files, tools, code execution, GitHub and memory.
- Beginner onboarding, help, accessibility, themes and recovery.
- Import/export, model library, resource profiles, diagnostics, crash recovery.
- Windows packaging, install/upgrade/uninstall.
- Full end-to-end acceptance and user documentation.

**Gate:** genuine installable Windows desktop application; all agreed requirements implemented; CI and local validation evidence present; release and rollback instructions complete.

## User validation gates

A phase needing direct GPU/model/file-system interaction must be labelled `WAITING_FOR_USER_VALIDATION` until the user performs the exact local steps in `WINDOWS_LOCAL_VALIDATION_RUNBOOK.md`. Do not call it complete. Continue independent work while waiting when safe and useful.
