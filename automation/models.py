import hashlib
import json
import uuid
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


def is_valid_transition(from_status: Any, to_status: Any) -> bool:
    """Return True iff the transition from_status → to_status is permitted by the state machine."""
    try:
        from_enum = AutomationStatus(from_status)
        to_enum = AutomationStatus(to_status)
        return to_enum in VALID_TRANSITIONS.get(from_enum, set())
    except (ValueError, TypeError):
        return False


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


# ---------------------------------------------------------------------------
# Phase 6: Declarative Workflow Specification Models
# ---------------------------------------------------------------------------

class StepCondition(BaseModel):
    """
    Defines a conditional expression for a workflow step.
    Evaluated dynamically against inputs, variables, or outputs of prior steps.
    """
    field: str = Field(..., description="Context path to evaluate (e.g. 'inputs.amount', 'variables.found')")
    operator: str = Field(
        default="==",
        description="Comparison operator: '==', '!=', '>', '<', '>=', '<=', 'contains', 'in', 'is_empty', 'is_not_empty', 'exists'"
    )
    value: Optional[Any] = Field(default=None, description="Expected value to compare against")


class RetryPolicy(BaseModel):
    """
    Retry configuration for transient failures on a workflow step.
    """
    max_retries: int = Field(default=0, ge=0, description="Max retry attempts after failure")
    max_attempts: Optional[int] = Field(default=None, description="Total attempts including first attempt")
    backoff_seconds: float = Field(default=1.0, ge=0.0, description="Delay between retry attempts")
    delay_seconds: Optional[float] = Field(default=None, description="Alias for backoff_seconds")
    retry_on_errors: List[str] = Field(
        default_factory=list,
        description="Optional list of error substrings that qualify for retry"
    )


class WorkflowInputDefinition(BaseModel):
    """
    Declares an expected input parameter for a declarative workflow.
    """
    name: str = Field(..., description="Variable identifier for the input")
    type: str = Field(default="string", description="Parameter type: 'string', 'number', 'boolean', 'object', 'array'")
    default: Optional[Any] = Field(default=None, description="Default value if not provided")
    required: bool = Field(default=False, description="Whether the input is mandatory")
    description: Optional[str] = Field(default=None, description="Explanation of what this input represents")


class WorkflowTriggerConfig(BaseModel):
    """
    Configurable trigger definition for declarative workflows.
    """
    type: str = Field(default="manual", description="Trigger mechanism: 'manual', 'event', 'webhook', 'schedule'")
    application: Optional[str] = Field(default=None, description="Target application slug if event-driven")
    event_type: Optional[str] = Field(default=None, description="Triggering event type if event-driven")
    event: Optional[str] = Field(default=None, description="Alias for event_type")
    description: Optional[str] = Field(default=None, description="Human description of trigger condition")
    conditions: List[StepCondition] = Field(default_factory=list, description="Optional filtering conditions")


class WorkflowStep(BaseModel):
    """
    A declarative workflow step with support for parameter templating,
    branching conditions, output mapping, and retry policies.
    """
    id: str = Field(..., description="Unique deterministic step ID (e.g. 'step_search_cust')")
    name: Optional[str] = Field(default=None, description="Friendly display label for step")
    type: str = Field(..., description="Action verb (e.g. 'search_customer', 'send_message') or control verb")
    application: str = Field(default="workflow_system", description="Target application name")
    description: Optional[str] = Field(default=None, description="Human explanation of step action")
    target: Optional[str] = Field(default=None, description="Target entity, recipient, or locator")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters with {{variable}} templating support"
    )
    condition: Optional[StepCondition] = Field(default=None, description="Condition guard for step execution")
    on_true: Optional[str] = Field(default=None, description="Next step ID if condition evaluates True")
    on_false: Optional[str] = Field(default=None, description="Next step ID if condition evaluates False")
    retry_policy: Optional[RetryPolicy] = Field(default=None, description="Retry configuration on error")
    timeout_seconds: Optional[float] = Field(default=None, description="Per-step timeout limit")
    continue_on_failure: bool = Field(
        default=False,
        description="If True, step failure logs a warning and continues without halting"
    )
    output_mapping: Optional[Dict[str, str]] = Field(
        default=None,
        description="Map step output fields into workflow variables (e.g. {'customer_id': 'data.id'})"
    )


def _generate_workflow_id() -> str:
    """Generate a clean unique identifier for declarative workflows."""
    return f"wf_{uuid.uuid4().hex[:12]}"


class WorkflowDefinition(BaseModel):
    """
    Phase 6 Declarative Workflow Specification.
    Supports structured inputs, variables, triggers, conditional branching, and step policies.
    """
    id: Optional[str] = Field(
        default_factory=_generate_workflow_id,
        description="Unique workflow definition ID"
    )
    name: str = Field(..., description="Human-readable workflow title")
    description: Optional[str] = Field(default=None, description="Detailed explanation of workflow")
    version: str = Field(default="1.0.0", description="Semantic version string")
    trigger: WorkflowTriggerConfig = Field(default_factory=WorkflowTriggerConfig, description="Trigger settings")
    inputs: List[WorkflowInputDefinition] = Field(default_factory=list, description="Input definitions")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Initial default workflow variables")
    steps: List[WorkflowStep] = Field(default_factory=list, description="Ordered workflow steps")
    requires_approval: bool = Field(default=True, description="Safety gate: whether execution requires approval")
    tags: List[str] = Field(default_factory=list, description="Optional workflow categorization tags")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp")
    definition_hash: Optional[str] = Field(default=None, description="Canonical SHA-256 fingerprint of workflow specification")


