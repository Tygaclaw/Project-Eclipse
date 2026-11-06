# Free-model provider pool

**Purpose:** Keep the ECLIPSE GitHub Actions engineering agent usable when one free model route is unavailable, while preventing paid usage.

## Current configured routes

| Command | OpenCode model | Provider | State |
|---|---|---|---|
| `/oc` | `tokenharbor/deepseek-v4.1-flash:free` | Token Harbor | Existing default |
| `/oc-mimo` | `tokenharbor/mimo-v2.6-flash:free` | Token Harbor | Existing manual alternate |
| `/oc-openrouter` | `openrouter/cohere/north-mini-code:free` | OpenRouter | Added in this milestone |
| `/oc-openrouter-flint` | `openrouter/recursive/flint-v1.0:free` | OpenRouter | Added in this milestone |

The OpenRouter models are listed with explicit free-variant IDs. North Mini Code is a coding/agent-oriented model with tool calling, a 256K context and 64K maximum output. Flint is a coding-agent model with tool support and a 262K context. Their availability and upstream endpoints can change, so re-check the catalogue before changing or adding model IDs.

## Credentials

Store credentials only as GitHub Actions repository secrets:

- `TOKENHARBOR_API_KEY`
- `OPENROUTER_API_KEY`

The workflow passes them through environment variables. It checks that the selected provider key is present but never prints the value. Do not commit keys to `opencode.json`, source files, issue comments, artifacts or logs.

## Free-use boundaries

- OpenRouter free variants currently allow 20 requests per minute and 50 requests per day for accounts below the lifetime-credit threshold. Failed attempts count toward the daily request cap. Do not buy credits to increase the allowance.
- OpenRouter may retry another healthy upstream provider for the same model where its routing policy permits. That is upstream endpoint redundancy, not cross-model failover and not a bypass for the OpenRouter account's own free-tier cap.
- Token Harbor's free routes have their own value-based rolling seven-day allowance and free-account request limits. Never use paid routes, wallet credits or top-ups.
- Check provider/model data-retention terms before sending repository or user content. Never include secrets or private credentials in model prompts.

## Important implementation boundary

**This milestone only adds OpenRouter as a selectable independent provider and adds two selectable free coding models. It does not yet implement automatic cross-provider failover.**

OpenCode's GitHub Action requires one model selection for each run, and OpenCode's current retry behaviour is not a verified cross-model fallback chain. The next milestone must add an external, bounded coordinator that can:
1. classify provider failures without confusing them with code/test failures;
2. retry transient failures with capped backoff;
3. switch to another configured provider/model when appropriate;
4. remember cooldowns and rate-limit resets without storing secrets;
5. preserve the runner worktree and continuation notes between attempts;
6. stop before spending any money or entering an unbounded retry loop.

Test failover using mocked provider errors and workflow-level simulations before using real model requests. Real provider smoke tests consume free request allowance and should be deliberately limited.

## Source references

- OpenRouter free model catalogue: https://openrouter.ai/collections/free-models
- North Mini Code: https://openrouter.ai/cohere/north-mini-code
- Recursive Flint: https://openrouter.ai/recursive/flint-v1.0:free
- OpenRouter rate limits: https://openrouter.ai/docs/api/reference/limits
- OpenCode provider configuration: https://docs.opencode.ai/docs/providers/
- OpenCode GitHub Action: https://dev.opencode.ai/docs/github
