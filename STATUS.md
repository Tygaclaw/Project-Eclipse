# ECLIPSE Project Status

**Status:** `AUTONOMOUS_BOOTSTRAP_IMPLEMENTED_ON_FEATURE_BRANCH — OWNER_REVIEW_PENDING`  
**Last updated:** 2026-11-06  
**Current main head audited:** `876034bc42566b79dcf144867664b443317a1a95`

## Mainline history — verified

The following milestones are already merged to `main`:

- PR #1 — project handoff, initial bounded GGUF inspector and repository baseline.
- PR #4 — Windows-first three-workspace PySide6 shell, Model Atlas UI and packaging.
- PR #5 — bounded static tokenizer and chat-template intelligence.
- PR #6 — complete product/runtime vision specification.
- PR #7 — OpenCode headless external-directory deny safeguard.
- PR #10 — clean mainline hardware discovery and static RAM/VRAM/KV feasibility planner.
- PR #11 — six approved free API providers, 12 ranked model routes, ranking research and best-first OpenCode configuration.

The old stacked PR #8 (hardware increment) and PR #9 (free provider pool) are closed unmerged and superseded by PR #10 and PR #11. Do not merge or revive those old branches.

## What is implemented on main

- Bounded, read-only GGUF v2/v3 inspection and versioned GGML storage derivation.
- Bounded Safetensors header/tensor-index inspection.
- Hugging Face folder/shard-index inspection.
- Bounded tokenizer/chat-template metadata and inert template previews.
- Evidence-labelled Model Atlas and CLI.
- Windows host snapshot including OS/CPU/RAM and NVIDIA data when available.
- Static architecture-aware weight/KV feasibility estimates with RAM/VRAM reserves and SSD shown separately.
- PySide6 desktop shell with exactly three primary workspaces; Model Intelligence is connected to the Atlas.
- Windows x64 PyInstaller packaging and CI.
- Ranked six-provider/12-route free OpenCode pool and benchmark report.

A static estimate is not an executable placement plan or proof of inference. The Capability and Agent screens are not yet full implementations.

## Autonomous bootstrap — feature branch only

Branch: `feature/autonomous-engineering-engine-2026-11-06`  
Base: current `main` at the time the branch was created.

Implemented in this branch:
- `docs/AUTONOMOUS_ENGINEERING_PROTOCOL.md` — operating contract for autonomous milestones, retry/failover, same-session continuation, safety and merge gates.
- `AUTONOMOUS_BACKLOG.md` — prioritized end-to-end implementation queue and evidence requirements.
- `.eclipse/AUTONOMOUS_SESSION_HANDOFF.md` — durable sanitized context for runner/session recovery.
- `scripts/eclipse_autonomous.py` — parent controller that selects ranked free routes, retries transient failures (initial + five retries), skips provider-wide quota/auth failures, reuses the same OpenCode session ID when available, runs local validation, scans changed files, creates a branch/PR and handles CI/merge/continuation.
- `tests/test_autonomous_runner.py` — retry classification, same-session failover and credential-isolation tests.
- `.github/workflows/eclipse-autonomous.yml` — manual, main-push and six-hour scheduled entry points, serialized with concurrency protection.
- Updated `DEEPSEEK_START_HERE.md`, `STATUS.md`, `CONTINUATION.md` and `README.md`.

**This controller is not yet active on main.** It changes protected workflow/security/controller paths, so its bootstrap PR must remain a draft for owner review even if CI passes. The first live run, provider credentials and end-to-end recovery still need validation.

## What is not yet complete as a working product

- Real ECLIPSE-managed model inference lifecycle and backend capability matrix.
- Executable CPU/GPU/hybrid placement and context/KV allocation verification.
- Reversible prepared variants and transformation lineage.
- Runtime profiles, actual telemetry and benchmarked performance.
- Capability Watchdog, planner, research/context service, permissioned tool registry and sandbox.
- Independent verification, recovery, loop detection, verified correction memory and reusable skills.
- Obsidian knowledge vault and approval workflow.
- Functional ECLIPSE Agent with chat, history, model switching, files, tools and Stop.
- Complete end-to-end integration of all three workspaces through one Core.
- Four remaining evaluations: multi-file development, runtime debugging, safe interconnected-code changes and Three.js/game development.
- Windows installer/update/uninstall/recovery and release compliance.

## User-only release gates

Do all independent development and GitHub-hosted Windows checks first. Then bundle only the remaining local checks into one clear Windows 11 validation run:
- verify the existing llama.cpp/Vulkan/Qwen connection without reinstalling or changing the known-good configuration;
- test real model load/generate/stop, actual hardware telemetry and resource recovery;
- validate the user's Obsidian vault integration;
- verify installation/update/uninstall on the target PC.

Keep these gates `WAITING_FOR_OWNER_VALIDATION` until real evidence exists. Do not ask the owner to repeat the completed A* challenge, general hardware audit, Qwen installation or API-key setup.

## Free & Safe Checklist

- [x] Six-provider, 12-model approved pool is configured on main.
- [x] Provider order is benchmark-based and free routes are explicit where required.
- [x] No paid model, paid fallback, top-up or automatic account rotation is permitted.
- [x] Static inspectors do not load or execute target model weights/code.
- [x] Original model checkpoints remain read-only.
- [x] Autonomous child receives only one selected provider key; controller GitHub token is not forwarded to it.
- [x] Autonomous runner cannot push or commit through its agent permissions; controller owns Git operations.
- [ ] Autonomous bootstrap PR reviewed/merged and first workflow run verified.
- [ ] Each API route passes live non-confidential text and tool-call smoke tests.
- [ ] Runtime, sandbox, Obsidian, Agent, security/dependency scans and release gates complete.
- [ ] License selection remains an owner decision; Qt/PySide6 LGPL packaging obligations must be addressed before redistribution.
