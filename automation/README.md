# WorkFlowOS — Automation Module (Phase 4)

## Overview

The **Automation** module translates human-approved [`WorkflowProposal`](../ai/models.py) schemas (produced by Phase 3 AI understanding) into validated, sequential action execution pipelines.

> ⚠️ **Important Architecture Notice**:
> **Phase 4.2 does not execute browser automation.**
> Phase 4.2 establishes the engine architecture, action mapping, safety approval gate, and abstract execution interface using a deterministic `NoOpExecutor`. Browser interaction via Playwright is strictly introduced in Phase 4.3.

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
    │ Phase 4.2 Default:        │ Phase 4.3 Target:        │
    │ NoOpExecutor              │ PlaywrightExecutor       │
    │ (Validation & Simulation) │ (Live Browser Control)   │
    └───────────────────────────┴──────────────────────────┘
```

---

## Core Components

### 1. `AutomationEngine` ([`automation/engine.py`](file:///Users/vishalkumar/Library/CloudStorage/GoogleDrive-rohitmpk200416@gmail.com/My%20Drive/workflowOS/automation/engine.py))
Responsible for:
1. Receiving a validated [`WorkflowProposal`](file:///Users/vishalkumar/Library/CloudStorage/GoogleDrive-rohitmpk200416@gmail.com/My%20Drive/workflowOS/ai/models.py#L38-L115).
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
| `download_attachment` | `demo_email` | `/demo/email` | Downloads `customer_request.pdf` |
| `search_customer` | `demo_crm` | `/demo/crm` | Searches for customer record (e.g. Rahul) |
| `update_customer` | `demo_crm` | `/demo/crm` | Updates customer profile fields |
| `send_message` | `demo_messaging` | `/demo/chat` | Posts notification to `#customer-support` |

If an unknown action verb is encountered (e.g., `hack_mainframe`), an `UnsupportedActionError` is raised and execution is refused without running any steps.

### 3. Approval Safety Gate
- Execution is strictly conditioned on explicit operator approval (`approved=True`).
- If `approved=False`, status remains `AutomationStatus.PENDING`, `completed_actions` is empty, and zero actions are executed.
- Approval cannot be automatically inferred or bypassed.

### 4. `ActionExecutor` Abstraction ([`automation/executor.py`](file:///Users/vishalkumar/Library/CloudStorage/GoogleDrive-rohitmpk200416@gmail.com/My%20Drive/workflowOS/automation/executor.py))
Defines an asynchronous interface:
```python
class ActionExecutor(ABC):
    @abstractmethod
    async def execute(self, action: AutomationAction, context: Optional[Dict[str, Any]] = None) -> ExecutionActionResult:
        pass
```

- **`NoOpExecutor` (Active in Phase 4.2)**:
  - Validates action structure and confirms step execution flow.
  - Returns deterministic success responses with zero side effects.
  - Does **not** launch a browser or import Playwright.
  - Supports configurable `fail_actions` for testing error recovery.

- **`PlaywrightExecutor` (Target for Phase 4.3)**:
  - Will implement `ActionExecutor`.
  - Connects to the controlled demo applications (`/demo/email`, `/demo/crm`, `/demo/chat`).
  - Interacts with stable `data-testid` selectors established in Phase 4.1.

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

Phase 4.2 includes unit and engine integration tests:
```bash
python backend/test_phase4_2.py
```

Tests verify:
1. `WorkflowProposal` → `AutomationAction` conversion.
2. Strict action ordering preservation.
3. Approval safety gate blocks unapproved runs.
4. Approved runs complete via `NoOpExecutor`.
5. All 5 canonical actions are accepted.
6. Unknown actions are rejected with `UnsupportedActionError`.
7. Step failure halts subsequent actions immediately.
8. Accurate tracking of `completed_actions` and `total_actions`.
9. Zero Playwright/browser launches or imports.
