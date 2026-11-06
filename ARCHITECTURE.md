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

`src/eclipse/model_intelligence/tokenizer.py` statically inspects tokenizer assets and chat templates. It reads bounded JSON/text control files (`tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`, `added_tokens.json`, `vocab.json`, `vocab.txt`, `merges.txt`, `chat_template.jinja`, `additional_chat_templates/*.jinja` and legacy `chat_template.json`), inventories SentencePiece `*.model` files by name/size only, and summarises GGUF `tokenizer.*` metadata from the bounded previews the GGUF parser already produced. It never imports Jinja, compiles or renders a template, loads a tokenizer runtime, or reads tensor payloads. Discovered values carry `observed`, `declared`, `derived` or `unknown` evidence, and chat-template precedence cites the documented Hugging Face loader order rather than inferring one.

`src/eclipse/model_intelligence/model_atlas.py` composes those parsers into one evidence-labelled JSON atlas (parameters, storage bytes, type/dtype distribution and, for folder/GGUF sources, a `tokenizer` section) selected by input type. It holds no model facts of its own and delegates all reading to the inspectors. A tokenizer failure is reported as an honest unavailable section and never fails the checkpoint inspection.

`src/eclipse/model_intelligence/ggml_types.py` is a versioned registry of GGML tensor types pinned to a reviewed upstream llama.cpp/GGML revision. It supplies the block size and encoded type size used to derive exact GGUF tensor storage bytes (`type_size * elements / block_size`). A tensor type absent from the registry is reported as `unknown_<id>` with its storage size explicitly unknown, and a quantized row whose length is not a block multiple is left unknown rather than guessed. Safetensors storage bytes are observed directly from the declared header offsets.

## Desktop shell

`src/eclipse/desktop/` is the PySide6 `6.12.0` Windows-first shell. `MainWindow` hosts the three primary workspaces (`NAV_ITEMS`, with `Ctrl+1/2/3` shortcuts) over one sidebar and a `QStackedWidget`. The Model Intelligence workspace performs native file/folder selection and runs `AtlasClient` on a background `QThread`, rendering the existing evidence-labelled atlas JSON. The Capability and Agent workspaces are honest placeholders; the Agent screen has no chat input and states that no model adapter is connected.

`AtlasClient` is the only desktop-to-core boundary. It launches the unchanged `build-atlas` command through `subprocess.Popen` with an argument list (`shell=False`), a timeout and cancellation, bounded stdout/stderr, and validates the `eclipse_model_atlas`/`atlas_version == 1` contract plus the read-only invariants (`tensor_payloads_loaded is False`, `tensor_payload_bytes_read == 0`, `source_modified is False`). No parsing is duplicated in the UI.

The frozen build reuses the same core through `--atlas-backend`, which dispatches to the existing CLI; see `packaging/eclipse-desktop.spec` and `docs/desktop-build-workflow.yml`.

## Technology direction

- Python 3.11+ for the shared model/agent core and AI ecosystem integrations.
- Standard-library-only runtime for the static inspectors and Model Atlas core.
- PySide6 `6.12.0` desktop shell, packaged with PyInstaller `6.22.3`; see `docs/ADR-001-desktop-framework.md`.
- Inference is delegated to supported, maintained engines through adapters; ECLIPSE will not start by implementing its own matrix-multiplication kernels.

## Trust boundaries

- Model files and their metadata are untrusted data.
- Static inspection does not import or execute code from model repositories.
- Original checkpoints are never modified.
- External provider credentials are never embedded in source or printed to logs.
- Future agent file/terminal execution must be project-scoped, permissioned and resource-limited.
