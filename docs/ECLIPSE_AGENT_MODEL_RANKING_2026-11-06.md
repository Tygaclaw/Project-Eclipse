# ECLIPSE Agent Model Ranking — 6 November 2026

**Repository:** `Tygaclaw/Project-Eclipse`  
**Scope:** the 12 exact model routes configured for the six approved free API providers in PR #9.  
**Purpose:** choose the strongest available coding/agent models for ECLIPSE development—not the largest models, the most popular models, or simply the easiest APIs to obtain.

## Executive decision

**Rank #1 and default: Token Harbor — DeepSeek V4.1 Flash Free.**

It has the strongest relevant published combination among these routes in the two most useful common measures found: DeepSWE v1.1 (74.2) and Terminal-Bench 2.1 (90.6). Gemini 3.8 Flash is a very close second (73.7 / 89.4), and MiMo V2.6 Flash is third (67.9 / 87.6). These top three should receive the first controlled ECLIPSE repository-task trials.

The current `/oc` default already points to DeepSeek V4.1 Flash Free. That default is retained. The provider configuration is reordered so the strongest route group appears first, and model choices within each provider are ordered best-first.

## How to interpret this ranking

The ranking is an evidence-weighted engineering judgement, not a mathematically exact leaderboard.

Priority was given to:
1. Repository-level issue fixing and multi-file software engineering.
2. Terminal-based agent work, tool use and the ability to complete a task through an agent harness.
3. Long-horizon planning, instruction following and research.
4. Evidence that the model works with the kind of tool harness used by ECLIPSE/OpenCode.

The most useful public measures were DeepSWE v1.1, Terminal-Bench 2.1, SWE-bench Verified/Pro, NL2Repo, LiveCodeBench, AutomationBench and tool-use evaluations.

**Scores from different benchmark versions, harnesses, pass@k settings, model precisions and vendor laboratories are not directly interchangeable.** In particular:
- SWE-bench Verified and SWE-bench Pro are different benchmark sets.
- Pass@1 and pass@10 are not the same metric.
- Terminal-Bench v2, 2.0 and 2.1 are not silently treated as identical.
- A vendor's own benchmark result is evidence, but not an independent replication.
- The API route may use a particular serving revision, quantization or prompt template that differs from the vendor's tested checkpoint.

For that reason, the numeric results below support a practical ordering but do not establish that rank 4 will always beat rank 5 on every ECLIPSE task.

## Overall ranking — best to worst for ECLIPSE development

