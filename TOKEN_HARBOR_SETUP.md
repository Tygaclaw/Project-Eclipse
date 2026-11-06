# Token Harbor free-model setup for ECLIPSE

**Current default:** Token Harbor deepseek-v4.1-flash:free through OpenCode.
**Manual fallback:** mimo-v2.6-flash:free using the /oc-mimo comment command.
**Paid routes:** prohibited for this project.

## GitHub Actions secret

Add a repository Actions secret named exactly:

TOKENHARBOR_API_KEY

The value is the user's Token Harbor API key. Never place the key in this repository, an issue comment, a workflow file, or a log.

GitHub path:
Repository → Settings → Secrets and variables → Actions → New repository secret.

## Free route requirements

- Use only model IDs ending in :free.
- Free routes never deduct from the Token Harbor wallet balance.
- Free model access uses a value-based allowance over a personal rolling seven-day period. The first free request starts that period. The live dashboard shows the allowance used.
- Free accounts are subject to 60 API requests per minute and 1,800 per hour per account. Token Harbor says there is no separate concurrent-request cap.
- If the free allowance is exhausted, free-route requests stop until the period refreshes; the paid base model must not be substituted.
- Free routes require the user's dashboard opt-in. Free-route prompts and responses may be retained and reviewed by Token Harbor and may be processed under upstream providers' own policies. Do not send secrets, private credentials, personal data, or confidential material.

## OpenCode configuration

opencode.json defines the Token Harbor OpenAI-compatible endpoint and reads the key from the TOKENHARBOR_API_KEY environment variable. Context is capped at 131,072 tokens and output at 32,768 tokens to keep agent requests bounded.

## Start commands

On Issue #2 or another repository issue, an owner can comment:

- /oc GO — start DeepSeek V4.1 Flash Free.
- /oc-mimo GO — manually use MiMo V2.6 Flash Free if the DeepSeek free route is unavailable.

The GitHub monitor checks workflow state only. It deliberately makes no model API probes, so monitoring does not consume the free allowance.

## Recovery requirements

The coding agent must work in small, independently testable milestones, update STATUS.md and CONTINUATION.md, and preserve verified work in a reviewable GitHub pull request before the Actions job reaches its timeout. A failed or exhausted free route must pause without invoking a paid route.
