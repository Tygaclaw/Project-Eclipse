# ECLIPSE Autonomous Backlog

**Execution owner:** OpenCode autonomous engineering controller  
**Product source of truth:** `docs/COMPLETE_PRODUCT_RUNTIME_VISION.md`, `REQUIREMENTS.md`, `ARCHITECTURE.md`, original ECLIPSE Master Plan and Qwen capability-amplification handoff.  
**Rule:** The model may select and implement one ready milestone per run. It may not mark work complete without objective acceptance evidence.

## Mainline foundation — already landed

| ID | Delivered capability | Evidence / history | Status |
|---|---|---|---|
| BASE-01 | Three-workspace Windows desktop shell and Model Atlas UI | PR #4; user launched packaged app and navigated all three destinations | VERIFIED |
| BASE-02 | Bounded GGUF, Safetensors and Hugging Face folder inspection | Main source, unit tests and CI | VERIFIED |
| BASE-03 | Static tokenizer and chat-template inventory with bounded budgets and safe previews | PR #5; merged to main | VERIFIED |
| BASE-04 | Complete product/runtime vision specification | PR #6; merged to main | VERIFIED |
| BASE-05 | Headless OpenCode external-directory deny safeguard | PR #7; merged to main | VERIFIED_CONFIG_ONLY |
| BASE-06 | Host hardware snapshot and static RAM/VRAM/KV feasibility planner | PR #10; merged to main | VERIFIED_STATIC_ONLY |
| BASE-07 | Six-provider, 12-route free model catalogue and benchmark-based order | PR #11; merged to main | VERIFIED_CONFIG_ONLY |
| BASE-08 | Windows x64 PyInstaller build and CI workflows | Main workflows and prior successful runs | VERIFIED_CI_PACKAGE |

The above does not establish that inference, the Capability System or Agent are implemented. Do not describe placeholders or static estimates as working runtime features.

## Priority 0 — Autonomous development control plane

| ID | Milestone | Acceptance evidence | Status |
|---|---|---|---|
| AUTO-01 | Safe autonomous run workflow, branch/PR controller, one-open-PR guard and scheduled/manual resume | Controller tests pass; Python 3.11–3.14 CI passes; Qt/PyInstaller packaging and packaged backend smoke test pass; still requires owner review/merge and one confirmed live Actions run | IN_PROGRESS |
| AUTO-02 | Ranked free-only failover with initial attempt + five retries, same-session model switching, context compaction, error classification and durable handoff | Mocked retry/quota/context/session tests pass on current PR head; live non-confidential route and tool-call smoke tests remain | IN_PROGRESS |
| AUTO-03 | PR repair/resume from CI failures without duplicate branches or lost work | CI-log collection, same-session repair and checkpoint-recovery code implemented; deliberate end-to-end failed-PR recovery scenario remains | IN_PROGRESS |
| AUTO-04 | Model-independent review stage and evidence-based backlog completion checks | Deterministic `scripts/eclipse_review.py` gate wired into controller `validate_worktree`; `tests/test_review.py` proves rejection of a deleted/newly skipped test and of false completion claims (placeholder VERIFIED, invented test reference, completion claim while work remains). Protected controller change still needs Windows CI and owner merge | IN_PROGRESS |

## Priority 1 — Real model runtime and resource management

| ID | Milestone | Acceptance evidence | Status |
|---|---|---|---|
| RUN-01 | Runtime adapter/backend capability contract and support matrix | `BackendCapabilities`/`DeviceSupport`/`ControlSupport` contract, evidence-labelled support-matrix evaluator and `runtime-support` CLI; `tests/test_runtime.py` and `tests/test_runtime_cli.py` cover supported/unsupported/unknown formats, architectures, tensor types, CPU/GPU devices, placement modes and controls. Local portable suite passed 283 tests (11 skipped) after the PR #16 stale-branch recovery; Windows matrix CI runs on the milestone PR | VERIFIED_STATIC_ONLY |
| RUN-02 | Windows-compatible llama.cpp adapter that discovers and connects to the existing Vulkan setup without reinstalling or altering it | Mocked adapter integration plus one bundled Windows 11 local launch/stop validation | READY |
| RUN-03 | Truthful model lifecycle: load, generate, stop, unload, restart, failure cleanup and process ownership | Integration tests prove actual process state and no orphan on failed load | READY |
| RUN-04 | Context/KV-cache accepted-vs-requested reporting and actual allocation where backend exposes it | Backend integration evidence and allocation reconciliation | READY |
| RUN-05 | Supported CPU/GPU/hybrid placement, RAM/VRAM reserves and executable placement manifest | Placement tests against declared backend capabilities; no unsupported knobs shown | READY |
| RUN-06 | Runtime profiles, last-known-good, restore/rollback, diagnostics and logs | Reproducible save/restore/failed-profile rollback tests | READY |
| RUN-07 | Real telemetry and benchmark harness (TTFT, prompt processing, sustained rate, CPU/RAM/VRAM/disk/cache, quality) | Repeated runs with median/variance and raw manifests | READY |

## Priority 2 — Reversible model preparation and optimisation

