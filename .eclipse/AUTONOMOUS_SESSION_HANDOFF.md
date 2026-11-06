# Autonomous Session Handoff

**Purpose:** durable, sanitized recovery note for model/provider switches and GitHub Actions runner restarts.

## Current state

- Status: BOOTSTRAP
- Active backlog item: AUTO-01 — autonomous run controller and workflow.
- Base branch: main
- Session ID: created by the autonomous controller at runtime and recorded in the runner log only; never place provider credentials here.
- Last verified checkpoint: main includes merged PRs #5, #6, #7, #10 and #11.

## Current product reality

Implemented on main: bounded GGUF/Safetensors/Hugging Face inspectors, tokenizer/chat-template inventory, Model Atlas, Windows desktop shell, host discovery and static feasibility estimates, ranked six-provider/12-model free OpenCode pool.

Not yet implemented as a working integrated product: actual ECLIPSE-managed inference lifecycle, execution placement/profiles/telemetry, Capability Amplification tools/planner/sandbox/verification/recovery, Obsidian integration, real Agent chat/runtime, and full three-workspace integration.

## Recovery rules

1. Read this file, `AUTONOMOUS_BACKLOG.md`, `docs/AUTONOMOUS_ENGINEERING_PROTOCOL.md`, `STATUS.md` and `CONTINUATION.md`.
2. Inspect `git status`, `git log`, open PRs and the active CI evidence before doing anything.
3. Do not redo merged or verified work.
4. If the native OpenCode session still exists, continue its exact session ID and task using `opencode run --session <id> --model <next-approved-route>`.
5. If the runner/session no longer exists, reconstruct from this file, the merged commits, current branch diff, backlog status and validation logs. Do not claim that a new session is the same in-memory context.
6. Never include keys, raw environment values, private prompts or full sensitive logs in this note.

## Latest milestone result

Update this section after each milestone with changed files, commit/PR, selected model(s), retries/failovers, checks and the next acceptance step.

### Audit and repair — 2026-11-06 (setup engineer session)

- Audited PR #12: ranked routing, initial attempt + five retries, immediate failover on auth/quota/rate-limit/model errors, same-session continuation, credential scrubbing, protected-path draft policy and CI-repair resume are all present and unit-tested.
- Fixed: a context-length compaction call wrongly consumed one of the six calls for a model (the old `attempt -= 1` inside a `for` loop had no effect). Added a regression test that fails on the old code.
- Added: a test that fails CI if the controller's route order ever differs from the ranked table in `docs/FREE_MODEL_PROVIDER_POOL.md`.
- Still unproven: no live Actions run, live provider smoke test or real failover has happened yet. Activation requires the owner to merge PR #12 (it changes protected automation files, so it must stay draft until reviewed) and dispatch `ECLIPSE autonomous engineering` once.

