"""
WorkFlowOS Phase 5 — Desktop Activity Agent Service

Orchestrates the agent lifecycle (start, stop, status), integrating:
- macOS activity collection (MacOSActivityCollector)
- Event normalization & privacy filtering (EventNormalizer)
- Backend event streaming & retry buffer (BackendEventClient)
"""

import logging
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional

from backend.models.event import EventCreate
from agent.config import AgentConfig, generate_session_id
from agent.collector import MacOSActivityCollector
from agent.normalizer import EventNormalizer
from agent.client import BackendEventClient

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class DesktopActivityAgent:
    """
    Primary desktop activity monitoring service.
    
    Observes user application switches and window focus transitions on macOS,
    normalizes them according to WorkFlowOS privacy policies, and streams them
    to the WorkFlowOS backend.
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        collector: Optional[MacOSActivityCollector] = None,
        normalizer: Optional[EventNormalizer] = None,
        client: Optional[BackendEventClient] = None,
    ):
        self.config = config or AgentConfig()
        self.collector = collector or MacOSActivityCollector(config=self.config)
        self.normalizer = normalizer or EventNormalizer(config=self.config)
        self.client = client or BackendEventClient(config=self.config)

        self.state: AgentState = AgentState.IDLE
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Telemetry & observability counters
        self.start_time: Optional[datetime] = None
        self.stop_time: Optional[datetime] = None
        self.events_captured: int = 0
        self.events_sent: int = 0
        self.events_dropped: int = 0
        self.last_event: Optional[Dict[str, Any]] = None

        # Optional callback invoked on each captured event (useful for live UI/CLI stream)
        self.on_event_callback: Optional[Callable[[EventCreate], None]] = None

    @property
    def is_running(self) -> bool:
        return self.state == AgentState.RUNNING and (self._thread is not None and self._thread.is_alive())

    def start(self, session_id: Optional[str] = None):
        """
        Starts desktop activity monitoring.
        
        Requires explicit user action. Launches a background observer thread.
        """
        with self._lock:
            if self.is_running:
                logger.warning("DesktopActivityAgent is already running.")
                return

            if session_id:
                self.config.session_id = session_id
            elif not self.config.session_id:
                self.config.session_id = generate_session_id()

            # Ensure collector and normalizer share the updated session
            self.normalizer.config = self.config
            self.collector.reset()

            self._stop_event.clear()
            self.state = AgentState.RUNNING
            self.start_time = datetime.now(timezone.utc)
            self.stop_time = None

            self._thread = threading.Thread(
                target=self._worker_loop,
                name="DesktopActivityAgentWorker",
                daemon=True
            )
            self._thread.start()
            logger.info(
                f"DesktopActivityAgent started (session='{self.config.session_id}', "
                f"poll_interval={self.config.poll_interval_seconds}s, "
                f"backend='{self.config.api_base_url}')"
            )

    def stop(self):
        """
        Stops desktop activity monitoring.
        
        Halts the background observer thread and flushes pending buffered events.
        """
        with self._lock:
            if not self.is_running and self.state != AgentState.RUNNING:
                self.state = AgentState.STOPPED
                return

            logger.info("Stopping DesktopActivityAgent...")
            self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

        with self._lock:
            self.state = AgentState.STOPPED
            self.stop_time = datetime.now(timezone.utc)
            # Drain the async delivery queue then stop the delivery thread
            self.client.flush_sync()
            self.client.stop()
            logger.info(
                f"DesktopActivityAgent stopped cleanly. "
                f"Summary: captured={self.events_captured}, sent={self.events_sent}, dropped={self.events_dropped}"
            )

    def capture_step(self) -> Optional[EventCreate]:
        """
        Executes a single observation, normalization, and delivery cycle.
        
        Returns the normalized EventCreate if an event occurred and passed privacy rules,
        or None if no state change occurred or the app was filtered out.
        """
        # Step 1: Query native collector for state transition
        activity = self.collector.poll()
        if not activity:
            return None

        # Phase 12 Privacy Gate: Consult centralized privacy_service as runtime authority.
        # Fails closed: if privacy_service cannot be accessed or raises an exception, drop immediately.
        try:
            from backend.privacy.service import privacy_service
            collection_enabled = privacy_service.is_collection_enabled()
        except Exception:
            logger.warning("[DesktopActivityAgent] Privacy service check failed; failing closed and dropping event.")
            self.events_dropped += 1
            return None

        if not collection_enabled:
            # Dropped at privacy gate: no normalization, no buffering, no retries, no persistence
            self.events_dropped += 1
            return None

        self.events_captured += 1

        # Step 2: Normalize and filter according to privacy policy
        event = self.normalizer.normalize(
            app_name=activity["app_name"],
            event_type=activity["event_type"],
            bundle_id=activity.get("bundle_id"),
            process_id=activity.get("process_id"),
            target=activity.get("target"),
            previous_app=activity.get("previous_app"),
            previous_bundle_id=activity.get("previous_bundle_id"),
            window_title=activity.get("window_title"),
        )

        if not event:
            self.events_dropped += 1
            return None

        # Phase 12 Privacy: Sanitize metadata and target before buffering or streaming.
        # Fails closed: if sanitization fails for any reason, drop immediately (no HTTP, no buffer, no retry).
        try:
            from backend.privacy.redaction import redact_sensitive_data
            if event.metadata:
                event.metadata = redact_sensitive_data(event.metadata, inplace=False)
            if event.target:
                event.target = redact_sensitive_data(event.target, inplace=False)
        except Exception:
            logger.warning("[DesktopActivityAgent] Sensitive data sanitization error; failing closed and dropping event.")
            self.events_dropped += 1
            return None

        # Step 3: Stream to backend
        delivered = self.client.send_event(event)
        if delivered:
            self.events_sent += 1

        self.last_event = event.model_dump()

        if self.on_event_callback:
            try:
                self.on_event_callback(event)
            except Exception as e:
                logger.debug(f"Error in on_event_callback: {e}")

        return event

    def _worker_loop(self):
        """Continuous background polling loop."""
        logger.debug("DesktopActivityAgent worker loop entered.")
        interval = max(0.2, self.config.poll_interval_seconds)

        while not self._stop_event.is_set():
            try:
                self.capture_step()
            except Exception as e:
                logger.error(f"Error during agent capture cycle: {e}", exc_info=True)

            self._stop_event.wait(timeout=interval)

        logger.debug("DesktopActivityAgent worker loop exited.")

    def status(self) -> Dict[str, Any]:
        """Returns comprehensive status dictionary for observability and CLI."""
        uptime = 0.0
        if self.start_time:
            end = self.stop_time or datetime.now(timezone.utc)
            uptime = round((end - self.start_time).total_seconds(), 2)

        frontmost = self.collector.get_frontmost_app()
        frontmost_name = frontmost.get("name") if frontmost else None

        collection_enabled = False
        try:
            from backend.privacy.service import privacy_service
            collection_enabled = privacy_service.is_collection_enabled()
        except Exception:
            collection_enabled = False

        return {
            "state": self.state.value,
            "is_running": self.is_running,
            "session_id": self.config.session_id,
            "uptime_seconds": uptime,
            "events_captured": self.events_captured,
            "events_sent": self.events_sent,
            "events_dropped": self.events_dropped,
            "events_buffered": self.client.buffered_count,
            "backend_url": self.config.api_base_url,
            "backend_connected": self.client.check_health(),
            "accessibility_granted": self.collector.accessibility_granted,
            "allowlist": self.config.allowlist,
            "collection_enabled": collection_enabled,
            "include_window_title": self.config.include_window_title,
            "poll_interval_seconds": self.config.poll_interval_seconds,
            "current_frontmost_app": frontmost_name,
            "last_event": self.last_event,
        }
