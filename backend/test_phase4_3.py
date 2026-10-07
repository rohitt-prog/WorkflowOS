"""
Phase 4.3 Integration Tests — PlaywrightExecutor

PREREQUISITES:
  - Frontend must be running at http://localhost:3000 (cd frontend && npm run dev)
  - Playwright Chromium must be installed (.venv/bin/playwright install chromium)
  - Python venv must be active (.venv)

Run with:
  .venv/bin/python backend/test_phase4_3.py

Tests do NOT require the FastAPI backend to be running.
Tests do NOT connect to real Gmail, Slack, Salesforce, or any external SaaS.
"""

import asyncio
import sys
import os
import unittest

# ─── Path Setup ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.models import WorkflowProposal, WorkflowAction, WorkflowTrigger
from automation.engine import AutomationEngine
from automation.executor import NoOpExecutor
from automation.models import AutomationStatus, AutomationAction
from automation.playwright_executor import PlaywrightExecutor, PLAYWRIGHT_SUPPORTED_ACTIONS

FRONTEND_BASE_URL = os.getenv("PLAYWRIGHT_BASE_URL", "http://localhost:3000")

APP_MAP = {
    "open_email": "demo_email",
    "download_attachment": "demo_email",
    "search_customer": "demo_crm",
    "update_customer": "demo_crm",
    "send_message": "demo_chat",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_automation_action(action_type: str, target: str = "customer_request", params: dict = None) -> AutomationAction:
    """Creates AutomationAction for direct executor.execute() calls (has id + parameters)."""
    return AutomationAction(
        id=f"act_test_{action_type}",
        type=action_type,
        application=APP_MAP.get(action_type, "demo_app"),
        description=f"Phase 4.3 test: {action_type}",
        target=target,
        parameters=params or {},
    )


def make_proposal(action_types=None, customer_name="Rahul") -> WorkflowProposal:
    """Creates WorkflowProposal for full engine.execute_workflow() tests."""
    if action_types is None:
        action_types = ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"]
    actions = []
    for at in action_types:
        target = customer_name if at in ("search_customer", "update_customer") else "customer_request"
        actions.append(WorkflowAction(
            type=at,
            application=APP_MAP.get(at, "demo_app"),
            description=f"Phase 4.3 test: {at}",
            target=target,
        ))

    return WorkflowProposal(
        name="Process Customer Request (Phase 4.3 Test)",
        intent="Automate customer email attachment processing and CRM update",
        trigger=WorkflowTrigger(
            type="new_email",
            application="demo_email",
            description="Email received from customer"
        ),
        actions=actions,
        variables=["customer_name", "attachment"],
        applications=["demo_email", "demo_crm", "demo_chat"],
        requires_approval=True
    )


def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ─── Test Class ───────────────────────────────────────────────────────────────

class TestPhase43PlaywrightExecutor(unittest.TestCase):
    """
    Phase 4.3 integration tests.

    IMPORTANT: Tests in this class perform REAL browser automation via Playwright.
    They require the frontend to be running at PLAYWRIGHT_BASE_URL.
    No actual emails, CRM, or SaaS services are used — only local demo applications.
    """

    def setUp(self):
        """Verify frontend is reachable before each test."""
        import urllib.request
        try:
            urllib.request.urlopen(f"{FRONTEND_BASE_URL}/demo/email", timeout=3)
        except Exception:
            self.skipTest(
                f"Frontend not reachable at {FRONTEND_BASE_URL}. "
                "Please run: cd frontend && npm run dev"
            )

    # ── Test 1: Constructor ────────────────────────────────────────────────────

    def test_01_playwright_executor_can_be_constructed(self):
        """PlaywrightExecutor can be instantiated with and without explicit config."""
        ex = PlaywrightExecutor(base_url=FRONTEND_BASE_URL, headless=True)
        self.assertIsNotNone(ex)
        self.assertEqual(ex.base_url, FRONTEND_BASE_URL.rstrip("/"))
        self.assertTrue(ex.headless)
        self.assertFalse(ex.is_running)
        print("  ✓ PlaywrightExecutor constructed with correct configuration.")

    # ── Test 2: Base URLs ─────────────────────────────────────────────────────

    def test_02_correct_demo_base_urls_are_generated(self):
        """Correct demo route URLs are built from base URL."""
        ex = PlaywrightExecutor(base_url="http://localhost:3000/", headless=True)
        self.assertEqual(ex.email_url, "http://localhost:3000/demo/email")
        self.assertEqual(ex.crm_url, "http://localhost:3000/demo/crm")
        self.assertEqual(ex.chat_url, "http://localhost:3000/demo/chat")
        print("  ✓ Demo route URLs generated correctly from base_url.")

    # ── Test 3: open_email ────────────────────────────────────────────────────

    def test_03_open_email_succeeds(self):
        """open_email navigates to /demo/email and opens the Rahul email."""
        async def run():
            async with PlaywrightExecutor(base_url=FRONTEND_BASE_URL, headless=True) as ex:
                action = make_automation_action("open_email")
                result = await ex.execute(action)
                self.assertTrue(result.success, f"open_email failed: {result.message}")
                self.assertEqual(result.action_type, "open_email")
                print(f"  ✓ open_email: {result.message}")

        run_async(run())

    # ── Test 4: download_attachment ───────────────────────────────────────────

    def test_04_download_attachment_succeeds(self):
        """download_attachment clicks the download button and verifies confirmation."""
        async def run():
            async with PlaywrightExecutor(base_url=FRONTEND_BASE_URL, headless=True) as ex:
                # First open the email so attachment is visible
                open_action = make_automation_action("open_email")
                await ex.execute(open_action)

                # Then download
                download_action = make_automation_action("download_attachment")
                result = await ex.execute(download_action)
                self.assertTrue(result.success, f"download_attachment failed: {result.message}")
                self.assertEqual(result.action_type, "download_attachment")
                print(f"  ✓ download_attachment: {result.message}")

        run_async(run())

    # ── Test 5: search_customer (Rahul) ───────────────────────────────────────

    def test_05_search_customer_rahul_succeeds(self):
        """search_customer finds Rahul in the demo CRM."""
        async def run():
            async with PlaywrightExecutor(base_url=FRONTEND_BASE_URL, headless=True) as ex:
                action = make_automation_action("search_customer", target="Rahul")
                result = await ex.execute(action)
                self.assertTrue(result.success, f"search_customer failed: {result.message}")
                self.assertIn("Rahul", result.message)
                print(f"  ✓ search_customer: {result.message}")

        run_async(run())

    # ── Test 6: update_customer ───────────────────────────────────────────────

    def test_06_update_customer_succeeds(self):
        """update_customer updates notes and verifies 'Customer updated' confirmation."""
        async def run():
            async with PlaywrightExecutor(base_url=FRONTEND_BASE_URL, headless=True) as ex:
                # Search first so customer profile is loaded
                search_action = make_automation_action("search_customer", target="Rahul")
                await ex.execute(search_action)

                update_action = make_automation_action("update_customer", target="customer")
                result = await ex.execute(update_action)
                self.assertTrue(result.success, f"update_customer failed: {result.message}")
                print(f"  ✓ update_customer: {result.message}")

        run_async(run())

    # ── Test 7: send_message ──────────────────────────────────────────────────

    def test_07_send_message_succeeds(self):
        """send_message sends to the chat channel and verifies 'Message sent' status."""
        async def run():
            async with PlaywrightExecutor(base_url=FRONTEND_BASE_URL, headless=True) as ex:
                action = make_automation_action("send_message", target="#customer-support")
                result = await ex.execute(action)
                self.assertTrue(result.success, f"send_message failed: {result.message}")
                print(f"  ✓ send_message: {result.message}")

        run_async(run())

    # ── Test 8: Full 5-action happy path ──────────────────────────────────────

    def test_08_full_five_action_workflow_completes(self):
        """
        Full happy-path end-to-end: open_email → download_attachment → search_customer
        → update_customer → send_message completes with status=completed.
        """
        proposal = make_proposal()
        engine = AutomationEngine()
        executor = PlaywrightExecutor(base_url=FRONTEND_BASE_URL, headless=True)

        async def run():
            execution = await engine.execute_workflow(
                proposal=proposal,
                approved=True,
                executor=executor,
            )
            return execution

        execution = run_async(run())

        self.assertEqual(execution.status, AutomationStatus.COMPLETED,
            f"Expected COMPLETED, got {execution.status}. Error: {execution.error}")
        self.assertEqual(
            execution.completed_actions,
            ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"]
        )
        self.assertEqual(execution.total_actions, 5)
        self.assertIsNone(execution.error)
        print(f"\n  ✓ Full 5-action workflow completed: {execution.completed_actions}")

    # ── Test 9: Unknown action rejected by engine ──────────────────────────────

    def test_09_unknown_action_rejected_by_engine(self):
        """Unknown action verb is rejected by AutomationEngine validation (no browser launch needed)."""
        from automation.engine import UnsupportedActionError
        from ai.models import WorkflowAction, WorkflowTrigger

        bad_proposal = WorkflowProposal(
            name="Bad Workflow",
            intent="Test unsupported action",
            trigger=WorkflowTrigger(
                type="new_email",
                application="demo_email",
                description="Test trigger"
            ),
            actions=[
                WorkflowAction(
                    type="open_email",
                    application="demo_email",
                    description="Open email",
                    target="test"
                ),
                WorkflowAction(
                    type="hack_mainframe",
                    application="demo_something",
                    description="Invalid action",
                    target="mainframe"
                ),
            ],
            variables=[],
            applications=["demo_email"],
            requires_approval=True
        )

        engine = AutomationEngine(default_executor=NoOpExecutor())

        async def run():
            return await engine.execute_workflow(bad_proposal, approved=True)

        execution = run_async(run())

        self.assertEqual(execution.status, AutomationStatus.FAILED)
        self.assertIn("hack_mainframe", execution.error)
        self.assertEqual(execution.completed_actions, [])
        print("  ✓ Unknown action 'hack_mainframe' rejected by AutomationEngine.")

    # ── Test 10: Failure stops subsequent actions ─────────────────────────────

    def test_10_failure_stops_subsequent_actions(self):
        """
        Searching for 'Unknown Customer' causes search_customer to fail.
        update_customer and send_message must NOT execute.
        Status must be PAUSED with human intervention required.
        """
        proposal = make_proposal(customer_name="Unknown Customer")
        engine = AutomationEngine()
        executor = PlaywrightExecutor(base_url=FRONTEND_BASE_URL, headless=True)

        async def run():
            return await engine.execute_workflow(
                proposal=proposal,
                approved=True,
                executor=executor,
            )

        execution = run_async(run())

        self.assertEqual(
            execution.status,
            AutomationStatus.PAUSED
        )

        self.assertTrue(
            execution.requires_human_intervention
        )

        self.assertTrue(
            execution.resume_available
        )

        self.assertIn(
            "search_customer",
            execution.current_action or ""
        )

        self.assertNotIn(
            "update_customer",
            execution.completed_actions
        )

        self.assertNotIn(
            "send_message",
            execution.completed_actions
        )
        print(f"  ✓ Failure at search_customer halted workflow. Completed: {execution.completed_actions}")

    # ── Test 11: Browser cleanup ──────────────────────────────────────────────

    def test_11_browser_resources_are_cleaned_up(self):
        """After execute_workflow, browser and page are fully released."""
        executor = PlaywrightExecutor(base_url=FRONTEND_BASE_URL, headless=True)
        proposal = make_proposal(["open_email"])
        engine = AutomationEngine()

        async def run():
            execution = await engine.execute_workflow(
                proposal=proposal,
                approved=True,
                executor=executor,
            )
            return execution

        run_async(run())

        # After cleanup, is_running should be False
        self.assertFalse(executor.is_running,
            "Browser is still running after workflow completed — possible resource leak!")
        self.assertIsNone(executor._browser)
        self.assertIsNone(executor._page)
        self.assertIsNone(executor._playwright)
        print("  ✓ Browser resources fully cleaned up after workflow completion.")

    # ── Test 12: Approval gate blocks Playwright execution ────────────────────

    def test_12_approval_false_prevents_playwright_execution(self):
        """
        approved=False must not trigger ANY browser action.
        Status must be pending, completed_actions must be empty.
        Playwright must NOT be launched.
        """
        proposal = make_proposal()

        # Use a real PlaywrightExecutor but DON'T approve — it should never start()
        executor = PlaywrightExecutor(base_url=FRONTEND_BASE_URL, headless=True)
        engine = AutomationEngine(default_executor=executor)

        async def run():
            return await engine.execute_workflow(proposal=proposal, approved=False)

        execution = run_async(run())

        self.assertEqual(execution.status, AutomationStatus.PENDING)
        self.assertEqual(execution.completed_actions, [])
        # Confirm browser was never launched
        self.assertFalse(executor.is_running,
            "Playwright was launched despite approved=False!")
        self.assertIsNone(executor._browser,
            "Browser object was created despite approved=False!")
        print("  ✓ approved=False: Playwright browser NOT launched. Status=pending.")


if __name__ == "__main__":
    print("=" * 70)
    print("  Phase 4.3 — PlaywrightExecutor Integration Tests")
    print(f"  Frontend URL: {FRONTEND_BASE_URL}")
    print("  Browser: Chromium (headless)")
    print("  Phase 4.3 adds browser execution but does NOT connect the")
    print("  frontend approval button to automation.")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPhase43PlaywrightExecutor)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
