# ECLIPSE

ECLIPSE is a single, Windows-first AI ecosystem with three connected user workspaces:

1. **Model Intelligence & Inference Platform** — inspect, understand, prepare, optimize and run supported models.
2. **Capability Amplification & Knowledge System** — planning, research/context, execution, verification, recovery, correction memory and Obsidian knowledge.
3. **ECLIPSE Agent** — a ChatGPT/Claude-like conversational workspace that can use shared ECLIPSE capabilities through controlled tools.

The five model-engineering subsystems from the original ECLIPSE v3.0 plan remain internal parts of the first workspace and shared Core; they are not additional primary navigation destinations.

## Current working features

Four read-only, static inspectors emit JSON without loading model weights:

- **GGUF v2/v3 inspector** — reads the header, bounded metadata, tensor descriptors and per-tensor storage bytes. Storage bytes are derived from a versioned GGML type registry pinned to a reviewed upstream llama.cpp/GGML revision. Unknown tensor type IDs and rows that are not block-multiple remain explicitly unknown.
- **Safetensors inspector** — reads the 8-byte header length, the bounded JSON header and the declared tensor byte ranges. It does not read, map or decode tensor payloads.
- **Hugging Face folder inspector** — reads only the small control files (`config.json`, `model.safetensors.index.json`), lists shard file sizes and cross-checks the shard index against the files on disk. It does not follow symbolic links or read shard payloads.
- **Tokenizer and chat-template inspector** — reads the small tokenizer control files (`tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`, `added_tokens.json`, `vocab.json`, `vocab.txt`, `merges.txt`, `chat_template.jinja`, `additional_chat_templates/*.jinja` and legacy `chat_template.json`) and reports tokenizer class/model, observed vs declared vocabulary size, added and special tokens, and chat templates with bounded plain-text previews. SentencePiece `*.model` files are inventoried by name and size only. JSON files have per-file and aggregate byte caps; text and templates have size caps; embedded, standalone and named templates share aggregate byte/count budgets; token previews and added-token ID scans are bounded. Templates are treated as untrusted text: they are never imported, compiled or rendered. A processor repository mixing legacy `chat_template.json` with modern Jinja files is documented by [Hugging Face](https://huggingface.co/docs/transformers/en/chat_templating_writing) as incompatible; ECLIPSE flags the conditional caveat without guessing the folder's model kind or claiming an effective default.

On top of these, `build-atlas` composes the relevant inspectors into one evidence-labelled JSON atlas (parameters, storage bytes, type/dtype distribution and, for folder/GGUF sources, a tokenizer section) chosen automatically from the input.

No inspector loads, maps, decodes or executes tensor weights, and no inspector imports, compiles or renders a chat template.

Two further read-only commands support memory planning: `inspect-host` reports currently observable host facts (OS/CPU, RAM, NVIDIA VRAM via `nvidia-smi` when available, storage capacity), and `plan-feasibility` combines that snapshot with the atlas to estimate weight and KV-cache memory against usable RAM and the largest single GPU. The result is a static capacity envelope, not an executable layer placement and not a speed prediction; unavailable values are reported as unknown, and the KV estimate assumes full attention on every layer.

## Shared Core, model runtime, Capability System and Agent

A standard-library Core now sits under all three workspaces: one SQLite store (`src/eclipse/core/storage.py`) for models, prepared variants, profiles, runs, conversations, attachments, tasks, corrections and knowledge notes; one event bus; one settings/home layout; and one permission broker that scopes file access to an approved project folder and requires explicit approval for writes and commands.

Model preparation is reversible and auditable (`src/eclipse/model_intelligence/preparation.py`): index and copy packages record SHA-256 lineage, verification detects changed files, removal deletes only the derived package, and quantization is gated on a real `llama-quantize` executable.

The runtime (`src/eclipse/runtime/`) supports a managed `llama-server` process and an OpenAI-compatible attached endpoint. It streams text and tool calls, reports the context the backend actually accepted, measures time-to-first-token, completion tokens and tokens/second, records every load/generation/stop, cleans up failed launches, and never turns a failed load into a Ready state. Execution profiles resolve intent into explicit context, GPU-layer, parallel-slot and KV-cache settings with warnings when the model declares a smaller context. A model-specific `runtime-support` report compares an atlas and host snapshot against the backend's declarations without claiming a successful load. Successful loads save a profile; a successful generation marks it last-known-good and exposes it for restore in the desktop. The `benchmark` command runs warm-up plus repeated measured generations and stores median, range and variance for TTFT and tokens/second.

The Capability System (`src/eclipse/capability/`) implements a watchdog and planner with acceptance criteria, workspace-scoped tools, independent `compileall`/test verification with a bounded repair loop, loop detection, project indexing, correction memory that only promotes candidates with evidence and a regression case, and an Obsidian-compatible Markdown vault whose AI proposals stay in an Inbox until explicitly approved. Approval never overwrites an existing trusted note.

The Agent (`src/eclipse/agent/`) is a real streaming chat service on the same runtime: persistent conversations with search/rename/delete, model selection, text attachments, tool use with approvals, activity reporting and Stop. It shares the same knowledge, correction memory and permission boundaries as the Capability workspace.

The same Core is exposed through 23 CLI commands, including `registry-add`, `prepare`, `verify-package`, `runtime-support`, `chat`, `benchmark`, `profiles list|delete`, `task new|run`, `knowledge propose|approve|search`, `corrections propose|promote`, `app-status`, `diagnostics` and `detect-checks`.

## Desktop application

A PySide6 `6.12.0` Windows-first shell (`eclipse-desktop`) hosts the three primary workspaces over one shared `AppContext`. Model Intelligence has two tabs: **Inspect & feasibility** renders the evidence-labelled atlas with progress, cancellation and read-only safety reporting, while **Prepare & run** registers models, creates and verifies prepared packages, starts/stops/restarts the managed or attached backend, shows truthful runtime state and measured telemetry, saves and restores last-known-good execution profiles, runs repeated measured benchmarks, and runs a real generation test. The Capability workspace has **Plan & evidence**, **Verification**, **Knowledge** and **Corrections** tabs and runs real tasks with per-action approval and Stop. The Agent workspace provides conversation search, streaming chat, attachments, tool activity, approvals, model status and Stop. The shell also has a persisted light/dark theme. The inspection boundary remains a bounded, cancellable subprocess (`AtlasClient`), so parsing is not duplicated in the UI.

See [`docs/ADR-001-desktop-framework.md`](docs/ADR-001-desktop-framework.md) for the framework decision. The active Windows desktop build workflow is [`.github/workflows/desktop.yml`](.github/workflows/desktop.yml); its readable reference copy is [`docs/desktop-build-workflow.yml`](docs/desktop-build-workflow.yml). The workflow runs on pushes and pull requests to `main` (or when started manually), tests the Qt UI, builds a portable Windows x64 package and uploads the `ECLIPSE-windows-x64` artifact. Latest Windows verification: Python checks [#42330519701](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42330519701) passed Windows Python 3.11–3.14 and the desktop build [#42330519740](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42330519740) passed the full Qt/offscreen suite, PyInstaller build, packaged backend smoke test, ZIP creation and artifact upload on `e27fec7` (340 tests; `ECLIPSE-windows-x64` artifact, 52,935,974 bytes). The packaged UI has also been manually exercised on Windows 11 with a real GGUF: its Atlas reported zero tensor payload bytes read and no source modification. This is static inspection only, not inference or a GPU-feasibility claim.

## Requirements

- Windows 11 is the primary target. The core parsers are portable Python.
- Python 3.11 or newer.
- The static inspectors and Model Atlas core require no third-party runtime packages.
- The desktop shell requires the pinned packages in `requirements-desktop.txt` (PySide6 `6.12.0`).

## Run from PowerShell

From the repository root, point Python at the source folder and run an inspector:

```powershell
$env:PYTHONPATH = "src"
py -3 -m eclipse inspect-gguf "D:\Models\model.gguf"
py -3 -m eclipse inspect-safetensors "D:\Models\model.safetensors"
py -3 -m eclipse inspect-hf-folder "D:\Models\YourModelFolder"
py -3 -m eclipse inspect-tokenizer "D:\Models\YourModelFolder"
py -3 -m eclipse build-atlas "D:\Models\YourModelFolder"
py -3 -m eclipse inspect-host --storage-path "D:\Models"
py -3 -m eclipse plan-feasibility "D:\Models\model.gguf" --context-tokens 8192
```

The integrated Core and workspaces are also available from the CLI:

```powershell
$env:PYTHONPATH = "src"
py -3 -m eclipse registry-add "D:\Models\model.gguf"
py -3 -m eclipse prepare "D:\Models\model.gguf" --register
py -3 -m eclipse backends --compact
py -3 -m eclipse runtime-support "D:\Models\model.gguf" --placement hybrid --control context_tokens
py -3 -m eclipse chat --endpoint http://127.0.0.1:8080 --prompt "Hello" --json
py -3 -m eclipse benchmark --endpoint http://127.0.0.1:8080 --runs 3 --warmup 1 --json
py -3 -m eclipse task new "Add a bounded --json flag and verify it" --workspace .
py -3 -m eclipse knowledge propose --title "Observed fact" --body "Evidence-backed note"
py -3 -m eclipse app-status --compact
```

For a compact JSON report, add `--compact` to either command:

```powershell
$env:PYTHONPATH = "src"
py -3 -m eclipse inspect-gguf "D:\Models\model.gguf" --compact
```

To run the tests:

```powershell
$env:PYTHONPATH = "src"
py -3 -m unittest discover -s tests -v
```

The input checkpoint is opened read-only. The report includes only the source filename by default, not the full local path.

To run the desktop shell from source:

```powershell
py -3 -m pip install -r requirements-desktop.txt
$env:PYTHONPATH = "src"
py -3 -m eclipse.desktop.app
```

To build the Windows executable:

```powershell
py -3 -m PyInstaller --noconfirm --clean packaging/eclipse-desktop.spec
```

This produces `dist\ECLIPSE\ECLIPSE.exe`.

## Project status

The three workspaces, shared Core, reversible preparation, runtime lifecycle/telemetry, saved profiles with last-known-good restore, measured benchmarks, Capability System, Obsidian-compatible knowledge workflow and Agent are implemented and covered by **340 automated tests**, including a real spawned HTTP inference double, real tool/verification execution, CLI end-to-end chat and benchmark runs, and offscreen Qt UI tests. This is a locally and hosted-Windows verified implementation, not final release acceptance: real Windows llama.cpp/Vulkan/Qwen load and generation, owner launch/installation of the CI-built package, a real Obsidian vault walkthrough, the four remaining evaluations, installer/update and the license decision still require owner or release validation. See [`STATUS.md`](STATUS.md) and [`CONTINUATION.md`](CONTINUATION.md) for the exact evidence and remaining gates.

## Autonomous engineering

The repository's autonomous development controller is defined by [`docs/AUTONOMOUS_ENGINEERING_PROTOCOL.md`](docs/AUTONOMOUS_ENGINEERING_PROTOCOL.md) and [`AUTONOMOUS_BACKLOG.md`](AUTONOMOUS_BACKLOG.md). It is designed to select one bounded milestone per run, use the ranked free model pool, retry transient failures up to five times after the initial attempt, switch models while preserving the same OpenCode session when possible, run tests, and create a verified branch/PR.

The workflow entry points are manual dispatch, main-branch updates and a six-hour schedule. Safe product PRs are only eligible for automatic merge after the Windows Python matrix and Windows Qt/PyInstaller package checks pass. Workflow, credential, permission and controller changes require owner review. No paid fallback or automatic top-up is allowed.

**Controller status:** the autonomous bootstrap PRs #12/#13 and the follow-up controller work are merged on `main`. The product implementation described above was built on one integration branch after checking every remote side branch; the remaining unmerged branches were duplicate controller attempts, not product code. The backlog and remaining owner/release gates are tracked in `AUTONOMOUS_BACKLOG.md` and `STATUS.md`.



## Local UI activity and error diagnostics

The desktop records a structured local session log by default. It captures mouse clicks, double-clicks, scrolling, workspace/tab navigation, safe keyboard shortcuts, focus changes, context-menu use, drag/drop event types, and application/Qt/Python errors. Application-generated message boxes are recorded with their severity, title, visible message, informative text and detailed text. Error details and tracebacks retain up to 8,000 characters per field after credential redaction. The sidebar has a **Record UI activity** switch and an **Open diagnostics folder** button.

Logs are written under the ECLIPSE application data folder in `logs/` as JSON Lines files. They stay on the computer and are not uploaded automatically. The recorder does not read text typed into input controls or the Agent composer, clipboard contents, file contents, screenshots or absolute screen coordinates. Diagnostic errors and stack traces are saved for troubleshooting; common credential formats are redacted, but review logs before sharing because error details may include local paths or other technical information. Interaction logs can be paused from the sidebar; error logging remains active so failures can still be diagnosed. Old logs are pruned and each session has a size limit.

On Windows, the default folder is `%LOCALAPPDATA%\ECLIPSE\logs`. See `TESTING.md` for the diagnostics test coverage.
