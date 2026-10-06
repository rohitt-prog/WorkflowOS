"""
WorkFlowOS Phase 7.1: Integration Foundation Models & Schemas

Defines core data models, parameter validation schemas, status enums,
and structured result types for external and mock service integrations.
"""

from enum import Enum
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class IntegrationStatus(str, Enum):
    """Lifecycle connection status of an integration adapter."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


class ParameterType(str, Enum):
    """Allowed data types for action parameter definitions."""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


class ActionParameterDefinition(BaseModel):
    """
    Schema definition for an input parameter of an integration action.
    Used for strict input validation before action dispatch.
    """
    name: str = Field(..., description="Parameter key name")
    type: ParameterType = Field(default=ParameterType.STRING, description="Expected parameter data type")
    required: bool = Field(default=False, description="Whether this parameter must be provided")
    default: Optional[Any] = Field(default=None, description="Default value if omitted")
    description: Optional[str] = Field(default=None, description="Human description of the parameter")
    allowed_values: Optional[List[Any]] = Field(default=None, description="Enumerated allowed values if restricted")


class IntegrationActionDefinition(BaseModel):
    """
    Declaration of a capability/action exposed by an integration adapter.
    """
    name: str = Field(..., description="Unique action verb within the adapter (e.g. 'mock_echo')")
    display_name: str = Field(..., description="Human-friendly label")
    description: str = Field(..., description="Detailed description of what the action does")
    parameters: List[ActionParameterDefinition] = Field(
        default_factory=list,
        description="Declared parameter schema definitions"
    )
    required_scopes: List[str] = Field(
        default_factory=list,
        description="Permission scopes required by this action"
    )
    is_safe: bool = Field(default=True, description="Whether the action is safe / non-destructive")
    is_mutating: bool = Field(default=False, description="Whether the action mutates external or local state")
    is_destructive: bool = Field(default=False, description="Flag indicating potential data mutation or deletion")
    allow_direct_execution: bool = Field(
        default=False,
        description="Server-side declaration allowing direct standalone execution outside workflow engine"
    )
    supported_strategies: List[str] = Field(
        default_factory=list,
        description="Supported automation strategies (e.g. ['API', 'INTEGRATION', 'BROWSER'])"
    )
    requires_approval: Optional[bool] = Field(
        default=None,
        description="Whether this action explicitly requires human approval (defaults to True if mutating)"
    )


# ── Phase 13 Application Ecosystem Models ───────────────────────────────────

class ApplicationHealthStatus(str, Enum):
    """Health & connection lifecycle status of an application."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"


class ApplicationHealth(BaseModel):
    """
    Lightweight health/connection status for an application in the ecosystem.
    """
    application_id: str = Field(..., description="Target application identifier")
    status: ApplicationHealthStatus = Field(..., description="Current health/connection status")
    is_healthy: bool = Field(..., description="Whether application is currently operational")
    message: str = Field(..., description="Status summary or diagnostic message")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO UTC check timestamp"
    )
    details: Optional[Dict[str, Any]] = Field(default=None, description="Optional diagnostic details")

    @property
    def connected(self) -> bool:
        """Convenience property indicating active connection."""
        return self.status == ApplicationHealthStatus.CONNECTED


class ApplicationCapability(BaseModel):
    """
    Structured representation of a capability/action exposed by an application.
    """
    action_id: str = Field(..., description="Canonical action ID (e.g. 'gmail.search_messages', 'crm.update_customer')")
    application_id: str = Field(..., description="Application identifier (e.g. 'gmail', 'crm')")
    name: str = Field(..., description="Action verb (e.g. 'search_messages', 'update_customer')")
    display_name: str = Field(..., description="Human-friendly label")
    description: str = Field(..., description="Detailed capability description")
    category: str = Field(default="general", description="Capability category")
    read_only: bool = Field(default=True, description="Whether action is read-only")
    mutating: bool = Field(default=False, description="Whether action mutates state")
    requires_credentials: bool = Field(default=False, description="Whether authentication is required")
    requires_approval: bool = Field(default=False, description="Whether approval is mandatory (always True if mutating)")
    supported_strategies: List[str] = Field(default_factory=list, description="Supported automation strategies (API, INTEGRATION, BROWSER)")
    parameters: List[ActionParameterDefinition] = Field(default_factory=list, description="Parameter schema definitions")
    reliability: Optional[Dict[str, Any]] = Field(default=None, description="Reliability metadata")


