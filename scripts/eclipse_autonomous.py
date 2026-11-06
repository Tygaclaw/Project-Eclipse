#!/usr/bin/env python3
"""Bounded autonomous ECLIPSE milestone runner for GitHub Actions.

The controller owns Git/GitHub writes. OpenCode receives only one provider key
per invocation and cannot commit, push, or access paths outside the worktree.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
PROVIDER_ROUTES = (
    ("tokenharbor", "deepseek-v4.1-flash:free", "TOKENHARBOR_API_KEY", "TOKENHARBOR_API_KEY"),
    ("google", "gemini-3.8-flash", "GEMINI_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY"),
    ("tokenharbor", "mimo-v2.6-flash:free", "TOKENHARBOR_API_KEY", "TOKENHARBOR_API_KEY"),
    ("google", "gemini-3.7-flash", "GEMINI_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY"),
    ("dahl", "deepseek-ai/DeepSeek-V4-Flash-0731", "DAHL_API_KEY", "DAHL_API_KEY"),
    ("groq", "qwen/qwen3.8-27b", "GROQ_API_KEY", "GROQ_API_KEY"),
    ("openrouter", "cohere/north-mini-code:free", "OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
    ("zai", "glm-4.7-flash", "ZAI_API_KEY", "ZAI_API_KEY"),
    ("dahl", "MiniMaxAI/MiniMax-M2.7", "DAHL_API_KEY", "DAHL_API_KEY"),
    ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free", "OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
    ("groq", "openai/gpt-oss-120b", "GROQ_API_KEY", "GROQ_API_KEY"),
    ("zai", "glm-4.5-flash", "ZAI_API_KEY", "ZAI_API_KEY"),
)

MAX_CALLS_PER_MODEL = 6  # initial call + five retries
DEFAULT_TURN_TIMEOUT = 2_400
DEFAULT_RUN_BUDGET = 270 * 60
MAX_BACKOFF = 90
PROTECTED_PREFIXES = (
    ".github/workflows/",
    ".github/scripts/",
    "scripts/eclipse_autonomous.py",
    "tests/test_autonomous_runner.py",
    "opencode.json",
    "DEEPSEEK_START_HERE.md",
    "SECURITY.md",
    "docs/AUTONOMOUS_ENGINEERING_PROTOCOL.md",
)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
)


@dataclass(frozen=True)
class Route:
    provider: str
    model_id: str
    secret_name: str
    api_env_name: str

    @property
    def open_code_id(self) -> str:
        return f"{self.provider}/{self.model_id}"


ROUTES = tuple(Route(*row) for row in PROVIDER_ROUTES)


@dataclass(frozen=True)
class Failure:
    kind: str
    skip_provider: bool = False
    retryable: bool = False
    reason: str = ""


@dataclass
class RunResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


def classify_failure(output: str, timed_out: bool = False) -> Failure:
    """Classify a failed route without retrying exhausted or invalid providers."""
    text = output.lower()
    if any(token in text for token in (
        "429", "rate limit", "rate_limit", "quota exceeded", "resource_exhausted",
        "insufficient_quota", "free tier limit", "credits exhausted", "payment required",
    )):
        return Failure("quota", True, False, "provider quota/rate limit")
    if any(token in text for token in (
        "401", "403", "unauthorized", "invalid api key", "invalid_api_key",
        "authentication failed", "permission denied for api key",
    )):
        return Failure("authentication", True, False, "provider credential/authorization failure")
    if any(token in text for token in (
        "model not found", "unknown model", "model_not_found", "model is unavailable",
        "model unavailable", "404 model",
    )):
        return Failure("model_unavailable", False, False, "model route unavailable")
    if timed_out or any(token in text for token in (
        "502", "503", "504", "gateway timeout", "connection reset", "connection refused",
        "temporarily unavailable", "econnreset", "etimedout", "network error",
        "socket hang up", "internal server error",
    )):
        return Failure("transient", False, True, "transient provider/network failure")
    return Failure("agent_or_unknown", False, True, "model call failed; retry same session")


def extract_session_id(output: str) -> str | None:
    """Read a session ID from OpenCode JSON events or diagnostic text."""
    for line in output.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        found = _find_session_id(payload)
        if found:
            return found
    match = re.search(r"\bses_[A-Za-z0-9]{8,}\b", output)
    return match.group(0) if match else None


def _find_session_id(value: object) -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in {"sessionid", "session_id"} and isinstance(nested, str):
                if nested.startswith("ses_"):
                    return nested
            for nested in value.values():
            found = _find_session_id(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_session_id(nested)
            if found:
                return found
    return None


def safe_child_environment(route: Route, source: dict[str, str]) -> dict[str, str]:
    """Construct an allowlisted child environment; never forward GitHub tokens."""
    allowed = (
        "PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP",
        "APPDATA", "LOCALAPPDATA", "SYSTEMROOT", "WINDIR", "CI",
    )
    env = {key: source[key] for key in allowed if key in source}
    key_value = source.get(route.secret_name, "")
    if not key_value:
        raise ValueError(f"Missing approved secret {route.secret_name}")
    env[route.api_env_name] = key_value
    env["CI"] = "true"
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "1"
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps({
        "agent": {
            "eclipse-autonomous": {
                "description": "Autonomous ECLIPSE engineer. Do not create commits, push, or use GitHub write commands.",
                "mode": "primary",
                "permission": {
                    "external_directory": "deny",
                    "bash": {
                        "*": "allow",
                        "git commit*": "deny",
                        "git push*": "deny",
                        "git reset --hard*": "deny",
                        "git clean -f*": "deny",
                        "gh *": "deny",
                        "env": "deny",
                        "printenv*": "deny",
                        "curl*": "deny",
                        "wget*": "deny",
                        "nc *": "deny",
                        "socat*": "deny",
                        "python -c*": "deny",
                        "rm -rf*": "deny",
                    },
                },
            },
        },
    })
    return env


def build_run_prompt(run_title: str) -> str:
    return f"""You are the implementation model inside the autonomous ECLIPSE engineering system.
