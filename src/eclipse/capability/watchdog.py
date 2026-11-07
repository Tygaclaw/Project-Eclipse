"""Capability Watchdog: decide how much process a task actually justifies.

A simple factual question must not trigger a six-stage workflow, while a large
application change should. The watchdog is deliberately deterministic: its
routing can be inspected, tested and explained instead of being a hidden model
decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

MODES = ("fast", "balanced", "enhanced", "auto")

_HIGH_RISK = (
    "delete",
    "drop table",
    "destroy",
    "force push",
    "production",
    "deploy",
    "migrate",
    "credentials",
    "secret",
    "api key",
    "payment",
    "billing",
    "permission",
    "registry",
    "install",
    "uninstall",
    "overwrite",
    "truncate",
)
_ELEVATED_RISK = (
    "refactor",
    "redesign",
    "architecture",
    "multiple files",
    "multi-file",
    "integration",
    "security",
    "performance",
    "optimise",
    "optimize",
    "database",
    "migration",
    "dependency",
)
_COMPLEX = (
    "implement",
    "build",
    "create",
    "add feature",
    "debug",
    "fix",
    "test",
    "refactor",
    "analyse",
    "analyze",
    "research",
    "compare",
    "plan",
    "write",
    "run",
    "verify",
    "review",
    "explain how",
)
_TRIVIAL = (
    "what is",
    "who is",
    "define",
    "translate",
    "summarise",
    "summarize",
    "hello",
    "hi",
    "thanks",
    "capital of",
)

_FULL_TOOLS = (
    "list_dir",
    "read_file",
    "search_text",
    "write_file",
    "run_command",
    "knowledge_search",
    "correction_lookup",
    "verify",
)
_LIGHT_TOOLS = ("read_file", "list_dir", "search_text", "knowledge_search")


@dataclass(frozen=True, slots=True)
class TaskAssessment:
    mode: str
    risk: str
    complexity: int
    requires_verification: bool
    allows_writes: bool
    allows_commands: bool
    max_steps: int
    tools: tuple[str, ...]
    rationale: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "risk": self.risk,
            "complexity": self.complexity,
            "requires_verification": self.requires_verification,
            "allows_writes": self.allows_writes,
            "allows_commands": self.allows_commands,
            "max_steps": self.max_steps,
            "tools": list(self.tools),
            "rationale": list(self.rationale),
        }


def classify_task(goal: str, *, mode: str = "auto") -> TaskAssessment:
    """Classify a task into a process level, tools and a step budget."""

    text = (goal or "").strip().lower()
    if mode not in MODES:
        raise ValueError(f"Unknown watchdog mode: {mode}")
    words = re.findall(r"[a-z0-9_+.]+", text)
    rationale: list[str] = []

    risk = "low"
    for phrase in _HIGH_RISK:
        if phrase in text:
            risk = "high"
            rationale.append(f"High-risk phrase detected: '{phrase}'.")
            break
    if risk == "low":
        for phrase in _ELEVATED_RISK:
            if phrase in text:
                risk = "elevated"
                rationale.append(f"Elevated-risk phrase detected: '{phrase}'.")
                break

    complexity = 0
    if len(words) > 12:
        complexity += 1
    if len(words) > 40:
        complexity += 1
    if any(phrase in text for phrase in _COMPLEX):
        complexity += 2
    if any(phrase in text for phrase in ("plan", "multiple", "tests", "verify", "then")):
        complexity += 1
    if risk == "elevated":
        complexity += 1
    if risk == "high":
        complexity += 2

    trivial = any(text.startswith(phrase) or f" {phrase}" in text for phrase in _TRIVIAL)
    if trivial and complexity <= 2:
        complexity = max(0, complexity - 2)
        rationale.append("The request looks like a simple question.")

    resolved = mode
    if mode == "auto":
        if risk == "high" or complexity >= 5:
            resolved = "enhanced"
        elif complexity >= 2:
            resolved = "balanced"
        else:
            resolved = "fast"
        rationale.append(f"Auto resolved to '{resolved}' from risk and complexity.")

    if resolved == "fast":
        tools = _LIGHT_TOOLS
        max_steps = 2
        verification = False
        writes = False
        commands = False
        rationale.append("Fast mode uses read-only tools and no mandatory verification.")
    elif resolved == "balanced":
        tools = ("list_dir", "read_file", "search_text", "write_file", "run_command", "knowledge_search", "correction_lookup")
        max_steps = 6
        verification = complexity >= 2
        writes = True
        commands = True
        rationale.append("Balanced mode allows scoped writes and commands with approval.")
    else:
        tools = _FULL_TOOLS
        max_steps = 12
        verification = True
        writes = True
        commands = True
        rationale.append("Enhanced mode requires independent verification and more steps.")

    if risk == "high":
        rationale.append("High-risk work always needs explicit approval and verification.")
        verification = True

    return TaskAssessment(
        mode=resolved,
        risk=risk,
        complexity=min(complexity, 10),
        requires_verification=verification,
        allows_writes=writes,
        allows_commands=commands,
        max_steps=max_steps,
        tools=tuple(tools),
        rationale=tuple(rationale),
    )