class ApplicationSummary(BaseModel):
    """
    Public API representation of an application in the ecosystem.
    """
    application_id: str = Field(..., description="Unique application identifier")
    display_name: str = Field(..., description="Display title")
    description: str = Field(..., description="Explanation of application purpose")
    version: str = Field(default="1.0.0", description="Semantic version string")
    category: str = Field(default="general", description="Application category")
    icon: Optional[str] = Field(default=None, description="Icon key")
    integration_type: str = Field(default="api", description="Type: 'oauth', 'demo', 'mock', 'api'")
    is_mock: bool = Field(default=False, description="Whether this is a simulated demo/mock application")
    disclaimer: Optional[str] = Field(default=None, description="User-facing disclaimer")
    health: ApplicationHealth = Field(..., description="Current lightweight health status")
    is_connected: bool = Field(..., description="Whether application is connected")
    connected_at: Optional[str] = Field(default=None, description="ISO timestamp of connection")
    capabilities: List[ApplicationCapability] = Field(default_factory=list, description="Exposed capabilities")


class IntegrationMetadata(BaseModel):
    """
    Static metadata identifying an integration adapter.
    """
    id: str = Field(..., description="Unique deterministic identifier (e.g. 'mock_service')")
    name: str = Field(..., description="Display title of the integration")
    description: str = Field(..., description="Explanation of integration purpose")
    version: str = Field(default="1.0.0", description="Semantic version string")
    category: str = Field(default="developer", description="Category: developer, testing, productivity, crm, etc.")
    icon: Optional[str] = Field(default=None, description="Icon identifier or SVG key")
    is_mock: bool = Field(default=False, description="True if this is a non-production mock adapter")
    disclaimer: Optional[str] = Field(
        default=None,
        description="Clear user-facing disclaimer regarding real vs simulated status"
    )


class IntegrationSummary(BaseModel):
    """
    API representation of an integration including status and capabilities.
    """
    id: str
    name: str
    description: str
    version: str
    category: str
    icon: Optional[str] = None
    is_mock: bool
    disclaimer: Optional[str] = None
    status: IntegrationStatus
    is_connected: bool
    connected_at: Optional[str] = None
    last_error: Optional[str] = None
    actions: List[IntegrationActionDefinition] = Field(default_factory=list)


class IntegrationActionResult(BaseModel):
    """
    Deterministic result of executing an integration action.
    """
    action_name: str = Field(..., description="Name of executed action")
    success: bool = Field(..., description="Whether action succeeded")
    message: str = Field(..., description="Status summary or error message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Output payload produced by action")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO UTC execution timestamp"
    )
    error_code: Optional[str] = Field(default=None, description="Machine-readable error code if failed")


# ── Exception Hierarchy ──────────────────────────────────────────────────────

class IntegrationError(Exception):
    """Base exception for integration-related operations."""
    pass


class UnknownIntegrationError(IntegrationError):
    """Raised when an action or lookup targets an unregistered integration ID."""
    pass


class DuplicateIntegrationError(IntegrationError):
    """Raised when registering an integration ID that already exists in the registry."""
    pass


class UnsupportedActionError(IntegrationError):
    """Raised when an action is not declared by the target integration adapter."""
    pass


class IntegrationConnectionError(IntegrationError):
    """Raised when attempting action execution while the integration is disconnected."""
    pass


class IntegrationValidationError(IntegrationError):
    """Raised when action parameters fail schema validation."""
    pass
