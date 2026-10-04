"""
WorkFlowOS Phase 7.2: Gmail Integration Adapter

Implements the BaseIntegrationAdapter interface for Google Workspace Gmail:
1. Real provider integration (is_mock=False).
2. Read-only message listing capability (list_recent_messages).
3. Server-side token retrieval with automated refresh via EncryptedTokenStorage.
4. Token revocation on disconnect.
5. Strict schema validation, parameter bounding (max 20 messages), and credential safety.
"""

import time
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
import httpx

from integrations.base import BaseIntegrationAdapter
from integrations.models import (
    IntegrationMetadata,
    IntegrationStatus,
    IntegrationActionDefinition,
    ActionParameterDefinition,
    ParameterType,
    IntegrationActionResult,
    IntegrationConnectionError,
    IntegrationValidationError,
)
from integrations.credentials import (
    CredentialStorage,
    EncryptedTokenStorage,
    sanitize_credential_dict,
    sanitize_log_message,
)
from integrations.oauth import (
    GoogleOAuthManager,
    default_google_oauth_manager,
    GMAIL_READONLY_SCOPE,
)

logger = logging.getLogger(__name__)

# Gmail API Base URL
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


def get_oauth_token_storage() -> EncryptedTokenStorage:
    """
    Returns the server-side EncryptedTokenStorage configured for real OAuth tokens.
    Fails closed (allow_ephemeral_dev_key=False) if WORKFLOWOS_CREDENTIAL_KEY is missing or invalid.
    """
    return EncryptedTokenStorage(allow_ephemeral_dev_key=False)


