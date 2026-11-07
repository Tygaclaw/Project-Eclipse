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

`src/eclipse/model_intelligence/gguf.py`, `src/eclipse/model_intelligence/safetensors.py`, `src/eclipse/model_intelligence/hf_folder.py` and `src/eclipse/model_intelligence/tokenizer.py` are standard-library-only static parsers. Each reads a checkpoint's header/index (or small tokenizer control files) sequentially in read-only mode, applies explicit limits, and returns a JSON-safe report. Tensor payloads are neither loaded nor memory-mapped. The parsers record metadata/tensor descriptor offsets, the absolute start of each tensor in the payload region and per-tensor storage bytes. The Hugging Face folder parser reads only small control files (`config.json`, `model.safetensors.index.json`), enumerates file sizes, cross-checks the shard index against the files on disk, and does not follow symbolic links.

`src/eclipse/model_intelligence/tokenizer.py` statically inspects tokenizer assets and chat templates. It reads bounded JSON/text control files (`tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`, `added_tokens.json`, `vocab.json`, `vocab.txt`, `merges.txt`, `chat_template.jinja`, `additional_chat_templates/*.jinja` and legacy `chat_template.json`), inventories SentencePiece `*.model` files by name/size only, and summarises GGUF `tokenizer.*` metadata from the bounded previews the GGUF parser already produced. It never imports Jinja, compiles or renders a template, loads a tokenizer runtime, or reads tensor payloads. Per-file/aggregate JSON and template byte caps, a shared template count, bounded added-token ID scans, clipped previews, root/nested symlink rejection and source immutability tests bound untrusted input handling. Discovered values carry `observed`, `declared`, `derived` or `unknown` evidence. It reports the documented Hugging Face load sequence and the conditional legacy-processor incompatibility without guessing the folder's model kind.

`src/eclipse/model_intelligence/model_atlas.py` composes those parsers into one evidence-labelled JSON atlas (parameters, storage bytes, type/dtype distribution and, for folder/GGUF sources, a `tokenizer` section) selected by input type. It holds no model facts of its own and delegates all reading to the inspectors. A tokenizer failure is reported as an honest unavailable section and never fails the checkpoint inspection.

`src/eclipse/model_intelligence/ggml_types.py` is a versioned registry of GGML tensor types pinned to a reviewed upstream llama.cpp/GGML revision. It supplies the block size and encoded type size used to derive exact GGUF tensor storage bytes (`type_size * elements / block_size`). A tensor type absent from the registry is reported as `unknown_<id>` with its storage size explicitly unknown, and a quantized row whose length is not a block multiple is left unknown rather than guessed. Safetensors storage bytes are observed directly from the declared header offsets.

## Shared Core

`src/eclipse/core/` is the single application Core. `config.py` owns the home layout (`models/`, `prepared/`, `knowledge/`, `logs/`, `attachments/`, SQLite database and settings JSON); `storage.py` is a SQLite schema for models, prepared variants, profiles, runs, conversations, messages, attachments, tasks, correction memory, knowledge-note metadata and settings; `events.py` is a thread-safe event bus with bounded history; `security.py` provides the permission broker, canonical path scoping, write/command approvals, command validation, redaction and atomic writes. No workspace creates a second store or runtime.

## Model preparation and runtime

`src/eclipse/model_intelligence/preparation.py` creates index or copy packages with SHA-256 inventories, source/output identity, lineage, a JSON manifest, verification against the recorded hashes, safe removal of only derived packages, and a quantize path that is unavailable unless a real `llama-quantize` is found.

`src/eclipse/runtime/` owns inference. `backends.py` is the support matrix; `client.py` is a streaming OpenAI-compatible client with SSE parsing, cancellation and tool-call assembly; `llamacpp.py` launches and health-checks a real `llama-server` process and reads its observed context; `manager.py` is the only owner of runtime state and process lifecycle; `profiles.py` resolves intent into explicit settings and rejects unsupported combinations; `telemetry.py` samples the process/host and computes measured stream metrics. A failed launch cleans up the process and reports `failed` with the real error. Attach mode never claims ownership of an external server.

## Capability System

`src/eclipse/capability/` contains the watchdog (`classify_task`), planner (`build_plan`/`mark_objective` with acceptance criteria and drift signals), project index/stack detection, tool registry, verification engine, execution loop (`run_tool_loop` with loop detection and cancellation), correction memory and Obsidian-compatible knowledge base. `engine.py` creates durable tasks, executes the plan through the model and tools, runs independent verification, performs a bounded repair loop, and marks completion only when every objective is done and verification actually passed. Permission denials and failed commands are recorded as failures, not converted into success.

## Agent

`src/eclipse/agent/agent.py` implements conversations on the same store and runtime: persistent history, search/rename/delete, model selection, copied text attachments, bounded context, streaming deltas, tool execution with the same permission broker, persisted tool metadata, honest runtime-error messages and a working Stop/cancellation token.

## Desktop shell

`src/eclipse/desktop/` is the PySide6 `6.12.0` Windows-first shell. `MainWindow` hosts the three primary workspaces (`NAV_ITEMS`, with `Ctrl+1/2/3` shortcuts) over one sidebar and a `QStackedWidget`, and owns one `AppContext` (store, settings, event bus, runtime, knowledge, memory, capability engine and agent). The Model Intelligence platform has Inspect & feasibility and Prepare & run tabs; the latter drives registry, preparation, backend profiles, lifecycle, telemetry, diagnostics and a real generation test. The Capability workspace has Plan & evidence, Verification, Knowledge and Corrections tabs. The Agent workspace has a conversation sidebar, streaming transcript, composer, attachments and Stop.

`AtlasClient` remains the bounded inspection boundary. It launches `build-atlas` through `subprocess.Popen` with an argument list (`shell=False`), a timeout and cancellation, bounded stdout/stderr, and validates the `eclipse_model_atlas`/`atlas_version == 1` contract plus the read-only invariants (`tensor_payloads_loaded is False`, `tensor_payload_bytes_read == 0`, `source_modified is False`). Other workspace operations call the shared Core in-process through worker threads so the UI stays responsive.

The frozen build reuses the same core through `--atlas-backend`, which dispatches to the existing CLI; see `packaging/eclipse-desktop.spec` and `docs/desktop-build-workflow.yml`. The spec lists the Core, runtime, capability, agent and desktop modules as hidden imports so the packaged app includes them.

## Technology direction

- Python 3.11+ for the shared Core and AI ecosystem integrations.
- Standard-library-only Core (SQLite, urllib SSE, subprocess management) for portability; PySide6 `6.12.0` desktop shell packaged with PyInstaller `6.22.3`; see `docs/ADR-001-desktop-framework.md`.
- Inference is delegated to supported, maintained engines through adapters; ECLIPSE does not implement its own matrix-multiplication kernels.
- Obsidian knowledge is plain Markdown with YAML front matter, so the vault remains usable outside ECLIPSE.

## Trust boundaries

- Model files and their metadata are untrusted data.
- Static inspection does not import or execute code from model repositories.
- Original checkpoints are never modified; preparation writes only to the prepared store.
- File tools are canonicalized inside the approved workspace; traversal and symlink escape are rejected. Writes use atomic replacement after explicit approval. Commands are argument lists, never shell strings, and are timeout-bounded.
- The current boundary is application-level path/process scoping, not an OS container sandbox; do not describe it as one.
- External provider credentials are read from the environment and never embedded in source or printed to logs.
- Knowledge proposals stay in the AI Inbox until a human approves them into a trusted folder.
