"""
Regression tests for:
1. Resume state restoration:
   - Resuming from an earlier step after a later step previously failed
   - Resumed workflow branches around the previously failed step
   - Later condition does not read stale failure state from previous attempts
   - Historical execution records remain preserved as intended
2. Sensitive data sanitization in snapshot and actions_detail:
   - Redacts secret-like credentials from completed, skipped, failed, and pending step messages
3. Step completion derivation from latest result:
   - Step completed, then failed during replay with continue_on_failure, then resumed
4. Active variables isolation at resume cursor:
   - Resuming before or at a variable-populating step resets stale variables to defaults
   - Downstream steps consume fresh rebuilt variables
"""

import unittest
from typing import Optional, Dict, Any, List

from automation.models import (
    WorkflowDefinition,
    WorkflowStep,
    StepCondition,
    AutomationStatus,
    AutomationAction,
    ExecutionActionResult,
)
from automation.engine import AutomationEngine
from automation.executor import ActionExecutor


class CustomMockExecutor(ActionExecutor):
    """Mock executor for testing branching, failures, variable mapping, and sensitive messages."""

    def __init__(
        self,
        fail_steps: Optional[List[str]] = None,
        step_messages: Optional[Dict[str, str]] = None,
        step_data: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        self.fail_steps = set(fail_steps or [])
        self.step_messages = step_messages or {}
        self.step_data = step_data or {}
        self.executed_steps: List[str] = []
        self.executed_actions: List[AutomationAction] = []

    async def execute(
        self, action: AutomationAction, context: Optional[Dict[str, Any]] = None
    ) -> ExecutionActionResult:
        self.executed_steps.append(action.id)
        self.executed_actions.append(action)
        msg = self.step_messages.get(action.id, f"Executed action {action.id}")

        if action.id in self.fail_steps or action.type in self.fail_steps:
            return ExecutionActionResult(
                action_id=action.id,
                action_type=action.type,
                success=False,
                message=msg,
            )

        data = self.step_data.get(action.id, {"result": "ok", "action_id": action.id})
        return ExecutionActionResult(
            action_id=action.id,
            action_type=action.type,
            success=True,
            data=data,
            message=msg,
        )


class TestResumeAndSanitizationRegression(unittest.IsolatedAsyncioTestCase):
    """Regression test suite for resume state isolation and action details sanitization."""

    async def asyncSetUp(self):
        self.engine = AutomationEngine()

    async def test_01_resume_from_earlier_step_branches_around_failed_step_without_stale_failure(self):
        """
        Validates:
        1. Resume from an earlier step after a later step previously failed.
        2. Resumed workflow branches around that previously failed step.
        3. A later condition does not read stale failure state.
        4. Historical execution records remain preserved as intended.
        5. Carried-forward results are deduplicated.
        """
        workflow = WorkflowDefinition(
            id="wf_resume_branch_test",
            name="Resume Branching Test Workflow",
            steps=[
                WorkflowStep(
                    id="step_1",
                    name="Initial Step",
                    type="open_email",
                    application="demo_email",
                ),
                WorkflowStep(
                    id="step_2",
                    name="Search Step",
                    type="search_customer",
                    application="demo_crm",
                ),
                WorkflowStep(
                    id="step_3",
                    name="Risky Step",
                    type="update_customer",
                    application="demo_crm",
                    condition=StepCondition(
                        field="inputs.skip_risky",
                        operator="!=",
                        value="true",
                    ),
                ),
                WorkflowStep(
                    id="step_4",
                    name="Final Step",
                    type="send_message",
                    application="demo_chat",
                    condition=StepCondition(
                        field="steps.step_3.status",
                        operator="!=",
                        value="failed",
                    ),
                ),
            ],
            requires_approval=False,
        )

        # 1. Initial Attempt: skip_risky="false", step_3 runs and fails -> PAUSED
        initial_executor = CustomMockExecutor(fail_steps=["step_3", "update_customer"])
        initial_exec = await self.engine.execute_declarative_workflow(
            workflow=workflow,
            inputs={"skip_risky": "false"},
            approved=True,
            executor=initial_executor,
        )

        self.assertEqual(initial_exec.status, AutomationStatus.PAUSED)
        self.assertEqual(initial_exec.failed_action, "update_customer")
        self.assertEqual(initial_exec.completed_actions, ["open_email", "search_customer"])
        self.assertEqual(len(initial_exec.step_results), 3)
        self.assertEqual(initial_exec.step_results[2].step_id, "step_3")
        self.assertEqual(initial_exec.step_results[2].status, "failed")

        # 2. Resume from earlier step (step_2) with skip_risky="true"
        resumed_executor = CustomMockExecutor(fail_steps=[])
        resumed_exec = await self.engine.resume_declarative_workflow(
            execution=initial_exec,
            resume_step_id="step_2",
            inputs={"skip_risky": "true"},
            executor=resumed_executor,
        )

        self.assertEqual(resumed_exec.status, AutomationStatus.COMPLETED)
        self.assertEqual(resumed_exec.resume_count, 1)

        # Verify step_3 was branched around and NOT executed by resumed executor
        self.assertNotIn("step_3", resumed_executor.executed_steps)
        self.assertIn("step_2", resumed_executor.executed_steps)
        self.assertIn("step_4", resumed_executor.executed_steps)

        # Verify step_4 condition evaluated True because step_3 was NOT restored
        # with stale "failed" status into active runtime context
        self.assertIn("open_email", resumed_exec.completed_actions)
        self.assertIn("search_customer", resumed_exec.completed_actions)
        self.assertIn("send_message", resumed_exec.completed_actions)
        self.assertNotIn("update_customer", resumed_exec.completed_actions)

        # Verify actions_detail in snapshot
        detail_map = {d["action_id"]: d for d in resumed_exec.actions_detail}
        self.assertEqual(detail_map["step_1"]["status"], "completed")
        self.assertEqual(detail_map["step_2"]["status"], "completed")
        self.assertEqual(detail_map["step_3"]["status"], "skipped")
        self.assertEqual(detail_map["step_4"]["status"], "completed")

        # Historical records preserved
        historical_step_3_failures = [
            sr for sr in resumed_exec.step_results
            if sr.step_id == "step_3" and sr.status == "failed"
        ]
        self.assertEqual(len(historical_step_3_failures), 1)
        self.assertGreaterEqual(len(resumed_exec.step_results), 5)

        # Results deduplication: rerun steps do not duplicate carried-forward results
        result_action_ids = [r.action_id for r in resumed_exec.results]
        self.assertEqual(result_action_ids, ["step_1", "step_2", "step_4"])
        self.assertEqual(len(resumed_exec.results), 3)

    async def test_02_sensitive_data_sanitization_in_actions_detail(self):
        """
        Validates that credentials in step errors, logs, and messages are
        sanitized and redacted with [REDACTED] in snapshot and actions_detail.
        """
        secret_bearer = "Bearer ya29.a0AfH6SMA_secret_token_12345"
        secret_pw = "password=SuperSecretPassword999"

        workflow = WorkflowDefinition(
            id="wf_sanitization_test",
            name="Sanitization Test Workflow",
            steps=[
                WorkflowStep(
                    id="step_auth_success",
                    name="Step With Auth Log",
                    type="open_email",
                    application="demo_email",
                ),
                WorkflowStep(
                    id="step_auth_failure",
                    name="Step With Password Error",
                    type="update_customer",
                    application="demo_crm",
                ),
                WorkflowStep(
                    id="step_pending",
                    name="Step Pending",
                    type="send_message",
                    application="demo_chat",
                ),
            ],
            requires_approval=False,
        )

        executor = CustomMockExecutor(
            fail_steps=["step_auth_failure", "update_customer"],
            step_messages={
                "step_auth_success": f"Connected to server with {secret_bearer} successfully",
                "step_auth_failure": f"Authentication failed with {secret_pw} for user admin",
            },
        )

        exec_res = await self.engine.execute_declarative_workflow(
            workflow=workflow,
            approved=True,
            executor=executor,
        )

        self.assertEqual(exec_res.status, AutomationStatus.PAUSED)
        self.assertTrue(len(exec_res.actions_detail) > 0)

        for detail in exec_res.actions_detail:
            msg = detail["message"]
            self.assertNotIn("ya29.", msg, f"Bearer token leaked in step {detail['action_id']}")
            self.assertNotIn("SuperSecretPassword999", msg, f"Password leaked in step {detail['action_id']}")
            if detail["action_id"] == "step_auth_success":
                self.assertIn("[REDACTED]", msg)
            elif detail["action_id"] == "step_auth_failure":
                self.assertIn("[REDACTED]", msg)

        for detail in exec_res.all_actions:
            msg = detail["message"]
            self.assertNotIn("ya29.", msg)
            self.assertNotIn("SuperSecretPassword999", msg)

        if exec_res.error:
            self.assertNotIn("SuperSecretPassword999", exec_res.error)
        if exec_res.failure_reason:
            self.assertNotIn("SuperSecretPassword999", exec_res.failure_reason)

        for sr in exec_res.step_results:
            if sr.error:
                self.assertNotIn("SuperSecretPassword999", sr.error)
            for log_entry in sr.logs:
                self.assertNotIn("ya29.", log_entry)
                self.assertNotIn("SuperSecretPassword999", log_entry)

    async def test_03_resume_with_step_completed_then_failed_on_replay_with_continue_on_failure(self):
        """
        Finding 1 Regression:
        A step that completed in attempt 1, then failed during replay (with continue_on_failure)
        in attempt 2, must have its latest failed status take precedence. When subsequently
        resuming from a later step, the older completed result must NOT override the newer failure.
        """
        workflow = WorkflowDefinition(
            id="wf_replay_continue_on_failure",
            name="Replay Continue on Failure Workflow",
            steps=[
                WorkflowStep(
                    id="step_1",
                    name="Step 1",
                    type="open_email",
                    application="demo_email",
                    continue_on_failure=True,
                ),
                WorkflowStep(
                    id="step_2",
                    name="Step 2",
                    type="search_customer",
                    application="demo_crm",
                    continue_on_failure=False,
                ),
            ],
            requires_approval=False,
        )

        # Attempt 1: Step 1 succeeds, Step 2 fails -> PAUSED
        exec_1 = await self.engine.execute_declarative_workflow(
            workflow=workflow,
            approved=True,
            executor=CustomMockExecutor(fail_steps=["step_2"]),
        )
        self.assertEqual(exec_1.status, AutomationStatus.PAUSED)
        self.assertEqual(exec_1.step_results[0].status, "completed")
        self.assertEqual(exec_1.step_results[1].status, "failed")

        # Attempt 2 (Replay from step_1): Step 1 fails on replay, but continues; Step 2 fails again
        exec_2 = await self.engine.resume_declarative_workflow(
            execution=exec_1,
            resume_step_id="step_1",
            executor=CustomMockExecutor(fail_steps=["step_1", "step_2"]),
        )
        self.assertEqual(exec_2.status, AutomationStatus.PAUSED)
        # Verify history has 4 records: step_1(ok), step_2(fail), step_1(fail), step_2(fail)
        self.assertEqual(len(exec_2.step_results), 4)
        self.assertEqual(exec_2.step_results[2].step_id, "step_1")
        self.assertEqual(exec_2.step_results[2].status, "failed")

        # Attempt 3: Resume from step_2
        # Since step_1's LATEST attempt before start_step_idx was "failed",
        # the older "completed" must NOT override the newer "failed" result.
        exec_3 = await self.engine.resume_declarative_workflow(
            execution=exec_2,
            resume_step_id="step_2",
            executor=CustomMockExecutor(fail_steps=[]),  # step_2 now succeeds
        )
        self.assertEqual(exec_3.status, AutomationStatus.COMPLETED)

        # Step 1 must NOT be in completed_actions because its latest prior result was failed
        self.assertNotIn("open_email", exec_3.completed_actions)
        self.assertIn("search_customer", exec_3.completed_actions)

        # actions_detail in snapshot: step_1 should be failed, not completed
        detail_map = {d["action_id"]: d for d in exec_3.actions_detail}
        self.assertEqual(detail_map["step_1"]["status"], "failed")
        self.assertEqual(detail_map["step_2"]["status"], "completed")

        # Prior results must NOT contain step_1
        result_action_ids = [r.action_id for r in exec_3.results]
        self.assertEqual(result_action_ids, ["step_2"])

        # Historical attempts remain preserved
        self.assertEqual(len(exec_3.step_results), 5)

    async def test_04_resume_variable_isolation_rebuilds_active_variables_cleanly(self):
        """
        Finding 2 Regression:
        Rebuilds active variables at the resume cursor:
        - Output mappings from steps validly completed before cursor are retained.
        - Steps at or after cursor do NOT leak stale variables from prior executions.
        - When a step is rerun or skipped on resume, downstream steps do not consume stale values.
        """
        workflow = WorkflowDefinition(
            id="wf_variable_isolation_test",
            name="Variable Isolation Test Workflow",
            variables={
                "customer_id": "DEFAULT_CUST",
                "order_status": "NONE",
            },
            steps=[
                WorkflowStep(
                    id="step_1",
                    name="Step 1 Initial",
                    type="open_email",
                    application="demo_email",
                    output_mapping={"customer_id": "data.customer_id"},
                ),
                WorkflowStep(
                    id="step_2",
                    name="Step 2 Populator",
                    type="search_customer",
                    application="demo_crm",
                    condition=StepCondition(
                        field="inputs.skip_step_2",
                        operator="!=",
                        value="true",
                    ),
                    output_mapping={"order_status": "data.order_status"},
                ),
                WorkflowStep(
                    id="step_3",
                    name="Step 3 Risky",
                    type="update_customer",
                    application="demo_crm",
                ),
                WorkflowStep(
                    id="step_4",
                    name="Step 4 Consumer",
                    type="send_message",
                    application="demo_chat",
                    target="{{variables.customer_id}}:{{variables.order_status}}",
                ),
            ],
            requires_approval=False,
        )

        # Attempt 1: skip_step_2 is false, step_1 sets customer_id, step_2 sets order_status, step_3 fails
        initial_executor = CustomMockExecutor(
            fail_steps=["step_3"],
            step_data={
                "step_1": {"customer_id": "CUST_999"},
                "step_2": {"order_status": "PROCESSING"},
            },
        )
        exec_1 = await self.engine.execute_declarative_workflow(
            workflow=workflow,
            inputs={"skip_step_2": "false"},
            approved=True,
            executor=initial_executor,
        )
        self.assertEqual(exec_1.status, AutomationStatus.PAUSED)
        self.assertEqual(exec_1.variables.get("customer_id"), "CUST_999")
        self.assertEqual(exec_1.variables.get("order_status"), "PROCESSING")

        # Attempt 2: Resume from step_2 with skip_step_2="true"
        # Since step_2 is AT the cursor, its previous output (order_status='PROCESSING')
        # must NOT be retained. It must revert to default 'NONE'.
        # step_1 (before cursor) MUST retain customer_id='CUST_999'.
        resumed_executor = CustomMockExecutor(
            fail_steps=[],
            step_data={},
        )
        exec_2 = await self.engine.resume_declarative_workflow(
            execution=exec_1,
            resume_step_id="step_2",
            inputs={"skip_step_2": "true"},
            executor=resumed_executor,
        )

        self.assertEqual(exec_2.status, AutomationStatus.COMPLETED)
        # Variable checks on completed execution
        self.assertEqual(exec_2.variables.get("customer_id"), "CUST_999")
        self.assertEqual(exec_2.variables.get("order_status"), "NONE")

        # Downstream step 4 consumption check:
        # Step 4 target was resolved from runtime_context["variables"]
        step_4_action = next(a for a in resumed_executor.executed_actions if a.id == "step_4")
        self.assertEqual(step_4_action.target, "CUST_999:NONE")
        self.assertNotEqual(step_4_action.target, "CUST_999:PROCESSING")


if __name__ == "__main__":
    unittest.main()
