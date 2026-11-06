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

Two further read-only commands support memory planning: `inspect-host` reports currently observable host facts (OS/CPU, RAM, NVIDIA VRAM via `nvidia-smi` when available, storage capacity), and `plan-feasibility` combines that snapshot with the atlas to estimate weight and KV-cache memory against usable RAM and the largest single GPU. The result is a static capacity envelope, not an executable layer placement and not a speed prediction; unavailable values are reported as unknown, and the KV estimate assumes full attention on every layer. See [`STATUS.md`](STATUS.md) for which pull request currently carries these commands.

## Desktop application

A PySide6 `6.12.0` Windows-first shell (`eclipse-desktop`) hosts the three primary workspaces. The Model Intelligence workspace lets you pick a GGUF, Safetensors file or Hugging Face folder and renders the same evidence-labelled atlas, with progress, cancellation and read-only safety reporting. It talks to the core through a bounded, cancellable subprocess boundary, so no parsing is duplicated in the UI. The Capability and Agent workspaces are honest placeholders; the Agent screen has no chat input and reports that no model adapter is connected.

See [`docs/ADR-001-desktop-framework.md`](docs/ADR-001-desktop-framework.md) for the framework decision. The active Windows desktop build workflow is [`.github/workflows/desktop.yml`](.github/workflows/desktop.yml); its readable reference copy is [`docs/desktop-build-workflow.yml`](docs/desktop-build-workflow.yml). The workflow runs on pull requests to `main` (or when started manually), tests the Qt UI, builds a portable Windows x64 package and uploads the `ECLIPSE-windows-x64` artifact. Latest PR #5 corrected Windows desktop validation: [#42198092066](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42198092066) (145 tests including Qt, PyInstaller build and packaged backend smoke test passed). The packaged UI has also been manually exercised on Windows 11 with a real GGUF: its Atlas reported zero tensor payload bytes read and no source modification. This is static inspection only, not inference or a GPU-feasibility claim.

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

See [`STATUS.md`](STATUS.md) and [`CONTINUATION.md`](CONTINUATION.md). This is an early engineering milestone, not a complete desktop app or a claim that the full ECLIPSE roadmap has shipped.

## Autonomous engineering

The repository's autonomous development controller is defined by [`docs/AUTONOMOUS_ENGINEERING_PROTOCOL.md`](docs/AUTONOMOUS_ENGINEERING_PROTOCOL.md) and [`AUTONOMOUS_BACKLOG.md`](AUTONOMOUS_BACKLOG.md). It is designed to select one bounded milestone per run, use the ranked free model pool, retry transient failures up to five times after the initial attempt, switch models while preserving the same OpenCode session when possible, run tests, and create a verified branch/PR.

The workflow entry points are manual dispatch, main-branch updates and a six-hour schedule. Safe product PRs are only eligible for automatic merge after the Windows Python matrix and Windows Qt/PyInstaller package checks pass. Workflow, credential, permission and controller changes require owner review. No paid fallback or automatic top-up is allowed.

**Bootstrap status:** the autonomous controller is being introduced on `feature/autonomous-engineering-engine-2026-11-06`. It is not active on `main` until its protected bootstrap PR is reviewed/merged and the first GitHub Actions run succeeds. The project is not yet the finished application; see `AUTONOMOUS_BACKLOG.md` and `STATUS.md`.

