# ECLIPSE — Complete Product and Runtime Vision

**Date:** 6 November 2026  
**Document role:** Additive product and engineering specification  
**Status:** Defines intended product behaviour. Implementation status remains in `STATUS.md`.

This document consolidates the ECLIPSE product decisions and requirements established in project discussions. It supplements, rather than replaces, `ARCHITECTURE.md`, `REQUIREMENTS.md`, `docs/PRODUCT_SPECIFICATION.md`, `docs/INTEGRATED_ROADMAP.md` and `docs/ORIGINAL_PHASE_MAP.md`.

## 1. Mission

ECLIPSE is a single Windows-first, local-first desktop application for understanding, preparing, executing, managing and improving open-weight AI models on the hardware actually available to the user.

It is not merely a model-file viewer, tensor inspector, downloader, quantizer, thin launcher or chatbot. ECLIPSE must connect model understanding to real execution: inspect a model before loading it; understand the host hardware; calculate feasible execution arrangements; launch the model through a supported inference engine; observe what actually happened; and let the user adjust and save the configuration.

The central objective is the greatest **verified useful capability at the best practical sustained speed**, within explicit resource limits and while keeping Windows responsive. Successful loading alone is not success. A model that loads but generates too slowly, pages the PC heavily or loses important capabilities must be reported honestly.

Performance goals are targets to measure, not promises:
- Preferred where model and hardware allow: approximately 15–20+ sustained tokens/second.
- Primary everyday acceptance target: 10+ sustained tokens/second.
- Below 5 tokens/second may be useful for research or batch work, but must not be presented as the everyday fast path.
- Always measure time to first token, sustained generation rate, variability, resource use, storage traffic and output quality.

A model/hardware combination is allowed to fail a performance gate. ECLIPSE must explain the limiting factor and show the fastest verified alternative rather than inventing a speed claim.

## 2. One application, three primary workspaces

ECLIPSE is one integrated application with exactly three primary destinations:

1. **Model Intelligence & Inference Platform** — inspect models, understand their requirements, prepare variants, plan execution, run models and manage runtime resources.
2. **Capability Amplification & Knowledge System** — support complex tasks with research, context retrieval, controlled tools, verification, recovery, memory and reusable skills.
3. **ECLIPSE Agent** — everyday conversational AI with model selection, conversation history, attachments, project context and access to approved ECLIPSE tools.

All three use one shared Core. They must not become separate applications or disconnected implementations.

### 2.1 Shared Core

The Core provides the model registry and provenance; runtime adapters; hardware discovery and resource budgets; feasibility and execution-profile services; inference lifecycle and telemetry; conversation/context retrieval; project and correction memory; skills; planning/orchestration; permissions and approvals; tools; sandboxed execution; verification/recovery; diagnostics and evaluation.

A model selected in Agent must resolve through the same model registry and runtime services used by the Model Intelligence workspace.

### 2.2 Five original model-engineering subsystems

These remain internal components, not additional primary navigation tabs:

1. Model Intelligence Laboratory.
2. Model Preparation and Optimization.
3. High-Speed Inference Engine.
4. Intelligence Preservation and Recovery.
5. ECLIPSE Desktop and Resource Manager.

The High-Speed Inference Engine is the third original model-engineering subsystem. Its functionality belongs primarily inside Model Intelligence & Inference Platform and is also exposed through shared Core services to Agent. It does not create a fourth primary workspace.

## 3. Complete model lifecycle

The Model Intelligence & Inference Platform must ultimately support this lifecycle:

1. **Import:** register a supported model file or folder without loading all weights into RAM or VRAM.
2. **Inspect:** read bounded metadata, architecture, tensor descriptors, tokenizer assets and supported configuration; build a Model Atlas.
3. **Assess hardware:** discover the actual computer, available resources, backend support, compute capability and storage characteristics.
4. **Plan feasibility:** calculate memory needs and candidate device placements, including context/KV-cache costs and runtime overhead.
5. **Prepare:** optionally create reversible, separately stored variants and indexes while keeping the original immutable.
6. **Configure:** create an execution profile and manifest describing model, backend, precision, placement, context, cache policies and budgets.
7. **Launch:** start a supported inference backend from within ECLIPSE.
8. **Observe:** show actual runtime status and measurements from the OS, backend and available hardware telemetry.
9. **Tune:** allow supported settings to change, move supported data between memory tiers, or safely restart with a new profile.
10. **Save and compare:** retain working profiles and benchmark records; preserve failed experiments and diagnostics for reproduction.

