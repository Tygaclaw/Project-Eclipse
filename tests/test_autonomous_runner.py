from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

from scripts import eclipse_autonomous
from scripts.eclipse_autonomous import (
    MAX_CALLS_PER_MODEL,
    REVIEW_COMMAND,
    ROOT,
    ROUTES,
    Route,
    RunResult,
    approval_gate_evidence,
    approval_gate_evidence_message,
    ci_evidence_has_log,
    ci_requires_owner_approval,
    ci_run_conclusions,
    classify_ci_run,
    classify_failure,
    existing_pr_owner_review_message,
    extract_session_id,
    failure_log_is_available,
    owner_approval_required_message,
    remote_ci_failure_context,
    unusable_ci_prompt_message,
    unusable_repair_evidence_message,
    safe_child_environment,
    safety_scan,
    select_current_head_ci_runs,
    run_opencode,
    validation_commands,
    validation_environment,
    build_repair_prompt,
)


class FailureClassificationTests(unittest.TestCase):
    def test_quota_is_immediate_provider_failover(self) -> None:
        failure = classify_failure("HTTP 429: rate limit exceeded")
        self.assertEqual(failure.kind, "quota")
        self.assertTrue(failure.skip_provider)
        self.assertFalse(failure.retryable)

    def test_invalid_key_skips_provider(self) -> None:
        failure = classify_failure("401 invalid api key")
        self.assertEqual(failure.kind, "authentication")
        self.assertTrue(failure.skip_provider)

    def test_missing_model_skips_only_route(self) -> None:
        failure = classify_failure("model not found: unknown model")
        self.assertEqual(failure.kind, "model_unavailable")
        self.assertFalse(failure.skip_provider)

    def test_transient_server_error_is_retryable(self) -> None:
        failure = classify_failure("HTTP 503 gateway temporarily unavailable")
        self.assertEqual(failure.kind, "transient")
        self.assertTrue(failure.retryable)

    def test_timeout_is_retryable(self) -> None:
        self.assertTrue(classify_failure("", timed_out=True).retryable)

    def test_context_length_error_requests_compaction_before_retry(self) -> None:
        failure = classify_failure("context_length_exceeded: maximum context length is 65536")
        self.assertEqual(failure.kind, "context_length")
        self.assertFalse(failure.retryable)
        prompt = build_repair_prompt("maximum context length exceeded")
        self.assertIn("compact the conversation", prompt)
        self.assertIn("Do not restart the milestone", prompt)

    def test_default_retry_policy_is_initial_plus_five(self) -> None:
        self.assertEqual(MAX_CALLS_PER_MODEL, 6)


class SessionAndEnvironmentTests(unittest.TestCase):
    def test_session_id_is_extracted_from_json_event(self) -> None:
        output = '{"type":"session.created","properties":{"info":{"id":"ses_abcdefgh12345678"}}}'
        self.assertEqual(extract_session_id(output), "ses_abcdefgh12345678")

    def test_session_id_can_be_extracted_from_log_text(self) -> None:
        self.assertEqual(extract_session_id("Created ses_abcdefgh12345678 successfully"), "ses_abcdefgh12345678")

    def test_other_provider_keys_and_github_tokens_are_not_forwarded(self) -> None:
        route = ROUTES[0]
        env = {
            "PATH": "/usr/bin",
            "TOKENHARBOR_API_KEY": "token-harbor-secret",
            "GEMINI_API_KEY": "other-provider-secret",
            "GITHUB_TOKEN": "github-secret",
            "GH_TOKEN": "gh-secret",
            "HOME": "/home/runner",
        }
        child = safe_child_environment(route, env)
        self.assertEqual(child["TOKENHARBOR_API_KEY"], "token-harbor-secret")
        self.assertNotIn("GEMINI_API_KEY", child)
        self.assertNotIn("GITHUB_TOKEN", child)
        self.assertNotIn("GH_TOKEN", child)
        self.assertNotIn("GH_TOKEN", child.values())

    def test_google_route_uses_google_environment_key_name(self) -> None:
        route = next(item for item in ROUTES if item.provider == "google")
        child = safe_child_environment(route, {"GEMINI_API_KEY": "gemini-secret"})
        self.assertEqual(child["GOOGLE_GENERATIVE_AI_API_KEY"], "gemini-secret")
        self.assertNotIn("GEMINI_API_KEY", child)