| Rank | Provider / exact model route | Most relevant published evidence located | Assessment |
|---:|---|---|---|
| **1** | **Token Harbor — `deepseek-v4.1-flash:free`** | DeepSWE v1.1 **74.2**; Terminal-Bench 2.1 **90.6**; NL2Repo-Bench **65.4**; Terminal-Bench 4.0 **31.2** | Best overall starting point for coding, repository work and terminal agents. Strongest published combination in the shortlist. |
| **2** | **Gemini — `gemini-3.8-flash`** | DeepSWE v1.1 **73.7**; Terminal-Bench 2.1 **89.4**; Terminal-Bench 4.0 **19.1** | Extremely close to #1. Strong long-horizon engineering and agentic terminal results; excellent first alternate. |
| **3** | **Token Harbor — `mimo-v2.6-flash:free`** | DeepSWE v1.1 **67.9**; Terminal-Bench 2.1 **87.6**; AutomationBench **52.3**; Toolathlon-Verified **73.6**; Terminal-Bench 4.0 **28.8** | Strong multi-step coding and general-agent alternative. Particularly interesting for multimodal, computer-use and visual-development tasks. |
| **4** | **Gemini — `gemini-3.7-flash`** | DeepSWE v1.1 **65.3**; Terminal-Bench 2.1 **85.8**; Terminal-Bench 4.0 **11.2** | Strong, well-documented fallback, although clearly behind Gemini 3.8 on the same model-card comparisons. |
| **5** | **Dahl — `deepseek-ai/DeepSeek-V4-Flash-0731`** | DeepSWE **54.4**; Terminal-Bench 2.1 **82.7**; NL2Repo **54.2**; Toolathlon-Verified **70.3** | Strong coding-agent model, but the published results are below the V4.1 Flash route. Treat the dated Dahl model ID as its own route; do not assume it silently receives V4.1 results. |
| **6** | **Groq — `qwen/qwen3.8-27b`** | SWE-bench Pro **61.7**; Terminal-Bench 2.1 **73.0**; LiveCodeBench v6 **90.3**; NL2Repo **42.3**; DeepSWE v1.1 **42.2** | Strong code reasoning and an attractive tool-use option. Groq documents parallel tool-call support, which is useful when an agent needs several tools. Some figures use different benchmark sets, so avoid comparing its SWE-Pro score directly with SWE-Verified scores. |
| **7** | **OpenRouter — `cohere/north-mini-code:free`** | mini-SWE-Agent pass@1 **61.0**; SWE-bench Verified pass@10 **80.2**; Terminal-Bench v2 pass@10 **55.1**; Artificial Analysis Coding Index **33.4** | Purpose-built for agentic software engineering and explicitly trained for robustness across harnesses including OpenCode. Strong specialist choice. Its pass@10 figures must not be compared directly with other models' pass@1 results. |
| **8** | **Z.AI — `glm-4.7-flash`** | SWE-bench Verified **59.2**; LiveCodeBench v6 **64.0**; τ²-Bench **79.5**; BrowseComp **42.8** | Credible compact coding/agent model with useful tool and browsing results. The published model-specific Flash results are less complete than those for the top group. |
| **9** | **Dahl — `MiniMaxAI/MiniMax-M2.7`** | SWE-bench Pro **56.22**; Terminal-Bench 2 **57.0**; NL2Repo **39.8**; Multi-SWE-Bench **52.7**; Toolathon **46.3** | A capable real-world engineering model with agent-team support. Results are useful, but the reported terminal benchmark is not labelled 2.1 and its coding scores do not place it in the top group. |
| **10** | **OpenRouter — `nvidia/nemotron-3-ultra-550b-a55b:free`** | SWE-bench Verified **71.9** (BF16) / **69.7** (NVFP4); Terminal-Bench 2.1 **56.4** / **53.9**; PinchBench **90.0**; TauBench V3 average **70.9** | Strong general reasoning, long-context analysis and agent orchestration. Its Terminal-Bench score is much lower than the leading coding agents, so it is better treated as a specialist reviewer/planner than the default repository implementer. |
| **11** | **Groq — `openai/gpt-oss-120b`** | SWE-bench Verified **62.4** at high reasoning effort; Aider Polyglot **44.4**; Tau-Bench Retail **67.8** / Airline **49.2** | Useful open reasoning/tool-use model, but the published coding-agent evidence is older and less directly comparable to the leading routes. Groq's selected endpoint is also not documented as supporting parallel tool calls. |
| **12** | **Z.AI — `glm-4.5-flash`** | No reliable, exact-model coding-agent score located for this Flash route. | Ranked last because the evidence for this exact model ID is insufficient—not because a benchmark proves it is the weakest. Do not transfer flagship GLM-4.5 results to GLM-4.5-Flash; they are different model variants. Keep it as an experimental fallback until it has a live ECLIPSE evaluation. |

## Model-by-model evidence and caveats

### 1. DeepSeek V4.1 Flash — Token Harbor

DeepSeek's September 2026 release notes report DeepSWE v1.1 **74.2**, Terminal-Bench 2.1 **90.6**, NL2Repo-Bench **65.4**, Automation-Bench **54.8**, and additional agentic results. This is the best directly relevant combination found in the current 12-model list.

The official report says its code-agent evaluations use the DeepSeek Harness minimal mode for some benchmarks, mini-SWE for DeepSWE, and multiple scaffold configurations. Therefore, these results should not be treated as a guarantee of the same score inside OpenCode.

**Recommendation:** default coding agent; use first for repository understanding, implementation and debugging.

Sources:
- https://api-docs.deepseek.com/updates/
- https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash

### 2. Gemini 3.8 Flash

Google DeepMind's September 2026 model card reports DeepSWE v1.1 **73.7%**, Terminal-Bench 2.1 **89.4%**, and Terminal-Bench 4.0 **19.1%**. The card describes improvements in software engineering and agentic knowledge workflows.

This is close enough to the top route that the eventual ECLIPSE task comparison may change their order. Keep it as the first alternate rather than treating rank 1 as an unquestionable winner.

**Recommendation:** first alternate for coding, long-horizon work and independent review.

Source:
- https://deepmind.google/models/model-cards/gemini-3-8-flash/

### 3. MiMo V2.6 Flash

