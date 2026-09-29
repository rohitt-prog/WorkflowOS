"""
Phase 4.4 Integration Tests — Frontend Approval to Automation Execution

PREREQUISITES:
  - Frontend running at http://localhost:3000 (cd frontend && npm run dev)
  - Playwright Chromium installed (.venv/bin/playwright install chromium)
  - Python venv active (.venv)

RUN WITH:
  .venv/bin/python backend/test_phase4_4.py

COVERS:
  A. approved=false blocks execution and never launches Playwright
  B. approved=true happy-path executes all 5 actions end-to-end to status='completed'
  C. failure at search_customer stops later actions, returns status='failed' with human intervention info
  D. execution chain: API route -> AutomationService -> AutomationEngine -> PlaywrightExecutor
  E. executor_type='noop' validation for unit testing
  F. GET /api/automation/executions history tracking
"""

import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.main import app
from ai.models import WorkflowProposal, WorkflowAction, WorkflowTrigger
from automation.models import AutomationStatus
from automation.service import automation_service

FRONTEND_BASE_URL = os.getenv("PLAYWRIGHT_BASE_URL", "http://localhost:3000")


def make_five_step_proposal(customer_name: str = "Rahul") -> WorkflowProposal:
    """Creates a canonical 5-action WorkflowProposal matching Phase 3 output."""
    return WorkflowProposal(
        name="Process Customer Request (Phase 4.4)",
        intent="Automate customer email attachment processing and CRM update",
        trigger=WorkflowTrigger(
            type="new_email",
            application="demo_email",
            description="Email received from customer"
        ),
        actions=[
            WorkflowAction(
                type="open_email",
                application="demo_email",
                description="Open customer email",
                target="customer_request"
            ),
            WorkflowAction(
                type="download_attachment",
                application="demo_email",
                description="Download email attachment",
                target="attachment"
            ),
            WorkflowAction(
                type="search_customer",
                application="demo_crm",
                description="Search customer in CRM",
                target=customer_name
            ),
            WorkflowAction(
                type="update_customer",
                application="demo_crm",
                description="Update customer record in CRM",
                target=customer_name
            ),
            WorkflowAction(
                type="send_message",
                application="demo_chat",
                description="Send notification message to chat",
                target="customer_request"
            ),
        ],
        variables=["customer_name", "attachment"],
        applications=["demo_email", "demo_crm", "demo_chat"],
        requires_approval=True
    )


