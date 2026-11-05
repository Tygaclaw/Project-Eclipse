#!/usr/bin/env python3
"""Low-cost, transition-only monitor for the ECLIPSE OpenCode run and Dahl capacity.

The monitor probes Dahl only while an OpenCode GitHub Actions run is queued or
in progress. It posts to Issue #2 only when the recorded state changes.
Secrets are read from the environment and are never printed.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]
DAHL_KEY = os.environ.get("DAHL_API_KEY", "")
ISSUE_NUMBER = int(os.environ.get("MONITOR_ISSUE_NUMBER", "2"))
API_ROOT = "https://api.github.com"
MODEL = "deepseek-ai/DeepSeek-V4-Flash-0731"
MARKER_RE = re.compile(r"<!-- eclipse-dahl-monitor-v1 (\{.*?\}) -->", re.S)


def api_request(method: str, path: str, payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        API_ROOT + path,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "eclipse-dahl-monitor",
            **({"Content-Type": "application/json"} if data is not None else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else None


def probe_dahl() -> tuple[str, str]:
    if not DAHL_KEY:
        return "secret_missing", "The DAHL_API_KEY repository secret is not available to this workflow."
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "max_tokens": 1,
        "stream": False,
    }
    req = urllib.request.Request(
        "https://inference.dahl.global/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {DAHL_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "eclipse-dahl-capacity-probe",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            response.read()
            return "available", "The small DeepSeek V4 Flash test request succeeded."
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}
        err = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = str(err.get("message") or payload.get("message") or raw[:300])
        code = str(err.get("code", ""))
        if exc.code == 429 and (code == "model_concurrency" or "concurrency capacity" in message.lower()):
            return "busy", "Dahl returned HTTP 429: DeepSeek V4 Flash is at concurrency capacity."
        if exc.code in (401, 403):
            return "auth_error", f"Dahl rejected the API credential (HTTP {exc.code}); the secret was not displayed."
        if exc.code == 429:
            return "rate_limited", f"Dahl returned HTTP 429: {message[:240]}"
        return "provider_error", f"Dahl returned HTTP {exc.code}: {message[:240]}"
    except Exception as exc:  # network/TLS/timeout errors are useful monitor state
        return "network_error", f"The Dahl availability check could not complete: {type(exc).__name__}."


def main() -> int:
    runs_response = api_request(
        "GET",
        f"/repos/{REPO}/actions/workflows/opencode.yml/runs?per_page=10",
    )
    runs = runs_response.get("workflow_runs", [])
    active_runs = [r for r in runs if r.get("status") in ("queued", "in_progress")]
    active_runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)

    latest = active_runs[0] if active_runs else (runs[0] if runs else None)
    if latest is None:
        print("No OpenCode GitHub Actions runs were found; no Dahl probe was made.")
        return 0

    is_active = latest.get("status") in ("queued", "in_progress")
    if is_active:
        dahl_state, dahl_detail = probe_dahl()
    else:
        dahl_state = "not_probed"
        dahl_detail = "No OpenCode run is currently queued or running; the monitor did not spend a Dahl request."

    state = {
        "run_id": latest.get("id"),
        "run_status": latest.get("status"),
        "run_conclusion": latest.get("conclusion"),
        "dahl": dahl_state,
        "active": is_active,
    }

    comments = api_request(
        "GET",
        f"/repos/{REPO}/issues/{ISSUE_NUMBER}/comments?per_page=100&sort=created&direction=desc",
    )
    previous = None
    for comment in comments:
        match = MARKER_RE.search(comment.get("body", ""))
        if match:
            try:
                previous = json.loads(match.group(1))
                break
            except json.JSONDecodeError:
                continue

    print("Monitor state: " + json.dumps(state, sort_keys=True))
    if previous == state:
        print("No change since the previous check; no issue comment posted.")
        return 0

    checked = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    marker = "<!-- eclipse-dahl-monitor-v1 " + json.dumps(state, sort_keys=True, separators=(",", ":")) + " -->"

    if is_active:
        run_line = f"OpenCode run [#{latest['run_number']}]({latest['html_url']}) is **{latest['status']}**."
        dahl_label = {
            "available": "AVAILABLE",
            "busy": "AT CAPACITY",
            "rate_limited": "RATE LIMITED",
            "auth_error": "AUTHENTICATION ERROR",
            "secret_missing": "SECRET MISSING",
            "provider_error": "PROVIDER ERROR",
            "network_error": "NETWORK CHECK FAILED",
        }.get(dahl_state, dahl_state.upper())
        detail = dahl_detail
        if dahl_state == "available":
            next_step = "The monitor did not launch another coding agent; the active OpenCode run remains responsible for its task."
        elif dahl_state == "busy":
            next_step = "The active OpenCode run may retry independently. This monitor will check again in about 10 minutes."
        else:
            next_step = "Review the detail above before changing repository settings."
        body = (
            f"{marker}\n"
            f"## ECLIPSE monitor update — {checked}\n\n"
            f"- **OpenCode:** {run_line}\n"
            f"- **Dahl DeepSeek V4 Flash:** **{dahl_label}**\n"
            f"- **Check:** {detail}\n\n"
            f"{next_step}"
        )
    else:
        conclusion = latest.get("conclusion") or latest.get("status")
        body = (
            f"{marker}\n"
            f"## ECLIPSE monitor update — {checked}\n\n"
            f"- **Latest OpenCode run:** [#{latest['run_number']}]({latest['html_url']}) is **{conclusion}**.\n"
            f"- **Dahl DeepSeek V4 Flash:** not probed because there is no active OpenCode run.\n\n"
            "The 10-minute capacity checks will resume automatically when a new OpenCode run starts."
        )

    api_request(
        "POST",
        f"/repos/{REPO}/issues/{ISSUE_NUMBER}/comments",
        {"body": body},
    )
    print("State changed; posted a status update to Issue #" + str(ISSUE_NUMBER))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Avoid dumping request headers or environment values into Actions logs.
        print(f"Monitor failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
