# ECLIPSE Project Status

**Status:** `ACTIVE — HARDWARE_FEASIBILITY_CLOSEOUT_AWAITING_REVIEW`

**Last updated:** 2026-11-06

## Branch stack (read this first)

This branch (`feature/hardware-feasibility-v1`) is **stacked on PR #5's branch** (`opencode/issue2-20261106071400`); it is not based on `main` alone.

- `main` (`04e46ce`) contains only the merged PR #3 and PR #4 foundation.
- PR #5 (tokenizer and chat-template intelligence) is open, unmerged and awaiting the owner's fresh review. Its only review is `CHANGES_REQUESTED`, written against an older commit than the current head.
- PR #6 (documentation-only product/runtime specification, `docs/COMPLETE_PRODUCT_RUNTIME_VISION.md`) is open and unmerged. That file is **not** on this branch; the two branches diverged and are reconciled only when the owner merges them. The specification states requirements, not implementation status.
- PR #7 (OpenCode `external_directory` permission fix in `opencode.json`) is open and unmerged. Passing application CI does not prove the OpenCode hang is fixed; that needs a real headless OpenCode run after it is merged.
- The hardware-feasibility work is the 13 commits on top of PR #5's branch plus the close-out commits. It is opened as a stacked PR **targeting PR #5's branch** so its diff shows only hardware work. It must not become a 45-commit PR against `main`. After the owner merges PR #5, retarget it to `main` and re-run all PR checks.
- CI note: `ci.yml` runs on pushes to `feature/**` and on PRs to `main`; `desktop.yml` runs only on PRs to `main` or by manual dispatch. A PR into PR #5's branch therefore does not start the Windows Qt/PyInstaller build automatically. It is dispatched manually, and `.github/workflows/*` is intentionally untouched.

## Completed in this repository increment

