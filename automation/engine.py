import logging
import uuid
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Set

from ai.models import WorkflowProposal, WorkflowAction
from automation.models import (
    AutomationAction,
    AutomationExecution,
    AutomationStatus,
    ExecutionActionResult,
    is_valid_transition,
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


class InvalidStateTransitionError(AutomationEngineError):
    """Raised when a requested state transition is not allowed by the state machine."""
    pass


class AutomationEngine:
    """
    Core engine responsible for translating Phase 3 WorkflowProposal definitions
    into validated AutomationAction sequences, applying human approval safety gates,
    and coordinating sequential action execution through the ActionExecutor interface.

    Phase 4.6 adds:
    - PAUSED execution status when an action fails (enabling human-in-the-loop)
    - execute_from_index(): resume from a specific action without re-running completed actions
    - State machine transition enforcement via is_valid_transition()
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

    def _build_actions_detail(
        self,
        all_actions: List[AutomationAction],
        completed: List[str],
        action_results: List[ExecutionActionResult],
        failed_action_id: Optional[str] = None,
        is_pending: bool = False,
        paused: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Build the actions_detail list from the current execution state.

        Phase 4.6 change:
        - When paused=True: actions after the failed action stay as 'pending'
          (they are NOT marked 'skipped' — they will be retried on resume).
        - When not paused (i.e. terminal FAILED): actions after failure are 'skipped'.
        """
        details = []
        for act in all_actions:
            if is_pending:
                act_status = "pending"
                msg = "Pending human approval"
            elif act.type in completed:
                act_status = "completed"
                res = next((r for r in action_results if r.action_id == act.id), None)
                msg = res.message if res else "Completed successfully"
            elif act.id == failed_action_id or (failed_action_id and act.type == failed_action_id):
                act_status = "failed"
                res = next((r for r in action_results if r.action_id == act.id), None)
                msg = res.message if res else "Action execution failed"
            else:
                # Post-failure action
                if paused:
                    act_status = "pending"   # Will be retried after human intervention
                    msg = "Pending — awaiting human intervention to resume"
                else:
                    act_status = "skipped"
                    msg = "Not executed (halted after prior action failure)"

            details.append({
                "action": act.type,
                "action_id": act.id,
                "description": act.description,
                "application": act.application,
                "target": act.target,
                "status": act_status,
                "message": msg,
            })
        return details

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

        Phase 4.6 behaviour change:
        - When an action fails, execution status is set to PAUSED (not FAILED).
        - requires_human_intervention=True and resume_available=True are set.
        - Actions after the failed action remain PENDING (not SKIPPED).
        - The serialized action list is stored on the execution for resume support.

        APPROVAL SAFETY GATE:
        - If approved is False, execution is refused immediately.
        - Status is set to AutomationStatus.PENDING with 0 completed actions.
        """
        start_time = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        total_actions = len(proposal.actions)
        applications = list(dict.fromkeys(
            proposal.applications or [act.application for act in proposal.actions if act.application]
        ))

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
            now_iso = datetime.now(timezone.utc).isoformat()
            exec_obj = AutomationExecution(
                execution_id=execution_id,
                workflow_name=proposal.name,
                status=AutomationStatus.FAILED,
                current_action=None,
                completed_actions=[],
                total_actions=total_actions,
                error=str(uae),
                requires_human_intervention=False,
                results=[],
                started_at=started_at,
                completed_at=now_iso,
                execution_time_seconds=round(time.perf_counter() - start_time, 3),
                applications=applications,
                actions_detail=[],
                all_actions=[],
            )
            return exec_obj

        # 2. Approval Safety Gate
        if not approved:
            logger.info(
                f"Workflow '{proposal.name}' is unapproved. Refusing execution (status=pending)."
            )
            actions_detail = self._build_actions_detail(actions, [], [], is_pending=True)
            exec_obj = AutomationExecution(
                execution_id=execution_id,
                workflow_name=proposal.name,
                status=AutomationStatus.PENDING,
                current_action=None,
                completed_actions=[],
                total_actions=len(actions),
                error=None,
                requires_human_intervention=False,
                results=[],
                started_at=started_at,
                completed_at=started_at,
                execution_time_seconds=0.0,
                applications=applications,
                actions_detail=actions_detail,
                all_actions=actions_detail,
            )
            return exec_obj

        # 3. Approved Execution — delegate to internal runner
        return await self._run_actions(
            actions=actions,
            execution_id=execution_id,
            workflow_name=proposal.name,
            start_index=0,
            prior_completed=[],
            prior_results=[],
            start_time=start_time,
            started_at=started_at,
            applications=applications,
            executor=executor,
            context=context,
            resume_count=0,
            resumed_at=None,
        )

    async def execute_from_index(
        self,
        execution: AutomationExecution,
        start_index: int,
        executor: Optional[ActionExecutor] = None,
        context: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> AutomationExecution:
        """
        Phase 4.6: Resume execution from a specific action index.

        Reconstructs AutomationAction objects from the serialized list stored on the
        execution, then runs only the actions at and after start_index.
        Already-completed actions are NOT re-executed.

        :param execution: The existing PAUSED AutomationExecution.
        :param start_index: Zero-based index of the first action to (re-)execute.
        :param executor: Optional executor override.
        :param context: Optional runtime context.
        :param parameters: Optional updated action parameters.
        :return: Updated AutomationExecution with final status.
        """
        if not is_valid_transition(execution.status, AutomationStatus.RUNNING):
            raise InvalidStateTransitionError(
                f"Cannot resume execution '{execution.execution_id}': "
                f"invalid state transition {execution.status} → RUNNING. "
                f"Only PAUSED executions can be resumed."
            )

        # Reconstruct actions from serialized list
        actions = [AutomationAction(**a) for a in execution.serialized_actions]
        if parameters:
            for act in actions:
                if act.id in parameters:
                    act.parameters.update(parameters[act.id])
                elif act.type in parameters:
                    act.parameters.update(parameters[act.type])

        prior_completed = list(execution.completed_actions)
        # Keep only results of actions completed prior to start_index (deduplicate retried action)
        prior_results = [r for r in execution.results if r.success and r.action_type in prior_completed]
        now_iso = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"Resuming execution '{execution.execution_id}' from action index {start_index} "
            f"(already completed: {prior_completed})"
        )

        return await self._run_actions(
            actions=actions,
            execution_id=execution.execution_id,
            workflow_name=execution.workflow_name,
            start_index=start_index,
            prior_completed=prior_completed,
            prior_results=prior_results,
            start_time=time.perf_counter(),
            started_at=execution.started_at or now_iso,
            applications=execution.applications,
            executor=executor,
            context=context,
            resume_count=execution.resume_count + 1,
            resumed_at=now_iso,
            accumulated_time=execution.execution_time_seconds or 0.0,
        )

    async def _run_actions(
        self,
        actions: List[AutomationAction],
        execution_id: str,
        workflow_name: str,
        start_index: int,
        prior_completed: List[str],
        prior_results: List[ExecutionActionResult],
        start_time: float,
        started_at: str,
        applications: List[str],
        executor: Optional[ActionExecutor],
        context: Optional[Dict[str, Any]],
        resume_count: int,
        resumed_at: Optional[str],
        accumulated_time: float = 0.0,
    ) -> AutomationExecution:
        """
        Internal sequential execution runner.
        Runs actions[start_index:] with the given executor.
        Carries forward completed actions from prior_completed.
        """
        active_executor = executor or self._default_executor
        completed_actions: List[str] = list(prior_completed)
        results: List[ExecutionActionResult] = list(prior_results)

        logger.info(
            f"Approval confirmed. Executing {len(actions) - start_index} actions "
            f"(index {start_index}–{len(actions) - 1}) sequentially "
            f"via {active_executor.__class__.__name__}..."
        )

        # Serialise full action list for potential future resumes
        serialized_actions = [a.model_dump() for a in actions]

        try:
            await active_executor.start()

            for idx, action in enumerate(actions):
                if idx < start_index:
                    # Skip already-completed actions
                    continue

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
                    # ── Phase 4.6: PAUSED instead of FAILED ─────────────
                    logger.warning(
                        f"Action {action.id} failed: {result.message}. "
                        f"Execution PAUSED — human intervention required."
                    )
                    elapsed = round(accumulated_time + (time.perf_counter() - start_time), 3)
                    now_iso = datetime.now(timezone.utc).isoformat()
                    actions_detail = self._build_actions_detail(
                        actions,
                        completed_actions,
                        results,
                        failed_action_id=action.id,
                        paused=True,    # post-failure actions stay PENDING, not SKIPPED
                    )
                    return AutomationExecution(
                        execution_id=execution_id,
                        workflow_name=workflow_name,
                        status=AutomationStatus.PAUSED,
                        current_action=action.type,
                        completed_actions=completed_actions,
                        total_actions=len(actions),
                        error=result.message,
                        requires_human_intervention=True,
                        # Phase 4.6
                        failed_action=action.type,
                        failure_reason=result.message,
                        resume_available=True,
                        resume_count=resume_count,
                        paused_at=now_iso,
                        resumed_at=resumed_at,
                        serialized_actions=serialized_actions,
                        context=context or {},
                        results=results,
                        started_at=started_at,
                        completed_at=None,
                        execution_time_seconds=elapsed,
                        applications=applications,
                        actions_detail=actions_detail,
                        all_actions=actions_detail,
                    )

                # Record completed action
                completed_actions.append(action.type)

            # ── All actions completed successfully ────────────────────────
            logger.info(
                f"Workflow '{workflow_name}' completed successfully "
                f"({len(completed_actions)}/{len(actions)} actions)."
            )
            elapsed = round(accumulated_time + (time.perf_counter() - start_time), 3)
            now_iso = datetime.now(timezone.utc).isoformat()
            actions_detail = self._build_actions_detail(actions, completed_actions, results)
            return AutomationExecution(
                execution_id=execution_id,
                workflow_name=workflow_name,
                status=AutomationStatus.COMPLETED,
                current_action=None,
                completed_actions=completed_actions,
                total_actions=len(actions),
                error=None,
                requires_human_intervention=False,
                # Phase 4.6
                failed_action=None,
                failure_reason=None,
                resume_available=False,
                resume_count=resume_count,
                resumed_at=resumed_at,
                serialized_actions=serialized_actions,
                context=context or {},
                results=results,
                started_at=started_at,
                completed_at=now_iso,
                execution_time_seconds=elapsed,
                applications=applications,
                actions_detail=actions_detail,
                all_actions=actions_detail,
            )
        finally:
            await active_executor.cleanup()


# Singleton instance for general use
automation_engine = AutomationEngine()



