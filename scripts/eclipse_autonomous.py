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
import tempfile
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
        "context_length_exceeded", "maximum context length", "context window exceeded",
        "prompt is too long", "input is too long", "too many tokens",
    )):
        return Failure("context_length", False, False, "context limit exceeded")
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
    lowered = failure_output.lower()
    if any(token in lowered for token in (
        "context_length_exceeded", "maximum context length", "context window exceeded",
        "prompt is too long", "input is too long", "too many tokens",
    )):
        return f"""Continue the SAME ECLIPSE task in this SAME OpenCode session. The provider rejected the current context length.
Before retrying, compact the conversation:
- Re-read the current Git diff, working tree, backlog and durable handoff.
- Retain the original goal, acceptance criteria, project constraints, decisions, completed work and current error.
- Drop duplicated logs, repeated discussion and unrelated history.
- Do not restart the milestone, discard code, remove requirements or weaken tests.
Then continue from the existing working tree.

Context-limit response:
{clipped}
"""
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
    # Bash sources BASH_ENV for non-interactive commands. Remove all provider/GitHub
    # credentials from the shell and its descendants before the model can run tools.
    scrub_names = (
        "DAHL_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY",
        "GROQ_API_KEY", "OPENROUTER_API_KEY", "TOKENHARBOR_API_KEY", "ZAI_API_KEY",
        "GITHUB_TOKEN", "GH_TOKEN",
    )
    fd, scrub_path = tempfile.mkstemp(prefix="eclipse-bash-scrub-", suffix=".sh")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as scrub_file:
            for name in scrub_names:
                scrub_file.write(f"unset {name}\n")
            scrub_file.write("unset BASH_ENV\n")
        os.chmod(scrub_path, 0o600)
        child_env["BASH_ENV"] = scrub_path
    except Exception:
        try:
            os.unlink(scrub_path)
        except OSError:
            pass
        raise

    command = [
        "opencode", "run", "--standalone", "--format", "json", "--agent", "eclipse-autonomous",
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
    finally:
        try:
            os.unlink(scrub_path)
        except OSError:
            pass


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
            command, cwd=ROOT, env=validation_environment(dict(os.environ)),
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
        cwd=ROOT, env=validation_environment(dict(os.environ)),
        text=True, capture_output=True, check=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT, env=validation_environment(dict(os.environ)),
        text=True, capture_output=True, check=True,
    ).stdout.splitlines()
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT, env=validation_environment(dict(os.environ)),
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
        if path.is_symlink():
            problems.append(f"{name}: symlinks are not allowed in autonomous source PRs")
            continue
        if not path.exists():
            # Only a deleted, previously tracked file requires owner review.
            tracked = subprocess.run(
                ["git", "ls-files", "--error-unmatch", "--", name],
                cwd=ROOT,
                env=validation_environment(dict(os.environ)),
                text=True,
                capture_output=True,
                check=False,
            ).returncode == 0
            protected = protected or tracked
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


def validation_environment(source_env: dict[str, str]) -> dict[str, str]:
    """Environment for tests and local Git inspection; contains no provider or GitHub credentials."""
    allowed = (
        "PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP",
        "APPDATA", "LOCALAPPDATA", "SYSTEMROOT", "WINDIR", "CI",
    )
    env = {key: source_env[key] for key in allowed if key in source_env}
    env["CI"] = "true"
    return env


