import logging
import uuid
from typing import List, Optional, Dict, Any, Set

from ai.models import WorkflowProposal, WorkflowAction
from automation.models import (
    AutomationAction,
    AutomationExecution,
    AutomationStatus,
    ExecutionActionResult,
)
from automation.executor import ActionExecutor, NoOpExecutor

logger = logging.getLogger(__name__)

# Canonical action verbs supported by the Phase 4 WorkFlowOS automation pipeline
SUPPORTED_ACTION_TYPES: Set[str] = {
    "open_email",
    "download_attachment",
    "search_customer",
    "update_customer",
    "send_message",
}


class AutomationEngineError(Exception):
    """Base exception for automation engine errors."""
    pass


class UnsupportedActionError(AutomationEngineError):
    """Raised when a workflow contains an unsupported action verb."""
    pass


class ApprovalRequiredError(AutomationEngineError):
    """Raised when an unapproved workflow is requested to execute."""
    pass


class AutomationEngine:
    """
    Core engine responsible for translating Phase 3 WorkflowProposal definitions
    into validated AutomationAction sequences, applying human approval safety gates,
    and coordinating sequential action execution through the ActionExecutor interface.

    Phase 4.2 uses NoOpExecutor by default. No browser is launched.
    """

    def __init__(self, default_executor: Optional[ActionExecutor] = None):
        self._default_executor = default_executor or NoOpExecutor()

    def validate_and_convert_actions(
        self,
        workflow_actions: List[WorkflowAction],
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[AutomationAction]:
        """
        Validates action verbs against supported types and converts WorkflowAction
        objects into executable AutomationAction objects preserving strict order.

        :param workflow_actions: Ordered list of actions from WorkflowProposal.
        :param parameters: Optional execution parameters.
        :return: Ordered list of AutomationAction instances.
        :raises UnsupportedActionError: If any action type is not supported.
        """
        if not workflow_actions:
            raise AutomationEngineError("Cannot convert an empty action list.")

        params = parameters or {}
        automation_actions: List[AutomationAction] = []

        for idx, act in enumerate(workflow_actions, start=1):
            action_type = act.type.strip().lower()

            if action_type not in SUPPORTED_ACTION_TYPES:
                supported_list = sorted(list(SUPPORTED_ACTION_TYPES))
                err_msg = (
                    f"Action step {idx} '{act.type}' is not supported for automation. "
                    f"Supported actions are: {supported_list}"
                )
                logger.error(err_msg)
                raise UnsupportedActionError(err_msg)

            action_id = f"act_{idx:02d}_{action_type}"
            automation_actions.append(
                AutomationAction(
                    id=action_id,
                    type=action_type,
                    application=act.application,
                    description=act.description,
                    target=act.target,
                    parameters=params.get(action_id, {}),
                )
            )

        return automation_actions

    async def execute_workflow(
        self,
        proposal: WorkflowProposal,
        approved: bool = False,
        executor: Optional[ActionExecutor] = None,
        parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AutomationExecution:
        """
        Executes a workflow proposal after validating approval and action types.

        APPROVAL SAFETY GATE:
        - If approved is False, execution is refused immediately.
        - Status is set to AutomationStatus.PENDING with 0 completed actions.

        ACTION MAPPING:
        - WorkflowActions are converted to AutomationActions.
        - Unknown action types produce a controlled error and halt execution.

        EXECUTION:
        - Actions are executed sequentially through the ActionExecutor.
        - Execution halts immediately if any action fails.
        - Completed actions are recorded.

        :param proposal: Validated WorkflowProposal produced by Phase 3.
        :param approved: Explicit boolean approval flag.
        :param executor: Optional ActionExecutor override (defaults to NoOpExecutor).
        :param parameters: Optional parameter dictionary for actions.
        :param context: Optional runtime context.
        :return: AutomationExecution tracking the execution state and results.
        """
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        total_actions = len(proposal.actions)

        logger.info(
            f"Initiating automation engine for workflow: '{proposal.name}' "
            f"(execution_id={execution_id}, approved={approved}, actions={total_actions})"
        )

        # 1. Action Validation & Mapping
        try:
            actions = self.validate_and_convert_actions(
                proposal.actions,
                parameters=parameters
            )
        except UnsupportedActionError as uae:
            logger.error(f"Workflow '{proposal.name}' action validation failed: {uae}")
            return AutomationExecution(
                execution_id=execution_id,
                workflow_name=proposal.name,
                status=AutomationStatus.FAILED,
                current_action=None,
                completed_actions=[],
                total_actions=total_actions,
                error=str(uae),
                requires_human_intervention=False,
                results=[],
            )

        # 2. Approval Safety Gate
        # Do not automatically approve anything.
        # If approval is False, do NOT execute any action.
        if not approved:
            logger.info(
                f"Workflow '{proposal.name}' is unapproved. Refusing execution (status=pending)."
            )
            return AutomationExecution(
                execution_id=execution_id,
                workflow_name=proposal.name,
                status=AutomationStatus.PENDING,
                current_action=None,
                completed_actions=[],
                total_actions=len(actions),
                error=None,
                requires_human_intervention=False,
                results=[],
            )

        # 3. Approved Execution
        active_executor = executor or self._default_executor
        completed_actions: List[str] = []
        results: List[ExecutionActionResult] = []

        logger.info(
            f"Approval confirmed. Executing {len(actions)} actions sequentially "
            f"via {active_executor.__class__.__name__}..."
        )

        for action in actions:
            # Execute current action
            logger.info(f"Executing step {action.id} ({action.type})...")
            try:
                result = await active_executor.execute(action, context=context)
                results.append(result)
            except Exception as e:
                logger.error(f"Unexpected exception executing {action.id}: {e}", exc_info=True)
                result = ExecutionActionResult(
                    action_id=action.id,
                    action_type=action.type,
                    success=False,
                    message=f"Executor exception: {str(e)}"
                )
                results.append(result)

            if not result.success:
                # Stop subsequent actions immediately
                logger.warning(
                    f"Action {action.id} failed: {result.message}. Halting workflow execution."
                )
                return AutomationExecution(
                    execution_id=execution_id,
                    workflow_name=proposal.name,
                    status=AutomationStatus.FAILED,
                    current_action=action.type,
                    completed_actions=completed_actions,
                    total_actions=len(actions),
                    error=result.message,
                    requires_human_intervention=False,
                    results=results,
                )

            # Record completed action
            completed_actions.append(action.type)

        # 4. Completed Execution
        logger.info(
            f"Workflow '{proposal.name}' completed successfully ({len(completed_actions)}/{len(actions)} actions)."
        )
        return AutomationExecution(
            execution_id=execution_id,
            workflow_name=proposal.name,
            status=AutomationStatus.COMPLETED,
            current_action=None,
            completed_actions=completed_actions,
            total_actions=len(actions),
            error=None,
            requires_human_intervention=False,
            results=results,
        )


# Singleton instance for general use
automation_engine = AutomationEngine()
