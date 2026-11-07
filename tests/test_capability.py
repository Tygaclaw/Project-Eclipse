from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from eclipse.capability import (
    CapabilityEngine,
    CorrectionMemory,
    KnowledgeBase,
    KnowledgeError,
    MemoryError,
    ProjectIndex,
    ToolRegistry,
    VerificationEngine,
    build_plan,
    classify_task,
)
from eclipse.capability.engine import RuntimeUnavailable
from eclipse.capability.knowledge import INBOX
from eclipse.capability.planner import mark_objective
from eclipse.core.config import AppPaths, Settings
from eclipse.core.security import Action, ApprovalDenied, PermissionBroker, PathEscapeError
from eclipse.core.storage import Store
from eclipse.runtime.client import ChatError, StreamChunk, ToolCall


class ScriptedRuntime:
    """Deterministic runtime used to test orchestration, not model quality."""

    def __init__(self, turns: list[dict]) -> None:
        self.turns = list(turns)
        self.settings = {"command_timeout_seconds": 60, "agent_max_steps": 6}
        self.status = SimpleNamespace(model_name="scripted-model")
        self.calls: list[list[str]] = []

    def require_ready(self) -> None:
        if getattr(self, "not_ready", False):
            raise ChatError("No model is loaded")

    def stream_chat(self, messages, *, tools=None, temperature=None, max_tokens=None, cancel=None, emit_deltas=False):
        self.calls.append([message.role for message in messages])
        turn = self.turns.pop(0) if self.turns else {"text": "Done."}
        if turn.get("raise"):
            raise ChatError(turn["raise"])
        for piece in turn.get("chunks") or ([turn["text"]] if turn.get("text") else []):
            yield StreamChunk(text=piece)
        tool = turn.get("tool")
        if tool:
            yield StreamChunk(
                tool_calls=(
                    ToolCall(
                        id=tool.get("id", "call_1"),
                        name=tool["name"],
                        arguments=json.dumps(tool.get("arguments") or {}),
                    ),
                ),
                finish_reason="tool_calls",
                done=True,
            )
        else:
            yield StreamChunk(finish_reason="stop", done=True)


def approver(*_args) -> bool:
    return True


class WatchdogTests(unittest.TestCase):
    def test_simple_question_routes_to_fast_mode(self) -> None:
        assessment = classify_task("What is the capital of France?")
        self.assertEqual(assessment.mode, "fast")
        self.assertFalse(assessment.requires_verification)
        self.assertFalse(assessment.allows_writes)

    def test_large_feature_routes_to_enhanced_and_requires_verification(self) -> None:
        assessment = classify_task(
            "Implement a multi-file authentication feature, refactor the database migration, "
            "run tests and verify the security model."
        )
        self.assertIn(assessment.mode, {"enhanced"})
        self.assertTrue(assessment.requires_verification)
        self.assertGreaterEqual(assessment.max_steps, 10)

    def test_high_risk_keyword_forces_verification(self) -> None:
        assessment = classify_task("Remove production credentials and deploy", mode="fast")
        self.assertEqual(assessment.risk, "high")
        self.assertTrue(assessment.requires_verification)

    def test_explicit_mode_is_respected(self) -> None:
        self.assertEqual(classify_task("Anything", mode="enhanced").mode, "enhanced")


