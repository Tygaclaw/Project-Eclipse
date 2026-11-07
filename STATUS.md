# ECLIPSE Project Status

**Status:** `INTEGRATED_LOCAL_IMPLEMENTATION_COMPLETE — OWNER_WINDOWS_VALIDATION_PENDING`
**Last updated:** 2026-11-07
**Implementation base:** `84ce050` (`main`); integrated on `freebuff/938f3f76478afd5f73c65464`

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

## Integrated product implementation — 7 November 2026

The previous placeholders and pending runtime layers have been replaced by working systems on the integration branch:

- **Shared Core** — one SQLite store for models, prepared variants, profiles, runs, conversations, messages, attachments, tasks, corrections, knowledge metadata and settings; one event bus; one home/config layout; one permission broker with canonical path scoping, approvals, command validation and redaction. The desktop, CLI and tests all use this Core.
- **Reversible preparation** — index/copy packages with source and output identity, SHA-256 inventories, manifests, lineage, verification, safe removal and quantization gated on a real `llama-quantize`.
- **Inference runtime** — managed `llama-server` lifecycle and OpenAI-compatible attach mode; streaming text/tool calls; cancellation; observed vs requested context; measured TTFT, completion tokens and tokens/second; load/generation/stop run records; failure cleanup; truthful states; execution profiles with validation.
- **Capability System** — watchdog routing, durable plans with acceptance criteria, project index/stack detection, workspace-scoped tools, independent `compileall`/test verification, bounded repair loop, loop detection, drift signals and Stop. Completion requires passing verification, not a model's claim.
- **Correction memory and knowledge** — candidates are promoted only with substantive evidence and a regression reference; model notes wait in an Obsidian-compatible AI Inbox and approval copies them to trusted folders without overwriting existing notes.
- **Agent** — persistent/searchable conversations, streaming, model selection, text attachments, scoped project tools, approvals, activity reporting and Stop on the same runtime and permission boundary.
- **Desktop** — all three workspaces are functional: Inspect & feasibility, Prepare & run (registry, prepare/verify/delete, backend/profile, start/stop/restart, telemetry, test, diagnostics), Capability (four tabs), Agent (chat), plus a persisted light/dark theme.
- **CLI** — 20 commands covering inspection, registry/preparation, runtime/chat, tasks, knowledge, corrections, status, diagnostics and check detection.

A static feasibility estimate is still not an executable placement plan or proof of inference. The application-level permission boundary is not an OS container sandbox. The runtime has been exercised against a real spawned HTTP/SSE test server, but not yet against the owner's real Windows llama.cpp/Vulkan/Qwen installation.

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

## What still requires real-world validation

- Real Windows llama.cpp/Vulkan/Qwen load, generation, stop and restart through the packaged app, including observed context and actual VRAM/RAM telemetry.
- Rebuilding the PyInstaller Windows package with the new Core/runtime/capability/agent hidden imports and smoke-testing the packaged executable.
- Owner walkthrough of the rebuilt three-workspace UI and the real Obsidian vault.
- Real Safetensors and multi-shard Hugging Face folder validation on Windows.
- Executable CPU/GPU/hybrid placement planning and allocation reconciliation (profiles exist; placement is still configuration-based).
- Four remaining evaluations: multi-file development, runtime debugging, safe interconnected-code changes and Three.js/game development.
- Windows installer/update/uninstall/recovery, license/Qt LGPL compliance and security/dependency scans.
- Live provider route/tool-call smoke tests and one completed live autonomous workflow run.

## User-only release gates

Do all independent development and GitHub-hosted Windows checks first. Then bundle only the remaining local checks into one clear Windows 11 validation run:
- rebuild the package and launch the three-workspace app;
- verify the existing llama.cpp/Vulkan/Qwen connection without reinstalling or changing the known-good configuration;
- test real model load/generate/stop/restart, observed context, actual hardware telemetry and resource recovery;
- run one Capability task and one Agent tool task with real approvals;
- validate the user's real Obsidian vault workflow;
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
- [x] Shared Core, managed/attached runtime, Capability System, knowledge workflow and Agent implemented and locally tested.
- [x] File tools are workspace-scoped and require explicit approval for writes and commands.
- [x] A failed load, denied action or failed check is recorded as a failure, never converted into success.
- [x] AI knowledge proposals remain in an Inbox until human approval; trusted notes are never overwritten.
- [ ] Real Windows runtime, rebuilt package and real Obsidian walkthrough verified.
- [ ] Security/dependency scans and release compliance complete.
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

