"""Capability Engine: plan, execute, verify, recover and record lessons.

This is the practical system-intelligence layer. It gives a connected model a
durable plan, scoped tools, independent verification and a bounded repair loop.
Completion is decided by command evidence, not by the model's own claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any, Callable, Mapping, Sequence

from eclipse.core.config import AppPaths
from eclipse.core.events import EventBus
from eclipse.core.security import PermissionBroker
from eclipse.core.storage import Store
from eclipse.runtime.client import CancellationToken, ChatError, ChatMessage
from .execution import LoopResult, ToolEvent, run_tool_loop
from .knowledge import KnowledgeBase
from .memory import CorrectionMemory, MemoryError
from .planner import Objective, Plan, build_plan, mark_objective
from .research import ProjectIndex, detect_project_stack, list_workspace_files
from .tools import ToolRegistry, ToolResult
from .verification import VerificationEngine
from .watchdog import TaskAssessment, classify_task


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CapabilityError(Exception):
    """Base class for expected capability-run failures."""


class RuntimeUnavailable(CapabilityError):
    """No inference runtime is ready for a capability task."""


@dataclass
class TaskRun:
    task_id: str
    status: str
    summary: str
    plan: dict[str, Any]
    evidence: list[dict[str, Any]] = field(default_factory=list)
    verification: list[dict[str, Any]] = field(default_factory=list)
    stopped_reason: str = "complete"
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    assessment: dict[str, Any] = field(default_factory=dict)
    correction_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "summary": self.summary,
            "plan": self.plan,
            "evidence": self.evidence,
            "verification": self.verification,
            "stopped_reason": self.stopped_reason,
            "tool_events": self.tool_events,
            "assessment": self.assessment,
            "correction_id": self.correction_id,
        }


class CapabilityEngine:
    """Shared, permissioned execution for complex tasks."""

    def __init__(
        self,
        store: Store,
        runtime: Any,
        paths: AppPaths,
        *,
        events: EventBus | None = None,
        memory: CorrectionMemory | None = None,
        knowledge: KnowledgeBase | None = None,
        workspace_root: str | os.PathLike[str] | None = None,
    ) -> None:
        self.store = store
        self.runtime = runtime
        self.paths = paths
        self.events = events or EventBus()
        self.memory = memory or CorrectionMemory(store)
        self.knowledge = knowledge
        self.workspace_root = str(workspace_root) if workspace_root else None
        self.verifier = VerificationEngine()
        self._lock = threading.RLock()

    def set_workspace(self, root: str | os.PathLike[str] | None) -> None:
        self.workspace_root = str(root) if root else None

    # -- planning --------------------------------------------------------

    def create_task(
        self,
        goal: str,
        *,
        mode: str = "auto",
        workspace_root: str | os.PathLike[str] | None = None,
    ) -> dict[str, Any]:
        workspace = str(workspace_root or self.workspace_root or "") or None
        assessment = classify_task(goal, mode=mode)
        files: list[str] = []
        if workspace:
            try:
                files = list_workspace_files(workspace, limit=800)
            except Exception:  # noqa: BLE001 - a missing workspace is reported later
                files = []
        plan = build_plan(goal, assessment, workspace_files=files, project_root=workspace)
        task = self.store.create_task(
            goal=goal,
            mode=assessment.mode,
            plan={**plan.to_dict(), "assessment": assessment.to_dict()},
            status="planned",
            project_root=workspace or "",
        )
        self.events.emit("task.created", task_id=task["id"], goal=goal, mode=assessment.mode)
        return task

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self.store.get_task(task_id)

    def list_tasks(self) -> list[dict[str, Any]]:
        return self.store.list_tasks()

    # -- execution -------------------------------------------------------

    def run_task(
        self,
        task_id: str,
        *,
        cancel: CancellationToken | None = None,
        approver: Callable[[str, str, str], bool] | None = None,
        workspace_root: str | os.PathLike[str] | None = None,
    ) -> TaskRun:
        task = self.store.get_task(task_id)
        if task is None:
            raise CapabilityError("Unknown task")
        cancel = cancel or CancellationToken()
        workspace = str(workspace_root or task.get("project_root") or self.workspace_root or "") or None
        if not workspace or not Path(workspace).exists():
            raise CapabilityError(
                "This task needs an existing project workspace. Choose a folder first."
            )
        try:
            self.runtime.require_ready()
        except ChatError as exc:
            self.store.update_task(task_id, status="needs_attention")
            raise RuntimeUnavailable(str(exc)) from exc

        assessment_payload = (task["plan"] or {}).get("assessment") or {}
        assessment = TaskAssessment(
            mode=assessment_payload.get("mode", task["mode"]),
            risk=assessment_payload.get("risk", "low"),
            complexity=int(assessment_payload.get("complexity", 0)),
            requires_verification=bool(assessment_payload.get("requires_verification", True)),
            allows_writes=bool(assessment_payload.get("allows_writes", True)),
            allows_commands=bool(assessment_payload.get("allows_commands", True)),
            max_steps=int(assessment_payload.get("max_steps", 8)),
            tools=tuple(assessment_payload.get("tools") or ()),
            rationale=tuple(assessment_payload.get("rationale") or ()),
        )
        plan_payload = dict(task["plan"])
        plan_payload.pop("assessment", None)
        plan = Plan.from_dict(plan_payload)

        broker = PermissionBroker(
            [workspace],
            allow_write=assessment.allows_writes,
            allow_commands=assessment.allows_commands,
            approver=approver,
            command_timeout_seconds=int(self.runtime.settings.get("command_timeout_seconds", 120)),
        )
        tools = ToolRegistry(
            broker,
            workspace,
            store=self.store,
            knowledge=self.knowledge,
            verifier=self.verifier,
            events=self.events,
        )
        self.store.update_task(task_id, status="running")
        self.events.emit("task.status", task_id=task_id, status="running")
        evidence: list[dict[str, Any]] = []
        tool_events: list[dict[str, Any]] = []
        verification: list[dict[str, Any]] = []
        stopped_reason = "complete"
        summary = ""
        correction_id = None

        def record(message: str, kind: str = "note") -> None:
            evidence.append({"kind": kind, "message": message, "at": utc_now_iso()})

        try:
            context = self._context_block(workspace, plan, task["goal"])
            system = ChatMessage(role="system", content=context)
            user = ChatMessage(
                role="user",
                content=(
                    f"Goal: {task['goal']}\n\n"
                    "Execute this plan using the available tools. Read the relevant files "
                    "before editing. Make coherent, scoped changes. When you are done, reply "
                    "with a short factual summary of what you changed and what you verified. "
                    "Never claim a check passed unless a tool returned its output."
                ),
            )
            loop = run_tool_loop(
                runtime=self.runtime,
                messages=[system, user],
                tool_schemas=tools.schemas(assessment.tools),
                tool_caller=tools.call,
                max_steps=assessment.max_steps,
                cancel=cancel,
                on_delta=lambda text: self.events.emit("task.delta", task_id=task_id, text=text),
                on_tool=lambda event: self._on_tool(task_id, event, tool_events, record),
                on_step=lambda step: self.events.emit("task.step", task_id=task_id, step=step),
            )
            summary = loop.text.strip()
            stopped_reason = loop.stopped_reason
            record(f"Model loop finished with reason '{loop.stopped_reason}' after {loop.steps} step(s).")

            if "answer" in {objective.id for objective in plan.objectives}:
                # Fast-mode tasks have a single 'answer' objective and no
                # verification stage. Without this the objective stayed pending
                # and every successful fast task was reported as needs_attention.
                if summary:
                    mark_objective(
                        plan,
                        "answer",
                        "done",
                        [f"Model produced an answer after {loop.steps} step(s); no tool evidence is required in fast mode."],
                    )
                else:
                    mark_objective(
                        plan,
                        "answer",
                        "failed",
                        ["The model returned no answer text."],
                    )

            used = {event.name for event in loop.tool_events}
            if "inspect" in {objective.id for objective in plan.objectives}:
                if used & {"read_file", "search_text", "list_dir"}:
                    mark_objective(plan, "inspect", "done", [f"Used tools: {', '.join(sorted(used))}"])
                else:
                    mark_objective(plan, "inspect", "failed", ["No inspection tool was used."])
            if "implement" in {objective.id for objective in plan.objectives}:
                change_attempts = [
                    event for event in loop.tool_events if event.name in {"write_file", "run_command"}
                ]
                succeeded = [event for event in change_attempts if event.result.ok]
                if succeeded:
                    names = ", ".join(sorted({event.name for event in succeeded}))
                    mark_objective(plan, "implement", "done", [f"Changed via: {names}"])
                elif change_attempts:
                    mark_objective(
                        plan,
                        "implement",
                        "failed",
                        ["Every write or command attempt failed or was denied."],
                    )
                elif assessment.mode == "fast":
                    mark_objective(plan, "implement", "done", ["No change was requested in fast mode."])
                else:
                    mark_objective(plan, "implement", "failed", ["No write or command tool was used."])

            if assessment.requires_verification and not cancel.cancelled:
                verification = self._verify(task_id, broker, workspace, plan)
                record(
                    "Verification: "
                    + ("passed" if all(item.get("ok") for item in verification) else "failed")
                    + f" ({len(verification)} check(s))",
                    kind="verification",
                )
                if verification and not all(item.get("ok") for item in verification):
                    repair = run_tool_loop(
                        runtime=self.runtime,
                        messages=[
                            system,
                            *loop.messages[-6:],
                            ChatMessage(
                                role="user",
                                content=(
                                    "Independent verification failed. Here is the real output:\n"
                                    + _verification_excerpt(verification)
                                    + "\nDiagnose the actual cause, fix it with the tools, then stop. "
                                    "Do not claim success without rerunning the check."
                                ),
                            ),
                        ],
                        tool_schemas=tools.schemas(assessment.tools),
                        tool_caller=tools.call,
                        max_steps=min(4, assessment.max_steps),
                        cancel=cancel,
                        on_delta=lambda text: self.events.emit("task.delta", task_id=task_id, text=text),
                        on_tool=lambda event: self._on_tool(task_id, event, tool_events, record),
                    )
                    summary = repair.text.strip() or summary
                    verification = self._verify(task_id, broker, workspace, plan)
                    record(
                        "Repair verification: "
                        + ("passed" if all(item.get("ok") for item in verification) else "failed"),
                        kind="verification",
                    )
                    if verification and all(item.get("ok") for item in verification):
                        correction_id = self._record_candidate_correction(task, summary, verification)
                verified_ok = bool(verification) and all(item.get("ok") for item in verification)
                if verified_ok:
                    mark_objective(plan, "verify", "done", ["Independent checks passed."])
                else:
                    mark_objective(plan, "verify", "failed", ["Independent checks did not pass."])

            signals = plan.drift_signals()
            if signals:
                record("; ".join(signals), kind="drift")
            pending = [objective.id for objective in plan.objectives if objective.status != "done"]
            completed = (
                not pending
                and stopped_reason == "complete"
                and not cancel.cancelled
                and (
                    not assessment.requires_verification
                    or (bool(verification) and all(item.get("ok") for item in verification))
                )
            )
            status = "completed" if completed else "needs_attention"
            if cancel.cancelled:
                status = "cancelled"
                stopped_reason = "cancelled"

            self.store.update_task(
                task_id,
                status=status,
                evidence=evidence,
                plan={
                    **plan.to_dict(),
                    "assessment": assessment.to_dict(),
                    # Persist the raw verification reports so the desktop
                    # Verification tab still shows the commands and their real
                    # output after the task is reselected or the app restarts.
                    "verification": verification,
                },
            )
            self.store.record_run(
                kind="capability_task",
                metrics={
                    "task_id": task_id,
                    "steps": loop.steps,
                    "tool_calls": len(tool_events),
                    "verification_count": len(verification),
                    "verification_ok": bool(verification) and all(item.get("ok") for item in verification),
                },
                status=status,
            )
            self.events.emit(
                "task.completed",
                task_id=task_id,
                status=status,
                summary=summary,
                verification=verification,
            )
            return TaskRun(
                task_id=task_id,
                status=status,
                summary=summary,
                plan={**plan.to_dict(), "assessment": assessment.to_dict()},
                evidence=evidence,
                verification=verification,
                stopped_reason=stopped_reason,
                tool_events=tool_events,
                assessment=assessment.to_dict(),
                correction_id=correction_id,
            )
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"
            record(failure, kind="error")
            self.store.update_task(
                task_id,
                status="cancelled" if cancel.cancelled else "failed",
                evidence=evidence,
                plan={
                    **plan.to_dict(),
                    "assessment": assessment.to_dict(),
                    "verification": verification,
                },
            )
            self.events.emit(
                "task.completed",
                task_id=task_id,
                status="cancelled" if cancel.cancelled else "failed",
                summary=failure,
                verification=verification,
            )
            raise

    def _context_block(self, workspace: str, plan: Plan, goal: str) -> str:
        stack = detect_project_stack(workspace)
        lines = [
            "You are the ECLIPSE capability execution engine.",
            "You work inside one approved project workspace and use only the provided tools.",
            "Tool output is the only evidence that an action happened. Never invent file contents.",
            "",
            f"Workspace: {Path(workspace).name}",
            f"Observed project signals: {', '.join(stack.get('signals') or []) or 'none'}",
            f"Plan mode: {plan.mode}; risk: {plan.risk}",
            "",
            "Plan:",
        ]
        for objective in plan.objectives:
            lines.append(f"- [{objective.status}] {objective.id}: {objective.title}")
            for criterion in objective.acceptance_criteria:
                lines.append(f"    acceptance: {criterion}")
        if plan.likely_files:
            lines.append("Likely relevant files: " + ", ".join(plan.likely_files[:8]))
        if self.knowledge is not None:
            knowledge = self.knowledge.context_block(goal)
            if knowledge:
                lines.extend(["", knowledge])
        lessons = self.memory.context_block(goal)
        if lessons:
            lines.extend(["", lessons])
        lines.extend(
            [
                "",
                "Rules:",
                "- Prefer reading existing code over guessing APIs.",
                "- Keep changes small, coherent and inside the workspace.",
                "- Respect the user's approval decisions; a denied tool means choose another approach.",
                "- Stop when the goal is met; report honestly what remains unknown.",
            ]
        )
        return "\n".join(lines)

    def _on_tool(
        self,
        task_id: str,
        event: ToolEvent,
        tool_events: list[dict[str, Any]],
        record: Callable[..., None],
    ) -> None:
        payload = event.to_dict()
        tool_events.append(payload)
        record(
            f"Tool {event.name} -> {'ok' if event.result.ok else 'failed'}: {event.result.output[:240]}",
            kind="tool",
        )
        self.events.emit("task.tool", task_id=task_id, **payload)

    def _verify(
        self,
        task_id: str,
        broker: PermissionBroker,
        workspace: str,
        plan: Plan,
    ) -> list[dict[str, Any]]:
        self.events.emit("task.verification_started", task_id=task_id)
        try:
            reports = self.verifier.run(broker=broker, workspace_root=workspace)
        except Exception as exc:  # noqa: BLE001 - verification failure is evidence
            reports = [
                {
                    "command": [],
                    "ok": False,
                    "exit_code": None,
                    "stdout": "",
                    "stderr": f"Verification could not run: {type(exc).__name__}: {exc}",
                    "evidence": "observed",
                }
            ]
        if not any(objective.id == "verify" for objective in plan.objectives):
            plan.objectives.append(
                Objective(
                    id="verify",
                    title="Verify the change with independent checks",
                    acceptance_criteria=["A real check passes."],
                    verification="Run the project's checks.",
                )
            )
        self.events.emit("task.verification", task_id=task_id, reports=reports)
        return reports

    def _record_candidate_correction(
        self, task: Mapping[str, Any], summary: str, verification: Sequence[Mapping[str, Any]]
    ) -> str | None:
        try:
            lesson = self.memory.propose(
                title=f"Repair after verification failure: {str(task['goal'])[:80]}",
                issue=_verification_excerpt(verification)[:1200],
                root_cause="Candidate: recorded from a model-guided repair that later passed checks.",
                fix=(summary or "See the recorded repair steps.")[:1200],
                scope=f"workspace:{task.get('project_root') or 'unknown'}",
                evidence="; ".join(
                    f"{' '.join(map(str, report.get('command') or []))} exited {report.get('exit_code')}"
                    for report in verification
                )[:1500],
                regression="",
            )
            if self.knowledge is not None:
                self.knowledge.propose_note(
                    title=lesson["title"],
                    body=(
                        f"## Observed issue\n\n{lesson['issue']}\n\n"
                        f"## Candidate fix\n\n{lesson['fix']}\n\n"
                        f"## Verification evidence\n\n{lesson['evidence']}\n\n"
                        "This is a candidate lesson until a regression check is recorded."
                    ),
                    source="capability_engine",
                )
            return lesson["id"]
        except (MemoryError, Exception):  # noqa: BLE001 - memory is best effort
            return None

    def propose_skill(
        self, *, title: str, body: str, verification: str = ""
    ) -> dict[str, Any]:
        if self.knowledge is None:
            raise CapabilityError("No knowledge vault is connected")
        return self.knowledge.propose_note(
            title=title,
            body=body + (f"\n\n## Verification\n\n{verification}" if verification else ""),
            source="capability_skill",
        )


def _verification_excerpt(reports: Sequence[Mapping[str, Any]], limit: int = 2500) -> str:
    chunks = []
    for report in reports:
        command = " ".join(str(part) for part in report.get("command") or [])
        chunks.append(
            f"$ {command}\nexit: {report.get('exit_code')}\n"
            f"{(report.get('stdout') or '')[-1200:]}\n{(report.get('stderr') or '')[-1200:]}"
        )
    text = "\n\n".join(chunks)
    return text[-limit:] if len(text) > limit else text
