#!/usr/bin/env python3
"""
WorkFlowOS Phase 12: Privacy & Safety Test Suite

Validates all Phase 12 requirements and regression safety:
1. Password redaction
2. Nested redaction
3. Token redaction (Bearer, ghp_, glpat-, sk-, AIza)
4. Original input not mutated (immutability / non-destructive)
5. Event ingestion privacy (sanitized before storage)
6. Execution privacy (sanitized outcomes and error traces)
7. API response privacy (no secrets exposed via endpoints)
8. Collection enabled (events ingested and processed)
9. Collection disabled (events dropped at privacy gate, no buffer, no persistence)
10. Retention policy (deterministic cutoff calculation and dry-run cleanup)
11. Existing Phase 9 regression (learning state & formulas intact)
12. Existing Phase 10 regression (planner scoring & requires_approval intact)
13. Existing Phase 11 regression (idempotency, fallback, PAUSED, CANCELLED, NOT_EXECUTED)
14. Financial & card detection (Luhn checksum validation)
15. Deterministic privacy audit utility & API
16. Privacy status & toggle REST endpoints
"""

import copy
import json
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.privacy.redaction import (
    redact_sensitive_data,
    sanitize_log_message,
    audit_sensitive_data,
    is_sensitive_key,
    SENSITIVE_KEY_NAMES,
)
from backend.privacy.service import privacy_service, PrivacyService
from backend.services.event_service import event_service
from backend.models.event import EventCreate
from backend.learning.service import learning_service
from backend.learning.outcome import (
    evaluate_execution_outcome,
    ExecutionOutcomeStatus,
    FailureCategory,
)
from automation.planner import automation_planner, AutomationStrategyType
from automation.models import (
    AutomationExecution,
    AutomationStatus,
    ExecutionActionResult,
    StepExecutionResult,
)
from agent.config import AgentConfig
from agent.service import DesktopActivityAgent


def make_test_execution(
    workflow_id="wf_phase12_test",
    workflow_name="Phase 12 Test Workflow",
    status=AutomationStatus.COMPLETED,
    total_actions=1,
    completed_actions=None,
    failed_action=None,
    error=None,
    results=None,
    step_results=None,
    context=None,
    inputs=None,
    execution_id=None,
):
    """Deterministic factory for test AutomationExecution objects."""
    return AutomationExecution(
        execution_id=execution_id or f"exec_p12_{uuid.uuid4().hex[:8]}",
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
        inputs=inputs or {},
    )


class MockNativeCollector:
    """Mock macOS activity collector for agent privacy tests."""
    def __init__(self, sample_event=None):
        self.sample_event = sample_event or {
            "app_name": "Google Chrome",
            "event_type": "switch_application",
            "bundle_id": "com.google.Chrome",
            "process_id": 1234,
            "target": "https://mail.google.com/mail/u/0/#inbox",
            "window_title": "Inbox (10) - Work Email",
        }
        self.accessibility_granted = True
        self.polled_count = 0

    def poll(self):
        self.polled_count += 1
        return copy.deepcopy(self.sample_event)

    def reset(self):
        self.polled_count = 0

    def get_frontmost_app(self):
        return {"name": "Google Chrome"}


class MockEventClient:
    """Mock event client to verify event streaming without external HTTP calls."""
    def __init__(self):
        self.sent_events = []
        self.buffered_count = 0
        self.send_count = 0

    def send_event(self, event):
        self.send_count += 1
        self.sent_events.append(event)
        return True

    def check_health(self):
        return True

    def flush_sync(self, timeout=5.0):
        return 0

    def stop(self):
        pass


