#!/usr/bin/env python3
"""Validate ECLIPSE's six-provider, free-model OpenCode pool."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "opencode.json"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "opencode.yml"

PROVIDERS = {
    "tokenharbor": {
        "secret": "TOKENHARBOR_API_KEY",
        "models": {"deepseek-v4.1-flash:free", "mimo-v2.6-flash:free"},
    },
    "google": {
        "secret": "GEMINI_API_KEY",
        "models": {"gemini-3.8-flash", "gemini-3.7-flash"},
    },
    "dahl": {
        "secret": "DAHL_API_KEY",
        "models": {
            "MiniMaxAI/MiniMax-M2.7",
            "deepseek-ai/DeepSeek-V4-Flash-0731",
        },
    },
    "groq": {
        "secret": "GROQ_API_KEY",
        "models": {"openai/gpt-oss-120b", "qwen/qwen3.8-27b"},
    },
    "openrouter": {
        "secret": "OPENROUTER_API_KEY",
        "models": {
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "cohere/north-mini-code:free",
        },
    },
    "zai": {
        "secret": "ZAI_API_KEY",
        "models": {"glm-4.7-flash", "glm-4.5-flash"},
    },
}

# Keep the JSON declaration order aligned with the published global ranking.
EXPECTED_PROVIDER_ORDER = ["tokenharbor", "google", "dahl", "groq", "openrouter", "zai"]
EXPECTED_MODEL_ORDER = {
    "tokenharbor": ["deepseek-v4.1-flash:free", "mimo-v2.6-flash:free"],
    "google": ["gemini-3.8-flash", "gemini-3.7-flash"],
    "dahl": ["deepseek-ai/DeepSeek-V4-Flash-0731", "MiniMaxAI/MiniMax-M2.7"],
    "groq": ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"],
    "openrouter": ["cohere/north-mini-code:free", "nvidia/nemotron-3-ultra-550b-a55b:free"],
    "zai": ["glm-4.7-flash", "glm-4.5-flash"],
}
DEFAULT_MODEL = "tokenharbor/deepseek-v4.1-flash:free"

DISALLOWED_SECRET_NAMES = {
    "NVIDIA_API_KEY",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "COHERE_API_KEY",
    "ORCAROUTER_API_KEY",
    "KILO_API_KEY",
    "ZAI_GLM_API_KEY",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read valid OpenCode JSON: {exc}")

    try:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"Could not read OpenCode workflow: {exc}")

    if "timeout-minutes: 350" not in workflow:
        fail("The OpenCode workflow must retain timeout-minutes: 350.")

    if config.get("permission", {}).get("external_directory") != "deny":
        fail("opencode.json must retain permission.external_directory = deny.")

    configured_providers = config.get("provider", {})
    if list(configured_providers) != EXPECTED_PROVIDER_ORDER:
        fail(
            "Provider groups must be declared best-first according to the published ECLIPSE ranking: "
            + ", ".join(EXPECTED_PROVIDER_ORDER)
        )

    if config.get("model") != DEFAULT_MODEL:
        fail(f"The default /oc route must remain the rank-1 model: {DEFAULT_MODEL}")

    for provider, expected_order in EXPECTED_MODEL_ORDER.items():
        actual_order = list(configured_providers.get(provider, {}).get("models", {}))
        if actual_order != expected_order:
            fail(
                f"{provider}: models must be declared best-first; "
                f"expected {expected_order}, got {actual_order}."
            )
    if set(configured_providers) != set(PROVIDERS):
        fail(
            "The OpenCode provider set must be exactly: "
            + ", ".join(sorted(PROVIDERS))
            + f"; got: {', '.join(sorted(configured_providers))}"
        )

    default_model = config.get("model", "")
    if "/" not in default_model:
        fail(f"Default model has no provider prefix: {default_model!r}")
    default_provider, default_id = default_model.split("/", 1)
    if default_provider not in PROVIDERS:
        fail(f"Default model uses an unapproved provider: {default_provider!r}")
    if default_id not in configured_providers[default_provider].get("models", {}):
        fail(f"Default model is missing from provider config: {default_model}")

    case_match = re.search(
        r'case "\$COMMENT_BODY" in(.*?)\n\s*esac',
        workflow,
        flags=re.DOTALL,
    )
    if not case_match:
        fail("Could not find the comment-to-model selector case statement.")

    route_pattern = re.compile(
        r'^\s*\*"(/[^"]+)"\*\)\s*\n'
        r'\s*provider="([^"]+)"\s*\n'
        r'\s*model="([^"]+)"\s*;{2}',
        flags=re.MULTILINE,
    )
    routes = route_pattern.findall(case_match.group(1))
    if not routes:
        fail("No comment routes were found in the selector.")

    commands = [command for command, _, _ in routes]
    if len(commands) != len(set(commands)):
        fail("Duplicate comment commands were found.")

    seen: dict[str, set[str]] = {name: set() for name in PROVIDERS}
    # The default /oc route is selected before the case statement, so count it
    # as an explicit route for the default model.
    seen[default_provider].add(default_id)
    for command, provider, model in routes:
        if provider not in PROVIDERS:
            fail(f"{command}: provider {provider!r} is not in the six-provider allowlist.")
        if "/" not in model:
            fail(f"{command}: model must be provider/model, got {model!r}")

        model_provider, model_id = model.split("/", 1)
        if model_provider != provider:
            fail(f"{command}: model provider {model_provider!r} does not match {provider!r}.")

        allowed_models = PROVIDERS[provider]["models"]
        if model_id not in allowed_models:
            fail(f"{command}: model {model!r} is not in the approved model set.")

        configured_models = configured_providers[provider].get("models", {})
        if model_id not in configured_models:
            fail(f"{command}: model {model!r} is missing from opencode.json.")

        if model_id in seen[provider]:
            fail(f"{command}: duplicate model route for {provider}/{model_id}.")
        seen[provider].add(model_id)

        secret = PROVIDERS[provider]["secret"]
        if f"secrets.{secret}" not in workflow:
            fail(f"{command}: workflow does not reference {secret}.")

        if provider in {"openrouter", "tokenharbor"} and not model_id.endswith(":free"):
            fail(f"{command}: route is not explicitly marked free: {model!r}")

    for provider, details in PROVIDERS.items():
        expected = details["models"]
        actual = set(configured_providers[provider].get("models", {}))
        if actual != expected:
            fail(f"{provider}: expected exactly {sorted(expected)}, got {sorted(actual)}.")
        if seen[provider] != expected:
            fail(f"{provider}: every configured model must have one route; got {sorted(seen[provider])}.")

    action_step = workflow.split("Run OpenCode with the selected provider credential", 1)
    if len(action_step) != 2:
        fail("Could not find the OpenCode action step.")
    action_env = action_step[1]
    for provider, details in PROVIDERS.items():
        secret = details["secret"]
        if f"steps.route.outputs.provider == '{provider}' && secrets.{secret}" not in action_env:
            fail(f"OpenCode action does not scope {secret} to provider {provider!r}.")

    for old_secret in DISALLOWED_SECRET_NAMES:
        if old_secret in workflow:
            fail(f"Removed provider secret still appears in workflow: {old_secret}.")

    print("Provider allowlist validation passed: exactly 6 providers.")
    print("Model selection validation passed: exactly 2 configured models per provider (12 total).")
    print("All 12 comment routes resolve to configured model IDs and matching GitHub secrets.")
    print("Only the selected provider credential is passed to OpenCode.")
    print("No removed-provider secrets remain in the workflow.")
    print("350-minute timeout and external-directory deny rule: preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
