"""
WorkFlowOS Phase 7.1: Integration Foundation Package

Provides abstractions, registry, secure credential handling, and mock adapter
for extensible service integrations.
"""

from integrations.models import (
    IntegrationStatus,
    ParameterType,
    ActionParameterDefinition,
    IntegrationActionDefinition,
    IntegrationMetadata,
    IntegrationSummary,
    IntegrationActionResult,
    IntegrationError,
    UnknownIntegrationError,
    DuplicateIntegrationError,
    UnsupportedActionError,
    IntegrationConnectionError,
    IntegrationValidationError,
)
from integrations.base import BaseIntegrationAdapter
from integrations.registry import IntegrationRegistry, integration_registry
from integrations.credentials import (
    CredentialStorage,
    EnvCredentialStorage,
    EncryptedTokenStorage,
    sanitize_credential_dict,
    sanitize_log_message,
    CredentialMaskedException,
)
from integrations.mock import MockTestIntegrationAdapter
from integrations.executor import IntegrationExecutor
from integrations.oauth import (
    OAuthStateStore,
    GoogleOAuthManager,
    GMAIL_READONLY_SCOPE,
    default_oauth_state_store,
    default_google_oauth_manager,
)
from integrations.gmail import GmailIntegrationAdapter, get_oauth_token_storage
from integrations.crm import CrmIntegrationAdapter
from integrations.chat import ChatIntegrationAdapter
from integrations.registry import ApplicationRegistry, application_registry
from integrations.models import (
    ApplicationHealthStatus,
    ApplicationHealth,
    ApplicationCapability,
    ApplicationSummary,
)

# Automatically seed ecosystem applications into registry
if not integration_registry.get("mock_service"):
    integration_registry.register(MockTestIntegrationAdapter())

if not integration_registry.get("gmail"):
    integration_registry.register(GmailIntegrationAdapter())

if not integration_registry.get("crm"):
    integration_registry.register(CrmIntegrationAdapter())

if not integration_registry.get("chat"):
    integration_registry.register(ChatIntegrationAdapter())

__all__ = [
    "IntegrationStatus",
    "ParameterType",
    "ActionParameterDefinition",
    "IntegrationActionDefinition",
    "IntegrationMetadata",
    "IntegrationSummary",
    "IntegrationActionResult",
    "IntegrationError",
    "UnknownIntegrationError",
    "DuplicateIntegrationError",
    "UnsupportedActionError",
    "IntegrationConnectionError",
    "IntegrationValidationError",
    "ApplicationHealthStatus",
    "ApplicationHealth",
    "ApplicationCapability",
    "ApplicationSummary",
    "BaseIntegrationAdapter",
    "IntegrationRegistry",
    "integration_registry",
    "ApplicationRegistry",
    "application_registry",
    "CredentialStorage",
    "EnvCredentialStorage",
    "EncryptedTokenStorage",
    "sanitize_credential_dict",
    "sanitize_log_message",
    "CredentialMaskedException",
    "MockTestIntegrationAdapter",
    "CrmIntegrationAdapter",
    "ChatIntegrationAdapter",
    "IntegrationExecutor",
    "OAuthStateStore",
    "GoogleOAuthManager",
    "GMAIL_READONLY_SCOPE",
    "default_oauth_state_store",
    "default_google_oauth_manager",
    "GmailIntegrationAdapter",
    "get_oauth_token_storage",
]
