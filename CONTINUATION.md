# ECLIPSE Continuation Record

## Current checkpoint

- Repository: `Tygaclaw/Project-Eclipse`.
- Default branch: `main`.
- Audited main head when this record was rewritten: `acd7c41975fd6846fdfd4d7ac7c6616dd66765bb`.
- Autonomous bootstrap PRs #12 and #13 are merged to `main`; a live autonomous run created the current `feature/eclipse-autonomous-*` branch.
- Mainline PRs #5, #6, #7, #10 and #11 are merged. PRs #8 and #9 are obsolete, closed and superseded.
- The existing product foundation includes static model inspection/Atlas, tokenizer/chat-template intelligence, static hardware feasibility, and the three-workspace Windows desktop shell.

## Product truth

The Model Intelligence workspace has genuine static inspection and feasibility foundations. It does not yet have a managed inference lifecycle, executable placement planner, runtime profiles or full telemetry. Capability Amplification, Obsidian and the ECLIPSE Agent remain future implementation work beyond the existing honest placeholder screens. Do not report the product finished until the integrated backlog and release gates are satisfied.

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

Use `AUTONOMOUS_BACKLOG.md` as the canonical queue. After the bootstrap controller is merged, continue with:
1. Finish live provider smoke tests and failover/recovery acceptance.
2. Build a real inference backend adapter compatible with the existing Windows/Vulkan setup, preserving the known-good configuration.
3. Implement true load/generate/stop/unload lifecycle, execution profiles, actual runtime allocation and telemetry.
4. Implement reversible preparation and integrity/rollback.
5. Build the shared Capability Core: planning, research/context, tools, sandbox, verification, recovery, loop detection, corrections and skills.
6. Integrate Obsidian with scoped retrieval and approval.
7. Implement the full Agent chat/runtime, history, attachments, memory, tools, approvals and Stop.
8. Complete three-workspace integration, UX and the remaining four evaluations.
9. Complete release and final bundled Windows 11/Vulkan/Obsidian owner validation.

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

## RUN-01 runtime capability contract — 6 November 2026

Base main: `acd7c41975fd6846fdfd4d7ac7c6616dd66765bb`.

Implemented:
- `src/eclipse/core/runtime.py`: `BackendCapabilities`, `DeviceSupport`, `ControlSupport` contract with strict validation; `from_dict`/`to_dict` JSON manifest round-trip; `load_capabilities(path)`; `evaluate_model_support(...)` producing an evidence-labelled `eclipse_runtime_support` matrix; `evaluate_controls(...)`.
- Per-dimension status vocabulary is `declared_supported` / `unsupported` / `unknown`. Missing atlas facts, an undeclared adapter capability, an unenumerated GPU API (Vulkan/SYCL/Metal) or a missing host snapshot stay `unknown`. An observed NVIDIA GPU for a CUDA device is `hardware_present_backend_unvalidated`, never supported. `runtime_verified` is always `false`; the matrix is a declaration comparison and does not prove loading, generation or speed.
- `src/eclipse/core/__init__.py` exports the contract and evaluator; `src/eclipse/__main__.py` adds the `runtime-support` command (model path plus `--capabilities manifest.json`, optional `--placement` and repeatable `--control`).
- `tests/test_runtime.py` (24 tests) and `tests/test_runtime_cli.py` (6 tests) cover supported/unsupported/unknown formats, architectures, tensor types, CPU/CUDA/Vulkan devices, placement, controls/restart flags, manifest validation and JSON round-trip, plus CLI success and error paths.

Verification actually run locally (Linux, Python 3.12.16, PySide6 not installed): focused `tests.test_runtime` + `tests.test_runtime_cli` = 30 tests OK; full `python -m unittest discover -s tests` = 269 tests OK, 11 skipped, both with `PYTHONPATH=src` and with `PYTHONPATH` removed; `python -m compileall -q src tests scripts .github/scripts` passed; `git diff --check` clean.

This is a static contract milestone, not a working inference adapter. No backend is integrated and the CLI reports `not_integrated` unless a manifest declares otherwise. RUN-02 (Windows-compatible llama.cpp adapter that connects to the existing Vulkan setup) remains the runtime integration gate and has owner-only Windows validation. Next READY backend-independent milestone after RUN-01 is PREP-01 (source identity, checksums and prepared-variant registry).

