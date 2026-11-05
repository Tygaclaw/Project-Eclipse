# ECLIPSE

ECLIPSE is a single, Windows-first AI ecosystem with three connected user workspaces:

1. **Model Intelligence & Inference Platform** — inspect, understand, prepare, optimize and run supported models.
2. **Capability Amplification & Knowledge System** — planning, research/context, execution, verification, recovery, correction memory and Obsidian knowledge.
3. **ECLIPSE Agent** — a ChatGPT/Claude-like conversational workspace that can use shared ECLIPSE capabilities through controlled tools.

The five model-engineering subsystems from the original ECLIPSE v3.0 plan remain internal parts of the first workspace and shared Core; they are not additional primary navigation destinations.

## Current working feature

The first code increment is a **read-only GGUF v2/v3 inspector**. It reads the format header, bounded metadata and tensor descriptors, then emits JSON. It does not load, map, decode, or execute tensor weights. Unknown tensor type IDs remain explicitly unknown. Tensor payload byte sizes are intentionally not guessed until a verified upstream type-layout table is implemented.

## Requirements

- Windows 11 is the primary target. The core parser is portable Python.
- Python 3.11 or newer.
- No third-party runtime packages are required by the current feature.

## Run from PowerShell

From the repository root, point Python at the source folder and run the inspector:

```powershell
$env:PYTHONPATH = "src"
py -3 -m eclipse inspect-gguf "D:\Models\model.gguf"
```

For a compact JSON report:

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
