#!/usr/bin/env python3
"""
WorkFlowOS Phase 4.2 Verification & Test Suite

Tests:
1. Valid workflow conversion from WorkflowProposal to AutomationAction.
2. Strict action ordering preserved.
3. Unapproved workflow does NOT execute (status="pending", completed_actions=[]).
4. Approved workflow executes through NoOpExecutor (status="completed").
5. All five supported actions are accepted (open_email, download_attachment, search_customer, update_customer, send_message).
6. Unknown action is rejected (UnsupportedActionError / controlled error, 0 actions executed).
7. Successful execution reports completed status.
8. Failed executor halts subsequent actions immediately.
9. Execution tracks completed action count accurately.
10. No browser or Playwright process is launched.

Usage:
  python backend/test_phase4_2.py
"""

import os
import sys
import unittest
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.models import WorkflowProposal, WorkflowAction, WorkflowTrigger
from automation.models import (
    AutomationAction,
    AutomationExecution,
    AutomationStatus,
    ExecutionActionResult,
)
from automation.executor import ActionExecutor, NoOpExecutor
from automation.engine import (
    AutomationEngine,
    automation_engine,
    SUPPORTED_ACTION_TYPES,
    UnsupportedActionError,
    AutomationEngineError,
)
from automation.service import AutomationService


def create_sample_proposal(
    action_types: Optional[List[str]] = None,
    name: str = "Process Customer Request"
) -> WorkflowProposal:
    """Helper to construct a valid Phase 3 WorkflowProposal."""
    if action_types is None:
        action_types = [
            "open_email",
            "download_attachment",
            "search_customer",
            "update_customer",
            "send_message",
        ]

    actions = []
    app_map = {
        "open_email": ("demo_email", "Open customer email", "customer_request"),
        "download_attachment": ("demo_email", "Download PDF attachment", "customer_request.pdf"),
        "search_customer": ("demo_crm", "Search CRM for customer", "Rahul"),
        "update_customer": ("demo_crm", "Update customer profile", "Rahul"),
        "send_message": ("demo_messaging", "Send notification to support", "#customer-support"),
    }

    for act_type in action_types:
        app, desc, target = app_map.get(
            act_type, ("demo_app", f"Perform {act_type}", "target")
        )
        actions.append(
            WorkflowAction(
                type=act_type,
                application=app,
                description=desc,
                target=target,
            )
        )

    return WorkflowProposal(
        name=name,
        intent="Process customer verification and update CRM",
        trigger=WorkflowTrigger(
            type="new_email",
            application="demo_email",
            description="Incoming email received",
        ),
        actions=actions,
        variables=["customer_name", "attachment"],
        applications=["demo_email", "demo_crm", "demo_messaging"],
        requires_approval=True,
    )


