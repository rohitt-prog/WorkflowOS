# WorkFlowOS — Automation Module (Phase 4)

## Overview

The **Automation** module translates human-approved [`WorkflowProposal`](../ai/models.py) schemas (produced by Phase 3 AI understanding) into validated, sequential action execution pipelines.

> ⚠️ **Phase 4.3 Notice**:
> Phase 4.3 adds **real browser execution** via `PlaywrightExecutor`, targeting the controlled local demo applications.
> **Phase 4.3 does NOT yet connect the frontend approval button to automation.** The approval flow integration belongs to a later phase.

---

## Architecture

```
Discovered Workflow (Phase 2)
           ↓
AI Workflow Understanding (Phase 3: WorkflowProposal)
           ↓
[Human Approval Safety Gate: approved == True]
           ↓
AutomationEngine (Phase 4.2)
   ├── Action Mapping & Validation (SUPPORTED_ACTION_TYPES)
   ├── Sequential Step Coordinator
   └── ActionExecutor Interface
           ↓
     ┌───────────────────────────┬──────────────────────────┐
     │ Phase 4.2 Default:        │ Phase 4.3 Active:        │
     │ NoOpExecutor              │ PlaywrightExecutor       │
     │ (Validation & Simulation) │ (Live Browser Control)   │
     └───────────────────────────┴──────────────────────────┘
           ↓
     Controlled Demo Applications
       /demo/email  /demo/crm  /demo/chat
```

---

## Core Components

### 1. `AutomationEngine` ([`automation/engine.py`](engine.py))
Responsible for:
1. Receiving a validated [`WorkflowProposal`](../ai/models.py).
2. Enforcing the **Approval Safety Gate** (`approved == True`).
3. Converting `WorkflowAction` objects into `AutomationAction` steps while preserving exact ordering.
4. Generating deterministic execution IDs (`exec_<hex>`).
5. Sequentially dispatching actions through an `ActionExecutor`.
6. Halting immediately upon any step failure and preserving completed steps.
7. Returning an `AutomationExecution` snapshot.

### 2. Action Mapping & Supported Verbs
The engine validates that every action belongs to the canonical Phase 4 action verbs:

| Action Verb | Application Target | Canonical Route | Description |
|---|---|---|---|
| `open_email` | `demo_email` | `/demo/email` | Opens customer request email in WorkFlow Mail |
| `download_attachment` | `demo_email` | `/demo/email` | Downloads `customer_request.pdf` (mock state) |
| `search_customer` | `demo_crm` | `/demo/crm` | Searches for customer record (e.g. Rahul) |
| `update_customer` | `demo_crm` | `/demo/crm` | Updates customer notes field |
| `send_message` | `demo_chat` | `/demo/chat` | Posts notification to `#customer-support` |

If an unknown action verb is encountered (e.g., `hack_mainframe`), an `UnsupportedActionError` is raised and execution is refused without running any steps.

### 3. Approval Safety Gate
- Execution is strictly conditioned on explicit operator approval (`approved=True`).
- If `approved=False`, status remains `AutomationStatus.PENDING`, `completed_actions` is empty, and zero actions are executed.
- Approval cannot be automatically inferred or bypassed.
- **`PlaywrightExecutor` itself does NOT bypass this gate.** The engine controls all dispatch.

### 4. `ActionExecutor` Abstraction ([`automation/executor.py`](executor.py))
Defines an asynchronous interface:
```python
class ActionExecutor(ABC):
    @abstractmethod
    async def execute(self, action: AutomationAction, context: Optional[Dict[str, Any]] = None) -> ExecutionActionResult:
        pass
```

- **`NoOpExecutor` (Phase 4.2, still available)**:
  - Validates action structure and confirms step execution flow.
  - Returns deterministic success responses with zero side effects.
  - Does **not** launch a browser or import Playwright.
  - Supports configurable `fail_actions` for testing error recovery.

- **`PlaywrightExecutor` (Phase 4.3, active)**:
  - Implements `ActionExecutor` using the Playwright Python async API.
  - Connects to the controlled demo applications (`/demo/email`, `/demo/crm`, `/demo/chat`).
  - Interacts with stable `data-testid` selectors established in Phase 4.1.
  - Never bypasses the AutomationEngine approval gate.

---

## PlaywrightExecutor (Phase 4.3)

### File
[`automation/playwright_executor.py`](playwright_executor.py)

### Supported Browser Actions

| Action | Demo App | Key Selectors |
|---|---|---|
| `open_email` | `/demo/email` | `[data-testid="email-item"]`, `[data-testid="open-email"]`, verifies `[data-testid="download-attachment"]` |
| `download_attachment` | `/demo/email` | `[data-testid="download-attachment"]`, verifies `[data-testid="download-status"]` contains "Attachment downloaded" |
| `search_customer` | `/demo/crm` | `[data-testid="customer-search"]`, `[data-testid="search-customer"]`, verifies `[data-testid="customer-result"]` |
| `update_customer` | `/demo/crm` | `[data-testid="customer-notes"]`, `[data-testid="update-customer"]`, verifies `[data-testid="update-status"]` contains "Customer updated" |
| `send_message` | `/demo/chat` | `[data-testid="message-input"]`, `[data-testid="send-message"]`, verifies `[data-testid="sent-message"]` and `[data-testid="send-status"]` contains "Message sent" |

