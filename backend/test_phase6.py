#!/usr/bin/env python3
"""
WorkFlowOS Phase 6 - Declarative Workflow Engine Test Suite

Validates:
1.  Declarative Workflow Definition schema and input validation.
2.  Template resolution & variable interpolation ({{inputs.x}}, {{variables.y}}, {{steps.s1.output.z}}).
3.  Step condition evaluation across all comparison operators (==, !=, >, <, contains, in, exists, is_empty).
4.  Conditional branching (on_true and on_false jump routing and skipping).
5.  Retry policy execution with backoff on step failure.
6.  continue_on_failure tolerance.
7.  Output mapping from step results into workflow variables.
8.  Approval safety gate enforcement on unapproved workflows.
9.  Pause, Resume, and Cancel lifecycle transitions.
10. REST API endpoints for workflow templates and execution telemetry.
"""

import unittest
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi.testclient import TestClient

from backend.main import app
from ai.models import WorkflowProposal, WorkflowAction, WorkflowTrigger
from automation.models import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowInputDefinition,
    WorkflowTriggerConfig,
    StepCondition,
    RetryPolicy,
    AutomationStatus,
    ExecuteWorkflowRequest,
)
from automation.engine import (
    automation_engine,
    resolve_template_value,
    evaluate_step_condition,
    proposal_to_workflow_definition,
    AutomationEngineError,
)
from automation.executor import ActionExecutor, NoOpExecutor
from automation.service import automation_service


