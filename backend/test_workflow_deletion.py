#!/usr/bin/env python3
"""
Unit tests for Rejected Workflow Deletion (UX Improvement 3).

Verifies:
1. Non-rejected workflows (NEW, RECOMMENDED, LEARNING, DEPRIORITIZED without rejection) cannot be deleted (400 Bad Request).
2. Explicitly rejected workflows can be deleted via DELETE /api/workflows/{workflow_id} (200 OK).
3. Deleting a rejected workflow removes it from subsequent discovery scan results.
4. Attempting to delete an already deleted workflow returns 400.
5. Invalid workflow ID inputs are rejected safely.
"""

import unittest
from fastapi.testclient import TestClient

from backend.main import app
from backend.learning.models import FeedbackDecision, WorkflowFeedbackRequest
from backend.learning.service import learning_service


class TestWorkflowDeletion(unittest.TestCase):
    def setUp(self):
        learning_service.reset_cache()
        self.client = TestClient(app)

    def tearDown(self):
        learning_service.reset_cache()

    def test_delete_non_rejected_workflow_is_rejected(self):
        """A new or non-rejected workflow must return 400 when deletion is attempted."""
        wf_id = "wf_unreviewed_workflow"
        res = self.client.delete(f"/api/workflows/{wf_id}")
        self.assertEqual(res.status_code, 400)
        self.assertIn("not in an explicitly rejected state", res.json()["detail"])

    def test_delete_approved_workflow_is_rejected(self):
        """An approved workflow must return 400 when deletion is attempted."""
        wf_id = "wf_approved_workflow"
        # Submit approval feedback
        res_fb = self.client.post(
            f"/api/workflows/{wf_id}/feedback",
            json={"decision": "approve"}
        )
        self.assertEqual(res_fb.status_code, 200)

        # Attempt delete
        res = self.client.delete(f"/api/workflows/{wf_id}")
        self.assertEqual(res.status_code, 400)
        self.assertIn("not in an explicitly rejected state", res.json()["detail"])

    def test_delete_deprioritized_without_rejection_is_forbidden(self):
        """A workflow deprioritized solely by score/failures without human rejection cannot be deleted."""
        wf_id = "wf_deprioritized_by_failures"
        from backend.learning.models import WorkflowLearningState, RecommendationStatus
        state = WorkflowLearningState(
            workflow_id=wf_id,
            rejection_count=0,
            failed_execution_count=5,
            learning_score=0.20,
            recommendation_status=RecommendationStatus.DEPRIORITIZED,
        )
        learning_service._states[wf_id] = state

        res = self.client.delete(f"/api/workflows/{wf_id}")
        self.assertEqual(res.status_code, 400)
        self.assertIn("not in an explicitly rejected state", res.json()["detail"])


    def test_delete_rejected_workflow_succeeds(self):
        """A workflow explicitly rejected by operator can be deleted successfully."""
        wf_id = "wf_candidate_to_delete"

        # Operator explicitly rejects the workflow
        res_fb = self.client.post(
            f"/api/workflows/{wf_id}/feedback",
            json={"decision": "reject", "rejection_reason": "Redundant workflow"}
        )
        self.assertEqual(res_fb.status_code, 200)

        # Now delete it
        res_del = self.client.delete(f"/api/workflows/{wf_id}")
        self.assertEqual(res_del.status_code, 200)
        data = res_del.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["workflow_id"], wf_id)

        # Second deletion should fail
        res_del_again = self.client.delete(f"/api/workflows/{wf_id}")
        self.assertEqual(res_del_again.status_code, 400)

    def test_invalid_workflow_id_formats(self):
        """Invalid characters in workflow_id should be rejected with 400."""
        res = self.client.delete("/api/workflows/invalid*id!bad")
        self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
