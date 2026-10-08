#!/usr/bin/env python3
"""
WorkFlowOS Phase 7.2: Gmail OAuth 2.0 Integration & Read-Only Action Test Suite

Validates:
1. Google OAuth Manager & State Store:
   - Cryptographically random state generation, single-use enforcement, TTL expiration.
   - Safe validation and consumption of state tokens.
   - Missing/invalid client configuration handling.
   - Secure authorization URL generation.
   - Server-side code-for-token exchange and token refresh using mocked Google responses.
   - Token revocation safety without token leakage.
2. Credential Storage Safety:
   - Authenticated encryption (Fernet) round-trip.
   - Missing/invalid encryption key fail-closed behavior (no ephemeral key for real OAuth).
   - Tamper detection and safe credential deletion on disconnect.
3. Gmail Adapter:
   - Provider registration (is_mock=False) and connection state lifecycle.
   - Read-only action parameter validation (bounded to max 20 messages).
   - Mocked successful Gmail messages list and metadata retrieval.
   - Automatic access token refresh when expired.
   - Error handling for revoked tokens (401), rate limits (429), and network failures.
   - Response and exception sanitization (no secret leakage).
4. REST API Routes:
   - GET /api/integrations/gmail/connect (initiating OAuth flow and redirect).
   - GET /api/integrations/gmail/callback (error handling, state verification, token exchange).
   - GET /api/integrations/gmail/status and POST /api/integrations/gmail/disconnect.
5. Workflow Engine Compatibility & Approval Gate:
   - Approval gate enforcement on workflows containing Gmail actions (status PENDING when unapproved).
   - Execution of approved workflow steps targeting Gmail adapter.
"""

import os
import base64
import hashlib
import time
import asyncio
import unittest
from unittest.mock import patch
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
    CredentialStorageConfigurationError,
    sanitize_credential_dict,
    sanitize_log_message,
)
from integrations.oauth import (
    OAuthStateStore,
    GoogleOAuthManager,
    OAuthConfigurationError,
    OAuthTokenExchangeError,
    GMAIL_READONLY_SCOPE,
    default_oauth_state_store,
    default_google_oauth_manager,
)
from integrations.gmail import (
    GmailIntegrationAdapter,
    get_oauth_token_storage,
)
from automation.models import (
    WorkflowDefinition,
    WorkflowStep,
    AutomationStatus,
)
from automation.service import automation_service


def setUpModule():
    import mongomock_motor
    import backend.database as db_mod
    db_mod._mongo_client = mongomock_motor.AsyncMongoMockClient()
    db_mod._database = db_mod._mongo_client["workflowos"]

def tearDownModule():
    import backend.database as db_mod
    db_mod._mongo_client = None
    db_mod._database = None


class TestOAuthStateStore(unittest.TestCase):
    """Tests cryptographically secure state generation, single-use, and TTL."""

    def setUp(self):
        self.state_store = OAuthStateStore(default_ttl_seconds=600)

    def test_state_generation_and_uniqueness(self):
        s1 = self.state_store.create_state()
        s2 = self.state_store.create_state()
        self.assertIsInstance(s1, str)
        self.assertGreater(len(s1), 32)
        self.assertNotEqual(s1, s2)

    def test_state_single_use_consumption(self):
        state = self.state_store.create_state()
        # First validation must succeed
        self.assertTrue(self.state_store.validate_and_consume(state))
        # Second validation of the same state MUST fail (prevent replay attacks)
        self.assertFalse(self.state_store.validate_and_consume(state))

    def test_state_expiration(self):
        # Create state with negative TTL (already expired)
        expired_state = self.state_store.create_state(ttl_seconds=-1)
        self.assertFalse(self.state_store.validate_and_consume(expired_state))

    def test_invalid_or_missing_state(self):
        self.assertFalse(self.state_store.validate_and_consume(None))
        self.assertFalse(self.state_store.validate_and_consume(""))
        self.assertFalse(self.state_store.validate_and_consume("non_existent_state_token"))


class TestGoogleOAuthManager(unittest.IsolatedAsyncioTestCase):
    """Tests authorization URL generation and mocked token exchange."""

    def test_missing_config_fails_validation(self):
        unconfigured = GoogleOAuthManager(client_id="", client_secret="", redirect_uri="")
        self.assertFalse(unconfigured.is_configured())
        with self.assertRaises(OAuthConfigurationError):
            unconfigured.build_authorization_url(state="test_state")

    def test_authorization_url_construction(self):
        manager = GoogleOAuthManager(
            client_id="test-client-id.apps.googleusercontent.com",
            client_secret="test-client-secret",
            redirect_uri="http://localhost:8000/api/integrations/gmail/callback",
        )
        self.assertTrue(manager.is_configured())
        url = manager.build_authorization_url(state="secure_random_state_123")

        self.assertTrue(url.startswith("https://accounts.google.com/o/oauth2/v2/auth"))
        self.assertIn("client_id=test-client-id.apps.googleusercontent.com", url)
        self.assertIn("response_type=code", url)
        self.assertIn("access_type=offline", url)
        self.assertIn("prompt=consent", url)
        self.assertIn("state=secure_random_state_123", url)
        self.assertIn("scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.readonly", url)

    async def test_token_exchange_success(self):
        # Mock HTTP transport returning successful token response
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(str(request.url), "https://oauth2.googleapis.com/token")
            return httpx.Response(
                200,
                json={
                    "access_token": "mock_google_access_token_xyz",
                    "refresh_token": "mock_google_refresh_token_123",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    "scope": GMAIL_READONLY_SCOPE,
                },
            )

        mock_transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=mock_transport) as client:
            manager = GoogleOAuthManager(
                client_id="test-client-id",
                client_secret="test-client-secret",
                redirect_uri="http://localhost:8000/api/integrations/gmail/callback",
                http_client=client,
            )
            tokens = await manager.exchange_code_for_tokens("valid_auth_code_abc")

        self.assertEqual(tokens["access_token"], "mock_google_access_token_xyz")
        self.assertEqual(tokens["refresh_token"], "mock_google_refresh_token_123")
        self.assertEqual(tokens["token_type"], "Bearer")
        self.assertGreater(tokens["expires_at"], time.time())

    async def test_token_exchange_failure_safe_handling(self):
        # Mock HTTP transport returning 400 Bad Request
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={"error": "invalid_grant", "error_description": "Code was already redeemed."},
            )

        mock_transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=mock_transport) as client:
            manager = GoogleOAuthManager(
                client_id="test-client-id",
                client_secret="test-client-secret",
                redirect_uri="http://localhost:8000/api/integrations/gmail/callback",
                http_client=client,
            )
            with self.assertRaises(OAuthTokenExchangeError) as ctx:
                await manager.exchange_code_for_tokens("expired_code")
            self.assertIn("Google OAuth token exchange failed", str(ctx.exception))
            # Verify client secret is never included in error message
            self.assertNotIn("test-client-secret", str(ctx.exception))

    async def test_token_refresh_success(self):
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "access_token": "new_refreshed_access_token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    "scope": GMAIL_READONLY_SCOPE,
                },
            )

        mock_transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=mock_transport) as client:
            manager = GoogleOAuthManager(
                client_id="test-client-id",
                client_secret="test-client-secret",
                redirect_uri="http://localhost:8000/api/integrations/gmail/callback",
                http_client=client,
            )
            refreshed = await manager.refresh_access_token("existing_refresh_token")
            self.assertEqual(refreshed["access_token"], "new_refreshed_access_token")
            self.assertGreater(refreshed["expires_at"], time.time())


class TestEncryptedOAuthTokenStorage(unittest.IsolatedAsyncioTestCase):
    """Validates encrypted token storage security for OAuth credentials."""

    def test_fail_closed_without_encryption_key(self):
        # Real OAuth credential storage must NOT silently fall back to an ephemeral key
        with patch.dict(os.environ, {"WORKFLOWOS_CREDENTIAL_KEY": ""}):
            with self.assertRaises(CredentialStorageConfigurationError):
                EncryptedTokenStorage(encryption_key=None, allow_ephemeral_dev_key=False)

    async def test_token_encryption_roundtrip_and_tamper_detection(self):
        valid_key = Fernet.generate_key().decode("utf-8")
        storage = EncryptedTokenStorage(encryption_key=valid_key, allow_ephemeral_dev_key=False)

        creds = {
            "access_token": "ya29.secret_access_token_value",
            "refresh_token": "1//04secret_refresh_token_value",
            "expires_at": time.time() + 3600,
        }
        await storage.store_credential("gmail", creds)

        # Ciphertext inspection: internal store MUST NOT contain plaintext tokens
        raw_ciphertext = storage._store.get("gmail")
        self.assertIsNotNone(raw_ciphertext)
        self.assertNotIn("ya29.secret_access_token_value", raw_ciphertext)
        self.assertNotIn("1//04secret_refresh_token_value", raw_ciphertext)
        self.assertTrue(raw_ciphertext.startswith("gAAAAA"))

        # Decryption round trip
        retrieved = await storage.get_credential("gmail")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["access_token"], "ya29.secret_access_token_value")
        self.assertEqual(retrieved["refresh_token"], "1//04secret_refresh_token_value")

        # Tampering with ciphertext fails closed (returns None)
        storage._store["gmail"] = raw_ciphertext[:-6] + "TAMPER"
        self.assertIsNone(await storage.get_credential("gmail"))

        # Disconnect token purge
        storage._store["gmail"] = raw_ciphertext
        deleted = await storage.delete_credential("gmail")
        self.assertTrue(deleted)
        self.assertIsNone(await storage.get_credential("gmail"))


