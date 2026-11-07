# Security and Privacy

- Treat checkpoints, model repositories, metadata, docs and tool output as untrusted input.
- Never import or execute code from a model repository during static inspection.
- Open original model files read-only and never overwrite original weights.
- Enforce parser limits before allocating or iterating over attacker-controlled lengths/counts. Tokenizer inspection also applies per-file and aggregate JSON/template byte caps, a shared template-count cap, bounded added-token entry scans, clipped previews, and rejects a symlinked inspection root; nested symlinks are reported and skipped.
- Do not commit API keys, passwords, tokens, private prompts, private logs, personal data or local-only sensitive paths.
- Do not commit model checkpoints or generated inspection reports containing local paths unless explicitly reviewed and sanitized.
- Redact secrets in future logs and diagnostic bundles.
- Future terminal/filesystem/network tools must have explicit permissions, path allowlists and resource limits.
- Require confirmation for destructive actions, credential use, external uploads and consequential account operations.
- Do not modify drivers, registry, Windows paging settings or system security settings without explicit approval and rollback instructions.

## Dependency audit — 7 November 2026

- `pip-audit 2.10.1 -r requirements-desktop.txt` reported no known vulnerabilities for PySide6 6.12.0, shiboken6, the PySide6 module wheels, PyInstaller 6.22.3 and pyinstaller-hooks-contrib 2026.9.
- The development environment's `pip` 24.0 carried 12 advisories; it is installer tooling and not a declared or shipped dependency. Upgrading it to 26.3 and re-scanning the environment reported no known vulnerabilities.
- This is advisory-database matching for Python packages. It does not cover Windows binaries, malware, license compatibility or Qt CVEs, and it does not replace the owner's security review before release.
