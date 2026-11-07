"""Obsidian knowledge library with an AI Inbox and approval workflow.

Notes are ordinary Markdown files in an inspectable vault. ECLIPSE can create
proposals in ``06 - AI Inbox`` and, after approval, copy them into a trusted
folder. It never edits or deletes a trusted note silently; an approved note is
written as a new file and collisions get a numbered suffix.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Mapping

from eclipse.core.storage import Store

VAULT_FOLDERS = (
    "00 - Dashboard",
    "01 - System Knowledge",
    "02 - Projects",
    "03 - Verified Skills",
    "04 - Corrections",
    "05 - Research",
    "06 - AI Inbox",
)
TRUSTED_FOLDERS = (
    "01 - System Knowledge",
    "02 - Projects",
    "03 - Verified Skills",
    "04 - Corrections",
    "05 - Research",
)
INBOX = "06 - AI Inbox"
DASHBOARD = "00 - Dashboard"


class KnowledgeError(Exception):
    """A knowledge-vault operation was refused."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: str, limit: int = 70) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 -]+", "", value).strip().replace(" ", "-")
    cleaned = re.sub(r"-+", "-", cleaned)
    return (cleaned or "note")[:limit]


class KnowledgeBase:
    """A file-backed Obsidian vault plus a searchable note registry."""

    def __init__(self, vault_path: str | Path, store: Store) -> None:
        self.vault_path = Path(vault_path).expanduser().resolve()
        self.store = store

    # -- scaffolding -----------------------------------------------------

    def ensure_vault(self) -> dict[str, Any]:
        self.vault_path.mkdir(parents=True, exist_ok=True)
        for folder in VAULT_FOLDERS:
            (self.vault_path / folder).mkdir(parents=True, exist_ok=True)
        dashboard = self.vault_path / DASHBOARD / "ECLIPSE Dashboard.md"
        if not dashboard.exists():
            dashboard.write_text(self._dashboard_text(), encoding="utf-8")
        return {
            "vault_path": str(self.vault_path),
            "folders": list(VAULT_FOLDERS),
            "dashboard": str(dashboard),
            "created": True,
        }

    def _dashboard_text(self) -> str:
        counts = self.store.counts()
        lines = [
            "# ECLIPSE Knowledge Dashboard",
            "",
            f"_Updated {utc_now_iso()}_",
            "",
            "## Current state",
            "",
            f"- Registered models: {counts['models']}",
            f"- Conversations: {counts['conversations']}",
            f"- Capability tasks: {counts['tasks']}",
            f"- Verified corrections: {len(self.store.list_corrections(status='verified'))}",
            f"- Notes waiting in the AI Inbox: {len(self.store.list_knowledge_notes(status='inbox'))}",
            "",
            "## Folders",
            "",
        ]
        for folder in VAULT_FOLDERS:
            lines.append(f"- `{folder}`")
        lines.extend(
            [
                "",
                "## Rules",
                "",
                "- AI proposals land in `06 - AI Inbox` and stay candidates until approved.",
                "- Trusted notes are never silently rewritten or deleted.",
                "- Corrections require independent evidence before promotion.",
            ]
        )
        return "\n".join(lines) + "\n"

    def refresh_dashboard(self) -> Path:
        self.ensure_vault()
        dashboard = self.vault_path / DASHBOARD / "ECLIPSE Dashboard.md"
        dashboard.write_text(self._dashboard_text(), encoding="utf-8")
        return dashboard

    # -- path safety -----------------------------------------------------

    def _resolve_inside(self, relative: str) -> Path:
        candidate = (self.vault_path / relative).resolve()
        try:
            candidate.relative_to(self.vault_path)
        except ValueError as exc:
            raise KnowledgeError("The note path escapes the vault") from exc
        return candidate

    # -- proposals -------------------------------------------------------

    def propose_note(
        self,
        *,
        title: str,
        body: str,
        source: str = "",
        folder: str = INBOX,
    ) -> dict[str, Any]:
        if folder != INBOX:
            raise KnowledgeError("New AI proposals must go to the AI Inbox")
        if not title.strip():
            raise KnowledgeError("A note needs a title")
        self.ensure_vault()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        base_name = f"{stamp}-{_slug(title)}"
        filename = f"{base_name}.md"
        target = self._resolve_inside(f"{INBOX}/{filename}")
        # Two proposals with the same title within one second used to share a
        # filename, so the second silently overwrote the first candidate note.
        suffix = 2
        while target.exists():
            filename = f"{base_name}-{suffix}.md"
            target = self._resolve_inside(f"{INBOX}/{filename}")
            suffix += 1
        content = "\n".join(
            [
                f"# {title.strip()}",
                "",
                f"_Proposed {utc_now_iso()} · status: candidate_",
                "",
                body.strip(),
                "",
                "---",
                f"Source: {source.strip() or 'agent proposal'}",
                "",
                "This note is a candidate. It is not trusted knowledge until reviewed and approved.",
            ]
        )
        target.write_text(content, encoding="utf-8")
        note = self.store.add_knowledge_note(
            slug=_slug(title),
            title=title.strip(),
            folder=INBOX,
            path=str(target.relative_to(self.vault_path)),
            status="inbox",
            source=source.strip(),
        )
        return note

    def list_notes(self, *, status: str | None = None) -> list[dict[str, Any]]:
        notes = self.store.list_knowledge_notes(status=status)
        result = []
        for note in notes:
            path = self._resolve_inside(note["path"])
            result.append(
                {
                    **note,
                    "exists": path.is_file(),
                    "size_bytes": path.stat().st_size if path.is_file() else None,
                }
            )
        return result

    def read_note(self, note_id: str) -> dict[str, Any]:
        notes = {note["id"]: note for note in self.store.list_knowledge_notes()}
        note = notes.get(note_id)
        if note is None:
            raise KnowledgeError("Unknown note")
        path = self._resolve_inside(note["path"])
        if not path.is_file():
            raise KnowledgeError("The note file is missing from the vault")
        return {
            "note": note,
            "content": path.read_text(encoding="utf-8", errors="replace"),
            "path": str(path.relative_to(self.vault_path)),
        }

    def approve_note(
        self,
        note_id: str,
        *,
        target_folder: str,
        reviewer: str = "user",
        verification: str = "",
    ) -> dict[str, Any]:
        """Promote an inbox note into a trusted folder without overwriting."""

        if target_folder not in TRUSTED_FOLDERS:
            raise KnowledgeError("Approval target must be a trusted knowledge folder")
        notes = {note["id"]: note for note in self.store.list_knowledge_notes()}
        note = notes.get(note_id)
        if note is None:
            raise KnowledgeError("Unknown note")
        if note["status"] != "inbox":
            raise KnowledgeError("Only inbox notes can be approved")
        source_path = self._resolve_inside(note["path"])
        if not source_path.is_file():
            raise KnowledgeError("The inbox note file is missing")
        (self.vault_path / target_folder).mkdir(parents=True, exist_ok=True)
        base_name = source_path.stem
        destination = self.vault_path / target_folder / f"{base_name}.md"
        counter = 2
        while destination.exists():
            destination = self.vault_path / target_folder / f"{base_name}-{counter}.md"
            counter += 1
        original = source_path.read_text(encoding="utf-8", errors="replace")
        header = [
            f"> Approved by {reviewer} on {utc_now_iso()}.",
            f"> Verification: {verification.strip() or 'reviewed without a recorded automated check'}",
            "> Provenance: promoted from the ECLIPSE AI Inbox; the original proposal remains unchanged.",
            "",
        ]
        destination.write_text("\n".join(header) + original, encoding="utf-8")
        relative = str(destination.relative_to(self.vault_path))
        self.store.update_knowledge_note(
            note_id, status="approved", folder=target_folder, path=relative
        )
        self.refresh_dashboard()
        refreshed = self.store.list_knowledge_notes()
        updated = next((item for item in refreshed if item["id"] == note_id), None)
        return {
            "note": updated,
            "approved_path": relative,
            "original_inbox_path": note["path"],
        }

    def reject_note(self, note_id: str, *, reason: str = "") -> dict[str, Any]:
        notes = {note["id"]: note for note in self.store.list_knowledge_notes()}
        note = notes.get(note_id)
        if note is None:
            raise KnowledgeError("Unknown note")
        if note["status"] != "inbox":
            raise KnowledgeError("Only inbox notes can be rejected")
        path = self._resolve_inside(note["path"])
        if path.is_file():
            content = path.read_text(encoding="utf-8", errors="replace")
            path.write_text(
                content
                + f"\n\n---\nRejected {utc_now_iso()}: {reason.strip() or 'no reason recorded'}\n",
                encoding="utf-8",
            )
        self.store.update_knowledge_note(
            note_id, status="rejected", folder=note["folder"], path=note["path"]
        )
        return {"note_id": note_id, "status": "rejected"}

    # -- retrieval -------------------------------------------------------

    def search(self, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        terms = [term for term in re.findall(r"[A-Za-z0-9_]{2,}", (query or "").lower())]
        hits: list[tuple[int, dict[str, Any]]] = []
        if not self.vault_path.is_dir():
            return []
        for path in sorted(self.vault_path.rglob("*.md")):
            try:
                relative = str(path.relative_to(self.vault_path))
            except ValueError:
                continue
            if any(part.startswith(".") for part in Path(relative).parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")[:200_000]
            except OSError:
                continue
            lowered = text.lower()
            score = sum(lowered.count(term) for term in terms) if terms else 0
            if terms and score == 0:
                continue
            title = next(
                (line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")),
                path.stem,
            )
            excerpt_line = next(
                (line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")),
                "",
            )
            hits.append(
                (
                    score + (5 if INBOX.split(" - ")[-1].lower() in relative.lower() else 0),
                    {
                        "path": relative,
                        "title": title[:200],
                        "excerpt": excerpt_line[:300],
                        "folder": Path(relative).parts[0] if Path(relative).parts else "",
                        "provenance": "obsidian_vault",
                    },
                )
            )
        hits.sort(key=lambda item: (-item[0], item[1]["path"]))
        return [hit for _, hit in hits[: max(1, limit)]]

    def context_block(self, query: str, limit: int = 4) -> str:
        hits = [hit for hit in self.search(query, limit=limit) if INBOX not in hit["path"]]
        if not hits:
            return ""
        lines = ["Approved Obsidian knowledge relevant to this task:"]
        for hit in hits:
            lines.append(f"- {hit['title']} ({hit['path']}): {hit['excerpt']}")
        return "\n".join(lines)
