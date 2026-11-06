#!/usr/bin/env python3
"""GitHub-only, transition-based monitor for the ECLIPSE OpenCode run.

This monitor never calls a model API, so it does not consume provider allowance.
Secrets are read from the environment and are never printed.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]
ISSUE_NUMBER = int(os.environ.get("MONITOR_ISSUE_NUMBER", "2"))
API_ROOT = "https://api.github.com"
MARKER_RE = re.compile(r"<!-- eclipse-agent-monitor-v1 (\\{.*?\\}) -->", re.S)


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
            "User-Agent": "eclipse-agent-monitor",
            **({"Content-Type": "application/json"} if data is not None else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else None


def main() -> int:
    runs_response = api_request(
        "GET",
        f"/repos/{REPO}/actions/workflows/opencode.yml/runs?per_page=10",
    )
    runs = runs_response.get("workflow_runs", [])
    active_runs = [run for run in runs if run.get("status") in ("queued", "in_progress")]
    active_runs.sort(key=lambda run: run.get("created_at", ""), reverse=True)
    latest = active_runs[0] if active_runs else (runs[0] if runs else None)

    state = {
        "run_id": latest.get("id") if latest else None,
        "run_status": latest.get("status") if latest else "not_found",
        "run_conclusion": latest.get("conclusion") if latest else None,
        "active": bool(latest and latest.get("status") in ("queued", "in_progress")),
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

    print("GitHub-only monitor state: " + json.dumps(state, sort_keys=True))
    if previous == state:
        print("No status change; no issue comment posted.")
        return 0

    checked = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    marker = "<!-- eclipse-agent-monitor-v1 " + json.dumps(
        state, sort_keys=True, separators=(",", ":")
    ) + " -->"

    if latest is None:
        body = (
            f"{marker}\\n"
            f"## ECLIPSE monitor update — {checked}\\n\\n"
            "- No OpenCode workflow runs were found.\\n"
            "- This monitor checks GitHub only and makes no model API requests."
        )
    elif state["active"]:
        body = (
            f"{marker}\\n"
            f"## ECLIPSE monitor update — {checked}\\n\\n"
            f"- OpenCode run [#{latest['run_number']}]({latest['html_url']}) is "
            f"**{latest['status']}**.\\n"
            "- This monitor checks GitHub only; it does not send test prompts or consume model allowance."
        )
    else:
        conclusion = latest.get("conclusion") or latest.get("status")
        body = (
            f"{marker}\\n"
            f"## ECLIPSE monitor update — {checked}\\n\\n"
            f"- Latest OpenCode run [#{latest['run_number']}]({latest['html_url']}) is "
            f"**{conclusion}**.\\n"
            "- This monitor checks GitHub only; it does not send test prompts or consume model allowance."
        )

    api_request(
        "POST",
        f"/repos/{REPO}/issues/{ISSUE_NUMBER}/comments",
        {"body": body},
    )
    print(f"Status changed; posted an update to Issue #{ISSUE_NUMBER}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Avoid dumping request headers or environment values into Actions logs.
        print(f"Monitor failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
