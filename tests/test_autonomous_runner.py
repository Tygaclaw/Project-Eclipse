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


if __name__ == "__main__":
    unittest.main()
