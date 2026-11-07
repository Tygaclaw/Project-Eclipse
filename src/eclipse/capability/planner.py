"""Structured planning with acceptance criteria and drift signals.

The planner builds a durable, inspectable plan. It is heuristic and local so a
plan exists before any model call; the executing model fills in the work, and
verification evidence — not the plan text — decides completion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Mapping


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Objective:
    id: str
    title: str
    acceptance_criteria: list[str]
    verification: str
    status: str = "pending"
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "acceptance_criteria": list(self.acceptance_criteria),
            "verification": self.verification,
            "status": self.status,
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Objective":
        return cls(
            id=str(payload.get("id") or "o1"),
            title=str(payload.get("title") or "Objective"),
            acceptance_criteria=[str(item) for item in payload.get("acceptance_criteria") or []],
            verification=str(payload.get("verification") or ""),
            status=str(payload.get("status") or "pending"),
            evidence=[str(item) for item in payload.get("evidence") or []],
        )


@dataclass
class Plan:
    goal: str
    mode: str
    risk: str
    constraints: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    objectives: list[Objective] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    likely_files: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    checkpoints: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "mode": self.mode,
            "risk": self.risk,
            "constraints": list(self.constraints),
            "non_goals": list(self.non_goals),
            "objectives": [objective.to_dict() for objective in self.objectives],
            "dependencies": list(self.dependencies),
            "likely_files": list(self.likely_files),
            "assumptions": list(self.assumptions),
            "unknowns": list(self.unknowns),
            "checkpoints": list(self.checkpoints),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Plan":
        return cls(
            goal=str(payload.get("goal") or ""),
            mode=str(payload.get("mode") or "balanced"),
            risk=str(payload.get("risk") or "low"),
            constraints=[str(item) for item in payload.get("constraints") or []],
            non_goals=[str(item) for item in payload.get("non_goals") or []],
            objectives=[Objective.from_dict(item) for item in payload.get("objectives") or [] if isinstance(item, Mapping)],
            dependencies=[str(item) for item in payload.get("dependencies") or []],
            likely_files=[str(item) for item in payload.get("likely_files") or []],
            assumptions=[str(item) for item in payload.get("assumptions") or []],
            unknowns=[str(item) for item in payload.get("unknowns") or []],
            checkpoints=[str(item) for item in payload.get("checkpoints") or []],
            created_at=str(payload.get("created_at") or utc_now_iso()),
        )

    def progress(self) -> dict[str, Any]:
        total = len(self.objectives)
        done = sum(1 for objective in self.objectives if objective.status == "done")
        failed = sum(1 for objective in self.objectives if objective.status == "failed")
        return {
            "total": total,
            "done": done,
            "failed": failed,
            "pending": total - done - failed,
            "fraction": (done / total) if total else 0.0,
        }

    def drift_signals(self) -> list[str]:
        """Report objectives that claim completion without evidence."""

        signals = []
        for objective in self.objectives:
            if objective.status == "done" and not objective.evidence:
                signals.append(f"{objective.id}: marked done without recorded evidence.")
            if objective.status == "pending" and objective.id == "verify" and self.mode != "fast":
                continue
        return signals


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_.-]{3,}", text.lower())}


def _guess_files(goal: str, workspace_files: list[str], limit: int = 8) -> list[str]:
    keywords = _tokens(goal)
    scored: list[tuple[int, str]] = []
    for name in workspace_files:
        lowered = name.lower()
        score = sum(1 for keyword in keywords if keyword in lowered)
        if score:
            scored.append((score, name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in scored[:limit]]


def build_plan(
    goal: str,
    assessment: Any,
    *,
    workspace_files: list[str] | None = None,
    project_root: str | None = None,
) -> Plan:
    """Create a dependency-ordered plan from a goal and watchdog assessment."""

    goal_text = (goal or "").strip()
    if not goal_text:
        raise ValueError("A task goal is required")
    objective_list: list[Objective] = []

    mode = getattr(assessment, "mode", "balanced")
    risk = getattr(assessment, "risk", "low")
    requires_verification = bool(getattr(assessment, "requires_verification", False))
    likely = _guess_files(goal_text, workspace_files or [])

    if mode == "fast":
        objective_list.append(
            Objective(
                id="answer",
                title="Answer the request using approved read-only context",
                acceptance_criteria=[
                    "The answer addresses the exact request.",
                    "Any claim about local code cites inspected files.",
                ],
                verification="Review the cited file paths and line references.",
            )
        )
    else:
        objective_list.append(
            Objective(
                id="inspect",
                title="Inspect the relevant project context before changing anything",
                acceptance_criteria=[
                    "The files that own the behaviour are identified.",
                    "Existing conventions and constraints are recorded.",
                ],
                verification="List the inspected files with observed facts.",
            )
        )
        objective_list.append(
            Objective(
                id="implement",
                title="Implement the requested change in scoped files",
                acceptance_criteria=[
                    "The change matches the goal and does not add unrelated behaviour.",
                    "Existing working behaviour is preserved.",
                ],
                verification="Review the diff and run the affected checks.",
            )
        )
        if requires_verification:
            objective_list.append(
                Objective(
                    id="verify",
                    title="Verify the change with independent checks",
                    acceptance_criteria=[
                        "The relevant test or compile check passes on the changed files.",
                        "A failing check is reported, not hidden.",
                    ],
                    verification="Run the project's compile and test commands and record output.",
                )
            )
        if risk == "high":
            objective_list.append(
                Objective(
                    id="safety",
                    title="Confirm the risky action is reversible and approved",
                    acceptance_criteria=[
                        "A rollback path exists for every destructive or irreversible action.",
                        "Consequential actions received explicit approval.",
                    ],
                    verification="Record the approval decisions and rollback path.",
                )
            )

    plan = Plan(
        goal=goal_text,
        mode=mode,
        risk=risk,
        constraints=[
            "Work only inside the approved project workspace.",
            "Never modify files outside the approved root.",
            "Do not claim success without evidence from a real command or test.",
            "Original model checkpoints remain read-only.",
        ],
        non_goals=[
            "Unrequested refactors or cosmetic rewrites.",
            "Installing dependencies or changing system settings without approval.",
        ],
        objectives=objective_list,
        dependencies=[project_root] if project_root else [],
        likely_files=likely,
        assumptions=[
            "The project workspace is the only writable root for this task.",
        ],
        unknowns=[] if likely else ["No existing files obviously match the goal; inspection comes first."],
        checkpoints=[
            "After inspection: record observed facts before editing.",
            "After implementation: run the verification command.",
        ],
    )
    plan.drift_signals()
    return plan


def mark_objective(
    plan: Plan, objective_id: str, status: str, evidence: list[str] | None = None
) -> None:
    for objective in plan.objectives:
        if objective.id == objective_id:
            objective.status = status
            if evidence:
                objective.evidence.extend(evidence)
            return
    raise KeyError(f"Unknown objective: {objective_id}")
