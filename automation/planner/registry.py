"""
WorkFlowOS Phase 10: Strategy Capability Registry

Provides a lightweight, deterministic registry describing what each automation
strategy can handle, reflecting actual capabilities available in the repository.

Does NOT introduce fake adapters or speculative capabilities:
- API: Real API/direct-execution endpoints and adapters in integration_registry
- INTEGRATION: Registered adapters in integration_registry
- SEMANTIC_UI: Declared in hierarchy, but marked unavailable unless a real semantic provider exists
- BROWSER: Verified Playwright-supported actions and demo web applications
- MANUAL: Universal fallback requiring human intervention
"""

import logging
from typing import Dict, Any, Optional, Set, Tuple
from automation.planner.models import AutomationStrategyType
from integrations.registry import integration_registry, IntegrationRegistry
from automation.playwright_executor import PLAYWRIGHT_SUPPORTED_ACTIONS
from automation.engine import SUPPORTED_ACTION_TYPES

logger = logging.getLogger(__name__)

# Applications considered web/browser-based in WorkFlowOS demo ecosystem
KNOWN_WEB_APPLICATIONS: Set[str] = {
    "demo_email",
    "demo_crm",
    "demo_chat",
    "web",
    "browser",
    "webapp",
    "workflow_system",
}

# Actions inherently compatible with direct API execution
API_ACTION_PATTERNS: Set[str] = {
    "simulate_ping",
    "mock_echo",
    "list_recent_messages",
    "get_customer",
    "api_request",
    "webhook_call",
}


