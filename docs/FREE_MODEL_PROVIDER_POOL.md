# ECLIPSE — six-provider free model pool

**Scope:** ECLIPSE's GitHub Actions OpenCode agent is configured for exactly six API providers. No other provider configuration is permitted in this pool.

**Providers:** Dahl, Google Gemini API, Groq, OpenRouter, Token Harbor and Z.AI.

**Models:** two choices per provider, 12 configured routes total. These are configured routes, not a claim that every key or upstream model has passed a live inference test.

## Model and command list

| Provider | Comment command | OpenCode model ID | Intended role |
|---|---|---|---|
| Token Harbor | `/oc` | `tokenharbor/deepseek-v4.1-flash:free` | Default coding and agent route |
| Token Harbor | `/oc-mimo` | `tokenharbor/mimo-v2.6-flash:free` | Alternate general/multimodal model |
| Dahl | `/oc-dahl` | `dahl/MiniMaxAI/MiniMax-M2.7` | Primary Dahl agent model |
| Dahl | `/oc-dahl-deepseek` | `dahl/deepseek-ai/DeepSeek-V4-Flash-0731` | Fast coding/reasoning alternative |
| Google Gemini | `/oc-gemini` | `google/gemini-3.8-flash` | Primary Gemini coding/agent model |
| Google Gemini | `/oc-gemini37` | `google/gemini-3.7-flash` | Previous stable Flash alternative |
| Groq | `/oc-groq` | `groq/openai/gpt-oss-120b` | Larger reasoning/coding option |
| Groq | `/oc-groq-small` | `groq/openai/gpt-oss-20b` | Faster, lighter alternative |
| OpenRouter | `/oc-openrouter` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | Long-context agent/reasoning model |
| OpenRouter | `/oc-openrouter-lightning` | `openrouter/nvidia/nemotron-3.5-lightning:free` | Smaller, faster agentic model |
| Z.AI | `/oc-zai` | `zai/glm-4.7-flash` | Primary GLM coding/agent model |
| Z.AI | `/oc-zai-45` | `zai/glm-4.5-flash` | Alternate free Flash model |

The model names above are exact IDs, including capitalization and the `:free` suffix where applicable. The Dahl model catalogue can rotate; refresh `GET https://inference.dahl.global/v1/models` before treating a Dahl route failure as an OpenCode configuration bug.

## GitHub Actions secrets

The workflow reads only these six repository secrets. Their names match the repository settings shown by the owner.

| Secret | OpenCode provider | API base URL |
|---|---|---|
| `DAHL_API_KEY` | `dahl` | `https://inference.dahl.global/v1` |
| `GEMINI_API_KEY` | `google` | Google Gemini API |
| `GROQ_API_KEY` | `groq` | `https://api.groq.com/openai/v1` (built-in provider) |
| `OPENROUTER_API_KEY` | `openrouter` | OpenRouter (built-in provider) |
| `TOKENHARBOR_API_KEY` | `tokenharbor` | `https://tokenharbor.ai/v1` |
| `ZAI_API_KEY` | `zai` | `https://api.z.ai/api/paas/v4` |

Do not rename these secrets or add provider aliases without updating both `opencode.json` and `.github/workflows/opencode.yml`. The selector checks that the chosen secret is present but never prints its value. The OpenCode action receives only the selected provider's key.

## Free-access and billing boundaries

### Dahl

Dahl advertises a **100-million-token signup grant**, not an unlimited recurring free API tier. New API keys start with zero allocated tokens; tokens must be moved from the account pool to the key. The grant expires after seven days without a request. Dahl documents prepaid inference at $0.02 per million tokens after free tokens are exhausted. It has no recurring subscription charges, but a user-initiated top-up is paid.

For this repository: use only the signup grant, do not top up, and expect an exhausted/empty key to fail rather than silently become free. The workflow does not initiate purchases or top-ups.

### Google Gemini API