class TestGmailIntegrationAdapter(unittest.IsolatedAsyncioTestCase):
    """Validates Gmail integration adapter capabilities, execution, and error handling."""

    def setUp(self):
        self.fernet_key = Fernet.generate_key().decode("utf-8")
        self.token_storage = EncryptedTokenStorage(
            encryption_key=self.fernet_key,
            allow_ephemeral_dev_key=False
        )
        self.oauth_manager = GoogleOAuthManager(
            client_id="mock_client_id",
            client_secret="mock_client_secret",
            redirect_uri="http://localhost:8000/api/integrations/gmail/callback",
        )

    def test_adapter_registration_and_metadata(self):
        adapter = GmailIntegrationAdapter(
            oauth_manager=self.oauth_manager,
            token_storage=self.token_storage
        )
        self.assertEqual(adapter.id, "gmail")
        self.assertEqual(adapter.name, "Gmail")
        self.assertFalse(adapter.metadata.is_mock)
        self.assertEqual(adapter.metadata.category, "email")
        self.assertIn("list_recent_messages", adapter.declared_action_names)

        # Check action safety policy
        action_def = adapter.get_action("list_recent_messages")
        self.assertIsNotNone(action_def)
        self.assertTrue(action_def.is_safe)
        self.assertFalse(action_def.is_mutating)
        self.assertFalse(action_def.is_destructive)
        self.assertFalse(action_def.allow_direct_execution)

    async def test_connect_stores_credentials_and_preserves_refresh_token(self):
        adapter = GmailIntegrationAdapter(
            oauth_manager=self.oauth_manager,
            token_storage=self.token_storage
        )

        initial_creds = {
            "access_token": "initial_access_token",
            "refresh_token": "original_refresh_token_to_preserve",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        }
        connected = await adapter.connect(credentials=initial_creds)
        self.assertTrue(connected)
        self.assertTrue(adapter.is_connected)
        self.assertEqual(adapter.status, IntegrationStatus.CONNECTED)

        # Reconnect with new access token where Google omitted refresh token
        update_creds = {
            "access_token": "updated_access_token",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        }
        reconnected = await adapter.connect(credentials=update_creds)
        self.assertTrue(reconnected)

        stored = await self.token_storage.get_credential("gmail")
        self.assertEqual(stored["access_token"], "updated_access_token")
        self.assertEqual(stored["refresh_token"], "original_refresh_token_to_preserve")

    async def test_parameter_validation_bounds(self):
        adapter = GmailIntegrationAdapter(
            oauth_manager=self.oauth_manager,
            token_storage=self.token_storage
        )
        await adapter.connect(credentials={
            "access_token": "tok",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        })

        # max_results > 20 rejected
        res_large = await adapter.execute_action("list_recent_messages", {"max_results": 50})
        self.assertFalse(res_large.success)
        self.assertEqual(res_large.error_code, "VALIDATION_ERROR")
        self.assertIn("cannot exceed 20", res_large.message)

        # max_results < 1 rejected
        res_zero = await adapter.execute_action("list_recent_messages", {"max_results": 0})
        self.assertFalse(res_zero.success)
        self.assertEqual(res_zero.error_code, "VALIDATION_ERROR")

    async def test_list_recent_messages_success_mocked(self):
        # Mock Gmail REST API endpoints
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            # 1. Message list endpoint
            if "/messages?maxResults=" in url_str:
                self.assertIn("Bearer valid_access_token_123", request.headers.get("Authorization", ""))
                return httpx.Response(
                    200,
                    json={
                        "messages": [
                            {"id": "msg_001", "threadId": "th_001"},
                            {"id": "msg_002", "threadId": "th_002"},
                        ],
                        "resultSizeEstimate": 2,
                    },
                )
            # 2. Message detail endpoint
            elif "/messages/msg_001" in url_str:
                return httpx.Response(
                    200,
                    json={
                        "id": "msg_001",
                        "threadId": "th_001",
                        "snippet": "Meeting notes from Monday morning sync",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "alice@example.com"},
                                {"name": "Subject", "value": "Sprint Planning Recap"},
                                {"name": "Date", "value": "Mon, 05 Oct 2026 09:30:00 GMT"},
                            ]
                        },
                    },
                )
            elif "/messages/msg_002" in url_str:
                return httpx.Response(
                    200,
                    json={
                        "id": "msg_002",
                        "threadId": "th_002",
                        "snippet": "Invoice for cloud services is available",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "billing@cloud.provider"},
                                {"name": "Subject", "value": "Monthly Cloud Invoice"},
                                {"name": "Date", "value": "Sun, 04 Oct 2026 12:00:00 GMT"},
                            ]
                        },
                    },
                )
            return httpx.Response(404, json={"error": "not found"})

        mock_transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=mock_transport) as client:
            adapter = GmailIntegrationAdapter(
                oauth_manager=self.oauth_manager,
                token_storage=self.token_storage,
                http_client=client,
            )
            await adapter.connect(credentials={
                "access_token": "valid_access_token_123",
                "refresh_token": "valid_refresh_token_456",
                "expires_at": time.time() + 3600,
                "_internal_oauth_source": True,
            })

            res = await adapter.execute_action(
                action_name="list_recent_messages",
                parameters={"max_results": 2, "query": "is:unread"},
            )

        self.assertTrue(res.success)
        self.assertIsNotNone(res.data)
        self.assertEqual(res.data["count"], 2)
        self.assertEqual(res.data["query"], "is:unread")
        messages = res.data["messages"]
        self.assertEqual(len(messages), 2)

        self.assertEqual(messages[0]["id"], "msg_001")
        self.assertEqual(messages[0]["subject"], "Sprint Planning Recap")
        self.assertEqual(messages[0]["from"], "alice@example.com")
        self.assertEqual(messages[0]["snippet"], "Meeting notes from Monday morning sync")

        self.assertEqual(messages[1]["id"], "msg_002")
        self.assertEqual(messages[1]["subject"], "Monthly Cloud Invoice")

    async def test_list_recent_messages_handles_revocation_401(self):
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "invalid_token"})

        mock_transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=mock_transport) as client:
            adapter = GmailIntegrationAdapter(
                oauth_manager=self.oauth_manager,
                token_storage=self.token_storage,
                http_client=client,
            )
            await adapter.connect(credentials={
                "access_token": "revoked_token",
                "expires_at": time.time() + 3600,
                "_internal_oauth_source": True,
            })

            res = await adapter.execute_action("list_recent_messages", {})

        self.assertFalse(res.success)
        self.assertIn("expired or was revoked", res.message)
        self.assertEqual(adapter.status, IntegrationStatus.ERROR)

    async def test_list_recent_messages_rate_limit_429(self):
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "rate_limit_exceeded"})

        mock_transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=mock_transport) as client:
            adapter = GmailIntegrationAdapter(
                oauth_manager=self.oauth_manager,
                token_storage=self.token_storage,
                http_client=client,
            )
            await adapter.connect(credentials={
                "access_token": "active_token",
                "expires_at": time.time() + 3600,
                "_internal_oauth_source": True,
            })

            res = await adapter.execute_action("list_recent_messages", {})

        self.assertFalse(res.success)
        self.assertIn("rate limit exceeded", res.message)


