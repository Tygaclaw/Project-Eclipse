# ECLIPSE Project Status

**Status:** `AUTONOMOUS_RUN_ACTIVE — RUN-01_RUNTIME_CAPABILITY_CONTRACT_LOCAL_VERIFIED`
**Last updated:** 2026-11-06
**Current main head audited:** `acd7c41975fd6846fdfd4d7ac7c6616dd66765bb`

## Mainline history — verified

The following milestones are already merged to `main`:

- PR #1 — project handoff, initial bounded GGUF inspector and repository baseline.
- PR #4 — Windows-first three-workspace PySide6 shell, Model Atlas UI and packaging.
- PR #5 — bounded static tokenizer and chat-template intelligence.
- PR #6 — complete product/runtime vision specification.
- PR #7 — OpenCode headless external-directory deny safeguard.
- PR #10 — clean mainline hardware discovery and static RAM/VRAM/KV feasibility planner.
- PR #11 — six approved free API providers, 12 ranked model routes, ranking research and best-first OpenCode configuration.

The old stacked PR #8 (hardware increment) and PR #9 (free provider pool) are closed unmerged and superseded by PR #10 and PR #11. Do not merge or revive those old branches.

## What is implemented on main

- Bounded, read-only GGUF v2/v3 inspection and versioned GGML storage derivation.
- Bounded Safetensors header/tensor-index inspection.
- Hugging Face folder/shard-index inspection.
- Bounded tokenizer/chat-template metadata and inert template previews.
- Evidence-labelled Model Atlas and CLI.
- Windows host snapshot including OS/CPU/RAM and NVIDIA data when available.
- Static architecture-aware weight/KV feasibility estimates with RAM/VRAM reserves and SSD shown separately.
- PySide6 desktop shell with exactly three primary workspaces; Model Intelligence is connected to the Atlas.
- Windows x64 PyInstaller packaging and CI.
- Ranked six-provider/12-route free OpenCode pool and benchmark report.

A static estimate is not an executable placement plan or proof of inference. The Capability and Agent screens are not yet full implementations.

## Autonomous engineering controller — merged to main

Bootstrap PRs #12 (controller/workflow/backlog/handoff) and #13 (OpenCode CLI invocation and config guard fixes) are merged on `main`. The controller, ranked free-only failover, session handoff and scheduled workflow are now part of the repository. A live autonomous run created the current `feature/eclipse-autonomous-*` branch.

Implemented by the bootstrap:
- `docs/AUTONOMOUS_ENGINEERING_PROTOCOL.md` — operating contract for autonomous milestones, retry/failover, same-session continuation, safety and merge gates.
- `AUTONOMOUS_BACKLOG.md` — prioritized end-to-end implementation queue and evidence requirements.
- `.eclipse/AUTONOMOUS_SESSION_HANDOFF.md` — durable sanitized context for runner/session recovery.
- `scripts/eclipse_autonomous.py` — parent controller that selects ranked free routes, retries transient failures (initial + five retries), skips provider-wide quota/auth failures, reuses the same OpenCode session ID when available, runs local validation, scans changed files, creates a branch/PR and handles CI/merge/continuation.
- `tests/test_autonomous_runner.py` — retry classification, same-session failover and credential-isolation tests.
- `.github/workflows/eclipse-autonomous.yml` — manual, main-push and six-hour scheduled entry points, serialized with concurrency protection.
- Updated `DEEPSEEK_START_HERE.md`, `STATUS.md`, `CONTINUATION.md` and `README.md`.

Live provider text/tool-call smoke tests, observed cross-provider failover and an injected end-to-end CI-repair/resume exercise are still open acceptance gates. Do not describe those as proven.

## Independent review stage — AUTO-04

The autonomous controller now runs a deterministic, model-independent review gate (`scripts/eclipse_review.py`) as part of `validate_worktree`, after unit tests and before the controller commits. It reads Git metadata and small text files only and cannot edit the repository. It rejects:

