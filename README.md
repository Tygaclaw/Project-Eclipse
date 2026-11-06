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

No inspector loads, maps, decodes or executes tensor weights.

## Requirements

- Windows 11 is the primary target. The core parsers are portable Python.
- Python 3.11 or newer.
- No third-party runtime packages are required by the current features.

## Run from PowerShell

From the repository root, point Python at the source folder and run an inspector:

```powershell
$env:PYTHONPATH = "src"
py -3 -m eclipse inspect-gguf "D:\Models\model.gguf"
py -3 -m eclipse inspect-safetensors "D:\Models\model.safetensors"
py -3 -m eclipse inspect-hf-folder "D:\Models\YourModelFolder"
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

## Project status

See [`STATUS.md`](STATUS.md) and [`CONTINUATION.md`](CONTINUATION.md). This is an early engineering milestone, not a complete desktop app or a claim that the full ECLIPSE roadmap has shipped.
