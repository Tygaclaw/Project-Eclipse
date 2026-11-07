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


def _dark_stylesheet() -> str:
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


def _light_stylesheet() -> str:
    return """
    QMainWindow, QWidget#Root {
        background: #f5f9fe;
    }
    QWidget {
        color: #10233a;
        font-family: "Segoe UI Variable", "Segoe UI", "Noto Sans", sans-serif;
        font-size: 14px;
    }
    QWidget#Sidebar {
        background: #eaf2fb;
        border-right: 1px solid #cfdeee;
    }
    QLabel#Brand {
        color: #0a2a44;
        font-size: 26px;
        font-weight: 800;
        letter-spacing: 5px;
    }
    QLabel#BrandTagline, QLabel#SidebarFaint, QLabel#Faint {
        color: #5a718c;
        font-size: 12px;
    }
    QLabel#SidebarCaption {
        color: #5a718c;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 2px;
    }
    QLabel#SidebarStatus {
        color: #16405f;
        font-size: 13px;
        font-weight: 600;
    }
    QListWidget#NavList {
        background: transparent;
        border: none;
        padding: 4px;
        outline: none;
    }
    QListWidget#NavList::item {
        color: #2c4763;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 11px;
        padding: 13px 14px;
        margin: 3px 2px;
    }
    QListWidget#NavList::item:hover { background: #dbe9f7; color: #0d2a44; }
    QListWidget#NavList::item:selected {
        background: #d3eff4;
        color: #06333d;
        border: 1px solid #71c4d2;
    }
    QLabel#PageTitle { color: #0a2137; font-size: 30px; font-weight: 750; }
    QLabel#PageSubtitle { color: #46607c; font-size: 15px; }
    QFrame#Card {
        background: #ffffff;
        border: 1px solid #d5e2f0;
        border-radius: 14px;
    }
    QFrame#EmptyCard {
        background: #f9fcff;
        border: 1px dashed #b9cfe4;
        border-radius: 14px;
    }
    QLabel#CardTitle { color: #0b2439; font-size: 17px; font-weight: 700; }
    QLabel#Muted { color: #46607c; }
    QLabel#FactLabel { color: #4a637d; font-size: 13px; }
    QLabel#FactValue { color: #0d2740; font-size: 14px; font-weight: 600; }
    QLabel#WarningText { color: #8a5a00; }
    QLabel#SuccessText { color: #0c6b42; }
    QLabel#ErrorBox {
        background: #fdeef1;
        color: #8a1f31;
        border: 1px solid #efc3cb;
        border-radius: 10px;
        padding: 12px;
    }
    QLabel#CodeBlock {
        color: #123; background: #f2f8ff; border: 1px solid #d5e2f0;
        border-radius: 8px; padding: 10px;
    }
    QPushButton {
        background: #ffffff;
        border: 1px solid #c4d8ea;
        border-radius: 9px;
        padding: 10px 18px;
        color: #123049;
        font-weight: 600;
    }
    QPushButton:hover { background: #eef7ff; border-color: #5fb9c7; }
    QPushButton:disabled { color: #92a5b8; background: #f4f8fc; border-color: #dbe7f2; }
    QPushButton#PrimaryButton { background: #0e8fa3; color: #ffffff; border-color: #0e8fa3; }
    QPushButton#PrimaryButton:hover { background: #0b7687; }
    QPushButton#PrimaryButton:disabled { background: #a9d4db; border-color: #a9d4db; color: #f4ffff; }
    QPushButton#QuietButton { background: transparent; border: 1px solid #c4d8ea; }
    QPushButton#DangerButton { background: #fdf0f2; border-color: #e9c3ca; color: #8a1f31; }
    QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
        background: #ffffff;
        border: 1px solid #c9dcec;
        border-radius: 8px;
        padding: 7px 9px;
        color: #10233a;
        selection-background-color: #b9e6ed;
    }
    QPlainTextEdit#Composer { font-size: 14px; }
    QListWidget, QTreeWidget, QTableWidget {
        background: #ffffff;
        border: 1px solid #d5e2f0;
        border-radius: 9px;
        padding: 4px;
    }
    QListWidget::item { padding: 7px; border-radius: 7px; }
    QListWidget::item:selected { background: #d8eef5; color: #073440; }
    QTabWidget::pane { border: 1px solid #d5e2f0; border-radius: 10px; background: #ffffff; }
    QTabBar::tab { padding: 9px 16px; color: #46607c; }
    QTabBar::tab:selected { color: #0b6d7c; font-weight: 700; }
    QToolButton#Disclosure { color: #0b6d7c; background: transparent; border: none; padding: 6px 0; font-weight: 600; }
    QProgressBar { background: #eaf2fa; border: 1px solid #d5e2f0; border-radius: 6px; height: 8px; }
    QProgressBar::chunk { background: #0e8fa3; border-radius: 5px; }
    QScrollArea#ResultsScroll, QScrollArea#ResultsScroll > QWidget > QWidget,
    QScrollArea#ChatScroll, QScrollArea#ChatScroll > QWidget > QWidget,
    QWidget#Transcript { background: transparent; border: none; }
    QStatusBar { background: #eaf2fb; color: #4a637d; border-top: 1px solid #cfdeee; }
    QLabel#EvidenceBadge { border-radius: 8px; padding: 3px 9px; font-size: 11px; font-weight: 700; }
    QLabel#EvidenceBadge[evidence="observed"] { background: #d9f4f8; color: #05545f; border: 1px solid #93d3dc; }
    QLabel#EvidenceBadge[evidence="derived"], QLabel#EvidenceBadge[evidence="declared"] {
        background: #fdf3d8; color: #745107; border: 1px solid #e8d296;
    }
    QLabel#EvidenceBadge[evidence="unknown"], QLabel#EvidenceBadge[evidence="partial"] {
        background: #fde9ec; color: #8a2233; border: 1px solid #eec3ca;
    }
    """


