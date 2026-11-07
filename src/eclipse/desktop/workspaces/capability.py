"""Capability Amplification & Knowledge System workspace."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from eclipse.capability import TRUSTED_FOLDERS, classify_task
from eclipse.runtime import CancellationToken

from ..approval import ApprovalBridge
from ..context import AppContext
from ..widgets import add_plain_text, add_text, clear_layout, make_card, make_header


class _Relay(QObject):
    event = Signal(str, object)


class _CreateTaskWorker(QThread):
    created = Signal(dict)
    failed = Signal(str)

    def __init__(self, context: AppContext, goal: str, mode: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self.goal = goal
        self.mode = mode

    def run(self) -> None:
        try:
            task = self.context.capability.create_task(self.goal, mode=self.mode)
            self.created.emit(task)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _RunTaskWorker(QThread):
    finished_with = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        context: AppContext,
        task_id: str,
        approver: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.task_id = task_id
        self.approver = approver
        self.cancel = CancellationToken()

    def run(self) -> None:
        try:
            result = self.context.capability.run_task(
                self.task_id, cancel=self.cancel, approver=self.approver
            )
            self.finished_with.emit(result.to_dict())
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

    def stop(self) -> None:
        self.cancel.cancel()


class CapabilityWorkspace(QWidget):
    """Real planning, scoped execution, verification and knowledge review."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self._task_worker: _RunTaskWorker | None = None
        self._selected_task_id: str | None = None
        self._relay = _Relay(self)
        self._approval = ApprovalBridge(self)
        self._approval.requested.connect(self._ask_approval)
        self.setObjectName("CapabilityWorkspace")
        self.setAccessibleName("Capability Amplification and Knowledge System")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout()
        layout.setContentsMargins(38, 30, 38, 30)
        layout.setSpacing(14)

        layout.addWidget(
            make_header(
                "Capability Amplification & Knowledge",
                "Structured planning, scoped tools, independent verification and a reviewable "
                "Obsidian knowledge library — all using the shared model runtime.",
            )
        )

        workspace_row = QHBoxLayout()
        self._workspace_label = QLabel(f"Workspace: {self.context.workspace or 'none selected'}")
        self._workspace_label.setObjectName("Muted")
        choose = QPushButton("Choose project folder…")
        choose.clicked.connect(self._choose_workspace)
        workspace_row.addWidget(self._workspace_label, 1)
        workspace_row.addWidget(choose)
        layout.addLayout(workspace_row)

        split = QSplitter()
        split.setChildrenCollapsible(False)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)

        new_card, new_layout = make_card(
            "New capability task",
            "The watchdog decides how much process is justified; you can override it.",
        )
        self._goal = QPlainTextEdit()
        self._goal.setPlaceholderText(
            "Describe a real task, for example: add a bounded --json flag to the CLI and verify the tests."
        )
        self._goal.setMinimumHeight(90)
        new_layout.addWidget(self._goal)
        self._mode = QComboBox()
        for label, value in (
            ("Auto (watchdog decides)", "auto"),
            ("Fast (read-only, minimal)", "fast"),
            ("Balanced", "balanced"),
            ("Enhanced (deep verification)", "enhanced"),
        ):
            self._mode.addItem(label, value)
        new_layout.addWidget(self._mode)
        self._assessment = QLabel("")
        self._assessment.setObjectName("Faint")
        self._assessment.setWordWrap(True)
        new_layout.addWidget(self._assessment)
        self._goal.textChanged.connect(self._preview_assessment)
        self._mode.currentIndexChanged.connect(self._preview_assessment)
        create_row = QHBoxLayout()
        self._create_button = QPushButton("Create plan")
        self._create_button.clicked.connect(self._create_task)
        create_row.addWidget(self._create_button)
        create_row.addStretch(1)
        new_layout.addLayout(create_row)
        left_layout.addWidget(new_card)

        tasks_card, tasks_layout = make_card("Tasks", "Plans and their verified status.")
        self._task_list = QListWidget()
        self._task_list.setObjectName("TaskList")
        self._task_list.currentRowChanged.connect(self._on_task_selected)
        tasks_layout.addWidget(self._task_list, 1)
        actions = QHBoxLayout()
        self._run_button = QPushButton("Run selected task")
        self._run_button.setObjectName("PrimaryButton")
        self._run_button.clicked.connect(self._run_task)
        self._run_button.setEnabled(False)
        self._stop_button = QPushButton("Stop")
        self._stop_button.setObjectName("DangerButton")
        self._stop_button.clicked.connect(self._stop_task)
        self._stop_button.setEnabled(False)
        actions.addWidget(self._run_button)
        actions.addWidget(self._stop_button)
        tasks_layout.addLayout(actions)
        self._activity = QLabel("No task is running.")
        self._activity.setObjectName("Faint")
        self._activity.setWordWrap(True)
        tasks_layout.addWidget(self._activity)
        left_layout.addWidget(tasks_card, 1)
        split.addWidget(left)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("WorkspaceTabs")
        self._tabs.addTab(self._build_plan_tab(), "Plan & evidence")
        self._tabs.addTab(self._build_verification_tab(), "Verification")
        self._tabs.addTab(self._build_knowledge_tab(), "Knowledge")
        self._tabs.addTab(self._build_corrections_tab(), "Corrections")
        split.addWidget(self._tabs)
        split.setSizes([440, 620])
        layout.addWidget(split, 1)
        outer.addLayout(layout)

        for name in ("task.tool", "task.step", "task.completed", "task.status", "task.verification"):
            self.context.events.subscribe(
                name, lambda event, event_name=name: self._relay.event.emit(event_name, event.payload)
            )
        self._relay.event.connect(self._on_core_event)
        self._preview_assessment()
        self.refresh_tasks()
        self.refresh_knowledge()
        self.refresh_corrections()

    # -- tabs ------------------------------------------------------------

    def _build_plan_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("ResultsScroll")
        scroll.setWidgetResizable(True)
        content = QWidget()
        self._plan_layout = QVBoxLayout(content)
        self._plan_layout.setContentsMargins(18, 18, 18, 18)
        self._plan_layout.setSpacing(12)
        scroll.setWidget(content)
        return scroll

    def _build_verification_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        add_text(
            layout,
            "Raw output from the commands that actually ran. A failure is shown as a failure.",
            "Faint",
        )
        self._verification_output = QPlainTextEdit()
        self._verification_output.setReadOnly(True)
        self._verification_output.setObjectName("EvidenceOutput")
        layout.addWidget(self._verification_output, 1)
        return widget

    def _build_knowledge_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        add_text(
            layout,
            "AI proposals wait in the Inbox. Approval copies a note into a trusted folder and "
            "never overwrites an existing trusted note.",
            "Faint",
        )
        row = QHBoxLayout()
        self._note_list = QListWidget()
        self._note_list.currentRowChanged.connect(self._preview_note)
        self._note_preview = QPlainTextEdit()
        self._note_preview.setReadOnly(True)
        row.addWidget(self._note_list, 1)
        row.addWidget(self._note_preview, 2)
        layout.addLayout(row, 1)
        approve_row = QHBoxLayout()
        self._folder_combo = QComboBox()
        for folder in TRUSTED_FOLDERS:
            self._folder_combo.addItem(folder, folder)
        self._verification_note = QLineEdit()
        self._verification_note.setPlaceholderText("Optional verification evidence")
        self._approve_button = QPushButton("Approve")
        self._approve_button.clicked.connect(self._approve_note)
        self._reject_button = QPushButton("Reject")
        self._reject_button.clicked.connect(self._reject_note)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_knowledge)
        approve_row.addWidget(self._folder_combo)
        approve_row.addWidget(self._verification_note, 1)
        approve_row.addWidget(self._approve_button)
        approve_row.addWidget(self._reject_button)
        approve_row.addWidget(refresh)
        layout.addLayout(approve_row)
        return widget

    def _build_corrections_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        add_text(
            layout,
            "Candidates are model-proposed until independent evidence and a regression are recorded.",
            "Faint",
        )
        row = QHBoxLayout()
        self._correction_list = QListWidget()
        self._correction_list.currentRowChanged.connect(self._preview_correction)
        self._correction_detail = QPlainTextEdit()
        self._correction_detail.setReadOnly(True)
        row.addWidget(self._correction_list, 1)
        row.addWidget(self._correction_detail, 2)
        layout.addLayout(row, 1)
        promote_form = QFormLayout()
        self._promote_evidence = QLineEdit()
        self._promote_evidence.setPlaceholderText("Exact command and observed passing output")
        self._promote_regression = QLineEdit()
        self._promote_regression.setPlaceholderText("Regression test name or repeatable check")
        promote_form.addRow("Evidence", self._promote_evidence)
        promote_form.addRow("Regression", self._promote_regression)
        layout.addLayout(promote_form)
        self._promote_button = QPushButton("Promote to verified")
        self._promote_button.clicked.connect(self._promote_correction)
        layout.addWidget(self._promote_button)
        return widget

    # -- tasks -----------------------------------------------------------

    def _choose_workspace(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose the approved project workspace")
        if folder:
            self.context.set_workspace(folder)
            self._workspace_label.setText(f"Workspace: {folder}")

    def _preview_assessment(self) -> None:
        goal = self._goal.toPlainText().strip()
        if not goal:
            self._assessment.setText("")
            return
        try:
            assessment = classify_task(goal, mode=str(self._mode.currentData()))
        except ValueError as exc:
            self._assessment.setText(str(exc))
            return
        self._assessment.setText(
            f"Watchdog: {assessment.mode} mode · risk {assessment.risk} · "
            f"{assessment.max_steps} step budget · verification "
            f"{'required' if assessment.requires_verification else 'not required'}"
        )

    def _create_task(self) -> None:
        goal = self._goal.toPlainText().strip()
        if not goal:
            QMessageBox.information(self, "Task", "Describe the task first.")
            return
        if not self.context.workspace:
            QMessageBox.information(
                self, "Workspace", "Choose an approved project folder before creating a task."
            )
            return
        self._create_button.setEnabled(False)
        worker = _CreateTaskWorker(self.context, goal, str(self._mode.currentData()), self)
        worker.created.connect(self._task_created)
        worker.failed.connect(self._task_failed)
        worker.finished.connect(lambda: self._create_button.setEnabled(True))
        worker.start()

    def _task_created(self, task: dict[str, Any]) -> None:
        self._goal.clear()
        self.refresh_tasks()
        self._select_task(task["id"])
        self._tabs.setCurrentIndex(0)

    def _task_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Task", message)

    def refresh_tasks(self) -> None:
        self._task_list.blockSignals(True)
        self._task_list.clear()
        tasks = self.context.capability.list_tasks()
        row_to_select = -1
        for row, task in enumerate(tasks):
            item = QListWidgetItem(f"{task['status'].replace('_', ' ').title()} · {task['goal'][:80]}")
            item.setData(Qt.ItemDataRole.UserRole, task["id"])
            self._task_list.addItem(item)
            if task["id"] == self._selected_task_id:
                row_to_select = row
        self._task_list.blockSignals(False)
        if row_to_select >= 0:
            self._task_list.setCurrentRow(row_to_select)
        elif tasks:
            self._task_list.setCurrentRow(0)
        else:
            self._selected_task_id = None
            self._render_plan(None)

    def _select_task(self, task_id: str) -> None:
        tasks = self.context.capability.list_tasks()
        for row, task in enumerate(tasks):
            if task["id"] == task_id:
                self._task_list.setCurrentRow(row)
                return

    def _on_task_selected(self, row: int) -> None:
        if row < 0:
            self._selected_task_id = None
            self._render_plan(None)
            self._run_button.setEnabled(False)
            return
        item = self._task_list.item(row)
        if item is None:
            return
        task_id = item.data(Qt.ItemDataRole.UserRole)
        self._selected_task_id = task_id
        task = self.context.store.get_task(task_id)
        self._render_plan(task)
        self._render_verification(task)
        running = self._task_worker is not None
        self._run_button.setEnabled(not running and task is not None and task["status"] != "running")

    def _render_plan(self, task: dict[str, Any] | None) -> None:
        clear_layout(self._plan_layout)
        if task is None:
            add_text(self._plan_layout, "No task selected. Create a plan to begin.", "Muted")
            return
        plan = task.get("plan") or {}
        assessment = plan.get("assessment") or {}
        title = QLabel(task["goal"])
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        self._plan_layout.addWidget(title)
        add_plain_text(
            self._plan_layout,
            f"Status: {task['status']}\nMode: {task.get('mode')} · Risk: {assessment.get('risk', 'unknown')}\n"
            f"Workspace: {task.get('project_root') or 'not set'}\nCreated: {task.get('created_at')}",
            "Muted",
        )
        if plan.get("rationale"):
            add_plain_text(self._plan_layout, "\n".join(f"• {line}" for line in plan["rationale"]), "Faint")
        for objective in plan.get("objectives") or []:
            card = QWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 6, 0, 6)
            status = str(objective.get("status") or "pending")
            heading = QLabel(f"[{status}] {objective.get('title')}")
            heading.setObjectName("ObjectiveTitle")
            heading.setWordWrap(True)
            card_layout.addWidget(heading)
            for criterion in objective.get("acceptance_criteria") or []:
                label = QLabel(f"Acceptance: {criterion}")
                label.setObjectName("Muted")
                label.setWordWrap(True)
                card_layout.addWidget(label)
            if objective.get("verification"):
                label = QLabel(f"Verification: {objective['verification']}")
                label.setObjectName("Faint")
                label.setWordWrap(True)
                card_layout.addWidget(label)
            for evidence in objective.get("evidence") or []:
                label = QLabel(f"Evidence: {evidence}")
                label.setObjectName("Faint")
                label.setWordWrap(True)
                card_layout.addWidget(label)
            self._plan_layout.addWidget(card)
        evidence = task.get("evidence") or []
        if evidence:
            add_text(self._plan_layout, "Recorded evidence", "CardTitle")
            for entry in evidence[-40:]:
                add_plain_text(
                    self._plan_layout,
                    f"[{entry.get('kind')}] {entry.get('message')}",
                    "Faint",
                )
        self._plan_layout.addStretch(1)

    def _render_verification(self, task: dict[str, Any] | None) -> None:
        if task is None:
            self._verification_output.setPlainText("")
            return
        lines: list[str] = []
        for entry in task.get("evidence") or []:
            if entry.get("kind") == "verification":
                lines.append(str(entry.get("message")))
        plan = task.get("plan") or {}
        verification = plan.get("verification") or []
        if verification:
            for report in verification:
                command = " ".join(str(part) for part in report.get("command") or [])
                lines.append(
                    f"$ {command}\nexit: {report.get('exit_code')}  ok: {report.get('ok')}\n"
                    f"{report.get('stdout') or ''}\n{report.get('stderr') or ''}"
                )
        self._verification_output.setPlainText("\n\n".join(lines) or "No verification has run for this task.")

    def _run_task(self) -> None:
        if self._selected_task_id is None or self._task_worker is not None:
            return
        task = self.context.store.get_task(self._selected_task_id)
        if task is None:
            return
        self._task_worker = _RunTaskWorker(self.context, task["id"], self._approval.approve, self)
        self._task_worker.finished_with.connect(self._task_finished)
        self._task_worker.failed.connect(self._task_failed_run)
        self._task_worker.finished.connect(self._task_cleanup)
        self._run_button.setEnabled(False)
        self._stop_button.setEnabled(True)
        self._create_button.setEnabled(False)
        self._activity.setText("Running. Tools and results appear here as they happen.")
        self.context.store.update_task(task["id"], status="running")
        self.refresh_tasks()
        self._task_worker.start()

    def _task_finished(self, result: dict[str, Any]) -> None:
        self._activity.setText(
            f"Finished: {result.get('status')} ({result.get('stopped_reason')}). "
            "Read the verification tab before trusting the summary."
        )
        self.refresh_tasks()
        if self._selected_task_id:
            task = self.context.store.get_task(self._selected_task_id)
            self._render_plan(task)
            self._render_verification(task)
        self.refresh_corrections()
        self.refresh_knowledge()

    def _task_failed_run(self, message: str) -> None:
        self._activity.setText(f"Task could not complete: {message}")
        self.refresh_tasks()

    def _task_cleanup(self) -> None:
        self._task_worker = None
        self._run_button.setEnabled(True)
        self._stop_button.setEnabled(False)
        self._create_button.setEnabled(True)

    def _stop_task(self) -> None:
        if self._task_worker is not None:
            self._task_worker.stop()
            self._activity.setText("Stop requested. Waiting for the current tool call to return…")

    def _on_core_event(self, name: str, payload: dict[str, Any]) -> None:
        if name in {"task.tool", "task.step"}:
            if name == "task.tool":
                result = payload.get("result") or {}
                status = "ok" if result.get("ok") else "failed"
                self._activity.setText(f"Tool {payload.get('name')} → {status}")
            else:
                self._activity.setText(f"Model step {payload.get('step')}…")
        if name == "task.completed":
            self._activity.setText(f"Task {payload.get('status')}.")
        if name == "task.verification":
            reports = payload.get("reports") or []
            lines = []
            for report in reports:
                lines.append(
                    f"$ {' '.join(map(str, report.get('command') or []))}\n"
                    f"exit: {report.get('exit_code')}\n{report.get('stdout') or ''}\n{report.get('stderr') or ''}"
                )
            self._verification_output.setPlainText("\n\n".join(lines))

    # -- knowledge -------------------------------------------------------

    def refresh_knowledge(self) -> None:
        self._note_list.blockSignals(True)
        self._note_list.clear()
        for note in self.context.knowledge.list_notes(status="inbox"):
            item = QListWidgetItem(f"{note['title']}\n{note['created_at']}")
            item.setData(Qt.ItemDataRole.UserRole, note["id"])
            self._note_list.addItem(item)
        self._note_list.blockSignals(False)
        if self._note_list.count() == 0:
            self._note_preview.setPlainText("The AI Inbox is empty.")
        else:
            self._note_list.setCurrentRow(0)

    def _preview_note(self, row: int) -> None:
        if row < 0:
            return
        item = self._note_list.item(row)
        if item is None:
            return
        try:
            payload = self.context.knowledge.read_note(item.data(Qt.ItemDataRole.UserRole))
        except Exception as exc:  # noqa: BLE001
            self._note_preview.setPlainText(str(exc))
            return
        self._note_preview.setPlainText(payload["content"])

    def _approve_note(self) -> None:
        item = self._note_list.currentItem()
        if item is None:
            return
        try:
            result = self.context.knowledge.approve_note(
                item.data(Qt.ItemDataRole.UserRole),
                target_folder=str(self._folder_combo.currentData()),
                verification=self._verification_note.text().strip(),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Knowledge", str(exc))
            return
        self._verification_note.clear()
        self.refresh_knowledge()
        QMessageBox.information(
            self, "Approved", f"Written as a new trusted note: {result['approved_path']}"
        )

    def _reject_note(self) -> None:
        item = self._note_list.currentItem()
        if item is None:
            return
        try:
            self.context.knowledge.reject_note(
                item.data(Qt.ItemDataRole.UserRole), reason="Rejected in the desktop review"
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Knowledge", str(exc))
            return
        self.refresh_knowledge()

    # -- corrections -----------------------------------------------------

    def refresh_corrections(self) -> None:
        self._correction_list.blockSignals(True)
        self._correction_list.clear()
        for correction in self.context.memory.lessons():
            item = QListWidgetItem(f"[{correction.status}] {correction.title}")
            item.setData(Qt.ItemDataRole.UserRole, correction.id)
            self._correction_list.addItem(item)
        self._correction_list.blockSignals(False)
        if self._correction_list.count() == 0:
            self._correction_detail.setPlainText("No candidate or verified corrections yet.")
        else:
            self._correction_list.setCurrentRow(0)

    def _preview_correction(self, row: int) -> None:
        if row < 0:
            return
        item = self._correction_list.item(row)
        if item is None:
            return
        correction_id = item.data(Qt.ItemDataRole.UserRole)
        lesson = next((item for item in self.context.memory.lessons() if item.id == correction_id), None)
        if lesson is None:
            return
        self._correction_detail.setPlainText(
            f"Status: {lesson.status}\n\nIssue:\n{lesson.issue}\n\nRoot cause:\n{lesson.root_cause}\n\n"
            f"Fix:\n{lesson.fix}\n\nScope:\n{lesson.scope}\n\nEvidence:\n{lesson.evidence or 'none recorded'}\n\n"
            f"Regression:\n{lesson.regression or 'none recorded'}"
        )

    def _promote_correction(self) -> None:
        item = self._correction_list.currentItem()
        if item is None:
            return
        try:
            self.context.memory.promote(
                item.data(Qt.ItemDataRole.UserRole),
                evidence=self._promote_evidence.text(),
                regression=self._promote_regression.text(),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Corrections", str(exc))
            return
        self.refresh_corrections()
        QMessageBox.information(self, "Corrections", "Promoted to verified memory.")

    # -- approvals -------------------------------------------------------

    def _ask_approval(self, action: str, target: str, detail: str, holder: Any) -> None:
        answer = QMessageBox.question(
            self,
            f"Approve {action}?",
            f"{detail}\n\n{target}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        ApprovalBridge.resolve(holder, answer == QMessageBox.StandardButton.Yes)

    def shutdown(self) -> None:
        if self._task_worker is not None:
            self._task_worker.stop()
            self._task_worker.wait(3000)
