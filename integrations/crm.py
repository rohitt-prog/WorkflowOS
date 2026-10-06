"""
WorkFlowOS Phase 13: CRM Application Adapter

Implements the BaseIntegrationAdapter interface for the WorkFlowOS CRM application.
Exposes deterministic customer operations:
- search_customer (read-only)
- get_customer (read-only)
- update_customer (mutating — requires human approval)
"""

import copy
import logging
from typing import Dict, Any, Optional, List

from integrations.base import BaseIntegrationAdapter
from integrations.models import (
    IntegrationMetadata,
    IntegrationStatus,
    IntegrationActionDefinition,
    ActionParameterDefinition,
    ParameterType,
    IntegrationActionResult,
    IntegrationValidationError,
)

logger = logging.getLogger(__name__)

DEFAULT_CRM_CUSTOMERS: Dict[str, Dict[str, Any]] = {
    "rahul": {
        "id": "cust_rahul_01",
        "name": "Rahul Sharma",
        "email": "rahul.sharma@example.com",
        "company": "Acme Corp",
        "tier": "Standard",
        "notes": "Interested in enterprise workflow automation.",
        "status": "Active",
    },
    "alice": {
        "id": "cust_alice_02",
        "name": "Alice Smith",
        "email": "alice.smith@example.com",
        "company": "TechStart Inc",
        "tier": "Premium",
        "notes": "Existing customer with priority support.",
        "status": "Active",
    },
    "acme": {
        "id": "cust_acme_03",
        "name": "Acme Corp",
        "email": "contact@acme.com",
        "company": "Acme Corp",
        "tier": "Enterprise",
        "notes": "Multi-seat enterprise account.",
        "status": "Active",
    },
}


