# Windows Local Validation Runbook

This document defines how ChatGPT must hand local tests to the user. The user is a beginner; instructions must be exact and safe.

## 1. When to request local testing

Only request a user test when the test genuinely requires the user's Windows machine, local model files/API, RTX 2060 Super/Vulkan GPU, Obsidian vault, local checkpoint storage, desktop install or an integration inaccessible to ChatGPT/GitHub CI.

Run all independent GitHub/CI/unit/build/static checks first when practical. Stop at a specific user-validation gate; do not claim it passed.

## 2. Required format for every test request

Provide:

1. **Why we're testing:** one short plain-English explanation.
2. **What this will do:** exact changes, if any.
3. **Risk level:** default should be low; state whether admin is needed (normal PowerShell is preferred).
4. **Before you start:** files to save/close, model state or disk-space requirements.
5. **Step-by-step clicks:** exact Windows navigation.
6. **Exact command:** full copy/paste-ready PowerShell commands, without placeholders.
7. **Expected result:** exact text, window, output file or status to look for.
8. **What to send back:** exact terminal output, screenshot or log path; never ask for API secrets.
9. **Troubleshooting:** likely error messages and safe next steps.
10. **Undo/cleanup:** how to stop, restore or remove generated test artifacts without touching the original model.

## 3. Command safety

- Use normal PowerShell unless administrator privileges are truly required.
- Explain any administrator requirement before asking the user.
- Do not change drivers, Windows paging/virtual memory, registry, security settings or global environment variables without explicit approval and a rollback plan.
- Never ask the user to paste an API-key value into chat.
- Use the existing secret file/local environment variable securely.
- Avoid commands that delete, overwrite or move original model/checkpoint files.
- Prefer a project-local test workspace and explicit output path.
- Give a clean stop command for long-running servers/processes.

## 4. Qwen baseline reminders

Historical known-good model: Qwen3.5-9B Q4_K_M. Historical preferred context target: 262,144 tokens; a temporary 8K run was diagnostic only. Existing llama.cpp Vulkan setup and local API were reported working. Do not reconfigure by default. If a new adapter test is needed, test the new integration narrowly and preserve the established setup.

Historical API secret location (path only; never its value): `%LOCALAPPDATA%\Qwen35-9B\llama-api-key.txt`.

## 5. Stop gate and return

The local test is `WAITING_FOR_USER_VALIDATION` until the user returns actual evidence. Review it, diagnose failures, update GitHub and continue. Do not ask the user to run the same test again unless a controlled retest is justified.
