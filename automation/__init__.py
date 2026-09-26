"""
WorkFlowOS Automation Module (Phase 4)

Provides the workflow translation, validation, approval gating,
and execution abstractions.
"""

from automation.models import (
    AutomationStatus,
    AutomationAction,
    ExecutionActionResult,
    AutomationExecution,
    ExecuteWorkflowRequest,
)
from automation.executor import (
    ActionExecutor,
    NoOpExecutor,
)
from automation.engine import (
    AutomationEngine,
    automation_engine,
    SUPPORTED_ACTION_TYPES,
    AutomationEngineError,
    UnsupportedActionError,
    ApprovalRequiredError,
)
from automation.service import (
    AutomationService,
    automation_service,
)

__all__ = [
    "AutomationStatus",
    "AutomationAction",
    "ExecutionActionResult",
    "AutomationExecution",
    "ExecuteWorkflowRequest",
    "ActionExecutor",
    "NoOpExecutor",
    "AutomationEngine",
    "automation_engine",
    "AutomationService",
    "automation_service",
    "SUPPORTED_ACTION_TYPES",
    "AutomationEngineError",
    "UnsupportedActionError",
    "ApprovalRequiredError",
]
