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

## Phase 4.6: Human-in-the-Loop Execution, Pause, Resume, and Cancel

### 1. Overview & Architecture

Phase 4.6 elevates WorkFlowOS execution from run-to-completion automation into an interactive **Human-in-the-Loop (HITL)** operational system. When an action encounters an issue (such as an unknown customer in CRM), the execution transitions into a **PAUSED** state rather than terminating irrecoverably.

A human operator can review the issue, correct parameters (e.g., selecting or creating the valid customer), and **resume** execution from the failed action. Already completed actions are preserved and never re-executed. Alternatively, the operator can **cancel** the execution.

```
       [ Proposal Approved ]
                 │
                 ▼
         ┌───────────────┐
         │    PENDING    │
         └───────┬───────┘
                 │ (execute)
                 ▼
         ┌───────────────┐  action failure  ┌───────────────┐
         │    RUNNING    ├─────────────────►│    PAUSED     │
         └──┬────────────┘                  └───────┬───────┘
            │          ▲                            │
            │          │         resume()           │  cancel()
            │          └────────────────────────────┤
            │                                       │
            │ (all actions succeed)                 ▼
            ▼                               ┌───────────────┐
    ┌───────────────┐                       │   CANCELLED   │
    │   COMPLETED   │                       └───────────────┘
    └───────────────┘
```

### 2. State Machine & Transitions

The execution lifecycle strictly adheres to `AutomationStatus`:

| From State | Allowed Target States | Trigger / Mechanism |
|---|---|---|
| `PENDING` | `RUNNING`, `CANCELLED` | Execution begins or proposal cancelled prior to start |
| `RUNNING` | `COMPLETED`, `PAUSED`, `FAILED` | Actions finish (`COMPLETED`), action fails (`PAUSED`), unrecoverable engine failure (`FAILED`) |
| `PAUSED` | `RUNNING`, `CANCELLED` | Operator calls `resume` (`RUNNING`) or operator calls `cancel` (`CANCELLED`) |
| `COMPLETED` | *(Terminal)* | Execution finished successfully |
| `FAILED` | *(Terminal)* | Irrecoverable system failure |
| `CANCELLED` | *(Terminal)* | Execution cancelled by operator |

Any invalid transition attempt (e.g., resuming a `CANCELLED` or `COMPLETED` execution) is rejected with `InvalidStateTransitionError` / `409 Conflict`.

### 3. Pause Behavior on Action Failure

When an action within `AutomationEngine` fails:
1. Status transitions from `RUNNING` → `PAUSED`.
2. `resume_available` is set to `True`.
3. `requires_human_intervention` is set to `True`.
4. `failed_action` stores the name of the failing action (`search_customer`).
5. `failure_reason` records the failure error message.
6. `paused_at` records the ISO 8601 timestamp.
7. Subsequent actions retain `pending` status (NOT marked `skipped`), clearly signaling they await human resumption.
8. Execution state (completed actions, results, action index) is preserved.

### 4. Resume Semantics & Flow

When an operator triggers `POST /api/automation/executions/{execution_id}/resume`:
1. Validates that the execution exists (`404 Not Found` if missing).
2. Validates that current status is `PAUSED` and `resume_available=True` (`409 Conflict` otherwise).
3. Increments `resume_count` by 1 and records `resumed_at` timestamp.
4. Identifies the failed action index (e.g. step index 2 for `search_customer`).
5. Updates context/parameters if supplied in the resume request (e.g. updated customer name/target).
6. Transitions status `PAUSED` → `RUNNING`.
7. Calls `AutomationEngine.execute_from_index(start_index=failed_index)`:
   - **Does NOT re-run completed actions** (Step 1 `open_email` and Step 2 `download_attachment` remain intact).
   - **Retries the failed action** with updated context.
   - If retry succeeds, proceeds through remaining pending actions (`update_customer`, `send_message`).
   - If retry fails again, cleanly transitions back to `PAUSED` for further intervention.
   - If all actions succeed, transitions to `COMPLETED`.

### 5. Cancel Semantics

When an operator triggers `POST /api/automation/executions/{execution_id}/cancel`:
1. Validates that the execution exists (`404 Not Found` if missing).
2. Validates that current status is `PAUSED` or `PENDING` (`409 Conflict` if already completed/cancelled).
3. Transitions status to `CANCELLED`.
4. Sets `resume_available = False` and `requires_human_intervention = False`.
5. Records `cancelled_at` ISO 8601 timestamp.
6. Subsequent resume attempts are permanently blocked with `409 Conflict`.

### 6. API Endpoints

#### Endpoint: `POST /api/automation/executions/{execution_id}/resume`
Resumes a paused execution from its failed action.

**Request Payload:**
```json
{
  "executor_type": "noop",
  "parameters": {
    "customer": "Rahul",
    "simulate_failure": false
  },
  "context": {
    "customer_id": "cust_123"
  }
}
```

