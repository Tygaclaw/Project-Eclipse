# ADR-001 — Windows-first desktop framework

**Status:** Accepted

**Date:** 2026-11-06

## Context

ECLIPSE needs a beginner-friendly Windows desktop shell that hosts the three
primary workspaces and renders the existing Python Model Atlas contract without
re-deriving model facts. The shared Core and all static inspectors are Python,
so the shell must interoperate with a Python process cheaply, package into a
double-clickable Windows build, and stay maintainable by a small project.

The static-inspection core must remain usable on its own. Any desktop choice
must not force model-format logic to be rewritten in a second language, and it
must not require loading tensor payloads.

## Options considered

- **PySide6 (Qt for Python).** Official LGPL Qt bindings with a
  `PyInstaller`-friendly onedir packaging story. Same-language call path to the
  existing inspectors, mature widgets, accessible controls, and a large
  deployment ecosystem.
- **WPF (.NET).** Native Windows look and excellent tooling, but would require
  re-implementing or out-of-process bridging the Python core, and it locks the
  shell to Windows only.
- **Tauri 2 (Rust + web view).** Small binaries and a web UI, but adds a Rust
  toolchain and a JavaScript front end, and requires a sidecar or IPC layer to
  reach the Python core.
- **Avalonia (.NET).** Cross-platform XAML, but shares WPF's language/bridge
  cost and did not need to be chosen for a Windows-first milestone.

## Decision

Use **PySide6 `6.12.0`** for the desktop shell, packaged with **PyInstaller
`6.22.3`**, and target Windows x64 first.

- The shell imports the existing `eclipse` package directly; the frozen build
  exposes a `--atlas-backend` mode that dispatches to the unchanged
  `build-atlas` CLI so the packaged app and the command line share one code
  path.
- The Model Atlas UI renders the existing versioned JSON contract; no parsing
  is duplicated in the UI layer.
- Desktop dependencies are optional and pinned in `requirements-desktop.txt`.

## Consequences

- One language and one test runner for core and shell; no IPC schema beyond the
  existing JSON atlas contract.
- PyInstaller `onedir` is used for faster startup and simpler DLL handling on
  Windows; the provided spec bundles hidden imports for the inspector modules.
- The GUI depends on Qt and its platform plugins, so a Linux/offscreen test
  environment needs the usual Qt runtime libraries (`libegl1`, `libgl1`,
  `libxkbcommon0`, `libdbus-1-3`, `libfontconfig1`).
- This decision can be revisited if the shell must become fully cross-platform
  or if a web front end is later required; the atlas contract is UI-agnostic
  and would survive such a change.
