#!/usr/bin/env python3
"""Model-independent, deterministic review stage for autonomous ECLIPSE work.

The implementation model may not review its own claim of success. This module
inspects the proposed change set against objective evidence rules before the
controller commits:

- a test file may not be deleted or newly skipped;
- a backlog item may not be marked ``VERIFIED*`` without substantive,
  resolvable acceptance evidence and supporting test changes;
- a status record may not newly claim the whole backlog is complete while
  backlog items remain unfinished.

It reads only Git metadata and small text files, never runs project code, and
has no repository write access. Exit code 0 means accepted; 1 means the review
rejected the change; 2 means the reviewer could not run.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "origin/main"

ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*-\d+$")
TEST_PATH_PATTERN = re.compile(r"(?:tests/[\w./-]+\.py|\btest_[A-Za-z0-9_]+\.py\b)")
URL_PATTERN = re.compile(r"https?://\S+")
SKIP_PATTERN = re.compile(
    r"^[ \t]*(?:@unittest\.skip|@pytest\.mark\.skip|(?:self\.)?skipTest\()",
    re.MULTILINE,
)

VERIFIED_PREFIX = "VERIFIED"
TEST_ROOT = "tests/"
COMPLETION_CLAIMS = (
    "100% complete",
    "all backlog items are complete",
    "all backlog items complete",
    "the backlog is complete",
    "the product is complete",
    "all requirements are met",
    "all requirements satisfied",
)
EVIDENCE_KEYWORDS = (
    "test", "tests", "unittest", "ci", "passed", "passes", "evidence",
    "verified", "pr #", "run #",
)


class ReviewError(RuntimeError):
    """Raised when the review cannot inspect the repository."""


@dataclass(frozen=True)
class FileChange:
    path: str
    change_type: str  # add | modify | delete
    old_text: str | None = None
    new_text: str | None = None


@dataclass(frozen=True)
class BacklogItem:
    item_id: str
    evidence: str
    status: str
    line_number: int


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ReviewResult:
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def blocking(self) -> tuple[Finding, ...]:
        return self.findings

    @property
    def accepted(self) -> bool:
        return not self.findings

    def to_text(self) -> str:
        if self.accepted:
            return "Independent review accepted the change set."
        lines = ["Independent review REJECTED the change set:"]
        lines.extend(f"- [{f.code}] {f.message}" + (f" ({f.path})" if f.path else "") for f in self.findings)
        return "\n".join(lines)


def normalize_status(status: str) -> str:
    return status.strip().strip("*` ").upper()


def is_verified(status: str) -> bool:
    return normalize_status(status).startswith(VERIFIED_PREFIX)


def is_unfinished(status: str) -> bool:
    normalized = normalize_status(status)
    return not is_verified(normalized)


def is_test_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith(TEST_ROOT) and normalized.endswith(".py")


def parse_backlog(text: str) -> dict[str, BacklogItem]:
    """Return backlog items keyed by ID from a Markdown table."""
    items: dict[str, BacklogItem] = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 4:
            continue
        item_id = cells[0].strip("*` ")
        if not ID_PATTERN.match(item_id):
            continue
        status = cells[-1]
        evidence = " | ".join(cells[1:-1])
        items[item_id] = BacklogItem(item_id, evidence, status, line_number)
    return items


def count_skips(text: str) -> int:
    return len(SKIP_PATTERN.findall(text))


def referenced_test_paths(evidence: str) -> list[str]:
    references: list[str] = []
    for match in TEST_PATH_PATTERN.findall(evidence):
        normalized = match.replace("\\", "/")
        if not normalized.startswith(TEST_ROOT):
            normalized = TEST_ROOT + normalized.split("/")[-1]
        references.append(normalized)
    return references


def has_substantive_evidence(evidence: str) -> bool:
    stripped = evidence.strip()
    if len(stripped) < 8:
        return False
    if URL_PATTERN.search(stripped) or TEST_PATH_PATTERN.search(stripped):
        return True
    lowered = stripped.lower()
    return any(keyword in lowered for keyword in EVIDENCE_KEYWORDS)


def review_file_changes(changes: Iterable[FileChange]) -> ReviewResult:
    findings: list[Finding] = []
    for change in changes:
        if change.change_type == "delete" and is_test_path(change.path):
            findings.append(Finding(
                "deleted_test_file",
                f"Test file was deleted: {change.path}",
                change.path,
            ))
            continue
        if not is_test_path(change.path) or change.new_text is None:
            continue
        before = count_skips(change.old_text or "")
        after = count_skips(change.new_text)
        if after > before:
            findings.append(Finding(
                "skipped_test_added",
                f"New test skip was introduced in {change.path} ({before} -> {after})",
                change.path,
            ))
    return ReviewResult(tuple(findings))


def review_backlog(
    before_text: str | None,
    after_text: str | None,
    changed_paths: Sequence[str],
    exists: Callable[[str], bool],
) -> ReviewResult:
    """Reject a backlog item newly marked verified without real evidence."""
    before_items = parse_backlog(before_text or "")
    after_items = parse_backlog(after_text or "")
    test_changes = [path for path in changed_paths if is_test_path(path)]
    findings: list[Finding] = []
    for item_id, item in after_items.items():
        if not is_verified(item.status):
            continue
        previous = before_items.get(item_id)
        if previous is not None and is_verified(previous.status):
            continue
        evidence = item.evidence
        if not has_substantive_evidence(evidence):
            findings.append(Finding(
                "false_completion_claim",
                f"{item_id} marked {normalize_status(item.status)} without substantive acceptance evidence",
                "AUTONOMOUS_BACKLOG.md",
            ))
            continue
        missing = [ref for ref in referenced_test_paths(evidence) if not exists(ref)]
        if missing:
            findings.append(Finding(
                "false_completion_claim",
                f"{item_id} evidence references missing test file(s): {', '.join(missing)}",
                "AUTONOMOUS_BACKLOG.md",
            ))
            continue
        if not test_changes and not URL_PATTERN.search(evidence):
            findings.append(Finding(
                "false_completion_claim",
                f"{item_id} marked {normalize_status(item.status)} without changed tests or a CI/PR record",
                "AUTONOMOUS_BACKLOG.md",
            ))
    return ReviewResult(tuple(findings))


def review_completion_claims(
    filename: str,
    before_text: str | None,
    after_text: str | None,
    backlog: dict[str, BacklogItem],
) -> ReviewResult:
    """Reject a newly added whole-project completion claim while work remains."""
    before_lowered = (before_text or "").lower()
    after_lowered = (after_text or "").lower()
    findings: list[Finding] = []
    unfinished = [item.item_id for item in backlog.values() if is_unfinished(item.status)]
    for claim in COMPLETION_CLAIMS:
        if claim in after_lowered and claim not in before_lowered:
            findings.append(Finding(
                "false_completion_claim",
                f"{filename} newly claims completion ({claim!r}) while {len(unfinished)} "
                "backlog item(s) remain unfinished",
                filename,
            ))
    return ReviewResult(tuple(findings))


def _run_git(repo_root: Path, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise ReviewError(
            f"git {' '.join(args)} failed: {(completed.stderr or completed.stdout).strip()}"
        )
    return completed


def _read_base_text(repo_root: Path, base_ref: str, path: str) -> str | None:
    completed = _run_git(repo_root, ["show", f"{base_ref}:{path}"], check=False)
    if completed.returncode != 0:
        return None
    return completed.stdout


def _read_current_text(repo_root: Path, path: str) -> str | None:
    target = repo_root / path
    if not target.is_file() or target.is_symlink():
        return None
    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def collect_worktree_changes(repo_root: Path, base_ref: str) -> list[FileChange]:
    """Describe tracked and untracked working-tree changes relative to a base."""
    tracked = _run_git(repo_root, ["diff", "--name-status", "--no-renames", base_ref]).stdout
    changes: dict[str, FileChange] = {}
    for line in tracked.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        code, path = parts[0], parts[-1]
        if code.startswith("D"):
            change_type = "delete"
        elif code.startswith("A"):
            change_type = "add"
        else:
            change_type = "modify"
        changes[path] = _describe_change(repo_root, base_ref, path, change_type)

    untracked = _run_git(repo_root, ["ls-files", "--others", "--exclude-standard"]).stdout
    for path in untracked.splitlines():
        if path and path not in changes:
            changes[path] = _describe_change(repo_root, base_ref, path, "add")
    return list(changes.values())


def _describe_change(repo_root: Path, base_ref: str, path: str, change_type: str) -> FileChange:
    if is_test_path(path):
        old_text = None if change_type == "add" else _read_base_text(repo_root, base_ref, path)
        new_text = None if change_type == "delete" else _read_current_text(repo_root, path)
        return FileChange(path, change_type, old_text, new_text)
    return FileChange(path, change_type)


def review_worktree(repo_root: Path | str = ROOT, base_ref: str = DEFAULT_BASE) -> ReviewResult:
    """Run the full deterministic review against the working tree."""
    root = Path(repo_root)
    changes = collect_worktree_changes(root, base_ref)
    changed_paths = [change.path for change in changes]
    findings: list[Finding] = list(review_file_changes(changes).findings)

    backlog_before = _read_base_text(root, base_ref, "AUTONOMOUS_BACKLOG.md")
    backlog_after = _read_current_text(root, "AUTONOMOUS_BACKLOG.md")
    if backlog_after is not None:
        exists = lambda ref: (root / ref).is_file()  # noqa: E731 - tiny local predicate
        findings.extend(
            review_backlog(backlog_before, backlog_after, changed_paths, exists).findings
        )
        backlog_items = parse_backlog(backlog_after)
        for filename in ("STATUS.md", "CONTINUATION.md"):
            findings.extend(
                review_completion_claims(
                    filename,
                    _read_base_text(root, base_ref, filename),
                    _read_current_text(root, filename),
                    backlog_items,
                ).findings
            )
    return ReviewResult(tuple(findings))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the model-independent ECLIPSE review stage.")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Git ref to review against")
    parser.add_argument("--root", default=str(ROOT), help="Repository root")
    args = parser.parse_args(argv)
    try:
        result = review_worktree(args.root, args.base)
    except ReviewError as exc:
        print(f"REVIEW_ERROR: {exc}", file=sys.stderr)
        return 2
    print(result.to_text())
    return 0 if result.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())