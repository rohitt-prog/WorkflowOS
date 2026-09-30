# WorkFlowOS — Automation Module (Phase 4)

## Overview

The **Automation** module translates human-approved [`WorkflowProposal`](../ai/models.py) schemas (produced by Phase 3 AI understanding) into validated, sequential action execution pipelines.

Phase 4.4 connects the **Frontend AI Workflow Proposal approval flow** to the backend **AutomationEngine** and **PlaywrightExecutor**, enabling end-to-end execution of the complete 5-action demo workflow with browser automation, visual progress tracking, and human intervention handling.

---

## Phase 4.4 End-to-End Architecture

```
Frontend UI (Proposal Review Modal)
        │
        │ [User clicks: APPROVE & RUN] (approved=True)
        ▼
POST /api/automation/execute
        │
        ▼
AutomationService (automation/service.py)
        │
        ▼
AutomationEngine (automation/engine.py)
   ├── 1. Action Mapping & Validation (SUPPORTED_ACTION_TYPES)
   ├── 2. Approval Safety Gate (approved == True required)
   └── 3. Sequential Step Coordinator
        │
        ▼
PlaywrightExecutor (automation/playwright_executor.py)
        │
        ├── Action 1: open_email           → /demo/email
        ├── Action 2: download_attachment  → /demo/email
        ├── Action 3: search_customer      → /demo/crm
        ├── Action 4: update_customer      → /demo/crm
        └── Action 5: send_message         → /demo/chat
        │
        ▼
Execution Result & Progress UI
   ├── Happy Path: ✅ Workflow completed successfully (all 5 actions green)
   └── Failure Path: ❌ Action failed + ⚠ Human intervention required (Workflow paused)
```

---

## Execution Chain & Safety

Strict hierarchy prevents execution bypass:

1. **API Route** (`POST /api/automation/execute`):
   - Validates request payload (`workflow` / `actions`, `approved`, `parameters`, `executor_type`).
   - Delegates execution directly to `automation_service`.
   - Never calls `PlaywrightExecutor` directly from the route.

2. **AutomationService** (`automation/service.py`):
   - Coordinates execution runs, selects the appropriate executor (`PlaywrightExecutor` for live execution or `NoOpExecutor` for headless unit testing).
   - Records execution history accessible via `GET /api/automation/executions`.

3. **AutomationEngine** (`automation/engine.py`):
   - **Approval Gate**: If `approved != True`, immediately returns `status="pending"` with 0 completed actions. Neither Playwright nor browser is ever launched.
   - **Action Validation**: Ensures all action verbs belong to `SUPPORTED_ACTION_TYPES`.
   - **Sequential Execution**: Runs actions one-by-one. Halts immediately upon any action failure. Preserves already completed actions and cleans up all browser resources.

4. **PlaywrightExecutor** (`automation/playwright_executor.py`):
   - Launches headless Chromium browser.
   - Drives user interactions across `/demo/email`, `/demo/crm`, and `/demo/chat` via robust `data-testid` selectors.
   - Cleans up all browser contexts and pages upon workflow completion or error.

---

## API Specification

### Endpoint: `POST /api/automation/execute`

#### Request Payload
```json
{
  "workflow": {
    "name": "Process Customer Request",
    "intent": "Automate customer email attachment processing and CRM update",
    "trigger": {
      "type": "new_email",
      "application": "demo_email",
      "description": "Email received from customer"
    },
    "actions": [
      {
        "type": "open_email",
        "application": "demo_email",
        "description": "Open customer email",
        "target": "customer_request"
      },
      {
        "type": "download_attachment",
        "application": "demo_email",
        "description": "Download email attachment",
        "target": "attachment"
      },
      {
        "type": "search_customer",
        "application": "demo_crm",
        "description": "Search customer in CRM",
        "target": "Rahul"
      },
      {
        "type": "update_customer",
        "application": "demo_crm",
        "description": "Update customer record in CRM",
        "target": "Rahul"
      },
      {
        "type": "send_message",
        "application": "demo_chat",
        "description": "Send notification message to chat",
        "target": "customer_request"
      }
    ],
    "variables": ["customer_name", "attachment"],
    "applications": ["demo_email", "demo_crm", "demo_chat"],
    "requires_approval": true
  },
  "approved": true,
  "session_id": "session_001",
  "parameters": {
    "customer_name": "Rahul"
  },
  "executor_type": "playwright"
}
```

