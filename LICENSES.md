# Dependency and License Inventory

Last reviewed: 7 November 2026.

## Project license

No project license has been selected. Repository visibility does not itself grant permission to reuse, modify or redistribute the code. The repository owner should choose a license before inviting external contributions or distributing builds.

## Core and CLI

- Python 3.11+ standard library only.
- Third-party runtime dependencies: none (`pyproject.toml` declares `dependencies = []`).
- Build backend: setuptools `>= 68`, declared as a build-system requirement only.
- Tests: Python `unittest` standard library.

## Desktop and packaging (pinned)

`requirements-desktop.txt` and the `desktop`/`packaging` extras pin two dependencies:

| Component | Version | Declared license |
| --- | --- | --- |
| PySide6 (Qt for Python) | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PyInstaller | 6.22.3 | GPLv2-or-later with a special exception allowing PyInstaller to build and distribute non-free programs |

- PySide6 pulls `shiboken6` and the PySide6 module wheels, all carrying the same LGPL-3.0-only / GPL-2.0-only / GPL-3.0-only choice. The development environment also installs `PySide6_Addons`, `PySide6_Pdf` and `PySide6_WebEngine` as wheel dependencies; the application code in `src/eclipse/desktop` imports only `QtCore`, `QtGui` and `QtWidgets`.
- PyInstaller is used only to build the portable Windows package. Its standard hooks are the source of the bootloader and bundled CPython runtime.
- Developer tooling used for verification but not shipped: pip, pip-audit.

## Qt/PySide6 distribution obligations

If the package is redistributed under the LGPLv3 option, the distributor must at minimum include the LGPLv3 text and the Qt/PySide6 notices, preserve the ability for recipients to replace the Qt libraries, provide source for any modifications to Qt, and avoid static linking. The current PyInstaller `onedir` layout keeps the Qt DLLs as separate replaceable files, which is intended to support that requirement, but the layout has not been legally reviewed and the packaged artifact's DLL inventory has not been audited in this environment. Distributing under GPLv3 or a commercial Qt license is the alternative. Selecting the project license and confirming these obligations remain owner decisions before any redistribution.

## Verification — 7 November 2026

`pip-audit 2.10.1` was run against the declared and installed dependency sets:

- `pip-audit -r requirements-desktop.txt` resolved and audited PySide6 6.12.0, the PySide6 module wheels, shiboken6 6.12.0, PyInstaller 6.22.3 and pyinstaller-hooks-contrib 2026.9: **no known vulnerabilities found**.
- `pip-audit --path .venv/lib/python3.12/site-packages` initially reported 12 advisories for the development environment's `pip` 24.0. `pip` is installer tooling, is not listed in the declared requirements and is not bundled by the application. Upgrading that environment to `pip` 26.3 and re-running the scan produced **no known vulnerabilities**.

Limits: this is advisory-database matching (PyPI/OSV) for Python packages. It is not a malware scan, a license-compatibility review, a Qt CVE-in-binary review or a Windows DLL audit, and the packaged artifact's binary contents were not re-inspected here. Owner-side security scanning and release compliance remain open gates.
