"""
WorkFlowOS Phase 7.1: Central Integration Registry

Provides a decoupled, centralized registry for discovering, registering,
inspecting, and dispatching actions to integration adapters without coupling
to any specific third-party service.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple

from integrations.base import BaseIntegrationAdapter
from integrations.models import (
    IntegrationSummary,
    IntegrationActionResult,
    DuplicateIntegrationError,
    UnknownIntegrationError,
    UnsupportedActionError,
    ApplicationHealth,
    ApplicationCapability,
    ApplicationSummary,
)

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    """
    Central registry for managing integration adapters and application ecosystem in WorkFlowOS.
    """

    def __init__(self):
        self._adapters: Dict[str, BaseIntegrationAdapter] = {}
        self._aliases: Dict[str, str] = {
            "demo_crm": "crm",
            "demo_chat": "chat",
            "slack": "chat",
        }

    def register_alias(self, alias: str, target_id: str) -> None:
        """Registers a case-insensitive application ID alias."""
        self._aliases[alias.strip().lower()] = target_id.strip().lower()

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
        Retrieves an integration adapter by ID (case-insensitive) or alias, or returns None.
        """
        if not integration_id:
            return None
        lower_id = integration_id.strip().lower()
        if lower_id in self._adapters:
            return self._adapters[lower_id]
        for aid, adapter in self._adapters.items():
            if aid.lower() == lower_id:
                return adapter
        # Check registered alias mapping
        if lower_id in self._aliases:
            target_id = self._aliases[lower_id]
            if target_id in self._adapters:
                return self._adapters[target_id]
            for aid, adapter in self._adapters.items():
                if aid.lower() == target_id:
                    return adapter
        return None

    def find_adapter_by_action(self, action_name: str) -> Optional[BaseIntegrationAdapter]:
        """Finds a registered adapter that declares the specified action name."""
        if not action_name:
            return None
        norm_name = action_name.strip().lower()
        for adapter in self._adapters.values():
            if norm_name in [a.lower() for a in adapter.declared_action_names]:
                return adapter
        return None

    def get_or_raise(self, integration_id: str) -> BaseIntegrationAdapter:
        """
        Retrieves an integration adapter by ID or raises UnknownIntegrationError.
        """
        adapter = self.get(integration_id)
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

    # ── Phase 13 Application Ecosystem Methods ────────────────────────────────

    def list_applications(self) -> List[BaseIntegrationAdapter]:
        """Returns all registered application adapters."""
        return list(self._adapters.values())

    def get_application(self, application_id: str) -> Optional[BaseIntegrationAdapter]:
        """Retrieves an application adapter by ID or alias."""
        return self.get(application_id)

    def list_capabilities(self, application_id: Optional[str] = None) -> List[ApplicationCapability]:
        """
        Returns all declared capabilities across all registered applications,
        or for a specific application if application_id is provided.
        """
        if application_id:
            adapter = self.get(application_id)
            return adapter.capabilities() if adapter else []

        all_caps: List[ApplicationCapability] = []
        for adapter in self._adapters.values():
            all_caps.extend(adapter.capabilities())
        return all_caps

    def _resolve_app_and_action(
        self,
        arg1: str,
        arg2: Optional[str] = None,
        application_id: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> Tuple[Optional[str], str]:
        target_app = app_id or application_id
        if target_app:
            return target_app.strip(), arg1.strip()
        if arg2 is not None:
            # We have two positional/keyword arguments: arg1 and arg2
            # E.g. ("crm", "update_customer") or ("update_customer", "crm")
            if self.get(arg1) is not None:
                return arg1.strip(), arg2.strip()
            elif self.get(arg2) is not None:
                return arg2.strip(), arg1.strip()
            return arg2.strip(), arg1.strip()
        # Single argument: might be "crm.update_customer"
        if "." in arg1:
            parts = arg1.strip().split(".", 1)
            return parts[0].strip(), parts[1].strip()
        return None, arg1.strip()

    def get_capability(
        self,
        action_id_or_name: str,
        application_id: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> Optional[ApplicationCapability]:
        """
        Retrieves ApplicationCapability by canonical ID ('app.action')
        or by action verb with optional application context.
        Supports both (app, action) and (action, app) call orders.
        """
        if not action_id_or_name:
            return None

        target_app, clean_name = self._resolve_app_and_action(
            action_id_or_name, arg2=application_id, app_id=app_id
        )

        if target_app:
            adapter = self.get(target_app)
            if adapter:
                for cap in adapter.capabilities():
                    if (
                        cap.name.lower() == clean_name.lower()
                        or cap.action_id.lower() == clean_name.lower()
                        or cap.action_id.lower() == f"{target_app.lower()}.{clean_name.lower()}"
                    ):
                        return cap
            return None

        # Search across all applications
        for adapter in self._adapters.values():
            for cap in adapter.capabilities():
                if cap.name.lower() == clean_name.lower() or cap.action_id.lower() == clean_name.lower():
                    return cap

        return None

    def get_capability_or_raise(
        self,
        action_id_or_name: str,
        application_id: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> ApplicationCapability:
        """
        Retrieves ApplicationCapability or raises appropriate structured error:
        - UnknownIntegrationError if specified application is not registered.
        - UnsupportedActionError if action is not supported.
        """
        if not action_id_or_name:
            raise UnsupportedActionError("Action identifier cannot be empty.")

        target_app, clean_name = self._resolve_app_and_action(
            action_id_or_name, arg2=application_id, app_id=app_id
        )

        if target_app:
            adapter = self.get(target_app)
            if not adapter:
                raise UnknownIntegrationError(f"Application '{target_app}' is not registered.")
            for cap in adapter.capabilities():
                if (
                    cap.name.lower() == clean_name.lower()
                    or cap.action_id.lower() == clean_name.lower()
                    or cap.action_id.lower() == f"{target_app.lower()}.{clean_name.lower()}"
                ):
                    return cap
            raise UnsupportedActionError(
                f"Action '{clean_name}' is not supported by application '{target_app}'."
            )

        for adapter in self._adapters.values():
            for cap in adapter.capabilities():
                if cap.name.lower() == clean_name.lower() or cap.action_id.lower() == clean_name.lower():
                    return cap

        raise UnsupportedActionError(
            f"Action '{clean_name}' is not supported by any registered application."
        )

    def is_action_mutating(
        self,
        action_name: str,
        application_id: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> bool:
        """
        Determines if an action mutates state.
        Returns True for verified mutating capabilities or canonical mutating names.
        Returns False for read-only actions and unverified unknown actions.
        NOTE: Returning False does NOT imply the action is read-only.
        """
        target_app, clean_name = self._resolve_app_and_action(
            action_name, arg2=application_id, app_id=app_id
        )
        cap = self.get_capability(clean_name, application_id=target_app)
        if cap is not None:
            return cap.mutating
        canonical_mutating = {
            "update_customer",
            "send_message",
            "create_record",
            "delete_record",
            "modify_record",
            "simulate_mutating_write",
        }
        return clean_name.lower() in canonical_mutating

    def is_action_read_only(
        self,
        action_name: str,
        application_id: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> bool:
        """
        Determines if an action is safe / read-only.
        SAFETY REQUIREMENTS:
        - Must return True ONLY for verified, registered read-only capabilities.
        - Must return False for mutating actions AND unknown/unsupported actions.
        - Unknown actions MUST NOT be classified as read-only.
        """
        target_app, clean_name = self._resolve_app_and_action(
            action_name, arg2=application_id, app_id=app_id
        )
        cap = self.get_capability(clean_name, application_id=target_app)
        if cap is not None:
            return cap.read_only
        return False

    def requires_approval(
        self,
        action_name: str,
        application_id: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> bool:
        """
        CRITICAL SAFETY CHECK:
        Returns True if action requires mandatory human approval.
        SAFETY REQUIREMENTS:
        - Always returns True for any mutating action.
        - Returns False ONLY for verified, registered read-only actions.
        - FAILS CLOSED (returns True) for any unknown or unsupported action so it cannot bypass approval.
        """
        target_app, clean_name = self._resolve_app_and_action(
            action_name, arg2=application_id, app_id=app_id
        )
        cap = self.get_capability(clean_name, application_id=target_app)
        if cap is not None:
            return cap.requires_approval
        # Unknown/unsupported action: fail-closed safety gate
        return True

    def get_application_health(self, application_id: str) -> Optional[ApplicationHealth]:
        """Returns current lightweight health status for target application."""
        adapter = self.get(application_id)
        if not adapter:
            return None
        return adapter.health()

    def get_application_summaries(self) -> List[ApplicationSummary]:
        """Returns serializable application summaries for all registered ecosystem applications."""
        return [adapter.to_application_summary() for adapter in self._adapters.values()]


# Global singleton integration registry
integration_registry = IntegrationRegistry()


class ApplicationRegistry:
    """
    Dedicated Phase 13 Application Ecosystem Registry.
    Provides deterministic discovery, capability lookup, and health inspection.
    """

    def __init__(self, integration_reg: Optional[IntegrationRegistry] = None):
        self._registry = integration_reg or integration_registry

    def register(self, adapter: BaseIntegrationAdapter) -> None:
        self._registry.register(adapter)

    def unregister(self, integration_id: str) -> None:
        self._registry.unregister(integration_id)

    def list_applications(self) -> List[BaseIntegrationAdapter]:
        return self._registry.list_applications()

    def get_application(self, application_id: str) -> Optional[BaseIntegrationAdapter]:
        return self._registry.get_application(application_id)

    def list_capabilities(self, application_id: Optional[str] = None) -> List[ApplicationCapability]:
        return self._registry.list_capabilities(application_id)

    def get_capability(
        self,
        action_id_or_name: str,
        application_id: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> Optional[ApplicationCapability]:
        return self._registry.get_capability(action_id_or_name, application_id=application_id, app_id=app_id)

    def get_capability_or_raise(
        self,
        action_id_or_name: str,
        application_id: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> ApplicationCapability:
        return self._registry.get_capability_or_raise(action_id_or_name, application_id=application_id, app_id=app_id)

    def is_action_mutating(
        self,
        action_name: str,
        application_id: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> bool:
        return self._registry.is_action_mutating(action_name, application_id=application_id, app_id=app_id)

    def is_action_read_only(
        self,
        action_name: str,
        application_id: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> bool:
        return self._registry.is_action_read_only(action_name, application_id=application_id, app_id=app_id)

    def requires_approval(
        self,
        action_name: str,
        application_id: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> bool:
        return self._registry.requires_approval(action_name, application_id=application_id, app_id=app_id)

    def get_application_health(self, application_id: str) -> Optional[ApplicationHealth]:
        return self._registry.get_application_health(application_id)

    def get_health(self, application_id: str) -> Optional[ApplicationHealth]:
        return self._registry.get_application_health(application_id)

    def get_application_summaries(self) -> List[ApplicationSummary]:
        return self._registry.get_application_summaries()

    def get_summaries(self) -> List[ApplicationSummary]:
        return self._registry.get_application_summaries()


# Global singleton application registry
application_registry = ApplicationRegistry(integration_registry)
