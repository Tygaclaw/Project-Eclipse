"""Scoped research and project-context retrieval with provenance.

Retrieval is bounded and task-scoped: the indexer skips binaries, virtual
environments, model weights and version-control internals, and every result
records the file and line it came from. Installed package versions are read
from real metadata, not recalled from memory.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.metadata
import os
from pathlib import Path
import re
from typing import Any, Iterable

_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "models",
    ".idea",
    ".vscode",
    "docs/source_material",
}
_TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".sql",
    ".sh",
    ".ps1",
    ".c",
    ".h",
    ".cpp",
    ".cs",
    ".java",
    ".rs",
    ".go",
    ".qml",
    ".ui",
}
MAX_FILE_BYTES = 256 * 1024
MAX_INDEX_FILES = 4000
MAX_RESULTS = 20


class RetrievalError(Exception):
    """A scoped retrieval request could not be completed."""


@dataclass(frozen=True, slots=True)
class ContextHit:
    path: str
    line: int
    snippet: str
    score: int
    provenance: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "line": self.line,
            "snippet": self.snippet,
            "score": self.score,
            "provenance": self.provenance,
        }


def _iter_text_files(root: Path, limit: int = MAX_INDEX_FILES) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    seen = 0
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name.lower() not in _SKIP_DIRS and not name.startswith(".")
        )
        for filename in sorted(filenames):
            path = Path(directory) / filename
            if path.is_symlink():
                continue
            if path.suffix.lower() not in _TEXT_SUFFIXES:
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield path
            seen += 1
            if seen >= limit:
                return


def list_workspace_files(root: str | os.PathLike[str], limit: int = 2000) -> list[str]:
    base = Path(root).expanduser().resolve()
    files = []
    for path in _iter_text_files(base, limit):
        try:
            files.append(str(path.relative_to(base)))
        except ValueError:
            files.append(path.name)
    return files


def _terms(query: str) -> list[str]:
    return [
        term
        for term in re.findall(r"[A-Za-z0-9_.-]{2,}", query.lower())
        if term not in {"the", "and", "for", "with", "from", "that", "this", "into"}
    ]


class ProjectIndex:
    """A bounded keyword index over one approved workspace."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.exists():
            raise RetrievalError("The project workspace does not exist")
        self._files: list[Path] = []
        self._content: dict[Path, str] = {}
        self._build()

    def _build(self) -> None:
        for path in _iter_text_files(self.root):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            self._files.append(path)
            self._content[path] = text

    @property
    def file_count(self) -> int:
        return len(self._files)

    def file_names(self) -> list[str]:
        names = []
        for path in self._files:
            try:
                names.append(str(path.relative_to(self.root)))
            except ValueError:
                names.append(path.name)
        return names

    def search(self, query: str, *, limit: int = 8) -> list[ContextHit]:
        terms = _terms(query)
        if not terms:
            return []
        scored: list[tuple[int, Path, int, str]] = []
        for path, text in self._content.items():
            lowered = text.lower()
            name_score = sum(3 for term in terms if term in path.name.lower())
            term_score = sum(lowered.count(term) for term in terms)
            if term_score == 0 and name_score == 0:
                continue
            best_line = 1
            best_snippet = ""
            best_local = 0
            for number, line in enumerate(text.splitlines(), start=1):
                local = sum(1 for term in terms if term in line.lower())
                if local > best_local:
                    best_local = local
                    best_line = number
                    best_snippet = line.strip()[:400]
            if not best_snippet:
                best_line = 1
                first = text.strip().splitlines()
                best_snippet = (first[0][:400] if first else "")
            scored.append((name_score + term_score, path, best_line, best_snippet))
        scored.sort(key=lambda item: (-item[0], str(item[1])))
        results = []
        for score, path, line, snippet in scored[:limit]:
            try:
                relative = str(path.relative_to(self.root))
            except ValueError:
                relative = path.name
            results.append(
                ContextHit(
                    path=relative,
                    line=line,
                    snippet=snippet,
                    score=score,
                    provenance="workspace_index",
                )
            )
        return results

    def read(self, relative_path: str, *, max_bytes: int = 64 * 1024) -> dict[str, Any]:
        candidate = (self.root / relative_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise RetrievalError("The requested file is outside the workspace") from exc
        if not candidate.is_file():
            raise RetrievalError("The requested file does not exist")
        data = candidate.read_bytes()[:max_bytes]
        text = data.decode("utf-8", errors="replace")
        return {
            "path": relative_path,
            "bytes": len(data),
            "truncated": candidate.stat().st_size > max_bytes,
            "content": text,
            "provenance": "workspace_file",
        }


def installed_package_version(name: str) -> dict[str, Any]:
    try:
        version = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return {"package": name, "version": None, "evidence": "unknown", "source": "importlib.metadata"}
    return {
        "package": name,
        "version": version,
        "evidence": "observed",
        "source": "importlib.metadata",
    }


def detect_project_stack(root: str | os.PathLike[str]) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    facts: dict[str, Any] = {"root_name": base.name, "signals": []}
    if (base / "pyproject.toml").is_file():
        facts["signals"].append("python_pyproject")
        facts["python"] = installed_package_version("eclipse-core")
    if (base / "package.json").is_file():
        facts["signals"].append("node_package")
        try:
            import json

            package = json.loads((base / "package.json").read_text(encoding="utf-8"))
            facts["node_name"] = package.get("name")
            facts["node_version"] = package.get("version")
        except (OSError, ValueError):
            facts["node_name"] = None
    if (base / "requirements-desktop.txt").is_file():
        facts["signals"].append("desktop_requirements")
    if (base / "tests").is_dir():
        facts["signals"].append("python_tests")
    facts["evidence"] = "observed"
    return facts