class TestGmailWorkflowExecutionAndApproval(unittest.IsolatedAsyncioTestCase):
    """Validates workflow engine compatibility and approval gate enforcement for Gmail actions."""

    async def asyncSetUp(self):
        self.fernet_key = Fernet.generate_key().decode("utf-8")
        self.token_storage = EncryptedTokenStorage(
            encryption_key=self.fernet_key,
            allow_ephemeral_dev_key=False
        )

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "/messages?maxResults=" in url_str:
                return httpx.Response(
                    200,
                    json={"messages": [{"id": "wf_msg_10", "threadId": "th_10"}]},
                )
            elif "/messages/wf_msg_10" in url_str:
                return httpx.Response(
                    200,
                    json={
                        "id": "wf_msg_10",
                        "threadId": "th_10",
                        "snippet": "Approved workflow message content",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "system@workflowos.io"},
                                {"name": "Subject", "value": "Security Audit Report"},
                                {"name": "Date", "value": "Sun, 04 Oct 2026 12:00:00 GMT"},
                            ]
                        },
                    },
                )
            elif "oauth2.googleapis.com/revoke" in url_str:
                return httpx.Response(200, json={"status": "revoked"})
            return httpx.Response(404, json={})

        self.mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        self.oauth_manager = GoogleOAuthManager(
            client_id="mock_client_id",
            client_secret="mock_client_secret",
            redirect_uri="http://localhost:8000/api/integrations/gmail/callback",
            http_client=self.mock_client,
        )
        self.adapter = GmailIntegrationAdapter(
            oauth_manager=self.oauth_manager,
            token_storage=self.token_storage,
            http_client=self.mock_client,
        )
        await self.adapter.connect(credentials={
            "access_token": "wf_token",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        })
        # Register in global registry for workflow executor lookup
        integration_registry.unregister("gmail")
        integration_registry.register(self.adapter)

    async def asyncTearDown(self):
        await self.adapter.disconnect()
        await self.mock_client.aclose()

    async def test_workflow_approval_gate_blocks_unapproved_gmail_step(self):
        """Unapproved workflow containing Gmail action must be refused and remain in PENDING status."""
        wf = WorkflowDefinition(
            id="wf_gmail_unapproved_test",
            name="Unapproved Gmail Inspection",
            steps=[
                WorkflowStep(
                    id="step_read_mail",
                    name="Read Mail Metadata",
                    type="list_recent_messages",
                    application="gmail",
                    parameters={"max_results": 1},
                )
            ],
            requires_approval=True,
        )

        execution = await automation_service.run_workflow(
            workflow_definition=wf,
            approved=False,
            executor_type="integration",
        )

        self.assertEqual(execution.status, AutomationStatus.PENDING)
        self.assertEqual(len(execution.completed_actions), 0)

    async def test_workflow_executes_approved_gmail_step(self):
        """Approved workflow with Gmail action executes successfully and maps outputs."""
        wf = WorkflowDefinition(
            id="wf_gmail_approved_test",
            name="Approved Gmail Inspection",
            steps=[
                WorkflowStep(
                    id="step_read_mail",
                    name="Read Mail Metadata",
                    type="list_recent_messages",
                    application="gmail",
                    parameters={"max_results": 1},
                    output_mapping={"mail_count": "data.count"},
                )
            ],
            requires_approval=True,
        )

        execution = await automation_service.run_workflow(
            workflow_definition=wf,
            approved=True,
            executor_type="integration",
        )

        self.assertEqual(execution.status, AutomationStatus.COMPLETED)
        self.assertEqual(len(execution.completed_actions), 1)
        self.assertIn("list_recent_messages", execution.completed_actions)
        self.assertEqual(execution.variables.get("mail_count"), 1)


class TestGmailStorageLifecycle(unittest.IsolatedAsyncioTestCase):
    """SEC-01: Verifies that the Gmail adapter maintains a single shared CredentialStorage instance."""

    async def test_storage_instance_reuse_and_credential_persistence(self):
        """Adapter must memoize and reuse _token_storage, keeping credentials available across calls."""
        key = Fernet.generate_key().decode("utf-8")
        import os
        old_key = os.environ.get("WORKFLOWOS_CREDENTIAL_KEY")
        os.environ["WORKFLOWOS_CREDENTIAL_KEY"] = key
        try:
            adapter = GmailIntegrationAdapter()
            # Separate calls to _get_storage() must return the identical object reference
            s1 = adapter._get_storage()
            s2 = adapter._get_storage()
            self.assertIs(s1, s2, "Separate calls to _get_storage() must return the identical instance.")

            # Connect adapter using default storage
            connect_creds = {
                "access_token": "ya29.persistent_token_abc",
                "expires_at": time.time() + 3600,
                "_internal_oauth_source": True,
            }
            success = await adapter.connect(credentials=connect_creds)
            self.assertTrue(success)

            # Subsequent token retrieval must succeed on the same adapter instance
            token = await adapter.get_valid_access_token()
            self.assertEqual(token, "ya29.persistent_token_abc")
        finally:
            if old_key:
                os.environ["WORKFLOWOS_CREDENTIAL_KEY"] = old_key
            else:
                os.environ.pop("WORKFLOWOS_CREDENTIAL_KEY", None)


