#!/usr/bin/env python3
"""Validate that every OpenCode comment route resolves to a configured model.

This deliberately uses only Python's standard library so CI can run it on every
supported Python version without installing extra packages.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "opencode.json"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "opencode.yml"

PROVIDER_CONFIG_IDS = {
    "tokenharbor": "tokenharbor",
    "openrouter": "openrouter",
    "google": "google",
    "groq": "groq",
    "nvidia": "nvidia",
    "cloudflare": "cloudflare-workers-ai",
    "cohere": "cohere",
    "orcarouter": "orcarouter",
}

PROVIDER_SECRET_NAMES = {
    "tokenharbor": ("TOKENHARBOR_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "google": (
        "GEMINI_API_KEY",
        "GOOGLE_GENERATIVE_AI_API_KEY",
        "GOOGLE_API_KEY",
    ),
    "groq": ("GROQ_API_KEY",),
    "nvidia": ("NVIDIA_API_KEY",),
    "cloudflare": ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"),
    "cohere": ("COHERE_API_KEY",),
    "orcarouter": ("ORCAROUTER_API_KEY",),
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

    default_model = config.get("model", "")
    if "/" not in default_model:
        fail(f"Default model has no provider prefix: {default_model!r}")
    default_provider, default_id = default_model.split("/", 1)
    if default_id not in config.get("provider", {}).get(default_provider, {}).get("models", {}):
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

    providers = config.get("provider", {})
    counts: dict[str, int] = {}
    for command, workflow_provider, model in routes:
        config_provider = PROVIDER_CONFIG_IDS.get(workflow_provider)
        if not config_provider:
            fail(f"{command}: unknown workflow provider {workflow_provider!r}")

        if "/" not in model:
            fail(f"{command}: model must be provider/model, got {model!r}")

        model_provider, model_id = model.split("/", 1)
        if model_provider != config_provider:
            fail(
                f"{command}: model provider {model_provider!r} does not match "
                f"workflow provider {workflow_provider!r} (config key "
                f"{config_provider!r})."
            )

        model_map = providers.get(config_provider, {}).get("models", {})
        if model_id not in model_map:
            fail(f"{command}: model {model!r} is missing from opencode.json.")

        counts[workflow_provider] = counts.get(workflow_provider, 0) + 1

        for secret_name in PROVIDER_SECRET_NAMES[workflow_provider]:
            if f"secrets.{secret_name}" not in workflow:
                fail(f"{command}: workflow does not reference {secret_name}.")

        # Free OpenRouter selections must be explicit free variants, the
        # free router, or the published zero-price stealth preview.
        if workflow_provider == "openrouter":
            if not (
                model_id == "free"
                or model_id.endswith(":free")
                or model_id == "stealth/crouton-alpha"
            ):
                fail(f"{command}: OpenRouter model is not marked free: {model!r}")

        # OrcaRouter must use only its explicit zero-price free routes.
        if workflow_provider == "orcarouter" and model_id not in {
            "orcarouter/free",
            "deepseek/deepseek-v4-flash-free",
        }:
            fail(f"{command}: OrcaRouter route is not explicitly free: {model!r}")

    # The agent step must conditionally pass provider credentials rather than
    # giving every key to every model.
    agent_step = workflow.split("Run OpenCode with the selected free", 1)
    if len(agent_step) == 1:
        fail("Could not find the selected-model OpenCode action step.")
    for provider in PROVIDER_CONFIG_IDS:
        if f"steps.route.outputs.provider == '{provider}'" not in agent_step[1]:
            fail(f"OpenCode action credentials are not scoped to provider {provider!r}.")

    total_models = sum(len(item.get("models", {})) for item in providers.values())
    print(f"Provider route validation passed: {len(routes)} commands.")
    print(f"Configured model/router entries: {total_models}.")
    print(
        "Routes by provider: "
        + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    )
    print("Free-only OpenRouter route check: passed.")
    print("350-minute timeout and external-directory deny rule: preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
