"""Desktop application entry point and backend dispatch."""

from __future__ import annotations

import os
import sys
from typing import Sequence

from PySide6.QtGui import QFont, QFontInfo
from PySide6.QtWidgets import QApplication

from eclipse import __version__

from .main_window import MainWindow
from .theme import build_stylesheet


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication(list(sys.argv if argv is None else argv))
    application.setApplicationName("ECLIPSE")
    application.setApplicationDisplayName("ECLIPSE")
    application.setOrganizationName("ECLIPSE")
    application.setApplicationVersion(__version__)
    application.setStyle("Fusion")

    font = QFont("Segoe UI Variable", 10)
    if not QFontInfo(font).exactMatch():
        font = QFont("Segoe UI", 10)
    application.setFont(font)
    application.setStyleSheet(build_stylesheet())
    return application


def run_gui(argv: Sequence[str] | None = None) -> int:
    application = create_application(argv)
    window = MainWindow()
    window.show()
    return application.exec()


def _ensure_standard_streams() -> None:
    for name, descriptor in (("stdout", 1), ("stderr", 2)):
        if getattr(sys, name) is None:
            try:
                setattr(
                    sys,
                    name,
                    os.fdopen(
                        descriptor,
                        "w",
                        encoding="utf-8",
                        errors="replace",
                        buffering=1,
                        closefd=False,
                    ),
                )
            except OSError:
                pass


def _run_backend(argv: Sequence[str]) -> int:
    _ensure_standard_streams()
    index = list(argv).index("--atlas-backend")
    backend_args = ["build-atlas", *argv[index + 1 :]]
    from eclipse.__main__ import main as cli_main

    return cli_main(backend_args)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--atlas-backend" in arguments:
        return _run_backend(arguments)
    return run_gui(arguments)


if __name__ == "__main__":
    raise SystemExit(main())