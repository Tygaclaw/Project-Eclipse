# Autonomous Session Handoff

**Purpose:** durable, sanitized recovery note for model/provider switches and GitHub Actions runner restarts.

## Current state

- Status: RECOVERED — the stale autonomous branch was reconciled with the integrated `main`.
- Active backlog item: none newly started. This is the PR #16 recovery; its RUN-01 static contract was already adapted into `main`'s `src/eclipse/runtime/backends.py` (see `STATUS.md`, `CONTINUATION.md` and `AUTONOMOUS_BACKLOG.md`).
- Base branch: main
- Session ID: created by the autonomous controller at runtime and recorded in the runner log only; never place provider credentials here.
- Last verified checkpoint: `main` includes merged PRs #5, #6, #7, #10, #11, #12, #13, #14, #15, #17 and #18 plus the integrated-implementation commits `8dddf39`, `5ee46bf`, `ed07f38`, the runtime completion pass (`962436b`, `906222c`), the Windows CI repairs and the UI diagnostics work through `64ff0cd`; current `main` head at recovery was `8dfe683`.

## Current product reality

Implemented on main: bounded GGUF/Safetensors/Hugging Face inspectors, tokenizer/chat-template inventory, Model Atlas, Windows desktop shell, host discovery and static feasibility estimates, ranked six-provider/12-model free OpenCode pool.

Not yet implemented as a working integrated product: actual ECLIPSE-managed inference lifecycle, execution placement/profiles/telemetry, Capability Amplification tools/planner/sandbox/verification/recovery, Obsidian integration, real Agent chat/runtime, and full three-workspace integration.

## Recovery rules

1. Read this file, `AUTONOMOUS_BACKLOG.md`, `docs/AUTONOMOUS_ENGINEERING_PROTOCOL.md`, `STATUS.md` and `CONTINUATION.md`.
2. Inspect `git status`, `git log`, open PRs and the active CI evidence before doing anything.
3. Do not redo merged or verified work.
4. If the native OpenCode session still exists, continue its exact session ID and task using `opencode run --session <id> --model <next-approved-route>`.
5. If the runner/session no longer exists, reconstruct from this file, the merged commits, current branch diff, backlog status and validation logs. Do not claim that a new session is the same in-memory context.
6. Never include keys, raw environment values, private prompts or full sensitive logs in this note.

## Latest milestone result

Update this section after each milestone with changed files, commit/PR, selected model(s), retries/failovers, checks and the next acceptance step.

### Audit and repair — 2026-11-06 (setup engineer session)

- Audited PR #12: ranked routing, initial attempt + five retries, immediate failover on auth/quota/rate-limit/model errors, same-session continuation, credential scrubbing, protected-path draft policy and CI-repair resume are all present and unit-tested.
- Fixed: a context-length compaction call wrongly consumed one of the six calls for a model (the old `attempt -= 1` inside a `for` loop had no effect). Added a regression test that fails on the old code.
- Added: a test that fails CI if the controller's route order ever differs from the ranked table in `docs/FREE_MODEL_PROVIDER_POOL.md`.
- Still unproven: no live Actions run, live provider smoke test or real failover has happened yet. Activation requires the owner to merge PR #12 (it changes protected automation files, so it must stay draft until reviewed) and dispatch `ECLIPSE autonomous engineering` once.


### First live run failed — 2026-11-06 (run 42296217269)

- Cause 1: the controller passed `--standalone`, which OpenCode 1.19.5 does not have; every call printed CLI usage and exited non-zero.
- Cause 2: OpenCode rejects `opencode.json` when a model defines `limit.context` without `limit.output` (three Dahl/Z.AI models). `limit.output` is now 32768 for those three — a conservative client-side cap, not a measured provider maximum.
- Cause 3: a CLI/config error was classed as a retryable unknown failure, burning 6 calls on each of 12 routes (~8 min). It is now a fatal `configuration` failure that stops the run immediately.
- Guards added: the validator now rejects any model `limit` missing `context` or `output`; a test restricts the command line to flags present in 1.19.5.
- Verified against the real pinned CLI: config loads, the `eclipse-autonomous` agent resolves, a session ID is produced. A real provider call is still unproven (the sandbox used for this check has no network path to the providers).

### AUTO-04 independent review stage — 2026-11-06