Run title: {run_title}

Read these files first:
- DEEPSEEK_START_HERE.md
- docs/AUTONOMOUS_ENGINEERING_PROTOCOL.md
- AUTONOMOUS_BACKLOG.md
- .eclipse/AUTONOMOUS_SESSION_HANDOFF.md
- STATUS.md, CONTINUATION.md, README.md, ARCHITECTURE.md, REQUIREMENTS.md, TESTING.md
- docs/COMPLETE_PRODUCT_RUNTIME_VISION.md and the relevant implementation files/tests.

Select the highest-priority READY backlog milestone whose dependencies are met. Implement ONE coherent, reviewable milestone end-to-end. Do not redo items already verified on main. Inspect actual code before editing. Preserve Windows 11 first, the three exact workspaces, shared Core, static-first inspection, all five internal subsystems, both phase maps, free-only provider rules and all user constraints.

Add real tests for every behavior changed. Run focused tests and the full portable test suite. Do not weaken/delete tests, skip failing checks, fabricate output, commit, push, merge, alter repository permissions, use GitHub CLI/API write actions, or touch files outside the worktree. The runner/controller performs commits and PR operations after checks. Do not modify protected automation/security files unless this milestone is specifically assigned and an owner-review PR is expected.

Update AUTONOMOUS_BACKLOG.md, STATUS.md, CONTINUATION.md and .eclipse/AUTONOMOUS_SESSION_HANDOFF.md with factual state and exact evidence. Mark a requirement VERIFIED only when its acceptance evidence exists. If a requirement needs owner-only Windows/GPU/Obsidian validation, label only that gate WAITING_FOR_OWNER_VALIDATION and continue independent work.

When done, leave a concise summary of changed files, tests actually run, test results, any remaining limitations and the next backlog milestone. Do not claim the full product is complete unless every requirement and release gate is objectively satisfied.
"""


def build_repair_prompt(failure_output: str) -> str:
    clipped = failure_output[-12_000:]
    return f"""Continue the SAME ECLIPSE task in this SAME OpenCode session. Do not restart or discard successful work.
The independent validation step failed. Diagnose the concrete failure, fix the underlying issue, add/update regression coverage, and rerun the relevant test plus the full portable suite. Do not weaken tests or claim success without output.