- a deleted test file or a newly introduced test skip (seeded regression);
- a backlog item newly marked `VERIFIED*` without substantive acceptance evidence, an existing referenced test module, and either changed tests or a CI/PR record;
- a newly added whole-project completion claim while backlog items remain unfinished.

`tests/test_review.py` covers the pure checks and a real temporary-Git working-tree integration. `tests/test_autonomous_runner.py` asserts the controller's validation command list includes the separate reviewer. The local focused run passed 49 tests (20 reviewer, 28 controller, 1 import-bootstrap); the full portable suite result is recorded in `TESTING.md`. The first live controller validation exposed that its allowlisted child environment omitted `PYTHONPATH`, so every `eclipse.*` test module failed to import. Two complementary fixes now exist: `validation_environment()` sets `PYTHONPATH=<repo>/src` for fresh controller processes, and `tests/_bootstrap.py` (imported by every `eclipse`-importing test module) adds `src` when `PYTHONPATH` is absent. The latter lets an already-running controller pass without a restart.

Because this milestone changes the protected controller, its PR remains draft for owner review and Windows CI; it is not auto-merged. Batch status remains `IN_PROGRESS` until CI and merge are confirmed.

## Runtime capability contract and support matrix — RUN-01

`src/eclipse/core/runtime.py` adds the first shared-Core runtime contract. `BackendCapabilities`, `DeviceSupport` and `ControlSupport` let an inference adapter declare its support envelope (formats, architectures, tensor types, CPU/GPU devices, placement modes, controls, telemetry, maximum context). `evaluate_model_support(...)` compares a Model Atlas and host snapshot against that declaration and returns an evidence-labelled `eclipse_runtime_support` matrix. Per-dimension results are `declared_supported`, `unsupported` or `unknown`; a missing host snapshot or an unenumerated API (for example Vulkan) stays `unknown`, and an observed NVIDIA GPU is `hardware_present_backend_unvalidated` rather than supported. `runtime_verified` is always `false`; the contract never claims a model loads or generates. `load_capabilities(path)` reads a JSON manifest, and the `runtime-support` CLI command combines the atlas, host snapshot, requested placement mode and requested controls.

Tests: `tests/test_runtime.py` (24 tests) and `tests/test_runtime_cli.py` (6 tests) cover supported/unsupported/unknown formats, architectures, tensor types, CPU/CUDA/Vulkan device cases, placement modes, control support and restart flags, manifest JSON round-trip and validation errors, and CLI success/error paths. Focused run: 30 tests OK. Full portable suite after the PR #16 stale-branch recovery: `python -m unittest discover -s tests` ran **283 tests, OK, 11 skipped** (optional Qt tests) both with `PYTHONPATH=src` and with `PYTHONPATH` removed. This is a static contract and declaration comparison, not a working inference adapter; RUN-02 (real llama.cpp adapter) remains the runtime integration gate.

## PR #16 recovery — stale branch resynchronised with main

The recovered PR #16 branch was cut from `main` at PR #14 and did not contain PR #15. Because the controller's independent review gate compares the worktree against `origin/main`, it reported `tests/test_autonomous_orphans.py` and `tests/test_autonomous_parking.py` as deleted and rejected the change set even though the RUN-01 product code was correct. The recovery restored the three files PR #15 changed (`scripts/eclipse_autonomous.py` plus the two controller test modules) from `origin/main`; no test or product behaviour was weakened. `tests/test_recovery.py` (2 tests) reproduces the stale-base failure and the resynchronisation fix in a temporary Git repository. Local gates: 283 tests OK (11 skipped), compile OK, provider pool OK, independent review accepted, whitespace clean. This recovery did not start a new backlog item and did not change any milestone status. It changes controller/test paths, so the PR remains owner-review only.

## What is not yet complete as a working product

