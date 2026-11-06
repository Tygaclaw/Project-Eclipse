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


if __name__ == "__main__":
    unittest.main()
