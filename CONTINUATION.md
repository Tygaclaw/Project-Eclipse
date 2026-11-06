# ECLIPSE Continuation Record

## Current checkpoint

- Repository: `Tygaclaw/Project-Eclipse`.
- Current baseline: `main`, after squash-merging PR #4 at `4c887160a4131ab6f6ebe5259f8f3405f242a9b0`.
- Completed increment: PySide6 Windows-first desktop shell with the three primary workspaces; Model Intelligence workspace connected to the existing Model Atlas through a bounded, cancellable subprocess boundary; PyInstaller Windows x64 packaging and active workflow.
- Primary workspaces: Model Intelligence & Inference Platform; Capability Amplification & Knowledge System; ECLIPSE Agent.

## What was actually verified in this increment

- Latest Windows desktop workflow [run #42178385983](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42178385983), Python 3.12 + PySide6 `6.12.0`: 110 tests passed, including all 8 offscreen desktop UI tests with no skips. PyInstaller built the Windows x64 package; the packaged backend smoke test, ZIP creation and artifact upload all passed. Artifact `ECLIPSE-windows-x64` is 50,931,411 bytes.
- Latest core CI matrix [run #42178385942](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42178385942) passed Python 3.11–3.14. Its eight UI tests were skipped because PySide6 is intentionally optional in that dependency-free matrix.
- The desktop Atlas path runs the unchanged `build-atlas` command via `subprocess.Popen` with an argument list, a timeout, cancellation and bounded output, and validates the `eclipse_model_atlas`/`atlas_version == 1` contract and read-only invariants before rendering.
- `packaging/eclipse-desktop.spec` and `packaging/launcher.py` built a windowed onedir `ECLIPSE.exe` on a GitHub-hosted Windows runner; `ECLIPSE.exe --atlas-backend --help` passed.
- The active workflow is installed at `.github/workflows/desktop.yml`; `docs/desktop-build-workflow.yml` is its reference copy. Latest run #42178385983 uploaded the successful Windows x64 artifact.
- The desktop framework comparison and decision are recorded in `docs/ADR-001-desktop-framework.md` and `DECISIONS.md` D-011.
- All inspectors and the atlas open inputs read-only and read zero tensor payload bytes.
- GGUF tensor storage bytes are derived from `ggml_types.py`, pinned to llama.cpp revision `67107ac34f62882d8b53ea41ad68010ea635b9be`; unknown types and non-block-multiple rows are left explicitly unknown.
- Safetensors storage bytes are observed from declared header `data_offsets`; malformed offsets, overlapping ranges and invalid JSON fail with a clear error.
- Hugging Face folder inspection reads only `config.json` and `model.safetensors.index.json`, cross-checks the shard map against files on disk, and does not follow symlinks.
- The Model Atlas core composes the three inspectors, counts tensor elements from observed shapes, aggregates storage bytes with evidence labels, and reports incomplete coverage when referenced shards are missing or cannot be inspected. Unreferenced files are not counted as model weights.
- Hugging Face folder scans are lazy and stop at the configured entry limit; control-file reads are capped even if a file changes during inspection. Index `metadata.total_size` is compared with observed tensor-data bytes, not whole Safetensors file sizes.
- Baseline CI on `main` (parent commit `122fc56`) is green: "Python checks" run #17 on `windows-latest` passed all four Python 3.11–3.14 jobs.
- The current core PR matrix [#42178385942](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42178385942) is green on Windows Python 3.11–3.14. The eight desktop tests skip in that matrix because it intentionally omits PySide6; all eight ran and passed in the dedicated desktop job [#42178385983](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42178385983).

User-reported manual Windows 11 real-file validation (packaged application):
- Selected `Qwen3.5-9B-Q4_K_M.gguf` from the Model Intelligence workspace and pressed Inspect model.
- Atlas rendered successfully: GGUF v3, architecture `qwen35`, model name `Qwen3.5-9B`, 427 tensors and 8,953,803,264 parameters.
- Registry-derived tensor storage: 5,669,554,176 bytes (5.28 GiB); displayed file size: 5.29 GiB; storage coverage reported complete.
- Safety panel reported 0 tensor payload bytes read, payloads not loaded and source not modified.
- The warning correctly says GGUF storage is derived from the pinned type registry and has not yet been reconciled against a trusted full-checkpoint loader. This was a static inspection only; it did not test inference or GPU feasibility.

- No GPU runtime or inference was tested. Real Safetensors and multi-shard Hugging Face folder inspection on the user's PC remain pending.

## Next engineering actions

1. Review and include PySide6/Qt LGPL notices, relinking instructions and a corresponding-source offer in the public release package before broader redistribution.
2. Add bounded, static tokenizer and chat-template inspection (no downloaded code execution), with clear observed/derived/unknown labels and tests.
3. Reconcile derived GGUF storage against a trusted upstream loader using a real full checkpoint; keep the registry-derived warning visible until independently verified.
4. Add the evidence-labelled memory/VRAM feasibility planner with explicit assumptions, RAM/VRAM budgets and unknowns; do not claim runtime success from a static estimate.
5. Validate a real Safetensors file and a multi-shard Hugging Face folder on Windows.
6. Continue Capability Amplification and ECLIPSE Agent through the shared Core, without repeating completed Qwen/API setup or the A* evaluation.

## Do not repeat

- General Windows/hardware audit.
- Qwen local installation or API-key recreation.
- The already completed A* challenge.

Never ask for, print or commit API-key values. The existing model and working 256K context baseline are historical known-good state; do not alter them without a narrowly justified test and rollback plan.
