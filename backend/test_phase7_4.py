#!/usr/bin/env python3
"""
WorkFlowOS Phase 7.4: Reliability, Security, and Recoverability Test Suite

Validates:
1. Durable Execution State:
   - Persistence of execution records to MongoDB collection.
   - Restoration of execution history across simulated backend restarts.
   - Intermediate progress persistence before and after each step.

2. Recovery of Interrupted Executions:
   - Startup detection of executions left in RUNNING status.
   - Safe transition to PAUSED with requires_human_intervention=True and resume_available=True.
   - Preservation of completed steps (no blind rerun of completed actions).
   - Audit logging of recovery reason and incremented recovery_attempts.

3. Idempotency & Duplicate Execution Prevention:
   - Idempotency key deduplication across repeated execution requests.
   - Prevention of duplicate runs on network retries.

4. Approval Security & Definition Hash Tamper Detection:
   - SHA-256 canonical definition hash validation.
   - Detection and rejection (HTTP 409) when workflow is modified after approval.
   - Rejection of direct execution or unapproved execution.

5. Step Timeouts & Error Classification:
   - Action timeout enforcement via asyncio.wait_for (cancels hanging actions).
   - Non-retryable error classification (401, 403, 404, validation errors abort retries immediately).
   - Bounded retries with backoff for transient errors.

6. State Machine Integrity:
   - Rejection of invalid transitions (terminal states cannot be cancelled or resumed).
   - Paused, cancelled, completed, and failed status enforcement.

7. Resource Cleanup & Shutdown Hooks:
   - Active PlaywrightExecutor registration and shutdown cleanup.
   - Lifespan startup and shutdown execution.

8. Credential Redaction & Security:
   - Redaction of sensitive tokens, keys, and passwords from execution history, logs, and variables.
   - Graceful fallback during database outages.
"""

import asyncio
import os
import unittest
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from unittest.mock import patch, AsyncMock, MagicMock

import httpx
from fastapi.testclient import TestClient

from backend.main import app
from automation.models import (
    AutomationExecution,
    AutomationStatus,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowInputDefinition,
    WorkflowTriggerConfig,
    RetryPolicy,
    is_valid_transition,
    compute_workflow_definition_hash,
)
from automation.engine import (
    AutomationEngine,
    ApprovalTamperingError,
    InvalidStateTransitionError,
    is_non_retryable_error,
)
from automation.service import AutomationService
from automation.executor import ActionExecutor, NoOpExecutor
from automation.playwright_executor import (
    PlaywrightExecutor,
    _active_executors,
    register_active_executor,
    unregister_active_executor,
    close_active_executors,
)
from integrations.credentials import sanitize_credential_dict, sanitize_log_message


class MockAsyncCollection:
    """Mock MongoDB async collection for hermetic persistence testing."""

    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}

    async def update_one(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any], upsert: bool = False):
        key = filter_dict.get("execution_id")
        doc = update_dict.get("$set", {})
        self._data[key] = dict(doc)
        return MagicMock(acknowledged=True)

    def find(self, filter_dict: Optional[Dict[str, Any]] = None):
        items = list(self._data.values())

        class AsyncCursor:
            def __init__(self, data_list):
                self._items = list(data_list)
                self._idx = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._idx < len(self._items):
                    item = dict(self._items[self._idx])
                    self._idx += 1
                    return item
                raise StopAsyncIteration

        return AsyncCursor(items)


class MockSlowExecutor(ActionExecutor):
    """Executor that simulates a hanging network/integration call."""

    def __init__(self, delay_sec: float = 1.0):
        self.delay_sec = delay_sec

    async def execute(self, action, context=None):
        await asyncio.sleep(self.delay_sec)
        from automation.models import ExecutionActionResult
        return ExecutionActionResult(
            action_id=action.id,
            action_type=action.type,
            success=True,
            message="Completed after delay",
        )


