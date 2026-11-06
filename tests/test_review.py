from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.eclipse_review import (
    FileChange,
    main,
    parse_backlog,
    review_backlog,
    review_completion_claims,
    review_file_changes,
    review_worktree,
)

HEADER = "| ID | Milestone | Acceptance evidence | Status |\n|---|---|---|---|\n"

SIMPLE_TEST = """import unittest


class ExampleTests(unittest.TestCase):
    def test_ok(self) -> None:
        self.assertTrue(True)
"""


def backlog_row(item_id: str, evidence: str, status: str) -> str:
    return f"| {item_id} | Example milestone | {evidence} | {status} |\n"


class BacklogParsingTests(unittest.TestCase):
    def test_parses_items_and_skips_header_rows(self) -> None:
        text = HEADER + backlog_row("AUTO-99", "tests/test_review.py", "READY")
        items = parse_backlog(text)
        self.assertEqual(list(items), ["AUTO-99"])
        self.assertEqual(items["AUTO-99"].status, "READY")
        self.assertIn("tests/test_review.py", items["AUTO-99"].evidence)

    def test_verified_status_prefix_is_recognised(self) -> None:
        text = HEADER + backlog_row("BASE-01", "PR #4", "VERIFIED_CONFIG_ONLY")
        items = parse_backlog(text)
        self.assertEqual(items["BASE-01"].status, "VERIFIED_CONFIG_ONLY")


class SeededRegressionTests(unittest.TestCase):
    def test_deleted_test_file_is_rejected(self) -> None:
        result = review_file_changes([FileChange("tests/test_tokenizer.py", "delete")])
        self.assertFalse(result.accepted)
        self.assertEqual(result.findings[0].code, "deleted_test_file")

    def test_new_test_skip_is_rejected(self) -> None:
        before = "import unittest\n\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertTrue(True)\n"
        after = (
            "import unittest\n\nclass T(unittest.TestCase):\n"
            "    @unittest.skip('flaky')\n    def test_a(self):\n        self.assertTrue(True)\n"
        )
        result = review_file_changes([FileChange("tests/test_example.py", "modify", before, after)])
        self.assertFalse(result.accepted)
        self.assertEqual(result.findings[0].code, "skipped_test_added")

    def test_new_test_file_that_is_skipped_is_rejected(self) -> None:
        after = (
            "import unittest\n\n@unittest.skip('todo')\nclass S(unittest.TestCase):\n"
            "    def test_a(self):\n        pass\n"
        )
        result = review_file_changes([FileChange("tests/test_new.py", "add", None, after)])
        self.assertFalse(result.accepted)
        self.assertEqual(result.findings[0].code, "skipped_test_added")

    def test_removing_an_existing_skip_is_accepted(self) -> None:
        before = (
            "import unittest\n\nclass T(unittest.TestCase):\n"
            "    @unittest.skip('flaky')\n    def test_a(self):\n        self.assertTrue(True)\n"
        )
        after = "import unittest\n\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertTrue(True)\n"
        result = review_file_changes([FileChange("tests/test_example.py", "modify", before, after)])
        self.assertTrue(result.accepted, result.to_text())

    def test_unrelated_source_change_is_accepted(self) -> None:
        result = review_file_changes([FileChange("src/eclipse/core/example.py", "modify")])
        self.assertTrue(result.accepted, result.to_text())


