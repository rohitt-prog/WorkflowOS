# WorkFlowOS — System Architecture

**WorkFlowOS** is an AI-powered desktop workflow automation system designed to observe user activity, discover repetitive cross-application patterns, synthesize structured workflow proposals, enforce human-in-the-loop safety boundaries, plan robust automation strategies, execute approved workflows, and adaptively learn from execution outcomes.

---

## 1. High-Level Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        macOS Desktop Environment                       │
│    Applications (Browser, Mail, CRM, Chat, Terminal, Document Editors) │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Accessibility / NSWorkspace Events
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  Desktop Activity Agent (agent/)                       │
│      NSWorkspace Observer → Normalizer → Privacy Filter → Client       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ POST /api/events
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     FastAPI Ingestion & Privacy Gate                   │
│      Auth & Validation → Sensitive Data Redactor → Retention Control   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Structured Events
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        MongoDB Atlas Storage                           │
│      Collections: events, sessions, workflows, executions, feedback    │
└───────────────────┬───────────────────────────────┬────────────────────┘
                    │ Read Sessions                 │ Read Historical Logs
                    ▼                               ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│     Workflow Discovery Engine        │  │   Adaptive Learning Engine   │
│  - Multi-session local alignment     │  │   (backend/learning/)        │
│  - Repetition detection (Phase 2/8)  │  │   - Phase 9 scoring formula  │
│  - Confidence scoring & ranking      │  │   - State transitions        │
│  - Deterministic explainability      │  │   - Closed-loop telemetry    │
└───────────────────┬──────────────────┘  └──────────────┬───────────────┘
                    │ Workflow Candidates                │ Prior Evidence
                    ▼                                    │
┌──────────────────────────────────────┐                 │
│      AI Understanding & Proposals    │                 │
│  - Gemini SDK / Structured Schema    │                 │
│  - Intent & parameter extraction     │                 │
└───────────────────┬──────────────────┘                 │
                    │ Proposed Workflow                  │
                    ▼                                    │
┌────────────────────────────────────────────────────────┴───────────────┐
│                    Human Approval & Review Boundary                    │
│   MANDATORY GATE: Requires explicit human confirmation for execution   │
│   Mutating actions strictly flagged; unapproved runs rejected          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Approved Workflow
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│              Intelligent Automation Planner (Phase 10)                 │
│   Strategy Priority: API → INTEGRATION → SEMANTIC_UI → BROWSER → MANUAL│
│   Capability & credential inspection → Fallback chain generation       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Automation Plan
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│              Declarative Automation Engine (Phase 4/6/7)               │
│   Step validation → Parameter interpolation → Retry & conditions       │
│   Dispatches to: Playwright | Integration Adapters | NoOp / Mock       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Execution Stream & Results
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│              Closed-Loop Outcome Evaluator (Phase 11)                  │
│   Statuses: SUCCESS | FAILED | PARTIAL | PAUSED | CANCELLED            │
│   11-category failure taxonomy classification → Strategy Evidence      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Feedback Signals (A, R, E, X, C, I)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     Adaptive Feedback Loop (Phase 9)                   │
│   Re-weights candidate strategy scores and recommendation statuses     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Responsibilities

### 2.1 Desktop Activity Agent (`agent/`)
- **Role**: Lightweight, non-intrusive daemon observing desktop application focus, window transitions, and structured user actions on macOS.
- **Technology**: Uses `NSWorkspace` notifications and Accessibility APIs via `pyobjc`.
- **Privacy Guarantee**: Operates strictly on structured application metadata (app names, window titles, interaction targets). **Does NOT capture screenshots, does NOT log raw keystrokes, and does NOT perform video recording.**
- **Resilience**: Features exponential backoff buffering if the backend API is temporarily unreachable.

### 2.2 Event Ingestion & Privacy Gate (`backend/routes/events.py`, `backend/privacy/`)
- **Role**: Entry point for desktop activity events.
- **Enforcement**:
  - Validates event schema using Pydantic models.
  - Passes event data through the recursive sensitive data redaction engine (`redact_sensitive_data`).
  - Enforces the collection toggle (`is_collection_enabled()`); drops incoming activity if collection is disabled.
  - Enforces retention boundaries (`EVENT_RETENTION_DAYS`) with automated cutoff pruning.

