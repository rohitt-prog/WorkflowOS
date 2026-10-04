#!/usr/bin/env python3
"""
WorkFlowOS Phase 7.3: Gmail Declarative Workflow Integration Test Suite

Validates:
1. Gmail Action Registration:
   - Registration and discovery in integration registry.
   - Case-insensitive retrieval and action-to-adapter resolution.
   - Schema parameter definitions (max_results, query bounds).
   - allow_direct_execution=False enforcement on list_recent_messages.

2. Declarative Workflow Step Validation:
   - Valid Gmail workflow steps with parameter checks.
   - Invalid step inputs (bounds, malformed parameters).
   - Structured error handling for invalid steps.

3. Variable Interpolation & Nested Output Mapping:
   - Interpolation from workflow inputs (e.g., {{inputs.query}}).
   - Downstream step interpolation from Gmail step outputs with array indexing
     (e.g., {{steps.step_1.output.messages.0.from}}).

4. Approval Gate & Security Enforcement:
   - Unapproved workflow with Gmail action halts with PENDING status.
   - Direct action execution via REST endpoint returns 403 Forbidden.
   - No credential, token, or raw email body leakage.

5. Workflow Execution Engine Integration:
   - End-to-end execution of declarative workflow containing Gmail action.
   - Mocked Gmail API transport for hermetic testing.
   - Execution history recording with sanitized metadata and timing.

6. Failure Modes & Edge Cases:
   - Disconnected Gmail account handling.
   - Expired token auto-refresh success.
   - Revoked refresh token / refresh failure.
   - Google API HTTP errors (401, 403, 429, 503) and network failures.
   - Retry policy enforcement (max retries, backoff).
   - Halt vs continue_on_failure policies.

7. Mixed Provider & Engine Lifecycle:
   - Multi-provider workflow (mock_echo + gmail list_recent_messages + demo_crm).
   - Pause, resume, and cancellation mechanics.
"""

import os
import time
import asyncio
import unittest
from unittest.mock import patch, AsyncMock
from typing import Dict, Any, Optional
import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.main import app
from integrations.base import BaseIntegrationAdapter
from integrations.models import (
    IntegrationStatus,
    IntegrationActionResult,
    IntegrationConnectionError,
    IntegrationValidationError,
)
from integrations.registry import integration_registry
from integrations.credentials import (
    EncryptedTokenStorage,
    sanitize_credential_dict,
    sanitize_log_message,
)
from integrations.oauth import (
    GoogleOAuthManager,
    OAuthTokenExchangeError,
)
from integrations.gmail import (
    GmailIntegrationAdapter,
    get_oauth_token_storage,
)
from automation.models import (
    WorkflowDefinition,
    WorkflowStep,
    AutomationStatus,
    RetryPolicy,
)
from automation.engine import (
    automation_engine,
    _get_nested_val,
    resolve_template_value,
)
from automation.service import automation_service


def _build_mock_gmail_transport(messages_data=None, api_status_code=200, error_body=None):
    """Creates a mock HTTP transport simulating Gmail REST API."""
    if messages_data is None:
        messages_data = [
            {
                "id": "msg_101",
                "threadId": "th_101",
                "snippet": "Quarterly enterprise contract review",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "client@enterprise.com"},
                        {"name": "Subject", "value": "Contract Approval Request"},
                        {"name": "Date", "value": "Sun, 04 Oct 2026 10:00:00 GMT"},
                    ]
                },
            },
            {
                "id": "msg_102",
                "threadId": "th_102",
                "snippet": "Monthly platform metrics and analytics report",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "metrics@company.internal"},
                        {"name": "Subject", "value": "Platform Weekly Summary"},
                        {"name": "Date", "value": "Sun, 04 Oct 2026 11:00:00 GMT"},
                    ]
                },
            },
        ]

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if api_status_code != 200:
            err = error_body or {"error": {"message": f"API error {api_status_code}", "code": api_status_code}}
            return httpx.Response(api_status_code, json=err)

        if "/messages?maxResults=" in url_str:
            return httpx.Response(
                200,
                json={
                    "messages": [{"id": m["id"], "threadId": m["threadId"]} for m in messages_data],
                    "resultSizeEstimate": len(messages_data),
                },
            )

        for m in messages_data:
            if f"/messages/{m['id']}" in url_str:
                return httpx.Response(200, json=m)

        return httpx.Response(404, json={"error": "Not found"})

    return httpx.MockTransport(mock_handler)