Static inspection and initial feasibility must remain useful even when the complete model cannot run on the user's PC. Running the model is a later, separate capability gate.

## 4. Model Intelligence Laboratory — inspect before execution

The Laboratory determines what can be learned from checkpoint files and metadata without executing the target model.

Initial formats include GGUF, Safetensors, Hugging Face-style model folders/shard indexes, and supported tokenizer/chat-template assets.

Where declared by the source, the Atlas should describe:
- architecture family, layer count, hidden dimensions, attention and key/value heads, head dimensions and positional-embedding details;
- dense or Mixture-of-Experts structure, expert count, declared experts-per-token and shared experts;
- tensor inventory, names, shapes, data types, byte offsets and shard locations;
- quantization types and relevant metadata;
- tokenizer assets, vocabulary declarations/count evidence, special tokens and chat-template sources;
- declared context-window information and related configuration.

Use bounded file reads and explicit limits. Do not load tensor payloads merely to inspect metadata. Never import or execute model-repository code, template code or custom modules. Treat model files and embedded metadata as untrusted input.

Every factual field must identify its evidence category, such as observed, derived, published, estimated, hypothesized or unknown. Missing values remain unknown rather than being guessed from a model name.

Static inspection can identify declared architecture and routing configuration. It cannot prove real-world expert frequency, actual runtime placement, token speed or quality retention; those require separate runtime or behavioural evidence.

## 5. Hardware discovery and feasibility planning

ECLIPSE must reason about the computer on which the user intends to run the model, not a hypothetical workstation.

The established target baseline is Windows 11, Intel Core i7-8700K, NVIDIA RTX 2060 Super with 8 GB VRAM, 48 GB DDR4-3200 system RAM, and user-selected local storage. These are recorded target specifications, not hard-coded assumptions for every installation. ECLIPSE must detect current devices and available resources whenever it builds or validates a plan.

The planner must account for:
- physical and currently available VRAM;
- available system RAM plus a configurable reserve for Windows and foreground applications;
- model weights and the amount of each group that can be resident in each tier;
- KV-cache memory at the requested context length and cache precision;
- backend/runtime overhead, workspaces, temporary buffers, batch size and concurrency;
- CPU thread/compute limits;
- GPU/backend/operator compatibility;
- storage type, read performance where measurable and data-transfer costs;
- other running processes and user-configured resource ceilings.

### 5.1 Context and KV-cache calculation

Context length is a real memory and performance decision, not just a text box.

For common transformer attention layouts, a standard starting formula for KV storage is:

`2 × layer_count × context_tokens × KV_heads × head_dimension × bytes_per_KV_element`

The implementation must account for architecture-specific differences, precision, backend layout, alignment, cache quantization, batching/parallel sequence slots and runtime overhead. This is not a universal substitute for a backend's actual allocation report.

The UI must distinguish:
- model-declared/native context limit;
- context requested in the profile;
- context accepted by the backend;
- KV-cache memory estimated before launch;
- actual cache allocation/runtime-reported use, when exposed.

A command-line flag being accepted does not prove the requested context was allocated or can be used correctly. If the backend cannot confirm a value, say so.

### 5.2 Feasibility outcomes

Return understandable outcomes such as **Fits comfortably**, **Fits with trade-offs**, **Marginal / needs a test**, **Not practical on this hardware**, or **Unknown**. Explain whether the limiting factor is capacity, bandwidth, compute or compatibility. Separate observed, derived, estimated and unknown values. Do not invent tokens/second predictions.

## 6. High-Speed Inference Engine — make the model actually run

The inference engine is a core product capability, not an optional launcher.

ECLIPSE owns orchestration, planning, execution profiles, resource coordination, telemetry, measurement and user experience. It should reuse established, maintained inference engines and optimized kernels wherever they support the model and target hardware. It should not begin by writing a replacement matrix-multiplication kernel library.

A backend adapter must declare and test:
- supported model formats and architectures;
- CPU/GPU devices and Windows execution path;
- tensor/quantization types and operator support;
- CPU/GPU hybrid execution and device-placement controls;
- KV-cache placement and precision controls where available;
- context, batch and parallel-slot settings;
- telemetry it can reliably report and features it does not support.

