import logging
from typing import Optional, List
from pydantic import BaseModel, Field
from automation.models import AutomationExecution, AutomationStatus
from integrations.credentials import sanitize_log_message

logger = logging.getLogger(__name__)


class ExecutionLearningOutcome(BaseModel):
    """
    Interpreted execution signals extracted from an AutomationExecution.
    Used by LearningService to update the workflow's learning state.
    """
    workflow_id: str = Field(..., description="Canonical target workflow ID")
    execution_id: str = Field(..., description="Execution ID")
    status: str = Field(..., description="Lifecycle status: completed, paused, failed, cancelled")
    is_completed: bool = Field(default=False, description="Whether execution finished successfully")
    is_failed: bool = Field(default=False, description="Whether execution failed terminally")
    requires_intervention: bool = Field(default=False, description="Whether human intervention was requested")
    is_recovery: bool = Field(default=False, description="Whether execution was resumed or recovered")
    failed_step: Optional[str] = Field(default=None, description="Step action type that failed")
    failure_reason: Optional[str] = Field(default=None, description="Sanitized failure reason")


def interpret_execution_outcome(
    execution: AutomationExecution,
    target_workflow_id: Optional[str] = None,
) -> Optional[ExecutionLearningOutcome]:
    """
    Interprets an AutomationExecution record into learning signals.
    Does NOT alter existing execution semantics or records.
    Returns None if execution is PENDING or RUNNING (not yet a learning signal milestone).
    """
    if execution.status in (AutomationStatus.PENDING, AutomationStatus.RUNNING):
        return None

    # Resolve workflow ID: target override > execution.workflow_id > slugified workflow_name
    resolved_id = target_workflow_id or execution.workflow_id
    if not resolved_id:
        if execution.workflow_name:
            import re
            slug = re.sub(r"[^a-zA-Z0-9_]+", "_", execution.workflow_name.strip().lower())
            resolved_id = f"wf_{slug}"
        else:
            resolved_id = "wf_unknown"

    is_completed = (execution.status == AutomationStatus.COMPLETED)
    is_failed = (execution.status == AutomationStatus.FAILED)
    requires_intervention = (
        execution.requires_human_intervention
        or execution.status == AutomationStatus.PAUSED
    )
    is_recovery = (
        (execution.recovery_attempts is not None and execution.recovery_attempts > 0)
        or (execution.resume_count is not None and execution.resume_count > 0)
    )

    failed_step = execution.failed_action or execution.current_action
    if not failed_step and execution.step_results:
        for sr in execution.step_results:
            if sr.status == "failed":
                failed_step = sr.action_type or sr.step_id
                break

    raw_reason = execution.failure_reason or execution.error
    sanitized_reason = sanitize_log_message(raw_reason) if raw_reason else None

    return ExecutionLearningOutcome(
        workflow_id=resolved_id,
        execution_id=execution.execution_id,
        status=str(execution.status.value if hasattr(execution.status, "value") else execution.status),
        is_completed=is_completed,
        is_failed=is_failed,
        requires_intervention=requires_intervention,
        is_recovery=is_recovery,
        failed_step=failed_step,
        failure_reason=sanitized_reason,
    )