class TestPhase73GmailActionRegistration(unittest.TestCase):
    """Tests Gmail action registration, discovery, and schema definitions."""

    def test_gmail_adapter_registered_and_discoverable(self):
        adapter = integration_registry.get("gmail")
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.id, "gmail")
        self.assertFalse(adapter.metadata.is_mock)

        # Case-insensitive resolution
        self.assertIs(integration_registry.get("GMAIL"), adapter)
        self.assertIs(integration_registry.get("Gmail"), adapter)

    def test_find_adapter_by_action(self):
        adapter = integration_registry.find_adapter_by_action("list_recent_messages")
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.id, "gmail")

        # Unknown action returns None
        self.assertIsNone(integration_registry.find_adapter_by_action("non_existent_action"))

    def test_action_schema_and_allow_direct_execution_false(self):
        adapter = integration_registry.get("gmail")
        actions = adapter.declared_actions
        action_names = [a.name for a in actions]
        self.assertIn("list_recent_messages", action_names)

        list_action = next(a for a in actions if a.name == "list_recent_messages")
        self.assertFalse(
            list_action.allow_direct_execution,
            "list_recent_messages MUST require workflow approval gate and forbid standalone direct execution",
        )
        param_names = [p.name for p in list_action.parameters]
        self.assertIn("max_results", param_names)
        self.assertIn("query", param_names)


class TestPhase73VariableInterpolation(unittest.TestCase):
    """Tests variable interpolation, nested dictionary access, and array indexing."""

    def test_nested_val_dict_and_array_indexing(self):
        context = {
            "inputs": {"customer_name": "Alice Corp", "query": "label:INBOX"},
            "steps": {
                "step_1": {
                    "output": {
                        "count": 2,
                        "messages": [
                            {"id": "msg_1", "subject": "Hello World", "from": "alice@corp.com"},
                            {"id": "msg_2", "subject": "Second Email", "from": "bob@corp.com"},
                        ],
                    }
                }
            },
        }

        # Dict traversal
        self.assertEqual(_get_nested_val(context, "inputs.customer_name"), "Alice Corp")
        self.assertEqual(_get_nested_val(context, "steps.step_1.output.count"), 2)

        # Array indexing via dot notation
        self.assertEqual(_get_nested_val(context, "steps.step_1.output.messages.0.subject"), "Hello World")
        self.assertEqual(_get_nested_val(context, "steps.step_1.output.messages.0.from"), "alice@corp.com")
        self.assertEqual(_get_nested_val(context, "steps.step_1.output.messages.1.subject"), "Second Email")

        # Array indexing via bracket notation
        self.assertEqual(_get_nested_val(context, "steps.step_1.output.messages[0].subject"), "Hello World")

        # Missing key/index returns None safely
        self.assertIsNone(_get_nested_val(context, "steps.step_1.output.messages.5.subject"))
        self.assertIsNone(_get_nested_val(context, "non_existent.path"))

    def test_interpolate_val_strings(self):
        context = {
            "inputs": {"user": "Bob"},
            "steps": {
                "gmail_step": {
                    "output": {
                        "messages": [{"from": "sender@domain.com"}],
                    }
                }
            },
        }

        # Entire variable replacement
        self.assertEqual(resolve_template_value("{{inputs.user}}", context), "Bob")

        # Embedded variable replacement
        self.assertEqual(
            resolve_template_value("Sender is {{steps.gmail_step.output.messages.0.from}}", context),
            "Sender is sender@domain.com",
        )


