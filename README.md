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
| **Phase 7.1** | Integration Foundation & Encrypted Token Storage | ✅ Complete |
| **Phase 7.2** | Secure Gmail OAuth 2.0 Integration & Read-Only Action | ✅ Complete |
| **Phase 7.3** | Declarative Workflow Builder & UI Action Testing | ✅ Complete |
| **Phase 7.4** | Reliability, Security, & Operational Recovery | ✅ Complete |
| **Phase 8.1** | Discovery Evaluation & Calibrated Confidence Scoring | ✅ Complete |
| **Phase 8.2** | Smarter Sequence Detection & Dynamic Local Alignment | ✅ Complete |
| **Phase 8.3** | Pattern Ranking, Noise Reduction & Duplicate Detection | ✅ Complete |
| **Phase 8.4** | Explainable Discovery & Empirical Verification | ✅ Complete |
| **Phase 8.5** | Discovery Quality, Robustness & Semantic Grouping | ✅ Complete |
| **Phase 9** | Adaptive Learning & Human Review Feedback Loop | ✅ Complete |
| **Phase 10** | Intelligent Automation — Deterministic Strategy Planning | ✅ Complete |

---

## Quick Start

### 1. Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# → Configure MONGODB_URI, GEMINI_API_KEY, and WORKFLOWOS_CREDENTIAL_KEY

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

## Phase 7.1 & 7.2 — Integration Architecture & Gmail OAuth 2.0

WorkFlowOS includes an extensible, secure integration subsystem enabling connectivity with external services while maintaining strict human approval gates.

```
┌─────────────────────────────────────────────────────────────┐
│  Next.js Settings View (src/components/views/SettingsView)  │
│  - Connect Gmail / Disconnect                              │
│  - Scope disclosure (gmail.readonly)                       │
│  - Direct action test sandbox (list_recent_messages)       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ OAuth 2.0 Auth Code Flow
┌──────────────────────────▼──────────────────────────────────┐
│  FastAPI Integration API (backend/routes/integrations.py)    │
│  ├── GET  /api/integrations                                 │
│  ├── GET  /api/integrations/gmail/connect (CSRF state gen)  │
│  ├── GET  /api/integrations/gmail/callback (Token exchange) │
│  ├── GET  /api/integrations/gmail/status                    │
│  ├── POST /api/integrations/gmail/disconnect (Revocation)   │
│  └── POST /api/integrations/{provider}/actions/{action}     │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
┌──────────────▼─────────────┐   ┌─────────────▼──────────────┐
│  EncryptedTokenStorage     │   │  IntegrationRegistry       │
│  - Fernet AES-CBC + HMAC   │   │  ├── MockEmailAdapter (7.1)│
│  - Key from env var only   │   │  └── GmailAdapter (7.2)    │
│  - In-memory cache + purge │   └─────────────┬──────────────┘
└────────────────────────────┘                 │
                                 ┌─────────────▼──────────────┐
                                 │  Google APIs               │
                                 │  - oauth2.googleapis.com   │
                                 │  - gmail.googleapis.com    │
                                 └────────────────────────────┘
```

### Security Architecture & Principles

1. **Strictly Authenticated Encryption**:
   - OAuth tokens (access & refresh) are encrypted at rest using AES-128-CBC + HMAC-SHA256 (Fernet) via `EncryptedTokenStorage`.
   - The encryption key is sourced strictly from `WORKFLOWOS_CREDENTIAL_KEY`. Ephemeral development keys are completely prohibited for real OAuth credentials (fails closed).
   - Plaintext tokens are never stored, logged, exposed in API responses, or sent to frontend state.

2. **Single-Use, Time-Bound CSRF State Protection**:
   - Cryptographically random state values (`secrets.token_urlsafe(32)`) generated by `OAuthStateStore`.
   - Bound to an in-memory TTL store (10-minute expiry) with auto-cleanup of expired states.
   - States are validated and consumed exactly once (`validate_and_consume`), preventing replay and CSRF attacks.

3. **Human-in-the-Loop Workflow Safety Preserved**:
   - Connecting Gmail does **NOT** grant automated workflow approval.
   - Declarative workflows containing Gmail actions strictly require human approval (`approved=True`).
   - The initial Gmail capability `list_recent_messages` is strictly read-only and bounded (max 20 messages, headers + snippet only; no email sending, modification, or deletion).
   - Standalone direct execution of safe actions is permitted in Settings for diagnostic testing, but workflow steps remain under strict human gatekeeping.

4. **Token Lifecycle & Automatic Refresh**:
   - Automatic refresh token exchange when access tokens near expiry (within 60-second safety window).
   - Existing refresh tokens are preserved across reconnects if Google omits returning a new refresh token.
   - Disconnection securely calls Google's token revocation endpoint (`https://oauth2.googleapis.com/revoke`) and scrubs stored credentials.

---

### Google Cloud Project Setup Guide

To connect a real Gmail account, configure Google Cloud Platform:

#### 1. Create or Select a GCP Project
1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. `workflowos-dev`) or select an existing project.

