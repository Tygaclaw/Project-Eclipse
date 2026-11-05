# ECLIPSE Decision Log

## D-001 — Greenfield implementation

**Decision:** Build a new ECLIPSE software implementation in a separate repository.

**Reason:** The user explicitly superseded the historical `START HERE` instruction to continue `Tygaclaw/Project-Eclipse`.

**Consequence:** Old code is read-only reference. Preserve research, docs, model setup, tests and lessons; do not overwrite the historical repo.

## D-002 — One unified application

**Decision:** ECLIPSE is one product combining model intelligence/inference engineering, capability amplification/knowledge, and a full conversational agent.

**Reason:** The user explicitly wants the original model dissection/transformation design and the newer intelligence system united, plus a complete ChatGPT/Claude-like everyday AI experience.

## D-003 — Three primary user-facing workspaces

**Decision:** Main navigation has three destinations: (1) Model Intelligence & Inference Platform, (2) Capability Amplification & Knowledge System, (3) ECLIPSE Agent.

**Reason:** The original unified handoff explicitly describes two connected workstreams (Qwen capability amplification; model intelligence/inference platform). The user requires a third Agent workspace. These are workspaces within one app, not independent products.

## D-004 — Preserve five internal technical subsystems

**Decision:** Retain the original Master Plan's five major subsystems: Model Intelligence Laboratory; Model Preparation and Optimization; High-Speed Inference Engine; Intelligence Preservation and Recovery; ECLIPSE Desktop and Resource Manager.

**Reason:** These are explicitly listed in the original v3.0 plan. They fit under the two engineering workspaces and shared core; they must not be dropped because the top-level UI has three destinations.

## D-005 — Static-first model inspection

**Decision:** Model Atlas and initial feasibility must work without local inference, full checkpoint loading, runtime hooks or live expert observation.

**Reason:** The target model may be larger than local RAM/VRAM. Offline inspection is a foundational purpose of ECLIPSE.

## D-006 — Original nine phases preserved

**Decision:** Preserve Master Plan Phase 1–9 as the original nine numbered core stages, bracketed by Phase 0 foundation and Phase 10 desktop. Also preserve the later integrated Phase 0–11 roadmap as a separate delivery roadmap.

**Reason:** The source documents contain both sequences. They are related but not identical.

## D-007 — Predictive loading is a research feature

**Decision:** Investigate predicting future use of existing expert/weight blocks and prefetching them. The actual model router remains authoritative.

**Reason:** This reflects the original user idea while preventing approximate predictions from silently substituting model decisions.

## D-008 — NECS is experimental

**Decision:** Neural Error-Correction Sidecar remains optional research and is not a core dependency unless held-out tests prove benefit.

**Reason:** The source Master Plan labels it experimental and warns about quality/speed trade-offs.

## D-009 — Beginner-friendly colourful UX

**Decision:** No crowded dashboard. Use simple main navigation, uncluttered screens, purposeful colour, clear hierarchy, progressive disclosure and plain language.

**Reason:** The user explicitly rejected the earlier busy preview and wants a colourful, lively desktop experience that beginners can understand.

## D-010 — GitHub as permanent source of truth

**Decision:** All source, docs, decisions, phases, test evidence and continuation state live in a new private GitHub repository. Do not assume connection; verify it in the active ChatGPT session.

## D-011 — Local validation must be evidence-gated

**Decision:** If ChatGPT cannot test a Windows/GPU/local integration, it provides exact steps and waits for actual evidence before declaring that gate complete.
