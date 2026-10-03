"""
WorkFlowOS Phase 7.1: Workflow Engine Integration Executor

Bridges the workflow execution engine with the integration foundation,
dispatching workflow actions targeting integration adapters while preserving
telemetry, execution policies, error mapping, and human-in-the-loop recovery.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from automation.models import AutomationAction, ExecutionActionResult
from automation.executor import ActionExecutor
from integrations.registry import integration_registry, IntegrationRegistry

logger = logging.getLogger(__name__)


class IntegrationExecutor(ActionExecutor):
    """
    ActionExecutor implementation that routes workflow action steps to registered
    integration adapters via the IntegrationRegistry.
    """

    def __init__(self, registry: Optional[IntegrationRegistry] = None):
        self.registry = registry or integration_registry

    def _extract_integration_id(self, application: str) -> str:
        """Extracts integration ID from application string (e.g. 'integration:mock_service' -> 'mock_service')."""
        if application.startswith("integration:"):
            return application.split(":", 1)[1].strip()
        return application.strip()

    def is_integration_action(self, action: AutomationAction) -> bool:
        """Determines if the given action targets a registered integration adapter."""
        target_id = self._extract_integration_id(action.application)
        return self.registry.get(target_id) is not None

    async def execute(
        self,
        action: AutomationAction,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionActionResult:
        """
        Executes a workflow action step on an integration adapter.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        integration_id = self._extract_integration_id(action.application)
        adapter = self.registry.get(integration_id)

        if not adapter:
            err_msg = (
                f"Action '{action.id}' targets unknown integration '{integration_id}'. "
                f"Available integrations: {[a.id for a in self.registry.list_all()]}"
            )
            logger.error(f"[IntegrationExecutor] {err_msg}")
            return ExecutionActionResult(
                action_id=action.id,
                action_type=action.type,
                success=False,
                message=err_msg,
                timestamp=now_iso,
            )

        logger.info(
            f"[IntegrationExecutor] Dispatching action '{action.type}' to adapter '{integration_id}'..."
        )

        res = await self.registry.route_action(
            integration_id=integration_id,
            action_name=action.type,
            parameters=action.parameters,
            context=context,
        )

        return ExecutionActionResult(
            action_id=action.id,
            action_type=action.type,
            success=res.success,
            message=res.message,
            data=res.data,
            timestamp=res.timestamp or now_iso,
        )
