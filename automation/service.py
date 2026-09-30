import logging
from typing import Optional, Dict, Any, List

from ai.models import WorkflowProposal
from automation.models import AutomationExecution
from automation.engine import automation_engine, AutomationEngine
from automation.executor import ActionExecutor

logger = logging.getLogger(__name__)


class AutomationService:
    """
    Internal service layer managing workflow automation executions and history.
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
        self._executions[execution.execution_id] = execution
        return execution


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
