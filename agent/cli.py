"""
WorkFlowOS Phase 5 — Desktop Activity Agent CLI

Command-line interface for controlling and inspecting the Desktop Activity Agent:
- run: Foreground interactive monitoring with live event stream (Ctrl+C to exit)
- start: Start background monitoring session (PID managed)
- stop: Stop running background agent session
- status: Inspect agent status, metrics, and backend connectivity
- test-connection: Verify connectivity to WorkFlowOS backend
- check-permissions: Inspect macOS Accessibility permissions
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from agent.config import AgentConfig, generate_session_id
from agent.service import DesktopActivityAgent
from agent.collector import check_accessibility_trusted
from backend.models.event import EventCreate

logger = logging.getLogger("workflowos.agent")

# Path to PID file for background mode
PID_FILE = Path(__file__).resolve().parent.parent / ".agent.pid"


def get_agent_pid() -> Optional[int]:
    """Reads PID from PID_FILE if it exists and process is currently alive."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process is running
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        # Stale PID file
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def cmd_run(args):
    """Interactive foreground execution with real-time logging."""
    config = AgentConfig(
        api_base_url=args.api_url,
        session_id=args.session or generate_session_id(),
        poll_interval_seconds=args.interval,
        allowlist=[a.strip().lower() for a in args.allow.split(",") if a.strip()] if args.allow else None,
        include_window_title=args.include_title,
    )

    agent = DesktopActivityAgent(config=config)

    # Pretty banner
    backend_ok = agent.client.check_health()
    ax_ok = agent.collector.accessibility_granted

    print("=" * 66)
    print("  WorkFlowOS Phase 5 — Real Desktop Activity Agent")
    print("=" * 66)
    print(f"  Session ID        : {config.session_id}")
    print(f"  Backend URL       : {config.api_base_url} ({'CONNECTED' if backend_ok else 'UNREACHABLE'})")
    print(f"  Poll Interval     : {config.poll_interval_seconds}s")
    print(f"  Application Filter: {', '.join(config.allowlist) if config.allowlist else 'ALL (non-denylisted apps)'}")
    print(f"  Window Titles     : {'ENABLED (Opt-in)' if config.include_window_title else 'DISABLED (Privacy Default)'}")
    print(f"  Accessibility     : {'GRANTED' if ax_ok else 'NOT GRANTED (Standard app tracking active)'}")
    print("  Privacy Policy    :")
    print("    - Keystrokes & Clipboard  : STRICTLY NEVER CAPTURED")
    print("    - Screenshots / Recordings: STRICTLY NEVER CAPTURED")
    print("    - Sensitive Credentials   : DENYLISTED (1Password, Keychain, etc.)")
    print("=" * 66)
    print("  Monitoring active desktop... Press Ctrl+C to stop.")
    print("=" * 66)

    def on_event(event: EventCreate):
        ts = event.timestamp.split("T")[-1].rstrip("Z")
        print(f"  [{ts}] [EVENT] {event.event_type:<18} -> {event.application:<20} target={event.target}")

    agent.on_event_callback = on_event

    def sigint_handler(signum, frame):
        print("\n\nStopping agent gracefully...")
        agent.stop()
        stat = agent.status()
        print("=" * 66)
        print("  Session Summary:")
        print(f"    Total Events Captured: {stat['events_captured']}")
        print(f"    Total Events Sent    : {stat['events_sent']}")
        print(f"    Events Filtered/Drop : {stat['events_dropped']}")
        print(f"    Duration             : {stat['uptime_seconds']}s")
        print("=" * 66)
        sys.exit(0)

    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGTERM, sigint_handler)

    agent.start()

    # Keep main thread alive
    while agent.is_running:
        time.sleep(0.5)


def cmd_start(args):
    """Starts the agent in daemon/background mode."""
    existing_pid = get_agent_pid()
    if existing_pid:
        print(f"Desktop Activity Agent is already running with PID {existing_pid}.")
        return

    import subprocess
    cmd = [
        sys.executable,
        "-m", "agent", "run",
        "--api-url", args.api_url,
        "--interval", str(args.interval),
    ]
    if args.session:
        cmd.extend(["--session", args.session])
    if args.allow:
        cmd.extend(["--allow", args.allow])
    if args.include_title:
        cmd.append("--include-title")

    # Spawn detached process
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    PID_FILE.write_text(str(proc.pid))
    print(f"Started Desktop Activity Agent in background (PID {proc.pid}).")
    print("Use 'python -m agent status' to inspect or 'python -m agent stop' to halt.")