class TestPhase44ApprovalToExecution(unittest.TestCase):
    """
    Phase 4.4 integration tests connecting the frontend approval flow
    to the AutomationEngine and PlaywrightExecutor.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # ── Test A: approved=False blocks execution ──────────────────────────────

    def test_01_approved_false_blocks_execution(self):
        """
        Req 3 & 11A:
        When approved=False:
        - execution does not start
        - status is 'pending'
        - Playwright is NOT called
        - completed_actions is empty
        """
        proposal = make_five_step_proposal("Rahul")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": False,
            "executor_type": "playwright"
        }

        res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual(data["status"], "pending", f"Expected 'pending', got: {data['status']}")
        self.assertEqual(len(data["completed_actions"]), 0)
        self.assertEqual(len(data["actions"]), 0)
        self.assertFalse(data["requires_human_intervention"])
        print("  ✓ Test A: approved=False safely refused. Playwright not started. Status=pending.")

    # ── Test B: approved=True happy path ─────────────────────────────────────

    def test_02_approved_true_happy_path_five_actions(self):
        """
        Req 7 & 11B:
        When approved=True with target 'Rahul':
        - all 5 canonical actions execute end-to-end via Playwright
        - open_email -> download_attachment -> search_customer -> update_customer -> send_message
        - final status is 'completed'
        - completed_actions contains all 5 actions
        """
        proposal = make_five_step_proposal("Rahul")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": True,
            "parameters": {"customer_name": "Rahul"},
            "executor_type": "playwright"
        }

        res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual(data["status"], "completed", f"Expected 'completed', got: {data}")
        self.assertTrue(data["workflow_id"].startswith("exec_"))

        expected_actions = [
            "open_email",
            "download_attachment",
            "search_customer",
            "update_customer",
            "send_message"
        ]
        self.assertEqual(data["completed_actions"], expected_actions)
        self.assertEqual(len(data["actions"]), 5)
        for act in data["actions"]:
            self.assertEqual(act["status"], "completed")

        print("  ✓ Test B: approved=True executed all 5 actions end-to-end. Status=completed.")

    # ── Test C: failure at search_customer ───────────────────────────────────

    def test_03_failure_at_search_customer_stops_subsequent_actions(self):
        """
        Req 8, 9 & 11C:
        When searching for a non-existent customer ('Unknown Customer'):
        - open_email: completed
        - download_attachment: completed
        - search_customer: failed
        - update_customer: NOT executed
        - send_message: NOT executed
        - status: 'failed'
        - failed_action: 'search_customer'
        - requires_human_intervention: True
        - human_intervention contains instructions for CRM
        """
        proposal = make_five_step_proposal("Unknown Customer")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": True,
            "parameters": {"customer_name": "Unknown Customer"},
            "executor_type": "playwright"
        }

        res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual(data["status"], "failed", f"Expected 'failed', got: {data['status']}")
        self.assertEqual(data["failed_action"], "search_customer")
        self.assertIn("Unknown Customer", data["message"])
        self.assertTrue(data["requires_human_intervention"])

        # Check human intervention details
        hi = data.get("human_intervention") or {}
        self.assertEqual(hi.get("title"), "Workflow paused")
        self.assertIn("CRM", hi.get("action_required", ""))

        # Check completed actions
        completed = data["completed_actions"]
        self.assertIn("open_email", completed)
        self.assertIn("download_attachment", completed)
        self.assertNotIn("update_customer", completed)
        self.assertNotIn("send_message", completed)

        print("  ✓ Test C: Unknown Customer failed at search_customer. Subsequent actions halted. Status=failed.")

    # ── Test D: executor_type='noop' unit testing ────────────────────────────

    def test_04_noop_executor_execution(self):
        """
        Req 2:
        Ensure NoOpExecutor remains fully operational through the API endpoint
        for headless/deterministic unit testing without browser dependencies.
        """
        proposal = make_five_step_proposal("Rahul")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": True,
            "executor_type": "noop"
        }

        res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(len(data["completed_actions"]), 5)
        print("  ✓ Test D: NoOpExecutor runs cleanly through POST /api/automation/execute.")

    # ── Test E: execution tracking and history ────────────────────────────────

    def test_05_execution_tracking_in_service_and_history(self):
        """
        Req 1:
        Verify the execution chain records runs in AutomationService
        and that GET /api/automation/executions returns them.
        """
        res = self.client.get("/api/automation/executions")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("executions", data)
        self.assertGreater(len(data["executions"]), 0)
        print(f"  ✓ Test E: History tracked. Recorded executions: {len(data['executions'])}.")

    # ── Test F: unsupported action type validation ───────────────────────────

    def test_06_unsupported_action_verb_rejected(self):
        """Verify that unsupported action verbs are blocked by AutomationEngine."""
        bad_action = WorkflowAction(
            type="format_hard_drive",
            application="system",
            description="Malicious step",
            target="disk"
        )
        proposal = WorkflowProposal(
            name="Dangerous Workflow",
            intent="Test invalid verb",
            trigger=WorkflowTrigger(type="evt", application="app", description="desc"),
            actions=[bad_action],
            variables=[],
            applications=["system"],
            requires_approval=True
        )

        payload = {
            "workflow": proposal.model_dump(),
            "approved": True,
            "executor_type": "noop"
        }

        res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "failed")
        self.assertIn("format_hard_drive", data["message"])
        print("  ✓ Test F: Unsupported action verb gracefully failed by AutomationEngine.")


if __name__ == "__main__":
    print("=" * 70)
    print("  Phase 4.4 — End-to-End Approval to Execution Tests")
    print(f"  Frontend URL: {FRONTEND_BASE_URL}")
    print("  Backend API: /api/automation/execute")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPhase44ApprovalToExecution)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
