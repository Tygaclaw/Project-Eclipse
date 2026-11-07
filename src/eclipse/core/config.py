"""Application paths and small persistent settings for the shared ECLIPSE core.

All mutable state lives under one application root so a user can inspect,
back up or remove it predictably. ``ECLIPSE_HOME`` overrides the location,
which keeps tests and the desktop packaging story reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import threading
from typing import Any, Mapping

APP_NAME = "ECLIPSE"
DEFAULT_THEME = "dark"
VALID_THEMES = ("dark", "light")


def default_root() -> Path:
    override = os.environ.get("ECLIPSE_HOME")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "eclipse"


@dataclass(frozen=True, slots=True)
class AppPaths:
    """One resolved ECLIPSE application directory tree."""

    root: Path

    @classmethod
    def discover(cls, root: str | os.PathLike[str] | None = None) -> "AppPaths":
        if root is None:
            return cls(default_root())
        return cls(Path(root).expanduser())

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def models_dir(self) -> Path:
        return self.root / "models"

    @property
    def prepared_dir(self) -> Path:
        return self.root / "prepared"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def knowledge_dir(self) -> Path:
        return self.root / "knowledge" / "ECLIPSE-Knowledge"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "eclipse.sqlite3"

    @property
    def settings_path(self) -> Path:
        return self.config_dir / "settings.json"

    def ensure(self) -> "AppPaths":
        for directory in (
            self.root,
            self.config_dir,
            self.data_dir,
            self.models_dir,
            self.prepared_dir,
            self.logs_dir,
            self.knowledge_dir.parent,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return self

    def to_dict(self) -> dict[str, str]:
        return {
            "root": str(self.root),
            "data": str(self.data_dir),
            "models": str(self.models_dir),
            "prepared": str(self.prepared_dir),
            "logs": str(self.logs_dir),
            "knowledge": str(self.knowledge_dir),
            "database": str(self.database_path),
        }


_DEFAULTS: dict[str, Any] = {
    "theme": DEFAULT_THEME,
    "active_model_id": None,
    "memory_enabled": True,
    "knowledge_enabled": True,
    "project_root": None,
    "last_conversation_id": None,
    "runtime_endpoint": None,
    "runtime_backend": "llamacpp_server",
    "max_context_tokens": 8192,
    "agent_max_steps": 6,
    "command_timeout_seconds": 120,
    "approve_writes": True,
    "approve_commands": True,
    "onboarding_complete": False,
}


class Settings:
    """JSON-backed settings with thread-safe reads and atomic writes."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()
        self._values: dict[str, Any] = dict(_DEFAULTS)
        self._load()

    def _load(self) -> None:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            return
        if isinstance(loaded, dict):
            for key, value in loaded.items():
                if isinstance(key, str):
                    self._values[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if key in self._values:
                return self._values[key]
        return _DEFAULTS.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if not isinstance(key, str) or not key:
            raise ValueError("Settings keys must be non-empty strings")
        with self._lock:
            self._values[key] = value
            self._write()

    def update(self, values: Mapping[str, Any]) -> None:
        with self._lock:
            for key, value in values.items():
                if not isinstance(key, str) or not key:
                    raise ValueError("Settings keys must be non-empty strings")
                self._values[key] = value
            self._write()

    def _write(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self._values, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temporary, self._path)

    def as_dict(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._values)
