# START HERE — ECLIPSE Continuation Handoff

**This is an existing project. Do not restart it.** The user has already completed the environment audit, established the local Qwen/API setup, recorded a working 256K Qwen3.5-9B baseline, completed the A* evaluation, selected Obsidian, and authorized full autonomous ECLIPSE implementation.

Read these files in this order:

1. `ECLIPSE_Unified_Implementation_Handoff.md` — full combined architecture, technical requirements, phases, test gates, privacy, and implementation instructions.
2. `ECLIPSE_Continuation_Ledger.md` — what is already done, what remains, and the hard constraints from prior conversations. **Use this to avoid repeating completed work.**
3. `ECLIPSE_Full_Up_to_Date_Master_Plan_Styled.pdf` — original ECLIPSE v3.0 model-engineering blueprint.
4. `I think we should aim much higher t.txt` — original Qwen3.5-9B capability-amplification discussion.

## Non-negotiable continuation instructions

- Continue the existing `Tygaclaw/Project-Eclipse` project/repository. Preserve its current work; do not assume it is empty.
- Do **not** repeat Phase 0 machine auditing or Phase 1 local Qwen connection/setup. They are completed/established.
- Reuse the existing Qwen3.5-9B Q4_K_M setup and its previously working 256K configuration. The temporary 8K diagnostic launch is not the preferred baseline. Never reveal the API-key value.
- The Model Intelligence Laboratory must inspect large models **without running them locally**. No inference, activation hooks, runtime tracing, or live expert-call observation may be prerequisites for static inspection or the Model Atlas.
- The A* pathfinding test is already complete. Finish the four remaining evaluation categories listed in the ledger.
- Implement the actual application and all required integrations/dependencies. Do not stop at a plan, mock-up, scaffold, or proof of concept.
- Repeatedly review, test, fix, and re-test. Keep `STATUS.md`, diagnostics, and evidence current.
- Keep API keys, private prompts, personal data, private logs, and local-only details out of public GitHub. Do not automate account rotation to evade provider usage limits.

Begin by reading the current project's `STATUS.md` and relevant source files to preserve existing work, then continue with the next uncompleted implementation milestone. **Do not send the user back through completed setup or investigations.**