Sanitized validation output:
{clipped}
"""


def run_opencode(
    route: Route,
    prompt: str,
    session_id: str | None,
    run_title: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    timeout: int = DEFAULT_TURN_TIMEOUT,
    source_env: dict[str, str] | None = None,
) -> tuple[RunResult, str | None]:
    env_source = source_env if source_env is not None else dict(os.environ)
    child_env = safe_child_environment(route, env_source)
    command = [
        "opencode", "run", "--format", "json", "--agent", "eclipse-autonomous",
        "--model", route.open_code_id, "--title", run_title, "--auto",
    ]
    if session_id:
        command.extend(["--session", session_id])
    command.append(prompt)
    try:
        completed = runner(
            command, cwd=ROOT, env=child_env, text=True, capture_output=True,
            timeout=timeout, check=False,
        )
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        return RunResult(completed.returncode, completed.stdout or "", completed.stderr or ""), (
            extract_session_id(output) or session_id
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return RunResult(124, stdout, stderr, True), extract_session_id(stdout + "\n" + stderr) or session_id


def validate_worktree() -> tuple[bool, str]:
    commands = (
        ("Compile", [sys.executable, "-m", "compileall", "-q", "src", "tests", ".github/scripts", "scripts"]),
        ("Provider configuration", [sys.executable, ".github/scripts/validate_provider_pool.py"]),
        ("Unit tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
        ("Whitespace", ["git", "diff", "--check"]),
    )
    outputs: list[str] = []
    for title, command in commands:
        completed = subprocess.run(
            command, cwd=ROOT, env=controller_environment(dict(os.environ)),
            text=True, capture_output=True, check=False,
        )
        combined = (completed.stdout or "") + (completed.stderr or "")
        outputs.append(f"===== {title} (exit {completed.returncode}) =====\n{combined[-8_000:]}")
        if completed.returncode != 0:
            return False, "\n".join(outputs)
    return True, "\n".join(outputs)


def changed_paths() -> list[str]:
    names = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=ROOT, env=controller_environment(dict(os.environ)),
        text=True, capture_output=True, check=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT, env=controller_environment(dict(os.environ)),
        text=True, capture_output=True, check=True,
    ).stdout.splitlines()
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT, env=controller_environment(dict(os.environ)),
        text=True, capture_output=True, check=True,
    ).stdout.splitlines()
    return sorted(set(names + untracked + staged))


def safety_scan(paths: Sequence[str], *, max_bytes: int = 10 * 1024 * 1024) -> tuple[bool, str, bool]:
    problems: list[str] = []
    protected = False
    for name in paths:
        path = ROOT / name
        if any(name.startswith(prefix) for prefix in PROTECTED_PREFIXES):
            protected = True
        if not path.exists():
            # Deletions require explicit review; never silently auto-merge them.
            protected = True
            continue
        if path.is_symlink():
            problems.append(f"{name}: symlinks are not allowed in autonomous source PRs")
            continue
        if path.is_file():
            if path.stat().st_size > max_bytes:
                problems.append(f"{name}: exceeds 10 MiB; model weights/binaries must not enter Git")
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                problems.append(f"{name}: binary file is not permitted in autonomous source PRs")
                continue
            for pattern in SECRET_PATTERNS:
                if pattern.search(content):
                    problems.append(f"{name}: possible credential/private-key pattern detected")
                    break
    return not problems, "\n".join(problems), protected


def redact(text: str, source: dict[str, str]) -> str:
    result = text
    for key in (
        "DAHL_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY",
        "TOKENHARBOR_API_KEY", "ZAI_API_KEY", "GITHUB_TOKEN", "GH_TOKEN",
    ):
        value = source.get(key)
        if value:
            result = result.replace(value, "[REDACTED]")
    return result


def controller_environment(source_env: dict[str, str]) -> dict[str, str]:
    """Allowlist the parent controller's environment; provider keys stay out of Git/gh/tests."""
    allowed = (
        "PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP",
        "APPDATA", "LOCALAPPDATA", "SYSTEMROOT", "WINDIR", "CI",
    )
    env = {key: source_env[key] for key in allowed if key in source_env}
    for key in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"):
        if source_env.get(key):
            env[key] = source_env[key]
    return env