Select the backend using actual model compatibility, operator coverage, Windows support, GPU generation and measured performance. Never assume a backend supports every model or every low-bit type.

The previously working local Qwen3.5-9B Q4_K_M plus llama.cpp configuration is a known-good historical baseline. Its reported all-33-layer GPU offload and 256K context target are reference information to preserve, not permission to reconfigure or replace the working installation. The recorded server exposed the RTX 2060 Super through Vulkan; do not describe it as CUDA without fresh evidence. ECLIPSE should manage/connect to this proven setup through a safe adapter rather than asking the user to reinstall it.

## 7. Three-tier memory and intelligent placement

The engine must coordinate three physical memory tiers. They are not interchangeable.

| Tier | Intended role | Operating principle |
|---|---|---|
| GPU VRAM | Fastest working space for GPU-executed layers/weights, active experts, KV/cache buffers and temporary workspaces | Use a hard budget, reserve room for display/backend overhead, and never assume all installed VRAM is available. |
| System RAM | Warm residency for weights or experts that do not fit in VRAM, mapped pages, staging, prefetch candidates, cache and runtime buffers | Preserve a Windows/application reserve and avoid paging or memory thrashing. |
| SSD/storage | Original checkpoints, prepared packages, cold weight/expert data, indexes and logs | Use for persistence, loading and controlled prefetch; avoid repeated large cold reads in the per-token critical path. |

The planner should work out the best practical distribution for the model and actual computer. Depending on architecture and backend support, this can include:
- choosing which layers or supported tensor groups execute on the GPU;
- keeping other layers/groups in RAM for CPU execution or staging;
- keeping model source and cold data on SSD;
- choosing supported CPU/GPU split and offload modes;
- deciding which data stays resident and which can be prefetched;
- assigning safe budgets to weights, KV cache, temporary buffers and caches.

Total parameter count alone is insufficient. Layer dimensions, tensor types, quantization, shared layers, expert activity, context length, cache precision, kernels, bandwidth and compute capacity all matter.

Represent the selected arrangement in an execution manifest. Record model identity/source hash, backend/version, device inventory, requested and accepted context, placement/offload settings, cache policy, budgets, precision settings and evidence supporting each value.

### 7.1 User-adjustable placement and memory policies

The user must be able to review and change ECLIPSE's recommendations. Provide automatic recommendations with manual overrides for supported settings, including:
- context length and cache settings;
- VRAM/RAM budgets and reserves;
- supported GPU-offloaded layer count or equivalent placement controls;
- CPU/GPU split and backend-specific placement modes;
- KV-cache device and precision where supported;
- cache size, expert residency and prefetch budgets where supported;
- CPU threads, batch and concurrency where relevant.

Explain each setting in plain language, its likely memory/speed consequence, backend limitations, and whether a restart is needed.

Do not expose controls the active backend cannot honour. Unsupported settings must be clearly unavailable with an explanation, not represented as working controls.

### 7.2 Moving weights, context and cache

The user should be able to control where model data is kept, within the selected backend's real capabilities.

Be precise about "context":
- Conversation text and prompt history are application-managed input data.
- The **KV cache** is runtime memory holding attention state for processed tokens; it is often the large allocation associated with long context.
- Model weights are the learned parameters used during inference.

Expose these separately: prompt/context limit, KV-cache allocation/placement, and model-weight/layer/expert placement.

Where the backend supports safe live movement or resizing, ECLIPSE may offer it with clear status and measurements. Where it does not, stage the requested change and perform a controlled unload/reload or restart. Never pretend arbitrary weights or a live KV cache can be moved between devices when the backend has no such capability.

The user must be able to change a profile and move supported data between VRAM, RAM and storage without modifying the original checkpoint. Changes requiring conversion or a derived package must create a separate, traceable output.

### 7.3 MoE residency and prefetch

For MoE models, eventually manage hot, warm and cold expert data using layer/expert size, workload profile, observed access information where available, transfer cost and available memory.

