# Autonomous Session Handoff

**Purpose:** durable, sanitized recovery note for model/provider switches and GitHub Actions runner restarts.

## Current state

- Status: ACTIVE
- Active backlog item: RUN-01 (runtime capability contract) implemented locally this run; next READY backend-independent item is PREP-01 (source identity, checksums and prepared-variant registry).
- Note: the PR #16 recovery of 2026-11-06 did not start PREP-01; it re-synchronised the stale branch with `main` (PR #15) so the independent review gate passes. See "Recovery — stale branch" below.
- Base branch: main
- Session ID: created by the autonomous controller at runtime and recorded in the runner log only; never place provider credentials here.
- Last verified checkpoint: main includes merged PRs #5, #6, #7, #10 and #11.

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

### RUN-01 runtime capability contract — 2026-11-06

- Base: branch created from main at `acd7c41975fd6846fdfd4d7ac7c6616dd66765bb` (bootstrap PRs #12/#13 merged). Working tree was clean and matched `origin/main` before this run.
- Added `src/eclipse/core/runtime.py`: `BackendCapabilities`, `DeviceSupport`, `ControlSupport` contract with strict validation and JSON manifest round-trip (`load_capabilities`); `evaluate_model_support(...)` and `evaluate_controls(...)` produce an evidence-labelled `eclipse_runtime_support` matrix. Status vocabulary: `declared_supported` / `unsupported` / `unknown`; observed NVIDIA GPU for CUDA is `hardware_present_backend_unvalidated`; `runtime_verified` is always `false`.
- Wired `src/eclipse/core/__init__.py` exports and the `runtime-support` CLI command in `src/eclipse/__main__.py` (model path plus `--capabilities manifest.json`, optional `--placement` and repeatable `--control`).
- Tests: new `tests/test_runtime.py` (24) and `tests/test_runtime_cli.py` (6) cover supported/unsupported/unknown formats, architectures, tensor types, CPU/CUDA/Vulkan devices, placement modes, controls and restart flags, manifest validation and CLI paths.
- Checks actually run (Linux, Python 3.12.16, no PySide6): focused 30 tests OK; full `python -m unittest discover -s tests` = 269 tests OK, 11 skipped, with and without `PYTHONPATH`; `compileall` OK; `git diff --check` clean.
- Limitation: static contract only. No backend is integrated; no model load/generate/stop, telemetry or performance evidence exists. RUN-02 (real Windows llama.cpp/Vulkan adapter) remains the integration gate with owner-only Windows validation, so only that gate is `WAITING_FOR_OWNER_VALIDATION`.
- Next READY backend-independent milestone: PREP-01.

### Recovery — stale branch versus main (PR #16) — 2026-11-06

- Trigger: the recovered run received CI evidence showing the "Python checks" and "Windows desktop build" workflow runs in `action_required` state with no retrievable logs (the runs had not been approved/executed). The agent is not able to change GitHub-side run approval; the reproducible local failure was used instead.
- Real reproducible failure: the branch was cut from `main` at PR #14 (`37419e9`) and therefore does not contain PR #15 (`84ce050`). The controller's independent review gate (`scripts/eclipse_review.py --base origin/main`, run inside `validate_worktree`) compares the working tree against `origin/main` and therefore reported two **deleted test files**, `tests/test_autonomous_orphans.py` and `tests/test_autonomous_parking.py`, and rejected the change set. Nothing was wrong with the RUN-01 product code; the branch was simply stale.
- Fix: re-synchronised the branch with `main` by restoring the three files PR #15 changed — `scripts/eclipse_autonomous.py`, `tests/test_autonomous_orphans.py` and `tests/test_autonomous_parking.py` — from `origin/main`. No product code or test was weakened; the branch now contains the current controller test suite instead of appearing to delete it.
- Regression coverage: `tests/test_recovery.py` reproduces the stale-base shape deterministically in a temporary Git repository and asserts (a) a branch behind an advanced base is rejected as a deleted test and (b) incorporating the base advance accepts the identical product change.
- Local gates actually run (Linux, Python 3.12.16, PySide6 not installed): `python -m unittest discover -s tests` = **283 tests OK, 11 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed; `python -m compileall -q src tests .github/scripts scripts` OK; `python .github/scripts/validate_provider_pool.py` OK; `scripts/eclipse_review.py --base origin/main` accepted; `git diff --check` clean.
- Consequence recorded honestly: restoring `scripts/eclipse_autonomous.py` and the `tests/test_autonomous_*` files touches controller/test paths that the controller classifies as protected, so this recovered PR is expected to remain owner-review only rather than auto-merge.
- Not changed by this recovery: no new backlog item, no change to any milestone status, no commit/push/merge by the agent.