| ID | Milestone | Acceptance evidence | Status |
|---|---|---|---|
| PREP-01 | Source identity, checksums, prepared-variant registry and manifest schema | Deterministic manifest tests; source remains read-only | READY |
| PREP-02 | Lossless indexes/layout preparation and integrity verification | Rebuild/reopen verification and rollback test | READY |
| PREP-03 | Quantization/mixed precision/sparsity/pruning/low-rank/distillation experiment framework | Reproducible candidate lineage and held-out quality reports | READY |
| PREP-04 | Predictive hot/warm/cold weight and MoE expert cache/prefetch research | Router remains authoritative; baseline comparison proves net latency/bytes benefit | READY |
| PREP-05 | NECS sidecar research, separate from agent correction memory | Held-out evidence of repeatable quality gain at acceptable cost; otherwise document negative result | READY |

## Priority 3 — Capability Amplification and knowledge

| ID | Milestone | Acceptance evidence | Status |
|---|---|---|---|
| CAP-01 | Shared tool registry, permission broker and project-scoped execution sandbox | Path/process/resource boundary and escape tests | READY |
| CAP-02 | Task planner, acceptance criteria, dependency tracking and Capability Watchdog | Multi-step task tests with risk/difficulty routing | READY |
| CAP-03 | Research/context retrieval with source/date/provenance and scoped context budgets | Retrieval relevance and leakage tests | READY |
| CAP-04 | Verification, retry/recovery, strategy change, loop detection and honest stop | Seeded-failure tests prove no false completion | READY |
| CAP-05 | Verified correction memory and reusable skills/playbooks linked to regression cases | Reproduction test required before promotion to trusted memory | READY |
| OBS-01 | Obsidian Markdown vault integration, AI Inbox, approval and dashboard | Scoped retrieval tests; approved notes never silently changed/deleted | READY |

## Priority 4 — ECLIPSE Agent and integrated desktop

| ID | Milestone | Acceptance evidence | Status |
|---|---|---|---|
| AGENT-01 | Real chat adapter using the shared model registry/runtime and free-provider/local model routes | Streaming/conversation integration tests with real provider smoke test | READY |
| AGENT-02 | Conversation history, search, files/attachments and project context | Persist/reopen/search and supported-file tests | READY |
| AGENT-03 | Memory/context controls and model switching through the shared Core | Provenance, isolation and context-budget tests | READY |
| AGENT-04 | Multi-step Agent tool execution, approvals, progress/activity and persistent Stop | End-to-end sandboxed task, cancellation and approval tests | READY |
| UI-01 | Complete three-workspace visual/UX integration, light/dark, accessibility and onboarding | Windows desktop walkthrough and automated UI tests | READY |
| INT-01 | Integrate all three workspaces through one Core and remove placeholder-only paths | End-to-end tests from Agent to Model Intelligence and Capability System | READY |

## Priority 5 — Evaluation and release

| ID | Milestone | Acceptance evidence | Status |
|---|---|---|---|
| EVAL-01 | Multi-file feature development evaluation | Same repo snapshot, acceptance tests and raw/basic/full comparisons | READY |
| EVAL-02 | Runtime debugging from real failures/logs | Failure injection, diagnosis, repair and regression tests | READY |
| EVAL-03 | Safe modification of an interconnected codebase | Existing regression suite; no unrelated regressions | READY |
| EVAL-04 | Three.js/game development evaluation | Playable build, automated checks and recorded result | READY |
| EVAL-05 | Controlled comparison of all available model routes | Repeat runs, identical prompts/tools/budgets, median outcomes and provider reliability | READY |
| REL-01 | Windows installer/update/uninstall/recovery and final documentation | Clean-machine/package smoke tests and bundled owner validation | READY |
| REL-02 | License selection, Qt LGPL notices/relinking, security/dependency scan and release hardening | Owner chooses license; compliance and scan evidence recorded | WAITING_FOR_OWNER_DECISION |
| REL-03 | Final single-pass Windows 11/Vulkan/Qwen/Obsidian acceptance | Owner runbook completed with evidence; no outstanding critical defects | WAITING_FOR_OWNER_VALIDATION |

## Phase maps to preserve

- **Original v3.0 map:** Phase 0 foundation; Phase 1 Model Intelligence; Phase 2 feasibility/compatibility; Phase 3 lossless preparation; Phase 4 first inference; Phase 5 fast-path; Phase 6 runtime intelligence; Phase 7 advanced compression; Phase 8 NECS/Capability Watchdog; Phase 9 externalized intelligence; Phase 10 complete desktop/resource manager.
- **Integrated delivery map:** Phase 0 historical foundation; Phase 1 repository control; Phase 2 architecture/three-workspace shell; Phase 3 static Model Intelligence; Phase 4 feasibility/preparation; Phase 5 real runtime; Phase 6 Capability Core; Phase 7 Obsidian; Phase 8 advanced reasoning/evaluation; Phase 9 fast-path/predictive memory; Phase 10 advanced compression/runtime intelligence/NECS; Phase 11 integrated desktop/release.

## Completion rule

The project is not 100% complete while any required READY/IN_PROGRESS backlog item remains unfinished, any required automated check is failing, a critical runtime capability is only a placeholder, or a final owner-only Windows/Obsidian gate remains unverified. Owner-only gates must be bundled and clearly labelled, not falsely marked complete.
