# WorkFlowOS Phase 5 — Desktop Activity Agent

A privacy-first macOS desktop activity agent that captures application-switching events and streams them to the WorkFlowOS backend as normalized workflow events.

---

## Overview

The Desktop Activity Agent runs as a lightweight background process on macOS. It:

- Observes which application is frontmost using `NSWorkspace` (PyObjC)
- Emits `activate_application` and `switch_application` events when focus changes
- Normalizes events to the WorkFlowOS `EventCreate` schema (Phases 1–2 compatible)
- Streams events to `POST /api/events` with retry, deduplication, and offline buffering
- Enforces a strict privacy policy: no keystrokes, no clipboard, no screenshots

---

## Quick Start

### 1. Install dependencies

```bash
cd workflowOS
python3 -m pip install -r requirements.txt
```

> **Note:** Requires `pyobjc-core` and `pyobjc-framework-Cocoa` (macOS only).

### 2. Configure (optional)

Create or edit `.env` in the project root:

```env
# Backend URL (default: http://localhost:8000)
AGENT_API_URL=http://localhost:8000

# Comma-separated app slugs to capture only (leave empty to capture all)
AGENT_ALLOWLIST=google_chrome,slack,vscode

# Include window titles in events (default: false for privacy)
AGENT_INCLUDE_WINDOW_TITLE=false

# Poll interval in seconds (default: 1.0)
AGENT_POLL_INTERVAL=1.0
```

### 3. Run the agent

```bash
# Foreground mode (Ctrl+C to stop)
python3 -m agent run

# Check status of a running background agent
python3 -m agent status

# Start as background daemon
python3 -m agent start --daemon

# Stop the daemon
python3 -m agent stop
```

---

## Architecture

```
agent/
├── __init__.py          # Package exports
├── __main__.py          # Entry point (python3 -m agent)
├── cli.py               # CLI commands: run, start, stop, status
├── service.py           # DesktopActivityAgent orchestrator + AgentState
├── collector.py         # MacOSActivityCollector (NSWorkspace / fallback)
├── normalizer.py        # EventNormalizer → EventCreate schema
├── client.py            # BackendEventClient (HTTP, retry, buffer, dedup)
└── config.py            # AgentConfig (dataclass + privacy rules)
```

### Data Flow

```
NSWorkspace.frontmostApplication()
      │
      ▼
MacOSActivityCollector.poll()
  - Returns: {event_type, app_name, bundle_id, previous_app, ...}
  - None if no state change
      │
      ▼
EventNormalizer.normalize()
  - Applies denylist/allowlist
  - Slugifies app name: "Google Chrome" → "google_chrome"
  - Enforces privacy rules (window title opt-in only)
  - Returns: EventCreate (or None if filtered)
      │
      ▼
BackendEventClient.send_event()
  - Deduplicates identical events
  - Retries on 5xx (up to max_retries)
  - Buffers offline events in memory
  - POST /api/events → WorkFlowOS backend
```

---

## Privacy Policy

| Category                  | Behavior                                      |
|---------------------------|-----------------------------------------------|
| Application name          | ✅ Captured as a slug                         |
| Bundle ID                 | ✅ Stored in metadata                         |
| Window title              | ⛔ Off by default; opt-in via `AGENT_INCLUDE_WINDOW_TITLE=true` |
| Keystrokes / typed text   | ⛔ Never captured                             |
| Clipboard contents        | ⛔ Never captured                             |
| Screenshots               | ⛔ Never captured                             |
| Network traffic           | ⛔ Never captured                             |
| Passwords / credentials   | ⛔ Blocked by permanent denylist              |

### Built-in Denylist (never observed)

The following applications are **permanently excluded** regardless of user configuration:

- 1Password, 1Password 7, 1Password 8
- Bitwarden, LastPass, KeePass, KeePassXC
- Keychain Access
- macOS SecurityAgent, loginwindow, screensaver

---

