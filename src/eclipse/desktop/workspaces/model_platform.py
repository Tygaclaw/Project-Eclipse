"""Inspect / Prepare / Run container for the first workspace."""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from ..context import AppContext
from ..runtime_panel import ModelRuntimePanel
from .model_intelligence import ModelIntelligenceWorkspace


class ModelIntelligencePlatform(QWidget):
    """Model Intelligence & Inference Platform: two coherent sub-views."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self.setObjectName("ModelIntelligencePlatform")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("WorkspaceTabs")
        self.inspect = ModelIntelligenceWorkspace()
        self.runtime = ModelRuntimePanel(context)
        self.tabs.addTab(self.inspect, "Inspect & feasibility")
        self.tabs.addTab(self.runtime, "Prepare & run")
        layout.addWidget(self.tabs)

        self.context.events.subscribe("runtime.state", lambda _event: self._mark_running())

    def _mark_running(self) -> None:
        status = self.context.runtime.status
        label = "Prepare & run"
        if status.model_name:
            label = f"Prepare & run · {status.model_name}"
        self.tabs.setTabText(1, label[:60])

    def show_runtime(self) -> None:
        self.tabs.setCurrentIndex(1)

    def shutdown(self) -> None:
        self.inspect.shutdown()
        self.runtime.shutdown()
