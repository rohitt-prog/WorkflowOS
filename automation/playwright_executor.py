import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from automation.models import AutomationAction, ExecutionActionResult
from automation.executor import ActionExecutor
from backend.config import settings

logger = logging.getLogger(__name__)

# Supported Playwright action verbs
PLAYWRIGHT_SUPPORTED_ACTIONS = {
    "open_email",
    "download_attachment",
    "search_customer",
    "update_customer",
    "send_message",
}


class PlaywrightExecutor(ActionExecutor):
    """
    Playwright-based concrete implementation of ActionExecutor.

    Automates browser interactions across the controlled WorkFlowOS demo applications:
    - /demo/email
    - /demo/crm
    - /demo/chat

    Adheres strictly to the human approval safety gate: does not trigger or execute
    unless explicitly called by AutomationEngine when approved=True.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        headless: Optional[bool] = None,
        timeout_ms: int = 10000,
        slow_mo: Optional[float] = None,
    ):
        """
        :param base_url: Root URL where the frontend is served (default from settings or http://localhost:3000).
        :param headless: Run browser in headless mode (default True).
        :param timeout_ms: Maximum wait timeout per selector in milliseconds.
        :param slow_mo: Optional artificial delay in milliseconds between actions.
        """
        self.base_url = (base_url or getattr(settings, "PLAYWRIGHT_BASE_URL", None) or os.getenv("PLAYWRIGHT_BASE_URL", "http://localhost:3000")).rstrip("/")
        
        if headless is not None:
            self.headless = headless
        else:
            self.headless = getattr(settings, "PLAYWRIGHT_HEADLESS", True)
            if isinstance(self.headless, str):
                self.headless = self.headless.lower() in ("true", "1", "yes")

        self.timeout_ms = timeout_ms
        self.slow_mo = slow_mo

        # Route endpoints
        self.email_url = f"{self.base_url}/demo/email"
        self.crm_url = f"{self.base_url}/demo/crm"
        self.chat_url = f"{self.base_url}/demo/chat"

        # Lifecycle objects
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    @property
    def is_running(self) -> bool:
        """Returns True if the browser and page are active."""
        return self._page is not None and not self._page.is_closed()

    async def start(self) -> None:
        """
        Initializes the Playwright driver, launches Chromium, and opens a new page.
        Safe to call multiple times (idempotent).
        """
        if self.is_running:
            return

        from playwright.async_api import async_playwright

        logger.info(
            f"[PlaywrightExecutor] Launching browser (headless={self.headless}, base_url={self.base_url})..."
        )
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
            )
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()
            logger.info("[PlaywrightExecutor] Browser, context, and page ready.")
        except Exception as e:
            logger.error(f"[PlaywrightExecutor] Failed to launch browser: {e}", exc_info=True)
            await self.cleanup()
            raise

    async def cleanup(self) -> None:
        """
        Cleanly closes page, context, browser, and terminates the Playwright engine.
        Guarantees no orphaned browser processes remain.
        """
        logger.info("[PlaywrightExecutor] Releasing browser resources...")
        try:
            if self._page and not self._page.is_closed():
                await self._page.close()
        except Exception as e:
            logger.debug(f"[PlaywrightExecutor] Error closing page: {e}")
        finally:
            self._page = None

        try:
            if self._context:
                await self._context.close()
        except Exception as e:
            logger.debug(f"[PlaywrightExecutor] Error closing context: {e}")
        finally:
            self._context = None

        try:
            if self._browser:
                await self._browser.close()
        except Exception as e:
            logger.debug(f"[PlaywrightExecutor] Error closing browser: {e}")
        finally:
            self._browser = None

        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.debug(f"[PlaywrightExecutor] Error stopping Playwright: {e}")
        finally:
            self._playwright = None

        logger.info("[PlaywrightExecutor] Browser cleanup complete.")

    async def close(self) -> None:
        """Alias for cleanup()."""
        await self.cleanup()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def _safe_goto(self, url: str) -> None:
        """Navigates to URL, waiting for networkidle with fallback to domcontentloaded."""
        try:
            await self._page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
        except Exception:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)

    async def execute(
        self,
        action: AutomationAction,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionActionResult:
        """
        Executes a single AutomationAction step using Playwright.
        Validates action type, manages browser readiness, and executes deterministically.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # Delegate integration actions to IntegrationExecutor without launching browser
        from integrations.registry import integration_registry
        from integrations.executor import IntegrationExecutor
        app_id = action.application.split(":", 1)[1].strip() if action.application.startswith("integration:") else action.application.strip()
        if integration_registry.get(app_id):
            return await IntegrationExecutor(integration_registry).execute(action, context=context)

        if action.type not in PLAYWRIGHT_SUPPORTED_ACTIONS:
            return ExecutionActionResult(
                action_id=action.id,
                action_type=action.type,
                success=False,
                message=f"Action '{action.type}' is not supported by PlaywrightExecutor",
                timestamp=now_iso,
            )

        ctx = context or {}

        try:
            # Ensure browser is running
            if not self.is_running:
                await self.start()

            if action.type == "open_email":
                return await self._execute_open_email(action, ctx)
            elif action.type == "download_attachment":
                return await self._execute_download_attachment(action, ctx)
            elif action.type == "search_customer":
                return await self._execute_search_customer(action, ctx)
            elif action.type == "update_customer":
                return await self._execute_update_customer(action, ctx)
            elif action.type == "send_message":
                return await self._execute_send_message(action, ctx)
            else:
                return ExecutionActionResult(
                    action_id=action.id,
                    action_type=action.type,
                    success=False,
                    message=f"Unhandled action type '{action.type}'",
                    timestamp=now_iso,
                )
        except Exception as e:
            logger.error(
                f"[PlaywrightExecutor] Exception executing '{action.type}': {e}",
                exc_info=True,
            )
            return ExecutionActionResult(
                action_id=action.id,
                action_type=action.type,
                success=False,
                message=f"Playwright error during '{action.type}': {str(e)}",
                timestamp=now_iso,
            )

    # ─────────────────────────────────────────────────────────────
    # Action Implementations
    # ─────────────────────────────────────────────────────────────

    async def _execute_open_email(
        self, action: AutomationAction, context: Dict[str, Any]
    ) -> ExecutionActionResult:
        """
        Action 1: open_email
        1. Navigate to /demo/email
        2. Locate data-testid="email-item"
        3. Click data-testid="open-email"
        4. Verify data-testid="download-attachment" appears
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        page = self._page

        # Navigate to email client if not already there
        if "/demo/email" not in page.url:
            logger.info(f"[PlaywrightExecutor] Navigating to {self.email_url}")
            await self._safe_goto(self.email_url)

        # Locate the email item
        await page.wait_for_selector('[data-testid="email-item"]', timeout=self.timeout_ms)

        # Click the Open button
        open_btn = page.locator('[data-testid="open-email"]').first
        await open_btn.wait_for(state="visible", timeout=self.timeout_ms)
        await open_btn.click()

        # Verify email detail view and attachment section are visible
        await page.wait_for_selector('[data-testid="download-attachment"]', timeout=self.timeout_ms)

        logger.info("[PlaywrightExecutor] open_email successful: attachment UI visible.")
        return ExecutionActionResult(
            action_id=action.id,
            action_type=action.type,
            success=True,
            message="Customer email opened and attachment container verified",
            timestamp=now_iso,
        )

    async def _execute_download_attachment(
        self, action: AutomationAction, context: Dict[str, Any]
    ) -> ExecutionActionResult:
        """
        Action 2: download_attachment
        1. On /demo/email, locate data-testid="attachment"
        2. Locate and click data-testid="download-attachment"
        3. Verify data-testid="download-status" indicates "Attachment downloaded"
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        page = self._page

        # Ensure on /demo/email
        if "/demo/email" not in page.url or not await page.locator('[data-testid="download-attachment"]').is_visible():
            await self._safe_goto(self.email_url)
            await page.wait_for_selector('[data-testid="open-email"]', timeout=self.timeout_ms)
            await page.locator('[data-testid="open-email"]').first.click()

        # Locate and click download button
        download_btn = page.locator('[data-testid="download-attachment"]').first
        await download_btn.wait_for(state="visible", timeout=self.timeout_ms)
        await download_btn.click()

        # Verify download confirmation status
        status_el = await page.wait_for_selector(
            '[data-testid="download-status"]', timeout=self.timeout_ms
        )
        status_text = (await status_el.text_content()) or ""

        if "Attachment downloaded" not in status_text:
            return ExecutionActionResult(
                action_id=action.id,
                action_type=action.type,
                success=False,
                message=f"Download status text did not match expected confirmation: '{status_text}'",
                timestamp=now_iso,
            )

        logger.info("[PlaywrightExecutor] download_attachment successful: 'Attachment downloaded' verified.")
        return ExecutionActionResult(
            action_id=action.id,
            action_type=action.type,
            success=True,
            message="Attachment downloaded and confirmed in demo UI",
            timestamp=now_iso,
        )

    async def _execute_search_customer(
        self, action: AutomationAction, context: Dict[str, Any]
    ) -> ExecutionActionResult:
        """
        Action 3: search_customer
        1. Navigate to /demo/crm
        2. Locate data-testid="customer-search"
        3. Enter customer name (workflow parameters or context, fallback "Rahul")
        4. Click data-testid="search-customer"
        5. Verify data-testid="customer-result" appears. If not found, return structured failure.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        page = self._page

        # Extract target customer name
        customer_name = (
            action.parameters.get("customer_name")
            or action.parameters.get("customer")
            or context.get("customer_name")
            or (context.get("variables") or {}).get("customer_name")
        )
        if not customer_name:
            if action.target and action.target.lower() not in (
                "customer", "customer_request", "crm", "demo_crm"
            ):
                customer_name = action.target
            else:
                customer_name = "Rahul"

        logger.info(f"[PlaywrightExecutor] Searching CRM for customer: '{customer_name}'")

        # Navigate to CRM
        await self._safe_goto(self.crm_url)

        # Locate search input
        search_input = page.locator('[data-testid="customer-search"]')
        await search_input.wait_for(state="visible", timeout=self.timeout_ms)
        await search_input.fill(customer_name)

        # Click Search button
        search_btn = page.locator('[data-testid="search-customer"]')
        await search_btn.click()

        # Wait for either customer-result or not-found-message
        await page.wait_for_selector(
            '[data-testid="customer-result"], [data-testid="not-found-message"]',
            timeout=self.timeout_ms,
        )

        not_found_locator = page.locator('[data-testid="not-found-message"]')
        if await not_found_locator.is_visible():
            logger.warning(f"[PlaywrightExecutor] Customer not found: '{customer_name}'")
            return ExecutionActionResult(
                action_id=action.id,
                action_type=action.type,
                success=False,
                message=f"Customer '{customer_name}' not found",
                data={"error": "No customer result was displayed"},
                timestamp=now_iso,
            )

        result_locator = page.locator('[data-testid="customer-result"]')
        if not await result_locator.is_visible():
            return ExecutionActionResult(
                action_id=action.id,
                action_type=action.type,
                success=False,
                message="Customer result was not displayed",
                data={"error": "No customer result was displayed"},
                timestamp=now_iso,
            )

        logger.info(f"[PlaywrightExecutor] Customer '{customer_name}' found successfully.")
        return ExecutionActionResult(
            action_id=action.id,
            action_type=action.type,
            success=True,
            message=f"Customer {customer_name} found",
            data={"customer_name": customer_name},
            timestamp=now_iso,
        )

    async def _execute_update_customer(
        self, action: AutomationAction, context: Dict[str, Any]
    ) -> ExecutionActionResult:
        """
        Action 4: update_customer
        1. On /demo/crm with customer profile already displayed
        2. Update deterministic notes field (data-testid="customer-notes" or #edit-notes)
        3. Click data-testid="update-customer"
        4. Verify data-testid="update-status" indicates "Customer updated"
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        page = self._page

        # Verify on CRM page and customer profile is active
        if "/demo/crm" not in page.url or not await page.locator('[data-testid="customer-result"]').is_visible():
            # If not yet on customer profile, navigate and search default customer
            await self._safe_goto(self.crm_url)
            await page.locator('[data-testid="customer-search"]').fill("Rahul")
            await page.locator('[data-testid="search-customer"]').click()
            await page.wait_for_selector('[data-testid="customer-result"]', timeout=self.timeout_ms)

        # Update notes field deterministically
        notes_selector = '[data-testid="customer-notes"]'
        if await page.locator(notes_selector).count() == 0:
            notes_selector = '#edit-notes'

        notes_input = page.locator(notes_selector)
        await notes_input.wait_for(state="visible", timeout=self.timeout_ms)
        await notes_input.fill(
            "Account verified from email attachment. High-priority enterprise support status activated."
        )

        # Click Update Customer button
        update_btn = page.locator('[data-testid="update-customer"]')
        await update_btn.wait_for(state="visible", timeout=self.timeout_ms)
        await update_btn.click()

        # Verify update confirmation status
        status_el = await page.wait_for_selector(
            '[data-testid="update-status"]', timeout=self.timeout_ms
        )
        status_text = (await status_el.text_content()) or ""

        if "Customer updated" not in status_text:
            return ExecutionActionResult(
                action_id=action.id,
                action_type=action.type,
                success=False,
                message=f"Update status text did not match expected confirmation: '{status_text}'",
                timestamp=now_iso,
            )

        logger.info("[PlaywrightExecutor] update_customer successful: 'Customer updated' verified.")
        return ExecutionActionResult(
            action_id=action.id,
            action_type=action.type,
            success=True,
            message="Customer updated successfully in CRM",
            timestamp=now_iso,
        )

    async def _execute_send_message(
        self, action: AutomationAction, context: Dict[str, Any]
    ) -> ExecutionActionResult:
        """
        Action 5: send_message
        1. Navigate to /demo/chat
        2. Locate data-testid="message-input" and enter workflow notification message
        3. Click data-testid="send-message"
        4. Verify data-testid="sent-message" appears
        5. Verify data-testid="send-status" indicates "Message sent"
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        page = self._page

        # Navigate to chat
        if "/demo/chat" not in page.url:
            await self._safe_goto(self.chat_url)

        # Locate message input
        message_input = page.locator('[data-testid="message-input"]')
        await message_input.wait_for(state="visible", timeout=self.timeout_ms)

        # Determine notification content
        notification_text = (
            action.parameters.get("message")
            or context.get("message")
            or "Customer Rahul record updated in CRM with VIP tier. Request document verified."
        )
        await message_input.fill(notification_text)

        # Click Send button
        send_btn = page.locator('[data-testid="send-message"]')
        await send_btn.wait_for(state="visible", timeout=self.timeout_ms)
        await send_btn.click()

        # Verify sent-message appears
        await page.wait_for_selector('[data-testid="sent-message"]', timeout=self.timeout_ms)

        # Verify send-status indicates "Message sent"
        status_el = await page.wait_for_selector(
            '[data-testid="send-status"]', timeout=self.timeout_ms
        )
        status_text = (await status_el.text_content()) or ""

        if "Message sent" not in status_text:
            return ExecutionActionResult(
                action_id=action.id,
                action_type=action.type,
                success=False,
                message=f"Send status text did not match expected confirmation: '{status_text}'",
                timestamp=now_iso,
            )

        logger.info("[PlaywrightExecutor] send_message successful: 'Message sent' verified.")
        return ExecutionActionResult(
            action_id=action.id,
            action_type=action.type,
            success=True,
            message="Notification message sent to chat channel",
            timestamp=now_iso,
        )