class SafetyScanTests(unittest.TestCase):
    def test_opencode_config_is_protected(self) -> None:
        safe, message, protected = safety_scan(["opencode.json"])
        self.assertTrue(safe, message)
        self.assertTrue(protected)

    def test_ordinary_source_is_not_protected(self) -> None:
        safe, message, protected = safety_scan(["src/eclipse/example.py"])
        self.assertTrue(safe, message)
        self.assertFalse(protected)

    def test_protected_protocol_requires_owner_review(self) -> None:
        safe, message, protected = safety_scan(["docs/AUTONOMOUS_ENGINEERING_PROTOCOL.md"])
        self.assertTrue(safe, message)
        self.assertTrue(protected)



    def test_opencode_invocation_uses_only_valid_flags_and_carries_session_and_selected_model(self) -> None:
        captured = {}
        route = ROUTES[1]

        def fake_runner(command, **kwargs):
            captured["command"] = command
            captured["env"] = kwargs["env"]
            with open(kwargs["env"]["BASH_ENV"], encoding="utf-8") as scrub_file:
                captured["scrubber"] = scrub_file.read()
            captured["scrubber_path"] = kwargs["env"]["BASH_ENV"]
            return __import__("subprocess").CompletedProcess(
                command, 0,
                stdout='{"type":"session.updated","sessionID":"ses_abcdefgh12345678"}\n',
                stderr="",
            )

        result, session = run_opencode(
            route,
            "continue task",
            "ses_previous12345678",
            "autonomous-test",
            runner=fake_runner,
            source_env={
                "PATH": "/usr/bin",
                "GEMINI_API_KEY": "gemini-test-key",
                "TOKENHARBOR_API_KEY": "must-not-leak",
                "GITHUB_TOKEN": "must-not-leak-either",
            },
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(session, "ses_abcdefgh12345678")
        self.assertNotIn("--standalone", captured["command"])
        # Only flags that exist in OpenCode 1.19.5 `opencode run --help`.
        valid = {"--format", "--agent", "--model", "--title", "--auto", "--session"}
        used = {part for part in captured["command"] if part.startswith("--")}
        self.assertLessEqual(used, valid)
        self.assertIn("--session", captured["command"])
        self.assertIn("ses_previous12345678", captured["command"])
        self.assertIn("--model", captured["command"])
        self.assertIn(route.open_code_id, captured["command"])
        self.assertEqual(captured["env"]["GOOGLE_GENERATIVE_AI_API_KEY"], "gemini-test-key")
        self.assertIn("unset GOOGLE_GENERATIVE_AI_API_KEY\n", captured["scrubber"])
        self.assertIn("unset GITHUB_TOKEN\n", captured["scrubber"])
        self.assertFalse(__import__("os").path.exists(captured["scrubber_path"]))
        self.assertNotIn("TOKENHARBOR_API_KEY", captured["env"])
        self.assertNotIn("GITHUB_TOKEN", captured["env"])

    def test_payment_required_skips_provider_without_retry(self) -> None:
        failure = classify_failure("HTTP 402 Payment Required: credits exhausted")
        self.assertEqual(failure.kind, "quota")
        self.assertTrue(failure.skip_provider)
        self.assertFalse(failure.retryable)


    def test_validation_environment_contains_no_github_or_provider_credentials(self) -> None:
        env = validation_environment({
            "PATH": "/usr/bin",
            "HOME": "/tmp",
            "GITHUB_TOKEN": "github-secret",
            "GH_TOKEN": "gh-secret",
            "GEMINI_API_KEY": "gemini-secret",
            "TOKENHARBOR_API_KEY": "token-secret",
        })
        self.assertEqual(env["PATH"], "/usr/bin")
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertNotIn("GH_TOKEN", env)
        self.assertNotIn("GEMINI_API_KEY", env)
        self.assertNotIn("TOKENHARBOR_API_KEY", env)

    def test_validation_environment_exposes_source_package_on_pythonpath(self) -> None:
        from pathlib import Path

        env = validation_environment({"PATH": "/usr/bin"})
        self.assertEqual(env["PYTHONPATH"], str(ROOT / "src"))
        self.assertTrue((Path(env["PYTHONPATH"]) / "eclipse").is_dir())


class FailoverLoopTests(unittest.TestCase):
    @staticmethod
    def all_provider_secrets() -> dict[str, str]:
        return {
            "TOKENHARBOR_API_KEY": "token-harbor-test",
            "GEMINI_API_KEY": "gemini-test",
            "DAHL_API_KEY": "dahl-test",
            "GROQ_API_KEY": "groq-test",
            "OPENROUTER_API_KEY": "openrouter-test",
            "ZAI_API_KEY": "zai-test",
        }

    def test_raw_approval_gate_ci_prompt_is_refused_before_any_provider_call(self) -> None:
        """A stale caller replaying the #43966482393/#43966482410 chunks cannot burn a model call."""
        from scripts.eclipse_autonomous import run_agent_with_failover

        calls = []
        prompt = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 43966482393 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43966482410 (action_required) =====\n"
            "failed to get run log: log not found"
        )

        def fake_call(route, prompt, session_id, run_title, **kwargs):
            calls.append(route.open_code_id)
            return RunResult(0, stdout='{"type":"session.updated"}'), "ses_gate1234567890"

        success, _session, _model, failure = run_agent_with_failover(
            prompt, "gate-test", self.all_provider_secrets(),
            call=fake_call,
            validate=lambda: (True, "all passed"),
            sleep=lambda _seconds: None,
            rng=lambda: 0.0,
        )

        self.assertFalse(success)
        self.assertEqual(calls, [])
        self.assertIn("OWNER_APPROVAL_REQUIRED", failure)

    def test_raw_newest_approval_gate_ci_prompt_is_refused_before_any_provider_call(self) -> None:
        """A stale caller replaying the #44042810216/#44042810197 chunks cannot burn a model call."""
        from scripts.eclipse_autonomous import run_agent_with_failover

        calls = []
        prompt = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 44042810197 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 44042810216 (action_required) =====\n"
            "failed to get run log: log not found"
        )

        def fake_call(route, prompt, session_id, run_title, **kwargs):
            calls.append(route.open_code_id)
            return RunResult(0, stdout='{"type":"session.updated"}'), "ses_gate44042810216"

        success, _session, _model, failure = run_agent_with_failover(
            prompt, "gate-test", self.all_provider_secrets(),
            call=fake_call,
            validate=lambda: (True, "all passed"),
            sleep=lambda _seconds: None,
            rng=lambda: 0.0,
        )

        self.assertFalse(success)
        self.assertEqual(calls, [])
        self.assertIn("OWNER_APPROVAL_REQUIRED", failure)

    def test_raw_newest_approval_gate_ci_prompt_44174341838_is_refused(self) -> None:
        """A stale caller replaying the #44174341838/#44174342093 chunks cannot burn a model call."""
        from scripts.eclipse_autonomous import run_agent_with_failover

        calls = []
        prompt = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Python checks run 44174341838 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Windows desktop build run 44174342093 (action_required) =====\n"
            "failed to get run log: log not found"
        )

        def fake_call(route, prompt, session_id, run_title, **kwargs):
            calls.append(route.open_code_id)
            return RunResult(0, stdout='{"type":"session.updated"}'), "ses_gate44174341838"

        success, _session, _model, failure = run_agent_with_failover(
            prompt, "gate-test", self.all_provider_secrets(),
            call=fake_call,
            validate=lambda: (True, "all passed"),
            sleep=lambda _seconds: None,
            rng=lambda: 0.0,
        )

        self.assertFalse(success)
        self.assertEqual(calls, [])
        self.assertIn("OWNER_APPROVAL_REQUIRED", failure)

    def test_raw_unavailable_failure_log_prompt_is_refused_before_any_provider_call(self) -> None:
        """A caller bypassing build_repair_prompt still cannot send an empty failure log."""
        from scripts.eclipse_autonomous import run_agent_with_failover

        calls = []
        prompt = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 111 (failure) =====\n"
            "failed to get run log: log not found"
        )

        def fake_call(route, prompt, session_id, run_title, **kwargs):
            calls.append(route.open_code_id)
            return RunResult(0, stdout='{"type":"session.updated"}'), "ses_nolog1234567890"

        success, _session, _model, failure = run_agent_with_failover(
            prompt, "no-log-test", self.all_provider_secrets(),
            call=fake_call,
            validate=lambda: (True, "all passed"),
            sleep=lambda _seconds: None,
            rng=lambda: 0.0,
        )

        self.assertFalse(success)
        self.assertEqual(calls, [])
        self.assertIn("CI_EVIDENCE_UNAVAILABLE", failure)

    def test_raw_newest_approval_gate_ci_prompt_44258836858_is_refused(self) -> None:
        """A stale caller replaying the #44258836858/#44258836775 chunks cannot burn a model call."""
        from scripts.eclipse_autonomous import run_agent_with_failover

        calls = []
        prompt = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 44258836858 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 44258836775 (action_required) =====\n"
            "failed to get run log: log not found"
        )

        def fake_call(route, prompt, session_id, run_title, **kwargs):
            calls.append(route.open_code_id)
            return RunResult(0, stdout='{"type":"session.updated"}'), "ses_gate44258836858"

        success, _session, _model, failure = run_agent_with_failover(
            prompt, "gate-test", self.all_provider_secrets(),
            call=fake_call,
            validate=lambda: (True, "all passed"),
            sleep=lambda _seconds: None,
            rng=lambda: 0.0,
        )

        self.assertFalse(success)
        self.assertEqual(calls, [])
        self.assertIn("OWNER_APPROVAL_REQUIRED", failure)

    def test_headerless_raw_unavailable_log_prompt_is_refused_before_any_provider_call(self) -> None:
        """A stale caller that strips the CI headers still cannot send a log-less notice."""
        from scripts.eclipse_autonomous import run_agent_with_failover

        calls = []
        prompt = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "failed to get run log: log not found"
        )

        def fake_call(route, prompt, session_id, run_title, **kwargs):
            calls.append(route.open_code_id)
            return RunResult(0, stdout='{"type":"session.updated"}'), "ses_bare_nolog123"

        success, _session, _model, failure = run_agent_with_failover(
            prompt, "bare-no-log-test", self.all_provider_secrets(),
            call=fake_call,
            validate=lambda: (True, "all passed"),
            sleep=lambda _seconds: None,
            rng=lambda: 0.0,
        )

        self.assertFalse(success)
        self.assertEqual(calls, [])
        self.assertIn("CI_EVIDENCE_UNAVAILABLE", failure)

    def test_ordinary_prompt_without_ci_evidence_is_not_refused(self) -> None:
        """The boundary guard must not block normal milestone prompts."""
        self.assertIsNone(
            unusable_ci_prompt_message(
                "Continue the highest-priority unfinished ECLIPSE milestone and add tests."
            )
        )

    def test_raw_real_failure_ci_prompt_still_reaches_the_provider(self) -> None:
        """The boundary guard must not block genuine failure logs."""
        from scripts.eclipse_autonomous import run_agent_with_failover

        calls = []
        prompt = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 111 (failure) =====\n"
            "AssertionError: Windows check failed"
        )

        def fake_call(route, prompt, session_id, run_title, **kwargs):
            calls.append((route.open_code_id, prompt))
            return RunResult(0, stdout='{"type":"session.updated"}'), "ses_realfail12345678"

        success, _session, _model, failure = run_agent_with_failover(
            prompt, "real-failure-test", self.all_provider_secrets(),
            call=fake_call,
            validate=lambda: (True, "all passed"),
            sleep=lambda _seconds: None,
            rng=lambda: 0.0,
        )

        self.assertTrue(success, failure)
        self.assertEqual(len(calls), 1)
        self.assertIn("AssertionError: Windows check failed", calls[0][1])

    def test_transient_model_failure_switches_after_initial_plus_five_and_keeps_session(self) -> None:
        from scripts.eclipse_autonomous import run_agent_with_failover

        calls = []
        session = "ses_recovery12345678"

        def fake_call(route, prompt, session_id, run_title, **kwargs):
            calls.append((route.open_code_id, session_id, prompt))
            if route == ROUTES[0]:
                return RunResult(1, stderr="HTTP 503 gateway temporarily unavailable"), session
            return RunResult(0, stdout='{"type":"session.updated"}'), session_id or session

        success, returned_session, selected_model, failure = run_agent_with_failover(
            "initial task", "test-run", self.all_provider_secrets(),
            max_calls_per_model=6,
            call=fake_call,
            validate=lambda: (True, "all passed"),
            sleep=lambda _seconds: None,
            rng=lambda: 0.0,
        )

        self.assertTrue(success, failure)
        self.assertEqual(returned_session, session)
        self.assertEqual(selected_model, ROUTES[1].open_code_id)
        self.assertEqual(len(calls), 7)
        self.assertEqual([call[0] for call in calls[:6]], [ROUTES[0].open_code_id] * 6)
        self.assertEqual(calls[6][0], ROUTES[1].open_code_id)
        self.assertTrue(all(call[1] == session for call in calls[1:]))
        self.assertIn("SAME ECLIPSE task", calls[6][2])

    def test_context_compaction_does_not_advance_to_another_model(self) -> None:
        from scripts.eclipse_autonomous import run_agent_with_failover

        calls = []
        session = "ses_context12345678"

        def fake_call(route, prompt, session_id, run_title, **kwargs):
            calls.append((route.open_code_id, prompt, session_id))
            if len(calls) == 1:
                return RunResult(1, stderr="context_length_exceeded: maximum context length"), session
            return RunResult(0, stdout='{"type":"session.updated"}'), session_id

        success, returned_session, selected_model, failure = run_agent_with_failover(
            "initial task",
            "context-test",
            self.all_provider_secrets(),
            call=fake_call,
            validate=lambda: (True, "all passed"),
            sleep=lambda _seconds: None,
            rng=lambda: 0.0,
        )
        self.assertTrue(success, failure)
        self.assertEqual(returned_session, session)
        self.assertEqual(selected_model, ROUTES[0].open_code_id)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], calls[1][0])
        self.assertEqual(calls[1][2], session)
        self.assertIn("compact the conversation", calls[1][1])

    def test_quota_failure_skips_remaining_models_from_same_provider(self) -> None:
        from scripts.eclipse_autonomous import run_agent_with_failover

        calls = []
        session = "ses_quota1234567890"

        def fake_call(route, prompt, session_id, run_title, **kwargs):
            calls.append(route.open_code_id)
            if len(calls) == 1:
                return RunResult(1, stderr="HTTP 429 rate limit exceeded"), None
            return RunResult(0, stdout='{"type":"session.updated"}'), session

        success, returned_session, selected_model, failure = run_agent_with_failover(
            "initial task", "quota-test", self.all_provider_secrets(),
            max_calls_per_model=6,
            call=fake_call,
            validate=lambda: (True, "all passed"),
            sleep=lambda _seconds: None,
            rng=lambda: 0.0,
        )

        self.assertTrue(success, failure)
        self.assertEqual(calls, [ROUTES[0].open_code_id, ROUTES[1].open_code_id])
        self.assertEqual(selected_model, ROUTES[1].open_code_id)


    def test_context_compaction_does_not_consume_a_retry(self) -> None:
        from scripts.eclipse_autonomous import run_agent_with_failover

        calls = []
        session = "ses_compactretry1234"

        def fake_call(route, prompt, session_id, run_title, **kwargs):
            calls.append(route.open_code_id)
            if route == ROUTES[0]:
                if len(calls) == 1:
                    return RunResult(1, stderr="context_length_exceeded: maximum context length"), session
                return RunResult(1, stderr="HTTP 503 gateway temporarily unavailable"), session
            return RunResult(0, stdout='{"type":"session.updated"}'), session_id or session

        success, _session, selected_model, failure = run_agent_with_failover(
            "initial task", "compaction-budget", self.all_provider_secrets(),
            max_calls_per_model=6,
            call=fake_call,
            validate=lambda: (True, "all passed"),
            sleep=lambda _seconds: None,
            rng=lambda: 0.0,
        )

        self.assertTrue(success, failure)
        # One compaction call plus the full initial call and five retries on rank 1.
        self.assertEqual(calls[:7], [ROUTES[0].open_code_id] * 7)
        self.assertEqual(calls[7], ROUTES[1].open_code_id)
        self.assertEqual(selected_model, ROUTES[1].open_code_id)


