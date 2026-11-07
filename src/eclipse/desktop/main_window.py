"""Main ECLIPSE window and primary workspace navigation."""

from __future__ import annotations

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from eclipse import __version__

from .context import AppContext
from .theme import build_stylesheet
from .workspaces import AgentWorkspace, CapabilityWorkspace
from .workspaces.model_platform import ModelIntelligencePlatform

NAV_ITEMS = (
    "Model Intelligence & Inference Platform",
    "Capability Amplification & Knowledge System",
    "ECLIPSE Agent",
)

_STATE_LABELS = {
    "not_loaded": "Not loaded",
    "preparing": "Preparing",
    "starting": "Starting",
    "loading": "Loading",
    "ready": "Ready",
    "generating": "Generating",
    "stopping": "Stopping",
    "unloading": "Unloading",
    "restart_required": "Restart required",
    "failed": "Failed",
    "needs_attention": "Needs attention",
}


class _Relay(QObject):
    event = Signal(str, object)


class MainWindow(QMainWindow):
    """One window with the three required primary workspaces and one shared Core."""

    def __init__(self, context: AppContext | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context or AppContext()
        self.setWindowTitle("ECLIPSE — Local AI Workspace")
        self.setMinimumSize(1080, 720)
        self.resize(1400, 900)
        self.setAccessibleName("ECLIPSE main window")
        self._relay = _Relay(self)
        self._relay.event.connect(self._on_core_event)

        central = QWidget()
        central.setObjectName("Root")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(318)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(26, 30, 20, 24)
        sidebar_layout.setSpacing(0)

        brand = QLabel("ECLIPSE")
        brand.setObjectName("Brand")
        brand.setAccessibleName("ECLIPSE")
        tagline = QLabel("Understand models · amplify capability · work with an agent")
        tagline.setObjectName("BrandTagline")
        tagline.setWordWrap(True)
        sidebar_layout.addWidget(brand)
        sidebar_layout.addSpacing(8)
        sidebar_layout.addWidget(tagline)
        sidebar_layout.addSpacing(30)

        caption = QLabel("PRIMARY WORKSPACES")
        caption.setObjectName("SidebarCaption")
        sidebar_layout.addWidget(caption)
        sidebar_layout.addSpacing(8)

        self.nav = QListWidget()
        self.nav.setObjectName("NavList")
        self.nav.setAccessibleName("Primary workspaces")
        self.nav.setWordWrap(True)
        self.nav.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for item_text in NAV_ITEMS:
            item = QListWidgetItem(item_text)
            item.setSizeHint(QSize(0, 62))
            item.setToolTip(item_text)
            self.nav.addItem(item)
        sidebar_layout.addWidget(self.nav)
        sidebar_layout.addStretch(1)

        core_caption = QLabel("SHARED CORE")
        core_caption.setObjectName("SidebarCaption")
        self._core_status = QLabel("Ready")
        self._core_status.setObjectName("SidebarStatus")
        self._core_detail = QLabel("No model loaded")
        self._core_detail.setObjectName("SidebarFaint")
        self._core_detail.setWordWrap(True)
        self._project_label = QLabel(
            f"Project: {self.context.workspace}" if self.context.workspace else "No project folder attached"
        )
        self._project_label.setObjectName("SidebarFaint")
        self._project_label.setWordWrap(True)
        sidebar_layout.addWidget(core_caption)
        sidebar_layout.addSpacing(5)
        sidebar_layout.addWidget(self._core_status)
        sidebar_layout.addWidget(self._core_detail)
        sidebar_layout.addSpacing(10)
        sidebar_layout.addWidget(self._project_label)
        sidebar_layout.addSpacing(18)

        self._theme_button = QPushButton("Switch to light theme")
        self._theme_button.setObjectName("QuietButton")
        self._theme_button.clicked.connect(self._toggle_theme)
        sidebar_layout.addWidget(self._theme_button)
        sidebar_layout.addSpacing(14)
        version = QLabel(f"Version {__version__}")
        version.setObjectName("SidebarFaint")
        sidebar_layout.addWidget(version)

        self.stack = QStackedWidget()
        self.stack.setObjectName("WorkspaceStack")
        self.model_platform = ModelIntelligencePlatform(self.context)
        self.model_workspace = self.model_platform.inspect
        self.capability_workspace = CapabilityWorkspace(self.context)
        self.agent_workspace = AgentWorkspace(self.context)
        self.stack.addWidget(self.model_platform)
        self.stack.addWidget(self.capability_workspace)
        self.stack.addWidget(self.agent_workspace)

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        for index in range(len(NAV_ITEMS)):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{index + 1}"), self)
            shortcut.activated.connect(lambda target=index: self.navigate(target))

        self.statusBar().showMessage(
            "Local-first. Model files are read-only; every write or command needs your approval."
        )
        for name in ("runtime.state", "runtime.metrics"):
            self.context.events.subscribe(
                name, lambda event, event_name=name: self._relay.event.emit(event_name, event.payload)
            )
        self._refresh_core_status()
        self._apply_theme(str(self.context.settings.get("theme", "dark")))

    def navigate(self, index: int) -> None:
        if 0 <= index < self.stack.count():
            self.nav.setCurrentRow(index)
            self.stack.setCurrentIndex(index)

    def _refresh_core_status(self) -> None:
        status = self.context.runtime.status
        label = _STATE_LABELS.get(status.state.value, status.state.value.title())
        self._core_status.setText(label)
        if status.model_name:
            context_detail = (
                f"{status.model_name} · context "
                f"{status.observed_context or status.requested_context or 'unknown'}"
            )
            if status.state.value in {"ready", "generating"}:
                self._core_detail.setText(context_detail)
            elif status.error:
                self._core_detail.setText(f"{context_detail} · {status.error}")
            else:
                self._core_detail.setText(context_detail)
        else:
            self._core_detail.setText("No model loaded")
        self._project_label.setText(
            f"Project: {self.context.workspace}" if self.context.workspace else "No project folder attached"
        )

    def _on_core_event(self, name: str, payload: dict[str, object]) -> None:
        if name == "runtime.state":
            self._refresh_core_status()

    def _toggle_theme(self) -> None:
        current = str(self.context.settings.get("theme", "dark"))
        target = "light" if current == "dark" else "dark"
        self.context.settings.set("theme", target)
        self._apply_theme(target)

    def _apply_theme(self, theme: str) -> None:
        # Apply to this window so the choice takes effect immediately and the
        # three workspaces inherit the same theme.
        self.setStyleSheet(build_stylesheet(theme))
        self._theme_button.setText(
            "Switch to dark theme" if theme == "light" else "Switch to light theme"
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self.agent_workspace.shutdown()
            self.capability_workspace.shutdown()
            self.model_platform.shutdown()
        finally:
            self.context.shutdown()
        super().closeEvent(event)