class StrategyCapabilityRegistry:
    """
    Registry that inspects an action and application against actual system capabilities
    to determine which automation strategies are genuinely available.
    """

    def __init__(self, registry: Optional[IntegrationRegistry] = None):
        self._integration_registry = registry or integration_registry
        self._semantic_providers: Dict[str, Any] = {}

    def register_semantic_provider(self, name: str, provider: Any) -> None:
        """Hook to register a real accessibility/semantic UI provider if one exists."""
        self._semantic_providers[name] = provider

    def _extract_app_id(self, application: str, action: str) -> str:
        """Normalizes application identifier."""
        if not application:
            return ""
        norm = application.strip().lower()
        if norm.startswith("integration:"):
            return norm.split(":", 1)[1].strip()
        return norm

    def is_api_capable(
        self,
        action: str,
        application: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], bool, bool]:
        """
        Determines if API strategy is capable of executing this action.
        Returns: (is_capable, rejection_reason, is_mutating, credentials_available)
        """
        app_id = self._extract_app_id(application, action)
        norm_action = (action or "").strip().lower()

        # Check if explicitly overridden in context
        ctx = context or {}
        api_override = ctx.get("api_available")
        if api_override is not None:
            if not api_override:
                return False, "API strategy marked unavailable in context", False, False
            return True, None, False, ctx.get("credentials_available", True)

        # Check adapter in registry
        adapter = self._integration_registry.get(app_id) if app_id else self._integration_registry.find_adapter_by_action(norm_action)
        if adapter:
            action_def = adapter.get_action(norm_action)
            if action_def:
                # API strategy requires allow_direct_execution or safe read API
                if action_def.allow_direct_execution or (not action_def.is_mutating and action_def.is_safe):
                    # Check credentials
                    needs_creds = len(action_def.required_scopes) > 0 or not adapter.metadata.is_mock
                    creds_avail = adapter.is_connected or not needs_creds or ctx.get("credentials_available", False)
                    return True, None, action_def.is_mutating, creds_avail
                else:
                    return False, f"Action '{action}' on '{adapter.id}' requires managed integration context rather than direct API", action_def.is_mutating, True

        # Check known API actions
        if norm_action in API_ACTION_PATTERNS or "api" in app_id:
            creds_avail = ctx.get("credentials_available", True)
            return True, None, False, creds_avail

        # Known web applications with email actions mapped to Gmail API
        if norm_action in ("open_email", "list_recent_messages", "search_email") and (app_id in ("demo_email", "gmail", "email")):
            gmail_adapter = self._integration_registry.get("gmail")
            if gmail_adapter:
                creds_avail = gmail_adapter.is_connected or ctx.get("credentials_available", False)
                return True, None, False, creds_avail

        return False, f"No direct API adapter available for action '{action}' on '{application}'", False, True

    def is_integration_capable(
        self,
        action: str,
        application: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], bool, bool]:
        """
        Determines if INTEGRATION strategy is capable of executing this action.
        Returns: (is_capable, rejection_reason, is_mutating, credentials_available)
        """
        app_id = self._extract_app_id(application, action)
        norm_action = (action or "").strip().lower()

        ctx = context or {}
        int_override = ctx.get("integration_available")
        if int_override is not None:
            if not int_override:
                return False, "Integration strategy marked unavailable in context", False, False
            return True, None, False, ctx.get("credentials_available", True)

        adapter = self._integration_registry.get(app_id) if app_id else self._integration_registry.find_adapter_by_action(norm_action)
        if adapter:
            action_def = adapter.get_action(norm_action)
            if action_def:
                is_mut = action_def.is_mutating
                needs_creds = len(action_def.required_scopes) > 0 or not adapter.metadata.is_mock
                creds_avail = adapter.is_connected or not needs_creds or ctx.get("credentials_available", False)
                return True, None, is_mut, creds_avail
            return False, f"Action '{action}' is not supported by integration '{adapter.id}'", False, True

        # Check if mapped to CRM / mock / email adapter
        if norm_action in ("search_customer", "update_customer") and (app_id in ("demo_crm", "mock_crm", "crm")):
            # If a mock CRM or custom adapter is registered
            mock_adapter = self._integration_registry.get("mock_service")
            if mock_adapter:
                return True, None, (norm_action == "update_customer"), True

        return False, f"No registered integration adapter for '{application}' or action '{action}'", False, True

    def is_semantic_ui_capable(
        self,
        action: str,
        application: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], bool, bool]:
        """
        Determines if SEMANTIC_UI strategy is capable.
        Reflects actual repository state: no fake accessibility adapter is created.
        """
        ctx = context or {}
        if ctx.get("semantic_ui_available", False) and self._semantic_providers:
            return True, None, False, True
        return False, "No accessibility or semantic UI automation provider registered", False, True

    def is_browser_capable(
        self,
        action: str,
        application: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], bool, bool]:
        """
        Determines if BROWSER strategy is capable of executing this action.
        Returns: (is_capable, rejection_reason, is_mutating, credentials_available)
        """
        norm_action = (action or "").strip().lower()
        app_id = self._extract_app_id(application, action)

        ctx = context or {}
        browser_override = ctx.get("browser_available")
        if browser_override is not None:
            if not browser_override:
                return False, "Browser strategy marked unavailable in context", False, True
            return True, None, False, True

        # Supported Playwright action verbs
        if norm_action in PLAYWRIGHT_SUPPORTED_ACTIONS:
            return True, None, (norm_action in ("update_customer", "send_message")), True

        # Generic web actions on known web applications
        if (app_id in KNOWN_WEB_APPLICATIONS or "browser" in app_id or "web" in app_id) and norm_action in {
            "click", "fill", "navigate", "press", "wait", "screenshot", "hover", "select",
        }:
            return True, None, False, True

        return False, f"Action '{action}' on '{application}' is not a supported browser action", False, True

    def is_manual_capable(
        self,
        action: str,
        application: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], bool, bool]:
        """
        MANUAL is always available as the universal human-in-the-loop fallback.
        """
        return True, None, False, True

    def get_capabilities_for_step(
        self,
        action: str,
        application: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[AutomationStrategyType, Dict[str, Any]]:
        """
        Evaluates all strategies for a given workflow step.
        Returns a dict mapping each strategy to capability and metadata details.
        """
        results = {}

        # 1. API
        api_cap, api_rej, api_mut, api_creds = self.is_api_capable(action, application, context)
        results[AutomationStrategyType.API] = {
            "is_available": api_cap,
            "rejection_reason": api_rej,
            "is_mutating": api_mut,
            "requires_credentials": True if "gmail" in application.lower() else False,
            "credentials_available": api_creds,
        }

        # 2. INTEGRATION
        int_cap, int_rej, int_mut, int_creds = self.is_integration_capable(action, application, context)
        results[AutomationStrategyType.INTEGRATION] = {
            "is_available": int_cap,
            "rejection_reason": int_rej,
            "is_mutating": int_mut,
            "requires_credentials": False if "mock" in application.lower() else True,
            "credentials_available": int_creds,
        }

        # 3. SEMANTIC_UI
        sem_cap, sem_rej, sem_mut, sem_creds = self.is_semantic_ui_capable(action, application, context)
        results[AutomationStrategyType.SEMANTIC_UI] = {
            "is_available": sem_cap,
            "rejection_reason": sem_rej,
            "is_mutating": sem_mut,
            "requires_credentials": False,
            "credentials_available": sem_creds,
        }

        # 4. BROWSER
        br_cap, br_rej, br_mut, br_creds = self.is_browser_capable(action, application, context)
        results[AutomationStrategyType.BROWSER] = {
            "is_available": br_cap,
            "rejection_reason": br_rej,
            "is_mutating": br_mut,
            "requires_credentials": False,
            "credentials_available": br_creds,
        }

        # 5. MANUAL
        man_cap, man_rej, man_mut, man_creds = self.is_manual_capable(action, application, context)
        results[AutomationStrategyType.MANUAL] = {
            "is_available": man_cap,
            "rejection_reason": man_rej,
            "is_mutating": man_mut,
            "requires_credentials": False,
            "credentials_available": man_creds,
        }

        return results


# Global singleton capability registry
capability_registry = StrategyCapabilityRegistry()
