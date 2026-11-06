# ECLIPSE Continuation Record

## Current checkpoint

- Repository: `Tygaclaw/Project-Eclipse`.
- Working branch: `opencode/issue2-20261106041332` (feature branch for this increment).
- Increment: versioned GGML type registry plus derived exact GGUF tensor storage bytes; bounded Safetensors header inspector; bounded Hugging Face folder/`config.json`/shard-index discovery.
- Primary workspaces: Model Intelligence & Inference Platform; Capability Amplification & Knowledge System; ECLIPSE Agent.

## What was actually verified in this increment

- Python 3.14.4: 74 local synthetic-fixture unit tests passed with Python's standard-library `unittest`; `compileall` over `src tests .github/scripts` passed.
- All three inspectors open inputs read-only and read zero tensor payload bytes.
- GGUF tensor storage bytes are derived from `ggml_types.py`, pinned to llama.cpp revision `67107ac34f62882d8b53ea41ad68010ea635b9be`; unknown types and non-block-multiple rows are left explicitly unknown.
- Safetensors storage bytes are observed from declared header `data_offsets`; malformed offsets, overlapping ranges and invalid JSON fail with a clear error.
- Hugging Face folder inspection reads only `config.json` and `model.safetensors.index.json`, cross-checks the shard map against files on disk, and does not follow symlinks.
- Baseline CI on `main` (parent commit `122fc56`) is green: "Python checks" run #17 on `windows-latest` passed all four Python 3.11–3.14 jobs. This increment's own PR CI run is pending.
- No real user model file or Windows/GPU runtime was tested in this environment.

## Next engineering actions

1. Run the GitHub Actions workflow and inspect the actual run result.
2. Run the inspectors on real GGUF, Safetensors and multi-shard folders on Windows without moving or modifying the model.
3. Reconcile derived GGUF sizes against a trusted upstream loader on a full real checkpoint.
4. Add tokenizer/chat-template file inspection and optional remote model-card metadata.
5. Build the first Model Atlas with explicit evidence labels.
6. Add the memory/VRAM feasibility estimator, preserving measured/derived/estimated/unknown distinctions.
7. Continue the Capability Amplification and Agent workstreams without duplicating completed Qwen/API setup or the already completed A* evaluation.

## Do not repeat

- General Windows/hardware audit.
- Qwen local installation or API-key recreation.
- The already completed A* challenge.

Never ask for, print or commit API-key values. The existing model and working 256K context baseline are historical known-good state; do not alter them without a narrowly justified test and rollback plan.