def cmd_stop(args):
    """Stops the running background agent session."""
    pid = get_agent_pid()
    if not pid:
        print("No running Desktop Activity Agent found.")
        PID_FILE.unlink(missing_ok=True)
        return

    print(f"Stopping Desktop Activity Agent (PID {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            time.sleep(0.2)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
        else:
            os.kill(pid, signal.SIGKILL)
        print("Desktop Activity Agent stopped.")
    except Exception as e:
        print(f"Error stopping process {pid}: {e}")
    finally:
        PID_FILE.unlink(missing_ok=True)


def cmd_status(args):
    """Displays current agent status and connectivity."""
    pid = get_agent_pid()
    config = AgentConfig(api_base_url=args.api_url)
    agent = DesktopActivityAgent(config=config)
    stat = agent.status()
    backend_ok = agent.client.check_health()
    ax_ok = check_accessibility_trusted()

    if args.json:
        result = {
            "is_running": pid is not None,
            "pid": pid,
            "backend_url": config.api_base_url,
            "backend_connected": backend_ok,
            "accessibility_granted": ax_ok,
            "current_frontmost_app": stat.get("current_frontmost_app"),
        }
        print(json.dumps(result, indent=2))
        return

    print("=" * 60)
    print("  WorkFlowOS Desktop Activity Agent Status")
    print("=" * 60)
    print(f"  Agent Process       : {'RUNNING (PID ' + str(pid) + ')' if pid else 'STOPPED / NOT RUNNING'}")
    print(f"  Backend URL         : {config.api_base_url}")
    print(f"  Backend Reachable   : {'YES (HTTP 200 OK)' if backend_ok else 'NO (Check uvicorn backend)'}")
    print(f"  Accessibility Perms : {'GRANTED' if ax_ok else 'NOT GRANTED (Standard app tracking only)'}")
    print(f"  Active Frontmost App: {stat.get('current_frontmost_app') or 'N/A'}")
    print("=" * 60)


def cmd_test_connection(args):
    """Tests connectivity to WorkFlowOS backend."""
    config = AgentConfig(api_base_url=args.api_url)
    agent = DesktopActivityAgent(config=config)
    print(f"Testing connection to WorkFlowOS backend at: {config.api_base_url}")

    health_ok = agent.client.check_health()
    if health_ok:
        print("  ✓ GET /health succeeded (200 OK)")
    else:
        print("  ✗ GET /health failed. Ensure backend is running:")
        print("    uvicorn backend.main:app --reload --port 8000")
        sys.exit(1)

    print("Backend connection verified successfully.")


def cmd_check_permissions(args):
    """Inspects macOS permissions and provides guidance."""
    print("=" * 60)
    print("  WorkFlowOS — macOS Desktop Agent Permission Inspector")
    print("=" * 60)
    ax = check_accessibility_trusted()
    print(f"  Accessibility Permission (AXIsProcessTrusted): {'GRANTED' if ax else 'NOT GRANTED'}")
    print("")
    print("  Notes on macOS Permissions:")
    print("  - Application Activation & Switches: Supported natively without special permissions.")
    print("  - Window Focus Inspection: Enhanced when Accessibility is granted.")
    print("")
    if not ax:
        print("  To grant Accessibility permission (optional):")
        print("    1. Open System Settings -> Privacy & Security -> Accessibility")
        print("    2. Enable permission for your Terminal or Python interpreter.")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        prog="python -m agent",
        description="WorkFlowOS Phase 5 — Real Desktop Activity Agent CLI"
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("AGENT_API_URL", os.getenv("API_URL", "http://localhost:8000")),
        help="Backend API base URL (default: http://localhost:8000)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Agent commands")

    # Command: run (foreground)
    p_run = subparsers.add_parser("run", help="Run agent interactively in foreground with live stream")
    p_run.add_argument("--session", help="Session ID (default: auto-generated timestamped session)")
    p_run.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds (default: 1.0)")
    p_run.add_argument("--allow", help="Comma-separated application allowlist (e.g. 'google_chrome,slack,demo_email')")
    p_run.add_argument("--include-title", action="store_true", help="Opt-in to capturing window titles (default: False)")

    # Command: start (daemon)
    p_start = subparsers.add_parser("start", help="Start agent in background daemon mode")
    p_start.add_argument("--session", help="Session ID")
    p_start.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds")
    p_start.add_argument("--allow", help="Comma-separated application allowlist")
    p_start.add_argument("--include-title", action="store_true", help="Opt-in to window titles")

    # Command: stop
    subparsers.add_parser("stop", help="Stop background agent session")

    # Command: status
    p_status = subparsers.add_parser("status", help="Inspect agent status and connectivity")
    p_status.add_argument("--json", action="store_true", help="Output status as JSON")

    # Command: test-connection
    subparsers.add_parser("test-connection", help="Test backend connectivity")

    # Command: check-permissions
    subparsers.add_parser("check-permissions", help="Inspect macOS permissions")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "run": cmd_run,
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "test-connection": cmd_test_connection,
        "check-permissions": cmd_check_permissions,
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