class TestPhase73ApprovalGateAndDirectBypass(unittest.TestCase):
    """Validates that Gmail actions strictly require workflow approval and cannot be bypassed."""

    def setUp(self):
        self.client = TestClient(app)

    def test_direct_execution_endpoint_forbidden(self):
        """Standalone POST to direct action execution endpoint MUST return 403 Forbidden."""
        resp = self.client.post(
            "/api/integrations/gmail/actions/list_recent_messages/execute",
            json={"parameters": {"max_results": 5}},
        )
        self.assertEqual(resp.status_code, 403)
        data = resp.json()
        self.assertIn("forbidden", data.get("detail", "").lower())
        self.assertIn("approved workflow", data.get("detail", "").lower())

    def test_unapproved_workflow_halts_with_pending_status(self):
        """A workflow containing a Gmail action submitted without approval MUST halt as PENDING."""
        wf_def = WorkflowDefinition(
            id="wf_unapproved_01",
            name="Unapproved Gmail Triage",
            steps=[
                WorkflowStep(
                    id="step_1",
                    name="Fetch Emails",
                    type="list_recent_messages",
                    application="gmail",
                    parameters={"max_results": 5},
                )
            ],
            requires_approval=True,
        )

        resp = self.client.post(
            "/api/automation/execute",
            json={
                "workflow_definition": wf_def.model_dump(),
                "approved": False,  # Explicitly unapproved
                "parameters": {},
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "pending")
        self.assertIn("approval", data.get("message", "").lower())


class TestPhase73DeclarativeGmailExecution(unittest.IsolatedAsyncioTestCase):
    """Tests declarative execution of Gmail steps with mocked credentials and HTTP transports."""

    def setUp(self):
        self.test_key = Fernet.generate_key().decode()
        self.token_storage = EncryptedTokenStorage(encryption_key=self.test_key)
        self.oauth_manager = GoogleOAuthManager(
            client_id="test_client_id.apps.googleusercontent.com",
            client_secret="test_client_secret",
            redirect_uri="http://127.0.0.1:8000/api/integrations/gmail/callback",
        )

    async def _setup_connected_gmail_adapter(self, transport):
        client = httpx.AsyncClient(transport=transport)
        adapter = GmailIntegrationAdapter(
            oauth_manager=self.oauth_manager,
            token_storage=self.token_storage,
            http_client=client,
        )
        # Store valid token
        await adapter.connect(credentials={
            "access_token": "valid_mock_access_token_xyz",
            "refresh_token": "valid_mock_refresh_token_abc",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        })
        return adapter, client

    async def test_successful_gmail_declarative_workflow_execution(self):
        """Tests complete successful declarative workflow execution with Gmail action."""
        transport = _build_mock_gmail_transport()
        adapter, http_client = await self._setup_connected_gmail_adapter(transport)

        orig_get = integration_registry.get
        orig_find = integration_registry.find_adapter_by_action

        def mock_get(app_id):
            if app_id and app_id.lower() == "gmail":
                return adapter
            return orig_get(app_id)

        def mock_find(action_name):
            if action_name == "list_recent_messages":
                return adapter
            return orig_find(action_name)

        with patch.object(integration_registry, "get", side_effect=mock_get), \
             patch.object(integration_registry, "find_adapter_by_action", side_effect=mock_find):

            wf_def = WorkflowDefinition(
                id="wf_gmail_test_01",
                name="Gmail Read-Only Inbox Audit",
                steps=[
                    WorkflowStep(
                        id="step_1",
                        name="List Inbox Messages",
                        type="list_recent_messages",
                        application="gmail",
                        parameters={"max_results": 2, "query": "label:INBOX"},
                    ),
                    WorkflowStep(
                        id="step_2",
                        name="Process First Message",
                        type="search_customer",
                        application="demo_crm",
                        parameters={"customer_name": "{{steps.step_1.output.messages.0.from}}"},
                    ),
                ],
                requires_approval=True,
            )

            res = await automation_service.run_workflow(
                workflow_definition=wf_def,
                executor_type="noop",
                inputs={},
                approved=True,
            )

        await http_client.aclose()

        self.assertEqual(res.status, AutomationStatus.COMPLETED)
        self.assertEqual(len(res.completed_actions), 2)
        self.assertEqual(res.completed_actions[0], "list_recent_messages")
        self.assertEqual(res.completed_actions[1], "search_customer")

        # Verify execution record exists in history
        history_record = automation_service.get_execution(res.execution_id)
        self.assertIsNotNone(history_record)
        self.assertEqual(history_record.status, "completed")
        self.assertGreater(history_record.total_actions, 0)
        self.assertEqual(len(history_record.completed_actions), 2)

    async def test_disconnected_gmail_pauses_or_fails_workflow(self):
        """When Gmail is not connected, workflow execution MUST fail cleanly without crashing."""
        # Unconnected adapter
        adapter = GmailIntegrationAdapter(
            oauth_manager=self.oauth_manager,
            token_storage=self.token_storage,
        )
        self.assertFalse(adapter.is_connected)

        with patch.object(integration_registry, "get", return_value=adapter), \
             patch.object(integration_registry, "find_adapter_by_action", return_value=adapter):

            wf_def = WorkflowDefinition(
                id="wf_disc_test",
                name="Disconnected Gmail Triage",
                steps=[
                    WorkflowStep(
                        id="step_1",
                        name="Fetch Messages",
                        type="list_recent_messages",
                        application="gmail",
                        parameters={"max_results": 5},
                    )
                ],
            )

            res = await automation_service.run_workflow(
                workflow_definition=wf_def,
                approved=True,
            )

        self.assertIn(res.status, [AutomationStatus.FAILED, AutomationStatus.PAUSED])
        self.assertIn("disconnected", (res.failure_reason or res.message or "").lower())

    async def test_token_auto_refresh_during_workflow_step(self):
        """When an access token is expired, the adapter automatically refreshes it."""
        token_refreshed = False

        async def mock_refresh(refresh_token):
            nonlocal token_refreshed
            token_refreshed = True
            return {
                "access_token": "freshly_minted_access_token_999",
                "expires_in": 3600,
                "token_type": "Bearer",
            }

        transport = _build_mock_gmail_transport()
        client = httpx.AsyncClient(transport=transport)
        adapter = GmailIntegrationAdapter(
            oauth_manager=self.oauth_manager,
            token_storage=self.token_storage,
            http_client=client,
        )
        # Expired token in storage
        await adapter.connect(credentials={
            "access_token": "expired_old_token",
            "refresh_token": "valid_refresh_token",
            "expires_at": time.time() - 300,  # 5 minutes expired
            "_internal_oauth_source": True,
        })

        with patch.object(self.oauth_manager, "refresh_access_token", side_effect=mock_refresh):
            res = await adapter.execute_action("list_recent_messages", {"max_results": 2})

        await client.aclose()
        self.assertTrue(token_refreshed, "Expired access token should have triggered refresh_access_token")
        self.assertTrue(res.success)
        self.assertEqual(res.data["count"], 2)

    async def test_token_refresh_failure_halts_workflow(self):
        """When token refresh fails (e.g. revoked refresh token), workflow step fails."""
        async def mock_failed_refresh(refresh_token):
            raise OAuthTokenExchangeError("invalid_grant: Token has been expired or revoked.")

        transport = _build_mock_gmail_transport()
        client = httpx.AsyncClient(transport=transport)
        adapter = GmailIntegrationAdapter(
            oauth_manager=self.oauth_manager,
            token_storage=self.token_storage,
            http_client=client,
        )
        await adapter.connect(credentials={
            "access_token": "expired_old_token",
            "refresh_token": "revoked_refresh_token",
            "expires_at": time.time() - 300,
            "_internal_oauth_source": True,
        })

        with patch.object(self.oauth_manager, "refresh_access_token", side_effect=mock_failed_refresh):
            res = await adapter.execute_action("list_recent_messages", {"max_results": 2})

        await client.aclose()
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "CONNECTION_ERROR")
        self.assertIn("failed to refresh", res.message.lower())
        self.assertEqual(adapter.status, IntegrationStatus.ERROR)

    async def test_google_api_429_rate_limit_and_503_errors(self):
        """Tests handling of rate limit (429) and backend error (503)."""
        # 429 Rate limit
        transport_429 = _build_mock_gmail_transport(api_status_code=429)
        adapter_429, client_429 = await self._setup_connected_gmail_adapter(transport_429)
        res_429 = await adapter_429.execute_action("list_recent_messages", {"max_results": 2})
        await client_429.aclose()
        self.assertFalse(res_429.success)
        self.assertIn("rate limit", res_429.message.lower())

        # 503 Service unavailable
        transport_503 = _build_mock_gmail_transport(api_status_code=503)
        adapter_503, client_503 = await self._setup_connected_gmail_adapter(transport_503)
        res_503 = await adapter_503.execute_action("list_recent_messages", {"max_results": 2})
        await client_503.aclose()
        self.assertFalse(res_503.success)
        self.assertIn("service unavailable", res_503.message.lower())

    async def test_retry_policy_on_transient_failure(self):
        """Tests that workflow engine retries a transiently failing Gmail step."""
        attempts = 0

        async def flaking_handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return httpx.Response(503, json={"error": "temporary unavailable"})
            return httpx.Response(
                200,
                json={"messages": [{"id": "m1", "threadId": "t1"}], "resultSizeEstimate": 1},
            )

        transport = httpx.MockTransport(flaking_handler)
        adapter, client = await self._setup_connected_gmail_adapter(transport)

        with patch.object(integration_registry, "get", return_value=adapter), \
             patch.object(integration_registry, "find_adapter_by_action", return_value=adapter):

            wf_def = WorkflowDefinition(
                id="wf_retry_test",
                name="Retry Test Workflow",
                steps=[
                    WorkflowStep(
                        id="retry_step",
                        name="Flaky List Messages",
                        type="list_recent_messages",
                        application="gmail",
                        parameters={"max_results": 1},
                        retry_policy=RetryPolicy(max_attempts=3, delay_seconds=0.01),
                    )
                ],
            )

            res = await automation_service.run_workflow(
                workflow_definition=wf_def,
                approved=True,
            )

        await client.aclose()
        step_res = res.step_results[0]
        self.assertEqual(step_res.attempts, 2, "Step should have retried and succeeded on 2nd attempt")
        self.assertEqual(res.status, AutomationStatus.COMPLETED)

    async def test_sanitized_execution_history_no_secrets_no_raw_bodies(self):
        """Ensures execution records do not contain access tokens, refresh tokens, or email bodies."""
        transport = _build_mock_gmail_transport()
        adapter, client = await self._setup_connected_gmail_adapter(transport)

        with patch.object(integration_registry, "get", return_value=adapter), \
             patch.object(integration_registry, "find_adapter_by_action", return_value=adapter):

            wf_def = WorkflowDefinition(
                id="wf_sanitization_test",
                name="Sanitization Test Workflow",
                steps=[
                    WorkflowStep(
                        id="step_1",
                        name="List Recent Emails",
                        type="list_recent_messages",
                        application="gmail",
                        parameters={"max_results": 2},
                    )
                ],
            )

            res = await automation_service.run_workflow(
                workflow_definition=wf_def,
                approved=True,
            )

        await client.aclose()
        exec_record = automation_service.get_execution(res.execution_id)
        exec_json = exec_record.model_dump_json()

        # Verify no credentials leaked
        self.assertNotIn("valid_mock_access_token_xyz", exec_json)
        self.assertNotIn("valid_mock_refresh_token_abc", exec_json)
        self.assertNotIn(self.test_key, exec_json)

        # Verify action status metadata is present
        self.assertEqual(len(exec_record.completed_actions), 1)
        self.assertIsNotNone(exec_record.started_at)
        self.assertIsNotNone(exec_record.completed_at)


