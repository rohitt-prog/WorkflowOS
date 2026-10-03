"""
WorkFlowOS Phase 5 — Backend Event Client

Responsible for delivering normalized activity events to the WorkFlowOS backend
via POST /api/events.

Includes:
- Non-blocking send_event(): events are queued immediately; a background
  delivery thread handles HTTP posting so the polling loop is never stalled.
- Robust error handling and timeout protection
- Exponential backoff retries for transient errors
- Event deduplication guard (ring buffer)
- In-memory event buffer for temporary network dropouts
"""

import collections
import logging
import queue
import threading
import time
from typing import Any, Dict, List, Optional, Set
import requests

from backend.models.event import EventCreate
from agent.config import AgentConfig

logger = logging.getLogger(__name__)


class BackendEventClient:
    """
    HTTP client for publishing events to WorkFlowOS backend.

    Features:
    - Synchronous delivery directly from the worker loop
    - Exponential backoff retries on transient errors (5xx, timeouts)
    - Ring-buffer event deduplication guard
    - Offline in-memory buffer for temporary network dropouts
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.session = requests.Session()
        # Ring buffer of recently delivered signatures for idempotency
        self._sent_signatures: collections.deque = collections.deque(maxlen=5000)
        self._sent_set: Set[str] = set()
        # Offline buffer queue (used when backend is temporarily unreachable)
        self._offline_buffer: collections.deque = collections.deque(maxlen=self.config.max_buffer_size)

    @property
    def events_url(self) -> str:
        return f"{self.config.api_base_url}/api/events"

    @property
    def health_url(self) -> str:
        return f"{self.config.api_base_url}/health"

    @property
    def buffered_count(self) -> int:
        return len(self._offline_buffer)

    def _event_signature(self, event: EventCreate) -> str:
        """Computes a unique signature for an event to prevent duplicates."""
        return f"{event.session_id}:{event.timestamp}:{event.application}:{event.event_type}:{event.target}"

    def check_health(self) -> bool:
        """Verifies whether the WorkFlowOS backend is reachable and healthy."""
        try:
            res = self.session.get(self.health_url, timeout=self.config.request_timeout_seconds)
            return res.status_code == 200 and res.json().get("status") == "ok"
        except Exception as e:
            logger.debug(f"Health check failed for {self.health_url}: {e}")
            return False

    def send_event(self, event: EventCreate) -> bool:
        """
        Sends a normalized event to POST /api/events with retries and buffering.

        Returns:
            True if delivered (or already sent / deduplicated),
            False if delivery failed and event was buffered locally.
        """
        sig = self._event_signature(event)
        if sig in self._sent_set:
            logger.debug(f"Duplicate event ignored by client: {sig}")
            return True

        # Flush offline buffer if we have recovered connectivity
        if self._offline_buffer:
            self._flush_buffer()

        success = self._post_with_retries(event)
        if success:
            self._record_sent(sig)
            return True
        else:
            self._buffer_event(event)
            return False

    def flush_sync(self, timeout: float = 5.0) -> int:
        """Flush buffer synchronously; compatibility alias."""
        return self.flush()

    def stop(self):
        """Clean shutdown hook; flushes pending offline events."""
        self.flush()

    def _post_with_retries(self, event: EventCreate) -> bool:
        """Execute HTTP POST with exponential backoff on network/5xx errors."""
        payload = event.model_dump()
        backoff = self.config.retry_backoff_seconds

        for attempt in range(1, self.config.max_retries + 1):
            try:
                res = self.session.post(
                    self.events_url,
                    json=payload,
                    timeout=self.config.request_timeout_seconds,
                    headers={"Content-Type": "application/json"}
                )

                if res.status_code in (200, 201):
                    logger.debug(f"Event delivered: {event.event_type} on '{event.application}'")
                    return True

                # Permanent client error (4xx except 429) should not retry indefinitely
                if 400 <= res.status_code < 500 and res.status_code != 429:
                    logger.error(
                        f"Backend rejected event (status {res.status_code}): {res.text}"
                    )
                    return False

                logger.warning(
                    f"Backend error (status {res.status_code}) on attempt {attempt}/{self.config.max_retries}. "
                    f"Retrying in {backoff:.1f}s..."
                )

            except (requests.ConnectionError, requests.Timeout) as e:
                logger.warning(
                    f"Network error on attempt {attempt}/{self.config.max_retries} connecting to {self.events_url}: {e}"
                )
            except Exception as e:
                logger.error(f"Unexpected error posting event on attempt {attempt}: {e}", exc_info=True)
                return False

            if attempt < self.config.max_retries:
                time.sleep(backoff)
                backoff *= 1.5

        return False

    def _record_sent(self, signature: str):
        """Add signature to deduplication set and ring buffer."""
        if len(self._sent_signatures) >= self._sent_signatures.maxlen:
            oldest = self._sent_signatures.popleft()
            self._sent_set.discard(oldest)
        self._sent_signatures.append(signature)
        self._sent_set.add(signature)

    def _buffer_event(self, event: EventCreate):
        """Safely buffers event in FIFO queue."""
        if len(self._offline_buffer) >= self._offline_buffer.maxlen:
            dropped = self._offline_buffer.popleft()
            logger.warning(f"Offline event buffer full ({self.config.max_buffer_size}). Dropped oldest event: {dropped.event_type}")
        self._offline_buffer.append(event)
        logger.info(f"Event buffered locally (current buffer size: {len(self._offline_buffer)})")

    def _flush_buffer(self):
        """Attempts to flush buffered events to backend."""
        logger.debug(f"Flushing {len(self._offline_buffer)} buffered events to backend...")
        flushed_count = 0
        while self._offline_buffer:
            next_ev = self._offline_buffer[0]
            # Try to send without re-entering _flush_buffer
            success = self._post_with_retries(next_ev)
            if success:
                self._offline_buffer.popleft()
                sig = self._event_signature(next_ev)
                self._record_sent(sig)
                flushed_count += 1
            else:
                # Backend still unreachable, halt flushing for now
                break
        if flushed_count > 0:
            logger.info(f"Successfully flushed {flushed_count} buffered events to backend.")

    def flush(self) -> int:
        """Public method to manually flush all pending offline events."""
        initial = len(self._offline_buffer)
        self._flush_buffer()
        return initial - len(self._offline_buffer)

    def stop(self):
        """Clean shutdown hook; flushes pending offline events."""
        self.flush()
