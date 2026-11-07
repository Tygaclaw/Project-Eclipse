# ECLIPSE Continuation Record

## Current checkpoint

- Repository: `Tygaclaw/Project-Eclipse`.
- Default branch: `main`.
- Integration base: `84ce050`; implementation work was done on `freebuff/938f3f76478afd5f73c65464` and is integrated into `main`. Windows CI and the portable package passed on code head `e27fec7`.
- Autonomous bootstrap PRs #12/#13 and later controller work are merged. Every remote side branch was checked: the only unmerged branches were duplicate autonomous-controller attempts, not product code.
- Mainline PRs #5, #6, #7, #10 and #11 are merged. PRs #8 and #9 are obsolete, closed and superseded.
- The product now includes the previously missing shared Core, runtime, preparation, Capability System, knowledge workflow, Agent and full three-workspace integration described below, plus saved profiles with last-known-good restore, a model-specific support report and a repeated measured benchmark harness.
- Latest local suite: **340 tests, OK**; a real CLI benchmark against the spawned HTTP/SSE test server completed with two measured samples.
- Windows Python 3.11–3.14 checks passed in [run #42330519701](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42330519701); the Windows desktop package passed in [run #42330519740](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42330519740), including PyInstaller, packaged-backend smoke test and artifact upload.

## Product truth — 7 November 2026

The three primary workspaces are now functional and share one `AppContext`: one SQLite store, runtime manager, event bus, knowledge base, correction memory, permission broker and agent. Model Intelligence retains the static inspectors and feasibility planner and adds a Prepare & run tab with registry/preparation, managed or attached inference, profiles, lifecycle, observed context, measured telemetry, diagnostics and a real generation test. Capability has a watchdog/planner, workspace-scoped tools, independent verification, a bounded repair loop, loop detection, correction memory and an Obsidian-compatible Inbox/approval workflow. Agent has persistent conversations, streaming, attachments, tools, approvals and Stop.

The runtime and Capability/Agent orchestration have been exercised end to end against a real spawned HTTP/SSE inference double, real subprocess tool execution and the real SQLite store. The CLI `chat --endpoint` path was also run end to end and returned a real streamed answer and measured state; the CLI `benchmark` path returned two measured samples with median TTFT and throughput. This is local automated evidence, not owner Windows/GPU acceptance. Original model files remain read-only; the permission boundary is application-level scoping, not an OS sandbox. The remaining gates are listed in `STATUS.md`.

## Autonomous controller bootstrap

The current feature branch adds:

- `docs/AUTONOMOUS_ENGINEERING_PROTOCOL.md`
- `AUTONOMOUS_BACKLOG.md`
- `.eclipse/AUTONOMOUS_SESSION_HANDOFF.md`
- `scripts/eclipse_autonomous.py`
- `tests/test_autonomous_runner.py`
- `.github/workflows/eclipse-autonomous.yml`
- updated root execution/status/readme records.

The controller uses the 12-model ranked free pool. Transient model errors receive one initial attempt plus up to five retries with backoff. Quota/auth/provider-wide failures skip that provider immediately. Model retries and model switches reuse the same OpenCode session ID when available. If no session was created before a provider error, the next route starts the same task from the same prompt/checkpoint.

The OpenCode child receives only the selected provider credential. GitHub credentials remain in the parent controller; the model agent is denied commit/push/GitHub CLI write commands. The controller checks the worktree, commits and pushes, and opens a PR. Safe product PRs require Windows Python 3.11–3.14 and Windows Qt/PyInstaller checks before automatic squash-merge. Changes to workflow, credential, permission, controller and security policy files remain draft for owner review.

The workflow has manual dispatch, main-branch push and six-hour scheduled entry points, with a concurrency group and one-open-autonomous-PR guard. A successful safe merge queues the next run. An open draft/protected PR intentionally pauses further work until owner review; a failed CI/safety gate is not merged.

**Important:** This bootstrap branch is not yet on main and its workflow has not yet had a live Actions run. CI and first-run behavior must be verified after the bootstrap PR is opened. Do not describe automation as active until it is merged and the first run succeeds.

## Next autonomous work order

Use `AUTONOMOUS_BACKLOG.md` as the canonical queue. The local implementation work is complete; the remaining order is:
1. Owner-install or launch the CI-built Windows package and smoke-test all three workspaces plus the packaged backend.
2. Verify the real Windows llama.cpp/Vulkan/Qwen connection, load/generate/stop/restart, observed context, telemetry and resource recovery.
3. Walk through all three workspaces and the real Obsidian vault on Windows; run one Capability task and one Agent tool task with approvals.
4. Complete the four model-agent evaluations with recorded evidence.
5. Finish live provider route smoke tests and the live autonomous-workflow acceptance gates.
6. Installer/update/uninstall, license/Qt LGPL compliance and the remaining binary/Qt security review (the Python dependency audit is already recorded in `LICENSES.md`).

## Windows CI/package close-out — 7 November 2026

- Code head `e27fec7` passed Windows Python checks 3.11–3.14 ([run #42330519701](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42330519701)).
- The Windows desktop workflow passed the full Qt/offscreen suite, PyInstaller onedir build, packaged `ECLIPSE.exe --atlas-backend --help` smoke test, ZIP creation and artifact upload ([run #42330519740](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42330519740)). Artifact `ECLIPSE-windows-x64`, ID `13556659342`, 52,935,974 bytes, SHA-256 `2ff2029fc52363a2ad6d399807417708f02671ee4fd8d80bcea50a811c3c40cc`.
- The first push-triggered run caught three real Windows defects: `.py` server scripts were launched without the interpreter, message ordering used SQLite `rowid`, and one test deleted a temp SQLite directory before closing it. Fixed in `edc02e7`, `1aeff21` and `e27fec7`; local Python 3.11.16 and 3.12 suites pass 340 tests.
- This does not verify the owner's GPU-backed model runtime, installed-app launch or Obsidian vault. Those remain owner gates.

## Runtime completion pass — 7 November 2026

- `src/eclipse/runtime/backends.py` now exposes `evaluate_model_support(...)` and `runtime-support`, a model-specific declaration comparison covering format, architecture, tensor types, devices, placement and requested controls. It keeps `runtime_verified: false` and labels observed GPU hardware as unvalidated. This adapts the useful idea from stale PR #16 without merging its duplicate `core/runtime.py`.
- `src/eclipse/runtime/profiles.py` and `manager.py` persist the effective profile after a successful load and mark it last-known-good after a successful generation. The desktop can apply, save and restore profiles; the CLI lists/deletes them. Restoring validates the saved profile against the current model and then starts it.
- `src/eclipse/runtime/benchmark.py` runs configurable warm-up plus measured generations, reports min/median/mean/max/stdev and persists a `benchmark` run. The desktop has a Benchmark control; the CLI has `benchmark`.
- Verification: full suite **340 tests, OK**; real CLI benchmark `status=ok`, 2 samples, TTFT median `0.0016 s`, throughput median `122.645 tok/s` against the fake server. The values are test-double evidence only.
- PR #16 remains stale and unmerged; its unique static-contract value is now implemented against the live runtime. Its controller/recovery changes are not product requirements.

## Model order and free-only safety

The global order is in `docs/FREE_MODEL_PROVIDER_POOL.md`; detailed public benchmark evidence is in `docs/ECLIPSE_AGENT_MODEL_RANKING_2026-11-06.md`. The ranking is provisional until routes and identical ECLIPSE tasks are tested live. No paid route, top-up, account rotation or unapproved provider is allowed.

## Do not repeat

- General Windows/hardware audit.
- Qwen local installation or API-key recreation.
- The already completed A* evaluation.

Never ask for, print or commit API-key values. Preserve the original model files and the known-good local setup. Continue independent engineering while a specific owner-only local gate is waiting.

## Autonomous bootstrap CI checkpoint — 6 November 2026

PR #12: https://github.com/Tygaclaw/Project-Eclipse/pull/12  
Branch: `feature/autonomous-engineering-engine-2026-11-06`.

Verified head `44a463732448c6faa544620760eb725ab8944563`:
- Python checks run #42292375849 passed on Windows Python 3.11–3.14; each ran 210 tests with 11 optional-dependency skips.
- Windows desktop build run #42292375824 passed the full Qt/offscreen suite, PyInstaller build, packaged-backend smoke test, ZIP and artifact upload.
- Artifact `ECLIPSE-windows-x64`: 51,137,344 bytes.
- Retry/failover, same-session switching, context compaction, quota skip and credential-scrubbing behavior have mocked regression coverage.
- Actual live provider/tool-call smoke tests and an injected end-to-end CI-repair/resume exercise remain open.
- PR #12 remains an owner-review draft due protected workflow/controller/security changes; do not merge or activate without that review. After merge, verify the first live Actions run before describing automation as active.

The autonomous backlog now marks AUTO-01/02/03 in progress rather than complete, because operational acceptance is not yet proven.

## AUTO-04 independent review stage — 6 November 2026

Base main: `acd7c41975fd6846fdfd4d7ac7c6616dd66765bb` (bootstrap PRs #12 and #13 merged).

Implemented:
- `scripts/eclipse_review.py`: deterministic, read-only reviewer. Rejects deleted tests, newly added test skips, false `VERIFIED*` backlog claims (placeholder evidence, missing referenced test, no changed test/CI record) and new whole-project completion claims while backlog work remains.
- `scripts/eclipse_autonomous.py`: `REVIEW_COMMAND` and `validation_commands()` add the reviewer to `validate_worktree` after unit tests, so the same-session repair loop must satisfy an independent acceptance gate before the controller commits.
- `tests/test_review.py`: 20 focused tests including a real temporary-Git working-tree integration.
- `tests/test_autonomous_runner.py`: 2 wiring tests confirming the reviewer is a separate command in the validation gate, plus 1 regression test asserting the validation environment exposes `src` on `PYTHONPATH`.

Fix from the first live validation run: the controller's allowlisted validation environment omitted `PYTHONPATH`, so the `eclipse.*` test modules failed to import. `validation_environment()` now sets `PYTHONPATH=<repo>/src`; verified by running the controller's environment against `tests.test_hardware` with an empty parent `PYTHONPATH` (14 tests OK).

Second live validation repeated the same import failure because the already-running controller process still held the pre-fix `validation_environment` in memory; editing the script cannot reload that process. Added `tests/_bootstrap.py`, imported by every `eclipse`-importing test module, which inserts `<repo>/src` into `sys.path` when `PYTHONPATH` is absent. A subprocess regression test (`tests/test_test_bootstrap.py`) runs the suite with `PYTHONPATH` removed. Result: full `python -m unittest discover -s tests` passes both with and without `PYTHONPATH`.

Verification actually run locally (Linux, Python 3.12.16, no PySide6): focused `tests.test_review` + `tests.test_autonomous_runner` + `tests.test_test_bootstrap` = 49 tests OK. Full portable suite result is recorded in `TESTING.md`.

The controller change is protected, so the milestone PR must remain draft for owner review and Windows CI. AUTO-04 stays `IN_PROGRESS` until that merge and CI are confirmed. Next READY milestone after AUTO-04 is RUN-01 (runtime adapter/backend capability contract and support matrix).