class CustomMockExecutor(ActionExecutor):
    """Configurable executor for testing retries, simulated failures, and outputs."""
    def __init__(self, fail_steps: Optional[Dict[str, int]] = None, step_data: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.fail_steps = fail_steps or {}  # step_id -> number of times to fail before succeeding
        self.step_data = step_data or {}
        self.attempts: Dict[str, int] = {}
        self.executed_steps = []

    async def execute(self, action, context=None):
        self.executed_steps.append(action.id)
        self.attempts[action.id] = self.attempts.get(action.id, 0) + 1
        curr_attempt = self.attempts[action.id]
        should_fail_times = self.fail_steps.get(action.id, 0)

        from automation.models import ExecutionActionResult
        if curr_attempt <= should_fail_times:
            return ExecutionActionResult(
                action_id=action.id,
                action_type=action.type,
                success=False,
                message=f"Simulated failure on attempt {curr_attempt}",
            )
        data = self.step_data.get(action.id, {"customer_id": "CUST_999", "status": "verified"})
        return ExecutionActionResult(
            action_id=action.id,
            action_type=action.type,
            success=True,
            message="Executed successfully",
            data=data,
        )


class TestDeclarativeWorkflowEngine(unittest.IsolatedAsyncioTestCase):

    def _make_sample_workflow(self) -> WorkflowDefinition:
        return WorkflowDefinition(
            id="test_wf_order_processing",
            name="Order Processing Pipeline",
            description="Process order email, verify customer in CRM, update record, notify chat",
            version="1.0.0",
            trigger=WorkflowTriggerConfig(type="event", application="demo_email", event_type="open_email"),
            inputs=[
                WorkflowInputDefinition(name="customer_name", type="string", default="Priya Patel", required=True),
                WorkflowInputDefinition(name="order_amount", type="number", default=250.0, required=False),
                WorkflowInputDefinition(name="vip_tier", type="string", default="gold", required=False),
            ],
            variables={"verified": False, "priority": "normal"},
            steps=[
                WorkflowStep(
                    id="step_1_open",
                    name="Open Order Email",
                    type="open_email",
                    application="demo_email",
                    target="order_request",
                    parameters={"subject": "Order for {{inputs.customer_name}}"},
                    output_mapping={"opened": "data.status"},
                ),
                WorkflowStep(
                    id="step_2_search",
                    name="Search CRM",
                    type="search_customer",
                    application="demo_crm",
                    target="{{inputs.customer_name}}",
                    parameters={"query": "{{inputs.customer_name}}"},
                    output_mapping={"customer_id": "data.customer_id"},
                ),
                WorkflowStep(
                    id="step_3_update",
                    name="Update CRM",
                    type="update_customer",
                    application="demo_crm",
                    target="{{inputs.customer_name}}",
                    parameters={"customer_id": "{{variables.customer_id}}", "amount": "{{inputs.order_amount}}"},
                ),
                WorkflowStep(
                    id="step_4_notify",
                    name="Send Chat",
                    type="send_message",
                    application="demo_chat",
                    target="sales_team",
                    parameters={"recipient": "{{inputs.customer_name}}", "msg": "Order confirmed"},
                ),
            ],
            requires_approval=True,
        )

    # 1. Template Resolution Tests
    def test_01_template_resolution_variables(self):
        ctx = {
            "inputs": {"customer": "Alice", "amount": 100},
            "variables": {"tier": "platinum"},
            "steps": {"s1": {"output": {"id": "REC_123"}}},
        }
        res1 = resolve_template_value("Hello {{inputs.customer}}!", ctx)
        self.assertEqual(res1, "Hello Alice!")

        res2 = resolve_template_value("{{variables.tier}}", ctx)
        self.assertEqual(res2, "platinum")

        res3 = resolve_template_value("{{steps.s1.output.id}}", ctx)
        self.assertEqual(res3, "REC_123")

        dict_val = {"target": "{{inputs.customer}}", "val": "{{inputs.amount}}"}
        res4 = resolve_template_value(dict_val, ctx)
        self.assertEqual(res4["target"], "Alice")
        self.assertEqual(res4["val"], 100)

    # 2. Condition Evaluation Tests
    def test_02_condition_evaluation_operators(self):
        ctx = {
            "inputs": {"age": 30, "name": "Bob", "tags": ["admin", "staff"], "bio": ""},
            "variables": {"tier": "gold"},
        }
        self.assertTrue(evaluate_step_condition(StepCondition(field="inputs.age", operator="==", value=30), ctx))
        self.assertTrue(evaluate_step_condition(StepCondition(field="inputs.age", operator=">", value=25), ctx))
        self.assertTrue(evaluate_step_condition(StepCondition(field="inputs.age", operator="<=", value=30), ctx))
        self.assertTrue(evaluate_step_condition(StepCondition(field="inputs.name", operator="!=", value="Alice"), ctx))
        self.assertTrue(evaluate_step_condition(StepCondition(field="inputs.tags", operator="contains", value="admin"), ctx))
        self.assertTrue(evaluate_step_condition(StepCondition(field="variables.tier", operator="in", value=["silver", "gold"]), ctx))
        self.assertTrue(evaluate_step_condition(StepCondition(field="inputs.bio", operator="is_empty"), ctx))
        self.assertTrue(evaluate_step_condition(StepCondition(field="inputs.name", operator="is_not_empty"), ctx))
        self.assertTrue(evaluate_step_condition(StepCondition(field="inputs.name", operator="exists"), ctx))
        self.assertFalse(evaluate_step_condition(StepCondition(field="inputs.non_existent", operator="exists"), ctx))

    # 3. Input Validation Test
    async def test_03_missing_required_input_fails_execution(self):
        wf = self._make_sample_workflow()
        wf.inputs[0].required = True
        wf.inputs[0].default = None  # no default for customer_name

        exec_res = await automation_engine.execute_declarative_workflow(
            workflow=wf,
            approved=True,
            inputs={},  # missing customer_name
        )
        self.assertEqual(exec_res.status, AutomationStatus.FAILED)
        self.assertIn("Missing required workflow inputs", exec_res.error or "")

    # 4. Approval Gate Safety Test
    async def test_04_approval_gate_unapproved(self):
        wf = self._make_sample_workflow()
        wf.requires_approval = True

        exec_res = await automation_engine.execute_declarative_workflow(
            workflow=wf,
            approved=False,
        )
        self.assertEqual(exec_res.status, AutomationStatus.PENDING)
        self.assertEqual(len(exec_res.completed_actions), 0)
        self.assertTrue(all(a["status"] == "pending" for a in exec_res.actions_detail))

    # 5. Full Approved Execution with Variable Output Mapping
    async def test_05_successful_declarative_execution_with_output_mapping(self):
        wf = self._make_sample_workflow()
        executor = CustomMockExecutor(step_data={"step_2_search": {"customer_id": "CUST_9876"}})

        exec_res = await automation_engine.execute_declarative_workflow(
            workflow=wf,
            approved=True,
            executor=executor,
            inputs={"customer_name": "Rohan Verma", "order_amount": 500.0},
        )
        self.assertEqual(exec_res.status, AutomationStatus.COMPLETED)
        self.assertEqual(len(exec_res.completed_actions), 4)
        self.assertEqual(exec_res.variables.get("customer_id"), "CUST_9876")
        self.assertEqual(len(exec_res.step_results), 4)
        self.assertTrue(all(sr.status == "completed" for sr in exec_res.step_results))

    # 6. Step Condition & Branching Jump Test
    async def test_06_step_condition_and_branching(self):
        wf = self._make_sample_workflow()
        # Add condition on step 2: only run if inputs.vip_tier == 'platinum'
        wf.steps[1].condition = StepCondition(field="inputs.vip_tier", operator="==", value="platinum")
        executor = CustomMockExecutor()

        # Run with vip_tier='gold' -> step 2 should be skipped
        exec_res = await automation_engine.execute_declarative_workflow(
            workflow=wf,
            approved=True,
            executor=executor,
            inputs={"vip_tier": "gold"},
        )
        self.assertEqual(exec_res.status, AutomationStatus.COMPLETED)
        step_2_res = next(sr for sr in exec_res.step_results if sr.step_id == "step_2_search")
        self.assertEqual(step_2_res.status, "skipped")

    # 7. Retry Policy Execution Test
    async def test_07_retry_policy_recovers(self):
        wf = self._make_sample_workflow()
        # step 1 fails once, but retry policy allows 2 retries
        wf.steps[0].retry_policy = RetryPolicy(max_retries=2, backoff_seconds=0.01)
        executor = CustomMockExecutor(fail_steps={"step_1_open": 1})

        exec_res = await automation_engine.execute_declarative_workflow(
            workflow=wf,
            approved=True,
            executor=executor,
        )
        self.assertEqual(exec_res.status, AutomationStatus.COMPLETED)
        step_1_res = next(sr for sr in exec_res.step_results if sr.step_id == "step_1_open")
        self.assertEqual(step_1_res.attempts, 2)
        self.assertEqual(step_1_res.status, "completed")

    # 8. continue_on_failure Test
    async def test_08_continue_on_failure_tolerance(self):
        wf = self._make_sample_workflow()
        # step 1 fails, but continue_on_failure is True
        wf.steps[0].continue_on_failure = True
        executor = CustomMockExecutor(fail_steps={"step_1_open": 5})

        exec_res = await automation_engine.execute_declarative_workflow(
            workflow=wf,
            approved=True,
            executor=executor,
        )
        self.assertEqual(exec_res.status, AutomationStatus.COMPLETED)
        step_1_res = next(sr for sr in exec_res.step_results if sr.step_id == "step_1_open")
        self.assertEqual(step_1_res.status, "failed")
        # Remaining steps should still execute
        self.assertEqual(len(exec_res.completed_actions), 3)

    # 9. Pause on Step Failure and Resume Test
    async def test_09_pause_on_failure_and_resume(self):
        wf = self._make_sample_workflow()
        # step 2 fails permanently without continue_on_failure
        executor = CustomMockExecutor(fail_steps={"step_2_search": 1})

        exec_res = await automation_service.run_declarative_workflow(
            workflow=wf,
            approved=True,
            executor=executor,
        )
        self.assertEqual(exec_res.status, AutomationStatus.PAUSED)
        self.assertTrue(exec_res.resume_available)
        self.assertEqual(exec_res.failed_action, "search_customer")

        # Now resume: executor has already exhausted its 1 failure, so next attempt succeeds!
        resumed_res = await automation_service.resume_execution(
            execution_id=exec_res.execution_id,
            executor=executor,
        )
        self.assertEqual(resumed_res.status, AutomationStatus.COMPLETED)
        self.assertEqual(resumed_res.resume_count, 1)

    # 10. Backward Compatibility: Proposal Conversion Test
    def test_10_proposal_to_workflow_definition_backward_compat(self):
        proposal = WorkflowProposal(
            name="Legacy Email CRM Workflow",
            intent="Sync email to CRM",
            trigger=WorkflowTrigger(type="open_email", application="demo_email", description="Email opened"),
            actions=[
                WorkflowAction(type="open_email", application="demo_email", description="Open email", target="req"),
                WorkflowAction(type="search_customer", application="demo_crm", description="Search customer", target="cust"),
            ],
            variables=["cust_name"],
            applications=["demo_email", "demo_crm"],
            requires_approval=True,
        )
        wf_def = proposal_to_workflow_definition(proposal)
        self.assertEqual(wf_def.name, "Legacy Email CRM Workflow")
        self.assertEqual(len(wf_def.steps), 2)
        self.assertEqual(wf_def.steps[0].type, "open_email")
        self.assertEqual(wf_def.steps[1].type, "search_customer")
        self.assertEqual(len(wf_def.inputs), 1)
        self.assertEqual(wf_def.inputs[0].name, "cust_name")


class TestPhase6RestApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_11_list_and_get_workflow_templates(self):
        res = self.client.get("/api/automation/workflows")
        self.assertEqual(res.status_code, 200)
        workflows = res.json()
        self.assertIsInstance(workflows, list)
        self.assertGreaterEqual(len(workflows), 1)
        first_id = workflows[0]["id"]

        res2 = self.client.get(f"/api/automation/workflows/{first_id}")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["id"], first_id)

    def test_12_execute_declarative_workflow_api(self):
        wf = WorkflowDefinition(
            id="api_test_wf",
            name="API Test Workflow",
            description="API test execution",
            trigger=WorkflowTriggerConfig(type="manual"),
            inputs=[WorkflowInputDefinition(name="client_name", default="Aarav")],
            steps=[
                WorkflowStep(
                    id="s1",
                    type="open_email",
                    application="demo_email",
                    target="inbox",
                    parameters={"client": "{{inputs.client_name}}"},
                )
            ],
            requires_approval=True,
        )

        # 1. Unapproved -> status=pending
        payload = {
            "workflow_definition": wf.model_dump(),
            "approved": False,
            "executor_type": "noop",
        }
        res1 = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["status"], "pending")

        # 2. Approved -> status=completed
        payload["approved"] = True
        res2 = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["status"], "completed")
        self.assertIn("workflow_definition_id", data2)
        self.assertEqual(data2["workflow_definition_id"], "api_test_wf")
        self.assertGreaterEqual(len(data2["step_results"]), 1)

    def test_13_cancel_execution_api(self):
        # Create a paused execution manually via service to test cancel endpoint
        from automation.models import AutomationExecution
        now_iso = datetime.now(timezone.utc).isoformat()
        exec_id = "test_cancel_exec_p6"
        paused_exec = AutomationExecution(
            execution_id=exec_id,
            workflow_name="Cancelable Workflow",
            status=AutomationStatus.PAUSED,
            failed_action="search_customer",
            failure_reason="Customer unavailable",
            resume_available=True,
            total_actions=3,
            completed_actions=["open_email"],
            started_at=now_iso,
            paused_at=now_iso,
        )
        automation_service._executions[exec_id] = paused_exec

        res = self.client.post(f"/api/automation/executions/{exec_id}/cancel")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "cancelled")
        self.assertFalse(res.json()["resume_available"])


if __name__ == "__main__":
    unittest.main()
