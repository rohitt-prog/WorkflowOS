# WorkFlowOS — Discovery Module & Smarter Sequence Detection (Phases 2, 8.1, & 8.2)

The **Discovery** module observes recorded user activity events, identifies recurring workflows across user sessions, evaluates pattern quality against a deterministic ground-truth benchmark, and calculates transparent, calibrated confidence scores.

Discovery is a deterministic system — no LLMs, probabilistic guessing, or external APIs are used in pattern matching or confidence calculation.

---

## Architecture

```
Events (MongoDB Atlas)
    ↓
sequence.py      — Groups events by session_id, sorts chronologically, normalises to event_type verbs
    ↓
alignment.py     — Semi-global dynamic programming local alignment with Damerau transposition extension
    ↓
detector.py      — Generates candidates (full sessions, pairwise LCS, n-grams), evaluates local alignment
                   across distinct sessions, prunes shadows/subsumed slices, and ranks candidates
    ↓
confidence.py    — Calculates 5 deterministic signals + composite confidence score + human explanation
    ↓
service.py       — Orchestrates sequence fetch + repetition detection + confidence scoring
    ↓
models.py        — Pydantic response models: DiscoveredWorkflow, DiscoveryResult, ConfidenceBreakdown
    ↓
backend/routes/discovery.py  — GET /api/discovery/repeated (with optional min_confidence query param)
    ↓
evaluation.py    — Deterministic 16-scenario synthetic benchmark harness (Phase 8.1 vs Phase 8.2)
```

---

## Module Files

| File | Purpose |
|------|---------|
| `alignment.py` | Semi-global local alignment DP with Damerau transposition extension & pairwise LCS |
| `detector.py` | `RepetitionDetector` class + `detect_repeated_workflows()` with local alignment and shadow pruning |
| `confidence.py` | Calibrated deterministic signal calculation, confidence scoring, and explanations |
| `models.py` | `DiscoveredWorkflow`, `DiscoveryResult`, and `ConfidenceBreakdown` Pydantic models |
| `sequence.py` | `build_session_sequences()` and `fetch_session_sequences()` with session isolation |
| `service.py` | `DiscoveryService` — wires event retrieval, session extraction, and detection |
| `evaluation.py` | Deterministic 16-scenario synthetic evaluation dataset and comparative benchmark runner |

---

## Phase 8.2 — Smarter Sequence Detection

Phase 8.2 enhances the Discovery Engine to detect workflows embedded within longer, noisy user sessions, tolerating real-world human behavioral variations.

### 1. Algorithm Selection & Design Rationale

Standard global sequence matching (e.g. `difflib.SequenceMatcher` or global Levenshtein) fails on embedded workflows because prefix or suffix noise lowers the global similarity ratio below operational thresholds:

$$\text{Global Ratio } = \frac{2 \times \text{matches}}{\text{len}(\text{Pattern}) + \text{len}(\text{Session})}$$

If a 5-step workflow is surrounded by 5 noise actions in a 10-step session, the global ratio drops to $\frac{10}{15} = 0.667$, missing the match even though the 5-step workflow is 100% present.

**Selected Approach: Semi-Global Dynamic Programming with Damerau Transposition Extension**:
- **Free Start & End Gaps in Session**: The pattern can begin and end at any index in the session sequence without score penalty.
- **Strict Pattern Alignment**: The pattern itself must align end-to-end within the discovered sub-window.
- **Configurable Scoring**:
  - Exact Match: $+2.0$
  - Substitution / Mismatch: $-1.0$
  - Insertion in Session (extra action): $-1.0$
  - Deletion in Session (missing action): $-1.0$
  - Adjacent Step Transposition: $+1.8$ (treating adjacent step swaps like $A \to B$ vs $B \to A$ with minor penalty rather than two separate errors).
- **Coverage Requirement**: $\text{coverage} = \frac{\text{matches} + \text{transpositions}}{\text{len}(\text{pattern})} \ge 0.75$. Prevents a short 3-step pattern from losing an essential step.
- **Computational Efficiency**: $O(m \times n)$ with $m \le 15, n \le 30$. Executes in $<0.05$ milliseconds per session pair with zero external dependencies.

---

### 2. Multi-Session Candidate Generation

Candidates are extracted deterministically across the session pool:
1. **Full Qualified Sequences**: Every unique sequence from qualified sessions ($\text{length} \ge \text{min\_length}$).
2. **Pairwise Longest Common Subsequences (LCS)**: Exact LCS extracted between session pairs, automatically stripping non-shared noise actions.
3. **Frequent Contiguous N-Grams**: Contiguous slices of lengths $k \in [\text{min\_length}, \dots, 10]$ occurring across sessions.

---

### 3. Distinct-Session Occurrence Counting

- **Rule**: Each session `session_id` can contribute **at most once** to the occurrence count of a candidate pattern.
- If a user performs a 3-step workflow 5 times within a single session, the pattern occurrence count is **1**.
- Discovered workflows require support from at least `min_occurrences` (default: 2) **distinct sessions**.

---

### 4. Shadow Pruning & Distinct Workflow Separation

To prevent returning redundant sub-slices (e.g. returning both a 5-step workflow and its 3-step sub-slice), candidate deduplication enforces:

