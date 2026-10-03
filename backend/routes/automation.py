import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status

from ai.models import WorkflowProposal, WorkflowAction, WorkflowTrigger
from automation.models import (
    AutomationExecution,
    AutomationStatus,
    ExecuteWorkflowRequest,
    ExecuteWorkflowResponse,
    WorkflowDefinition,
)
from automation.engine import InvalidStateTransitionError
from automation.service import automation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/automation", tags=["automation"])


def _build_response(execution: AutomationExecution) -> ExecuteWorkflowResponse:
    """
    Shared helper: map an AutomationExecution to an ExecuteWorkflowResponse.
    Handles all statuses: pending, paused, cancelled, failed, completed.
    Enriched with Phase 6 declarative telemetry and step execution logs.
    """
    actions_list: List[Dict[str, Any]] = [
        {
            "action": r.action_type,
            "status": "completed" if r.success else "failed",
            "message": r.message,
            "application": next(
                (d.get("application", "") for d in execution.actions_detail
                 if d.get("action") == r.action_type),
                "",
            ),
        }
        for r in execution.results
    ]

    base_kwargs = {
        "workflow_id": execution.execution_id,
        "workflow_name": execution.workflow_name,
        "workflow_definition_id": execution.workflow_id,
        "variables": execution.variables or {},
        "step_results": [r.model_dump() for r in execution.step_results],
        "execution_logs": execution.execution_logs or [],
        "actions": actions_list,
        "completed_actions": execution.completed_actions,
        "total_actions": execution.total_actions,
        "execution_time_seconds": execution.execution_time_seconds,
        "applications": execution.applications,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "all_actions": execution.actions_detail,
        "resume_count": execution.resume_count,
    }

    # ── PENDING (unapproved) ──────────────────────────────────────────────
    if execution.status == AutomationStatus.PENDING:
        return ExecuteWorkflowResponse(
            status="pending",
            message="Workflow execution pending approval. Human approval is required.",
            requires_human_intervention=False,
            resume_available=False,
            **base_kwargs,
        )

    # ── PAUSED (action failed, awaiting human intervention) ───────────────
    elif execution.status == AutomationStatus.PAUSED:
        failed_action = execution.failed_action or execution.current_action
        reason_msg = execution.failure_reason or execution.error or "Action execution failed"

        if execution.current_action in ("search_customer", "update_customer"):
            action_req = "Please resolve the issue in WorkFlow CRM, then click Resume."
        else:
            action_req = "Please fix the issue and click Resume to retry from the failed action."

        human_intervention_info = {
            "title": "Workflow paused — action failed",
            "reason": reason_msg,
            "action_required": action_req,
            "failed_action": failed_action,
        }

        return ExecuteWorkflowResponse(
            status="paused",
            failed_action=failed_action,
            failure_reason=reason_msg,
            message=f"Workflow paused after '{failed_action}' failed. Human intervention required.",
            requires_human_intervention=True,
            human_intervention=human_intervention_info,
            resume_available=execution.resume_available,
            paused_at=execution.paused_at,
            resumed_at=execution.resumed_at,
            **base_kwargs,
        )

    # ── CANCELLED ─────────────────────────────────────────────────────────
    elif execution.status == AutomationStatus.CANCELLED:
        return ExecuteWorkflowResponse(
            status="cancelled",
            message="Workflow execution was cancelled by user.",
            requires_human_intervention=False,
            resume_available=False,
            paused_at=execution.paused_at,
            cancelled_at=execution.cancelled_at,
            **base_kwargs,
        )

    # ── FAILED (terminal, not resumable — validation failures etc.) ───────
    elif execution.status == AutomationStatus.FAILED:
        reason_msg = execution.error or "Action execution failed"
        if "Customer" in reason_msg and "not found" in reason_msg:
            action_req = "Please resolve the issue in WorkFlow CRM."
            reason_text = "Customer not found"
        elif execution.current_action in ("search_customer", "update_customer"):
            action_req = "Please resolve the issue in WorkFlow CRM."
            reason_text = reason_msg
        else:
            action_req = "Please review the failed step and take manual action."
            reason_text = reason_msg

        return ExecuteWorkflowResponse(
            status="failed",
            failed_action=execution.current_action,
            failure_reason=reason_text,
            message=execution.error or "Workflow execution failed",
            requires_human_intervention=True,
            human_intervention={
                "title": "Workflow paused",
                "reason": reason_text,
                "action_required": action_req,
            },
            resume_available=False,
            **base_kwargs,
        )

    # ── COMPLETED ─────────────────────────────────────────────────────────
    else:
        return ExecuteWorkflowResponse(
            status="completed",
            message="Workflow completed successfully",
            requires_human_intervention=False,
            resume_available=False,
            resumed_at=execution.resumed_at,
            **base_kwargs,
        )


# ---------------------------------------------------------------------------
# Declarative Workflow Template Management Endpoints (Phase 6)
# ---------------------------------------------------------------------------

@router.get(
    "/workflows",
    response_model=List[WorkflowDefinition],
    summary="List Declarative Workflows",
    description="Returns all registered declarative workflow definitions and templates."
)
async def list_workflows_endpoint():
    """GET /api/automation/workflows"""
    return automation_service.list_workflows()


@router.post(
    "/workflows",
    response_model=WorkflowDefinition,
    status_code=status.HTTP_201_CREATED,
    summary="Create or Register Declarative Workflow",
    description="Registers a new declarative workflow definition."
)
async def register_workflow_endpoint(workflow: WorkflowDefinition):
    """POST /api/automation/workflows"""
    return automation_service.register_workflow(workflow)


