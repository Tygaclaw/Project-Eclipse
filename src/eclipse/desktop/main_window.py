"""Main ECLIPSE window and primary workspace navigation."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from eclipse import __version__

from .workspaces import AgentWorkspace, CapabilityWorkspace, ModelIntelligenceWorkspace

NAV_ITEMS = (
    "Model Intelligence & Inference Platform",
    "Capability Amplification & Knowledge System",
    "ECLIPSE Agent",
)


class MainWindow(QMainWindow):
    """One window with the three required primary workspaces."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ECLIPSE — Local AI Workspace")
        self.setMinimumSize(1080, 720)
        self.resize(1320, 860)
        self.setAccessibleName("ECLIPSE main window")

        central = QWidget()
        central.setObjectName("Root")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(320)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(28, 34, 22, 28)
        sidebar_layout.setSpacing(0)

        brand = QLabel("ECLIPSE")
        brand.setObjectName("Brand")
        brand.setAccessibleName("ECLIPSE")
        tagline = QLabel("Windows-first · local-first AI workspace")
        tagline.setObjectName("BrandTagline")
        tagline.setWordWrap(True)
        sidebar_layout.addWidget(brand)
        sidebar_layout.addSpacing(8)
        sidebar_layout.addWidget(tagline)
        sidebar_layout.addSpacing(34)

        caption = QLabel("PRIMARY WORKSPACES")
        caption.setObjectName("SidebarCaption")
        sidebar_layout.addWidget(caption)
        sidebar_layout.addSpacing(10)

        self.nav = QListWidget()
        self.nav.setObjectName("NavList")
        self.nav.setAccessibleName("Primary workspaces")
        self.nav.setWordWrap(True)
        self.nav.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        for item_text in NAV_ITEMS:
            item = QListWidgetItem(item_text)
            item.setSizeHint(QSize(0, 64))
            item.setToolTip(item_text)
            self.nav.addItem(item)
        sidebar_layout.addWidget(self.nav, 0)

        sidebar_layout.addStretch(1)

        core_caption = QLabel("SHARED CORE")
        core_caption.setObjectName("SidebarCaption")
        core_status = QLabel("Foundation only")
        core_status.setObjectName("SidebarStatus")
        core_detail = QLabel("No model adapter connected")
        core_detail.setObjectName("SidebarFaint")
        core_detail.setWordWrap(True)
        sidebar_layout.addWidget(core_caption)
        sidebar_layout.addSpacing(5)
        sidebar_layout.addWidget(core_status)
        sidebar_layout.addWidget(core_detail)
        sidebar_layout.addSpacing(20)

        atlas_caption = QLabel("MODEL ATLAS")
        atlas_caption.setObjectName("SidebarCaption")
        atlas_status = QLabel("Connected · static read-only")
        atlas_status.setObjectName("SidebarStatus")
        atlas_detail = QLabel("Inspects headers and indexes only")
        atlas_detail.setObjectName("SidebarFaint")
        atlas_detail.setWordWrap(True)
        sidebar_layout.addWidget(atlas_caption)
        sidebar_layout.addSpacing(5)
        sidebar_layout.addWidget(atlas_status)
        sidebar_layout.addWidget(atlas_detail)
        sidebar_layout.addSpacing(24)

        version = QLabel(f"Version {__version__}")
        version.setObjectName("SidebarFaint")
        sidebar_layout.addWidget(version)

        self.stack = QStackedWidget()
        self.stack.setObjectName("WorkspaceStack")
        self.model_workspace = ModelIntelligenceWorkspace()
        self.capability_workspace = CapabilityWorkspace()
        self.agent_workspace = AgentWorkspace()
        self.stack.addWidget(self.model_workspace)
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
            "Static inspection is read-only. No model code is executed and no model file is uploaded."
        )

    def navigate(self, index: int) -> None:
        if 0 <= index < self.stack.count():
            self.nav.setCurrentRow(index)
            self.stack.setCurrentIndex(index)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.model_workspace.shutdown()
        super().closeEvent(event)