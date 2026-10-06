"""
WorkFlowOS Phase 14: Productization Tests

Validates:
1. System status API aggregation (/api/system/status)
2. Desktop agent status detection and graceful fallback
3. Onboarding endpoint (/api/system/onboarding)
4. Safe system settings (/api/system/settings) with zero credential leaks
5. Preservation of Phase 12 privacy and Phase 13 application ecosystem security:
   - Unknown application remains rejected (fail-closed)
   - Unknown action remains rejected (fail-closed)
   - Mutating action requires approval
   - PII redaction active
"""

import os
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from integrations.registry import application_registry


class TestPhase14Productization(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_system_status_endpoint(self):
        """GET /api/system/status returns aggregated telemetry without secret leakage."""
        res = self.client.get("/api/system/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Structural assertions
        self.assertIn("backend", data)
        self.assertEqual(data["backend"], "healthy")
        self.assertIn("agent", data)
        self.assertIn(data["agent"], ["connected", "disconnected", "degraded"])

        self.assertIn("applications", data)
        self.assertIsInstance(data["applications"]["connected"], int)
        self.assertIsInstance(data["applications"]["available"], int)
        self.assertGreaterEqual(data["applications"]["available"], 1)

        self.assertIn("workflows", data)
        self.assertIsInstance(data["workflows"]["discovered"], int)
        self.assertIsInstance(data["workflows"]["declarative"], int)

        self.assertIn("executions", data)
        self.assertIsInstance(data["executions"]["total"], int)
        self.assertIsInstance(data["executions"]["successful"], int)

        self.assertIn("privacy", data)
        self.assertIn("collection_enabled", data["privacy"])
        self.assertIn("retention_days", data["privacy"])
        self.assertTrue(data["privacy"]["redaction_active"])
        self.assertTrue(data["privacy"]["human_approval_required"])

        # Security assertion: No secrets or raw connection strings leaked
        raw_text = res.text.lower()
        self.assertNotIn("mongodb+srv://", raw_text)
        self.assertNotIn("password", raw_text)
        self.assertNotIn("access_token", raw_text)
        self.assertNotIn("refresh_token", raw_text)
        self.assertNotIn("client_secret", raw_text)

    def test_system_onboarding_endpoint(self):
        """GET /api/system/onboarding surfaces onboarding checklist."""
        res = self.client.get("/api/system/onboarding")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertTrue(data["completed"])
        self.assertIn("Welcome to WorkFlowOS", data["title"])
        self.assertIsInstance(data["steps"], list)
        step_ids = [s["id"] for s in data["steps"]]
        self.assertIn("agent", step_ids)
        self.assertIn("backend", step_ids)
        self.assertIn("applications", step_ids)
        self.assertIn("privacy", step_ids)

    def test_system_settings_safe_configuration(self):
        """GET /api/system/settings returns public config with masked credentials."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-super-secret-key-12345"}):
            res = self.client.get("/api/system/settings")
            self.assertEqual(res.status_code, 200)
            data = res.json()

            self.assertIn("backend_url", data)
            self.assertIn("frontend_url", data)
            self.assertIn("activity_collection", data)
            self.assertIn("credentials_configured", data)

            # Secret must be masked as 'Configured', never the actual secret key
            self.assertEqual(data["credentials_configured"].get("GEMINI_API_KEY"), "Configured")
            self.assertNotIn("test-super-secret-key-12345", res.text)

    def test_unknown_application_fails_closed(self):
        """Phase 13 security requirement: Unknown applications must fail closed."""
        res = self.client.get("/api/applications/non_existent_app")
        self.assertEqual(res.status_code, 404)

        res_caps = self.client.get("/api/applications/non_existent_app/capabilities")
        self.assertEqual(res_caps.status_code, 404)

        # Registry safety: unknown application adapter is None
        self.assertIsNone(application_registry.get_application("non_existent_app"))
        self.assertFalse(application_registry.is_action_read_only("non_existent_app", "any_action"))
        self.assertFalse(application_registry.is_action_mutating("non_existent_app", "any_action"))
        # Must require approval to prevent bypass
        self.assertTrue(application_registry.requires_approval("non_existent_app", "any_action"))

    def test_unknown_action_fails_closed(self):
        """Phase 13 security requirement: Unknown action on valid app must fail closed."""
        self.assertFalse(application_registry.is_action_read_only("demo_crm", "dangerous_unregistered_action"))
        self.assertFalse(application_registry.is_action_mutating("demo_crm", "dangerous_unregistered_action"))
        self.assertTrue(application_registry.requires_approval("demo_crm", "dangerous_unregistered_action"))

    def test_mutating_action_requires_approval(self):
        """Phase 13 security requirement: Known mutating action requires human approval."""
        self.assertTrue(application_registry.is_action_mutating("demo_crm", "update_customer"))
        self.assertFalse(application_registry.is_action_read_only("demo_crm", "update_customer"))
        self.assertTrue(application_registry.requires_approval("demo_crm", "update_customer"))

    def test_read_only_action_safety(self):
        """Phase 13 security requirement: Known read-only action does not require approval."""
        self.assertTrue(application_registry.is_action_read_only("demo_crm", "search_customer"))
        self.assertFalse(application_registry.is_action_mutating("demo_crm", "search_customer"))
        self.assertFalse(application_registry.requires_approval("demo_crm", "search_customer"))

    def test_privacy_controls_enforced(self):
        """Phase 12 privacy checks: Toggle status and audit payload work."""
        status_res = self.client.get("/api/privacy/status")
        self.assertEqual(status_res.status_code, 200)
        self.assertIn("collection_enabled", status_res.json())

        # Audit sensitive payload
        audit_res = self.client.post(
            "/api/privacy/audit",
            json={"payload": {"password": "secret", "user": "alice"}}
        )
        self.assertEqual(audit_res.status_code, 200)
        self.assertTrue(audit_res.json()["contains_sensitive_data"])


if __name__ == "__main__":
    unittest.main()
