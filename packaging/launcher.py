"""PyInstaller launcher for the ECLIPSE desktop application."""

from __future__ import annotations

from eclipse.desktop.app import main

if __name__ == "__main__":
    raise SystemExit(main())