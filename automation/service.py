import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from ai.models import WorkflowProposal
from automation.models import AutomationExecution, AutomationStatus, is_valid_transition
from automation.engine import automation_engine, AutomationEngine, InvalidStateTransitionError
from automation.executor import ActionExecutor

logger = logging.getLogger(__name__)


class AutomationService:
    """
    Internal service layer managing workflow automation executions and history.

    Phase 4.6 adds:
    - resume_execution(): validate PAUSED state, find failed action index, delegate to engine
    - cancel_execution(): validate PAUSED state, transition to CANCELLED, record timestamp
    """

    def __init__(self, engine: Optional[AutomationEngine] = None):
        self._engine = engine or automation_engine
        self._executions: Dict[str, AutomationExecution] = {}

    async def run_workflow(
        self,
        proposal: WorkflowProposal,
        approved: bool = False,
        executor: Optional[ActionExecutor] = None,
        executor_type: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AutomationExecution:
        """
        Executes a workflow proposal through the automation engine and records the run.
        Supports concrete PlaywrightExecutor selection for Phase 4.4 and NoOpExecutor for testing.
        """
        active_executor = executor
        if active_executor is None and executor_type:
            if executor_type.lower() == "playwright":
                from automation.playwright_executor import PlaywrightExecutor
                active_executor = PlaywrightExecutor()
            elif executor_type.lower() == "noop":
                from automation.executor import NoOpExecutor
                fail_actions = (parameters or {}).get("fail_actions") or (context or {}).get("fail_actions")
                active_executor = NoOpExecutor(fail_actions=fail_actions)

        execution = await self._engine.execute_workflow(
            proposal=proposal,
            approved=approved,
            executor=active_executor,
            parameters=parameters,
            context=context,
        )
        execution = execution.model_copy(update={
            "executor_type": executor_type or "playwright",
            "context": context or {},
        })
        self._executions[execution.execution_id] = execution
        return execution

    async def resume_execution(
        self,
        execution_id: str,
        executor: Optional[ActionExecutor] = None,
        executor_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> AutomationExecution:
        """
        Phase 4.6: Resume a PAUSED execution from the failed action.

        Validates the execution exists and is in PAUSED state with resume_available=True.
        Locates the failed action index, then delegates to engine.execute_from_index().

        :raises KeyError: If execution not found.
        :raises InvalidStateTransitionError: If execution is not PAUSED or not resumable.
        """
        execution = self._executions.get(execution_id)
        if not execution:
            raise KeyError(f"Execution '{execution_id}' not found.")

        if execution.status != AutomationStatus.PAUSED:
            raise InvalidStateTransitionError(
                f"Cannot resume execution '{execution_id}': "
                f"current status is '{execution.status}'. Only PAUSED executions can be resumed."
            )

        if not execution.resume_available:
            raise InvalidStateTransitionError(
                f"Cannot resume execution '{execution_id}': resume_available is False."
            )

        merged_context = dict(execution.context or {})
        if context:
            merged_context.update(context)

        # Determine the index to resume from (the failed action, so it is retried)
        failed_action_type = execution.failed_action
        actions = execution.serialized_actions  # list of dicts from model_dump()
        start_index = 0
        if failed_action_type and actions:
            for idx, act in enumerate(actions):
                if act.get("type") == failed_action_type:
                    start_index = idx
                    break

        logger.info(
            f"AutomationService: resuming execution '{execution_id}' "
            f"from index {start_index} (failed_action='{failed_action_type}')"
        )

        # Resolve executor
        active_executor = executor
        resolved_type = executor_type or execution.executor_type or "playwright"
        if active_executor is None:
            if resolved_type.lower() == "playwright":
                from automation.playwright_executor import PlaywrightExecutor
                active_executor = PlaywrightExecutor()
            elif resolved_type.lower() == "noop":
                from automation.executor import NoOpExecutor
                fail_actions = merged_context.get("fail_actions")
                active_executor = NoOpExecutor(fail_actions=fail_actions)

        updated = await self._engine.execute_from_index(
            execution=execution,
            start_index=start_index,
            executor=active_executor,
            context=merged_context,
            parameters=parameters,
        )

        updated = updated.model_copy(update={
            "executor_type": resolved_type,
            "context": merged_context,
        })
        self._executions[execution_id] = updated
        return updated

    def cancel_execution(self, execution_id: str) -> AutomationExecution:
        """
        Phase 4.6: Cancel a PAUSED execution.

        Validates the execution exists and is in PAUSED state.
        Sets status to CANCELLED, marks resume_available=False, records cancelled_at.

        :raises KeyError: If execution not found.
        :raises InvalidStateTransitionError: If state transition is invalid.
        """
        execution = self._executions.get(execution_id)
        if not execution:
            raise KeyError(f"Execution '{execution_id}' not found.")

        if not is_valid_transition(execution.status, AutomationStatus.CANCELLED):
            raise InvalidStateTransitionError(
                f"Cannot cancel execution '{execution_id}': "
                f"invalid state transition {execution.status} → CANCELLED. "
                f"Only PAUSED, RUNNING, or PENDING executions can be cancelled."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        logger.info(f"AutomationService: cancelling execution '{execution_id}'")

        # Mutate in-place using model_copy (Pydantic v2)
        cancelled = execution.model_copy(update={
            "status": AutomationStatus.CANCELLED,
            "resume_available": False,
            "requires_human_intervention": False,
            "cancelled_at": now_iso,
            "completed_at": now_iso,
        })
        self._executions[execution_id] = cancelled
        return cancelled

    def get_execution(self, execution_id: str) -> Optional[AutomationExecution]:
        """
        Retrieves a recorded execution run by its ID.
        """
        return self._executions.get(execution_id)

    def list_executions(self) -> List[AutomationExecution]:
        """
        Returns all recorded execution runs.
        """
        return list(self._executions.values())


# Singleton instance
automation_service = AutomationService()