**Response (Success `200 OK`):**
```json
{
  "execution_id": "exec-abc123xyz",
  "status": "completed",
  "actions_completed": 5,
  "total_actions": 5,
  "failed_action": null,
  "failure_reason": null,
  "resume_available": false,
  "resume_count": 1,
  "resumed_at": "2026-10-03T07:45:00.000Z",
  "paused_at": "2026-10-03T07:40:00.000Z",
  "cancelled_at": null,
  "all_actions": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
  "actions_detail": [
    { "action": "open_email", "status": "completed", "message": "Email opened" },
    { "action": "download_attachment", "status": "completed", "message": "Attachment downloaded" },
    { "action": "search_customer", "status": "completed", "message": "Customer found" },
    { "action": "update_customer", "status": "completed", "message": "Customer updated" },
    { "action": "send_message", "status": "completed", "message": "Message sent" }
  ]
}
```

**Errors:**
- `404 Not Found`: Execution ID not recognized.
- `409 Conflict`: Execution not in `PAUSED` state or already cancelled/completed.

---

#### Endpoint: `POST /api/automation/executions/{execution_id}/cancel`
Cancels a paused or pending execution.

**Response (`200 OK`):**
```json
{
  "execution_id": "exec-abc123xyz",
  "status": "cancelled",
  "resume_available": false,
  "requires_human_intervention": false,
  "cancelled_at": "2026-10-03T07:46:00.000Z"
}
```

**Errors:**
- `404 Not Found`: Execution ID not recognized.
- `409 Conflict`: Execution not cancellable (e.g. already finished or cancelled).

---

## Testing

### 1. Phase 4.6 HITL & State Machine Tests
```bash
.venv/bin/python backend/test_phase4_6.py
```
Validates:
- Execution enters `PAUSED` on action failure with `resume_available=True`
- Subsequent actions remain in `pending` state awaiting resume
- Resuming executes the failed action and continues downstream actions
- Resuming does not re-run already completed actions
- Context and parameters are passed to resumed action
- `resume_count` increments and `resumed_at` is tracked
- Repeated pause and resume cycles
- Cancel transitions `PAUSED` → `CANCELLED` and sets `cancelled_at`
- Cancelling makes resume unavailable and rejects future resume with `409 Conflict`
- Invalid transitions are rejected
- Execution history preserves lifecycle metadata across pauses and resumes
- Observability and API routes correctly expose all Phase 4.6 telemetry

### 2. Full Regression Suite
```bash
.venv/bin/python backend/test_phase4_2.py
.venv/bin/python backend/test_phase4_3.py
.venv/bin/python backend/test_phase4_4.py
.venv/bin/python backend/test_phase4_5.py
.venv/bin/python backend/test_phase4_6.py
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
5. **Human-in-the-Loop Pause Demo**:
   - In proposal modal, select `Unknown Customer (Fail Demo)` and click **APPROVE & RUN**.
   - Step 1 (`open_email`) and Step 2 (`download_attachment`) succeed (`✓`).
   - Step 3 (`search_customer`) fails with `Customer not found`.
   - Workflow transitions to `⏸ Automation paused (Requires Human Intervention)`.
   - Observe Steps 4 & 5 remain in `○ pending` state (not skipped).
   - Yellow Human Intervention Banner appears with failure reason and prompt.
   - Footer controls present:
     - Target Fix dropdown (`Rahul (Valid Customer)`).
     - **[ Resume Execution ]** button.
     - **[ Cancel Execution ]** button.
6. **Resume Execution Demo**:
   - Select `Rahul (Valid Customer)` in the intervention quick-fix dropdown.
   - Click **[ Resume Execution ]**.
   - Observe status change to `Resuming execution from step 3...`.
   - Step 3 is retried and succeeds (`✓`).
   - Steps 4 and 5 execute and complete (`✓`).
   - Workflow finishes with `✓ Automation completed` (`5 / 5 actions`, `Resumed 1 time`).
7. **Cancel Execution Demo**:
   - Run another execution with `Unknown Customer (Fail Demo)`.
   - When execution enters `⏸ Automation paused`, click **[ Cancel Execution ]**.
   - Execution transitions to `⏹ Automation cancelled`.
   - Resume controls are disabled.
8. **Execution History Inspection**:
   - In **Execution History (Phase 4.5 & 4.6)**, inspect runs.
   - Paused runs show `⏸ paused` badge.
   - Resumed runs show `✓ completed` badge with `↺ Resumed 1x` tag.
   - Cancelled runs show `⏹ cancelled` badge.
   - Click **Inspect Details** to view full lifecycle audit trail with timestamps (`paused_at`, `resumed_at`, `cancelled_at`).

---

## Known Limitations

- Supported canonical actions are currently restricted to the 5 demo actions (`open_email`, `download_attachment`, `search_customer`, `update_customer`, `send_message`).
- Automated actions target local demo endpoints (`/demo/email`, `/demo/crm`, `/demo/chat`), not external third-party SaaS services. Real external integrations belong to Phase 7.
- Execution history is stored in-memory during the application lifecycle for demo simplicity; persistent DB storage can be connected via existing database adapters.

---

## Phase 6 — Generalized Workflow Engine

Phase 6 upgrades the automation module with a fully declarative workflow engine that supports complex branching, retry policies, variable interpolation, and a proper execution state machine — while remaining 100% backward compatible with Phase 4 `WorkflowProposal` schemas.

### New Models (`automation/models.py`)

| Model | Purpose |
|-------|---------|
| `WorkflowStep` | A single declarative step with `id`, `type`, `application`, `parameters`, `condition`, `retry`, `output_mapping` |
| `WorkflowDefinition` | Full workflow with `id`, `name`, `trigger`, `inputs`, `steps`, `requires_approval`, `tags` |
| `StepCondition` | Conditional execution: `variable`, `operator`, `value` |
| `RetryPolicy` | `max_attempts`, `delay_seconds` |
| `WorkflowInputDefinition` | Named typed input parameter |
| `StepExecutionResult` | Per-step output, timing, retries, skip reason |

### Engine Functions (`automation/engine.py`)

| Function | Description |
|----------|-------------|
| `resolve_template_value(val, ctx)` | Resolve `{{inputs.x}}`, `{{steps.id.output.y}}`, `{{variables.z}}` |
| `evaluate_step_condition(cond, ctx)` | Evaluate skip/branch conditions at runtime |
| `execute_declarative_workflow(wf, req)` | Run a `WorkflowDefinition` end-to-end |
| `_run_declarative_steps(steps, ctx, exec)` | Step loop with conditions, retries, output mapping |
| `resume_declarative_workflow(exec, req)` | Resume a paused declarative execution |
| `proposal_to_workflow_definition(proposal)` | Convert legacy `WorkflowProposal` → `WorkflowDefinition` |

### Variable Interpolation Syntax

Templates in `parameters` fields use `{{...}}`:

```python
# Input parameter
"{{inputs.customer_name}}"