## Configuration Reference

| Environment Variable         | Default                    | Description                                       |
|------------------------------|----------------------------|---------------------------------------------------|
| `AGENT_API_URL`              | `http://localhost:8000`    | WorkFlowOS backend URL                            |
| `AGENT_SESSION_ID`           | Auto-generated             | Session identifier for grouping events            |
| `AGENT_ALLOWLIST`            | _(empty = all apps)_       | Comma-separated app slugs or bundle IDs to allow  |
| `AGENT_INCLUDE_WINDOW_TITLE` | `false`                    | Opt-in to capture window titles                   |
| `AGENT_POLL_INTERVAL`        | `1.0`                      | Observation frequency in seconds                  |
| `AGENT_REQUEST_TIMEOUT`      | `5.0`                      | HTTP request timeout in seconds                   |
| `AGENT_MAX_RETRIES`          | `3`                        | Max delivery retries per event on 5xx             |
| `AGENT_RETRY_BACKOFF`        | `1.0`                      | Delay (seconds) between retry attempts            |
| `AGENT_MAX_BUFFER_SIZE`      | `1000`                     | Max events buffered offline when backend is down  |

---

## macOS Permissions

The agent uses `NSWorkspace.sharedWorkspace().frontmostApplication()`, which requires **no special permissions** for basic app-name and bundle ID capture.

**Accessibility API (optional):** If `AGENT_INCLUDE_WINDOW_TITLE=true`, the agent will need Accessibility access:

1. Open **System Settings → Privacy & Security → Accessibility**
2. Add and enable the Terminal (or your Python launcher)

The agent checks accessibility status at startup and reports it in `python3 -m agent status`.

---

## Event Schema

Events sent to the backend follow the Phase 1 `EventCreate` schema:

```json
{
  "session_id": "desktop_session_20261003_120000_abc123",
  "timestamp": "2026-10-03T12:00:00.123456Z",
  "application": "google_chrome",
  "event_type": "switch_application",
  "target": "com.google.Chrome",
  "metadata": {
    "app_name": "Google Chrome",
    "bundle_id": "com.google.Chrome",
    "source": "macos_desktop_agent",
    "agent_version": "1.0.0",
    "previous_application": "slack",
    "previous_app_name": "Slack",
    "previous_bundle_id": "com.tinyspeck.slackmacgap"
  }
}
```

### Event Types

| Event Type             | When emitted                                             |
|------------------------|----------------------------------------------------------|
| `activate_application` | First app observed at agent startup, or after reset      |
| `switch_application`   | User switches from one app to another                    |

---

## Running Tests

```bash
# Phase 5 unit tests (all macOS APIs mocked — no live desktop required)
python3 backend/test_phase5.py

# Phase 1–4.6 regression tests
python3 backend/test_phase3.py
python3 backend/test_phase4_2.py
python3 backend/test_phase4_5.py
python3 backend/test_phase4_6.py
```

Expected Phase 5 output:
```
Ran 45 tests in ~0.5s
PASS
```

---

## Status Output Example

```
$ python3 -m agent status

WorkFlowOS Desktop Activity Agent — Status
══════════════════════════════════════════
  State             : running
  Session ID        : desktop_session_20261003_120000_abc123
  Uptime            : 183.4s
  Backend           : http://localhost:8000 (connected)
  Accessibility     : granted
  Events captured   : 47
  Events sent       : 47
  Events dropped    : 0
  Events buffered   : 0
  Allowlist         : [all apps]
  Window titles     : off
  Current app       : Google Chrome
══════════════════════════════════════════
```

---

## Integration with WorkFlowOS

Phase 5 events flow into the existing WorkFlowOS pipeline:

```
Agent → POST /api/events → Phase 1 ingestion
                         → Phase 2 discovery (repetition detection)
                         → Phase 3 workflow extraction
                         → Phase 4.x automation suggestions
```

No backend changes are required — the agent is a standalone sidecar.
