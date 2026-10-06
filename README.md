# WorkFlowOS — AI-Powered Workflow Automation System

WorkFlowOS is an extensible, privacy-first desktop workflow automation system designed to observe user activity, autonomously discover repetitive task patterns, synthesize declarative automation workflows using AI, and execute them through an approval-gated, multi-strategy planning engine with closed-loop adaptive learning.

Unlike traditional Robotic Process Automation (RPA) tools that require manual macro scripting and break upon minor UI changes, WorkFlowOS operates as an intelligent workflow discovery operating system. It observes routine desktop interactions non-invasively, identifies recurring cross-application sequences, converts them into structured declarative workflows, and validates all mutating operations through strict human approval.

The system is engineered with an emphasis on production-grade reliability: it features a 5-tier hierarchical automation planner (`API` → `Integration` → `Semantic UI` → `Browser` → `Manual`), comprehensive PII and credential redaction, fail-closed safety boundaries, and a Bayesian learning feedback loop that dynamically adjusts execution confidence based on runtime receipts.

---

## The Problem

Knowledge workers spend substantial portions of their workdays executing repetitive, multi-step procedures across disparate desktop and web applications: copying customer details from CRM software, composing repetitive confirmation emails, updating spreadsheets, and pinging team chat channels.

While workers intuitively understand their day-to-day tasks, traditional automation solutions present critical barriers:
1. **High Authoring Friction**: Traditional RPA tools require users to manually record brittle coordinate clicks, configure XPath selectors, or write custom glue scripts.
2. **Brittle Execution**: Coordinate and selector-based automations break when window sizes change, applications update, or network latency causes timing mismatches.
3. **Severe Privacy Concerns**: Many experimental "desktop AI agents" capture continuous desktop video streams, run keystroke loggers, or send raw desktop screenshots to cloud LLMs, leaking sensitive corporate data and credentials.
4. **Lack of Outcome Feedback**: Most automations operate in an open-loop model with zero self-assessment, repeatedly failing on the same error without adapting.

---

## The Solution

WorkFlowOS solves this problem through an end-to-end, privacy-conscious closed-loop pipeline:

```text
Observe
   ↓
Understand
   ↓
Detect Repetition
   ↓
Generate Workflow
   ↓
User Approval
   ↓
Plan Automation
   ↓
Execute
   ↓
Evaluate Outcome
   ↓
Learn
```

1. **Observe**: Non-invasive desktop agent observes window switches, application focus changes, and semantic metadata without screenshots or keylogging.
2. **Understand**: Sanitizes and normalizes event streams into structured event logs with automatic PII and credential scrubbing.
3. **Detect Repetition**: Pattern discovery engine identifies recurring multi-step sequences across distinct sessions using sliding-window n-gram mining and local sequence alignment.
4. **Generate Workflow**: AI synthesizer (powered by Google Gemini with deterministic heuristic fallbacks) maps raw UI events into declarative workflow graphs with parameterized inputs and semantic descriptions.
5. **User Approval**: Mandatory human approval gate halts all mutating operations (`send_email`, `update_record`, `post_message`), guaranteeing that no state-altering actions execute autonomously.
6. **Plan Automation**: Multi-strategy planner evaluates available system capabilities, application adapters, and historical reliability to select the safest execution path.
7. **Execute**: Declarative workflow engine executes approved steps with timeout enforcement, exponential retry backoff, and failure containment.
8. **Evaluate Outcome**: Outcome evaluation engine compares runtime execution receipts against post-conditions, classifying errors using an 11-category failure taxonomy.
9. **Learn**: Closed-loop adaptive learning engine updates empirical strategy weights, reinforcing reliable connectors and routing future plans around flaky paths.

---

## System Architecture

