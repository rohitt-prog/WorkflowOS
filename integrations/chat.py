"""
WorkFlowOS Phase 13: Chat / Slack Application Adapter

Implements the BaseIntegrationAdapter interface for the WorkFlowOS Chat / messaging application.
Exposes deterministic messaging operations:
- search_messages (read-only)
- read_message (read-only)
- send_message (mutating — requires human approval)
"""

import copy
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from integrations.base import BaseIntegrationAdapter
from integrations.models import (
    IntegrationMetadata,
    IntegrationStatus,
    IntegrationActionDefinition,
    ActionParameterDefinition,
    ParameterType,
    IntegrationActionResult,
    IntegrationValidationError,
)

logger = logging.getLogger(__name__)

DEFAULT_CHAT_MESSAGES: List[Dict[str, Any]] = [
    {
        "id": "msg_001",
        "channel": "general",
        "sender": "System",
        "recipient": None,
        "message": "Welcome to WorkFlowOS team chat workspace.",
        "timestamp": "2026-10-06T10:00:00Z",
    },
    {
        "id": "msg_002",
        "channel": "support",
        "sender": "Alice",
        "recipient": None,
        "message": "Customer ticket #1042 has been verified and customer profile updated.",
        "timestamp": "2026-10-06T10:15:00Z",
    },
    {
        "id": "msg_003",
        "channel": "ops",
        "sender": "Rahul",
        "recipient": None,
        "message": "Invoice specification document downloaded and reviewed.",
        "timestamp": "2026-10-06T10:30:00Z",
    },
]


