"""
WorkFlowOS Phase 5 — Desktop Activity Agent Package

Exports primary interfaces for observing, normalizing, and streaming
macOS desktop activity events to WorkFlowOS backend.
"""

from agent.config import AgentConfig, generate_session_id
from agent.normalizer import EventNormalizer, slugify_application_name
from agent.collector import MacOSActivityCollector, check_accessibility_trusted
from agent.client import BackendEventClient
from agent.service import DesktopActivityAgent, AgentState

__all__ = [
    "AgentConfig",
    "generate_session_id",
    "EventNormalizer",
    "slugify_application_name",
    "MacOSActivityCollector",
    "check_accessibility_trusted",
    "BackendEventClient",
    "DesktopActivityAgent",
    "AgentState",
]