Correctness rules:
- The model's actual router-selected expert is authoritative.
- A predictor may only provide a cache or prefetch hint.
- Never substitute a predicted expert for the one actually selected.
- On a cache miss, fetch and execute the router-selected expert; correctness takes priority over latency.
- Apply bandwidth limits, confidence thresholds, cancellation, prioritization and cache-pollution safeguards.
- Measure residency, hits/misses, load times, transferred bytes, evictions, useful/wasted prefetch and actual latency benefit.

Static inspection does not prove expert-use frequency. Runtime routing/access information may be used only when a compatible backend exposes reliable telemetry or authorized external traces exist. Basic model execution must not depend on tracing.

## 8. Runtime controls — start, stop, unload and restart

The user must be able to operate the model from inside ECLIPSE without manually rebuilding command lines or opening a separate terminal for routine use.

The runtime manager must provide real controls:
- **Start / Load:** validate the selected profile and budgets, then launch the backend.
- **Stop:** request graceful shutdown and show whether the process exited.
- **Unload:** release model/backend allocations and verify resource release where observable.
- **Restart:** apply settings requiring a fresh process, then relaunch with the selected profile.
- **Apply changes:** update live only where the backend explicitly supports it; otherwise show **Restart required**.
- **Recover:** capture diagnostics, clean up a failed child process where safe, and allow restart with the last known-good profile.
- **Select profile:** switch among saved configurations with a clear reload indication.

Use truthful lifecycle states such as `Not loaded`, `Preparing`, `Starting`, `Loading`, `Ready`, `Generating`, `Stopping`, `Unloading`, `Restart required`, `Failed` and `Needs attention`. Derive them from process/backend results, not decorative timers or assumed success.

A stop control must remain accessible while the model runs. Failed launches must not leave a false `Ready` state or orphaned process. Track process ownership, timeouts, cancellation, logs and exit codes.

On restart, preserve the selected profile and, where practical, conversation history separately from the old runtime. Explain that the old model's KV cache is runtime state and may be lost when its process restarts.

## 9. Execution profiles

Each model can have multiple named profiles. Useful profile intents include:
- **Auto:** choose the best tested settings within configured resource limits.
- **Balanced:** balance speed, memory headroom and quality.
- **Fast:** prioritize measured throughput/latency while retaining safe reserves.
- **Quality / Long Context:** prioritize supported quality/context settings while explaining memory and speed costs.
- **Custom:** expose the user's supported overrides.

These are not magical backend modes. Each profile must resolve to explicit settings for the active model/backend.

Record model identity, format, source hash, prepared-variant lineage, backend/version/device path, requested and accepted context, placement/offload configuration, budgets/reserves, KV-cache configuration, cache/prefetch/expert settings where supported, CPU/batch/concurrency options, hardware snapshot, creation time, validation and benchmark outcomes.

Keep the last known-good profile. An untested profile must not overwrite it. Retain failed experiments with diagnostics and provide rollback.

## 10. Runtime telemetry and hardware sensors

Show useful, truthful runtime information without turning the default screen into a permanent wall of metrics.

Where supported, collect GPU utilization/VRAM, CPU and process use, system RAM, storage activity/read throughput, temperatures/power/clocks only through supported sensor interfaces, model load time, time to first token, prompt processing, generation rate, latency/variance, KV-cache/backend allocation, bytes moved, cache hits/misses, expert residency, process health and logs.

Identify telemetry sources. If a sensor or backend statistic is unavailable, display unavailable/unknown, not zero. Avoid polling so aggressively that monitoring itself harms performance; measure monitoring overhead.

Provide a compact normal status view and expandable diagnostics/advanced view. Use actual host/backend measurements rather than synthetic telemetry or fake progress.

## 11. Preparation and intelligence preservation

Preparation outputs must be separate from source imports. Start with low-risk indexes, manifests, checksums, bounded access/memory-mapped layouts where supported, and tensor layout/alignment only when a backend can benefit.

Later experiments may include quantization, mixed precision, sensitivity/importance methods, structured sparsity, pruning, low-rank approximations and distillation when prerequisites exist.

Every derived candidate records source hash, method/parameters, tool versions, output hash, integrity checks, benchmark settings and quality results. Original checkpoints remain immutable.

Compression does not automatically improve speed. Kernel support, dequantization overhead, data movement, CPU fallback, bandwidth, memory footprint and output quality must be compared with a baseline.