```text
┌────────────────────────────────────────────────────────┐
│               Desktop Activity Agent                   │
│   (macOS NSWorkspace Poller → Normalizer → Privacy)    │
└───────────────────────────┬────────────────────────────┘
                            │ POST /api/events/batch
┌───────────────────────────▼────────────────────────────┐
│                  Privacy & Safety Gate                 │
│    (PII / Secret Redaction • Collection Kill-Switch)   │
└───────────────────────────┬────────────────────────────┘
                            │ Clean Normalized Events
┌───────────────────────────▼────────────────────────────┐
│                    MongoDB Atlas                       │
│    (Events • Workflows • Executions • Learning State)  │
└───────────────────────────┬────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
┌──────────────────────────┐  ┌──────────────────────────┐
│ Workflow Discovery Engine│  │   AI Workflow Synthesizer│
│ - Sliding-Window Mining  │  │   - Intent Classification│
│ - DP Local Alignment     │  │   - Schema Synthesis     │
│ - Pattern Deduplication  │  │   - Parameter Extraction │
└─────────────┬────────────┘  └───────────┬──────────────┘
              │                           │
              └─────────────┬─────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│             Human-in-the-Loop Approval Gate            │
│   (Mandatory Authorization for All Mutating Actions)   │
└───────────────────────────┬────────────────────────────┘
                            │ Approved Workflow
┌───────────────────────────▼────────────────────────────┐
│               Automation Strategy Planner              │
│    API ──► Integration ──► Semantic UI ──► Browser ──► │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│          Declarative Workflow Execution Engine         │
│   (Step Timeout • Retry Backoff • Failure Containment) │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│             Outcome Evaluator & Adaptive Loop          │
│    (11-Category Taxonomy • Bayesian Weight Updates)    │
└────────────────────────────────────────────────────────┘
```

*For comprehensive architecture documentation, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).*

---

## Roadmap & Phase Status

WorkFlowOS was engineered across 16 sequential, verified architectural phases:

| Phase | Milestone | Description | Status |
|:---|:---|:---|:---:|
| **Phase 1** | Foundation & Events | Core event schemas, REST ingestion, MongoDB Atlas storage | Complete |
| **Phase 2** | Workflow Discovery | Sliding-window candidate detection & repetition frequency | Complete |
| **Phase 3** | AI Understanding | Gemini-powered intent classification & workflow generation | Complete |
| **Phase 4** | Automation Engine | Playwright browser executor, demo apps, execution tracking | Complete |
| **Phase 5** | Desktop Activity Agent | macOS activity collector, focus polling, batch synchronization | Complete |
| **Phase 6** | Declarative Engine | AST step validation, variable interpolation, condition branches | Complete |
| **Phase 7** | Integrations & Reliability | Fernet-encrypted token storage, Gmail OAuth 2.0, state recovery | Complete |
| **Phase 8** | Discovery Intelligence | Calibrated confidence, DP alignment, ranking, explainability | Complete |
| **Phase 9** | Adaptive Learning | Human review feedback loops, Bayesian learning score formula | Complete |
| **Phase 10** | Intelligent Automation | Multi-strategy planning hierarchy, failure-aware fallback | Complete |
| **Phase 11** | Closed-Loop Intelligence | 11-category failure taxonomy, strategy outcome feedback | Complete |
| **Phase 12** | Privacy & Safety | Authoritative kill-switch, Luhn credit card & token redaction | Complete |
| **Phase 13** | Application Ecosystem | Capability registry, read-only vs mutating, fail-closed actions | Complete |
| **Phase 14** | Productization | Unified Next.js product dashboard, onboarding & telemetry | Complete |
| **Phase 15** | Evaluation & Benchmarking | 24-scenario benchmark harness, deterministic evaluation | Complete |
| **Phase 16** | Final Product Release | Production documentation, full regression, portfolio release | Complete |

---

## Feature Matrix