class ChatIntegrationAdapter(BaseIntegrationAdapter):
    """
    Chat / Slack Application Adapter for WorkFlowOS.
    Clearly classified as demo/mock; supports both direct integration execution
    and Playwright browser execution against /demo/chat.
    """

    def __init__(self, adapter_id: str = "chat"):
        metadata = IntegrationMetadata(
            id=adapter_id,
            name="WorkFlowOS Chat",
            description="Team messaging integration for searching messages, reading channels, and sending notifications.",
            version="1.0.0",
            category="messaging",
            icon="message-square",
            is_mock=True,
            disclaimer="Demo chat integration for team communication workflows.",
        )
        super().__init__(metadata=metadata)
        # Demo chat is connected out-of-the-box
        self._status = IntegrationStatus.CONNECTED
        self._messages: List[Dict[str, Any]] = copy.deepcopy(DEFAULT_CHAT_MESSAGES)

    def reset_seed_data(self) -> None:
        """Resets in-memory messages to factory defaults."""
        self._messages = copy.deepcopy(DEFAULT_CHAT_MESSAGES)

    def _register_capabilities(self) -> None:
        """Declares Chat capabilities and schemas."""

        # 1. Read-only: search_messages
        self.register_action(
            IntegrationActionDefinition(
                name="search_messages",
                display_name="Search Messages",
                description="Search team chat messages across channels by keyword or sender.",
                parameters=[
                    ActionParameterDefinition(
                        name="query",
                        type=ParameterType.STRING,
                        required=True,
                        description="Search text or keyword query",
                    ),
                    ActionParameterDefinition(
                        name="channel",
                        type=ParameterType.STRING,
                        required=False,
                        default=None,
                        description="Optional target channel filter (e.g. 'general', 'support')",
                    ),
                ],
                required_scopes=[],
                is_safe=True,
                is_mutating=False,
                is_destructive=False,
                allow_direct_execution=True,
                supported_strategies=["INTEGRATION", "BROWSER"],
                requires_approval=False,
            ),
            handler=self._handle_search_messages,
        )

        # 2. Read-only: read_message
        self.register_action(
            IntegrationActionDefinition(
                name="read_message",
                display_name="Read Message",
                description="Retrieve a specific message record by unique message ID.",
                parameters=[
                    ActionParameterDefinition(
                        name="message_id",
                        type=ParameterType.STRING,
                        required=True,
                        description="Unique message identifier (e.g. 'msg_001')",
                    ),
                    ActionParameterDefinition(
                        name="channel",
                        type=ParameterType.STRING,
                        required=False,
                        default=None,
                        description="Optional channel filter",
                    ),
                ],
                required_scopes=[],
                is_safe=True,
                is_mutating=False,
                is_destructive=False,
                allow_direct_execution=True,
                supported_strategies=["INTEGRATION", "BROWSER"],
                requires_approval=False,
            ),
            handler=self._handle_read_message,
        )

        # 3. Mutating: send_message (MANDATORY APPROVAL GATE)
        self.register_action(
            IntegrationActionDefinition(
                name="send_message",
                display_name="Send Notification Message",
                description="Post a workflow notification or message to a chat channel or recipient.",
                parameters=[
                    ActionParameterDefinition(
                        name="message",
                        type=ParameterType.STRING,
                        required=False,
                        default="Automated notification",
                        description="Notification text or message payload to send",
                    ),
                    ActionParameterDefinition(
                        name="channel",
                        type=ParameterType.STRING,
                        required=False,
                        default="general",
                        description="Target destination channel",
                    ),
                    ActionParameterDefinition(
                        name="recipient",
                        type=ParameterType.STRING,
                        required=False,
                        default=None,
                        description="Target user or recipient tag",
                    ),
                ],
                required_scopes=[],
                is_safe=False,
                is_mutating=True,
                is_destructive=False,
                allow_direct_execution=True,
                supported_strategies=["INTEGRATION", "BROWSER"],
                requires_approval=True,  # STRICT APPROVAL INVARIANT
            ),
            handler=self._handle_send_message,
        )

    async def _handle_search_messages(
        self, parameters: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Executes read-only search across messages."""
        q = str(parameters.get("query") or "").strip().lower()
        channel = str(parameters.get("channel") or "").strip().lower()

        results = []
        for msg in self._messages:
            if channel and channel != "all" and msg.get("channel", "").lower() != channel:
                continue
            if not q or q in msg.get("message", "").lower() or q in msg.get("sender", "").lower():
                results.append(copy.deepcopy(msg))

        return {
            "query": q,
            "channel": channel,
            "count": len(results),
            "messages": results,
        }

    async def _handle_read_message(
        self, parameters: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Executes read-only retrieval of a single message."""
        mid = str(parameters.get("message_id") or "").strip()
        if not mid:
            raise IntegrationValidationError("Parameter 'message_id' is required.")

        for msg in self._messages:
            if msg.get("id") == mid:
                return {
                    "success": True,
                    "message_record": copy.deepcopy(msg),
                    "message": copy.deepcopy(msg),
                }

        # Fallback to latest message if available
        if self._messages:
            latest = copy.deepcopy(self._messages[-1])
            return {
                "success": True,
                "message_record": latest,
                "message": latest,
                "fallback": True,
            }

        return {
            "success": False,
            "message": f"Message with ID '{mid}' not found.",
        }

    async def _handle_send_message(
        self, parameters: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes mutating send message action.
        SAFETY REQUIREMENT: Handled under approved workflow execution.
        """
        msg_text = str(
            parameters.get("message")
            or parameters.get("text")
            or parameters.get("content")
            or ""
        ).strip()
        if not msg_text and context:
            msg_text = str(
                context.get("message")
                or context.get("text")
                or context.get("content")
                or ""
            ).strip()

        if not msg_text:
            raise IntegrationValidationError("Parameter 'message' cannot be empty.")

        channel = str(
            parameters.get("channel")
            or parameters.get("target")
            or (context.get("target") if context else "")
            or "general"
        ).strip()
        recipient = parameters.get("recipient")
        new_id = f"msg_{uuid.uuid4().hex[:6]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        record = {
            "id": new_id,
            "channel": channel,
            "sender": "WorkFlowOS Bot",
            "recipient": recipient,
            "message": msg_text,
            "timestamp": now_iso,
        }
        self._messages.append(record)

        logger.info(f"[{self.id}] Dispatched message '{new_id}' to channel '{channel}'")
        return {
            "sent": True,
            "message_id": new_id,
            "channel": channel,
            "message": msg_text,
            "timestamp": now_iso,
            "status": "Message sent successfully",
        }
