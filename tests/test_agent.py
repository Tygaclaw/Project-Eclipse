from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from eclipse.agent import AgentService
from eclipse.core.config import AppPaths, Settings
from eclipse.core.storage import Store
from eclipse.runtime.client import CancellationToken, ChatCancelled, ChatError, StreamChunk, ToolCall
from tests.test_capability import ScriptedRuntime, approver


class AgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "project"
        self.workspace.mkdir()
        (self.workspace / "notes.txt").write_text("Project fact: the sky is blue.\n", encoding="utf-8")
        self.paths = AppPaths.discover(self.root / "home").ensure()
        self.store = Store(self.paths.database_path)
        self.addCleanup(self.store.close)
        self.settings = Settings(self.paths.settings_path)

    def service(self, runtime: ScriptedRuntime) -> AgentService:
        runtime.settings = {**self.settings.as_dict(), "agent_max_steps": 4}
        return AgentService(self.store, runtime, self.paths, workspace_root=self.workspace)

    def test_conversation_and_message_persistence(self) -> None:
        runtime = ScriptedRuntime([{"chunks": ["Hello", " there", "."]}])
        agent = self.service(runtime)
        conversation = agent.new_conversation()
        result = agent.send(conversation["id"], "Hi, who are you?")
        self.assertEqual(result["message"]["content"], "Hello there.")
        self.assertEqual(result["steps"], 1)
        stored = agent.conversation(conversation["id"])
        self.assertEqual([message["role"] for message in stored["messages"]], ["user", "assistant"])
        self.assertEqual(stored["title"], "Hi, who are you?")

    def test_streaming_events_are_emitted(self) -> None:
        deltas: list[str] = []
        runtime = ScriptedRuntime([{"chunks": ["A", "B"]}])
        agent = self.service(runtime)
        agent.events.subscribe("agent.delta", lambda event: deltas.append(event.payload.get("text", "")))
        conversation = agent.new_conversation()
        agent.send(conversation["id"], "Stream please")
        self.assertEqual("".join(deltas), "AB")

    def test_conversation_search_and_delete(self) -> None:
        agent = self.service(ScriptedRuntime([{"text": "alpha"}]))
        first = agent.new_conversation()
        agent.send(first["id"], "alpha topic")
        second = agent.new_conversation()
        agent.send(second["id"], "beta topic")
        self.assertEqual(len(agent.conversations("beta")), 1)
        agent.delete_conversation(second["id"])
        self.assertEqual(len(agent.conversations()), 1)

    def test_attachment_text_is_included_once(self) -> None:
        runtime = ScriptedRuntime([{"text": "ok"}, {"text": "again"}])
        agent = self.service(runtime)
        conversation = agent.new_conversation()
        agent.attach_file(conversation["id"], str(self.workspace / "notes.txt"))
        agent.send(conversation["id"], "Summarise the attachment")
        agent.send(conversation["id"], "Follow-up question")
        first_call = runtime.calls[0]
        second_call = runtime.calls[1]
        self.assertIn("user", first_call)
        second_user_contents = [
            message["content"]
            for message in self.store.list_messages(conversation["id"])
            if message["role"] == "user"
        ][-1]
        self.assertNotIn("the sky is blue", second_user_contents)
        self.assertGreaterEqual(len(second_call), 3)

    def test_tool_calls_are_executed_and_reported(self) -> None:
        runtime = ScriptedRuntime(
            [
                {"tool": {"name": "read_file", "arguments": {"path": "notes.txt"}}},
                {"text": "The note says the sky is blue."},
            ]
        )
        agent = self.service(runtime)
        conversation = agent.new_conversation()
        result = agent.send(conversation["id"], "Read the note")
        self.assertEqual(len(result["tool_events"]), 1)
        self.assertTrue(result["tool_events"][0]["result"]["ok"])
        message = self.store.list_messages(conversation["id"])[-1]
        self.assertEqual(message["content"], "The note says the sky is blue.")
        self.assertEqual(len(message["metadata"]["tool_events"]), 1)

    def test_stop_is_not_recorded_as_a_runtime_failure(self) -> None:
        class StoppingRuntime(ScriptedRuntime):
            def stream_chat(self, messages, **kwargs):
                raise ChatCancelled("stopped by user")
                yield  # pragma: no cover - keeps this method a generator

        agent = self.service(StoppingRuntime([]))
        conversation = agent.new_conversation()
        with self.assertRaises(ChatCancelled):
            agent.send(conversation["id"], "Stop please")
        messages = self.store.list_messages(conversation["id"])
        self.assertEqual(messages[-1]["role"], "assistant")
        self.assertIn("stopped at your request", messages[-1]["content"])
        self.assertTrue(messages[-1]["metadata"].get("cancelled"))
        self.assertNotIn("runtime is not available", messages[-1]["content"])

    def test_runtime_failure_is_recorded_honestly(self) -> None:
        runtime = ScriptedRuntime([{"raise": "endpoint unreachable"}])
        agent = self.service(runtime)
        conversation = agent.new_conversation()
        with self.assertRaises(ChatError):
            agent.send(conversation["id"], "Hello")
        messages = self.store.list_messages(conversation["id"])
        self.assertEqual(messages[-1]["role"], "assistant")
        self.assertIn("could not complete", messages[-1]["content"])
        self.assertTrue(messages[-1]["metadata"].get("error"))

    def test_rename_and_model_switch(self) -> None:
        agent = self.service(ScriptedRuntime([]))
        conversation = agent.new_conversation()
        agent.rename(conversation["id"], "Renamed")
        agent.set_model(conversation["id"], "model_123")
        stored = agent.conversation(conversation["id"])
        self.assertEqual(stored["title"], "Renamed")
        self.assertEqual(stored["model_id"], "model_123")

    def test_no_workspace_still_allows_conversation(self) -> None:
        runtime = ScriptedRuntime([{"text": "No tools needed."}])
        agent = AgentService(self.store, runtime, self.paths, workspace_root=None)
        conversation = agent.new_conversation()
        result = agent.send(conversation["id"], "Just chat")
        self.assertEqual(result["message"]["content"], "No tools needed.")


if __name__ == "__main__":
    unittest.main()
