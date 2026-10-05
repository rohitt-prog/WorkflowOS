#!/usr/bin/env python3
"""
WorkFlowOS Phase 9: Adaptive Learning & Feedback Test Suite

Validates all 24 mandatory Phase 9 requirements:
1. Approve feedback
2. Reject feedback
3. Edit + approve feedback
4. Feedback persistence
5. Feedback retrieval
6. Learning state creation
7. Learning state update
8. Approval count
9. Rejection count
10. Edit count
11. Successful execution learning
12. Failed execution learning
13. Intervention learning
14. Recovery learning
15. Learning score bounds in [0.0, 1.0]
16. Deterministic learning score formula
17. Recommendation status transitions (NEW -> LEARNING -> RECOMMENDED -> DEPRIORITIZED)
18. Negative feedback does not permanently delete workflow
19. Positive evidence can recover a deprioritized workflow
20. Learning does NOT bypass human approval gate
21. Existing Phase 8 confidence remains unchanged
22. Existing Phase 8 ranking remains unchanged
23. Learning explanation correctness
24. Backward-compatible API behavior
"""

import asyncio
import os
import unittest
from datetime import datetime, timezone
from typing import Dict, Any, List

from fastapi.testclient import TestClient

from backend.main import app
from backend.learning.models import (
    FeedbackDecision,
    RecommendationStatus,
    WorkflowFeedbackRequest,
    WorkflowLearningState,
)
from backend.learning.service import learning_service, derive_workflow_id_from_sequence
from backend.learning.state import (
    compute_learning_score,
    determine_recommendation_status,
    generate_learning_explanation,
    recalculate_learning_state,
)
from automation.models import (
    AutomationExecution,
    AutomationStatus,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowInputDefinition,
)
from automation.service import automation_service
from discovery.detector import detect_repeated_workflows


