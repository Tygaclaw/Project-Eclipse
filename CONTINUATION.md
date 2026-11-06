# ECLIPSE Continuation Record

## Current checkpoint

- Repository: `Tygaclaw/Project-Eclipse`.
- Default branch: `main`.
- Audited main head when this record was rewritten: `876034bc42566b79dcf144867664b443317a1a95`.
- Current autonomous bootstrap branch: `feature/autonomous-engineering-engine-2026-11-06`.
- Mainline PRs #5, #6, #7, #10 and #11 are merged. PRs #8 and #9 are obsolete, closed and superseded.
- The existing product foundation includes static model inspection/Atlas, tokenizer/chat-template intelligence, static hardware feasibility, and the three-workspace Windows desktop shell.

## Product truth

The Model Intelligence workspace has genuine static inspection and feasibility foundations. It does not yet have a managed inference lifecycle, executable placement planner, runtime profiles or full telemetry. Capability Amplification, Obsidian and the ECLIPSE Agent remain future implementation work beyond the existing honest placeholder screens. Do not report the product finished until the integrated backlog and release gates are satisfied.

## Autonomous controller bootstrap

The current feature branch adds:

- `docs/AUTONOMOUS_ENGINEERING_PROTOCOL.md`
- `AUTONOMOUS_BACKLOG.md`
- `.eclipse/AUTONOMOUS_SESSION_HANDOFF.md`
- `scripts/eclipse_autonomous.py`
- `tests/test_autonomous_runner.py`
- `.github/workflows/eclipse-autonomous.yml`
- updated root execution/status/readme records.

The controller uses the 12-model ranked free pool. Transient model errors receive one initial attempt plus up to five retries with backoff. Quota/auth/provider-wide failures skip that provider immediately. Model retries and model switches reuse the same OpenCode session ID when available. If no session was created before a provider error, the next route starts the same task from the same prompt/checkpoint.

The OpenCode child receives only the selected provider credential. GitHub credentials remain in the parent controller; the model agent is denied commit/push/GitHub CLI write commands. The controller checks the worktree, commits and pushes, and opens a PR. Safe product PRs require Windows Python 3.11–3.14 and Windows Qt/PyInstaller checks before automatic squash-merge. Changes to workflow, credential, permission, controller and security policy files remain draft for owner review.

The workflow has manual dispatch, main-branch push and six-hour scheduled entry points, with a concurrency group and one-open-autonomous-PR guard. A successful safe merge queues the next run. An open draft/protected PR intentionally pauses further work until owner review; a failed CI/safety gate is not merged.

**Important:** This bootstrap branch is not yet on main and its workflow has not yet had a live Actions run. CI and first-run behavior must be verified after the bootstrap PR is opened. Do not describe automation as active until it is merged and the first run succeeds.

## Next autonomous work order

Use `AUTONOMOUS_BACKLOG.md` as the canonical queue. After the bootstrap controller is merged, continue with:
1. Finish live provider smoke tests and failover/recovery acceptance.
2. Build a real inference backend adapter compatible with the existing Windows/Vulkan setup, preserving the known-good configuration.
3. Implement true load/generate/stop/unload lifecycle, execution profiles, actual runtime allocation and telemetry.
4. Implement reversible preparation and integrity/rollback.
5. Build the shared Capability Core: planning, research/context, tools, sandbox, verification, recovery, loop detection, corrections and skills.
6. Integrate Obsidian with scoped retrieval and approval.
7. Implement the full Agent chat/runtime, history, attachments, memory, tools, approvals and Stop.
8. Complete three-workspace integration, UX and the remaining four evaluations.
9. Complete release and final bundled Windows 11/Vulkan/Obsidian owner validation.

## Model order and free-only safety

The global order is in `docs/FREE_MODEL_PROVIDER_POOL.md`; detailed public benchmark evidence is in `docs/ECLIPSE_AGENT_MODEL_RANKING_2026-11-06.md`. The ranking is provisional until routes and identical ECLIPSE tasks are tested live. No paid route, top-up, account rotation or unapproved provider is allowed.

## Do not repeat

- General Windows/hardware audit.
- Qwen local installation or API-key recreation.
- The already completed A* evaluation.

Never ask for, print or commit API-key values. Preserve the original model files and the known-good local setup. Continue independent engineering while a specific owner-only local gate is waiting.

## Autonomous bootstrap CI checkpoint — 6 November 2026

PR #12: https://github.com/Tygaclaw/Project-Eclipse/pull/12  
Branch: `feature/autonomous-engineering-engine-2026-11-06`.

Verified head `44a463732448c6faa544620760eb725ab8944563`:
- Python checks run #42292375849 passed on Windows Python 3.11–3.14; each ran 210 tests with 11 optional-dependency skips.
- Windows desktop build run #42292375824 passed the full Qt/offscreen suite, PyInstaller build, packaged-backend smoke test, ZIP and artifact upload.
- Artifact `ECLIPSE-windows-x64`: 51,137,344 bytes.
- Retry/failover, same-session switching, context compaction, quota skip and credential-scrubbing behavior have mocked regression coverage.
- Actual live provider/tool-call smoke tests and an injected end-to-end CI-repair/resume exercise remain open.
- PR #12 remains an owner-review draft due protected workflow/controller/security changes; do not merge or activate without that review. After merge, verify the first live Actions run before describing automation as active.

The autonomous backlog now marks AUTO-01/02/03 in progress rather than complete, because operational acceptance is not yet proven.