@router.get(
    "/workflows/{workflow_id}",
    response_model=WorkflowDefinition,
    summary="Get Declarative Workflow",
    description="Retrieves a specific declarative workflow definition by ID."
)
async def get_workflow_endpoint(workflow_id: str):
    """GET /api/automation/workflows/{workflow_id}"""
    wf = automation_service.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow definition '{workflow_id}' not found."
        )
    return wf


@router.post(
    "/execute",
    response_model=ExecuteWorkflowResponse,
    summary="Execute Workflow Automation",
    description=(
        "Executes either a declarative WorkflowDefinition (Phase 6) or a legacy WorkflowProposal (Phase 3/4). "
        "Strictly gated by human approval (approved=True required). "
        "On action failure: execution transitions to PAUSED with resume_available=True."
    ),
)
async def execute_workflow_endpoint(request: ExecuteWorkflowRequest):
    """
    POST /api/automation/execute

    Executes a complete workflow end-to-end via PlaywrightExecutor or NoOpExecutor.
    If approved is not True, execution is blocked and a pending approval response is returned.
    """
    context = dict(request.context or {})
    if request.session_id and "session_id" not in context:
        context["session_id"] = request.session_id

    executor_type = request.executor_type or "playwright"

    # Branch 1: Declarative WorkflowDefinition (Phase 6)
    if request.workflow_definition:
        execution = await automation_service.run_workflow(
            workflow_definition=request.workflow_definition,
            approved=request.approved,
            executor_type=executor_type,
            inputs=request.inputs,
            parameters=request.parameters,
            context=context,
        )
        return _build_response(execution)

    # Branch 2: Legacy WorkflowProposal (Phase 3/4)
    proposal = request.workflow or request.proposal
    if not proposal and request.actions:
        proposal = WorkflowProposal(
            name="Custom Workflow Execution",
            intent="Execute specified automation actions",
            trigger=WorkflowTrigger(
                type="custom_trigger",
                application="demo_email",
                description="Custom action trigger",
            ),
            actions=request.actions,
            variables=[],
            applications=list({a.application for a in request.actions}),
            requires_approval=True,
        )

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A 'workflow_definition', 'workflow', 'proposal', or list of 'actions' is required for execution.",
        )

    execution = await automation_service.run_workflow(
        proposal=proposal,
        approved=request.approved,
        executor_type=executor_type,
        parameters=request.parameters,
        context=context,
    )

    return _build_response(execution)


class ResumeExecutionRequest(BaseModel):
    """Optional payload for resuming a paused execution."""
    executor_type: Optional[str] = Field(
        default=None,
        description="Executor override: 'playwright' or 'noop'"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Updated parameters for actions"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Updated runtime context"
    )


@router.post(
    "/executions/{execution_id}/resume",
    response_model=ExecuteWorkflowResponse,
    summary="Resume Paused Execution",
    description=(
        "Phase 4.6: Resume a PAUSED workflow execution from the failed action. "
        "The execution must be in PAUSED state with resume_available=True. "
        "The failed action is retried; already-completed actions are NOT re-executed. "
        "On success after resume: returns status=completed. "
        "On failure again: returns status=paused with updated failure information."
    ),
)
async def resume_execution_endpoint(
    execution_id: str,
    request: Optional[ResumeExecutionRequest] = None,
    executor_type: Optional[str] = None,
):
    """
    POST /api/automation/executions/{execution_id}/resume

    Resumes a PAUSED execution from the failed action index.
    Supports optional request body or executor_type query param.
    """
    try:
        resolved_executor = (request.executor_type if request and request.executor_type else None) or executor_type
        parameters = request.parameters if request else None
        context = request.context if request else None

        execution = await automation_service.resume_execution(
            execution_id=execution_id,
            executor_type=resolved_executor,
            parameters=parameters,
            context=context,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution with ID '{execution_id}' not found.",
        )
    except InvalidStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return _build_response(execution)


@router.post(
    "/executions/{execution_id}/cancel",
    response_model=ExecuteWorkflowResponse,
    summary="Cancel Paused Execution",
    description=(
        "Phase 4.6: Cancel a PAUSED workflow execution. "
        "The execution must be in PAUSED state. "
        "Status transitions to CANCELLED (terminal) and resume_available is set to False."
    ),
)
async def cancel_execution_endpoint(execution_id: str):
    """
    POST /api/automation/executions/{execution_id}/cancel

    Cancels a PAUSED execution permanently. This is irreversible.
    """
    try:
        execution = automation_service.cancel_execution(execution_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution with ID '{execution_id}' not found.",
        )
    except InvalidStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return _build_response(execution)


@router.get(
    "/executions",
    summary="List Workflow Executions",
    description="Returns recorded automation workflow runs (Phase 4.5+).",
)
async def list_executions_endpoint():
    """GET /api/automation/executions"""
    return {"executions": automation_service.list_executions()}


@router.get(
    "/executions/{execution_id}",
    summary="Get Specific Workflow Execution",
    description="Returns recorded details of a specific execution run.",
)
async def get_execution_endpoint(execution_id: str):
    """GET /api/automation/executions/{execution_id}"""
    execution = automation_service.get_execution(execution_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution with ID '{execution_id}' not found.",
        )
    return execution



