from enum import Enum
from typing import List, Optional, Dict, Any, Set
from pydantic import BaseModel, Field

from ai.models import WorkflowProposal, WorkflowAction


class AutomationStatus(str, Enum):
    """
    Status of an automation execution run.

    Phase 4.6 adds PAUSED and CANCELLED to support human-in-the-loop execution.
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_FOR_HUMAN = "waiting_for_human"  # legacy alias kept for backward compat
    PAUSED = "paused"       # Phase 4.6: execution paused pending human intervention
    CANCELLED = "cancelled" # Phase 4.6: execution cancelled by user


# Phase 4.6: Valid state transitions for the execution state machine.
# Keys are the CURRENT state; values are the set of ALLOWED target states.
VALID_TRANSITIONS: Dict[AutomationStatus, Set[AutomationStatus]] = {
    AutomationStatus.PENDING:    {AutomationStatus.RUNNING, AutomationStatus.CANCELLED},
    AutomationStatus.RUNNING:    {
        AutomationStatus.COMPLETED,
        AutomationStatus.PAUSED,
        AutomationStatus.FAILED,
        AutomationStatus.CANCELLED,
    },
    AutomationStatus.PAUSED:     {AutomationStatus.RUNNING, AutomationStatus.CANCELLED},
    AutomationStatus.COMPLETED:  set(),   # terminal — no further transitions allowed
    AutomationStatus.FAILED:     set(),   # terminal
    AutomationStatus.CANCELLED:  set(),   # terminal
    AutomationStatus.WAITING_FOR_HUMAN: {AutomationStatus.RUNNING, AutomationStatus.CANCELLED},
}


def is_valid_transition(from_status: AutomationStatus, to_status: AutomationStatus) -> bool:
    """Return True iff the transition from_status → to_status is permitted by the state machine."""
    return to_status in VALID_TRANSITIONS.get(from_status, set())


class AutomationAction(BaseModel):
    """
    A single executable action within an automation workflow.
    Derived and validated from Phase 3 WorkflowAction.
    """
    id: str = Field(
        ...,
        description="Deterministic unique identifier for this action step"
    )
    type: str = Field(
        ...,
        description="Action verb type (e.g. 'open_email', 'download_attachment')"
    )
    application: str = Field(
        ...,
        description="Target application name (e.g. 'demo_email', 'demo_crm')"
    )
    description: str = Field(
        ...,
        description="Human-readable description of what the action performs"
    )
    target: str = Field(
        ...,
        description="Target element or entity (e.g. 'customer_request', 'Rahul')"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional parameters or variables for execution"
    )


class ExecutionActionResult(BaseModel):
    """
    Result of executing an individual action step.
    """
    action_id: str = Field(..., description="ID of the executed action")
    action_type: str = Field(..., description="Type of the executed action")
    success: bool = Field(..., description="Whether the action succeeded")
    message: str = Field(..., description="Status message or detail")
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional execution output data or extracted values"
    )
    timestamp: Optional[str] = Field(
        default=None,
        description="ISO timestamp when execution occurred"
    )


class AutomationExecution(BaseModel):
    """
    Complete state and result of an automation workflow execution.

    Phase 4.6 adds human-in-the-loop fields:
    - failed_action / failure_reason: what went wrong
    - resume_available: whether resume is currently allowed
    - resume_count: how many times the execution has been resumed
    - paused_at / resumed_at / cancelled_at: lifecycle timestamps
    - all_actions: full action list (alias for actions_detail, Phase 4.5 compat)
    - _serialized_actions: serialized AutomationAction dicts for resume support
    """
    execution_id: str = Field(
        ...,
        description="Unique identifier for this workflow execution run"
    )
    workflow_name: str = Field(
        ...,
        description="Name of the workflow proposal being executed"
    )
    status: AutomationStatus = Field(
        default=AutomationStatus.PENDING,
        description="Current lifecycle status of the execution"
    )
    current_action: Optional[str] = Field(
        default=None,
        description="Currently running action type or last attempted action"
    )
    completed_actions: List[str] = Field(
        default_factory=list,
        description="List of action types successfully completed so far"
    )
    total_actions: int = Field(
        default=0,
        description="Total number of actions in the workflow"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed or was interrupted"
    )
    requires_human_intervention: bool = Field(
        default=False,
        description="Whether human intervention is required to proceed"
    )

    # ── Phase 4.6: human-in-the-loop fields ──────────────────────────────
    failed_action: Optional[str] = Field(
        default=None,
        description="Action type that failed and triggered a pause"
    )
    failure_reason: Optional[str] = Field(
        default=None,
        description="Human-readable explanation of why the action failed"
    )
    resume_available: bool = Field(
        default=False,
        description="Whether this execution can currently be resumed"
    )
    resume_count: int = Field(
        default=0,
        description="Number of times this execution has been resumed"
    )
    paused_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp when execution was paused"
    )
    resumed_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp of the most recent resume"
    )
    cancelled_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp when execution was cancelled"
    )
    # Serialised AutomationAction list stored so the engine can resume
    # from the correct action without re-running the entire workflow.
    serialized_actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Serialised AutomationAction list for resume support (internal)"
    )
    executor_type: Optional[str] = Field(
        default="playwright",
        description="Executor type used for execution ('playwright' or 'noop')"
    )
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Runtime context dictionary"
    )
    # ─────────────────────────────────────────────────────────────────────

    results: List[ExecutionActionResult] = Field(
        default_factory=list,
        description="Ordered list of individual action execution results"
    )
    started_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp when execution started"
    )
    completed_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp when execution finished"
    )
    execution_time_seconds: Optional[float] = Field(
        default=None,
        description="Measured execution duration in seconds"
    )
    applications: List[str] = Field(
        default_factory=list,
        description="Unique applications involved in the workflow"
    )
    actions_detail: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Ordered details of all workflow actions with states (Phase 4.5)"
    )
    # Phase 4.5 alias — same data as actions_detail kept for backward compat
    all_actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Alias for actions_detail; comprehensive action list with states"
    )


class ExecuteWorkflowRequest(BaseModel):
    """
    Request payload to trigger workflow execution.
    Requires explicit approved=True to pass the approval safety gate.
    """
    workflow: Optional[WorkflowProposal] = Field(
        default=None,
        description="Validated WorkflowProposal produced by Phase 3"
    )
    proposal: Optional[WorkflowProposal] = Field(
        default=None,
        description="Alternative alias for workflow proposal"
    )
    actions: Optional[List[WorkflowAction]] = Field(
        default=None,
        description="Optional list of actions if proposal is not provided"
    )
    approved: bool = Field(
        default=False,
        description="Explicit human approval flag. Execution is refused if False."
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional originating session ID"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional runtime execution parameters or variable overrides"
    )
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional runtime context"
    )
    executor_type: Optional[str] = Field(
        default="playwright",
        description="Executor to use: 'playwright' (default for Phase 4.4) or 'noop' (unit testing)"
    )


class ExecuteWorkflowResponse(BaseModel):
    """
    Structured response returned after workflow execution.
    Enriched with Phase 4.5 observability and Phase 4.6 human-in-the-loop fields.
    """
    status: str = Field(..., description="Status: 'completed', 'failed', 'pending', 'paused', 'cancelled'")
    workflow_id: str = Field(..., description="Unique execution ID")
    workflow_name: Optional[str] = Field(default=None, description="Name of the workflow")
    failed_action: Optional[str] = Field(default=None, description="Action type that failed, if any")
    failure_reason: Optional[str] = Field(default=None, description="Reason the action failed")
    message: Optional[str] = Field(default=None, description="Status or error message")
    requires_human_intervention: bool = Field(default=False, description="Flag indicating human action required")
    human_intervention: Optional[Dict[str, Any]] = Field(default=None, description="Guidance for human intervention")
    # Phase 4.6
    resume_available: bool = Field(default=False, description="Whether this execution can be resumed")
    resume_count: int = Field(default=0, description="Number of resume operations performed")
    paused_at: Optional[str] = Field(default=None, description="Timestamp when execution paused")
    resumed_at: Optional[str] = Field(default=None, description="Timestamp of most recent resume")
    cancelled_at: Optional[str] = Field(default=None, description="Timestamp when execution was cancelled")
    # Phase 4.5
    actions: List[Dict[str, Any]] = Field(default_factory=list, description="Ordered action execution statuses")
    completed_actions: List[str] = Field(default_factory=list, description="Names of completed actions")
    total_actions: int = Field(default=0, description="Total number of actions in the workflow")
    execution_time_seconds: Optional[float] = Field(default=None, description="Measured execution duration in seconds")
    applications: List[str] = Field(default_factory=list, description="Unique applications involved in the workflow")
    started_at: Optional[str] = Field(default=None, description="Execution start timestamp")
    completed_at: Optional[str] = Field(default=None, description="Execution completion timestamp")
    all_actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Comprehensive list of all actions in the workflow with their execution states"
    )

