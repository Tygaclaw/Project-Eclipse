from __future__ import annotations

import json
import subprocess
import unittest

from scripts.eclipse_autonomous import (
    MAX_PARKED_OWNER_PRS,
    build_run_prompt,
    is_parked_owner_pr,
    list_open_autonomous_prs,
    safety_scan,
)


def pr(number, head, draft, title="ECLIPSE autonomous milestone"):
    return {"number": number, "headRefName": head, "isDraft": draft, "title": title,
            "url": f"https://example/pull/{number}", "body": "", "headRefOid": "x"}


class ParkingTests(unittest.TestCase):
    def test_finished_protected_draft_is_parked(self) -> None:
        self.assertTrue(is_parked_owner_pr(pr(1, "feature/eclipse-autonomous-1-1", True)))

    def test_checkpoint_draft_is_resumable_not_parked(self) -> None:
        item = pr(2, "feature/eclipse-autonomous-2-1", True, "Checkpoint: ECLIPSE autonomous run 2")
        self.assertFalse(is_parked_owner_pr(item))

    def test_ready_pr_is_not_parked(self) -> None:
        self.assertFalse(is_parked_owner_pr(pr(3, "feature/eclipse-autonomous-3-1", False)))

    def test_only_autonomous_branches_are_listed(self) -> None:
        listing = [pr(1, "feature/eclipse-autonomous-1-1", True), pr(2, "fix/other", True)]

        def fake_gh(args, *, source_env, check=True):
            return subprocess.CompletedProcess(args, 0, json.dumps(listing), "")

        found = list_open_autonomous_prs({}, gh_fn=fake_gh)
        self.assertEqual([item["number"] for item in found], [1])

    def test_pause_threshold_is_small_but_allows_progress(self) -> None:
        self.assertGreaterEqual(MAX_PARKED_OWNER_PRS, 2)
        self.assertLessEqual(MAX_PARKED_OWNER_PRS, 5)

    def test_prompt_carries_parked_note_first(self) -> None:
        prompt = build_run_prompt("t", "NOTE: parked #14.\n\n")
        self.assertTrue(prompt.startswith("NOTE: parked #14."))
        self.assertIn("Read these files first", prompt)


class ProtectedListTests(unittest.TestCase):
    def test_reviewer_and_controller_tests_are_owner_review_only(self) -> None:
        for path in ("scripts/eclipse_review.py", "tests/test_review.py",
                     "tests/test_autonomous_runner.py", "tests/test_autonomous_parking.py"):
            _safe, _msg, protected = safety_scan([path])
            self.assertTrue(protected, path)

    def test_ordinary_product_code_is_not_protected(self) -> None:
        _safe, _msg, protected = safety_scan(["src/eclipse/hardware.py"])
        self.assertFalse(protected)


if __name__ == "__main__":
    unittest.main()