class CrmIntegrationAdapter(BaseIntegrationAdapter):
    """
    CRM Application Adapter for WorkFlowOS.
    Clearly classified as demo/mock; supports both direct integration execution
    and Playwright browser execution against /demo/crm.
    """

    def __init__(self, adapter_id: str = "crm"):
        metadata = IntegrationMetadata(
            id=adapter_id,
            name="WorkFlowOS CRM",
            description="Customer Relationship Management integration for searching profiles and updating records.",
            version="1.0.0",
            category="crm",
            icon="users",
            is_mock=True,
            disclaimer="Demo CRM application for customer operations.",
        )
        super().__init__(metadata=metadata)
        # Demo CRM is available and connected out-of-the-box
        self._status = IntegrationStatus.CONNECTED
        self._customers: Dict[str, Dict[str, Any]] = copy.deepcopy(DEFAULT_CRM_CUSTOMERS)

    def reset_seed_data(self) -> None:
        """Resets in-memory customer records to factory defaults."""
        self._customers = copy.deepcopy(DEFAULT_CRM_CUSTOMERS)

    def _register_capabilities(self) -> None:
        """Declares CRM capabilities and input schemas."""

        # 1. Read-only: search_customer
        self.register_action(
            IntegrationActionDefinition(
                name="search_customer",
                display_name="Search Customer",
                description="Search customer records by customer name, email, or company query.",
                parameters=[
                    ActionParameterDefinition(
                        name="customer_name",
                        type=ParameterType.STRING,
                        required=False,
                        default="",
                        description="Customer name or query string",
                    ),
                    ActionParameterDefinition(
                        name="query",
                        type=ParameterType.STRING,
                        required=False,
                        default="",
                        description="Generic search query filter",
                    ),
                ],
                required_scopes=[],
                is_safe=True,
                is_mutating=False,
                is_destructive=False,
                allow_direct_execution=True,
                supported_strategies=["INTEGRATION", "BROWSER"],
                requires_approval=False,
            ),
            handler=self._handle_search_customer,
        )

        # 2. Read-only: get_customer
        self.register_action(
            IntegrationActionDefinition(
                name="get_customer",
                display_name="Get Customer Profile",
                description="Retrieve customer profile details by unique customer ID or name.",
                parameters=[
                    ActionParameterDefinition(
                        name="customer_id",
                        type=ParameterType.STRING,
                        required=False,
                        default="",
                        description="Unique customer ID (e.g. 'cust_rahul_01')",
                    ),
                    ActionParameterDefinition(
                        name="customer_name",
                        type=ParameterType.STRING,
                        required=False,
                        default="",
                        description="Customer full or partial name",
                    ),
                ],
                required_scopes=[],
                is_safe=True,
                is_mutating=False,
                is_destructive=False,
                allow_direct_execution=True,
                supported_strategies=["API", "INTEGRATION", "BROWSER"],
                requires_approval=False,
            ),
            handler=self._handle_get_customer,
        )

        # 3. Mutating: update_customer (MANDATORY APPROVAL GATE)
        self.register_action(
            IntegrationActionDefinition(
                name="update_customer",
                display_name="Update Customer Record",
                description="Update customer notes, tier, or status in the CRM database.",
                parameters=[
                    ActionParameterDefinition(
                        name="customer",
                        type=ParameterType.STRING,
                        required=False,
                        description="Customer identifier or name to update",
                    ),
                    ActionParameterDefinition(
                        name="customer_name",
                        type=ParameterType.STRING,
                        required=False,
                        description="Customer name to update",
                    ),
                    ActionParameterDefinition(
                        name="customer_id",
                        type=ParameterType.STRING,
                        required=False,
                        description="Customer ID to update",
                    ),
                    ActionParameterDefinition(
                        name="notes",
                        type=ParameterType.STRING,
                        required=False,
                        default=None,
                        description="Updated notes or activity memo",
                    ),
                    ActionParameterDefinition(
                        name="status",
                        type=ParameterType.STRING,
                        required=False,
                        default=None,
                        description="Customer lifecycle status (e.g. 'Active', 'Verified')",
                    ),
                    ActionParameterDefinition(
                        name="tier",
                        type=ParameterType.STRING,
                        required=False,
                        default=None,
                        description="Customer membership tier (e.g. 'Standard', 'VIP')",
                    ),
                    ActionParameterDefinition(
                        name="updates",
                        type=ParameterType.OBJECT,
                        required=False,
                        default=None,
                        description="Key-value mapping of updates to apply",
                    ),
                ],
                required_scopes=[],
                is_safe=False,
                is_mutating=True,
                is_destructive=False,
                allow_direct_execution=True,
                supported_strategies=["INTEGRATION", "BROWSER"],
                requires_approval=True,  # STRICT APPROVAL INVARIANT
            ),
            handler=self._handle_update_customer,
        )

    def _find_customer(self, query: str) -> Optional[Dict[str, Any]]:
        """Case-insensitive customer lookup helper."""
        if not query:
            return None
        q = query.strip().lower()
        # Direct key match
        if q in self._customers:
            return self._customers[q]
        # Match by name, email, or id
        for key, cust in self._customers.items():
            if (
                q in cust.get("name", "").lower()
                or q in cust.get("email", "").lower()
                or q == cust.get("id", "").lower()
                or q in cust.get("company", "").lower()
            ):
                return cust
        return None

    async def _handle_search_customer(
        self, parameters: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Executes read-only customer search."""
        query = str(
            parameters.get("customer_name")
            or parameters.get("customer_id")
            or parameters.get("customer")
            or parameters.get("query")
            or parameters.get("name")
            or parameters.get("id")
            or parameters.get("target")
            or ""
        ).strip()
        if not query and context:
            query = str(
                context.get("customer_name")
                or context.get("customer_id")
                or context.get("customer")
                or context.get("target")
                or context.get("query")
                or context.get("name")
                or context.get("id")
                or ""
            ).strip()

        if query:
            matched = self._find_customer(query)
            if matched:
                return {
                    "found": True,
                    "customer_name": matched["name"],
                    "customer": copy.deepcopy(matched),
                    "customers": [copy.deepcopy(matched)],
                    "count": 1,
                }
            return {
                "found": False,
                "query": query,
                "customers": [],
                "count": 0,
                "message": f"Customer '{query}' not found in CRM.",
            }
        return {
            "found": True,
            "customers": [copy.deepcopy(c) for c in self._customers.values()],
            "count": len(self._customers),
        }

    async def _handle_get_customer(
        self, parameters: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Executes read-only customer profile retrieval."""
        cust_id = str(parameters.get("customer_id") or parameters.get("id") or "").strip()
        cust_name = str(
            parameters.get("customer_name")
            or parameters.get("customer")
            or parameters.get("query")
            or parameters.get("name")
            or parameters.get("target")
            or ""
        ).strip()
        target = cust_id or cust_name
        if not target and context:
            target = str(
                context.get("customer_id")
                or context.get("customer_name")
                or context.get("customer")
                or context.get("target")
                or context.get("query")
                or context.get("name")
                or context.get("id")
                or ""
            ).strip()

        if target:
            matched = self._find_customer(target)
            if not matched:
                raise IntegrationValidationError(f"Customer not found for '{target}' in CRM.")
        else:
            matched = list(self._customers.values())[0] if self._customers else None

        if matched:
            return {
                "success": True,
                "customer": copy.deepcopy(matched),
            }
        raise IntegrationValidationError("No customers available in CRM.")

    async def _handle_update_customer(
        self, parameters: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes mutating customer update.
        SAFETY REQUIREMENT: Handled under approved workflow execution.
        """
        target = str(
            parameters.get("customer_id")
            or parameters.get("customer_name")
            or parameters.get("customer")
            or parameters.get("name")
            or parameters.get("id")
            or parameters.get("query")
            or parameters.get("target")
            or ""
        ).strip()
        if not target and context:
            target = str(
                context.get("customer_id")
                or context.get("customer_name")
                or context.get("customer")
                or context.get("target")
                or context.get("query")
                or context.get("name")
                or context.get("id")
                or ""
            ).strip()
        if not target and self._customers:
            target = list(self._customers.values())[0]["id"]
        if not target:
            raise IntegrationValidationError("Parameter 'customer_name' or 'customer_id' is required to update CRM record.")

        matched = self._find_customer(target)
        if not matched:
            key = target.lower().replace(" ", "_")
            matched = {
                "id": f"cust_{key}",
                "name": target,
                "email": f"{key}@example.com",
                "company": "Customer Company",
                "tier": "Standard",
                "notes": "",
                "status": "Active",
            }
            self._customers[key] = matched

        # Apply updates
        updates = parameters.get("updates")
        if isinstance(updates, dict):
            for k, v in updates.items():
                matched[k] = v

        if parameters.get("notes") is not None:
            matched["notes"] = parameters["notes"]
        if parameters.get("status") is not None:
            matched["status"] = parameters["status"]
        if parameters.get("tier") is not None:
            matched["tier"] = parameters["tier"]

        logger.info(f"[{self.id}] Updated customer record for '{matched['name']}' (status='{matched.get('status')}')")
        return {
            "updated": True,
            "customer_name": matched["name"],
            "status": matched.get("status"),
            "customer": copy.deepcopy(matched),
            "message": f"Customer '{matched['name']}' updated successfully in CRM.",
        }
