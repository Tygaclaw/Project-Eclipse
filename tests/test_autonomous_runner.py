from __future__ import annotations

import unittest

from scripts.eclipse_autonomous import (
    MAX_CALLS_PER_MODEL,
    ROUTES,
    Route,
    RunResult,
    classify_failure,
    extract_session_id,
    safe_child_environment,
    safety_scan,
    run_opencode,
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


class RankedPoolConsistencyTests(unittest.TestCase):
    def test_controller_route_order_matches_ranked_provider_pool_document(self) -> None:
        import re
        from pathlib import Path

        doc = (Path(__file__).resolve().parents[1] / "docs" / "FREE_MODEL_PROVIDER_POOL.md").read_text(encoding="utf-8")
        ranked = re.findall(r"^\|\s*\*{0,2}(\d+)\*{0,2}\s*\|[^|]*\|[^|]*\|\s*`([^`]+)`", doc, re.M)
        ranked.sort(key=lambda row: int(row[0]))
        self.assertEqual(len(ranked), 12)
        self.assertEqual([row[1] for row in ranked], [route.open_code_id for route in ROUTES])


if __name__ == "__main__":
    unittest.main()