### 2.3 Workflow Discovery Engine (`discovery/`)
- **Role**: Automatically detects recurring operational patterns across user sessions without supervision.
- **Architecture**:
  - `RepetitionDetector`: Extracts candidate sequences via session LCS (Longest Common Subsequences) and contiguous $n$-grams.
  - `local_sequence_alignment`: Identifies pattern matches embedded in noisy user sessions with intermediate clicks or omitted optional steps.
  - `calculate_pattern_confidence`: Evaluates frequency, structural consistency, and action entropy into a calibrated score in $[0.0, 1.0]$.
  - `calculate_ranking_score`: Evaluates automation utility using length, occurrence volume, distinct session support, and noise penalties.
  - `build_workflow_explanation`: Produces deterministic, inspectable evidence for every discovered workflow.

### 2.4 AI Workflow Understanding (`ai/`)
- **Role**: Translates raw event sequences into human-understandable declarative workflow proposals.
- **Technology**: Google Gemini API via official SDK (`google-genai`).
- **Output**: `WorkflowProposal` defining descriptive title, inferred operational intent, trigger conditions, ordered steps, dynamic variables, and application dependencies.
- **Safety**: Generates structural schemas only; proposals always initialize with `requires_approval=True`.

### 2.5 Human Approval Boundary (`automation/engine.py`, `integrations/registry.py`)
- **Role**: The zero-trust gate separating passive observation from active system automation.
- **Invariants**:
  - No workflow can execute without explicit user approval.
  - Attempting to run an unapproved workflow immediately halts execution in `PENDING` status with 0 actions run.
  - State-mutating capabilities (`update_customer`, `send_message`) strictly require approval.
  - Unknown or unregistered actions fail closed (`requires_approval = True`, `is_action_read_only = False`).

### 2.6 Automation Planner (`automation/planner/`)
- **Role**: Deterministically selects the safest and most reliable automation strategy for each workflow step.
- **Strategy Hierarchy**:
  $$\text{API} \longrightarrow \text{INTEGRATION} \longrightarrow \text{SEMANTIC\_UI} \longrightarrow \text{BROWSER} \longrightarrow \text{MANUAL}$$
- **Inspection**: Evaluates whether actions have native APIs, whether OAuth credentials are valid, whether registered integration adapters exist, or whether browser automation via Playwright is required.
- **Fallbacks**: Plans secondary fallback strategies (e.g., fallback to browser or manual prompt if API tokens expire).

### 2.7 Declarative Workflow Engine (`automation/engine.py`, `automation/service.py`)
- **Role**: Coordinates step-by-step execution of approved declarative workflows.
- **Capabilities**:
  - Dynamic input validation and variable interpolation (`{{inputs.var}}`, `{{data.field}}`).
  - Conditional branching evaluation (`equals`, `contains`, `greater_than`).
  - Retry policies with exponential backoff.
  - State machine enforcement (`PENDING` $\to$ `RUNNING` $\to$ `COMPLETED` / `PAUSED` / `FAILED` / `CANCELLED`).
  - Human-in-the-loop pause and resume from failed steps without restarting completed actions.
  - Cryptographic definition hash verification (`compute_workflow_definition_hash`) to prevent tampering after approval.

### 2.8 Integration Ecosystem & Adapters (`integrations/`)
- **Role**: Manages communication with external SaaS applications and local demo services.
- **Adapters**:
  - `GmailIntegrationAdapter`: Read-only message listing and snippet retrieval via Google OAuth 2.0 with Fernet-encrypted token storage.
  - `CrmIntegrationAdapter`: Customer profile searches and account tier updates with safe mock backends.
  - `ChatIntegrationAdapter`: Internal team channel notifications.
  - `MockTestIntegrationAdapter`: Isolated testing harness for verifying action dispatch and error handling.
- **Registry**: Centralized `ApplicationRegistry` enforcing capability declaration, health checks, and safety classifications.

### 2.9 Closed-Loop Outcome Evaluation (`backend/learning/outcome.py`)
- **Role**: Analyzes workflow execution logs to produce structured post-mortem outcome records.
- **Taxonomy**: Deterministically classifies failure causes into 11 bounded categories: `TIMEOUT`, `AUTHENTICATION`, `AUTHORIZATION`, `NETWORK`, `VALIDATION`, `TARGET_NOT_FOUND`, `UNSUPPORTED_ACTION`, `RATE_LIMIT`, `INTEGRATION_ERROR`, `BROWSER_ERROR`, and `UNKNOWN`.
- **Strategy Evidence**: Tracks success rates, consecutive failures, and fallback occurrences per strategy and step.