#### 2. Enable the Gmail API
1. In the GCP Console, go to **APIs & Services > Library**.
2. Search for **Gmail API**.
3. Click **Enable**.

#### 3. Configure the OAuth Consent Screen
1. Go to **APIs & Services > OAuth consent screen**.
2. Select **External** (or **Internal** if using Google Workspace).
3. Fill in required App information:
   - App name: `WorkFlowOS`
   - User support email: your email
   - Developer contact email: your email
4. Click **Save and Continue**.
5. Under **Scopes**, click **Add or Remove Scopes**:
   - Filter and select: `https://www.googleapis.com/auth/gmail.readonly` (Read resources and metadata in your Gmail account).
   - *Note*: `gmail.readonly` is classified as a Google **Restricted Scope**. For development and personal hackathon use, keep the app in **Testing** status and add your email to **Test Users**. (Production distribution across non-whitelisted users would require a formal Google CASA security assessment and verification).
6. Under **Test Users**, add your Google email address.
7. Click **Save and Continue**.

#### 4. Create OAuth 2.0 Client Credentials
1. Go to **APIs & Services > Credentials**.
2. Click **Create Credentials > OAuth client ID**.
3. Select Application type: **Web application**.
4. Set Name: `WorkFlowOS Web Client`.
5. Under **Authorized redirect URIs**, click **Add URI** and enter:
   ```
   http://127.0.0.1:8000/api/integrations/gmail/callback
   ```
   *(Ensure exact IP, port, and path match. Google OAuth treats `127.0.0.1` and `localhost` as distinct origins).*
6. Click **Create**.
7. Copy the generated **Client ID** and **Client Secret**.

---

### Environment Setup & Configuration Guide

Follow these steps to set up your local `.env` configuration safely:

#### 1. Create `.env` from `.env.example`
```bash
cp .env.example .env
```

#### 2. MongoDB Atlas Configuration
- `MONGODB_URI`: Required for persistent workflow storage, event ingestion, and execution history. Sourced from MongoDB Atlas (*Database > Connect > Drivers*).
- `MONGODB_DATABASE`: Database name (defaults to `workflowos`).
*(Note: Automated test suites use an in-memory fallback when `MONGODB_URI` is not provided).*