class TestGmailConcurrency(unittest.IsolatedAsyncioTestCase):
    """SEC-03: Verifies that concurrent access token refresh is serialized and executes only once."""

    async def test_concurrent_token_refresh_single_execution(self):
        refresh_call_count = 0

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal refresh_call_count
            if "oauth2.googleapis.com/token" in str(request.url):
                refresh_call_count += 1
                # Small async sleep to ensure competing coroutines arrive while in-flight
                await asyncio.sleep(0.02)
                return httpx.Response(
                    200,
                    json={
                        "access_token": "new_refreshed_concurrent_token",
                        "expires_in": 3600,
                        "token_type": "Bearer",
                    },
                )
            return httpx.Response(200, json={})

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        key = Fernet.generate_key().decode("utf-8")
        storage = EncryptedTokenStorage(encryption_key=key, allow_ephemeral_dev_key=False)
        oauth_mgr = GoogleOAuthManager(
            client_id="cid", client_secret="csec", redirect_uri="http://localhost:8000/cb",
            http_client=mock_client
        )
        adapter = GmailIntegrationAdapter(
            oauth_manager=oauth_mgr,
            token_storage=storage,
            http_client=mock_client,
        )

        # Store expired token with valid refresh token
        await storage.store_credential("gmail", {
            "access_token": "expired_token",
            "refresh_token": "valid_refresh_token_to_keep",
            "expires_at": time.time() - 10,
        })
        adapter._status = IntegrationStatus.CONNECTED

        # Launch 10 simultaneous coroutines requesting valid access token
        tasks = [adapter.get_valid_access_token() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All 10 tasks must receive the new refreshed token
        for tok in results:
            self.assertEqual(tok, "new_refreshed_concurrent_token")

        # Refresh network call count MUST be exactly 1
        self.assertEqual(refresh_call_count, 1)

        # Existing refresh token must be preserved
        saved = await storage.get_credential("gmail")
        self.assertEqual(saved["refresh_token"], "valid_refresh_token_to_keep")


class TestSanitizationHygiene(unittest.TestCase):
    """SEC-06: Verifies that log and exception messages redact sensitive secrets."""

    def test_sanitize_log_message_scrubs_secrets(self):
        msg = "Error: Bearer ya29.secretToken123+45/67= occurred with password='mySuperSecretPassword!'"
        clean = sanitize_log_message(msg)
        self.assertNotIn("ya29.secretToken123", clean)
        self.assertNotIn("mySuperSecretPassword", clean)
        self.assertIn("Bearer [REDACTED]", clean)
        self.assertIn("password='[REDACTED]'", clean)

    def test_sanitize_basic_auth_header(self):
        msg = "Connecting with Basic dXNlcjpwYXNzd29yZDEyMw=="
        clean = sanitize_log_message(msg)
        self.assertNotIn("dXNlcjpwYXNzd29yZDEyMw==", clean)
        self.assertIn("Basic [REDACTED]", clean)


class TestGmailOAuthRoutes(unittest.TestCase):
    """Tests FastAPI REST endpoints for Gmail OAuth connect, callback, status, and disconnect."""

    @classmethod
    def setUpClass(cls):
        import os
        cls._saved_key = os.environ.get("WORKFLOWOS_CREDENTIAL_KEY")
        cls.test_key = Fernet.generate_key().decode("utf-8")
        os.environ["WORKFLOWOS_CREDENTIAL_KEY"] = cls.test_key

    @classmethod
    def tearDownClass(cls):
        import os
        if cls._saved_key:
            os.environ["WORKFLOWOS_CREDENTIAL_KEY"] = cls._saved_key
        else:
            os.environ.pop("WORKFLOWOS_CREDENTIAL_KEY", None)

    def setUp(self):
        self.client = TestClient(app)

    def test_connect_endpoint_unconfigured_error(self):
        """When Google client is not configured, /connect redirects with error parameter."""
        orig_id = default_google_oauth_manager._client_id
        default_google_oauth_manager._client_id = ""
        try:
            res = self.client.get("/api/integrations/gmail/connect", follow_redirects=False)
            self.assertEqual(res.status_code, 307)
            self.assertIn("status=error", res.headers.get("location", ""))
            self.assertIn("Google+OAuth+client+credentials+are+not+configured", res.headers.get("location", ""))
        finally:
            default_google_oauth_manager._client_id = orig_id

    def test_connect_endpoint_success_redirects_to_google_and_sets_cookie(self):
        """SEC-02: When configured, /connect creates CSRF state, sets cookie, and redirects to Google."""
        default_google_oauth_manager._client_id = "configured-id.apps.googleusercontent.com"
        default_google_oauth_manager._client_secret = "configured-secret"
        default_google_oauth_manager._redirect_uri = "http://localhost:8000/api/integrations/gmail/callback"

        res = self.client.get("/api/integrations/gmail/connect", follow_redirects=False)
        self.assertEqual(res.status_code, 307)
        loc = res.headers.get("location", "")
        self.assertTrue(loc.startswith("https://accounts.google.com/o/oauth2/v2/auth"))
        self.assertIn("client_id=configured-id.apps.googleusercontent.com", loc)
        self.assertIn("state=", loc)

        # SEC-02: Verify session binding cookie is set
        set_cookie = res.headers.get("set-cookie", "")
        self.assertIn("workflowos_oauth_state=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("samesite=lax", set_cookie.lower())

    def test_connect_endpoint_aligns_loopback_hosts(self):
        """SEC-02: If browser arrives via localhost but redirect_uri is 127.0.0.1, connect redirects to align origins."""
        default_google_oauth_manager._client_id = "configured-id.apps.googleusercontent.com"
        default_google_oauth_manager._client_secret = "configured-secret"
        orig_uri = default_google_oauth_manager._redirect_uri
        default_google_oauth_manager._redirect_uri = "http://127.0.0.1:8000/api/integrations/gmail/callback"

        try:
            localhost_client = TestClient(app, base_url="http://localhost:8000")
            res = localhost_client.get("/api/integrations/gmail/connect", follow_redirects=False)
            self.assertEqual(res.status_code, 307)
            self.assertEqual(res.headers.get("location"), "http://127.0.0.1:8000/api/integrations/gmail/connect")
        finally:
            default_google_oauth_manager._redirect_uri = orig_uri

    def test_callback_handles_error_param_and_clears_cookie(self):
        """SEC-02: When user denies consent, callback safely redirects to frontend and clears cookie."""
        self.client.cookies.set("workflowos_oauth_state", "test_state", path="/api/integrations/gmail")
        res = self.client.get(
            "/api/integrations/gmail/callback?error=access_denied&error_description=User+declined+permissions",
            follow_redirects=False,
        )
        self.assertEqual(res.status_code, 307)
        loc = res.headers.get("location", "")
        self.assertIn("status=error", loc)
        self.assertIn("access_denied", loc)
        set_cookie = res.headers.get("set-cookie", "")
        self.assertTrue("max-age=0" in set_cookie.lower() or "expires=" in set_cookie.lower())

    def test_callback_rejects_missing_cookie(self):
        """SEC-02: Callback must reject requests without matching session cookie (login CSRF)."""
        state = default_oauth_state_store.create_state()
        res = self.client.get(
            f"/api/integrations/gmail/callback?code=some_code&state={state}",
            follow_redirects=False,
        )
        self.assertEqual(res.status_code, 307)
        loc = res.headers.get("location", "")
        self.assertIn("status=error", loc)
        self.assertIn("Invalid+or+missing+OAuth+session+binding", loc)

    def test_callback_rejects_mismatched_cookie(self):
        """SEC-02: Callback must reject requests where cookie does not match returned state."""
        state = default_oauth_state_store.create_state()
        self.client.cookies.set("workflowos_oauth_state", "different_state_abc", path="/api/integrations/gmail")
        res = self.client.get(
            f"/api/integrations/gmail/callback?code=some_code&state={state}",
            follow_redirects=False,
        )
        self.assertEqual(res.status_code, 307)
        loc = res.headers.get("location", "")
        self.assertIn("status=error", loc)
        self.assertIn("Invalid+or+missing+OAuth+session+binding", loc)

    def test_callback_rejects_invalid_or_expired_state(self):
        """Callback must reject invalid, missing, or expired state tokens."""
        self.client.cookies.set("workflowos_oauth_state", "fake_state", path="/api/integrations/gmail")
        res = self.client.get(
            "/api/integrations/gmail/callback?code=some_code&state=fake_state",
            follow_redirects=False,
        )
        self.assertEqual(res.status_code, 307)
        loc = res.headers.get("location", "")
        self.assertIn("status=error", loc)
        self.assertIn("Invalid+or+expired", loc)

    def test_callback_success_mocked(self):
        """SEC-02: Valid code and state with matching cookie exchanges token, saves credentials, clears cookie."""
        state = default_oauth_state_store.create_state()
        self.client.cookies.set("workflowos_oauth_state", state, path="/api/integrations/gmail")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "access_token": "test_callback_access_token",
                    "refresh_token": "test_callback_refresh_token",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    "scope": GMAIL_READONLY_SCOPE,
                },
            )

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        orig_http = default_google_oauth_manager._http_client
        default_google_oauth_manager._http_client = mock_client
        default_google_oauth_manager._client_id = "test-client"
        default_google_oauth_manager._client_secret = "test-secret"
        default_google_oauth_manager._redirect_uri = "http://localhost:8000/api/integrations/gmail/callback"

        try:
            res = self.client.get(
                f"/api/integrations/gmail/callback?code=auth_code_123&state={state}",
                follow_redirects=False,
            )
            self.assertEqual(res.status_code, 307)
            loc = res.headers.get("location", "")
            self.assertIn("status=connected", loc)
            self.assertIn("integration=gmail", loc)
            # Cookie must be cleared after exchange
            set_cookie = res.headers.get("set-cookie", "")
            self.assertTrue("max-age=0" in set_cookie.lower() or "expires=" in set_cookie.lower())
        finally:
            default_google_oauth_manager._http_client = orig_http

    def test_status_endpoint(self):
        """GET /api/integrations/gmail/status returns adapter summary."""
        res = self.client.get("/api/integrations/gmail/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["id"], "gmail")
        self.assertIn("list_recent_messages", [a["name"] for a in data["actions"]])

    def test_disconnect_valid_configured_frontend_origins(self):
        """SEC-04: Disconnect endpoint allows explicitly configured frontend origins even with Sec-Fetch-Site: cross-site."""
        # 1. http://localhost:3000 with cross-site (standard Next.js to FastAPI in local dev)
        res_lh_cross = self.client.post(
            "/api/integrations/gmail/disconnect",
            headers={
                "Origin": "http://localhost:3000",
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-Mode": "cors",
            }
        )
        self.assertEqual(res_lh_cross.status_code, 200)
        self.assertEqual(res_lh_cross.json()["status"], "disconnected")

        # 2. http://127.0.0.1:3000 with cross-site
        res_ip_cross = self.client.post(
            "/api/integrations/gmail/disconnect",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-Mode": "cors",
            }
        )
        self.assertEqual(res_ip_cross.status_code, 200)

        # 3. http://localhost:3000 with same-site
        res_same_site = self.client.post(
            "/api/integrations/gmail/disconnect",
            headers={
                "Origin": "http://localhost:3000",
                "Sec-Fetch-Site": "same-site",
            }
        )
        self.assertEqual(res_same_site.status_code, 200)

        # 4. Trailing slash normalized
        res_slash = self.client.post(
            "/api/integrations/gmail/disconnect",
            headers={"Origin": "http://localhost:3000/"}
        )
        self.assertEqual(res_slash.status_code, 200)

    def test_disconnect_untrusted_origins_rejected(self):
        """SEC-04: Disconnect endpoint rejects untrusted origins with 403 Forbidden."""
        # 1. External malicious origin
        res_untrusted = self.client.post(
            "/api/integrations/gmail/disconnect",
            headers={"Origin": "https://attacker-site.com"}
        )
        self.assertEqual(res_untrusted.status_code, 403)
        self.assertIn("Untrusted origin", res_untrusted.json()["detail"])

        # 2. External malicious origin with Sec-Fetch-Site: cross-site
        res_cross_untrusted = self.client.post(
            "/api/integrations/gmail/disconnect",
            headers={
                "Origin": "https://attacker-site.com",
                "Sec-Fetch-Site": "cross-site",
            }
        )
        self.assertEqual(res_cross_untrusted.status_code, 403)
        self.assertIn("Untrusted origin", res_cross_untrusted.json()["detail"])

        # 3. Domain prefix/suffix evasion attempt
        res_subdomain = self.client.post(
            "/api/integrations/gmail/disconnect",
            headers={"Origin": "http://localhost:3000.attacker.com"}
        )
        self.assertEqual(res_subdomain.status_code, 403)
        self.assertIn("Untrusted origin", res_subdomain.json()["detail"])

        # 4. Unconfigured localhost port
        res_wrong_port = self.client.post(
            "/api/integrations/gmail/disconnect",
            headers={"Origin": "http://localhost:8080"}
        )
        self.assertEqual(res_wrong_port.status_code, 403)
        self.assertIn("Untrusted origin", res_wrong_port.json()["detail"])

    def test_disconnect_missing_or_invalid_origin_handled_securely(self):
        """SEC-04: Disconnect endpoint securely handles missing or invalid Origin headers."""
        # 1. Empty Origin header rejected
        res_empty = self.client.post(
            "/api/integrations/gmail/disconnect",
            headers={"Origin": ""}
        )
        self.assertEqual(res_empty.status_code, 403)
        self.assertIn("Untrusted origin", res_empty.json()["detail"])

        # 2. Opaque / sandboxed Origin 'null' rejected
        res_null = self.client.post(
            "/api/integrations/gmail/disconnect",
            headers={"Origin": "null"}
        )
        self.assertEqual(res_null.status_code, 403)
        self.assertIn("Untrusted origin", res_null.json()["detail"])

        # 3. Cross-site browser request missing Origin rejected
        res_cross_no_origin = self.client.post(
            "/api/integrations/gmail/disconnect",
            headers={"Sec-Fetch-Site": "cross-site"}
        )
        self.assertEqual(res_cross_no_origin.status_code, 403)
        self.assertIn("Cross-origin request rejected", res_cross_no_origin.json()["detail"])

        # 4. Browser request (Sec-Fetch-Mode) missing both Origin and Referer rejected
        res_browser_no_ref = self.client.post(
            "/api/integrations/gmail/disconnect",
            headers={"Sec-Fetch-Mode": "cors"}
        )
        self.assertEqual(res_browser_no_ref.status_code, 403)
        self.assertIn("missing Origin/Referer", res_browser_no_ref.json()["detail"])

        # 5. Browser request with untrusted Referer rejected
        res_bad_ref = self.client.post(
            "/api/integrations/gmail/disconnect",
            headers={
                "Sec-Fetch-Mode": "cors",
                "Referer": "https://malicious-site.com/exploit",
            }
        )
        self.assertEqual(res_bad_ref.status_code, 403)
        self.assertIn("Untrusted referer", res_bad_ref.json()["detail"])

        # 6. Browser request with trusted Referer allowed
        res_good_ref = self.client.post(
            "/api/integrations/gmail/disconnect",
            headers={
                "Sec-Fetch-Mode": "cors",
                "Referer": "http://localhost:3000/?view=settings",
            }
        )
        self.assertEqual(res_good_ref.status_code, 200)

        # 7. Safe programmatic CLI request (no browser headers) succeeds
        res_cli = self.client.post("/api/integrations/gmail/disconnect")
        self.assertEqual(res_cli.status_code, 200)
        data = res_cli.json()
        self.assertEqual(data["id"], "gmail")
        self.assertEqual(data["status"], "disconnected")
        self.assertFalse(data["is_connected"])

    def test_disconnect_successful_credential_cleanup(self):
        """Disconnect endpoint revokes token with Google, purges local credentials, and updates status."""
        adapter = integration_registry.get("gmail")
        self.assertIsNotNone(adapter)
        storage = adapter._get_storage()

        # Connect adapter with credentials
        async def _setup():
            await adapter.connect(credentials={
                "access_token": "ya29.test_disconnect_token",
                "refresh_token": "1//04test_refresh_token",
                "expires_at": time.time() + 3600,
                "_internal_oauth_source": True,
            })

        asyncio.run(_setup())
        self.assertTrue(adapter.is_connected)

        # Mock revoke_token on oauth_manager
        revoked_tokens = []
        orig_revoke = adapter._oauth_manager.revoke_token
        async def mock_revoke(tok):
            revoked_tokens.append(tok)
            return True
        adapter._oauth_manager.revoke_token = mock_revoke

        try:
            # Issue disconnect from configured frontend origin with Sec-Fetch-Site: cross-site
            res = self.client.post(
                "/api/integrations/gmail/disconnect",
                headers={
                    "Origin": "http://localhost:3000",
                    "Sec-Fetch-Site": "cross-site",
                }
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["id"], "gmail")
            self.assertEqual(data["status"], "disconnected")
            self.assertFalse(data["is_connected"])

            # Verify adapter status updated
            self.assertFalse(adapter.is_connected)

            # Verify storage credentials deleted
            async def _check_storage():
                return await storage.get_credential("gmail")
            saved = asyncio.run(_check_storage())
            self.assertIsNone(saved)

            # Verify revoke_token was called
            self.assertTrue(len(revoked_tokens) > 0)
            self.assertIn("1//04test_refresh_token", revoked_tokens)

            # Verify GET /status reflects disconnected state
            status_res = self.client.get("/api/integrations/gmail/status")
            self.assertEqual(status_res.status_code, 200)
            self.assertEqual(status_res.json()["status"], "disconnected")
            self.assertFalse(status_res.json()["is_connected"])
        finally:
            adapter._oauth_manager.revoke_token = orig_revoke
            async def _cleanup():
                await storage.delete_credential("gmail")
            asyncio.run(_cleanup())

    def test_generic_connect_endpoint_rejects_gmail_direct_credentials(self):
        """SEC-05: Direct manual credential submission to generic connect endpoint must be rejected."""
        res = self.client.post(
            "/api/integrations/gmail/connect",
            json={"credentials": {"access_token": "unauthorized_manual_token"}}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("OAuth 2.0 authorization", res.json()["detail"])


class TestGmailDirectConnectRejection(unittest.IsolatedAsyncioTestCase):
    """SEC-05: Verifies that GmailIntegrationAdapter._do_connect rejects direct credentials and prevents overwrite."""

    async def test_adapter_direct_credential_injection_rejected(self):
        key = Fernet.generate_key().decode("utf-8")
        storage = EncryptedTokenStorage(encryption_key=key, allow_ephemeral_dev_key=False)
        adapter = GmailIntegrationAdapter(token_storage=storage)
        success = await adapter.connect(credentials={"access_token": "manual_injected_token"})
        self.assertFalse(success)
        self.assertIn("Direct credential submission is not permitted", adapter.last_error)

    async def test_adapter_cannot_overwrite_existing_credentials(self):
        key = Fernet.generate_key().decode("utf-8")
        storage = EncryptedTokenStorage(encryption_key=key, allow_ephemeral_dev_key=False)
        adapter = GmailIntegrationAdapter(token_storage=storage)

        # Connect valid internal credentials
        valid_creds = {
            "access_token": "legitimate_access_token",
            "refresh_token": "legitimate_refresh_token",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        }
        await adapter.connect(credentials=valid_creds)
        self.assertTrue(adapter.is_connected)

        # Attempt to overwrite with arbitrary credentials without internal flag
        attempt = await adapter.connect(credentials={"access_token": "malicious_overwrite_token"})
        self.assertFalse(attempt)
        self.assertIn("Direct credential submission is not permitted", adapter.last_error)

        # Verify stored credentials remain untouched
        stored = await storage.get_credential("gmail")
        self.assertEqual(stored["access_token"], "legitimate_access_token")
        self.assertEqual(stored["refresh_token"], "legitimate_refresh_token")


class TestGmailDownloadAttachment(unittest.IsolatedAsyncioTestCase):
    """
    Comprehensive test suite for real Gmail download_attachment implementation:
    1. Valid attachment download
    2. Missing message ID
    3. Missing attachment ID
    4. Gmail 404
    5. Gmail 403
    6. Malformed response
    7. Attachment size limit
    8. Token refresh
    9. Approval gate
    10. Privacy/logging safety
    """

    async def asyncSetUp(self):
        self.fernet_key = Fernet.generate_key().decode("utf-8")
        self.token_storage = EncryptedTokenStorage(
            encryption_key=self.fernet_key,
            allow_ephemeral_dev_key=False,
        )
        self.client = TestClient(app)

    # 1. Valid attachment download
    async def test_01_valid_attachment_download(self):
        test_payload = b"Sample PDF attachment data for testing WorkFlowOS!"
        b64_data = base64.urlsafe_b64encode(test_payload).decode("ascii").rstrip("=")
        expected_sha = hashlib.sha256(test_payload).hexdigest()

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "/messages/msg_valid_01/attachments/att_valid_01" in url_str:
                self.assertIn("Bearer valid_test_token", request.headers.get("Authorization", ""))
                return httpx.Response(
                    200,
                    json={
                        "size": len(test_payload),
                        "attachmentId": "att_valid_01",
                        "data": b64_data,
                    },
                )
            return httpx.Response(404, json={})

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        oauth_mgr = GoogleOAuthManager(
            client_id="mock_client_id",
            client_secret="mock_client_secret",
            redirect_uri="http://localhost:8000/api/integrations/gmail/callback",
            http_client=mock_client,
        )
        adapter = GmailIntegrationAdapter(
            oauth_manager=oauth_mgr,
            token_storage=self.token_storage,
            http_client=mock_client,
        )
        await adapter.connect(credentials={
            "access_token": "valid_test_token",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        })

        # Test default metadata return (raw data omitted for privacy & memory safety)
        res = await adapter.execute_action(
            "download_attachment",
            {"message_id": "msg_valid_01", "attachment_id": "att_valid_01", "filename": "sample.pdf"},
        )
        self.assertTrue(res.success)
        self.assertEqual(res.data["service"], "gmail")
        self.assertEqual(res.data["action"], "download_attachment")
        self.assertEqual(res.data["message_id"], "msg_valid_01")
        self.assertEqual(res.data["attachment_id"], "att_valid_01")
        self.assertEqual(res.data["filename"], "sample.pdf")
        self.assertEqual(res.data["size_bytes"], len(test_payload))
        self.assertEqual(res.data["sha256"], expected_sha)
        self.assertEqual(res.data["status"], "downloaded")
        self.assertNotIn("data_base64", res.data)

        # Test with explicit include_raw_data=True
        res_raw = await adapter.execute_action(
            "download_attachment",
            {
                "message_id": "msg_valid_01",
                "attachment_id": "att_valid_01",
                "filename": "sample.pdf",
                "include_raw_data": True,
            },
        )
        self.assertTrue(res_raw.success)
        self.assertIn("data_base64", res_raw.data)
        self.assertEqual(base64.b64decode(res_raw.data["data_base64"]), test_payload)

        await adapter.disconnect()
        await mock_client.aclose()

    # 2. Missing message ID
    async def test_02_missing_message_id(self):
        adapter = GmailIntegrationAdapter(token_storage=self.token_storage)
        await adapter.connect(credentials={
            "access_token": "test_tok",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        })

        # Omitted message_id
        res1 = await adapter.execute_action("download_attachment", {"attachment_id": "att_01"})
        self.assertFalse(res1.success)
        self.assertEqual(res1.error_code, "VALIDATION_ERROR")
        self.assertIn("message_id", res1.message)

        # Empty string message_id
        res2 = await adapter.execute_action("download_attachment", {"message_id": "", "attachment_id": "att_01"})
        self.assertFalse(res2.success)
        self.assertEqual(res2.error_code, "VALIDATION_ERROR")

        # Whitespace message_id
        res3 = await adapter.execute_action("download_attachment", {"message_id": "   ", "attachment_id": "att_01"})
        self.assertFalse(res3.success)
        self.assertEqual(res3.error_code, "VALIDATION_ERROR")

        await adapter.disconnect()

    # 3. Missing attachment ID
    async def test_03_missing_attachment_id(self):
        adapter = GmailIntegrationAdapter(token_storage=self.token_storage)
        await adapter.connect(credentials={
            "access_token": "test_tok",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        })

        # Omitted attachment_id
        res1 = await adapter.execute_action("download_attachment", {"message_id": "msg_01"})
        self.assertFalse(res1.success)
        self.assertEqual(res1.error_code, "VALIDATION_ERROR")
        self.assertIn("attachment_id", res1.message)

        # Empty string attachment_id
        res2 = await adapter.execute_action("download_attachment", {"message_id": "msg_01", "attachment_id": ""})
        self.assertFalse(res2.success)
        self.assertEqual(res2.error_code, "VALIDATION_ERROR")

        # Whitespace attachment_id
        res3 = await adapter.execute_action("download_attachment", {"message_id": "msg_01", "attachment_id": "   "})
        self.assertFalse(res3.success)
        self.assertEqual(res3.error_code, "VALIDATION_ERROR")

        await adapter.disconnect()

    # 4. Gmail 404
    async def test_04_gmail_404_not_found(self):
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": {"code": 404, "message": "Attachment not found"}})

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        adapter = GmailIntegrationAdapter(token_storage=self.token_storage, http_client=mock_client)
        await adapter.connect(credentials={
            "access_token": "test_tok",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        })

        res = await adapter.execute_action(
            "download_attachment",
            {"message_id": "msg_missing", "attachment_id": "att_missing"},
        )
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "CONNECTION_ERROR")
        self.assertTrue("404" in res.message or "not found" in res.message.lower())

        await adapter.disconnect()
        await mock_client.aclose()

    # 5. Gmail 403
    async def test_05_gmail_403_forbidden(self):
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, text="Forbidden: Insufficient permissions for user attachment")

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        adapter = GmailIntegrationAdapter(token_storage=self.token_storage, http_client=mock_client)
        await adapter.connect(credentials={
            "access_token": "test_tok",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        })

        res = await adapter.execute_action(
            "download_attachment",
            {"message_id": "msg_01", "attachment_id": "att_01"},
        )
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "CONNECTION_ERROR")
        self.assertTrue("403" in res.message or "permission denied" in res.message.lower())

        await adapter.disconnect()
        await mock_client.aclose()

    # 6. Malformed response
    async def test_06_malformed_response(self):
        # A: Non-JSON response
        async def mock_non_json(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html><body>Bad Gateway</body></html>")

        client_a = httpx.AsyncClient(transport=httpx.MockTransport(mock_non_json))
        adapter_a = GmailIntegrationAdapter(token_storage=self.token_storage, http_client=client_a)
        await adapter_a.connect(credentials={"access_token": "tok", "expires_at": time.time() + 3600, "_internal_oauth_source": True})
        res_a = await adapter_a.execute_action("download_attachment", {"message_id": "m1", "attachment_id": "a1"})
        self.assertFalse(res_a.success)
        self.assertEqual(res_a.error_code, "CONNECTION_ERROR")
        self.assertIn("Malformed Gmail API response", res_a.message)
        await adapter_a.disconnect()
        await client_a.aclose()

        # B: Missing attachment data field
        async def mock_missing_data(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"size": 1024, "attachmentId": "a1"})

        client_b = httpx.AsyncClient(transport=httpx.MockTransport(mock_missing_data))
        adapter_b = GmailIntegrationAdapter(token_storage=self.token_storage, http_client=client_b)
        await adapter_b.connect(credentials={"access_token": "tok", "expires_at": time.time() + 3600, "_internal_oauth_source": True})
        res_b = await adapter_b.execute_action("download_attachment", {"message_id": "m1", "attachment_id": "a1"})
        self.assertFalse(res_b.success)
        self.assertEqual(res_b.error_code, "CONNECTION_ERROR")
        self.assertIn("missing attachment data", res_b.message)
        await adapter_b.disconnect()
        await client_b.aclose()

        # C: Invalid base64 characters
        async def mock_invalid_b64(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"size": 10, "data": "%%%NotValidBase64!!!"})

        client_c = httpx.AsyncClient(transport=httpx.MockTransport(mock_invalid_b64))
        adapter_c = GmailIntegrationAdapter(token_storage=self.token_storage, http_client=client_c)
        await adapter_c.connect(credentials={"access_token": "tok", "expires_at": time.time() + 3600, "_internal_oauth_source": True})
        res_c = await adapter_c.execute_action("download_attachment", {"message_id": "m1", "attachment_id": "a1"})
        self.assertFalse(res_c.success)
        self.assertEqual(res_c.error_code, "CONNECTION_ERROR")
        self.assertIn("invalid base64url data", res_c.message)
        await adapter_c.disconnect()
        await client_c.aclose()

    # 7. Attachment size limit
    async def test_07_attachment_size_limit(self):
        # A: Declared size in Gmail API response exceeds limit
        async def mock_large_declared(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"size": 20 * 1024 * 1024, "data": "dGVzdA=="})

        client_a = httpx.AsyncClient(transport=httpx.MockTransport(mock_large_declared))
        adapter_a = GmailIntegrationAdapter(
            token_storage=self.token_storage,
            http_client=client_a,
            max_attachment_size_bytes=10 * 1024 * 1024,
        )
        await adapter_a.connect(credentials={"access_token": "tok", "expires_at": time.time() + 3600, "_internal_oauth_source": True})
        res_a = await adapter_a.execute_action("download_attachment", {"message_id": "m1", "attachment_id": "a1"})
        self.assertFalse(res_a.success)
        self.assertEqual(res_a.error_code, "VALIDATION_ERROR")
        self.assertIn("exceeds configured limit", res_a.message)
        await adapter_a.disconnect()
        await client_a.aclose()

        # B: Decoded data exceeds custom small limit
        payload = b"A" * 200
        b64 = base64.urlsafe_b64encode(payload).decode("ascii")
        async def mock_large_bytes(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"size": 50, "data": b64})

        client_b = httpx.AsyncClient(transport=httpx.MockTransport(mock_large_bytes))
        adapter_b = GmailIntegrationAdapter(
            token_storage=self.token_storage,
            http_client=client_b,
            max_attachment_size_bytes=100,
        )
        await adapter_b.connect(credentials={"access_token": "tok", "expires_at": time.time() + 3600, "_internal_oauth_source": True})
        res_b = await adapter_b.execute_action("download_attachment", {"message_id": "m1", "attachment_id": "a1"})
        self.assertFalse(res_b.success)
        self.assertEqual(res_b.error_code, "VALIDATION_ERROR")
        self.assertIn("exceeds configured limit of 100 bytes", res_b.message)

        # C: Parameter-level max_size_bytes constraint
        res_c = await adapter_b.execute_action("download_attachment", {"message_id": "m1", "attachment_id": "a1", "max_size_bytes": 10})
        self.assertFalse(res_c.success)
        self.assertEqual(res_c.error_code, "VALIDATION_ERROR")

        await adapter_b.disconnect()
        await client_b.aclose()

    # 8. Token refresh
    async def test_08_token_refresh_on_expired_token(self):
        refreshed_called = False

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal refreshed_called
            url_str = str(request.url)
            if "oauth2.googleapis.com/token" in url_str:
                refreshed_called = True
                return httpx.Response(
                    200,
                    json={
                        "access_token": "newly_refreshed_token_xyz",
                        "expires_in": 3600,
                        "token_type": "Bearer",
                    },
                )
            elif "/attachments/att_refresh" in url_str:
                self.assertIn("Bearer newly_refreshed_token_xyz", request.headers.get("Authorization", ""))
                return httpx.Response(
                    200,
                    json={
                        "size": 4,
                        "attachmentId": "att_refresh",
                        "data": base64.urlsafe_b64encode(b"DATA").decode("ascii"),
                    },
                )
            return httpx.Response(404, json={})

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        oauth_mgr = GoogleOAuthManager(
            client_id="mock_client_id",
            client_secret="mock_client_secret",
            redirect_uri="http://localhost:8000/api/integrations/gmail/callback",
            http_client=mock_client,
        )
        adapter = GmailIntegrationAdapter(
            oauth_manager=oauth_mgr,
            token_storage=self.token_storage,
            http_client=mock_client,
        )
        # Store expired access token with valid refresh token
        await adapter.connect(credentials={
            "access_token": "expired_old_token",
            "refresh_token": "valid_refresh_token_123",
            "expires_at": time.time() - 300,
            "_internal_oauth_source": True,
        })

        res = await adapter.execute_action(
            "download_attachment",
            {"message_id": "msg_01", "attachment_id": "att_refresh"},
        )
        self.assertTrue(res.success)
        self.assertTrue(refreshed_called)
        self.assertEqual(res.data["size_bytes"], 4)

        # Confirm token storage was updated
        updated_creds = await self.token_storage.get_credential("gmail")
        self.assertEqual(updated_creds["access_token"], "newly_refreshed_token_xyz")

        # Subtest: expired token with invalid/failing refresh token
        async def mock_fail_refresh(request: httpx.Request) -> httpx.Response:
            if "oauth2.googleapis.com/token" in str(request.url):
                return httpx.Response(400, json={"error": "invalid_grant", "error_description": "Token revoked"})
            return httpx.Response(404, json={})

        client_fail = httpx.AsyncClient(transport=httpx.MockTransport(mock_fail_refresh))
        oauth_fail = GoogleOAuthManager(
            client_id="cid", client_secret="csec", redirect_uri="http://cb", http_client=client_fail
        )
        adapter_fail = GmailIntegrationAdapter(oauth_manager=oauth_fail, token_storage=self.token_storage, http_client=client_fail)
        await adapter_fail.connect(credentials={
            "access_token": "expired_old_token_2",
            "refresh_token": "invalid_refresh_tok",
            "expires_at": time.time() - 300,
            "_internal_oauth_source": True,
        })
        res_fail = await adapter_fail.execute_action("download_attachment", {"message_id": "m1", "attachment_id": "a1"})
        self.assertFalse(res_fail.success)
        self.assertEqual(res_fail.error_code, "CONNECTION_ERROR")
        self.assertIn("Failed to refresh expired Gmail token", res_fail.message)

        await adapter.disconnect()
        await adapter_fail.disconnect()
        await mock_client.aclose()
        await client_fail.aclose()

    # 9. Approval gate
    async def test_09_approval_gate_enforcement(self):
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            if "/attachments/wf_att_01" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "size": 6,
                        "attachmentId": "wf_att_01",
                        "data": base64.urlsafe_b64encode(b"WFDATA").decode("ascii"),
                    },
                )
            return httpx.Response(404, json={})

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        adapter = GmailIntegrationAdapter(token_storage=self.token_storage, http_client=mock_client)
        await adapter.connect(credentials={"access_token": "wf_tok", "expires_at": time.time() + 3600, "_internal_oauth_source": True})
        integration_registry.unregister("gmail")
        integration_registry.register(adapter)

        try:
            # A: Standalone REST direct execution must be blocked with 403 Forbidden
            rest_res = self.client.post(
                "/api/integrations/gmail/actions/download_attachment/execute",
                json={
                    "parameters": {"message_id": "m1", "attachment_id": "a1"},
                },
            )
            self.assertEqual(rest_res.status_code, 403)
            self.assertIn("Direct standalone execution", rest_res.json()["detail"])

            # B: Unapproved workflow execution must remain PENDING
            wf = WorkflowDefinition(
                id="wf_download_att_approval",
                name="Download Attachment Workflow",
                steps=[
                    WorkflowStep(
                        id="step_download",
                        name="Download Attachment",
                        type="download_attachment",
                        application="gmail",
                        parameters={"message_id": "m1", "attachment_id": "wf_att_01"},
                    )
                ],
                requires_approval=True,
            )

            # Unapproved execution
            unapproved_exec = await automation_service.run_workflow(
                workflow_definition=wf,
                approved=False,
                executor_type="integration",
            )
            self.assertEqual(unapproved_exec.status, AutomationStatus.PENDING)
            self.assertEqual(len(unapproved_exec.completed_actions), 0)

            # Approved execution
            approved_exec = await automation_service.run_workflow(
                workflow_definition=wf,
                approved=True,
                executor_type="integration",
            )
            self.assertEqual(approved_exec.status, AutomationStatus.COMPLETED)
            self.assertEqual(len(approved_exec.completed_actions), 1)
            self.assertIn("download_attachment", approved_exec.completed_actions)
        finally:
            await adapter.disconnect()
            await mock_client.aclose()

    # 10. Privacy/logging safety
    async def test_10_privacy_and_logging_safety(self):
        secret_bytes = b"TOP_SECRET_PROPRIETARY_CONTRACT_CONTENT_ABCXYZ"
        secret_b64 = base64.urlsafe_b64encode(secret_bytes).decode("ascii")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"size": len(secret_bytes), "attachmentId": "att_secret", "data": secret_b64},
            )

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        adapter = GmailIntegrationAdapter(token_storage=self.token_storage, http_client=mock_client)
        await adapter.connect(credentials={
            "access_token": "sensitive_bearer_token_999",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        })

        with self.assertLogs("integrations.gmail", level="INFO") as log_capture:
            res = await adapter.execute_action(
                "download_attachment",
                {"message_id": "msg_sec", "attachment_id": "att_secret", "filename": "confidential.pdf"},
            )

        self.assertTrue(res.success)
        logs_text = " ".join(log_capture.output)

        # Assert secret attachment content is NEVER in logs
        self.assertNotIn("TOP_SECRET_PROPRIETARY_CONTRACT_CONTENT_ABCXYZ", logs_text)
        self.assertNotIn(secret_b64, logs_text)

        # Assert OAuth token is NEVER in logs
        self.assertNotIn("sensitive_bearer_token_999", logs_text)

        # Assert result dictionary doesn't store raw data unless explicitly asked
        self.assertNotIn("data_base64", res.data)
        self.assertNotIn("data", res.data)

        # Assert only metadata is logged
        self.assertIn("Successfully downloaded attachment 'att_secret'", logs_text)

        await adapter.disconnect()
        await mock_client.aclose()


