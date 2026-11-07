"""ECLIPSE Agent workspace: real chat, model context, tools and approvals."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
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
    QVBoxLayout,
    QWidget,
)

from eclipse.runtime import CancellationToken

from ..approval import ApprovalBridge
from ..context import AppContext


class _Relay(QObject):
    event = Signal(str, object)


class _Composer(QPlainTextEdit):
    submitted = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.submitted.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _SendWorker(QThread):
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, context: AppContext, conversation_id: str, text: str, approver: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self.conversation_id = conversation_id
        self.text = text
        self.approver = approver
        self.cancel = CancellationToken()

    def run(self) -> None:
        try:
            result = self.context.agent.send(
                self.conversation_id,
                self.text,
                cancel=self.cancel,
                approver=self.approver,
            )
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

    def stop(self) -> None:
        self.cancel.cancel()


class _Bubble(QFrame):
    def __init__(self, role: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("UserBubble" if role == "user" else "AssistantBubble")
        self.setProperty("role", role)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label.setObjectName("BubbleText")
        layout.addWidget(self.label)
        self._text = text

    def append_text(self, delta: str) -> None:
        self._text += delta
        self.label.setText(self._text)


class AgentWorkspace(QWidget):
    """Conversation list, chat, streaming, tools, approvals and Stop."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self._conversation_id: str | None = None
        self._worker: _SendWorker | None = None
        self._stream_bubble: _Bubble | None = None
        self._stream_conversation: str | None = None
        self._relay = _Relay(self)
        self._approval = ApprovalBridge(self)
        self._approval.requested.connect(self._ask_approval)
        self.setObjectName("AgentWorkspace")
        self.setAccessibleName("ECLIPSE Agent")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("ChatSidebar")
        sidebar.setFixedWidth(280)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(16, 22, 16, 18)
        side_layout.setSpacing(10)
        title = QLabel("Conversations")
        title.setObjectName("PanelTitle")
        side_layout.addWidget(title)
        new_button = QPushButton("+ New chat")
        new_button.setObjectName("PrimaryButton")
        new_button.clicked.connect(self._new_conversation)
        side_layout.addWidget(new_button)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search conversations…")
        self._search.textChanged.connect(self._refresh_conversations)
        side_layout.addWidget(self._search)
        self._conversation_list = QListWidget()
        self._conversation_list.setObjectName("ConversationList")
        self._conversation_list.currentRowChanged.connect(self._on_conversation_selected)
        side_layout.addWidget(self._conversation_list, 1)
        delete_button = QPushButton("Delete conversation")
        delete_button.clicked.connect(self._delete_conversation)
        side_layout.addWidget(delete_button)
        self._workspace_label = QLabel(self._workspace_text())
        self._workspace_label.setObjectName("Faint")
        self._workspace_label.setWordWrap(True)
        side_layout.addWidget(self._workspace_label)
        workspace_button = QPushButton("Project folder…")
        workspace_button.clicked.connect(self._choose_workspace)
        side_layout.addWidget(workspace_button)
        self._memory_check = QCheckBox("Use verified corrections")
        self._memory_check.setChecked(bool(self.context.settings.get("memory_enabled", True)))
        self._memory_check.toggled.connect(
            lambda value: self.context.settings.set("memory_enabled", bool(value))
        )
        side_layout.addWidget(self._memory_check)
        self._knowledge_check = QCheckBox("Use approved knowledge")
        self._knowledge_check.setChecked(bool(self.context.settings.get("knowledge_enabled", True)))
        self._knowledge_check.toggled.connect(
            lambda value: self.context.settings.set("knowledge_enabled", bool(value))
        )
        side_layout.addWidget(self._knowledge_check)
        root.addWidget(sidebar)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("ChatHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(26, 16, 26, 14)
        self._conversation_title = QLabel("New conversation")
        self._conversation_title.setObjectName("ChatTitle")
        self._model_label = QLabel("No model loaded")
        self._model_label.setObjectName("ModelChip")
        header_layout.addWidget(self._conversation_title, 1)
        header_layout.addWidget(self._model_label)
        main_layout.addWidget(header)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("ChatScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        transcript = QWidget()
        transcript.setObjectName("Transcript")
        self._transcript_layout = QVBoxLayout(transcript)
        self._transcript_layout.setContentsMargins(28, 18, 28, 18)
        self._transcript_layout.setSpacing(12)
        self._transcript_layout.addStretch(1)
        self._scroll.setWidget(transcript)
        main_layout.addWidget(self._scroll, 1)

        self._activity = QLabel("")
        self._activity.setObjectName("ActivityLine")
        self._activity.setWordWrap(True)
        self._activity.setContentsMargins(28, 0, 28, 4)
        main_layout.addWidget(self._activity)

        composer_row = QHBoxLayout()
        composer_row.setContentsMargins(24, 8, 24, 20)
        composer_row.setSpacing(10)
        self._attach_button = QPushButton("Attach…")
        self._attach_button.clicked.connect(self._attach_file)
        composer = QWidget()
        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(0, 0, 0, 0)
        composer_layout.setSpacing(4)
        self._attachments_label = QLabel("")
        self._attachments_label.setObjectName("Faint")
        self._attachments_label.setWordWrap(True)
        composer_layout.addWidget(self._attachments_label)
        self._composer = _Composer()
        self._composer.setObjectName("Composer")
        self._composer.setPlaceholderText("Message ECLIPSE…  (Enter to send, Shift+Enter for a new line)")
        self._composer.setMinimumHeight(72)
        self._composer.setMaximumHeight(160)
        self._composer.submitted.connect(self._send)
        composer_layout.addWidget(self._composer)
        self._send_button = QPushButton("Send")
        self._send_button.setObjectName("PrimaryButton")
        self._send_button.clicked.connect(self._send)
        self._stop_button = QPushButton("Stop")
        self._stop_button.setObjectName("DangerButton")
        self._stop_button.clicked.connect(self._stop)
        self._stop_button.setEnabled(False)
        composer_row.addWidget(self._attach_button, 0, Qt.AlignmentFlag.AlignBottom)
        composer_row.addWidget(composer, 1)
        composer_row.addWidget(self._send_button, 0, Qt.AlignmentFlag.AlignBottom)
        composer_row.addWidget(self._stop_button, 0, Qt.AlignmentFlag.AlignBottom)
        main_layout.addLayout(composer_row)
        root.addWidget(main, 1)

        for name in ("agent.delta", "agent.tool", "agent.completed", "agent.conversation_created", "runtime.state"):
            self.context.events.subscribe(
                name, lambda event, event_name=name: self._relay.event.emit(event_name, event.payload)
            )
        self._relay.event.connect(self._on_core_event)

        self._refresh_conversations()
        conversations = self.context.agent.conversations()
        if conversations:
            self._select_conversation(conversations[0]["id"])
        else:
            self._new_conversation()
        self._render_model_label()

    # -- conversations ---------------------------------------------------

    def _workspace_text(self) -> str:
        return f"Project: {Path(self.context.workspace).name}" if self.context.workspace else "No project folder attached"

    def _choose_workspace(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose the Agent project folder")
        if folder:
            self.context.set_workspace(folder)
            self._workspace_label.setText(self._workspace_text())

    def _new_conversation(self) -> None:
        model = self.context.selected_model()
        conversation = self.context.agent.new_conversation(
            model_id=model["id"] if model else None
        )
        self._refresh_conversations()
        self._select_conversation(conversation["id"])

    def _refresh_conversations(self) -> None:
        current = self._conversation_id
        self._conversation_list.blockSignals(True)
        self._conversation_list.clear()
        conversations = self.context.agent.conversations(self._search.text().strip() or None)
        row_to_select = -1
        for row, conversation in enumerate(conversations):
            item = QListWidgetItem(f"{conversation['title']}\n{conversation['updated_at'][:16].replace('T', ' ')}")
            item.setData(Qt.ItemDataRole.UserRole, conversation["id"])
            self._conversation_list.addItem(item)
            if conversation["id"] == current:
                row_to_select = row
        self._conversation_list.blockSignals(False)
        if row_to_select >= 0:
            self._conversation_list.setCurrentRow(row_to_select)
        elif conversations:
            self._conversation_list.setCurrentRow(0)
            self._select_conversation(conversations[0]["id"])
        else:
            self._conversation_id = None

    def _select_conversation(self, conversation_id: str) -> None:
        self._conversation_id = conversation_id
        self.context.settings.set("last_conversation_id", conversation_id)
        try:
            conversation = self.context.agent.conversation(conversation_id)
        except Exception:  # noqa: BLE001
            return
        self._conversation_title.setText(conversation["title"])
        self._render_transcript(conversation["messages"])
        attachments = conversation["attachments"]
        self._attachments_label.setText(
            "Attached: " + ", ".join(item["name"] for item in attachments) if attachments else ""
        )
        self._refresh_conversations()
        self._composer.setFocus()

    def _on_conversation_selected(self, row: int) -> None:
        if row < 0:
            return
        item = self._conversation_list.item(row)
        if item is None:
            return
        conversation_id = item.data(Qt.ItemDataRole.UserRole)
        if conversation_id != self._conversation_id:
            self._select_conversation(conversation_id)

    def _delete_conversation(self) -> None:
        if self._conversation_id is None:
            return
        answer = QMessageBox.question(self, "Delete conversation", "Delete this conversation and its messages?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.context.agent.delete_conversation(self._conversation_id)
        self._conversation_id = None
        self._refresh_conversations()

    # -- transcript ------------------------------------------------------

    def _render_transcript(self, messages: list[dict[str, Any]]) -> None:
        while self._transcript_layout.count() > 1:
            item = self._transcript_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not messages:
            welcome = QLabel(
                "Ask anything, or give a project task. Tools run only inside the approved folder, "
                "and every write or command asks for your approval."
            )
            welcome.setObjectName("TranscriptEmpty")
            welcome.setWordWrap(True)
            self._transcript_layout.insertWidget(0, welcome)
            return
        for message in messages:
            if message["role"] not in {"user", "assistant"}:
                continue
            bubble = _Bubble(message["role"], message["content"])
            row = QHBoxLayout()
            row.addStretch(1) if message["role"] == "user" else None
            row.addWidget(bubble, 0 if message["role"] == "user" else 1)
            if message["role"] == "assistant":
                row.addStretch(0)
            wrapper = QWidget()
            wrapper.setLayout(row)
            wrapper.setObjectName("BubbleRow")
            self._transcript_layout.insertWidget(self._transcript_layout.count() - 1, wrapper)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _append_stream_bubble(self) -> None:
        bubble = _Bubble("assistant", "")
        row = QHBoxLayout()
        row.addWidget(bubble, 1)
        wrapper = QWidget()
        wrapper.setLayout(row)
        self._transcript_layout.insertWidget(self._transcript_layout.count() - 1, wrapper)
        self._stream_bubble = bubble
        self._stream_conversation = self._conversation_id
        self._scroll_to_bottom()

    # -- sending ---------------------------------------------------------

    def _send(self) -> None:
        text = self._composer.toPlainText().strip()
        if not text or self._worker is not None:
            return
        if self.context.runtime.status.state.value not in {"ready", "generating"}:
            QMessageBox.information(
                self,
                "No model loaded",
                "Load a model in Model Intelligence → Prepare & run, or attach an endpoint there.",
            )
            return
        if self._conversation_id is None:
            self._new_conversation()
        assert self._conversation_id is not None
        conversation_id = self._conversation_id
        self._composer.clear()
        user_bubble = _Bubble("user", text)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(user_bubble)
        wrapper = QWidget()
        wrapper.setLayout(row)
        self._transcript_layout.insertWidget(self._transcript_layout.count() - 1, wrapper)
        self._append_stream_bubble()
        if self._conversation_title.text() == "New conversation":
            self._conversation_title.setText(text.splitlines()[0][:70])
        self._scroll_to_bottom()
        self._send_button.setEnabled(False)
        self._stop_button.setEnabled(True)
        self._activity.setText("Thinking…")
        worker = _SendWorker(self.context, conversation_id, text, self._approval.approve, self)
        self._worker = worker
        worker.completed.connect(self._completed)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._cleanup)
        worker.start()

    def _completed(self, result: dict[str, Any]) -> None:
        self._activity.setText(
            f"Finished in {result.get('steps')} step(s) · {result.get('stopped_reason')}"
        )
        if self._stream_bubble is not None and self._stream_conversation == self._conversation_id:
            if not self._stream_bubble._text:
                self._stream_bubble.append_text(result.get("message", {}).get("content", ""))
        self._stream_bubble = None
        self._refresh_conversations()
        try:
            conversation = self.context.agent.conversation(self._conversation_id or "")
        except Exception:  # noqa: BLE001
            return
        self._conversation_title.setText(conversation["title"])

    def _failed(self, message: str) -> None:
        self._activity.setText("")
        if self._stream_bubble is not None:
            self._stream_bubble.append_text(f"\n\n[Generation failed: {message}]")
        self._stream_bubble = None
        QMessageBox.warning(self, "Agent", message)

    def _cleanup(self) -> None:
        self._worker = None
        self._send_button.setEnabled(True)
        self._stop_button.setEnabled(False)
        self._scroll_to_bottom()

    def _stop(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self._activity.setText("Stop requested…")

    def _attach_file(self) -> None:
        if self._conversation_id is None:
            self._new_conversation()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Attach a file",
            "",
            "Text and documents (*.txt *.md *.py *.json *.toml *.yaml *.yml *.csv *.log *.pdf);;All files (*)",
        )
        if not path or self._conversation_id is None:
            return
        try:
            self.context.agent.attach_file(self._conversation_id, path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Attachment", str(exc))
            return
        conversation = self.context.agent.conversation(self._conversation_id)
        names = ", ".join(item["name"] for item in conversation["attachments"])
        self._attachments_label.setText(f"Attached: {names}")

    # -- events ----------------------------------------------------------

    def _on_core_event(self, name: str, payload: dict[str, Any]) -> None:
        if name == "agent.delta" and payload.get("conversation_id") == self._conversation_id:
            if self._stream_bubble is None:
                self._append_stream_bubble()
            if self._stream_bubble is not None:
                self._stream_bubble.append_text(str(payload.get("text") or ""))
                self._scroll_to_bottom()
        elif name == "agent.tool":
            result = payload.get("result") or {}
            self._activity.setText(
                f"Tool {payload.get('name')} → {'ok' if result.get('ok') else 'failed'}"
            )
        elif name == "runtime.state":
            self._render_model_label()
        elif name == "agent.conversation_created":
            self._refresh_conversations()

    def _render_model_label(self) -> None:
        status = self.context.runtime.status
        if status.model_name and status.state.value in {"ready", "generating"}:
            self._model_label.setText(f"{status.model_name} · {status.state.value}")
        elif status.model_name:
            self._model_label.setText(f"{status.model_name} · {status.state.value.replace('_', ' ')}")
        else:
            self._model_label.setText("No model loaded")

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
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(3000)
