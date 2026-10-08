# WorkFlowOS — Final Demonstration Guide

This guide details how to set up, operate, and present an end-to-end demonstration of **WorkFlowOS — AI-Powered Workflow Automation System**.

---

## 1. Demo Objective

The primary objective of demonstrating WorkFlowOS is to show a complete, robust automation lifecycle:

> **WorkFlowOS observes repetitive desktop activity, discovers repeated workflows, understands the underlying task intent using AI, presents proposals for human approval, plans safe automation strategies via an explicit strategy hierarchy, executes them deterministically, evaluates outcomes, and feeds execution receipts into an adaptive learning engine for future planning.**

---

## 2. System Requirements & Setup

### 2.1 Prerequisites
* **Python**: 3.11+
* **Node.js**: v18+ (Node 20+ recommended)
* **MongoDB**: MongoDB Atlas connection URI configured in `.env`
* **Google Gemini API**: Optional for live LLM inference (`GEMINI_API_KEY`); intelligent deterministic fallbacks run automatically if not configured.

---

### 2.2 Environment Configuration

Ensure `.env` in the repository root has the required variables (copy from `.env.example`):

```bash
cp .env.example .env
```

Ensure `MONGODB_URI` points to your MongoDB Atlas cluster. All privacy toggles default safely to:
```env
ACTIVITY_COLLECTION_ENABLED=true
EVENT_RETENTION_DAYS=30
```

---

### 2.3 Starting the Backend

From the repository root:

```bash
source .venv/bin/activate
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Verify backend health at `http://127.0.0.1:8000/api/health` or `http://127.0.0.1:8000/health`.

---

### 2.4 Starting the Frontend

In a separate terminal:

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000` in your web browser.

---

### 2.5 Starting the Desktop Activity Agent (Optional / Interactive)

To capture live active window events on macOS:

```bash
source .venv/bin/activate
python -m agent run --interval 1.0
```

*Note: For deterministic demonstration without waiting for real desktop actions, use the built-in synthetic event generation in the Product UI or Phase 15 benchmark harness.*

---

## 3. End-to-End Demonstration Sequence (12 Steps)

Follow this structured, 12-step presentation flow to showcase the full engineering breadth of WorkFlowOS.

```text
Dashboard ──► Activity ──► Discovery ──► AI Understanding ──► Approval ──► Planning
                                                                               │
Learning ◄── Outcome ◄── Execution ◄── Strategy Selection ◄────────────────────┘
   │
   ├──► Privacy Controls
   ├──► Application Ecosystem
   └──► Verified Phase 15 Evaluation
