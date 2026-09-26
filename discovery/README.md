# WorkFlowOS — Discovery Module (Phase 2)

The **Discovery** module detects recurring workflows from recorded user activity events.
It is a fully deterministic system — no LLMs, no AI, no external APIs.

## Architecture

```
Events (MongoDB)
    ↓
sequence.py      — Groups events by session_id, sorts chronologically, normalises to event_type verbs
    ↓
detector.py      — Compares sequences across sessions; exact-match + similarity-threshold matching
    ↓
service.py       — Orchestrates fetch + detection; used by the FastAPI route
    ↓
models.py        — Pydantic response models: DiscoveredWorkflow, DiscoveryResult
    ↓
backend/routes/discovery.py  — GET /api/discovery/repeated
```

## Module Files

| File | Purpose |
|------|---------|
| `models.py` | `DiscoveredWorkflow` + `DiscoveryResult` Pydantic models |
| `sequence.py` | `build_session_sequences()` and `fetch_session_sequences()` |
| `detector.py` | `RepetitionDetector` class + `detect_repeated_workflows()` convenience fn |
| `service.py` | `DiscoveryService` — wires sequence fetch + detection |

## Sequence Normalisation

Events are normalised by **`event_type` only**.
Dynamic values (`_id`, `timestamp`, `metadata`, customer names) are discarded.

```
{ "event_type": "search_customer", "metadata": { "customer": "Rahul" } }
         ↓
"search_customer"
```

## Repetition Detection Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_length` | 3 | Minimum events in a qualifying sequence |
| `min_occurrences` | 2 | Minimum sessions sharing the pattern |
| `similarity_threshold` | 0.8 | Minimum `difflib.SequenceMatcher` ratio |

## Known Deterministic Labels

| Sequence | Label |
|----------|-------|
| `open_email → download_attachment → search_customer → update_customer → send_message` | Customer Request Processing |
| `search_customer → update_customer → send_message` | Customer Account Tier Update |
| `open_email → download_attachment` | Attachment Retrieval Routine |
| *(other)* | Repeated Workflow |

## API

### `GET /api/discovery/repeated`

**Optional query params:**
- `min_length` (int, default 3)
- `min_occurrences` (int, default 2)
- `similarity_threshold` (float, default 0.8)

**Success response:**
```json
{
  "detected": true,
  "workflows": [
    {
      "label": "Customer Request Processing",
      "sequence": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
      "occurrences": 3,
      "similarity": 1.0,
      "session_ids": ["session_001", "session_002", "session_003"]
    }
  ]
}
```

**No pattern:**
```json
{ "detected": false, "workflows": [] }
```

## Development Test Data

Seed 3 identical sessions (Rahul, Priya, Amit) explicitly:

```bash
python backend/test_event.py --seed-workflows
```

> **IMPORTANT:** This is NOT triggered automatically. Run it manually when you need test data.

Then verify detection:

```bash
curl http://localhost:8000/api/discovery/repeated
```

## Phase Boundaries

- **Phase 2 (this module):** Deterministic repetition detection, no AI.
- **Phase 3 (future):** AI-generated intent labels, suggested automation scripts.
- **Phase 4 (future):** Automation execution via Playwright.
