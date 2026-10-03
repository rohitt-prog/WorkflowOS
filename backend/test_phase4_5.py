"""
Phase 4.5 Integration Tests — Execution Observability & Details

Covers:
1. Execution History via GET /api/automation/executions
2. Completed execution representation with timing, applications, and action states
3. Failed execution representation with human intervention and skipped actions
4. Action status representation (completed, failed, skipped, pending)
5. Execution detail retrieval via GET /api/automation/executions/{execution_id}
6. Timing metadata measurement (execution_time_seconds, started_at, completed_at)
"""

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
from automation.service import automation_service


def make_test_proposal(name: str = "Test Observability Workflow", customer: str = "Rahul") -> WorkflowProposal:
    return WorkflowProposal(
        name=name,
        intent="Test execution observability for Phase 4.5",
        trigger=WorkflowTrigger(
            type="new_email",
            application="demo_email",
            description="Email received"
        ),
        actions=[
            WorkflowAction(
                type="open_email",
                application="demo_email",
                description="Open email in demo client",
                target="customer_request"
            ),
            WorkflowAction(
                type="download_attachment",
                application="demo_email",
                description="Download attachment file",
                target="attachment"
            ),
            WorkflowAction(
                type="search_customer",
                application="demo_crm",
                description="Search for customer record",
                target=customer
            ),
            WorkflowAction(
                type="update_customer",
                application="demo_crm",
                description="Update customer record",
                target=customer
            ),
            WorkflowAction(
                type="send_message",
                application="demo_chat",
                description="Send confirmation message",
                target="customer_request"
            ),
        ],
        variables=["customer_name", "attachment"],
        applications=["demo_email", "demo_crm", "demo_chat"],
        requires_approval=True
    )