- Base main: `acd7c41975fd6846fdfd4d7ac7c6616dd66765bb`; bootstrap PRs #12 and #13 are merged.
- Added `scripts/eclipse_review.py`: deterministic, read-only, model-independent review. It rejects seeded regressions (deleted test, newly added test skip) and false completion claims (placeholder `VERIFIED`, missing referenced test file, no changed test/CI record, new whole-project completion claim while backlog work remains).
- Wired the reviewer into `scripts/eclipse_autonomous.py` via `REVIEW_COMMAND` and `validation_commands()`; it runs after unit tests inside `validate_worktree`, so the same-session repair loop must pass it before the controller commits.
- Tests: new `tests/test_review.py` (20 tests, including a temporary-Git working-tree integration), 3 controller tests in `tests/test_autonomous_runner.py` (2 wiring + 1 `PYTHONPATH` regression) and 1 import-bootstrap subprocess test. Focused run passed 49 tests. Full portable suite recorded in `TESTING.md`.
- First live-run fix: the controller's `validation_environment()` omitted `PYTHONPATH`, so the `eclipse.*` test modules could not import and the unit-test gate failed with 10 errors. It now sets `PYTHONPATH=<repo>/src`; verified against `tests.test_hardware` with an empty parent `PYTHONPATH` (14 tests OK).
- Second live-run fix: the already-running controller still held the old `validation_environment` in memory, so the same import failure recurred. Added `tests/_bootstrap.py`, imported by every `eclipse`-importing test module, which inserts `<repo>/src` into `sys.path` when `PYTHONPATH` is absent. `tests/test_test_bootstrap.py` reproduces the controller's no-`PYTHONPATH` environment in a subprocess. Full suite now passes with and without `PYTHONPATH`.
- This changes protected controller/test paths, so the PR is draft for owner review + Windows CI. AUTO-04 remains `IN_PROGRESS` until merged. Next READY milestone: RUN-01.

### Recovery — PR #16 reconciled with the integrated main — 2026-11-13

- Trigger: the recovered PR #16 branch (`feature/eclipse-autonomous-42307488690-1`) was again stale relative to `origin/main`. `main` had advanced with the integrated implementation, the runtime completion pass and the UI diagnostics work (`8dddf39`…`64ff0cd`), while the branch's last resync stopped at `ed07f38`.
- Real reproducible failure: the controller's independent review gate runs `scripts/eclipse_review.py --base origin/main`, which compares the worktree with `origin/main`. The stale worktree appeared to delete `main`'s newer `tests/test_diagnostics.py` (and the added-but-nontest `src/eclipse/desktop/diagnostics.py`, `src/eclipse/runtime/benchmark.py` and `.github/scripts/run_tests.py`), so the review rejected the change set even though nothing was wrong with the branch's own product code.
- Fix — resynchronise, do not duplicate: the worktree was brought up to `origin/main` by taking `main`'s version of every tracked file, which restored the files above and un-reverted `main`'s newer work. The branch's own RUN-01 static runtime-contract work (`src/eclipse/core/runtime.py`, `tests/test_runtime_contract.py`, `tests/test_runtime_cli.py`) was recognised as already superseded: `main` commit `906222c` explicitly reconciled PR #16 by adapting the useful model-specific declaration comparison into `src/eclipse/runtime/backends.py` (`evaluate_model_support(...)` and the production `runtime-support` CLI) and recorded that the PR's duplicate `core/runtime.py` would not be merged. The duplicate `core/runtime.py` module and its duplicated CLI test module were therefore dropped instead of re-introduced, and the controller's own `__main__.py`/`core/__init__.py` from `main` (which already dispatch `runtime-support` through `app_cli`) were kept unchanged.
- Regression coverage preserved and strengthened: the branch's `tests/test_runtime_contract.py` was ported onto `main`'s production `evaluate_model_support`/`evaluate_controls` in `src/eclipse/runtime/backends.py`, adding direct unit coverage that `main` previously lacked (format/architecture/quantization/device/placement dimensions, the `hardware_present_backend_unvalidated` and `runtime_verified: false` guarantees, control validation, invalid-input rejection and the two-backend support-matrix report); `tests/test_recovery.py` still reproduces the stale-base shape in a temporary Git repository and pins both the single-file and PR #16 multi-file rejection/acceptance behaviour; `tests/test_packaging_spec.py` now guards that every PyInstaller `hiddenimport` in `packaging/eclipse-desktop.spec` resolves to a real module under `src/` and that the integrated `eclipse.runtime`, `eclipse.runtime.backends`, `eclipse.runtime.benchmark` and `eclipse.desktop.diagnostics` modules are explicitly packaged, so a broken spec fails fast instead of failing the remote Windows desktop build.
- Local gates actually run (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`): `python -m unittest discover -s tests` = **377 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed; `python -m compileall -q src tests scripts .github/scripts` OK; `python .github/scripts/validate_provider_pool.py` OK; `scripts/eclipse_review.py --base origin/main` accepted; `git diff --check origin/main` clean.
- Honest status: this recovery adds no new backlog item and changes no milestone status. It does not claim the Windows CI or the owner Windows/GPU/Obsidian gates; those remain the unresolved acceptance gates. The protected-path/draft decision is unchanged because the change set is confined to non-protected test and documentation files plus the reconciliation of already-merged product code.
