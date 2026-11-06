# Free-model provider pool

**Purpose:** Keep the ECLIPSE GitHub Actions engineering agent usable when one free model route is unavailable, while preventing paid usage.

**Last reviewed:** 6 November 2026. Provider/model catalogs, free quotas and terms change frequently. “Configured” does not mean “live-tested”.

## At a glance

The current branch configures **six provider connections**:

1. Token Harbor — existing free routes.
2. OpenRouter — multiple independently hosted free model routes behind one key.
3. Google AI Studio / Gemini API — free-tier Gemini and Gemma.
4. Groq — free-plan GPT-OSS and Qwen routes.
5. NVIDIA API Catalog / NIM — developer/free prototype endpoint, subject to eligibility and capacity.
6. Cloudflare Workers AI — models available on the Workers Free plan, subject to its daily Neurons cap.
7. Cohere — separate **evaluation-only** key; not counted as a dependable production/survival connection.

The workflow checks the selected provider's credential, passes only that provider's credential to OpenCode, and keeps the existing 350-minute job timeout.

## Configured routes

### Token Harbor

| Comment command | OpenCode model |
|---|---|
| `/oc` | `tokenharbor/deepseek-v4.1-flash:free` |
| `/oc-mimo` | `tokenharbor/mimo-v2.6-flash:free` |

Both are existing routes. Use only IDs ending in `:free`.

### OpenRouter

One key unlocks the following explicit free/zero-price routes:

| Comment command | OpenCode model | Context | Notes |
|---|---|---:|---|
| `/oc-openrouter` | `openrouter/cohere/north-mini-code:free` | 256K | Purpose-built for agentic coding and terminal work; tool calling. |
| `/oc-openrouter-flint` | `openrouter/recursive/flint-v1.0:free` | 262K | Coding-agent model for codebase investigation, bug fixing, features and tests. |
| `/oc-openrouter-nemotron` | `openrouter/nvidia/nemotron-3.5-lightning:free` | 1M | Fast MoE model; agentic workloads. |
| `/oc-openrouter-gemma` | `openrouter/google/gemma-4-26b-a4b-it:free` | 262K | Tool calling, multimodal input and structured outputs. |
| `/oc-openrouter-gemma31` | `openrouter/google/gemma-4-31b-it:free` | 262K | Larger Gemma route; verify endpoint availability at smoke-test time. |
| `/oc-openrouter-nano` | `openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | 256K | Multimodal text/image/audio/video; tool calling. |
| `/oc-openrouter-xing` | `openrouter/xingchen-agi/xing4.0-29b-a4b:free` | 262K | Tuned for engineering/agent work and multi-step planning. |
| `/oc-openrouter-ultra` | `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | 1M | 550B MoE, 55B active; long-horizon reasoning/orchestration; tools. |
| `/oc-openrouter-supervl` | `openrouter/nvidia/nemotron-3.5-super-vl:free` | 1M | Multimodal agent model for documents, screenshots and video; tools. |
| `/oc-openrouter-dots` | `openrouter/dots-studio/dots-3-note-preview:free` | 512K | Temporary preview; OpenRouter currently lists removal on **31 December 2026**. |
| `/oc-openrouter-crouton` | `openrouter/stealth/crouton-alpha` | 1.05M | Free zero-price preview with tool calling; anonymous third-party operator. Treat as experimental and do not send confidential data. |
| `/oc-openrouter-auto` | `openrouter/free` | Selected by router | OpenRouter chooses an eligible free model for each request; actual model may vary. |

OpenRouter's free catalogue ranks models by recent usage, **not quality**. The top-used list must never be mistaken for a benchmark leaderboard.

### Google AI Studio / Gemini API

| Comment command | OpenCode model | Context | Notes |
|---|---|---:|---|
| `/oc-gemini` | `google/gemini-3.8-flash` | 1M | Long-horizon software engineering and autonomous-agent model. |
| `/oc-gemini-lite` | `google/gemini-3.5-flash-lite` | 1M | Lower-cost/low-latency model for high-volume and subagent tasks. |
| `/oc-gemini-gemma31` | `google/gemma-4-31b-it` | 256K | Gemma 4 31B hosted through Gemini API. |
| `/oc-gemini-gemma26` | `google/gemma-4-26b-a4b-it` | 256K | Gemma 4 26B-A4B hosted through Gemini API. |

Gemini's free API tier is limited by model and project. The exact current quota is shown in Google AI Studio and may change. Google says free-tier content may be used to improve its products. Do not send private credentials, personal information or confidential material.

