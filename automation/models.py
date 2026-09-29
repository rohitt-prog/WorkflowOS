from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from ai.models import WorkflowProposal, WorkflowAction


class AutomationStatus(str, Enum):
    """
    Status of an automation execution run.
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_FOR_HUMAN = "waiting_for_human"


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
        description="Whether human intervention is required to proceed (Phase 4.6)"
    )
    results: List[ExecutionActionResult] = Field(
        default_factory=list,
        description="Ordered list of individual action execution results"
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
    Matches Phase 4.4 specification for completed and failed workflows.
    """
    status: str = Field(..., description="Status: 'completed', 'failed', or 'pending'")
    workflow_id: str = Field(..., description="Unique execution ID")
    workflow_name: Optional[str] = Field(default=None, description="Name of the workflow")
    failed_action: Optional[str] = Field(default=None, description="Action type that failed, if any")
    message: Optional[str] = Field(default=None, description="Status or error message")
    requires_human_intervention: bool = Field(default=False, description="Flag indicating human action required")
    human_intervention: Optional[Dict[str, Any]] = Field(default=None, description="Guidance for human intervention")
    actions: List[Dict[str, Any]] = Field(default_factory=list, description="Ordered action execution statuses")
    completed_actions: List[str] = Field(default_factory=list, description="Names of completed actions")
    total_actions: int = Field(default=0, description="Total number of actions in the workflow")

