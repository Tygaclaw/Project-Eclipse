"""Shared application context for the three desktop workspaces.

One store, one runtime, one knowledge vault and one agent service. The desktop
never builds a second copy of a Core service.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from eclipse.agent import AgentService
from eclipse.capability import CapabilityEngine, CorrectionMemory, KnowledgeBase
from eclipse.core.config import AppPaths, Settings
from eclipse.core.events import EventBus
from eclipse.core.storage import Store
from eclipse.runtime import RuntimeManager


class AppContext:
    """Owns the Core services for one desktop application instance."""

    def __init__(self, root: str | os.PathLike[str] | None = None) -> None:
        self.paths = AppPaths.discover(root).ensure()
        self.settings = Settings(self.paths.settings_path)
        self.store = Store(self.paths.database_path)
        self.events = EventBus()
        self.runtime = RuntimeManager(self.store, self.settings, self.paths, events=self.events)
        self.knowledge = KnowledgeBase(self.paths.knowledge_dir, self.store)
        self.knowledge.ensure_vault()
        self.memory = CorrectionMemory(self.store)
        workspace = self.settings.get("project_root")
        if isinstance(workspace, str) and not Path(workspace).is_dir():
            workspace = None
        self.workspace: str | None = str(workspace) if workspace else None
        self.capability = CapabilityEngine(
            self.store,
            self.runtime,
            self.paths,
            events=self.events,
            memory=self.memory,
            knowledge=self.knowledge,
            workspace_root=self.workspace,
        )
        self.agent = AgentService(
            self.store,
            self.runtime,
            self.paths,
            events=self.events,
            knowledge=self.knowledge,
            memory=self.memory,
            workspace_root=self.workspace,
        )
        self._closed = False

    def set_workspace(self, path: str | os.PathLike[str] | None) -> None:
        resolved = str(Path(path).expanduser().resolve()) if path else None
        self.workspace = resolved
        self.capability.set_workspace(resolved)
        self.agent.set_workspace(resolved)
        self.settings.set("project_root", resolved)

    def active_model(self) -> dict[str, Any] | None:
        status = self.runtime.status
        if not status.model_id:
            return None
        return self.store.get_model(status.model_id)

    def selected_model(self) -> dict[str, Any] | None:
        model_id = self.settings.get("active_model_id")
        if isinstance(model_id, str):
            model = self.store.get_model(model_id)
            if model is not None:
                return model
        models = self.store.list_models()
        return models[0] if models else None

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.runtime.shutdown()
        except Exception:  # noqa: BLE001 - shutdown must not raise
            pass
        try:
            self.store.close()
        except Exception:  # noqa: BLE001
            pass