```

---

### Step 1 — Product Dashboard
* **Route**: `/` (or `/dashboard`)
* **What to Show**:
  * Clean, portfolio-grade interface showing system health, active agent status, recent activity volume, discovered workflows, and registered application integrations.
  * System overview cards displaying execution metrics and privacy enforcement posture.
* **Talking Point**:
  > *"WorkFlowOS is designed as a complete operating system for desktop workflow automation. Rather than requiring users to manually author automation scripts or build brittle RPA macros, it continuously surfaces candidate workflows for user review."*

---

### Step 2 — Desktop Activity Observation
* **Route**: `/activity` (or interactive demo at `/demo`)
* **What to Show**:
  * Stream of ingested desktop events: application focus, title metadata, timestamps, and session tags.
  * Sanitized metadata showing zero raw keystrokes, zero screenshots, and zero OCR images.
* **Talking Point**:
  > *"WorkFlowOS enforces a strict privacy-first model. The desktop agent emits structured metadata events (e.g. active application, window title with sensitive token redaction, timestamps) rather than capturing invasive video feeds, screenshots, or keylogger buffers."*

---

### Step 3 — Workflow Discovery Engine
* **Route**: `/workflows` (or `/discovery`)
* **What to Show**:
  * Discovered workflow candidate cards with repetition counts, confidence scores, and identified step sequences.
  * Filter by confidence threshold, frequency, and application groupings.
* **Talking Point**:
  > *"The discovery engine scans normalized event sequences using sliding-window pattern mining and temporal n-gram analysis. When repeated sequences exceed user-configured support and confidence thresholds, they are surfaced as workflow candidates."*

---

### Step 4 — AI Workflow Understanding
* **Route**: `/workflows/[id]`
* **What to Show**:
  * Structured declarative workflow generated from raw events: Step 1 (Extract customer contact from mock CRM), Step 2 (Search and read customer messages via read-only Gmail integration), Step 3 (Post notification to mock Chat).
  * Parameterization: variables extracted dynamically from event metadata rather than hard-coded strings.
* **Talking Point**:
  > *"Raw application switches don't explain intent. WorkFlowOS routes candidate sequences through an AI understanding pipeline (Google Gemini with deterministic AST fallbacks) that classifies intent, identifies source and destination applications, parameterizes variables, and outputs a declarative workflow definition."*

---

### Step 5 — Human Approval & Safety Boundary
* **Route**: Workflow Detail / Approval Modal
* **What to Show**:
  * Clear classification of read-only vs. mutating steps.
  * Approval requirement badge: mutating actions (`send_email`, `update_record`, `post_message`) require explicit user confirmation.
* **Talking Point**:
  > *"WorkFlowOS rejects silent autonomous execution of mutating actions. Any workflow containing state-altering operations requires explicit human approval before execution can proceed. Read-only discovery is autonomous; action execution is human-gated."*

---

### Step 6 — Automation Strategy Planning
* **Route**: Automation Planner Inspector / Execution Plan View
* **What to Show**:
  * The planner's strategy selection for each step based on the strict hierarchy:
    ```text
    API (Fastest, Highest Reliability)
      ↓
    Integration Adapter (App Registry)
      ↓
    Semantic UI (Accessibility Tree)
      ↓
    Browser Automation (Playwright DOM)
      ↓
    Manual Step (Human Intervention Required)
    ```
  * Capability check: why an API or integration adapter was chosen over UI automation.
* **Talking Point**:
  > *"Traditional RPA defaults directly to fragile coordinate clicks. WorkFlowOS uses an intelligent automation planner that evaluates available connectors, prior reliability scores, and prerequisite tokens to select the most reliable execution path available."*

---

### Step 7 — Deterministic Execution Engine
* **Route**: `/executions` (or Execution Detail View)
* **What to Show**:
  * Live or completed execution trace showing step-by-step progress, parameter interpolation, retry attempts, and duration timestamps.
* **Talking Point**:
  > *"Once approved, workflows are passed to the Declarative Workflow Engine. Steps are executed with timeout management, exponential backoff retries, and comprehensive error containment so failures don't crash the orchestrator."*

---

### Step 8 — Outcome Evaluation
* **Route**: Execution Result Cards
* **What to Show**:
  * Outcome states: `COMPLETED`, `FAILED`, `CANCELLED`, `PAUSED`, `PARTIAL_SUCCESS`.
  * Step receipts: verification that the expected output matches the actual output returned by the integration adapter.
* **Talking Point**:
  > *"Execution does not end with fire-and-forget. The outcome evaluator assesses every step's execution receipts against expected post-conditions to verify real-world success or diagnose failure modes."*

---

### Step 9 — Adaptive Learning & Feedback Loop
* **Route**: `/learning`
* **What to Show**:
  * Learning evidence records: historical success rates, latency tracking, failure patterns, and strategy confidence adjustments.
  * How a successful execution increases an adapter's confidence rating, while repeated failures trigger automatic fallback to alternative strategies in future runs.
* **Talking Point**:
  > *"WorkFlowOS implements a closed feedback loop. Execution outcomes and human feedback update an empirical evidence ledger, dynamically adjusting strategy weights for future automation planning without requiring model retraining."*

---

### Step 10 — Privacy & Safety Controls
* **Route**: `/settings` (Privacy Tab)
* **What to Show**:
  * Master collection switch: `ACTIVITY_COLLECTION_ENABLED` (fails closed when toggled off).
  * Automated PII, credential, and auth token scrubbing.
  * Application allowlist/denylist controls.
* **Talking Point**:
  > *"Privacy is not an afterthought in WorkFlowOS. The system features centralized fail-closed switches, regex-based sanitization for emails, credit cards, and API keys, and automatic denylisting of password managers and banking apps."*

---

### Step 11 — Application Ecosystem
* **Route**: `/applications`
* **What to Show**:
  * Registered adapters: Google Workspace (Gmail — read-only OAuth integration), CRM System (mock/local integration), Communication (mock/local Chat integration).
  * Capability inspection: read-only vs. mutating operations clearly delineated.
  * Fail-closed behavior: attempts to call unregistered applications or unknown actions are rejected immediately.
* **Talking Point**:
  > *"The integration registry provides a secure, decoupled contract for third-party tools. Unregistered actions fail closed by default, preventing unauthorized script execution or privilege escalation."*

---

### Step 12 — Evaluation & Benchmark Results
* **Route**: Terminal / `docs/PHASE_15_REPORT.md`
* **What to Show**:
  * Run Phase 15 evaluation suite:
    ```bash
    .venv/bin/python -m unittest discover -s backend -p "test_phase15*.py"
    ```
  * Point to verified metrics:
    * **Discovery Precision**: 100%
    * **Discovery Recall**: 100%
    * **Discovery F1 Score**: 100%
    * **Strategy Selection Accuracy**: 100%
    * **Closed-Loop Taxonomy Accuracy**: 100%
    * **Safety Compliance Rate**: 100% (Zero unauthorized mutating bypasses across all benchmark scenarios)
* **Talking Point**:
  > *"WorkFlowOS was formally benchmarked across 10 synthetic scenarios (Scenarios A through J in `docs/PHASE_15_REPORT.md`) in Phase 15, measuring end-to-end performance across discovery accuracy, planning reliability, safety compliance, and closed-loop adaptability. Note that these metrics validate structural correctness and safety boundaries deterministically on synthetic matrices rather than noisy live enterprise traces."*

---

## 4. Troubleshooting During Demos

| Issue | Cause | Resolution |
| :--- | :--- | :--- |
| **Backend fails on start** | Port 8000 in use or MongoDB Atlas unreachable | Ensure `.env` has valid `MONGODB_URI`. Check `lsof -i :8000`. |
| **Frontend shows API error** | Backend not running on port 8000 | Verify FastAPI server is running at `http://127.0.0.1:8000`. |
| **Gemini API Key missing** | No `GEMINI_API_KEY` set | System automatically uses robust deterministic heuristic fallbacks; no crash occurs. |
| **Agent permissions on macOS** | Accessibility permissions disabled | Run `.venv/bin/python -m agent check-permissions` to verify OS permissions. |
