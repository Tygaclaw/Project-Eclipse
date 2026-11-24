"""Regression coverage for recovering an autonomous PR after the base advanced.

The 2026-11-06 recovery of PR #16 hit a real, reproducible failure: the feature
branch was cut before the ``main`` commit that added
``tests/test_autonomous_orphans.py`` and ``tests/test_autonomous_parking.py``
merged. Relative to ``origin/main`` the stale worktree therefore *appeared* to
delete those two tests, and the independent reviewer rejected the whole change
set even though the product change was correct.

These tests reproduce that shape deterministically in a temporary Git
repository and pin the behaviour that must hold: a stale branch whose base has
advanced is rejected as a deleted test until the base advance is incorporated,
after which the identical product change is accepted.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.eclipse_review import review_worktree

TEST_SOURCE = (
    "import unittest\n\n\n"
    "class Later(unittest.TestCase):\n"
    "    def test_ok(self) -> None:\n"
    "        self.assertTrue(True)\n"
)

BACKLOG = (
    "| ID | Milestone | Acceptance evidence | Status |\n"
    "|---|---|---|---|\n"
    "| REC-01 | Example recovery milestone | tests/test_recovery.py | READY |\n"
)


class StaleBaseRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._git("init")
        self._git("config", "user.email", "recovery@example.test")
        self._git("config", "user.name", "Recovery Test")
        self._git("checkout", "-b", "main")

        (self.root / "AUTONOMOUS_BACKLOG.md").write_text(BACKLOG, encoding="utf-8")
        (self.root / "STATUS.md").write_text("Status: in progress\n", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_existing.py").write_text(TEST_SOURCE, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-m", "base")

        # The feature branch performs its own product work and adds its own test.
        self._git("checkout", "-b", "feature")
        (self.root / "src").mkdir()
        (self.root / "src" / "runtime.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "tests" / "test_runtime.py").write_text(TEST_SOURCE, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-m", "feature work")

        # Main advances with a test file the feature branch never saw.
        self._git("checkout", "main")
        (self.root / "tests" / "test_later.py").write_text(TEST_SOURCE, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-m", "main advance")
        self.main_tip = self._git("rev-parse", "HEAD").stdout.strip()
        self._git("checkout", "feature")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self.root, text=True, capture_output=True, check=True
        )

    def test_stale_branch_worktree_is_rejected_as_deleted_test(self) -> None:
        result = review_worktree(self.root, self.main_tip)
        self.assertFalse(result.accepted)
        codes = {finding.code for finding in result.findings}
        self.assertIn("deleted_test_file", codes)
        self.assertTrue(
            any("test_later.py" in (finding.path or "") for finding in result.findings)
        )

    def test_incorporating_base_advance_accepts_the_same_product_change(self) -> None:
        # The recovery fix: restore the newer base file into index and worktree.
        self._git("checkout", self.main_tip, "--", "tests/test_later.py")
        result = review_worktree(self.root, self.main_tip)
        self.assertTrue(result.accepted, result.to_text())


class MultiFileStaleBaseRecoveryTests(unittest.TestCase):
    """The PR #16 shape: one base advance adds several tests and a fixture.

    The 2026-11-07 recovery found the branch cut before the integrated ``main``
    commits, which added five test modules and a fixture at once. The reviewer
    reported every one as a deletion. This class pins both halves of the fix:
    all of them are reported, and restoring all of them accepts the branch's
    additive change.
    """

    BASE_TESTS = (
        "tests/test_agent.py",
        "tests/test_app_cli.py",
        "tests/test_capability.py",
        "tests/test_core_foundation.py",
        "tests/test_preparation.py",
        "tests/fixtures/fake_llama_server.py",
    )

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._git("init")
        self._git("config", "user.email", "recovery@example.test")
        self._git("config", "user.name", "Recovery Test")
        self._git("checkout", "-b", "main")

        (self.root / "AUTONOMOUS_BACKLOG.md").write_text(BACKLOG, encoding="utf-8")
        (self.root / "STATUS.md").write_text("Status: in progress\n", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_existing.py").write_text(TEST_SOURCE, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-m", "base")

        # The stale feature branch does its own product work with its own tests.
        self._git("checkout", "-b", "feature")
        (self.root / "src").mkdir()
        (self.root / "src" / "core").mkdir()
        (self.root / "src" / "core" / "runtime.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "tests" / "test_runtime_contract.py").write_text(TEST_SOURCE, encoding="utf-8")
        (self.root / "tests" / "test_runtime_cli.py").write_text(TEST_SOURCE, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-m", "feature work")

        # Main advances with several tests and a fixture the branch never saw.
        self._git("checkout", "main")
        (self.root / "tests" / "fixtures").mkdir()
        for path in self.BASE_TESTS:
            (self.root / path).write_text(TEST_SOURCE, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-m", "integrated main advance")
        self.main_tip = self._git("rev-parse", "HEAD").stdout.strip()
        self._git("checkout", "feature")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self.root, text=True, capture_output=True, check=True
        )

    def test_all_base_advance_tests_are_reported_as_deleted(self) -> None:
        result = review_worktree(self.root, self.main_tip)
        self.assertFalse(result.accepted)
        deleted = {f.path for f in result.findings if f.code == "deleted_test_file"}
        self.assertEqual(deleted, set(self.BASE_TESTS), result.to_text())

    def test_restoring_all_base_files_accepts_the_additive_change(self) -> None:
        self._git("checkout", self.main_tip, "--", *self.BASE_TESTS)
        result = review_worktree(self.root, self.main_tip)
        self.assertTrue(result.accepted, result.to_text())
        # The branch's own additive tests must still be present afterwards.
        self.assertTrue((self.root / "tests" / "test_runtime_contract.py").is_file())
        self.assertTrue((self.root / "tests" / "test_runtime_cli.py").is_file())


class AppendOnlyDocumentationConflictTests(unittest.TestCase):
    """Pin the PR #16 documentation conflict and its non-overlapping fix.

    The recovery branch copied ``main``'s new section and then appended its
    own recovery note immediately after it in ``CONTINUATION.md`` and
    ``STATUS.md``. Both sides therefore inserted at the old end-of-file, so the
    branch was still unmergeable even though its content already contained the
    newer ``main`` text. Moving the recovery note into a pre-existing region
    keeps the same content and merges cleanly.
    """

    BASE = "# Log\n\nIntro.\n\n## Stable section\n\nKeep this.\n"
    MAIN_ADDITION = "\n## New on main\n\nMain content.\n"
    RECOVERY = "## Recovery\n\nUnique recovery note.\n\n"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._git("init")
        self._git("config", "user.email", "recovery@example.test")
        self._git("config", "user.name", "Recovery Test")
        self._git("checkout", "-b", "main")
        (self.root / "LOG.md").write_text(self.BASE, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-m", "base")

        self._git("checkout", "-b", "feature")
        self._git("checkout", "main")
        (self.root / "LOG.md").write_text(self.BASE + self.MAIN_ADDITION, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-m", "main advance")
        self._git("checkout", "feature")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self.root, text=True, capture_output=True, check=True
        )

    def _commit_feature_doc(self, content: str) -> None:
        (self.root / "LOG.md").write_text(content, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-m", "feature recovery note")

    def _merge_main(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "merge", "--no-edit", "main"],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_appending_recovery_after_main_section_conflicts(self) -> None:
        self._commit_feature_doc(self.BASE + self.MAIN_ADDITION + self.RECOVERY)
        merged = self._merge_main()
        self.assertNotEqual(merged.returncode, 0)
        self.assertIn("CONFLICT", merged.stdout + merged.stderr)
        self._git("merge", "--abort")

    def test_placing_recovery_in_a_preexisting_region_merges_cleanly(self) -> None:
        content = self.BASE.replace(
            "## Stable section", self.RECOVERY + "## Stable section"
        ) + self.MAIN_ADDITION
        self._commit_feature_doc(content)
        merged = self._merge_main()
        self.assertEqual(merged.returncode, 0, merged.stdout + merged.stderr)
        merged_text = (self.root / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("Unique recovery note.", merged_text)
        self.assertIn("Main content.", merged_text)

    def test_relocated_real_incident_sections_merge_cleanly(self) -> None:
        """The 2026-11-21 PR #16 shape: two newest sections appended after main's EOF.

        ``TESTING.md`` was unmergeable because its two most recent recovery
        sections were appended *after* ``main``'s new end-of-file section. Moving
        exactly those sections into the pre-existing recovery region clears the
        conflict and keeps every section, which is the fix that was applied.
        """
        first = "## Recovery one\n\nFirst unique note.\n\n"
        second = "## Recovery two\n\nSecond unique note.\n\n"
        # The broken shape: copy main's new section, then append both notes after it.
        self._commit_feature_doc(self.BASE + self.MAIN_ADDITION + first + second)
        merged = self._merge_main()
        self.assertNotEqual(merged.returncode, 0)
        self.assertIn("CONFLICT", merged.stdout + merged.stderr)
        self._git("merge", "--abort")

        # The fix: place both notes in a region that already existed in the base.
        content = self.BASE.replace(
            "## Stable section", first + second + "## Stable section"
        ) + self.MAIN_ADDITION
        self._commit_feature_doc(content)
        merged = self._merge_main()
        self.assertEqual(merged.returncode, 0, merged.stdout + merged.stderr)
        merged_text = (self.root / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("First unique note.", merged_text)
        self.assertIn("Second unique note.", merged_text)
        self.assertIn("Main content.", merged_text)


if __name__ == "__main__":
    unittest.main()
