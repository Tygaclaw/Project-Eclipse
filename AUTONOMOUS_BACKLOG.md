# ECLIPSE Autonomous Backlog

**Execution owner:** OpenCode autonomous engineering controller  
**Product source of truth:** `docs/COMPLETE_PRODUCT_RUNTIME_VISION.md`, `REQUIREMENTS.md`, `ARCHITECTURE.md`, original ECLIPSE Master Plan and Qwen capability-amplification handoff.  
**Rule:** The model may select and implement one ready milestone per run. It may not mark work complete without objective acceptance evidence. `IMPLEMENTED_LOCAL_TESTS` means automated local evidence exists; it is not a claim that the owner-only Windows/GPU/Obsidian gate has passed.

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
| BASE-08 | Windows x64 PyInstaller build and CI workflows | Main workflows; `e27fec7` Python checks #42330519701 and desktop package #42330519740 both succeeded | VERIFIED_CI_PACKAGE |

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
| RUN-01 | Runtime adapter/backend capability contract and support matrix | `src/eclipse/runtime/backends.py`; CLI `backends` test; profile validation tests cover unsupported format/architecture/controls | IMPLEMENTED_LOCAL_TESTS |
| RUN-02 | Windows-compatible llama.cpp adapter that discovers and connects to the existing Vulkan setup without reinstalling or altering it | Managed adapter and binary discovery implemented; `tests/test_runtime.py` exercises a real spawned server process. The owner's real Windows/Vulkan/Qwen connection is the remaining gate | IN_PROGRESS |
| RUN-03 | Truthful model lifecycle: load, generate, stop, unload, restart, failure cleanup and process ownership | `tests/test_runtime.py` proves ready/pids/stop process exit, missing-binary failure state, startup-crash cleanup and attach-mode ownership; no orphan on failed launch | IMPLEMENTED_LOCAL_TESTS |
| RUN-04 | Context/KV-cache accepted-vs-requested reporting and actual allocation where backend exposes it | `/props` observed context is recorded and displayed; fake-server test asserts observed 2048 vs requested; requested/observed fields exist in status and UI. Real backend allocation reconciliation pending | IMPLEMENTED_LOCAL_TESTS |
| RUN-05 | Supported CPU/GPU/hybrid placement, RAM/VRAM reserves and executable placement manifest | Profiles expose only backend-declared controls and validate them; a true executable layer-placement planner is still pending | IN_PROGRESS |
| RUN-06 | Runtime profiles, last-known-good, restore/rollback, diagnostics and logs | Effective profile is persisted after a successful load and marked last-known-good only after a successful generation; desktop save/apply/restore controls and CLI `profiles list|delete` are implemented. `tests/test_runtime.py` covers save, mark-good and restore-after-stop. Real Windows rollback remains an owner gate | IMPLEMENTED_LOCAL_TESTS |
| RUN-07 | Real telemetry and benchmark harness (TTFT, prompt processing, sustained rate, CPU/RAM/VRAM/disk/cache, quality) | Measured TTFT, completion tokens, tokens/second and process/host samples are recorded per generation. `src/eclipse/runtime/benchmark.py` runs warm-up plus repeated generations, reports min/median/mean/max/stdev and persists a benchmark run; CLI and desktop controls are wired. Prompt-processing, GPU/disk/cache sensors and quality comparison remain | IMPLEMENTED_LOCAL_TESTS |

## Priority 2 — Reversible model preparation and optimisation

| ID | Milestone | Acceptance evidence | Status |
|---|---|---|---|
| PREP-01 | Source identity, checksums, prepared-variant registry and manifest schema | `tests/test_preparation.py` covers deterministic manifests, hashes, registry and read-only source | IMPLEMENTED_LOCAL_TESTS |
| PREP-02 | Lossless indexes/layout preparation and integrity verification | Index/copy package verification, corruption detection and safe removal covered by `tests/test_preparation.py` | IMPLEMENTED_LOCAL_TESTS |
| PREP-03 | Quantization/mixed precision/sparsity/pruning/low-rank/distillation experiment framework | Real `llama-quantize` gating and GGUF-only validation implemented; the broader experiment framework and held-out quality reports remain | IN_PROGRESS |
| PREP-04 | Predictive hot/warm/cold weight and MoE expert cache/prefetch research | Router remains authoritative; baseline comparison proves no net latency/bytes benefit yet | READY |
| PREP-05 | NECS sidecar research, separate from agent correction memory | Held-out evidence of repeatable quality gain at acceptable cost is not yet available | READY |

