#!/usr/bin/env python3
"""
WorkFlowOS Phase 11: Closed-Loop Intelligence Test Suite

Validates all 22 mandatory Phase 11 scenarios:
1. successful execution produces positive evidence
2. failed execution produces negative evidence
3. cancelled execution is not treated as failure
4. paused execution is not treated as failure
5. partial execution is handled correctly
6. failed step is identified
7. evidence is associated with workflow + step + strategy
8. success rate is calculated correctly
9. recent outcomes influence evidence
10. repeated failures reduce suitability
11. repeated successes improve suitability
12. fallback success produces positive evidence
13. fallback failure produces negative evidence
14. Phase 10 planner consumes outcome evidence
15. safety still dominates strategy selection
16. missing credentials remain unsafe/unavailable
17. credentials/secrets never appear in outcome records
18. outcome explanations are deterministic
19. Phase 9 learning state remains backward compatible
20. Phase 10 behavior remains backward compatible
21. API validation/security behavior
22. closed-loop summary is correct
"""

import json
import unittest
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from backend.learning.outcome import (
    FailureCategory,
    ExecutionOutcomeStatus,
    StepOutcome,
    WorkflowExecutionOutcome,
    categorize_failure,
    evaluate_execution_outcome,
)
from backend.learning.evidence import (
    StrategyOutcomeEvidence,
    ClosedLoopSummary,
    update_strategy_evidence,
    synthesize_closed_loop_summary,
)
from backend.learning.service import learning_service
from backend.learning.models import RecommendationStatus
from automation.models import (
    AutomationExecution,
    AutomationStatus,
    ExecutionActionResult,
    StepExecutionResult,
)
from automation.planner import (
    AutomationStrategyType,
    automation_planner,
    strategy_scorer,
    capability_registry,
)
from automation.service import automation_service


def make_execution(
    workflow_id="wf_test",
    workflow_name="Test Workflow",
    status=AutomationStatus.COMPLETED,
    total_actions=1,
    completed_actions=None,
    failed_action=None,
    error=None,
    results=None,
    step_results=None,
    context=None,
    execution_id=None,
    actions_detail=None,
):
    """Deterministic factory for AutomationExecution instances in tests."""
    return AutomationExecution(
        execution_id=execution_id or f"exec_{uuid.uuid4().hex[:8]}",
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        status=status,
        total_actions=total_actions,
        completed_actions=completed_actions or [],
        failed_action=failed_action,
        error=error,
        results=results or [],
        step_results=step_results or [],
        context=context or {},
        actions_detail=actions_detail or [],
    )