#### Happy Path Response (`status="completed"`)
```json
{
  "status": "completed",
  "workflow_id": "exec_301325576b79",
  "workflow_name": "Process Customer Request",
  "message": "Workflow completed successfully",
  "requires_human_intervention": false,
  "human_intervention": null,
  "actions": [
    {
      "action": "open_email",
      "status": "completed",
      "message": "Customer email opened and attachment container verified"
    },
    {
      "action": "download_attachment",
      "status": "completed",
      "message": "Attachment downloaded and confirmed in demo UI"
    },
    {
      "action": "search_customer",
      "status": "completed",
      "message": "Customer Rahul found"
    },
    {
      "action": "update_customer",
      "status": "completed",
      "message": "Customer updated successfully in CRM"
    },
    {
      "action": "send_message",
      "status": "completed",
      "message": "Notification message sent to chat channel"
    }
  ],
  "completed_actions": [
    "open_email",
    "download_attachment",
    "search_customer",
    "update_customer",
    "send_message"
  ],
  "total_actions": 5
}
```

#### Failure Path Response (`status="failed"`)
```json
{
  "status": "failed",
  "workflow_id": "exec_833f47d588d0",
  "workflow_name": "Process Customer Request",
  "failed_action": "search_customer",
  "message": "Customer 'Unknown Customer' not found",
  "requires_human_intervention": true,
  "human_intervention": {
    "title": "Workflow paused",
    "reason": "Customer not found",
    "action_required": "Please resolve the issue in WorkFlow CRM."
  },
  "actions": [
    {
      "action": "open_email",
      "status": "completed",
      "message": "Customer email opened and attachment container verified"
    },
    {
      "action": "download_attachment",
      "status": "completed",
      "message": "Attachment downloaded and confirmed in demo UI"
    },
    {
      "action": "search_customer",
      "status": "failed",
      "message": "Customer 'Unknown Customer' not found"
    }
  ],
  "completed_actions": [
    "open_email",
    "download_attachment"
  ],
  "total_actions": 5
}
```

#### Unapproved Response (`approved=false`)
```json
{
  "status": "pending",
  "workflow_id": "exec_e64a21283e8e",
  "workflow_name": "Process Customer Request",
  "message": "Workflow execution pending approval. Human approval is required.",
  "requires_human_intervention": false,
  "human_intervention": null,
  "actions": [],
  "completed_actions": [],
  "total_actions": 5
}
```

---

## Playwright Selectors Used

All actions interact deterministically with stable `data-testid` attributes:

| Route | Action | Key Selectors |
|---|---|---|
| `/demo/email` | `open_email` | `[data-testid="email-item"]`, `[data-testid="open-email"]` |
| `/demo/email` | `download_attachment` | `[data-testid="download-attachment"]`, `[data-testid="download-status"]` |
| `/demo/crm` | `search_customer` | `[data-testid="customer-search"]`, `[data-testid="search-customer"]`, `[data-testid="customer-result"]`, `[data-testid="not-found-message"]` |
| `/demo/crm` | `update_customer` | `[data-testid="customer-notes"]`, `[data-testid="update-customer"]`, `[data-testid="update-status"]` |
| `/demo/chat` | `send_message` | `[data-testid="chat-channel"]`, `[data-testid="message-input"]`, `[data-testid="send-message"]`, `[data-testid="send-status"]` |

---

## Frontend UI Behavior

The Workflow Proposal review modal (`frontend/src/app/page.tsx`) provides:

1. **Parameter Selector**:
   - `Rahul (Happy Path)`: Searches for known customer; executes all 5 actions to completion.
   - `Unknown Customer (Fail Demo)`: Searches for non-existent customer; deterministically triggers human intervention failure.
2. **Action Trigger**:
   - Button labeled `APPROVE & RUN` (`id="approve-workflow-btn"`).
   - When clicked, displays active state: `Running Workflow...` with animated spinner.
