#!/usr/bin/env python3
"""
WorkFlowOS Phase 10: Intelligent Automation Test Suite

Validates all 21 mandatory Phase 10 scenarios:
Strategy selection:
1. API available → API selected
2. Integration available → Integration selected
3. API unavailable → Integration selected
4. Browser-only action → Browser selected
5. Unsupported action → Manual

Intelligent selection:
6. Higher-priority strategy with poor history loses to reliable lower-priority strategy
7. Reliable strategy receives higher score
8. Repeated failures reduce score
9. Missing credentials reduce suitability
10. Safety constraints prevent unsafe selection

Learning integration:
11. Phase 9 learning state affects strategy suitability
12. Phase 9 learning formula remains unchanged
13. Phase 10 does not alter Phase 8 confidence/ranking

Fallback:
14. Primary strategy unavailable → valid fallback selected
15. No safe fallback → human intervention

Explainability:
16. Every selected strategy has an explanation
17. Rejected strategies have reasons

Security:
18. Credentials never appear in plan/explanation
19. Approval gate cannot be bypassed
20. Malformed workflow IDs are rejected
21. No raw internal exceptions leak through APIs
"""

import json
import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from backend.main import app
from automation.planner import (
    AutomationStrategyType,
    StrategyScoreBreakdown,
    StrategyCandidate,
    StepPlan,
    AutomationPlan,
    AutomationPlanRequest,
    AutomationPlanResponse,
    StrategyCapabilityRegistry,
    capability_registry,
    StrategyScorer,
    strategy_scorer,
    AutomationPlanner,
    automation_planner,
)
from backend.learning.models import (
    WorkflowLearningState,
    RecommendationStatus,
    FeedbackDecision,
    WorkflowFeedbackRequest,
)
from backend.learning.service import learning_service
from backend.learning.state import (
    compute_learning_score,
    determine_recommendation_status,
    recalculate_learning_state,
)
from discovery.confidence import calculate_pattern_confidence, ConfidenceBreakdown
from discovery.ranking import calculate_ranking_score, RankingBreakdown
from automation.service import automation_service
from automation.engine import automation_engine, AutomationEngine
from automation.models import (
    AutomationExecution,
    AutomationStatus,
    WorkflowDefinition,
    WorkflowStep,
)


