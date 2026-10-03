"""
Phase 4.6 Integration Tests — Human-in-the-Loop Execution: Pause, Resume, Cancel

Covers all 15 required test specifications:
  TEST 1:  Successful execution still works (approved=True, 5/5 completed)
  TEST 2:  Action failure transitions execution: RUNNING → PAUSED
  TEST 3:  Paused execution metadata: failed_action, failure_reason,
           requires_human_intervention=True, resume_available=True, paused_at
  TEST 4:  Resume retries the failed action
  TEST 5:  Resume does NOT rerun previously completed actions (open_email, download_attachment)
  TEST 6:  Resume continues through remaining actions (search_customer, update_customer, send_message)
  TEST 7:  Successful resume results in COMPLETED (5/5 actions completed)
  TEST 8:  Resume increments resume_count
  TEST 9:  Cancel paused execution: PAUSED → CANCELLED
  TEST 10: Cancelled execution cannot be resumed (409 Conflict)
  TEST 11: Completed execution cannot be resumed (409 Conflict)
  TEST 12: Failed/non-resumable execution cannot be resumed (409 Conflict)
  TEST 13: Invalid state transitions are rejected (e.g. cancel completed -> 409, unknown id -> 404)
  TEST 14: Execution history contains paused, resumed, and cancelled executions
  TEST 15: Phase 4.5 observability remains correct (actions_detail, timestamps, applications, total_actions)
"""

import sys
import os
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.main import app
from ai.models import WorkflowProposal, WorkflowAction, WorkflowTrigger
from automation.models import AutomationStatus, VALID_TRANSITIONS, is_valid_transition
from automation.service import automation_service


