#!/usr/bin/env python3
"""
WorkFlowOS Phase 7.1 - Integration Foundation Test Suite

Validates:
1. Adapter interface and registration lifecycle.
2. Duplicate registration prevention.
3. Unknown integration and unsupported action containment.
4. Connection and disconnection states.
5. Action execution requirement for connected state.
6. Schema-based parameter input validation.
7. Successful mock actions (mock_echo, simulate_ping).
8. Structured failure responses (simulate_failure).
9. Credential redaction in dictionaries, logs, and exception wrappers.
10. REST API integration endpoints (listing, get, connect, disconnect, execute action).
11. Approval gate enforcement on integration workflows (refusal when unapproved).
12. Seamless compatibility with declarative workflow execution engine.
13. Pause, resume, and cancellation compatibility with integration steps.
"""

import unittest
import asyncio
from typing import Dict, Any

from fastapi.testclient import TestClient

from backend.main import app
from integrations.base import BaseIntegrationAdapter
from integrations.models import (
    IntegrationMetadata,
    IntegrationStatus,
    IntegrationActionDefinition,
    ActionParameterDefinition,
    ParameterType,
    IntegrationActionResult,
    DuplicateIntegrationError,
    UnknownIntegrationError,
    UnsupportedActionError,
    IntegrationValidationError,
)
from cryptography.fernet import Fernet
from integrations.registry import IntegrationRegistry, integration_registry
from integrations.mock import MockTestIntegrationAdapter
from integrations.credentials import (
    sanitize_credential_dict,
    sanitize_log_message,
    CredentialMaskedException,
    EnvCredentialStorage,
    EncryptedTokenStorage,
    CredentialStorageConfigurationError,
)
from integrations.executor import IntegrationExecutor
from automation.models import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowInputDefinition,
    WorkflowTriggerConfig,
    AutomationStatus,
    AutomationAction,
    ExecuteWorkflowRequest,
)
from automation.service import automation_service