Xiaomi's MiMo V2.6 release is built around reinforcement learning across coding, general agents, visual tasks and cybersecurity. Its released Flash checkpoint reports DeepSWE v1.1 **67.9**, Terminal-Bench 2.1 **87.6**, AutomationBench **52.3**, Toolathlon-Verified **73.6**, and Terminal-Bench 4.0 **28.8**.

The model is also multimodal and its release describes computer-use, visual verification and interactive 3D/game-development workflows. This makes it especially interesting for ECLIPSE's eventual Three.js/game-development and desktop-agent evaluations, even though the coding-only metrics trail the top two.

**Recommendation:** third overall; give it a dedicated multimodal, computer-use and 3D development trial.

Sources:
- https://mimo.mi.com/docs/en-US/news/latest/v2-6
- https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Flash-RL

### 4. Gemini 3.7 Flash

Google's model card reports DeepSWE v1.1 **65.3%**, Terminal-Bench 2.1 **85.8%**, and Terminal-Bench 4.0 **11.2%**. It remains a capable agent model, but the same comparison table shows Gemini 3.8 ahead on these measures.

**Recommendation:** dependable alternate, below Gemini 3.8.

Source:
- https://deepmind.google/models/model-cards/gemini-3-7-flash/

### 5. DeepSeek V4 Flash — Dahl

DeepSeek's July 2026 V4 Flash announcement reports Terminal-Bench 2.1 **82.7**, DeepSWE **54.4**, NL2Repo **54.2**, Toolathlon-Verified **70.3**, and AutomationBench **25.1**.

The configured Dahl ID includes the dated suffix `DeepSeek-V4-Flash-0731`. DeepSeek's own later API notes say its older `deepseek-v4-flash` API name is temporarily routed to V4.1 Flash, but that does **not** prove Dahl's separately named dated model route has been updated. The ranking therefore uses the V4 Flash release evidence and does not borrow V4.1 scores.

**Recommendation:** good coding fallback; verify the exact Dahl-served model revision during the live smoke test.

Source:
- https://api-docs.deepseek.com/updates/

### 6. Qwen 3.8 27B — Groq

Groq's model page reports SWE-bench Pro **61.7**, Terminal-Bench 2.1 **73.0**, LiveCodeBench v6 **90.3**, NL2Repo-Bench **42.3**, and IFBench **79.5**. The Qwen model report also lists repo-level code generation and DeepSWE results.

Its key practical differentiator in this pool is parallel tool calling. That is useful for an agent that may need to inspect several files, run tests and consult repository tools in the same task. It is still below the leaders on the published Terminal-Bench 2.1 score.

**Recommendation:** best Groq choice for ECLIPSE coding-agent work; use it before GPT-OSS 120B.

Sources:
- https://console.groq.com/docs/model/qwen/qwen3.8-27b
- https://huggingface.co/Qwen/Qwen3.8-27B-FP8

### 7. Cohere North Mini Code — OpenRouter

Cohere designed North Mini Code specifically for agentic software engineering. Its published material reports **61.0% pass@1** using mini-SWE-Agent, plus **80.2% pass@10** on SWE-bench Verified and **55.1% pass@10** on Terminal-Bench v2. Cohere also describes training across multiple harness styles, including OpenCode's typed tools.

This makes it unusually relevant to the actual OpenCode workflow. However, pass@10 is a best-of-many sampling metric; it is not comparable with another model's pass@1 score.

**Recommendation:** high-value coding-specialist fallback and a priority candidate for testing in the exact OpenCode harness.

Source:
- https://huggingface.co/blog/CohereLabs/introducing-north-mini-code
- https://huggingface.co/CohereLabs/North-Mini-Code-1.0-fp8

### 8. GLM-4.7 Flash — Z.AI

The model-specific GLM-4.7 Flash card reports SWE-bench Verified **59.2**, LiveCodeBench v6 **64.0**, τ²-Bench **79.5**, and BrowseComp **42.8**. It is a 30B-A3B model intended for lightweight agentic reasoning, coding and tool use.

The public result set found is useful, but it does not give the same complete Terminal-Bench/DeepSWE comparison available for the top models.

**Recommendation:** a credible mid-pool coding and tool-use option.

Source:
- https://huggingface.co/zai-org/GLM-4.7-Flash
- https://ai.azure.com/catalog/models/zai-org--glm-4.7-flash

### 9. MiniMax M2.7 — Dahl

