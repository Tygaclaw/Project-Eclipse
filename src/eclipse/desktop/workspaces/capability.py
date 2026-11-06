"""Capability Amplification & Knowledge System workspace."""

from __future__ import annotations

from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from ..widgets import (
    add_text,
    make_card,
    make_empty_card,
    make_header,
    planned_capabilities,
)


class CapabilityWorkspace(QWidget):
    """Honest, navigable placeholder for the capability workstream."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CapabilityWorkspace")
        self.setAccessibleName("Capability Amplification and Knowledge System")

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
                "Capability Amplification & Knowledge System",
                "Planning, research, verification, recovery and a human-readable knowledge library "
                "for long, reliable work.",
            )
        )

        status_card, status_layout = make_card(
            "Current status",
            "This workspace is present and navigable, but its capabilities are not implemented yet.",
        )
        add_text(
            status_layout,
            "Not yet implemented: planning, research/context retrieval, task-scoped tools, "
            "execution, verification, recovery, correction memory, skills and Obsidian integration.",
            "WarningText",
        )
        add_text(
            status_layout,
            "No task is running, no tool is connected and no knowledge base has been indexed. "
            "This screen does not simulate progress or results.",
        )
        layout.addWidget(status_card)

        layout.addWidget(
            make_empty_card(
                "Nothing to run yet",
                "Capability work will appear here once the shared Core, permission broker and "
                "verified execution loop exist. Until then this workspace only explains the plan.",
            )
        )

        layout.addWidget(
            planned_capabilities(
                [
                    ("Capability Watchdog", "Detect stalled or looping work and verify task-level outcomes."),
                    ("Planner", "Turn a goal into steps, acceptance criteria and recovery points."),
                    ("Research & context", "Retrieve project knowledge with clear provenance."),
                    ("Scoped tools", "Run only approved tools inside explicit filesystem and network limits."),
                    ("Verification & recovery", "Check results, correct mistakes and roll back safely."),
                    ("Correction memory & skills", "Reuse verified fixes and specialised procedures."),
                    ("Obsidian knowledge", "Promote approved notes into a searchable knowledge library."),
                ]
            )
        )

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)