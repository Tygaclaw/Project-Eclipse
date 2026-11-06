# ECLIPSE Continuation Record

## Current checkpoint

- Repository: `Tygaclaw/Project-Eclipse`.
- `main` baseline at synchronization: `04e46ce08284388c79a7fad91590c5258d1b162d`.
- Working branch: `opencode/issue2-20261106071400` (PR #5 feature branch). It was created from `4c887160a4131ab6f6ebe5259f8f3405f242a9b0`; this continuation update merges current `main` at `04e46ce08284388c79a7fad91590c5258d1b162d` as the second parent, preserving the feature commit and incorporating the latest main documentation checkpoint.
- Increment: bounded, read-only tokenizer and chat-template intelligence, integrated into the evidence-labelled Model Atlas and the Model Intelligence desktop workspace, plus the `inspect-tokenizer` CLI command.
- Primary workspaces: Model Intelligence & Inference Platform; Capability Amplification & Knowledge System; ECLIPSE Agent.
- The prior increment delivered the PySide6 Windows-first desktop shell, the Model Atlas subprocess boundary, PyInstaller packaging and the active Windows workflow; that work is unchanged.

## What was actually verified in this increment

- Tokenizer/chat-template increment, Python 3.14.4 with PySide6 `6.12.0`: `python -m compileall -q src tests` passed; `PYTHONPATH=src python -m unittest discover -s tests` → **131 tests passed, 0 skipped** (110 prior + 21 new tokenizer tests, with the desktop smoke test extended to assert the tokenizer card).
- `tokenizer.py` reads only small control files and bounded UTF-8 templates, never imports or renders Jinja, never follows symlinks, and reports `templates_rendered == False`, `jinja_imported == False` and `tensor_payload_bytes_read == 0`.
- Chat-template reporting records the documented Hugging Face load sequence: read embedded `tokenizer_config.json` metadata (or the legacy `chat_template.json` format for processors), let root `chat_template.jinja` override the default, then merge named `additional_chat_templates/*.jinja` files. A processor repository mixing legacy `chat_template.json` with modern `.jinja` files is flagged as conditionally incompatible; ECLIPSE does not guess the folder's model kind or report an effective default for that combination. Templates remain untrusted plain text.
- GGUF tokenizer facts are summarised only from the bounded `tokenizer.*` metadata previews already produced by the GGUF parser; the file is not reread. Safetensors and non-tokenizer sources report an honest unavailable tokenizer section.
- `py -3 -m eclipse inspect-tokenizer <folder>` emits the standalone `eclipse_tokenizer_inspection` JSON, and `build-atlas` adds a top-level `tokenizer` section plus an `evidence.tokenizer` label without changing `atlas_version == 1`.
- The desktop Model Intelligence workspace renders a "Tokenizer and chat format" card with a beginner summary and a hidden technical disclosure; template previews are shown as untrusted plain text.
- PR #5 is already pushed and open at https://github.com/Tygaclaw/Project-Eclipse/pull/5. Its current review state is `CHANGES_REQUESTED`; the eight required corrections are still pending. The original PR head had no associated GitHub Actions runs at the last check. The 131-test result above is local-only, not CI evidence.
- The prior increment's Windows desktop workflow [run #42178385983](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42178385983), Python 3.12 + PySide6 `6.12.0`: 110 tests passed, including all 8 offscreen desktop UI tests with no skips. PyInstaller built the Windows x64 package; the packaged backend smoke test, ZIP creation and artifact upload all passed. Artifact `ECLIPSE-windows-x64` is 50,931,411 bytes.
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

1. Complete all eight requested corrections in PR #5: embedded and aggregate template limits; bounded JSON/token-entry work; nested-symlink warnings; invalid UTF-8 and named-template tests; clipped token previews; the vocabulary candidate UI fix; the Hugging Face legacy/modern processor-template incompatibility caveat; accurate status records; and full synchronization/CI.
2. Leave PR #5 open for maintainer review. Do not merge it automatically.
3. Complete a repository-wide product/code audit against `docs/COMPLETE_PRODUCT_RUNTIME_VISION.md` after that specification is merged. Identify gaps and repair existing systems rather than adding duplicate scaffolds.
4. Build the evidence-labelled memory/VRAM/KV-cache feasibility planner, then reversible preparation and a real Windows-compatible inference adapter.
5. Continue the shared Core, Capability Amplification, Obsidian and Agent work in separate tested milestones. Do not repeat completed Qwen/API setup or the A* evaluation.
6. Review and include PySide6/Qt LGPL notices, relinking instructions and a corresponding-source offer before broader redistribution.

## Cross-PR coordination and performance interpretation

- PR #6 is a documentation-only complete product/runtime specification. Its 10+ sustained tokens/second primary target and 15–20+ preferred target apply only to large models that cannot run natively on the target computer. Native-fit models have no fixed tokens/second threshold; optimize for their best verified native speed and preserve quality. The PR #6 document is being amended to reflect this owner clarification.
- PR #7 is the separate OpenCode headless external-directory permission fix. It passed the Python matrix and Windows desktop CI, but remains open pending owner review; it is not part of PR #5 and has not been merged.

## Do not repeat

- General Windows/hardware audit.
- Qwen local installation or API-key recreation.
- The already completed A* challenge.

Never ask for, print or commit API-key values. The existing model and working 256K context baseline are historical known-good state; do not alter them without a narrowly justified test and rollback plan.
