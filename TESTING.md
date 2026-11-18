# Testing Strategy

## Current automated suite

The core inspection suite uses only Python's standard library and synthetic binary fixtures. The desktop tests additionally require PySide6 `6.12.0` and skip when it is not installed. The tokenizer review-correction suite adds cases for bounded embedded/standalone templates, JSON budgets, token previews, privacy, symlinks and compatibility; use the latest CI run for the authoritative test count.

- GGUF v2/v3 and big-endian v3 header handling.
- Metadata and tensor descriptor parsing.
- Unknown tensor type preservation.
- Bounded array previews.
- Invalid magic/version and truncated headers.
- Excessive counts, duplicate keys/names, invalid alignment, bad dimensions and out-of-region offsets.
- Read-only behavior, path privacy and JSON CLI output.
- GGML type registry block/type sizes, derived exact GGUF storage bytes, non-block-multiple rows and truncated-file warnings.
- Safetensors header parsing, metadata, unknown dtypes, shape/range mismatch warnings, overlapping/out-of-range/negative offsets, invalid JSON, header limits and read-only behavior.
- Hugging Face folder discovery: `config.json` summaries, shard-index weight-map parsing, referenced/missing/unreferenced shard handling, bounded lazy directory enumeration, capped control-file reads, path-separator rejection, symlink skipping and read-only behavior.
- Model Atlas core: GGUF/Safetensors/folder dispatch, tensor-element and storage aggregation, evidence labels, missing/corrupt shard incompleteness, unreferenced-shard exclusion, tensor-data total reconciliation, unsupported input and shard limits, plus the tokenizer section for folder/GGUF sources and the honest unavailable section for Safetensors.
- Tokenizer and chat templates (`tests/test_tokenizer.py`): asset inventory (`tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`, `added_tokens.json`, `vocab.json`, `vocab.txt`, `merges.txt`, SentencePiece models as inventory-only), observed/declared vocabulary candidates, added and special tokens, aggregate and per-file JSON/template byte limits, aggregate template-count limits shared across embedded and file-based sources, bounded token-entry work, clipped previews, nested/root symlink rejection, invalid UTF-8 templates, named embedded-template lists, legacy/modern processor-template incompatibility, path privacy, source immutability, GGUF tokenizer metadata, CLI limits and no-execution invariants.
- Desktop boundary (`tests/test_atlas_client.py`): argument-list command construction, a real synthetic GGUF integration run, invalid JSON/contract rejection, payload-safety invariant rejection, bounded output, stderr propagation, cancellation and timeout.
- Desktop smoke (`tests/test_desktop_smoke.py`): offscreen Qt startup with a temporary `AppContext`, all three navigation destinations, real Capability tabs and controls, Agent composer/conversation state, Prepare & run panel state, persisted light/dark toggle, empty state and Atlas section rendering, including the "Tokenizer and chat format" card and the `Declared` evidence label.
- Shared Core foundation (`tests/test_core_foundation.py`): settings/home layout, event bus ordering and failure isolation, path scoping/approval/redaction/command validation, SQLite models/variants/runs/conversations/attachments/tasks/corrections/knowledge metadata and settings persistence.
- Preparation (`tests/test_preparation.py`): index/copy packages, hashes and lineage, source identity, idempotence, corruption detection, safe removal and quantization unavailability without a real tool.
- Runtime (`tests/test_runtime.py` + `tests/fixtures/fake_llama_server.py`): a real spawned HTTP/SSE server process, streamed text and usage, tool-call assembly, cancellation, managed lifecycle, observed context, measured telemetry, stop/process exit, startup failure cleanup, attach-mode ownership, binary discovery, saved profiles, last-known-good marking, restore after stop and repeated benchmark aggregation.
- Capability (`tests/test_capability.py`): watchdog routing, plans/acceptance criteria/drift, path escape rejection, approval-denied writes, real command/verification subprocesses, verification failure reporting, loop detection, task completion only with passing verification, missing-runtime handling, correction promotion evidence gates and the knowledge Inbox/approval/no-overwrite workflow.
- Agent (`tests/test_agent.py`): conversation persistence/search/rename/delete, streaming deltas, attachment copy and one-time context inclusion, tool execution with persisted metadata, honest runtime-error messages and workspace-free chat.
- CLI (`tests/test_app_cli.py`): registry, prepare/verify, knowledge propose/approve/search, correction evidence gates, app status, check detection, task plan creation, backend matrix, model-specific `runtime-support`, saved-profile list/delete and quantization failure path.
- Independent review (`tests/test_review.py`): backlog table parsing, seeded-regression rejection (deleted test file, newly added test skip), false completion-claim rejection (placeholder evidence, missing referenced test, no changed test/CI record, completion claim while work remains), acceptance of legitimate verification, and real temporary-Git working-tree integration plus CLI exit codes.
- Controller review wiring (`tests/test_autonomous_runner.py`): `validation_commands()` includes a separate `scripts/eclipse_review.py` gate distinct from the implementing controller. It also covers CI-run classification for the recovery loop: `action_required` is an approval gate (never sent to `run view`, never packaged as `log not found` evidence), `failure`/`timed_out` are repairable, success/skipped/cancelled/incomplete are ignored, a real failure log still takes priority over an approval gate, `owner_approval_required_message` returns the park message for an approval gate but not for a real failure, and `existing_pr_owner_review_message` early-parks a protected non-checkpoint PR while leaving checkpoint drafts resumable.
- Runtime support contract (`tests/test_runtime_contract.py`): direct unit coverage of `evaluate_model_support`/`evaluate_controls` in `eclipse.runtime.backends` — supported/unsupported/unknown format, architecture, tensor-type, device (CPU/CUDA/ROCm/Vulkan/remote) and placement dimensions, the `hardware_present_backend_unvalidated` and `runtime_verified: false` guarantees, control validation against the declaration, invalid-input rejection and the two-backend support matrix report.
- Recovery (`tests/test_recovery.py`): the stale-base shape is reproduced in a temporary Git repository and the independent reviewer rejects the apparent deleted test until the base advance is incorporated, including the multi-file shape that the PR #16 resynchronisations fixed. It also reproduces the append-only documentation conflict — a branch that copies `main`'s new end-of-file section and then appends its recovery note is still unmergeable — and verifies that placing the note in a pre-existing region merges cleanly.
- Failed-PR recovery end to end (`tests/test_autonomous_runner.py`): `EndToEndFailedPrRecoveryTests` drives the real `resume_existing_pr` path against a temporary Git repository with a real bare `origin`. Only `gh` and `run_agent_with_failover` are mocked; Git fetch/switch/commit/push and the controller safety guards run for real. It proves a failed non-draft PR is repaired on the same branch and session (the follow-up CI repair passes `initial_session_id`), no duplicate branch or `pr create` happens, the recovery prompt carries a real failure log instead of `log not found`, and the merge occurs only after the checks turn green. The same fixture proves the exact sanitized `action_required` run pairs (#43567081759/#43567081760, #43601410296/#43601410276 and #43648458309/#43648458292) park with `OWNER_APPROVAL_REQUIRED` before any model call or `run view`, and that a non-draft PR changing a protected path (`SECURITY.md`) returns `OWNER_REVIEW_REQUIRED` before any `gh` call, CI check, commit or merge. Separately, `failure_log_is_available` rejects empty logs and GitHub CLI `failed to get run log`/`log not found` notices, so even a genuinely failed run with an unavailable log cannot become fabricated evidence. As defence in depth, `approval_gate_evidence`/`approval_gate_evidence_message` recognise the legacy `action_required` chunk format, and `ci_evidence_has_log`/`unusable_repair_evidence_message` reject a `failure` chunk whose body is only an unavailable-log notice; `build_repair_prompt` refuses to emit a repair instruction for either, and all three repair sites (including the PR-body/check-output fallback) park successfully (exit 0) before any model call. A mixed evidence set with at least one readable log still repairs normally.
- Windows packaging guard (`tests/test_packaging_spec.py`): every PyInstaller `hiddenimport` in `packaging/eclipse-desktop.spec` must resolve to a real module under `src/`, and the integrated `eclipse.runtime`, `eclipse.runtime.backends`, `eclipse.runtime.benchmark` and `eclipse.desktop.diagnostics` modules must be listed, so a broken packaging spec fails fast instead of failing the remote Windows desktop build.

Run (desktop tests need PySide6; use an offscreen platform on headless machines):

```powershell
$env:PYTHONPATH = "src"
py -3 -m unittest discover -s tests -v
```

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m unittest discover -s tests -v
```

## Local verification evidence

- Windows CI close-out `e27fec7`: Python checks [#42330519701](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42330519701) succeeded on Windows Python 3.11, 3.12, 3.13 and 3.14; Windows desktop build [#42330519740](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42330519740) passed the full Qt/offscreen suite, PyInstaller build, packaged backend smoke test, ZIP creation and artifact upload. Artifact `ECLIPSE-windows-x64` ID `13556659342`, 52,935,974 bytes, SHA-256 `2ff2029fc52363a2ad6d399807417708f02671ee4fd8d80bcea50a811c3c40cc`, expires 2026-11-21.
- Local Python 3.11.16 (Linux, no PySide6): **340 tests, OK, 13 skipped** (optional Qt tests). Python 3.12 with PySide6 `6.12.0`: **340 tests, OK**. The first Windows push-triggered run exposed Python-script launch, SQLite `rowid` ordering and SQLite cleanup failures; those were fixed and the final Windows runs above passed.
- Dependency audit (Linux sandbox, 7 November 2026): `pip-audit 2.10.1 -r requirements-desktop.txt` audited PySide6 6.12.0, its module wheels/shiboken6, PyInstaller 6.22.3 and pyinstaller-hooks-contrib 2026.9 with **no known vulnerabilities**. Scanning the dev venv surfaced 12 advisories for `pip` 24.0; upgrading that tooling to `pip` 26.3 and re-scanning gave no known vulnerabilities. This is advisory matching only, not a binary/malware or Qt CVE review.
- Integrated product implementation, local sandbox (Linux, Python 3.12, PySide6 `6.12.0` in the project virtual environment): `QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m unittest discover -s tests` ran **340 tests, OK**, including the real spawned inference server, capability/agent execution, CLI and Qt smoke tests. A separate CLI run started a real fake HTTP server, ran `eclipse chat --endpoint ... --json`, and received `Hello from the fake server.` with state `ready`; metrics are recorded as generation runs. A second real CLI run ran `eclipse benchmark --endpoint ... --runs 2 --warmup 1 --json` and returned `status=ok`, two samples, median TTFT `0.0016 s` and median throughput `122.645 tok/s` against the test double. `eclipse backends`, `runtime-support` and the full CLI help were also exercised. These test-double numbers are not a model benchmark and not a substitute for the owner's real Windows/GPU validation.
- AUTO-04 review stage, local sandbox (Linux, Python 3.12.16, PySide6 not installed): focused `tests.test_review` + `tests.test_autonomous_runner` + `tests.test_test_bootstrap` ran **49 tests, OK** (20 reviewer + 28 controller + 1 import-bootstrap); full `python -m unittest discover -s tests` ran **239 tests, OK, 11 skipped** (the optional Qt desktop smoke tests) both with `PYTHONPATH=src` and with `PYTHONPATH` removed; `python -m compileall -q src tests .github/scripts scripts` passed. The reviewer also accepted this milestone's own working-tree change set against `origin/main`.
- First live controller validation exposed a real regression in the controller, not the product: `validation_environment()` used an allowlist without `PYTHONPATH`, so `unittest discover` failed to import every `eclipse.*` test module (10 errors). The fix sets `PYTHONPATH=<repo>/src`; re-running the controller's own environment against `tests.test_hardware` with an empty parent `PYTHONPATH` gave **14 tests, OK**.
- Second live validation repeated the failure because the already-running controller process held the pre-fix function in memory. Test-level robustness added: `tests/_bootstrap.py` inserts `<repo>/src` into `sys.path` when `PYTHONPATH` is absent, and every `eclipse`-importing test module imports it. The no-`PYTHONPATH` child process scenario is regression-tested by `tests/test_test_bootstrap.py`. Full suite without `PYTHONPATH`: **239 tests, OK, 11 skipped**.
- Hardware-feasibility close-out, local sandbox (Linux, Python 3.13.18, PySide6 not installed): `python -m unittest discover -s tests` ran **190 tests, OK, 11 skipped** (the optional Qt desktop smoke tests); `python -m compileall -q src tests .github/scripts` passed. 6 of the 190 are new (4 `nvidia-smi` lookup cases, 2 KV-assumption cases). Synthetic fixtures on a non-Windows host only.
- Historical pre-review local result: **131 tests passed** on Python 3.14.4 with PySide6 `6.12.0`; historical only.
- Corrected PR #5 code head `ce8fcb679373129365a4fb067a50b4777570330f`: Python checks [#42198091790](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198091790) passed Python 3.11, 3.12, 3.13 and 3.14, **145 tests per job**, with 8 Qt tests skipped in this core-only matrix.
- The same corrected code head's Windows desktop run [#42198092066](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198092066) passed **145 tests including Qt**, PyInstaller build, packaged backend smoke test, ZIP creation and artifact upload. Artifact ID `13493741785`, 50,965,917 bytes, SHA-256 `3d6220bbf9736d39fd840fc65b3b9c82eb99f6d779af4632b0ef49aa603f1a49`.

## PR #16 recovery evidence — 13 November 2026

The recovered PR #16 branch (`feature/eclipse-autonomous-42307488690-1`) was stale against the integrated `main`; the independent reviewer compares the worktree with `origin/main` and rejected the branch as deleting `main`'s newer `tests/test_diagnostics.py`. The worktree was resynchronised with `origin/main`; the branch's superseded duplicate static runtime contract was dropped in favour of `main`'s adapted `evaluate_model_support(...)`/`runtime-support` in `src/eclipse/runtime/backends.py`, and the branch's contract tests were ported onto that production evaluator. The first recovery still appended its note to the end of `CONTINUATION.md` and `STATUS.md` after `main`'s new end-of-file sections, which reproduced a merge conflict; those duplicate sections were removed and the record remains here and in the session handoff. The following was actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest discover -s tests` — **379 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK.
- `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git merge-tree --write-tree --messages origin/main <recovery-tree>` — clean (exit 0), no conflicts.
- `git diff --check origin/main` — clean.

Windows Qt/PyInstaller CI and the owner Windows/GPU/Obsidian gates remain the unresolved acceptance gates.

## PR #16 `action_required` recovery evidence — 14 November 2026

The recovered PR #16 branch had two current-head workflow runs (`Python checks` #43495367336 and `Windows desktop build` #43495367455) concluding `action_required`; `gh run view <id> --log-failed` returned `failed to get run log: log not found`. The controller had counted `action_required` as a failed run and built the recovery prompt from that empty log, so the model was asked to fix a check that was only waiting for approval. The fix (AUTO-03) collects logs only for `failure`/`timed_out` runs and parks the PR with `OWNER_APPROVAL_REQUIRED` when the exact current head is blocked solely by an `action_required` gate; `owner_approval_required_message` centralises this for all three CI-handling sites (`resume_existing_pr` recovery, its CI-repair loop, and the post-PR repair loop). A non-checkpoint existing PR whose change set is owner-review-only is additionally parked by `existing_pr_owner_review_message` before any recovery model runs, so a protected PR cannot be re-fed log-less CI evidence. Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- Focused `python -m unittest tests.test_autonomous_runner -v` — **45 tests OK** (5 `CiRunClassificationTests`, 7 mocked-`gh` `RemoteCiFailureContextTests`, 3 `ExistingPrOwnerReviewTests`, 2 real-Git `EndToEndFailedPrRecoveryTests`).
- `python -m unittest discover -s tests` — **396 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `EndToEndFailedPrRecoveryTests` runs `resume_existing_pr` against a temporary repository with a real bare `origin` and real Git commit/push; only `gh` and the OpenCode child are mocked. It asserts same-branch/same-session repair, no duplicate PR, a real failure log in the prompt and a merge only after green checks; its second case proves the exact sanitized `action_required` pair returns 9 without an agent call, `run view`, commit or merge.
- `failure_log_is_available` drops empty logs and GitHub CLI `failed to get run log`/`log not found` notices, so an unavailable log can never be packaged as code-failure evidence.
- `python -m compileall -q src tests scripts .github/scripts` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK.
- `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git merge-tree --write-tree --messages origin/main <recovery-tree>` — clean (exit 0), no conflicts.
- `git diff --check origin/main` — clean.

The mocked-`gh` tests are the concrete regression: a current-head `action_required` run produces an empty failure context and is never passed to `run view`, which is exactly the failure that produced the `log not found` recovery prompt.

### Recovered run — latest approval-gate evidence and protected-PR early park — 14 November 2026

The next recovered run again carried the sanitized pair `Python checks` #43601410296 and `Windows desktop build` #43601410276, both `action_required` with `failed to get run log: log not found`. This is still an approval gate, not a code failure, so no product change was required; the existing AUTO-03 behaviour was preserved and the regression evidence was extended instead of starting a new backlog item. Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner -v` — **47 tests OK**. The new `test_latest_sanitized_action_required_evidence_parks_without_a_model_call` pins the #43601410296/#43601410276 pair as an empty failure context with `OWNER_APPROVAL_REQUIRED` and no `run view`; `test_protected_non_draft_pr_parks_before_ci_checks_or_a_model_call` drives the real `resume_existing_pr` Git path for a non-draft PR that touches `SECURITY.md`, proving `OWNER_REVIEW_REQUIRED` is returned before any `gh` call, CI check, model call, commit or merge.
- `python -m unittest discover -s tests` — **398 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK.
- `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean.

The remote checks are approval gates that only the owner can approve; they are not evidence of a failing build, and this pass claims no Windows or owner gate.

### Recovered run — repair-prompt hardening — 14 November 2026

The validation prompt reproduced the concrete defect: `build_repair_prompt` told the model to "Diagnose the concrete failure" using only legacy `action_required` chunks (#43601410296/#43601410276) and `failed to get run log: log not found`. The branch now refuses that evidence at every layer: `ci_run_conclusions`/`approval_gate_evidence` classify the legacy chunks, `build_repair_prompt` returns an `OWNER_APPROVAL_REQUIRED` park instruction instead of a repair instruction, and `resume_existing_pr` (including its PR-body/check-output fallback), its CI-repair loop and the post-PR repair loop exit 9 before any model call. This is defence in depth for stale/external callers that still pass the old format; normal runs are already classed by `classify_ci_run`. Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner` — **51 tests OK**, including the legacy-chunk detection, real-failure/mixed rejection, `build_repair_prompt` refusal and a real-Git `resume_existing_pr` case that forces legacy evidence through the fallback and asserts exit 9 with no agent call, `run view`, commit or merge.
- `python -m unittest discover -s tests` — **402 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK.
- `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean; `git merge-tree` against `origin/main` — clean.

### Recovered run — unavailable-log evidence — 14 November 2026

The next validation prompt used `Python checks` #43648092677 and `Windows desktop build` #43648092720, again `action_required` with `failed to get run log: log not found`. The committed `approval_gate_evidence` classifies that exact sanitized block correctly, which confirms the prompt came from the pre-fix controller running on `main` (the workflow checkouts `${{ github.ref }}`). A remaining gap was still closed: a genuine `failure` run with no readable log could reach `build_repair_prompt` via a stale/external caller. `ci_evidence_has_log` now checks each chunk, `unusable_repair_evidence_message` reports `CI_EVIDENCE_UNAVAILABLE`, `build_repair_prompt` refuses to emit a repair instruction, and all repair sites (including the fallbacks) park before a model call; mixed evidence with one readable log still repairs. Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner` — **55 tests OK**.
- `python -m unittest discover -s tests` — **406 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts packaging` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK; `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean; `git merge-tree` against `origin/main` — clean.

The #43648092677/#43648092720 runs remain approval gates; only the owner can approve them or merge this protected PR. Merging (or dispatching the workflow on this branch) is required before the controller on `main` stops generating these prompts.

### Recovered run — successful park and current evidence — 14 November 2026

The validation prompt then carried `Python checks` #43648458309 and `Windows desktop build` #43648458292, again `action_required` with `failed to get run log: log not found`. The committed branch already classifies that exact block (`approval_gate_evidence` returns true, verified directly against the sanitized text), so the prompt is still emitted by the pre-fix controller executing from `main`. The remaining actionable issue was that a deliberate owner-approval park returned exit 9, which marks the autonomous workflow run as failed even though parking is the correct outcome. Owner-approval and unusable-evidence parks now return **0** with the `OWNER_APPROVAL_REQUIRED`/`CI_EVIDENCE_UNAVAILABLE` message, while genuine failures still return their previous non-zero codes and are repaired. The exact #43648458309/#43648458292 pair is pinned in the tests. Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner` — **56 tests OK**.
- `python -m unittest discover -s tests` — **407 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts packaging` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK; `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean; `git merge-tree` against `origin/main` — clean.

The remote runs remain approval gates. Only the owner can approve them or merge this protected PR; merging or dispatching the workflow on this branch is required before the controller on `main` stops generating these prompts.

### Recovered run — newest approval-gate evidence pinned — 15 November 2026

The recovery prompt carried `Windows desktop build` #43649302769 and `Python checks` #43649302743, both `action_required` with `failed to get run log: log not found`. This is the same approval-gate class AUTO-03 already handles on this branch; the executing controller that produced the prompt still runs the pre-fix code from `main` (`origin/main` still contains `action_required` in `remote_ci_failure_context`; the workflow checks out `${{ github.ref }}`). No code failure exists to repair and no new backlog item was started: the existing work was preserved and the newest evidence pair was pinned. Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner` — **58 tests OK**. `test_current_sanitized_action_required_pair_parks_without_a_model_call` proves the #43649302769/#43649302743 pair yields an empty failure context, reports `OWNER_APPROVAL_REQUIRED` and is never sent to `run view`; `test_current_sanitized_approval_gate_pair_is_refused` proves the exact legacy chunk text cannot produce a repair instruction.
- `python -m unittest discover -s tests` — **409 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts packaging` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK; `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean; `git merge-tree` against `origin/main` — clean.

The #43649302769/#43649302743 runs are approval gates, not code failures; only the owner can approve them or merge this protected PR. Merging or dispatching the workflow on this branch is required before the controller on `main` stops generating these prompts.

### Recovered run — newest ci-run pair #43685572267 pinned — 15 November 2026

The recovery prompt carried `Windows desktop build` #43685572267 and `Python checks` #43685572300, both `action_required` with `failed to get run log: log not found`. This is the same approval-gate class AUTO-03 already handles on this branch; the executing controller that produced the prompt still runs the pre-fix code from `main` (`origin/main` still contains `action_required` in `remote_ci_failure_context`; the workflow checks out `${{ github.ref }}`). No code failure exists to repair and no new backlog item was started: the existing work was preserved and the newest evidence pair was pinned. A follow-up validation repair then replayed the exact same pair through the "Repair this existing PR's remote Windows CI failure" path; the concrete diagnosis is identical (it is an approval gate, not a code failure), so the same evidence was additionally pinned through the full `resume_existing_pr` path. Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner` — **61 tests OK**. `test_newest_ci_run_pair_43685572267_parks_without_a_model_call` proves the #43685572267/#43685572300 pair yields an empty failure context, reports `OWNER_APPROVAL_REQUIRED` and is never sent to `run view`; `test_newest_ci_run_pair_43685572267_cannot_build_a_repair_prompt` proves the exact legacy chunk text cannot produce a repair instruction; `test_newest_ci_run_pair_43685572267_parks_through_the_full_recovery_path` feeds the exact replayed validation evidence into the real-Git `resume_existing_pr` and proves exit 0 with no agent call, `run view`, merge, commit or new PR.
- `python -m unittest discover -s tests` — **412 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts packaging` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK; `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean; `git merge-tree` against `origin/main` — clean.

The #43685572267/#43685572300 runs are approval gates, not code failures; only the owner can approve them or merge this protected PR. Merging or dispatching the workflow on this branch is required before the controller on `main` stops generating these prompts.

### Recovered run — header-less unavailable-log gap closed and #43749264535 pinned — 15 November 2026

The recovery prompt carried `Windows desktop build` #43749264535 and `Python checks` #43749264536, both `action_required` with `failed to get run log: log not found`. The committed branch already refuses those exact chunks as an owner-approval gate; the prompt is still produced by the pre-fix controller executing from `main`. What was different this pass was a genuine adjacent defect found while diagnosing it: both `build_repair_prompt` and `unusable_repair_evidence_message` only refused unavailable-log evidence when it carried a `===== ... run <id> (<conclusion>) =====` header. A header-less notice such as a bare `failed to get run log: log not found` fell through to the generic "Diagnose the concrete failure" prompt, which no code change can satisfy. The condition now tests `not ci_evidence_has_log(failure_output)` directly, so any evidence with no readable log is refused. A real failure log without headers is still repaired. Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner` — **64 tests OK**. `test_bare_unavailable_log_notice_cannot_build_a_repair_prompt` reproduces the gap (renamed to fail on the old code); `test_newest_ci_run_pair_43749264535_parks_without_a_model_call` and `test_newest_ci_run_pair_43749264535_cannot_build_a_repair_prompt` pin the reported pair.
- `python -m unittest discover -s tests` — **415 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts packaging` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK; `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean; `git merge-tree` against `origin/main` — clean.

The #43749264535/#43749264536 runs are approval gates, not code failures; only the owner can approve them or merge this protected PR. Merging or dispatching the workflow on this branch is required before the controller on `main` stops generating these prompts.

### Recovered run — newest approval-gate pair pinned and non-checkpoint evidence fallback fixed — 16 November 2026

The recovery prompt carried `Windows desktop build` #43749765989 and `Python checks` #43749766017, both `action_required` with `failed to get run log: log not found`. This is the same approval-gate class AUTO-03 already handles; the prompt is still produced by the pre-fix controller executing from `main`, because `.github/workflows/eclipse-autonomous.yml` checks out `${{ github.ref }}` and `origin/main` still treats `action_required` as a repairable failure. No code failure exists to repair and no new backlog item was started: the existing work was preserved and the newest evidence pair was pinned.

A genuine adjacent defect was fixed while diagnosing it. In `resume_existing_pr`, when `remote_ci_failure_context` came back empty, the old fallback used the PR body and then the `gh pr checks` summary as "failure evidence". For a normal non-checkpoint PR the body is just the milestone description, so the model was told to "diagnose" text that named no failure. That fallback is now limited to checkpoint PRs, whose body really does carry the prior run's sanitized failure context; a non-checkpoint PR with no readable CI log parks with `CI_EVIDENCE_UNAVAILABLE` instead of burning model calls. Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner` — **70 tests OK**. `test_newest_ci_run_pair_43749765989_parks_without_a_model_call` and `test_newest_ci_run_pair_43749765989_cannot_build_a_repair_prompt` pin the exact #43749765989/#43749766017 pair; `test_newest_ci_run_pair_43749765989_parks_through_the_full_recovery_path` feeds the exact replayed validation evidence into the real-Git `resume_existing_pr` and proves exit 0 with no agent call, `run view`, merge, commit or new PR; `test_followup_ci_repair_rejects_replayed_approval_gate_evidence` drives the actual reported stage — a successful first repair and commit, then the follow-up CI check replaying the same `action_required` chunks — and proves the second pass parks with no extra model call, commit or merge; `test_non_checkpoint_failure_without_remote_logs_parks_instead_of_using_pr_body` fails on the old body fallback; `test_checkpoint_body_still_resumes_without_ci_logs` proves checkpoint recovery still uses its body as prior-run context.
- `python -m unittest discover -s tests` — **421 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts packaging` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK; `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean; `git merge-tree` against `origin/main` — clean.

The #43749765989/#43749766017 runs are approval gates, not code failures; only the owner can approve them or merge this protected PR. Merging or dispatching the workflow on this branch is required before the controller on `main` stops generating these prompts. AUTO-03 remains `IN_PROGRESS`; this pass does not commit, push or merge and claims no Windows or owner gate.

### Recovered run — newest approval-gate pair #43817219556 pinned — 16 November 2026

The recovery prompt carried `Windows desktop build` #43817219556 and `Python checks` #43817219541, both `action_required` with `failed to get run log: log not found`. This is the same approval-gate class AUTO-03 already handles on this branch; the prompt is still produced by the pre-fix controller executing from `main`, which classifies `action_required` as a repairable failure and checks out `${{ github.ref }}`. There is no failing check for this branch to repair, and the branch's own controller already early-parks a protected non-checkpoint PR before any `gh` call, so no product code changed and no new backlog item was started. The existing work was preserved and the exact newest evidence pair was pinned.

Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner` — **74 tests OK**. `test_newest_ci_run_pair_43817219556_parks_without_a_model_call` proves the #43817219556/#43817219541 pair yields an empty failure context, reports `OWNER_APPROVAL_REQUIRED` and is never sent to `run view`; `test_newest_ci_run_pair_43817219556_cannot_build_a_repair_prompt` proves the exact legacy chunk text cannot produce a repair instruction; `test_newest_ci_run_pair_43817219556_parks_through_the_full_recovery_path` feeds the exact validation evidence into the real-Git `resume_existing_pr` and proves exit 0 with no agent call, `run view`, merge, commit or new PR; `test_followup_ci_repair_rejects_replayed_43817219556_evidence` drives the actual reported stage — a successful first repair and commit, then the follow-up CI check replaying the same `action_required` chunks with the CI-repair instruction — and proves `build_repair_prompt` returns `OWNER_APPROVAL_REQUIRED` and the second pass parks with no extra model call, `run view`, commit or merge. The next validation replay used #43966081267/#43966081265 and is pinned by `test_followup_ci_repair_rejects_replayed_43966081267_evidence` at the same stage.
- `python -m unittest discover -s tests` — **426 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts packaging` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK; `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean; `git merge-tree` against `origin/main` — clean.

The #43817219556/#43817219541 runs are approval gates, not code failures; only the owner can approve them or merge this protected PR. Merging or dispatching the workflow on this branch is required before the controller on `main` stops generating these prompts. AUTO-03 remains `IN_PROGRESS`; this pass does not commit, push or merge and claims no Windows or owner gate.

### Recovered run — newest approval-gate pair #43966482393 pinned — 17 November 2026

The recovery prompt carried `Windows desktop build` #43966482393 and `Python checks` #43966482410, both `action_required` with `failed to get run log: log not found`. This is the same approval-gate class AUTO-03 already handles on this branch; the prompt is still produced by the pre-fix controller executing from `main`, which classifies `action_required` as a repairable failure and checks out `${{ github.ref }}`. There is no failing check for this branch to repair, and the branch's own controller already early-parks a protected non-checkpoint PR before any `gh` call, so no new backlog item was started. The existing work was preserved and the exact newest evidence pair was pinned.

A validation replay then supplied the raw CI-repair prompt directly, so the model-call boundary was hardened as well. `unusable_ci_prompt_message` now detects a prompt that contains CI run headers but only `action_required` or unavailable-log bodies, and `run_agent_with_failover` refuses it before selecting a route or calling any provider. This protects stale/external callers that bypass `build_repair_prompt`; genuine failure logs and ordinary task/context-compaction prompts still run normally.

Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner` — **82 tests OK**. `test_newest_ci_run_pair_43966482393_parks_without_a_model_call` proves the #43966482393/#43966482410 pair yields an empty failure context, reports `OWNER_APPROVAL_REQUIRED` and is never sent to `run view`; `test_newest_ci_run_pair_43966482393_cannot_build_a_repair_prompt` proves the exact legacy chunk text cannot produce a repair instruction; `test_newest_ci_run_pair_43966482393_parks_through_the_full_recovery_path` feeds the exact validation evidence into the real-Git `resume_existing_pr` and proves exit 0 with no agent call, `run view`, merge, commit or new PR; `test_followup_ci_repair_rejects_replayed_43966482393_evidence` drives the actual reported stage — a successful first repair and commit, then the follow-up CI check replaying the same `action_required` chunks with the CI-repair instruction — and proves `build_repair_prompt` returns `OWNER_APPROVAL_REQUIRED` and the second pass parks with no extra model call, `run view`, commit or merge. `test_raw_approval_gate_ci_prompt_is_refused_before_any_provider_call` pins the same raw prompt at the model-call boundary, `test_raw_unavailable_failure_log_prompt_is_refused_before_any_provider_call` pins a log-less `failure` chunk, and `test_raw_real_failure_ci_prompt_still_reaches_the_provider` proves the guard does not block a genuine failure log.
- `python -m unittest discover -s tests` — **433 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts packaging` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK; `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean; `git merge-tree` against `origin/main` — clean.

The #43966482393/#43966482410 runs are approval gates, not code failures; only the owner can approve them or merge this protected PR. Merging or dispatching the workflow on this branch is required before the controller on `main` stops generating these prompts. AUTO-03 remains `IN_PROGRESS`; this pass does not commit, push or merge and claims no Windows or owner gate.

### Recovered run — newest approval-gate pair #44042810216 pinned — 17 November 2026

The recovery prompt carried `Python checks` #44042810216 and `Windows desktop build` #44042810197, both `action_required` with `failed to get run log: log not found`. This is the same approval-gate class AUTO-03 already handles on this branch; the prompt is still produced by the pre-fix controller executing from `main`, which classifies `action_required` as a repairable failure and checks out `${{ github.ref }}`. There is no failing check for this branch to repair, and the branch's own controller already early-parks a protected non-checkpoint PR before any `gh` call, so no new backlog item was started. The existing work was preserved and the exact newest evidence pair was pinned.

Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner` — **87 tests OK**. `test_newest_ci_run_pair_44042810216_parks_without_a_model_call` proves the #44042810216/#44042810197 pair yields an empty failure context, reports `OWNER_APPROVAL_REQUIRED` and is never sent to `run view`; `test_newest_ci_run_pair_44042810216_cannot_build_a_repair_prompt` proves the exact legacy chunk text cannot produce a repair instruction; `test_newest_ci_run_pair_44042810216_parks_through_the_full_recovery_path` feeds the exact validation evidence into the real-Git `resume_existing_pr` and proves exit 0 with no agent call, `run view`, merge, commit or new PR; `test_followup_ci_repair_rejects_replayed_44042810216_evidence` drives the follow-up CI-repair stage — a successful first repair and commit, then the same `action_required` chunks replayed — and proves `build_repair_prompt` returns `OWNER_APPROVAL_REQUIRED` and the second pass parks with no extra model call, `run view`, commit or merge; `test_raw_newest_approval_gate_ci_prompt_is_refused_before_any_provider_call` pins the same raw prompt at the model-call boundary. The earlier #43966482393/#43966482410, genuine-failure and unavailable-log controls are unchanged.
- `python -m unittest discover -s tests` — **438 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts packaging` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK; `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean; `git merge-tree` against `origin/main` — clean.

The #44042810216/#44042810197 runs are approval gates, not code failures; only the owner can approve them or merge this protected PR. Merging or dispatching the workflow on this branch is required before the controller on `main` stops generating these prompts. AUTO-03 remains `IN_PROGRESS`; this pass does not commit, push or merge and claims no Windows or owner gate.

### Recovered run — newest approval-gate pair #44174341838 pinned — 18 November 2026

The recovery prompt carried `Python checks` #44174341838 and `Windows desktop build` #44174342093, both `action_required` with `failed to get run log: log not found`. This is the same approval-gate class AUTO-03 already handles on this branch; the prompt is still produced by the pre-fix controller executing from `main`, which classifies `action_required` as a repairable failure and checks out `${{ github.ref }}`. There is no failing check for this branch to repair, and the branch's own controller already early-parks a protected non-checkpoint PR before any `gh` call, so no new backlog item was started. The existing work was preserved and the exact newest evidence pair was pinned.

Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner` — **92 tests OK**. `test_newest_ci_run_pair_44174341838_parks_without_a_model_call` proves the #44174341838/#44174342093 pair yields an empty failure context, reports `OWNER_APPROVAL_REQUIRED` and is never sent to `run view`; `test_newest_ci_run_pair_44174341838_cannot_build_a_repair_prompt` proves the exact legacy chunk text cannot produce a repair instruction; `test_newest_ci_run_pair_44174341838_parks_through_the_full_recovery_path` feeds the exact validation evidence into the real-Git `resume_existing_pr` and proves exit 0 with no agent call, `run view`, merge, commit or new PR; `test_followup_ci_repair_rejects_replayed_44174341838_evidence` drives the follow-up CI-repair stage — a successful first repair and commit, then the same `action_required` chunks replayed — and proves `build_repair_prompt` returns `OWNER_APPROVAL_REQUIRED` and the second pass parks with no extra model call, `run view`, commit or merge; `test_raw_newest_approval_gate_ci_prompt_44174341838_is_refused` pins the same raw prompt at the model-call boundary. The earlier #44042810216/#44042810197, #43966482393/#43966482410, genuine-failure and unavailable-log controls are unchanged.
- `python -m unittest discover -s tests` — **443 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts packaging` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK; `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean; `git merge-tree` against `origin/main` — clean.

The #44174341838/#44174342093 runs are approval gates, not code failures; only the owner can approve them or merge this protected PR. Merging or dispatching the workflow on this branch is required before the controller on `main` stops generating these prompts. AUTO-03 remains `IN_PROGRESS`; this pass does not commit, push or merge and claims no Windows or owner gate.

### Recovered run — validation replay #44174341838 refused at the model boundary — 18 November 2026

The independent validation replay passed the exact approval-gate evidence back into the session: the CI-repair instruction plus `Python checks` #44174341838 and `Windows desktop build` #44174342093, both `action_required`, each followed by `failed to get run log: log not found`. There is no failing check to repair; this is the owner-approval gate class AUTO-03 handles, and the replay is still produced by the pre-fix controller executing from `main`.

Concrete adjacent defect fixed: `unusable_ci_prompt_message` only refused a log-less prompt that carried a `===== ... run <id> (<conclusion>) =====` header, so a stale caller that strips the headers could still send a bare `failed to get run log: log not found` prompt to a provider. The model-call boundary now refuses any prompt containing an unavailable-log marker through a shared `ci_evidence_unavailable_message` helper; ordinary milestone prompts and genuine failure logs are unaffected.

Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner` — **95 tests OK**. `test_exact_validation_replay_44174341838_is_refused` pins the exact replayed text including the repair instruction and trailing newline; `test_headerless_raw_unavailable_log_prompt_is_refused_before_any_provider_call` proves a header-less unavailable-log prompt never reaches a provider; `test_ordinary_prompt_without_ci_evidence_is_not_refused` proves ordinary milestone prompts still pass the guard. The exact #44174341838 mocked-`gh`, legacy-chunk, full-Git recovery and follow-up replay tests remain.
- `python -m unittest discover -s tests` — **446 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts packaging` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK; `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean; `git merge-tree` against `origin/main` — clean.

The #44174341838/#44174342093 runs are approval gates, not code failures; only the owner can approve them or merge this protected PR. AUTO-03 remains `IN_PROGRESS`; this pass does not commit, push or merge and claims no Windows or owner gate.

### Recovered run — newest approval-gate pair #44258836858 pinned — 18 November 2026

The validation replay carried the CI-repair instruction plus `Windows desktop build` #44258836858 and `Python checks` #44258836775, both `action_required` with `failed to get run log: log not found`. This is the same owner-approval gate class AUTO-03 already handles; the replay is still produced by the pre-fix controller executing from `main`. There is no failing check to repair and no product code change was needed in this pass; the previous header-less boundary hardening is retained.

Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner` — **101 tests OK**. `test_newest_ci_run_pair_44258836858_parks_without_a_model_call` proves the pair yields an empty failure context, reports `OWNER_APPROVAL_REQUIRED` and is never sent to `run view`; `test_newest_ci_run_pair_44258836858_cannot_build_a_repair_prompt` and `test_exact_validation_replay_44258836858_is_refused` pin the exact legacy chunks and the full replayed text; `test_newest_ci_run_pair_44258836858_parks_through_the_full_recovery_path` drives the real-Git `resume_existing_pr` and proves exit 0 with no agent call, `run view`, merge, commit or new PR; `test_followup_ci_repair_rejects_replayed_44258836858_evidence` proves the follow-up stage parks after a real first repair; `test_raw_newest_approval_gate_ci_prompt_44258836858_is_refused` pins the model-call boundary.
- `python -m unittest discover -s tests` — **452 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts packaging` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK; `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean; `git merge-tree` against `origin/main` — clean.

The #44258836858/#44258836775 runs are approval gates, not code failures; only the owner can approve them or merge this protected PR. AUTO-03 remains `IN_PROGRESS`; this pass does not commit, push or merge and claims no Windows or owner gate.

### Recovered run — newest approval-gate pair #44259167673 pinned — 18 November 2026

The validation replay carried the CI-repair instruction plus `Python checks` #44259167673 and `Windows desktop build` #44259167616, both `action_required` with `failed to get run log: log not found`. This is the same owner-approval gate class AUTO-03 already handles; the replay is still produced by the pre-fix controller executing from `main`. There is no failing check to repair and no product code change was needed in this pass; the header-less boundary hardening from the earlier pass is retained.

Actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest tests.test_autonomous_runner` — **107 tests OK**. `test_newest_ci_run_pair_44259167673_parks_without_a_model_call` proves the pair yields an empty failure context, reports `OWNER_APPROVAL_REQUIRED` and is never sent to `run view`; `test_newest_ci_run_pair_44259167673_cannot_build_a_repair_prompt` and `test_exact_validation_replay_44259167673_is_refused` pin the exact legacy chunks and the full replayed text; `test_newest_ci_run_pair_44259167673_parks_through_the_full_recovery_path` drives the real-Git `resume_existing_pr` and proves exit 0 with no agent call, `run view`, merge, commit or new PR; `test_followup_ci_repair_rejects_replayed_44259167673_evidence` proves the follow-up stage parks after a real first repair; `test_raw_newest_approval_gate_ci_prompt_44259167673_is_refused` pins the model-call boundary.
- `python -m unittest discover -s tests` — **458 tests OK, 20 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts packaging` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK; `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean; `git merge-tree` against `origin/main` — clean.

The #44259167673/#44259167616 runs are approval gates, not code failures; only the owner can approve them or merge this protected PR. AUTO-03 remains `IN_PROGRESS`; this pass does not commit, push or merge and claims no Windows or owner gate.

## Verified GitHub Actions evidence

- Hardware branch head `4385fb6` (before the close-out commit): Python checks [#42204589092](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42204589092) passed Windows Python 3.11–3.14, **184 tests per job, 11 skipped**. No Windows desktop (Qt/PyInstaller) run existed for that head: `desktop.yml` triggers only on PRs to `main` or manual dispatch, so a stacked PR into PR #5's branch needs a manual dispatch. The result for the close-out head is reported on the stacked PR.
- Latest PR #5 corrected Windows desktop run [#42198092066](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198092066): all **145 tests passed** with PySide6 installed; PyInstaller created the Windows x64 app; packaged `ECLIPSE.exe --atlas-backend --help` passed; ZIP and artifact upload succeeded (ID `13493741785`, 50,965,917 bytes).
- Latest PR #5 corrected Python matrix [#42198091790](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198091790): all four Windows jobs passed Python 3.11–3.14, with **145 tests per job**; 8 Qt tests skip in this matrix because PySide6 is intentionally optional, and run in the dedicated desktop job.

## Manual Windows 11 smoke test

- User-confirmed: the packaged application launched on Windows 11 and all three workspace pages were clickable and displayed successfully.
- User-confirmed: selected `Qwen3.5-9B-Q4_K_M.gguf` in the Model Intelligence workspace and ran Inspect model. The Atlas displayed GGUF v3, architecture `qwen35`, model name `Qwen3.5-9B`, 427 tensors, 8,953,803,264 parameters, 5,669,554,176 bytes (5.28 GiB) registry-derived tensor storage and a 5.29 GiB file size; storage coverage was complete.
- The UI safety panel reported 0 tensor payload bytes read, payloads not loaded and source not modified. The displayed warning correctly notes the GGUF storage calculation has not yet been reconciled against a trusted full-checkpoint loader.
- This validates the packaged UI-to-Atlas integration with one real GGUF on Windows 11. It does not validate inference, GPU feasibility, Safetensors files or multi-shard Hugging Face folders.

## Test evidence boundaries

Synthetic tests prove parser behavior for the cases represented by their fixtures. They do not establish compatibility with every real-world GGUF variant or multi-shard folder layout. A real-file Windows test is a separate acceptance gate. One GGUF now passes that manual gate; further format/architecture coverage and an independent storage cross-check remain necessary. GitHub Actions results must be inspected before claiming CI has passed.

## Next tests

1. Owner-install or launch the CI-built Windows package and smoke-test all three workspaces plus the packaged backend.
2. Run real llama.cpp/Vulkan/Qwen load/generate/stop/restart and compare observed context/telemetry with the backend.
3. Real Capability and Agent tool tasks with approvals and Stop on Windows; real Obsidian vault walkthrough.
4. Real GGUF files from additional architectures and quantization types.
2. Large metadata arrays and resource-limit behavior on Windows.
3. Real Safetensors files and multi-shard Hugging Face folders on Windows.
4. Compare metadata/tensor descriptor output and derived sizes with a trusted upstream loader.
5. Run the tokenizer/chat-format card against a real multi-file Hugging Face folder (including `additional_chat_templates/*.jinja`) and a real GGUF with embedded `tokenizer.chat_template`.
6. Owner Windows 11 validation of `inspect-host`, `plan-feasibility` and the Model Intelligence memory-fit controls against the known-good model; check the KV estimate against backend-reported allocation (the estimate assumes full attention on every layer). Then separately validate runtime correctness and preparation integrity.


## UI interaction and error diagnostics

- `tests/test_diagnostics.py` verifies mouse press/release and wheel-scroll events, safe widget metadata, typed-text privacy, credential redaction, full-length bounded error details, and application-generated `QMessageBox` capture (severity, title, message, informative text and detailed text), including while ordinary interaction capture is paused.
- Manual desktop check: launch ECLIPSE, confirm **Record UI activity** is checked, click between all three workspaces, use the inner tabs, scroll a page, open a menu and perform a harmless action. Select **Open diagnostics folder**. Confirm the current `eclipse-ui-*.jsonl` file contains event entries for the actions. Type a harmless test sentence into the Agent composer and confirm the sentence itself does not appear in the log.
- To pause interaction capture, uncheck **Record UI activity**. Python/Qt error events and application-generated message boxes remain logged. Re-check it to resume.
- To validate dialog capture, trigger a harmless validation message (for example, try **Load selected model** before registering/selecting a model). The log should contain `message_box_shown` with severity, title and message text. Detailed text is captured when the dialog supplies it.
- Logs are local only. Do not attach logs publicly without reviewing them; they may contain widget identifiers, local paths from error reports, and technical environment details even though typed text and common credentials are excluded.