def _extra_styles(theme: str) -> str:
    if theme == "light":
        palette = {
            "header": "#ffffff",
            "border": "#d5e2f0",
            "text": "#10233a",
            "muted": "#46607c",
            "chip": "#e6f5f8",
            "chip_text": "#07525e",
            "user": "#dff3f7",
            "assistant": "#ffffff",
            "activity": "#4a637d",
            "sidebar": "#f0f6fd",
        }
    else:
        palette = {
            "header": "#0b1524",
            "border": "#1f3350",
            "text": "#e9f2ff",
            "muted": "#93a9c6",
            "chip": "#103442",
            "chip_text": "#8ef0fb",
            "user": "#123141",
            "assistant": "#0d1626",
            "activity": "#8fa6c4",
            "sidebar": "#0a1524",
        }
    return f"""
    QWidget#ChatSidebar {{ background: {palette['sidebar']}; border-right: 1px solid {palette['border']}; }}
    QWidget#ChatHeader {{ background: {palette['header']}; border-bottom: 1px solid {palette['border']}; }}
    QLabel#ChatTitle {{ font-size: 17px; font-weight: 700; color: {palette['text']}; }}
    QLabel#ModelChip {{
        background: {palette['chip']}; color: {palette['chip_text']};
        border-radius: 9px; padding: 5px 11px; font-size: 12px; font-weight: 600;
    }}
    QLabel#PanelTitle {{ font-size: 16px; font-weight: 700; color: {palette['text']}; }}
    QLabel#ActivityLine {{ color: {palette['activity']}; font-size: 12px; }}
    QFrame#UserBubble {{ background: {palette['user']}; border-radius: 12px; }}
    QFrame#AssistantBubble {{ background: {palette['assistant']}; border: 1px solid {palette['border']}; border-radius: 12px; }}
    QLabel#BubbleText {{ color: {palette['text']}; font-size: 14px; }}
    QLabel#TranscriptEmpty {{ color: {palette['muted']}; font-size: 14px; padding: 24px; }}
    QLabel#ObjectiveTitle {{ font-size: 14px; font-weight: 700; color: {palette['text']}; }}
    QLabel#RuntimeState {{
        font-size: 15px; font-weight: 700; color: {palette['text']};
        padding: 4px 10px; border-radius: 8px; background: {palette['chip']};
    }}
    QWidget#ModelList, QWidget#TaskList {{ background: transparent; border: none; }}
    QPlainTextEdit#EvidenceOutput {{ font-family: Consolas, "Courier New", monospace; font-size: 12px; }}
    QTabWidget#WorkspaceTabs::pane {{ border: none; }}
    """


def build_stylesheet(theme: str = "dark") -> str:
    """Return the single application stylesheet for a theme."""

    if theme == "light":
        return _light_stylesheet() + _extra_styles("light")
    return _dark_stylesheet() + _extra_styles("dark")