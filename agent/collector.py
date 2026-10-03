"""
WorkFlowOS Phase 5 — macOS Activity Collector

Observes desktop application activation, application switches, and window focus changes
using native macOS APIs (PyObjC / AppKit).

Privacy guarantees:
- No keystroke capture
- No clipboard reading
- No screen recording or pixel scraping
- Explicit, graceful accessibility permission checks

IMPORTANT — Thread-safety note
--------------------------------
NSWorkspace.sharedWorkspace().frontmostApplication() relies on an internal
Notification-Center cache that is only refreshed when the Cocoa NSRunLoop
processes NSWorkspaceDidActivateApplicationNotification.  When called from a
background thread that has *no* running NSRunLoop, the method returns the same
app it saw at first access — i.e. it is permanently stale.

Fix: Use Carbon.GetFrontProcess() to obtain the frontmost PID directly from
WindowServer (a true IPC call, RunLoop-independent), then look up the app
metadata via NSRunningApplication.runningApplicationWithProcessIdentifier_().
Both operations are documented as safe from any thread.
"""

import ctypes
import logging
import sys
from ctypes import util
from typing import Any, Dict, Optional

from agent.config import AgentConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Carbon – low-level frontmost-PID helper (thread-safe, no RunLoop needed)
# ---------------------------------------------------------------------------

class _ProcessSerialNumber(ctypes.Structure):
    _fields_ = [("highLongOfPSN", ctypes.c_uint32),
                ("lowLongOfPSN", ctypes.c_uint32)]


def _load_carbon():
    """Load Carbon framework via ctypes.  Returns None if unavailable."""
    path = util.find_library("Carbon")
    if not path:
        return None
    try:
        lib = ctypes.cdll.LoadLibrary(path)
        lib.GetFrontProcess.argtypes = [ctypes.POINTER(_ProcessSerialNumber)]
        lib.GetFrontProcess.restype  = ctypes.c_int32
        lib.GetProcessPID.argtypes  = [ctypes.POINTER(_ProcessSerialNumber),
                                        ctypes.POINTER(ctypes.c_int32)]
        lib.GetProcessPID.restype   = ctypes.c_int32
        return lib
    except Exception as exc:
        logger.debug(f"Could not load Carbon framework: {exc}")
        return None


_CARBON = _load_carbon()


def _get_frontmost_pid() -> Optional[int]:
    """
    Returns the PID of the frontmost (key) application by asking WindowServer
    directly via Carbon.GetFrontProcess/GetProcessPID.  This is thread-safe
    and does not require a running NSRunLoop.
    """
    if _CARBON is None:
        return None
    try:
        psn = _ProcessSerialNumber()
        if _CARBON.GetFrontProcess(ctypes.byref(psn)) != 0:
            return None
        pid = ctypes.c_int32(0)
        if _CARBON.GetProcessPID(ctypes.byref(psn), ctypes.byref(pid)) != 0:
            return None
        return int(pid.value)
    except Exception as exc:
        logger.debug(f"Carbon GetFrontProcess error: {exc}")
        return None


# ---------------------------------------------------------------------------
# AppKit – NSRunningApplication for app metadata (thread-safe per Apple docs)
# ---------------------------------------------------------------------------

try:
    from AppKit import NSRunningApplication, NSWorkspace
    HAS_APPKIT = True
except ImportError:
    NSRunningApplication = None  # type: ignore
    NSWorkspace = None           # type: ignore
    HAS_APPKIT = False
    logger.warning(
        "AppKit (PyObjC) not available. Desktop activity capture will use fallback mode."
    )


def check_accessibility_trusted() -> bool:
    """
    Checks if the current process has been granted macOS Accessibility permissions
    via ApplicationServices.AXIsProcessTrusted().
    
    Does NOT trigger an OS prompt. Returns True if granted, False otherwise.
    """
    try:
        app_services_path = util.find_library("ApplicationServices")
        if not app_services_path:
            return False
        app_services = ctypes.cdll.LoadLibrary(app_services_path)
        app_services.AXIsProcessTrusted.argtypes = []
        app_services.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(app_services.AXIsProcessTrusted())
    except Exception as e:
        logger.debug(f"Failed to check accessibility permission via ctypes: {e}")
        return False


