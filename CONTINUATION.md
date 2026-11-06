# ECLIPSE Continuation Record

## Current checkpoint

- Repository: `Tygaclaw/Project-Eclipse`.
- `main` baseline at synchronization: `04e46ce08284388c79a7fad91590c5258d1b162d`.
- Working branch: `feature/hardware-feasibility-v1`, stacked on PR #5's branch `opencode/issue2-20261106071400` (which preserves the tokenizer work and its review corrections; corrected PR #5 code head verified by CI: `ce8fcb679373129365a4fb067a50b4777570330f`).
- Increment: read-only host hardware discovery and static RAM/VRAM/KV-cache memory-feasibility planning (`inspect-host`, `plan-feasibility` and Model Intelligence UI controls), on top of PR #5's tokenizer/chat-template work.
- Primary workspaces: Model Intelligence & Inference Platform; Capability Amplification & Knowledge System; ECLIPSE Agent.
- The prior increment delivered the PySide6 Windows-first desktop shell, the Model Atlas subprocess boundary, PyInstaller packaging and the active Windows workflow; that work is unchanged.

## Hardware-feasibility close-out (this branch)

- The branch is 13 hardware commits on top of PR #5's branch plus the close-out commits. It is opened as a stacked PR targeting `opencode/issue2-20261106071400` and must not be turned into a 45-commit PR against `main`. After PR #5 is merged by the owner, retarget it to `main` and re-run all PR checks including the Windows desktop workflow.
- Close-out changes: `nvidia-smi` location fallback in `hardware.py`; explicit full-attention-on-every-layer KV assumption in `feasibility.py` output and warnings; 6 new tests; documentation reconciled with the code (STATUS, CONTINUATION, README, REQUIREMENTS, TESTING, roadmap and alignment audit).
- Evidence: local sandbox 190 tests OK with 11 skipped (Qt, PySide6 absent); CI on the pre-close-out head `4385fb6` passed Python 3.11–3.14 with 184 tests per job ([run #42204589092](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42204589092)). No Windows desktop run is recorded in these files: `desktop.yml` does not trigger for PRs that do not target `main` and was left untouched, so it is dispatched manually and reported on the PR.
- Still pending: owner Windows 11 validation of `inspect-host`, `plan-feasibility` and the UI controls; owner review of PRs #5, #6 and #7.

## Inherited verification evidence (PR #5 tokenizer increment, unchanged on this branch)

- Historical pre-review local tokenizer result: Python 3.14.4 with PySide6 `6.12.0`, **131 tests passed**. This is retained as historical evidence only; acceptance of the corrected implementation is based on the PR-head GitHub Actions runs below.
- `tokenizer.py` reads only small control files and bounded UTF-8 templates, never imports or renders Jinja, never follows symlinks, and reports `templates_rendered == False`, `jinja_imported == False` and `tensor_payload_bytes_read == 0`.
- Chat-template reporting records the documented Hugging Face load sequence: read embedded `tokenizer_config.json` metadata (or the legacy `chat_template.json` format for processors), let root `chat_template.jinja` override the default, then merge named `additional_chat_templates/*.jinja` files. A processor repository mixing legacy `chat_template.json` with modern `.jinja` files is flagged as conditionally incompatible; ECLIPSE does not guess the folder's model kind or report an effective default for that combination. Templates remain untrusted plain text.
- GGUF tokenizer facts are summarised only from the bounded `tokenizer.*` metadata previews already produced by the GGUF parser; the file is not reread. Safetensors and non-tokenizer sources report an honest unavailable tokenizer section.
- `py -3 -m eclipse inspect-tokenizer <folder>` emits the standalone `eclipse_tokenizer_inspection` JSON, and `build-atlas` adds a top-level `tokenizer` section plus an `evidence.tokenizer` label without changing `atlas_version == 1`.
- The desktop Model Intelligence workspace renders a "Tokenizer and chat format" card with a beginner summary and a hidden technical disclosure; template previews are shown as untrusted plain text.
- PR #5 is pushed and open at https://github.com/Tygaclaw/Project-Eclipse/pull/5. All eight requested corrections are implemented. The original review remains `CHANGES_REQUESTED` until the owner reviews the updated code; the PR remains unmerged and mergeable. The original head lacked CI, but the corrected code head `ce8fcb679373129365a4fb067a50b4777570330f` passed Python matrix [#42198091790](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198091790) and Windows desktop CI [#42198092066](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198092066).
- Corrected PR #5 Python matrix [run #42198091790](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198091790): all four Windows jobs passed on Python 3.11–3.14, each with **145 tests passed** and 8 optional Qt tests skipped in the dependency-free matrix.
- Corrected PR #5 Windows desktop [run #42198092066](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198092066): **145 tests passed** with PySide6, PyInstaller package built, packaged backend smoke test passed, ZIP created and uploaded. Artifact `ECLIPSE-windows-x64` is 50,965,917 bytes (ID `13493741785`).
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

1. PR #5 review corrections are complete and verified. Keep PR #5 open for the owner's fresh review; do not merge it automatically.
2. Complete a repository-wide product/code alignment audit against `docs/COMPLETE_PRODUCT_RUNTIME_VISION.md` on the separate PR #6 specification branch. Identify missing, incomplete, disconnected, duplicated or inconsistent systems; repair existing code rather than creating parallel scaffolds. Keep PR #6 open for owner review.
3. The static hardware feasibility planner (RAM/VRAM/SSD budgets and reserves, weight storage, context/KV-cache estimate, honest fit classification) is implemented on this branch and awaits owner review as a stacked PR into PR #5's branch, plus owner Windows 11 validation. Backend/runtime-overhead estimates, compatibility and executable placement remain future work. Do not merge before PR #5.
4. Add reversible preparation and then a proven Windows-compatible inference adapter that can connect to the user's known-good llama.cpp configuration without reinstalling or changing it. Measure actual sustained throughput/resource use; apply the 10+ and 15–20+ tokens/s targets only to large models classified as not natively runnable.
5. Continue shared Core, Capability Amplification, Obsidian and Agent work in separate tested milestones. Do not repeat completed Qwen/API setup or the A* evaluation.
6. Review and include PySide6/Qt LGPL notices, relinking instructions and a corresponding-source offer before broader redistribution.

## Cross-PR coordination and performance interpretation

- PR #6 is a documentation-only complete product/runtime specification, and its performance section already incorporates the owner clarification: 10+ sustained tokens/second primary and 15–20+ preferred apply only to large models that cannot run natively. Native-fit models have no fixed throughput floor; optimize their best verified native performance without degrading quality. PR #6 CI after this correction passed.
- PR #7 is the separate OpenCode headless external-directory permission fix. It passed the Python matrix and Windows desktop CI, but remains open pending owner review; it is not part of PR #5 and has not been merged.

## Do not repeat

- General Windows/hardware audit.
- Qwen local installation or API-key recreation.
- The already completed A* challenge.

Never ask for, print or commit API-key values. The existing model and working 256K context baseline are historical known-good state; do not alter them without a narrowly justified test and rollback plan.

## Ranked free provider pool — continuation checkpoint (6 November 2026)

- Current candidate pool: six providers and 12 exact configured free model IDs.
- Rank-1 default: `tokenharbor/deepseek-v4.1-flash:free` (`/oc`).
- Global ranking and individual benchmark evidence: `docs/ECLIPSE_AGENT_MODEL_RANKING_2026-11-06.md`.
- Command/provider catalog and billing caveats: `docs/FREE_MODEL_PROVIDER_POOL.md`.
- Provider config validator enforces best-first JSON order and rank-1 default.
- The model ranking remains provisional until each API route passes live completion and tool-call tests, followed by identical ECLIPSE tasks.
- No provider failover exists yet; the upcoming autonomous runner must preserve the same OpenCode session when switching models, checkpoint its task context, and enforce free-only behavior.
- No paid fallback, automatic account rotation or automatic top-up is permitted.

