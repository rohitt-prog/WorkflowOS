# WorkFlowOS — Discovery Module & Confidence Scoring (Phases 2 & 8.1)

The **Discovery** module observes recorded user activity events, identifies recurring workflows across user sessions, evaluates pattern quality against a deterministic ground-truth benchmark, and calculates transparent, calibrated confidence scores.

Discovery is a deterministic system — no LLMs, probabilistic guessing, or external APIs are used in pattern matching or confidence calculation.

---

## Architecture

```
Events (MongoDB Atlas)
    ↓
sequence.py      — Groups events by session_id, sorts chronologically, normalises to event_type verbs
    ↓
detector.py      — Compares sequences across sessions; exact clustering + SequenceMatcher similarity
    ↓
confidence.py    — Calculates 5 deterministic signals + composite confidence score + human explanation
    ↓
service.py       — Orchestrates sequence fetch + repetition detection + confidence scoring
    ↓
models.py        — Pydantic response models: DiscoveredWorkflow, DiscoveryResult, ConfidenceBreakdown
    ↓
backend/routes/discovery.py  — GET /api/discovery/repeated (with optional min_confidence query param)
    ↓
evaluation.py    — Deterministic 8-scenario synthetic benchmark harness (Precision, Recall, F1)
```

---

## Module Files

| File | Purpose |
|------|---------|
| `models.py` | `DiscoveredWorkflow`, `DiscoveryResult`, and `ConfidenceBreakdown` Pydantic models |
| `sequence.py` | `build_session_sequences()` and `fetch_session_sequences()` with session isolation |
| `detector.py` | `RepetitionDetector` class + `detect_repeated_workflows()` with confidence ranking |
| `confidence.py` | Calibrated deterministic signal calculation, confidence scoring, and explanations |
| `service.py` | `DiscoveryService` — wires event retrieval, session extraction, and detection |
| `evaluation.py` | Deterministic synthetic evaluation dataset and benchmark runner |

---

## Sequence Normalisation & Session Isolation

Events are normalised strictly by **`event_type`**. Dynamic runtime parameters (`_id`, `timestamp`, `metadata`, customer names) are stripped to prevent overfitting to session-specific data.

```
{ "session_id": "s1", "event_type": "search_customer", "metadata": { "customer": "Rahul" } }
         ↓
"search_customer"
```

Multi-session activity arriving in an interleaved chronological stream is partitioned cleanly by `session_id`. Actions within a session are ordered strictly by timestamp.

---

## Phase 8.1 — Confidence Scoring System

Confidence in WorkFlowOS is a deterministic, normalized index $C \in [0.0, 1.0]$ measuring empirical evidence that a detected sequence represents an intentional, automatable workflow rather than random noise or monotonous loops.

### The Five Deterministic Signals

Each signal is normalized to $[0.0, 1.0]$ and assigned a clear, justified weight:

$$\text{Confidence } C = \sum_{k} w_k S_k = 0.30 S_{\text{rep}} + 0.25 S_{\text{sim}} + 0.20 S_{\text{div}} + 0.15 S_{\text{len}} + 0.10 S_{\text{cons}}$$

```
┌─────────────────────────────────┬────────┬────────────────────────────────────────────────────────┐
│ Signal                          │ Weight │ Description & Formula                                  │
├─────────────────────────────────┼────────┼────────────────────────────────────────────────────────┤
│ Repetition Support (S_rep)      │  0.30  │ Volume of observations across distinct sessions.       │
│                                 │        │ S_rep = min(1.0, 0.50 + 0.50 * (N - 2) / 3) for N >= 2 │
├─────────────────────────────────┼────────┼────────────────────────────────────────────────────────┤
│ Sequence Similarity (S_sim)     │  0.25  │ Average SequenceMatcher alignment across sessions.     │
│                                 │        │ S_sim = 0.60 + 0.40 * (avg_sim - 0.80) / 0.20          │
├─────────────────────────────────┼────────┼────────────────────────────────────────────────────────┤
│ Action Diversity (S_div)        │  0.20  │ Unique actions ratio; penalizes low-entropy repetition │
│                                 │        │ U=1 -> 0.10 (severe penalty for view x 3 loops)        │
│                                 │        │ U>1 -> 0.10 + 0.90 * (U - 1) / (L - 1)                 │
├─────────────────────────────────┼────────┼────────────────────────────────────────────────────────┤
│ Sequence Length (S_len)         │  0.15  │ Task complexity and intentionality.                    │
│                                 │        │ L=3 -> 0.60, L=4 -> 0.80, L>=5 -> 1.00                 │
├─────────────────────────────────┼────────┼────────────────────────────────────────────────────────┤
│ Session Consistency (S_cons)    │  0.10  │ Proportion of exact 1.0 match sessions.                │
│                                 │        │ S_cons = 0.50 + 0.50 * (exact_matches / N)             │
└─────────────────────────────────┴────────┴────────────────────────────────────────────────────────┘
```

### Confidence Tiers
- **`high` ($\ge 0.80$)**: Strong candidate for operator review and workflow proposal.
- **`medium` ($0.65 \le C < 0.80$)**: Moderate evidence; minor variations or short sequence.
- **`low` ($< 0.65$)**: Low evidence, insufficient repetitions, or low-entropy single-action noise.

### Deterministic Explanation
The engine synthesizes an explainable, non-probabilistic textual rationale:
> *"High confidence (95%): robust session support (4 sessions), identical sequence alignment (100%), high action variety (5/5 distinct steps)."*

---

## Deterministic Synthetic Evaluation Dataset

`discovery/evaluation.py` defines 8 standardized test scenarios with explicit ground truth:

1. **`scenario_1_identical_repeated`**: Canonical 5-step customer inquiry processing repeated across 4 sessions.
   - *Expected:* Detected (TP=1), High confidence (~0.95).
2. **`scenario_2_minor_variations`**: 3 sessions with 1 session containing an extra inspect step (similarity ~0.95).
   - *Expected:* Detected (TP=1), Medium confidence (~0.80).
3. **`scenario_3_unrelated_actions`**: Arbitrary disconnected actions across sessions with no overlap.
   - *Expected:* Not detected (TN=1).
4. **`scenario_4_incomplete_sequences`**: Short bursts below minimum workflow length threshold.
   - *Expected:* Not detected (TN=1).
5. **`scenario_5_interleaved_sessions`**: Events from 2 separate sessions arriving interleaved in time.
   - *Expected:* Partitioned cleanly by session, detected (TP=1), Medium confidence (~0.79).
6. **`scenario_6_frequent_common_actions`**: Monotonous single action (`view_dashboard` repeated 3 times).
   - *Expected:* Monotonous low-entropy noise should not form an automated workflow.
   - *Engine Result:* Detected at baseline as FP, but penalized by confidence scoring to 0.66 (action_diversity=0.10).
7. **`scenario_7_missing_or_reordered`**: 5-step workflow with missing and swapped intermediate steps across sessions.
   - *Expected:* Detected (TP=1), High confidence (~0.81).
8. **`scenario_8_distinct_workflows_no_merge`**: Two separate workflows (Billing vs Support) sharing a prefix.
   - *Expected:* Two distinct workflows detected without improper merging (TP=2).

---

## Baseline vs. Confidence-Filtered Benchmark

Evaluated using `python -m discovery.evaluation`:

| Metric | Default Baseline (Min Length=3, Min Occur=2, Sim=0.8) | High Confidence Filter (`min_confidence=0.80`) |
|--------|------------------------------------------------------|------------------------------------------------|
| **Precision** | **85.71%** (0.8571) | **100.0%** (1.0000) |
| **Recall** | **100.0%** (1.0000) | **66.67%** (0.6667) |
| **F1 Score** | **0.9231** | **0.8000** |
| **True Positives (TP)** | 6 | 4 |
| **False Positives (FP)** | 1 (`view_dashboard x 3` monotonous loop) | 0 |
| **False Negatives (FN)** | 0 | 2 (Scenarios with 2-3 sessions & variations) |
| **True Negatives (TN)** | 2 | 3 |

### Ground-Truth Metric Definitions:
- **True Positive (TP)**: Expected workflow sequence detected with SequenceMatcher ratio $\ge 0.80$ against ground truth.
- **False Positive (FP)**: Spurious workflow detected in negative scenario, or distinct workflows erroneously merged.
- **False Negative (FN)**: Expected ground truth workflow omitted from detection results.
- **True Negative (TN)**: Negative scenario where engine correctly reports `detected=False` with 0 workflows.

---

## API Reference

### `GET /api/discovery/repeated`

**Query Parameters:**
- `min_length` (int, default `3`): Minimum sequence length.
- `min_occurrences` (int, default `2`): Minimum distinct session occurrences.
- `similarity_threshold` (float, default `0.8`): Minimum sequence similarity ratio.
- `min_confidence` (float, optional): Filter returned workflows by minimum confidence score.

**Response Example:**
```json
{
  "detected": true,
  "workflows": [
    {
      "label": "Customer Request Processing",
      "sequence": [
        "open_email",
        "download_attachment",
        "search_customer",
        "update_customer",
        "send_message"
      ],
      "occurrences": 4,
      "similarity": 1.0,
      "session_ids": ["session_101", "session_102", "session_103", "session_104"],
      "confidence": 0.95,
      "confidence_tier": "high",
      "confidence_breakdown": {
        "repetition_support": 0.8333,
        "sequence_similarity": 1.0,
        "action_diversity": 1.0,
        "sequence_length": 1.0,
        "session_consistency": 1.0,
        "raw_signals": {
          "occurrences": 4,
          "length": 5,
          "unique_actions": 5,
          "avg_similarity": 1.0,
          "exact_matches_count": 4
        }
      },
      "confidence_explanation": "High confidence (95%): robust session support (4 sessions), identical sequence alignment (100%), high action variety (5/5 distinct steps)."
    }
  ]
}
```

---

## Limitations & Known Failure Cases

1. **Fixed Sliding Window Clustering**: Patterns embedded inside very long sessions without clean delimiter markers rely on exact cluster sorting rather than local alignment (targeted for Phase 8.2).
2. **Low-Entropy Repetitive Loops**: In default mode (no `min_confidence` filter), sequences like `[view, view, view]` pass the structural occurrence threshold; confidence scoring penalizes their diversity to 0.10 and drops confidence to 0.66, but filtering requires passing `min_confidence >= 0.70` or checking `confidence_tier`.
3. **Reordered Intermediate Steps**: Levenshtein / SequenceMatcher handles insertions and deletions well, but penalizes adjacent step transpositions more heavily than human semantic equivalence would suggest.

---

## Reproducing Evaluation and Tests

```bash
# Run the synthetic evaluation benchmark
.venv/bin/python3 -m discovery.evaluation

# Run Phase 8.1 test suite
.venv/bin/python3 -m unittest backend.test_phase8_1 -v

# Run full backend regression suite
.venv/bin/python3 -m unittest discover -s backend -p "test_*.py" -v

# Run frontend lint, typecheck, and build
npm --prefix frontend run lint
./frontend/node_modules/.bin/tsc --project frontend --noEmit
npm --prefix frontend run build
```
