"""
WorkFlowOS Phase 13: Application Ecosystem REST API Routes

Provides endpoints for:
- GET /api/applications: List registered ecosystem applications with health & capabilities.
- GET /api/applications/{application_id}: Retrieve detailed metadata for a specific application.
- GET /api/applications/{application_id}/capabilities: Retrieve exposed capabilities for an application.
- GET /api/applications/{application_id}/health: Inspect lightweight connection/health status.

Strict Privacy & Security:
- Respects Phase 12 redaction: sensitive credentials or tokens are never exposed.
- Deterministic capability discovery without LLM or vector lookups.
- Mutating actions are marked with requires_approval=True.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status

from integrations.registry import application_registry
from integrations.models import (
    ApplicationSummary,
    ApplicationCapability,
    ApplicationHealth,
)
from backend.privacy.redaction import redact_sensitive_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.get(
    "",
    response_model=List[ApplicationSummary],
    summary="List Ecosystem Applications",
    description="Returns all registered applications in the WorkFlowOS ecosystem with their connection status and capabilities.",
)
async def list_applications_endpoint():
    """GET /api/applications"""
    summaries = application_registry.get_summaries()
    # Phase 12 Privacy: Ensure no sensitive credential leakage
    sanitized_dicts = [redact_sensitive_data(s.model_dump(), inplace=False) for s in summaries]
    return [ApplicationSummary.model_validate(d) for d in sanitized_dicts]


@router.get(
    "/{application_id}",
    response_model=ApplicationSummary,
    summary="Get Application Details",
    description="Retrieves detailed metadata, health status, and declared capabilities for a specific application.",
)
async def get_application_endpoint(application_id: str):
    """GET /api/applications/{application_id}"""
    adapter = application_registry.get_application(application_id)
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' is not registered in the ecosystem.",
        )

    summary = adapter.to_application_summary()
    sanitized_dict = redact_sensitive_data(summary.model_dump(), inplace=False)
    return ApplicationSummary.model_validate(sanitized_dict)


@router.get(
    "/{application_id}/capabilities",
    response_model=List[ApplicationCapability],
    summary="List Application Capabilities",
    description="Returns all capabilities exposed by a specific application, including safety classification and supported strategies.",
)
async def get_application_capabilities_endpoint(application_id: str):
    """GET /api/applications/{application_id}/capabilities"""
    adapter = application_registry.get_application(application_id)
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' is not registered in the ecosystem.",
        )

    caps = adapter.capabilities()
    sanitized_dicts = [redact_sensitive_data(c.model_dump(), inplace=False) for c in caps]
    return [ApplicationCapability.model_validate(d) for d in sanitized_dicts]


@router.get(
    "/{application_id}/health",
    response_model=ApplicationHealth,
    summary="Get Application Health Status",
    description="Returns the lightweight connection and availability status for an application.",
)
async def get_application_health_endpoint(application_id: str):
    """GET /api/applications/{application_id}/health"""
    health_status = application_registry.get_health(application_id)
    if not health_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' is not registered in the ecosystem.",
        )

    sanitized_dict = redact_sensitive_data(health_status.model_dump(), inplace=False)
    return ApplicationHealth.model_validate(sanitized_dict)
