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
- Runtime (`tests/test_runtime.py` + `tests/fixtures/fake_llama_server.py`): a real spawned HTTP/SSE server process, streamed text and usage, tool-call assembly, cancellation, managed lifecycle, observed context, measured telemetry, stop/process exit, startup failure cleanup, attach-mode ownership and binary discovery.
- Capability (`tests/test_capability.py`): watchdog routing, plans/acceptance criteria/drift, path escape rejection, approval-denied writes, real command/verification subprocesses, verification failure reporting, loop detection, task completion only with passing verification, missing-runtime handling, correction promotion evidence gates and the knowledge Inbox/approval/no-overwrite workflow.
- Agent (`tests/test_agent.py`): conversation persistence/search/rename/delete, streaming deltas, attachment copy and one-time context inclusion, tool execution with persisted metadata, honest runtime-error messages and workspace-free chat.
- CLI (`tests/test_app_cli.py`): registry, prepare/verify, knowledge propose/approve/search, correction evidence gates, app status, check detection, task plan creation, backend matrix and quantization failure path.
- Independent review (`tests/test_review.py`): backlog table parsing, seeded-regression rejection (deleted test file, newly added test skip), false completion-claim rejection (placeholder evidence, missing referenced test, no changed test/CI record, completion claim while work remains), acceptance of legitimate verification, and real temporary-Git working-tree integration plus CLI exit codes.
- Controller review wiring (`tests/test_autonomous_runner.py`): `validation_commands()` includes a separate `scripts/eclipse_review.py` gate distinct from the implementing controller.
- Runtime contract (`tests/test_runtime_contract.py`): the manifest-driven `BackendCapabilities`/`DeviceSupport`/`ControlSupport` contract, JSON round-trip and validation, and the evidence-labelled support matrix (supported/unsupported/unknown formats, architectures, tensor types, CPU/CUDA/Vulkan devices, placement modes and controls). Distinct from the real adapter suite in `tests/test_runtime.py`.
- Runtime-support CLI (`tests/test_runtime_cli.py`): the `runtime-support` command emits the support matrix, validates the capability manifest, and reports invalid manifests, missing files, atlas errors and bad placement choices without a traceback.
- Recovery (`tests/test_recovery.py`): the stale-base shape is reproduced in a temporary Git repository and the independent reviewer rejects the apparent deleted test until the base advance is incorporated, including the multi-file shape that the PR #16 resynchronisation fixed.
- Windows packaging guard (`tests/test_packaging_spec.py`): every PyInstaller `hiddenimport` in `packaging/eclipse-desktop.spec` must resolve to a real module under `src/`, and the branch-added `eclipse.core.runtime` must be listed, so a broken packaging spec fails fast instead of failing the remote Windows desktop build.

Run (desktop tests need PySide6; use an offscreen platform on headless machines):