| Capability | Status | Implementation Details |
|:---|:---:|:---|
| **Event Ingestion & Normalization** | Implemented | High-throughput FastAPI endpoints (`/api/events`), batch ingestion, UUID deduplication |
| **MongoDB Atlas Persistence** | Implemented | Schema-fluid document storage for events, workflows, executions, and learning state |
| **Workflow Pattern Discovery** | Implemented | Sliding-window n-gram mining, dynamic local sequence alignment, noise suppression |
| **AI Workflow Synthesis** | Implemented | Google Gemini prompt engineering with deterministic rule-based heuristic fallbacks |
| **Human Approval Boundary** | Implemented | Cryptographically bound approval gate; mutating actions cannot execute autonomously |
| **Hierarchical Strategy Planner** | Implemented | Strict 5-tier fallback planner (`API` → `Integration` → `Semantic UI` → `Browser` → `Manual`) |
| **Declarative Execution Engine** | Implemented | Step execution with timeout control, exponential retry backoff, and variable interpolation |
| **Desktop Activity Agent** | Implemented | Non-invasive macOS agent capturing active window focus and metadata at 1.0s intervals |
| **Application Ecosystem** | Implemented | Decoupled adapter contracts (Gmail, CRM, Chat) with explicit capability schemas |
| **Closed-Loop Adaptive Learning** | Implemented | Bayesian evidence updating ($L \in [0.0, 1.0]$) dynamically tuning strategy selection |
| **Privacy & Secret Redaction** | Implemented | Authoritative collection switch, Luhn-verified PAN scrubbing, credential pattern redaction |
| **Fail-Closed Unknown Handling** | Implemented | Unregistered actions and unknown apps fail closed; cannot be classified as read-only |
| **Product Dashboard UI** | Implemented | Next.js 16 (React 19, Tailwind CSS v4) with unified navigation, activity stream, execution logs |
| **Evaluation Framework** | Implemented | 24-scenario synthetic benchmark harness testing discovery, planning, learning, and safety |

---

## Technology Stack

### Backend
* **Python**: 3.11+
* **FastAPI**: Asynchronous REST API framework
* **Pydantic v2**: Runtime data validation and schema enforcement
* **Uvicorn**: ASGI web server
* **Cryptography (Fernet)**: AES-128-CBC + HMAC-SHA256 authenticated token encryption

### Frontend
* **Next.js**: 16.3.6 (React 19, App Router)
* **TypeScript**: 5.x for static typing
* **Tailwind CSS**: v4 for utility-first responsive styling
* **Lucide React**: Clean iconography

### Database & Storage
* **MongoDB Atlas**: Managed cloud document database for events, workflows, executions, and learning state
* **PyMongo**: Asynchronous and synchronous MongoDB drivers with compound indexing

### AI & Automation
* **Google Gemini**: Gemini 2.5 Flash API for natural language workflow synthesis and intent extraction
* **Deterministic Fallback Engine**: AST-based rule engine providing 100% offline workflow synthesis
* **Playwright**: Headless/headed browser automation for web application workflows

---

## Application Ecosystem

WorkFlowOS interacts with external applications through an explicit, decoupled integration registry (`integrations/registry.py`). Each integration publishes a strict capability manifest:

| Application | Adapter Type | Supported Operations | Capability Safety |
|:---|:---|:---|:---:|
| **Gmail** | Google Workspace OAuth 2.0 | `list_recent_messages` | Read-Only (Safe) |
| **Gmail** | Google Workspace OAuth 2.0 | `send_email` | Mutating (Approval Gated) |
| **CRM System** | Native API / Mock CRM | `search_customer`, `get_contact` | Read-Only (Safe) |
| **CRM System** | Native API / Mock CRM | `update_customer`, `create_deal` | Mutating (Approval Gated) |
| **Chat / Messaging** | Webhook / Mock Chat | `read_channel` | Read-Only (Safe) |
| **Chat / Messaging** | Webhook / Mock Chat | `post_message` | Mutating (Approval Gated) |

### Fail-Closed Security Policy
* **Unregistered Actions**: Any action not explicitly declared in an application's capability manifest is rejected immediately (`UNKNOWN_ACTION`). It is **never** classified as read-only and **cannot** execute silently.
* **Unregistered Applications**: Calls targeting unknown applications fail closed with zero side effects.
* **Mutating Operations**: Any action altering external state requires explicit human confirmation before execution can begin.

---

## Privacy & Safety Controls

WorkFlowOS enforces a strict privacy boundary:

1. **No Invasive Monitoring**: The system captures **zero screenshots**, **zero desktop video streams**, **zero keystroke buffers**, and **zero OCR images**.
2. **Authoritative Master Kill-Switch**: The `ACTIVITY_COLLECTION_ENABLED` setting acts as an authoritative privacy gate. When set to `false`, the desktop agent immediately drops all OS focus events before they enter the pipeline.
3. **Comprehensive Secret & PII Redaction**: The redaction service (`backend/privacy/redaction.py`) automatically sanitizes all event payloads, execution outputs, and log messages:
   * **Authentication Secrets**: Bearer tokens, GitHub personal tokens (`ghp_`), Google tokens (`ya29.`), OpenAI keys (`sk-`), AWS keys (`AKIA`), passwords, and private keys.
   * **Financial Data**: Credit card PANs validated via the **Luhn checksum algorithm** to eliminate false positives on order IDs.
   * **Personal Data**: Email addresses, phone numbers, and identifying session tokens.
4. **Application Denylisting**: Sensitive desktop applications (e.g. 1Password, Bitwarden, banking portals) are denylisted by default.
5. **Configurable Data Retention**: Stored events auto-expire after a configurable window (`EVENT_RETENTION_DAYS`, default: 30 days).

---

## Phase 15 Evaluation & Benchmark Results

In Phase 15, WorkFlowOS was evaluated across a standardized benchmark suite of 24 synthetic scenarios testing discovery precision, strategy planning, failure classification, and security guardrails:

| Evaluation Benchmark | Metric | Verified Result | Target Standard |
|:---|:---|:---:|:---:|
| **Workflow Discovery** | Precision | **100.0%** | $\ge 90.0\%$ |
| **Workflow Discovery** | Recall | **100.0%** | $\ge 90.0\%$ |
| **Workflow Discovery** | F1 Score | **1.0000** | $\ge 0.900$ |
| **Pattern Ranking** | Top-1 Accuracy | **87.5%** | $\ge 80.0\%$ |
| **Pattern Ranking** | Mean Reciprocal Rank (MRR) | **0.9375** | $\ge 0.850$ |
| **Explainability Engine** | Audit Coverage | **100.0%** | $100.0\%$ |
| **Automation Planning** | Strategy Selection Accuracy | **100.0%** | $\ge 95.0\%$ |
| **Outcome Evaluation** | 11-Category Taxonomy Accuracy | **100.0%** | $\ge 95.0\%$ |
| **Execution Safety** | Unauthorized Bypass Rate | **0.0%** | $0.0\%$ |
| **Safety Compliance** | Safety Compliance Rate | **100.0%** | $100.0\%$ |
| **End-to-End Pipeline** | Full Synthetic Run Success | **100.0%** | $100.0\%$ |

*Note: Benchmarks reflect deterministic evaluation over synthetic scenario matrices. Full benchmark reports are documented in [docs/PHASE_15_REPORT.md](docs/PHASE_15_REPORT.md).*

---

## Quick Start & Local Setup

### Prerequisites
* **Python**: 3.11+
* **Node.js**: v18+ (Node 20+ recommended)
* **MongoDB**: Active MongoDB Atlas cluster URI

---

### 1. Environment Setup

Copy `.env.example` to `.env` in the repository root:

```bash
cp .env.example .env
```

