# WorkFlowOS — REST API Reference

The WorkFlowOS backend provides a structured, typed REST API built on **FastAPI** and **Pydantic**.
All endpoints return JSON responses. Sensitive fields (credentials, tokens, private keys) are automatically scrubbed or redacted.

---

## 1. Health & System Telemetry

### `GET /health`
- **Description**: Lightweight health check endpoint verifying database connectivity.
- **Response**:
  ```json
  {
    "status": "healthy",
    "database": "connected"
  }
  ```

### `GET /api/system/status`
- **Description**: Aggregates operational status, desktop agent connectivity, connected applications, discovered patterns, and execution statistics.
- **Response**:
  ```json
  {
    "backend": "healthy",
    "agent": "connected",
    "agent_details": { "process_id": 12345, "mode": "daemon" },
    "applications": { "connected": 4, "available": 4 },
    "workflows": { "discovered": 8, "declarative": 2 },
    "executions": { "total": 12, "successful": 11, "failed": 1 },
    "privacy": {
      "collection_enabled": true,
      "retention_days": 30,
      "redaction_active": true,
      "human_approval_required": true
    }
  }
  ```

### `GET /api/system/settings`
- **Description**: Returns safe, non-sensitive runtime configuration parameters.

---

## 2. Desktop Activity Events

### `POST /api/events`
- **Description**: Ingests a structured user interaction event from the desktop agent. Passes payload through the privacy redaction engine and verifies collection toggle.
- **Request Body**:
  ```json
  {
    "session_id": "session_101",
    "application": "demo_email",
    "window_title": "Inbox — customer_inquiry.pdf",
    "action": "open_email",
    "target": "inbox_item_44",
    "timestamp": "2026-10-06T12:00:00Z",
    "metadata": {}
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "status": "success",
    "event_id": "6702e88a0b0d3e582d90ef01",
    "redacted": false
  }
  ```

### `GET /api/events`
- **Description**: Retrieves recent desktop events with optional session, application, or limit filters.
- **Query Parameters**:
  - `session_id` (optional, string)
  - `application` (optional, string)
  - `limit` (default: 50, integer)

---

## 3. Workflow Discovery

### `GET /api/discovery/repeated`
- **Description**: Executes the multi-session repetition detector and local sequence alignment engine to find recurring workflow patterns.
- **Query Parameters**:
  - `min_length` (default: 3, integer)
  - `min_occurrences` (default: 2, integer)
  - `similarity_threshold` (default: 0.8, float)
- **Response**:
  ```json
  {
    "detected": true,
    "workflows": [
      {
        "label": "Customer Request Processing",
        "sequence": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
        "occurrences": 3,
        "similarity": 0.95,
        "confidence": 0.82,
        "ranking_score": 0.87,
        "quality_tier": "strong",
        "explanation": {
          "human_readable_summary": "Discovered across 3 distinct sessions with high alignment consistency."
        }
      }
    ]
  }
  ```

### `POST /api/discovery/proposals/generate`
- **Description**: Uses Google Gemini to convert an observed event sequence into a structured, human-readable `WorkflowProposal`.

---

## 4. Declarative Workflows & Management

### `GET /api/automation/workflows`
- **Description**: Lists all registered declarative workflow definitions (`WorkflowDefinition`).

### `POST /api/automation/workflows`
- **Description**: Registers or updates a declarative workflow definition. Computes definition hash automatically.

### `GET /api/automation/workflows/{workflow_id}`
- **Description**: Retrieves a single workflow definition by ID.

---

## 5. Intelligent Automation Planning

### `POST /api/automation/plan`
- **Description**: Invokes the Phase 10 Automation Planner to analyze workflow steps, inspect capabilities, and select optimal strategies with safe fallbacks.
- **Request Body**:
  ```json
  {
    "workflow_id": "wf_customer_support_pipeline",
    "steps": [
      { "id": "step_1", "type": "open_email", "application": "demo_email" },
      { "id": "step_2", "type": "download_attachment", "application": "demo_email" }
    ]
  }
  ```
- **Response**:
  ```json
  {
    "workflow_id": "wf_customer_support_pipeline",
    "selected_strategy": "INTEGRATION",
    "overall_score": 0.88,
    "requires_approval": true,
    "fallback_available": true,
    "steps": [
      {
        "step_id": "step_1",
        "action": "open_email",
        "selected_strategy": "API",
        "score": 0.90,
        "fallback_strategy": "BROWSER",
        "selected_reasons": ["Native API capability available"]
      }
    ]
  }
  ```

---

## 6. Execution Engine

### `POST /api/automation/execute`
- **Description**: Executes an approved workflow proposal or declarative workflow. Refuses execution if `approved=false`.
- **Request Body**:
  ```json
  {
    "proposal": { ... },
    "approved": true,
    "executor_type": "noop",
    "idempotency_key": "optional_idempotency_uuid"
  }
  ```
- **Response**:
  ```json
  {
    "status": "completed",
    "workflow_id": "exec_abc123",
    "completed_actions": ["open_email", "download_attachment", "search_customer"],
    "total_actions": 3,
    "execution_time_seconds": 0.12
  }
  ```

### `GET /api/automation/executions`
- **Description**: Retrieves execution history with per-step results, timestamps, and error messages.

### `POST /api/automation/executions/{execution_id}/resume`
- **Description**: Resumes a `PAUSED` execution from the failed step without re-executing previously completed actions.

### `POST /api/automation/executions/{execution_id}/cancel`
- **Description**: Cancels a running or paused execution gracefully.

---

## 7. Adaptive Learning & Feedback

### `POST /api/workflows/{workflow_id}/feedback`
- **Description**: Submits human operator feedback (`approve`, `reject`, `edit_approve`, `intervention`). Recalculates the learning score immediately using the exact Phase 9 equation.
- **Request Body**:
  ```json
  {
    "feedback_type": "approve",
    "notes": "Verified correct behavior"
  }
  ```
- **Response**:
  ```json
  {
    "workflow_id": "wf_customer_support_pipeline",
    "learning_score": 0.70,
    "recommendation_status": "LEARNING",
    "approval_count": 2,
    "rejection_count": 0
  }
  ```

### `GET /api/workflows/{workflow_id}/learning`
- **Description**: Retrieves the complete learning state, score, recommendation tier, and explanation for a workflow.

---

## 8. Privacy & Data Governance

### `GET /api/privacy/status`
- **Description**: Returns current collection status, retention policy window, and active redactor status.

### `POST /api/privacy/collection`
- **Description**: Toggles desktop activity event collection dynamically (`{"enabled": false}`).

### `POST /api/privacy/retention`
- **Description**: Configures event retention threshold in days (`{"retention_days": 14}`).

### `POST /api/privacy/cleanup`
- **Description**: Purges events older than the configured retention policy cutoff. Supports dry-run reporting (`{"dry_run": true}`).

### `POST /api/privacy/audit`
- **Description**: Audits a JSON payload for detected sensitive categories without exposing values.

---

## 9. Application Ecosystem

### `GET /api/applications`
- **Description**: Lists all registered application adapters (`gmail`, `crm`, `chat`, `mock_service`) with connection health.

### `GET /api/applications/{app_id}/health`
- **Description**: Queries real-time connection status and health diagnostics for a target application.

### `GET /api/applications/capabilities`
- **Description**: Returns the unified catalog of declared capabilities across all applications, detailing mutation type and approval requirements.