def compute_workflow_definition_hash(workflow: WorkflowDefinition) -> str:
    """
    Computes a canonical SHA-256 hash of a WorkflowDefinition's core executable specification.
    Includes name, trigger, inputs, variables, steps (id, type, application, target, parameters, condition, on_true, on_false),
    and requires_approval flag.
    Excludes volatile fields like created_at, updated_at, id, and definition_hash itself.
    """
    norm = {
        "name": workflow.name,
        "trigger": workflow.trigger.model_dump() if workflow.trigger else {},
        "inputs": [inp.model_dump() for inp in workflow.inputs],
        "variables": workflow.variables or {},
        "steps": [
            {
                "id": s.id,
                "type": s.type,
                "application": s.application,
                "target": s.target or "",
                "parameters": s.parameters or {},
                "condition": s.condition.model_dump() if s.condition else None,
                "on_true": s.on_true,
                "on_false": s.on_false,
                "continue_on_failure": s.continue_on_failure,
                "timeout_seconds": s.timeout_seconds,
            }
            for s in workflow.steps
        ],
        "requires_approval": workflow.requires_approval,
    }
    raw = json.dumps(norm, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class StepExecutionResult(BaseModel):
    """
    Detailed runtime telemetry, outputs, and log entries for a single executed step.
    """
    step_id: str = Field(..., description="ID of the workflow step")
    action_type: str = Field(..., description="Action verb executed")
    application: str = Field(..., description="Application context")
    status: str = Field(..., description="Status: 'completed', 'failed', 'skipped', 'running'")
    attempts: int = Field(default=1, description="Number of attempts executed")
    started_at: Optional[str] = Field(default=None, description="ISO timestamp of step start")
    completed_at: Optional[str] = Field(default=None, description="ISO timestamp of step end")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Resolved input parameters")
    outputs: Dict[str, Any] = Field(default_factory=dict, description="Produced output data")
    logs: List[str] = Field(default_factory=list, description="Structured log messages for step")
    error: Optional[str] = Field(default=None, description="Error message if step failed")


class AutomationExecution(BaseModel):
    """
    Complete state, telemetry, and result of an automation workflow execution.

    Phase 4.6 & 6:
    - failed_action / failure_reason: what went wrong
    - resume_available: whether resume is currently allowed
    - resume_count: how many times the execution has been resumed
    - paused_at / resumed_at / cancelled_at: lifecycle timestamps
    - all_actions: full action list with states
    - serialized_actions: serialized AutomationAction dicts for legacy resume support
    - Phase 6 additions: workflow_id, inputs, variables, step_results, execution_logs, serialized_workflow
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
    # ── Phase 6 additions ────────────────────────────────────────────────
    workflow_id: Optional[str] = Field(
        default=None,
        description="ID of the executed WorkflowDefinition if applicable"
    )
    inputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Resolved input arguments passed to the workflow"
    )
    variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow runtime variables state"
    )
    step_results: List[StepExecutionResult] = Field(
        default_factory=list,
        description="Detailed per-step execution results and outputs"
    )
    execution_logs: List[str] = Field(
        default_factory=list,
        description="Workflow-level execution event log"
    )
    serialized_workflow: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Serialized WorkflowDefinition for pause/resume"
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
    all_actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Alias for actions_detail; comprehensive action list with states"
    )
    # Phase 7.4: Reliability, Idempotency & Security
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Client idempotency key to prevent duplicate runs (Phase 7.4)"
    )
    definition_hash: Optional[str] = Field(
        default=None,
        description="SHA-256 fingerprint of approved workflow definition (Phase 7.4)"
    )
    recovery_attempts: int = Field(
        default=0,
        description="Count of system recoveries performed on restart (Phase 7.4)"
    )
    recovery_reason: Optional[str] = Field(
        default=None,
        description="Audit reason for recovery classification (Phase 7.4)"
    )


class ExecuteWorkflowRequest(BaseModel):
    """
    Request payload to trigger workflow execution.
    Requires explicit approved=True to pass the approval safety gate.
    Supports both legacy Phase 3/4 proposals and Phase 6 declarative workflows.
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
    # Phase 6: Declarative workflow specification
    workflow_definition: Optional[WorkflowDefinition] = Field(
        default=None,
        description="Phase 6 Declarative WorkflowDefinition"
    )
    inputs: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Phase 6 input values matching workflow inputs"
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
    # Phase 7.4 additions
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Optional idempotency key to prevent duplicate runs (Phase 7.4)"
    )
    definition_hash: Optional[str] = Field(
        default=None,
        description="Optional expected SHA-256 fingerprint of approved workflow definition (Phase 7.4)"
    )


class ExecuteWorkflowResponse(BaseModel):
    """
    Structured response returned after workflow execution.
    Enriched with Phase 4.5 observability, Phase 4.6 recovery, and Phase 6 declarative telemetry.
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
    # Phase 6
    workflow_definition_id: Optional[str] = Field(default=None, description="Workflow definition ID if applicable")
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Final workflow variables state")
    step_results: List[Dict[str, Any]] = Field(default_factory=list, description="Detailed per-step results and logs")
    execution_logs: List[str] = Field(default_factory=list, description="Workflow-level execution logs")
    # Phase 7.4
    idempotency_key: Optional[str] = Field(default=None, description="Client idempotency key if provided (Phase 7.4)")
    definition_hash: Optional[str] = Field(default=None, description="SHA-256 fingerprint of approved workflow (Phase 7.4)")