def gh(
    args: Sequence[str],
    *,
    source_env: dict[str, str],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = controller_environment(source_env)
    token = env.get("GITHUB_TOKEN") or env.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is unavailable to the parent controller.")
    env["GH_TOKEN"] = token
    return subprocess.run(
        ["gh", *args], cwd=ROOT, env=env, text=True, capture_output=True, check=check,
    )


def git_with_write_token(
    args: Sequence[str], *, source_env: dict[str, str], check: bool = True
) -> subprocess.CompletedProcess[str]:
    token = source_env.get("GITHUB_TOKEN") or source_env.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is unavailable to the parent controller.")
    env = controller_environment(source_env)
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "http.https://github.com/.extraheader"
    encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    env["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: basic {encoded}"
    return subprocess.run(
        ["git", *args], cwd=ROOT, env=env, text=True, capture_output=True, check=check,
    )


def check_open_autonomous_pr(source_env: dict[str, str]) -> bool:
    result = gh(
        ["pr", "list", "--state", "open", "--base", "main", "--json", "headRefName,isDraft,url"],
        source_env=source_env,
    )
    entries = json.loads(result.stdout or "[]")
    return any(
        str(item.get("headRefName", "")).startswith("feature/eclipse-autonomous-")
        for item in entries
    )


def route_models() -> list[Route]:
    return list(ROUTES)


def run_agent_with_failover(
    prompt: str,
    run_title: str,
    source_env: dict[str, str],
    *,
    max_calls_per_model: int = MAX_CALLS_PER_MODEL,
    turn_timeout: int = DEFAULT_TURN_TIMEOUT,
    call: Callable[..., tuple[RunResult, str | None]] = run_opencode,
    validate: Callable[[], tuple[bool, str]] = validate_worktree,
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
) -> tuple[bool, str | None, str, str | None]:
    session_id: str | None = None
    skipped_providers: set[str] = set()
    last_failure = ""
    for route in route_models():
        if route.provider in skipped_providers:
            continue
        if not source_env.get(route.secret_name):
            skipped_providers.add(route.provider)
            last_failure = f"{route.provider}: missing configured secret {route.secret_name}"
            continue

        for attempt in range(max_calls_per_model):
                    current_prompt = (
                prompt if attempt == 0 and session_id is None
                else build_repair_prompt(last_failure) if last_failure
                else prompt
            )
            result, observed_session = call(
                route, current_prompt, session_id, run_title,
                timeout=turn_timeout, source_env=source_env,
            )
            session_id = observed_session or session_id
            raw_output = redact(result.stdout + "\n" + result.stderr, source_env)

            if result.returncode != 0:
                failure = classify_failure(raw_output, result.timed_out)
                last_failure = f"{route.open_code_id}: {failure.reason}\n{raw_output[-6_000:]}"
                if failure.skip_provider:
                    skipped_providers.add(route.provider)
                    break
                if failure.kind == "model_unavailable":
                    break
                if failure.retryable and attempt + 1 < max_calls_per_model:
                    sleep(min(MAX_BACKOFF, (2 ** attempt) + rng() * 3))
                    continue
                break

            if session_id is None:
                last_failure = (
                    f"{route.open_code_id}: OpenCode returned no recoverable session ID. "
                    "Refusing to claim same-session failover."
                )
                break

            valid, validation_output = validate()
            if valid:
                return True, session_id, route.open_code_id, ""
            last_failure = redact(validation_output, source_env)
            if attempt + 1 < max_calls_per_model:
                continue
            break

    return False, session_id, "", last_failure or "No approved free model route was available."


def make_pr_body(branch: str, paths: Sequence[str], validation: str, protected: bool) -> str:
    preview = "\n".join(f"- `{item}`" for item in paths[:80])
    if len(paths) > 80:
        preview += f"\n- … and {len(paths) - 80} more files"
    return f"""## Autonomous ECLIPSE milestone

- Branch: `{branch}`
- Base: `main`
- Automatic merge eligible: **{"no — protected paths require owner review" if protected else "yes, after both Windows workflows pass"}**

### Changed files

{preview}

### Validation performed by the parent controller

```text
{validation[-12_000:]}
```

### Merge policy

This PR is not considered complete because a model says it is complete. The controller requires successful Windows Python 3.11–3.14 and Windows Qt/PyInstaller CI. Protected workflow, credential, policy and controller changes remain draft for owner review. No provider key or GitHub token is included in this PR.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-agent-minutes", type=int, default=int(os.getenv("ECLIPSE_MAX_AGENT_MINUTES", "240")))
    args = parser.parse_args()
    source_env = dict(os.environ)
    repository = source_env.get("GITHUB_REPOSITORY", "Tygaclaw/Project-Eclipse")
    run_id = source_env.get("GITHUB_RUN_ID", str(int(time.time())))
    attempt_id = source_env.get("GITHUB_RUN_ATTEMPT", "1")
    base_branch = source_env.get("ECLIPSE_BASE_BRANCH", source_env.get("GITHUB_REF_NAME", "main"))
    run_title = f"ECLIPSE autonomous milestone {run_id}-{attempt_id}"
    deadline = time.monotonic() + args.max_agent_minutes * 60

    if check_open_autonomous_pr(source_env):
        print("An autonomous milestone PR is already open. No duplicate work will be started.")
        return 0

    controller_env = controller_environment(source_env)
    subprocess.run(["git", "fetch", "origin", base_branch], cwd=ROOT, env=controller_env, check=True)
    subprocess.run(["git", "switch", "--detach", f"origin/{base_branch}"], cwd=ROOT, env=controller_env, check=True)
    branch = f"feature/eclipse-autonomous-{run_id}-{attempt_id}"
    subprocess.run(["git", "switch", "-c", branch], cwd=ROOT, env=controller_env, check=True)

    prompt = build_run_prompt(run_title)
    source_env.setdefault("ECLIPSE_MAX_AGENT_MINUTES", str(args.max_agent_minutes))
    # Reserve enough time for checks, pushing, PR creation and CI observation.
    remaining = max(120, int(deadline - time.monotonic()) - 45 * 60)
    turn_timeout = min(DEFAULT_TURN_TIMEOUT, remaining)

    success, session_id, selected_model, failure = run_agent_with_failover(
        prompt, run_title, source_env, turn_timeout=turn_timeout,
    )
    if not success:
        print("BLOCKED_NO_FREE_MODEL_OR_RECOVERABLE_SESSION")
        print(redact(failure, source_env))
        return 2

    paths = changed_paths()
    if not paths:
        print("No repository changes were produced. Backlog/agent state must be inspected; no empty PR created.")
        return 0

    safe, scan_message, protected = safety_scan(paths)
    if not safe:
        print("SAFETY_SCAN_BLOCKED")
        print(scan_message)
        return 3

    # Controller owns commits. Agent credentials never contain GITHUB_TOKEN or GH_TOKEN.
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, env=controller_env,
        text=True, capture_output=True, check=True,
    ).stdout
    if status.strip():
        subprocess.run(["git", "add", "-A"], cwd=ROOT, env=controller_env, check=True)
        subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, env=controller_env, check=True)
        subprocess.run(
            ["git", "-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
             "commit", "-m", "feat: complete autonomous ECLIPSE milestone"],
            cwd=ROOT, env=controller_env, check=True,
        )

    final_paths = changed_paths()
    safe, scan_message, protected = safety_scan(final_paths)
    if not safe:
        print("SAFETY_SCAN_BLOCKED_AFTER_STAGE")
        print(scan_message)
        return 3

    git_with_write_token(["push", "--set-upstream", "origin", branch], source_env=source_env)
    body = make_pr_body(branch, final_paths, "Portable checks passed; Windows CI is the required merge gate.", protected)
    create_args = ["pr", "create", "--base", "main", "--head", branch,
                   "--title", "ECLIPSE autonomous milestone", "--body", body]
    if protected:
        create_args.append("--draft")
    created = gh(create_args, source_env=source_env)
    pr_url = created.stdout.strip().splitlines()[-1]
    print(f"Created {'draft ' if protected else ''}PR: {pr_url}")
    print(f"Selected model: {selected_model}")
    print(f"OpenCode session: {session_id}")
    print("Changed paths:")
    print("\n".join(final_paths))

    checks = gh(["pr", "checks", pr_url, "--watch", "--fail-fast"], source_env=source_env, check=False)
    if checks.returncode != 0:
        print("CI_NOT_GREEN: PR remains open and will not be merged.")
        print(redact(checks.stdout + checks.stderr, source_env)[-8_000:])
        return 4

    if protected:
        print("OWNER_REVIEW_REQUIRED: protected automation/security paths changed; CI passed but PR intentionally remains draft.")
        return 0

    details = json.loads(gh(["pr", "view", pr_url, "--json", "headRefOid,state,isDraft"], source_env=source_env).stdout)
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()
    if details.get("state") != "OPEN" or details.get("isDraft") or details.get("headRefOid") != current_head:
        print("PR_HEAD_CHANGED_OR_NOT_MERGEABLE: refusing automatic merge.")
        return 5

    merged = gh(["pr", "merge", pr_url, "--squash", "--delete-branch"], source_env=source_env, check=False)
    if merged.returncode != 0:
        print("AUTO_MERGE_BLOCKED: PR remains open for inspection.")
        print(redact(merged.stdout + merged.stderr, source_env)[-8_000:])
        return 6

    print("AUTONOMOUS_MILESTONE_MERGED")
    print(redact(merged.stdout, source_env))
    # workflow_dispatch is an allowed GITHUB_TOKEN-triggered workflow event.
    # Concurrency ensures the next run waits until this run releases the group.
    dispatch = gh(
        ["workflow", "run", "eclipse-autonomous.yml", "--ref", "main", "-f", "mode=continue"],
        source_env=source_env, check=False,
    )
    if dispatch.returncode == 0:
        print("NEXT_AUTONOMOUS_RUN_QUEUED")
    else:
        print("NEXT_RUN_NOT_QUEUED; six-hour schedule will resume the backlog.")
        print(redact(dispatch.stdout + dispatch.stderr, source_env)[-4_000:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
