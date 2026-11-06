# ECLIPSE — six-provider free model pool

**Scope:** ECLIPSE's GitHub Actions OpenCode agent is configured for exactly six API providers. No other provider configuration is permitted in this pool.

**Providers:** Dahl, Google Gemini API, Groq, OpenRouter, Token Harbor and Z.AI.

**Models:** two choices per provider, 12 configured routes total. These are configured routes, not a claim that every key or upstream model has passed a live inference test.

## Ranked model and command list

The global rank is based on ECLIPSE-relevant published coding-agent benchmarks, with explicit confidence caveats. The complete score-by-score research is in [`docs/ECLIPSE_AGENT_MODEL_RANKING_2026-11-06.md`](ECLIPSE_AGENT_MODEL_RANKING_2026-11-06.md).

| Rank | Provider | Comment command | OpenCode model ID | Intended role |
|---:|---|---|---|---|
| **1** | Token Harbor | `/oc` (default) | `tokenharbor/deepseek-v4.1-flash:free` | Primary coding, repository engineering and terminal-agent route |
| **2** | Google Gemini | `/oc-gemini` | `google/gemini-3.8-flash` | First alternate; long-horizon coding and agent work |
| **3** | Token Harbor | `/oc-mimo` | `tokenharbor/mimo-v2.6-flash:free` | Strong coding/general agent and multimodal, visual-development alternative |
| **4** | Google Gemini | `/oc-gemini37` | `google/gemini-3.7-flash` | Previous-generation Flash fallback |
| **5** | Dahl | `/oc-dahl-deepseek` | `dahl/deepseek-ai/DeepSeek-V4-Flash-0731` | Strong coding and terminal alternative; dated model ID needs live revision confirmation |
| **6** | Groq | `/oc-groq-qwen` | `groq/qwen/qwen3.8-27b` | Coding agent with parallel tool calls |
| **7** | OpenRouter | `/oc-openrouter` | `openrouter/cohere/north-mini-code:free` | OpenCode-oriented agentic coding specialist |
| **8** | Z.AI | `/oc-zai` | `zai/glm-4.7-flash` | Lightweight coding and tool-use fallback |
| **9** | Dahl | `/oc-dahl` | `dahl/MiniMaxAI/MiniMax-M2.7` | Complex project-engineering and agent-team alternative |
| **10** | OpenRouter | `/oc-openrouter-ultra` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | Long-context reasoning, planning and review specialist |
| **11** | Groq | `/oc-groq` | `groq/openai/gpt-oss-120b` | Secondary reasoning/tool-use route |
| **12** | Z.AI | `/oc-zai-45` | `zai/glm-4.5-flash` | Experimental fallback; exact-model benchmark evidence is limited |

The order above is the global ranking. The `opencode.json` provider groups and the models inside each provider are also arranged best-first. The workflow's selector keeps suffix-specific commands ahead of broader commands where needed to prevent a command such as `/oc-gemini37` from being mistaken for `/oc-gemini`; that syntax ordering is not the benchmark ranking.

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

The selected models are `gemini-3.8-flash` and `gemini-3.7-flash`. These are not paid-only models: Google's current official pricing page explicitly lists both at $0 input/output on the Gemini API Free tier. Google positions 3.8 Flash for long-horizon software engineering and autonomous agents, and 3.7 Flash for coding, agentic tool use and reliable multi-step execution. That makes them a more appropriate pair for ECLIPSE than picking a random lightweight model solely because it has a Flash-Lite label.

Use the Google AI Studio free tier only. Free access is limited to eligible models and quotas vary by model and project. Do not enable billing or move this project to a paid tier. When free quota is exhausted, the route should stop until the quota resets. Google states that free-tier content may be used to improve its products, so do not include secrets, credentials or confidential information in prompts.

### Groq

The selected pair is deliberately `openai/gpt-oss-120b` plus `qwen/qwen3.8-27b`, not GPT-OSS 20B. Groq's official Free-plan table lists both at 30 RPM, 1,000 RPD, 8K TPM and 200K TPD. Groq's tool-use documentation confirms Qwen 3.8 27B supports parallel tool calls; GPT-OSS supports tool use but not parallel tool calls. This is a more useful pair for a coding agent that may need to call several repository tools. The account Limits page is authoritative and quotas can change.

Keep the account on Groq's Free plan. Both selected model IDs appear in Groq's published Free-plan rate-limit table. Limits may change; the Groq console's Limits page is authoritative. Do not upgrade to a paid Developer plan or enable paid usage. When the free allowance is exhausted, treat a rate-limit response as a provider cooldown, not permission to spend money.

### OpenRouter

The selected pair is `cohere/north-mini-code:free` plus `nvidia/nemotron-3-ultra-550b-a55b:free`. North Mini Code is explicitly designed for agentic coding and terminal tasks and has been trained to generalize across coding harnesses including OpenCode and SWE-Agent. OpenRouter documents 256K context, up to 64K output and tool calling. Nemotron 3 Ultra is the complementary long-context reasoning/planning model with 1M context and tool calling. Both are marked $0. OpenRouter free endpoints are rate-limited and the free pool may change; do not assume free quota is multiplied by the number of model IDs. The free model rankings on OpenRouter measure usage, not model quality.

Both configured models use explicit `:free` model IDs. They are zero-price endpoints but rate-limited; availability can change. Free-model request limits are shared account-level limits, not multiplied by having two models. Do not remove `:free`, select a paid variant, or configure a paid fallback.

The Nemotron Ultra free endpoint is operated upstream by NVIDIA. OpenRouter's model page discloses that NVIDIA may log free-endpoint sessions for product improvement. The Cohere North Mini Code route is a separate upstream model. Do not send credentials, personal data or confidential source material through the OpenRouter free pool.

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
- [Gemini 3.8 Flash Free-tier pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini 3.7 Flash Free-tier pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Google Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Groq supported models](https://console.groq.com/docs/models)
- [Groq tool-use support](https://console.groq.com/docs/tool-use/overview)
- [Groq model rate limits](https://console.groq.com/docs/rate-limits)
- [Groq free-plan rate limits](https://console.groq.com/docs/rate-limits)
- [OpenRouter free model catalogue](https://openrouter.ai/collections/free-models)
- [OpenRouter Nemotron 3 Ultra Free](https://openrouter.ai/nvidia/nemotron-3-ultra-550b-a55b:free)
- [OpenRouter Cohere North Mini Code Free](https://openrouter.ai/cohere/north-mini-code:free)
- [OpenRouter Nemotron 3 Ultra Free](https://openrouter.ai/nvidia/nemotron-3-ultra-550b-a55b:free)
- [Token Harbor free model catalogue](https://tokenharbor.ai/models?category=free)
- [Token Harbor free-route FAQ](https://tokenharbor.ai/faq)
- [Z.AI model pricing](https://docs.z.ai/guides/overview/pricing)
- [OpenCode provider configuration](https://docs.opencode.ai/docs/providers/)
