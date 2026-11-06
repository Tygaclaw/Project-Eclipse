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