The optional Neural Error-Correction Sidecar (NECS) is experimental and separate from the Capability System's verified correction memory. Do not make NECS a dependency unless held-out evaluations demonstrate repeatable quality benefit at acceptable speed/memory cost.

## 12. Capability Amplification & Knowledge System

This workspace supports the selected model; it does not change its learned parameter count or make a smaller model literally equivalent to a much larger one.

Provide:
- Capability Watchdog for task difficulty, risk, uncertainty and testability;
- Planning Engine for dependencies, acceptance criteria, checkpoints and risks;
- Research & Context Engine for current documentation, project maps, relevant files and trusted knowledge;
- task-scoped tools and controlled execution;
- independent verification using tests, builds, runtime checks or other evidence;
- recovery and strategy changes when an approach repeatedly fails;
- loop detection and honest stopping conditions;
- persistent verified correction memory with root cause, proven fix, scope and reproduction test;
- reusable specialized skills/playbooks loaded only when relevant.

Keep model intelligence (learned capability) distinct from system intelligence (useful work enabled by information, tools, planning, execution, feedback and verification).

## 13. Obsidian and persistent knowledge

Obsidian is the intended human-readable, local knowledge library. It makes project knowledge and verified learning inspectable by the user.

Planned areas include system knowledge/operating rules; project architecture, requirements, decisions and progress; verified skills; verified corrections and regression cases; dated research with sources; an AI Inbox for proposed/unverified notes; and a dashboard linking active projects, progress, research, corrections, skills and issues.

Use scoped retrieval; do not load the entire vault into every prompt. New lessons first enter a proposed/unverified area. Promote them only after evidence and, where appropriate, user approval. Do not silently delete or rewrite trusted notes.

Direct Markdown access may be sufficient initially. Any plugin/MCP integration must be evaluated for maintenance, permissions and security. Start with least privilege.

## 14. ECLIPSE Agent

The Agent is the everyday conversational front end. It should provide a familiar chat layout and streaming where supported; a model picker using the shared registry; conversation history; file attachments and project context; context retrieval/memory controls; approved tools, research and GitHub integration; multi-step plans and progress; safe terminal/filesystem execution through permissioned boundaries; approvals for consequential actions; activity details and an accessible stop action.

The Agent must use the same model and runtime services as the other workspaces. Do not call it a working local chat interface until a real adapter is connected and tested. Do not replace honest placeholders with fake controls.

## 15. Desktop experience

Model workflow:
1. Choose/import a model.
2. Inspect it.
3. Review the plain-language hardware feasibility result.
4. Accept the recommended profile or open advanced settings.
5. Adjust context, resource budgets or supported placement options.
6. Start the model.
7. See truthful Ready/Generating status and compact live resource information.
8. Open diagnostics or tune a profile when needed.
9. Save, compare, stop, unload or restart.

Keep default screens uncluttered. Explain specialist terms. Put advanced settings, full telemetry and experiment details behind progressive disclosure. No permanently open metrics wall, fake progress or fake controls. The three primary destinations remain clear. Use a polished, colourful, spacious design with accessible contrast, keyboard navigation, visible focus, scalable text, light/dark themes and restrained motion. Keep stop controls prominent.

## 16. Safety, privacy and Windows-first constraints

- Windows 11 is primary; core workflows must not require Linux/WSL.
- Prefer free, open-source, maintained and pinned dependencies.
- No mandatory paid API, cloud inference, subscription or automatic spending.
- Never request, log, print, commit or upload API-key contents.
- Keep model paths, prompts, private project files and diagnostics private by default.
- Original checkpoints are immutable; transformations create separate outputs.
- Static inspection never executes repository code or renders untrusted templates.
- Runtime processes are cancellable, bounded and observable.
- Apply explicit CPU/RAM/VRAM/storage limits and preserve Windows/foreground headroom.
- Prevent uncontrolled paging, memory thrashing and endless cold storage reads.
- Do not destructively move, overwrite or transform files without clear intent, safe destination and rollback.
- Explain administrator requirements and system-level changes first; normal user permissions are preferred.
- Redact secrets and unnecessary private data from logs and diagnostic bundles.

## 17. Evaluation and proof

### Model/runtime evaluation

Compare baseline settings with recommended and manually tuned profiles. Control model revision, prompt, context, output length, sampling, backend version, hardware state and warm/cold cache condition. Repeat runs and report median and variability.

