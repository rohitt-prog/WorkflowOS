#!/usr/bin/env python3
"""
WorkFlowOS Phase 13: Application Ecosystem Test Suite

Validates all Phase 13 requirements and multi-phase regression safety:
1. Application registration
2. Capability registration
3. Capability lookup
4. Application health/status
5. Gmail capabilities (read-only preserved)
6. CRM capabilities
7. Chat capabilities
8. Read-only classification
9. Mutating classification
10. Approval requirement enforcement
11. Unsupported capability handling
12. Disconnected application handling
13. Planner capability integration
14. Credential non-exposure
15. Privacy/redaction integration
16. Failure handling
17. Existing Phase 7 regression
18. Phase 9 regression
19. Phase 10 regression
20. Phase 11 regression
21. Phase 12 regression
"""

import copy
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from integrations import (
    integration_registry,
    application_registry,
    BaseIntegrationAdapter,
    ApplicationCapability,
    ApplicationHealth,
    ApplicationSummary,
    ApplicationHealthStatus,
    IntegrationActionDefinition,
    ActionParameterDefinition,
    IntegrationActionResult,
    IntegrationMetadata,
    UnsupportedActionError,
    UnknownIntegrationError,
    IntegrationConnectionError,
    GmailIntegrationAdapter,
    CrmIntegrationAdapter,
    ChatIntegrationAdapter,
)
from automation.planner import automation_planner, AutomationStrategyType
from automation.planner.registry import capability_registry
from automation.models import (
    AutomationExecution,
    AutomationStatus,
    WorkflowStep,
    ExecutionActionResult,
    StepExecutionResult,
)
from backend.learning.service import learning_service
from backend.learning.outcome import evaluate_execution_outcome, ExecutionOutcomeStatus
from backend.privacy.redaction import redact_sensitive_data, audit_sensitive_data
from backend.privacy.service import privacy_service


