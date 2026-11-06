# ECLIPSE Architecture

## Product shape

ECLIPSE is one desktop application with three primary workspaces:

- Model Intelligence & Inference Platform.
- Capability Amplification & Knowledge System.
- ECLIPSE Agent.

All workspaces use one shared Core for model registry/provenance, hardware/resource services, memory/retrieval, planning, permissions, tools, diagnostics, verification and evaluation. The desktop shell is not a fourth workspace.

## Model-engineering subsystems

The original Master Plan's five subsystems are retained inside the Model Intelligence & Inference Platform and shared Core:

1. Model Intelligence Laboratory.
2. Model Preparation and Optimization.
3. High-Speed Inference Engine.
4. Intelligence Preservation and Recovery.
5. ECLIPSE Desktop and Resource Manager.

## Current vertical slice

`src/eclipse/model_intelligence/gguf.py` and `src/eclipse/model_intelligence/safetensors.py` are standard-library-only static parsers. Each reads a checkpoint's header/index sequentially in read-only mode, applies explicit limits, and returns a JSON-safe report. Tensor payloads are neither loaded nor memory-mapped. The parsers record metadata/tensor descriptor offsets, the absolute start of each tensor in the payload region and per-tensor storage bytes.

`src/eclipse/model_intelligence/ggml_types.py` is a versioned registry of GGML tensor types pinned to a reviewed upstream llama.cpp/GGML revision. It supplies the block size and encoded type size used to derive exact GGUF tensor storage bytes (`type_size * elements / block_size`). A tensor type absent from the registry is reported as `unknown_<id>` with its storage size explicitly unknown, and a quantized row whose length is not a block multiple is left unknown rather than guessed. Safetensors storage bytes are observed directly from the declared header offsets.

## Technology direction

- Python 3.11+ for the shared model/agent core and AI ecosystem integrations.
- Standard-library-only runtime for the first static parser.
- Desktop framework decision remains open pending a focused Windows-native comparison and a small UI spike.
- Inference is delegated to supported, maintained engines through adapters; ECLIPSE will not start by implementing its own matrix-multiplication kernels.

## Trust boundaries

- Model files and their metadata are untrusted data.
- Static inspection does not import or execute code from model repositories.
- Original checkpoints are never modified.
- External provider credentials are never embedded in source or printed to logs.
- Future agent file/terminal execution must be project-scoped, permissioned and resource-limited.