class PlannerTests(unittest.TestCase):
    def test_plan_has_acceptance_criteria_and_verification(self) -> None:
        assessment = classify_task("Build a new feature in app.py and tests")
        plan = build_plan("Build a new feature in app.py and tests", assessment, workspace_files=["src/app.py"], project_root="/tmp/x")
        ids = [objective.id for objective in plan.objectives]
        self.assertIn("inspect", ids)
        self.assertIn("implement", ids)
        self.assertIn("verify", ids)
        self.assertTrue(all(objective.acceptance_criteria for objective in plan.objectives))
        self.assertEqual(plan.likely_files, ["src/app.py"])

    def test_drift_detects_done_without_evidence(self) -> None:
        assessment = classify_task("Fix the parser")
        plan = build_plan("Fix the parser", assessment)
        mark_objective(plan, "inspect", "done")
        self.assertTrue(plan.drift_signals())
        mark_objective(plan, "inspect", "done", ["read_file app.py"])
        self.assertEqual(plan.progress()["total"], 3)
        self.assertFalse([signal for signal in plan.drift_signals() if signal.startswith("inspect")])

    def test_plan_round_trip(self) -> None:
        assessment = classify_task("Fix the parser")
        plan = build_plan("Fix the parser", assessment)
        restored = type(plan).from_dict(plan.to_dict())
        self.assertEqual(restored.goal, plan.goal)
        self.assertEqual(len(restored.objectives), len(plan.objectives))


class ToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
        self.store = Store(self.root / "db.sqlite3")
        self.addCleanup(self.store.close)
        self.broker = PermissionBroker([self.root], approver=approver)
        self.tools = ToolRegistry(self.broker, self.root, store=self.store, verifier=VerificationEngine())

    def test_read_and_search_are_workspace_scoped(self) -> None:
        read = self.tools.call("read_file", {"path": "app.py"})
        self.assertTrue(read.ok)
        self.assertIn("return 42", read.output)
        search = self.tools.call("search_text", {"query": "answer"})
        self.assertTrue(search.ok)
        self.assertIn("app.py", search.output)

    def test_path_escape_is_refused(self) -> None:
        result = self.tools.call("read_file", {"path": "../outside.txt"})
        self.assertFalse(result.ok)
        self.assertIn("outside", result.error.lower())

    def test_write_requires_approval_and_is_atomic(self) -> None:
        result = self.tools.call("write_file", {"path": "new.py", "content": "print('hi')\n"})
        self.assertTrue(result.ok)
        self.assertEqual((self.root / "new.py").read_text(encoding="utf-8"), "print('hi')\n")
        denied = ToolRegistry(
            PermissionBroker([self.root], approver=lambda *_: False), self.root
        )
        refused = denied.call("write_file", {"path": "no.py", "content": "x"})
        self.assertFalse(refused.ok)
        self.assertFalse((self.root / "no.py").exists())

    def test_command_runs_real_process_without_shell(self) -> None:
        result = self.tools.call("run_command", {"command": ["python", "-c", "print(6 * 7)"]})
        self.assertTrue(result.ok)
        self.assertIn("42", result.output)
        refused = self.tools.call("run_command", {"command": ["bash", "-c", "echo hi"]})
        self.assertFalse(refused.ok)

    def test_verification_runs_compile_and_tests(self) -> None:
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_ok.py").write_text(
            "from app import answer\n\nimport unittest\n\nclass T(unittest.TestCase):\n"
            "    def test_answer(self):\n        self.assertEqual(answer(), 42)\n",
            encoding="utf-8",
        )
        result = self.tools.call("verify", {})
        self.assertTrue(result.ok, result.output)
        self.assertEqual(len(result.data["checks"]), 2)

    def test_verification_reports_a_real_failure(self) -> None:
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_fail.py").write_text(
            "import unittest\n\nclass T(unittest.TestCase):\n    def test_fail(self):\n        self.assertEqual(1, 2)\n",
            encoding="utf-8",
        )
        result = self.tools.call("verify", {})
        self.assertFalse(result.ok)
        self.assertIn("FAILED", result.output)

    def test_project_index_returns_provenance(self) -> None:
        index = ProjectIndex(self.root)
        hits = index.search("answer")
        self.assertTrue(hits)
        self.assertEqual(hits[0].path, "app.py")
        self.assertEqual(hits[0].provenance, "workspace_index")


class MemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "db.sqlite3")
        self.addCleanup(self.store.close)
        self.memory = CorrectionMemory(self.store)

    def test_candidate_cannot_be_promoted_without_evidence(self) -> None:
        correction = self.memory.propose(
            title="Parser crash", issue="IndexError", root_cause="empty header", fix="guard length", scope="gguf"
        )
        with self.assertRaises(MemoryError):
            self.memory.promote(correction["id"], evidence="", regression="test_gguf")
        with self.assertRaises(MemoryError):
            self.memory.promote(correction["id"], evidence="tests passed on my machine", regression="")
        promoted = self.memory.promote(
            correction["id"],
            evidence="python -m unittest tests.test_gguf -> OK (17 tests)",
            regression="tests/test_gguf.py::test_empty_header",
        )
        self.assertEqual(promoted["status"], "verified")
        self.assertIn("Parser crash", self.memory.context_block("parser"))

    def test_candidates_are_not_injected_as_trusted_lessons(self) -> None:
        self.memory.propose(
            title="Candidate", issue="i", root_cause="r", fix="f", scope="s"
        )
        self.assertEqual(self.memory.context_block("candidate"), "")


class KnowledgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "db.sqlite3")
        self.addCleanup(self.store.close)
        self.vault = self.root / "ECLIPSE-Knowledge"
        self.knowledge = KnowledgeBase(self.vault, self.store)
        self.knowledge.ensure_vault()

    def test_vault_scaffold_and_dashboard(self) -> None:
        self.assertTrue((self.vault / "00 - Dashboard" / "ECLIPSE Dashboard.md").is_file())
        for folder in ("01 - System Knowledge", "02 - Projects", "03 - Verified Skills", "04 - Corrections", "05 - Research", "06 - AI Inbox"):
            self.assertTrue((self.vault / folder).is_dir())

    def test_proposal_stays_in_inbox_until_approved(self) -> None:
        note = self.knowledge.propose_note(title="Boundary test", body="Use argv lists.", source="test")
        self.assertEqual(note["folder"], INBOX)
        self.assertEqual(note["status"], "inbox")
        self.assertTrue((self.vault / note["path"]).is_file())
        approved = self.knowledge.approve_note(
            note["id"],
            target_folder="03 - Verified Skills",
            verification="python -m unittest tests.test_capability -> OK",
        )
        self.assertTrue((self.vault / approved["approved_path"]).is_file())
        self.assertIn("Approved by user", (self.vault / approved["approved_path"]).read_text(encoding="utf-8"))
        hits = self.knowledge.search("Boundary test")
        self.assertTrue(any("03 - Verified Skills" in hit["path"] for hit in hits))

    def test_approval_never_overwrites_a_trusted_note(self) -> None:
        note = self.knowledge.propose_note(title="Duplicate", body="First.", source="test")
        source_name = Path(note["path"]).stem
        target = self.vault / "04 - Corrections" / f"{source_name}.md"
        target.write_text("Existing trusted note", encoding="utf-8")
        approved = self.knowledge.approve_note(note["id"], target_folder="04 - Corrections")
        self.assertNotEqual(Path(approved["approved_path"]).name, target.name)
        self.assertEqual(target.read_text(encoding="utf-8"), "Existing trusted note")

    def test_trusted_folders_only_and_inbox_only_approval(self) -> None:
        note = self.knowledge.propose_note(title="X", body="Y")
        with self.assertRaises(KnowledgeError):
            self.knowledge.approve_note(note["id"], target_folder="06 - AI Inbox")
        self.knowledge.reject_note(note["id"], reason="not useful")
        with self.assertRaises(KnowledgeError):
            self.knowledge.approve_note(note["id"], target_folder="04 - Corrections")


class EngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "project"
        self.workspace.mkdir()
        (self.workspace / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (self.workspace / "tests").mkdir()
        (self.workspace / "tests" / "test_app.py").write_text(
            "from app import add\n\nimport unittest\n\nclass T(unittest.TestCase):\n"
            "    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n",
            encoding="utf-8",
        )
        self.paths = AppPaths.discover(self.root / "home").ensure()
        self.store = Store(self.paths.database_path)
        self.addCleanup(self.store.close)
        self.knowledge = KnowledgeBase(self.paths.knowledge_dir, self.store)
        self.knowledge.ensure_vault()

    def engine(self, runtime: ScriptedRuntime) -> CapabilityEngine:
        return CapabilityEngine(
            self.store,
            runtime,
            self.paths,
            knowledge=self.knowledge,
            workspace_root=self.workspace,
        )

    def test_end_to_end_task_completes_only_with_verification(self) -> None:
        runtime = ScriptedRuntime(
            [
                {"tool": {"name": "read_file", "arguments": {"path": "app.py"}}},
                {
                    "tool": {
                        "name": "write_file",
                        "arguments": {"path": "app.py", "content": "def add(a, b):\n    return a + b + 0\n"},
                    }
                },
                {"text": "Updated add and verified the tests."},
            ]
        )
        engine = self.engine(runtime)
        task = engine.create_task("Fix and verify the add function", mode="balanced")
        run = engine.run_task(task["id"], approver=approver)
        self.assertEqual(run.status, "completed", run.to_dict())
        self.assertEqual(run.stopped_reason, "complete")
        self.assertTrue(run.verification)
        self.assertTrue(all(report["ok"] for report in run.verification))
        stored = self.store.get_task(task["id"])
        self.assertEqual(stored["status"], "completed")
        self.assertTrue(any(entry["kind"] == "tool" for entry in stored["evidence"]))

    def test_verification_failure_is_not_reported_as_success(self) -> None:
        runtime = ScriptedRuntime(
            [
                {"tool": {"name": "read_file", "arguments": {"path": "app.py"}}},
                {
                    "tool": {
                        "name": "write_file",
                        "arguments": {"path": "tests/test_app.py", "content": "this is not python"},
                    }
                },
                {"text": "Done."},
                {"text": "I could not repair it."},
            ]
        )
        engine = self.engine(runtime)
        task = engine.create_task("Break the test file", mode="balanced")
        run = engine.run_task(task["id"], approver=approver)
        self.assertIn(run.status, {"needs_attention", "failed"})
        self.assertTrue(any(not report["ok"] for report in run.verification))

    def test_loop_detection_stops_repeated_tool_calls(self) -> None:
        repeated = {"tool": {"name": "read_file", "arguments": {"path": "app.py"}}}
        runtime = ScriptedRuntime([dict(repeated) for _ in range(8)])
        engine = self.engine(runtime)
        task = engine.create_task("Read the same file forever", mode="balanced")
        run = engine.run_task(task["id"], approver=approver)
        self.assertEqual(run.stopped_reason, "loop_detected")
        self.assertIn(run.status, {"needs_attention", "failed"})

    def test_missing_runtime_is_reported_not_faked(self) -> None:
        runtime = ScriptedRuntime([])
        runtime.not_ready = True
        engine = self.engine(runtime)
        task = engine.create_task("Do something", mode="balanced")
        with self.assertRaises(RuntimeUnavailable):
            engine.run_task(task["id"], approver=approver)
        self.assertEqual(self.store.get_task(task["id"])["status"], "needs_attention")

    def test_denied_write_does_not_complete_the_task(self) -> None:
        runtime = ScriptedRuntime(
            [
                {"tool": {"name": "read_file", "arguments": {"path": "app.py"}}},
                {
                    "tool": {
                        "name": "write_file",
                        "arguments": {"path": "app.py", "content": "modified"},
                    }
                },
                {"text": "Done."},
                {"text": "Still denied."},
            ]
        )
        engine = self.engine(runtime)
        task = engine.create_task("Modify the app", mode="balanced")
        run = engine.run_task(task["id"], approver=lambda *_: False)
        self.assertNotEqual(run.status, "completed")


if __name__ == "__main__":
    unittest.main()
