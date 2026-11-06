from __future__ import annotations

import subprocess
import unittest

from scripts.eclipse_autonomous import find_orphan_autonomous_branches, gh


def fake_gh_factory(branches: list[str], with_pr: set[str]):
    def fake_gh(args, *, source_env, check=True):
        if args[0] == "api":
            return subprocess.CompletedProcess(args, 0, "\n".join(branches) + "\n", "")
        head = args[args.index("--head") + 1]
        return subprocess.CompletedProcess(args, 0, '[{"number": 1}]' if head in with_pr else "[]", "")
    return fake_gh


class OrphanBranchTests(unittest.TestCase):
    ENV = {"GITHUB_REPOSITORY": "Tygaclaw/Project-Eclipse"}

    def test_branch_without_any_pr_is_an_orphan(self) -> None:
        fake = fake_gh_factory(["main", "feature/eclipse-autonomous-1-1"], set())
        self.assertEqual(find_orphan_autonomous_branches(self.ENV, gh_fn=fake), ["feature/eclipse-autonomous-1-1"])

    def test_branch_with_a_pr_is_not_an_orphan(self) -> None:
        fake = fake_gh_factory(["feature/eclipse-autonomous-1-1"], {"feature/eclipse-autonomous-1-1"})
        self.assertEqual(find_orphan_autonomous_branches(self.ENV, gh_fn=fake), [])

    def test_unrelated_branches_are_ignored(self) -> None:
        fake = fake_gh_factory(["main", "fix/other", "feature/hardware-feasibility-v1"], set())
        self.assertEqual(find_orphan_autonomous_branches(self.ENV, gh_fn=fake), [])


class GhErrorTests(unittest.TestCase):
    def test_failed_gh_call_reports_its_own_error_text_and_redacts_secrets(self) -> None:
        import scripts.eclipse_autonomous as controller

        def failing_run(cmd, **kwargs):
            raise subprocess.CalledProcessError(
                1, cmd, output="", stderr="GitHub Actions is not permitted to create pull requests. tok-secret-value-123"
            )

        original = controller.subprocess.run
        controller.subprocess.run = failing_run
        try:
            with self.assertRaises(RuntimeError) as ctx:
                gh(["pr", "create"], source_env={"GITHUB_TOKEN": "tok-secret-value-123"})
        finally:
            controller.subprocess.run = original
        message = str(ctx.exception)
        self.assertIn("not permitted to create pull requests", message)
        self.assertNotIn("tok-secret-value-123", message)


if __name__ == "__main__":
    unittest.main()
