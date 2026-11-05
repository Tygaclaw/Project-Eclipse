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

`src/eclipse/model_intelligence/gguf.py` is a standard-library-only static parser. It reads a GGUF file sequentially in read-only mode, applies explicit header, string, metadata, tensor and array limits, and returns a JSON-safe report. Tensor payloads are neither loaded nor memory-mapped. The parser records metadata/tensor descriptor offsets and the absolute start of each tensor in the payload region.

The first slice deliberately does not calculate exact tensor storage bytes: that requires a verified, versioned GGML type-layout table. A tensor type it does not recognize is reported as `unknown_<id>`.

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
