# Autonomous Session Handoff

**Purpose:** durable, sanitized recovery note for model/provider switches and GitHub Actions runner restarts.

## Current state

- Status: IN_PROGRESS — integrated product on `main`; RUN-05 executable placement planning implemented locally on `freebuff/112e97381b60e3079576fd9d`.
- Active backlog item: RUN-05 real-backend acceptance (owner Windows/Vulkan gate). Next independent candidate: CAP-03 web research/context retrieval or PREP-03 experiment framework.
- Base branch: `main` (`84ce050`). Product work from 7 November is merged; this session's placement work is unmerged.
- Session ID: created by the autonomous controller at runtime and recorded in the runner log only; never place provider credentials here.
- Controller: **blocked** by open PR #16 (`mergeable_state=dirty`, non-draft). PR #16 is superseded by `main` and should be closed by the owner, never merged.
- Last verified checkpoint: Windows CI green on `e27fec7` (runs #42330519701 / #42330519740); UI diagnostics merged via PR #17 and #18.

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

### Executable placement planning (RUN-05) — 2026-11-07

- Added `src/eclipse/runtime/placement.py` (planner + reconciliation) and wired it into `profiles.py`, `manager.py`, `app_cli.py` and the desktop Prepare & run panel.
- `resolve_profile` uses the planned split only when `gpu_layers` is not pinned; planned status and estimated bytes are stored in the profile payload. Loading records the plan; stopping records RAM reconciliation and marks VRAM unavailable.
- Tests: `tests/test_placement.py` 24 tests, one runtime load/stop evidence test, plus two offscreen desktop assertions. Portable suite **374 tests, OK, 22 skipped**. Qt could not run here (missing `libxkbcommon`, no root).
- Not verified: real backend acceptance of a planned split, actual VRAM allocation, multi-GPU splitting.

### AUTO-04 independent review stage — 2026-11-06

- Base main: `acd7c41975fd6846fdfd4d7ac7c6616dd66765bb`; bootstrap PRs #12 and #13 are merged.
- Added `scripts/eclipse_review.py`: deterministic, read-only, model-independent review. It rejects seeded regressions (deleted test, newly added test skip) and false completion claims (placeholder `VERIFIED`, missing referenced test file, no changed test/CI record, new whole-project completion claim while backlog work remains).
- Wired the reviewer into `scripts/eclipse_autonomous.py` via `REVIEW_COMMAND` and `validation_commands()`; it runs after unit tests inside `validate_worktree`, so the same-session repair loop must pass it before the controller commits.
- Tests: new `tests/test_review.py` (20 tests, including a temporary-Git working-tree integration), 3 controller tests in `tests/test_autonomous_runner.py` (2 wiring + 1 `PYTHONPATH` regression) and 1 import-bootstrap subprocess test. Focused run passed 49 tests. Full portable suite recorded in `TESTING.md`.
- First live-run fix: the controller's `validation_environment()` omitted `PYTHONPATH`, so the `eclipse.*` test modules could not import and the unit-test gate failed with 10 errors. It now sets `PYTHONPATH=<repo>/src`; verified against `tests.test_hardware` with an empty parent `PYTHONPATH` (14 tests OK).
- Second live-run fix: the already-running controller still held the old `validation_environment` in memory, so the same import failure recurred. Added `tests/_bootstrap.py`, imported by every `eclipse`-importing test module, which inserts `<repo>/src` into `sys.path` when `PYTHONPATH` is absent. `tests/test_test_bootstrap.py` reproduces the controller's no-`PYTHONPATH` environment in a subprocess. Full suite now passes with and without `PYTHONPATH`.
- This changes protected controller/test paths, so the PR is draft for owner review + Windows CI. AUTO-04 remains `IN_PROGRESS` until merged. Next READY milestone: RUN-01.
