# WorkFlowOS

**WorkFlowOS** is a serious, long-term portfolio project: a privacy-conscious macOS desktop activity agent that observes user workflows, discovers patterns, and automates them with AI-assisted proposal generation and human-in-the-loop control.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│  macOS Desktop (Phase 5)                              │
│  agent/ — NSWorkspace poller → normaliser → client   │
└──────────────────────┬───────────────────────────────┘
                       │ POST /api/events
┌──────────────────────▼───────────────────────────────┐
│  FastAPI Backend (Python)                             │
│  ├── routes/events.py     (Phase 1 ingestion)        │
│  ├── routes/discovery.py  (Phase 2 pattern scan)     │
│  ├── routes/ai.py         (Phase 3 Gemini proposal)  │
│  └── routes/automation.py (Phase 4–6 execution)      │
│                                                       │
│  automation/                                          │
│  ├── models.py   — Pydantic: execution + Phase 6     │
│  ├── engine.py   — Declarative executor + conditions │
│  └── service.py  — Registry, run, resume, cancel     │
│                                                       │
│  MongoDB Atlas  — events + sessions                  │
└──────────────────────┬───────────────────────────────┘
                       │ REST
┌──────────────────────▼───────────────────────────────┐
│  Next.js 16 Frontend (React 19 + TailwindCSS v4)     │
│  src/components/                                      │
│  ├── Sidebar.tsx           sidebar nav               │
│  ├── Header.tsx            breadcrumb + controls     │
│  └── views/                                          │
│      ├── DashboardView     KPIs + recent feeds       │
│      ├── ActivityView      live event table          │
│      ├── DiscoveryView     pattern cards + AI modal  │
│      ├── BuilderView       declarative WF editor     │
│      ├── ExecutionsView    history + detail modal    │
│      └── SettingsView      config + phase status     │
└──────────────────────────────────────────────────────┘
```

---

## Phase Status

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Observational Event Ingestion (MongoDB Atlas) | ✅ Complete |
| **Phase 2** | Workflow Discovery — repeated pattern detection | ✅ Complete |
| **Phase 3** | AI Workflow Understanding (Gemini SDK) | ✅ Complete |
| **Phase 4.1** | Demo Applications (Mail, CRM, Chat) | ✅ Complete |
| **Phase 4.2–4.3** | Automation Engine + PlaywrightExecutor | ✅ Complete |
| **Phase 4.4–4.6** | Execution tracking, history, human-in-the-loop | ✅ Complete |
| **Phase 5** | Real macOS Desktop Activity Agent | ✅ Complete |
| **Phase 6** | Production Workflow Engine + Frontend Redesign | ✅ Complete |

---

## Quick Start

### 1. Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and fill secrets
cp .env.example .env
# → Set MONGODB_URI, GEMINI_API_KEY, SESSION_SECRET

# Start backend (from repo root)
uvicorn backend.app:app --reload --port 8000
```

### 2. Desktop Agent (Phase 5)

```bash
# Start the macOS activity capture agent
python -m agent run

# Check status
python -m agent status
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev        # dev server at http://localhost:3000
npm run build      # production build
```

### 4. Seed test data

```bash
# Send all sample events
python backend/test_event.py --all

# Seed workflow discovery patterns
python backend/test_event.py --seed-workflows
```

---

## Phase 6 — Generalized Workflow Engine

### Declarative Workflow Schema

```python
WorkflowDefinition(
    id="my_workflow",
    name="Customer Support Pipeline",
    description="End-to-end support case handling",
    trigger=WorkflowTriggerConfig(type="manual"),
    inputs=[WorkflowInputDefinition(name="customer_name", type="string", required=True)],
    steps=[
        WorkflowStep(
            id="check_email",
            name="Open support email",
            type="open_email",
            application="demo_email",
            retry=RetryPolicy(max_attempts=3, delay_seconds=1),
        ),
        WorkflowStep(
            id="lookup_crm",
            name="Search customer in CRM",
            type="search_customer",
            application="demo_crm",
            parameters={"customer": "{{inputs.customer_name}}"},
            output_mapping={"customer_id": "data.customer_id"},
            condition=StepCondition(
                variable="steps.check_email.output.status",
                operator="==",
                value="success",
            ),
        ),
    ],
    requires_approval=True,
)
```

### Variable Interpolation

Templates use `{{...}}` syntax resolved at runtime:

| Syntax | Resolves to |
|--------|------------|
| `{{inputs.customer_name}}` | Input parameter value |
| `{{variables.temp_val}}` | Named workflow variable |
| `{{steps.step_id.output.field}}` | Output from a prior step |

### Condition Operators

`==`, `!=`, `>`, `<`, `>=`, `<=`, `contains`, `in`, `is_empty`, `is_not_empty`, `exists`

### Execution State Machine

```
pending → running → completed
                 ↘ paused  ← human review → resumed → completed
                 ↘ failed  (terminal if not pause_on_failure)
                 ↘ cancelled (terminal)
```

---

## Phase 6 REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/automation/workflows` | List registered workflow templates |
| `POST` | `/api/automation/workflows` | Register a new workflow definition |
| `GET`  | `/api/automation/workflows/{id}` | Get a specific workflow template |
| `POST` | `/api/automation/execute` | Execute a workflow (legacy or declarative) |
| `GET`  | `/api/automation/executions` | List all execution records |
| `GET`  | `/api/automation/executions/{id}` | Get full execution detail |
| `POST` | `/api/automation/executions/{id}/resume` | Resume a paused execution |
| `POST` | `/api/automation/executions/{id}/cancel` | Cancel a paused/running execution |

### Execute Declarative Workflow

```bash
curl -X POST http://localhost:8000/api/automation/execute \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_definition": {
      "name": "My Workflow",
      "steps": [
        {"id": "s1", "name": "Open email", "type": "open_email", "application": "demo_email"}
      ]
    },
    "approved": true,
    "inputs": {"customer_name": "Rahul"},
    "executor_type": "playwright"
  }'
```

---

## Running Tests

```bash
# All phase tests
.venv/bin/python3 -m unittest discover -s backend -p "test_phase*.py" -v

# Phase 6 only
.venv/bin/python3 -m unittest backend.test_phase6 -v

# Phase 5 (agent) tests
.venv/bin/python3 -m unittest backend.test_phase5 -v
```

**Test Results (Phase 6):** 122 tests · 120 passed · 2 skipped (require live MongoDB) · 0 failures in engine/executor/API tests.

---

## Privacy

The Phase 5 desktop agent uses **macOS NSWorkspace APIs only** for application focus tracking:
- ✅ Application name + bundle ID when you switch apps
- ❌ No keystrokes, clipboard, file contents, or screen capture
- ❌ No network calls outside your own backend (`localhost:8000` by default)
- ❌ No data sent to external services (Gemini calls are made server-side from the backend)

The agent respects an allowlist/denylist in `agent/config.py` and can be stopped at any time with `python -m agent stop`.
