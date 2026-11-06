# ECLIPSE

ECLIPSE is a single, Windows-first AI ecosystem with three connected user workspaces:

1. **Model Intelligence & Inference Platform** — inspect, understand, prepare, optimize and run supported models.
2. **Capability Amplification & Knowledge System** — planning, research/context, execution, verification, recovery, correction memory and Obsidian knowledge.
3. **ECLIPSE Agent** — a ChatGPT/Claude-like conversational workspace that can use shared ECLIPSE capabilities through controlled tools.

The five model-engineering subsystems from the original ECLIPSE v3.0 plan remain internal parts of the first workspace and shared Core; they are not additional primary navigation destinations.

## Current working features

Three read-only, static inspectors emit JSON without loading model weights:

- **GGUF v2/v3 inspector** — reads the header, bounded metadata, tensor descriptors and per-tensor storage bytes. Storage bytes are derived from a versioned GGML type registry pinned to a reviewed upstream llama.cpp/GGML revision. Unknown tensor type IDs and rows that are not block-multiple remain explicitly unknown.
- **Safetensors inspector** — reads the 8-byte header length, the bounded JSON header and the declared tensor byte ranges. It does not read, map or decode tensor payloads.
- **Hugging Face folder inspector** — reads only the small control files (`config.json`, `model.safetensors.index.json`), lists shard file sizes and cross-checks the shard index against the files on disk. It does not follow symbolic links or read shard payloads.

On top of these, `build-atlas` composes the relevant inspector into one evidence-labelled JSON atlas (parameters, storage bytes and type/dtype distribution) chosen automatically from the input.

No inspector loads, maps, decodes or executes tensor weights.

## Desktop application

A PySide6 `6.12.0` Windows-first shell (`eclipse-desktop`) hosts the three primary workspaces. The Model Intelligence workspace lets you pick a GGUF, Safetensors file or Hugging Face folder and renders the same evidence-labelled atlas, with progress, cancellation and read-only safety reporting. It talks to the core through a bounded, cancellable subprocess boundary, so no parsing is duplicated in the UI. The Capability and Agent workspaces are honest placeholders; the Agent screen has no chat input and reports that no model adapter is connected.

See [`docs/ADR-001-desktop-framework.md`](docs/ADR-001-desktop-framework.md) for the framework decision. The active Windows desktop build workflow is [`.github/workflows/desktop.yml`](.github/workflows/desktop.yml); its readable reference copy is [`docs/desktop-build-workflow.yml`](docs/desktop-build-workflow.yml). The workflow runs on pull requests to `main`, tests the Qt UI, builds a portable Windows x64 package and uploads the `ECLIPSE-windows-x64` artifact. Latest successful Windows desktop run: [#42173214699](https://github.com/Tygaclaw/Project-Eclipse/actions/runs/42173214699) (110 tests and package build passed). The packaged UI has also been manually exercised on Windows 11 with a real GGUF: its Atlas reported zero tensor payload bytes read and no source modification. This is static inspection only, not inference or a GPU-feasibility claim.

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
py -3 -m eclipse build-atlas "D:\Models\YourModelFolder"
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
