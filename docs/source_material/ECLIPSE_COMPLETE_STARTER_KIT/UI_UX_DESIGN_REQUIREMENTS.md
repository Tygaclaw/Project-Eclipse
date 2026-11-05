# ECLIPSE UI/UX and Visual Design Requirements

## 1. Product feel

ECLIPSE must feel like a polished modern AI desktop application: inviting, colourful, alive, calm and easy to learn. The last preview was rejected because too many controls, panels and metrics were visible at once. Do not reproduce that dashboard-heavy approach.

The app is powerful underneath and simple on the surface.

## 2. Three main destinations

Use a small, persistent primary navigation for:

1. **Model Intelligence** — the Model Intelligence & Inference Platform.
2. **Capability System** — the Capability Amplification & Knowledge System.
3. **Agent** — the full conversational AI experience.

Use the final names recovered and confirmed from the source docs and user's three-workspace direction. These are the main places users go; do not expose every internal subsystem as a top-level tab.

## 3. Default landing page

Default to Agent for an everyday AI experience unless usability testing supports a better onboarding choice. Agent layout should be familiar:

- Slim navigation and conversation list.
- One central conversation area.
- Clear model picker.
- Simple composer with attachment/action controls.
- Quiet progress/tool indicator.
- Optional expandable activity details.

No permanently open right-hand diagnostics panel. No wall of performance metrics. No more than the controls needed for the current action.

## 4. Visual language

Use a cohesive, purposeful palette. Suggested direction:

- Deep navy/blue or a soft neutral surface as the structural foundation.
- Cyan/teal for primary action and connected/active states.
- Violet for intelligence/research/model capabilities.
- Green for verified/success states.
- Warm amber for caution or attention.
- Red reserved for errors/danger.

Use accent colour selectively. The application should have more life and warmth than a sterile monochrome dashboard, but must not look childish or chaotic. Provide both light and dark themes and check contrast/accessibility.

Use generous spacing, legible typography, restrained shadows, consistent iconography, rounded but not excessive surfaces, and restrained motion. Respect reduced-motion settings.

## 5. Progressive disclosure

- Basic mode is the default.
- Advanced settings are hidden behind a clear `Advanced` affordance.
- Technical telemetry appears on demand or in a focused diagnostics view.
- Explain terms in plain English; show the technical term as optional detail.
- Do not present expert routing, tensor inventory, KV cache or quantization options before the user needs them.
- Use guided workflows for importing a model, inspecting it, checking compatibility, transforming it and launching it.
- Clearly identify measured values vs estimates.

## 6. Status and feedback

Use understandable states such as `Ready`, `Inspecting model`, `Checking compatibility`, `Preparing`, `Running`, `Needs attention`, `Waiting for approval`, `Failed`, `Verified`. Provide a way to view details, logs and evidence without placing all details in the default view.

Progress must be honest. Never animate fake metrics or fabricate progress.

## 7. Beginner workflows

Provide guided, reversible flows:

- Connect a local model.
- Import a model checkpoint for inspection.
- Understand whether it can run on this PC.
- Create a derived model variant.
- Select a model in Agent chat.
- Ask Agent to perform a project task.
- Approve/deny consequential tool actions.
- Review and restore a project/model snapshot.

The user must not need to know what GGUF, Safetensors, MoE, KV cache or quantization mean to complete basic tasks.

## 8. Usability acceptance

Test with a first-time user or structured beginner walkthrough. A new user should be able to identify the three destinations, start a chat, select a model, import a model for inspection, understand a feasibility result, and locate help without reading source code. Record confusing labels and fix them.
