# Integrated Delivery Roadmap

ECLIPSE has three connected workstreams. The UI is designed early and integrated throughout; it is not postponed until final productization.

## Workstream A — Model Intelligence & Inference Platform

Static checkpoint inspection → Model Atlas → hardware feasibility → reversible preparation → supported inference adapter → measured fast path → runtime intelligence where available → compression/quality experiments.

## Workstream B — Capability Amplification & Knowledge System

Capability Watchdog → planner and acceptance criteria → research/context retrieval → task-scoped tools → execution → verification/recovery → correction memory and skills → Obsidian integration.

## Workstream C — ECLIPSE Agent and desktop experience

Everyday chat and model selection → history/files/project context → shared Core tools → task planning → approved sandboxed execution → GitHub and research → Windows packaging/onboarding/recovery.

## Current gate

Static GGUF, Safetensors, Hugging Face folder and tokenizer/chat-template inspection are present as source code with synthetic tests. The evidence-labelled Model Atlas core composes them into one JSON document (now including a tokenizer section for folder and GGUF sources), and the PySide6 Windows-first shell brings that atlas into the first real workspace screen with all three primary destinations navigable. The Windows build workflow is installed at [`.github/workflows/desktop.yml`](../.github/workflows/desktop.yml); a readable reference copy is at [`desktop-build-workflow.yml`](desktop-build-workflow.yml). The remaining acceptance gates are read-only Windows runs against real Safetensors files, multi-shard Hugging Face folders and tokenizer folders, plus an independent GGUF storage cross-check; none blocks independent engineering. Next, add the memory/VRAM feasibility estimator.

See [`ORIGINAL_PHASE_MAP.md`](ORIGINAL_PHASE_MAP.md) for both canonical phase sequences and the five internal subsystems.
