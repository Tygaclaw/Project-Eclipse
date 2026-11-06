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


if __name__ == "__main__":
    unittest.main()
