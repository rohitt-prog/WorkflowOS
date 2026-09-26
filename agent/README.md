# WorkFlowOS - Agent Module (Phase 2+)

## Overview
The **Agent** module will be responsible for local task observation, monitoring user actions across applications, desktop windows, browser tabs, and terminal environments.

## Future Pipeline Stage: `OBSERVE`
- **Telemetry Ingestion**: Capturing fine-grained OS and application telemetry events (keystrokes, navigation, active application focus, clipboard, file system modifications).
- **Lightweight Event Streamer**: Packaging native event stream data and delivering it to the WorkFlowOS backend `/api/events` endpoint.
- **Privacy & Redaction**: Sanitizing sensitive user data (passwords, credentials, personal identification) locally before transmitting events.

> **Note**: In Phase 1, observation events are submitted directly via the REST API or using `backend/test_event.py`.