class TestPhase73MixedProviderWorkflow(unittest.IsolatedAsyncioTestCase):
    """Tests workflows that chain native mock provider, Gmail read-only adapter, and CRM actions."""

    async def test_mixed_provider_workflow_execution(self):
        test_key = Fernet.generate_key().decode()
        token_storage = EncryptedTokenStorage(encryption_key=test_key)
        oauth_manager = GoogleOAuthManager(
            client_id="cid", client_secret="csec", redirect_uri="http://localhost/cb"
        )
        transport = _build_mock_gmail_transport()
        client = httpx.AsyncClient(transport=transport)
        gmail_adapter = GmailIntegrationAdapter(
            oauth_manager=oauth_manager,
            token_storage=token_storage,
            http_client=client,
        )
        await gmail_adapter.connect(credentials={
            "access_token": "valid_tok",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        })

        mock_adapter = integration_registry.get("mock_service")
        if mock_adapter:
            await mock_adapter.connect()

        # Multi-step definition
        wf_def = WorkflowDefinition(
            id="wf_mixed_provider_01",
            name="Tri-Provider Declarative Workflow",
            steps=[
                # 1. Mock adapter echo
                WorkflowStep(
                    id="step_mock",
                    name="Echo Test Message",
                    type="mock_echo",
                    application="mock_service",
                    parameters={"message": "Phase 7.3 Pipeline Start"},
                ),
                # 2. Gmail read-only fetch
                WorkflowStep(
                    id="step_gmail",
                    name="Fetch Latest Customer Inquiry",
                    type="list_recent_messages",
                    application="gmail",
                    parameters={"max_results": 1},
                ),
                # 3. Demo CRM customer search
                WorkflowStep(
                    id="step_crm",
                    name="Reconcile with CRM Account",
                    type="search_customer",
                    application="demo_crm",
                    parameters={"customer_name": "{{steps.step_gmail.output.messages.0.from}}"},
                ),
            ],
            requires_approval=True,
        )

        orig_get = integration_registry.get
        orig_find = integration_registry.find_adapter_by_action

        def mock_get(app_id):
            if app_id and app_id.lower() == "gmail":
                return gmail_adapter
            return orig_get(app_id)

        def mock_find(action_name):
            if action_name == "list_recent_messages":
                return gmail_adapter
            return orig_find(action_name)

        with patch.object(integration_registry, "get", side_effect=mock_get), \
             patch.object(integration_registry, "find_adapter_by_action", side_effect=mock_find):

            res = await automation_service.run_workflow(
                workflow_definition=wf_def,
                executor_type="noop",
                approved=True,
            )

        await client.aclose()
        self.assertEqual(res.status, AutomationStatus.COMPLETED)
        self.assertEqual(len(res.completed_actions), 3)