class ConfigurationErrorTests(unittest.TestCase):
    def test_cli_usage_error_is_fatal_configuration_failure(self) -> None:
        failure = classify_failure("opencode run [message..]\n\nrun opencode with a message\nOptions:")
        self.assertEqual(failure.kind, "configuration")
        self.assertFalse(failure.retryable)

    def test_invalid_config_is_fatal_configuration_failure(self) -> None:
        self.assertEqual(
            classify_failure("Error: Configuration is invalid at opencode.json").kind, "configuration"
        )

    def test_configuration_error_aborts_without_retries_or_failover(self) -> None:
        from scripts.eclipse_autonomous import run_agent_with_failover

        calls = []

        def fake_call(route, prompt, session_id, run_title, **kwargs):
            calls.append(route.open_code_id)
            return RunResult(1, stderr="Error: Configuration is invalid at opencode.json"), None

        success, _s, _m, failure = run_agent_with_failover(
            "task", "cfg", {
                "TOKENHARBOR_API_KEY": "tokenharbor-fake-key-1", "GEMINI_API_KEY": "gemini-fake-key-2",
                "DAHL_API_KEY": "dahl-fake-key-3", "GROQ_API_KEY": "groq-fake-key-4",
                "OPENROUTER_API_KEY": "openrouter-fake-key-5", "ZAI_API_KEY": "zai-fake-key-6",
            },
            call=fake_call, validate=lambda: (True, ""), sleep=lambda _s: None, rng=lambda: 0.0,
        )
        self.assertFalse(success)
        self.assertEqual(len(calls), 1)
        self.assertIn("CONFIGURATION_ERROR", failure)


class IndependentReviewWiringTests(unittest.TestCase):
    def test_worktree_validation_runs_the_model_independent_review(self) -> None:
        commands = dict(validation_commands())
        self.assertIn("Independent review", commands)
        self.assertEqual(commands["Independent review"], REVIEW_COMMAND)
        self.assertIn("scripts/eclipse_review.py", REVIEW_COMMAND)
        self.assertIn("--base", REVIEW_COMMAND)

    def test_reviewer_is_separate_from_the_implementing_controller(self) -> None:
        self.assertNotIn("scripts/eclipse_autonomous.py", REVIEW_COMMAND)


class RankedPoolConsistencyTests(unittest.TestCase):
    def test_controller_route_order_matches_ranked_provider_pool_document(self) -> None:
        import re
        from pathlib import Path

        doc = (Path(__file__).resolve().parents[1] / "docs" / "FREE_MODEL_PROVIDER_POOL.md").read_text(encoding="utf-8")
        ranked = re.findall(r"^\|\s*\*{0,2}(\d+)\*{0,2}\s*\|[^|]*\|[^|]*\|\s*`([^`]+)`", doc, re.M)
        ranked.sort(key=lambda row: int(row[0]))
        self.assertEqual(len(ranked), 12)
        self.assertEqual([row[1] for row in ranked], [route.open_code_id for route in ROUTES])


class CiRunClassificationTests(unittest.TestCase):
    def test_action_required_run_is_an_approval_gate_not_a_repairable_failure(self) -> None:
        run = {"status": "completed", "conclusion": "action_required", "headSha": "abc"}
        self.assertEqual(classify_ci_run(run), "approval_required")

    def test_failed_and_timed_out_runs_are_repairable(self) -> None:
        for conclusion in ("failure", "timed_out"):
            with self.subTest(conclusion=conclusion):
                self.assertEqual(
                    classify_ci_run({"status": "completed", "conclusion": conclusion}),
                    "repairable",
                )

    def test_success_skipped_cancelled_and_incomplete_runs_are_ignored(self) -> None:
        for run in (
            {"status": "completed", "conclusion": "success"},
            {"status": "completed", "conclusion": "skipped"},
            {"status": "completed", "conclusion": "cancelled"},
            {"status": "in_progress", "conclusion": None},
            {"status": "queued", "conclusion": None},
        ):
            with self.subTest(run=run):
                self.assertEqual(classify_ci_run(run), "ignored")

    def test_only_the_exact_head_and_only_classified_runs_are_selected(self) -> None:
        runs = [
            {"status": "completed", "conclusion": "failure", "headSha": "head"},
            {"status": "completed", "conclusion": "action_required", "headSha": "head"},
            {"status": "completed", "conclusion": "failure", "headSha": "other"},
            {"status": "queued", "conclusion": None, "headSha": "head"},
        ]
        repairable, approval = select_current_head_ci_runs(runs, "head")
        self.assertEqual([run["conclusion"] for run in repairable], ["failure"])
        self.assertEqual([run["conclusion"] for run in approval], ["action_required"])

    def test_missing_expected_head_selects_nothing(self) -> None:
        runs = [{"status": "completed", "conclusion": "failure", "headSha": "head"}]
        self.assertEqual(select_current_head_ci_runs(runs, None), ([], []))