def gh(
    args: Sequence[str],
    *,
    source_env: dict[str, str],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = validation_environment(source_env)
    token = source_env.get("GITHUB_TOKEN") or source_env.get("GH_TOKEN")
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
    env = validation_environment(source_env)
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
    deadline: float | None = None,
    initial_session_id: str | None = None,
    start_model_id: str | None = None,
) -> tuple[bool, str | None, str, str | None]:
    session_id: str | None = initial_session_id
    skipped_providers: set[str] = set()
    last_failure = ""
    routes = route_models()
    if start_model_id:
        start_index = next((i for i, item in enumerate(routes) if item.open_code_id == start_model_id), 0)
        routes = routes[start_index:]
    for route in routes:
        if deadline is not None and deadline - time.monotonic() < 90:
            return False, session_id, "", last_failure or "Autonomous run time budget reached; checkpoint required."
        if route.provider in skipped_providers:
            continue
        if not source_env.get(route.secret_name):
            skipped_providers.add(route.provider)
            last_failure = f"{route.provider}: missing configured secret {route.secret_name}"
            continue

        context_compacted = False
        for attempt in range(max_calls_per_model):
            if deadline is not None:
                remaining_for_model = int(deadline - time.monotonic() - 45 * 60)
                if remaining_for_model < 60:
                    return False, session_id, "", last_failure or "Autonomous run time budget reached; checkpoint required."
                current_timeout = min(turn_timeout, remaining_for_model)
            else:
                current_timeout = turn_timeout
            current_prompt = (
                prompt if session_id is None
                else build_repair_prompt(last_failure) if last_failure
                else prompt
            )
            result, observed_session = call(
                route, current_prompt, session_id, run_title,
                timeout=current_timeout, source_env=source_env,
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
                if failure.kind == "context_length":
                    if not context_compacted:
                        context_compacted = True
                        attempt -= 1  # context compaction does not consume a retry
                        continue
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


def remote_ci_failure_context(
    pr_url: str, branch: str, source_env: dict[str, str]
) -> str:
    """Collect failed GitHub Actions logs for the exact current PR head."""
    details = json.loads(gh(
        ["pr", "view", pr_url, "--json", "headRefOid"],
        source_env=source_env,
    ).stdout)
    expected_head = details.get("headRefOid")
    runs_result = gh(
        ["run", "list", "--branch", branch, "--limit", "20",
         "--json", "databaseId,headSha,status,conclusion,name"],
        source_env=source_env,
    )
    runs = json.loads(runs_result.stdout or "[]")
    failed = [
        run for run in runs
        if run.get("headSha") == expected_head
        and run.get("status") == "completed"
        and run.get("conclusion") in {"failure", "timed_out", "cancelled", "action_required"}
    ]
    chunks: list[str] = []
    for run in failed[:6]:
        run_id = str(run.get("databaseId", ""))
        if not run_id:
            continue
        logs = gh(["run", "view", run_id, "--log-failed"], source_env=source_env, check=False)
        raw = (logs.stdout or "") + (logs.stderr or "")
        chunks.append(
            f"===== {run.get('name', 'GitHub Actions')} run {run_id} "
            f"({run.get('conclusion')}) =====\n{redact(raw, source_env)[-8_000:]}"
        )
    return "\n\n".join(chunks)[-24_000:]


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


def commit_and_push_worktree(
    branch: str, source_env: dict[str, str]
) -> tuple[list[str], bool, str]:
    """Run controller-side guards, commit and push; never called by the model child."""
    controller_env = validation_environment(source_env)
    paths = changed_paths()
    if not paths:
        return [], False, ""
    safe, message, protected = safety_scan(paths)
    if not safe:
        raise RuntimeError("SAFETY_SCAN_BLOCKED: " + message)

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, env=controller_env,
        text=True, capture_output=True, check=True,
    ).stdout
    if status.strip():
        subprocess.run(["git", "add", "-A"], cwd=ROOT, env=controller_env, check=True)
        subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, env=controller_env, check=True)
        subprocess.run(
            ["git", "-c", "user.name=github-actions[bot]",
             "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
             "commit", "-m", "feat: complete autonomous ECLIPSE milestone"],
            cwd=ROOT, env=controller_env, check=True,
        )

    final_paths = changed_paths()
    safe, message, protected_after = safety_scan(final_paths)
    if not safe:
        raise RuntimeError("SAFETY_SCAN_BLOCKED_AFTER_STAGE: " + message)
    protected = protected or protected_after
    git_with_write_token(["push", "--set-upstream", "origin", branch], source_env=source_env)
    return final_paths, protected, "Controller secret/large-file/diff guards passed."