class TestPhase74ReliabilityAndSecurity(unittest.IsolatedAsyncioTestCase):
    """Phase 7.4 Test Suite covering durable persistence, recovery, security, and cleanup."""

    def setUp(self):
        self.client = TestClient(app)
        self.engine = AutomationEngine()
        self.service = AutomationService(engine=self.engine)

    def _create_sample_workflow(self, name: str = "Reliability Test Workflow") -> WorkflowDefinition:
        now_iso = datetime.now(timezone.utc).isoformat()
        return WorkflowDefinition(
            id=f"wf_test_{int(datetime.now().timestamp())}",
            name=name,
            version="1.0.0",
            trigger=WorkflowTriggerConfig(type="manual", application="workflow_system"),
            inputs=[
                WorkflowInputDefinition(name="customer_id", type="string", default="CUST-100", required=True),
                WorkflowInputDefinition(name="api_token", type="string", default="secret-token-value-999", required=False),
            ],
            variables={"status": "init"},
            steps=[
                WorkflowStep(
                    id="step_1",
                    name="Step 1 Verify",
                    type="search_customer",
                    application="demo_crm",
                    target="{{inputs.customer_id}}",
                    parameters={"query": "{{inputs.customer_id}}"},
                ),
                WorkflowStep(
                    id="step_2",
                    name="Step 2 Update",
                    type="update_customer",
                    application="demo_crm",
                    target="{{inputs.customer_id}}",
                    parameters={"customer": "{{inputs.customer_id}}", "status": "active"},
                ),
                WorkflowStep(
                    id="step_3",
                    name="Step 3 Notify",
                    type="send_message",
                    application="demo_chat",
                    target="ops_channel",
                    parameters={"message": "Customer updated"},
                ),
            ],
            requires_approval=True,
            created_at=now_iso,
            updated_at=now_iso,
        )

    # -----------------------------------------------------------------------
    # Step 2: Durable Execution State
    # -----------------------------------------------------------------------

    async def test_durable_persistence_and_restore_across_restarts(self):
        """Validates that executions are persisted to MongoDB and restored on backend restart."""
        mock_col = MockAsyncCollection()
        mock_db = {"executions": mock_col}

        workflow = self._create_sample_workflow()
        executor = NoOpExecutor()

        with patch("backend.database.get_database", return_value=mock_db):
            execution = await self.service.run_declarative_workflow(
                workflow=workflow,
                approved=True,
                executor=executor,
            )

        self.assertEqual(execution.status, AutomationStatus.COMPLETED)
        self.assertIn(execution.execution_id, mock_col._data)

        # Simulate backend restart with a brand new AutomationService instance
        fresh_service = AutomationService(engine=self.engine)
        self.assertEqual(len(fresh_service.list_executions()), 0)

        with patch("backend.database.get_database", return_value=mock_db):
            loaded_count = await fresh_service.load_executions_from_db()

        self.assertEqual(loaded_count, 1)
        restored_exec = fresh_service.get_execution(execution.execution_id)
        self.assertIsNotNone(restored_exec)
        self.assertEqual(restored_exec.status, AutomationStatus.COMPLETED)
        self.assertEqual(restored_exec.total_actions, 3)
        self.assertEqual(len(restored_exec.completed_actions), 3)

    async def test_step_level_intermediate_progress_persistence(self):
        """Validates that progress callback records RUNNING status before and during step execution."""
        mock_col = MockAsyncCollection()
        mock_db = {"executions": mock_col}
        workflow = self._create_sample_workflow()

        captured_statuses: List[str] = []

        original_persist = self.service._persist_execution

        async def track_persist(exec_obj):
            captured_statuses.append(exec_obj.status.value if hasattr(exec_obj.status, "value") else str(exec_obj.status))
            await original_persist(exec_obj)

        with patch.object(self.service, "_persist_execution", side_effect=track_persist):
            with patch("backend.database.get_database", return_value=mock_db):
                execution = await self.service.run_declarative_workflow(
                    workflow=workflow,
                    approved=True,
                    executor=NoOpExecutor(),
                )

        self.assertIn("running", captured_statuses)
        self.assertIn("completed", captured_statuses)
        self.assertEqual(execution.status, AutomationStatus.COMPLETED)

    # -----------------------------------------------------------------------
    # Step 3: Recovery of Interrupted Executions
    # -----------------------------------------------------------------------

    async def test_interrupted_running_execution_recovery_to_paused(self):
        """
        Validates that executions left in RUNNING status during unexpected shutdown
        are safely recovered to PAUSED with completed steps preserved.
        """
        mock_col = MockAsyncCollection()
        mock_db = {"executions": mock_col}

        now_iso = datetime.now(timezone.utc).isoformat()
        interrupted_exec = AutomationExecution(
            execution_id="exec_interrupted_123",
            workflow_id="wf_interrupted",
            workflow_name="Interrupted Workflow",
            status=AutomationStatus.RUNNING,
            current_action="update_customer",
            completed_actions=["search_customer"],
            total_actions=3,
            started_at=now_iso,
            step_results=[],
            serialized_workflow=self._create_sample_workflow().model_dump(),
        )

        # Store in mock database as left by unexpected shutdown
        mock_col._data[interrupted_exec.execution_id] = interrupted_exec.model_dump()

        service = AutomationService(engine=self.engine)
        with patch("backend.database.get_database", return_value=mock_db):
            await service.load_executions_from_db()
            recovered_ids = await service.recover_interrupted_executions()

        self.assertIn("exec_interrupted_123", recovered_ids)
        recovered_exec = service.get_execution("exec_interrupted_123")
        self.assertEqual(recovered_exec.status, AutomationStatus.PAUSED)
        self.assertTrue(recovered_exec.requires_human_intervention)
        self.assertTrue(recovered_exec.resume_available)
        self.assertEqual(recovered_exec.recovery_attempts, 1)
        self.assertIn("preserved", recovered_exec.recovery_reason.lower())
        self.assertEqual(recovered_exec.completed_actions, ["search_customer"])

    async def test_completed_step_preservation_on_resume_after_recovery(self):
        """Validates that resuming an execution after recovery never reruns completed actions."""
        workflow = self._create_sample_workflow()
        # Fail action 2
        fail_executor = NoOpExecutor(fail_actions=["update_customer"])

        execution = await self.service.run_declarative_workflow(
            workflow=workflow,
            approved=True,
            executor=fail_executor,
        )
        self.assertEqual(execution.status, AutomationStatus.PAUSED)
        self.assertEqual(execution.completed_actions, ["search_customer"])

        # Resume with working executor
        success_executor = NoOpExecutor()
        executed_actions = []

        original_exec = success_executor.execute
        async def record_exec(action, context=None):
            executed_actions.append(action.type)
            return await original_exec(action, context)

        success_executor.execute = record_exec

        resumed = await self.service.resume_execution(
            execution_id=execution.execution_id,
            executor=success_executor,
        )

        self.assertEqual(resumed.status, AutomationStatus.COMPLETED)
        # Verify search_customer was NOT re-executed
        self.assertNotIn("search_customer", executed_actions)
        self.assertIn("update_customer", executed_actions)
        self.assertIn("send_message", executed_actions)

    # -----------------------------------------------------------------------
    # Step 4: Approval Security & Cryptographic Tamper Detection
    # -----------------------------------------------------------------------

    async def test_workflow_definition_hash_tamper_detection(self):
        """Validates that modifying a workflow definition after approval raises ApprovalTamperingError."""
        workflow = self._create_sample_workflow()
        initial_hash = compute_workflow_definition_hash(workflow)
        self.assertTrue(len(initial_hash) == 64)

        # Tamper with the workflow: modify step target
        workflow.steps[0].target = "tampered_target_hacker"
        tampered_hash = compute_workflow_definition_hash(workflow)
        self.assertNotEqual(initial_hash, tampered_hash)

        # Attempt to run claiming approved with the old definition_hash
        with self.assertRaises(ApprovalTamperingError):
            await self.service.run_declarative_workflow(
                workflow=workflow,
                approved=True,
                expected_definition_hash=initial_hash,
                executor=NoOpExecutor(),
            )

    def test_api_execute_rejects_definition_tampering_with_409(self):
        """API execution endpoint returns HTTP 409 Conflict when definition hash is tampered."""
        workflow = self._create_sample_workflow()
        canonical_hash = compute_workflow_definition_hash(workflow)

        # Tamper with the step parameters
        workflow.steps[1].parameters = {"malicious": "injected"}

        payload = {
            "workflow_definition": workflow.model_dump(),
            "approved": True,
            "definition_hash": canonical_hash,  # Old hash
            "executor_type": "noop",
        }

        res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res.status_code, 409)
        self.assertIn("modified after approval", res.json()["detail"])

    def test_unapproved_workflow_execution_halted(self):
        """Unapproved workflow cannot execute mutating actions and returns PENDING."""
        workflow = self._create_sample_workflow()
        payload = {
            "workflow_definition": workflow.model_dump(),
            "approved": False,
            "executor_type": "noop",
        }
        res = self.client.post("/api/automation/execute", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "pending")
        self.assertEqual(len(data["completed_actions"]), 0)

    # -----------------------------------------------------------------------
    # Step 5: Duplicate Execution Prevention (Idempotency)
    # -----------------------------------------------------------------------

    async def test_idempotency_key_duplicate_prevention(self):
        """Sending the same idempotency key returns the existing execution without duplicating runs."""
        workflow = self._create_sample_workflow()
        idempotency_key = "idemp_test_key_999"

        # First execution
        exec1 = await self.service.run_declarative_workflow(
            workflow=workflow,
            approved=True,
            executor=NoOpExecutor(),
            idempotency_key=idempotency_key,
        )

        # Second execution with same idempotency key
        exec2 = await self.service.run_declarative_workflow(
            workflow=workflow,
            approved=True,
            executor=NoOpExecutor(),
            idempotency_key=idempotency_key,
        )

        self.assertEqual(exec1.execution_id, exec2.execution_id)
        self.assertEqual(exec2.idempotency_key, idempotency_key)

    # -----------------------------------------------------------------------
    # Step 6: Step Timeouts and Error Classification
    # -----------------------------------------------------------------------

    async def test_step_timeout_enforcement(self):
        """Validates that a step hanging beyond its timeout is aborted with a timeout message."""
        now_iso = datetime.now(timezone.utc).isoformat()
        slow_workflow = WorkflowDefinition(
            id="wf_timeout_test",
            name="Timeout Workflow",
            version="1.0.0",
            trigger=WorkflowTriggerConfig(type="manual", application="workflow_system"),
            inputs=[],
            variables={},
            steps=[
                WorkflowStep(
                    id="step_slow",
                    name="Slow Action",
                    type="search_customer",
                    application="demo_crm",
                    timeout_seconds=0.1,  # 100ms timeout
                )
            ],
            requires_approval=True,
            created_at=now_iso,
            updated_at=now_iso,
        )

        # Executor hangs for 1.0 second
        slow_executor = MockSlowExecutor(delay_sec=1.0)
        execution = await self.service.run_declarative_workflow(
            workflow=slow_workflow,
            approved=True,
            executor=slow_executor,
        )

        self.assertEqual(execution.status, AutomationStatus.PAUSED)
        self.assertIn("timed out after 0.1s", execution.error)

    async def test_non_retryable_error_aborts_retries_immediately(self):
        """Validates that 401/403/404 or auth/validation errors abort retries without waiting out max_retries."""
        self.assertTrue(is_non_retryable_error("HTTP 401 Unauthorized: token expired"))
        self.assertTrue(is_non_retryable_error("403 Forbidden: insufficient permissions"))
        self.assertTrue(is_non_retryable_error("404 Not Found: customer missing"))
        self.assertTrue(is_non_retryable_error("Validation error: field required"))
        self.assertFalse(is_non_retryable_error("503 Service Unavailable: connection reset"))
        self.assertFalse(is_non_retryable_error("Network timeout while contacting host"))

        now_iso = datetime.now(timezone.utc).isoformat()
        retry_workflow = WorkflowDefinition(
            id="wf_non_retryable_test",
            name="Non Retryable Test",
            version="1.0.0",
            trigger=WorkflowTriggerConfig(type="manual", application="workflow_system"),
            inputs=[],
            variables={},
            steps=[
                WorkflowStep(
                    id="step_auth_fail",
                    name="Auth Failure Step",
                    type="search_customer",
                    application="demo_crm",
                    retry_policy=RetryPolicy(max_retries=5, backoff_seconds=0.1),
                )
            ],
            requires_approval=True,
            created_at=now_iso,
            updated_at=now_iso,
        )

        attempt_counter = 0

        class NonRetryableFailExecutor(ActionExecutor):
            async def execute(self, action, context=None):
                nonlocal attempt_counter
                attempt_counter += 1
                from automation.models import ExecutionActionResult
                return ExecutionActionResult(
                    action_id=action.id,
                    action_type=action.type,
                    success=False,
                    message="401 Unauthorized: Invalid API credentials",
                )

        execution = await self.service.run_declarative_workflow(
            workflow=retry_workflow,
            approved=True,
            executor=NonRetryableFailExecutor(),
        )

        # Max retries was 5 (total 6 attempts), but non-retryable error must abort after 1 attempt!
        self.assertEqual(attempt_counter, 1)
        self.assertEqual(execution.status, AutomationStatus.PAUSED)
        self.assertIn("Non-retryable error detected", execution.step_results[0].logs[-1])

    # -----------------------------------------------------------------------
    # Step 7: State Machine Transitions & Terminal State Protection
    # -----------------------------------------------------------------------

    def test_state_machine_transition_validation(self):
        """Ensures state transitions follow strict state machine rules."""
        # Allowed transitions
        self.assertTrue(is_valid_transition(AutomationStatus.PENDING, AutomationStatus.RUNNING))
        self.assertTrue(is_valid_transition(AutomationStatus.RUNNING, AutomationStatus.PAUSED))
        self.assertTrue(is_valid_transition(AutomationStatus.PAUSED, AutomationStatus.RUNNING))
        self.assertTrue(is_valid_transition(AutomationStatus.RUNNING, AutomationStatus.COMPLETED))
        self.assertTrue(is_valid_transition(AutomationStatus.RUNNING, AutomationStatus.FAILED))
        self.assertTrue(is_valid_transition(AutomationStatus.PAUSED, AutomationStatus.CANCELLED))

        # Terminal state protection (no further transitions allowed)
        self.assertFalse(is_valid_transition(AutomationStatus.COMPLETED, AutomationStatus.RUNNING))
        self.assertFalse(is_valid_transition(AutomationStatus.COMPLETED, AutomationStatus.CANCELLED))
        self.assertFalse(is_valid_transition(AutomationStatus.FAILED, AutomationStatus.RUNNING))
        self.assertFalse(is_valid_transition(AutomationStatus.CANCELLED, AutomationStatus.RUNNING))
        self.assertFalse(is_valid_transition(AutomationStatus.CANCELLED, AutomationStatus.PAUSED))

    async def test_terminal_executions_cannot_be_cancelled_or_resumed(self):
        """Cancelling or resuming a completed or cancelled execution raises InvalidStateTransitionError."""
        workflow = self._create_sample_workflow()
        execution = await self.service.run_declarative_workflow(
            workflow=workflow,
            approved=True,
            executor=NoOpExecutor(),
        )
        self.assertEqual(execution.status, AutomationStatus.COMPLETED)

        # Attempt to cancel completed execution
        with self.assertRaises(InvalidStateTransitionError):
            self.service.cancel_execution(execution.execution_id)

        # Attempt to resume completed execution
        with self.assertRaises(InvalidStateTransitionError):
            await self.service.resume_execution(execution.execution_id)

    # -----------------------------------------------------------------------
    # Step 8: Playwright Browser Lifecycle and Cleanup
    # -----------------------------------------------------------------------

    async def test_playwright_executor_registry_and_shutdown_cleanup(self):
        """Validates that active PlaywrightExecutor instances are tracked and cleaned up on shutdown."""
        executor = PlaywrightExecutor()
        # Mock cleanup
        executor.cleanup = AsyncMock()

        register_active_executor(executor)
        self.assertIn(executor, _active_executors)

        await close_active_executors()
        executor.cleanup.assert_awaited_once()
        self.assertNotIn(executor, _active_executors)

    # -----------------------------------------------------------------------
    # Step 9: Credential Redaction in Execution History
    # -----------------------------------------------------------------------

    async def test_credential_redaction_in_execution_history_and_logs(self):
        """Validates that sensitive tokens, keys, and authorization headers are scrubbed."""
        workflow = self._create_sample_workflow()
        sensitive_inputs = {
            "customer_id": "CUST-999",
            "api_token": "super_secret_bearer_token_xyz123",
            "password": "super_secret_user_password_456",
        }

        execution = await self.service.run_declarative_workflow(
            workflow=workflow,
            approved=True,
            executor=NoOpExecutor(),
            inputs=sensitive_inputs,
        )

        # Verify inputs on execution
        self.assertEqual(execution.inputs.get("api_token"), "[REDACTED]")
        self.assertEqual(execution.inputs.get("password"), "[REDACTED]")
        self.assertEqual(execution.inputs.get("customer_id"), "CUST-999")

        # Verify raw log scrubbing
        log_str = sanitize_log_message("Bearer super_secret_bearer_token_xyz123 was used")
        self.assertNotIn("super_secret_bearer_token_xyz123", log_str)
        self.assertIn("[REDACTED]", log_str)

    # -----------------------------------------------------------------------
    # Step 10: MongoDB Outage Graceful Degradation
    # -----------------------------------------------------------------------

    async def test_mongodb_outage_graceful_degradation(self):
        """Validates that when MongoDB is unreachable, executions still succeed in memory without crashing."""
        workflow = self._create_sample_workflow()

        def broken_db():
            raise ConnectionError("Simulated MongoDB Atlas network outage")

        with patch("backend.database.get_database", side_effect=broken_db):
            execution = await self.service.run_declarative_workflow(
                workflow=workflow,
                approved=True,
                executor=NoOpExecutor(),
            )

        self.assertEqual(execution.status, AutomationStatus.COMPLETED)
        self.assertIn(execution.execution_id, self.service._executions)


if __name__ == "__main__":
    unittest.main()