- [x] Confirmed the authenticated GitHub account and write access to `Tygaclaw/Project-Eclipse`.
- [x] Confirmed the existing `main` branch and preserved its initial commit.
- [x] Created/used an isolated feature branch for implementation.
- [x] Recorded the user-directed decision to continue in this existing repository.
- [x] Added a bounded, read-only GGUF v2/v3 parser for metadata and tensor descriptors.
- [x] Added a versioned GGML type registry (`ggml_types.py`) pinned to a reviewed upstream llama.cpp/GGML revision.
- [x] Derived exact GGUF tensor storage bytes, leaving unregistered types and non-block-multiple rows explicitly unknown.
- [x] Added a bounded, read-only Safetensors header and tensor-index parser.
- [x] Added bounded Hugging Face folder discovery (`config.json` summary and `model.safetensors.index.json` shard-index cross-check) without following symlinks or reading shard payloads.
- [x] Kept folder enumeration and bounded control-file reads within configured memory limits.
- [x] Added an evidence-labelled Model Atlas core that composes the three inspectors into one summary (parameters, storage bytes, type/dtype distribution).
- [x] Made Atlas completeness depend on the referenced shard set; unrelated shards are excluded and index `total_size` is reconciled against tensor-data bytes, not whole-file sizes.
- [x] Added JSON CLI output and standard-library synthetic tests.
- [x] Chose PySide6 `6.12.0` + PyInstaller `6.22.3` for the Windows-first desktop shell and recorded the comparison in `docs/ADR-001-desktop-framework.md` (D-011).
- [x] Built a three-workspace `MainWindow` (`Model Intelligence & Inference Platform`, `Capability Amplification & Knowledge System`, `ECLIPSE Agent`) with sidebar navigation and `Ctrl+1/2/3` shortcuts.
- [x] Connected the Model Intelligence workspace to the existing Model Atlas through a bounded, cancellable `AtlasClient` subprocess boundary; no parsing is duplicated in the UI.
- [x] Added honest Capability and Agent placeholder screens; the Agent screen has no chat input and reports that no adapter is connected.
- [x] Added desktop boundary and offscreen Qt smoke tests.
- [x] Added a PyInstaller spec/launcher and pinned desktop requirements.
- [x] Installed the Windows x64 desktop build workflow at `.github/workflows/desktop.yml` using the owner-level GitHub connection; the reference copy remains at `docs/desktop-build-workflow.yml`.
- [x] Reviewed and squash-merged desktop milestone PR #4 into `main` at `4c887160a4131ab6f6ebe5259f8f3405f242a9b0`.
- [x] PR #5 tokenizer/chat-template review corrections implemented on the existing feature branch; branch synchronized with current `main` without force-push; Python 3.11–3.14 and Windows Qt/PyInstaller PR-head CI passed. PR #5 remains open and unmerged for owner review.
- [x] Manually validated the packaged desktop-to-Atlas flow on Windows 11 using a real local GGUF file; the UI rendered the atlas and reported zero tensor payload bytes read and no source modification.
- [x] Added a bounded, read-only tokenizer and chat-template inspector (`tokenizer.py`) for local Hugging Face folders: tokenizer class/model/pre-tokenizer/decoder/normalizer, declared and observed vocabulary size candidates, added tokens, special tokens, and declared max length are read from small control files only.
- [x] Inventoried all supported tokenizer assets (`tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`, `added_tokens.json`, `vocab.json`, `vocab.txt`, `merges.txt`, legacy `chat_template.json`, and SentencePiece `*.model` files as inventory-only).
- [x] Added static chat-template discovery (`chat_template.jinja`, `additional_chat_templates/*.jinja` and embedded `tokenizer_config.json` templates) with a documented loader-precedence note, bounded plain-text previews, content hashes and conflict detection; templates are never imported, compiled or rendered.
- [x] Reused GGUF `tokenizer.*` metadata (bounded previews already read by the GGUF parser) for a GGUF tokenizer/chat-template summary without rereading the file.
- [x] Added the `eclipse inspect-tokenizer <folder>` CLI command and surfaced a beginner-friendly "Tokenizer and chat format" card (with a technical disclosure) and a tokenizer evidence label in the Model Atlas and desktop workspace.
- [x] Hardened tokenizer inspection for PR #5 review: per-file and aggregate JSON/template byte caps; shared embedded/file/GGUF template count and byte budgets; bounded added-token entry scans; clipped token previews; nested/root symlink handling; source immutability/path privacy tests; HF processor-template compatibility warning; and vocabulary evidence rendering.
- [x] Added a read-only host snapshot (`src/eclipse/core/hardware.py`): OS/CPU, RAM total/available via `GlobalMemoryStatusEx` (POSIX `sysconf` fallback), NVIDIA GPU name/VRAM/driver through `nvidia-smi` when it responds, and selected-volume storage capacity. Unavailable values stay unknown, never zero; no CUDA/Vulkan/backend compatibility is inferred.
- [x] Added bounded architecture facts with key aliases for GGUF (observed) and Hugging Face `config.json`/`text_config` (declared); conflicting aliases remain unknown.
- [x] Added a static memory-feasibility planner (`src/eclipse/model_intelligence/feasibility.py`): weights, a KV-cache estimate (layers × context × KV heads × key+value dimensions × dtype bytes × sequence slots), RAM and largest-single-GPU VRAM budgets with reserves, SSD reported separately, and a conditional performance-goal classification that applies the 10+ / 15–20+ tokens/second goals only to candidates oversized for the requested profile.
- [x] Added `inspect-host` and `plan-feasibility` CLI commands and hardware/memory-fit controls in the existing Model Intelligence workspace (background worker with cancellation).
- [x] Hardware-feasibility close-out: `nvidia-smi` discovery now tries each known location in turn when one cannot be launched (previously only the first location was tried), and the KV-cache estimate now states in its output and warnings that it assumes full-attention key/value state on every layer and can overstate hybrid, sliding-window or latent-attention models.

## What works now

- `py -3 -m eclipse inspect-gguf <file.gguf>` parses GGUF header, metadata, tensor index and per-tensor derived storage bytes without loading weights.
- `py -3 -m eclipse inspect-safetensors <file.safetensors>` parses the header length, bounded JSON header and declared tensor byte ranges without loading weights.
- `py -3 -m eclipse inspect-hf-folder <folder>` summarizes `config.json`, enumerates shard sizes, and cross-checks the shard index against the files on disk.
- `py -3 -m eclipse inspect-tokenizer <folder>` statically summarizes tokenizer assets and chat templates from small control files, with observed/declared/unknown evidence labels and no template execution.
- `py -3 -m eclipse build-atlas <path>` dispatches by input type and emits one evidence-labelled JSON atlas that now includes a `tokenizer` section (folder and GGUF sources; Safetensors reports it as unavailable).
- `py -3 -m eclipse inspect-host [--storage-path <path>]` prints a read-only host snapshot (OS/CPU, RAM total/available, NVIDIA VRAM when `nvidia-smi` responds, storage volume capacity). Unavailable values are reported as unknown.
- `py -3 -m eclipse plan-feasibility <model path>` builds the atlas and prints a static memory-capacity estimate (weights plus KV cache against usable RAM and the largest single GPU). It is a capacity envelope only: no layer placement, backend validation, model load or tokens/second prediction.
- `eclipse-desktop` opens the three-workspace shell; the Model Intelligence workspace selects a GGUF, Safetensors file or Hugging Face folder, runs the atlas with progress, cancellation and prior-inspection evidence, and renders model/architecture, parameters/storage, distribution, tokenizer/chat format, warnings, safety, evidence and an advanced disclosure.
- `packaging/launcher.py` + `packaging/eclipse-desktop.spec` build a windowed onedir `dist/ECLIPSE/ECLIPSE.exe`; `ECLIPSE.exe --atlas-backend ...` reuses the unchanged `build-atlas` CLI.
- Parser limits cap header/index bytes, tensor count, metadata entry count, strings, array elements, dimensions, header size, folder entries and shard count.
- Malformed or unsupported inputs fail with a clear error instead of being guessed.
- Unknown tensor types are retained as explicit unknown IDs with unknown storage size.

