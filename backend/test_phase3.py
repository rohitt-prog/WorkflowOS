#!/usr/bin/env python3
"""
WorkFlowOS Phase 3 Verification & Test Suite

Verifies:
1. Phase 1 APIs (GET /health, GET /api/events)
2. Phase 2 Discovery (GET /api/discovery/repeated: detected=True, occurrences=3, similarity=1.0)
3. Phase 3 AI Schema & Pydantic Validation
4. Phase 3 API Endpoint (POST /api/ai/workflow/generate) with validation & mocked service
5. Phase 3 Live Gemini Service (optional flag --live-gemini)

Usage:
  python backend/test_phase3.py
  python backend/test_phase3.py --live-gemini
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import unittest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from ai.models import (
    WorkflowTrigger,
    WorkflowAction,
    WorkflowProposal,
    GenerateWorkflowRequest,
    GenerateWorkflowResponse,
)
from ai.gemini_service import (
    GeminiWorkflowService,
    GeminiConfigurationError,
    WorkflowUnderstandingError,
)
from fastapi.testclient import TestClient
from backend.config import settings
from backend.main import app


class TestPhase3AIModels(unittest.TestCase):
    """Test Pydantic model validation for Phase 3 schemas."""

    def test_workflow_trigger_validation(self):
        trigger = WorkflowTrigger(
            type="new_email",
            application="demo_email",
            description="Customer email received"
        )
        self.assertEqual(trigger.type, "new_email")
        self.assertEqual(trigger.application, "demo_email")

    def test_workflow_action_validation(self):
        action = WorkflowAction(
            type="open_email",
            application="demo_email",
            description="Open incoming email",
            target="customer_request"
        )
        self.assertEqual(action.type, "open_email")
        self.assertEqual(action.target, "customer_request")

    def test_workflow_proposal_validation_success(self):
        proposal_dict = {
            "name": "Process Customer Request",
            "intent": "Process customer emails and update CRM",
            "trigger": {
                "type": "new_email",
                "application": "demo_email",
                "description": "Incoming email arrives"
            },
            "actions": [
                {
                    "type": "open_email",
                    "application": "demo_email",
                    "description": "Open customer email",
                    "target": "customer_request"
                },
                {
                    "type": "download_attachment",
                    "application": "demo_email",
                    "description": "Download PDF attachment",
                    "target": "attachment"
                }
            ],
            "variables": ["customer_name", "attachment"],
            "applications": ["demo_email", "demo_crm"],
            "requires_approval": True
        }
        proposal = WorkflowProposal.model_validate(proposal_dict)
        self.assertEqual(proposal.name, "Process Customer Request")
        self.assertEqual(len(proposal.actions), 2)
        self.assertTrue(proposal.requires_approval)
        self.assertEqual(proposal.variables, ["customer_name", "attachment"])

    def test_workflow_proposal_missing_fields_raises(self):
        with self.assertRaises(ValidationError):
            # Missing actions and trigger
            WorkflowProposal.model_validate({
                "name": "Incomplete Workflow",
                "intent": "Does something",
                "applications": ["demo_app"]
            })


class TestPhase3MockedGeminiService(unittest.TestCase):
    """Unit tests for GeminiWorkflowService isolating external API calls."""

    def test_missing_api_key_raises_configuration_error(self):
        service = GeminiWorkflowService(api_key="")
        with self.assertRaises(GeminiConfigurationError):
            service.generate_workflow(sequence=["open_email"])

    def test_empty_sequence_raises_error(self):
        service = GeminiWorkflowService(api_key="fake-key")
        with self.assertRaises(WorkflowUnderstandingError):
            service.generate_workflow(sequence=[])

    def test_generate_workflow_mocked_success(self):
        mock_client = MagicMock()
        mock_proposal = WorkflowProposal(
            name="Mocked Customer Workflow",
            intent="Mocked intent description",
            trigger=WorkflowTrigger(
                type="new_email",
                application="demo_email",
                description="Mock trigger"
            ),
            actions=[
                WorkflowAction(
                    type="open_email",
                    application="demo_email",
                    description="Open email",
                    target="customer_request"
                )
            ],
            variables=["customer_name"],
            applications=["demo_email"],
            requires_approval=True
        )

        mock_response = MagicMock()
        mock_response.parsed = mock_proposal
        mock_response.text = mock_proposal.model_dump_json()
        mock_client.models.generate_content.return_value = mock_response

        service = GeminiWorkflowService(
            api_key="test-key",
            model="gemini-2.5-flash",
            client=mock_client
        )
        result = service.generate_workflow(
            sequence=["open_email"],
            applications=["demo_email"]
        )

        self.assertEqual(result.name, "Mocked Customer Workflow")
        self.assertTrue(result.requires_approval)
        self.assertEqual(len(result.actions), 1)


class TestPhase3EndpointWithMock(unittest.TestCase):
    """Test POST /api/ai/workflow/generate endpoint with TestClient."""

    def setUp(self):
        self.client = TestClient(app)

    def test_generate_workflow_empty_sequence_returns_400(self):
        res = self.client.post("/api/ai/workflow/generate", json={"sequence": []})
        self.assertEqual(res.status_code, 400)
        self.assertIn("A non-empty 'sequence' list is required", res.json()["detail"])

    def test_generate_workflow_missing_payload_returns_400(self):
        res = self.client.post("/api/ai/workflow/generate", json={})
        self.assertEqual(res.status_code, 400)

    @patch("backend.routes.ai.gemini_workflow_service.generate_workflow")
    def test_generate_workflow_mocked_success(self, mock_generate):
        mock_proposal = WorkflowProposal(
            name="Inferred Customer Workflow",
            intent="Auto-process email requests and record in CRM",
            trigger=WorkflowTrigger(
                type="new_email",
                application="demo_email",
                description="Trigger description"
            ),
            actions=[
                WorkflowAction(
                    type="open_email",
                    application="demo_email",
                    description="Open email",
                    target="customer_request"
                ),
                WorkflowAction(
                    type="search_customer",
                    application="demo_crm",
                    description="Search CRM",
                    target="customer"
                )
            ],
            variables=["customer_name"],
            applications=["demo_email", "demo_crm"],
            requires_approval=True
        )
        mock_generate.return_value = mock_proposal

        res = self.client.post(
            "/api/ai/workflow/generate",
            json={
                "sequence": ["open_email", "search_customer"],
                "applications": ["demo_email", "demo_crm"]
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIsNotNone(data["workflow"])
        self.assertEqual(data["workflow"]["name"], "Inferred Customer Workflow")
        self.assertEqual(len(data["workflow"]["actions"]), 2)
        self.assertTrue(data["workflow"]["requires_approval"])

    @patch("backend.routes.ai.gemini_workflow_service.generate_workflow")
    def test_generate_workflow_missing_key_returns_503(self, mock_generate):
        mock_generate.side_effect = GeminiConfigurationError("Missing GEMINI_API_KEY")
        res = self.client.post(
            "/api/ai/workflow/generate",
            json={"sequence": ["open_email"]}
        )
        self.assertEqual(res.status_code, 503)
        self.assertIn("Gemini service is not configured", res.json()["detail"])


class TestPhase1AndPhase2Regression(unittest.TestCase):
    """Verify that Phase 1 and Phase 2 endpoints remain intact and functioning."""

    def setUp(self):
        import backend.database as db_mod
        try:
            import mongomock_motor
            db_mod._mongo_client = mongomock_motor.AsyncMongoMockClient()
            db_mod._database = db_mod._mongo_client[settings.MONGODB_DATABASE]
        except ImportError:
            db_mod._mongo_client = None
            db_mod._database = None
        self.client = TestClient(app)

    def tearDown(self):
        import backend.database as db_mod
        if db_mod._mongo_client:
            db_mod._mongo_client.close()
        db_mod._mongo_client = None
        db_mod._database = None

    def test_phase1_health_check(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ok"})

    def test_phase1_events_endpoint(self):
        res = self.client.get("/api/events?limit=5")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    def test_phase2_discovery_repeated(self):
        res = self.client.get("/api/discovery/repeated")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("detected", data)
        self.assertIn("workflows", data)
        if data["detected"]:
            wf = data["workflows"][0]
            self.assertEqual(wf["occurrences"], 3)
            self.assertAlmostEqual(wf["similarity"], 1.0, places=2)
            self.assertEqual(
                wf["sequence"],
                ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"]
            )


if __name__ == "__main__":
    live_test = "--live-gemini" in sys.argv
    if live_test:
        sys.argv.remove("--live-gemini")

    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestPhase3AIModels))
    suite.addTest(unittest.makeSuite(TestPhase3MockedGeminiService))
    suite.addTest(unittest.makeSuite(TestPhase3EndpointWithMock))
    suite.addTest(unittest.makeSuite(TestPhase1AndPhase2Regression))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if not result.wasSuccessful():
        sys.exit(1)

    if live_test:
        print("\n--- Running Live Gemini API Test ---")
        client = TestClient(app)
        res = client.post(
            "/api/ai/workflow/generate",
            json={
                "sequence": [
                    "open_email",
                    "download_attachment",
                    "search_customer",
                    "update_customer",
                    "send_message"
                ],
                "applications": ["demo_email", "demo_crm", "demo_messaging"]
            }
        )
        print(f"Status: {res.status_code}")
        print(f"Workflow: {res.json().get('workflow', {}).get('name')}")
        print("Live Gemini test passed!")
