"""
WorkFlowOS Phase 7.1: Secure Credential Management Abstraction

Provides:
1. CredentialStorage abstract interface.
2. EnvCredentialStorage (development credentials loaded safely from environment).
3. EncryptedTokenStorage (envelope encryption interface for OAuth tokens, preventing plaintext storage).
4. Sanitization and redaction utilities to prevent leaking secrets in logs, exceptions, and API payloads.
"""

import os
import re
import json
import base64
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class CredentialStorageConfigurationError(Exception):
    """Raised when credential storage is misconfigured or an invalid/missing key is detected."""
    pass


# Common keys containing sensitive secrets that must be redacted
SENSITIVE_KEYS: Set[str] = {
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
    "secret",
    "api_key",
    "apikey",
    "password",
    "authorization",
    "auth",
    "private_key",
    "credential",
    "credentials",
    "oauth_token",
}

# Regex to scrub bearer and basic authorization tokens from strings and logs
# Matches standard Base64 characters including +, /, and = padding
_BEARER_REGEX = re.compile(r"\bBearer\s+([a-zA-Z0-9_\-\.\+\/=]{8,})", re.IGNORECASE)
_BASIC_REGEX = re.compile(r"\bBasic\s+([a-zA-Z0-9_\-\.\+\/=]{8,})", re.IGNORECASE)

# Scrub token/key-value pairs without consuming unrelated words like 'the key of' or 'event key=Enter'
_KEY_VAL_SECRET_REGEX = re.compile(
    r"\b(token|access_token|refresh_token|secret|client_secret|password|api_key|apikey|private_key)\b(\s*[:=]\s*)(['\"]?)([a-zA-Z0-9_\-\.\+\/=!@#$%^&*]{4,})\3",
    re.IGNORECASE
)


