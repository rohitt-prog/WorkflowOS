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
from fastapi import APIRouter, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse

from backend.config import settings
from integrations.registry import integration_registry
from integrations.models import (
    IntegrationSummary,
    IntegrationActionResult,
    UnknownIntegrationError,
    UnsupportedActionError,
    IntegrationConnectionError,
    IntegrationValidationError,
)
import os
import hmac
import urllib.parse
from integrations.credentials import sanitize_credential_dict, sanitize_log_message
from integrations.oauth import (
    default_oauth_state_store,
    default_google_oauth_manager,
    OAuthConfigurationError,
    OAuthTokenExchangeError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def _validate_origin_for_csrf(request: Request) -> None:
    """
    SEC-04: Validates Origin and Fetch Metadata headers for state-changing requests to prevent CSRF.
    Enforces that:
    1. If an Origin header is present, it must match an explicitly configured frontend origin in settings.cors_origins.
       Legitimate cross-site requests between localhost and 127.0.0.1 in local development are permitted ONLY if
       the Origin is explicitly trusted.
    2. If Origin is absent, any browser-initiated cross-site request (Sec-Fetch-Site: cross-site) is rejected.
    3. If Origin is absent but Sec-Fetch headers indicate a browser request, a valid Referer from a trusted origin is required.
    4. Programmatic/CLI requests with no browser indicators are permitted for local development/automation.
    """
    trusted_origins = {o.rstrip("/").lower() for o in settings.cors_origins if o}
    origin = request.headers.get("origin")
    sec_fetch_site = request.headers.get("sec-fetch-site")

    if origin is not None:
        normalized_origin = origin.strip().rstrip("/").lower()
        if not normalized_origin or normalized_origin not in trusted_origins:
            logger.warning(f"[CSRF] Blocked request from untrusted origin: {sanitize_log_message(origin)}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Untrusted origin. Request rejected."
            )
        # Origin header is present and explicitly matches configured frontend origins.
        # Even if Sec-Fetch-Site is 'cross-site' (common when frontend is on localhost:3000
        # and API is on 127.0.0.1:8000), the browser has validated the Origin header,
        # which cannot be forged by web pages. The request is trusted.
        return

    # If Origin header is absent:
    if sec_fetch_site == "cross-site":
        logger.warning("[CSRF] Blocked cross-site browser request missing Origin header.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-origin request rejected."
        )

    # Check if Sec-Fetch-* headers indicate a browser request
    has_sec_fetch = any(
        request.headers.get(h) for h in ("sec-fetch-mode", "sec-fetch-dest", "sec-fetch-site")
    )
    referer = request.headers.get("referer", "").strip()

    if has_sec_fetch:
        if referer:
            parsed_ref = urllib.parse.urlparse(referer)
            ref_origin = f"{parsed_ref.scheme}://{parsed_ref.netloc}".rstrip("/").lower()
            if ref_origin not in trusted_origins:
                logger.warning(f"[CSRF] Blocked browser request from untrusted referer: {sanitize_log_message(referer)}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Untrusted referer. Request rejected."
                )
        else:
            logger.warning("[CSRF] Blocked browser request missing Origin and Referer headers.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Browser request missing Origin/Referer header. Request rejected."
            )
    elif referer:
        # Non-Sec-Fetch browser client with Referer
        parsed_ref = urllib.parse.urlparse(referer)
        ref_origin = f"{parsed_ref.scheme}://{parsed_ref.netloc}".rstrip("/").lower()
        if ref_origin not in trusted_origins:
            logger.warning(f"[CSRF] Blocked request from untrusted referer: {sanitize_log_message(referer)}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Untrusted referer. Request rejected."
            )



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


# ── Gmail OAuth 2.0 Dedicated Endpoints (Phase 7.2) ─────────────────────────

@router.get(
    "/gmail/connect",
    summary="Initiate Gmail OAuth Flow",
    description="Generates a cryptographically secure CSRF state token and redirects to Google's OAuth consent screen.",
)
async def gmail_connect_endpoint(request: Request, redirect: bool = True):
    """GET /api/integrations/gmail/connect"""
    frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

    # 1. Verify Google OAuth configuration
    if not default_google_oauth_manager.is_configured():
        err_msg = "Google OAuth client credentials are not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        if redirect:
            encoded_err = urllib.parse.quote_plus(err_msg)
            return RedirectResponse(
                url=f"{frontend_origin}/?view=settings&integration=gmail&status=error&message={encoded_err}",
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )

    # SEC-02: Ensure request host aligns with redirect_uri host for loopback consistency
    # Browsers strictly isolate cookies between localhost and 127.0.0.1.
    # If the user accesses via one loopback alias while GOOGLE_REDIRECT_URI uses another,
    # redirect to the matching host before setting the session cookie.
    redirect_uri = default_google_oauth_manager.redirect_uri
    if redirect_uri:
        parsed_redirect = urllib.parse.urlparse(redirect_uri)
        redirect_hostname = parsed_redirect.hostname
        request_hostname = request.url.hostname

        loopback_hosts = {"127.0.0.1", "localhost"}
        if (
            redirect
            and request_hostname in loopback_hosts
            and redirect_hostname in loopback_hosts
            and request_hostname != redirect_hostname
        ):
            target_port = parsed_redirect.port or request.url.port or 8000
            target_scheme = parsed_redirect.scheme or request.url.scheme
            target_url = f"{target_scheme}://{redirect_hostname}:{target_port}/api/integrations/gmail/connect"
            if request.url.query:
                target_url = f"{target_url}?{request.url.query}"
            logger.info(
                f"[Gmail OAuth] Aligning connect request host from {request_hostname} to {redirect_hostname} "
                f"to match configured OAuth redirect URI domain."
            )
            return RedirectResponse(
                url=target_url,
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            )

    # 2. Verify encrypted credential key configuration
    credential_key = os.getenv("WORKFLOWOS_CREDENTIAL_KEY")
    if not credential_key:
        err_msg = "Credential encryption key is not configured. Set WORKFLOWOS_CREDENTIAL_KEY in environment."
        if redirect:
            encoded_err = urllib.parse.quote_plus(err_msg)
            return RedirectResponse(
                url=f"{frontend_origin}/?view=settings&integration=gmail&status=error&message={encoded_err}",
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=err_msg,
        )

    # 3. Create short-lived, single-use state token
    state = default_oauth_state_store.create_state()
    auth_url = default_google_oauth_manager.build_authorization_url(state=state)

    is_secure = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto", "").lower() == "https"
    )

    if not redirect:
        resp = JSONResponse({"auth_url": auth_url, "state": state})
        resp.set_cookie(
            key="workflowos_oauth_state",
            value=state,
            max_age=600,
            httponly=True,
            samesite="lax",
            secure=is_secure,
            path="/api/integrations/gmail",
        )
        return resp

    resp = RedirectResponse(url=auth_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    # SEC-02: Bind state token to browser session via HttpOnly, SameSite=Lax cookie
    resp.set_cookie(
        key="workflowos_oauth_state",
        value=state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        path="/api/integrations/gmail",
    )
    return resp


@router.get(
    "/gmail/callback",
    summary="Google OAuth Callback",
    description="Validates CSRF state, exchanges authorization code for tokens, and securely persists encrypted credentials.",
)
async def gmail_callback_endpoint(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """GET /api/integrations/gmail/callback"""
    frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

    def _clear_cookie(response: Response) -> Response:
        response.delete_cookie(key="workflowos_oauth_state", path="/api/integrations/gmail")
        response.delete_cookie(key="workflowos_oauth_state", path="/")
        return response

    # 1. Handle user cancellation or Google error
    if error:
        safe_err_log = sanitize_log_message(str(error))
        safe_err_query = urllib.parse.quote_plus(safe_err_log)
        logger.warning(f"[Gmail OAuth] User cancelled or Google returned error: {safe_err_log}")
        return _clear_cookie(RedirectResponse(
            url=f"{frontend_origin}/?view=settings&integration=gmail&status=error&message={safe_err_query}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        ))

    # 2. SEC-02: Validate browser cookie session binding against returned state
    cookie_state = request.cookies.get("workflowos_oauth_state")
    if not cookie_state or not state or not hmac.compare_digest(cookie_state, state):
        # If state token exists in store, consume it to prevent any replay
        if state:
            default_oauth_state_store.validate_and_consume(state)
        if not cookie_state:
            logger.warning(
                f"[Gmail OAuth] Missing OAuth session cookie on host '{request.url.hostname}'. "
                f"State parameter present: {bool(state)}."
            )
        else:
            logger.warning("[Gmail OAuth] Mismatched OAuth session cookie value.")
        encoded_err = urllib.parse.quote_plus(
            "Invalid or missing OAuth session binding. Please retry authorization from Settings."
        )
        return _clear_cookie(RedirectResponse(
            url=f"{frontend_origin}/?view=settings&integration=gmail&status=error&message={encoded_err}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        ))

    # 3. Validate and consume state token exactly once from OAuthStateStore
    if not default_oauth_state_store.validate_and_consume(state):
        logger.warning("[Gmail OAuth] Invalid, missing, or expired OAuth state token.")
        encoded_err = urllib.parse.quote_plus("Invalid or expired OAuth state token. Please retry authorization.")
        return _clear_cookie(RedirectResponse(
            url=f"{frontend_origin}/?view=settings&integration=gmail&status=error&message={encoded_err}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        ))

    # 4. Validate authorization code
    if not code:
        logger.warning("[Gmail OAuth] Missing authorization code in callback.")
        encoded_err = urllib.parse.quote_plus("Missing OAuth authorization code from Google callback.")
        return _clear_cookie(RedirectResponse(
            url=f"{frontend_origin}/?view=settings&integration=gmail&status=error&message={encoded_err}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        ))

    # 5. Exchange code for tokens server-side
    try:
        tokens = await default_google_oauth_manager.exchange_code_for_tokens(code)
    except Exception as e:
        safe_msg = sanitize_log_message(str(e))
        logger.error(f"[Gmail OAuth] Token exchange error: {safe_msg}")
        encoded_err = urllib.parse.quote_plus(f"OAuth token exchange failed: {safe_msg}")
        return _clear_cookie(RedirectResponse(
            url=f"{frontend_origin}/?view=settings&integration=gmail&status=error&message={encoded_err}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        ))

    # 6. Connect adapter and persist encrypted tokens (SEC-05: marked as internal OAuth source)
    adapter = integration_registry.get("gmail")
    if not adapter:
        encoded_err = urllib.parse.quote_plus("Gmail adapter is not registered in system.")
        return _clear_cookie(RedirectResponse(
            url=f"{frontend_origin}/?view=settings&integration=gmail&status=error&message={encoded_err}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        ))

    tokens["_internal_oauth_source"] = True
    success = await adapter.connect(credentials=tokens)
    if not success:
        err_msg = adapter.last_error or "Failed to establish Gmail connection."
        encoded_err = urllib.parse.quote_plus(err_msg)
        return _clear_cookie(RedirectResponse(
            url=f"{frontend_origin}/?view=settings&integration=gmail&status=error&message={encoded_err}",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        ))

    logger.info("[Gmail OAuth] Gmail connection successfully established via OAuth 2.0.")
    return _clear_cookie(RedirectResponse(
        url=f"{frontend_origin}/?view=settings&integration=gmail&status=connected",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    ))


@router.get(
    "/gmail/status",
    response_model=IntegrationSummary,
    summary="Get Gmail Integration Status",
    description="Returns current connection status and declared capabilities for Gmail adapter.",
)
async def gmail_status_endpoint():
    """GET /api/integrations/gmail/status"""
    adapter = integration_registry.get("gmail")
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gmail adapter not found.",
        )
    return adapter.to_summary()


@router.post(
    "/gmail/disconnect",
    response_model=IntegrationSummary,
    summary="Disconnect Gmail Integration",
    description="Revokes OAuth tokens with Google and purges local encrypted credential storage.",
)
async def gmail_disconnect_endpoint(request: Request):
    """POST /api/integrations/gmail/disconnect"""
    # SEC-04: Validate Origin against trusted frontend origins to prevent cross-origin CSRF
    _validate_origin_for_csrf(request)

    adapter = integration_registry.get("gmail")
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gmail adapter not found.",
        )
    await adapter.disconnect()
    return adapter.to_summary()



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
    # SEC-05: Disallow direct manual credential submission for real OAuth adapters
    if integration_id == "gmail":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail integration requires OAuth 2.0 authorization. Manual credential submission via this endpoint is not permitted.",
        )

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

    if not adapter.is_connected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integration '{integration_id}' is disconnected. Connect it before executing actions.",
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
