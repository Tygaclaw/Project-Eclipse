# Integrated Delivery Roadmap

ECLIPSE has three connected workstreams. The UI is designed early and integrated throughout; it is not postponed until final productization.

## Workstream A — Model Intelligence & Inference Platform

Static checkpoint inspection → Model Atlas → hardware feasibility → reversible preparation → supported inference adapter → measured fast path → runtime intelligence where available → compression/quality experiments.

## Workstream B — Capability Amplification & Knowledge System

Capability Watchdog → planner and acceptance criteria → research/context retrieval → task-scoped tools → execution → verification/recovery → correction memory and skills → Obsidian integration.

## Workstream C — ECLIPSE Agent and desktop experience

Everyday chat and model selection → history/files/project context → shared Core tools → task planning → approved sandboxed execution → GitHub and research → Windows packaging/onboarding/recovery.

## Current gate

Static GGUF, Safetensors and Hugging Face folder inspection are present as source code with synthetic tests. The evidence-labelled Model Atlas core composes them into one JSON document. The pull-request CI run passed on Windows with Python 3.11–3.14. The remaining real-file acceptance gate is a read-only Windows run against actual checkpoints; it does not block independent engineering. Next, add tokenizer/chat-template inspection and begin the Windows desktop framework spike and navigable three-workspace shell, bringing the Model Atlas into the first real workspace screen.

See [`ORIGINAL_PHASE_MAP.md`](ORIGINAL_PHASE_MAP.md) for both canonical phase sequences and the five internal subsystems.
