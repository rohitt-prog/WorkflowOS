"""
WorkFlowOS Phase 7.1: Central Integration Registry

Provides a decoupled, centralized registry for discovering, registering,
inspecting, and dispatching actions to integration adapters without coupling
to any specific third-party service.
"""

import logging
from typing import Dict, Any, Optional, List

from integrations.base import BaseIntegrationAdapter
from integrations.models import (
    IntegrationSummary,
    IntegrationActionResult,
    DuplicateIntegrationError,
    UnknownIntegrationError,
)

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    """
    Central registry for managing integration adapters in WorkFlowOS.
    """

    def __init__(self):
        self._adapters: Dict[str, BaseIntegrationAdapter] = {}

    def register(self, adapter: BaseIntegrationAdapter) -> None:
        """
        Registers an integration adapter.
        Prevents duplicate registrations by raising DuplicateIntegrationError.
        """
        if adapter.id in self._adapters:
            err_msg = f"Integration with ID '{adapter.id}' is already registered."
            logger.error(err_msg)
            raise DuplicateIntegrationError(err_msg)

        self._adapters[adapter.id] = adapter
        logger.info(
            f"[IntegrationRegistry] Registered adapter: '{adapter.id}' ({adapter.name}, is_mock={adapter.metadata.is_mock})"
        )

    def unregister(self, integration_id: str) -> bool:
        """
        Unregisters an adapter by ID.
        """
        if integration_id in self._adapters:
            del self._adapters[integration_id]
            logger.info(f"[IntegrationRegistry] Unregistered adapter: '{integration_id}'")
            return True
        return False

    def get(self, integration_id: str) -> Optional[BaseIntegrationAdapter]:
        """
        Retrieves an integration adapter by ID or returns None.
        """
        return self._adapters.get(integration_id)

    def get_or_raise(self, integration_id: str) -> BaseIntegrationAdapter:
        """
        Retrieves an integration adapter by ID or raises UnknownIntegrationError.
        """
        adapter = self._adapters.get(integration_id)
        if not adapter:
            raise UnknownIntegrationError(f"Integration with ID '{integration_id}' is not registered.")
        return adapter

    def list_all(self) -> List[BaseIntegrationAdapter]:
        """
        Returns all registered integration adapters.
        """
        return list(self._adapters.values())

    def get_summaries(self) -> List[IntegrationSummary]:
        """
        Returns serializable summary snapshots of all registered integrations.
        """
        return [adapter.to_summary() for adapter in self._adapters.values()]

    async def route_action(
        self,
        integration_id: str,
        action_name: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> IntegrationActionResult:
        """
        Dispatches an action to the appropriate adapter with structured error containment.
        """
        adapter = self.get(integration_id)
        if not adapter:
            return IntegrationActionResult(
                action_name=action_name,
                success=False,
                message=f"Integration '{integration_id}' is not registered.",
                error_code="UNKNOWN_INTEGRATION",
            )

        return await adapter.execute_action(
            action_name=action_name,
            parameters=parameters,
            context=context,
        )


# Global singleton registry
integration_registry = IntegrationRegistry()
