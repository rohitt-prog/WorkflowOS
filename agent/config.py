"""
WorkFlowOS Phase 5 — Desktop Activity Agent Configuration

Defines configuration settings for local macOS desktop activity observation:
- Backend connection settings
- Session identification
- Polling intervals
- Privacy allowlist and denylist
- Retry and buffering behavior
"""

import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Set
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


def _slugify(name: str) -> str:
    """Lightweight slugifier for allowlist/denylist matching (mirrors normalizer logic)."""
    if not name:
        return "unknown_application"
    cleaned = re.sub(r"\.app$", "", name, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", cleaned)
    slug = cleaned.strip("_").lower()
    return slug or "unknown_application"

# Built-in privacy denylist: sensitive system or security applications
# that must NEVER be observed regardless of user allowlist configuration.
DEFAULT_DENYLIST: Set[str] = {
    "1password",
    "1password 7",
    "1password 8",
    "bitwarden",
    "lastpass",
    "keepass",
    "keepassxc",
    "keychain access",
    "keychain",
    "securityagent",
    "loginwindow",
    "screensaver",
    "coreauthd",
    "authd",
    "com.agilebits.onepassword",
    "com.bitwarden.desktop",
    "com.apple.keychainaccess",
    "com.apple.SecurityAgent",
}


def generate_session_id() -> str:
    """Generate a clean, timestamped session identifier for agent runs."""
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    rand_suffix = uuid.uuid4().hex[:6]
    return f"desktop_session_{now_str}_{rand_suffix}"


@dataclass
class AgentConfig:
    """Configuration parameters for the Desktop Activity Agent."""

    # Backend API URL
    api_base_url: str = field(
        default_factory=lambda: os.getenv(
            "AGENT_API_URL",
            os.getenv("API_URL", "http://localhost:8000")
        ).rstrip("/")
    )

    # Session identifier
    session_id: str = field(
        default_factory=lambda: os.getenv("AGENT_SESSION_ID") or generate_session_id()
    )

    # Polling frequency in seconds (default 1.0s)
    poll_interval_seconds: float = field(
        default_factory=lambda: float(os.getenv("AGENT_POLL_INTERVAL", "1.0"))
    )

    # Application allowlist: if specified, ONLY apps matching these names or bundle IDs are captured.
    # Empty list or None captures all non-denylisted applications.
    allowlist: Optional[List[str]] = field(
        default_factory=lambda: [
            app.strip().lower()
            for app in os.getenv("AGENT_ALLOWLIST", "").split(",")
            if app.strip()
        ] or None
    )

    # Application denylist: applications permanently excluded from capture
    denylist: Set[str] = field(default_factory=lambda: set(DEFAULT_DENYLIST))

    # Window title capture: strictly opt-in (default False for privacy)
    include_window_title: bool = field(
        default_factory=lambda: os.getenv("AGENT_INCLUDE_WINDOW_TITLE", "false").lower() in ("true", "1", "yes")
    )

    # Phase 12 Privacy: User control over activity collection (default True)
    collection_enabled: bool = field(
        default_factory=lambda: os.getenv("ACTIVITY_COLLECTION_ENABLED", "true").lower() in ("true", "1", "yes")
    )

    # Backend request configuration
    request_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("AGENT_REQUEST_TIMEOUT", "5.0"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("AGENT_MAX_RETRIES", "3"))
    )
    retry_backoff_seconds: float = field(
        default_factory=lambda: float(os.getenv("AGENT_RETRY_BACKOFF", "1.0"))
    )

    # In-memory event buffer cap when backend is temporarily unreachable
    max_buffer_size: int = field(
        default_factory=lambda: int(os.getenv("AGENT_MAX_BUFFER_SIZE", "1000"))
    )

    def is_app_allowed(self, app_name: str, bundle_id: Optional[str] = None) -> bool:
        """
        Check whether an application is permitted for capture under current
        privacy rules and allowlist/denylist configuration.

        Allowlist entries may be:
          - A raw lowercase app name      (e.g. "google chrome")
          - A slugified app name          (e.g. "google_chrome")
          - A bundle ID                   (e.g. "com.google.Chrome")
        """
        app_name_lower = (app_name or "").strip().lower()
        bundle_id_lower = (bundle_id or "").strip().lower()
        app_slug = _slugify(app_name)

        # Step 1: Strict denylist check (highest priority — slug + raw + bundle)
        if app_name_lower in self.denylist or bundle_id_lower in self.denylist:
            return False
        if app_slug in self.denylist:
            return False

        # Step 2: Allowlist check (if configured)
        if self.allowlist:
            allowed = [a.lower() for a in self.allowlist]
            return (
                app_name_lower in allowed
                or app_slug in allowed
                or bundle_id_lower in allowed
            )

        # Step 3: Default allow if not denylisted
        return True
