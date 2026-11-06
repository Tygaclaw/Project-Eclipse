# ECLIPSE Decision Log

## D-001 — One product, three workspaces

**Decision:** ECLIPSE is one application with Model Intelligence & Inference Platform, Capability Amplification & Knowledge System, and ECLIPSE Agent as its three primary destinations.

**Reason:** This preserves both original technical workstreams while adding the everyday conversational AI surface. A shared Core coordinates them.

## D-002 — Preserve the original five internal subsystems

**Decision:** The five Master Plan subsystems remain internal architecture, not five additional top-level workspaces.

## D-003 — Static inspection precedes inference

**Decision:** Model inspection and the first Model Atlas must work without loading or executing the target model.

**Reason:** The target use case includes models that cannot fit the available computer.

## D-004 — Python core; desktop shell decision deferred

**Decision:** Begin with a Python 3.11+ core and keep the UI framework undecided until a focused Windows-native comparison/spike is completed.

**Reason:** Python is already the natural integration layer for model formats and agent tooling; delaying the shell avoids premature commitment before backend boundaries are proven.

## D-005 — Use the existing repository by explicit user direction

**Decision:** Continue in `Tygaclaw/Project-Eclipse`.

**Reason:** The user directly instructed that work continue in the existing repository. This supersedes conflicting greenfield/new-repository language in the uploaded handoff kit. The repository's existing history and `main` branch are preserved; implementation work is isolated on a feature branch.

## D-006 — Leave project license undecided

**Decision:** Do not add a license until the repository owner selects one. Public visibility does not itself grant reuse rights.

## D-007 — Derive GGUF sizes from a versioned GGML type registry

**Decision:** Calculate exact GGUF tensor storage bytes from a single registry pinned to a reviewed upstream llama.cpp/GGML revision, and leave sizes explicitly unknown for unregistered types or rows that are not block-multiple.

**Reason:** Quantized GGML tensors store whole blocks, so a bits-per-weight approximation is not an exact byte count. Pinning the registry and its revision makes the derivation auditable and reproducible, and keeping unknown cases unknown preserves the project's evidence rules. Safetensors sizes are observed header offsets and need no registry.

## D-008 — Static inspection covers GGUF and Safetensors before any runtime work

**Decision:** Implement bounded static Safetensors inspection alongside GGUF before preparing an inference adapter.

**Reason:** Both formats share the same read-only, no-payload trust boundary and satisfy the "inspect oversized models without loading them" requirement. This widens Model Atlas coverage without adding runtime dependencies.

## D-009 — Treat a Hugging Face folder as a bounded set of control files

**Decision:** Inspect a local Hugging Face model folder by reading only its small control files (`config.json`, `model.safetensors.index.json`) up to configured byte limits, enumerating file sizes, cross-checking the index shard map, and never following symbolic links or reading shard payloads.

**Reason:** Multi-shard checkpoints are the common Hugging Face layout, and reconciling the index with the files on disk catches incomplete downloads without loading weights. The controls keep the same read-only trust boundary and introduce no third-party dependencies; tokenizer and remote metadata parsing are deliberately deferred.

## D-010 — Model Atlas is an evidence-labelled aggregate, not a renderer

**Decision:** Build the Model Atlas core as a pure, standard-library composition of the existing inspectors that emits one machine-readable JSON document with explicit `observed`/`derived`/`unknown` labels. A desktop/UI renderer is a separate layer over this contract.

**Reason:** Keeping the atlas as data lets it be tested with synthetic fixtures, reused by the future feasibility estimator and CLI, and rendered later without re-deriving model facts. It preserves the single read-only no-payload trust boundary and avoids coupling model facts to a still-undecided UI framework.

## D-011 — PySide6 desktop shell over the existing Python core

**Decision:** Build the Windows-first desktop shell with PySide6 `6.12.0`, packaged with PyInstaller `6.22.3`, and keep the Model Atlas JSON contract and Python inspectors as the single source of model facts.

**Reason:** PySide6 keeps the shell in the same language as the shared Core and existing inspectors, avoids a second-language rewrite or bridge, and has a mature Windows packaging story. The frozen build reuses the existing `build-atlas` CLI through a `--atlas-backend` dispatch so packaged and command-line behavior cannot drift. See `docs/ADR-001-desktop-framework.md` for the compared options (WPF, Tauri 2, Avalonia).