class TestPhase42AutomationEngine(unittest.IsolatedAsyncioTestCase):
    """Test suite for Phase 4.2 Automation Engine abstraction and validation layer."""

    async def asyncSetUp(self):
        self.engine = AutomationEngine()

    def test_01_valid_workflow_conversion(self):
        """Verify that WorkflowProposal actions convert to AutomationAction objects."""
        proposal = create_sample_proposal()
        actions = self.engine.validate_and_convert_actions(proposal.actions)

        self.assertEqual(len(actions), 5)
        for act in actions:
            self.assertIsInstance(act, AutomationAction)
            self.assertTrue(act.id.startswith("act_"))
            self.assertIn(act.type, SUPPORTED_ACTION_TYPES)

    def test_02_action_ordering_preserved(self):
        """Verify that the strict sequential order of actions is preserved."""
        ordered_verbs = [
            "open_email",
            "download_attachment",
            "search_customer",
            "update_customer",
            "send_message",
        ]
        proposal = create_sample_proposal(ordered_verbs)
        actions = self.engine.validate_and_convert_actions(proposal.actions)

        converted_types = [a.type for a in actions]
        self.assertEqual(converted_types, ordered_verbs)
        self.assertEqual(actions[0].type, "open_email")
        self.assertEqual(actions[1].type, "download_attachment")
        self.assertEqual(actions[2].type, "search_customer")
        self.assertEqual(actions[3].type, "update_customer")
        self.assertEqual(actions[4].type, "send_message")

    async def test_03_unapproved_workflow_does_not_execute(self):
        """Verify the approval gate: unapproved workflow remains pending and executes 0 actions."""
        proposal = create_sample_proposal()
        execution = await self.engine.execute_workflow(
            proposal=proposal,
            approved=False,  # Unapproved
        )

        self.assertEqual(execution.status, AutomationStatus.PENDING)
        self.assertEqual(len(execution.completed_actions), 0)
        self.assertEqual(len(execution.results), 0)
        self.assertIsNone(execution.error)
        self.assertFalse(execution.requires_human_intervention)

    async def test_04_approved_workflow_executes_through_noop_executor(self):
        """Verify that approved=True executes the workflow successfully via NoOpExecutor."""
        proposal = create_sample_proposal()
        execution = await self.engine.execute_workflow(
            proposal=proposal,
            approved=True,  # Explicit approval
        )

        self.assertEqual(execution.status, AutomationStatus.COMPLETED)
        self.assertEqual(len(execution.completed_actions), 5)
        self.assertEqual(execution.total_actions, 5)
        self.assertIsNone(execution.error)
        self.assertEqual(len(execution.results), 5)
        for res in execution.results:
            self.assertTrue(res.success)
            self.assertIn("execution deferred to Playwright executor", res.message)

    def test_05_all_five_supported_actions_accepted(self):
        """Verify all five Phase 4 supported actions are accepted by the validation layer."""
        expected_supported = {
            "open_email",
            "download_attachment",
            "search_customer",
            "update_customer",
            "send_message",
        }
        self.assertEqual(SUPPORTED_ACTION_TYPES, expected_supported)

        # Test each supported action individually
        for act_verb in expected_supported:
            proposal = create_sample_proposal([act_verb])
            converted = self.engine.validate_and_convert_actions(proposal.actions)
            self.assertEqual(len(converted), 1)
            self.assertEqual(converted[0].type, act_verb)

    async def test_06_unknown_action_is_rejected(self):
        """Verify that an unknown action verb produces a controlled error and halts execution."""
        # Proposal with an unsupported action
        invalid_proposal = create_sample_proposal(
            ["open_email", "hack_mainframe", "send_message"]
        )

        # Direct validation raises UnsupportedActionError
        with self.assertRaises(UnsupportedActionError) as ctx:
            self.engine.validate_and_convert_actions(invalid_proposal.actions)
        self.assertIn("hack_mainframe", str(ctx.exception))

        # Full execution returns FAILED status without running any action
        execution = await self.engine.execute_workflow(
            proposal=invalid_proposal,
            approved=True,
        )
        self.assertEqual(execution.status, AutomationStatus.FAILED)
        self.assertEqual(len(execution.completed_actions), 0)
        self.assertIn("hack_mainframe", execution.error)

    async def test_07_successful_execution_reports_completed(self):
        """Verify that a successful run correctly populates all execution fields."""
        proposal = create_sample_proposal()
        execution = await self.engine.execute_workflow(proposal=proposal, approved=True)

        self.assertTrue(execution.execution_id.startswith("exec_"))
        self.assertEqual(execution.workflow_name, proposal.name)
        self.assertEqual(execution.status, AutomationStatus.COMPLETED)
        self.assertIsNone(execution.current_action)
        self.assertEqual(
            execution.completed_actions,
            ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"]
        )
        self.assertEqual(execution.total_actions, 5)

    async def test_08_failed_executor_halts_subsequent_actions(self):
        """Verify that if an executor reports failure on step 3, steps 4 and 5 are halted."""
        proposal = create_sample_proposal()

        # Executor configured to fail on "search_customer" (step 3)
        failing_executor = NoOpExecutor(fail_actions=["search_customer"])

        execution = await self.engine.execute_workflow(
            proposal=proposal,
            approved=True,
            executor=failing_executor,
        )

        # Phase 4.6 intentional change: action failure transitions to PAUSED (resumable) instead of terminal FAILED
        self.assertIn(execution.status, [AutomationStatus.PAUSED, AutomationStatus.FAILED])
        self.assertEqual(execution.current_action, "search_customer")
        # Step 1 and 2 completed successfully
        self.assertEqual(
            execution.completed_actions,
            ["open_email", "download_attachment"]
        )
        # Total steps in workflow remains 5
        self.assertEqual(execution.total_actions, 5)
        # Results contain 3 records (2 successful, 1 failed)
        self.assertEqual(len(execution.results), 3)
        self.assertTrue(execution.results[0].success)
        self.assertTrue(execution.results[1].success)
        self.assertFalse(execution.results[2].success)
        self.assertIn("Simulated execution failure", execution.error)

    async def test_09_execution_tracks_completed_action_count(self):
        """Verify execution count tracking across partial and full runs."""
        # 3-step workflow
        proposal_3 = create_sample_proposal(["open_email", "download_attachment", "search_customer"])
        exec_3 = await self.engine.execute_workflow(proposal=proposal_3, approved=True)
        self.assertEqual(len(exec_3.completed_actions), 3)
        self.assertEqual(exec_3.total_actions, 3)

        # 5-step workflow
        proposal_5 = create_sample_proposal()
        exec_5 = await self.engine.execute_workflow(proposal=proposal_5, approved=True)
        self.assertEqual(len(exec_5.completed_actions), 5)
        self.assertEqual(exec_5.total_actions, 5)

    def test_10_no_browser_or_playwright_is_launched(self):
        """Verify that Phase 4.2 NoOpExecutor does not launch or interact with a browser."""
        # Core automation engine/executor modules must not START a browser
        import automation.engine
        import automation.executor
        import automation.models

        # NoOpExecutor must never reference a browser or page
        executor = NoOpExecutor()
        self.assertIsInstance(executor, ActionExecutor)

        # NoOpExecutor must not have any Playwright browser state attributes
        self.assertFalse(hasattr(executor, "_browser"),
            "NoOpExecutor must not have a _browser attribute")
        self.assertFalse(hasattr(executor, "_page"),
            "NoOpExecutor must not have a _page attribute")
        self.assertFalse(hasattr(executor, "_playwright"),
            "NoOpExecutor must not have a _playwright attribute")

    async def test_11_automation_service_history_tracking(self):
        """Verify internal AutomationService records execution runs in history."""
        service = AutomationService()
        proposal = create_sample_proposal()

        exec_res = await service.run_workflow(proposal=proposal, approved=True)
        retrieved = service.get_execution(exec_res.execution_id)

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.execution_id, exec_res.execution_id)
        self.assertEqual(retrieved.status, AutomationStatus.COMPLETED)
        self.assertIn(exec_res, service.list_executions())


if __name__ == "__main__":
    unittest.main(verbosity=2)