3. **Happy Path Progress**:
   - Shows `✅ Workflow completed successfully`.
   - Displays real-time checklist:
     - `✓ Open email`
     - `✓ Download attachment`
     - `✓ Search customer`
     - `✓ Update customer`
     - `✓ Send message`
4. **Failure & Human Intervention UI**:
   - Displays action checklist highlighting point of failure:
     - `✓ Open email`
     - `✓ Download attachment`
     - `❌ Search customer`
   - Halts prior to executing `update_customer` or `send_message`.
   - Displays human intervention alert card:
     ```
     Workflow paused
     Reason: Customer not found
     Action required: Please resolve the issue in WorkFlow CRM.
     ⚠ Human intervention required
     ```

---

## Phase 4.5 Execution Observability & Frontend Polish

Phase 4.5 improves execution observability and frontend demo polish without introducing new automation mechanisms. It exposes and visualizes the execution state produced by the existing `AutomationService`, `AutomationEngine`, and `PlaywrightExecutor`.

### 1. Execution Observability & Action States

Phase 4.5 tracks and surfaces the exact action lifecycle states across all execution modes:
- `pending`: Action is queued and has not yet started execution.
- `running`: Action is actively being executed.
- `completed`: Action executed successfully (`✓`).
- `failed`: Action encountered an error and halted execution (`✗`).
- `skipped`: Subsequent action was not executed due to an upstream failure (`○ NOT EXECUTED`).

Visual representation during execution and inspection:
```
✓ Open email                (WorkFlow Mail - completed)
✓ Download attachment       (WorkFlow Mail - completed)
✗ Search customer           (WorkFlow CRM - failed)
○ Update customer           (WorkFlow CRM - skipped / not executed)
○ Send message              (WorkFlow Chat - skipped / not executed)
```

No execution events or metrics are fabricated. If an action fails at step 3, downstream steps 4 and 5 are strictly reported as `skipped` / `not executed`.

### 2. Execution Summary

After execution completes, the UI presents an enriched execution summary:

#### Success State:
- **Status Badge**: `✓ Automation completed`
- **Actions Count**: `X / Y actions completed` (e.g. `5 / 5 actions completed`)
- **Execution Time**: Real measured duration in seconds (e.g. `2.02s` via `time.perf_counter()`)
- **Applications Involved**: Count and badges of distinct applications involved (e.g. `3 applications: WorkFlow Mail, WorkFlow CRM, WorkFlow Chat`)

#### Failure State:
- **Status Badge**: `⚠ Automation stopped`
- **Actions Count**: `X / Y actions completed` (e.g. `2 / 5 actions completed`)
- **Failed Action**: Target action name (e.g. `search_customer`)
- **Reason**: Precise failure message (e.g. `Customer not found`)
- **Human Intervention Notice**:
  ```
  Workflow paused
  Reason: Customer not found
  Action required: Please resolve the issue in WorkFlow CRM.
  ⚠ Human intervention required
  ```

### 3. Execution History Section

Located directly on the main dashboard (`/`), the **Execution History** table automatically pulls records from `GET /api/automation/executions`:
- **Workflow Name**: Proposal or execution name.
- **Status Badge**: Standardized status badges (`✓ Automation completed`, `⚠ Automation stopped`, `● Automation running`, `○ Pending approval`).
- **Completed/Total Actions**: Progress ratio and percentage progress bar.
- **Timestamp**: Formatted execution start time.
- **Duration**: Actual measured execution duration.
- **Applications**: Badges for applications touched during the run.
- **Failure Reason**: Direct explanation if failed.
- **Inspect**: "Inspect Details" action button opening the execution modal.

### 4. Execution Details Inspection Modal

Clicking "Inspect Details" on any execution history row opens a modal displaying:
- **Workflow Title & Status Banner**: Current execution status and message.
- **Metadata Grid**: Execution ID, start/completion timestamps, duration, and application count.
- **Step-by-Step Action Timeline**:
  - Sequence number and status icon (`✓`, `✗`, `○`).
  - Human-friendly action title and raw action verb.
  - Target application badge.
  - Status pill (`completed`, `failed`, `skipped`, `pending`).
  - Action-specific execution message or failure reason.

### 5. Backend Extensions in Phase 4.5