class TestPersistentEncryptedGmailCredentials(unittest.IsolatedAsyncioTestCase):
    """
    Validates persistent encrypted Gmail credential storage in MongoDB Atlas collection:
    integration_credentials.

    Verifies:
    1. Credentials are encrypted with Fernet before MongoDB persistence.
    2. Plaintext access_token is never stored in MongoDB.
    3. Plaintext refresh_token is never stored in MongoDB.
    4. Credential can be loaded and decrypted after adapter recreation.
    5. Gmail remains connected after simulated backend restart.
    6. Access-token refresh updates the encrypted MongoDB record.
    7. Disconnect deletes the stored credential from MongoDB.
    8. Invalid or missing Fernet key fails closed without exposing secrets.
    9. Corrupted ciphertext fails safely.
    10. Unique index on integration_id prevents duplicate credential documents.
    """

    async def asyncSetUp(self):
        import backend.database as db_mod
        self.db = db_mod.get_database()
        if self.db is not None:
            await self.db["integration_credentials"].delete_many({})
        self.fernet_key = Fernet.generate_key().decode("utf-8")
        self.storage = EncryptedTokenStorage(
            encryption_key=self.fernet_key,
            allow_ephemeral_dev_key=False,
        )

    async def asyncTearDown(self):
        if self.db is not None:
            await self.db["integration_credentials"].delete_many({})

    async def test_01_credentials_are_encrypted_before_mongodb_persistence(self):
        creds = {
            "access_token": "ya29.secret_test_access_token_123",
            "refresh_token": "1//04secret_test_refresh_token_456",
            "expires_at": time.time() + 3600,
        }
        await self.storage.store_credential("gmail", creds)

        doc = await self.db["integration_credentials"].find_one({"integration_id": "gmail"})
        self.assertIsNotNone(doc)
        self.assertIn("encrypted_payload", doc)
        self.assertTrue(doc["encrypted_payload"].startswith("gAAAAA"))
        self.assertIn("created_at", doc)
        self.assertIn("updated_at", doc)

    async def test_02_plaintext_tokens_never_stored_in_mongodb(self):
        creds = {
            "access_token": "ya29.confidential_access_token_777",
            "refresh_token": "1//04confidential_refresh_token_888",
            "expires_at": time.time() + 3600,
        }
        await self.storage.store_credential("gmail", creds)

        doc = await self.db["integration_credentials"].find_one({"integration_id": "gmail"})
        self.assertIsNotNone(doc)
        doc_str = str(doc)
        self.assertNotIn("ya29.confidential_access_token_777", doc_str)
        self.assertNotIn("1//04confidential_refresh_token_888", doc_str)
        self.assertNotIn("access_token", doc)
        self.assertNotIn("refresh_token", doc)
        self.assertNotIn(self.fernet_key, doc_str)

    async def test_03_credential_loaded_and_decrypted_after_adapter_recreation(self):
        creds = {
            "access_token": "ya29.persisted_token_across_instances",
            "refresh_token": "1//04refresh_across_instances",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        }
        adapter1 = GmailIntegrationAdapter(token_storage=self.storage)
        success = await adapter1.connect(credentials=creds)
        self.assertTrue(success)
        self.assertEqual(adapter1.status, IntegrationStatus.CONNECTED)

        # Recreate adapter with fresh storage sharing the same key and DB
        fresh_storage = EncryptedTokenStorage(
            encryption_key=self.fernet_key,
            allow_ephemeral_dev_key=False,
        )
        self.assertEqual(len(fresh_storage._store), 0)

        adapter2 = GmailIntegrationAdapter(token_storage=fresh_storage)
        loaded_creds = await fresh_storage.get_credential("gmail")
        self.assertIsNotNone(loaded_creds)
        self.assertEqual(loaded_creds["access_token"], "ya29.persisted_token_across_instances")
        self.assertEqual(loaded_creds["refresh_token"], "1//04refresh_across_instances")

        connected = await adapter2.connect()
        self.assertTrue(connected)
        self.assertEqual(adapter2.status, IntegrationStatus.CONNECTED)

    async def test_04_gmail_remains_connected_after_simulated_backend_restart(self):
        from backend.main import restore_persistent_integrations
        from integrations.registry import integration_registry

        creds = {
            "access_token": "ya29.startup_restoration_token",
            "refresh_token": "1//04startup_restoration_refresh",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        }
        real_adapter = integration_registry.get("gmail")
        self.assertIsNotNone(real_adapter)

        real_adapter._token_storage = self.storage
        await real_adapter.connect(credentials=creds)
        self.assertEqual(real_adapter.status, IntegrationStatus.CONNECTED)

        # Simulate restart
        restart_storage = EncryptedTokenStorage(
            encryption_key=self.fernet_key,
            allow_ephemeral_dev_key=False,
        )
        real_adapter._token_storage = restart_storage
        real_adapter._status = IntegrationStatus.DISCONNECTED

        with patch.dict(os.environ, {"WORKFLOWOS_CREDENTIAL_KEY": self.fernet_key}):
            await restore_persistent_integrations()

        self.assertEqual(real_adapter.status, IntegrationStatus.CONNECTED)
        self.assertIsNone(real_adapter.last_error)
        valid_token = await real_adapter.get_valid_access_token()
        self.assertEqual(valid_token, "ya29.startup_restoration_token")

    async def test_05_access_token_refresh_updates_encrypted_mongodb_record(self):
        expired_creds = {
            "access_token": "ya29.old_expired_token",
            "refresh_token": "1//04valid_refresh_token",
            "expires_at": time.time() - 100,
            "_internal_oauth_source": True,
        }
        await self.storage.store_credential("gmail", expired_creds)
        old_doc = await self.db["integration_credentials"].find_one({"integration_id": "gmail"})
        old_ciphertext = old_doc["encrypted_payload"]

        async def mock_refresh(refresh_token):
            return {
                "access_token": "ya29.new_refreshed_access_token",
                "expires_at": time.time() + 3600,
            }

        oauth_mgr = GoogleOAuthManager(
            client_id="test_client", client_secret="test_secret", redirect_uri="http://test"
        )
        oauth_mgr.refresh_access_token = mock_refresh

        adapter = GmailIntegrationAdapter(
            oauth_manager=oauth_mgr,
            token_storage=self.storage,
        )
        await adapter.connect()

        new_token = await adapter.get_valid_access_token()
        self.assertEqual(new_token, "ya29.new_refreshed_access_token")

        updated_doc = await self.db["integration_credentials"].find_one({"integration_id": "gmail"})
        self.assertIsNotNone(updated_doc)
        self.assertNotEqual(updated_doc["encrypted_payload"], old_ciphertext)

        decrypted = await self.storage.get_credential("gmail")
        self.assertEqual(decrypted["access_token"], "ya29.new_refreshed_access_token")
        self.assertEqual(decrypted["refresh_token"], "1//04valid_refresh_token")

    async def test_06_disconnect_deletes_stored_credential_from_mongodb(self):
        creds = {
            "access_token": "ya29.token_to_disconnect",
            "refresh_token": "1//04refresh_to_disconnect",
            "expires_at": time.time() + 3600,
            "_internal_oauth_source": True,
        }
        adapter = GmailIntegrationAdapter(token_storage=self.storage)
        await adapter.connect(credentials=creds)

        doc = await self.db["integration_credentials"].find_one({"integration_id": "gmail"})
        self.assertIsNotNone(doc)

        with patch.object(adapter._oauth_manager, "revoke_token", return_value=True):
            await adapter.disconnect()

        self.assertEqual(adapter.status, IntegrationStatus.DISCONNECTED)
        doc_after = await self.db["integration_credentials"].find_one({"integration_id": "gmail"})
        self.assertIsNone(doc_after)
        self.assertFalse(await self.storage.has_credential("gmail"))

    async def test_07_invalid_or_missing_fernet_key_fails_closed(self):
        with patch.dict(os.environ, {"WORKFLOWOS_CREDENTIAL_KEY": ""}):
            with self.assertRaises(CredentialStorageConfigurationError):
                EncryptedTokenStorage(encryption_key=None, allow_ephemeral_dev_key=False)

        with self.assertRaises(CredentialStorageConfigurationError):
            EncryptedTokenStorage(encryption_key="invalid-fernet-key-bytes", allow_ephemeral_dev_key=False)

    async def test_08_corrupted_ciphertext_fails_safely_and_sets_error_status(self):
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        await self.db["integration_credentials"].update_one(
            {"integration_id": "gmail"},
            {
                "$set": {
                    "encrypted_payload": "gAAAAABcorruptedCiphertextPayloadThatCannotBeDecrypted===",
                    "updated_at": now_iso,
                    "created_at": now_iso,
                }
            },
            upsert=True,
        )

        fresh_storage = EncryptedTokenStorage(
            encryption_key=self.fernet_key,
            allow_ephemeral_dev_key=False,
        )
        self.assertTrue(await fresh_storage.has_credential("gmail"))
        self.assertIsNone(await fresh_storage.get_credential("gmail"))

        adapter = GmailIntegrationAdapter(token_storage=fresh_storage)
        connected = await adapter.connect()
        self.assertFalse(connected)
        self.assertEqual(adapter.status, IntegrationStatus.ERROR)
        self.assertIn("could not be decrypted", adapter.last_error)

    async def test_09_unique_index_enforcement_on_integration_id(self):
        await self.db["integration_credentials"].create_index([("integration_id", 1)], unique=True)
        await self.db["integration_credentials"].insert_one({
            "integration_id": "gmail",
            "encrypted_payload": "payload1",
        })
        from pymongo.errors import DuplicateKeyError
        with self.assertRaises(DuplicateKeyError):
            await self.db["integration_credentials"].insert_one({
                "integration_id": "gmail",
                "encrypted_payload": "payload2",
            })


if __name__ == "__main__":
    unittest.main()