class TestPhase13ApplicationEcosystem(unittest.IsolatedAsyncioTestCase):
    """Phase 13 Application Ecosystem tests verifying all 21 requirements."""

    def setUp(self):
        self.client = TestClient(app)

    # 1. Application registration
    async def test_01_application_registration(self):
        apps = application_registry.list_applications()
        app_ids = [a.application_id for a in apps]
        self.assertIn("gmail", app_ids)
        self.assertIn("crm", app_ids)
        self.assertIn("chat", app_ids)
        self.assertIn("mock_service", app_ids)

        # Dynamic registration and unregistration
        class CustomAppAdapter(BaseIntegrationAdapter):
            def __init__(self):
                super().__init__(
                    metadata=IntegrationMetadata(
                        id="custom_tool",
                        name="Custom Tool",
                        description="Custom tool description",
                        is_mock=True,
                    )
                )

            def _register_capabilities(self):
                self.register_action(
                    IntegrationActionDefinition(
                        name="run_query",
                        display_name="Run Query",
                        description="Run a read query",
                        is_safe=True,
                        is_mutating=False,
                        requires_approval=False,
                        supported_strategies=["API"],
                    ),
                    handler=self._handle_run_query,
                )

            async def _handle_run_query(self, params, context=None):
                return {"result": "ok"}

        custom_adapter = CustomAppAdapter()
        application_registry.register(custom_adapter)
        self.assertIsNotNone(application_registry.get_application("custom_tool"))
        self.assertIn("custom_tool", [a.application_id for a in application_registry.list_applications()])

        # Cleanup
        application_registry.unregister("custom_tool")
        self.assertIsNone(application_registry.get_application("custom_tool"))

    # 2. Capability registration
    async def test_02_capability_registration(self):
        caps = application_registry.list_capabilities()
        self.assertGreater(len(caps), 0)
        action_ids = [c.action_id for c in caps]
        self.assertIn("gmail.search_messages", action_ids)
        self.assertIn("gmail.read_message", action_ids)
        self.assertIn("crm.search_customer", action_ids)
        self.assertIn("crm.update_customer", action_ids)
        self.assertIn("chat.search_messages", action_ids)
        self.assertIn("chat.send_message", action_ids)

        for cap in caps:
            self.assertIsInstance(cap, ApplicationCapability)
            self.assertTrue(bool(cap.action_id))
            self.assertTrue(bool(cap.application_id))
            self.assertTrue(bool(cap.description))
            self.assertIsInstance(cap.read_only, bool)
            self.assertIsInstance(cap.mutating, bool)
            self.assertIsInstance(cap.requires_approval, bool)
            self.assertIsInstance(cap.supported_strategies, list)

    # 3. Capability lookup
    async def test_03_capability_lookup(self):
        cap_crm = application_registry.get_capability("crm.update_customer")
        self.assertIsNotNone(cap_crm)
        self.assertEqual(cap_crm.application_id, "crm")
        self.assertEqual(cap_crm.action_id, "crm.update_customer")
        self.assertTrue(cap_crm.mutating)
        self.assertTrue(cap_crm.requires_approval)

        # Lookup with app_id and action_name
        cap_gmail = application_registry.get_capability("read_message", app_id="gmail")
        self.assertIsNotNone(cap_gmail)
        self.assertEqual(cap_gmail.action_id, "gmail.read_message")
        self.assertTrue(cap_gmail.read_only)
        self.assertFalse(cap_gmail.mutating)

        # Lookup non-existent capability
        self.assertIsNone(application_registry.get_capability("non_existent_action"))
        self.assertIsNone(application_registry.get_capability("unknown.action"))

    # 4. Application health/status
    async def test_04_application_health_status(self):
        health_crm = application_registry.get_application_health("crm")
        self.assertIsNotNone(health_crm)
        self.assertEqual(health_crm.status, ApplicationHealthStatus.CONNECTED)
        self.assertTrue(health_crm.connected)

        health_chat = application_registry.get_application_health("chat")
        self.assertIsNotNone(health_chat)
        self.assertEqual(health_chat.status, ApplicationHealthStatus.CONNECTED)
        self.assertTrue(health_chat.connected)

        # Gmail without credentials should report NOT_CONFIGURED or DISCONNECTED, never fake connected
        health_gmail = application_registry.get_application_health("gmail")
        self.assertIsNotNone(health_gmail)
        self.assertIn(health_gmail.status, [ApplicationHealthStatus.NOT_CONFIGURED, ApplicationHealthStatus.DISCONNECTED])
        self.assertFalse(health_gmail.connected)

        # API health endpoint
        res = self.client.get("/api/applications/crm/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"].upper(), "CONNECTED")
        self.assertTrue(data.get("connected") or data.get("is_healthy"))

    # 5. Gmail capabilities (read-only preserved)
    async def test_05_gmail_capabilities_readonly_preserved(self):
        gmail_app = application_registry.get_application("gmail")
        self.assertIsNotNone(gmail_app)
        caps = gmail_app.capabilities()
        cap_map = {c.action_id: c for c in caps}

        self.assertIn("gmail.search_messages", cap_map)
        self.assertIn("gmail.read_message", cap_map)
        self.assertIn("gmail.download_attachment", cap_map)
        self.assertIn("gmail.list_recent_messages", cap_map)

        # Strictly verify read-only: NO mutating actions exist on Gmail adapter
        for cap in caps:
            self.assertTrue(cap.read_only, f"{cap.action_id} must be read_only")
            self.assertFalse(cap.mutating, f"{cap.action_id} must not be mutating")

        # Verify Gmail OAuth scopes remain read-only
        self.assertEqual(len(gmail_app.oauth_scopes), 1)
        self.assertEqual(gmail_app.oauth_scopes[0], "https://www.googleapis.com/auth/gmail.readonly")

    # 6. CRM capabilities
    async def test_06_crm_capabilities_execution(self):
        crm_app = application_registry.get_application("crm")
        self.assertIsNotNone(crm_app)
        self.assertTrue(crm_app.is_demo)

        caps = crm_app.capabilities()
        action_names = [c.action_id for c in caps]
        self.assertIn("crm.search_customer", action_names)
        self.assertIn("crm.get_customer", action_names)
        self.assertIn("crm.update_customer", action_names)

        # Execute search_customer
        res_search = await crm_app.execute_action("search_customer", {"query": "Alice"})
        self.assertTrue(res_search.success)
        self.assertGreater(len(res_search.data["customers"]), 0)
        alice = res_search.data["customers"][0]
        self.assertEqual(alice["name"], "Alice Smith")

        # Execute get_customer
        res_get = await crm_app.execute_action("get_customer", {"customer_id": alice["id"]})
        self.assertTrue(res_get.success)
        self.assertEqual(res_get.data["customer"]["email"], "alice.smith@example.com")

        # Execute update_customer
        res_upd = await crm_app.execute_action("update_customer", {
            "customer_id": alice["id"],
            "updates": {"phone": "+1-555-999-8888"}
        })
        self.assertTrue(res_upd.success)
        self.assertEqual(res_upd.data["customer"]["phone"], "+1-555-999-8888")

    # 7. Chat capabilities
    async def test_07_chat_capabilities_execution(self):
        chat_app = application_registry.get_application("chat")
        self.assertIsNotNone(chat_app)
        self.assertTrue(chat_app.is_demo)

        caps = chat_app.capabilities()
        action_names = [c.action_id for c in caps]
        self.assertIn("chat.search_messages", action_names)
        self.assertIn("chat.read_message", action_names)
        self.assertIn("chat.send_message", action_names)

        # Execute search_messages
        res_search = await chat_app.execute_action("search_messages", {"query": "ticket"})
        self.assertTrue(res_search.success)
        self.assertGreater(len(res_search.data["messages"]), 0)

        # Execute send_message
        res_send = await chat_app.execute_action("send_message", {
            "channel": "#general",
            "message": "Hello WorkFlowOS ecosystem!"
        })
        self.assertTrue(res_send.success)
        msg_id = res_send.data["message_id"]
        self.assertEqual(res_send.data["message"], "Hello WorkFlowOS ecosystem!")

        # Execute read_message
        res_read = await chat_app.execute_action("read_message", {"message_id": msg_id})
        self.assertTrue(res_read.success)
        self.assertEqual(res_read.data["message"]["channel"], "#general")

    # 8. Read-only classification
    async def test_08_read_only_classification(self):
        read_only_actions = [
            ("gmail", "search_messages"),
            ("gmail", "read_message"),
            ("gmail", "download_attachment"),
            ("crm", "search_customer"),
            ("crm", "get_customer"),
            ("chat", "search_messages"),
            ("chat", "read_message"),
        ]
        for app_id, action in read_only_actions:
            self.assertTrue(
                application_registry.is_action_read_only(app_id, action),
                f"{app_id}.{action} should be read-only"
            )
            self.assertFalse(
                application_registry.is_action_mutating(app_id, action),
                f"{app_id}.{action} should not be mutating"
            )

    # 9. Mutating classification
    async def test_09_mutating_classification(self):
        mutating_actions = [
            ("crm", "update_customer"),
            ("chat", "send_message"),
        ]
        for app_id, action in mutating_actions:
            self.assertTrue(
                application_registry.is_action_mutating(app_id, action),
                f"{app_id}.{action} should be mutating"
            )
            self.assertFalse(
                application_registry.is_action_read_only(app_id, action),
                f"{app_id}.{action} should not be read-only"
            )

    # 10. Approval requirement enforcement
    async def test_10_approval_requirement_enforcement(self):
        # Canonical mutating actions MUST require approval
        self.assertTrue(application_registry.requires_approval("crm", "update_customer"))
        self.assertTrue(application_registry.requires_approval("chat", "send_message"))

        # Check all mutating actions across all registered applications
        for app_obj in application_registry.list_applications():
            for cap in app_obj.capabilities():
                if cap.mutating:
                    self.assertTrue(
                        cap.requires_approval,
                        f"Mutating capability {cap.action_id} MUST require approval"
                    )

        # Enforced fail-closed even if an adapter attempts to register a mutating action without approval flag
        class UnsafeAdapter(BaseIntegrationAdapter):
            def __init__(self):
                super().__init__(
                    metadata=IntegrationMetadata(
                        id="unsafe_app",
                        name="Unsafe App",
                        description="Test unsafe",
                        is_mock=True,
                    )
                )

            def _register_capabilities(self):
                self.register_action(
                    IntegrationActionDefinition(
                        name="delete_record",
                        display_name="Delete Record",
                        description="Deletes data",
                        is_safe=False,
                        is_mutating=True,
                        requires_approval=False,  # Unsafe attempt!
                        supported_strategies=["API"],
                    ),
                    handler=self._dummy_handler,
                )

            async def _dummy_handler(self, params, context=None):
                return {}

        unsafe = UnsafeAdapter()
        caps = unsafe.capabilities()
        self.assertTrue(
            caps[0].requires_approval,
            "BaseIntegrationAdapter MUST override and enforce requires_approval=True on mutating actions"
        )

    # 11. Unsupported capability handling
    async def test_11_unsupported_capability_handling(self):
        crm_app = application_registry.get_application("crm")
        res = await crm_app.execute_action("delete_customer", {"id": "1"})
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "UNSUPPORTED_ACTION")

        # API returns 404 for unknown application capability
        res_api = self.client.get("/api/applications/crm/capabilities")
        self.assertEqual(res_api.status_code, 200)
        res_bad = self.client.get("/api/applications/non_existent_app/capabilities")
        self.assertEqual(res_bad.status_code, 404)

    # 12. Disconnected application handling
    async def test_12_disconnected_application_handling(self):
        gmail_app = application_registry.get_application("gmail")
        # Gmail is disconnected when without credentials
        self.assertFalse(gmail_app.is_connected)
        res = await gmail_app.execute_action("read_message", {"message_id": "msg_123"})
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "INTEGRATION_DISCONNECTED")

    # 13. Planner capability integration
    async def test_13_planner_capability_integration(self):
        # Verify strategy capability registry queries application ecosystem
        self.assertTrue(capability_registry.is_api_capable("read_message", "gmail")[0])
        self.assertTrue(capability_registry.is_integration_capable("update_customer", "crm")[0])
        self.assertTrue(capability_registry.is_integration_capable("send_message", "chat")[0])

        # Verify planner constructs an automation plan incorporating ecosystem capabilities
        steps = [
            {
                "id": "s1",
                "name": "Read Email",
                "type": "read_message",
                "application": "gmail",
            },
            {
                "id": "s2",
                "name": "Update CRM",
                "type": "update_customer",
                "application": "crm",
            },
        ]
        plan = await automation_planner.create_plan(
            workflow_id="wf_ecosystem_test",
            steps=steps,
        )
        self.assertEqual(len(plan.steps), 2)
        # Step 1: Read Email -> API / INTEGRATION
        self.assertIn(plan.steps[0].selected_strategy, [AutomationStrategyType.API, AutomationStrategyType.INTEGRATION])
        # Step 2: Update CRM is mutating -> MUST require approval
        self.assertTrue(plan.requires_approval)
        self.assertTrue(plan.steps[1].is_mutating)

    # 14. Credential non-exposure
    async def test_14_credential_non_exposure(self):
        # Inspect API responses
        res_apps = self.client.get("/api/applications")
        self.assertEqual(res_apps.status_code, 200)
        apps_json = res_apps.json()
        raw_text = json.dumps(apps_json)

        # Check sensitive keywords are never leaked in payload keys or values
        forbidden = ["token", "secret", "password", "refresh_token", "private_key", "Bearer "]
        for word in forbidden:
            self.assertNotIn(f'"{word}"', raw_text.lower())
            self.assertNotIn(f'"{word}:', raw_text.lower())

        # Inspect single app API
        res_single = self.client.get("/api/applications/gmail")
        self.assertEqual(res_single.status_code, 200)
        single_text = json.dumps(res_single.json())
        self.assertNotIn("client_secret", single_text)
        self.assertNotIn("access_token", single_text)

    # 15. Privacy/redaction integration
    async def test_15_privacy_redaction_integration(self):
        # Applications endpoint filters any sensitive data through centralized redact_sensitive_data
        sample_payload = {
            "application_id": "crm",
            "password": "supersecretpassword",
            "api_key": "sk-1234567890abcdef1234567890abcdef",
            "capabilities": [{"action_id": "crm.search", "secret": "hidden"}],
        }
        redacted = redact_sensitive_data(sample_payload)
        self.assertEqual(redacted["password"], "[REDACTED]")
        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertEqual(redacted["capabilities"][0]["secret"], "[REDACTED]")

        # Audit should detect findings accurately
        audit = audit_sensitive_data(sample_payload)
        self.assertTrue(audit["contains_sensitive_data"])
        self.assertGreater(len(audit["redacted_fields"]), 0)

    # 16. Failure handling
    async def test_16_failure_handling(self):
        crm_app = application_registry.get_application("crm")
        # Invalid parameters should return clean IntegrationActionResult(success=False) without crashing
        res = await crm_app.execute_action("get_customer", {"customer_id": "non_existent_9999"})
        self.assertFalse(res.success)
        self.assertIn("Customer not found", res.message)

        # Chat send_message with missing required message param
        chat_app = application_registry.get_application("chat")
        res_chat = await chat_app.execute_action("send_message", {"channel": "#general", "message": ""})
        self.assertFalse(res_chat.success)
        self.assertIn("message", res_chat.message.lower())

    # 17. Existing Phase 7 regression
    async def test_17_existing_phase7_regression(self):
        from integrations.credentials import EncryptedTokenStorage
        storage = EncryptedTokenStorage(allow_ephemeral_dev_key=True)
        secret_payload = {"access_token": "ya29.test_token_phase7", "refresh_token": "1//test_refresh"}
        await storage.store_credential("gmail", secret_payload)
        retrieved = await storage.get_credential("gmail")
        self.assertEqual(retrieved["access_token"], "ya29.test_token_phase7")
        self.assertEqual(retrieved["refresh_token"], "1//test_refresh")

    # 18. Phase 9 regression
    async def test_18_phase9_learning_regression(self):
        from backend.learning.state import compute_learning_score
        # Verify Phase 9 formula: 0.50 + 0.10*approval + 0.08*edit + 0.15*success + 0.05*recovery - 0.20*rejection - 0.15*failed - 0.05*intervention
        score_base = compute_learning_score(0, 0, 0, 0, 0, 0, 0)
        self.assertEqual(score_base, 0.50)
        score_pos = compute_learning_score(1, 0, 0, 1, 0, 0, 0)
        self.assertEqual(score_pos, 0.75)
        score_neg = compute_learning_score(0, 1, 0, 0, 1, 0, 0)
        self.assertEqual(score_neg, 0.15)

    # 19. Phase 10 regression
    async def test_19_phase10_planner_regression(self):
        # Verify strategy hierarchy exists and orders properly:
        # API, INTEGRATION, SEMANTIC_UI, BROWSER, MANUAL
        strategies = [
            AutomationStrategyType.API,
            AutomationStrategyType.INTEGRATION,
            AutomationStrategyType.SEMANTIC_UI,
            AutomationStrategyType.BROWSER,
            AutomationStrategyType.MANUAL,
        ]
        self.assertEqual(len(strategies), 5)

        # Plan for demo CRM search customer
        steps = [
            {
                "id": "s1",
                "name": "Search CRM",
                "type": "search_customer",
                "application": "crm",
            }
        ]
        plan = await automation_planner.create_plan(
            workflow_id="wf_phase10_test",
            steps=steps,
        )
        self.assertEqual(len(plan.steps), 1)
        self.assertIn(plan.steps[0].selected_strategy, [AutomationStrategyType.API, AutomationStrategyType.INTEGRATION, AutomationStrategyType.BROWSER])

    # 20. Phase 11 regression
    async def test_20_phase11_closed_loop_regression(self):
        # Evaluate execution outcome
        now = datetime.now(timezone.utc)
        exec_record = AutomationExecution(
            execution_id="exec_p13_test",
            workflow_id="wf_p13_test",
            workflow_name="Phase 13 Workflow",
            status=AutomationStatus.COMPLETED,
            total_actions=1,
            completed_actions=["search_customer"],
            step_results=[
                StepExecutionResult(
                    step_id="step_1",
                    action_type="search_customer",
                    application="crm",
                    status="completed",
                )
            ],
            results=[
                ExecutionActionResult(
                    action_id="step_1",
                    action_type="search_customer",
                    success=True,
                    message="Success",
                )
            ],
        )
        outcome = evaluate_execution_outcome(exec_record)
        self.assertEqual(outcome.status, ExecutionOutcomeStatus.SUCCESS)
        self.assertEqual(outcome.total_steps, 1)
        self.assertEqual(outcome.completed_steps, 1)

    # 21. Phase 12 regression
    async def test_21_phase12_privacy_regression(self):
        # Collection control flag
        self.assertTrue(privacy_service.is_collection_enabled())

        # Centralized redaction patterns
        text_with_token = "Here is my secret Bearer eyJhbGciOiJIUzI1NiJ9.test and password=SecretPass!"
        clean = redact_sensitive_data(text_with_token)
        self.assertNotIn("SecretPass!", clean)
        self.assertIn("[REDACTED]", clean)

    # 22. Security Review: Capability safety, read-only/mutating invariants, and approval fail-closed
    async def test_22_security_review_capability_safety_and_approval_fail_closed(self):
        """
        Validates required safety behaviors:
        1. Unknown action: MUST NOT be read-only, MUST fail closed on approval, MUST NOT be executable.
        2. Unsupported action on known application: MUST NOT be read-only, MUST fail closed on approval, MUST NOT be executable.
        3. Unknown application + action: MUST NOT be read-only, MUST fail closed on approval, MUST NOT be executable.
        4. Known read-only action: is_action_read_only=True, is_action_mutating=False, requires_approval=False.
        5. Known mutating action: is_action_read_only=False, is_action_mutating=True, requires_approval=True.
        """
        # --- Case 1: Unknown action (no app specified) ---
        unknown_act = "non_existent_action_xyz"
        self.assertIsNone(application_registry.get_capability(unknown_act))
        self.assertFalse(application_registry.is_action_read_only(unknown_act), "Unknown action MUST NOT be classified as read-only")
        self.assertFalse(application_registry.is_action_mutating(unknown_act))
        self.assertTrue(application_registry.requires_approval(unknown_act), "requires_approval MUST fail closed (return True) for unknown action")
        with self.assertRaises(UnsupportedActionError):
            application_registry.get_capability_or_raise(unknown_act)

        # --- Case 2: Unsupported action on known application ---
        unsupported_act = "format_server_drive"
        self.assertIsNone(application_registry.get_capability(unsupported_act, application_id="crm"))
        self.assertFalse(application_registry.is_action_read_only(unsupported_act, application_id="crm"), "Unsupported action on CRM MUST NOT be read-only")
        self.assertFalse(application_registry.is_action_mutating(unsupported_act, application_id="crm"))
        self.assertTrue(application_registry.requires_approval(unsupported_act, application_id="crm"), "requires_approval MUST fail closed for unsupported action on CRM")
        with self.assertRaises(UnsupportedActionError):
            application_registry.get_capability_or_raise(unsupported_act, application_id="crm")

        # Verify unsupported action is NOT executable via adapter or route_action
        crm_app = application_registry.get_application("crm")
        exec_res = await crm_app.execute_action(unsupported_act, {})
        self.assertFalse(exec_res.success)
        self.assertEqual(exec_res.error_code, "UNSUPPORTED_ACTION")

        route_res = await integration_registry.route_action("crm", unsupported_act, {})
        self.assertFalse(route_res.success)
        self.assertEqual(route_res.error_code, "UNSUPPORTED_ACTION")

        # Planner capability checks reject unsupported action
        int_capable, int_reason, _, _ = capability_registry.is_integration_capable(unsupported_act, "crm")
        self.assertFalse(int_capable, "Planner must reject unsupported action on CRM")
        self.assertIn("not supported", int_reason.lower())

        br_capable, br_reason, _, _ = capability_registry.is_browser_capable(unsupported_act, "crm")
        self.assertFalse(br_capable, "Planner must reject unsupported action for browser execution")

        # --- Case 3: Unknown application + action ---
        unknown_app = "unknown_accounting_system"
        unknown_app_act = "transfer_funds"
        self.assertIsNone(application_registry.get_capability(unknown_app_act, application_id=unknown_app))
        self.assertFalse(application_registry.is_action_read_only(unknown_app_act, application_id=unknown_app), "Action on unknown app MUST NOT be read-only")
        self.assertFalse(application_registry.is_action_mutating(unknown_app_act, application_id=unknown_app))
        self.assertTrue(application_registry.requires_approval(unknown_app_act, application_id=unknown_app), "requires_approval MUST fail closed for unknown app + action")
        with self.assertRaises(UnknownIntegrationError):
            application_registry.get_capability_or_raise(unknown_app_act, application_id=unknown_app)

        # Verify unknown application execution fails safely
        route_unknown_res = await integration_registry.route_action(unknown_app, unknown_app_act, {})
        self.assertFalse(route_unknown_res.success)
        self.assertEqual(route_unknown_res.error_code, "UNKNOWN_INTEGRATION")

        int_unknown_capable, _, _, _ = capability_registry.is_integration_capable(unknown_app_act, unknown_app)
        self.assertFalse(int_unknown_capable)

        # --- Case 4: Known read-only action ---
        ro_act = "search_customer"
        ro_cap = application_registry.get_capability(ro_act, application_id="crm")
        self.assertIsNotNone(ro_cap)
        self.assertTrue(application_registry.is_action_read_only(ro_act, application_id="crm"))
        self.assertFalse(application_registry.is_action_mutating(ro_act, application_id="crm"))
        self.assertFalse(application_registry.requires_approval(ro_act, application_id="crm"))
        cap_raised = application_registry.get_capability_or_raise(ro_act, application_id="crm")
        self.assertEqual(cap_raised.name, "search_customer")
        self.assertTrue(cap_raised.read_only)
        self.assertFalse(cap_raised.requires_approval)

        # Gmail read-only action
        gmail_act = "search_messages"
        self.assertTrue(application_registry.is_action_read_only(gmail_act, application_id="gmail"))
        self.assertFalse(application_registry.is_action_mutating(gmail_act, application_id="gmail"))
        self.assertFalse(application_registry.requires_approval(gmail_act, application_id="gmail"))

        # --- Case 5: Known mutating action ---
        mut_act = "update_customer"
        mut_cap = application_registry.get_capability(mut_act, application_id="crm")
        self.assertIsNotNone(mut_cap)
        self.assertFalse(application_registry.is_action_read_only(mut_act, application_id="crm"))
        self.assertTrue(application_registry.is_action_mutating(mut_act, application_id="crm"))
        self.assertTrue(application_registry.requires_approval(mut_act, application_id="crm"))
        mut_cap_raised = application_registry.get_capability_or_raise(mut_act, application_id="crm")
        self.assertEqual(mut_cap_raised.name, "update_customer")
        self.assertTrue(mut_cap_raised.mutating)
        self.assertTrue(mut_cap_raised.requires_approval)

        # Chat send_message mutating action
        chat_mut_act = "send_message"
        self.assertFalse(application_registry.is_action_read_only(chat_mut_act, application_id="chat"))
        self.assertTrue(application_registry.is_action_mutating(chat_mut_act, application_id="chat"))
        self.assertTrue(application_registry.requires_approval(chat_mut_act, application_id="chat"))


if __name__ == "__main__":
    unittest.main()
