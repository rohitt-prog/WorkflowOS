import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, status

from ai.models import WorkflowProposal, WorkflowAction, WorkflowTrigger
from automation.models import (
    AutomationExecution,
    AutomationStatus,
    ExecuteWorkflowRequest,
    ExecuteWorkflowResponse,
)
from automation.service import automation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/automation", tags=["automation"])


@router.post(
    "/execute",
    response_model=ExecuteWorkflowResponse,
    summary="Execute Workflow Automation",
    description=(
        "Executes a validated WorkflowProposal across controlled demo apps using PlaywrightExecutor. "
        "Strictly gated by human approval (approved=True required). "
        "Follows the execution chain: API Route -> AutomationService -> AutomationEngine -> PlaywrightExecutor."
    ),
)
async def execute_workflow_endpoint(request: ExecuteWorkflowRequest):
    """
    POST /api/automation/execute

    Executes a complete 5-action demo workflow end-to-end via PlaywrightExecutor.
    If approved is not True, execution is blocked and a pending approval response is returned.
    """
    # 1. Resolve WorkflowProposal
    proposal = request.workflow or request.proposal
    if not proposal and request.actions:
        # Construct synthetic proposal from raw action list
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
            detail="A 'workflow', 'proposal', or list of 'actions' is required for execution.",
        )

    # 2. Build runtime context
    context = dict(request.context or {})
    if request.session_id and "session_id" not in context:
        context["session_id"] = request.session_id

    # 3. Execution Chain: API Route -> AutomationService -> AutomationEngine -> PlaywrightExecutor
    # Default to "playwright" executor for Phase 4.4, with "noop" supported for unit tests.
    executor_type = request.executor_type or "playwright"

    execution: AutomationExecution = await automation_service.run_workflow(
        proposal=proposal,
        approved=request.approved,
        executor_type=executor_type,
        parameters=request.parameters,
        context=context,
    )

    # 4. Map structured response
    actions_list = [
        {
            "action": r.action_type,
            "status": "completed" if r.success else "failed",
            "message": r.message,
        }
        for r in execution.results
    ]

    if execution.status == AutomationStatus.PENDING:
        return ExecuteWorkflowResponse(
            status="pending",
            workflow_id=execution.execution_id,
            workflow_name=execution.workflow_name,
            message="Workflow execution pending approval. Human approval is required.",
            requires_human_intervention=False,
            actions=actions_list,
            completed_actions=execution.completed_actions,
            total_actions=execution.total_actions,
        )

    elif execution.status == AutomationStatus.FAILED:
        # Determine appropriate guidance message
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

        human_intervention_info = {
            "title": "Workflow paused",
            "reason": reason_text,
            "action_required": action_req,
        }

        return ExecuteWorkflowResponse(
            status="failed",
            workflow_id=execution.execution_id,
            workflow_name=execution.workflow_name,
            failed_action=execution.current_action,
            message=execution.error or "Workflow execution failed",
            requires_human_intervention=True,
            human_intervention=human_intervention_info,
            actions=actions_list,
            completed_actions=execution.completed_actions,
            total_actions=execution.total_actions,
        )

    else:
        return ExecuteWorkflowResponse(
            status="completed",
            workflow_id=execution.execution_id,
            workflow_name=execution.workflow_name,
            message="Workflow completed successfully",
            requires_human_intervention=False,
            actions=actions_list,
            completed_actions=execution.completed_actions,
            total_actions=execution.total_actions,
        )


@router.get(
    "/executions",
    summary="List Workflow Executions",
    description="Returns recorded automation workflow runs.",
)
async def list_executions_endpoint():
    """GET /api/automation/executions"""
    return {"executions": automation_service.list_executions()}