### Usage

```python
from automation.playwright_executor import PlaywrightExecutor
from automation.engine import AutomationEngine

# Inject PlaywrightExecutor into the engine
engine = AutomationEngine()
executor = PlaywrightExecutor(base_url="http://localhost:3000", headless=True)

execution = await engine.execute_workflow(
    proposal=proposal,
    approved=True,
    executor=executor,
)
```

Using as context manager (handles lifecycle automatically):
```python
async with PlaywrightExecutor(base_url="http://localhost:3000", headless=True) as executor:
    result = await executor.execute(action)
```

### BASE_URL Configuration

The executor reads `PLAYWRIGHT_BASE_URL` from:
1. Constructor argument `base_url=...`
2. `settings.PLAYWRIGHT_BASE_URL` (from `backend/config.py`)
3. Environment variable `PLAYWRIGHT_BASE_URL`
4. Default fallback: `http://localhost:3000`

Demo routes are derived automatically:
```
{BASE_URL}/demo/email
{BASE_URL}/demo/crm
{BASE_URL}/demo/chat
```

Do **not** hardcode `localhost` throughout the executor — always use the configured `base_url`.

### Headless / Headed Configuration

```bash
# Headless (default for production/CI)
PLAYWRIGHT_HEADLESS=true

# Headed (useful for debugging)
PLAYWRIGHT_HEADLESS=false
```

Or pass directly:
```python
PlaywrightExecutor(headless=False)  # opens visible browser window
```

### Browser Lifecycle

Each workflow execution follows a clean lifecycle:

```
start()
  ↓
async_playwright().start()
  ↓
chromium.launch(headless=...)
  ↓
browser.new_context()
  ↓
context.new_page()
  ↓
execute actions sequentially
  ↓
cleanup() — always called in finally block
  ↓
page.close() → context.close() → browser.close() → playwright.stop()
```

**No orphaned browser processes are left after execution** — cleanup is always called even if an action raises an exception.

### Happy Path

```
/demo/email
    ↓ open_email (click Open button on Rahul's email)
    ↓ download_attachment (click Download, verify "Attachment downloaded" status)
    ↓
/demo/crm
    ↓ search_customer (search "Rahul", verify customer-result appears)
    ↓ update_customer (fill notes, click Update Customer, verify "Customer updated")
    ↓
/demo/chat
    ↓ send_message (type message, click Send, verify "Message sent")
    ↓
status = completed
completed_actions = ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"]
```

### Failure Behavior

- If any action fails (e.g., customer not found), execution halts immediately.
- Subsequent actions are **not** executed.
- `completed_actions` only contains successfully completed actions.
- `status` is set to `AutomationStatus.FAILED`.
- Stack traces are **not** exposed in `ExecutionActionResult`; only structured error messages.
- Browser cleanup is always performed, even after failure.

**Deterministic failure test**: searching for `"Unknown Customer"` triggers `search_customer` failure → `update_customer` and `send_message` are skipped.

### Action Variables / Parameters

Action parameters are resolved from multiple sources (in priority order):
1. `action.parameters` dict (e.g., `{"customer_name": "Rahul"}`)
2. `context` dict passed to engine
3. Fallback: `"Rahul"` for customer name, default notification text for messages

---

## Phase 4.3 Limitations

The following are **explicitly not implemented** in Phase 4.3 and belong to later phases:

- Frontend Approve → Execute integration
- Human intervention UI
- Pause / Resume workflow
- Execution dashboard
- Retries on failure
- CV / image-based automation fallback
- Real SaaS integrations (Gmail, Slack, Salesforce)
- Authentication flows
- Background workers / parallel execution
- Automatic workflow triggering

---

## Execution Lifecycle States (`AutomationStatus`)

| Status | Meaning |
|---|---|
| `pending` | Workflow proposal received but awaiting operator approval (`approved=False`). |
| `running` | Actions are actively executing sequentially. |
| `completed` | All actions executed successfully without error. |
| `failed` | An action failed during execution; subsequent steps were halted. |
| `waiting_for_human` | Execution paused for operator intervention (Phase 4.6). |

---

## Testing

### Phase 4.2 (Unit / Engine, no browser required)
```bash
.venv/bin/python backend/test_phase4_2.py
```

### Phase 4.3 (Integration tests, Playwright browser required)

**Prerequisites:**
1. Frontend running: `cd frontend && npm run dev`
2. Playwright Chromium installed: `.venv/bin/playwright install chromium`
3. Python venv active: `.venv`

```bash
.venv/bin/python backend/test_phase4_3.py
```

**Tests cover:**
1. `PlaywrightExecutor` can be constructed
2. Correct demo base URLs are generated
3. `open_email` works
4. `download_attachment` works
5. `search_customer` works for Rahul
6. `update_customer` works
7. `send_message` works
8. Full 5-action happy-path workflow completes
9. Unknown action rejected by `AutomationEngine`
10. Failure stops subsequent actions
11. Browser resources are cleaned up
12. `approved=False` prevents Playwright execution

---

## Phase 4.3 Statement

> **Phase 4.3 adds browser execution via `PlaywrightExecutor` but does not yet connect the frontend approval button to automation.** Workflow execution is triggered programmatically from tests or direct API calls. The frontend Approve button integration belongs to a later phase.