def create_draft_checkpoint(
    branch: str,
    source_env: dict[str, str],
    session_id: str | None,
    selected_model: str,
    failure: str,
) -> str | None:
    """Preserve safe partial work after exhaustion instead of losing the runner worktree."""
    handoff = ROOT / ".eclipse" / "AUTONOMOUS_SESSION_HANDOFF.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    old = handoff.read_text(encoding="utf-8") if handoff.exists() else "# Autonomous Session Handoff\n"
    handoff.write_text(
        old.rstrip() + "\n\n## Interrupted run checkpoint\n"
        + f"- Run: {source_env.get('GITHUB_RUN_ID', 'unknown')}\n"
        + f"- Session ID: {session_id or 'not created'}\n"
        + f"- Last selected model: {selected_model or 'none'}\n"
        + "- State: BLOCKED; partial changes are preserved for review, not marked complete.\n"
        + f"- Failure (sanitized): {redact(failure, source_env)[-5000:]}\n",
        encoding="utf-8",
    )
    paths, _protected, guard_note = commit_and_push_worktree(branch, source_env)
    if not paths:
        return None
    body = make_pr_body(
        branch, paths,
        guard_note + "\n\n**Checkpoint only:** the autonomous task did not complete. Do not merge this draft as a finished milestone.\n\n"
        + redact(failure, source_env),
        True,
    )
    created = gh(
        ["pr", "create", "--draft", "--base", "main", "--head", branch,
         "--title", "Checkpoint: ECLIPSE autonomous run requires recovery", "--body", body],
        source_env=source_env,
    )
    return created.stdout.strip().splitlines()[-1]


def find_open_autonomous_pr(source_env: dict[str, str]) -> dict[str, object] | None:
    result = gh(
        ["pr", "list", "--state", "open", "--base", "main",
         "--json", "number,title,body,headRefName,isDraft,url,headRefOid"],
        source_env=source_env,
    )
    entries = json.loads(result.stdout or "[]")
    return next(
        (
            item for item in entries
            if str(item.get("headRefName", "")).startswith("feature/eclipse-autonomous-")
        ),
        None,
    )