- Real ECLIPSE-managed model inference lifecycle. The backend capability contract and static support matrix exist (RUN-01), but no backend is integrated and no model is loaded, generated, stopped or measured by ECLIPSE yet.
- Executable CPU/GPU/hybrid placement and context/KV allocation verification.
- Reversible prepared variants and transformation lineage.
- Runtime profiles, actual telemetry and benchmarked performance.
- Capability Watchdog, planner, research/context service, permissioned tool registry and sandbox.
- Independent verification, recovery, loop detection, verified correction memory and reusable skills.
- Obsidian knowledge vault and approval workflow.
- Functional ECLIPSE Agent with chat, history, model switching, files, tools and Stop.
- Complete end-to-end integration of all three workspaces through one Core.
- Four remaining evaluations: multi-file development, runtime debugging, safe interconnected-code changes and Three.js/game development.
- Windows installer/update/uninstall/recovery and release compliance.

## User-only release gates

Do all independent development and GitHub-hosted Windows checks first. Then bundle only the remaining local checks into one clear Windows 11 validation run:
- verify the existing llama.cpp/Vulkan/Qwen connection without reinstalling or changing the known-good configuration;
- test real model load/generate/stop, actual hardware telemetry and resource recovery;
- validate the user's Obsidian vault integration;
- verify installation/update/uninstall on the target PC.

Keep these gates `WAITING_FOR_OWNER_VALIDATION` until real evidence exists. Do not ask the owner to repeat the completed A* challenge, general hardware audit, Qwen installation or API-key setup.

## Free & Safe Checklist

- [x] Six-provider, 12-model approved pool is configured on main.
- [x] Provider order is benchmark-based and free routes are explicit where required.
- [x] No paid model, paid fallback, top-up or automatic account rotation is permitted.
- [x] Static inspectors do not load or execute target model weights/code.
- [x] Original model checkpoints remain read-only.
- [x] Autonomous child receives only one selected provider key; controller GitHub token is not forwarded to it.
- [x] Autonomous runner cannot push or commit through its agent permissions; controller owns Git operations.
- [x] Protected bootstrap PRs #12 and #13 reviewed and merged to `main`.
- [ ] First live autonomous run verified end-to-end (milestone PR merged by the controller).
- [ ] Each API route passes live non-confidential text and tool-call smoke tests.
- [ ] Runtime, sandbox, Obsidian, Agent, security/dependency scans and release gates complete.
- [ ] License selection remains an owner decision; Qt/PySide6 LGPL packaging obligations must be addressed before redistribution.

## Autonomous bootstrap verification evidence — PR #12 (merged)

PR: https://github.com/Tygaclaw/Project-Eclipse/pull/12  
Branch: `feature/autonomous-engineering-engine-2026-11-06`  
Last verified PR head before this documentation update: `44a463732448c6faa544620760eb725ab8944563`.

- [x] Windows Python matrix run [#42292375849](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42292375849): Python 3.11, 3.12, 3.13 and 3.14 all succeeded; each ran 210 unit tests with 11 expected optional dependency skips.
- [x] Windows desktop run [#42292375824](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42292375824): full suite including Qt/offscreen desktop tests succeeded; PyInstaller Windows x64 build succeeded; packaged backend smoke test succeeded; ZIP creation and artifact upload succeeded.
- [x] Artifact `ECLIPSE-windows-x64` uploaded successfully (51,137,344 bytes).
- [x] Mocked tests cover initial + five retries, same-session model switch, provider quota/auth handling, context compaction, standalone OpenCode session invocation and child credential scrubbing.
- [ ] Live API text/tool-call smoke test across the 12 routes; these tests are not yet claimed.
- [ ] End-to-end failure injection to prove GitHub CI repair and scheduled checkpoint resume.
- [x] Protected bootstrap PR #12 was reviewed and merged; the follow-up CLI/config fix PR #13 is also merged.
- [ ] Observation of a completed live autonomous workflow run that produces a merged milestone PR.

PR #12/#13 are now on `main`; the historical draft state above is superseded. Do not mark AUTO-01/02/03 completely accepted before the remaining live gates are satisfied.

