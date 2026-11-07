"""Capability Amplification & Knowledge System core."""

from .engine import CapabilityEngine, CapabilityError, RuntimeUnavailable, TaskRun
from .execution import LoopResult, ToolEvent, run_tool_loop
from .knowledge import INBOX, TRUSTED_FOLDERS, VAULT_FOLDERS, KnowledgeBase, KnowledgeError
from .memory import CorrectionMemory, Lesson, MemoryError
from .planner import Objective, Plan, build_plan, mark_objective
from .research import ContextHit, ProjectIndex, detect_project_stack, installed_package_version, list_workspace_files
from .tools import TOOL_SPECS, ToolRegistry, ToolResult, ToolSpec
from .verification import VerificationEngine, VerificationError, default_checks
from .watchdog import MODES, TaskAssessment, classify_task

__all__ = [
    "CapabilityEngine",
    "CapabilityError",
    "ContextHit",
    "CorrectionMemory",
    "INBOX",
    "KnowledgeBase",
    "KnowledgeError",
    "Lesson",
    "LoopResult",
    "MODES",
    "MemoryError",
    "Objective",
    "Plan",
    "ProjectIndex",
    "RuntimeUnavailable",
    "TOOL_SPECS",
    "TRUSTED_FOLDERS",
    "TaskAssessment",
    "TaskRun",
    "ToolEvent",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "VAULT_FOLDERS",
    "VerificationEngine",
    "VerificationError",
    "build_plan",
    "classify_task",
    "default_checks",
    "detect_project_stack",
    "installed_package_version",
    "list_workspace_files",
    "mark_objective",
    "run_tool_loop",
]
