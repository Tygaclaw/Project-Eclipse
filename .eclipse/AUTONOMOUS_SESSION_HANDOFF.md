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
- Second real failure — append-only document conflict: the recovery note had been appended to the end of `CONTINUATION.md` and `STATUS.md` immediately after `main`'s own new end-of-file sections. Because the branch was cut before `main` added those sections, both sides inserted at the same old EOF location, so `git merge-tree origin/main HEAD` still reported content conflicts in both files and GitHub kept the PR `dirty`/unmergeable even though every tracked file already matched `main`. Fix: the duplicate recovery sections were removed from those two files; the authoritative, fully detailed recovery record remains here and in `TESTING.md`. The resulting tree has no conflict against `origin/main`.
- CI evidence inspected before repairing: the only Windows workflow runs for this PR were on `ab2af36`/`e409711` and both concluded `action_required` (an approval gate), not a test failure; head `e96dece` had no project workflow run. The actionable failure was therefore the dirty/unmergeable merge state, not a failing unit or packaging test.
- Regression coverage preserved and strengthened: the branch's `tests/test_runtime_contract.py` was ported onto `main`'s production `evaluate_model_support`/`evaluate_controls` in `src/eclipse/runtime/backends.py`, adding direct unit coverage that `main` previously lacked (format/architecture/quantization/device/placement dimensions, the `hardware_present_backend_unvalidated` and `runtime_verified: false` guarantees, control validation, invalid-input rejection and the two-backend support-matrix report); `tests/test_recovery.py` reproduces the stale-base shape in a temporary Git repository, pins both the single-file and PR #16 multi-file rejection/acceptance behaviour, and now also pins the append-only documentation conflict plus the non-overlapping placement that merges cleanly; `tests/test_packaging_spec.py` now guards that every PyInstaller `hiddenimport` in `packaging/eclipse-desktop.spec` resolves to a real module under `src/` and that the integrated `eclipse.runtime`, `eclipse.runtime.backends`, `eclipse.runtime.benchmark` and `eclipse.desktop.diagnostics` modules are explicitly packaged, so a broken spec fails fast instead of failing the remote Windows desktop build.
- Local gates actually run (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`): `python -m unittest discover -s tests` = **379 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed; `python -m compileall -q src tests scripts .github/scripts` OK; `python .github/scripts/validate_provider_pool.py` OK; `scripts/eclipse_review.py --base origin/main` accepted; `git merge-tree --write-tree --messages origin/main <recovery-tree>` = **clean (exit 0)**; `git diff --check origin/main` clean.
- Honest status: this recovery adds no new backlog item and changes no milestone status. It does not claim the Windows CI or the owner Windows/GPU/Obsidian gates; those remain the unresolved acceptance gates. The protected-path/draft decision is unchanged because the change set is confined to non-protected test and documentation files plus the reconciliation of already-merged product code.

### Recovered run — PR #16 `action_required` CI gate fix (AUTO-03) — 2026-11-14

- Trigger: the recovered PR #16 branch had two current-head workflow runs (`Python checks` #43495367336 and `Windows desktop build` #43495367455) whose conclusion was `action_required`, and `gh run view <id> --log-failed` returned `failed to get run log: log not found`. The controller's `remote_ci_failure_context` counted `action_required` as a failed run, so the recovery prompt handed the model "evidence" that contained no diagnostic content and could never be repaired by editing code.
- Root cause (AUTO-03): `remote_ci_failure_context` included `cancelled` and `action_required` in its failed-run set and unconditionally fetched logs. `action_required` is an approval/pending gate with no log; `cancelled` is likewise not a code failure.
- Fix: added pure `classify_ci_run` / `select_current_head_ci_runs` helpers plus `current_head_ci_runs`; `remote_ci_failure_context` now collects logs only for `failure`/`timed_out` (`REPAIRABLE_CI_CONCLUSIONS`). New `ci_requires_owner_approval` / `owner_approval_required_message` detect an exact-current-head `action_required` run with no repairable failure. All three CI-handling sites (`resume_existing_pr` pre-recovery, its CI-repair loop, and the `main` post-PR repair loop) now print `OWNER_APPROVAL_REQUIRED` and return 9 (park/wait) instead of invoking the model or burning the CI-repair budget.
- Regression coverage: `tests/test_autonomous_runner.py` adds `CiRunClassificationTests` (classification of `action_required`/`failure`/`timed_out`/`success`/`skipped`/`cancelled`/incomplete and exact-head selection) and `RemoteCiFailureContextTests` (a mocked `gh` proves an `action_required` run produces empty context, is never sent to `run view`, a real failure log still takes priority, and `owner_approval_required_message` returns the park message only for an approval gate).
- Local gates run (Linux, Python 3.12.16, `QT_QPA_PLATFORM=offscreen`): focused `tests.test_autonomous_runner` = 37 tests OK; full-suite, compileall, provider validation, independent review, whitespace and merge-tree results are recorded in `TESTING.md`.
- Mergeability: `STATUS.md` and `CONTINUATION.md` were deliberately left matching `origin/main`. Appending a new section at their end re-creates the append-only EOF conflict the 2026-11-13 recovery had to undo, because the branch's merge base predates `main`'s own end-of-file sections. The authoritative record therefore lives here, in `TESTING.md` and in the `AUTO-03` backlog row; `git merge-tree` against `origin/main` is clean.
- Honest status: this continues AUTO-03 (still `IN_PROGRESS`); it marks no milestone complete and claims no Windows or owner gate. Because it edits the protected controller and its protected tests, the PR remains draft for owner review as before.