All Phase 4.5 extensions are strictly additive and backward-compatible with Phase 4.2–4.4:
- **`automation/models.py`**:
  - `ActionDetail`: Structured per-action status record (`action`, `application`, `status`, `message`, `target`).
  - `AutomationExecution` & `ExecuteWorkflowResponse`: Added `started_at`, `completed_at`, `execution_time_seconds`, `applications`, `actions_detail`, and `all_actions`.
- **`automation/engine.py`**:
  - Calculates actual execution duration via `time.perf_counter()`.
  - Records ISO 8601 timestamps and unique application names.
  - Populates granular action states for completed, failed, and skipped steps.
- **`automation/service.py`**:
  - Passes simulation parameters to `NoOpExecutor` for controlled failure unit tests.
- **`backend/routes/automation.py`**:
  - Added `GET /api/automation/executions/{execution_id}` endpoint.
  - Returns timing, application list, and full action details in `POST /api/automation/execute`.

---

## Testing

### 1. Phase 4.5 Observability Tests
```bash
.venv/bin/python backend/test_phase4_5.py
```
Validates:
- Completed execution representation, action details, and timing metadata
- Failed execution representation, human intervention requirement, and skipped action states
- Unapproved execution pending state representation
- `GET /api/automation/executions` history listing endpoint
- `GET /api/automation/executions/{execution_id}` detail endpoint

### 2. Full Regression Suite
```bash
.venv/bin/python backend/test_phase4_2.py
.venv/bin/python backend/test_phase4_3.py
.venv/bin/python backend/test_phase4_4.py
.venv/bin/python backend/test_phase3.py
```

### 3. Frontend Production Build
```bash
cd frontend && npm run build
```

---

## Manual Demo Steps

1. **Start Backend**:
   ```bash
   uvicorn backend.main:app --port 8000 --reload
   ```
2. **Start Frontend**:
   ```bash
   cd frontend && npm run dev
   ```
3. Open `http://localhost:3000` in your browser.
4. **Happy Path Execution**:
   - Under **Workflow Candidates (Phase 2 & 3)**, click **Review AI Proposal**.
   - Keep `Rahul (Happy Path)` selected.
   - Click **APPROVE & RUN**.
   - Observe status change to `● Automation running` with pending/running action items.
   - Upon completion, observe `✓ Automation completed`, `5 / 5 actions completed`, execution time, and application list.
   - Observe all 5 action items marked with green checkmarks (`✓`).
5. **Execution History Inspection**:
   - Scroll down to the **Execution History (Phase 4.5)** section on the main dashboard.
   - Verify the newly completed execution appears with `✓ Automation completed`, duration, and application badges.
   - Click **Inspect Details** to open the inspection modal.
   - Verify the action timeline displays all 5 steps with application names and `completed` status pills.
6. **Failure & Observability Demo**:
   - Return to the proposal modal (or click **Run Again**).
   - Select `Unknown Customer (Fail Demo)` and click **APPROVE & RUN**.
   - Observe execution halt at Step 3 (`search_customer`).
   - Status badge shows `⚠ Automation stopped`.
   - Steps 1 & 2 show `✓ completed`.
   - Step 3 shows `✗ failed` with reason: `Customer not found`.
   - Steps 4 & 5 show `○ NOT EXECUTED` (`skipped`).
   - Human intervention alert displays:
     ```
     Workflow paused
     Reason: Customer not found
     Action required: Please resolve the issue in WorkFlow CRM.
     ⚠ Human intervention required
     ```
   - In **Execution History**, verify the run is recorded with `⚠ Automation stopped`, `2 / 5 actions`, and inspect its timeline in the details modal.

---

## Known Limitations

- Supported canonical actions are currently restricted to the 5 demo actions (`open_email`, `download_attachment`, `search_customer`, `update_customer`, `send_message`).
- Automated actions target local demo endpoints (`/demo/email`, `/demo/crm`, `/demo/chat`), not external third-party SaaS services.
- Resuming workflows after human intervention (pause/resume state machine) is scheduled for Phase 4.6.
- Execution history is currently stored in-memory during the application lifecycle for hackathon simplicity; it resets on server restart.
