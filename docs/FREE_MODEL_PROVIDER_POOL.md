# Free-model provider pool

**Purpose:** Keep the ECLIPSE GitHub Actions engineering agent usable when one free model route is unavailable, while preventing paid usage.

Last reviewed: 6 November 2026. Provider free tiers change frequently; the limits below are the current documented boundaries, not availability guarantees.

## Configured model routes

| Command | OpenCode model | Provider | Context | Tool use | Credential |
|---|---|---|---:|---|---|
| `/oc` | `tokenharbor/deepseek-v4.1-flash:free` | Token Harbor | 128K configured | Provider dependent | `TOKENHARBOR_API_KEY` |
| `/oc-mimo` | `tokenharbor/mimo-v2.6-flash:free` | Token Harbor | 128K configured | Provider dependent | `TOKENHARBOR_API_KEY` |
| `/oc-openrouter` | `openrouter/cohere/north-mini-code:free` | OpenRouter | 256K | Yes | `OPENROUTER_API_KEY` |
| `/oc-openrouter-flint` | `openrouter/recursive/flint-v1.0:free` | OpenRouter | 262K | Yes | `OPENROUTER_API_KEY` |
| `/oc-openrouter-nemotron` | `openrouter/nvidia/nemotron-3.5-lightning:free` | OpenRouter | 1M | Yes | `OPENROUTER_API_KEY` |
| `/oc-openrouter-gemma` | `openrouter/google/gemma-4-26b-a4b-it:free` | OpenRouter | 262K | Yes | `OPENROUTER_API_KEY` |
| `/oc-openrouter-auto` | `openrouter/free` | OpenRouter | Router-selected | Filters for tool calling | `OPENROUTER_API_KEY` |
| `/oc-gemini` | `google/gemini-3.8-flash` | Google AI Studio | 1M | Yes | `GEMINI_API_KEY` (aliases accepted; see below) |
| `/oc-groq` | `groq/openai/gpt-oss-120b` | Groq | 128K | Yes | `GROQ_API_KEY` |
| `/oc-groq-qwen` | `groq/qwen/qwen3.8-27b` | Groq | 128K | Yes | `GROQ_API_KEY` |
| `/oc-nvidia` | `nvidia/nemotron-3-super-120b-a12b` | NVIDIA API Catalog / NIM | 1M | Yes | `NVIDIA_API_KEY` |
| `/oc-cloudflare` | `cloudflare-workers-ai/@cf/openai/gpt-oss-20b` | Cloudflare Workers AI | 128K | Yes | `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` |

The models above are configured candidates. An entry is not marked live/verified until a real, deliberately limited smoke test succeeds with the owner's credential.

## Credentials and secret aliases

Store credentials only as GitHub Actions repository secrets. Never paste keys into chat, code, issue comments or logs.

Required secret names:

- Existing: `TOKENHARBOR_API_KEY`, `OPENROUTER_API_KEY`
- Google: the workflow accepts `GEMINI_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, or `GOOGLE_API_KEY`, in that order.
- Groq: `GROQ_API_KEY`
- NVIDIA: `NVIDIA_API_KEY`
- Cloudflare: `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`

The user has reported that a Gemini key was added. The repository cannot read secret values, so actual availability is confirmed only when the `/oc-gemini` workflow's presence check succeeds. The workflow exposes only the selected provider's credential to the OpenCode process.

## Free-use boundaries

### Token Harbor

Use only model IDs ending in `:free`. The free routes have a value-based rolling seven-day allowance and free-account request limits. No wallet credits, top-ups, paid model IDs or paid fallbacks.

### OpenRouter

Use only explicit `:free` model variants or the `openrouter/free` router. Current free-variant account cap: 20 requests/minute and 50 requests/day for accounts below the lifetime-credit threshold. Failed attempts also count toward the daily cap. Do not purchase credits to raise the cap. The daily limit is shared across the OpenRouter routes; adding more model choices does not multiply it.

OpenRouter may retry a different healthy upstream host for the same selected model. That is provider-side endpoint redundancy, not ECLIPSE's cross-model failover.

### Google Gemini API

Google AI Studio offers a no-charge API tier for certain models, with per-model/project quotas. The exact quotas are shown in AI Studio and can change. Google states that free-tier API content may be used to improve its products. Do not send private credentials, secrets, personal information or confidential repository material to this route.

### Groq

Groq's Free plan has per-model RPM, RPD, TPM and TPD limits. The current published base free limits for GPT-OSS 120B and Qwen 3.8 27B are 30 RPM, 1,000 RPD, 8K TPM and 200K TPD; the account's Limits page is authoritative. Both listed models support tool use. Qwen 3.8 27B is a preview model and can change or be retired.

### NVIDIA API Catalog / NIM

NVIDIA's Developer Program offers free API-catalog endpoints for prototyping and experimentation. Endpoint availability, model access and rate limits can vary. The selected model must still show a free endpoint in the catalog; never switch to a paid partner deployment.

### Cloudflare Workers AI

The Workers Free plan includes 10,000 Neurons per day, resetting at 00:00 UTC. Use only models available on the Workers Free plan. Keep the account on Workers Free: do not upgrade to Workers Paid, add prepaid credits, or configure a payment method for inference. On the Free plan, exceeding the included allocation should fail rather than bill. The configured GPT-OSS 20B model supports function calling and has a 128K context. Cloudflare's model unit prices are not the same as the free Neurons allowance.

## Deliberately not added to the automatic pool

- **SambaNova Cloud:** its current official Free plan requires adding a payment method and purchasing credits before requests run.
- **Mistral API:** current Mistral documentation says its Free mode does not include API access; Studio API use requires billing activation/pay-as-you-go. Its free consumer Vibe plan is a different product.
- **Hugging Face Inference Providers:** free accounts currently receive a small $0.10/month credit, but this is a credit balance routed to paid partner inference and has an optional pay-as-you-go path. It is not treated as a standing unlimited free provider. It can be reconsidered as a strictly capped experimental route.
- **Cerebras:** a $0 API-key tier exists, but the currently public free-tier model/context eligibility is not sufficiently clear for an unattended coding agent. Revisit when the supported free model list is confirmed for the account.

These exclusions are intentional: a one-time credit, trial, required top-up, or uncertain free-model eligibility is not counted as a dependable free-tier connection.

## Important implementation boundary

**This milestone adds manual provider/model selection, not automatic cross-provider failover.**

The GitHub Action selects one model for each run. A separate bounded coordinator must still be built and tested to:
1. classify provider/network/rate-limit failures without confusing them with code/test failures;
2. retry transient failures with capped backoff and provider-provided reset hints;
3. move to another provider/model when appropriate;
4. remember cooldowns and quota windows without storing secrets;
5. preserve the runner worktree, commits and continuation notes between attempts;
6. stop before any paid usage or unbounded retry loop.

Test failover with mocked provider failures before using real model requests. Real smoke tests consume free allowance and must be deliberate and limited.

## Primary sources

- [OpenRouter free model catalogue](https://openrouter.ai/collections/free-models)
- [OpenRouter free rate limits](https://openrouter.ai/docs/api/reference/limits)
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Gemini 3.8 Flash model card](https://deepmind.google/models/model-cards/gemini-3-8-flash/)
- [Groq models](https://console.groq.com/docs/models)
- [Groq rate limits](https://console.groq.com/docs/rate-limits)
- [Groq tool use](https://console.groq.com/docs/tool-use/overview)
- [NVIDIA NIM developer FAQ](https://docs.api.nvidia.com/nim/docs/product)
- [NVIDIA Nemotron 3 Super API catalog](https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b)
- [Cloudflare Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- [Cloudflare Workers AI limits](https://developers.cloudflare.com/workers-ai/platform/limits/)
- [Cloudflare GPT-OSS 20B model page](https://developers.cloudflare.com/workers-ai/models/gpt-oss-20b/)
- [OpenCode provider configuration](https://docs.opencode.ai/docs/providers/)