# Output from a previous step
"{{steps.lookup_crm.output.customer_id}}"
# Also accessible as:
"{{steps.lookup_crm.output.data.customer_id}}"

# Named variable set during execution
"{{variables.my_var}}"
```

### Condition Operators

| Operator | Description |
|----------|-------------|
| `==` / `!=` | Equality check |
| `>` / `<` / `>=` / `<=` | Numeric comparison |
| `contains` | Substring or list membership |
| `in` | Value in list |
| `is_empty` / `is_not_empty` | Falsy / truthy check |
| `exists` | Key exists in context |

### Step Branching

```python
WorkflowStep(
    id="check",
    type="condition",
    condition=StepCondition(variable="inputs.flag", operator="==", value=True),
    on_true="step_a",   # jump to step_a if condition is True
    on_false="step_b",  # jump to step_b if condition is False
)
```

### Retry Policy

```python
WorkflowStep(
    id="fragile_step",
    type="search_customer",
    retry=RetryPolicy(max_attempts=3, delay_seconds=1),
)
```

### Execution State Machine

```
pending ──► running ──► completed
                    ╲
                     ╲──► paused  ──► (resume) ──► running ──► completed
                      ╲             ╲──► (cancel) ──► cancelled
                       ╲──► failed  (terminal unless pause_on_failure)
                        ╲──► cancelled (terminal)
```

### Service Registry (`automation/service.py`)

```python
from automation.service import automation_service

# List all registered templates
templates = automation_service.list_workflows()

# Register a new workflow
automation_service.register_workflow(my_definition)

# Run by workflow ID
result = await automation_service.run_declarative_workflow("wf_id", request)

# Unified runner (handles both legacy and declarative)
result = await automation_service.run_workflow(request)
```

### Phase 6 REST Endpoints

```
GET  /api/automation/workflows               → list templates
POST /api/automation/workflows               → register workflow
GET  /api/automation/workflows/{id}          → get template
POST /api/automation/execute                 → run (legacy or declarative)
GET  /api/automation/executions              → list history
GET  /api/automation/executions/{id}         → get detail
POST /api/automation/executions/{id}/resume  → resume paused
POST /api/automation/executions/{id}/cancel  → cancel
```

### Backward Compatibility

All Phase 4 `WorkflowProposal` execution paths continue to work unchanged. The `POST /api/automation/execute` endpoint auto-detects the request shape:
- If `workflow_definition` key is present → declarative engine
- If `workflow` (proposal) key is present → legacy `proposal_to_workflow_definition` conversion

### Phase 6 Test Coverage (`backend/test_phase6.py`)

| Test | Description |
|------|-------------|
| `test_01` | Workflow template registration and retrieval |
| `test_02` | Built-in template listing |
| `test_03` | Unapproved declarative workflow safely refused |
| `test_04` | Variable interpolation in step parameters |
| `test_05` | Output mapping from step result to context |
| `test_06` | Conditional branching (`on_true` / `on_false`) |
| `test_07` | Retry policy recovers from transient failure |
| `test_08` | `continue_on_failure` tolerance mode |
| `test_09` | Pause on failure → resume completes successfully |
| `test_10` | Backward compat: `WorkflowProposal` → declarative conversion |
| `test_11` | REST API: list + get workflow templates |
| `test_12` | REST API: execute declarative workflow (unapproved → approved) |
| `test_13` | REST API: cancel execution |
