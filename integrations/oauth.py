"""
WorkFlowOS Phase 7.2: Google OAuth 2.0 Security & State Manager

Provides:
1. OAuthStateStore: Single-use, time-bound CSRF token store for OAuth authorization flows.
2. GoogleOAuthManager: Encapsulates authorization URL generation, code-for-token exchange,
   token refresh, and revocation using official Google OAuth 2.0 endpoints.
3. Cryptographically secure token handling with zero secret leaks.
"""

import os
import time
import secrets
import logging
import urllib.parse
from typing import Dict, Any, Optional
import httpx

from integrations.credentials import sanitize_log_message

logger = logging.getLogger(__name__)

# Official Google OAuth 2.0 Endpoints
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"

# Minimum required read-only scope for listing message metadata
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class OAuthConfigurationError(Exception):
    """Raised when required OAuth environment configuration is missing or invalid."""
    pass


class OAuthStateError(Exception):
    """Raised when OAuth state token validation fails (missing, invalid, or expired)."""
    pass


class OAuthTokenExchangeError(Exception):
    """Raised when exchanging authorization code or refreshing token fails."""
    pass


class OAuthStateStore:
    """
    In-memory, single-use, time-bound CSRF state manager for local single-user desktop MVP.

    Guarantees:
    - Cryptographically random state values (secrets.token_urlsafe(32)).
    - Strict time-to-live (default 10 minutes).
    - Immediate single-use consumption upon validation (defense against replay).
    - Automated cleanup of expired state tokens.
    """

    def __init__(self, default_ttl_seconds: int = 600):
        self._default_ttl = default_ttl_seconds
        # Maps state -> expiration timestamp (float)
        self._states: Dict[str, float] = {}

    def create_state(self, ttl_seconds: Optional[int] = None) -> str:
        """Generates a cryptographically random state token bound to a short-lived TTL."""
        self._cleanup_expired()
        state = secrets.token_urlsafe(32)
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        self._states[state] = time.time() + ttl
        return state

    def validate_and_consume(self, state: Optional[str]) -> bool:
        """
        Validates and consumes a state token.
        Returns True if valid and not expired. Returns False otherwise.
        Once validated (or failed), the token cannot be reused.
        """
        self._cleanup_expired()
        if not state or not isinstance(state, str):
            return False

        # Pop token immediately to ensure single-use
        exp_time = self._states.pop(state, None)
        if exp_time is None:
            logger.warning("[OAuthStateStore] Rejected unknown or already-consumed state token.")
            return False

        if time.time() > exp_time:
            logger.warning("[OAuthStateStore] Rejected expired OAuth state token.")
            return False

        return True

    def _cleanup_expired(self) -> None:
        """Purges expired states to prevent memory leaks."""
        now = time.time()
        expired_keys = [k for k, exp in self._states.items() if now > exp]
        for k in expired_keys:
            self._states.pop(k, None)


