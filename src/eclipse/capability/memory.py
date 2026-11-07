"""Verified correction memory.

A model's explanation is never trusted automatically. A lesson starts as a
``candidate`` and only becomes ``verified`` when independent evidence and a
regression reference are supplied. Trusted lessons are retrieved with their
scope and provenance, not treated as universal rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from eclipse.core.storage import Store


class MemoryError(Exception):
    """A correction-memory operation was refused."""


@dataclass(frozen=True, slots=True)
class Lesson:
    id: str
    title: str
    status: str
    issue: str
    root_cause: str
    fix: str
    scope: str
    evidence: str
    regression: str
    created_at: str
    promoted_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "issue": self.issue,
            "root_cause": self.root_cause,
            "fix": self.fix,
            "scope": self.scope,
            "evidence": self.evidence,
            "regression": self.regression,
            "created_at": self.created_at,
            "promoted_at": self.promoted_at,
        }


class CorrectionMemory:
    def __init__(self, store: Store) -> None:
        self.store = store

    def propose(
        self,
        *,
        title: str,
        issue: str,
        root_cause: str,
        fix: str,
        scope: str,
        evidence: str = "",
        regression: str = "",
    ) -> dict[str, Any]:
        """Record a candidate lesson, regardless of who authored it."""

        if not title.strip():
            raise MemoryError("A correction needs a title")
        if not (issue.strip() and root_cause.strip() and fix.strip()):
            raise MemoryError("A correction needs the observed issue, root cause and fix")
        return self.store.add_correction(
            title=title.strip(),
            issue=issue.strip(),
            root_cause=root_cause.strip(),
            fix=fix.strip(),
            scope=scope.strip() or "unscoped",
            status="candidate",
            evidence=evidence.strip(),
            regression=regression.strip(),
        )

    def promote(self, correction_id: str, *, evidence: str, regression: str) -> dict[str, Any]:
        """Promote a candidate only with independent evidence and a regression."""

        correction = self.store.get_correction(correction_id)
        if correction is None:
            raise MemoryError("Unknown correction")
        if correction["status"] == "verified":
            return correction
        evidence = (evidence or "").strip()
        regression = (regression or "").strip()
        if len(evidence) < 20:
            raise MemoryError(
                "Promotion needs substantive evidence such as a passing test command and its output"
            )
        if not regression:
            raise MemoryError(
                "Promotion needs a regression reference (a test name or a repeatable check)"
            )
        return self.store.promote_correction(
            correction_id, evidence=evidence, regression=regression
        )

    def lessons(self, *, status: str | None = None) -> list[Lesson]:
        return [_lesson(row) for row in self.store.list_corrections(status=status)]

    def trusted(self, limit: int = 8) -> list[Lesson]:
        verified = self.lessons(status="verified")
        return verified[: max(0, limit)]

    def search(self, query: str, *, include_candidates: bool = True, limit: int = 8) -> list[Lesson]:
        terms = [term for term in re.findall(r"[A-Za-z0-9_]{3,}", (query or "").lower())]
        scored: list[tuple[int, Lesson]] = []
        for lesson in self.lessons():
            if not include_candidates and lesson.status != "verified":
                continue
            haystack = " ".join(
                (lesson.title, lesson.issue, lesson.root_cause, lesson.fix, lesson.scope)
            ).lower()
            score = sum(haystack.count(term) for term in terms) if terms else 0
            if score or not terms:
                if lesson.status == "verified":
                    score += 2
                scored.append((score, lesson))
        scored.sort(key=lambda item: (-item[0], item[1].created_at))
        return [lesson for _, lesson in scored[:limit]]

    def context_block(self, query: str, limit: int = 4) -> str:
        lessons = [lesson for lesson in self.search(query, include_candidates=False, limit=limit)]
        if not lessons:
            return ""
        lines = [
            "Verified corrections relevant to this task (external evidence, scoped rules):"
        ]
        for lesson in lessons:
            lines.append(f"- {lesson.title} [{lesson.scope}]: {lesson.fix} (evidence: {lesson.evidence[:180]})")
        return "\n".join(lines)


def _lesson(row: Mapping[str, Any]) -> Lesson:
    return Lesson(
        id=str(row["id"]),
        title=str(row["title"]),
        status=str(row["status"]),
        issue=str(row["issue"]),
        root_cause=str(row["root_cause"]),
        fix=str(row["fix"]),
        scope=str(row["scope"]),
        evidence=str(row.get("evidence") or ""),
        regression=str(row.get("regression") or ""),
        created_at=str(row["created_at"]),
        promoted_at=row.get("promoted_at"),
    )
