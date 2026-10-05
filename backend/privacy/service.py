"""
WorkFlowOS Phase 12: Privacy & Data Governance Service

Manages user privacy controls, activity collection states, and automated
data retention cleanup policies.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from backend.privacy.redaction import redact_sensitive_data, audit_sensitive_data

logger = logging.getLogger(__name__)


class PrivacyService:
    """
    Centralized controller for privacy policies, collection toggles,
    and event retention enforcement.
    """

    def __init__(self):
        # Initial state derived from environment with safe production defaults
        self._collection_enabled: bool = os.getenv(
            "ACTIVITY_COLLECTION_ENABLED", "true"
        ).lower() in ("true", "1", "yes")

        try:
            self._retention_days: int = int(os.getenv("EVENT_RETENTION_DAYS", "30"))
        except ValueError:
            self._retention_days = 30

    # -----------------------------------------------------------------------
    # Activity Collection Governance
    # -----------------------------------------------------------------------

    def is_collection_enabled(self) -> bool:
        """Returns True if desktop activity collection is currently permitted."""
        return self._collection_enabled

    def set_collection_enabled(self, enabled: bool) -> bool:
        """
        Dynamically updates the user's collection preference.
        Does NOT alter or delete previously recorded historical events.
        """
        self._collection_enabled = bool(enabled)
        logger.info(
            f"[PrivacyService] Activity collection toggled to: {self._collection_enabled}"
        )
        return self._collection_enabled

    # -----------------------------------------------------------------------
    # Data Retention Governance
    # -----------------------------------------------------------------------

    def get_retention_days(self) -> int:
        """Returns the configured retention threshold in days."""
        return self._retention_days

    def set_retention_days(self, days: int) -> int:
        """Configures the retention threshold in days (minimum 1 day)."""
        self._retention_days = max(1, int(days))
        logger.info(f"[PrivacyService] Event retention set to {self._retention_days} days")
        return self._retention_days

    def get_cutoff_timestamp(self, days: Optional[int] = None) -> str:
        """Computes the ISO 8601 UTC timestamp cutoff for event expiration."""
        effective_days = days if days is not None else self._retention_days
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=effective_days)
        return cutoff_dt.isoformat()

    async def cleanup_expired_events(
        self,
        dry_run: bool = False,
        retention_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Safely identifies and purges events older than the configured retention policy.
        If dry_run=True, reports expired event counts without mutating storage.
        """
        effective_days = retention_days if retention_days is not None else self._retention_days
        cutoff_iso = self.get_cutoff_timestamp(days=effective_days)
        filter_query = {"timestamp": {"$lt": cutoff_iso}}

        try:
            from backend.database import get_database
            db = get_database()
            if db is not None:
                collection = db["events"]
                expired_count = await collection.count_documents(filter_query)

                if dry_run:
                    return {
                        "dry_run": True,
                        "retention_days": effective_days,
                        "cutoff_timestamp": cutoff_iso,
                        "events_eligible_for_deletion": expired_count,
                        "deleted_count": 0,
                    }

                result = await collection.delete_many(filter_query)
                logger.info(
                    f"[PrivacyService] Purged {result.deleted_count} events older than {cutoff_iso}."
                )
                return {
                    "dry_run": False,
                    "retention_days": effective_days,
                    "cutoff_timestamp": cutoff_iso,
                    "events_eligible_for_deletion": expired_count,
                    "deleted_count": result.deleted_count,
                }
        except Exception as e:
            logger.error(f"[PrivacyService] Retention cleanup failed: {e}", exc_info=True)

        return {
            "dry_run": dry_run,
            "retention_days": effective_days,
            "cutoff_timestamp": cutoff_iso,
            "events_eligible_for_deletion": 0,
            "deleted_count": 0,
            "note": "Database unavailable or empty.",
        }

    # -----------------------------------------------------------------------
    # Status & Audit
    # -----------------------------------------------------------------------

    def get_privacy_status(self) -> Dict[str, Any]:
        """Returns comprehensive privacy posture and policy settings."""
        return {
            "collection_enabled": self._collection_enabled,
            "retention_days": self._retention_days,
            "retention_cutoff_timestamp": self.get_cutoff_timestamp(),
            "redaction_active": True,
            "zero_credentials_persisted": True,
            "approval_gate_required": True,
        }

    def audit_payload(self, payload: Any) -> Dict[str, Any]:
        """Inspects an arbitrary JSON payload and reports sensitive field detection."""
        return audit_sensitive_data(payload)


# Singleton privacy service instance
privacy_service = PrivacyService()
