"""The three primary ECLIPSE workspaces."""

from .agent import AgentWorkspace
from .capability import CapabilityWorkspace
from .model_intelligence import ModelIntelligenceWorkspace

__all__ = [
    "AgentWorkspace",
    "CapabilityWorkspace",
    "ModelIntelligenceWorkspace",
]