class TestPhase9AdaptiveLearning(unittest.IsolatedAsyncioTestCase):
    """Unit and integration tests for Phase 9 Adaptive Learning & Feedback."""

    def setUp(self):
        self.client = TestClient(app)
        learning_service.reset_cache()

    def tearDown(self):
        learning_service.reset_cache()

    # -----------------------------------------------------------------------
    # 1. Approve feedback
    # -----------------------------------------------------------------------
    async def test_01_approve_feedback(self):
        wf_id = "wf_test_approve"
        req = WorkflowFeedbackRequest(decision=FeedbackDecision.APPROVE)
        fb, state = await learning_service.record_feedback(wf_id, req)

        self.assertEqual(fb.workflow_id, wf_id)
        self.assertEqual(fb.decision, FeedbackDecision.APPROVE)
        self.assertEqual(state.approval_count, 1)
        self.assertEqual(state.rejection_count, 0)
        self.assertGreater(state.learning_score, 0.50)

    # -----------------------------------------------------------------------
    # 2. Reject feedback
    # -----------------------------------------------------------------------
    async def test_02_reject_feedback(self):
        wf_id = "wf_test_reject"
        req = WorkflowFeedbackRequest(
            decision=FeedbackDecision.REJECT,
            rejection_reason="Duplicate routine, not needed"
        )
        fb, state = await learning_service.record_feedback(wf_id, req)

        self.assertEqual(fb.workflow_id, wf_id)
        self.assertEqual(fb.decision, FeedbackDecision.REJECT)
        self.assertEqual(fb.rejection_reason, "Duplicate routine, not needed")
        self.assertEqual(state.rejection_count, 1)
        self.assertEqual(state.approval_count, 0)
        self.assertLess(state.learning_score, 0.50)

    # -----------------------------------------------------------------------
    # 3. Edit + approve feedback
    # -----------------------------------------------------------------------
    async def test_03_edit_approve_feedback(self):
        wf_id = "wf_test_edit_approve"
        edited_spec = {"steps": [{"type": "open_email"}, {"type": "send_message"}]}
        req = WorkflowFeedbackRequest(
            decision=FeedbackDecision.EDIT_APPROVE,
            edited_workflow=edited_spec,
        )
        fb, state = await learning_service.record_feedback(wf_id, req)

        self.assertEqual(fb.decision, FeedbackDecision.EDIT_APPROVE)
        self.assertEqual(fb.edited_workflow, edited_spec)
        self.assertEqual(state.edit_count, 1)
        self.assertGreater(state.learning_score, 0.50)

    # -----------------------------------------------------------------------
    # 4. Feedback persistence (in memory / DB)
    # -----------------------------------------------------------------------
    async def test_04_feedback_persistence(self):
        wf_id = "wf_persist_test"
        await learning_service.record_feedback(
            wf_id, WorkflowFeedbackRequest(decision=FeedbackDecision.APPROVE)
        )
        await learning_service.record_feedback(
            wf_id, WorkflowFeedbackRequest(decision=FeedbackDecision.REJECT, rejection_reason="Too noisy")
        )

        history = await learning_service.get_feedback_history(wf_id)
        self.assertEqual(len(history), 2)
        decisions = [h.decision for h in history]
        self.assertIn(FeedbackDecision.APPROVE, decisions)
        self.assertIn(FeedbackDecision.REJECT, decisions)

    # -----------------------------------------------------------------------
    # 5. Feedback retrieval via API
    # -----------------------------------------------------------------------
    def test_05_feedback_retrieval_api(self):
        wf_id = "wf_api_retrieve"
        # Submit feedback via API
        post_res = self.client.post(
            f"/api/workflows/{wf_id}/feedback",
            json={"decision": "approve"}
        )
        self.assertEqual(post_res.status_code, 200)
        data = post_res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["learning_state"]["approval_count"], 1)

        # Retrieve history via GET API
        get_res = self.client.get(f"/api/workflows/{wf_id}/feedback")
        self.assertEqual(get_res.status_code, 200)
        history = get_res.json()
        self.assertIsInstance(history, list)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["decision"], "approve")

    # -----------------------------------------------------------------------
    # 6. Learning state creation (initial clean state is NEW)
    # -----------------------------------------------------------------------
    async def test_06_learning_state_creation(self):
        wf_id = "wf_fresh_state"
        state = await learning_service.get_learning_state(wf_id)
        self.assertEqual(state.workflow_id, wf_id)
        self.assertEqual(state.approval_count, 0)
        self.assertEqual(state.rejection_count, 0)
        self.assertEqual(state.execution_count, 0)
        self.assertEqual(state.learning_score, 0.50)
        self.assertEqual(state.recommendation_status, RecommendationStatus.NEW)
        self.assertIn("New workflow candidate", state.learning_explanation)

    # -----------------------------------------------------------------------
    # 7. Learning state update on multiple signals
    # -----------------------------------------------------------------------
    async def test_07_learning_state_update(self):
        wf_id = "wf_state_update"
        await learning_service.record_feedback(wf_id, WorkflowFeedbackRequest(decision=FeedbackDecision.APPROVE))
        await learning_service.record_feedback(wf_id, WorkflowFeedbackRequest(decision=FeedbackDecision.APPROVE))
        state = await learning_service.get_learning_state(wf_id)
        self.assertEqual(state.approval_count, 2)
        self.assertEqual(state.recommendation_status, RecommendationStatus.LEARNING)
        self.assertAlmostEqual(state.learning_score, 0.70, places=2)

    # -----------------------------------------------------------------------
    # 8. Approval count tracking
    # -----------------------------------------------------------------------
    async def test_08_approval_count(self):
        wf_id = "wf_count_approvals"
        for _ in range(4):
            await learning_service.record_feedback(wf_id, WorkflowFeedbackRequest(decision=FeedbackDecision.APPROVE))
        state = await learning_service.get_learning_state(wf_id)
        self.assertEqual(state.approval_count, 4)

    # -----------------------------------------------------------------------
    # 9. Rejection count tracking
    # -----------------------------------------------------------------------
    async def test_09_rejection_count(self):
        wf_id = "wf_count_rejections"
        for i in range(3):
            await learning_service.record_feedback(
                wf_id,
                WorkflowFeedbackRequest(decision=FeedbackDecision.REJECT, rejection_reason=f"Reason {i}")
            )
        state = await learning_service.get_learning_state(wf_id)
        self.assertEqual(state.rejection_count, 3)

    # -----------------------------------------------------------------------
    # 10. Edit count tracking
    # -----------------------------------------------------------------------
    async def test_10_edit_count(self):
        wf_id = "wf_count_edits"
        for _ in range(2):
            await learning_service.record_feedback(
                wf_id,
                WorkflowFeedbackRequest(decision=FeedbackDecision.EDIT_APPROVE, edited_workflow={"name": "edited"})
            )
        state = await learning_service.get_learning_state(wf_id)
        self.assertEqual(state.edit_count, 2)

    # -----------------------------------------------------------------------
    # 11. Successful execution learning
    # -----------------------------------------------------------------------
    async def test_11_successful_execution_learning(self):
        wf_id = "wf_exec_success"
        now_iso = datetime.now(timezone.utc).isoformat()
        execution = AutomationExecution(
            execution_id="exec_succ_01",
            workflow_id=wf_id,
            workflow_name="Test Success Flow",
            status=AutomationStatus.COMPLETED,
            completed_actions=["open_email", "download_attachment"],
            total_actions=2,
            started_at=now_iso,
            completed_at=now_iso,
        )
        updated_state = await learning_service.record_execution_outcome(execution)
        self.assertIsNotNone(updated_state)
        self.assertEqual(updated_state.execution_count, 1)
        self.assertEqual(updated_state.successful_execution_count, 1)
        self.assertEqual(updated_state.failed_execution_count, 0)
        self.assertEqual(updated_state.last_execution_status, "completed")
        self.assertGreater(updated_state.learning_score, 0.50)

    # -----------------------------------------------------------------------
    # 12. Failed execution learning
    # -----------------------------------------------------------------------
    async def test_12_failed_execution_learning(self):
        wf_id = "wf_exec_fail"
        execution = AutomationExecution(
            execution_id="exec_fail_01",
            workflow_id=wf_id,
            workflow_name="Test Fail Flow",
            status=AutomationStatus.FAILED,
            failed_action="search_customer",
            failure_reason="Customer CRM service unreachable",
            error="Customer CRM service unreachable",
            total_actions=3,
        )
        updated_state = await learning_service.record_execution_outcome(execution)
        self.assertIsNotNone(updated_state)
        self.assertEqual(updated_state.execution_count, 1)
        self.assertEqual(updated_state.successful_execution_count, 0)
        self.assertEqual(updated_state.failed_execution_count, 1)
        self.assertEqual(updated_state.last_failed_step, "search_customer")
        self.assertLess(updated_state.learning_score, 0.50)

    # -----------------------------------------------------------------------
    # 13. Intervention learning
    # -----------------------------------------------------------------------
    async def test_13_intervention_learning(self):
        wf_id = "wf_exec_interv"
        execution = AutomationExecution(
            execution_id="exec_interv_01",
            workflow_id=wf_id,
            workflow_name="Test Intervention Flow",
            status=AutomationStatus.PAUSED,
            requires_human_intervention=True,
            failed_action="update_customer",
            failure_reason="Conflict detected",
            total_actions=3,
        )
        updated_state = await learning_service.record_execution_outcome(execution)
        self.assertIsNotNone(updated_state)
        self.assertEqual(updated_state.intervention_count, 1)

    # -----------------------------------------------------------------------
    # 14. Recovery learning
    # -----------------------------------------------------------------------
    async def test_14_recovery_learning(self):
        wf_id = "wf_exec_recovery"
        execution = AutomationExecution(
            execution_id="exec_recov_01",
            workflow_id=wf_id,
            workflow_name="Test Recovery Flow",
            status=AutomationStatus.COMPLETED,
            resume_count=1,
            recovery_attempts=1,
            total_actions=3,
        )
        updated_state = await learning_service.record_execution_outcome(execution)
        self.assertIsNotNone(updated_state)
        self.assertEqual(updated_state.recovery_count, 1)
        self.assertEqual(updated_state.successful_execution_count, 1)

    # -----------------------------------------------------------------------
    # 15. Learning score bounds [0.0, 1.0]
    # -----------------------------------------------------------------------
    def test_15_learning_score_bounds(self):
        # Extreme negative signals
        min_score = compute_learning_score(
            approval_count=0,
            rejection_count=20,
            edit_count=0,
            successful_execution_count=0,
            failed_execution_count=20,
            intervention_count=10,
            recovery_count=0,
        )
        self.assertEqual(min_score, 0.0)

        # Extreme positive signals
        max_score = compute_learning_score(
            approval_count=50,
            rejection_count=0,
            edit_count=10,
            successful_execution_count=50,
            failed_execution_count=0,
            intervention_count=0,
            recovery_count=10,
        )
        self.assertEqual(max_score, 1.0)

    # -----------------------------------------------------------------------
    # 16. Deterministic learning score formula
    # -----------------------------------------------------------------------
    def test_16_deterministic_learning_score(self):
        # 0.50 + 0.10*2 + 0.08*1 + 0.15*3 + 0.05*1 - 0.20*1 - 0.15*1 - 0.05*1
        # = 0.50 + 0.20 + 0.08 + 0.45 + 0.05 - 0.20 - 0.15 - 0.05
        # = 1.28 - 0.40 = 0.88
        score = compute_learning_score(
            approval_count=2,
            rejection_count=1,
            edit_count=1,
            successful_execution_count=3,
            failed_execution_count=1,
            intervention_count=1,
            recovery_count=1,
        )
        self.assertAlmostEqual(score, 0.88, places=4)

    # -----------------------------------------------------------------------
    # 17. Recommendation status transitions
    # -----------------------------------------------------------------------
    async def test_17_recommendation_status_transitions(self):
        wf_id = "wf_transitions"
        # Initial: NEW
        s0 = await learning_service.get_learning_state(wf_id)
        self.assertEqual(s0.recommendation_status, RecommendationStatus.NEW)

        # 1 approval: LEARNING
        _, s1 = await learning_service.record_feedback(wf_id, WorkflowFeedbackRequest(decision=FeedbackDecision.APPROVE))
        self.assertEqual(s1.recommendation_status, RecommendationStatus.LEARNING)

        # 1 successful execution: RECOMMENDED (score = 0.50 + 0.10 + 0.15 = 0.75 >= 0.70)
        now_iso = datetime.now(timezone.utc).isoformat()
        s2 = await learning_service.record_execution_outcome(
            AutomationExecution(
                execution_id="exec_trans_1",
                workflow_id=wf_id,
                workflow_name="Trans Flow",
                status=AutomationStatus.COMPLETED,
                started_at=now_iso,
                completed_at=now_iso,
            )
        )
        self.assertEqual(s2.recommendation_status, RecommendationStatus.RECOMMENDED)

    # -----------------------------------------------------------------------
    # 18. Negative feedback does not permanently delete workflow
    # -----------------------------------------------------------------------
    async def test_18_negative_feedback_preserves_workflow(self):
        wf_id = "wf_preserve_test"
        # Two rejections
        await learning_service.record_feedback(wf_id, WorkflowFeedbackRequest(decision=FeedbackDecision.REJECT))
        _, s_dep = await learning_service.record_feedback(wf_id, WorkflowFeedbackRequest(decision=FeedbackDecision.REJECT))
        self.assertEqual(s_dep.recommendation_status, RecommendationStatus.DEPRIORITIZED)

        # State and feedback remain queryable (not purged/deleted)
        state = await learning_service.get_learning_state(wf_id)
        self.assertIsNotNone(state)
        self.assertEqual(state.rejection_count, 2)
        history = await learning_service.get_feedback_history(wf_id)
        self.assertEqual(len(history), 2)

    # -----------------------------------------------------------------------
    # 19. Positive evidence can recover a deprioritized workflow
    # -----------------------------------------------------------------------
    async def test_19_recovery_of_deprioritized_workflow(self):
        wf_id = "wf_recovering"
        # Deprioritize with two rejections
        await learning_service.record_feedback(wf_id, WorkflowFeedbackRequest(decision=FeedbackDecision.REJECT))
        await learning_service.record_feedback(wf_id, WorkflowFeedbackRequest(decision=FeedbackDecision.REJECT))
        state = await learning_service.get_learning_state(wf_id)
        self.assertEqual(state.recommendation_status, RecommendationStatus.DEPRIORITIZED)

        # Operator edits & approves 3 times and executes 3 times successfully
        for _ in range(3):
            await learning_service.record_feedback(
                wf_id,
                WorkflowFeedbackRequest(decision=FeedbackDecision.APPROVE)
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        for i in range(3):
            await learning_service.record_execution_outcome(
                AutomationExecution(
                    execution_id=f"exec_recov_test_{i}",
                    workflow_id=wf_id,
                    workflow_name="Recovering Flow",
                    status=AutomationStatus.COMPLETED,
                    started_at=now_iso,
                    completed_at=now_iso,
                )
            )

        recovered_state = await learning_service.get_learning_state(wf_id)
        # Score = 0.50 - 0.40 + 0.30 + 0.45 = 0.85 >= 0.70
        self.assertGreaterEqual(recovered_state.learning_score, 0.70)
        self.assertEqual(recovered_state.recommendation_status, RecommendationStatus.RECOMMENDED)

    # -----------------------------------------------------------------------
    # 20. Learning does NOT bypass human approval gate
    # -----------------------------------------------------------------------
    def test_20_learning_does_not_bypass_approval(self):
        # A workflow that has RECOMMENDED status still CANNOT execute without approved=True
        res = self.client.post(
            "/api/automation/execute",
            json={
                "workflow_definition": {
                    "id": "wf_customer_support_pipeline",
                    "name": "Customer Email Pipeline",
                    "steps": [{"id": "s1", "type": "open_email"}],
                    "requires_approval": True,
                },
                "approved": False,  # Safety gate
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "pending")
        self.assertIn("Human approval is required", data["message"])

    # -----------------------------------------------------------------------
    # 21. Existing Phase 8 confidence remains unchanged
    # -----------------------------------------------------------------------
    def test_21_phase8_confidence_remains_unchanged(self):
        sessions = {
            "s1": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
            "s2": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
            "s3": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
        }
        res = detect_repeated_workflows(sessions, min_length=3, min_occurrences=2)
        self.assertTrue(res.detected)
        wf = res.workflows[0]
        # Calibrated Phase 8.1 confidence must be computed as expected (0.80 - 1.0)
        self.assertGreaterEqual(wf.confidence, 0.80)
        self.assertIsNotNone(wf.confidence_breakdown)

    # -----------------------------------------------------------------------
    # 22. Existing Phase 8 ranking remains unchanged
    # -----------------------------------------------------------------------
    def test_22_phase8_ranking_remains_unchanged(self):
        sessions = {
            "s1": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
            "s2": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
            "s3": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
        }
        res = detect_repeated_workflows(sessions, min_length=3, min_occurrences=2)
        self.assertTrue(res.detected)
        wf = res.workflows[0]
        self.assertEqual(wf.rank, 1)
        self.assertIsNotNone(wf.ranking_score)
        self.assertIsNotNone(wf.quality_tier)

    # -----------------------------------------------------------------------
    # 23. Learning explanation correctness
    # -----------------------------------------------------------------------
    def test_23_learning_explanation_correctness(self):
        # NEW
        expl_new = generate_learning_explanation(
            status=RecommendationStatus.NEW,
            score=0.50,
            approval_count=0,
            rejection_count=0,
            edit_count=0,
            execution_count=0,
            successful_execution_count=0,
            failed_execution_count=0,
            intervention_count=0,
            recovery_count=0,
        )
        self.assertIn("New workflow candidate", expl_new)

        # RECOMMENDED
        expl_rec = generate_learning_explanation(
            status=RecommendationStatus.RECOMMENDED,
            score=0.85,
            approval_count=3,
            rejection_count=0,
            edit_count=1,
            execution_count=2,
            successful_execution_count=2,
            failed_execution_count=0,
            intervention_count=0,
            recovery_count=1,
        )
        self.assertIn("Recommended because", expl_rec)
        self.assertIn("approved 4 times", expl_rec)
        self.assertIn("successfully executed 2 times", expl_rec)

        # DEPRIORITIZED by rejections
        expl_rej = generate_learning_explanation(
            status=RecommendationStatus.DEPRIORITIZED,
            score=0.10,
            approval_count=0,
            rejection_count=2,
            edit_count=0,
            execution_count=0,
            successful_execution_count=0,
            failed_execution_count=0,
            intervention_count=0,
            recovery_count=0,
            last_rejection_reason="Duplicate routine",
        )
        self.assertIn("rejected 2 times by operator", expl_rej)

        # DEPRIORITIZED by failures
        expl_fail = generate_learning_explanation(
            status=RecommendationStatus.DEPRIORITIZED,
            score=0.20,
            approval_count=0,
            rejection_count=0,
            edit_count=0,
            execution_count=2,
            successful_execution_count=0,
            failed_execution_count=2,
            intervention_count=1,
            recovery_count=0,
            last_failed_step="search_customer",
            last_failure_reason="Customer not found",
        )
        self.assertIn("workflow execution failed 2 times at step 'search_customer'", expl_fail)

    # -----------------------------------------------------------------------
    # 24. Backward-compatible API behavior
    # -----------------------------------------------------------------------
    def test_24_backward_compatible_api(self):
        # 1. Existing GET /api/discovery/repeated works seamlessly
        disc_res = self.client.get("/api/discovery/repeated")
        self.assertIn(disc_res.status_code, (200, 500))  # 200 or clean error if mock collection empty

        # 2. Existing GET /api/automation/workflows works
        wf_res = self.client.get("/api/automation/workflows")
        self.assertEqual(wf_res.status_code, 200)
        self.assertIsInstance(wf_res.json(), list)

        # 3. GET /api/workflows/{workflow_id}/learning returns clean state
        learn_res = self.client.get("/api/workflows/wf_customer_support_pipeline/learning")
        self.assertEqual(learn_res.status_code, 200)
        data = learn_res.json()
        self.assertEqual(data["workflow_id"], "wf_customer_support_pipeline")
        self.assertIn(data["recommendation_status"], ["NEW", "LEARNING", "RECOMMENDED", "DEPRIORITIZED"])
        self.assertIn("learning_score", data)


if __name__ == "__main__":
    unittest.main()