class GmailIntegrationAdapter(BaseIntegrationAdapter):
    """
    Integration adapter for Google Workspace Gmail.
    Provides verified OAuth connection lifecycle and read-only message inspection.
    """

    def __init__(
        self,
        oauth_manager: Optional[GoogleOAuthManager] = None,
        token_storage: Optional[CredentialStorage] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self._oauth_manager = oauth_manager or default_google_oauth_manager
        self._token_storage = token_storage
        self._http_client = http_client
        self._refresh_lock = asyncio.Lock()

        metadata = IntegrationMetadata(
            id="gmail",
            name="Gmail",
            description="Google Workspace Gmail integration for reading email metadata and message summaries.",
            version="1.0.0",
            category="email",
            icon="mail",
            is_mock=False,
            disclaimer="Requires Google OAuth authorization. Operates in read-only mode.",
        )
        super().__init__(metadata)

    def _get_storage(self) -> CredentialStorage:
        """Lazily obtains and memoizes token storage on the adapter instance to ensure a single shared store."""
        if self._token_storage is not None:
            return self._token_storage
        self._token_storage = get_oauth_token_storage()
        return self._token_storage

    def _register_capabilities(self) -> None:
        """Registers declared actions for Gmail adapter."""
        self.register_action(
            IntegrationActionDefinition(
                name="list_recent_messages",
                display_name="List Recent Messages",
                description="Lists recent Gmail messages and retrieves metadata (sender, subject, date, snippet).",
                parameters=[
                    ActionParameterDefinition(
                        name="max_results",
                        type=ParameterType.INTEGER,
                        required=False,
                        default=5,
                        description="Maximum number of messages to return (between 1 and 20).",
                    ),
                    ActionParameterDefinition(
                        name="query",
                        type=ParameterType.STRING,
                        required=False,
                        default="",
                        description="Optional Gmail search filter query (e.g. 'is:unread', 'from:alice@example.com').",
                    ),
                ],
                required_scopes=[GMAIL_READONLY_SCOPE],
                is_safe=True,
                is_mutating=False,
                is_destructive=False,
                allow_direct_execution=False,
            ),
            handler=self._handle_list_recent_messages,
        )

    def validate_action_inputs(
        self,
        action_name: str,
        parameters: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates parameters against schema and enforces strict read-only bounds.
        """
        is_valid, err = super().validate_action_inputs(action_name, parameters)
        if not is_valid:
            return False, err

        if action_name == "list_recent_messages":
            raw_max = (parameters or {}).get("max_results")
            if raw_max is not None:
                if not isinstance(raw_max, int) or isinstance(raw_max, bool):
                    return False, "Parameter 'max_results' must be an integer."
                if raw_max < 1:
                    return False, "Parameter 'max_results' must be at least 1."
                if raw_max > 20:
                    return False, "Parameter 'max_results' cannot exceed 20 for read-only inspection."

        return True, None

    async def _do_connect(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """
        Connects Gmail adapter by storing and validating OAuth credentials.
        Direct credential injection is disallowed; credentials must originate from internal OAuth flow.
        """
        storage = self._get_storage()

        if credentials and isinstance(credentials, dict):
            # Enforce that credentials originate strictly from internal OAuth flow (SEC-05)
            if not credentials.get("_internal_oauth_source"):
                self._last_error = (
                    "Direct credential submission is not permitted for Gmail adapter. "
                    "Please authorize through the Google OAuth flow."
                )
                return False

            # If reconnecting, preserve existing refresh token if Google didn't issue a new one
            existing_creds = await storage.get_credential(self.id) or {}
            merged_creds = dict(existing_creds)
            merged_creds.update(credentials)

            if not merged_creds.get("access_token"):
                self._last_error = "OAuth credentials missing access_token."
                return False

            creds_to_persist = dict(merged_creds)
            creds_to_persist.pop("_internal_oauth_source", None)
            await storage.store_credential(self.id, creds_to_persist)
            return True

        # If connect called without credentials, verify stored credentials exist
        stored = await storage.get_credential(self.id)
        if not stored or not stored.get("access_token"):
            self._last_error = "No valid Gmail credentials found. Please authorize via Google OAuth."
            return False

        return True

    async def _do_disconnect(self) -> None:
        """
        Disconnects Gmail adapter: revokes token with Google and purges local encrypted storage.
        """
        storage = self._get_storage()
        try:
            creds = await storage.get_credential(self.id)
            if creds:
                token_to_revoke = creds.get("refresh_token") or creds.get("access_token")
                if token_to_revoke:
                    await self._oauth_manager.revoke_token(token_to_revoke)
        except Exception as e:
            logger.warning(f"[{self.id}] Notice during token revocation: {sanitize_log_message(str(e))}")
        finally:
            await storage.delete_credential(self.id)

    async def get_valid_access_token(self) -> str:
        """
        Retrieves a valid decrypted access token, automatically refreshing if expired.
        Protected with asyncio.Lock and double-checked locking to handle concurrent requests safely.
        Raises IntegrationConnectionError on failure.
        """
        storage = self._get_storage()
        creds = await storage.get_credential(self.id)
        if not creds or not creds.get("access_token"):
            raise IntegrationConnectionError(
                "Gmail is not connected. Please authorize Gmail in Settings."
            )

        expires_at = creds.get("expires_at", 0)
        # Refresh if token expired or within 60-second expiration buffer
        if time.time() >= (expires_at - 60):
            async with self._refresh_lock:
                # Double-check inside lock: another coroutine may have refreshed it already
                creds = await storage.get_credential(self.id)
                if not creds or not creds.get("access_token"):
                    raise IntegrationConnectionError(
                        "Gmail is not connected. Please authorize Gmail in Settings."
                    )

                expires_at = creds.get("expires_at", 0)
                if time.time() < (expires_at - 60):
                    return creds["access_token"]

                refresh_tok = creds.get("refresh_token")
                if not refresh_tok:
                    raise IntegrationConnectionError(
                        "Gmail access token has expired and no refresh token is available. Please reconnect."
                    )

                logger.info(f"[{self.id}] Access token expired. Refreshing token with Google...")
                try:
                    new_tokens = await self._oauth_manager.refresh_access_token(refresh_tok)
                    updated_creds = dict(creds)
                    updated_creds.update(new_tokens)
                    await storage.store_credential(self.id, updated_creds)
                    return updated_creds["access_token"]
                except Exception as e:
                    safe_err = sanitize_log_message(str(e))
                    self._status = IntegrationStatus.ERROR
                    self._last_error = f"Token refresh failed: {safe_err}"
                    raise IntegrationConnectionError(
                        f"Failed to refresh expired Gmail token: {safe_err}. Please reconnect."
                    ) from None

        return creds["access_token"]

    async def _handle_list_recent_messages(
        self,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes read-only action 'list_recent_messages'.
        Fetches message IDs and retrieves sender, subject, date, snippet metadata.
        """
        # 1. Parameter Validation & Bounding
        raw_max = parameters.get("max_results", 5)
        try:
            max_results = int(raw_max)
        except (ValueError, TypeError):
            max_results = 5

        if max_results < 1:
            raise IntegrationValidationError("Parameter 'max_results' must be at least 1.")
        if max_results > 20:
            raise IntegrationValidationError("Parameter 'max_results' cannot exceed 20 for read-only inspection.")

        query = str(parameters.get("query", "")).strip()

        # 2. Token Retrieval
        access_token = await self.get_valid_access_token()

        # 3. Request message listing from Gmail API
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        list_params = {"maxResults": max_results}
        if query:
            list_params["q"] = query

        list_url = f"{GMAIL_API_BASE}/messages"

        try:
            if self._http_client:
                list_res = await self._http_client.get(
                    list_url,
                    headers=headers,
                    params=list_params,
                    timeout=15.0,
                )
            else:
                async with httpx.AsyncClient() as client:
                    list_res = await client.get(
                        list_url,
                        headers=headers,
                        params=list_params,
                        timeout=15.0,
                    )
        except Exception as e:
            safe_err = sanitize_log_message(str(e))
            logger.error(f"[{self.id}] Network error querying messages: {safe_err}")
            raise IntegrationConnectionError(f"Network error communicating with Gmail API: {safe_err}") from e

        if list_res.status_code == 401:
            self._status = IntegrationStatus.ERROR
            self._last_error = "Gmail authorization expired or was revoked. Please reconnect."
            raise IntegrationConnectionError("Gmail authorization expired or was revoked. Please reconnect.")
        elif list_res.status_code == 403:
            safe_err = sanitize_log_message(list_res.text)
            raise IntegrationConnectionError(f"Gmail API permission denied (403): {safe_err}")
        elif list_res.status_code in (429, 503):
            raise IntegrationConnectionError("Gmail API rate limit exceeded or service unavailable. Please retry later.")
        elif list_res.status_code != 200:
            safe_err = sanitize_log_message(list_res.text)
            raise IntegrationConnectionError(f"Gmail API error ({list_res.status_code}): {safe_err}")

        list_data = list_res.json()
        raw_messages: List[Dict[str, Any]] = list_data.get("messages", [])

        # 4. Fetch metadata for each message (strictly headers and snippet; no full body)
        messages_result: List[Dict[str, Any]] = []
        for msg_item in raw_messages[:max_results]:
            msg_id = msg_item.get("id")
            if not msg_id:
                continue

            msg_url = f"{GMAIL_API_BASE}/messages/{msg_id}"
            detail_params = [
                ("format", "metadata"),
                ("metadataHeaders", "From"),
                ("metadataHeaders", "Subject"),
                ("metadataHeaders", "Date"),
            ]

            try:
                if self._http_client:
                    detail_res = await self._http_client.get(
                        msg_url,
                        headers=headers,
                        params=detail_params,
                        timeout=10.0,
                    )
                else:
                    async with httpx.AsyncClient() as client:
                        detail_res = await client.get(
                            msg_url,
                            headers=headers,
                            params=detail_params,
                            timeout=10.0,
                        )

                if detail_res.status_code == 200:
                    d_json = detail_res.json()
                    headers_list = d_json.get("payload", {}).get("headers", [])
                    header_map = {
                        str(h.get("name", "")).lower(): str(h.get("value", ""))
                        for h in headers_list
                    }

                    messages_result.append({
                        "id": msg_id,
                        "thread_id": d_json.get("threadId", ""),
                        "from": header_map.get("from", ""),
                        "subject": header_map.get("subject", ""),
                        "date": header_map.get("date", ""),
                        "snippet": d_json.get("snippet", ""),
                    })
                else:
                    # Gracefully include stub on individual item failure
                    messages_result.append({
                        "id": msg_id,
                        "thread_id": msg_item.get("threadId", ""),
                        "from": "Unknown",
                        "subject": f"Unable to fetch metadata ({detail_res.status_code})",
                        "date": "",
                        "snippet": "",
                    })
            except Exception as e:
                logger.warning(f"[{self.id}] Failed to fetch metadata for message '{msg_id}': {sanitize_log_message(str(e))}")
                messages_result.append({
                    "id": msg_id,
                    "thread_id": msg_item.get("threadId", ""),
                    "from": "Unknown",
                    "subject": "Error loading message",
                    "date": "",
                    "snippet": "",
                })

        return {
            "service": self.id,
            "action": "list_recent_messages",
            "count": len(messages_result),
            "query": query,
            "messages": messages_result,
        }
