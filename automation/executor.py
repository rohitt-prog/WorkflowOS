import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from automation.models import AutomationAction, ExecutionActionResult

logger = logging.getLogger(__name__)


class ActionExecutor(ABC):
    """
    Abstract interface for executing individual workflow actions.

    Phase 4.2 provides NoOpExecutor for testing engine logic and validation
    without browser interactions.
    Phase 4.3 will implement PlaywrightExecutor to interact with web applications.
    """

    @abstractmethod
    async def execute(
        self,
        action: AutomationAction,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionActionResult:
        """
        Executes a single AutomationAction step.

        :param action: The action to execute.
        :param context: Optional execution context or variables.
        :return: ExecutionActionResult detailing success or failure.
        """
        pass

    async def start(self) -> None:
        """Optional hook invoked before beginning a workflow sequence."""
        pass

    async def cleanup(self) -> None:
        """Optional hook invoked after a workflow sequence completes or fails."""
        pass


class NoOpExecutor(ActionExecutor):
    """
    No-operation placeholder executor for Phase 4.2.

    Validates action structures and confirms execution flow without
    launching browsers or interacting with external systems.
    """

    def __init__(self, fail_actions: Optional[List[str]] = None):
        """
        :param fail_actions: Optional list of action types to simulate failure for testing.
        """
        self.fail_actions = fail_actions or []

    async def execute(
        self,
        action: AutomationAction,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionActionResult:
        now_iso = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"[NoOpExecutor] Validating action {action.id}: '{action.type}' on '{action.application}'"
        )

        # Allow tests to simulate action failure
        if action.type in self.fail_actions:
            logger.warning(
                f"[NoOpExecutor] Simulated failure triggered for action '{action.type}'"
            )
            return ExecutionActionResult(
                action_id=action.id,
                action_type=action.type,
                success=False,
                message=f"Simulated execution failure on action '{action.type}'",
                timestamp=now_iso,
            )

        return ExecutionActionResult(
            action_id=action.id,
            action_type=action.type,
            success=True,
            message=f"Action '{action.type}' validated; execution deferred to Playwright executor",
            timestamp=now_iso,
        )