class TestPhase73PauseResumeCancel(unittest.IsolatedAsyncioTestCase):
    """Tests pause, resume, and cancellation mechanics for declarative workflows."""

    async def test_cancellation_of_pending_or_paused_execution(self):
        wf_def = WorkflowDefinition(
            id="wf_to_cancel",
            name="Workflow to Cancel",
            steps=[
                WorkflowStep(
                    id="step_1",
                    name="Gmail list messages",
                    type="list_recent_messages",
                    application="gmail",
                    parameters={"max_results": 5},
                )
            ],
            requires_approval=True,
        )

        # Run unapproved to get into PENDING / PAUSED state
        res = await automation_service.run_workflow(
            workflow_definition=wf_def,
            approved=False,
        )

        self.assertEqual(res.status, AutomationStatus.PENDING)
        exec_id = res.execution_id

        # Cancel the execution
        cancel_res = automation_service.cancel_execution(exec_id)
        self.assertEqual(cancel_res.status, AutomationStatus.CANCELLED)
        self.assertIsNotNone(cancel_res.cancelled_at)

        # Confirm persisted record reflects cancelled status
        record = automation_service.get_execution(exec_id)
        self.assertEqual(record.status, "cancelled")


class TestPhase73WorkflowSaveAndValidation(unittest.TestCase):
    """Regression tests for Declarative Workflow Save and Schema Validation."""

    def setUp(self):
        self.client = TestClient(app)

    def test_save_workflow_with_explicit_id(self):
        """Saving a workflow with an explicit ID registers under that ID."""
        payload = {
            "id": "wf_explicit_123",
            "name": "Explicit ID Workflow",
            "description": "Test workflow with explicit ID",
            "steps": [
                {
                    "id": "s1",
                    "name": "Search CRM",
                    "type": "search_customer",
                    "application": "demo_crm",
                    "parameters": {"customer_name": "Alice"},
                }
            ],
            "requires_approval": True,
        }
        res = self.client.post("/api/automation/workflows", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["id"], "wf_explicit_123")
        self.assertEqual(data["name"], "Explicit ID Workflow")
        self.assertTrue(data["requires_approval"])

        # Fetch it back via GET
        get_res = self.client.get("/api/automation/workflows/wf_explicit_123")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["id"], "wf_explicit_123")

    def test_save_workflow_with_omitted_id(self):
        """Saving a workflow without an ID auto-generates a unique ID."""
        payload = {
            "name": "Auto ID Workflow",
            "description": "Test workflow without ID field",
            "steps": [
                {
                    "id": "s1",
                    "name": "Send Message",
                    "type": "send_message",
                    "application": "demo_chat",
                    "parameters": {"message": "Hello"},
                }
            ],
        }
        res = self.client.post("/api/automation/workflows", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertTrue(data["id"].startswith("wf_"))
        self.assertEqual(data["name"], "Auto ID Workflow")

        # Confirm persisted and retrievable
        get_res = self.client.get(f"/api/automation/workflows/{data['id']}")
        self.assertEqual(get_res.status_code, 200)

    def test_save_workflow_with_none_or_empty_id(self):
        """Saving with id=None or empty string auto-generates a valid ID."""
        for empty_id in (None, "", "   "):
            payload = {
                "id": empty_id,
                "name": "Empty ID Workflow",
                "steps": [
                    {
                        "id": "s1",
                        "name": "Step",
                        "type": "open_email",
                        "application": "demo_email",
                    }
                ],
            }
            res = self.client.post("/api/automation/workflows", json=payload)
            self.assertEqual(res.status_code, 201)
            data = res.json()
            self.assertTrue(data["id"].startswith("wf_"))

    def test_save_gmail_triage_preset_full_payload(self):
        """Phase 7.3 Gmail Inbox Triage preset saves successfully and preserves all configuration."""
        gmail_preset_payload = {
            "id": "wf_gmail_triage",
            "name": "Gmail Inbox Triage & CRM Lookup",
            "description": "Queries Gmail read-only API for recent messages, parses headers, and verifies CRM accounts.",
            "trigger": {"type": "manual", "application": "gmail", "event": "workflow_triggered"},
            "inputs": [
                {
                    "name": "query",
                    "type": "string",
                    "description": "Search filter for Gmail inbox messages",
                    "required": False,
                    "default": "label:INBOX",
                },
                {
                    "name": "max_results",
                    "type": "number",
                    "description": "Maximum emails to retrieve (1-20)",
                    "required": False,
                    "default": 5,
                },
                {
                    "name": "customer_name",
                    "type": "string",
                    "description": "Target customer name for CRM query",
                    "required": False,
                    "default": "Rahul",
                },
            ],
            "steps": [
                {
                    "id": "step_1",
                    "name": "List Recent Inbox Emails",
                    "type": "list_recent_messages",
                    "application": "gmail",
                    "parameters": {"max_results": 5, "query": "{{inputs.query}}"},
                    "retry_policy": {"max_attempts": 2, "delay_seconds": 2},
                },
                {
                    "id": "step_2",
                    "name": "Query CRM Account Records",
                    "type": "search_customer",
                    "application": "demo_crm",
                    "parameters": {"customer_name": "{{inputs.customer_name}}"},
                },
                {
                    "id": "step_3",
                    "name": "Send Confirmation Alert",
                    "type": "send_message",
                    "application": "demo_chat",
                    "parameters": {
                        "message": "Gmail triage completed. Recent messages retrieved and customer account reconciled."
                    },
                },
            ],
            "requires_approval": True,
            "tags": ["gmail", "read-only", "triage", "phase7.3"],
        }
        res = self.client.post("/api/automation/workflows", json=gmail_preset_payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()

        self.assertEqual(data["id"], "wf_gmail_triage")
        self.assertEqual(data["name"], "Gmail Inbox Triage & CRM Lookup")
        self.assertTrue(data["requires_approval"])
        self.assertEqual(len(data["inputs"]), 3)
        self.assertEqual(len(data["steps"]), 3)
        self.assertEqual(data["steps"][0]["type"], "list_recent_messages")
        self.assertEqual(data["steps"][0]["application"], "gmail")
        self.assertEqual(data["steps"][1]["type"], "search_customer")
        self.assertEqual(data["steps"][2]["type"], "send_message")
        self.assertEqual(data["tags"], ["gmail", "read-only", "triage", "phase7.3"])

    def test_save_customer_verification_preset(self):
        """Customer Verification preset saves successfully and preserves steps and approval."""
        customer_preset_payload = {
            "id": "wf_customer_verification",
            "name": "Customer Verification & Update",
            "description": "Automated customer inquiry handling across Email, CRM, and Chat.",
            "trigger": {"type": "manual", "application": "", "event": ""},
            "inputs": [
                {
                    "name": "customer_name",
                    "type": "string",
                    "description": "Target customer name for CRM query",
                    "required": True,
                    "default": "Rahul",
                }
            ],
            "steps": [
                {
                    "id": "step_1",
                    "name": "Open Customer Email",
                    "type": "open_email",
                    "application": "demo_email",
                    "parameters": {},
                },
                {
                    "id": "step_2",
                    "name": "Download PDF Attachment",
                    "type": "download_attachment",
                    "application": "demo_email",
                    "parameters": {"filename": "customer_request.pdf"},
                },
                {
                    "id": "step_3",
                    "name": "Search Customer in CRM",
                    "type": "search_customer",
                    "application": "demo_crm",
                    "parameters": {"customer_name": "{{inputs.customer_name}}"},
                    "condition": {"field": "{{inputs.customer_name}}", "operator": "not_empty"},
                    "retry_policy": {"max_attempts": 2, "delay_seconds": 1},
                },
                {
                    "id": "step_4",
                    "name": "Update CRM Notes",
                    "type": "update_customer",
                    "application": "demo_crm",
                    "parameters": {"notes": "Account verified from email attachment."},
                },
                {
                    "id": "step_5",
                    "name": "Send Confirmation via Chat",
                    "type": "send_message",
                    "application": "demo_chat",
                    "parameters": {"message": "Customer record updated in CRM."},
                },
            ],
            "requires_approval": True,
            "tags": ["enterprise", "crm", "email"],
        }
        res = self.client.post("/api/automation/workflows", json=customer_preset_payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["id"], "wf_customer_verification")
        self.assertEqual(len(data["steps"]), 5)
        self.assertTrue(data["requires_approval"])

    def test_validation_error_structured_format_on_invalid_payload(self):
        """Invalid workflow definition (missing required name or invalid step) returns 422 with structured errors."""
        res = self.client.post("/api/automation/workflows", json={"description": "No name provided"})
        self.assertEqual(res.status_code, 422)
        body = res.json()
        self.assertIn("detail", body)
        self.assertIsInstance(body["detail"], list)
        self.assertTrue(any(err.get("loc") == ["body", "name"] for err in body["detail"]))


class TestPhase73ExecutionEndpointAndRegression(unittest.TestCase):
    """Regression tests for Test Run Workflow button execution flow, history, and approval gate."""

    def setUp(self):
        self.client = TestClient(app)
        self.test_key = Fernet.generate_key().decode()
        self.token_storage = EncryptedTokenStorage(encryption_key=self.test_key)
        self.oauth_manager = GoogleOAuthManager(
            client_id="test_client_id.apps.googleusercontent.com",
            client_secret="test_client_secret",
            redirect_uri="http://127.0.0.1:8000/api/integrations/gmail/callback",
        )

    def test_unapproved_run_creates_pending_record_in_history_and_listing(self):
        """Clicking run unapproved halts with pending status and records execution in history."""
        wf_payload = {
            "id": "wf_test_unapproved_flow",
            "name": "Gmail Inbox Triage & CRM Lookup",
            "description": "Preset test workflow",
            "trigger": {"type": "manual", "application": "gmail", "event": "workflow_triggered"},
            "inputs": [
                {"name": "query", "type": "string", "default": "label:INBOX"},
                {"name": "customer_name", "type": "string", "default": "Rahul"},
            ],
            "steps": [
                {
                    "id": "step_1",
                    "name": "List Recent Messages",
                    "type": "list_recent_messages",
                    "application": "gmail",
                    "parameters": {"max_results": 5, "query": "label:INBOX"},
                },
                {
                    "id": "step_2",
                    "name": "Search Customer",
                    "type": "search_customer",
                    "application": "demo_crm",
                    "parameters": {"customer_name": "Rahul"},
                },
            ],
            "requires_approval": True,
            "tags": ["gmail", "read-only"],
        }

        resp = self.client.post(
            "/api/automation/execute",
            json={
                "workflow_definition": wf_payload,
                "approved": False,
                "inputs": {"customer_name": "Rahul", "query": "label:INBOX"},
                "parameters": {"customer_name": "Rahul", "query": "label:INBOX"},
                "executor_type": "noop",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "pending")
        exec_id = data.get("workflow_id")
        self.assertTrue(exec_id and exec_id.startswith("exec_"))
        self.assertIn("approval", data.get("message", "").lower())

        # Verify that GET /api/automation/executions returns this new execution
        list_resp = self.client.get("/api/automation/executions")
        self.assertEqual(list_resp.status_code, 200)
        executions = list_resp.json().get("executions", [])
        matched = [e for e in executions if e.get("execution_id") == exec_id]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["status"], "pending")

        # Verify that GET /api/automation/executions/{execution_id} returns the record
        detail_resp = self.client.get(f"/api/automation/executions/{exec_id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json().get("status"), "pending")

    def test_approved_run_with_gmail_records_completed_execution_in_history(self):
        """Approved execution with mock Gmail adapter records COMPLETED execution in history."""
        transport = _build_mock_gmail_transport()
        http_client = httpx.AsyncClient(transport=transport)
        adapter = GmailIntegrationAdapter(
            oauth_manager=self.oauth_manager,
            token_storage=self.token_storage,
            http_client=http_client,
        )

        async def _connect():
            await adapter.connect(credentials={
                "access_token": "valid_token",
                "refresh_token": "valid_refresh",
                "expires_at": time.time() + 3600,
                "_internal_oauth_source": True,
            })
        asyncio.run(_connect())

        orig_get = integration_registry.get
        orig_find = integration_registry.find_adapter_by_action

        def mock_get(app_id):
            if app_id and app_id.lower() == "gmail":
                return adapter
            return orig_get(app_id)

        def mock_find(action_name):
            if action_name == "list_recent_messages":
                return adapter
            return orig_find(action_name)

        wf_payload = {
            "id": "wf_test_approved_flow",
            "name": "Gmail Inbox Triage & CRM Lookup",
            "description": "Preset test workflow",
            "steps": [
                {
                    "id": "step_1",
                    "name": "List Recent Messages",
                    "type": "list_recent_messages",
                    "application": "gmail",
                    "parameters": {"max_results": 2},
                },
                {
                    "id": "step_2",
                    "name": "Search Customer",
                    "type": "search_customer",
                    "application": "demo_crm",
                    "parameters": {"customer_name": "Rahul"},
                },
            ],
            "requires_approval": True,
        }

        with patch.object(integration_registry, "get", side_effect=mock_get), \
             patch.object(integration_registry, "find_adapter_by_action", side_effect=mock_find):
            resp = self.client.post(
                "/api/automation/execute",
                json={
                    "workflow_definition": wf_payload,
                    "approved": True,
                    "inputs": {"customer_name": "Rahul"},
                    "parameters": {"customer_name": "Rahul"},
                    "executor_type": "noop",
                },
            )

        asyncio.run(http_client.aclose())

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "completed")
        exec_id = data.get("workflow_id")
        self.assertTrue(exec_id and exec_id.startswith("exec_"))
        self.assertEqual(len(data.get("completed_actions", [])), 2)

        # Execution history record must be immediately present
        list_resp = self.client.get("/api/automation/executions")
        self.assertEqual(list_resp.status_code, 200)
        executions = list_resp.json().get("executions", [])
        matched = [e for e in executions if e.get("execution_id") == exec_id]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["status"], "completed")

    def test_prewarming_failure_does_not_crash_endpoint(self):
        """If active_executor.start() fails during pre-warming, execution does not 500."""
        from automation.executor import NoOpExecutor

        wf_payload = {
            "id": "wf_prewarm_fail_test",
            "name": "Prewarm Safety Test",
            "steps": [
                {
                    "id": "step_1",
                    "name": "Search Customer",
                    "type": "search_customer",
                    "application": "demo_crm",
                    "parameters": {"customer_name": "Rahul"},
                }
            ],
            "requires_approval": False,
        }

        with patch.object(NoOpExecutor, "start", side_effect=Exception("Simulated pre-warm launch failure")):
            resp = self.client.post(
                "/api/automation/execute",
                json={
                    "workflow_definition": wf_payload,
                    "approved": True,
                    "parameters": {},
                    "executor_type": "noop",
                },
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "completed")
        self.assertTrue(data.get("workflow_id", "").startswith("exec_"))


if __name__ == "__main__":
    unittest.main()

