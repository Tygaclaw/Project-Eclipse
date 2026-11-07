# ECLIPSE Project Status

**Status:** `WINDOWS_CI_AND_PACKAGE_VERIFIED — OWNER_RUNTIME_AND_RELEASE_VALIDATION_PENDING`
**Last updated:** 2026-11-07
**Implementation base:** `e27fec7` (`main`); integrated into `main` by fast-forward after local verification
**Windows verification:** Python checks [#42330519701](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42330519701) and Windows desktop [#42330519740](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42330519740) both succeeded on `e27fec7`.

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

The previous placeholders and pending runtime layers have been replaced by working systems in the integrated implementation:

- **Shared Core** — one SQLite store for models, prepared variants, profiles, runs, conversations, messages, attachments, tasks, corrections, knowledge metadata and settings; one event bus; one home/config layout; one permission broker with canonical path scoping, approvals, command validation and redaction. The desktop, CLI and tests all use this Core.
- **Reversible preparation** — index/copy packages with source and output identity, SHA-256 inventories, manifests, lineage, verification, safe removal and quantization gated on a real `llama-quantize`.
- **Inference runtime** — managed `llama-server` lifecycle and OpenAI-compatible attach mode; streaming text/tool calls; cancellation; observed vs requested context; measured TTFT, completion tokens and tokens/second; load/generation/stop run records; failure cleanup; truthful states; execution profiles with validation.
- **Capability System** — watchdog routing, durable plans with acceptance criteria, project index/stack detection, workspace-scoped tools, independent `compileall`/test verification, bounded repair loop, loop detection, drift signals and Stop. Completion requires passing verification, not a model's claim.
- **Correction memory and knowledge** — candidates are promoted only with substantive evidence and a regression reference; model notes wait in an Obsidian-compatible AI Inbox and approval copies them to trusted folders without overwriting existing notes.
- **Agent** — persistent/searchable conversations, streaming, model selection, text attachments, scoped project tools, approvals, activity reporting and Stop on the same runtime and permission boundary.
- **Desktop** — all three workspaces are functional: Inspect & feasibility, Prepare & run (registry, prepare/verify/delete, backend/profile, start/stop/restart, telemetry, test, diagnostics), Capability (four tabs), Agent (chat), plus a persisted light/dark theme.
- **CLI** — 23 commands covering inspection, registry/preparation, runtime support/chat/benchmark/profiles, tasks, knowledge, corrections, status, diagnostics and check detection.

### Runtime completion pass — 7 November 2026

- **Model-specific support report** — `runtime-support` compares an inspected atlas and host snapshot against the selected backend's declared formats, architectures, tensor types, devices, placement modes and controls. Every dimension is `declared_supported`, `unsupported` or `unknown`; GPU hardware is `hardware_present_backend_unvalidated`. `runtime_verified` is always `false`. This adapts the useful part of PR #16 to the current runtime instead of merging its duplicate `core/runtime.py` interface.
- **Saved profiles and last-known-good restore** — a successful load persists the effective profile; a successful (non-cancelled) generation marks that profile last-known-good. The desktop can save, apply and restore profiles, and the CLI can list/delete them. Restoring a saved profile validates it against the current model before starting.
- **Measured benchmark harness** — `benchmark` performs configurable warm-up and measured generations, records every sample, and reports min/median/mean/max/stdev for TTFT, tokens/second, total time and completion tokens. It persists a `benchmark` run and labels the result as local wall-clock evidence, not a quality score.
- **Verification** — the complete suite now runs **340 tests, OK**. A real CLI benchmark against a spawned HTTP/SSE server returned `status=ok`, 2 measured samples, median TTFT `0.0016 s` and median throughput `122.645 tok/s`; the numbers are test-double measurements, not a model benchmark.

### Windows CI and package close-out — 7 November 2026

- **Windows Python matrix** — [run #42330519701](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42330519701) succeeded for Python 3.11, 3.12, 3.13 and 3.14.
- **Windows desktop package** — [run #42330519740](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42330519740) succeeded through pinned dependency installation, the full Qt/offscreen test suite, PyInstaller onedir build, packaged `ECLIPSE.exe --atlas-backend --help` smoke test, ZIP creation and artifact upload. Artifact `ECLIPSE-windows-x64` (ID `13556659342`, 52,935,974 bytes, SHA-256 `2ff2029fc52363a2ad6d399807417708f02671ee4fd8d80bcea50a811c3c40cc`) is available until 2026-11-21.
- **Defects found and fixed** — the first push-triggered run exposed Windows-only failures in Python-script server launch, SQLite `rowid` message ordering and a temp-directory/SQLite cleanup race. They were fixed in `edc02e7`, `1aeff21` and `e27fec7`; the local suite passes 340 tests on Python 3.11.16 and 3.12 (Python 3.11 skips the 13 optional Qt tests without PySide6).
- **Boundary** — this verifies hosted Windows CI and the portable package, not the owner's real GPU/model runtime, installed-app acceptance or Obsidian vault.
- **Dependency audit** — `pip-audit 2.10.1` audited `requirements-desktop.txt` (PySide6 6.12.0 chain, PyInstaller 6.22.3, pyinstaller-hooks-contrib 2026.9) with **no known vulnerabilities**. The development venv's `pip` 24.0 advisories were cleared by upgrading it to 26.3 and re-scanning; `pip` is tooling, not a shipped dependency. `LICENSES.md` now records the real PySide6 LGPL/GPL choice, PyInstaller's GPL-with-exception terms and the unresolved Qt distribution obligations.

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
- Real benchmark runs and last-known-good restore/rollback on the owner's backend; GPU/disk/cache sensors and quality evidence are not implemented.
- Owner launch/installation and acceptance of the CI-built Windows package; the package build and backend smoke test are verified in hosted CI, but an installed-app launch is not.
- Owner walkthrough of the rebuilt three-workspace UI and the real Obsidian vault.
- Real Safetensors and multi-shard Hugging Face folder validation on Windows.
- Executable CPU/GPU/hybrid placement planning and allocation reconciliation (profiles exist; placement is still configuration-based).
- Four remaining evaluations: multi-file development, runtime debugging, safe interconnected-code changes and Three.js/game development.
- Windows installer/update/uninstall/recovery, license/Qt LGPL compliance and the remaining binary/Qt security review (the Python dependency audit is recorded above).
- Live provider route/tool-call smoke tests and one completed live autonomous workflow run.

## User-only release gates

Do all independent development and GitHub-hosted Windows checks first. Then bundle only the remaining local checks into one clear Windows 11 validation run:
- launch the CI-built package (rebuild locally only if desired) and exercise the three-workspace app;
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
- [x] Model-specific support matrix, saved profiles with last-known-good restore, and repeated measured benchmark harness implemented and locally tested.
- [x] File tools are workspace-scoped and require explicit approval for writes and commands.
- [x] A failed load, denied action or failed check is recorded as a failure, never converted into success.
- [x] AI knowledge proposals remain in an Inbox until human approval; trusted notes are never overwritten.
- [x] Windows Python matrix and Windows x64 desktop package build/smoke/upload verified on `e27fec7`.
- [ ] Owner launch/installation of the CI-built package, real Windows runtime and real Obsidian walkthrough verified.
- [x] Dependency audit of the declared desktop requirements complete (`pip-audit`, 7 November 2026): no known advisories.
- [ ] Malware/binary and Qt CVE review plus release compliance complete.
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



## UI diagnostics addition

- Added a local session recorder for mouse clicks/double-clicks, wheel scrolling, workspace navigation, safe keyboard shortcuts, focus, context menus, drag/drop event types and Python/Qt/application errors.
- Interaction capture is enabled by default, has a visible sidebar pause/resume control, and can be opened from the sidebar. Logs remain on the PC under the ECLIPSE home `logs/` folder, with size/age retention limits.
- Privacy boundary: typed text, chat messages, passwords, clipboard contents, file contents, screenshots and absolute screen coordinates are not captured. Errors are recorded even when interaction capture is paused; common credential formats are redacted.
- Verification status: automated recorder tests and Windows build/test checks are pending this branch's CI. The owner must manually launch the new build and confirm the log reflects clicks and scrolling before this feature is accepted on the target PC.