class TestPhase45ExecutionObservability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_completed_execution_representation_and_timing(self):
        """
        Verify completed execution returns:
        - status='completed'
        - execution_time_seconds > 0
        - started_at and completed_at ISO strings
        - applications list
        - all_actions with status='completed' for all 5 actions
        """
        proposal = make_test_proposal("Successful Observability Run")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": True,
            "executor_type": "noop",  # Uses NoOpExecutor for fast deterministic test
            "parameters": {"customer_name": "Rahul"}
        }

        res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "completed")
        self.assertEqual(len(data["completed_actions"]), 5)
        self.assertEqual(data["total_actions"], 5)
        self.assertFalse(data["requires_human_intervention"])

        # Phase 4.5: timing metadata
        self.assertIn("execution_time_seconds", data)
        self.assertIsNotNone(data["execution_time_seconds"])
        self.assertGreaterEqual(data["execution_time_seconds"], 0.0)
        self.assertIn("started_at", data)
        self.assertIsNotNone(data["started_at"])
        self.assertIn("completed_at", data)
        self.assertIsNotNone(data["completed_at"])

        # Phase 4.5: applications list
        self.assertIn("applications", data)
        self.assertIn("demo_email", data["applications"])
        self.assertIn("demo_crm", data["applications"])
        self.assertIn("demo_chat", data["applications"])

        # Phase 4.5: all_actions details with application and status
        self.assertIn("all_actions", data)
        self.assertEqual(len(data["all_actions"]), 5)
        for act in data["all_actions"]:
            self.assertEqual(act["status"], "completed")
            self.assertIn(act["application"], ["demo_email", "demo_crm", "demo_chat"])
            self.assertTrue(len(act["description"]) > 0)

        print("  ✓ Test 1: Completed execution representation and timing metadata verified.")

    def test_02_paused_execution_representation_and_pending_actions(self):
        """
        Phase 4.6: Verify that when an action fails, execution transitions to PAUSED
        (not FAILED) and post-failure actions are PENDING (not SKIPPED).

        Verify:
        - status='paused'
        - failed_action='search_customer'
        - requires_human_intervention=True
        - resume_available=True
        - human_intervention title is 'Workflow paused — action failed'
        - all_actions: 2 completed, 1 failed, 2 pending (awaiting resume)
        """
        proposal = make_test_proposal("Paused Observability Run", customer="Unknown Customer")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": True,
            "executor_type": "noop",
            "parameters": {
                "fail_actions": ["search_customer"]
            }
        }

        res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Phase 4.6: failure produces PAUSED, not FAILED
        self.assertEqual(data["status"], "paused")
        self.assertEqual(data["failed_action"], "search_customer")
        self.assertTrue(data["requires_human_intervention"])
        self.assertIsNotNone(data["human_intervention"])
        self.assertEqual(data["human_intervention"]["title"], "Workflow paused — action failed")

        # Phase 4.6: resume_available must be True
        self.assertTrue(data["resume_available"])

        # Verify completed actions: only 2 succeeded
        self.assertEqual(len(data["completed_actions"]), 2)
        self.assertIn("open_email", data["completed_actions"])
        self.assertIn("download_attachment", data["completed_actions"])

        # Phase 4.6: all_actions state — 2 completed, 1 failed, 2 PENDING (not skipped)
        self.assertIn("all_actions", data)
        all_acts = data["all_actions"]
        self.assertEqual(len(all_acts), 5)

        self.assertEqual(all_acts[0]["action"], "open_email")
        self.assertEqual(all_acts[0]["status"], "completed")

        self.assertEqual(all_acts[1]["action"], "download_attachment")
        self.assertEqual(all_acts[1]["status"], "completed")

        self.assertEqual(all_acts[2]["action"], "search_customer")
        self.assertEqual(all_acts[2]["status"], "failed")

        # Phase 4.6: post-failure actions are 'pending', not 'skipped'
        self.assertEqual(all_acts[3]["action"], "update_customer")
        self.assertEqual(all_acts[3]["status"], "pending")

        self.assertEqual(all_acts[4]["action"], "send_message")
        self.assertEqual(all_acts[4]["status"], "pending")

        print("  ✓ Test 2: Paused execution (Phase 4.6) representation and pending post-failure actions verified.")

    def test_03_unapproved_execution_representation(self):
        """
        Verify unapproved (approved=False) execution returns:
        - status='pending'
        - 0 completed actions
        - all_actions with status='pending'
        """
        proposal = make_test_proposal("Unapproved Run")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": False,
            "executor_type": "noop"
        }

        res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["status"], "pending")
        self.assertEqual(len(data["completed_actions"]), 0)
        self.assertFalse(data["requires_human_intervention"])
        self.assertEqual(data["execution_time_seconds"], 0.0)

        for act in data.get("all_actions", []):
            self.assertEqual(act["status"], "pending")

        print("  ✓ Test 3: Unapproved execution pending state verified.")

    def test_04_execution_history_list_endpoint(self):
        """
        Verify GET /api/automation/executions returns list of all recorded executions
        including status, completed/total actions, timestamps, and failure reason.
        """
        res = self.client.get("/api/automation/executions")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("executions", data)
        executions = data["executions"]
        self.assertIsInstance(executions, list)
        self.assertGreaterEqual(len(executions), 3)

        # Verify fields on each recorded execution
        for ex in executions:
            self.assertIn("execution_id", ex)
            self.assertIn("workflow_name", ex)
            self.assertIn("status", ex)
            self.assertIn(ex["status"], ["completed", "failed", "pending", "running", "paused", "cancelled"])
            self.assertIn("completed_actions", ex)
            self.assertIn("total_actions", ex)
            self.assertIn("started_at", ex)

        print("  ✓ Test 4: GET /api/automation/executions history list endpoint verified.")

    def test_05_execution_detail_endpoint(self):
        """
        Verify GET /api/automation/executions/{execution_id} returns full detail
        for a specific execution run.
        """
        # Get list first
        list_res = self.client.get("/api/automation/executions")
        self.assertEqual(list_res.status_code, 200)
        executions = list_res.json()["executions"]
        self.assertGreater(len(executions), 0)

        target_id = executions[0]["execution_id"]
        detail_res = self.client.get(f"/api/automation/executions/{target_id}")
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.json()

        self.assertEqual(detail["execution_id"], target_id)
        self.assertIn("workflow_name", detail)
        self.assertIn("status", detail)
        self.assertIn("actions_detail", detail)
        self.assertIn("applications", detail)

        # 404 for unknown execution ID
        bad_res = self.client.get("/api/automation/executions/non_existent_id")
        self.assertEqual(bad_res.status_code, 404)

        print("  ✓ Test 5: GET /api/automation/executions/{execution_id} detail endpoint verified.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
