"""ECLIPSE desktop visual system.

A refined dark navy base with restrained cyan accents, readable typography,
visible focus states and spacious cards. Advanced values remain behind explicit
disclosure controls.
"""

from __future__ import annotations

COLORS = {
    "base": "#070c15",
    "sidebar": "#0a1220",
    "surface": "#0d1626",
    "surface_raised": "#111d30",
    "border": "#1f3350",
    "border_strong": "#2b4a6f",
    "text": "#e9f2ff",
    "muted": "#93a9c6",
    "faint": "#6f87a6",
    "cyan": "#39d8ea",
    "cyan_soft": "#7ceaf5",
    "warning": "#f3c77a",
    "danger": "#ff8794",
    "success": "#74d9a0",
}


def build_stylesheet() -> str:
    return """
    QMainWindow, QWidget#Root {
        background: #070c15;
    }
    QWidget {
        color: #e9f2ff;
        font-family: "Segoe UI Variable", "Segoe UI", "Noto Sans", sans-serif;
        font-size: 14px;
    }
    QWidget#Sidebar {
        background: #0a1220;
        border-right: 1px solid #1f3350;
    }
    QLabel#Brand {
        color: #f2fbff;
        font-size: 26px;
        font-weight: 800;
        letter-spacing: 5px;
    }
    QLabel#BrandTagline {
        color: #7f97b6;
        font-size: 12px;
        letter-spacing: 1px;
    }
    QLabel#SidebarCaption {
        color: #7f97b6;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 2px;
    }
    QLabel#SidebarStatus {
        color: #c6d8ee;
        font-size: 13px;
    }
    QLabel#SidebarFaint {
        color: #6f87a6;
        font-size: 11px;
    }
    QListWidget#NavList {
        background: transparent;
        border: none;
        padding: 4px;
        outline: none;
    }
    QListWidget#NavList::item {
        color: #b9cbe2;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 11px;
        padding: 13px 14px;
        margin: 3px 2px;
    }
    QListWidget#NavList::item:hover {
        background: #0f1d2f;
        color: #e9f2ff;
    }
    QListWidget#NavList::item:selected {
        background: #113141;
        color: #f4feff;
        border: 1px solid #2a6f82;
    }
    QListWidget#NavList:focus {
        border: 1px solid #39d8ea;
        border-radius: 12px;
    }
    QStackedWidget#WorkspaceStack {
        background: transparent;
    }
    QLabel#PageTitle {
        color: #f4faff;
        font-size: 30px;
        font-weight: 750;
    }
    QLabel#PageSubtitle {
        color: #9fb4cf;
        font-size: 15px;
    }
    QFrame#Card {
        background: #0d1626;
        border: 1px solid #1f3350;
        border-radius: 14px;
    }
    QFrame#EmptyCard {
        background: #0b1524;
        border: 1px dashed #2a4568;
        border-radius: 14px;
    }
    QLabel#CardTitle {
        color: #eef8ff;
        font-size: 17px;
        font-weight: 700;
    }
    QLabel#Muted {
        color: #93a9c6;
    }
    QLabel#Faint {
        color: #6f87a6;
        font-size: 12px;
    }
    QLabel#FactLabel {
        color: #8fa6c4;
        font-size: 13px;
    }
    QLabel#FactValue {
        color: #eef7ff;
        font-size: 14px;
        font-weight: 600;
    }
    QLabel#StatusLine {
        color: #9fb4cf;
    }
    QLabel#ErrorBox {
        background: #2a1219;
        color: #ffc2ca;
        border: 1px solid #6b2b3a;
        border-radius: 10px;
        padding: 12px;
    }
    QLabel#WarningText {
        color: #f3c77a;
    }
    QLabel#SuccessText {
        color: #74d9a0;
    }
    QLabel#CodeBlock {
        color: #c6e4ff;
        background: #0a1422;
        border: 1px solid #1f3350;
        border-radius: 8px;
        padding: 10px;
    }
    QLabel#EvidenceBadge {
        border-radius: 8px;
        padding: 3px 9px;
        font-size: 11px;
        font-weight: 700;
    }
    QLabel#EvidenceBadge[evidence="observed"],
    QLabel#EvidenceBadge[evidence="observed_metadata"],
    QLabel#EvidenceBadge[evidence="observed_header"] {
        background: #0e3540;
        color: #7ceaf5;
        border: 1px solid #1d6c7c;
    }
    QLabel#EvidenceBadge[evidence="derived"],
    QLabel#EvidenceBadge[evidence="declared"] {
        background: #2a2413;
        color: #f3c77a;
        border: 1px solid #6b5526;
    }
    QLabel#EvidenceBadge[evidence="unknown"],
    QLabel#EvidenceBadge[evidence="partial"] {
        background: #2a1620;
        color: #ffb3bc;
        border: 1px solid #6b2b3a;
    }
    QPushButton {
        background: #132238;
        border: 1px solid #28456a;
        border-radius: 9px;
        padding: 10px 18px;
        color: #e9f2ff;
        font-weight: 600;
    }
    QPushButton:hover {
        background: #18304c;
        border-color: #39d8ea;
    }
    QPushButton:pressed {
        background: #0f1c2e;
    }
    QPushButton:focus {
        border: 1px solid #7ceaf5;
    }
    QPushButton:disabled {
        color: #5c7090;
        background: #0e1726;
        border-color: #1a2a40;
    }
    QPushButton#PrimaryButton {
        background: #39d8ea;
        color: #04141a;
        border-color: #39d8ea;
    }
    QPushButton#PrimaryButton:hover {
        background: #62e6f5;
    }
    QPushButton#PrimaryButton:disabled {
        background: #17323a;
        color: #57727a;
        border-color: #17323a;
    }
    QPushButton#QuietButton {
        background: transparent;
        border: 1px solid #28456a;
    }
    QPushButton#DangerButton {
        background: #341722;
        border-color: #6b2b3a;
        color: #ffc2ca;
    }
    QPushButton#DangerButton:hover {
        background: #431d2b;
    }
    QToolButton#Disclosure {
        color: #8fd9e5;
        background: transparent;
        border: none;
        padding: 6px 0;
        font-weight: 600;
        text-align: left;
    }
    QToolButton#Disclosure:hover {
        color: #bff6ff;
    }
    QProgressBar {
        background: #0a1422;
        border: 1px solid #1f3350;
        border-radius: 6px;
        height: 8px;
        text-align: center;
    }
    QProgressBar::chunk {
        background: #39d8ea;
        border-radius: 5px;
    }
    QScrollArea#ResultsScroll,
    QScrollArea#ResultsScroll > QWidget > QWidget {
        background: transparent;
        border: none;
    }
    QStatusBar {
        background: #08101c;
        color: #7f97b6;
        border-top: 1px solid #1f3350;
    }
    """