class TestPhase11ClosedLoopIntelligence(unittest.IsolatedAsyncioTestCase):
    """Deterministic, offline test suite for Phase 11 Closed-Loop Intelligence."""

    def setUp(self):
        self.client = TestClient(app)
        learning_service.reset_cache()

    def tearDown(self):
        learning_service.reset_cache()

    # -----------------------------------------------------------------------
    # 1. Successful execution produces positive evidence
    # -----------------------------------------------------------------------
    async def test_01_successful_execution_produces_positive_evidence(self):
        execution = make_execution(
            workflow_id="wf_customer_support_pipeline",
            workflow_name="Customer Email & Support Pipeline",
            status=AutomationStatus.COMPLETED,
            total_actions=1,
            completed_actions=["open_email"],
            results=[
                ExecutionActionResult(
                    action_id="step_1",
                    action_type="open_email",
                    success=True,
                    message="Opened email successfully",
                )
            ],
            step_results=[
                StepExecutionResult(
                    step_id="step_1",
                    action_type="open_email",
                    application="demo_email",
                    status="completed",
                    duration_seconds=0.45,
                )
            ],
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.status, ExecutionOutcomeStatus.SUCCESS)

        evidence_list = await learning_service.get_strategy_evidence(
            workflow_id="wf_customer_support_pipeline",
            step_action="open_email",
        )
        self.assertEqual(len(evidence_list), 1)
        ev = evidence_list[0]
        self.assertEqual(ev.attempts, 1)
        self.assertEqual(ev.successes, 1)
        self.assertEqual(ev.failures, 0)
        self.assertEqual(ev.success_rate, 1.0)
        self.assertEqual(ev.last_outcome, "SUCCESS")
        self.assertEqual(ev.recent_successes, 1)
        self.assertEqual(ev.recent_failures, 0)

    # -----------------------------------------------------------------------
    # 2. Failed execution produces negative evidence
    # -----------------------------------------------------------------------
    async def test_02_failed_execution_produces_negative_evidence(self):
        execution = make_execution(
            workflow_id="wf_customer_support_pipeline",
            workflow_name="Customer Email & Support Pipeline",
            status=AutomationStatus.FAILED,
            total_actions=1,
            failed_action="update_customer",
            error="integration timeout communicating with CRM",
            step_results=[
                StepExecutionResult(
                    step_id="step_1",
                    action_type="update_customer",
                    application="demo_crm",
                    status="failed",
                    error="integration timeout communicating with CRM",
                    duration_seconds=10.0,
                )
            ],
            context={"step_strategies": {"update_customer": "INTEGRATION"}},
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.status, ExecutionOutcomeStatus.FAILED)
        self.assertEqual(outcome.failure_category, FailureCategory.TIMEOUT)

        evidence_list = await learning_service.get_strategy_evidence(
            workflow_id="wf_customer_support_pipeline",
            step_action="update_customer",
            strategy="INTEGRATION",
        )
        self.assertEqual(len(evidence_list), 1)
        ev = evidence_list[0]
        self.assertEqual(ev.attempts, 1)
        self.assertEqual(ev.successes, 0)
        self.assertEqual(ev.failures, 1)
        self.assertEqual(ev.success_rate, 0.0)
        self.assertEqual(ev.last_outcome, "FAILED")
        self.assertEqual(ev.last_failure_category, FailureCategory.TIMEOUT.value)
        self.assertEqual(ev.recent_failures, 1)

    # -----------------------------------------------------------------------
    # 3. Cancelled execution is not treated as technical failure
    # -----------------------------------------------------------------------
    async def test_03_cancelled_execution_not_treated_as_failure(self):
        execution = make_execution(
            workflow_id="wf_user_cancelled_test",
            workflow_name="User Cancelled Test",
            status=AutomationStatus.CANCELLED,
            total_actions=2,
            completed_actions=["open_email"],
            results=[
                ExecutionActionResult(
                    action_id="step_1",
                    action_type="open_email",
                    success=True,
                    message="Action completed prior to cancellation",
                )
            ],
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.status, ExecutionOutcomeStatus.CANCELLED)

        # Verified that cancelled does not penalize strategy as failure
        step_outcome = StepOutcome(
            step_id="step_1",
            action="open_email",
            application="demo_email",
            strategy="BROWSER",
            status=ExecutionOutcomeStatus.CANCELLED,
            duration_seconds=1.0,
        )
        ev = update_strategy_evidence(None, step_outcome, "wf_user_cancelled_test")
        self.assertEqual(ev.failures, 0)
        self.assertEqual(ev.recent_failures, 0)
        self.assertEqual(ev.last_outcome, "CANCELLED")

    # -----------------------------------------------------------------------
    # 4. Paused execution is not treated as technical failure
    # -----------------------------------------------------------------------
    async def test_04_paused_execution_not_treated_as_failure(self):
        execution = make_execution(
            workflow_id="wf_paused_test",
            workflow_name="Paused Test",
            status=AutomationStatus.PAUSED,
            total_actions=2,
            step_results=[
                StepExecutionResult(
                    step_id="step_1",
                    action_type="open_email",
                    application="demo_email",
                    status="completed",
                )
            ],
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.status, ExecutionOutcomeStatus.PAUSED)

        step_outcome = StepOutcome(
            step_id="step_1",
            action="open_email",
            application="demo_email",
            strategy="BROWSER",
            status=ExecutionOutcomeStatus.PAUSED,
            duration_seconds=1.0,
        )
        ev = update_strategy_evidence(None, step_outcome, "wf_paused_test")
        self.assertEqual(ev.failures, 0)
        self.assertEqual(ev.recent_failures, 0)
        self.assertEqual(ev.last_outcome, "PAUSED")

    # -----------------------------------------------------------------------
    # 5. Partial execution is handled correctly
    # -----------------------------------------------------------------------
    async def test_05_partial_execution_handled_correctly(self):
        # 4 steps: Step 1 & 2 succeed, Step 3 fails, Step 4 not reached
        execution = make_execution(
            workflow_id="wf_partial_pipeline",
            workflow_name="Partial Pipeline",
            status=AutomationStatus.FAILED,
            total_actions=4,
            completed_actions=["open_email", "download_attachment"],
            failed_action="search_customer",
            error="Customer database unavailable (500)",
            actions_detail=[
                {"action": "open_email", "application": "demo_email"},
                {"action": "download_attachment", "application": "demo_email"},
                {"action": "search_customer", "application": "demo_crm"},
                {"action": "update_customer", "application": "demo_crm"},
            ],
            step_results=[
                StepExecutionResult(step_id="step_1", action_type="open_email", application="demo_email", status="completed"),
                StepExecutionResult(step_id="step_2", action_type="download_attachment", application="demo_email", status="completed"),
                StepExecutionResult(step_id="step_3", action_type="search_customer", application="demo_crm", status="failed", error="500 Internal Error"),
            ],
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.status, ExecutionOutcomeStatus.PARTIAL)
        self.assertEqual(outcome.total_steps, 4)
        self.assertEqual(outcome.completed_steps, 2)
        self.assertEqual(outcome.failed_steps_count, 1)
        self.assertEqual(outcome.unexecuted_steps_count, 1)
        self.assertEqual(outcome.failed_step, "search_customer")

    # -----------------------------------------------------------------------
    # 6. Failed step is identified
    # -----------------------------------------------------------------------
    async def test_06_failed_step_identified(self):
        execution = make_execution(
            workflow_id="wf_failed_step_test",
            status=AutomationStatus.FAILED,
            total_actions=3,
            step_results=[
                StepExecutionResult(step_id="step_1", action_type="open_email", application="demo_email", status="completed"),
                StepExecutionResult(step_id="step_2", action_type="update_customer", application="demo_crm", status="failed", error="selector not found"),
            ],
        )

        outcome = evaluate_execution_outcome(execution, target_workflow_id="wf_failed_step_test")
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.failed_step, "update_customer")
        self.assertEqual(outcome.failure_category, FailureCategory.TARGET_NOT_FOUND)

    # -----------------------------------------------------------------------
    # 7. Evidence is associated with workflow + step + strategy
    # -----------------------------------------------------------------------
    async def test_07_evidence_associated_with_workflow_step_strategy(self):
        step_outcome = StepOutcome(
            step_id="step_1",
            action="update_customer",
            application="demo_crm",
            strategy="INTEGRATION",
            status=ExecutionOutcomeStatus.SUCCESS,
            duration_seconds=0.75,
        )
        ev = update_strategy_evidence(None, step_outcome, "wf_customer_support_pipeline")
        self.assertEqual(ev.workflow_id, "wf_customer_support_pipeline")
        self.assertEqual(ev.step_action, "update_customer")
        self.assertEqual(ev.strategy, "INTEGRATION")

    # -----------------------------------------------------------------------
    # 8. Success rate is calculated correctly
    # -----------------------------------------------------------------------
    async def test_08_success_rate_calculated_correctly(self):
        ev = None
        # 3 successes, 1 failure
        for _ in range(3):
            succ_step = StepOutcome(
                step_id="step_1",
                action="send_message",
                strategy="BROWSER",
                status=ExecutionOutcomeStatus.SUCCESS,
            )
            ev = update_strategy_evidence(ev, succ_step, "wf_test_rate")

        fail_step = StepOutcome(
            step_id="step_1",
            action="send_message",
            strategy="BROWSER",
            status=ExecutionOutcomeStatus.FAILED,
        )
        ev = update_strategy_evidence(ev, fail_step, "wf_test_rate")

        self.assertEqual(ev.attempts, 4)
        self.assertEqual(ev.successes, 3)
        self.assertEqual(ev.failures, 1)
        self.assertEqual(ev.success_rate, 0.75)

    # -----------------------------------------------------------------------
    # 9. Recent outcomes influence evidence and bounded window works
    # -----------------------------------------------------------------------
    async def test_09_recent_outcomes_bounded_window(self):
        ev = None
        # Push 12 outcomes (10 SUCCESS, then 2 FAILED)
        for _ in range(10):
            ev = update_strategy_evidence(
                ev,
                StepOutcome(step_id="s1", action="act", strategy="API", status=ExecutionOutcomeStatus.SUCCESS),
                "wf_window",
            )
        for _ in range(2):
            ev = update_strategy_evidence(
                ev,
                StepOutcome(step_id="s1", action="act", strategy="API", status=ExecutionOutcomeStatus.FAILED),
                "wf_window",
            )

        # Window size is bounded to 10
        self.assertEqual(len(ev.recent_outcomes), 10)
        self.assertEqual(ev.attempts, 12)
        self.assertEqual(ev.recent_failures, 2)
        self.assertEqual(ev.recent_successes, 8)
        self.assertEqual(ev.last_outcome, "FAILED")

    # -----------------------------------------------------------------------
    # 10. Repeated failures reduce suitability
    # -----------------------------------------------------------------------
    async def test_10_repeated_failures_reduce_suitability(self):
        # Fresh baseline
        cand_cold = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.API,
            is_available=True,
            rejection_reason=None,
            action="update_customer",
            application="demo_crm",
            is_mutating=False,
            requires_credentials=False,
            credentials_available=True,
        )

        # After 4 failures out of 5 attempts
        cand_failed = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.API,
            is_available=True,
            rejection_reason=None,
            action="update_customer",
            application="demo_crm",
            is_mutating=False,
            requires_credentials=False,
            credentials_available=True,
            history={
                "api_successes": 1,
                "api_failures": 4,
                "api_recent_failures": 3,
                "api_last_failed": True,
            },
        )

        self.assertLess(cand_failed.score, cand_cold.score)
        self.assertGreater(cand_failed.score_breakdown.failure_penalty, 0.30)

    # -----------------------------------------------------------------------
    # 11. Repeated successes improve suitability
    # -----------------------------------------------------------------------
    async def test_11_repeated_successes_improve_suitability(self):
        cand_cold = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.BROWSER,
            is_available=True,
            rejection_reason=None,
            action="open_email",
            application="demo_email",
            is_mutating=False,
            requires_credentials=False,
            credentials_available=True,
        )

        cand_reinforced = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.BROWSER,
            is_available=True,
            rejection_reason=None,
            action="open_email",
            application="demo_email",
            is_mutating=False,
            requires_credentials=False,
            credentials_available=True,
            history={
                "browser_successes": 10,
                "browser_failures": 0,
                "browser_recent_successes": 5,
                "browser_recent_failures": 0,
            },
        )

        self.assertGreater(cand_reinforced.score, cand_cold.score)
        self.assertIn("reinforcement", " ".join(cand_reinforced.selection_reasons).lower())

    # -----------------------------------------------------------------------
    # 12. Fallback success produces positive evidence
    # -----------------------------------------------------------------------
    async def test_12_fallback_success_produces_positive_evidence(self):
        execution = make_execution(
            workflow_id="wf_fallback_test",
            status=AutomationStatus.COMPLETED,
            total_actions=1,
            completed_actions=["update_customer"],
            step_results=[
                StepExecutionResult(
                    step_id="step_1",
                    action_type="update_customer",
                    application="demo_crm",
                    status="completed",
                    duration_seconds=1.2,
                )
            ],
            context={
                "is_fallback": True,
                "fallback_used": True,
                "primary_strategy": "API",
                "step_strategies": {"update_customer": "BROWSER"},
            },
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome)
        self.assertTrue(outcome.fallback_used)

        # Fallback BROWSER gained positive evidence
        browser_ev = await learning_service.get_strategy_evidence("wf_fallback_test", "update_customer", "BROWSER")
        self.assertEqual(len(browser_ev), 1)
        self.assertEqual(browser_ev[0].successes, 1)
        self.assertEqual(browser_ev[0].fallback_count, 1)

        # Primary API recorded failure
        api_ev = await learning_service.get_strategy_evidence("wf_fallback_test", "update_customer", "API")
        self.assertEqual(len(api_ev), 1)
        self.assertEqual(api_ev[0].failures, 1)
        self.assertEqual(api_ev[0].last_outcome, "FAILED")

    # -----------------------------------------------------------------------
    # 13. Fallback failure produces negative evidence
    # -----------------------------------------------------------------------
    async def test_13_fallback_failure_produces_negative_evidence(self):
        execution = make_execution(
            workflow_id="wf_fallback_fail_test",
            status=AutomationStatus.FAILED,
            total_actions=1,
            failed_action="update_customer",
            error="Playwright timeout waiting for selector",
            step_results=[
                StepExecutionResult(
                    step_id="step_1",
                    action_type="update_customer",
                    application="demo_crm",
                    status="failed",
                    error="Playwright timeout waiting for selector",
                )
            ],
            context={
                "is_fallback": True,
                "fallback_used": True,
                "primary_strategy": "API",
                "step_strategies": {"update_customer": "BROWSER"},
            },
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome)

        browser_ev = await learning_service.get_strategy_evidence("wf_fallback_fail_test", "update_customer", "BROWSER")
        self.assertEqual(browser_ev[0].failures, 1)
        self.assertEqual(browser_ev[0].last_outcome, "FAILED")

    # -----------------------------------------------------------------------
    # 14. Phase 10 planner consumes outcome evidence
    # -----------------------------------------------------------------------
    async def test_14_planner_consumes_outcome_evidence(self):
        wf_id = "wf_closed_loop_adaptation"
        # Record execution failure for API on simulate_ping
        step_out = StepOutcome(
            step_id="step_1",
            action="simulate_ping",
            application="mock_service",
            strategy="API",
            status=ExecutionOutcomeStatus.FAILED,
            failure_category=FailureCategory.TIMEOUT,
            error_message="Gateway timeout",
        )
        # Update 3 failures in learning service
        for _ in range(3):
            curr = await learning_service.get_strategy_evidence(wf_id, "simulate_ping", "API")
            c = curr[0] if curr else None
            updated = update_strategy_evidence(c, step_out, wf_id)
            learning_service._strategy_evidence[f"{wf_id}:simulate_ping:API"] = updated

        # Planner creates plan for this workflow without explicit context history
        plan = await automation_planner.create_plan(
            workflow_id=wf_id,
            steps=[{"id": "step_1", "action": "simulate_ping", "application": "mock_service"}],
        )

        api_cand = next(c for c in plan.steps[0].candidates if c.strategy == AutomationStrategyType.API)
        self.assertGreater(api_cand.score_breakdown.failure_penalty, 0.30)
        self.assertEqual(api_cand.metadata.get("recent_failures"), 3)

    # -----------------------------------------------------------------------
    # 15. Safety still dominates strategy selection
    # -----------------------------------------------------------------------
    async def test_15_safety_still_dominates_selection(self):
        # Step requires credentials that are not available
        cand = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.INTEGRATION,
            is_available=True,
            rejection_reason=None,
            action="update_customer",
            application="demo_crm",
            is_mutating=True,
            requires_credentials=True,
            credentials_available=False,  # Unsafe / Disconnected
            history={"integration_successes": 50, "integration_failures": 0},  # Great history!
        )

        # Safety penalty must penalize or lower score significantly
        self.assertGreater(cand.score_breakdown.safety_penalty, 0.20)
        self.assertEqual(cand.score_breakdown.credential_score, 0.0)

    # -----------------------------------------------------------------------
    # 16. Missing credentials remain unsafe / unavailable
    # -----------------------------------------------------------------------
    async def test_16_missing_credentials_remain_unsafe(self):
        # Missing credentials explicitly tested via scorer
        cand = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.API,
            is_available=True,
            rejection_reason=None,
            action="list_recent_messages",
            application="gmail",
            is_mutating=False,
            requires_credentials=True,
            credentials_available=False,
        )
        self.assertGreater(cand.score_breakdown.safety_penalty, 0.20)
        self.assertEqual(cand.score_breakdown.credential_score, 0.0)

    # -----------------------------------------------------------------------
    # 17. Credentials and secrets never appear in outcome records
    # -----------------------------------------------------------------------
    async def test_17_credentials_never_appear_in_outcome_records(self):
        secret_token = "ghp_super_secret_token_1234567890abcdef"
        secret_auth = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.rawtoken"

        execution = make_execution(
            workflow_id="wf_secret_leak_test",
            status=AutomationStatus.FAILED,
            error=f"Connection refused with {secret_token} and Authorization: {secret_auth}",
            step_results=[
                StepExecutionResult(
                    step_id="step_1",
                    action_type="update_customer",
                    application="demo_crm",
                    status="failed",
                    error=f"Failed auth for user password='mySecretPassword123' token={secret_token}",
                )
            ],
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome)

        serialized = outcome.model_dump_json()
        self.assertNotIn("ghp_super_secret", serialized)
        self.assertNotIn("mySecretPassword123", serialized)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", serialized)
        self.assertIn("[REDACTED", serialized)

    # -----------------------------------------------------------------------
    # 18. Outcome explanations are deterministic
    # -----------------------------------------------------------------------
    async def test_18_outcome_explanations_are_deterministic(self):
        # When Browser beats API due to repeated API failures:
        cand_api = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.API,
            is_available=True,
            rejection_reason=None,
            action="open_email",
            application="demo_email",
            is_mutating=False,
            requires_credentials=False,
            credentials_available=True,
            history={
                "api_successes": 1,
                "api_failures": 5,
                "api_recent_failures": 3,
                "api_last_failed": True,
            },
        )
        cand_browser = strategy_scorer.score_strategy(
            strategy=AutomationStrategyType.BROWSER,
            is_available=True,
            rejection_reason=None,
            action="open_email",
            application="demo_email",
            is_mutating=False,
            requires_credentials=False,
            credentials_available=True,
            history={
                "browser_successes": 8,
                "browser_failures": 0,
                "browser_recent_successes": 5,
            },
        )
        self.assertGreater(cand_browser.score, cand_api.score)

        # Plan step with this history
        step_plan = automation_planner._plan_step(
            step_id="step_email",
            action="open_email",
            application="demo_email",
            description="Open email",
            learning_state=None,
            context={
                "history": {
                    "api_successes": 1,
                    "api_failures": 5,
                    "api_recent_failures": 3,
                    "api_last_failed": True,
                    "browser_successes": 8,
                    "browser_failures": 0,
                    "browser_recent_successes": 5,
                }
            },
        )

        self.assertEqual(step_plan.selected_strategy, AutomationStrategyType.BROWSER)
        self.assertIn("Browser was selected because the API strategy has repeated recent failures", step_plan.reason)

    # -----------------------------------------------------------------------
    # 19. Phase 9 learning state remains backward compatible
    # -----------------------------------------------------------------------
    async def test_19_phase9_learning_state_backward_compatibility(self):
        execution = make_execution(
            workflow_id="wf_phase9_compat",
            status=AutomationStatus.COMPLETED,
            total_actions=1,
            completed_actions=["search_customer"],
            results=[
                ExecutionActionResult(
                    action_id="s1",
                    action_type="search_customer",
                    success=True,
                    message="Search succeeded",
                )
            ],
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome)

        # Phase 9 state updated
        state = await learning_service.get_learning_state("wf_phase9_compat")
        self.assertEqual(state.execution_count, 1)
        self.assertEqual(state.successful_execution_count, 1)
        self.assertGreater(state.learning_score, 0.50)

    # -----------------------------------------------------------------------
    # 20. Phase 10 behavior remains backward compatible
    # -----------------------------------------------------------------------
    async def test_20_phase10_behavior_backward_compatibility(self):
        # A cold-start workflow with no execution telemetry
        plan = await automation_planner.create_plan(
            workflow_id="wf_cold_test_pipeline",
            steps=[
                {"id": "step_1", "action": "download_attachment", "application": "demo_email"},
                {"id": "step_2", "action": "update_customer", "application": "demo_crm"},
            ],
        )

        self.assertIsNotNone(plan)
        self.assertTrue(plan.requires_approval)
        self.assertTrue(plan.fallback_available)
        self.assertEqual(len(plan.steps), 2)
        # Browser chosen for browser-only action download_attachment
        self.assertEqual(plan.steps[0].selected_strategy, AutomationStrategyType.BROWSER)

    # -----------------------------------------------------------------------
    # 21. API validation and security behavior
    # -----------------------------------------------------------------------
    def test_21_api_validation_and_security(self):
        # 1. Invalid workflow ID with malicious path traversal characters
        res = self.client.get("/api/workflows/../../etc/passwd/strategy-evidence")
        self.assertIn(res.status_code, [400, 404])

        # 2. Oversized workflow ID (> 128 chars)
        oversized = "a" * 150
        res2 = self.client.get(f"/api/workflows/{oversized}/strategy-evidence")
        self.assertEqual(res2.status_code, 400)

        # 3. Valid workflow ID returns 200
        res3 = self.client.get("/api/workflows/wf_customer_support_pipeline/strategy-evidence")
        self.assertEqual(res3.status_code, 200)
        self.assertIsInstance(res3.json(), list)

        # 4. Closed-loop summary endpoint returns 200
        res4 = self.client.get("/api/workflows/wf_customer_support_pipeline/closed-loop-summary")
        self.assertEqual(res4.status_code, 200)
        summary = res4.json()
        self.assertEqual(summary["workflow_id"], "wf_customer_support_pipeline")
        self.assertIn("Customer Email & Support Pipeline", summary["workflow_name"])

        # 5. Outcomes history endpoint returns 200
        res5 = self.client.get("/api/workflows/wf_customer_support_pipeline/outcomes")
        self.assertEqual(res5.status_code, 200)
        self.assertIsInstance(res5.json(), list)

    # -----------------------------------------------------------------------
    # 22. Closed-loop summary is synthesized correctly
    # -----------------------------------------------------------------------
    async def test_22_closed_loop_summary_synthesized_correctly(self):
        wf_id = "wf_customer_support_pipeline"
        # Seed evidence with an adapted step: API failing, Browser reliable
        ev_api = StrategyOutcomeEvidence(
            workflow_id=wf_id,
            step_action="update_customer",
            strategy="API",
            attempts=5,
            successes=1,
            failures=4,
            success_rate=0.20,
            recent_outcomes=["FAILED", "FAILED", "FAILED"],
            recent_failures=3,
            recent_successes=0,
            last_outcome="FAILED",
            last_failure_category="TIMEOUT",
        )
        ev_browser = StrategyOutcomeEvidence(
            workflow_id=wf_id,
            step_action="update_customer",
            strategy="BROWSER",
            attempts=5,
            successes=5,
            failures=0,
            success_rate=1.00,
            recent_outcomes=["SUCCESS", "SUCCESS", "SUCCESS"],
            recent_failures=0,
            recent_successes=3,
            last_outcome="SUCCESS",
        )

        learning_service._strategy_evidence[f"{wf_id}:update_customer:API"] = ev_api
        learning_service._strategy_evidence[f"{wf_id}:update_customer:BROWSER"] = ev_browser

        summary = await learning_service.get_closed_loop_summary(wf_id)
        self.assertEqual(summary.workflow_id, wf_id)
        self.assertGreater(len(summary.strategy_evidence), 0)
        self.assertGreater(len(summary.adaptations), 0)
        self.assertTrue(any("preferred for 'update_customer'" in a for a in summary.adaptations))

    # -----------------------------------------------------------------------
    # 23. Test 1 — Duplicate execution idempotency
    # -----------------------------------------------------------------------
    async def test_23_duplicate_execution_idempotency(self):
        wf_id = "wf_idempotency_test"
        exec_id = "exec_idempotency_123"
        execution = make_execution(
            execution_id=exec_id,
            workflow_id=wf_id,
            status=AutomationStatus.COMPLETED,
            total_actions=1,
            completed_actions=["open_email"],
            step_results=[
                StepExecutionResult(
                    step_id="step_1",
                    action_type="open_email",
                    application="demo_email",
                    status="completed",
                    duration_seconds=0.8,
                )
            ],
            context={"strategy": "BROWSER"},
        )

        # First processing
        outcome1 = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome1)
        self.assertEqual(outcome1.status, ExecutionOutcomeStatus.SUCCESS)

        ev1 = await learning_service.get_strategy_evidence(wf_id, "open_email", "BROWSER")
        self.assertEqual(len(ev1), 1)
        self.assertEqual(ev1[0].attempts, 1)
        self.assertEqual(ev1[0].successes, 1)
        self.assertEqual(ev1[0].failures, 0)
        self.assertEqual(len(ev1[0].recent_outcomes), 1)
        self.assertEqual(ev1[0].fallback_count, 0)

        # Second processing of the exact same execution
        outcome2 = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome2)
        self.assertEqual(outcome2.execution_id, exec_id)

        # Evidence must NOT be incremented again
        ev2 = await learning_service.get_strategy_evidence(wf_id, "open_email", "BROWSER")
        self.assertEqual(len(ev2), 1)
        self.assertEqual(ev2[0].attempts, 1, "Attempts must remain 1 after replaying execution")
        self.assertEqual(ev2[0].successes, 1, "Successes must remain 1 after replaying execution")
        self.assertEqual(ev2[0].failures, 0)
        self.assertEqual(len(ev2[0].recent_outcomes), 1, "Recent outcomes must not have duplicate entries")
        self.assertEqual(ev2[0].fallback_count, 0)

        # Third processing to ensure absolute idempotency
        await learning_service.record_closed_loop_outcome(execution)
        ev3 = await learning_service.get_strategy_evidence(wf_id, "open_email", "BROWSER")
        self.assertEqual(ev3[0].attempts, 1)
        self.assertEqual(ev3[0].successes, 1)

    # -----------------------------------------------------------------------
    # 24. Test 2 — Successful fallback
    # -----------------------------------------------------------------------
    async def test_24_successful_fallback(self):
        wf_id = "wf_succ_fallback_test"
        execution = make_execution(
            workflow_id=wf_id,
            status=AutomationStatus.COMPLETED,
            total_actions=1,
            completed_actions=["update_customer"],
            step_results=[
                StepExecutionResult(
                    step_id="step_1",
                    action_type="update_customer",
                    application="demo_crm",
                    status="completed",
                    duration_seconds=1.5,
                )
            ],
            context={
                "fallback_used": True,
                "primary_strategy": "API",
                "step_strategies": {"update_customer": "BROWSER"},
            },
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome)
        self.assertTrue(outcome.fallback_used)
        self.assertEqual(len(outcome.step_outcomes), 1)

        step_out = outcome.step_outcomes[0]
        self.assertEqual(step_out.status, ExecutionOutcomeStatus.SUCCESS)
        self.assertTrue(step_out.is_fallback)
        self.assertEqual(step_out.primary_strategy, "API")
        self.assertEqual(step_out.strategy, "BROWSER")

        # Verify API evidence recorded failure
        api_ev = await learning_service.get_strategy_evidence(wf_id, "update_customer", "API")
        self.assertEqual(len(api_ev), 1)
        self.assertEqual(api_ev[0].failures, 1)
        self.assertEqual(api_ev[0].successes, 0)

        # Verify Browser evidence recorded success and fallback count
        browser_ev = await learning_service.get_strategy_evidence(wf_id, "update_customer", "BROWSER")
        self.assertEqual(len(browser_ev), 1)
        self.assertEqual(browser_ev[0].successes, 1)
        self.assertEqual(browser_ev[0].failures, 0)
        self.assertEqual(browser_ev[0].fallback_count, 1)

    # -----------------------------------------------------------------------
    # 25. Test 3 — Failed fallback
    # -----------------------------------------------------------------------
    async def test_25_failed_fallback(self):
        wf_id = "wf_fail_fallback_test"
        execution = make_execution(
            workflow_id=wf_id,
            status=AutomationStatus.FAILED,
            total_actions=1,
            failed_action="update_customer",
            error="Playwright crash",
            step_results=[
                StepExecutionResult(
                    step_id="step_1",
                    action_type="update_customer",
                    application="demo_crm",
                    status="failed",
                    error="Playwright crash on selector",
                )
            ],
            context={
                "fallback_used": True,
                "primary_strategy": "API",
                "step_strategies": {"update_customer": "BROWSER"},
            },
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome)
        self.assertEqual(len(outcome.step_outcomes), 1)

        step_out = outcome.step_outcomes[0]
        self.assertEqual(step_out.status, ExecutionOutcomeStatus.FAILED)
        self.assertTrue(step_out.is_fallback)
        self.assertEqual(step_out.primary_strategy, "API")

        # Verify API failure recorded
        api_ev = await learning_service.get_strategy_evidence(wf_id, "update_customer", "API")
        self.assertEqual(len(api_ev), 1)
        self.assertEqual(api_ev[0].failures, 1)

        # Verify Browser failure recorded with fallback_count = 1
        browser_ev = await learning_service.get_strategy_evidence(wf_id, "update_customer", "BROWSER")
        self.assertEqual(len(browser_ev), 1)
        self.assertEqual(browser_ev[0].failures, 1)
        self.assertEqual(browser_ev[0].fallback_count, 1)

    # -----------------------------------------------------------------------
    # 26. Test 4 — Paused workflow
    # -----------------------------------------------------------------------
    async def test_26_paused_workflow_does_not_fail_unexecuted_steps(self):
        wf_id = "wf_paused_test_multi"
        execution = make_execution(
            workflow_id=wf_id,
            status=AutomationStatus.PAUSED,
            total_actions=3,
            completed_actions=["open_email", "search_customer"],
            actions_detail=[
                {"step_id": "step_1", "action": "open_email", "application": "demo_email"},
                {"step_id": "step_2", "action": "search_customer", "application": "demo_crm"},
                {"step_id": "step_3", "action": "update_customer", "application": "demo_crm"},
            ],
            step_results=[
                StepExecutionResult(step_id="step_1", action_type="open_email", application="demo_email", status="completed"),
                StepExecutionResult(step_id="step_2", action_type="search_customer", application="demo_crm", status="completed"),
                StepExecutionResult(step_id="step_3", action_type="update_customer", application="demo_crm", status="pending"),
            ],
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.status, ExecutionOutcomeStatus.PAUSED)
        self.assertEqual(outcome.completed_steps, 2)
        self.assertEqual(outcome.failed_steps_count, 0)
        self.assertEqual(outcome.unexecuted_steps_count, 1)

        # Steps 1 and 2 recorded correctly as SUCCESS
        self.assertEqual(outcome.step_outcomes[0].status, ExecutionOutcomeStatus.SUCCESS)
        self.assertEqual(outcome.step_outcomes[1].status, ExecutionOutcomeStatus.SUCCESS)

        # Step 3 must NOT become FAILED
        step_3 = outcome.step_outcomes[2]
        self.assertNotEqual(step_3.status, ExecutionOutcomeStatus.FAILED)
        self.assertIn(step_3.status, (ExecutionOutcomeStatus.PAUSED, ExecutionOutcomeStatus.NOT_EXECUTED))

        # Step 3 must NOT create strategy failure evidence
        step3_ev = await learning_service.get_strategy_evidence(wf_id, "update_customer")
        for ev in step3_ev:
            self.assertEqual(ev.failures, 0)
            self.assertEqual(ev.recent_failures, 0)

    # -----------------------------------------------------------------------
    # 27. Test 5 — Cancelled workflow
    # -----------------------------------------------------------------------
    async def test_27_cancelled_workflow_does_not_fail_unexecuted_steps(self):
        wf_id = "wf_cancelled_test_multi"
        execution = make_execution(
            workflow_id=wf_id,
            status=AutomationStatus.CANCELLED,
            total_actions=2,
            completed_actions=["open_email"],
            actions_detail=[
                {"step_id": "step_1", "action": "open_email", "application": "demo_email"},
                {"step_id": "step_2", "action": "update_customer", "application": "demo_crm"},
            ],
            step_results=[
                StepExecutionResult(step_id="step_1", action_type="open_email", application="demo_email", status="completed"),
            ],
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.status, ExecutionOutcomeStatus.CANCELLED)

        # Step 1 remains SUCCESS
        step_1 = next(s for s in outcome.step_outcomes if s.step_id == "step_1")
        self.assertEqual(step_1.status, ExecutionOutcomeStatus.SUCCESS)

        # Step 2 does NOT become FAILED
        step_2 = next(s for s in outcome.step_outcomes if s.step_id == "step_2")
        self.assertNotEqual(step_2.status, ExecutionOutcomeStatus.FAILED)
        self.assertIn(step_2.status, (ExecutionOutcomeStatus.CANCELLED, ExecutionOutcomeStatus.NOT_EXECUTED))

        # No strategy failure evidence for Step 2
        step2_ev = await learning_service.get_strategy_evidence(wf_id, "update_customer")
        for ev in step2_ev:
            self.assertEqual(ev.failures, 0)

    # -----------------------------------------------------------------------
    # 28. Test 6 — Phase 9 learning formula regression
    # -----------------------------------------------------------------------
    def test_28_phase9_learning_formula_regression(self):
        from backend.learning.state import compute_learning_score
        # Baseline prior = 0.50
        score_base = compute_learning_score(0, 0, 0, 0, 0, 0, 0)
        self.assertEqual(score_base, 0.50)

        # Approval: +0.10
        score_app = compute_learning_score(1, 0, 0, 0, 0, 0, 0)
        self.assertEqual(score_app, 0.60)

        # Successful execution: +0.15
        score_succ = compute_learning_score(0, 0, 0, 1, 0, 0, 0)
        self.assertEqual(score_succ, 0.65)

        # Rejection: -0.20
        score_rej = compute_learning_score(0, 1, 0, 0, 0, 0, 0)
        self.assertEqual(score_rej, 0.30)

        # Failed execution: -0.15
        score_fail = compute_learning_score(0, 0, 0, 0, 1, 0, 0)
        self.assertEqual(score_fail, 0.35)

        # Clamping check: raw < 0.0 -> clamped to 0.0
        score_min = compute_learning_score(0, 5, 0, 0, 5, 0, 0)
        self.assertEqual(score_min, 0.0)

        # Clamping check: raw > 1.0 -> clamped to 1.0
        score_max = compute_learning_score(10, 0, 5, 5, 0, 0, 0)
        self.assertEqual(score_max, 1.0)

    # -----------------------------------------------------------------------
    # 29. Test 7 — Existing successful execution
    # -----------------------------------------------------------------------
    async def test_29_existing_successful_execution(self):
        wf_id = "wf_normal_success"
        execution = make_execution(
            workflow_id=wf_id,
            workflow_name="Normal Success Workflow",
            status=AutomationStatus.COMPLETED,
            total_actions=1,
            completed_actions=["open_email"],
            step_results=[
                StepExecutionResult(
                    step_id="step_1",
                    action_type="open_email",
                    application="demo_email",
                    status="completed",
                )
            ],
            context={"strategy": "BROWSER"},
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertEqual(outcome.status, ExecutionOutcomeStatus.SUCCESS)

        # Strategy evidence incremented
        ev = await learning_service.get_strategy_evidence(wf_id, "open_email", "BROWSER")
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0].successes, 1)

        # Phase 9 learning state updated
        state = await learning_service.get_learning_state(wf_id)
        self.assertEqual(state.successful_execution_count, 1)
        self.assertEqual(state.failed_execution_count, 0)

        # Phase 10 planner consumes evidence
        plan = await automation_planner.create_plan(
            workflow_id=wf_id,
            steps=[{"id": "step_1", "action": "open_email", "application": "demo_email"}],
        )
        self.assertIsNotNone(plan)
        self.assertTrue(plan.requires_approval)

    # -----------------------------------------------------------------------
    # 30. Test 8 — Existing failed execution
    # -----------------------------------------------------------------------
    async def test_30_existing_failed_execution(self):
        wf_id = "wf_normal_failed"
        execution = make_execution(
            workflow_id=wf_id,
            workflow_name="Normal Failed Workflow",
            status=AutomationStatus.FAILED,
            total_actions=1,
            failed_action="search_customer",
            error="Connection timeout after 30s",
            step_results=[
                StepExecutionResult(
                    step_id="step_1",
                    action_type="search_customer",
                    application="demo_crm",
                    status="failed",
                    error="Connection timeout after 30s",
                )
            ],
            context={"strategy": "API"},
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertEqual(outcome.status, ExecutionOutcomeStatus.FAILED)
        self.assertEqual(outcome.failure_category, FailureCategory.TIMEOUT)

        # Strategy evidence failure incremented
        ev = await learning_service.get_strategy_evidence(wf_id, "search_customer", "API")
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0].failures, 1)
        self.assertEqual(ev[0].last_failure_category, "TIMEOUT")

        # Phase 10 planner consumes evidence
        plan = await automation_planner.create_plan(
            workflow_id=wf_id,
            steps=[{"id": "step_1", "action": "search_customer", "application": "demo_crm"}],
        )
        self.assertIsNotNone(plan)
        self.assertTrue(plan.requires_approval)


if __name__ == "__main__":
    unittest.main()
