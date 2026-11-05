# ECLIPSE Testing and Acceptance Plan

## 1. Test levels

1. Unit tests: parsers, calculations, planners, policy rules, data structures.
2. Integration tests: model adapters, registry, memory, tools, permissions, UI/backend boundaries.
3. Property and malformed-input tests: checkpoint parser robustness, bounds, offsets, corrupt headers, huge files.
4. Security tests: path traversal, malicious metadata, unsafe deserialization, command injection, secret redaction, sandbox escapes where practical.
5. Performance tests: bounded inspection memory, parse time, load times, cache, bytes moved, memory peaks, token speed and latency.
6. End-to-end tests: chat, tool use, file editing, code execution, repair, GitHub action and model inspection-to-feasibility workflows.
7. Windows hardware validation: real Qwen/runtime, Vulkan, VRAM/RAM budgets, desktop installer, resource guardian and recovery.

## 2. Historical model/agent evaluations

A* pathfinding is already recorded as completed. Preserve its historical result and do not repeat as a prerequisite. Four categories remain:

- Multi-file feature development.
- Runtime debugging using real logs and failures.
- Safe modification of an interconnected codebase.
- Three.js/game development.

Compare raw Qwen baseline, basic tool loop and complete ECLIPSE. Control task definition, environment, prompt/settings and acceptance tests. Record first-try success, success after repair, acceptance pass rate, regressions, false completion claims, tool calls/retries, elapsed time, context use and resource use.

Keep Reading List Manager regression cases: uninitialized collection; UUID regenerated during deserialization; wrong JSON nesting level; strings passed where enum values are expected; tests expecting output files that were never created.

## 3. Model Intelligence Laboratory acceptance

- Inspect a model too large for local inference using bounded file/metadata operations.
- No full-model load or inference required.
- GGUF metadata/tensor inventory reconciles with file structure.
- Safetensors headers/shard index parsing is bounded and correct for supported variants.
- Malformed/unsupported architectures fail safely and are labelled unknown, not guessed.
- Every field labels its evidence type.
- Original checkpoint is unchanged.
- Machine-readable and readable Atlas reports agree.
- Peak memory is measured and bounded by design/limits.

## 4. Feasibility and preparation acceptance

- KV-cache calculation uses actual architecture, KV heads, head dimension, layer count, precision and context.
- Weight, runtime and KV memory separated.
- RAM/VRAM/SSD budgets are explicit.
- Estimated vs measured values are labelled.
- Prepared package reproduces from manifest.
- Checksums pass; originals preserved.
- No unsupported speed prediction is presented as a measured fact.

## 5. Compression/transformation acceptance

Every derived candidate must have source hash, method/parameters, tool versions, output hash, integrity validation and test record. Compare model size, speed, memory and held-out task quality. Do not claim capability preservation without tests. Include regression tests and rollback. Distillation must document teacher/data/computation requirements.

## 6. Predictive runtime acceptance

- Router-selected expert remains authoritative.
- Prefetch decisions can be wrong without changing model semantics.
- Measure prediction coverage, useful prefetch, cache hit rate, wasted bytes, transfer overlap, latency, throughput and quality equivalence.
- Compare with a no-prefetch baseline.
- Measure telemetry/predictor overhead.
- Safe fallback when telemetry is missing or predictor confidence is low.

## 7. Agent acceptance

- Chat with at least one supported local model.
- Model selection and switching.
- Conversation history persistence and retrieval.
- Supported attachments/document analysis.
- Memory retrieval with scope and provenance.
- Multi-step plan execution.
- Approved filesystem operations within project boundary.
- Sandboxed code execution and tests.
- Tool activity and action records.
- GitHub read/write operation with explicit permission boundary.
- Error recovery and re-test.
- Claims match tool/test evidence.

## 8. Desktop UX acceptance

- Real installable Windows desktop application.
- Three primary workspaces are clear.
- Agent is easy to find and works as everyday chat.
- Default screens are uncluttered.
- Colourful, cohesive, lively visual system.
- Advanced metrics/settings are hidden until requested.
- Guided onboarding and model connection.
- Useful error and progress states.
- Keyboard/accessibility basics and light/dark themes.
- Install, launch, update, uninstall and recovery tested.

## 9. Release gate

No final release until required automated checks pass, Windows-dependent checks are completed or explicitly documented as blocked, secrets/security checks are reviewed, required documentation is current, and a reproducible install/recovery procedure exists.
