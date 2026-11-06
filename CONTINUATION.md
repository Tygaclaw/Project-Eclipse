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


## Provider-pool continuation (PR #9; feature branch only)

Branch: `feature/openrouter-free-models-20261106`, stacked on PR #7. These changes are not on `main`.

The current branch supports manual selections across Token Harbor, OpenRouter free models, Google Gemini/Gemma free-tier models, Groq Free-plan models, NVIDIA API Catalog/NIM, Cloudflare Workers AI free-plan models, and an optional Cohere evaluation-only route. The canonical command/model/limit list is `docs/FREE_MODEL_PROVIDER_POOL.md`.

The GitHub Actions workflow preserves `timeout-minutes: 350`, the headless external-directory deny rule, selected-provider connection checks and selected-credential-only environment passing. The owner reports that a Gemini key was added; the selected Gemini workflow check has not yet confirmed the actual secret-name match. OpenRouter is already saved. Groq, NVIDIA, Cloudflare and optional Cohere connections remain unconfirmed.

No live smoke tests were sent as part of this configuration change. Automatic cross-provider failover, cooldown memory and progress-safe retries are **not implemented yet**.

### Next steps

1. Inspect CI for the latest PR #9 head and read actual logs/test counts.
2. Run one deliberate Gemini smoke test to confirm the saved key alias.
3. Add only the additional provider credentials the owner wishes to use. Confirm Cloudflare remains on Workers Free before using its route. Cohere stays evaluation-only.
4. Build and failure-test the external free-only failover coordinator before enabling automatic switching.
5. Complete the ECLIPSE-specific model leaderboard using independent public benchmark evidence plus identical controlled ECLIPSE repository tasks. Do not invent a final ranking from provider marketing or usage popularity.

Do not repeat Qwen installation, the general Windows hardware audit, Gemini/OpenRouter setup or the completed A* evaluation. Never request or print secret values.


## Free-provider pool continuation — current checkpoint

**Branch:** `feature/openrouter-free-models-20261106`; **PR #9**, stacked on PR #7. Not merged to `main`.

Current configuration: 9 recurring free-provider families with 40 free model/router entries (Token Harbor 2; OpenRouter 13; Google 8; Groq 3; NVIDIA 4; Cloudflare 4; OrcaRouter 2; Kilo 1; Z.AI 3), plus one Cohere evaluation-only entry. The authoritative command/model/secret/limit inventory is `docs/FREE_MODEL_PROVIDER_POOL.md`.

New routes:
- OrcaRouter: `/oc-orca` uses the free-only router; `/oc-orca-deepseek` uses its explicit $0 DeepSeek V4 Flash model. Do not use paid OrcaRouter models or `orcarouter/auto`.
- Kilo Gateway: `/oc-kilo` uses only `kilo-auto/free`. This routes dynamically across the curated free model pool. Kilo warns some upstreams may log/use prompts to improve their services. No confidential source or credentials.
- Z.AI: `/oc-zai`, `/oc-zai-45`, `/oc-zai-vision` use its three official $0 GLM Flash models. Z.AI has not published numeric free-tier rate caps on its pricing page; check the account console and treat rate limits as unknown until tested.

Secret names newly required:
- `ORCAROUTER_API_KEY`
- `KILO_API_KEY`
- `ZAI_GLM_API_KEY`

Other not-yet-reported secrets remain `GROQ_API_KEY`, `NVIDIA_API_KEY`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, and optional `COHERE_API_KEY`. The owner reports a Gemini key and an OpenRouter key are saved. Never request or reveal secret values.

The workflow preserves the 350-minute Actions timeout and `external_directory: deny`, checks the selected provider's secret, and passes only the selected provider's key into the OpenCode process. A CI script checks every command against its model entry, the provider secret name, free-route whitelist, provider-scoped key handoff and timeout/permission safeguards.

No live inference smoke test has been made for the newly added routes. The manual selector is not automatic cross-provider failover. Next:
1. Inspect CI after the current branch head settles; require all Python 3.11–3.14 jobs and the provider route validator to pass.
2. Merge PR #7 first, then retarget/retest PR #9; do not merge without owner direction.
3. Owner saves `ORCAROUTER_API_KEY`, `KILO_API_KEY`, `ZAI_GLM_API_KEY`, and whichever of Groq/NVIDIA/Cloudflare credentials they want to use. Keep Cloudflare on Workers Free.
4. Run small, non-confidential live smoke tests, one provider at a time.
5. Implement and failure-test the separate free-only failover coordinator with error classification, capped backoff, cross-provider switching, cooldown state, and safe commit/continuation recovery.
6. Complete the ranked ECLIPSE model report from public benchmarks and controlled ECLIPSE repo tasks. Rank the strongest first and weakest last; do not fabricate missing results.

Do not repeat Qwen setup, the general hardware audit, or the completed A* evaluation.