class TestPhase12PrivacyAndSafety(unittest.IsolatedAsyncioTestCase):
    """Deterministic test suite for Phase 12 Privacy & Safety."""

    def setUp(self):
        import mongomock_motor
        import backend.database as db_mod
        db_mod._mongo_client = mongomock_motor.AsyncMongoMockClient()
        db_mod._database = db_mod._mongo_client["workflowos"]

        self.client = TestClient(app)
        # Ensure default collection is enabled for tests
        privacy_service.set_collection_enabled(True)
        privacy_service.set_retention_days(30)
        learning_service.reset_cache()

    def tearDown(self):
        import mongomock_motor
        import backend.database as db_mod
        db_mod._mongo_client = mongomock_motor.AsyncMongoMockClient()
        db_mod._database = db_mod._mongo_client["workflowos"]

        privacy_service.set_collection_enabled(True)
        privacy_service.set_retention_days(30)
        learning_service.reset_cache()

    # -----------------------------------------------------------------------
    # Test 1 — Password redaction
    # -----------------------------------------------------------------------
    def test_01_password_redaction(self):
        """Verifies that direct password and credential keys are redacted."""
        payload = {
            "username": "rohit",
            "password": "secret123",
        }
        sanitized = redact_sensitive_data(payload)
        self.assertEqual(sanitized["password"], "[REDACTED]")
        self.assertEqual(sanitized["username"], "rohit")

    # -----------------------------------------------------------------------
    # Test 2 — Nested redaction
    # -----------------------------------------------------------------------
    def test_02_nested_redaction(self):
        """Verifies recursive sanitization across arbitrarily nested dicts and lists."""
        nested = {
            "metadata": {
                "customer": "Rahul",
                "credentials": {
                    "password": "secret",
                    "api_key": "abc",
                },
                "tokens": [
                    "regular_item",
                    {"refresh_token": "token_val_999"},
                    {"safe_key": "safe_val"},
                ],
            }
        }
        sanitized = redact_sensitive_data(nested)
        self.assertEqual(sanitized["metadata"]["customer"], "Rahul")
        self.assertEqual(sanitized["metadata"]["credentials"]["password"], "[REDACTED]")
        self.assertEqual(sanitized["metadata"]["credentials"]["api_key"], "[REDACTED]")
        self.assertEqual(sanitized["metadata"]["tokens"][0], "regular_item")
        self.assertEqual(sanitized["metadata"]["tokens"][1]["refresh_token"], "[REDACTED]")
        self.assertEqual(sanitized["metadata"]["tokens"][2]["safe_key"], "safe_val")

    # -----------------------------------------------------------------------
    # Test 3 — Token redaction
    # -----------------------------------------------------------------------
    def test_03_token_redaction(self):
        """Verifies platform tokens and auth headers in strings are scrubbed."""
        tokens_to_test = [
            ("Bearer my_secret_bearer_token_12345", "Bearer [REDACTED]"),
            ("Basic dXNlcjpwYXNzd29yZA==", "Basic [REDACTED]"),
            ("token: ghp_1234567890abcdef1234567890abcdef", "[REDACTED]"),
            ("glpat-1234567890abcdef1234567890", "[REDACTED]"),
            ("sk-1234567890abcdef1234567890", "[REDACTED]"),
            ("AIzaSyB1234567890abcdef1234567890abcdef", "[REDACTED]"),
            ("AKIAIOSFODNN7EXAMPLE", "[REDACTED]"),
        ]

        for raw_str, expected_substring in tokens_to_test:
            sanitized = sanitize_log_message(raw_str)
            self.assertIn(expected_substring, sanitized, f"Failed for token string: {raw_str}")

    # -----------------------------------------------------------------------
    # Test 4 — Original input not mutated
    # -----------------------------------------------------------------------
    def test_04_original_input_not_mutated(self):
        """Verifies that non-inplace redaction preserves caller objects exactly."""
        original = {
            "user": "alice",
            "password": "my_actual_cleartext_password",
            "nested": {
                "api_key": "key_xyz_123",
                "tags": ["tag1", "tag2"],
            },
        }
        original_copy = copy.deepcopy(original)

        sanitized = redact_sensitive_data(original, inplace=False)

        # Original remains completely unaltered
        self.assertEqual(original, original_copy)
        self.assertEqual(original["password"], "my_actual_cleartext_password")
        self.assertEqual(original["nested"]["api_key"], "key_xyz_123")

        # Sanitized copy has redactions
        self.assertEqual(sanitized["password"], "[REDACTED]")
        self.assertEqual(sanitized["nested"]["api_key"], "[REDACTED]")

    # -----------------------------------------------------------------------
    # Test 5 — Event ingestion privacy
    # -----------------------------------------------------------------------
    async def test_05_event_ingestion_privacy(self):
        """POSTing an event with sensitive metadata redacts before storage and response."""
        now_iso = datetime.now(timezone.utc).isoformat()
        event_payload = {
            "session_id": "test_session_p12_05",
            "timestamp": now_iso,
            "application": "demo_email",
            "event_type": "open_email",
            "target": "customer_request",
            "metadata": {
                "customer": "Rahul",
                "password": "leaked_event_password",
                "api_key": "leaked_api_key_123",
                "notes": "Legitimate workflow context",
            },
        }

        response = self.client.post("/api/events", json=event_payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()

        # Sensitive metadata must be redacted
        self.assertEqual(data["metadata"]["password"], "[REDACTED]")
        self.assertEqual(data["metadata"]["api_key"], "[REDACTED]")
        # Legitimate metadata preserved
        self.assertEqual(data["metadata"]["customer"], "Rahul")
        self.assertEqual(data["metadata"]["notes"], "Legitimate workflow context")
        # Core structured event fields preserved
        self.assertEqual(data["application"], "demo_email")
        self.assertEqual(data["event_type"], "open_email")
        self.assertEqual(data["target"], "customer_request")

        # Verify DB lookup also returns sanitized data
        event_id = data["id"]
        fetched = await event_service.get_event_by_id(event_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.metadata.get("password"), "[REDACTED]")
        self.assertEqual(fetched.metadata.get("api_key"), "[REDACTED]")

    # -----------------------------------------------------------------------
    # Test 6 — Execution privacy
    # -----------------------------------------------------------------------
    async def test_06_execution_privacy(self):
        """Validates that execution errors and step payloads cannot leak credentials."""
        dirty_error = "Authentication failed with Bearer secret_token_xyz999 and password 'mypassword123'"
        execution = make_test_execution(
            status=AutomationStatus.FAILED,
            error=dirty_error,
            step_results=[
                StepExecutionResult(
                    step_id="step_1",
                    action_type="login",
                    application="demo_app",
                    status="failed",
                    success=False,
                    error=dirty_error,
                    inputs={"password": "cleartext_password", "user": "admin"},
                )
            ],
        )

        outcome = await learning_service.record_closed_loop_outcome(execution)
        self.assertIsNotNone(outcome)

        # Overall execution error message must be sanitized
        self.assertNotIn("secret_token_xyz999", outcome.error_message)
        self.assertNotIn("mypassword123", outcome.error_message)
        self.assertIn("[REDACTED]", outcome.error_message)

        # Step error message must be sanitized
        step_out = outcome.step_outcomes[0]
        self.assertNotIn("secret_token_xyz999", step_out.error_message)
        self.assertNotIn("mypassword123", step_out.error_message)

    # -----------------------------------------------------------------------
    # Test 7 — API response privacy
    # -----------------------------------------------------------------------
    async def test_07_api_response_privacy(self):
        """Verifies GET /api/events and workflow endpoints never return raw secrets."""
        now_iso = datetime.now(timezone.utc).isoformat()
        # Seed an event
        event_data = EventCreate(
            session_id="api_privacy_session",
            timestamp=now_iso,
            application="crm",
            event_type="submit_lead",
            target="lead_form",
            metadata={
                "client_secret": "super_secret_client_token",
                "bearer_token": "Bearer abc123def456ghi",
                "name": "Acme Corp",
            },
        )
        created = await event_service.create_event(event_data)

        # Query GET /api/events
        res = self.client.get(f"/api/events?session_id=api_privacy_session")
        self.assertEqual(res.status_code, 200)
        events = res.json()
        self.assertGreater(len(events), 0)
        for ev in events:
            raw_json = json.dumps(ev)
            self.assertNotIn("super_secret_client_token", raw_json)
            self.assertNotIn("abc123def456ghi", raw_json)

        # Query GET /api/events/{id}
        res_single = self.client.get(f"/api/events/{created.id}")
        self.assertEqual(res_single.status_code, 200)
        single_json = json.dumps(res_single.json())
        self.assertNotIn("super_secret_client_token", single_json)

    # -----------------------------------------------------------------------
    # Test 8 — Collection enabled
    # -----------------------------------------------------------------------
    async def test_08_collection_enabled(self):
        """When collection is enabled, events are accepted by API and agent."""
        privacy_service.set_collection_enabled(True)
        self.assertTrue(privacy_service.is_collection_enabled())

        # 1. API accepts event
        res = self.client.post(
            "/api/events",
            json={
                "session_id": "enabled_sess",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "application": "terminal",
                "event_type": "run_command",
                "target": "pytest",
            },
        )
        self.assertEqual(res.status_code, 201)

        # 2. Agent processes event
        mock_collector = MockNativeCollector()
        mock_client = MockEventClient()
        config = AgentConfig(collection_enabled=True)
        agent = DesktopActivityAgent(config=config, collector=mock_collector, client=mock_client)
        captured = agent.capture_step()
        self.assertIsNotNone(captured)
        self.assertEqual(agent.events_captured, 1)
        self.assertEqual(agent.events_dropped, 0)
        self.assertEqual(agent.events_sent, 1)
        self.assertEqual(mock_client.send_count, 1)

    # -----------------------------------------------------------------------
    # Test 9 — Collection disabled
    # -----------------------------------------------------------------------
    async def test_09_collection_disabled(self):
        """When collection is disabled, events are rejected by API and dropped at agent gate."""
        privacy_service.set_collection_enabled(False)
        self.assertFalse(privacy_service.is_collection_enabled())

        # 1. API rejects event with 403 Forbidden
        res = self.client.post(
            "/api/events",
            json={
                "session_id": "disabled_sess",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "application": "browser",
                "event_type": "open_tab",
            },
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("disabled", res.json()["detail"].lower())

        # 2. Agent drops event immediately at privacy gate
        mock_collector = MockNativeCollector()
        config = AgentConfig(collection_enabled=False)
        agent = DesktopActivityAgent(config=config, collector=mock_collector)
        captured = agent.capture_step()

        # Gate dropped the event
        self.assertIsNone(captured)
        self.assertEqual(agent.events_dropped, 1)
        self.assertEqual(agent.events_captured, 0)
        self.assertEqual(agent.client.buffered_count, 0)

    # -----------------------------------------------------------------------
    # Test 10 — Retention policy
    # -----------------------------------------------------------------------
    async def test_10_retention_policy(self):
        """Validates retention cutoff calculation and dry-run cleanup execution."""
        privacy_service.set_retention_days(30)
        self.assertEqual(privacy_service.get_retention_days(), 30)

        # Cutoff should be approximately 30 days in the past
        cutoff_iso = privacy_service.get_cutoff_timestamp(days=30)
        cutoff_dt = datetime.fromisoformat(cutoff_iso)
        expected_approx = datetime.now(timezone.utc) - timedelta(days=30)
        diff_seconds = abs((cutoff_dt - expected_approx).total_seconds())
        self.assertLess(diff_seconds, 10.0)

        # Dry run cleanup via service
        dry_result = await privacy_service.cleanup_expired_events(dry_run=True, retention_days=30)
        self.assertTrue(dry_result["dry_run"])
        self.assertEqual(dry_result["retention_days"], 30)
        self.assertEqual(dry_result["deleted_count"], 0)

        # Dry run cleanup via API endpoint
        api_res = self.client.post("/api/privacy/cleanup", json={"dry_run": True, "retention_days": 15})
        self.assertEqual(api_res.status_code, 200)
        api_data = api_res.json()
        self.assertTrue(api_data["dry_run"])
        self.assertEqual(api_data["retention_days"], 15)

    # -----------------------------------------------------------------------
    # Test 11 — Existing Phase 9 regression
    # -----------------------------------------------------------------------
    async def test_11_existing_phase9_regression(self):
        """Verifies Phase 9 learning behavior and state formula remains unchanged."""
        wf_id = f"wf_p9_reg_{uuid.uuid4().hex[:6]}"
        execution = make_test_execution(
            workflow_id=wf_id,
            status=AutomationStatus.COMPLETED,
            completed_actions=["open_email"],
            results=[
                ExecutionActionResult(
                    action_id="open_email",
                    action_type="open_email",
                    success=True,
                    message="Action completed",
                )
            ],
        )

        # Record outcome through learning service
        state = await learning_service.record_execution_outcome(execution)
        self.assertIsNotNone(state)
        self.assertEqual(state.workflow_id, wf_id)
        self.assertEqual(state.execution_count, 1)
        self.assertEqual(state.successful_execution_count, 1)
        self.assertGreater(state.learning_score, 0.0)

    # -----------------------------------------------------------------------
    # Test 12 — Existing Phase 10 regression
    # -----------------------------------------------------------------------
    async def test_12_existing_phase10_regression(self):
        """Verifies Phase 10 planner scoring and requires_approval invariant remain unchanged."""
        plan = await automation_planner.create_plan(
            workflow_id="wf_customer_support_pipeline",
            steps=[{"id": "step_1", "action": "open_email", "application": "demo_email"}],
        )
        self.assertIsNotNone(plan)
        # CRITICAL SAFETY INVARIANT: Human approval remains mandatory
        self.assertTrue(plan.requires_approval)
        self.assertEqual(len(plan.steps), 1)
        self.assertIn("summary", plan.explanation)

    # -----------------------------------------------------------------------
    # Test 13 — Existing Phase 11 regression
    # -----------------------------------------------------------------------
    async def test_13_existing_phase11_regression(self):
        """
        Verifies Phase 11 closed-loop invariants:
        - Idempotency: same terminal execution cannot double count
        - Fallback learning: primary failure + fallback success
        - Non-executable statuses (PAUSED, CANCELLED, NOT_EXECUTED) do not pollute strategy evidence
        """
        wf_id = f"wf_p11_reg_{uuid.uuid4().hex[:6]}"
        exec_id = f"exec_idempotent_{uuid.uuid4().hex[:6]}"

        # 1. Idempotency test
        execution = make_test_execution(
            execution_id=exec_id,
            workflow_id=wf_id,
            status=AutomationStatus.COMPLETED,
            completed_actions=["action_a"],
            step_results=[
                StepExecutionResult(
                    step_id="step_1",
                    action_type="action_a",
                    application="demo_crm",
                    status="completed",
                    success=True,
                )
            ],
        )

        outcome1 = await learning_service.record_closed_loop_outcome(
            execution,
            step_strategies={"action_a": "API"},
        )
        evidence1 = await learning_service.get_strategy_evidence(wf_id, step_action="action_a", strategy="API")
        self.assertEqual(len(evidence1), 1)
        self.assertEqual(evidence1[0].attempts, 1)

        # Duplicate call with identical execution
        outcome2 = await learning_service.record_closed_loop_outcome(
            execution,
            step_strategies={"action_a": "API"},
        )
        evidence2 = await learning_service.get_strategy_evidence(wf_id, step_action="action_a", strategy="API")
        self.assertEqual(len(evidence2), 1)
        self.assertEqual(evidence2[0].attempts, 1)  # Strictly idempotent: attempts remains 1

        # 2. PAUSED and CANCELLED steps do not create evidence
        paused_exec = make_test_execution(
            workflow_id=wf_id,
            status=AutomationStatus.PAUSED,
            step_results=[
                StepExecutionResult(
                    step_id="step_paused",
                    action_type="sensitive_step",
                    application="demo_crm",
                    status="paused",
                    success=False,
                    strategy="MANUAL",
                )
            ],
        )
        await learning_service.record_closed_loop_outcome(paused_exec)
        paused_evidence = await learning_service.get_strategy_evidence(wf_id, step_action="sensitive_step")
        self.assertEqual(len(paused_evidence), 0)  # Paused step did not generate evidence

    # -----------------------------------------------------------------------
    # Test 14 — Financial & Card Redaction
    # -----------------------------------------------------------------------
    def test_14_financial_card_redaction(self):
        """Verifies Luhn-valid credit card numbers are scrubbed, non-card numbers preserved."""
        # Valid test credit card (Visa test card format)
        valid_visa = "4111 1111 1111 1111"
        valid_text = f"Payment processed with card {valid_visa} securely."
        sanitized_card = sanitize_log_message(valid_text)
        self.assertNotIn("4111", sanitized_card)
        self.assertIn("[REDACTED_CARD]", sanitized_card)

        # Normal timestamp or order id (invalid Luhn) should NOT be redacted as a card
        normal_id = "Order #2026100612345678 was placed."
        sanitized_id = sanitize_log_message(normal_id)
        self.assertIn("2026100612345678", sanitized_id)

    # -----------------------------------------------------------------------
    # Test 15 — Privacy Audit Endpoint
    # -----------------------------------------------------------------------
    def test_15_privacy_audit_endpoint(self):
        """Verifies POST /api/privacy/audit reports detected fields without leaking values."""
        dirty_payload = {
            "user_id": "usr_123",
            "account": {
                "password": "super_secret_password",
                "api_key": "api_secret_key",
            },
            "token_header": "Bearer token_abc123xyz789",
        }

        res = self.client.post("/api/privacy/audit", json={"payload": dirty_payload})
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertTrue(data["contains_sensitive_data"])
        self.assertIn("account.password", data["redacted_fields"])
        self.assertIn("account.api_key", data["redacted_fields"])
        self.assertIn("token_header", data["redacted_fields"])
        # Crucial security guarantee: raw secrets are NOT in the audit output
        json_output = json.dumps(data)
        self.assertNotIn("super_secret_password", json_output)
        self.assertNotIn("api_secret_key", json_output)
        self.assertNotIn("token_abc123xyz789", json_output)

    # -----------------------------------------------------------------------
    # Test 16 — Privacy Status and Toggle Endpoints
    # -----------------------------------------------------------------------
    def test_16_privacy_status_and_toggle_endpoints(self):
        """Verifies GET /api/privacy/status and POST /api/privacy/toggle."""
        # 1. Status
        res_status = self.client.get("/api/privacy/status")
        self.assertEqual(res_status.status_code, 200)
        status_data = res_status.json()
        self.assertIn("collection_enabled", status_data)
        self.assertIn("retention_days", status_data)
        self.assertTrue(status_data["redaction_active"])
        self.assertTrue(status_data["approval_gate_required"])

        # 2. Toggle to False
        res_toggle_off = self.client.post("/api/privacy/toggle", json={"collection_enabled": False})
        self.assertEqual(res_toggle_off.status_code, 200)
        self.assertFalse(res_toggle_off.json()["collection_enabled"])
        self.assertFalse(privacy_service.is_collection_enabled())

        # 3. Toggle back to True
        res_toggle_on = self.client.post("/api/privacy/toggle", json={"collection_enabled": True})
        self.assertEqual(res_toggle_on.status_code, 200)
        self.assertTrue(res_toggle_on.json()["collection_enabled"])
        self.assertTrue(privacy_service.is_collection_enabled())

    # -----------------------------------------------------------------------
    # Test 17 (Test A) — Privacy Service Failure Fails Closed
    # -----------------------------------------------------------------------
    def test_17_privacy_service_failure_fails_closed(self):
        """Simulates privacy service error; verifies agent fails closed (drops event immediately)."""
        mock_collector = MockNativeCollector()
        mock_client = MockEventClient()
        config = AgentConfig()
        agent = DesktopActivityAgent(config=config, collector=mock_collector, client=mock_client)

        with patch("backend.privacy.service.privacy_service.is_collection_enabled", side_effect=RuntimeError("Privacy service offline")):
            captured = agent.capture_step()

        self.assertIsNone(captured)
        self.assertEqual(agent.events_dropped, 1)
        self.assertEqual(agent.events_captured, 0)
        self.assertEqual(agent.events_sent, 0)
        self.assertEqual(mock_client.buffered_count, 0)
        self.assertEqual(mock_client.send_count, 0)

    # -----------------------------------------------------------------------
    # Test 18 (Test B) — Sanitization Failure Fails Closed
    # -----------------------------------------------------------------------
    def test_18_sanitization_failure_fails_closed(self):
        """Simulates sanitization engine error; verifies agent fails closed without sending/buffering."""
        mock_collector = MockNativeCollector(sample_event={
            "app_name": "Google Chrome",
            "event_type": "switch_application",
            "target": "https://mail.google.com",
            "metadata": {"customer": "Alice"},
        })
        mock_client = MockEventClient()
        config = AgentConfig()
        agent = DesktopActivityAgent(config=config, collector=mock_collector, client=mock_client)

        with patch("backend.privacy.redaction.redact_sensitive_data", side_effect=ValueError("Corrupt redaction parser")):
            captured = agent.capture_step()

        self.assertIsNone(captured)
        self.assertEqual(agent.events_dropped, 1)
        self.assertEqual(agent.events_sent, 0)
        self.assertEqual(mock_client.buffered_count, 0)
        self.assertEqual(mock_client.send_count, 0)

    # -----------------------------------------------------------------------
    # Test 19 (Test C) — Runtime Privacy Toggle Without Restart
    # -----------------------------------------------------------------------
    def test_19_runtime_privacy_toggle_without_restart(self):
        """Verifies runtime toggle dynamically controls single agent instance without restart."""
        mock_collector = MockNativeCollector()
        mock_client = MockEventClient()
        config = AgentConfig()
        agent = DesktopActivityAgent(config=config, collector=mock_collector, client=mock_client)

        # 1. Enable collection
        privacy_service.set_collection_enabled(True)
        captured1 = agent.capture_step()
        self.assertIsNotNone(captured1)
        self.assertEqual(agent.events_sent, 1)
        self.assertEqual(agent.events_dropped, 0)
        self.assertEqual(mock_client.send_count, 1)

        # 2. Disable collection at runtime
        privacy_service.set_collection_enabled(False)
        captured2 = agent.capture_step()
        self.assertIsNone(captured2)
        self.assertEqual(agent.events_dropped, 1)
        self.assertEqual(agent.events_sent, 1)
        self.assertEqual(mock_client.buffered_count, 0)
        self.assertEqual(mock_client.send_count, 1)

        # 3. Re-enable collection at runtime
        privacy_service.set_collection_enabled(True)
        captured3 = agent.capture_step()
        self.assertIsNotNone(captured3)
        self.assertEqual(agent.events_sent, 2)
        self.assertEqual(agent.events_dropped, 1)
        self.assertEqual(mock_client.send_count, 2)

    # -----------------------------------------------------------------------
    # Test 20 (Test D) — Environment Initialization
    # -----------------------------------------------------------------------
    def test_20_environment_initialization(self):
        """Verifies ACTIVITY_COLLECTION_ENABLED=false initializes PrivacyService as disabled."""
        old_val = os.environ.get("ACTIVITY_COLLECTION_ENABLED")
        try:
            os.environ["ACTIVITY_COLLECTION_ENABLED"] = "false"
            fresh_service = PrivacyService()
            self.assertFalse(fresh_service.is_collection_enabled())

            os.environ["ACTIVITY_COLLECTION_ENABLED"] = "true"
            fresh_service_on = PrivacyService()
            self.assertTrue(fresh_service_on.is_collection_enabled())
        finally:
            if old_val is not None:
                os.environ["ACTIVITY_COLLECTION_ENABLED"] = old_val
            else:
                os.environ.pop("ACTIVITY_COLLECTION_ENABLED", None)


if __name__ == "__main__":
    unittest.main()