```powershell
$env:PYTHONPATH = "src"
py -3 -m unittest discover -s tests -v
```

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m unittest discover -s tests -v
```

## Local verification evidence

- Integrated product implementation, local sandbox (Linux, Python 3.12, PySide6 `6.12.0` in the project virtual environment): `QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m unittest discover -s tests` ran **333 tests, OK**, including the real spawned inference server, capability/agent execution, CLI and Qt smoke tests. A separate CLI run started a real fake HTTP server, ran `eclipse chat --endpoint ... --json`, and received `Hello from the fake server.` with state `ready`; metrics are recorded as generation runs. `eclipse backends` and the full CLI help were also exercised. This is not a substitute for the owner's real Windows/GPU validation.
- AUTO-04 review stage, local sandbox (Linux, Python 3.12.16, PySide6 not installed): focused `tests.test_review` + `tests.test_autonomous_runner` + `tests.test_test_bootstrap` ran **49 tests, OK** (20 reviewer + 28 controller + 1 import-bootstrap); full `python -m unittest discover -s tests` ran **239 tests, OK, 11 skipped** (the optional Qt desktop smoke tests) both with `PYTHONPATH=src` and with `PYTHONPATH` removed; `python -m compileall -q src tests .github/scripts scripts` passed. The reviewer also accepted this milestone's own working-tree change set against `origin/main`.
- First live controller validation exposed a real regression in the controller, not the product: `validation_environment()` used an allowlist without `PYTHONPATH`, so `unittest discover` failed to import every `eclipse.*` test module (10 errors). The fix sets `PYTHONPATH=<repo>/src`; re-running the controller's own environment against `tests.test_hardware` with an empty parent `PYTHONPATH` gave **14 tests, OK**.
- Second live validation repeated the failure because the already-running controller process held the pre-fix function in memory. Test-level robustness added: `tests/_bootstrap.py` inserts `<repo>/src` into `sys.path` when `PYTHONPATH` is absent, and every `eclipse`-importing test module imports it. The no-`PYTHONPATH` child process scenario is regression-tested by `tests/test_test_bootstrap.py`. Full suite without `PYTHONPATH`: **239 tests, OK, 11 skipped**.
- Hardware-feasibility close-out, local sandbox (Linux, Python 3.13.18, PySide6 not installed): `python -m unittest discover -s tests` ran **190 tests, OK, 11 skipped** (the optional Qt desktop smoke tests); `python -m compileall -q src tests .github/scripts` passed. 6 of the 190 are new (4 `nvidia-smi` lookup cases, 2 KV-assumption cases). Synthetic fixtures on a non-Windows host only.
- Historical pre-review local result: **131 tests passed** on Python 3.14.4 with PySide6 `6.12.0`; historical only.
- Corrected PR #5 code head `ce8fcb679373129365a4fb067a50b4777570330f`: Python checks [#42198091790](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198091790) passed Python 3.11, 3.12, 3.13 and 3.14, **145 tests per job**, with 8 Qt tests skipped in this core-only matrix.
- The same corrected code head's Windows desktop run [#42198092066](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198092066) passed **145 tests including Qt**, PyInstaller build, packaged backend smoke test, ZIP creation and artifact upload. Artifact ID `13493741785`, 50,965,917 bytes, SHA-256 `3d6220bbf9736d39fd840fc65b3b9c82eb99f6d779af4632b0ef49aa603f1a49`.

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

1. Rebuild the Windows package and smoke-test all three workspaces plus the packaged backend.
2. Run real llama.cpp/Vulkan/Qwen load/generate/stop/restart and compare observed context/telemetry with the backend.
3. Real Capability and Agent tool tasks with approvals and Stop on Windows; real Obsidian vault walkthrough.
4. Real GGUF files from additional architectures and quantization types.
2. Large metadata arrays and resource-limit behavior on Windows.
3. Real Safetensors files and multi-shard Hugging Face folders on Windows.
4. Compare metadata/tensor descriptor output and derived sizes with a trusted upstream loader.
5. Run the tokenizer/chat-format card against a real multi-file Hugging Face folder (including `additional_chat_templates/*.jinja`) and a real GGUF with embedded `tokenizer.chat_template`.
6. Owner Windows 11 validation of `inspect-host`, `plan-feasibility` and the Model Intelligence memory-fit controls against the known-good model; check the KV estimate against backend-reported allocation (the estimate assumes full attention on every layer). Then separately validate runtime correctness and preparation integrity.

## PR #16 recovery evidence — 7 November 2026

The recovered PR #16 branch was stale against the integrated `main`. The independent reviewer compares the worktree with `origin/main`, so the stale branch appeared to delete main's new test modules and fixture and was rejected. After resynchronising the worktree with `origin/main` and reconciling the branch's RUN-01 additions, the following was actually run locally (Linux, Python 3.12.16, PySide6 not installed, `QT_QPA_PLATFORM=offscreen`):

- `python -m unittest discover -s tests` — **370 tests OK, 13 skipped**, both with `PYTHONPATH=src` and with `PYTHONPATH` removed.
- `python -m compileall -q src tests scripts .github/scripts` — OK.
- `python .github/scripts/validate_provider_pool.py` — OK.
- `python scripts/eclipse_review.py --base origin/main` — accepted.
- `git diff --check origin/main` — clean.

Windows Qt/PyInstaller CI and the owner Windows/GPU/Obsidian gates remain the unresolved acceptance gates.
