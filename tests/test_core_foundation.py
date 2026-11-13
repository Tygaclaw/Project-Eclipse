"""Shared state, security and persistence tests."""

from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from eclipse.core.config import AppPaths, Settings
from eclipse.core.events import EventBus
from eclipse.core.security import (
    Action,
    ApprovalDenied,
    ApprovalPending,
    PathEscapeError,
    PermissionBroker,
    redact,
    resolve_within,
    split_command,
)
from eclipse.core.storage import Store


class ConfigTests(unittest.TestCase):
    def test_paths_are_created_and_settings_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = AppPaths.discover(Path(temp) / "home").ensure()
            self.assertTrue(paths.database_path.parent.is_dir())
            settings = Settings(paths.settings_path)
            self.assertEqual(settings.get("theme"), "dark")
            settings.set("theme", "light")
            settings.update({"active_model_id": "model_1"})
            reloaded = Settings(paths.settings_path)
            self.assertEqual(reloaded.get("theme"), "light")
            self.assertEqual(reloaded.get("active_model_id"), "model_1")

    def test_invalid_settings_file_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "settings.json"
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(Settings(path).get("theme"), "dark")


class SecurityTests(unittest.TestCase):
    def test_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            root.mkdir()
            (Path(temp) / "outside.txt").write_text("secret", encoding="utf-8")
            with self.assertRaises(PathEscapeError):
                resolve_within(root, "../outside.txt")
            inside = resolve_within(root, "src/app.py")
            self.assertEqual(inside, (root / "src/app.py").resolve(strict=False))

    def test_symlink_escape_is_rejected(self) -> None:
        if os.name == "nt":
            self.skipTest("Symlink creation needs privileges on Windows")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            root.mkdir()
            outside = Path(temp) / "outside"
            outside.mkdir()
            (root / "link").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(PathEscapeError):
                resolve_within(root, "link/file.txt")

    def test_reads_are_allowed_and_writes_need_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            decisions: list[tuple[str, str, str]] = []

            def approver(action: str, target: str, detail: str) -> bool:
                decisions.append((action, target, detail))
                return True

            broker = PermissionBroker([temp], approver=approver)
            broker.require(Action.READ, "file.txt")
            broker.require(Action.WRITE, "file.txt")
            self.assertEqual(decisions, [("write", "file.txt", "")])

    def test_denied_write_raises_and_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            broker = PermissionBroker([temp], approver=lambda *_: False)
            with self.assertRaises(ApprovalDenied):
                broker.require(Action.WRITE, "file.txt")
            self.assertEqual(broker.records()[-1].decision, "deny")

    def test_missing_approver_denies_instead_of_allowing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            broker = PermissionBroker([temp])
            with self.assertRaises(ApprovalPending):
                broker.require(Action.COMMAND, "python -m unittest")
            broker_denied = PermissionBroker([temp], allow_commands=False)
            with self.assertRaises(ApprovalDenied):
                broker_denied.require(Action.COMMAND, "python -m unittest")

    def test_previously_approved_target_does_not_reask(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            calls: list[str] = []

            def approver(action: str, target: str, detail: str) -> bool:
                calls.append(target)
                return True

            broker = PermissionBroker([temp], approver=approver)
            broker.require(Action.WRITE, "same.txt")
            broker.require(Action.WRITE, "same.txt")
            self.assertEqual(calls, ["same.txt"])

    def test_command_validation_rejects_shell_strings_and_operators(self) -> None:
        with self.assertRaises(Exception):
            split_command("python -m unittest && rm -rf /")
        with self.assertRaises(Exception):
            split_command("rm -rf /")
        self.assertEqual(split_command("python -m unittest discover -s tests")[:3], ["python", "-m", "unittest"])

    def test_credentials_are_redacted(self) -> None:
        text = "key sk-abcdefghijklmnop and github_pat_abcdefghijklmnopqrst"
        redacted = redact(text)
        self.assertNotIn("sk-abcdefghijklmnop", redacted)
        self.assertNotIn("github_pat_abcdefghijklmnopqrst", redacted)


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "eclipse.sqlite3")
        # Cleanups run LIFO: close SQLite before deleting its directory.
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.store.close)

    def test_model_registry_round_trip(self) -> None:
        model = self.store.add_model(
            name="Example",
            source_path="/models/example.gguf",
            source_kind="gguf",
            atlas={"format": "eclipse_model_atlas"},
            parameters=1234,
        )
        self.assertEqual(self.store.get_model(model["id"])["atlas"], {"format": "eclipse_model_atlas"})
        variant = self.store.add_variant(
            model_id=model["id"],
            name="prepared",
            kind="index",
            path="/prepared/x",
            status="verified",
            manifest={"format": "eclipse_prepared_model"},
        )
        self.assertEqual(len(self.store.list_variants(model["id"])), 1)
        self.store.delete_model(model["id"])
        self.assertIsNone(self.store.get_variant(variant["id"]))

    def test_conversations_messages_and_search(self) -> None:
        conversation = self.store.create_conversation(title="Testing storage")
        self.store.add_message(conversation["id"], "user", "How do I verify this?")
        self.store.add_message(conversation["id"], "assistant", "Run the tests.")
        self.assertEqual(len(self.store.list_messages(conversation["id"])), 2)
        self.assertEqual(len(self.store.list_conversations("verify")), 1)
        self.assertEqual(len(self.store.list_conversations("missing")), 0)
        self.assertEqual(self.store.list_messages(conversation["id"], limit=1)[0]["role"], "assistant")

    def test_legacy_messages_gain_ordinal_during_migration(self) -> None:
        legacy_path = Path(self.temp.name) / "legacy.sqlite3"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.execute(
                """
                CREATE TABLE messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO messages
                    (id, conversation_id, role, content, metadata_json, created_at)
                VALUES ('msg_old', 'conv_legacy', 'user', 'old', '{}', '2026-01-01T00:00:00+00:00')
                """
            )
            connection.commit()
        finally:
            connection.close()
        legacy = Store(legacy_path)
        self.addCleanup(legacy.close)
        old = legacy.list_messages("conv_legacy")
        self.assertEqual([message["content"] for message in old], ["old"])
        self.assertEqual(old[0]["ordinal"], 1)
        legacy.add_message("conv_legacy", "assistant", "new")
        messages = legacy.list_messages("conv_legacy")
        self.assertEqual([message["content"] for message in messages], ["old", "new"])
        self.assertEqual([message["ordinal"] for message in messages], [1, 2])

    def test_profiles_last_known_good_excludes_previous(self) -> None:
        first = self.store.add_profile(name="A", intent="balanced", payload={}, last_known_good=True)
        second = self.store.add_profile(name="B", intent="fast", payload={})
        self.store.mark_last_known_good(second)
        self.assertFalse(self.store.get_profile(first["id"])["last_known_good"])
        self.assertTrue(self.store.get_profile(second["id"])["last_known_good"])

    def test_tasks_corrections_and_notes(self) -> None:
        task = self.store.create_task(goal="Do work", mode="balanced", plan={"objectives": []})
        self.store.update_task(task["id"], status="completed", evidence=[{"kind": "note", "message": "ok"}])
        self.assertEqual(self.store.get_task(task["id"])["status"], "completed")

        correction = self.store.add_correction(
            title="t", issue="i", root_cause="r", fix="f", scope="s"
        )
        promoted = self.store.promote_correction(
            correction["id"], evidence="tests pass", regression="tests/test_x.py"
        )
        self.assertEqual(promoted["status"], "verified")

        note = self.store.add_knowledge_note(
            slug="s", title="T", folder="06 - AI Inbox", path="06 - AI Inbox/t.md", status="inbox"
        )
        self.store.update_knowledge_note(note["id"], status="approved", folder="05 - Research", path="05 - Research/t.md")
        self.assertEqual(self.store.list_knowledge_notes(status="approved")[0]["id"], note["id"])


class EventBusTests(unittest.TestCase):
    def test_events_reach_named_and_catch_all_subscribers(self) -> None:
        bus = EventBus()
        named: list[str] = []
        all_names: list[str] = []
        bus.subscribe("task.tool", lambda event: named.append(event.name))
        bus.subscribe(None, lambda event: all_names.append(event.name))
        bus.emit("task.tool", name="read_file")
        bus.emit("other")
        self.assertEqual(named, ["task.tool"])
        self.assertEqual(all_names, ["task.tool", "other"])
        self.assertEqual(len(bus.history(name="task.tool")), 1)

    def test_failing_listener_does_not_break_emit(self) -> None:
        bus = EventBus()
        seen: list[str] = []
        bus.subscribe("x", lambda event: (_ for _ in ()).throw(RuntimeError("boom")))
        bus.subscribe("x", lambda event: seen.append("ok"))
        bus.emit("x")
        self.assertEqual(seen, ["ok"])

    def test_unsubscribe(self) -> None:
        bus = EventBus()
        seen: list[str] = []
        unsubscribe = bus.subscribe("x", lambda event: seen.append("hit"))
        unsubscribe()
        bus.emit("x")
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
