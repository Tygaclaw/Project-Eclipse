# GitHub Operating Protocol

## Repository rule

Use a new private repository for the greenfield ECLIPSE implementation. The historical repository `Tygaclaw/Project-Eclipse` is read-only reference and must not be modified as the new product. Suggested new repository name: `ECLIPSE`; verify actual account, permissions and availability before creation.

## Before first write

1. Verify the GitHub connector/tools are available in the active ChatGPT session.
2. Identify the authenticated account and list accessible repositories.
3. Check create/write permissions.
4. Search for an existing new ECLIPSE repository to avoid duplicates.
5. Confirm historical repository identity and avoid writes to it.
6. Create the new private repository or request the exact user action if unavailable.

Never claim access or a write succeeded without tool confirmation.

## Branch and commit discipline

- Keep default branch protected/stable where practical.
- Work on feature branches.
- Use small, meaningful commits.
- Keep commit messages specific.
- Review changed files and commit metadata.
- Use pull requests for meaningful integrated milestones.
- Do not force-push.
- Do not overwrite unrelated user changes.
- Inspect current file/blob SHA before updating a file.
- For multi-file operations use the safest available tree/commit flow; verify final tree.

## Suggested branch names

- `main` — stable baseline.
- `develop` — integration branch if it reduces risk and the team needs it.
- `feature/<area>-<purpose>` — feature work.
- `fix/<area>-<problem>` — focused repair.
- `research/<topic>` — experiments that should not destabilize product code.

Do not create branches merely for ceremony; keep the workflow usable.

## Repository baseline files

At minimum maintain README, STATUS, ARCHITECTURE, CONTINUATION, DECISIONS, TESTING, SECURITY, MODEL_COMPATIBILITY, requirements/acceptance register, phase map, issues and dependency/license inventory.

## CI

Add GitHub Actions only when the project stack is selected. Include appropriate formatting, linting, type/static checks, unit tests, build checks and security checks. Pin actions to trusted versions/SHAs when practical. Avoid leaking secrets into logs.

Clearly distinguish hosted CI from tests requiring Windows, Vulkan, GPU, local files or a large checkpoint.

## Large assets

Do not commit huge model checkpoints into ordinary Git history. Evaluate Git LFS, release assets or appropriate external object storage. Explain cost, quotas and privacy before adopting a paid or usage-limited storage mechanism. Keep small synthetic fixtures for CI.

## Completion evidence

For every milestone, record:
- Commit SHA and branch.
- Changed files/features.
- Commands/workflows executed.
- Actual pass/fail output.
- Tests not run and why.
- Local validation still required.
- Risks and rollback path.

A generated file is not a verified feature. A successful commit is not a successful build.
