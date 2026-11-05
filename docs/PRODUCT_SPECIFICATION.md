# ECLIPSE Product Specification

## Product statement

ECLIPSE is one Windows-first, local-first AI desktop application. It unifies two original engineering workstreams and a third everyday Agent workspace through one shared Core.

## Primary workspaces

### 1. Model Intelligence & Inference Platform

Import supported model files/folders; perform static inspection; build a Model Atlas; estimate feasibility; prepare reversible variants; study compression; integrate proven inference engines; measure CPU/GPU/RAM/VRAM/SSD use; and manage resource budgets.

### 2. Capability Amplification & Knowledge System

Provide task planning, project understanding, research/context retrieval, scoped execution, verification, recovery, loop detection, correction memory, specialized skills and an Obsidian-backed human-readable knowledge library.

### 3. ECLIPSE Agent

Provide a familiar chat experience with model selection, streaming where supported, conversation history, file inputs, project context, memory, safe code/terminal execution, research, GitHub tools and multi-step task execution. It must invoke the other two workspaces through shared services rather than being a disconnected chatbot.

## Shared Core

Model registry and adapters; provenance; hardware/resource services; context retrieval; memory; planning/orchestration; permission broker; tool registry; sandboxed execution; verification/recovery; diagnostics; evaluation and preferences.

## Evidence levels

Every factual Atlas field is labelled `observed`, `derived`, `published`, `estimated`, `hypothesized` or `unknown`. Static metadata is not proof of runtime routing behavior, real tokens/second or quality retention.

## Product boundaries

- No mandatory paid API or cloud inference.
- No Linux/WSL requirement for core workflows.
- No model-repository code execution during static inspection.
- Original checkpoints are immutable; derived outputs use separate paths and manifests.
- Agent capabilities are described only when integrated and tested.
- Default interface is beginner-friendly and uncluttered; advanced metrics are optional.
