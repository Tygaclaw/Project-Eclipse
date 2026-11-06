# Integrated Delivery Roadmap

ECLIPSE has three connected workstreams. The UI is designed early and integrated throughout; it is not postponed until final productization.

## Workstream A — Model Intelligence & Inference Platform

Static checkpoint inspection → Model Atlas → hardware feasibility → reversible preparation → supported inference adapter → measured fast path → runtime intelligence where available → compression/quality experiments.

## Workstream B — Capability Amplification & Knowledge System

Capability Watchdog → planner and acceptance criteria → research/context retrieval → task-scoped tools → execution → verification/recovery → correction memory and skills → Obsidian integration.

## Workstream C — ECLIPSE Agent and desktop experience

Everyday chat and model selection → history/files/project context → shared Core tools → task planning → approved sandboxed execution → GitHub and research → Windows packaging/onboarding/recovery.

## Current gate

Static GGUF, Safetensors and Hugging Face folder inspection are present as source code with synthetic tests. GGUF tensor storage bytes are derived from a versioned GGML type registry, Safetensors storage bytes are observed from declared header offsets, and the folder inspector cross-checks a `model.safetensors.index.json` shard map against files on disk. The evidence-labelled Model Atlas core composes these into one JSON document. The next evidence gate is a verified GitHub Actions run plus a read-only real-file run on Windows. Work can then continue into tokenizer/chat-template inspection, the Model Atlas desktop UI and the memory/VRAM feasibility estimator while the desktop framework is evaluated separately.

See [`ORIGINAL_PHASE_MAP.md`](ORIGINAL_PHASE_MAP.md) for both canonical phase sequences and the five internal subsystems.