class MacOSActivityCollector:
    """
    Native macOS desktop activity observer.
    Monitors active application focus and window transitions.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.has_appkit = HAS_APPKIT
        self._last_app_name: Optional[str] = None
        self._last_bundle_id: Optional[str] = None
        self._last_pid: Optional[int] = None
        self._accessibility_granted: bool = check_accessibility_trusted()

    @property
    def accessibility_granted(self) -> bool:
        """Returns cached or refreshed accessibility permission status."""
        self._accessibility_granted = check_accessibility_trusted()
        return self._accessibility_granted

    def get_frontmost_app(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves the currently active (frontmost) desktop application.

        Implementation note
        -------------------
        We use Carbon.GetFrontProcess() → NSRunningApplication lookup rather
        than NSWorkspace.sharedWorkspace().frontmostApplication() because the
        latter relies on an NSRunLoop-driven notification cache that is never
        updated when called from a background thread (the worker thread used
        by DesktopActivityAgent._worker_loop).  GetFrontProcess() makes a
        direct IPC call to WindowServer and is always current.

        Returns:
            Dict containing name, bundle_id, pid, and activation_policy,
            or None if no application is active.
        """
        if self.has_appkit:
            # Step 1: ask WindowServer for the frontmost PID (thread-safe)
            pid = _get_frontmost_pid()
            if pid is not None and NSRunningApplication is not None:
                try:
                    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
                    if app is not None:
                        name = str(app.localizedName() or "")
                        bundle_id = str(app.bundleIdentifier() or "")
                        # Policy 0 = regular GUI app; 2 = background-only
                        policy = int(app.activationPolicy()) if hasattr(app, "activationPolicy") else 0
                        return {
                            "name": name,
                            "bundle_id": bundle_id,
                            "pid": pid,
                            "activation_policy": policy,
                        }
                except Exception as exc:
                    logger.debug(f"NSRunningApplication lookup failed for pid={pid}: {exc}")

            # Carbon unavailable or lookup failed — fall through to NSWorkspace
            # as a best-effort (will be stale in threads without RunLoop, but
            # better than returning None entirely).
            if NSWorkspace is not None:
                try:
                    ws = NSWorkspace.sharedWorkspace()
                    app = ws.frontmostApplication()
                    if app is not None:
                        name = str(app.localizedName() or "")
                        bundle_id = str(app.bundleIdentifier() or "")
                        pid_raw = int(app.processIdentifier())
                        policy = int(app.activationPolicy()) if hasattr(app, "activationPolicy") else 0
                        return {
                            "name": name,
                            "bundle_id": bundle_id,
                            "pid": pid_raw,
                            "activation_policy": policy,
                        }
                except Exception as exc:
                    logger.debug(f"NSWorkspace fallback also failed: {exc}")

        # Final fallback: osascript (no AppKit at all)
        return self._get_frontmost_app_fallback()

    def _get_frontmost_app_fallback(self) -> Optional[Dict[str, Any]]:
        """Secondary fallback using osascript if PyObjC is not installed."""
        import subprocess
        try:
            cmd = [
                "osascript", "-e",
                'tell application "System Events" to get {name, bundle identifier} of first application process whose frontmost is true'
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5)
            if proc.returncode == 0:
                parts = [p.strip() for p in proc.stdout.strip().split(",")]
                name = parts[0] if len(parts) > 0 else "unknown"
                bundle_id = parts[1] if len(parts) > 1 else ""
                return {
                    "name": name,
                    "bundle_id": bundle_id,
                    "pid": None,
                    "activation_policy": 0,
                }
        except Exception:
            pass
        return None

    def poll(self) -> Optional[Dict[str, Any]]:
        """
        Checks the current desktop state against the previous observation.

        If a new application became active or an application switch occurred,
        returns an activity event dictionary.  If no state change occurred,
        returns None.

        Change detection uses PID as the primary discriminator (reliable even
        when two apps share the same bundle ID), with app name and bundle ID
        as secondary checks for cases where PID is unavailable (fallback mode).
        """
        current = self.get_frontmost_app()
        if not current or not current.get("name"):
            return None

        # Defensive str() cast: ensure Python str, never an ObjC proxy that
        # could compare inequal across GC cycles even for the same value.
        name = sys.intern(str(current["name"]))
        bundle_id = sys.intern(str(current.get("bundle_id") or ""))
        pid = current.get("pid")  # int or None in fallback mode

        # Ignore background-only daemons (activation_policy == 2)
        if current.get("activation_policy") == 2:
            return None

        # --- Change detection ---
        # Primary:   PID changed (or first observation)
        # Secondary: name/bundle changed (covers fallback where PID is None)
        is_first = self._last_pid is None and self._last_app_name is None

        if pid is not None and self._last_pid is not None:
            # Both polls have valid PIDs — use PID as the source of truth
            is_changed = (pid != self._last_pid)
        else:
            # Fallback: compare by name + bundle when PIDs are unavailable
            is_changed = (
                name != self._last_app_name
                or bundle_id != self._last_bundle_id
            )

        if not is_first and not is_changed:
            return None

        previous_app    = self._last_app_name
        previous_bundle = self._last_bundle_id

        # Persist state for next poll
        self._last_app_name  = name
        self._last_bundle_id = bundle_id
        self._last_pid       = pid

        event_type = "activate_application" if is_first else "switch_application"

        activity = {
            "app_name": name,
            "bundle_id": bundle_id,
            "process_id": pid,
            "event_type": event_type,
            "previous_app": previous_app,
            "previous_bundle_id": previous_bundle,
            "target": bundle_id or name,
            "window_title": None,  # Private by default
        }

        logger.info(f"Desktop activity: {event_type} -> '{name}' ({bundle_id}) pid={pid}")
        return activity

    def reset(self):
        """Reset internal state tracking (clears all stored app identity)."""
        self._last_app_name  = None
        self._last_bundle_id = None
        self._last_pid       = None