## Priority 3 — Capability Amplification and knowledge

| ID | Milestone | Acceptance evidence | Status |
|---|---|---|---|
| CAP-01 | Shared tool registry, permission broker and project-scoped execution sandbox | `tests/test_capability.py` proves path-escape rejection, approval-denied writes, argument-list commands and bounded verification; `tests/test_core_foundation.py` covers the broker/security primitives. Application-level, not an OS sandbox | IMPLEMENTED_LOCAL_TESTS |
| CAP-02 | Task planner, acceptance criteria, dependency tracking and Capability Watchdog | Watchdog routing, plan objectives/criteria, file hints and drift signals covered by `tests/test_capability.py` | IMPLEMENTED_LOCAL_TESTS |
| CAP-03 | Research/context retrieval with source/date/provenance and scoped context budgets | Project index/search with provenance and bounded context composition implemented and tested; web research/source-date retrieval remains future work | IN_PROGRESS |
| CAP-04 | Verification, retry/recovery, strategy change, loop detection and honest stop | Seeded failing checks, denied writes, repair loop, loop detection and honest non-completion covered by `tests/test_capability.py` | IMPLEMENTED_LOCAL_TESTS |
| CAP-05 | Verified correction memory and reusable skills/playbooks linked to regression cases | Promotion requires substantive evidence and a regression reference; candidates are not injected as trusted lessons; repairs create candidates. Covered by `tests/test_capability.py` | IMPLEMENTED_LOCAL_TESTS |
| OBS-01 | Obsidian Markdown vault integration, AI Inbox, approval and dashboard | Vault scaffold, Inbox, trusted-folder approval/rejection, search and no-overwrite promotion covered by `tests/test_capability.py`; real Obsidian walkthrough pending | IMPLEMENTED_LOCAL_TESTS |

## Priority 4 — ECLIPSE Agent and integrated desktop

| ID | Milestone | Acceptance evidence | Status |
|---|---|---|---|
| AGENT-01 | Real chat adapter using the shared model registry/runtime and free-provider/local model routes | Streaming and conversation integration tested against a real spawned HTTP/SSE server; CLI `chat --endpoint` run end to end. Live provider-route smoke test remains | IMPLEMENTED_LOCAL_TESTS |
| AGENT-02 | Conversation history, search, files/attachments and project context | `tests/test_agent.py` covers persist/reopen/search/delete, attachment copy and one-time context inclusion | IMPLEMENTED_LOCAL_TESTS |
| AGENT-03 | Memory/context controls and model switching through the shared Core | Model selection, verified-correction context and approved-knowledge toggles implemented; shared store/runtime used by all workspaces | IMPLEMENTED_LOCAL_TESTS |
| AGENT-04 | Multi-step Agent tool execution, approvals, progress/activity and persistent Stop | Tool execution with persisted metadata, approval bridge, streaming activity and cancellation token covered by `tests/test_agent.py` and UI smoke tests | IMPLEMENTED_LOCAL_TESTS |
| UI-01 | Complete three-workspace visual/UX integration, light/dark, accessibility and onboarding | Functional workspaces, persisted light/dark theme and offscreen UI tests exist; the hosted Windows package passed, but owner launch/installation and walkthrough remain | IN_PROGRESS |
| INT-01 | Integrate all three workspaces through one Core and remove placeholder-only paths | One `AppContext` supplies store/runtime/knowledge/memory/agent to every workspace; offscreen smoke verifies the real controls; placeholder assertions were removed | IMPLEMENTED_LOCAL_TESTS |

## Priority 5 — Evaluation and release

| ID | Milestone | Acceptance evidence | Status |
|---|---|---|---|
| EVAL-01 | Multi-file feature development evaluation | Same repo snapshot, acceptance tests and raw/basic/full comparisons | READY |
| EVAL-02 | Runtime debugging from real failures/logs | Failure injection, diagnosis, repair and regression tests | READY |
| EVAL-03 | Safe modification of an interconnected codebase | Existing regression suite; no unrelated regressions | READY |
| EVAL-04 | Three.js/game development evaluation | Playable build, automated checks and recorded result | READY |
| EVAL-05 | Controlled comparison of all available model routes | Repeat runs, identical prompts/tools/budgets, median outcomes and provider reliability | READY |
| REL-01 | Windows installer/update/uninstall/recovery and final documentation | Clean-machine/package smoke tests and bundled owner validation | READY |
| REL-02 | License selection, Qt LGPL notices/relinking, security/dependency scan and release hardening | Owner chooses license; Qt LGPL notices/relinking and binary/security review remain. `pip-audit` on `requirements-desktop.txt` found no known vulnerabilities (7 Nov 2026) | WAITING_FOR_OWNER_DECISION |
| REL-03 | Final single-pass Windows 11/Vulkan/Qwen/Obsidian acceptance | Owner runbook completed with evidence; no outstanding critical defects | WAITING_FOR_OWNER_VALIDATION |