Measure load time, time to first token, prompt processing, sustained generation, RAM, VRAM, CPU, disk reads, bytes transferred, cache behaviour and output quality. Test whether placement, caching, prefetch and scheduling provide sustained benefit without changing model semantics or causing thrashing. Measure telemetry/scheduler overhead. Record each execution manifest and hardware snapshot.

### Capability evaluation

Preserve the four remaining user-established categories:
1. Multi-file feature development.
2. Runtime debugging using actual failures and logs.
3. Safe modification of an interconnected existing codebase.
4. Three.js/game development.

The A* pathfinding evaluation is already complete; do not repeat it as a prerequisite. Preserve Reading List Manager regressions: uninitialized collection; UUID regenerated during deserialization; incorrect JSON nesting; strings supplied where enum values are expected; tests expecting output files that were never created.

Compare raw model, basic tool loop and complete ECLIPSE under the same tasks, environment, prompt/settings and acceptance tests. Track first-try success, success after repair, acceptance pass rate, regressions, unsupported completion claims, tool calls/retries, elapsed time, context use and resource use.

## 18. Development sequence and inference acceptance gates

Preserve both canonical phase maps. The original Master Plan Phase 0–10 and the later integrated Phase 0–11 roadmap are related but are not interchangeable.

The integrated work progresses through historical foundation/repository control; shared Core and three-workspace shell; static Model Intelligence Laboratory; hardware feasibility and reversible preparation; first real inference runtime and registry; Capability System; Obsidian/memory/skills; advanced reasoning and benchmarks; fast-path inference and predictive memory management; advanced compression/runtime intelligence/optional NECS; and complete desktop/release.

A runtime milestone is not complete merely because a child process starts. Require evidence for:

1. Feasibility based on the selected model and actual host resources.
2. Reproducible profile/manifest with supported settings.
3. Backend-confirmed launch and ready state.
4. Correct real prompt/response behaviour and safe stop/error paths.
5. Actual RAM/VRAM/resource accounting compared with planned budgets.
6. Requested context evidence or an explicit unverified status; separate KV estimates from observed allocation.
7. Working start, stop, unload, restart and profile save/restore.
8. Actual supported CPU/GPU/memory placement and measured results.
9. Repeatable latency and sustained throughput benchmarks.
10. Recovery from failed launch, timeout, crash and resource exhaustion without false ready state or orphan processes.
11. Original weights unchanged and Windows headroom respected.
12. User-side validation for hardware-specific claims.

## 19. Current implementation boundary

This specification describes the intended complete product, not a claim that it already exists.

The repository currently contains bounded static GGUF, Safetensors and Hugging Face-folder inspection; an evidence-labelled Model Atlas and CLI; a Windows-first PySide6 desktop shell with three destinations; Model Intelligence integration with the Atlas; a Windows x64 packaged build; and user-reported inspection of one real GGUF on Windows.

The repository has not yet demonstrated a complete RAM/VRAM/KV feasibility planner; preparation/transformation workflows; a real inference adapter managed by the app; automatic device-placement planning and verified layer/weight/expert placement; integrated start/stop/unload/restart controls; editable saved execution profiles; runtime resource accounting, context allocation validation or telemetry; dynamic weight/KV/expert movement; the implemented Capability System; Obsidian integration; or a working Agent chat adapter.

These are future implementation gates. Keep them explicitly pending until code, tests, runtime evidence and, where necessary, user-side Windows validation demonstrate them.

## 20. Canonical interpretation

- **Model Atlas:** tells ECLIPSE what the model is and what the files declare.
- **Feasibility Planner:** estimates what is possible on the current hardware, with evidence and assumptions.
- **Execution Planner:** builds a supported arrangement for weights, layers, context/KV cache and resources.
- **High-Speed Inference Engine:** actually runs the model through a compatible backend.
- **Resource Manager:** lets the user monitor, adjust, save, stop, unload and restart the runtime.
- **Capability System:** helps the model plan, research, use tools, verify work and retain proven corrections.
- **ECLIPSE Agent:** brings shared model and system capabilities together in the everyday chat workspace.

The product is complete only when these pieces work together as one coherent Windows application. Model inspection is the beginning of the model lifecycle, not its final destination.