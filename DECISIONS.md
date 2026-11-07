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

## D-012 — Inspect tokenizer and chat templates as untrusted static data

**Decision:** Summarise tokenizer assets and chat templates statically under per-file and aggregate JSON/template byte limits, an aggregate template-count limit, bounded token-entry work and clipped previews. Reject a symlinked inspection root and do not follow root or nested symlinks. Never import, compile, render or execute a template; inventory SentencePiece `*.model` files by name and size only. Record the documented Hugging Face load sequence: read the legacy embedded `tokenizer_config.json` template (or the legacy `chat_template.json` format for processors), let root `chat_template.jinja` override the default, then merge named `additional_chat_templates/*.jinja`. Flag the documented processor incompatibility when `chat_template.json` coexists with modern Jinja files; do not infer that a folder is a processor and do not report an effective default for that combination. GGUF tokenizer facts are derived only from the bounded `tokenizer.*` previews the GGUF parser already produced.

**Reason:** Chat templates are executable Jinja in the Transformers runtime and are untrusted data here. Treating them as inert text preserves the project's no-execution trust boundary while still telling the user what the model declares. Per-file and aggregate limits, bounded token-entry scans and clipped previews prevent large or malformed tokenizer metadata from causing uncontrolled work. Reusing the GGUF parser's bounded previews avoids a second read of the file. The cited Hugging Face load behaviour is reported as documentation, not proof that a particular model folder is runtime-compatible.

## D-013 — One SQLite store and one event bus under all three workspaces

**Decision:** Put models, prepared variants, profiles, runs, conversations, attachments, tasks, corrections, knowledge metadata and settings in one standard-library SQLite store owned by `AppContext`. The desktop, CLI and tests use the same Core.

**Reason:** A single durable store prevents the three workspaces from drifting into separate histories or model registries. SQLite needs no server, works offline, and supports transactional updates and real integration tests without third-party packages.

## D-014 — Managed llama.cpp with an OpenAI-compatible attach mode

**Decision:** The first runtime adapter manages a real `llama-server` subprocess for GGUF models and also attaches to an existing OpenAI-compatible endpoint. Both use the same streaming client, profile validation and run records. States and errors are reported truthfully; a failed launch never becomes Ready.

**Reason:** This preserves the owner's known-good Windows/Vulkan/Qwen setup instead of reinstalling it, while keeping ECLIPSE independent of one engine. Attach mode also makes it possible to test the complete streaming/tool contract without a GPU or a model download.

## D-015 — Application-level permission boundary, not a claimed OS sandbox

**Decision:** Scope file tools to the approved project root, reject canonical path escapes, require explicit approval for writes/commands, use argument-list subprocesses with timeouts, and cap outputs. Document this as application-level scoping rather than an OS container sandbox.

**Reason:** The boundary is real and testable today, while an OS-level sandbox is a separate engineering and packaging problem. Overstating the protection would be worse than a precise limitation.

## D-016 — Completion requires independent evidence

**Decision:** A capability task is completed only when all plan objectives are done, the model loop stopped normally, and the verification engine actually ran passing checks. Denied or failed writes are recorded as failures. A correction memory entry is promoted only with substantive evidence and a regression reference. A repair produces a candidate lesson, not a verified one.

**Reason:** The model's own summary is not evidence. This is the core honesty rule of the Capability System and is enforced by tests that seed failing checks and denied approvals.

## D-018 — Backend support remains a declaration comparison until measured

**Decision:** `runtime-support` compares a model atlas and host snapshot against the backend's declared formats, architectures, tensor types, devices, placement modes and controls. It reports only `declared_supported`, `unsupported` or `unknown`, labels GPU hardware as `hardware_present_backend_unvalidated`, and always sets `runtime_verified` to false. Actual loading and telemetry are separate runtime evidence.

**Reason:** A manifest cannot prove that a backend binary was compiled with the needed kernels or that a model will load. Keeping the static matrix explicitly separate prevents the UI or CLI from presenting a declaration as a successful runtime result.

## D-019 — Mark profiles good only after a real generation

**Decision:** Persist the effective execution profile after a successful model load, but mark it last-known-good only after a successful, non-cancelled generation. Restoring a saved profile re-validates it against the current model before starting. Benchmarks run warm-up plus repeated measured generations and report median, range and variance rather than a single best run.

**Reason:** Loading alone does not prove the configuration produces usable output, and one fast run is not a benchmark. This makes rollback and performance claims depend on observed evidence, while still allowing a failed configuration to be replaced by the previously working profile.

## D-017 — Knowledge proposals are separated from trusted knowledge

**Decision:** Model-generated notes are written to `06 - AI Inbox` with `status: inbox`. Approval copies them into a trusted folder with an approval record; rejection records the reason. An existing trusted note is never overwritten; a collision gets a numeric suffix.

**Reason:** Retrieval must not silently promote untrusted model output into the knowledge base. Keeping the vault as ordinary Markdown preserves the user's ability to inspect, edit and version it in Obsidian.