class RemoteCiFailureContextTests(unittest.TestCase):
    """The recovery loop must never fabricate evidence from a log-less run.

    The 2026-11-06 recovery of PR #16 received a prompt whose only "failure evidence"
    was ``failed to get run log: log not found`` because the two current-head runs
    concluded ``action_required`` (an approval gate) and had no logs. These tests pin
    that such a run is reported as an owner-approval gate instead of a code failure.
    """

    HEAD = "headsha1234567890"

    def _patched_gh(self, runs: list[dict[str, object]], log_output: str | None = None):
        calls: list[list[str]] = []

        def fake_gh(args, *, source_env, check=True):
            calls.append(list(args))
            if list(args[:2]) == ["pr", "view"]:
                return CompletedProcess(list(args), 0, stdout=json.dumps({"headRefOid": self.HEAD}), stderr="")
            if list(args[:2]) == ["run", "list"]:
                return CompletedProcess(list(args), 0, stdout=json.dumps(runs), stderr="")
            if list(args[:2]) == ["run", "view"]:
                output = log_output if log_output is not None else f"log for {args[2]}"
                return CompletedProcess(list(args), 0, stdout=output, stderr="")
            return CompletedProcess(list(args), 0, stdout="", stderr="")

        return fake_gh, calls

    def test_action_required_run_is_not_packaged_as_failure_evidence(self) -> None:
        runs = [
            {"databaseId": 43495367336, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Python checks"},
        ]
        fake_gh, calls = self._patched_gh(runs)
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            context = remote_ci_failure_context("url", "branch", {"GITHUB_TOKEN": "x"})
            approval_required = ci_requires_owner_approval("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertEqual(context, "")
        self.assertTrue(approval_required)
        self.assertFalse(any(call[:2] == ["run", "view"] for call in calls))
        self.assertNotIn("log not found", context)

    def test_real_failure_log_is_collected_and_takes_priority_over_approval_gate(self) -> None:
        runs = [
            {"databaseId": 111, "headSha": self.HEAD, "status": "completed",
             "conclusion": "failure", "name": "Windows desktop build"},
            {"databaseId": 222, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Python checks"},
        ]
        fake_gh, calls = self._patched_gh(runs)
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            context = remote_ci_failure_context("url", "branch", {"GITHUB_TOKEN": "x"})
            approval_required = ci_requires_owner_approval("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertIn("log for 111", context)
        self.assertNotIn("log for 222", context)
        viewed = [call[2] for call in calls if call[:2] == ["run", "view"]]
        self.assertEqual(viewed, ["111"])
        self.assertFalse(approval_required)

    def test_exact_sanitized_action_required_evidence_parks_without_a_model_call(self) -> None:
        """The 14 November #43567081759/#43567081760 evidence must never reach the model."""
        runs = [
            {"databaseId": 43567081759, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Python checks"},
            {"databaseId": 43567081760, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Windows desktop build"},
        ]
        fake_gh, calls = self._patched_gh(runs, log_output="failed to get run log: log not found")
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            context = remote_ci_failure_context("url", "branch", {"GITHUB_TOKEN": "x"})
            message = owner_approval_required_message("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertEqual(context, "")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        self.assertFalse(any(call[:2] == ["run", "view"] for call in calls))

    def test_latest_sanitized_action_required_evidence_parks_without_a_model_call(self) -> None:
        """The 14 November #43601410296/#43601410276 evidence must never reach the model."""
        runs = [
            {"databaseId": 43601410296, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Python checks"},
            {"databaseId": 43601410276, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Windows desktop build"},
        ]
        fake_gh, calls = self._patched_gh(runs, log_output="failed to get run log: log not found")
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            context = remote_ci_failure_context("url", "branch", {"GITHUB_TOKEN": "x"})
            message = owner_approval_required_message("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertEqual(context, "")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        self.assertFalse(any(call[:2] == ["run", "view"] for call in calls))

    def test_current_sanitized_action_required_pair_parks_without_a_model_call(self) -> None:
        """The 15 November #43649302769/#43649302743 evidence must never reach the model."""
        runs = [
            {"databaseId": 43649302743, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Python checks"},
            {"databaseId": 43649302769, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Windows desktop build"},
        ]
        fake_gh, calls = self._patched_gh(runs, log_output="failed to get run log: log not found")
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            context = remote_ci_failure_context("url", "branch", {"GITHUB_TOKEN": "x"})
            message = owner_approval_required_message("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertEqual(context, "")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        self.assertFalse(any(call[:2] == ["run", "view"] for call in calls))

    def test_newest_sanitized_approval_gate_pair_is_refused(self) -> None:
        """The #43649302769/#43649302743 legacy chunks must never become a repair prompt."""
        evidence = (
            "===== Windows desktop build run 43649302769 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43649302743 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertTrue(approval_gate_evidence(evidence))
        message = unusable_repair_evidence_message(evidence, "url")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        prompt = build_repair_prompt(evidence)
        self.assertIn("OWNER_APPROVAL_REQUIRED", prompt)
        self.assertNotIn("Diagnose the concrete failure", prompt)

    def test_newest_ci_run_pair_43685572267_parks_without_a_model_call(self) -> None:
        """The 15 November #43685572267/#43685572300 evidence must never reach the model."""
        runs = [
            {"databaseId": 43685572300, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Python checks"},
            {"databaseId": 43685572267, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Windows desktop build"},
        ]
        fake_gh, calls = self._patched_gh(runs, log_output="failed to get run log: log not found")
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            context = remote_ci_failure_context("url", "branch", {"GITHUB_TOKEN": "x"})
            message = owner_approval_required_message("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertEqual(context, "")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        self.assertFalse(any(call[:2] == ["run", "view"] for call in calls))

    def test_newest_ci_run_pair_43685572267_cannot_build_a_repair_prompt(self) -> None:
        """The #43685572267/#43685572300 legacy chunks must never become a repair prompt."""
        evidence = (
            "===== Windows desktop build run 43685572267 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43685572300 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(evidence), ["action_required", "action_required"])
        self.assertTrue(approval_gate_evidence(evidence))
        message = unusable_repair_evidence_message(evidence, "url")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        prompt = build_repair_prompt(evidence)
        self.assertIn("OWNER_APPROVAL_REQUIRED", prompt)
        self.assertNotIn("Diagnose the concrete failure", prompt)

    def test_legacy_action_required_chunks_are_detected_as_an_approval_gate(self) -> None:
        evidence = (
            "===== Python checks run 43601410296 (action_required) =====\n"
            "failed to get run log: log not found\n\n"
            "===== Windows desktop build run 43601410276 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(evidence), ["action_required", "action_required"])
        self.assertTrue(approval_gate_evidence(evidence))
        message = approval_gate_evidence_message(evidence, "url")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)

    def test_real_failure_chunk_is_not_approval_gate_evidence(self) -> None:
        evidence = (
            "===== Windows desktop build run 111 (failure) =====\n"
            "AssertionError: expected 2 got 1"
        )
        self.assertFalse(approval_gate_evidence(evidence))
        self.assertIsNone(approval_gate_evidence_message(evidence, "url"))
        mixed = evidence + (
            "\n\n===== Python checks run 222 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertFalse(approval_gate_evidence(mixed))

    def test_build_repair_prompt_refuses_legacy_approval_gate_evidence(self) -> None:
        evidence = (
            "===== Python checks run 43601410296 (action_required) =====\n"
            "failed to get run log: log not found\n\n"
            "===== Windows desktop build run 43601410276 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        prompt = build_repair_prompt(evidence)
        self.assertIn("OWNER_APPROVAL_REQUIRED", prompt)
        self.assertNotIn("Diagnose the concrete failure", prompt)
        self.assertNotIn("fix the underlying issue", prompt)

    def test_current_sanitized_approval_gate_pair_is_refused(self) -> None:
        """The #43648458309/#43648458292 evidence must never become a repair prompt."""
        evidence = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Python checks run 43648458309 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Windows desktop build run 43648458292 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertTrue(approval_gate_evidence(evidence))
        message = unusable_repair_evidence_message(evidence, "url")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        prompt = build_repair_prompt(evidence)
        self.assertIn("OWNER_APPROVAL_REQUIRED", prompt)
        self.assertNotIn("Diagnose the concrete failure", prompt)

    def test_unavailable_failure_log_cannot_build_a_repair_prompt(self) -> None:
        """A `failure` header with only `log not found` is not actionable evidence."""
        evidence = (
            "===== Windows desktop build run 43648092720 (failure) =====\n"
            "failed to get run log: log not found"
        )
        self.assertFalse(ci_evidence_has_log(evidence))
        message = unusable_repair_evidence_message(evidence, "url")
        self.assertIsNotNone(message)
        self.assertIn("CI_EVIDENCE_UNAVAILABLE", message)
        prompt = build_repair_prompt(evidence)
        self.assertIn("CI_EVIDENCE_UNAVAILABLE", prompt)
        self.assertNotIn("Diagnose the concrete failure", prompt)

    def test_bare_unavailable_log_notice_cannot_build_a_repair_prompt(self) -> None:
        """A header-less `log not found` notice must still be refused, not "diagnosed"."""
        evidence = "failed to get run log: log not found"
        self.assertFalse(ci_evidence_has_log(evidence))
        message = unusable_repair_evidence_message(evidence, "url")
        self.assertIsNotNone(message)
        self.assertIn("CI_EVIDENCE_UNAVAILABLE", message)
        prompt = build_repair_prompt(evidence)
        self.assertIn("CI_EVIDENCE_UNAVAILABLE", prompt)
        self.assertNotIn("Diagnose the concrete failure", prompt)

    def test_newest_ci_run_pair_43749264535_parks_without_a_model_call(self) -> None:
        """The 15 November #43749264535/#43749264536 evidence must never reach the model."""
        runs = [
            {"databaseId": 43749264536, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Python checks"},
            {"databaseId": 43749264535, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Windows desktop build"},
        ]
        fake_gh, calls = self._patched_gh(runs, log_output="failed to get run log: log not found")
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            context = remote_ci_failure_context("url", "branch", {"GITHUB_TOKEN": "x"})
            message = owner_approval_required_message("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertEqual(context, "")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        self.assertFalse(any(call[:2] == ["run", "view"] for call in calls))

    def test_newest_ci_run_pair_43749264535_cannot_build_a_repair_prompt(self) -> None:
        """The #43749264535/#43749264536 legacy chunks must never become a repair prompt."""
        evidence = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 43749264535 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43749264536 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(evidence), ["action_required", "action_required"])
        self.assertTrue(approval_gate_evidence(evidence))
        message = unusable_repair_evidence_message(evidence, "url")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        prompt = build_repair_prompt(evidence)
        self.assertIn("OWNER_APPROVAL_REQUIRED", prompt)
        self.assertNotIn("Diagnose the concrete failure", prompt)

    def test_newest_ci_run_pair_43749765989_parks_without_a_model_call(self) -> None:
        """The 16 November #43749765989/#43749766017 evidence must never reach the model."""
        runs = [
            {"databaseId": 43749766017, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Python checks"},
            {"databaseId": 43749765989, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Windows desktop build"},
        ]
        fake_gh, calls = self._patched_gh(runs, log_output="failed to get run log: log not found")
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            context = remote_ci_failure_context("url", "branch", {"GITHUB_TOKEN": "x"})
            message = owner_approval_required_message("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertEqual(context, "")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        self.assertFalse(any(call[:2] == ["run", "view"] for call in calls))

    def test_newest_ci_run_pair_43749765989_cannot_build_a_repair_prompt(self) -> None:
        """The #43749765989/#43749766017 legacy chunks must never become a repair prompt."""
        evidence = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 43749765989 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43749766017 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(evidence), ["action_required", "action_required"])
        self.assertTrue(approval_gate_evidence(evidence))
        message = unusable_repair_evidence_message(evidence, "url")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        prompt = build_repair_prompt(evidence)
        self.assertIn("OWNER_APPROVAL_REQUIRED", prompt)
        self.assertNotIn("Diagnose the concrete failure", prompt)

    def test_newest_ci_run_pair_43817219556_parks_without_a_model_call(self) -> None:
        """The 16 November #43817219556/#43817219541 evidence must never reach the model."""
        runs = [
            {"databaseId": 43817219541, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Python checks"},
            {"databaseId": 43817219556, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Windows desktop build"},
        ]
        fake_gh, calls = self._patched_gh(runs, log_output="failed to get run log: log not found")
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            context = remote_ci_failure_context("url", "branch", {"GITHUB_TOKEN": "x"})
            message = owner_approval_required_message("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertEqual(context, "")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        self.assertFalse(any(call[:2] == ["run", "view"] for call in calls))

    def test_newest_ci_run_pair_43817219556_cannot_build_a_repair_prompt(self) -> None:
        """The #43817219556/#43817219541 legacy chunks must never become a repair prompt."""
        evidence = (
            "===== Windows desktop build run 43817219556 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43817219541 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(evidence), ["action_required", "action_required"])
        self.assertTrue(approval_gate_evidence(evidence))
        message = unusable_repair_evidence_message(evidence, "url")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        prompt = build_repair_prompt(evidence)
        self.assertIn("OWNER_APPROVAL_REQUIRED", prompt)
        self.assertNotIn("Diagnose the concrete failure", prompt)

    def test_newest_ci_run_pair_43966482393_parks_without_a_model_call(self) -> None:
        """The 17 November #43966482393/#43966482410 evidence must never reach the model."""
        runs = [
            {"databaseId": 43966482410, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Python checks"},
            {"databaseId": 43966482393, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Windows desktop build"},
        ]
        fake_gh, calls = self._patched_gh(runs, log_output="failed to get run log: log not found")
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            context = remote_ci_failure_context("url", "branch", {"GITHUB_TOKEN": "x"})
            message = owner_approval_required_message("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertEqual(context, "")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        self.assertFalse(any(call[:2] == ["run", "view"] for call in calls))

    def test_newest_ci_run_pair_43966482393_cannot_build_a_repair_prompt(self) -> None:
        """The #43966482393/#43966482410 legacy chunks must never become a repair prompt."""
        evidence = (
            "===== Windows desktop build run 43966482393 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43966482410 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(evidence), ["action_required", "action_required"])
        self.assertTrue(approval_gate_evidence(evidence))
        message = unusable_repair_evidence_message(evidence, "url")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        prompt = build_repair_prompt(evidence)
        self.assertIn("OWNER_APPROVAL_REQUIRED", prompt)
        self.assertNotIn("Diagnose the concrete failure", prompt)

    def test_newest_ci_run_pair_44042810216_parks_without_a_model_call(self) -> None:
        """The newest #44042810216/#44042810197 evidence must never reach the model."""
        runs = [
            {"databaseId": 44042810216, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Python checks"},
            {"databaseId": 44042810197, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Windows desktop build"},
        ]
        fake_gh, calls = self._patched_gh(runs, log_output="failed to get run log: log not found")
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            context = remote_ci_failure_context("url", "branch", {"GITHUB_TOKEN": "x"})
            message = owner_approval_required_message("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertEqual(context, "")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        self.assertFalse(any(call[:2] == ["run", "view"] for call in calls))

    def test_newest_ci_run_pair_44042810216_cannot_build_a_repair_prompt(self) -> None:
        """The #44042810216/#44042810197 legacy chunks must never become a repair prompt."""
        evidence = (
            "===== Windows desktop build run 44042810197 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 44042810216 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(evidence), ["action_required", "action_required"])
        self.assertTrue(approval_gate_evidence(evidence))
        message = unusable_repair_evidence_message(evidence, "url")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        prompt = build_repair_prompt(evidence)
        self.assertIn("OWNER_APPROVAL_REQUIRED", prompt)
        self.assertNotIn("Diagnose the concrete failure", prompt)

    def test_newest_ci_run_pair_44174341838_parks_without_a_model_call(self) -> None:
        """The 18 November #44174341838/#44174342093 evidence must never reach the model."""
        runs = [
            {"databaseId": 44174341838, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Python checks"},
            {"databaseId": 44174342093, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Windows desktop build"},
        ]
        fake_gh, calls = self._patched_gh(runs, log_output="failed to get run log: log not found")
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            context = remote_ci_failure_context("url", "branch", {"GITHUB_TOKEN": "x"})
            message = owner_approval_required_message("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertEqual(context, "")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        self.assertFalse(any(call[:2] == ["run", "view"] for call in calls))

    def test_newest_ci_run_pair_44174341838_cannot_build_a_repair_prompt(self) -> None:
        """The #44174341838/#44174342093 legacy chunks must never become a repair prompt."""
        evidence = (
            "===== Python checks run 44174341838 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Windows desktop build run 44174342093 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(evidence), ["action_required", "action_required"])
        self.assertTrue(approval_gate_evidence(evidence))
        message = unusable_repair_evidence_message(evidence, "url")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        prompt = build_repair_prompt(evidence)
        self.assertIn("OWNER_APPROVAL_REQUIRED", prompt)
        self.assertNotIn("Diagnose the concrete failure", prompt)

    def test_exact_validation_replay_44174341838_is_refused(self) -> None:
        """The exact 18 November validation replay must never become a repair prompt.

        This is the raw text the controller replayed into the session, including the
        CI-repair instruction and trailing newline, not just the bare run chunks.
        """
        replayed = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Python checks run 44174341838 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Windows desktop build run 44174342093 (action_required) =====\n"
            "failed to get run log: log not found\n"
        )
        self.assertEqual(ci_run_conclusions(replayed), ["action_required", "action_required"])
        self.assertTrue(approval_gate_evidence(replayed))
        self.assertIn("OWNER_APPROVAL_REQUIRED", build_repair_prompt(replayed))
        self.assertIn("OWNER_APPROVAL_REQUIRED", unusable_ci_prompt_message(replayed) or "")
        self.assertNotIn("Diagnose the concrete failure", build_repair_prompt(replayed))

    def test_newest_ci_run_pair_44258836858_parks_without_a_model_call(self) -> None:
        """The 18 November #44258836858/#44258836775 evidence must never reach the model."""
        runs = [
            {"databaseId": 44258836858, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Windows desktop build"},
            {"databaseId": 44258836775, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Python checks"},
        ]
        fake_gh, calls = self._patched_gh(runs, log_output="failed to get run log: log not found")
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            context = remote_ci_failure_context("url", "branch", {"GITHUB_TOKEN": "x"})
            message = owner_approval_required_message("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertEqual(context, "")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        self.assertFalse(any(call[:2] == ["run", "view"] for call in calls))

    def test_newest_ci_run_pair_44258836858_cannot_build_a_repair_prompt(self) -> None:
        """The #44258836858/#44258836775 legacy chunks must never become a repair prompt."""
        evidence = (
            "===== Windows desktop build run 44258836858 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 44258836775 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(evidence), ["action_required", "action_required"])
        self.assertTrue(approval_gate_evidence(evidence))
        message = unusable_repair_evidence_message(evidence, "url")
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        prompt = build_repair_prompt(evidence)
        self.assertIn("OWNER_APPROVAL_REQUIRED", prompt)
        self.assertNotIn("Diagnose the concrete failure", prompt)

    def test_exact_validation_replay_44258836858_is_refused(self) -> None:
        """The exact 18 November validation replay must never become a repair prompt."""
        replayed = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 44258836858 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 44258836775 (action_required) =====\n"
            "failed to get run log: log not found\n"
        )
        self.assertEqual(ci_run_conclusions(replayed), ["action_required", "action_required"])
        self.assertTrue(approval_gate_evidence(replayed))
        self.assertIn("OWNER_APPROVAL_REQUIRED", build_repair_prompt(replayed))
        self.assertIn("OWNER_APPROVAL_REQUIRED", unusable_ci_prompt_message(replayed) or "")
        self.assertNotIn("Diagnose the concrete failure", build_repair_prompt(replayed))

    def test_real_failure_log_still_builds_a_repair_prompt(self) -> None:
        evidence = (
            "===== Windows desktop build run 111 (failure) =====\n"
            "AssertionError: expected 2 got 1"
        )
        self.assertTrue(ci_evidence_has_log(evidence))
        self.assertIsNone(unusable_repair_evidence_message(evidence, "url"))
        prompt = build_repair_prompt(evidence)
        self.assertIn("Diagnose the concrete failure", prompt)
        self.assertIn("AssertionError: expected 2 got 1", prompt)

    def test_mixed_failure_and_unavailable_chunks_use_the_readable_log(self) -> None:
        evidence = (
            "===== Python checks run 1 (failure) =====\n"
            "failed to get run log: log not found\n\n"
            "===== Windows desktop build run 2 (failure) =====\n"
            "AssertionError: real failure"
        )
        self.assertTrue(ci_evidence_has_log(evidence))
        self.assertIsNone(unusable_repair_evidence_message(evidence, "url"))

    def test_unavailable_failure_log_is_not_packaged_as_evidence(self) -> None:
        """Even a genuine `failure` run with no retrievable log must not become fake evidence."""
        runs = [
            {"databaseId": 43567081760, "headSha": self.HEAD, "status": "completed",
             "conclusion": "failure", "name": "Windows desktop build"},
        ]
        fake_gh, _calls = self._patched_gh(runs, log_output="failed to get run log: log not found")
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            context = remote_ci_failure_context("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertEqual(context, "")
        self.assertNotIn("log not found", context)

    def test_failure_log_availability_rejects_empty_and_cli_notice(self) -> None:
        for raw in ("", "   ", "failed to get run log: log not found", "Log not found"):
            with self.subTest(raw=raw):
                self.assertFalse(failure_log_is_available(raw))
        self.assertTrue(failure_log_is_available("AssertionError: expected 2 got 1"))

    def test_owner_approval_message_is_returned_for_an_approval_gate(self) -> None:
        runs = [
            {"databaseId": 43495367336, "headSha": self.HEAD, "status": "completed",
             "conclusion": "action_required", "name": "Python checks"},
        ]
        fake_gh, _calls = self._patched_gh(runs)
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            message = owner_approval_required_message("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertIsNotNone(message)
        self.assertIn("OWNER_APPROVAL_REQUIRED", message)
        self.assertIn("action_required", message)

    def test_owner_approval_message_is_absent_when_a_real_failure_exists(self) -> None:
        runs = [
            {"databaseId": 1, "headSha": self.HEAD, "status": "completed",
             "conclusion": "failure", "name": "Windows desktop build"},
        ]
        fake_gh, _calls = self._patched_gh(runs)
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=fake_gh):
            message = owner_approval_required_message("url", "branch", {"GITHUB_TOKEN": "x"})
        self.assertIsNone(message)


class ExistingPrOwnerReviewTests(unittest.TestCase):
    def test_protected_non_checkpoint_pr_parks_for_owner_review(self) -> None:
        message = existing_pr_owner_review_message("url", False, ["scripts/eclipse_autonomous.py"])
        self.assertIsNotNone(message)
        self.assertIn("OWNER_REVIEW_REQUIRED", message)

    def test_protected_checkpoint_draft_is_still_resumable(self) -> None:
        self.assertIsNone(
            existing_pr_owner_review_message("url", True, ["scripts/eclipse_autonomous.py"])
        )

    def test_ordinary_non_checkpoint_pr_is_not_early_parked(self) -> None:
        self.assertIsNone(
            existing_pr_owner_review_message("url", False, ["src/eclipse/example.py"])
        )


class EndToEndFailedPrRecoveryTests(unittest.TestCase):
    """Drive the whole ``resume_existing_pr`` path against a real temporary Git repo.

    Only the external boundaries are mocked: ``gh`` (GitHub) and
    ``run_agent_with_failover`` (the OpenCode child). Git fetch/switch/commit/push and
    the controller's safety guards run for real. This pins the deliberate failed-PR
    recovery scenario: a real failed run is repaired on the *same* branch and
    session, no second branch or PR is created, and the merge happens only after the
    checks turn green.
    """

    BRANCH = "feature/eclipse-autonomous-1-1"
    PR_URL = "https://github.com/Tygaclaw/Project-Eclipse/pull/16"
    SESSION = "ses_e2e1234567890"
    MODEL = "provider/model-rank-1"
    RUN_ID = 43567081759

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.repo = self.tmp / "repo"
        self.remote = self.tmp / "remote.git"
        self.repo.mkdir()

        self._git("init", cwd=self.repo)
        self._git("config", "user.email", "e2e@example.test", cwd=self.repo)
        self._git("config", "user.name", "E2E Test", cwd=self.repo)
        self._git("checkout", "-b", "main", cwd=self.repo)
        (self.repo / "README.md").write_text("base\n", encoding="utf-8")
        self._git("add", "-A", cwd=self.repo)
        self._git("commit", "-m", "base", cwd=self.repo)

        self._git("init", "--bare", str(self.remote), cwd=self.tmp)
        self._git("remote", "add", "origin", str(self.remote), cwd=self.repo)
        self._git("push", "-u", "origin", "main", cwd=self.repo)

        self._git("checkout", "-b", self.BRANCH, cwd=self.repo)
        (self.repo / "src").mkdir()
        (self.repo / "src" / "feature.py").write_text("feature = True\n", encoding="utf-8")
        self._git("add", "-A", cwd=self.repo)
        self._git("commit", "-m", "feature work", cwd=self.repo)
        self._git("push", "-u", "origin", self.BRANCH, cwd=self.repo)
        self._git("fetch", "origin", cwd=self.repo)

        self._original_root = eclipse_autonomous.ROOT
        self._original_commit = eclipse_autonomous.commit_and_push_worktree
        eclipse_autonomous.ROOT = self.repo
        self.agent_calls: list[dict[str, object]] = []
        self.gh_calls: list[list[str]] = []
        self.run_views: list[list[str]] = []
        self.merge_calls: list[list[str]] = []
        self.commits = 0
        self.ci_conclusion = "failure"

    def tearDown(self) -> None:
        eclipse_autonomous.ROOT = self._original_root
        self._tmp.cleanup()

    def _git(self, *args: str, cwd: Path) -> CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=cwd, text=True, capture_output=True, check=True
        )

    def _head(self) -> str:
        return self._git("rev-parse", "HEAD", cwd=self.repo).stdout.strip()

    def _fake_gh(self, args, *, source_env, check=True):
        self.gh_calls.append(list(args))
        if list(args[:2]) == ["pr", "view"]:
            fields = args[args.index("--json") + 1]
            data: dict[str, object] = {"headRefOid": self._head(), "state": "OPEN", "isDraft": False}
            if "state" not in fields:
                data = {"headRefOid": data["headRefOid"]}
            return CompletedProcess(list(args), 0, json.dumps(data), "")
        if list(args[:2]) == ["run", "list"]:
            runs = [{
                "databaseId": self.RUN_ID, "headSha": self._head(), "status": "completed",
                "conclusion": self.ci_conclusion, "name": "Windows desktop build",
            }]
            return CompletedProcess(list(args), 0, json.dumps(runs), "")
        if list(args[:2]) == ["run", "view"]:
            self.run_views.append(list(args))
            return CompletedProcess(list(args), 0, "AssertionError: Windows check failed\n", "")
        if list(args[:2]) == ["pr", "checks"]:
            green = self.commits >= 2
            return CompletedProcess(
                list(args), 0 if green else 1, "", "" if green else "checks failed"
            )
        if list(args[:2]) == ["pr", "merge"]:
            self.merge_calls.append(list(args))
            return CompletedProcess(list(args), 0, "merged", "")
        return CompletedProcess(list(args), 0, "", "")

    def _fake_agent(self, prompt, run_title, source_env, **kwargs):
        self.agent_calls.append({
            "prompt": prompt,
            "initial_session_id": kwargs.get("initial_session_id"),
            "start_model_id": kwargs.get("start_model_id"),
        })
        recovery = self.repo / "src" / "recovery.py"
        if len(self.agent_calls) == 1:
            recovery.write_text("recovered = True\n", encoding="utf-8")
        else:
            recovery.write_text("recovered = True\nrepaired = True\n", encoding="utf-8")
        return True, self.SESSION, self.MODEL, ""

    def _commit_wrapper(self, branch, source_env):
        result = self._original_commit(branch, source_env)
        if result[0]:
            self.commits += 1
        return result

    def test_failed_pr_is_repaired_in_place_on_the_same_branch_without_a_new_pr(self) -> None:
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        # Same branch, same PR: no duplicate branch/PR was created.
        self.assertEqual(self._git("rev-parse", "--abbrev-ref", "HEAD", cwd=self.repo).stdout.strip(), self.BRANCH)
        self.assertFalse(any(call[:2] == ["pr", "create"] for call in self.gh_calls))
        # The first recovery and the follow-up CI repair both ran in one session.
        self.assertEqual(len(self.agent_calls), 2)
        self.assertIsNone(self.agent_calls[0]["initial_session_id"])
        self.assertEqual(self.agent_calls[1]["initial_session_id"], self.SESSION)
        self.assertEqual(self.agent_calls[1]["start_model_id"], self.MODEL)
        # The prompt carries the real failure log, not the old log-less evidence.
        self.assertIn(self.PR_URL, str(self.agent_calls[0]["prompt"]))
        self.assertIn("checkpoint: False", str(self.agent_calls[0]["prompt"]))
        self.assertIn("AssertionError: Windows check failed", str(self.agent_calls[0]["prompt"]))
        self.assertNotIn("log not found", str(self.agent_calls[0]["prompt"]))
        # Work was committed and pushed back to the same remote branch.
        self.assertEqual(self._git("rev-parse", f"origin/{self.BRANCH}", cwd=self.repo).stdout.strip(), self._head())
        self.assertEqual(len(self.merge_calls), 1)

    def test_action_required_pr_parks_before_any_model_call_or_run_log_fetch(self) -> None:
        """The exact sanitized run pair must park the PR, not start a recovery model call."""
        self.ci_conclusion = "action_required"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(self.agent_calls, [])
        self.assertEqual(self.run_views, [])
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.commits, 0)
        self.assertFalse(any(call[:2] == ["pr", "create"] for call in self.gh_calls))

    def test_legacy_approval_gate_evidence_parks_without_a_model_call(self) -> None:
        """Even if a stale/external caller supplies the old chunks, no repair runs."""
        legacy_evidence = (
            "===== Python checks run 43601410296 (action_required) =====\n"
            "failed to get run log: log not found\n\n"
            "===== Windows desktop build run 43601410276 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context", return_value=legacy_evidence
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(self.agent_calls, [])
        self.assertEqual(self.run_views, [])
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.commits, 0)

    def test_newest_ci_run_pair_43685572267_parks_through_the_full_recovery_path(self) -> None:
        """The exact reported validation evidence must park without a model, log or commit.

        This reproduces the reported validation failure verbatim: the two
        ``action_required`` chunks (#43685572267/#43685572300) are fed into
        ``resume_existing_pr`` and must be rejected as an owner-approval gate through the
        real Git recovery path, not sent to the recovery model as a code failure.
        """
        validation_evidence = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 43685572267 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43685572300 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context", return_value=validation_evidence
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(self.agent_calls, [])
        self.assertEqual(self.run_views, [])
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.commits, 0)
        self.assertFalse(any(call[:2] == ["pr", "create"] for call in self.gh_calls))

    def test_newest_ci_run_pair_43749765989_parks_through_the_full_recovery_path(self) -> None:
        """The exact 16 November validation evidence must park without a model, log or commit."""
        validation_evidence = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 43749765989 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43749766017 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context", return_value=validation_evidence
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(self.agent_calls, [])
        self.assertEqual(self.run_views, [])
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.commits, 0)
        self.assertFalse(any(call[:2] == ["pr", "create"] for call in self.gh_calls))

    def test_newest_ci_run_pair_43817219556_parks_through_the_full_recovery_path(self) -> None:
        """The exact 16 November validation evidence must park without a model, log or commit."""
        validation_evidence = (
            "===== Windows desktop build run 43817219556 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43817219541 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context", return_value=validation_evidence
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(self.agent_calls, [])
        self.assertEqual(self.run_views, [])
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.commits, 0)
        self.assertFalse(any(call[:2] == ["pr", "create"] for call in self.gh_calls))

    def test_followup_ci_repair_rejects_replayed_approval_gate_evidence(self) -> None:
        """The exact validation replay happens in the CI-repair stage, not only pre-recovery.

        The first recovery gets a real failure log and commits; the follow-up CI check then
        replays the #43749765989/#43749766017 ``action_required`` chunks. That second stage
        must park without another model call or commit, which is the concrete failure the
        independent validation step reported.
        """
        real_failure = (
            "===== Windows desktop build run 111 (failure) =====\n"
            "AssertionError: Windows check failed"
        )
        replayed = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 43749765989 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43749766017 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context",
                    side_effect=[real_failure, replayed],
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(len(self.agent_calls), 1)
        self.assertIn("AssertionError: Windows check failed", str(self.agent_calls[0]["prompt"]))
        self.assertEqual(self.commits, 1)
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.run_views, [])

    def test_followup_ci_repair_rejects_replayed_43817219556_evidence(self) -> None:
        """The exact reported validation replay must park at the follow-up CI-repair stage.

        The first recovery gets a real failure log and commits; the follow-up CI check then
        replays the #43817219556/#43817219541 ``action_required`` chunks, prefixed with the
        CI-repair instruction. That second stage must park without another model call,
        ``run view``, commit or merge, which is the concrete validation failure reported.
        """
        real_failure = (
            "===== Windows desktop build run 111 (failure) =====\n"
            "AssertionError: Windows check failed"
        )
        replayed = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 43817219556 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43817219541 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(replayed), ["action_required", "action_required"])
        self.assertIn("OWNER_APPROVAL_REQUIRED", build_repair_prompt(replayed))
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context",
                    side_effect=[real_failure, replayed],
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(len(self.agent_calls), 1)
        self.assertIn("AssertionError: Windows check failed", str(self.agent_calls[0]["prompt"]))
        self.assertNotIn("43817219556", str(self.agent_calls[0]["prompt"]))
        self.assertEqual(self.commits, 1)
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.run_views, [])

    def test_followup_ci_repair_rejects_replayed_43966081267_evidence(self) -> None:
        """The exact reported validation replay must park at the follow-up CI-repair stage.

        The first recovery gets a real failure log and commits; the follow-up CI check then
        replays the #43966081267/#43966081265 ``action_required`` chunks, prefixed with the
        CI-repair instruction. That second stage must park without another model call,
        ``run view``, commit or merge, which is the concrete validation failure reported.
        """
        real_failure = (
            "===== Windows desktop build run 111 (failure) =====\n"
            "AssertionError: Windows check failed"
        )
        replayed = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 43966081267 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43966081265 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(replayed), ["action_required", "action_required"])
        self.assertIn("OWNER_APPROVAL_REQUIRED", build_repair_prompt(replayed))
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context",
                    side_effect=[real_failure, replayed],
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(len(self.agent_calls), 1)
        self.assertIn("AssertionError: Windows check failed", str(self.agent_calls[0]["prompt"]))
        self.assertNotIn("43966081267", str(self.agent_calls[0]["prompt"]))
        self.assertEqual(self.commits, 1)
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.run_views, [])

    def test_newest_ci_run_pair_43966482393_parks_through_the_full_recovery_path(self) -> None:
        """The exact 17 November validation evidence must park without a model, log or commit."""
        validation_evidence = (
            "===== Windows desktop build run 43966482393 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43966482410 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context", return_value=validation_evidence
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(self.agent_calls, [])
        self.assertEqual(self.run_views, [])
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.commits, 0)
        self.assertFalse(any(call[:2] == ["pr", "create"] for call in self.gh_calls))

    def test_followup_ci_repair_rejects_replayed_43966482393_evidence(self) -> None:
        """The exact reported validation replay must park at the follow-up CI-repair stage.

        The first recovery gets a real failure log and commits; the follow-up CI check then
        replays the #43966482393/#43966482410 ``action_required`` chunks, prefixed with the
        CI-repair instruction. That second stage must park without another model call,
        ``run view``, commit or merge, which is the concrete validation failure reported.
        """
        real_failure = (
            "===== Windows desktop build run 111 (failure) =====\n"
            "AssertionError: Windows check failed"
        )
        replayed = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 43966482393 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 43966482410 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(replayed), ["action_required", "action_required"])
        self.assertIn("OWNER_APPROVAL_REQUIRED", build_repair_prompt(replayed))
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context",
                    side_effect=[real_failure, replayed],
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(len(self.agent_calls), 1)
        self.assertIn("AssertionError: Windows check failed", str(self.agent_calls[0]["prompt"]))
        self.assertNotIn("43966482393", str(self.agent_calls[0]["prompt"]))
        self.assertEqual(self.commits, 1)
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.run_views, [])

    def test_newest_ci_run_pair_44042810216_parks_through_the_full_recovery_path(self) -> None:
        """The exact newest validation evidence must park without a model, log or commit."""
        validation_evidence = (
            "===== Windows desktop build run 44042810197 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 44042810216 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context", return_value=validation_evidence
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(self.agent_calls, [])
        self.assertEqual(self.run_views, [])
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.commits, 0)
        self.assertFalse(any(call[:2] == ["pr", "create"] for call in self.gh_calls))

    def test_followup_ci_repair_rejects_replayed_44042810216_evidence(self) -> None:
        """A replayed #44042810216/#44042810197 CI-repair prompt must park at the follow-up stage.

        The first recovery gets a real failure log and commits; the follow-up CI check then
        replays the newest ``action_required`` chunks, prefixed with the CI-repair
        instruction. That second stage must park without another model call, ``run view``,
        commit or merge.
        """
        real_failure = (
            "===== Windows desktop build run 111 (failure) =====\n"
            "AssertionError: Windows check failed"
        )
        replayed = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 44042810197 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 44042810216 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(replayed), ["action_required", "action_required"])
        self.assertIn("OWNER_APPROVAL_REQUIRED", build_repair_prompt(replayed))
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context",
                    side_effect=[real_failure, replayed],
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(len(self.agent_calls), 1)
        self.assertIn("AssertionError: Windows check failed", str(self.agent_calls[0]["prompt"]))
        self.assertNotIn("44042810216", str(self.agent_calls[0]["prompt"]))
        self.assertEqual(self.commits, 1)
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.run_views, [])

    def test_newest_ci_run_pair_44174341838_parks_through_the_full_recovery_path(self) -> None:
        """The exact newest validation evidence must park without a model, log or commit."""
        validation_evidence = (
            "===== Python checks run 44174341838 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Windows desktop build run 44174342093 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context", return_value=validation_evidence
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(self.agent_calls, [])
        self.assertEqual(self.run_views, [])
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.commits, 0)
        self.assertFalse(any(call[:2] == ["pr", "create"] for call in self.gh_calls))

    def test_followup_ci_repair_rejects_replayed_44174341838_evidence(self) -> None:
        """A replayed #44174341838/#44174342093 CI-repair prompt must park at the follow-up stage.

        The first recovery gets a real failure log and commits; the follow-up CI check then
        replays the newest ``action_required`` chunks, prefixed with the CI-repair
        instruction. That second stage must park without another model call, ``run view``,
        commit or merge.
        """
        real_failure = (
            "===== Windows desktop build run 111 (failure) =====\n"
            "AssertionError: Windows check failed"
        )
        replayed = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Python checks run 44174341838 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Windows desktop build run 44174342093 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(replayed), ["action_required", "action_required"])
        self.assertIn("OWNER_APPROVAL_REQUIRED", build_repair_prompt(replayed))
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context",
                    side_effect=[real_failure, replayed],
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(len(self.agent_calls), 1)
        self.assertIn("AssertionError: Windows check failed", str(self.agent_calls[0]["prompt"]))
        self.assertNotIn("44174341838", str(self.agent_calls[0]["prompt"]))
        self.assertEqual(self.commits, 1)
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.run_views, [])

    def test_newest_ci_run_pair_44258836858_parks_through_the_full_recovery_path(self) -> None:
        """The exact newest validation evidence must park without a model, log or commit."""
        validation_evidence = (
            "===== Windows desktop build run 44258836858 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 44258836775 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context", return_value=validation_evidence
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(self.agent_calls, [])
        self.assertEqual(self.run_views, [])
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.commits, 0)
        self.assertFalse(any(call[:2] == ["pr", "create"] for call in self.gh_calls))

    def test_followup_ci_repair_rejects_replayed_44258836858_evidence(self) -> None:
        """A replayed #44258836858/#44258836775 CI-repair prompt must park at the follow-up stage."""
        real_failure = (
            "===== Windows desktop build run 111 (failure) =====\n"
            "AssertionError: Windows check failed"
        )
        replayed = (
            "Repair this existing PR's remote Windows CI failure in the SAME current session.\n\n"
            "===== Windows desktop build run 44258836858 (action_required) =====\n"
            "failed to get run log: log not found\n\n\n"
            "===== Python checks run 44258836775 (action_required) =====\n"
            "failed to get run log: log not found"
        )
        self.assertEqual(ci_run_conclusions(replayed), ["action_required", "action_required"])
        self.assertIn("OWNER_APPROVAL_REQUIRED", build_repair_prompt(replayed))
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context",
                    side_effect=[real_failure, replayed],
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(len(self.agent_calls), 1)
        self.assertIn("AssertionError: Windows check failed", str(self.agent_calls[0]["prompt"]))
        self.assertNotIn("44258836858", str(self.agent_calls[0]["prompt"]))
        self.assertEqual(self.commits, 1)
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.run_views, [])

    def test_non_checkpoint_failure_without_remote_logs_parks_instead_of_using_pr_body(self) -> None:
        """A normal PR body is not CI evidence; recover only from a real failure log.

        The old fallback handed the milestone description to the repair model and told
        it to "diagnose" text that names no failure. A non-checkpoint PR with no usable
        log must park for a fresh run instead of burning model calls.
        """
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "## Autonomous ECLIPSE milestone\n\n- Validation performed by the parent controller\n",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context", return_value=""
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(self.agent_calls, [])
        self.assertEqual(self.run_views, [])
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.commits, 0)
        self.assertFalse(any(call[:2] == ["pr", "create"] for call in self.gh_calls))

    def test_checkpoint_body_still_resumes_without_ci_logs(self) -> None:
        """A checkpoint body is the prior run's failure context and must remain resumable."""
        self.ci_conclusion = "failure"

        def checkpoint_gh(args, *, source_env, check=True):
            if list(args[:2]) == ["pr", "checks"]:
                self.gh_calls.append(list(args))
                green = self.commits >= 1
                return CompletedProcess(
                    list(args), 0 if green else 1, "", "" if green else "checks failed"
                )
            return self._fake_gh(args, source_env=source_env, check=check)

        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "Checkpoint: ECLIPSE autonomous run requires recovery",
            "isDraft": True,
            "headRefOid": "stale-head",
            "body": "Interrupted run checkpoint\nState: BLOCKED; failure: no free model route\n",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=checkpoint_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context", return_value=""
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(len(self.agent_calls), 1)
        self.assertIn("Interrupted run checkpoint", str(self.agent_calls[0]["prompt"]))
        self.assertEqual(self.commits, 1)
        self.assertEqual(len(self.merge_calls), 1)

    def test_unavailable_failure_log_parks_without_a_model_call(self) -> None:
        """A real `failure` run with no retrievable log must not start a repair."""
        unavailable = (
            "===== Windows desktop build run 43648092720 (failure) =====\n"
            "failed to get run log: log not found"
        )
        self.ci_conclusion = "failure"
        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "remote_ci_failure_context", return_value=unavailable
                ), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(self.agent_calls, [])
        self.assertEqual(self.run_views, [])
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.commits, 0)

    def test_protected_non_draft_pr_parks_before_ci_checks_or_a_model_call(self) -> None:
        """A non-draft PR touching protected automation paths must reach the owner first.

        This is the real PR #16 shape: a non-draft branch that changes the
        controller itself. Even if its runs are approval-gated or failing, the
        recovery model must not run and no CI log may be fetched.
        """
        (self.repo / "SECURITY.md").write_text("Security policy\n", encoding="utf-8")
        self._git("add", "-A", cwd=self.repo)
        self._git("commit", "-m", "touch protected path", cwd=self.repo)
        self._git("push", "origin", self.BRANCH, cwd=self.repo)
        self._git("fetch", "origin", cwd=self.repo)

        pr = {
            "headRefName": self.BRANCH,
            "url": self.PR_URL,
            "title": "ECLIPSE autonomous milestone",
            "isDraft": False,
            "headRefOid": "stale-head",
            "body": "",
        }
        env = {"GITHUB_TOKEN": "fake-token", "PATH": os.environ.get("PATH", "")}
        with mock.patch.object(eclipse_autonomous, "gh", side_effect=self._fake_gh), \
                mock.patch.object(
                    eclipse_autonomous, "run_agent_with_failover", side_effect=self._fake_agent
                ), \
                mock.patch.object(
                    eclipse_autonomous, "commit_and_push_worktree", side_effect=self._commit_wrapper
                ):
            result = eclipse_autonomous.resume_existing_pr(
                pr, env, "ECLIPSE autonomous test", time.monotonic() + 60
            )

        self.assertEqual(result, 0)
        self.assertEqual(self.agent_calls, [])
        self.assertEqual(self.run_views, [])
        self.assertEqual(self.merge_calls, [])
        self.assertEqual(self.commits, 0)
        self.assertEqual(self.gh_calls, [])
        self.assertFalse(any(call[:2] == ["pr", "checks"] for call in self.gh_calls))
        self.assertFalse(any(call[:2] == ["pr", "create"] for call in self.gh_calls))


if __name__ == "__main__":
    unittest.main()