class GoogleOAuthManager:
    """
    Manages Google OAuth 2.0 authorization-code flow for WorkFlowOS.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self._client_id = (
            client_id if client_id is not None else os.getenv("GOOGLE_CLIENT_ID", "")
        ).strip()
        self._client_secret = (
            client_secret if client_secret is not None else os.getenv("GOOGLE_CLIENT_SECRET", "")
        ).strip()
        self._redirect_uri = (
            redirect_uri if redirect_uri is not None else os.getenv(
                "GOOGLE_REDIRECT_URI",
                "http://127.0.0.1:8000/api/integrations/gmail/callback"
            )
        ).strip()
        self._http_client = http_client

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def redirect_uri(self) -> str:
        return self._redirect_uri

    def is_configured(self) -> bool:
        """Returns True if all required Google OAuth client credentials are configured."""
        return bool(self._client_id and self._client_secret and self._redirect_uri)

    def validate_configuration(self) -> None:
        """Validates that Google OAuth environment is configured, or raises OAuthConfigurationError."""
        if not self._client_id:
            raise OAuthConfigurationError(
                "Missing GOOGLE_CLIENT_ID. Please configure it in your environment or .env file."
            )
        if not self._client_secret:
            raise OAuthConfigurationError(
                "Missing GOOGLE_CLIENT_SECRET. Please configure it in your environment or .env file."
            )
        if not self._redirect_uri:
            raise OAuthConfigurationError(
                "Missing GOOGLE_REDIRECT_URI. Please configure it in your environment or .env file."
            )

    def build_authorization_url(
        self,
        state: str,
        scope: str = GMAIL_READONLY_SCOPE,
        prompt: str = "consent",
        access_type: str = "offline",
    ) -> str:
        """
        Builds Google's OAuth 2.0 authorization URL with required security parameters.
        Forces offline access and prompt=consent to ensure a refresh token is returned.
        """
        self.validate_configuration()

        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": scope,
            "access_type": access_type,
            "prompt": prompt,
            "state": state,
        }
        return f"{GOOGLE_AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchanges authorization code for Google OAuth tokens server-side.
        Never logs or exposes tokens or client secrets.
        """
        self.validate_configuration()
        if not code or not isinstance(code, str):
            raise OAuthTokenExchangeError("Authorization code is required.")

        payload = {
            "code": code,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": self._redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            if self._http_client:
                res = await self._http_client.post(
                    GOOGLE_TOKEN_ENDPOINT,
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=15.0,
                )
            else:
                async with httpx.AsyncClient() as client:
                    res = await client.post(
                        GOOGLE_TOKEN_ENDPOINT,
                        data=payload,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        timeout=15.0,
                    )
        except Exception as e:
            safe_err = sanitize_log_message(str(e))
            logger.error(f"[GoogleOAuthManager] Network failure during token exchange: {safe_err}")
            raise OAuthTokenExchangeError(f"Network error during OAuth token exchange: {safe_err}") from None

        if res.status_code != 200:
            safe_detail = sanitize_log_message(res.text)
            logger.error(f"[GoogleOAuthManager] Token exchange rejected by Google ({res.status_code}): {safe_detail}")
            raise OAuthTokenExchangeError(
                f"Google OAuth token exchange failed with status {res.status_code}. Verify client credentials."
            )

        token_data = res.json()
        expires_in = token_data.get("expires_in", 3600)

        return {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": expires_in,
            "expires_at": time.time() + float(expires_in),
            "token_type": token_data.get("token_type", "Bearer"),
            "scope": token_data.get("scope", GMAIL_READONLY_SCOPE),
        }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refreshes an expired access token using the stored refresh token.
        """
        self.validate_configuration()
        if not refresh_token:
            raise OAuthTokenExchangeError("No refresh token available for token refresh.")

        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            if self._http_client:
                res = await self._http_client.post(
                    GOOGLE_TOKEN_ENDPOINT,
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=15.0,
                )
            else:
                async with httpx.AsyncClient() as client:
                    res = await client.post(
                        GOOGLE_TOKEN_ENDPOINT,
                        data=payload,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        timeout=15.0,
                    )
        except Exception as e:
            safe_err = sanitize_log_message(str(e))
            logger.error(f"[GoogleOAuthManager] Network failure during token refresh: {safe_err}")
            raise OAuthTokenExchangeError(f"Network error during token refresh: {safe_err}") from None

        if res.status_code != 200:
            safe_detail = sanitize_log_message(res.text)
            logger.error(f"[GoogleOAuthManager] Token refresh rejected by Google ({res.status_code}): {safe_detail}")
            raise OAuthTokenExchangeError(
                f"Google OAuth token refresh failed with status {res.status_code}."
            )

        token_data = res.json()
        expires_in = token_data.get("expires_in", 3600)

        result: Dict[str, Any] = {
            "access_token": token_data.get("access_token"),
            "expires_in": expires_in,
            "expires_at": time.time() + float(expires_in),
            "token_type": token_data.get("token_type", "Bearer"),
            "scope": token_data.get("scope", GMAIL_READONLY_SCOPE),
        }
        # Google may or may not return a new refresh token during refresh
        if "refresh_token" in token_data:
            result["refresh_token"] = token_data["refresh_token"]

        return result

    async def revoke_token(self, token: str) -> bool:
        """
        Revokes an OAuth access or refresh token with Google's revocation endpoint.
        Fails safely without raising exceptions or leaking tokens.
        """
        if not token:
            return True

        params = {"token": token}
        try:
            if self._http_client:
                res = await self._http_client.post(
                    f"{GOOGLE_REVOKE_ENDPOINT}?{urllib.parse.urlencode(params)}",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10.0,
                )
            else:
                async with httpx.AsyncClient() as client:
                    res = await client.post(
                        f"{GOOGLE_REVOKE_ENDPOINT}?{urllib.parse.urlencode(params)}",
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        timeout=10.0,
                    )
            if res.status_code == 200:
                logger.info("[GoogleOAuthManager] Successfully revoked OAuth token with Google.")
                return True
            else:
                safe_err = sanitize_log_message(res.text)
                logger.warning(
                    f"[GoogleOAuthManager] Google revocation endpoint returned status {res.status_code}: {safe_err}"
                )
                return False
        except Exception as e:
            safe_err = sanitize_log_message(str(e))
            logger.warning(f"[GoogleOAuthManager] Error calling revocation endpoint: {safe_err}")
            return False


# Global singleton instances for application runtime
default_oauth_state_store = OAuthStateStore()
default_google_oauth_manager = GoogleOAuthManager()