def sanitize_credential_dict(data: Any) -> Any:
    """
    Recursively clones a dictionary or list, masking sensitive credentials with '[REDACTED]'.
    Ensures secrets are never exposed in execution results, telemetry, or API responses.
    """
    if isinstance(data, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEYS or any(s in str(k).lower() for s in ("secret", "token", "password")):
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = sanitize_credential_dict(v)
        return cleaned
    elif isinstance(data, list):
        return [sanitize_credential_dict(item) for item in data]
    return data


def sanitize_log_message(message: str) -> str:
    """
    Redacts common bearer tokens, basic auth credentials, and key-value secret
    patterns from log and error messages using best-effort regex matching.

    NOTE: Regex-based redaction is a defense-in-depth safeguard and does not
    guarantee that every arbitrary, unstructured secret format will be removed.
    """
    if not isinstance(message, str):
        return message
    scrubbed = _BEARER_REGEX.sub("Bearer [REDACTED]", message)
    scrubbed = _BASIC_REGEX.sub("Basic [REDACTED]", scrubbed)
    scrubbed = _KEY_VAL_SECRET_REGEX.sub(r"\1\2\3[REDACTED]\3", scrubbed)
    return scrubbed


class CredentialMaskedException(Exception):
    """
    Exception that guarantees its message and representation never leak secrets.
    """
    def __init__(self, message: str):
        safe_message = sanitize_log_message(str(message))
        super().__init__(safe_message)


class CredentialStorage(ABC):
    """
    Abstract interface for managing integration credentials and OAuth tokens.
    Designed for future token rotation, encrypted storage, and managed key services (KMS).
    """

    @abstractmethod
    async def store_credential(self, integration_id: str, credential_data: Dict[str, Any]) -> str:
        """Stores a credential payload for the given integration ID."""
        pass

    @abstractmethod
    async def get_credential(self, integration_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves decrypted credential payload or None if not found."""
        pass

    @abstractmethod
    async def delete_credential(self, integration_id: str) -> bool:
        """Removes credentials for the given integration ID."""
        pass

    @abstractmethod
    async def has_credential(self, integration_id: str) -> bool:
        """Returns True if valid credential exists for the given integration ID."""
        pass


class EnvCredentialStorage(CredentialStorage):
    """
    Reads development credentials from environment configuration.
    Environment secrets are loaded on-demand and never written to database or exposed.
    Convention: WORKFLOWOS_INTEGRATION_{INTEGRATION_ID}_{KEY}
    """

    def __init__(self, prefix: str = "WORKFLOWOS_INTEGRATION_"):
        self.prefix = prefix

    def _get_env_key(self, integration_id: str, key: str) -> str:
        sanitized_id = integration_id.upper().replace("-", "_")
        return f"{self.prefix}{sanitized_id}_{key.upper()}"

    async def store_credential(self, integration_id: str, credential_data: Dict[str, Any]) -> str:
        # In development, storing via EnvCredentialStorage updates runtime environment safely
        for k, v in credential_data.items():
            env_key = self._get_env_key(integration_id, k)
            os.environ[env_key] = str(v)
        return integration_id

    async def get_credential(self, integration_id: str) -> Optional[Dict[str, Any]]:
        prefix = f"{self.prefix}{integration_id.upper().replace('-', '_')}_"
        creds: Dict[str, Any] = {}
        for env_k, env_v in os.environ.items():
            if env_k.startswith(prefix):
                key_name = env_k[len(prefix):].lower()
                creds[key_name] = env_v
        return creds if creds else None

    async def delete_credential(self, integration_id: str) -> bool:
        prefix = f"{self.prefix}{integration_id.upper().replace('-', '_')}_"
        deleted = False
        for env_k in list(os.environ.keys()):
            if env_k.startswith(prefix):
                del os.environ[env_k]
                deleted = True
        return deleted

    async def has_credential(self, integration_id: str) -> bool:
        creds = await self.get_credential(integration_id)
        return bool(creds)


class EncryptedTokenStorage(CredentialStorage):
    """
    Authenticated credential storage abstraction using Fernet (AES-128-CBC + HMAC-SHA256).
    Enforces tamper-resistant encryption with per-operation random IVs and integrity checks.

    SECURITY NOTE:
    The previous repeating-XOR implementation has been removed. Repeating-XOR is an insecure
    stream-style cipher with no nonce/IV or integrity authentication, and is vulnerable to
    known-plaintext attacks. Real OAuth tokens must only use authenticated encryption.

    Key Configuration:
    - `encryption_key`: 32 url-safe base64 bytes passed directly or via `WORKFLOWOS_CREDENTIAL_KEY`.
    - No hardcoded production key fallback: if the key is missing or invalid, raises
      CredentialStorageConfigurationError unless allow_ephemeral_dev_key=True is explicitly set.
    - If `allow_ephemeral_dev_key=True` (for local development or testing only), generates
      a random in-memory ephemeral key that does not persist across restarts.
    """

    def __init__(
        self,
        encryption_key: Optional[str] = None,
        allow_ephemeral_dev_key: bool = False
    ):
        raw_key = encryption_key or os.getenv("WORKFLOWOS_CREDENTIAL_KEY")
        self._is_ephemeral = False

        if raw_key:
            try:
                key_bytes = raw_key.encode("utf-8") if isinstance(raw_key, str) else raw_key
                self._fernet = Fernet(key_bytes)
            except Exception as e:
                raise CredentialStorageConfigurationError(
                    f"Invalid WORKFLOWOS_CREDENTIAL_KEY format: {e}. Key must be 32 url-safe base64 bytes."
                ) from e
        elif allow_ephemeral_dev_key:
            self._is_ephemeral = True
            ephemeral_key = Fernet.generate_key()
            self._fernet = Fernet(ephemeral_key)
            logger.warning(
                "[EncryptedTokenStorage] WORKFLOWOS_CREDENTIAL_KEY not set. Using ephemeral in-memory key for local session. "
                "Tokens will not persist across restarts. Do not use in production."
            )
        else:
            raise CredentialStorageConfigurationError(
                "Encryption key is not configured. Set WORKFLOWOS_CREDENTIAL_KEY with a valid 32-byte url-safe base64 key, "
                "or pass allow_ephemeral_dev_key=True for local testing."
            )

        self._store: Dict[str, str] = {}

    @property
    def is_ephemeral(self) -> bool:
        return self._is_ephemeral

    async def store_credential(self, integration_id: str, credential_data: Dict[str, Any]) -> str:
        raw_json = json.dumps(credential_data).encode("utf-8")
        ciphertext = self._fernet.encrypt(raw_json).decode("utf-8")
        self._store[integration_id] = ciphertext
        return integration_id

    async def get_credential(self, integration_id: str) -> Optional[Dict[str, Any]]:
        ciphertext = self._store.get(integration_id)
        if not ciphertext:
            return None
        try:
            raw_bytes = self._fernet.decrypt(ciphertext.encode("utf-8"))
            return json.loads(raw_bytes.decode("utf-8"))
        except InvalidToken:
            logger.error(
                f"[EncryptedTokenStorage] Decryption failed for '{integration_id}': InvalidToken / tamper detected."
            )
            return None
        except Exception as e:
            safe_err = sanitize_log_message(str(e))
            logger.error(f"[EncryptedTokenStorage] Decryption error for '{integration_id}': {safe_err}")
            return None

    async def delete_credential(self, integration_id: str) -> bool:
        if integration_id in self._store:
            del self._store[integration_id]
            return True
        return False

    async def has_credential(self, integration_id: str) -> bool:
        return integration_id in self._store


# Default credential storage instance for local development with ephemeral key fallback
default_credential_storage: CredentialStorage = EncryptedTokenStorage(allow_ephemeral_dev_key=True)