The workflow accepts any one of these secret names for the Google key, in this order:
`GEMINI_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, `GOOGLE_API_KEY`.

The owner has reported adding a Gemini key. The secret value/name cannot be inspected by the repository integration; its presence will be confirmed only when a selected `/oc-gemini...` job passes the secret check.

### Groq

| Comment command | OpenCode model | Context | Free-plan limits |
|---|---|---:|---|
| `/oc-groq` | `groq/openai/gpt-oss-120b` | 128K | 30 RPM, 1,000 RPD, 8K TPM, 200K TPD |
| `/oc-groq-small` | `groq/openai/gpt-oss-20b` | 128K | 30 RPM, 1,000 RPD, 8K TPM, 200K TPD |
| `/oc-groq-qwen` | `groq/qwen/qwen3.8-27b` | 128K | 30 RPM, 1,000 RPD, 8K TPM, 200K TPD |

These are the published Free Plan base limits at the time of review; the owner's Groq Limits page is authoritative. Keep the account on Groq's Free plan. Do not activate a paid Developer plan or paid usage. Groq returns rate-limit errors when the free allowance is exhausted.

### NVIDIA API Catalog / NIM

| Comment command | OpenCode model | Context | Notes |
|---|---|---:|---|
| `/oc-nvidia` | `nvidia/nemotron-3-super-120b-a12b` | 1M configured | NVIDIA Developer API Catalog endpoint for prototyping. Access/availability and request limits depend on the account and endpoint. |

Use this only if NVIDIA's current API Catalog marks the chosen endpoint as free for the account. Do not select partner-hosted paid endpoints, create paid deployments, or accept a paid plan. There is no published uninterrupted-free capacity guarantee.

### Cloudflare Workers AI

| Comment command | OpenCode model | Context | Current Free-plan status |
|---|---|---:|---|
| `/oc-cloudflare` | `cloudflare-workers-ai/@cf/openai/gpt-oss-20b` | 128K | Free-plan model |
| `/oc-cloudflare-glm` | `cloudflare-workers-ai/@cf/zai-org/glm-4.7-flash` | 128K | Free-plan model |
| `/oc-cloudflare-gemma` | `cloudflare-workers-ai/@cf/google/gemma-4-26b-a4b-it` | 256K | Free-plan model |
| `/oc-cloudflare-nemotron` | `cloudflare-workers-ai/@cf/nvidia/nemotron-3-120b-a12b` | 256K | Free-plan model |

Workers Free includes **10,000 Neurons per day**, resetting at 00:00 UTC. The workflow requires both `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`.

**Billing safety warning:** use these commands only while the Cloudflare account remains on the Workers Free plan. Do not upgrade to Workers Paid, enable prepaid usage, or configure a paid inference path. Workers Paid can bill beyond the free allocation. The model catalogue can change; re-check the Free-plan eligibility before any new route is added.

### Cohere — evaluation only

| Comment command | OpenCode model | Limit / restriction |
|---|---|---|
| `/oc-cohere-eval` | `cohere/command-a-reasoning-08-2025` | Evaluation key: 1,000 API calls/month, 20 requests/minute. |

Cohere trial/evaluation access is free for testing, but it is not a durable production entitlement. Do not use it as an automatic production fallback; keep it separate for controlled non-production experiments. Create `COHERE_API_KEY` only if you want to test it. Cohere's terms govern permitted use.

## GitHub Actions secrets

Save keys only under **Repository → Settings → Secrets and variables → Actions**. Never paste keys into chat, issue comments, configuration files, or logs.

| Secret name | Provider | Required to use |
|---|---|---|
| `TOKENHARBOR_API_KEY` | Token Harbor | Already configured |
| `OPENROUTER_API_KEY` | OpenRouter | Owner reports saved |
| `GEMINI_API_KEY` **or** `GOOGLE_GENERATIVE_AI_API_KEY` **or** `GOOGLE_API_KEY` | Google AI Studio | Owner reports Gemini key saved; name/presence not yet verified |
| `GROQ_API_KEY` | Groq | Not yet reported saved |
| `NVIDIA_API_KEY` | NVIDIA API Catalog / NIM | Not yet reported saved |
| `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` | Cloudflare Workers AI | Not yet reported saved; account must remain Workers Free |
| `COHERE_API_KEY` | Cohere | Optional evaluation-only lane |

The workflow checks the selected key's presence without printing it. It passes only the selected provider's credential into the OpenCode action. No API key value is stored in this repository.

## Providers deliberately excluded from the dependable free pool

- **Mistral API:** the current official plan documentation says Free mode does not include developer API access; API calls require billing activation/pay-as-you-go. Mistral's free Vibe product is separate.
- **Cerebras:** the current pricing page describes a one-time $5 promotional credit that requires a valid payment method and expires after 30 days. Not an ongoing no-card free tier.
- **BytePlus ModelArk:** its Free Tokens Only mode grants a one-time 500,000-token starter quota to eligible new accounts and pauses at exhaustion. Useful for a temporary trial, not recurring provider capacity.
- **SambaNova Cloud:** current access requirements/credit conditions do not meet our dependable no-payment-method criterion.
- **Hugging Face Inference Providers:** free access is credit-based or requires paid entitlement, rather than a dependable recurring free API pool.

A one-time credit, expiring offer, required paid activation, or unclear billing boundary is not counted as a dependable free connection. We can list such trials separately later without ever allowing them into automatic failover.

## Important implementation boundary

**This milestone adds manual model/provider selection, not automatic cross-provider failover.**

The GitHub Action selects one model for each run. A separate bounded coordinator still needs to be implemented and tested to:
1. classify provider/network/rate-limit failures without confusing them with code/test failures;
2. retry transient failures with capped backoff and provider-provided reset hints;
3. move to another provider/model when appropriate;
4. remember cooldowns and quota windows without storing secrets;
5. preserve the runner worktree, commits and continuation notes between attempts;
6. stop before any paid usage or unbounded retry loop.

Test failover with mocked provider failures before using real model requests. Real smoke tests consume free allowance and must be deliberate and limited.

## Future ECLIPSE model leaderboard

The owner wants a final ranked report with the strongest model for ECLIPSE engineering at the top and weakest at the bottom. Do not rank models from marketing claims or OpenRouter usage popularity.

The final report must combine:
- independent coding benchmarks (SWE-bench Verified/Pro, Terminal-Bench, Aider Polyglot and LiveCodeBench where comparable results exist);
- tool/agent benchmarks (for example BFCL and other verifiable agentic task evaluations);
- published Artificial Analysis Coding and Agentic indices where available;
- exact model/version, date, benchmark harness, tool access, context and prompting details;
- score provenance and whether a result is provider/model-card self-reported or independently measured;
- ECLIPSE's own controlled task results.

ECLIPSE's local scorecard must test the same repository snapshot, prompts, allowed tools, test commands and time/token budgets across models. Include repository comprehension, multi-file feature development, real-log debugging, safe changes to interconnected code, tool-call correctness, regression-test success, Windows packaging/build repair and the previously retained Three.js/game task as a separate coding category. Repeat each task enough to reduce one-run randomness.

Keep **model capability** separate from **provider reliability** (availability, latency, rate limits, cooldown frequency and quota). A high-scoring model with a tiny quota may be a poor survival-pool choice. Do not mix incomparable benchmark numbers into one invented score. Publish raw scores, sample counts, caveats and a transparent weighted ranking.

## Primary sources

- [OpenRouter free model catalogue](https://openrouter.ai/collections/free-models)
- [OpenRouter free rate limits](https://openrouter.ai/docs/api/reference/limits)
- [OpenRouter Nemotron 3 Ultra](https://openrouter.ai/nvidia/nemotron-3-ultra-550b-a55b:free)
- [OpenRouter Nemotron 3.5 Super VL](https://openrouter.ai/nvidia/nemotron-3.5-super-vl:free)
- [OpenRouter Crouton Alpha](https://openrouter.ai/stealth/crouton-alpha)
- [OpenRouter Dots3-Note Preview](https://openrouter.ai/dots-studio/dots-3-note-preview:free)
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini model catalogue](https://ai.google.dev/gemini-api/docs/models)
- [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
- [Gemma 4 on Gemini API](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api)
- [Groq models](https://console.groq.com/docs/models)
- [Groq Free Plan rate limits](https://console.groq.com/docs/rate-limits)
- [NVIDIA NIM developer FAQ](https://docs.api.nvidia.com/nim/docs/product)
- [NVIDIA Nemotron 3 Super API catalog](https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b)
- [Cloudflare Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- [Cloudflare Workers AI limits](https://developers.cloudflare.com/workers-ai/platform/limits/)
- [Cloudflare free-plan model eligibility change](https://developers.cloudflare.com/changelog/post/2026-07-28-models-require-workers-paid/)
- [Cloudflare GPT-OSS 20B model page](https://developers.cloudflare.com/workers-ai/models/gpt-oss-20b/)
- [Cohere evaluation-key rate limits](https://docs.cohere.com/v2/docs/rate-limits)
- [Cohere Command A Reasoning](https://docs.cohere.com/docs/command-a-reasoning)
- [Mistral usage and limits](https://docs.mistral.ai/admin/billing-usage/usage-limits)
- [Cerebras pricing](https://www.cerebras.ai/pricing)
- [BytePlus Free Tokens Only mode](https://docs.byteplus.com/en/docs/modelark/free-tokens-only-mode)
- [OpenCode provider configuration](https://docs.opencode.ai/docs/providers/)