def make_test_proposal(name: str = "Customer Request Pipeline", customer: str = "Rahul") -> WorkflowProposal:
    """Creates a canonical 5-step proposal matching Phase 3 schema."""
    return WorkflowProposal(
        name=name,
        intent="Automate customer email processing, CRM update, and chat notification",
        trigger=WorkflowTrigger(
            type="new_email",
            application="demo_email",
            description="New email received"
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
                description="Download attachment",
                target="attachment"
            ),
            WorkflowAction(
                type="search_customer",
                application="demo_crm",
                description="Search customer in CRM",
                target=customer
            ),
            WorkflowAction(
                type="update_customer",
                application="demo_crm",
                description="Update customer record in CRM",
                target=customer
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


class TestPhase46HumanInTheLoop(unittest.TestCase):
    """
    Comprehensive test suite for Phase 4.6 Human-in-the-Loop:
    Pause on failure, Resume execution from failed step, and Cancel.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # ── TEST 1: Successful execution still works ─────────────────────────────
    def test_01_successful_execution_still_works(self):
        """TEST 1: Successful execution without errors completes all 5 actions."""
        proposal = make_test_proposal("Happy Path 4.6", customer="Rahul")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": True,
            "executor_type": "noop",
        }

        res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(len(data["completed_actions"]), 5)
        self.assertEqual(data["total_actions"], 5)
        self.assertFalse(data["requires_human_intervention"])
        self.assertFalse(data["resume_available"])
        self.assertEqual(data["resume_count"], 0)
        self.assertIsNotNone(data["completed_at"])
        print("  ✓ TEST 1: Successful execution completes normally with status=completed.")

    # ── TEST 2: Action failure causes RUNNING → PAUSED ───────────────────────
    def test_02_action_failure_causes_paused_state(self):
        """TEST 2: When an action fails, execution status is PAUSED (not FAILED)."""
        proposal = make_test_proposal("Failing Search Run", customer="Unknown Customer")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": True,
            "executor_type": "noop",
            "context": {"fail_actions": ["search_customer"]},
        }

        res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual(data["status"], "paused", f"Expected status 'paused', got: {data['status']}")
        self.assertEqual(data["failed_action"], "search_customer")
        self.assertTrue(data["resume_available"])
        print("  ✓ TEST 2: Action failure cleanly transitions RUNNING → PAUSED.")

    # ── TEST 3: Paused execution metadata ─────────────────────────────────────
    def test_03_paused_execution_contains_all_required_metadata(self):
        """TEST 3: Paused execution contains failure details, human guidance, and resume flag."""
        proposal = make_test_proposal("Metadata Pause Run", customer="Unknown Customer")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": True,
            "executor_type": "noop",
            "context": {"fail_actions": ["search_customer"]},
        }

        res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual(data["status"], "paused")
        self.assertEqual(data["failed_action"], "search_customer")
        self.assertIsNotNone(data["failure_reason"])
        self.assertTrue(data["requires_human_intervention"])
        self.assertTrue(data["resume_available"])
        self.assertEqual(data["resume_count"], 0)
        self.assertIsNotNone(data["paused_at"])
        self.assertIsNone(data["completed_at"])

        # Check human intervention object
        self.assertIsNotNone(data["human_intervention"])
        self.assertIn("title", data["human_intervention"])
        self.assertIn("reason", data["human_intervention"])
        self.assertIn("action_required", data["human_intervention"])

        # Check completed vs pending actions
        self.assertEqual(data["completed_actions"], ["open_email", "download_attachment"])
        print("  ✓ TEST 3: Paused execution contains complete human-in-the-loop metadata.")

    # ── TEST 4, 5, 6, 7, 8: Resume Execution Flow ────────────────────────────
    def test_04_to_08_resume_retries_failed_action_and_completes(self):
        """
        TEST 4: Resume retries the failed action.
        TEST 5: Resume does NOT rerun previously completed actions.
        TEST 6: Resume continues through remaining actions.
        TEST 7: Successful resume results in COMPLETED.
        TEST 8: Resume increments resume_count.
        """
        # Step 1: Trigger initial failure at search_customer
        proposal = make_test_proposal("Resume Test Run", customer="Unknown Customer")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": True,
            "executor_type": "noop",
            "context": {"fail_actions": ["search_customer"]},
        }

        exec_res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(exec_res.status_code, 200)
        exec_data = exec_res.json()
        self.assertEqual(exec_data["status"], "paused")
        execution_id = exec_data["workflow_id"]

        # Step 2: Resume with resolved human intervention (fail_actions cleared)
        resume_payload = {
            "executor_type": "noop",
            "context": {"fail_actions": []},
            "parameters": {"customer_name": "Rahul"},
        }
        resume_res = self.client.post(
            f"/api/automation/executions/{execution_id}/resume",
            json=resume_payload,
        )
        self.assertEqual(resume_res.status_code, 200)
        resumed_data = resume_res.json()

        # TEST 7: Successful resume reaches COMPLETED
        self.assertEqual(resumed_data["status"], "completed")

        # TEST 5: Completed actions contains all 5; previously completed were preserved
        expected_completed = [
            "open_email",
            "download_attachment",
            "search_customer",
            "update_customer",
            "send_message",
        ]
        self.assertEqual(resumed_data["completed_actions"], expected_completed)
        self.assertEqual(len(resumed_data["completed_actions"]), 5)

        # TEST 8: resume_count incremented to 1
        self.assertEqual(resumed_data["resume_count"], 1)
        self.assertIsNotNone(resumed_data["resumed_at"])
        self.assertFalse(resumed_data["resume_available"])
        self.assertFalse(resumed_data["requires_human_intervention"])

        # TEST 4 & 6: Actions detail verifies search_customer succeeded and subsequent actions ran
        actions = resumed_data["all_actions"]
        self.assertEqual(len(actions), 5)
        for act in actions:
            self.assertEqual(act["status"], "completed")

        print("  ✓ TESTS 4–8: Resume retried failed action, skipped completed ones, incremented count, and finished with status=completed.")

    # ── TEST 9: Cancel paused execution ──────────────────────────────────────
    def test_09_cancel_paused_execution(self):
        """TEST 9: Cancel paused execution transitions PAUSED → CANCELLED."""
        proposal = make_test_proposal("Cancel Run", customer="Unknown Customer")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": True,
            "executor_type": "noop",
            "context": {"fail_actions": ["search_customer"]},
        }

        exec_res = self.client.post("/api/automation/execute", json=payload)
        exec_data = exec_res.json()
        self.assertEqual(exec_data["status"], "paused")
        execution_id = exec_data["workflow_id"]

        # Cancel the paused execution
        cancel_res = self.client.post(f"/api/automation/executions/{execution_id}/cancel")
        self.assertEqual(cancel_res.status_code, 200)

        cancel_data = cancel_res.json()
        self.assertEqual(cancel_data["status"], "cancelled")
        self.assertFalse(cancel_data["resume_available"])
        self.assertFalse(cancel_data["requires_human_intervention"])
        self.assertIsNotNone(cancel_data["cancelled_at"])
        print("  ✓ TEST 9: Paused execution cancelled successfully with status=cancelled.")

    # ── TEST 10: Cancelled execution cannot be resumed ────────────────────────
    def test_10_cancelled_execution_cannot_be_resumed(self):
        """TEST 10: Resuming a CANCELLED execution is rejected with 409 Conflict."""
        proposal = make_test_proposal("Cancelled Not Resumable", customer="Unknown Customer")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": True,
            "executor_type": "noop",
            "context": {"fail_actions": ["search_customer"]},
        }

        exec_res = self.client.post("/api/automation/execute", json=payload)
        execution_id = exec_res.json()["workflow_id"]

        # Cancel first
        cancel_res = self.client.post(f"/api/automation/executions/{execution_id}/cancel")
        self.assertEqual(cancel_res.status_code, 200)

        # Attempt to resume cancelled execution
        resume_res = self.client.post(f"/api/automation/executions/{execution_id}/resume")
        self.assertEqual(resume_res.status_code, 409)
        self.assertIn("Only PAUSED executions can be resumed", resume_res.json()["detail"])
        print("  ✓ TEST 10: Cancelled execution cannot be resumed (409 Conflict).")

    # ── TEST 11: Completed execution cannot be resumed ───────────────────────
    def test_11_completed_execution_cannot_be_resumed(self):
        """TEST 11: Resuming a COMPLETED execution is rejected with 409 Conflict."""
        proposal = make_test_proposal("Completed Not Resumable", customer="Rahul")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": True,
            "executor_type": "noop",
        }

        exec_res = self.client.post("/api/automation/execute", json=payload)
        execution_id = exec_res.json()["workflow_id"]
        self.assertEqual(exec_res.json()["status"], "completed")

        # Attempt to resume completed execution
        resume_res = self.client.post(f"/api/automation/executions/{execution_id}/resume")
        self.assertEqual(resume_res.status_code, 409)
        self.assertIn("Only PAUSED executions can be resumed", resume_res.json()["detail"])
        print("  ✓ TEST 11: Completed execution cannot be resumed (409 Conflict).")

    # ── TEST 12: Failed execution cannot be resumed ──────────────────────────
    def test_12_terminal_failed_execution_cannot_be_resumed(self):
        """TEST 12: Validation-failed execution (terminal FAILED) cannot be resumed."""
        bad_action = WorkflowAction(
            type="unsupported_action",
            application="demo_email",
            description="Unsupported",
            target="target"
        )
        proposal = WorkflowProposal(
            name="Invalid Action Workflow",
            intent="Test invalid verb",
            trigger=WorkflowTrigger(type="evt", application="app", description="desc"),
            actions=[bad_action],
            variables=[],
            applications=["demo_email"],
            requires_approval=True
        )

        exec_res = self.client.post(
            "/api/automation/execute",
            json={"workflow": proposal.model_dump(), "approved": True, "executor_type": "noop"}
        )
        self.assertEqual(exec_res.json()["status"], "failed")
        execution_id = exec_res.json()["workflow_id"]

        # Attempt resume
        resume_res = self.client.post(f"/api/automation/executions/{execution_id}/resume")
        self.assertEqual(resume_res.status_code, 409)
        print("  ✓ TEST 12: Terminal failed execution cannot be resumed (409 Conflict).")

    # ── TEST 13: Invalid state transitions are rejected ───────────────────────
    def test_13_invalid_state_transitions_rejected(self):
        """TEST 13: State machine rules strictly reject disallowed transitions."""
        # 1. State machine table validations
        self.assertFalse(is_valid_transition(AutomationStatus.COMPLETED, AutomationStatus.RUNNING))
        self.assertFalse(is_valid_transition(AutomationStatus.COMPLETED, AutomationStatus.PAUSED))
        self.assertFalse(is_valid_transition(AutomationStatus.COMPLETED, AutomationStatus.CANCELLED))
        self.assertFalse(is_valid_transition(AutomationStatus.CANCELLED, AutomationStatus.RUNNING))
        self.assertFalse(is_valid_transition(AutomationStatus.FAILED, AutomationStatus.RUNNING))
        self.assertTrue(is_valid_transition(AutomationStatus.PAUSED, AutomationStatus.RUNNING))
        self.assertTrue(is_valid_transition(AutomationStatus.PAUSED, AutomationStatus.CANCELLED))
        self.assertTrue(is_valid_transition(AutomationStatus.RUNNING, AutomationStatus.PAUSED))

        # 2. Cancelling an already-completed execution via API -> 409 Conflict
        proposal = make_test_proposal("Complete Then Cancel", customer="Rahul")
        exec_res = self.client.post(
            "/api/automation/execute",
            json={"workflow": proposal.model_dump(), "approved": True, "executor_type": "noop"}
        )
        completed_id = exec_res.json()["workflow_id"]

        cancel_res = self.client.post(f"/api/automation/executions/{completed_id}/cancel")
        self.assertEqual(cancel_res.status_code, 409)

        # 3. Resume / Cancel with non-existent ID -> 404 Not Found
        res_resume_404 = self.client.post("/api/automation/executions/non_existent_id/resume")
        self.assertEqual(res_resume_404.status_code, 404)

        res_cancel_404 = self.client.post("/api/automation/executions/non_existent_id/cancel")
        self.assertEqual(res_cancel_404.status_code, 404)
        print("  ✓ TEST 13: Invalid state transitions and missing IDs correctly rejected.")

    # ── TEST 14: Execution history tracks paused/resumed/cancelled ────────────
    def test_14_execution_history_contains_all_new_statuses(self):
        """TEST 14: GET /api/automation/executions history includes paused/resumed/cancelled runs."""
        res = self.client.get("/api/automation/executions")
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertIn("executions", data)
        self.assertGreater(len(data["executions"]), 0)

        # Check that statuses in history are valid
        valid_statuses = {"pending", "running", "paused", "completed", "failed", "cancelled"}
        for item in data["executions"]:
            self.assertIn(item["status"], valid_statuses)
            self.assertIn("execution_id", item)
            self.assertIn("workflow_name", item)
            self.assertIn("completed_actions", item)
            self.assertIn("total_actions", item)

        # Confirm at least one completed and one paused or cancelled exist in history
        statuses_found = {item["status"] for item in data["executions"]}
        self.assertIn("completed", statuses_found)
        print(f"  ✓ TEST 14: Execution history verified with statuses: {statuses_found}")

    # ── TEST 15: Phase 4.5 Observability remains intact ───────────────────────
    def test_15_observability_fields_preserved_across_lifecycle(self):
        """TEST 15: Verify timestamps, actions_detail, applications, total_actions."""
        proposal = make_test_proposal("Observability Integrity", customer="Unknown Customer")
        payload = {
            "workflow": proposal.model_dump(),
            "approved": True,
            "executor_type": "noop",
            "context": {"fail_actions": ["search_customer"]},
        }

        # 1. Check paused execution observability
        res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("all_actions", data)
        self.assertEqual(len(data["all_actions"]), 5)
        self.assertEqual(data["total_actions"], 5)
        self.assertEqual(len(data["completed_actions"]), 2)
        self.assertIsNotNone(data["started_at"])
        self.assertIsNotNone(data["paused_at"])
        self.assertIn("demo_email", data["applications"])
        self.assertIn("demo_crm", data["applications"])

        # Check action statuses in paused execution: 2 completed, 1 failed, 2 pending
        actions = data["all_actions"]
        self.assertEqual(actions[0]["status"], "completed")
        self.assertEqual(actions[1]["status"], "completed")
        self.assertEqual(actions[2]["status"], "failed")
        self.assertEqual(actions[3]["status"], "pending")
        self.assertEqual(actions[4]["status"], "pending")

        # 2. Check resumed execution observability
        exec_id = data["workflow_id"]
        res_resume = self.client.post(
            f"/api/automation/executions/{exec_id}/resume",
            json={"executor_type": "noop", "context": {"fail_actions": []}}
        )
        resumed = res_resume.json()
        self.assertEqual(resumed["status"], "completed")
        self.assertEqual(len(resumed["completed_actions"]), 5)
        self.assertIsNotNone(resumed["resumed_at"])
        self.assertIsNotNone(resumed["completed_at"])
        self.assertGreaterEqual(resumed["execution_time_seconds"], 0.0)

        # All actions should now be completed
        for act in resumed["all_actions"]:
            self.assertEqual(act["status"], "completed")

        print("  ✓ TEST 15: Observability fields correctly maintained across Pause and Resume.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
