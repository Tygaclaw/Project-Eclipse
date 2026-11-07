"""SQLite persistence for the shared ECLIPSE Core.

One connection per process guarded by a re-entrant lock keeps the desktop,
CLI and agent on the same store. JSON columns are decoded into ordinary
dictionaries so callers never depend on SQLite row types.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterable, Mapping
import uuid


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    file_size_bytes INTEGER,
    parameters INTEGER,
    architecture TEXT,
    sha256 TEXT,
    atlas_json TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS variants (
    id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    status TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    model_id TEXT,
    name TEXT NOT NULL,
    intent TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    last_known_good INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    model_id TEXT,
    profile_id TEXT,
    status TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    model_id TEXT,
    system_prompt TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS messages_conversation
    ON messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    message_id TEXT,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mime TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    project_root TEXT NOT NULL DEFAULT '',
    plan_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS corrections (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    issue TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    fix TEXT NOT NULL,
    scope TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence TEXT NOT NULL DEFAULT '',
    regression TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    promoted_at TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_notes (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    folder TEXT NOT NULL,
    path TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_JSON_COLUMNS = {
    "atlas_json": "atlas",
    "manifest_json": "manifest",
    "payload_json": "payload",
    "metrics_json": "metrics",
    "metadata_json": "metadata",
    "plan_json": "plan",
    "evidence_json": "evidence",
}


def _decode_row(row: sqlite3.Row, table: str) -> dict[str, Any]:
    record = dict(row)
    for column, key in _JSON_COLUMNS.items():
        if column in record:
            raw = record.pop(column)
            record[key] = _loads(raw, {})
    if "archived" in record:
        record["archived"] = bool(record["archived"])
    if "last_known_good" in record:
        record["last_known_good"] = bool(record["last_known_good"])
    record["_table"] = table
    return record


def _loads(raw: Any, fallback: Any) -> Any:
    if raw is None:
        return fallback
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


class Store:
    """Thread-safe SQLite repository for every persistent ECLIPSE record."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(self.path), check_same_thread=False, timeout=15.0
        )
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.executescript(_SCHEMA)
            self._connection.commit()

    # -- lifecycle -------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            try:
                self._connection.close()
            except sqlite3.Error:
                pass

    def _execute(
        self, sql: str, params: Iterable[Any] = ()
    ) -> sqlite3.Cursor:
        with self._lock:
            cursor = self._connection.execute(sql, tuple(params))
            self._connection.commit()
            return cursor

    def _query(
        self, sql: str, params: Iterable[Any] = ()
    ) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._connection.execute(sql, tuple(params)))

    # -- models ----------------------------------------------------------

    def add_model(
        self,
        *,
        name: str,
        source_path: str,
        source_kind: str,
        atlas: Mapping[str, Any],
        file_size_bytes: int | None = None,
        parameters: int | None = None,
        architecture: str | None = None,
        sha256: str | None = None,
        notes: str = "",
        model_id: str | None = None,
    ) -> dict[str, Any]:
        identifier = model_id or new_id("model")
        created = utc_now_iso()
        self._execute(
            """
            INSERT INTO models (id, name, source_path, source_kind, file_size_bytes,
                parameters, architecture, sha256, atlas_json, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identifier,
                name,
                source_path,
                source_kind,
                file_size_bytes,
                parameters,
                architecture,
                sha256,
                _dumps(atlas),
                notes,
                created,
            ),
        )
        model = self.get_model(identifier)
        assert model is not None
        return model

    def get_model(self, model_id: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM models WHERE id = ?", (model_id,))
        return _decode_row(rows[0], "models") if rows else None

    def list_models(self) -> list[dict[str, Any]]:
        rows = self._query("SELECT * FROM models ORDER BY created_at DESC")
        return [_decode_row(row, "models") for row in rows]

    def delete_model(self, model_id: str) -> None:
        with self._lock:
            self._connection.execute("DELETE FROM variants WHERE model_id = ?", (model_id,))
            self._connection.execute("DELETE FROM profiles WHERE model_id = ?", (model_id,))
            self._connection.execute("DELETE FROM models WHERE id = ?", (model_id,))
            self._connection.commit()

    def update_model_notes(self, model_id: str, notes: str) -> None:
        self._execute("UPDATE models SET notes = ? WHERE id = ?", (notes, model_id))

    # -- variants --------------------------------------------------------

    def add_variant(
        self,
        *,
        model_id: str,
        name: str,
        kind: str,
        path: str,
        status: str,
        manifest: Mapping[str, Any],
    ) -> dict[str, Any]:
        identifier = new_id("variant")
        self._execute(
            """
            INSERT INTO variants (id, model_id, name, kind, path, status, manifest_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (identifier, model_id, name, kind, path, status, _dumps(manifest), utc_now_iso()),
        )
        variant = self.get_variant(identifier)
        assert variant is not None
        return variant

    def get_variant(self, variant_id: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM variants WHERE id = ?", (variant_id,))
        return _decode_row(rows[0], "variants") if rows else None

    def list_variants(self, model_id: str | None = None) -> list[dict[str, Any]]:
        if model_id is None:
            rows = self._query("SELECT * FROM variants ORDER BY created_at DESC")
        else:
            rows = self._query(
                "SELECT * FROM variants WHERE model_id = ? ORDER BY created_at DESC",
                (model_id,),
            )
        return [_decode_row(row, "variants") for row in rows]

    def delete_variant(self, variant_id: str) -> None:
        self._execute("DELETE FROM variants WHERE id = ?", (variant_id,))

    # -- profiles --------------------------------------------------------

    def add_profile(
        self,
        *,
        name: str,
        intent: str,
        payload: Mapping[str, Any],
        model_id: str | None = None,
        last_known_good: bool = False,
    ) -> dict[str, Any]:
        identifier = new_id("profile")
        self._execute(
            """
            INSERT INTO profiles (id, model_id, name, intent, payload_json,
                last_known_good, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identifier,
                model_id,
                name,
                intent,
                _dumps(payload),
                1 if last_known_good else 0,
                utc_now_iso(),
            ),
        )
        profile = self.get_profile(identifier)
        assert profile is not None
        return profile

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM profiles WHERE id = ?", (profile_id,))
        return _decode_row(rows[0], "profiles") if rows else None

    def list_profiles(self, model_id: str | None = None) -> list[dict[str, Any]]:
        if model_id is None:
            rows = self._query(
                "SELECT * FROM profiles ORDER BY last_known_good DESC, created_at DESC"
            )
        else:
            rows = self._query(
                "SELECT * FROM profiles WHERE model_id = ? ORDER BY last_known_good DESC, created_at DESC",
                (model_id,),
            )
        return [_decode_row(row, "profiles") for row in rows]

    def mark_last_known_good(self, profile: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if profile.get("model_id"):
                self._connection.execute(
                    "UPDATE profiles SET last_known_good = 0 WHERE model_id = ?",
                    (profile["model_id"],),
                )
            else:
                self._connection.execute("UPDATE profiles SET last_known_good = 0")
            self._connection.execute(
                "UPDATE profiles SET last_known_good = 1 WHERE id = ?",
                (profile["id"],),
            )
            self._connection.commit()
        refreshed = self.get_profile(profile["id"])
        assert refreshed is not None
        return refreshed

    # -- runs / telemetry ------------------------------------------------

    def record_run(
        self,
        *,
        kind: str,
        metrics: Mapping[str, Any],
        status: str,
        model_id: str | None = None,
        profile_id: str | None = None,
        started_at: str | None = None,
        ended_at: str | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        identifier = new_id("run")
        self._execute(
            """
            INSERT INTO runs (id, kind, model_id, profile_id, status, metrics_json,
                started_at, ended_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identifier,
                kind,
                model_id,
                profile_id,
                status,
                _dumps(metrics),
                started_at or utc_now_iso(),
                ended_at,
                notes,
            ),
        )
        run = self.get_run(identifier)
        assert run is not None
        return run

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM runs WHERE id = ?", (run_id,))
        return _decode_row(rows[0], "runs") if rows else None

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (max(0, int(limit)),)
        )
        return [_decode_row(row, "runs") for row in rows]

    # -- conversations ---------------------------------------------------

    def create_conversation(
        self,
        *,
        title: str = "New conversation",
        model_id: str | None = None,
        system_prompt: str = "",
    ) -> dict[str, Any]:
        identifier = new_id("conv")
        now = utc_now_iso()
        self._execute(
            """
            INSERT INTO conversations (id, title, model_id, system_prompt, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (identifier, title, model_id, system_prompt, now, now),
        )
        conversation = self.get_conversation(identifier)
        assert conversation is not None
        return conversation

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
        return _decode_row(rows[0], "conversations") if rows else None

    def list_conversations(self, query: str | None = None) -> list[dict[str, Any]]:
        if query:
            pattern = f"%{query}%"
            rows = self._query(
                """
                SELECT DISTINCT c.* FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.archived = 0 AND (c.title LIKE ? OR m.content LIKE ?)
                ORDER BY c.updated_at DESC
                """,
                (pattern, pattern),
            )
        else:
            rows = self._query(
                "SELECT * FROM conversations WHERE archived = 0 ORDER BY updated_at DESC"
            )
        return [_decode_row(row, "conversations") for row in rows]

    def update_conversation(self, conversation_id: str, **fields: Any) -> None:
        allowed = {"title", "model_id", "system_prompt", "archived"}
        assignments = []
        values: list[Any] = []
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(f"Unsupported conversation field: {key}")
            assignments.append(f"{key} = ?")
            values.append(int(value) if key == "archived" else value)
        if not assignments:
            return
        assignments.append("updated_at = ?")
        values.append(utc_now_iso())
        values.append(conversation_id)
        self._execute(
            f"UPDATE conversations SET {', '.join(assignments)} WHERE id = ?", values
        )

    def touch_conversation(self, conversation_id: str) -> None:
        self._execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (utc_now_iso(), conversation_id),
        )

    def delete_conversation(self, conversation_id: str) -> None:
        with self._lock:
            self._connection.execute(
                "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,)
            )
            self._connection.execute(
                "DELETE FROM attachments WHERE conversation_id = ?", (conversation_id,)
            )
            self._connection.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )
            self._connection.commit()

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        identifier = new_id("msg")
        self._execute(
            """
            INSERT INTO messages (id, conversation_id, role, content, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                identifier,
                conversation_id,
                role,
                content,
                _dumps(dict(metadata or {})),
                utc_now_iso(),
            ),
        )
        self.touch_conversation(conversation_id)
        message = self.get_message(identifier)
        assert message is not None
        return message

    def get_message(self, message_id: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM messages WHERE id = ?", (message_id,))
        return _decode_row(rows[0], "messages") if rows else None

    def list_messages(self, conversation_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        if limit is None:
            rows = self._query(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC, rowid ASC",
                (conversation_id,),
            )
            return [_decode_row(row, "messages") for row in rows]
        rows = self._query(
            """
            SELECT * FROM (
                SELECT * FROM messages WHERE conversation_id = ?
                ORDER BY created_at DESC, rowid DESC LIMIT ?
            ) ORDER BY created_at ASC, rowid ASC
            """,
            (conversation_id, max(0, int(limit))),
        )
        return [_decode_row(row, "messages") for row in rows]

    # -- attachments -----------------------------------------------------

    def add_attachment(
        self,
        *,
        conversation_id: str,
        name: str,
        path: str,
        size_bytes: int,
        mime: str = "",
        message_id: str | None = None,
    ) -> dict[str, Any]:
        identifier = new_id("att")
        self._execute(
            """
            INSERT INTO attachments (id, conversation_id, message_id, name, path, size_bytes, mime, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identifier,
                conversation_id,
                message_id,
                name,
                path,
                size_bytes,
                mime,
                utc_now_iso(),
            ),
        )
        rows = self._query("SELECT * FROM attachments WHERE id = ?", (identifier,))
        return _decode_row(rows[0], "attachments")

    def list_attachments(self, conversation_id: str) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT * FROM attachments WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
        return [_decode_row(row, "attachments") for row in rows]

    def claim_attachments(self, conversation_id: str, message_id: str) -> int:
        """Bind not-yet-sent attachments to the user message that carried them."""

        with self._lock:
            cursor = self._connection.execute(
                "UPDATE attachments SET message_id = ? "
                "WHERE conversation_id = ? AND message_id IS NULL",
                (message_id, conversation_id),
            )
            self._connection.commit()
        return int(cursor.rowcount or 0)

    # -- tasks -----------------------------------------------------------

    def create_task(
        self,
        *,
        goal: str,
        mode: str,
        plan: Mapping[str, Any],
        status: str = "planned",
        project_root: str = "",
    ) -> dict[str, Any]:
        identifier = new_id("task")
        now = utc_now_iso()
        self._execute(
            """
            INSERT INTO tasks (id, goal, mode, status, project_root, plan_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (identifier, goal, mode, status, project_root, _dumps(plan), now, now),
        )
        task = self.get_task(identifier)
        assert task is not None
        return task

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return _decode_row(rows[0], "tasks") if rows else None

    def list_tasks(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (max(0, int(limit)),)
        )
        return [_decode_row(row, "tasks") for row in rows]

    def update_task(
        self,
        task_id: str,
        *,
        status: str | None = None,
        evidence: list[Mapping[str, Any]] | None = None,
        plan: Mapping[str, Any] | None = None,
    ) -> None:
        assignments = ["updated_at = ?"]
        values: list[Any] = [utc_now_iso()]
        if status is not None:
            assignments.append("status = ?")
            values.append(status)
        if evidence is not None:
            assignments.append("evidence_json = ?")
            values.append(_dumps(list(evidence)))
        if plan is not None:
            assignments.append("plan_json = ?")
            values.append(_dumps(plan))
        values.append(task_id)
        self._execute(
            f"UPDATE tasks SET {', '.join(assignments)} WHERE id = ?", values
        )

    # -- corrections -----------------------------------------------------

    def add_correction(
        self,
        *,
        title: str,
        issue: str,
        root_cause: str,
        fix: str,
        scope: str,
        status: str = "candidate",
        evidence: str = "",
        regression: str = "",
    ) -> dict[str, Any]:
        identifier = new_id("corr")
        self._execute(
            """
            INSERT INTO corrections (id, title, issue, root_cause, fix, scope, status,
                evidence, regression, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identifier,
                title,
                issue,
                root_cause,
                fix,
                scope,
                status,
                evidence,
                regression,
                utc_now_iso(),
            ),
        )
        correction = self.get_correction(identifier)
        assert correction is not None
        return correction

    def get_correction(self, correction_id: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM corrections WHERE id = ?", (correction_id,))
        return _decode_row(rows[0], "corrections") if rows else None

    def list_corrections(self, status: str | None = None) -> list[dict[str, Any]]:
        if status is None:
            rows = self._query("SELECT * FROM corrections ORDER BY created_at DESC")
        else:
            rows = self._query(
                "SELECT * FROM corrections WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        return [_decode_row(row, "corrections") for row in rows]

    def promote_correction(
        self, correction_id: str, *, evidence: str, regression: str
    ) -> dict[str, Any]:
        self._execute(
            """
            UPDATE corrections SET status = 'verified', evidence = ?, regression = ?,
                promoted_at = ? WHERE id = ?
            """,
            (evidence, regression, utc_now_iso(), correction_id),
        )
        correction = self.get_correction(correction_id)
        assert correction is not None
        return correction

    def delete_correction(self, correction_id: str) -> None:
        self._execute("DELETE FROM corrections WHERE id = ?", (correction_id,))

    # -- knowledge notes -------------------------------------------------

    def add_knowledge_note(
        self,
        *,
        slug: str,
        title: str,
        folder: str,
        path: str,
        status: str,
        source: str = "",
    ) -> dict[str, Any]:
        identifier = new_id("note")
        now = utc_now_iso()
        self._execute(
            """
            INSERT INTO knowledge_notes (id, slug, title, folder, path, status, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (identifier, slug, title, folder, path, status, source, now, now),
        )
        rows = self._query("SELECT * FROM knowledge_notes WHERE id = ?", (identifier,))
        return _decode_row(rows[0], "knowledge_notes")

    def list_knowledge_notes(self, status: str | None = None) -> list[dict[str, Any]]:
        if status is None:
            rows = self._query("SELECT * FROM knowledge_notes ORDER BY created_at DESC")
        else:
            rows = self._query(
                "SELECT * FROM knowledge_notes WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        return [_decode_row(row, "knowledge_notes") for row in rows]

    def update_knowledge_note(self, note_id: str, *, status: str, folder: str, path: str) -> None:
        self._execute(
            "UPDATE knowledge_notes SET status = ?, folder = ?, path = ?, updated_at = ? WHERE id = ?",
            (status, folder, path, utc_now_iso(), note_id),
        )

    def search_corrections(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        pattern = f"%{query}%"
        rows = self._query(
            "SELECT * FROM corrections WHERE title LIKE ? OR issue LIKE ? OR root_cause LIKE ? "
            "OR fix LIKE ? OR scope LIKE ? ORDER BY created_at DESC LIMIT ?",
            (pattern, pattern, pattern, pattern, pattern, max(0, int(limit))),
        )
        return [_decode_row(row, "corrections") for row in rows]

    # -- key/value settings ----------------------------------------------

    def set_setting(self, key: str, value: Any) -> None:
        self._execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, _dumps(value)),
        )

    def get_setting(self, key: str, default: Any = None) -> Any:
        rows = self._query("SELECT value FROM settings WHERE key = ?", (key,))
        if not rows:
            return default
        return _loads(rows[0]["value"], default)

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for table in (
            "models",
            "variants",
            "conversations",
            "messages",
            "tasks",
            "corrections",
            "knowledge_notes",
            "runs",
        ):
            rows = self._query(f"SELECT COUNT(*) AS n FROM {table}")
            result[table] = int(rows[0]["n"]) if rows else 0
        return result
