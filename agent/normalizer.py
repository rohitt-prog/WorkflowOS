"""
WorkFlowOS Phase 5 — Event Normalizer

Transforms raw macOS activity into the standard WorkFlowOS EventCreate schema,
ensuring 100% compatibility with Phase 1 event ingestion, Phase 2 discovery engine,
and database validation layers.
"""

import re
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.models.event import EventCreate
from agent.config import AgentConfig

logger = logging.getLogger(__name__)


def slugify_application_name(name: str) -> str:
    """
    Normalizes human-readable application names into consistent lowercase slugs.
    
    Examples:
        'Google Chrome' -> 'google_chrome'
        'Visual Studio Code' -> 'visual_studio_code'
        'Antigravity IDE' -> 'antigravity_ide'
        'demo_email' -> 'demo_email'
    """
    if not name:
        return "unknown_application"
    
    # Strip common file extensions if present
    cleaned = re.sub(r"\.app$", "", name, flags=re.IGNORECASE)
    # Replace non-alphanumeric characters with underscores
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", cleaned)
    # Strip leading/trailing underscores and lowercase
    slug = cleaned.strip("_").lower()
    return slug or "unknown_application"


class EventNormalizer:
    """
    Normalizes captured desktop events into validated EventCreate instances.
    Enforces privacy controls and application allowlist filtering.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()

    def normalize(
        self,
        app_name: str,
        event_type: str,
        bundle_id: Optional[str] = None,
        process_id: Optional[int] = None,
        target: Optional[str] = None,
        previous_app: Optional[str] = None,
        previous_bundle_id: Optional[str] = None,
        window_title: Optional[str] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> Optional[EventCreate]:
        """
        Normalizes a captured desktop activity event.
        
        Returns:
            EventCreate instance if allowed, or None if filtered out by privacy rules.
        """
        # Step 1: Privacy and allowlist enforcement
        if not self.config.is_app_allowed(app_name=app_name, bundle_id=bundle_id):
            logger.debug(f"Event filtered by allowlist/denylist: app='{app_name}', bundle='{bundle_id}'")
            return None

        # Step 2: Timestamp generation (ISO 8601 UTC with 'Z')
        if timestamp is None:
            now = datetime.now(timezone.utc)
        elif timestamp.tzinfo is None:
            now = timestamp.replace(tzinfo=timezone.utc)
        else:
            now = timestamp.astimezone(timezone.utc)
        
        # Consistent format: 2026-10-03T14:30:00.123456Z
        formatted_ts = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Step 3: Application name normalization
        app_slug = slugify_application_name(app_name)

        # Step 4: Metadata construction with privacy guards
        metadata: Dict[str, Any] = {
            "app_name": app_name,
            "bundle_id": bundle_id or "",
            "source": "macos_desktop_agent",
            "agent_version": "1.0.0",
        }
        if process_id is not None:
            metadata["process_id"] = process_id
        if previous_app:
            metadata["previous_application"] = slugify_application_name(previous_app)
            metadata["previous_app_name"] = previous_app
        if previous_bundle_id:
            metadata["previous_bundle_id"] = previous_bundle_id

        # Privacy guard: window title is strictly opt-in
        if self.config.include_window_title and window_title:
            # Sanitize window title: strip and truncate if necessary
            metadata["window_title"] = window_title.strip()[:200]

        # Merge any caller-provided custom metadata (e.g. accessibility status)
        if custom_metadata:
            for k, v in custom_metadata.items():
                if k not in metadata and v is not None:
                    metadata[k] = v

        # Step 5: Target definition
        effective_target = target or bundle_id or app_slug

        # Step 6: Construct and validate EventCreate model
        try:
            return EventCreate(
                session_id=self.config.session_id,
                timestamp=formatted_ts,
                application=app_slug,
                event_type=event_type,
                target=effective_target,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to construct valid EventCreate: {e}", exc_info=True)
            return None