class TestPhase10IntelligentAutomation(unittest.IsolatedAsyncioTestCase):
    """Unit and integration tests for Phase 10 Intelligent Automation Planner."""

    def setUp(self):
        self.client = TestClient(app)
        learning_service.reset_cache()

    def tearDown(self):
        learning_service.reset_cache()

    # -----------------------------------------------------------------------
    # 1. API available → API selected
    # -----------------------------------------------------------------------
    async def test_01_api_available_selected(self):
        steps = [
            {
                "id": "step_ping",
                "action": "simulate_ping",
                "application": "mock_service",
                "description": "Simulate API ping",
            }
        ]
        plan = await automation_planner.create_plan(
            workflow_id="wf_test_api_select",
            steps=steps,
        )
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].selected_strategy, AutomationStrategyType.API)
        self.assertGreater(plan.steps[0].score, 0.70)
        self.assertIn("API", plan.steps[0].reason)

    # -----------------------------------------------------------------------
    # 2. Integration available → Integration selected
    # -----------------------------------------------------------------------
    async def test_02_integration_available_selected(self):
        # simulate_mutating_write requires managed integration context (allow_direct_execution=False)
        steps = [
            {
                "id": "step_write",
                "action": "simulate_mutating_write",
                "application": "mock_service",
                "description": "Mutating write via mock service adapter",
            }
        ]
        plan = await automation_planner.create_plan(
            workflow_id="wf_test_int_select",
            steps=steps,
        )
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].selected_strategy, AutomationStrategyType.INTEGRATION)
        self.assertGreater(plan.steps[0].score, 0.60)
        self.assertIn("INTEGRATION", plan.steps[0].reason)

    # -----------------------------------------------------------------------
    # 3. API unavailable → Integration selected
    # -----------------------------------------------------------------------
    async def test_03_api_unavailable_integration_selected(self):
        steps = [
            {
                "id": "step_crm",
                "action": "search_customer",
                "application": "demo_crm",
                "description": "Search CRM for customer record",
            }
        ]
        # Context forces API strategy to be unavailable
        ctx = {"api_available": False, "integration_available": True}
        plan = await automation_planner.create_plan(
            workflow_id="wf_test_api_unavail",
            steps=steps,
            context=ctx,
        )
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].selected_strategy, AutomationStrategyType.INTEGRATION)
        self.assertFalse(plan.steps[0].candidates[0].is_available)  # API candidate unavailable

    # -----------------------------------------------------------------------
    # 4. Browser-only action → Browser selected
    # -----------------------------------------------------------------------
    async def test_04_browser_only_action_selected(self):
        steps = [
            {
                "id": "step_download",
                "action": "download_attachment",
                "application": "demo_email",
                "description": "Download invoice attachment in browser UI",
            }
        ]
        plan = await automation_planner.create_plan(
            workflow_id="wf_test_browser_only",
            steps=steps,
        )
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].selected_strategy, AutomationStrategyType.BROWSER)
        self.assertIn("BROWSER", plan.steps[0].reason)

    # -----------------------------------------------------------------------
    # 5. Unsupported action → Manual
    # -----------------------------------------------------------------------
    async def test_05_unsupported_action_manual(self):
        steps = [
            {
                "id": "step_quantum",
                "action": "quantum_computation_step",
                "application": "unknown_quantum_device",
                "description": "Unsupported exotic operation",
            }
        ]
        plan = await automation_planner.create_plan(
            workflow_id="wf_test_unsupported",
            steps=steps,
        )
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].selected_strategy, AutomationStrategyType.MANUAL)
        self.assertIn("MANUAL", plan.steps[0].reason)

    # -----------------------------------------------------------------------
    # 6. Higher-priority strategy with poor history loses to reliable lower-priority
    # -----------------------------------------------------------------------
    async def test_06_failure_aware_selection_browser_beats_api(self):
        # Action supported by both API and Browser: open_email
        steps = [
            {
                "id": "step_email",
                "action": "open_email",
                "application": "demo_email",
            }
        ]
        # API has failed 8 out of 10 times; Browser has succeeded 9 out of 10 times
        ctx = {
            "history_step_email": {
                "api_successes": 2,
                "api_failures": 8,
                "browser_successes": 9,
                "browser_failures": 1,
            }
        }
        plan = await automation_planner.create_plan(
            workflow_id="wf_test_failure_aware",
            steps=steps,
            context=ctx,
        )
        selected = plan.steps[0].selected_strategy
        # Browser must win despite API having higher nominal priority
        self.assertEqual(selected, AutomationStrategyType.BROWSER)

        # Verify scores: Browser score > API score
        api_cand = next(c for c in plan.steps[0].candidates if c.strategy == AutomationStrategyType.API)
        browser_cand = next(c for c in plan.steps[0].candidates if c.strategy == AutomationStrategyType.BROWSER)
        self.assertGreater(browser_cand.score, api_cand.score)
        self.assertGreater(api_cand.score_breakdown.failure_penalty, 0.25)
        self.assertIn("API", plan.steps[0].rejected_strategies)

    # -----------------------------------------------------------------------
    # 7. Reliable strategy receives higher score
    # -----------------------------------------------------------------------
    async def test_07_reliable_strategy_higher_score(self):
        cand_reliable = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.API,
            is_available=True,
            rejection_reason=None,
            action="mock_echo",
            application="mock_service",
            is_mutating=False,
            requires_credentials=False,
            credentials_available=True,
            history={"successes": 20, "failures": 0},
        )
        cand_unreliable = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.API,
            is_available=True,
            rejection_reason=None,
            action="mock_echo",
            application="mock_service",
            is_mutating=False,
            requires_credentials=False,
            credentials_available=True,
            history={"successes": 2, "failures": 18},
        )
        self.assertGreater(cand_reliable.score, cand_unreliable.score)
        self.assertEqual(cand_reliable.score_breakdown.failure_penalty, 0.0)
        self.assertGreater(cand_unreliable.score_breakdown.failure_penalty, 0.30)

    # -----------------------------------------------------------------------
    # 8. Repeated failures reduce score
    # -----------------------------------------------------------------------
    async def test_08_repeated_failures_reduce_score(self):
        score_0_failures = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.BROWSER,
            is_available=True,
            rejection_reason=None,
            action="search_customer",
            application="demo_crm",
            is_mutating=False,
            requires_credentials=False,
            credentials_available=True,
            history={"browser_successes": 10, "browser_failures": 0},
        ).score

        score_5_failures = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.BROWSER,
            is_available=True,
            rejection_reason=None,
            action="search_customer",
            application="demo_crm",
            is_mutating=False,
            requires_credentials=False,
            credentials_available=True,
            history={"browser_successes": 5, "browser_failures": 5},
        ).score

        self.assertGreater(score_0_failures, score_5_failures)

    # -----------------------------------------------------------------------
    # 9. Missing credentials reduce suitability
    # -----------------------------------------------------------------------
    async def test_09_missing_credentials_reduce_suitability(self):
        cand_with_creds = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.API,
            is_available=True,
            rejection_reason=None,
            action="list_recent_messages",
            application="gmail",
            is_mutating=False,
            requires_credentials=True,
            credentials_available=True,
        )
        cand_missing_creds = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.API,
            is_available=True,
            rejection_reason=None,
            action="list_recent_messages",
            application="gmail",
            is_mutating=False,
            requires_credentials=True,
            credentials_available=False,
        )
        self.assertGreater(cand_with_creds.score, cand_missing_creds.score)
        self.assertGreater(cand_missing_creds.score_breakdown.safety_penalty, 0.20)
        self.assertEqual(cand_missing_creds.score_breakdown.credential_score, 0.0)

    # -----------------------------------------------------------------------
    # 10. Safety constraints prevent unsafe selection
    # -----------------------------------------------------------------------
    async def test_10_safety_constraints_prevent_unsafe_selection(self):
        cand_mutating = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.BROWSER,
            is_available=True,
            rejection_reason=None,
            action="update_customer",
            application="demo_crm",
            is_mutating=True,
            requires_credentials=False,
            credentials_available=True,
        )
        # Mutating action on UI strategy has safety deduction
        self.assertGreater(cand_mutating.score_breakdown.safety_penalty, 0.0)

    # -----------------------------------------------------------------------
    # 11. Phase 9 learning state affects strategy suitability
    # -----------------------------------------------------------------------
    async def test_11_phase9_learning_state_affects_suitability(self):
        state_recommended = WorkflowLearningState(
            workflow_id="wf_rec",
            learning_score=0.92,
            recommendation_status=RecommendationStatus.RECOMMENDED,
            execution_count=10,
            successful_execution_count=10,
        )
        state_deprioritized = WorkflowLearningState(
            workflow_id="wf_dep",
            learning_score=0.20,
            recommendation_status=RecommendationStatus.DEPRIORITIZED,
            execution_count=5,
            failed_execution_count=4,
        )

        cand_rec = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.INTEGRATION,
            is_available=True,
            rejection_reason=None,
            action="mock_echo",
            application="mock_service",
            is_mutating=False,
            requires_credentials=False,
            credentials_available=True,
            learning_state=state_recommended,
        )
        cand_dep = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.INTEGRATION,
            is_available=True,
            rejection_reason=None,
            action="mock_echo",
            application="mock_service",
            is_mutating=False,
            requires_credentials=False,
            credentials_available=True,
            learning_state=state_deprioritized,
        )

        self.assertGreater(cand_rec.score, cand_dep.score)
        self.assertGreater(cand_rec.score_breakdown.learning_score, cand_dep.score_breakdown.learning_score)

    # -----------------------------------------------------------------------
    # 12. Phase 9 learning formula remains unchanged
    # -----------------------------------------------------------------------
    async def test_12_phase9_learning_formula_unchanged(self):
        # Baseline check on Phase 9 recalculate_learning_state
        state = WorkflowLearningState(
            workflow_id="wf_p9_check",
            approval_count=3,
            rejection_count=0,
            successful_execution_count=4,
            failed_execution_count=0,
        )
        recalculated = recalculate_learning_state(state)
        # Expected bounded score using Phase 9 formula
        expected_score = compute_learning_score(
            approval_count=3,
            rejection_count=0,
            edit_count=0,
            successful_execution_count=4,
            failed_execution_count=0,
            intervention_count=0,
            recovery_count=0,
        )
        self.assertEqual(recalculated.learning_score, expected_score)
        self.assertEqual(recalculated.recommendation_status, RecommendationStatus.RECOMMENDED)

    # -----------------------------------------------------------------------
    # 13. Phase 10 does not alter Phase 8 confidence/ranking
    # -----------------------------------------------------------------------
    async def test_13_phase8_confidence_and_ranking_unaffected(self):
        seq = ["open_email", "download_attachment", "search_customer"]
        conf_score, conf_breakdown, tier, explanation = calculate_pattern_confidence(
            sequence=seq,
            occurrences=3,
            avg_similarity=0.90,
        )
        self.assertIsInstance(conf_breakdown, ConfidenceBreakdown)
        self.assertGreater(conf_score, 0.70)

        rank_score, rank_breakdown, rank_tier, rank_exp = calculate_ranking_score(
            sequence=seq,
            occurrences=3,
            avg_similarity=0.90,
            confidence=conf_score,
            session_consistency=1.0,
        )
        self.assertIsInstance(rank_breakdown, RankingBreakdown)
        self.assertGreater(rank_score, 0.50)

    # -----------------------------------------------------------------------
    # 14. Primary strategy unavailable → valid fallback selected
    # -----------------------------------------------------------------------
    async def test_14_fallback_strategy_selected(self):
        steps = [
            {
                "id": "step_search",
                "action": "search_customer",
                "application": "demo_crm",
            }
        ]
        plan = await automation_planner.create_plan(
            workflow_id="wf_test_fallback",
            steps=steps,
        )
        step = plan.steps[0]
        # Primary is INTEGRATION, fallback is BROWSER or vice versa
        self.assertIsNotNone(step.fallback_strategy)
        self.assertNotEqual(step.selected_strategy, step.fallback_strategy)
        self.assertTrue(plan.fallback_available)
        self.assertIsNotNone(step.fallback_reason)

    # -----------------------------------------------------------------------
    # 15. No safe fallback → human intervention
    # -----------------------------------------------------------------------
    async def test_15_no_safe_fallback_human_intervention(self):
        steps = [
            {
                "id": "step_exotic",
                "action": "unknown_manual_verification",
                "application": "external_paperwork",
            }
        ]
        plan = await automation_planner.create_plan(
            workflow_id="wf_test_manual_only",
            steps=steps,
        )
        step = plan.steps[0]
        self.assertEqual(step.selected_strategy, AutomationStrategyType.MANUAL)
        self.assertIsNone(step.fallback_strategy)
        self.assertTrue(plan.requires_approval)

    # -----------------------------------------------------------------------
    # 16. Every selected strategy has an explanation
    # -----------------------------------------------------------------------
    async def test_16_selected_strategy_has_explanation(self):
        plan = await automation_planner.create_plan("wf_customer_support_pipeline")
        for step in plan.steps:
            self.assertTrue(bool(step.reason))
            self.assertGreater(len(step.selected_reasons), 0)
        self.assertTrue(bool(plan.explanation.get("summary")))
        self.assertTrue(bool(plan.explanation.get("key_factors")))

    # -----------------------------------------------------------------------
    # 17. Rejected strategies have reasons
    # -----------------------------------------------------------------------
    async def test_17_rejected_strategies_have_reasons(self):
        plan = await automation_planner.create_plan("wf_customer_support_pipeline")
        for step in plan.steps:
            self.assertGreater(len(step.rejected_strategies), 0)
            for rejected_strat, reason in step.rejected_strategies.items():
                self.assertTrue(bool(reason))

    # -----------------------------------------------------------------------
    # 18. Credentials never appear in plan/explanation
    # -----------------------------------------------------------------------
    async def test_18_credentials_never_exposed_in_plan(self):
        secret_token = "ghp_VERY_SECRET_AUTH_TOKEN_9999"
        secret_password = "SuperSecretPassword123!"
        context_with_secrets = {
            "token": secret_token,
            "password": secret_password,
            "credentials_available": True,
        }
        steps = [
            {
                "id": "step_1",
                "action": "simulate_ping",
                "application": "mock_service",
                "parameters": {"secret": secret_password},
            }
        ]
        plan = await automation_planner.create_plan(
            workflow_id="wf_test_secret_leak",
            steps=steps,
            context=context_with_secrets,
        )
        serialized_plan = plan.model_dump_json()
        self.assertNotIn(secret_token, serialized_plan)
        self.assertNotIn(secret_password, serialized_plan)
        # Check reasons
        for step in plan.steps:
            for reason in step.selected_reasons:
                self.assertNotIn(secret_token, reason)
                self.assertNotIn(secret_password, reason)

    # -----------------------------------------------------------------------
    # 19. Approval gate cannot be bypassed
    # -----------------------------------------------------------------------
    async def test_19_approval_gate_cannot_be_bypassed(self):
        plan = await automation_planner.create_plan("wf_customer_support_pipeline")
        # Invariant 1: plan always specifies requires_approval=True
        self.assertTrue(plan.requires_approval)

        # Invariant 2: executing without approved=True in automation_engine returns PENDING
        from ai.models import WorkflowProposal, WorkflowAction, WorkflowTrigger
        proposal = WorkflowProposal(
            name="Test Support",
            intent="Support",
            description="Testing safety gate",
            trigger=WorkflowTrigger(
                type="manual",
                application="demo_email",
                description="Manual trigger for testing safety gate",
            ),
            actions=[
                WorkflowAction(
                    type="open_email",
                    application="demo_email",
                    description="Open email",
                    target="inbox",
                )
            ],
            variables=[],
            applications=["demo_email"],
            requires_approval=True,
        )
        exec_result = await automation_engine.execute_workflow(
            proposal=proposal,
            approved=False,  # Unapproved
        )
        self.assertEqual(exec_result.status, AutomationStatus.PENDING)

    # -----------------------------------------------------------------------
    # 20. Malformed workflow IDs are rejected
    # -----------------------------------------------------------------------
    def test_20_malformed_workflow_ids_rejected(self):
        # 1. Path traversal
        res = self.client.post("/api/workflows/..%2F..%2Fetc/automation-plan")
        self.assertIn(res.status_code, [400, 404])

        # 2. Spaces / invalid characters
        res = self.client.post("/api/workflows/invalid%20id%20with%20spaces/automation-plan")
        self.assertEqual(res.status_code, 400)
        self.assertIn("invalid characters", res.json().get("detail", ""))

        # 3. String exceeding 128 characters
        long_id = "a" * 129
        res = self.client.post(f"/api/workflows/{long_id}/automation-plan")
        self.assertEqual(res.status_code, 400)
        self.assertIn("must not exceed 128 characters", res.json().get("detail", ""))

    # -----------------------------------------------------------------------
    # 21. No raw internal exceptions leak through APIs
    # -----------------------------------------------------------------------
    def test_21_no_raw_internal_exceptions_leak(self):
        # Simulate an unexpected internal crash inside planner.create_plan
        with patch.object(
            automation_planner,
            "create_plan",
            side_effect=RuntimeError("CRITICAL_INTERNAL_DB_CRASH_SECRET_TRACEBACK")
        ):
            res = self.client.post("/api/workflows/wf_customer_support_pipeline/automation-plan")
            self.assertEqual(res.status_code, 500)
            detail = res.json().get("detail", "")
            # Detail must be sanitized and opaque
            self.assertEqual(detail, "Failed to generate automation plan. Please try again.")
            self.assertNotIn("CRITICAL_INTERNAL_DB_CRASH", detail)
            self.assertNotIn("Traceback", detail)


if __name__ == "__main__":
    unittest.main()