Use the Google AI Studio free tier only. Gemini free quotas vary by model, project and current Google policy. Do not enable billing or move the project to a paid tier for this agent. When free quota is exhausted, the route should stop until the quota resets.

Google's free-tier data handling differs from its paid tier. Do not include secrets, credentials or confidential information in prompts.

### Groq

Keep the account on Groq's Free plan. The configured GPT-OSS models support tool use. Free-plan rate limits are model-specific and may change; the Groq console's Limits page is authoritative. Do not upgrade to a paid Developer plan or enable paid usage. When the free allowance is exhausted, treat a rate-limit response as a provider cooldown, not permission to spend money.

### OpenRouter

Both configured models use explicit `:free` model IDs. They are zero-price endpoints but rate-limited; availability can change. Free-model request limits are shared account-level limits, not multiplied by having two models. Do not remove `:free`, select a paid variant, or configure a paid fallback.

The two selected free endpoints are operated upstream by NVIDIA. OpenRouter's model pages disclose that NVIDIA may log free-endpoint sessions for product improvement. Do not send credentials, personal data or confidential source material through these routes.

### Token Harbor

Only explicit `:free` model IDs are configured. Token Harbor documents a value-based free allowance over a rolling seven-day period; free routes stop accepting new requests when the allowance is exhausted. The free variants are not supposed to draw from a paid wallet. Do not top up or replace the model IDs with non-`:free` variants.

### Z.AI

Only GLM-4.7-Flash and GLM-4.5-Flash are configured. Z.AI's public pricing table currently lists both at $0 input/output. The exact free request/concurrency limits are account-specific or may change; check the Z.AI console. Do not enable paid models such as GLM-5.3, GLM-4.7-FlashX or the standard GLM-4.7 model.

## Implementation and safety

- The workflow contains exactly these six providers and 12 explicit model commands.
- The default `/oc` route remains Token Harbor DeepSeek V4.1 Flash Free.
- The workflow keeps the 350-minute GitHub Actions timeout.
- `opencode.json` retains `permission.external_directory = deny` to prevent unattended permission prompts outside the repository.
- Only the selected provider's API key is passed to the OpenCode action.
- No provider key values are stored in source control, comments, logs or this document.
- No paid model routes, paid fallback, provider auto-upgrade or automatic purchase path is configured.
- Provider selection is manual. **Automatic cross-provider failover, cooldown memory and progress-safe resume are not implemented yet.**
- The configuration and CI validator do not prove live API access. A deliberate smoke test is required for each provider; tool-call success should be checked separately from simple text completion.
- Treat remote model responses as untrusted. Review generated diffs and test results before merging code.

## Primary provider documentation

- [Dahl OpenCode setup](https://inference.dahl.global/docs/opencode)
- [Dahl model catalogue](https://inference.dahl.global/docs/models)
- [Dahl tokens and keys](https://inference.dahl.global/docs/tokens)
- [Dahl pricing](https://inference.dahl.global/pricing)
- [Google Gemini model catalogue](https://ai.google.dev/gemini-api/docs/models)
- [Google Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Groq supported models](https://console.groq.com/docs/models)
- [Groq tool-use support](https://console.groq.com/docs/tool-use/overview)
- [Groq free-plan rate limits](https://console.groq.com/docs/rate-limits)
- [OpenRouter free model catalogue](https://openrouter.ai/collections/free-models)
- [OpenRouter Nemotron 3 Ultra Free](https://openrouter.ai/nvidia/nemotron-3-ultra-550b-a55b:free)
- [OpenRouter Nemotron 3.5 Lightning Free](https://openrouter.ai/nvidia/nemotron-3.5-lightning:free)
- [Token Harbor free model catalogue](https://tokenharbor.ai/models?category=free)
- [Token Harbor free-route FAQ](https://tokenharbor.ai/faq)
- [Z.AI model pricing](https://docs.z.ai/guides/overview/pricing)
- [OpenCode provider configuration](https://docs.opencode.ai/docs/providers/)