## Local verification evidence

- Hardware-feasibility close-out, local sandbox run (Linux, Python 3.13.18, PySide6 not installed): `python -m unittest discover -s tests` ran **190 tests, OK, 11 skipped**; all 11 skips are the optional Qt desktop smoke tests (`PySide6 is not installed`). `python -m compileall -q src tests .github/scripts` passed. Before the close-out the same branch ran 184 tests (11 skipped), matching the recorded CI count; the close-out adds 6 tests (4 for `nvidia-smi` lookup, 2 for the KV assumption). This is local, synthetic-fixture evidence on a non-Windows host; it is not Windows, Qt or owner-machine evidence.
- Historical initial PR #5 local verification only (before review corrections): Python 3.14.4 with PySide6 `6.12.0`; **131 tests passed**. This is historical local evidence and is not used as the acceptance result for the corrected branch.
- Corrected PR #5 final code head `ce8fcb679373129365a4fb067a50b4777570330f`: Python matrix [run #42198091790](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198091790) passed all four Windows jobs on Python 3.11–3.14; each ran **145 tests**, with 8 optional Qt tests skipped because PySide6 is absent from the core matrix.
- Corrected PR #5 Windows desktop [run #42198092066](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198092066) passed **145 tests with PySide6**, PyInstaller Windows x64 packaging, packaged backend `--help` smoke test, ZIP creation and artifact upload. Artifact `ECLIPSE-windows-x64`, ID `13493741785`, size **50,965,917 bytes**, SHA-256 `3d6220bbf9736d39fd840fc65b3b9c82eb99f6d779af4632b0ef49aa603f1a49`.
- Latest Windows desktop run [#42178385983](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42178385983), Python 3.12 + PySide6 `6.12.0`: **110 tests passed**, including all 8 offscreen desktop UI tests; PyInstaller build, packaged backend smoke test, ZIP and artifact upload all succeeded.
- Latest Python matrix run [#42178385942](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42178385942): all four Windows jobs passed Python 3.11–3.14. The 8 Qt UI tests were skipped in that dependency-free matrix; the dedicated desktop job above runs them with PySide6 installed.
- Latest uploaded GitHub artifact from desktop run [#42178385983](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42178385983): `ECLIPSE-windows-x64` (50,931,411 bytes).

User-reported manual Windows 11 real-file validation (packaged application):
- Selected `Qwen3.5-9B-Q4_K_M.gguf` from the Model Intelligence workspace and pressed Inspect model.
- Atlas rendered successfully: GGUF v3, architecture `qwen35`, model name `Qwen3.5-9B`, 427 tensors and 8,953,803,264 parameters.
- Registry-derived tensor storage: 5,669,554,176 bytes (5.28 GiB); displayed file size: 5.29 GiB; storage coverage reported complete.
- Safety panel reported 0 tensor payload bytes read, payloads not loaded and source not modified.
- The warning correctly says GGUF storage is derived from the pinned type registry and has not yet been reconciled against a trusted full-checkpoint loader. This was a static inspection only; it did not test inference or GPU feasibility.
- Python 3.14.4: `python -m compileall -q src tests packaging` — passed.
- Python 3.14.4: `inspect-safetensors --compact`, `inspect-hf-folder --compact`, `build-atlas --compact` and desktop offscreen startup smoke tests — exit 0 with valid JSON / a shown window.

## CI verification evidence

- Hardware branch head `4385fb6076a866875e817465332e9ec48d475564` (before the close-out commit): Python checks [run #42204589092](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42204589092) succeeded on Windows Python 3.11–3.14, **184 tests per job, 11 skipped**. No Windows desktop (Qt/PyInstaller) run exists for this stack at that head. Results for the close-out head are recorded on the stacked PR rather than in this file.
- The original PR #5 head `17c2d4e0da480374a33c4de95debf9dce4e77d07` had no associated workflow runs; that is historical only. The corrected final code head `ce8fcb679373129365a4fb067a50b4777570330f` has successful Python 3.11–3.14 matrix [#42198091790](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198091790) and Windows Qt/PyInstaller build [#42198092066](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198092066).
- Baseline CI on `main` (parent commit `122fc56`) is **success**: workflow "Python checks" run [#17](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42157195462) on `windows-latest`, Python 3.11, 3.12, 3.13 and 3.14, all four jobs passed "Run unit tests".
- The prior increment's pull-request CI run is **success**: PR #3 run [#42164928747](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42164928747), all four Windows jobs passed on Python 3.11, 3.12, 3.13 and 3.14; that suite contained **86 tests**.
- The latest PR #5 corrected Windows desktop workflow [run #42198092066](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198092066) passed 145 tests (including Qt tests), PyInstaller, packaged backend smoke test, ZIP creation and artifact upload. Artifact `ECLIPSE-windows-x64`: 50,965,917 bytes, ID `13493741785`.
- The latest PR #5 corrected Python matrix [run #42198091790](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198091790) passed Windows Python 3.11–3.14, 145 tests per job; 8 optional Qt tests skipped in each core-only job.
- One real local GGUF file has now been inspected through the packaged UI on Windows 11. No GPU runtime or inference was tested.

## Not completed / not claimed

- [x] One real local GGUF file inspected through the packaged desktop UI on Windows 11 (details recorded above).
- [ ] Real Safetensors file and multi-shard Hugging Face folder validation.
- [x] Initial local tokenizer/chat-template implementation (folder and GGUF metadata), with no template execution.
- [x] PR #5 reviewer corrections, bounded-resource hardening, branch synchronization, and PR-head CI acceptance; PR remains open for owner review.
- [ ] Remote model-card metadata retrieval (no network access is used).
- [ ] Derived GGUF sizes reconciled against a trusted full checkpoint.
- [x] Static memory/VRAM feasibility estimate (capacity envelope only) implemented on this branch; owner Windows 11 validation of the host snapshot, CLI and UI controls is pending.
- [ ] Executable placement planning, backend/operator compatibility, runtime-overhead estimates, hybrid/sliding-window/latent-attention KV layouts, and any measured tokens/second.
- [x] User-reported Windows 11 manual launch and navigation smoke test: app opened successfully and all three workspaces were clickable and displayed without an observed problem.
- [ ] Model preparation/transformation, runtime adapters or inference.
- [ ] Capability Amplification system, Obsidian integration, or a working ECLIPSE Agent (placeholder screens only).

## Run locally

From the repository root in normal PowerShell:

```powershell
$env:PYTHONPATH = "src"
py -3 -m eclipse inspect-gguf "D:\Models\model.gguf"
py -3 -m eclipse inspect-safetensors "D:\Models\model.safetensors"
py -3 -m eclipse inspect-hf-folder "D:\Models\YourModelFolder"
py -3 -m eclipse inspect-tokenizer "D:\Models\YourModelFolder"
py -3 -m eclipse build-atlas "D:\Models\YourModelFolder"
py -3 -m eclipse inspect-host --storage-path "D:\Models"
py -3 -m eclipse plan-feasibility "D:\Models\model.gguf" --context-tokens 8192
py -3 -m unittest discover -s tests -v
```

To run the desktop shell from source, install the pinned desktop dependencies and launch it:

```powershell
py -3 -m pip install -r requirements-desktop.txt
$env:PYTHONPATH = "src"
py -3 -m eclipse.desktop.app
```

To build the Windows executable with PyInstaller:

```powershell
py -3 -m PyInstaller --noconfirm --clean packaging/eclipse-desktop.spec
```

The result is `dist\ECLIPSE\ECLIPSE.exe`. No administrator privileges, model runtime, API key or GPU are required for these commands.

## Known limitations

- GGUF v2/v3, Safetensors and Hugging Face model folders are supported. Local tokenizer files and chat templates are inspected statically; remote model-card metadata is not read and no network access is used.
- Tensor payloads are not decoded. GGUF sizes are derived from a pinned GGML registry; Safetensors and folder shard sizes are observed.
- Derived GGUF sizes are not yet reconciled against a trusted full checkpoint.
- Architecture-specific interpretation is still limited to metadata directly present in the checkpoint.
- The packaged Windows x64 build and backend smoke test passed on a GitHub-hosted Windows runner; the GUI shell passed 8 offscreen Qt tests there. The user confirmed interactive Windows 11 launch/navigation and successfully inspected one real GGUF through the packaged UI. The Atlas reported 0 tensor payload bytes read and no source modification. Real Safetensors/Hugging Face-folder validation, GPU runtime and inference remain untested.
- The agent workspace is a placeholder with no model adapter and no chat input, by design.
- The feasibility result is a static capacity envelope, not an executable placement manifest. It does not choose layers/tensors/experts, validate a backend or operators, verify context allocation, measure memory, load a model or predict speed. An estimated fit does not prove a model runs, and an "oversized" classification does not prove every possible placement fails.
- The KV-cache estimate assumes full-attention key/value state on every layer. Hybrid (linear/state-space), sliding-window or latent-attention models can need less, so a borderline "oversized" result must be re-checked against backend-reported allocation. Whether the owner's `qwen35` GGUF is such a case has not been checked.
- Host discovery covers NVIDIA GPUs through `nvidia-smi` only; AMD/Intel GPU telemetry, compute capability and Vulkan/CUDA support are not detected. The snapshot is point-in-time and free memory changes while other programs run.

## Free & Safe Checklist

- [x] Current parsers have no third-party runtime dependencies.
- [x] No paid API or cloud inference is required.
- [x] Source checkpoint opened read-only; payload bytes are not loaded.
- [x] No credentials, private prompts, or model weights in the repository.
- [x] No administrator privileges needed for current commands.
- [x] One real GGUF file validated through the packaged UI on Windows 11; Safetensors/Hugging Face-folder validation remains pending.
- [ ] Secret/dependency scanning and repository settings review pending.
- [ ] License selection remains with repository owner.
- [ ] PySide6/Qt LGPL license notices, relinking instructions and corresponding-source offer need review and inclusion in the public release package before broader redistribution.

See `CONTINUATION.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `TESTING.md`, `SECURITY.md` and `MODEL_COMPATIBILITY.md` for details.

## Six-provider OpenCode model pool and ECLIPSE coding-agent ranking — 6 November 2026

**Status:** Configured in the provider-ranking feature branch; not yet merged into main.

- Exactly six approved API providers: Dahl, Gemini, Groq, OpenRouter, Token Harbor and Z.AI.
- Exactly two approved model routes per provider; no direct NVIDIA, Cohere, Cloudflare, OrcaRouter or Kilo provider was added.
- Canonical configuration: `opencode.json`; exact free-tier rules and commands: `docs/FREE_MODEL_PROVIDER_POOL.md`.
- Benchmark report: `docs/ECLIPSE_AGENT_MODEL_RANKING_2026-11-06.md`.
- Rank-1 default: Token Harbor DeepSeek V4.1 Flash Free.
- Global order: DeepSeek V4.1 Flash; Gemini 3.8 Flash; MiMo V2.6 Flash; Gemini 3.7 Flash; Dahl DeepSeek V4 Flash; Groq Qwen 3.8 27B; OpenRouter Cohere North Mini Code; Z.AI GLM-4.7 Flash; Dahl MiniMax M2.7; OpenRouter Nemotron 3 Ultra; Groq GPT-OSS 120B; Z.AI GLM-4.5 Flash.
- The configuration validator enforces six providers, two models each, the rank-1 default, and best-first declaration order.
- The OpenCode comment workflow preserves specific command aliases before broad aliases to avoid substring collisions.
- CI on the earlier ranking commit passed; the clean-mainline provider branch still requires its own CI after integration.
- No live inference/tool-call smoke tests have passed for all 12 routes. Published benchmark ranking is provisional and does not prove endpoint equivalence.
- Automatic model retry/failover and progress-safe handoff are **not yet implemented**. This is the next automation milestone.

Free/billing safety:
- Dahl's signup grant is finite; no top-ups.
- Gemini stays on AI Studio Free; Groq stays on Free; OpenRouter/Token Harbor use explicit `:free` IDs; Z.AI only uses its approved $0 Flash routes.
- Quota exhaustion must never trigger a paid route, wallet spend, provider upgrade or account rotation.

