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

# Automatically seed the default mock integration adapter into registry
if not integration_registry.get("mock_service"):
    integration_registry.register(MockTestIntegrationAdapter())

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
    "BaseIntegrationAdapter",
    "IntegrationRegistry",
    "integration_registry",
    "CredentialStorage",
    "EnvCredentialStorage",
    "EncryptedTokenStorage",
    "sanitize_credential_dict",
    "sanitize_log_message",
    "CredentialMaskedException",
    "MockTestIntegrationAdapter",
    "IntegrationExecutor",
]