#### 3. AI / Gemini API Configuration
- `GEMINI_API_KEY`: Required for natural language prompt-to-workflow generation in Phase 3. Obtain a free key from [Google AI Studio](https://aistudio.google.com/).
- `GEMINI_MODEL`: Model identifier (defaults to `gemini-2.5-flash`).

#### 4. Google OAuth 2.0 Credentials (for Gmail Integration)
- `GOOGLE_CLIENT_ID`: Web application OAuth 2.0 Client ID from GCP Credentials.
- `GOOGLE_CLIENT_SECRET`: Client secret from GCP Credentials.
- `GOOGLE_REDIRECT_URI`: Must match the redirect URI authorized in GCP Console exactly (`http://127.0.0.1:8000/api/integrations/gmail/callback`).

#### 5. Generate Credential Encryption Key
Fernet envelope encryption protects OAuth tokens in-memory. Generate a unique 32-byte URL-safe base64 key:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Copy the generated string into your `.env`:
```bash
WORKFLOWOS_CREDENTIAL_KEY=your_generated_fernet_key_here
```

#### 6. Localhost URL and Port Alignment
Verify that your local backend and frontend URLs align consistently:
- `HOST=127.0.0.1`: Default backend bind address (loopback protection).
- `PORT=8000`: Backend server port.
- `FRONTEND_ORIGIN=http://localhost:3000`: Trusted origin for CORS and CSRF protection.
- `NEXT_PUBLIC_API_URL=http://localhost:8000`: Used by Next.js frontend client to communicate with the backend.
- `GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/integrations/gmail/callback`: Must align with backend host, port, and GCP console.

#### 7. Security: Never Commit `.env`
> [!CAUTION]
> `.env` contains sensitive API keys, database credentials, and encryption secrets. It is excluded by `.gitignore` and must **never** be committed, pushed, or logged.

#### 8. In-Memory Token Storage Lifecycle
> [!NOTE]
> For this hackathon MVP, Gmail OAuth tokens are held encrypted in-memory via `EncryptedTokenStorage` and are **not** persisted to MongoDB or disk. **Restarting the backend server clears active credentials**, requiring you to reauthorize Gmail from the Settings page. Persistent token storage is scheduled for Phase 8.

---

### Usage & Verification Walkthrough

#### 1. Start the Platform
```bash
# Terminal 1: Backend
uvicorn backend.app:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

#### 2. Connect Gmail
1. Open `http://localhost:3000` and click **Settings** in the sidebar.
2. Locate the **Google Gmail** integration card.
3. Click **Connect Gmail**.
4. You will be redirected to Google's consent screen (`accounts.google.com`).
5. Choose your Google account (must be listed under Test Users if app is in Testing mode).
6. Review permissions: *"Read all resources and metadata in your Gmail account"*.
7. Click **Continue / Allow**.
8. Google redirects back to `http://127.0.0.1:8000/api/integrations/gmail/callback`, which validates the single-use state, stores encrypted tokens, and redirects back to `http://localhost:3000/?view=settings&integration=gmail&status=connected`.
9. The Gmail card will now display status **Connected** with an emerald badge.

#### 3. Test Read-Only Action
1. Under the connected Gmail card, click **Test: List Recent Messages**.
2. The backend queries `https://gmail.googleapis.com/gmail/v1/users/me/messages` (up to 5 messages) and fetches subject, sender, date, and snippet.
3. The message metadata preview renders directly in the UI.

#### 4. Disconnect Gmail
1. Click **Disconnect** on the Gmail card.
2. The backend revokes the token with Google (`https://oauth2.googleapis.com/revoke`) and deletes the local encrypted credentials.
3. The status returns to **Not Connected**.

---

### Known Limitations & Architecture Notes
- **In-Memory Credential Storage (Re-authorization Required on Restart)**: For this hackathon MVP, OAuth credentials (access and refresh tokens) are held in-memory (encrypted with Fernet) and are not persisted to a database or local disk. If the backend server stops or restarts, the in-memory credential storage is cleared and Gmail must be reauthorized from the Settings page.
- **Localhost Loopback Binding**: The backend defaults to binding to `127.0.0.1` (loopback only) instead of `0.0.0.0` to prevent exposing integration endpoints to the local network.
- **Local Single-User Session Model**: The in-memory CSRF `OAuthStateStore` with HttpOnly cookie session binding is optimized for local single-user desktop operation. Multi-user SaaS deployment would require Redis/database-backed CSRF state and per-user token partitioning.
- **KMS / Key Rotation**: Fernet authenticated symmetric encryption is used with a single environment key. Production key rotation or cloud KMS (GCP Cloud KMS / AWS KMS) envelope encryption is planned for Phase 8.
- **Google App Verification**: When deployed in Testing mode in Google Cloud Console, up to 100 test users can authorize the app without formal Google security assessment. Public publishing requires Google App Verification.

---

---

## Phase 7.4: Reliability, Security, and Recoverability

Phase 7.4 hardens the execution engine, state persistence, approval authorization, and resource cleanup:

### 1. Execution State Lifecycle & Transitions
The workflow engine enforces a strict finite state machine:
- `PENDING`: Unapproved workflow awaiting operator approval.
- `RUNNING`: Actively executing workflow steps. Step progress is durably updated in MongoDB Atlas before and after each action.
- `PAUSED`: Action failure or unexpected interruption occurred. Halts execution, sets `requires_human_intervention=True`, and enables `resume_available=True`.
- `COMPLETED`: All steps executed successfully (terminal state).
- `FAILED`: Terminal failure (e.g. fatal validation error or unhandled exception).
- `CANCELLED`: Terminal cancellation by operator.

State transition rules:
- `PENDING` → `RUNNING`, `CANCELLED`
- `RUNNING` → `PAUSED`, `COMPLETED`, `FAILED`, `CANCELLED`
- `PAUSED` → `RUNNING` (via `/resume`), `CANCELLED` (via `/cancel`)
- `COMPLETED`, `FAILED`, `CANCELLED` are terminal: cannot be resumed, restarted, or cancelled.

### 2. Durable Persistence & Outage Fallback
- **MongoDB Atlas Storage**: Execution records and step-level history are saved to the `executions` collection.
- **Graceful Offline Fallback**: If MongoDB Atlas is unavailable or experiences a network outage, `AutomationService` gracefully falls back to its in-memory cache with warning logs, avoiding workflow execution loss.
- **Credential Redaction**: Before writing execution records to MongoDB or returning API payloads, all credentials (tokens, keys, passwords, bearer headers) are scrubbed using `sanitize_credential_dict` and `sanitize_log_message`.

### 3. Safe Recovery of Interrupted Executions
- **Startup Recovery Scan**: During FastAPI `lifespan` startup, `AutomationService.recover_interrupted_executions()` scans for any executions left in `RUNNING` state due to a crash or unexpected shutdown.
- **Safe Transition to PAUSED**: Active runs are transitioned to `PAUSED` with `requires_human_intervention=True`.
- **Completed-Step Preservation**: Completed actions are never blindly rerun. When resumed, execution starts from the failed or next step.
- **Audit Logging**: Recovery reasons, timestamps, and incremented `recovery_attempts` are permanently recorded in the execution record.

### 4. Idempotency & Duplicate Execution Prevention
- **Idempotency Key**: Clients can submit an `idempotency_key` with execution requests.
- **Deduplication**: If an execution with the given key already exists, the server returns the existing execution without duplicating execution actions.

### 5. Cryptographic Approval Binding & Tamper Detection
- **Canonical Definition Hash**: `compute_workflow_definition_hash()` generates a SHA-256 hash across workflow inputs, variables, triggers, steps, and approval requirements.
- **Tamper Detection**: If a workflow definition is modified after approval, the hash changes. The backend detects the mismatch and returns `HTTP 409 Conflict`, requiring renewed operator approval.

### 6. Timeouts, Error Classification, and Cleanup
- **Step Timeouts**: Every action execution is bounded by `timeout_seconds` (defaulting to `DEFAULT_ACTION_TIMEOUT = 30.0s`) using `asyncio.wait_for`.
- **Non-Retryable Error Classification**: Errors indicating authentication failures (401, 403), missing resources (404), or schema validation errors immediately abort retries. Transient errors retry with bounded backoff.
- **Resource Cleanup on Shutdown**: Active Playwright browser and page instances are tracked in a global registry and cleanly terminated during FastAPI shutdown via `close_active_executors()`.

---

## Phase 8.1 — Discovery Evaluation & Transparent Confidence Scoring

Phase 8.1 establishes an empirical evaluation framework and deterministic confidence scoring system for the Discovery Engine, replacing uncalibrated heuristics with transparent, explainable metrics.

### 1. The 5 Deterministic Scoring Signals
Confidence $C \in [0.0, 1.0]$ combines 5 orthogonal signals strictly summing to weight 1.00:
- **Repetition Support ($w=0.30$)**: Volume of session occurrences (scaled from 2 to 5+ sessions).
- **Sequence Similarity ($w=0.25$)**: Average SequenceMatcher alignment across matched sessions.
- **Action Diversity ($w=0.20$)**: Unique action count ratio; penalizes monotonous single-action loops (`view_dashboard x 3` drops to 0.10).
- **Sequence Length ($w=0.15$)**: Structural complexity / intentionality (scaled across 3 to 5+ steps).
- **Session Consistency ($w=0.10$)**: Proportion of matched sessions that are exact 100% replays.

### 2. Explainable Rationale & Tiers
- **`high` ($\ge 0.80$)**: Strong candidate for operator review and workflow proposal.
- **`medium` ($0.65 \le C < 0.80$)**: Moderate evidence; minor variations or short sequence.
- **`low` ($< 0.65$)**: Insufficient repetition or penalized low-entropy repetition.
- **Deterministic Text Explanations**: Generates clear, non-LLM natural summaries of the contributing evidence.

---

## Phase 8.2 — Smarter Sequence Detection with Local Alignment

Phase 8.2 introduces semi-global dynamic programming local alignment with Damerau transposition handling, enabling discovery of workflows embedded within longer, noisy user sessions.

### 1. Key Capabilities
- **Embedded Workflow Extraction**: Finds repeated sequences surrounded by arbitrary prefix and suffix noise.
- **Variation Tolerance**: Handles inserted intermediate actions, missing steps, and small adjacent step transpositions ($A \to B$ vs $B \to A$) within strict coverage limits ($\ge 0.75$).
- **Strict Distinct-Session Occurrences**: Single-session internal repetitions cannot artificially inflate candidate occurrence counts.
- **Shadow Pruning**: Prunes redundant sub-slices of longer workflows while preserving genuinely distinct workflows that share common prefixes (e.g. Billing vs. Support routines).

### 2. 16-Scenario Comparative Benchmark Results
Evaluated via `.venv/bin/python -m discovery.evaluation`:
- **Phase 8.1 Baseline**: Precision = 92.9%, Recall = 92.9%, F1 = 0.9286 (failed on embedded noise).
- **Phase 8.2 Smarter Detector**: Precision = **93.3%**, Recall = **100.0%** (14/14 ground truth workflows found), F1 = **0.9655**, Accuracy = **94.7%**.
- **Phase 8.2 with High-Confidence Filter ($\ge 0.80$)**: Precision = **100.0%** (0 False Positives).

---

## Phase 8.3 — Pattern Ranking, Noise Reduction & Duplicate Detection

Phase 8.3 enhances discovered pattern quality by prioritizing high-utility workflows, suppressing noise and repetitive loops, and deduplicating overlapping variants into canonical representatives.

### 1. Deterministic Utility Ranking
Ranking score $R \in [0.0, 1.0]$ evaluates automation utility (separate from detection confidence) using 5 normalized signals:
- **Pattern Confidence ($w=0.30$)**: Intrinsic match confidence from local alignment.
- **Execution Fidelity ($w=0.25$)**: Average sequence alignment (0.60) + session replay consistency (0.40).
- **Operational Volume ($w=0.20$)**: Multi-session adoption scaled from 2 to 7+ distinct sessions.
- **Automation Impact ($w=0.15$)**: Sequence length savings potential scaled from 3 to 5+ steps.
- **Task Richness ($w=0.10$)**: Unique verb diversity entropy.

Workflows receive discrete quality tiers (`exceptional` $\ge 0.85$, `strong` $\ge 0.70$, `moderate` $\ge 0.55$, `low` $< 0.55$) and deterministic 1-based ranks with explainable summaries.

### 2. Active Noise Reduction & Legitimate Loop Preservation
- **Monotonous Loops**: Sequences dominated by single repeated actions (e.g. `view_dashboard x 3`) are penalized and assigned suppression reason `monotonous_repeated_actions`.
- **Marginal Utility Filter**: Weak patterns below `min_ranking_score` (default: 0.50) are suppressed as `marginal_ranking_score`.
- **Legitimate Workflows Preserved**: Valid multi-step workflows with repeated actions (e.g. `download -> review -> review -> approve`) maintain high entropy and are preserved as valid.

### 3. Duplicate & Overlapping Variant Detection
- **Exact Duplicates**: Repeated candidate extractions collapse into a single canonical workflow with consolidated sessions.
- **Overlapping Shadows**: Shorter sub-sequences whose sessions are $\ge 70\%$ contained within a parent workflow are suppressed as `overlapping_shadow` with a link to `representative_pattern_id`.
- **Similar Variants**: Variants sharing $\ge 80\%$ alignment similarity and $\ge 50\%$ session overlap are deduplicated to the highest-confidence representative.
- **Independent Sequences**: Sub-sequences with $\ge \text{min\_occurrences}$ independent sessions outside the parent workflow are preserved.

### 4. Comparative Benchmark Results (Phase 8.1 through Phase 8.5)
Evaluated across the 33-scenario benchmark dataset via `.venv/bin/python -m discovery.evaluation`:
- **Phase 8.1 Baseline**: Precision = 90.3%, Recall = 84.8%, F1 = 0.8750, Acc = 80.5%
- **Phase 8.2 Smarter Detector**: Precision = 91.7%, Recall = **100.0%**, F1 = 0.9565, Acc = 92.7%
- **Phase 8.3/8.4 Ranked & Clean**: Precision = **97.1%**, Recall = **100.0%**, F1 = **0.9851**, Acc = **97.6%**, Duplicates Suppressed = **186**
- **Phase 8.5 Discovery Quality & Robustness**: Precision = **97.1%**, Recall = **100.0%**, F1 = **0.9851**, Acc = **97.6%**, Duplicates Suppressed = **186**, Optional Steps = 2, Partial Support = 15, Intra-Session Repetitions = 1, Explainability Audit = **100.0%** (272/272 evidence checks passed)

---

## Phase 8.4 — Explainable Discovery & Empirical Verification

Phase 8.4 equips WorkFlowOS with a deterministic, non-hallucinatory explainability engine that explains all discovery, confidence, ranking, and suppression decisions using computed evidence:

### 1. Zero-Hallucination Architecture
- **No LLM in Explanation Path**: Explanations are synthesized directly from actual computed metrics (session counts, alignment edit distances, entropy ratios, and deduplication overlaps).
- **Distinction of Concepts**: Clearly delineates observed facts (timestamps, sessions), algorithmic measurements (alignment score, edit distances), and heuristic operational scores (ranking utility $R$).

### 2. Structured Explainability Model (`WorkflowExplanation`)
- **Detection Reason**: Explicit threshold qualification, exact vs. approximate replay counts, and tolerated structural variations (insertions, deletions, transpositions).
- **Confidence & Ranking Drivers**: Itemized breakdown of positive drivers (e.g. high alignment, step savings) and limiting factors.
- **Suppression Evidence**: Explicit rejection reasons (`monotonous_repeated_actions`, `marginal_ranking_score`, `insufficient_occurrences`, `overlapping_shadow`, `similar_variant_overlap`), measured values vs. criterion thresholds, and canonical representative references.

### 3. Privacy-Safe Session Masking
- Session identifiers are masked with salted SHA-256 prefixes (`s_a1b2c3d4...`), preventing exposure of raw session tokens.
- Complete activity payloads, keystrokes, and authentication tokens are strictly excluded from explanation fields.

### 4. Frontend Experience
- Discovery cards include an expandable **"Why was this detected?"** accordion disclosing sequence fidelity, order consistency bars, scoring drivers, heuristic disclaimers, and suppressed candidate details.

---


## Phase 8.5 — Discovery Quality & Robustness

Phase 8.5 enhances discovery quality under messy user behavior while eliminating generic noise false positives:

1. **Robust Temporal Matching with Bounded Noise**: Up to 3 consecutive non-workflow insertions tolerated; stretches $>3$ are bounded and rejected.
2. **Deterministic Optional Step Detection**: DP traceback dynamically identifies steps present in some sessions but omitted in others (`optional_steps`).
3. **Partial Workflow Execution Support**: Sessions executing partial sequences (coverage $\in [0.35, 0.80)$) are tracked as `partial_support_count` without inflating distinct-session qualification counts.
4. **Position-Independent Alignment**: Matches recurring routines regardless of whether they appear at session prefix, middle, or suffix.
5. **Intra-Session Repetition Modeling**: Multiple executions within a single session are tracked separately (`intra_session_repetitions`) to prevent inflating multi-session support.
6. **Common Action False Positive Suppression**: Suppresses 1-action monotonous loops (`view_dashboard x 3`) and 2-action alternating ping-pong loops (`open_tab, search_tab, open_tab, search_tab`) while preserving legitimate workflows containing repetitive steps.
7. **Deterministic Representative Selection**: 6-factor tie-break key guarantees 100% reproducible canonical selections regardless of dictionary or hash set ordering.

---

## Phase 9 — Adaptive Learning & Feedback

Phase 9 completes the canonical WorkFlowOS loop:
**OBSERVE → UNDERSTAND → DETECT REPETITION → GENERATE WORKFLOW → USER APPROVAL → AUTOMATE → LEARN**

It implements a deterministic, explainable learning and feedback loop that learns from human review decisions and execution telemetry to dynamically adapt future workflow recommendations.

> [!IMPORTANT]
> **Deterministic Signals — No Opaque AI**:
> Phase 9 uses deterministic, explainable mathematical formulas and discrete state machines.
> It does **NOT** use machine learning, neural networks, embeddings, vector databases, or an LLM for feedback interpretation.

### 1. Conceptual Ranking Pipeline

Phase 8 confidence and ranking formulas remain completely untouched. Phase 9 introduces an independent downstream learning signal:

```
Discovery Candidate
       ↓
Phase 8 Confidence  (Calibrated pattern strength in [0.0, 1.0])
       ↓
Phase 8 Ranking     (Composite automation utility score R in [0.0, 1.0])
       ↓
Phase 9 Learning    (Bounded score L in [0.0, 1.0] from human feedback & execution telemetry)
       ↓
Recommendation Decision (NEW | LEARNING | RECOMMENDED | DEPRIORITIZED)
```

### 2. Feedback Model & Storage

- **Storage**: Persisted in MongoDB Atlas (`workflow_feedback` collection) with in-memory caching fallback.
- **Indexes**: `workflow_id` (1), `timestamp` (-1), `decision` (1).
- **Supported Decisions**:
  - `approve`: Workflow approved by human operator.
  - `reject`: Workflow dismissed or rejected (with structured `rejection_reason`).
  - `edit_approve`: Workflow approved with human parameter/action modifications (`edited_workflow`).

### 3. Workflow Learning State

- **Storage**: Persisted in MongoDB Atlas (`workflow_learning_state` collection, unique index on `workflow_id`).
- **Telemetry Signals**:
  - `approval_count`, `rejection_count`, `edit_count`
  - `execution_count`, `successful_execution_count`, `failed_execution_count`
  - `intervention_count`, `recovery_count`
  - `last_feedback`, `last_execution_status`, `last_failed_step`, `last_failure_reason`
  - `learning_score`: Bounded score in $[0.0, 1.0]$.
  - `recommendation_status`: `NEW`, `LEARNING`, `RECOMMENDED`, or `DEPRIORITIZED`.
  - `learning_explanation`: Deterministic human-readable explanation.

### 4. Execution Telemetry Integration

Directly adapts existing `AutomationExecution` records produced by `automation_service`:
- **Success (`completed`)**: `execution_count += 1`, `successful_execution_count += 1`.
- **Failure (`failed`)**: `execution_count += 1`, `failed_execution_count += 1`.
- **Human Intervention (`paused` / `requires_human_intervention=True`)**: `intervention_count += 1`.
- **System Recovery (`resume_count > 0` or `recovery_attempts > 0` and completed)**: `recovery_count += 1`.
- **Idempotency**: Execution outcome processing is indexed by execution ID and status milestone to prevent double counting.

### 5. Learning Score Formula

$$L = \text{clamp}\Big(0.50 + 0.10 \cdot A + 0.08 \cdot E_{\text{edit}} + 0.15 \cdot X_{\text{succ}} + 0.05 \cdot C_{\text{rec}} - 0.20 \cdot R - 0.15 \cdot X_{\text{fail}} - 0.05 \cdot I,\ 0.0,\ 1.0\Big)$$

- **Prior Baseline**: Neutral $0.50$.
- **Positive Weights**: Approval ($+0.10$), Edit & Approve ($+0.08$), Successful execution ($+0.15$), Recovery ($+0.05$).
- **Negative Weights**: Rejection ($-0.20$), Failed execution ($-0.15$), Operator intervention ($-0.05$).
- **Bounds**: Strictly clamped to $[0.0, 1.0]$.

### 6. Recommendation Status & Reversibility

- **`NEW`**: No human review or execution history recorded ($A + R + E_{\text{edit}} + X = 0$).
- **`RECOMMENDED`**: $L \ge 0.70$, $A + E_{\text{edit}} \ge 1$, $X_{\text{succ}} \ge 1$, and positive signals outweigh negative signals.
- **`DEPRIORITIZED`**: $L < 0.40$, or ($R \ge 2$ with no successful executions), or ($X_{\text{fail}} \ge 2$ with 0 successes).
- **`LEARNING`**: Active operational evidence accumulating.
- **Reversibility**: Workflows are never permanently deleted or suppressed. If an updated or fixed workflow accumulates new approvals and successful executions, its score recalculates upward and smoothly transitions back to `RECOMMENDED`.

### 7. REST APIs

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/workflows/{workflow_id}/feedback` | Submit operator review (`approve`, `reject`, `edit_approve`) |
| `GET` | `/api/workflows/{workflow_id}/feedback` | Audit history of feedback records |
| `GET` | `/api/workflows/{workflow_id}/learning` | Retrieve persistent learning state and explanation |

### 8. Security Guarantee

Learning signals influence future recommendation ranking. **Learning must NEVER bypass human approval or trigger autonomous execution.** Execution remains strictly gated by explicit operator approval (`approved=True`).

### 9. Limitations

- **Deterministic & Heuristic**: Learning scores and status transitions are rule-based, not calibrated probabilities.
- **Single-User Trust Model**: Designed for local operator review; no multi-tenant cross-user federation.
- **Evidence Dependent**: Learning accuracy depends directly on the completeness of recorded telemetry.
- **Zero Autonomous Execution**: WorkFlowOS will never autonomously execute workflows regardless of high learning scores.

---

## Phase 10 — Intelligent Automation

### 1. Purpose

Phase 10 implements an **Intelligent Automation Planner** that determines the most appropriate, reliable, and safest automation strategy for each workflow and each individual workflow action step. Rather than blindly executing every workflow with a single default strategy, WorkFlowOS deterministically inspects available repository capabilities, historical execution telemetry, and Phase 9 adaptive learning signals to produce an explainable, auditable automation plan.

> [!IMPORTANT]
> **Deterministic Heuristic Scores, Not Probabilities**:
> All strategy suitability scores ($S \in [0.0, 1.0]$) in Phase 10 are deterministic heuristic utility scores computed from explicit capability declarations, reliability metrics, and learning state. They are **NOT** statistical probabilities or machine learning outputs.

### 2. Architecture & Pipeline

```text
Discovery
   ↓
Confidence Scoring (Phase 8.1–8.2)
   ↓
Ranking & Noise Reduction (Phase 8.3–8.5)
   ↓
Adaptive Learning (Phase 9)
   ↓
Automation Planner (Phase 10)
   ├── Step Capability Inspection (API, INTEGRATION, SEMANTIC_UI, BROWSER, MANUAL)
   ├── Deterministic Strategy Scoring
   ├── Failure-Aware Adjustment (unreliable priority loses to reliable alternative)
   └── Safe Fallback Strategy Resolution
   ↓
Explainable Automation Plan
   ↓
Human Approval Gate (MANDATORY — approved=True)
   ↓
Workflow Execution Engine
   ↓
Execution Outcome Telemetry
   ↓
Adaptive Learning Update (Phase 9)
```

### 3. Strategy Hierarchy & Capability Registry

WorkFlowOS organizes automation strategies into a deterministic architectural priority hierarchy:

$$\text{API} \succ \text{INTEGRATION} \succ \text{SEMANTIC\_UI} \succ \text{BROWSER} \succ \text{MANUAL}$$

The `StrategyCapabilityRegistry` evaluates actions against actual system capabilities without fake adapters:

| Strategy | Description & Repository Capabilities |
|---|---|
| **`API`** | Direct API adapter execution (`allow_direct_execution=True`, safe read-only operations, or direct HTTP endpoints). High reliability, minimal latency, no browser required. |
| **`INTEGRATION`** | Application adapters registered in `integration_registry` (e.g. Google Workspace Gmail, mock CRM). Handles approved mutating and read actions within workflow context. |
| **`SEMANTIC_UI`** | Semantic accessibility automation. Maintained in the hierarchy but strictly marked unavailable unless a real accessibility provider is registered (no fake implementations). |
| **`BROWSER`** | Playwright browser automation on web applications (`demo_email`, `demo_crm`, `demo_chat`) supporting canonical verbs (`open_email`, `download_attachment`, `search_customer`, `update_customer`, `send_message`). |
| **`MANUAL`** | Universal human-in-the-loop fallback for unsupported, ambiguous, or safety-restricted actions. |

### 4. Deterministic Strategy Scoring

For each workflow step and candidate strategy, the heuristic suitability score is calculated as:

$$\text{Raw} = S_{\text{cap}} + S_{\text{prio}} + S_{\text{rel}} + S_{\text{learn}} + S_{\text{cred}} - P_{\text{fail}} - P_{\text{safe}}$$

$$\text{Final Score} = \text{clamp}(\text{Raw}, 0.0, 1.0)$$

Where:
- **Capability Score ($S_{\text{cap}} \in [0.0, 0.30]$)**: $0.30$ for native capability match, $0.10$ for generic manual fallback, $0.00$ if unavailable.
- **Priority Weight ($S_{\text{prio}} \in [0.0, 0.25]$)**: Architectural hierarchy baseline weight ($\text{API} = 0.25$, $\text{INTEGRATION} = 0.20$, $\text{SEMANTIC\_UI} = 0.15$, $\text{BROWSER} = 0.10$, $\text{MANUAL} = 0.00$).
- **Reliability Score ($S_{\text{rel}} \in [0.0, 0.25]$)**: Historical execution success rate: $\frac{\text{successes}}{\text{runs}} \times 0.25$ (or cold-start neutral baseline).
- **Learning Score ($S_{\text{learn}} \in [0.0, 0.15]$)**: Phase 9 adaptive learning signal: $L \times 0.10$ plus $+0.05$ bonus if `RECOMMENDED` or $-0.05$ penalty if `DEPRIORITIZED`.
- **Credential Score ($S_{\text{cred}} \in [0.0, 0.10]$)**: $+0.10$ if no credentials required or credentials verified present and valid.
- **Failure Penalty ($P_{\text{fail}} \in [0.0, 0.50]$)**: $\frac{\text{failures}}{\text{runs}} \times 0.40$, plus $+0.10$ if the most recent execution failed on this step.
- **Safety Penalty ($P_{\text{safe}} \in [0.0, 0.50]$)**: Deductions for missing required credentials ($+0.25$), or mutating actions on UI without safe isolation ($+0.05$).

### 5. Failure-Aware Strategy Selection

Nominal priority does not override empirical reliability. If a higher-priority strategy has repeatedly failed:
- **API (Poor History)**: 2 successes, 8 failures (80% failure rate) $\rightarrow \text{Score} = 0.43$
- **Browser (Reliable History)**: 9 successes, 1 failure (10% failure rate) $\rightarrow \text{Score} = 0.74$

The planner intelligently selects **`BROWSER`** despite API's higher nominal priority.

### 6. Phase 9 Learning Integration

- **Read-Only Consumption**: The planner reads `WorkflowLearningState` (`learning_score`, `recommendation_status`, `execution_count`, `successful_execution_count`, `failed_execution_count`) to bias suitability.
- **Non-Mutating**: Phase 10 never mutates learning state directly; telemetry is updated only when the execution engine completes through existing Phase 9 services.
- **Independence**: Phase 9 learning formula and Phase 8 confidence/ranking formulas remain completely unchanged.

### 7. Safe Fallback Behavior

Every automated step in the plan determines a valid secondary fallback strategy:
- If `API` is selected, `BROWSER` or `INTEGRATION` serves as fallback.
- If no automated fallback is viable, the system designates `MANUAL` (prompting human intervention).
- Fallback paths and reasons are recorded in `StepPlan.fallback_strategy` and `StepPlan.fallback_reason`.

### 8. Safety & Explainability

- **Mandatory Approval Gate**: `requires_approval` is strictly set to `True` on every plan. The planner never executes workflows or grants self-approval.
- **Credential Protection**: External secrets, tokens, and passwords are never included in plan serialization or human-readable explanations.
- **Explainable Decisions**: Every selected strategy contains detailed justifications (`reason`, `selected_reasons`), and every rejected alternative provides transparent rejection rationale (`rejected_strategies`).

### 9. REST APIs

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/workflows/{workflow_id}/automation-plan` | Generates a deterministic automation plan for a workflow |
| `GET` | `/api/workflows/{workflow_id}/automation-plan` | Retrieves the automation plan for an existing workflow |

### 10. Known Limitations

- **No Computer Vision**: WorkFlowOS strictly avoids fake or simulated computer vision models.
- **Semantic UI Inactive**: `SEMANTIC_UI` is defined in the strategy hierarchy but marked unavailable as no accessibility driver is installed in the current environment.
- **Deterministic Heuristics**: Scoring uses rule-based heuristic weights rather than opaque machine learning models or probabilistic estimators.

---

## Running Tests

```bash
# Full test suite across all phases (359 tests)
.venv/bin/python3 -m unittest discover -s backend -p "test_*.py" -v

# Or with pytest
.venv/bin/python -m pytest -q

# Phase 10 (Intelligent Automation - 21 test scenarios)
.venv/bin/python3 -m unittest backend.test_phase10 -v

# Phase 9 (Adaptive Learning & Feedback - 24 test scenarios)
.venv/bin/python3 -m unittest backend.test_phase9 -v

# Phase 8.5 (Discovery Quality & Robustness)
.venv/bin/python3 -m unittest backend.test_phase8_5 -v

# Phase 8.4 (Explainable Discovery & Empirical Validation)
.venv/bin/python3 -m unittest backend.test_phase8_4 -v

# Phase 8.3 (Pattern Ranking, Noise Reduction & Duplicate Detection)
.venv/bin/python3 -m unittest backend.test_phase8_3 -v

# Phase 8.2 (Smarter Sequence Detection & Local Alignment)
.venv/bin/python3 -m unittest backend.test_phase8_2 -v

# Phase 8.1 (Discovery Evaluation & Confidence Scoring)
.venv/bin/python3 -m unittest backend.test_phase8_1 -v

# Phase 7.4 (Reliability, Security & Recovery)
.venv/bin/python3 -m unittest backend.test_phase7_4 -v

# Frontend Checks
npm --prefix frontend run lint
./frontend/node_modules/.bin/tsc --project frontend/tsconfig.json --noEmit
npm --prefix frontend run build
```

**Test Results (Phase 10):** 359 tests · 345 passed · 14 skipped (live OAuth required) · 0 failures.


---

## Privacy

The Phase 5 desktop agent uses **macOS NSWorkspace APIs only** for application focus tracking:
- ✅ Application name + bundle ID when you switch apps
- ❌ No keystrokes, clipboard, file contents, or screen capture
- ❌ No network calls outside your own backend (`localhost:8000` by default)
- ❌ No data sent to external services (Gemini calls are made server-side from the backend)

The agent respects an allowlist/denylist in `agent/config.py` and can be stopped at any time with `python -m agent stop`.