## Local integration evidence — 7 November 2026

- Full `python -m unittest discover -s tests` with `PYTHONPATH=src`, `QT_QPA_PLATFORM=offscreen` and the project PySide6 environment: **340 tests, OK**.
- Windows code head `e27fec7`: Python checks #42330519701 succeeded on 3.11–3.14; Windows desktop #42330519740 passed the full Qt/offscreen suite, PyInstaller build, packaged backend smoke test, ZIP and artifact upload (`ECLIPSE-windows-x64`, 52,935,974 bytes).
- The runtime suite spawns the fake HTTP/SSE server as a real process, exercises managed load/stream/stop, startup failure cleanup, attach mode and measured telemetry.
- The Capability suite executes real `compileall`/unittest verification and real argument-list commands; failing checks and denied approvals cannot produce `completed`.
- The Agent suite exercises the same runtime/tool loop with persisted conversations and attachments.
- Offscreen Qt tests construct the full window with a temporary `AppContext` and exercise navigation, real workspace controls and theme switching.
- `pip-audit 2.10.1 -r requirements-desktop.txt` audited PySide6 6.12.0, shiboken6, the PySide6 module wheels, PyInstaller 6.22.3 and pyinstaller-hooks-contrib 2026.9 with no known vulnerabilities; the dev venv's `pip` 24.0 advisories were cleared by upgrading to 26.3 (pip is tooling, not shipped).
- A real CLI run (`eclipse chat --endpoint ... --json`) streamed an answer and reported state `ready` plus a generation run.
- A real CLI benchmark (`eclipse benchmark --endpoint ... --runs 2 --warmup 1 --json`) returned `status=ok`, two measured samples, median TTFT `0.0016 s` and median throughput `122.645 tok/s` against the fake HTTP/SSE server. These are test-double measurements, not a model-performance claim.
- `runtime-support` compares a real inspected GGUF atlas and host snapshot against the current backend declarations; `runtime_verified` stays false by design.

## PR #16 reconciliation — 7 November 2026

PR #16 is a stale static runtime-contract branch cut before the integrated runtime landed. Its `src/eclipse/core/runtime.py` would duplicate the current backend/profile interfaces. The useful model-specific declaration comparison was adapted into `src/eclipse/runtime/backends.py` as `evaluate_model_support(...)` and the `runtime-support` CLI, with tests. The PR itself was not merged; its controller/recovery changes are historical and do not belong in the product runtime.

These are local automated results on Linux. They do not replace the owner Windows 11 llama.cpp/Vulkan/Qwen, rebuilt-package, real-Obsidian or installer gates.

## Phase maps to preserve

- **Original v3.0 map:** Phase 0 foundation; Phase 1 Model Intelligence; Phase 2 feasibility/compatibility; Phase 3 lossless preparation; Phase 4 first inference; Phase 5 fast-path; Phase 6 runtime intelligence; Phase 7 advanced compression; Phase 8 NECS/Capability Watchdog; Phase 9 externalized intelligence; Phase 10 complete desktop/resource manager.
- **Integrated delivery map:** Phase 0 historical foundation; Phase 1 repository control; Phase 2 architecture/three-workspace shell; Phase 3 static Model Intelligence; Phase 4 feasibility/preparation; Phase 5 real runtime; Phase 6 Capability Core; Phase 7 Obsidian; Phase 8 advanced reasoning/evaluation; Phase 9 fast-path/predictive memory; Phase 10 advanced compression/runtime intelligence/NECS; Phase 11 integrated desktop/release.

## Completion rule

The project is not 100% complete while any required READY/IN_PROGRESS backlog item remains unfinished, any required automated check is failing, a critical runtime capability is only a placeholder, or a final owner-only Windows/Obsidian gate remains unverified. Owner-only gates must be bundled and clearly labelled, not falsely marked complete.