Configure your environment variables:
* `MONGODB_URI`: Your MongoDB Atlas connection URI.
* `GEMINI_API_KEY`: *(Optional)* Google AI Studio API key for live LLM inference.
* `WORKFLOWOS_CREDENTIAL_KEY`: Fernet 32-byte base64 encryption key (generate via `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).

---

### 2. Backend Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Start FastAPI backend
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Verify backend health at `http://127.0.0.1:8000/api/health`.

---

### 3. Frontend Setup

In a separate terminal:

```bash
cd frontend

# Install Node dependencies
npm install

# Start Next.js development server
npm run dev
```

Open `http://localhost:3000` in your browser.

---

### 4. Desktop Activity Agent (Optional)

To start observing active desktop application windows on macOS:

```bash
source .venv/bin/activate
python -m agent run --interval 1.0
```

---

### 5. Running the Test Suite

Execute the full backend unit and integration test suite (453 tests):

```bash
source .venv/bin/activate
python -m unittest discover -s backend -p "test_*.py"
```

Verify frontend TypeScript types and production build:

```bash
cd frontend
npm run lint
npm run type-check
npm run build
```

---

## Demonstration Guide

WorkFlowOS provides a complete, 12-step guided demonstration flow:

1. **Product Dashboard**: Inspect system health, desktop agent connectivity, and live telemetry cards.
2. **Activity Stream**: View sanitized, non-invasive desktop telemetry events.
3. **Workflow Discovery**: View discovered workflow candidates with repetition counts and confidence scores.
4. **AI Understanding**: Inspect generated declarative workflow graphs with parameterized inputs.
5. **Human Approval**: Review the approval gate for mutating actions.
6. **Strategy Planning**: Inspect the hierarchical plan (`API` → `Integration` → `Semantic UI` → `Browser` → `Manual`).
7. **Execution**: Trace step-by-step progress with retry and error containment.
8. **Outcome Evaluation**: Review post-condition evaluation and 11-category failure taxonomy.
9. **Adaptive Learning**: Inspect Bayesian evidence records and dynamic confidence adjustments.
10. **Privacy Controls**: Test the authoritative kill-switch and PII redaction engine.
11. **Application Ecosystem**: Verify capability schemas and fail-closed security for unknown actions.
12. **Evaluation Suite**: Run the Phase 15 benchmark harness.

*For complete step-by-step scripts and talking points, see [docs/DEMO.md](docs/DEMO.md).*

---

## API Overview

The backend exposes a clean REST API documented via OpenAPI at `http://127.0.0.1:8000/docs`:

| Resource Area | Route Pattern | Description |
|:---|:---|:---|
| **Health & Telemetry** | `GET /api/health`, `GET /api/system/status` | System readiness, component connectivity, onboarding checks |
| **Event Ingestion** | `POST /api/events`, `POST /api/events/batch` | Ingest sanitized desktop activity events |
| **Workflow Discovery** | `GET /api/discovery/patterns`, `POST /api/discovery/scan` | Mine recurring patterns from event sequences |
| **AI Generation** | `POST /api/ai/generate-workflow` | Synthesize declarative workflows from natural language or events |
| **Workflow Management** | `GET /api/workflows`, `POST /api/workflows` | Register, retrieve, and update declarative workflows |
| **Automation Planning** | `POST /api/workflows/{id}/automation-plan` | Generate deterministic multi-strategy automation plans |
| **Execution Engine** | `POST /api/automation/execute` | Execute approved workflows with live progress tracking |
| **Closed-Loop Learning** | `GET /api/workflows/{id}/learning` | Inspect Bayesian learning scores and evidence records |
| **Privacy Controls** | `GET /api/privacy/status`, `POST /api/privacy/toggle` | Manage authoritative kill-switch and retention pruning |
| **Integrations** | `GET /api/integrations`, `GET /api/integrations/gmail/connect`| Inspect connected apps and initiate OAuth flows |

*For complete endpoint schemas, parameters, and payloads, see [docs/API.md](docs/API.md).*

---

## Project Structure

```text
workflowOS/
├── agent/                  # Desktop activity capture agent (macOS NSWorkspace poller)
│   ├── collector.py        # Active window polling and normalization
│   ├── normalizer.py       # Event schema normalization & PII scrubbing
│   ├── client.py           # HTTP client with exponential retry backoff
│   └── cli.py              # Command-line interface (`python -m agent`)
├── ai/                     # AI workflow understanding & synthesis
│   └── gemini_service.py   # Google Gemini API integration with deterministic fallbacks
├── automation/             # Declarative workflow engine & strategy planner
│   ├── engine.py           # AST step executor, variable interpolation, condition evaluation
│   ├── planner.py          # 5-tier hierarchical strategy planner
│   ├── models.py           # Pydantic schemas for workflows, steps, and plans
│   ├── service.py          # Execution state management and crash recovery
│   └── playwright_executor.py # Headless browser automation runner
├── backend/                # FastAPI application backend
│   ├── main.py             # FastAPI entrypoint, middleware, lifespan handlers
│   ├── config.py           # Environment settings and configuration validation
│   ├── routes/             # REST route handlers (events, discovery, execution, privacy, etc.)
│   ├── discovery/          # Discovery engine, local alignment, pattern ranking, explainability
│   ├── learning/           # Phase 9/11 adaptive learning & closed-loop evidence stores
│   ├── privacy/            # Phase 12 redaction engine, retention pruning, privacy gate
│   └── tests/              # Comprehensive test suites (Phases 1–15)
├── docs/                   # Engineering documentation
│   ├── ARCHITECTURE.md     # Full architectural specification & safety invariants
│   ├── API.md              # REST API reference guide
│   ├── DEMO.md             # 12-step end-to-end demonstration guide
│   ├── PHASE_15_REPORT.md  # Verified benchmark evaluation report
│   ├── RELEASE_CHECKLIST.md# Phase 16 release verification checklist
│   └── RESUME.md           # Resume bullet points & 19 technical interview questions
├── frontend/               # Next.js 16 product dashboard (React 19 + Tailwind CSS)
│   ├── src/app/            # App router page routes
│   ├── src/components/     # UI views (Dashboard, Activity, Workflows, Applications, etc.)
│   └── src/lib/api.ts      # Strongly typed API client
├── integrations/           # Application ecosystem & adapter registry
│   ├── registry.py         # Capability registry & fail-closed action classifier
│   ├── oauth.py            # OAuth 2.0 PKCE / state management
│   ├── credentials.py      # Fernet AES-128-CBC token encryption
│   └── mock.py             # Mock adapters for local development & benchmarking
├── .env.example            # Environment configuration template (zero secrets)
├── requirements.txt        # Python backend dependencies
└── README.md               # Main project overview (this file)
```

---

## Known Limitations

To maintain absolute technical transparency, the current implementation has the following defined boundaries:

1. **Synthetic Benchmark Dataset**: Phase 15 evaluation metrics reflect testing against a standardized 24-scenario synthetic benchmark harness rather than live enterprise multi-tenant traces.
2. **Local Single-User Architecture**: WorkFlowOS is designed and tested as a single-node system running locally; it does not currently provide multi-tenant team isolation or Kubernetes clustering.
3. **Mock & In-Memory Application Adapters**: While the Gmail integration supports live Google OAuth 2.0 authentication, CRM and Chat capabilities currently utilize local mock adapters implementing realistic capability schemas.
4. **UI Automation DOM Sensitivity**: Browser and UI automation tiers are vulnerable to unexpected third-party DOM changes, application redesigns, or OS accessibility permission revocations.
5. **External AI API Dependency**: High-level natural language prompt synthesis relies on the external Google Gemini API; when unconfigured, the system gracefully falls back to deterministic rule-based heuristic generation.

---

## Future Scope

The following areas represent natural engineering extensions for WorkFlowOS:

* **Enterprise Multi-Tenancy**: Add organization workspaces, role-based access control (RBAC), and SSO authentication via OIDC/SAML.
* **Distributed Task Workers**: Decouple long-running workflow executions onto distributed worker pools (e.g. Celery or Temporal) for high-concurrency enterprise execution.
* **Native OS Accessibility Drivers**: Extend the Semantic UI tier with native macOS Accessibility (`AXUIElement`) and Windows UI Automation (`UIA`) drivers to automate non-web desktop applications without DOM selectors.
* **Self-Healing Automation Selectors**: Implement automatic runtime diagnosis of broken UI selectors using semantic DOM trees and visual diffing to auto-correct step parameters without failing.
* **Expanded Integration Connectors**: Implement production OAuth integrations for Salesforce, HubSpot, Slack, Jira, and Microsoft 365.

---

## Engineering Documentation

* [System Architecture Specification](docs/ARCHITECTURE.md)
* [REST API Reference](docs/API.md)
* [Demonstration Guide & Script](docs/DEMO.md)
* [Phase 15 Evaluation Report](docs/PHASE_15_REPORT.md)
* [Phase 16 Release Checklist](docs/RELEASE_CHECKLIST.md)
* [Resume & Technical Interview Guide](docs/RESUME.md)
