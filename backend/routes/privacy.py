"""
WorkFlowOS Phase 12: Privacy & Safety REST API Endpoints

Provides endpoints for inspecting and updating privacy controls, toggling
activity observation, running data retention cleanup, and auditing payloads.
"""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.privacy.service import privacy_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


class PrivacyToggleRequest(BaseModel):
    collection_enabled: bool = Field(
        ...,
        description="Whether desktop activity capture is permitted"
    )


class RetentionCleanupRequest(BaseModel):
    dry_run: bool = Field(
        default=False,
        description="If True, estimates expired events without deleting"
    )
    retention_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=3650,
        description="Override retention days window for this cleanup run"
    )


class PrivacyAuditRequest(BaseModel):
    payload: Any = Field(
        ...,
        description="Arbitrary JSON structure to audit for sensitive keys or secrets"
    )


@router.get(
    "/status",
    summary="Get Privacy Posture & Settings",
    description="Returns current collection state, retention threshold, and privacy guarantees."
)
async def get_privacy_status():
    """Returns the current privacy configuration and status."""
    return privacy_service.get_privacy_status()


@router.post(
    "/toggle",
    summary="Toggle Activity Collection",
    description="Enables or disables desktop activity collection. When disabled, incoming activity is dropped."
)
async def toggle_collection(request: PrivacyToggleRequest):
    """Updates whether new activity events can be ingested."""
    try:
        new_state = privacy_service.set_collection_enabled(request.collection_enabled)
        return {
            "collection_enabled": new_state,
            "message": "Activity collection enabled." if new_state else "Activity collection disabled.",
        }
    except Exception as e:
        logger.error(f"Error toggling activity collection: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update privacy collection settings."
        )


@router.post(
    "/cleanup",
    summary="Run Event Retention Cleanup",
    description="Deletes activity events older than the configured retention threshold."
)
async def run_retention_cleanup(request: Optional[RetentionCleanupRequest] = None):
    """Executes safe retention-based deletion of expired events."""
    req = request or RetentionCleanupRequest()
    try:
        result = await privacy_service.cleanup_expired_events(
            dry_run=req.dry_run,
            retention_days=req.retention_days,
        )
        return result
    except Exception as e:
        logger.error(f"Error running retention cleanup: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute retention cleanup."
        )


@router.post(
    "/audit",
    summary="Audit Payload for Sensitive Data",
    description="Inspects a structure and reports detected categories and field paths without leaking raw values."
)
async def audit_payload_endpoint(request: PrivacyAuditRequest):
    """Audits arbitrary payload for sensitive credentials or financial data."""
    try:
        audit_result = privacy_service.audit_payload(request.payload)
        return audit_result
    except Exception as e:
        logger.error(f"Error auditing payload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to audit payload."
        )