def resume_existing_pr(
    pr: dict[str, object], source_env: dict[str, str], run_title: str, deadline: float
) -> int:
    """Resume a safe checkpoint PR or repair a failed non-draft autonomous PR."""
    branch = str(pr["headRefName"])
    pr_url = str(pr["url"])
    is_checkpoint = str(pr.get("title", "")).startswith("Checkpoint: ECLIPSE autonomous run")
    is_draft = bool(pr.get("isDraft"))
    if is_draft and not is_checkpoint:
        print(f"OWNER_REVIEW_REQUIRED: protected autonomous PR is open: {pr_url}")
        return 0

    controller_env = validation_environment(source_env)
    subprocess.run(["git", "fetch", "origin", "main", branch], cwd=ROOT, env=controller_env, check=True)
    subprocess.run(
        ["git", "switch", "--force-create", branch, f"origin/{branch}"],
        cwd=ROOT, env=controller_env, check=True,
    )
    subprocess.run(["git", "merge-base", "HEAD", "origin/main"], cwd=ROOT, env=controller_env, check=True)

    check_result = gh(["pr", "checks", pr_url, "--watch", "--fail-fast"], source_env=source_env, check=False)
    if check_result.returncode == 0 and not is_checkpoint:
        paths = changed_paths()
        safe, reason, protected = safety_scan(paths)
        if safe and not protected:
            details = json.loads(gh(
                ["pr", "view", pr_url, "--json", "headRefOid,state,isDraft"],
                source_env=source_env,
            ).stdout)
            local_head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, env=controller_env,
                text=True, capture_output=True, check=True,
            ).stdout.strip()
            if details.get("state") == "OPEN" and not details.get("isDraft") and details.get("headRefOid") == local_head:
                merged = gh(["pr", "merge", pr_url, "--squash", "--delete-branch"], source_env=source_env, check=False)
                if merged.returncode == 0:
                    gh(["workflow", "run", "eclipse-autonomous.yml", "--ref", "main", "-f", "mode=continue"],
                       source_env=source_env, check=False)
                    print(f"Previously open autonomous PR passed checks and was merged: {pr_url}")
                    return 0
        print(f"Open PR checks pass but auto-merge is protected or blocked: {reason or pr_url}")
        return 0

    logs = remote_ci_failure_context(pr_url, branch, source_env)
    if not logs:
        logs = redact(str(pr.get("body", "")), source_env)[-12_000:]
    if not logs:
        logs = redact(check_result.stdout + check_result.stderr, source_env)[-12_000:]
    recovery_prompt = f"""RECOVER THE EXISTING ECLIPSE AUTONOMOUS PR — DO NOT START A NEW BACKLOG ITEM.

You are continuing work on existing PR {pr_url}, branch {branch}, against main.
This PR is a partial-work checkpoint: {is_checkpoint}. Read the current diff, AUTONOMOUS_BACKLOG.md,
.eclipse/AUTONOMOUS_SESSION_HANDOFF.md, STATUS.md, CONTINUATION.md and relevant tests.
Preserve all correct work already in this branch. If it is a partial checkpoint, continue the
same highest-priority unfinished milestone to completion. If it is a failed non-draft PR,
fix the actual failing checks. Add regression coverage and record evidence. Do not create another
branch or another PR, do not commit/push/merge, and do not weaken tests. The parent controller
commits/pushes this same branch and runs checks.

This is a recovered process. The old in-memory session may not exist on this runner. Treat the
branch, commits, sanitized handoff and logs as the authoritative checkpoint. Reuse an old native
session only if it is available and valid; otherwise create a new session and preserve task continuity
from the repository checkpoint.

Prior PR/checkpoint evidence:
{logs[-20_000:]}
"""
    success, session_id, selected_model, failure = run_agent_with_failover(
        recovery_prompt,
        run_title + " recover existing PR",
        source_env,
        turn_timeout=DEFAULT_TURN_TIMEOUT,
        deadline=deadline,
    )
    if not success:
        print("EXISTING_PR_RECOVERY_BLOCKED")
        print(redact(failure or "", source_env)[-8_000:])
        return 4

    try:
        paths, protected, guard_note = commit_and_push_worktree(branch, source_env)
    except Exception as exc:
        print(f"EXISTING_PR_RECOVERY_SAFETY_BLOCKED: {type(exc).__name__}: {exc}")
        return 4
    if not paths:
        print("Existing PR recovery produced no safe changes; PR remains open.")
        return 4

    for repair_round in range(5):
        checks = gh(["pr", "checks", pr_url, "--watch", "--fail-fast"], source_env=source_env, check=False)
        if checks.returncode == 0:
            break
        logs = remote_ci_failure_context(pr_url, branch, source_env)
        if not logs:
            print("Existing PR still fails CI; no fresh failure logs available. Leaving open.")
            return 4
        repaired, session_id, selected_model, failure = run_agent_with_failover(
            build_repair_prompt("Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n" + logs),
            run_title + f" recover PR CI {repair_round + 1}",
            source_env,
            turn_timeout=DEFAULT_TURN_TIMEOUT,
            deadline=deadline,
            initial_session_id=session_id,
            start_model_id=selected_model,
        )
        if not repaired:
            print("Existing PR CI repair exhausted the approved free-model routes.")
            print(redact(failure or "", source_env)[-8_000:])
            return 4
        new_paths, new_protected, guard_note = commit_and_push_worktree(branch, source_env)
        protected = protected or new_protected
        if not new_paths:
            print("Existing PR CI repair produced no new changes; leaving PR open.")
            return 4

    checks = gh(["pr", "checks", pr_url, "--watch", "--fail-fast"], source_env=source_env, check=False)
    if checks.returncode != 0:
        print("Existing PR remains failing after the repair limit; no merge performed.")
        return 4

    paths = changed_paths()
    safe, reason, path_protected = safety_scan(paths)
    protected = protected or path_protected
    if not safe:
        print(f"Existing PR safety scan failed: {reason}; leaving open.")
        return 4
    if protected:
        print(f"OWNER_REVIEW_REQUIRED: recovered PR changes protected paths: {pr_url}")
        return 0

    if is_checkpoint:
        ready = gh(["pr", "ready", pr_url], source_env=source_env, check=False)
        if ready.returncode != 0:
            print("CHECKPOINT_PR_COULD_NOT_BE_MARKED_READY; leaving draft.")
            print(redact(ready.stdout + ready.stderr, source_env)[-4_000:])
            return 5

    details = json.loads(gh(["pr", "view", pr_url, "--json", "headRefOid,state,isDraft"], source_env=source_env).stdout)
    local_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, env=controller_env,
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    if details.get("state") != "OPEN" or details.get("isDraft") or details.get("headRefOid") != local_head:
        print("Existing PR head changed or is not mergeable; no merge performed.")
        return 5
    merged = gh(["pr", "merge", pr_url, "--squash", "--delete-branch"], source_env=source_env, check=False)
    if merged.returncode != 0:
        print("Existing PR auto-merge remains blocked.")
        print(redact(merged.stdout + merged.stderr, source_env)[-6_000:])
        return 6
    gh(["workflow", "run", "eclipse-autonomous.yml", "--ref", "main", "-f", "mode=continue"],
       source_env=source_env, check=False)
    print(f"Recovered, verified and merged existing autonomous PR: {pr_url}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-agent-minutes", type=int, default=int(os.getenv("ECLIPSE_MAX_AGENT_MINUTES", "240")))
    args = parser.parse_args()
    source_env = dict(os.environ)
    run_id = source_env.get("GITHUB_RUN_ID", str(int(time.time())))
    attempt_id = source_env.get("GITHUB_RUN_ATTEMPT", "1")
    base_branch = source_env.get("ECLIPSE_BASE_BRANCH", source_env.get("GITHUB_REF_NAME", "main"))
    run_title = f"ECLIPSE autonomous milestone {run_id}-{attempt_id}"
    deadline = time.monotonic() + args.max_agent_minutes * 60

    existing_pr = find_open_autonomous_pr(source_env)
    if existing_pr:
        return resume_existing_pr(existing_pr, source_env, run_title, deadline)

    controller_env = validation_environment(source_env)
    subprocess.run(["git", "fetch", "origin", base_branch], cwd=ROOT, env=controller_env, check=True)
    subprocess.run(["git", "switch", "--detach", f"origin/{base_branch}"], cwd=ROOT, env=controller_env, check=True)
    branch = f"feature/eclipse-autonomous-{run_id}-{attempt_id}"
    subprocess.run(["git", "switch", "-c", branch], cwd=ROOT, env=controller_env, check=True)

    success, session_id, selected_model, failure = run_agent_with_failover(
        build_run_prompt(run_title),
        run_title,
        source_env,
        turn_timeout=DEFAULT_TURN_TIMEOUT,
        deadline=deadline,
    )

    if not success:
        print("BLOCKED_NO_FREE_MODEL_OR_RECOVERABLE_SESSION")
        print(redact(failure, source_env))
        try:
            checkpoint_pr = create_draft_checkpoint(
                branch, source_env, session_id, selected_model, failure or "No completed milestone."
            )
            if checkpoint_pr:
                print(f"PARTIAL_WORK_PRESERVED_AS_DRAFT: {checkpoint_pr}")
            else:
                print("No safe partial code changes existed to checkpoint.")
        except Exception as exc:
            print(f"CHECKPOINT_PRESERVATION_FAILED: {type(exc).__name__}: {exc}")
        return 2

    paths = changed_paths()
    if not paths:
        print("No repository changes were produced. No empty PR created.")
        return 0

    try:
        final_paths, protected, guard_note = commit_and_push_worktree(branch, source_env)
    except Exception as exc:
        print(f"SAFE_COMMIT_BLOCKED: {type(exc).__name__}: {exc}")
        return 3
    if not final_paths:
        print("No changes remained after validation.")
        return 0

    validation_note = (
        "Portable validation passed: compileall, provider configuration validator, "
        "full unittest discovery and git diff whitespace check. Windows CI remains the required merge gate.\n"
        + guard_note
    )
    body = make_pr_body(branch, final_paths, validation_note, protected)
    create_args = [
        "pr", "create", "--base", "main", "--head", branch,
        "--title", "ECLIPSE autonomous milestone", "--body", body,
    ]
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
    for repair_round in range(5):
        if checks.returncode == 0:
            break
        failure_context = remote_ci_failure_context(pr_url, branch, source_env)
        if not failure_context:
            print("CI_NOT_GREEN: no failed-run logs could be retrieved; preserving PR without merge.")
            print(redact(checks.stdout + checks.stderr, source_env)[-8_000:])
            return 4
        repair_prompt = build_repair_prompt(
            "The PR's Windows/GitHub Actions checks failed. Repair the real failure in this same "
            "OpenCode session and current feature branch. Keep all existing successful work.\n\n"
            + failure_context
        )
        repaired, session_id, selected_model, repair_failure = run_agent_with_failover(
            repair_prompt,
            run_title + f" CI repair {repair_round + 1}",
            source_env,
            turn_timeout=DEFAULT_TURN_TIMEOUT,
            deadline=deadline,
            initial_session_id=session_id,
            start_model_id=selected_model,
        )
        if not repaired:
            print("CI_REPAIR_EXHAUSTED: PR remains open and will not be merged.")
            print(redact(repair_failure or "", source_env)[-8_000:])
            return 4
        try:
            repair_paths, repair_protected, guard_note = commit_and_push_worktree(branch, source_env)
        except Exception as exc:
            print(f"CI_REPAIR_SAFETY_BLOCKED: {type(exc).__name__}: {exc}")
            return 4
        if not repair_paths:
            print("CI_REPAIR_MADE_NO_CHANGES: PR remains open and will not be merged.")
            return 4
        protected = protected or repair_protected
        print(f"CI repair {repair_round + 1} committed by controller; updated paths: {len(repair_paths)}")
        checks = gh(["pr", "checks", pr_url, "--watch", "--fail-fast"], source_env=source_env, check=False)

    if checks.returncode != 0:
        print("CI_NOT_GREEN_AFTER_REPAIR_LIMIT: PR remains open and will not be merged.")
        print(redact(checks.stdout + checks.stderr, source_env)[-8_000:])
        return 4

    if protected:
        print("OWNER_REVIEW_REQUIRED: protected automation/security paths changed; CI passed but PR intentionally remains draft.")
        return 0

    details = json.loads(gh(["pr", "view", pr_url, "--json", "headRefOid,state,isDraft"], source_env=source_env).stdout)
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, env=controller_env,
        text=True, capture_output=True, check=True,
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
    dispatch = gh(
        ["workflow", "run", "eclipse-autonomous.yml", "--ref", "main", "-f", "mode=continue"],
        source_env=source_env, check=False,
    )
    if dispatch.returncode == 0:
        print("NEXT_AUTONOMOUS_RUN_QUEUED")
    else:
        print("NEXT_RUN_NOT_QUEUED; main push/six-hour schedule will resume the backlog.")
        print(redact(dispatch.stdout + dispatch.stderr, source_env)[-4_000:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
