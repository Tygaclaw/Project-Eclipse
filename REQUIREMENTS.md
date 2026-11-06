# Requirements and Acceptance Register

| ID | Requirement | Current evidence / next gate |
|---|---|---|
| R-001 | Continue in `Tygaclaw/Project-Eclipse` at the user's direct instruction | Repository identity and write access verified; feature branch used |
| R-002 | One integrated ECLIPSE product | Three workspaces and shared Core recorded in `ARCHITECTURE.md` |
| R-003 | Model Intelligence & Inference Platform | GGUF v2/v3, Safetensors and Hugging Face folder/index static parsers implemented; one real GGUF was inspected through the packaged UI on Windows 11; broader real-format validation pending |
| R-004 | Capability Amplification & Knowledge System | Architecture recorded; planner/watchdog/execution work pending |
| R-005 | ECLIPSE Agent | Placeholder workspace present (no chat input, no adapter); working chat and tools pending |
| R-006 | Preserve five Master Plan technical subsystems | Recorded in `ARCHITECTURE.md` and `docs/ORIGINAL_PHASE_MAP.md` |
| R-007 | Inspect models without executing/loading full weights | Synthetic tests cover all inspectors; one real GGUF inspection on Windows 11 reported 0 tensor payload bytes read and no source modification; further format validation pending |
| R-008 | Bounded parser and explicit unknowns | Parser limits, unknown tensor IDs, derived GGUF sizes, Safetensors offsets and HF shard-index cross-checks implemented; synthetic tests present |
| R-009 | Model Atlas with evidence labels and source offsets | Evidence-labelled Atlas core and connected desktop UI render the report; one real GGUF UI inspection completed on Windows 11 with observed/derived labels and read-only safety invariants |
| R-010 | Feasibility and compatibility planner | Pending; exact GGUF storage bytes now available as an input |
| R-011 | Reversible preparation and transformation lineage | Pending |
| R-012 | Proven local inference adapter and resource manager | Pending; preserve existing Qwen/llama.cpp configuration |
| R-013 | Predictive prefetch with true router authority | Research/implementation pending |
| R-014 | Capability Watchdog, planning, verification and recovery | Pending |
| R-015 | Obsidian knowledge system with AI Inbox and approved promotion | Selected historically; integration pending |
| R-016 | Complete four remaining model-agent evaluations | Pending: multi-file feature, runtime debugging, connected-codebase modification, Three.js/game development |
| R-017 | Preserve completed A* evaluation and known-good Qwen baseline | Historical state only; do not make setup or A* retest a prerequisite |
| R-018 | Beginner-friendly Windows desktop with three primary workspaces | PySide6 `6.12.0` shell with all three workspaces navigable; Model Intelligence connected to Model Atlas; packaged Windows x64 artifact built and user-validated with one real GGUF |
| R-022 | Reproducible Windows desktop packaging | PyInstaller spec/launcher and active workflow at `.github/workflows/desktop.yml`; Windows x64 artifact built and uploaded successfully in run #42173214699 |
| R-019 | Safe sandboxed execution and permission boundaries | Requirements recorded in `SECURITY.md`; implementation pending |
| R-020 | Honest status and reproducible evidence | Status/continuation registers and automated tests added |
| R-021 | Discover local Hugging Face model folders | Bounded `config.json` summary and `model.safetensors.index.json` shard-index cross-check implemented; tokenizer assets are now inspected statically; real-folder validation pending |
| R-023 | Static tokenizer and chat-template intelligence without execution | Bounded, read-only tokenizer/chat-template inspector implemented for local folders plus GGUF metadata; `inspect-tokenizer` CLI, Atlas `tokenizer` section, desktop card and 21 synthetic tests added. Templates are never imported, compiled or rendered; real multi-file folder validation pending |

A feature is complete only when its acceptance evidence exists. One real GGUF desktop inspection is now verified on Windows 11; this does not satisfy broader Safetensors/Hugging Face, GPU or inference acceptance gates.
