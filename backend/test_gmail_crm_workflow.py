#!/usr/bin/env python3
"""
WorkFlowOS — Test Suite for Real Gmail → CRM → Chat Chained Workflow

Validates all 12 requirements (A through L):
A. Six-step workflow structure
B. Template interpolation between every step (End-to-End Execution)
C. Gmail sender → CRM exact email matching
D. Gmail sender → CRM normalized name matching
E. CRM not found → PAUSED
F. update_customer is not executed when customer is absent
G. send_message is not executed when customer is absent
H. integration workflow automatically selects IntegrationExecutor
I. approval still required for CRM update
J. approval still required for chat notification
K. existing Playwright workflows remain unaffected
L. existing test suite regression safety
"""

import copy
import unittest
from unittest.mock import AsyncMock, patch

from automation.models import (
    AutomationStatus,
    WorkflowDefinition,
)
from automation.planner import automation_planner
from automation.service import automation_service
from integrations.base import IntegrationStatus
from integrations.crm import CrmIntegrationAdapter
from integrations.chat import ChatIntegrationAdapter
from integrations.registry import integration_registry


class TestGmailCrmWorkflow(unittest.IsolatedAsyncioTestCase):
    """Comprehensive test suite for the Gmail → CRM → Chat triage workflow."""

    def setUp(self):
        # Reset CRM and Chat seed data before each test
        crm_adapter = integration_registry.get("crm")
        if isinstance(crm_adapter, CrmIntegrationAdapter):
            crm_adapter.reset_seed_data()

        chat_adapter = integration_registry.get("chat")
        if isinstance(chat_adapter, ChatIntegrationAdapter):
            chat_adapter.reset_seed_data()

    # ── Test A: Six-step workflow structure ──────────────────────────────────
    async def test_a_six_step_workflow_structure(self):
        """Validates that wf_gmail_triage_pipeline declares exactly the 6 required steps."""
        wf = automation_service.get_workflow("wf_gmail_triage_pipeline")
        self.assertIsNotNone(wf, "wf_gmail_triage_pipeline must be registered")
        self.assertEqual(len(wf.steps), 6, "Workflow must declare exactly 6 steps")

        expected_steps = [
            ("step_search_email", "search_messages", "gmail"),
            ("step_read_email", "read_message", "gmail"),
            ("step_download_attachment", "download_attachment", "gmail"),
            ("step_search_crm", "search_customer", "crm"),
            ("step_update_crm", "update_customer", "crm"),
            ("step_send_chat", "send_message", "chat"),
        ]

        for idx, (exp_id, exp_type, exp_app) in enumerate(expected_steps):
            step = wf.steps[idx]
            self.assertEqual(step.id, exp_id, f"Step {idx+1} ID mismatch")
            self.assertEqual(step.type, exp_type, f"Step {idx+1} type mismatch")
            self.assertEqual(step.application, exp_app, f"Step {idx+1} application mismatch")

        self.assertTrue(wf.requires_approval, "Workflow must require approval")

    # ── Test B: Template interpolation between every step ───────────────────
    async def test_b_template_interpolation_end_to_end(self):
        """
        Executes wf_gmail_triage_pipeline end-to-end and validates that
        data flows and interpolates accurately between all 6 steps.
        """
        wf = automation_service.get_workflow("wf_gmail_triage_pipeline")
        gmail_adapter = integration_registry.get("gmail")

        mock_search_res = {
            "service": "gmail",
            "action": "search_messages",
            "count": 1,
            "query": "has:attachment",
            "messages": [
                {
                    "id": "msg_invoice_101",
                    "thread_id": "thread_101",
                    "subject": "Monthly Services Invoice",
                    "from": "Rahul Sharma <rohit9.mwsp@gmail.com>",
                }
            ],
        }

        mock_read_res = {
            "service": "gmail",
            "action": "read_message",
            "id": "msg_invoice_101",
            "thread_id": "thread_101",
            "from": "Rahul Sharma <rohit9.mwsp@gmail.com>",
            "subject": "Monthly Services Invoice",
            "date": "2026-10-08T10:00:00Z",
            "snippet": "Attached is the monthly invoice for review.",
            "attachments": [
                {
                    "attachment_id": "att_inv_5544",
                    "filename": "invoice_october.pdf",
                    "size_bytes": 10420,
                    "mime_type": "application/pdf",
                }
            ],
        }

        mock_download_res = {
            "service": "gmail",
            "action": "download_attachment",
            "message_id": "msg_invoice_101",
            "attachment_id": "att_inv_5544",
            "filename": "invoice_october.pdf",
            "size_bytes": 10420,
            "sha256": "a1b2c3d4e5f67890123456789abcdef0",
            "status": "downloaded",
        }

        mock_search = AsyncMock(return_value=mock_search_res)
        mock_read = AsyncMock(return_value=mock_read_res)
        mock_dl = AsyncMock(return_value=mock_download_res)

        with patch.object(gmail_adapter, "_status", IntegrationStatus.CONNECTED), \
             patch.dict(gmail_adapter._handlers, {
                 "search_messages": mock_search,
                 "read_message": mock_read,
                 "download_attachment": mock_dl,
             }):

            execution = await automation_service.run_declarative_workflow(
                workflow=wf,
                approved=True,
            )

            self.assertEqual(execution.status, AutomationStatus.COMPLETED)
            self.assertEqual(len(execution.completed_actions), 6)

            # Step 1: search_messages was called with query filter
            mock_search.assert_called_once()

            # Step 2: read_message received the interpolated message_id from step 1
            mock_read.assert_called_once()
            read_call_params = mock_read.call_args[1]["parameters"]
            self.assertEqual(read_call_params.get("message_id"), "msg_invoice_101")

            # Step 3: download_attachment received interpolated message_id and attachment_id
            mock_dl.assert_called_once()
            dl_call_params = mock_dl.call_args[1]["parameters"]
            self.assertEqual(dl_call_params.get("message_id"), "msg_invoice_101")
            self.assertEqual(dl_call_params.get("attachment_id"), "att_inv_5544")
            self.assertEqual(dl_call_params.get("filename"), "invoice_october.pdf")

            # Step 4: CRM search matched Rahul Sharma
            crm_adapter = integration_registry.get("crm")
            customer_record = crm_adapter._find_customer("rohit9.mwsp@gmail.com")
            self.assertIsNotNone(customer_record)

            # Step 5: CRM update updated Rahul's record with the attachment hash and status
            self.assertEqual(customer_record.get("status"), "Verified")
            self.assertIn("invoice_october.pdf", customer_record.get("notes", ""))
            self.assertIn("a1b2c3d4e5f67890123456789abcdef0", customer_record.get("notes", ""))

            # Step 6: Chat sent notification with interpolated sender, filename, and CRM status
            chat_adapter = integration_registry.get("chat")
            last_chat = chat_adapter._messages[-1]
            self.assertEqual(last_chat["channel"], "general")
            self.assertIn("Rahul Sharma <rohit9.mwsp@gmail.com>", last_chat["message"])
            self.assertIn("invoice_october.pdf", last_chat["message"])
            self.assertIn("Verified", last_chat["message"])

    # ── Test C: Gmail sender → CRM exact email matching ─────────────────────
    async def test_c_gmail_sender_exact_email_matching(self):
        """Validates that a Gmail From header matches CRM customer by exact normalized email."""
        crm = integration_registry.get("crm")

        # 1. From header with full format
        cust1 = crm._find_customer("Rahul Sharma <rohit9.mwsp@gmail.com>")
        self.assertIsNotNone(cust1)
        self.assertEqual(cust1["id"], "cust_rahul_01")

        # 2. Raw email string
        cust2 = crm._find_customer("alice.smith@example.com")
        self.assertIsNotNone(cust2)
        self.assertEqual(cust2["id"], "cust_alice_02")

        # 3. Uppercase email with angle brackets
        cust3 = crm._find_customer("<ROHIT9.MWSP@GMAIL.COM>")
        self.assertIsNotNone(cust3)
        self.assertEqual(cust3["id"], "cust_rahul_01")

    # ── Test D: Gmail sender → CRM normalized name matching ─────────────────
    async def test_d_gmail_sender_normalized_name_matching(self):
        """Validates that a Gmail From header matches CRM customer by normalized name."""
        crm = integration_registry.get("crm")

        # 1. Exact full name
        cust1 = crm._find_customer("Rahul Sharma")
        self.assertIsNotNone(cust1)
        self.assertEqual(cust1["id"], "cust_rahul_01")

        # 2. Name with unmatched email
        cust2 = crm._find_customer("Alice Smith <alternate_work_email@corporate.net>")
        self.assertIsNotNone(cust2)
        self.assertEqual(cust2["id"], "cust_alice_02")

        # 3. Quoted name in header
        cust3 = crm._find_customer('"Rahul Sharma" <unmatched@corp.io>')
        self.assertIsNotNone(cust3)
        self.assertEqual(cust3["id"], "cust_rahul_01")

    # ── Test E: CRM not found → PAUSED ──────────────────────────────────────
    async def test_e_crm_not_found_pauses_workflow(self):
        """
        When the email sender is not found in the CRM, search_customer must fail,
        transitioning the workflow into PAUSED status with human intervention required.
        """
        wf = automation_service.get_workflow("wf_gmail_triage_pipeline")
        gmail_adapter = integration_registry.get("gmail")

        mock_search_res = {
            "service": "gmail",
            "action": "search_messages",
            "count": 1,
            "query": "has:attachment",
            "messages": [{"id": "msg_stranger_01", "thread_id": "thread_01"}],
        }

        mock_read_res = {
            "service": "gmail",
            "action": "read_message",
            "id": "msg_stranger_01",
            "from": "Unknown Stranger <stranger@unregistered-company.com>",
            "subject": "Inquiry from non-customer",
            "attachments": [
                {
                    "attachment_id": "att_stranger_11",
                    "filename": "proposal.pdf",
                    "size_bytes": 1024,
                }
            ],
        }

        mock_download_res = {
            "service": "gmail",
            "action": "download_attachment",
            "message_id": "msg_stranger_01",
            "attachment_id": "att_stranger_11",
            "filename": "proposal.pdf",
            "size_bytes": 1024,
            "sha256": "hash_proposal_123",
            "status": "downloaded",
        }

        with patch.object(gmail_adapter, "_status", IntegrationStatus.CONNECTED), \
             patch.dict(gmail_adapter._handlers, {
                 "search_messages": AsyncMock(return_value=mock_search_res),
                 "read_message": AsyncMock(return_value=mock_read_res),
                 "download_attachment": AsyncMock(return_value=mock_download_res),
             }):

            execution = await automation_service.run_declarative_workflow(
                workflow=wf,
                approved=True,
            )

            # Workflow must PAUSE rather than fail completely or succeed
            self.assertEqual(execution.status, AutomationStatus.PAUSED)
            self.assertTrue(execution.requires_human_intervention)
            self.assertTrue(execution.resume_available)
            self.assertEqual(execution.failed_action, "search_customer")
            self.assertEqual(execution.step_results[-1].step_id, "step_search_crm")
            self.assertIn("not found in CRM", execution.failure_reason or "")

    # ── Test F: update_customer is not executed when customer is absent ──────
    async def test_f_update_customer_not_executed_when_customer_absent(self):
        """Confirms that update_customer is never reached when search_customer fails."""
        wf = automation_service.get_workflow("wf_gmail_triage_pipeline")
        gmail_adapter = integration_registry.get("gmail")

        mock_search_res = {
            "service": "gmail",
            "action": "search_messages",
            "count": 1,
            "query": "has:attachment",
            "messages": [{"id": "msg_stranger_02", "thread_id": "thread_02"}],
        }
        mock_read_res = {
            "service": "gmail",
            "action": "read_message",
            "id": "msg_stranger_02",
            "from": "NonExistent User <nobody@nowhere.com>",
            "attachments": [{"attachment_id": "att_2", "filename": "doc.pdf", "size_bytes": 500}],
        }
        mock_download_res = {
            "service": "gmail",
            "action": "download_attachment",
            "message_id": "msg_stranger_02",
            "attachment_id": "att_2",
            "filename": "doc.pdf",
            "size_bytes": 500,
            "sha256": "hash500",
            "status": "downloaded",
        }

        with patch.object(gmail_adapter, "_status", IntegrationStatus.CONNECTED), \
             patch.dict(gmail_adapter._handlers, {
                 "search_messages": AsyncMock(return_value=mock_search_res),
                 "read_message": AsyncMock(return_value=mock_read_res),
                 "download_attachment": AsyncMock(return_value=mock_download_res),
             }):

            crm = integration_registry.get("crm")
            customer_count_before = len(crm._customers)

            execution = await automation_service.run_declarative_workflow(
                workflow=wf,
                approved=True,
            )

            # Verify update_customer was NOT executed
            self.assertNotIn("update_customer", execution.completed_actions)
            # Verify NO new customer was auto-created
            self.assertEqual(len(crm._customers), customer_count_before)

            # Direct test of update_customer with invalid customer ID
            upd_res = await crm.execute_action("update_customer", {
                "customer_id": "cust_ghost_999",
                "status": "Verified",
            })
            self.assertFalse(upd_res.success)
            self.assertIn("not found in CRM", upd_res.message)
            self.assertEqual(len(crm._customers), customer_count_before)

    # ── Test G: send_message is not executed when customer is absent ────────
    async def test_g_send_message_not_executed_when_customer_absent(self):
        """Confirms that send_message is never reached when search_customer fails."""
        wf = automation_service.get_workflow("wf_gmail_triage_pipeline")
        gmail_adapter = integration_registry.get("gmail")

        mock_search_res = {
            "service": "gmail",
            "action": "search_messages",
            "count": 1,
            "query": "has:attachment",
            "messages": [{"id": "msg_stranger_03", "thread_id": "thread_03"}],
        }
        mock_read_res = {
            "service": "gmail",
            "action": "read_message",
            "id": "msg_stranger_03",
            "from": "Unknown Contact <ghost@void.org>",
            "attachments": [{"attachment_id": "att_3", "filename": "x.pdf", "size_bytes": 100}],
        }
        mock_download_res = {
            "service": "gmail",
            "action": "download_attachment",
            "message_id": "msg_stranger_03",
            "attachment_id": "att_3",
            "filename": "x.pdf",
            "size_bytes": 100,
            "sha256": "hash100",
            "status": "downloaded",
        }

        with patch.object(gmail_adapter, "_status", IntegrationStatus.CONNECTED), \
             patch.dict(gmail_adapter._handlers, {
                 "search_messages": AsyncMock(return_value=mock_search_res),
                 "read_message": AsyncMock(return_value=mock_read_res),
                 "download_attachment": AsyncMock(return_value=mock_download_res),
             }):

            chat = integration_registry.get("chat")
            chat_msg_count_before = len(chat._messages)

            execution = await automation_service.run_declarative_workflow(
                workflow=wf,
                approved=True,
            )

            # Verify send_message was NOT executed
            self.assertNotIn("send_message", execution.completed_actions)
            # Verify no chat messages were posted
            self.assertEqual(len(chat._messages), chat_msg_count_before)

    # ── Test H: integration workflow automatically selects IntegrationExecutor
    async def test_h_integration_workflow_automatically_selects_integration_executor(self):
        """
        Validates that when an all-integration workflow is executed without an executor,
        AutomationService automatically selects IntegrationExecutor even if default
        executor_type is 'playwright' or omitted.
        """
        wf = automation_service.get_workflow("wf_gmail_triage_pipeline")
        self.assertTrue(automation_service._is_all_integrations_workflow(workflow=wf))

        # 1. executor_type=None
        with patch.object(automation_service._engine, "execute_declarative_workflow", new=AsyncMock()) as mock_exec:
            from automation.models import AutomationExecution
            mock_exec.return_value = AutomationExecution(
                execution_id="exec_test_h1",
                workflow_id=wf.id,
                workflow_name=wf.name,
                status=AutomationStatus.COMPLETED,
            )

            res = await automation_service.run_declarative_workflow(
                workflow=wf,
                approved=True,
                executor=None,
                executor_type=None,
            )
            self.assertEqual(res.executor_type, "integration")
            # Verify the executor passed into engine was IntegrationExecutor
            called_executor = mock_exec.call_args[1]["executor"]
            from integrations.executor import IntegrationExecutor
            self.assertIsInstance(called_executor, IntegrationExecutor)

        # 2. executor_type="playwright" (e.g. from API default)
        with patch.object(automation_service._engine, "execute_declarative_workflow", new=AsyncMock()) as mock_exec:
            mock_exec.return_value = AutomationExecution(
                execution_id="exec_test_h2",
                workflow_id=wf.id,
                workflow_name=wf.name,
                status=AutomationStatus.COMPLETED,
            )

            res = await automation_service.run_declarative_workflow(
                workflow=wf,
                approved=True,
                executor=None,
                executor_type="playwright",
            )
            self.assertEqual(res.executor_type, "integration")
            called_executor = mock_exec.call_args[1]["executor"]
            self.assertIsInstance(called_executor, IntegrationExecutor)

    # ── Test I: approval still required for CRM update ──────────────────────
    async def test_i_approval_still_required_for_crm_update(self):
        """Ensures that update_customer remains marked as mutating and requires approval."""
        crm = integration_registry.get("crm")
        act_def = crm.get_action("update_customer")
        self.assertIsNotNone(act_def)
        self.assertTrue(act_def.requires_approval, "CRM update_customer must require human approval")
        self.assertTrue(act_def.is_mutating, "CRM update_customer must be classified as mutating")

        # Calling workflow with approved=False must halt with PENDING
        wf = automation_service.get_workflow("wf_gmail_triage_pipeline")
        execution = await automation_service.run_declarative_workflow(
            workflow=wf,
            approved=False,
        )
        self.assertEqual(execution.status, AutomationStatus.PENDING)
        self.assertEqual(len(execution.completed_actions), 0)

    # ── Test J: approval still required for chat notification ───────────────
    async def test_j_approval_still_required_for_chat_notification(self):
        """Ensures that chat send_message remains marked as mutating and requires approval."""
        chat = integration_registry.get("chat")
        act_def = chat.get_action("send_message")
        self.assertIsNotNone(act_def)
        self.assertTrue(act_def.requires_approval, "Chat send_message must require human approval")
        self.assertTrue(act_def.is_mutating, "Chat send_message must be classified as mutating")

    # ── Test K: existing Playwright workflows remain unaffected ─────────────
    async def test_k_existing_playwright_workflows_remain_unaffected(self):
        """
        Confirms that browser workflows (such as wf_customer_support_pipeline)
        continue using PlaywrightExecutor and are NOT classified as pure integration workflows.
        """
        browser_wf = automation_service.get_workflow("wf_customer_support_pipeline")
        self.assertIsNotNone(browser_wf)

        # Because browser_wf uses demo_email (which is not an integration adapter),
        # _is_all_integrations_workflow must evaluate to False.
        self.assertFalse(automation_service._is_all_integrations_workflow(workflow=browser_wf))

        # Check executor resolution
        with patch.object(automation_service._engine, "execute_declarative_workflow", new=AsyncMock()) as mock_exec:
            from automation.models import AutomationExecution
            mock_exec.return_value = AutomationExecution(
                execution_id="exec_test_k",
                workflow_id=browser_wf.id,
                workflow_name=browser_wf.name,
                status=AutomationStatus.COMPLETED,
            )

            res = await automation_service.run_declarative_workflow(
                workflow=browser_wf,
                approved=True,
                executor=None,
                executor_type="playwright",
            )
            self.assertEqual(res.executor_type, "playwright")
            called_executor = mock_exec.call_args[1]["executor"]
            from automation.playwright_executor import PlaywrightExecutor
            self.assertIsInstance(called_executor, PlaywrightExecutor)

    # ── Test L: Planner generates 6 steps for triage pipeline ────────────────
    async def test_l_planner_creates_plan_for_all_six_steps(self):
        """Validates that the Intelligent Automation Planner plans all 6 steps with INTEGRATION strategy."""
        plan = await automation_planner.create_plan("wf_gmail_triage_pipeline")
        self.assertEqual(len(plan.steps), 6)
        expected_types = [
            "search_messages",
            "read_message",
            "download_attachment",
            "search_customer",
            "update_customer",
            "send_message",
        ]
        actual_types = [s.action for s in plan.steps]
        self.assertEqual(actual_types, expected_types)
        self.assertTrue(plan.requires_approval)


if __name__ == "__main__":
    unittest.main()
