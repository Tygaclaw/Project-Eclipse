"""Reusable desktop widgets that keep the three workspaces visually consistent."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QVBoxLayout,
    QWidget,
)

from .formatting import evidence_text


def clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
            continue
        child = item.layout()
        if child is not None:
            clear_layout(child)


def make_header(title: str, subtitle: str) -> QWidget:
    header = QWidget()
    layout = QVBoxLayout(header)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")
    title_label.setWordWrap(True)
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("PageSubtitle")
    subtitle_label.setWordWrap(True)
    layout.addWidget(title_label)
    layout.addWidget(subtitle_label)
    return header


def make_card(title: str, subtitle: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 22, 24, 24)
    layout.setSpacing(12)
    title_label = QLabel(title)
    title_label.setObjectName("CardTitle")
    title_label.setWordWrap(True)
    layout.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("Muted")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
    return frame, layout


def make_empty_card(title: str, body: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("EmptyCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(26, 26, 26, 28)
    layout.setSpacing(10)
    title_label = QLabel(title)
    title_label.setObjectName("CardTitle")
    title_label.setWordWrap(True)
    body_label = QLabel(body)
    body_label.setObjectName("Muted")
    body_label.setWordWrap(True)
    layout.addWidget(title_label)
    layout.addWidget(body_label)
    return frame


def make_badge(label: Any) -> QLabel:
    badge = QLabel(evidence_text(label))
    badge.setObjectName("EvidenceBadge")
    badge.setProperty("evidence", str(label) if isinstance(label, str) else "unknown")
    badge.setAccessibleName(f"Evidence: {evidence_text(label)}")
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return badge


def add_fact(
    layout: QVBoxLayout,
    label: str,
    value: str,
    evidence: Any | None = None,
) -> QLabel:
    row = QHBoxLayout()
    row.setSpacing(14)
    label_widget = QLabel(label)
    label_widget.setObjectName("FactLabel")
    label_widget.setMinimumWidth(185)
    label_widget.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    value_widget = QLabel(value)
    value_widget.setObjectName("FactValue")
    value_widget.setWordWrap(True)
    value_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    row.addWidget(label_widget)
    row.addWidget(value_widget, 1)
    if evidence is not None:
        row.addWidget(make_badge(evidence), 0, Qt.AlignmentFlag.AlignTop)
    layout.addLayout(row)
    return value_widget


def add_text(layout: QVBoxLayout, text: str, object_name: str = "Muted") -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(object_name)
    widget.setWordWrap(True)
    widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(widget)
    return widget


def planned_capabilities(items: list[tuple[str, str]]) -> QFrame:
    frame, layout = make_card(
        "Planned capabilities",
        "These are architecture commitments, not working features in this build.",
    )
    for title, detail in items:
        row = QHBoxLayout()
        row.setSpacing(14)
        name = QLabel(title)
        name.setObjectName("FactLabel")
        name.setMinimumWidth(185)
        name.setWordWrap(True)
        description = QLabel(detail)
        description.setObjectName("Muted")
        description.setWordWrap(True)
        row.addWidget(name)
        row.addWidget(description, 1)
        layout.addLayout(row)
    return frame