class FalseCompletionClaimTests(unittest.TestCase):
    def test_verified_without_substantive_evidence_is_rejected(self) -> None:
        before = backlog_row("AUTO-99", "Tests pending", "READY")
        after = backlog_row("AUTO-99", "done", "VERIFIED")
        result = review_backlog(before, after, [], lambda _ref: True)
        self.assertFalse(result.accepted)
        self.assertEqual(result.findings[0].code, "false_completion_claim")

    def test_verified_with_evidence_but_no_test_change_is_rejected(self) -> None:
        before = backlog_row("AUTO-99", "Tests pending", "READY")
        after = backlog_row("AUTO-99", "Covered by tests/test_review.py", "VERIFIED")
        result = review_backlog(before, after, ["src/eclipse/example.py"], lambda _ref: True)
        self.assertFalse(result.accepted)
        self.assertIn("without changed tests", result.findings[0].message)

    def test_missing_referenced_test_is_rejected(self) -> None:
        before = backlog_row("AUTO-99", "Tests pending", "READY")
        after = backlog_row("AUTO-99", "tests/test_missing.py proves it", "VERIFIED")
        result = review_backlog(before, after, ["tests/test_review.py"], lambda _ref: False)
        self.assertFalse(result.accepted)
        self.assertIn("missing test file", result.findings[0].message)

    def test_verified_with_new_test_and_existing_reference_is_accepted(self) -> None:
        before = backlog_row("AUTO-99", "Tests pending", "READY")
        after = backlog_row("AUTO-99", "tests/test_review.py proves it", "VERIFIED")
        result = review_backlog(before, after, ["tests/test_review.py"], lambda _ref: True)
        self.assertTrue(result.accepted, result.to_text())

    def test_verified_with_ci_record_is_accepted(self) -> None:
        before = backlog_row("AUTO-99", "Tests pending", "READY")
        after = backlog_row(
            "AUTO-99", "CI run https://example.test/actions/runs/1 passed", "VERIFIED"
        )
        result = review_backlog(before, after, [], lambda _ref: True)
        self.assertTrue(result.accepted, result.to_text())

    def test_already_verified_item_is_not_rechecked(self) -> None:
        before = backlog_row("BASE-01", "PR #4; merged", "VERIFIED")
        after = backlog_row("BASE-01", "PR #4; merged; historical note", "VERIFIED")
        result = review_backlog(before, after, [], lambda _ref: True)
        self.assertTrue(result.accepted, result.to_text())

    def test_new_completion_claim_with_unfinished_backlog_is_rejected(self) -> None:
        backlog = parse_backlog(HEADER + backlog_row("AUTO-99", "Tests pending", "READY"))
        result = review_completion_claims(
            "STATUS.md", "Status: in progress", "Status: the product is complete", backlog
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.findings[0].code, "false_completion_claim")

    def test_preexisting_completion_claim_is_not_reflagged(self) -> None:
        backlog = parse_backlog(HEADER + backlog_row("AUTO-99", "Tests pending", "READY"))
        text = "Status: the product is complete"
        result = review_completion_claims("STATUS.md", text, text, backlog)
        self.assertTrue(result.accepted, result.to_text())


class ReviewWorktreeIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._git("init")
        self._git("config", "user.email", "review@example.test")
        self._git("config", "user.name", "Review Test")
        (self.root / "AUTONOMOUS_BACKLOG.md").write_text(
            HEADER + backlog_row("AUTO-99", "Tests pending", "READY"), encoding="utf-8"
        )
        (self.root / "STATUS.md").write_text("Status: in progress\n", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_example.py").write_text(SIMPLE_TEST, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-m", "base")
        self.base = self._git("rev-parse", "HEAD").stdout.strip()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self.root, text=True, capture_output=True, check=True
        )

    def test_clean_source_change_with_new_test_is_accepted(self) -> None:
        (self.root / "src").mkdir()
        (self.root / "src" / "feature.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "tests" / "test_extra.py").write_text(SIMPLE_TEST, encoding="utf-8")
        result = review_worktree(self.root, self.base)
        self.assertTrue(result.accepted, result.to_text())

    def test_seeded_regression_deleting_test_is_rejected(self) -> None:
        (self.root / "tests" / "test_example.py").unlink()
        result = review_worktree(self.root, self.base)
        self.assertFalse(result.accepted)
        self.assertEqual(result.findings[0].code, "deleted_test_file")

    def test_false_completion_claim_is_rejected(self) -> None:
        (self.root / "AUTONOMOUS_BACKLOG.md").write_text(
            HEADER + backlog_row("AUTO-99", "done", "VERIFIED"), encoding="utf-8"
        )
        result = review_worktree(self.root, self.base)
        self.assertFalse(result.accepted)
        self.assertEqual(result.findings[0].code, "false_completion_claim")

    def test_cli_returns_nonzero_for_rejected_change(self) -> None:
        (self.root / "tests" / "test_example.py").unlink()
        self.assertEqual(main(["--root", str(self.root), "--base", self.base]), 1)

    def test_cli_returns_zero_for_accepted_change(self) -> None:
        (self.root / "src").mkdir()
        (self.root / "src" / "feature.py").write_text("x = 1\n", encoding="utf-8")
        self.assertEqual(main(["--root", str(self.root), "--base", self.base]), 0)


if __name__ == "__main__":
    unittest.main()