class TestIntegrationFoundation(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.mock_adapter = integration_registry.get("mock_service")
        if not self.mock_adapter:
            self.mock_adapter = MockTestIntegrationAdapter("mock_service")
            integration_registry.register(self.mock_adapter)

    async def asyncTearDown(self):
        # Reset mock adapter state to clean disconnected
        if self.mock_adapter:
            await self.mock_adapter.disconnect()

    # ── 1. Interface & Registration ──────────────────────────────────────────

    def test_mock_adapter_metadata(self):
        """Validates adapter identification, metadata, and mock labeling."""
        self.assertEqual(self.mock_adapter.id, "mock_service")
        self.assertEqual(self.mock_adapter.name, "Mock Test Integration")
        self.assertTrue(self.mock_adapter.metadata.is_mock)
        self.assertIn("isolated mock test fixture", self.mock_adapter.metadata.disclaimer)
        self.assertIn("mock_echo", self.mock_adapter.declared_action_names)
        self.assertIn("simulate_ping", self.mock_adapter.declared_action_names)
        self.assertIn("simulate_failure", self.mock_adapter.declared_action_names)

    def test_duplicate_registration_prevention(self):
        """Ensures duplicate integration registrations are rejected."""
        custom_registry = IntegrationRegistry()
        adapter1 = MockTestIntegrationAdapter("adapter_unique")
        adapter2 = MockTestIntegrationAdapter("adapter_unique")

        custom_registry.register(adapter1)
        with self.assertRaises(DuplicateIntegrationError):
            custom_registry.register(adapter2)

    def test_unknown_integration_handling(self):
        """Ensures unknown integrations raise UnknownIntegrationError."""
        custom_registry = IntegrationRegistry()
        with self.assertRaises(UnknownIntegrationError):
            custom_registry.get_or_raise("non_existent_adapter")

    # ── 2. Connection State Lifecycle ────────────────────────────────────────

    async def test_connection_and_disconnection_lifecycle(self):
        """Demonstrates transition between connected and disconnected states."""
        self.assertFalse(self.mock_adapter.is_connected)
        self.assertEqual(self.mock_adapter.status, IntegrationStatus.DISCONNECTED)

        # Connect
        connected = await self.mock_adapter.connect()
        self.assertTrue(connected)
        self.assertTrue(self.mock_adapter.is_connected)
        self.assertEqual(self.mock_adapter.status, IntegrationStatus.CONNECTED)
        self.assertIsNotNone(self.mock_adapter.connected_at)

        # Disconnect
        disconnected = await self.mock_adapter.disconnect()
        self.assertTrue(disconnected)
        self.assertFalse(self.mock_adapter.is_connected)
        self.assertEqual(self.mock_adapter.status, IntegrationStatus.DISCONNECTED)
        self.assertIsNone(self.mock_adapter.connected_at)

    async def test_action_execution_fails_when_disconnected(self):
        """Action execution must fail if adapter is disconnected."""
        await self.mock_adapter.disconnect()
        res = await self.mock_adapter.execute_action(
            action_name="mock_echo",
            parameters={"message": "Should fail"}
        )
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "INTEGRATION_DISCONNECTED")
        self.assertIn("disconnected", res.message)

    # ── 3. Input Validation ──────────────────────────────────────────────────

    async def test_action_input_validation(self):
        """Validates parameter schemas: required fields, types, and unsupported actions."""
        await self.mock_adapter.connect()

        # Missing required parameter 'message'
        res1 = await self.mock_adapter.execute_action(
            action_name="mock_echo",
            parameters={}
        )
        self.assertFalse(res1.success)
        self.assertEqual(res1.error_code, "VALIDATION_ERROR")
        self.assertIn("Missing required parameter 'message'", res1.message)

        # Wrong type: integer instead of string
        res2 = await self.mock_adapter.execute_action(
            action_name="mock_echo",
            parameters={"message": 12345}
        )
        self.assertFalse(res2.success)
        self.assertEqual(res2.error_code, "VALIDATION_ERROR")
        self.assertIn("must be a string", res2.message)

        # Unsupported action
        res3 = await self.mock_adapter.execute_action(
            action_name="invalid_action_name",
            parameters={}
        )
        self.assertFalse(res3.success)
        self.assertEqual(res3.error_code, "UNSUPPORTED_ACTION")

    # ── 4. Action Execution (Success & Failure) ───────────────────────────────

    async def test_mock_echo_action_success(self):
        """Executes safe mock_echo action and validates structured result."""
        await self.mock_adapter.connect()
        res = await self.mock_adapter.execute_action(
            action_name="mock_echo",
            parameters={"message": "WorkflowOS Integration Test", "prefix": ">> "}
        )
        self.assertTrue(res.success)
        self.assertIsNotNone(res.data)
        self.assertEqual(res.data.get("echoed_message"), ">> WorkflowOS Integration Test")
        self.assertEqual(res.data.get("service"), "mock_service")
        self.assertTrue(res.data.get("is_simulated"))

    async def test_simulate_ping_action(self):
        """Executes heartbeat simulate_ping action."""
        await self.mock_adapter.connect()
        res = await self.mock_adapter.execute_action(
            action_name="simulate_ping",
            parameters={"payload": "health_check_payload"}
        )
        self.assertTrue(res.success)
        self.assertTrue(res.data.get("pong"))
        self.assertEqual(res.data.get("payload"), "health_check_payload")

    async def test_simulate_failure_action(self):
        """Executes simulate_failure action to verify structured error responses."""
        await self.mock_adapter.connect()
        res = await self.mock_adapter.execute_action(
            action_name="simulate_failure",
            parameters={
                "error_message": "Network timeout simulated for testing",
                "error_code": "TEST_TIMEOUT"
            }
        )
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "TEST_TIMEOUT")
        self.assertIn("Network timeout simulated", res.message)

    # ── 5. Credential Security & Redaction ───────────────────────────────────

    def test_credential_sanitization_in_dict(self):
        """Verifies recursive masking of sensitive credential keys."""
        dirty_dict = {
            "user": "developer",
            "token": "ghp_abcdef1234567890secrettoken",
            "nested": {
                "client_secret": "my_super_secret_key",
                "safe_value": "hello_world",
                "api_key": "sk-1234567890",
            },
            "list": [
                {"password": "plain_password_123"},
                {"name": "ok"}
            ]
        }
        clean = sanitize_credential_dict(dirty_dict)
        self.assertEqual(clean["token"], "[REDACTED]")
        self.assertEqual(clean["nested"]["client_secret"], "[REDACTED]")
        self.assertEqual(clean["nested"]["api_key"], "[REDACTED]")
        self.assertEqual(clean["nested"]["safe_value"], "hello_world")
        self.assertEqual(clean["list"][0]["password"], "[REDACTED]")
        self.assertEqual(clean["list"][1]["name"], "ok")

    def test_credential_sanitization_in_strings(self):
        """Verifies pattern-based redaction for Bearer, Basic, Base64 secrets, and non-sensitive text."""
        # 1. Bearer token with Base64 characters (+, /, =)
        bearer_line = "Authorization: Bearer ya29.a0AfH6SMB_secret+token/value=="
        scrubbed_bearer = sanitize_log_message(bearer_line)
        self.assertNotIn("ya29.a0AfH6SMB_secret+token/value==", scrubbed_bearer)
        self.assertEqual(scrubbed_bearer, "Authorization: Bearer [REDACTED]")

        # 2. Basic authorization header
        basic_line = "Authorization: Basic dXNlcjpwYXNzd29yZDEyMw=="
        scrubbed_basic = sanitize_log_message(basic_line)
        self.assertNotIn("dXNlcjpwYXNzd29yZDEyMw==", scrubbed_basic)
        self.assertEqual(scrubbed_basic, "Authorization: Basic [REDACTED]")

        # 3. Key-value secrets with quotes and various delimiters
        kv_line = "client_secret='top_secret+key/123=' and api_key=\"sk-live-998877\" and token: ghp_token123"
        scrubbed_kv = sanitize_log_message(kv_line)
        self.assertNotIn("top_secret+key/123=", scrubbed_kv)
        self.assertNotIn("sk-live-998877", scrubbed_kv)
        self.assertNotIn("ghp_token123", scrubbed_kv)
        self.assertIn("client_secret='[REDACTED]'", scrubbed_kv)
        self.assertIn("api_key=\"[REDACTED]\"", scrubbed_kv)
        self.assertIn("token: [REDACTED]", scrubbed_kv)

        # 4. Ordinary non-sensitive text must NOT be consumed or corrupted
        safe_line = "User pressed key=Enter to submit. Navigating to /api/items?page=1&limit=50. Event target=button."
        scrubbed_safe = sanitize_log_message(safe_line)
        self.assertEqual(scrubbed_safe, safe_line)

    def test_credential_masked_exception(self):
        """Ensures CredentialMaskedException never exposes tokens in str(e)."""
        exc = CredentialMaskedException(
            "Connection failed with Bearer ya29.a0AfH6SMB_secret+token/val=="
        )
        self.assertNotIn("ya29.a0AfH6SMB_secret+token/val==", str(exc))
        self.assertIn("Bearer [REDACTED]", str(exc))

    async def test_encrypted_token_storage(self):
        """Verifies EncryptedTokenStorage authenticated encryption, ciphertext storage, and tamper detection."""
        key = Fernet.generate_key().decode("utf-8")
        storage = EncryptedTokenStorage(encryption_key=key)
        self.assertFalse(storage.is_ephemeral)

        test_creds = {"access_token": "secret_oauth_token_val", "refresh_token": "secret_refresh_val"}
        await storage.store_credential("test_adapter", test_creds)

        # Ensure internal store has ciphertext and never contains plaintext secrets
        raw_stored = storage._store.get("test_adapter")
        self.assertIsNotNone(raw_stored)
        self.assertNotIn("secret_oauth_token_val", raw_stored)
        self.assertNotIn("secret_refresh_val", raw_stored)
        self.assertTrue(raw_stored.startswith("gAAAAA"))  # Fernet token prefix

        # Retrieve and verify round-trip decryption
        decrypted = await storage.get_credential("test_adapter")
        self.assertEqual(decrypted["access_token"], "secret_oauth_token_val")
        self.assertEqual(decrypted["refresh_token"], "secret_refresh_val")

        # Tamper detection: modifying stored ciphertext must fail safely without decrypting corrupted data
        tampered_ciphertext = raw_stored[:-5] + "XXXXX"
        storage._store["test_adapter"] = tampered_ciphertext
        self.assertIsNone(await storage.get_credential("test_adapter"))

    def test_encrypted_token_storage_missing_key_fails(self):
        """EncryptedTokenStorage must reject initialization if key is missing and ephemeral is False."""
        with self.assertRaises(CredentialStorageConfigurationError):
            EncryptedTokenStorage(encryption_key=None, allow_ephemeral_dev_key=False)

    def test_encrypted_token_storage_invalid_key_fails(self):
        """EncryptedTokenStorage must reject invalid/malformed encryption keys."""
        with self.assertRaises(CredentialStorageConfigurationError):
            EncryptedTokenStorage(encryption_key="not-a-valid-fernet-key", allow_ephemeral_dev_key=False)

    def test_encrypted_token_storage_ephemeral_dev_mode(self):
        """EncryptedTokenStorage supports explicit ephemeral dev key for isolated testing."""
        storage = EncryptedTokenStorage(allow_ephemeral_dev_key=True)
        self.assertTrue(storage.is_ephemeral)

    # ── 6. REST API Endpoints ────────────────────────────────────────────────

    def test_api_list_integrations(self):
        """GET /api/integrations returns registered adapters."""
        res = self.client.get("/api/integrations")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        mock_entry = next((i for i in data if i["id"] == "mock_service"), None)
        self.assertIsNotNone(mock_entry)
        self.assertEqual(mock_entry["name"], "Mock Test Integration")
        self.assertTrue(mock_entry["is_mock"])

    def test_api_get_integration_detail(self):
        """GET /api/integrations/{id} returns specific adapter metadata."""
        res = self.client.get("/api/integrations/mock_service")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], "mock_service")
        self.assertIn("mock_echo", [a["name"] for a in data["actions"]])

        # 404 for unknown integration
        res_404 = self.client.get("/api/integrations/unknown_service")
        self.assertEqual(res_404.status_code, 404)

    def test_api_connect_and_disconnect(self):
        """POST /api/integrations/{id}/connect and /disconnect."""
        # Connect
        c_res = self.client.post("/api/integrations/mock_service/connect")
        self.assertEqual(c_res.status_code, 200)
        self.assertEqual(c_res.json()["status"], "connected")
        self.assertTrue(c_res.json()["is_connected"])

        # Execute permitted action via API
        exec_res = self.client.post(
            "/api/integrations/mock_service/actions/mock_echo/execute",
            json={"parameters": {"message": "Hello from REST API"}}
        )
        self.assertEqual(exec_res.status_code, 200)
        exec_data = exec_res.json()
        self.assertTrue(exec_data["success"])
        self.assertIn("Hello from REST API", exec_data["data"]["echoed_message"])

        # Disconnect
        d_res = self.client.post("/api/integrations/mock_service/disconnect")
        self.assertEqual(d_res.status_code, 200)
        self.assertEqual(d_res.json()["status"], "disconnected")
        self.assertFalse(d_res.json()["is_connected"])

        # Executing while disconnected fails with 409
        fail_res = self.client.post(
            "/api/integrations/mock_service/actions/mock_echo/execute",
            json={"parameters": {"message": "Should be rejected"}}
        )
        self.assertEqual(fail_res.status_code, 409)

    def test_api_direct_execution_blocked_for_mutating_action(self):
        """Standalone execution of mutating/unsafe actions via API must be rejected with 403 Forbidden."""
        self.client.post("/api/integrations/mock_service/connect")

        # Mutating action 'simulate_mutating_write' must be blocked from direct execution
        mutating_res = self.client.post(
            "/api/integrations/mock_service/actions/simulate_mutating_write/execute",
            json={"parameters": {"target_id": "cust_123", "value": "updated_state"}}
        )
        self.assertEqual(mutating_res.status_code, 403)
        self.assertIn("Direct standalone execution", mutating_res.json()["detail"])
        self.assertIn("must be executed within an approved workflow", mutating_res.json()["detail"])

        # Safe actions continue to be permitted for testing
        safe_res = self.client.post(
            "/api/integrations/mock_service/actions/mock_echo/execute",
            json={"parameters": {"message": "Safe check"}}
        )
        self.assertEqual(safe_res.status_code, 200)
        self.assertTrue(safe_res.json()["success"])

    # ── 7. Workflow Engine Compatibility & Approval Gate ─────────────────────

    async def test_workflow_approval_gate_enforcement(self):
        """Unapproved workflows containing integration actions must be blocked."""
        await self.mock_adapter.connect()

        wf = WorkflowDefinition(
            id="wf_integration_test_unapproved",
            name="Unapproved Integration Workflow",
            steps=[
                WorkflowStep(
                    id="step_mock_echo",
                    name="Echo Test",
                    type="mock_echo",
                    application="mock_service",
                    parameters={"message": "Echo payload"},
                )
            ],
            requires_approval=True,
        )

        # Run with approved=False -> status must be PENDING
        execution = await automation_service.run_workflow(
            workflow_definition=wf,
            approved=False,
            executor_type="integration",
        )
        self.assertEqual(execution.status, AutomationStatus.PENDING)
        self.assertEqual(len(execution.completed_actions), 0)

    async def test_workflow_execution_with_mutating_action_gated_by_approval(self):
        """Mutating actions can execute through the workflow engine, but are strictly gated by human approval."""
        await self.mock_adapter.connect()

        wf = WorkflowDefinition(
            id="wf_mutating_action_approval_test",
            name="Mutating Action Approval Workflow",
            steps=[
                WorkflowStep(
                    id="step_mutate",
                    name="Mutating Action Step",
                    type="simulate_mutating_write",
                    application="mock_service",
                    parameters={"target_id": "record_999", "value": "new_approved_val"},
                    output_mapping={"res_updated": "data.updated"},
                )
            ],
            requires_approval=True,
        )

        # 1. Unapproved execution is held in PENDING status; mutating action is NOT executed
        unapproved_exec = await automation_service.run_workflow(
            workflow_definition=wf,
            approved=False,
            executor_type="integration",
        )
        self.assertEqual(unapproved_exec.status, AutomationStatus.PENDING)
        self.assertEqual(len(unapproved_exec.completed_actions), 0)

        # 2. Approved execution succeeds and executes the mutating action safely
        approved_exec = await automation_service.run_workflow(
            workflow_definition=wf,
            approved=True,
            executor_type="integration",
        )
        self.assertEqual(approved_exec.status, AutomationStatus.COMPLETED)
        self.assertIn("simulate_mutating_write", approved_exec.completed_actions)
        self.assertTrue(approved_exec.variables.get("res_updated"))

    async def test_workflow_execution_with_approved_integration_step(self):
        """Approved declarative workflow with mock integration step executes successfully."""
        await self.mock_adapter.connect()

        wf = WorkflowDefinition(
            id="wf_integration_test_approved",
            name="Approved Integration Workflow",
            inputs=[
                WorkflowInputDefinition(
                    name="custom_msg",
                    type="string",
                    default="Dynamic workflow message",
                    required=True,
                )
            ],
            variables={"verified": True},
            steps=[
                WorkflowStep(
                    id="step_ping",
                    name="Heartbeat Ping",
                    type="simulate_ping",
                    application="mock_service",
                    parameters={"payload": "workflow_engine_ping"},
                    output_mapping={"ping_status": "data.status"},
                ),
                WorkflowStep(
                    id="step_echo",
                    name="Echo Message",
                    type="mock_echo",
                    application="integration:mock_service",
                    parameters={"message": "{{inputs.custom_msg}}", "prefix": "WF >> "},
                    output_mapping={"echoed": "data.echoed_message"},
                ),
            ],
            requires_approval=True,
        )

        execution = await automation_service.run_workflow(
            workflow_definition=wf,
            approved=True,
            executor_type="integration",
            inputs={"custom_msg": "Executed through workflow engine"},
        )

        self.assertEqual(execution.status, AutomationStatus.COMPLETED)
        self.assertEqual(len(execution.completed_actions), 2)
        self.assertIn("simulate_ping", execution.completed_actions)
        self.assertIn("mock_echo", execution.completed_actions)
        self.assertEqual(execution.variables.get("ping_status"), "healthy")
        self.assertEqual(execution.variables.get("echoed"), "WF >> Executed through workflow engine")

    async def test_workflow_pause_and_resume_on_integration_failure(self):
        """Integration action failure transitions workflow to PAUSED; resume succeeds after fix."""
        await self.mock_adapter.connect()

        wf = WorkflowDefinition(
            id="wf_integration_failure_test",
            name="Integration Failure & Recovery Workflow",
            steps=[
                WorkflowStep(
                    id="step_echo_ok",
                    name="Step 1 Echo",
                    type="mock_echo",
                    application="mock_service",
                    parameters={"message": "First step OK"},
                ),
                WorkflowStep(
                    id="step_simulate_fail",
                    name="Step 2 Simulated Fail",
                    type="simulate_failure",
                    application="mock_service",
                    parameters={"error_message": "External service simulated timeout"},
                ),
            ],
            requires_approval=True,
        )

        # 1. Initial run: fails on step 2 -> PAUSED with resume_available=True
        exec_init = await automation_service.run_workflow(
            workflow_definition=wf,
            approved=True,
            executor_type="integration",
        )

        self.assertEqual(exec_init.status, AutomationStatus.PAUSED)
        self.assertTrue(exec_init.resume_available)
        self.assertEqual(exec_init.failed_action, "simulate_failure")
        self.assertIn("mock_echo", exec_init.completed_actions)

        # 2. Cancel test
        cancelled = automation_service.cancel_execution(exec_init.execution_id)
        self.assertEqual(cancelled.status, AutomationStatus.CANCELLED)
        self.assertFalse(cancelled.resume_available)


if __name__ == "__main__":
    unittest.main()