MiniMax reports SWE-bench Pro **56.22%**, Terminal-Bench 2 **57.0%**, NL2Repo **39.8%**, SWE Multilingual **76.5**, and Multi-SWE-Bench **52.7**. It also reports native agent-team support and a Toolathon score of **46.3%**.

This is meaningful engineering evidence, but the terminal result is not identified as Terminal-Bench 2.1 and cannot be ranked as if it were exactly the same test as the 2.1 figures above.

**Recommendation:** useful alternate for complex project work and agent-team experiments, behind the stronger measured routes.

Source:
- https://github.com/MiniMax-AI/MiniMax-M2.7

### 10. NVIDIA Nemotron 3 Ultra — OpenRouter

NVIDIA reports SWE-bench Verified **71.9** and Terminal-Bench 2.1 **56.4** for BF16, with corresponding NVFP4 results of **69.7** and **53.9**. It also reports PinchBench **90.0** and TauBench V3 average **70.9**.

Its architecture is 550B total parameters with 55B active, and NVIDIA positions it for long-context analysis, reasoning and complex agentic workflows. The high SWE-bench Verified result is notable, but the Terminal-Bench score is relatively low against the leading coding-agent models. The actual OpenRouter free endpoint's serving precision must be confirmed; do not assume it is the BF16 variant.

**Recommendation:** specialist for long-context review, planning and reasoning—not the default terminal implementer.

Source:
- https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard

### 11. GPT-OSS 120B — Groq

OpenAI's evaluation card reports SWE-bench Verified **62.4** at high reasoning effort, Aider Polyglot **44.4**, Tau-Bench Retail **67.8**, and Tau-Bench Airline **49.2**. Tool use is supported, but the published coding-agent comparison set for this model is older and does not include the same current Terminal-Bench 2.1 / DeepSWE v1.1 results found for the top routes.

Groq's selected Qwen 3.8 route is the stronger choice for this specific multi-tool workflow, including its documented parallel tool-call support.

**Recommendation:** keep as a secondary Groq route, not the preferred coding model.

Source:
- https://deploymentsafety.openai.com/gpt-oss

### 12. GLM-4.5 Flash — Z.AI

I did not locate a reliable public coding-agent benchmark table for this exact Flash model ID. The larger GLM-4.5 flagship model's scores are not transferable to GLM-4.5-Flash.

**Recommendation:** leave it configured as a free fallback, but keep it last until the exact API route has passed controlled ECLIPSE evaluation.

Source:
- https://docs.z.ai/

## Practical selection policy

- **Default:** DeepSeek V4.1 Flash Free (`/oc`).
- **First alternate:** Gemini 3.8 Flash (`/oc-gemini`).
- **Third overall / multimodal alternate:** MiMo V2.6 Flash (`/oc-mimo`).
- **Specialist coding route:** North Mini Code (`/oc-openrouter`).
- **Best Groq route:** Qwen 3.8 27B (`/oc-groq-qwen`).
- **Long-context reasoning/reviewer specialist:** Nemotron 3 Ultra (`/oc-openrouter-ultra`).

The free model order does not authorise spending. A provider quota failure means stop, report the provider failure and use a manually selected approved free route. Do not silently switch to paid models or trigger a purchase.

## What this ranking does not prove

- It does not prove that all six API keys work.
- It does not prove that all 12 endpoints pass OpenCode tool calls.
- It does not prove that the hosted endpoint serves the same precision/revision used by the model publisher.
- It does not show which model will perform best on the exact ECLIPSE repository, its Windows/Python/Qt codebase or the user's four remaining evaluation categories.
- It does not implement automatic failover.

## Required next evaluation

Run the same non-confidential ECLIPSE task set through each live route using the same OpenCode version, system prompt, tools, repository snapshot, context/output budgets and stopping rules.

At minimum include:
1. Multi-file feature development.
2. Debugging from failing tests and real logs.
3. Safe modification of an interconnected codebase.
4. Three.js/game development.

Record first-pass success, repaired success, final test acceptance, regressions, invalid tool calls, repeated loops, elapsed time, token use and quota/rate-limit failures. Repeat tasks and report medians. This controlled result—not a marketing rank—should become the final ECLIPSE-specific ordering.

**Current evidence state:** published benchmark research complete for all 12 configured model IDs, with a material evidence gap for GLM-4.5-Flash. Live endpoint and ECLIPSE-task validation remain outstanding.
