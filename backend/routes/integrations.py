"""
WorkFlowOS Phase 7.1: Integration Management REST API Routes

Provides endpoints for:
- Listing registered integrations, connection status, and declared capabilities.
- Retrieving specific integration metadata.
- Connecting and disconnecting integration adapters.
- Executing permitted actions on integrations with validation and credential redaction.
"""

import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status

from integrations.registry import integration_registry
from integrations.models import (
    IntegrationSummary,
    IntegrationActionResult,
    UnknownIntegrationError,
    UnsupportedActionError,
    IntegrationConnectionError,
    IntegrationValidationError,
)
from integrations.credentials import sanitize_credential_dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


class ConnectIntegrationRequest(BaseModel):
    """Optional payload when connecting an integration."""
    credentials: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional connection credentials (never logged or stored in plaintext)"
    )


class ExecuteActionRequest(BaseModel):
    """Payload for direct execution of an integration action."""
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters adhering to the action's declared schema"
    )
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional runtime execution context"
    )


@router.get(
    "",
    response_model=List[IntegrationSummary],
    summary="List Registered Integrations",
    description="Returns all registered integration adapters, their connection statuses, and declared actions.",
)
async def list_integrations_endpoint():
    """GET /api/integrations"""
    return integration_registry.get_summaries()


@router.get(
    "/{integration_id}",
    response_model=IntegrationSummary,
    summary="Get Integration Details",
    description="Retrieves metadata, connection status, and declared capabilities for a specific integration.",
)
async def get_integration_endpoint(integration_id: str):
    """GET /api/integrations/{integration_id}"""
    adapter = integration_registry.get(integration_id)
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration '{integration_id}' not found.",
        )
    return adapter.to_summary()


@router.post(
    "/{integration_id}/connect",
    response_model=IntegrationSummary,
    summary="Connect Integration",
    description="Connects an integration adapter. For mock integrations, transitions state without external calls.",
)
async def connect_integration_endpoint(
    integration_id: str,
    request: Optional[ConnectIntegrationRequest] = None
):
    """POST /api/integrations/{integration_id}/connect"""
    adapter = integration_registry.get(integration_id)
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration '{integration_id}' not found.",
        )

    creds = request.credentials if request else None
    success = await adapter.connect(credentials=creds)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=adapter.last_error or "Failed to connect integration.",
        )

    return adapter.to_summary()


@router.post(
    "/{integration_id}/disconnect",
    response_model=IntegrationSummary,
    summary="Disconnect Integration",
    description="Disconnects an integration adapter and cleans up active resources.",
)
async def disconnect_integration_endpoint(integration_id: str):
    """POST /api/integrations/{integration_id}/disconnect"""
    adapter = integration_registry.get(integration_id)
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration '{integration_id}' not found.",
        )

    await adapter.disconnect()
    return adapter.to_summary()


@router.post(
    "/{integration_id}/actions/{action_name}/execute",
    response_model=IntegrationActionResult,
    summary="Execute Integration Action",
    description="Safely executes a permitted action on a connected integration with schema validation.",
)
async def execute_integration_action_endpoint(
    integration_id: str,
    action_name: str,
    request: ExecuteActionRequest,
):
    """POST /api/integrations/{integration_id}/actions/{action_name}/execute"""
    adapter = integration_registry.get(integration_id)
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration '{integration_id}' not found.",
        )

    if not adapter.is_connected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integration '{integration_id}' is disconnected. Connect it before executing actions.",
        )

    if action_name not in adapter.declared_action_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action '{action_name}' is not supported by integration '{integration_id}'. Supported: {adapter.declared_action_names}",
        )

    action_def = adapter.get_action(action_name)
    if not action_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action definition '{action_name}' not found on integration '{integration_id}'.",
        )

    # Server-side safety gate: prevent bypassing workflow human approval for mutating or unsafe actions
    if not action_def.allow_direct_execution or action_def.is_mutating or action_def.is_destructive or not action_def.is_safe:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Direct standalone execution of action '{action_name}' is forbidden. "
                "Actions that mutate external state or are not declared safe for direct execution "
                "must be executed within an approved workflow."
            ),
        )

    # Validate parameters
    is_valid, err_msg = adapter.validate_action_inputs(action_name, request.parameters)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=err_msg or "Invalid action parameters",
        )

    # Execute action
    result = await adapter.execute_action(
        action_name=action_name,
        parameters=request.parameters,
        context=request.context,
    )

    return result