### 2.10 Adaptive Learning Engine (`backend/learning/`)
- **Role**: Implements reinforcement-style preference learning based on human feedback and execution outcomes.
- **Mathematical Formula**:
  $$L = \text{clamp}(0.50 + 0.10 A + 0.08 E_{edit} + 0.15 X_{succ} + 0.05 C_{rec} - 0.20 R - 0.15 X_{fail} - 0.05 I, 0, 1)$$
- **Recommendation States**: Transitions workflow recommendation tiers between `NEW`, `LEARNING`, `RECOMMENDED`, and `DEPRIORITIZED`.

### 2.11 Evaluation & Benchmarking System (`evaluation/`)
- **Role**: Provides deterministic regression benchmarks across discovery, planning, execution, learning, safety, and performance on synthetic datasets.

### 2.12 Product UI (`frontend/`)
- **Role**: Modern, responsive web console built with Next.js 16, React 19, and Tailwind CSS.
- **Key Views**:
  - `DashboardView`: System status, KPI cards, agent connectivity, recent workflows.
  - `ActivityView`: Real-time structured desktop event stream with app filtering.
  - `WorkflowsView`: Discovered pattern inspection, approval modal, and learning indicators.
  - `BuilderView`: Visual declarative workflow editor with step addition and trigger configuration.
  - `ApplicationsView`: Connected applications, health monitoring, and declared capabilities.
  - `ExecutionsView`: Historical execution runs, live progress inspector, and step results.
  - `SettingsView`: Privacy collection toggle, retention slider, and security posture summary.

---

## 3. End-to-End Data Flow

```text
User Actions on macOS
       │
       ▼ [1] NSWorkspace / Accessibility
Desktop Agent (agent/)
       │
       ▼ [2] JSON Event Payload { app, window, action, timestamp }
Backend API Route (/api/events)
       │
       ▼ [3] Privacy Gate (Redact PII & check collection toggle)
MongoDB Atlas (events collection)
       │
       ▼ [4] Query multi-session sequences
RepetitionDetector (discovery/)
       │
       ▼ [5] Local Alignment & Ranking
Discovered Workflow Candidate
       │
       ▼ [6] Structural Synthesis (Gemini / Schema)
Workflow Proposal (with requires_approval=True)
       │
       ▼ [7] Operator Reviews & Approves in Frontend UI
AutomationPlanner (automation/planner/)
       │
       ▼ [8] Select Strategy (API / Browser / Integration) + Fallbacks
AutomationEngine (automation/engine/)
       │
       ▼ [9] Sequential Dispatch to Adapters (Playwright / REST)
Execution Output (AutomationExecution record)
       │
       ▼ [10] Closed-Loop Evaluator (outcome.py)
Outcome Record + Strategy Evidence
       │
       ▼ [11] Adaptive Learning Score Update (state.py)
Updated Recommendation Status (NEW / LEARNING / RECOMMENDED / DEPRIORITIZED)
```

---

## 4. Safety & Security Architecture

| Security Domain | Implementation | Guarantee |
| :--- | :--- | :--- |
| **Observation Privacy** | Event-level observation only; NO screenshots, NO video, NO keylogging | User privacy preserved; credentials not captured |
| **Data Ingestion Gate** | Recursive heuristic redactor (`redact_sensitive_data`) | Tokens, passwords, cards, and keys scrubbed to `[REDACTED]` |
| **Collection Control** | Global `ACTIVITY_COLLECTION_ENABLED` switch in `PrivacyService` | Collection can be paused instantly; fails closed |
| **Data Retention** | Configurable `EVENT_RETENTION_DAYS` policy | Stale events pruned automatically via ISO timestamp cutoffs |
| **Human Approval** | Mandatory gate in `AutomationEngine` and declarative executor | Zero execution without human confirmation |
| **Mutating Action Gate** | `requires_approval=True` enforced for mutating capabilities | Accidental side-effects blocked |
| **Unknown Capabilities** | `is_action_read_only = False`, `requires_approval = True` | Unknown actions fail closed; cannot bypass approval |
| **Unknown Applications** | Registry lookup returns `None`; dispatch rejected | Unregistered applications cannot be executed |
| **Credential Encryption** | Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256) | OAuth tokens stored encrypted; decrypted in-memory only |
| **Approval Tampering** | Cryptographic definition hash (`compute_workflow_definition_hash`) | Modified workflow definitions require re-approval |
| **Origin Isolation** | Strict CORS policy rejecting wildcard `*` origins | Cross-origin credential theft blocked |
