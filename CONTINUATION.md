# ECLIPSE Continuation Record

## Current checkpoint

- Repository: `Tygaclaw/Project-Eclipse`.
- Working branch: `opencode/issue2-20261106051627` (feature branch for this increment).
- Increment: PySide6 Windows-first desktop shell with the three primary workspaces; Model Intelligence workspace connected to the existing Model Atlas through a bounded, cancellable subprocess boundary; PyInstaller packaging and a proposed Windows workflow.
- Primary workspaces: Model Intelligence & Inference Platform; Capability Amplification & Knowledge System; ECLIPSE Agent.

## What was actually verified in this increment

- Python 3.14.4 with PySide6 `6.12.0` + PyInstaller `6.22.3`: 109 local unit tests passed (including 8 desktop tests) with standard-library `unittest` under `QT_QPA_PLATFORM=offscreen`; `compileall` over `src tests packaging` passed. The desktop tests skip cleanly when PySide6 is absent.
- The desktop Atlas path runs the unchanged `build-atlas` command via `subprocess.Popen` with an argument list, a timeout, cancellation and bounded output, and validates the `eclipse_model_atlas`/`atlas_version == 1` contract and read-only invariants before rendering.
- `packaging/eclipse-desktop.spec` and `packaging/launcher.py` build a windowed onedir `ECLIPSE.exe` that reuses `--atlas-backend` → `build-atlas`. The spec has not been run on Windows in this environment.
- `docs/desktop-build-workflow.yml` is a proposed workflow only; it is deliberately outside `.github/workflows/`, which the OpenCode GitHub App cannot write. No Windows desktop artifact exists yet.
- The desktop framework comparison and decision are recorded in `docs/ADR-001-desktop-framework.md` and `DECISIONS.md` D-011.
- All inspectors and the atlas open inputs read-only and read zero tensor payload bytes.
- GGUF tensor storage bytes are derived from `ggml_types.py`, pinned to llama.cpp revision `67107ac34f62882d8b53ea41ad68010ea635b9be`; unknown types and non-block-multiple rows are left explicitly unknown.
- Safetensors storage bytes are observed from declared header `data_offsets`; malformed offsets, overlapping ranges and invalid JSON fail with a clear error.
- Hugging Face folder inspection reads only `config.json` and `model.safetensors.index.json`, cross-checks the shard map against files on disk, and does not follow symlinks.
- The Model Atlas core composes the three inspectors, counts tensor elements from observed shapes, aggregates storage bytes with evidence labels, and reports incomplete coverage when referenced shards are missing or cannot be inspected. Unreferenced files are not counted as model weights.
- Hugging Face folder scans are lazy and stop at the configured entry limit; control-file reads are capped even if a file changes during inspection. Index `metadata.total_size` is compared with observed tensor-data bytes, not whole Safetensors file sizes.
- Baseline CI on `main` (parent commit `122fc56`) is green: "Python checks" run #17 on `windows-latest` passed all four Python 3.11–3.14 jobs.
- The preceding increment's PR CI run #42164928747 is green: all four Windows jobs passed Python 3.11–3.14, with 86 tests. This increment's desktop CI has not run: its workflow is only proposed at `docs/desktop-build-workflow.yml`.
- No real user model file, Windows desktop build or GPU runtime was tested in this environment.

## Next engineering actions

1. A maintainer installs `docs/desktop-build-workflow.yml` as `.github/workflows/desktop.yml`, runs it, and verifies the `ECLIPSE-windows-x64` artifact and the packaged `ECLIPSE.exe --atlas-backend --help` smoke step.
2. Run the inspectors and the desktop app on real GGUF, Safetensors and multi-shard folders on Windows without moving or modifying the model; keep this as a user-validation gate rather than a prerequisite for unrelated work.
3. Reconcile derived GGUF sizes against a trusted upstream loader on a full real checkpoint.
4. Add tokenizer/chat-template file inspection and optional remote model-card metadata.
5. Add the memory/VRAM feasibility estimator, preserving measured/derived/estimated/unknown distinctions.
6. Continue the Capability Amplification and Agent workstreams without duplicating completed Qwen/API setup or the already completed A* evaluation; the current Capability and Agent screens are honest placeholders.

## Do not repeat

- General Windows/hardware audit.
- Qwen local installation or API-key recreation.
- The already completed A* challenge.

Never ask for, print or commit API-key values. The existing model and working 256K context baseline are historical known-good state; do not alter them without a narrowly justified test and rollback plan.
