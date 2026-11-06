"""ECLIPSE Agent workspace."""

from __future__ import annotations

from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from ..widgets import (
    add_text,
    make_card,
    make_empty_card,
    make_header,
    planned_capabilities,
)


class AgentWorkspace(QWidget):
    """Honest placeholder until a verified model adapter and tools exist."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AgentWorkspace")
        self.setAccessibleName("ECLIPSE Agent")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("ResultsScroll")
        scroll.setWidgetResizable(True)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(44, 40, 44, 48)
        layout.setSpacing(22)

        layout.addWidget(
            make_header(
                "ECLIPSE Agent",
                "A familiar conversational workspace that can use shared ECLIPSE capabilities through "
                "controlled, permissioned tools.",
            )
        )

        status_card, status_layout = make_card(
            "No model adapter connected",
            "Chat is intentionally unavailable in this build.",
        )
        add_text(
            status_layout,
            "This screen does not accept messages and will not generate replies. There is no "
            "connected local model adapter, memory store, permission broker or tool registry yet.",
            "WarningText",
        )
        add_text(
            status_layout,
            "The model selection, conversation history, files, project context, agent planning and "
            "approval controls below are planned capabilities, not active features.",
        )
        layout.addWidget(status_card)

        layout.addWidget(
            make_empty_card(
                "Chat is not available yet",
                "A working Agent needs a verified inference adapter, shared memory and an explicit "
                "permission boundary. Until those are integrated and tested, this workspace stays "
                "read-only and honest.",
            )
        )

        layout.addWidget(
            planned_capabilities(
                [
                    ("Model selection", "Choose from a local model registry with provenance."),
                    ("Conversation history", "Resume saved conversations and attachments."),
                    ("Project context", "Bring approved files and notes into a task."),
                    ("Shared memory", "Use the same memory and knowledge as the other workspaces."),
                    ("Planned multi-step work", "Show steps, progress, verification and recovery."),
                    ("Safe tools", "Use project-scoped tools only after explicit permission."),
                    ("Approval & stop control", "Approve consequential actions and stop running work."),
                ]
            )
        )

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)