1. **Subsumption**: Candidate $C$ is subsumed by accepted workflow $A$ if $C$ is a strict subsequence of $A$, and $C$'s supporting sessions are predominantly contained in $A$'s sessions ($|C_{\text{sess}} \cap A_{\text{sess}}| / |C_{\text{sess}}| \ge 0.70$).
2. **Multi-Parent Coverage**: If $C$ is a sub-slice shared between multiple longer workflows (e.g. between Billing and Support), and all of $C$'s sessions are covered by longer workflows, $C$ is pruned as an intersection artifact.
3. **Independent Session Exception**: If candidate $C$ has at least `min_occurrences` sessions that *never executed $A$*, $C$ is recognized as an independent workflow and retained.
4. **Shared-Prefix Workflow Separation**: Distinct workflows sharing prefix steps (e.g. Billing vs. Support workflows starting with `open_email -> download_attachment`) diverge in their remaining steps; mutual similarity remains low ($< 0.40$), preserving both as distinct workflows.

---

## Deterministic Synthetic Evaluation Dataset

`discovery/evaluation.py` defines 16 standardized test scenarios with explicit ground truth:

### Phase 8.1 Regression Scenarios (1–8)
1. `scenario_1_identical_repeated`: Canonical 5-step flow across 4 sessions.
2. `scenario_2_minor_variations`: 3 sessions with 1 session containing an extra inspect step.
3. `scenario_3_unrelated_actions`: Arbitrary disconnected actions across sessions (Noise).
4. `scenario_4_incomplete_sequences`: Short bursts below minimum workflow length (< 3).
5. `scenario_5_interleaved_sessions`: Interleaved multi-session activity stream.
6. `scenario_6_frequent_common_actions`: Monotonous single action (`view_dashboard x 3`).
7. `scenario_7_missing_or_reordered`: 5-step flow with missing and swapped intermediate steps.
8. `scenario_8_distinct_workflows_no_merge`: Two distinct workflows sharing a prefix.

### Phase 8.2 Smarter Detection Scenarios (9–16)
9. `scenario_9_embedded_subsequence_with_noise`: Workflow embedded inside prefix and suffix noise.
10. `scenario_10_interleaved_inserted_actions`: Intermediate actions inserted between canonical steps.
11. `scenario_11_single_session_repetition_rejected`: Pattern repeated 3 times in 1 session; rejected due to distinct session requirement.
12. `scenario_12_adjacent_step_transpositions`: Adjacent step reordering tolerated via Damerau alignment.
13. `scenario_13_shared_prefix_distinct_workflows`: Billing and Support workflows kept separate.
14. `scenario_14_excessive_variation_rejected`: Excessive variation (>60% edit distance) rejected.
15. `scenario_15_mixture_exact_and_local`: 4 sessions combining exact, embedded, and inserted actions.
16. `scenario_16_similar_looking_distinct_workflows`: Workflows differing by a critical operational verb (`update` vs `delete`) kept separate.

---

## Comparative Benchmark Results (Phase 8.1 vs. Phase 8.2)

Evaluated across the 16-scenario dataset using `.venv/bin/python -m discovery.evaluation`:

| Metric | Phase 8.1 Baseline | Phase 8.2 Smarter Detector | Phase 8.2 (Conf $\ge$ 0.80) |
|--------|--------------------|----------------------------|-----------------------------|
| **Precision** | **92.86%** (0.9286) | **93.33%** (0.9333) | **100.0%** (1.0000) |
| **Recall** | **92.86%** (0.9286) | **100.0%** (1.0000) | **85.71%** (0.8571) |
| **F1 Score** | **0.9286** | **0.9655** | **0.9231** |
| **True Positives (TP)** | 13 | **14** (All ground-truth found) | 12 |
| **False Positives (FP)** | 1 | 1 (`view_dashboard x 3` noise) | **0** |
| **False Negatives (FN)** | 1 (Failed on embedded noise) | **0** | 2 |
| **True Negatives (TN)** | 4 | 4 | 5 |
| **Accuracy** | 89.47% | **94.74%** | 89.47% |

---

## Limitations & Trade-offs

1. **Adjacent Transpositions Only**: Step order tolerance is constrained to adjacent swaps (e.g. steps $i$ and $i+1$). Arbitrary wide reordering across distant steps is intentionally penalized to prevent false positive associations.
2. **Minimum Coverage Guard**: Patterns with length 3 require 100% of steps to match ($\text{coverage} \ge 0.75$), meaning a 3-step workflow does not tolerate missing actions. This is by design to ensure that short workflows retain structural integrity.
3. **Unsupervised Clustering Bound**: Candidate LCS generation pairs sessions up to a sliding horizon ($N \le 25$). For extreme enterprise scales ($>10,000$ concurrent sessions), prefix tree indexing or suffix arrays should be introduced in future optimization phases.

---

## Reproducing Evaluation and Tests

```bash
# Run the 16-scenario synthetic comparative benchmark
.venv/bin/python3 -m discovery.evaluation

# Run Phase 8.2 test suite
.venv/bin/python3 -m unittest backend.test_phase8_2 -v

# Run Phase 8.1 regression test suite
.venv/bin/python3 -m unittest backend.test_phase8_1 -v

# Run full backend regression suite (260+ tests)
.venv/bin/python3 -m unittest discover -s backend -p "test_*.py" -v

# Run frontend lint, typecheck, and build
npm --prefix frontend run lint
npx --prefix frontend tsc --noEmit
npm --prefix frontend run build
```
