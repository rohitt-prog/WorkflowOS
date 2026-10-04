# WorkFlowOS — Discovery Module & Pattern Intelligence (Phases 2, 8.1, 8.2, & 8.3)

The **Discovery** module observes recorded user activity events, identifies recurring workflows across user sessions, evaluates pattern quality against a deterministic ground-truth benchmark, calculates transparent confidence scores, ranks patterns by operational utility, suppresses noise, and detects duplicate variants.

Discovery is a deterministic system — no LLMs, probabilistic guessing, or external APIs are used in pattern matching, ranking, or duplicate detection.

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
                   across distinct sessions, prunes shadows, and orchestrates ranking & deduplication
    ↓
confidence.py    — Calculates 5 deterministic signals + composite confidence score + human explanation
    ↓
ranking.py       — Evaluates automation utility ($R \in [0.0, 1.0]$), assigns quality tiers, suppresses noise,
                   and detects exact duplicates and overlapping variants
    ↓
service.py       — Orchestrates sequence fetch + repetition detection + confidence scoring + ranking
    ↓
models.py        — Pydantic models: DiscoveredWorkflow, DiscoveryResult, ConfidenceBreakdown, RankingBreakdown
    ↓
backend/routes/discovery.py  — GET /api/discovery/repeated (with min_confidence, min_ranking_score, filter_noise)
    ↓
evaluation.py    — Deterministic 24-scenario synthetic benchmark harness (Phase 8.1 vs 8.2 vs 8.3)
```

---

## Module Files

| File | Purpose |
|------|---------|
| `alignment.py` | Semi-global local alignment DP with Damerau transposition extension & pairwise LCS |
| `detector.py` | `RepetitionDetector` class + `detect_repeated_workflows()` with local alignment and shadow pruning |
| `confidence.py` | Calibrated deterministic signal calculation, confidence scoring, and explanations |
| `ranking.py` | Deterministic utility ranking, quality-tier categorization, noise suppression, and deduplication |
| `models.py` | `DiscoveredWorkflow`, `DiscoveryResult`, `ConfidenceBreakdown`, and `RankingBreakdown` Pydantic models |
| `sequence.py` | `build_session_sequences()` and `fetch_session_sequences()` with session isolation |
| `service.py` | `DiscoveryService` — wires event retrieval, session extraction, detection, and ranking |
| `evaluation.py` | Deterministic 24-scenario synthetic evaluation dataset and comparative benchmark runner |

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

---

## Phase 8.3 — Pattern Ranking, Noise Reduction & Duplicate Detection

Phase 8.3 introduces an automated ranking system, active noise reduction, and duplicate variant suppression to ensure operators review high-impact, clean, representative workflows.

### 1. Deterministic Pattern Ranking

The ranking score $R \in [0.0, 1.0]$ evaluates a pattern's **operational automation usefulness**, keeping ranking cleanly separated from detection confidence. It combines five normalized, non-redundant signals whose weights strictly sum to 1.00:

$$R = 0.30 \cdot S_{\text{conf}} + 0.25 \cdot S_{\text{fidelity}} + 0.20 \cdot S_{\text{volume}} + 0.15 \cdot S_{\text{impact}} + 0.10 \cdot S_{\text{richness}}$$

| Contributing Signal | Weight | Definition & Normalization |
|---------------------|--------|----------------------------|
| **Pattern Confidence ($S_{\text{conf}}$)** | 0.30 | Intrinsic confidence score from Phase 8.1 / 8.2 local alignment matching. |
| **Execution Fidelity ($S_{\text{fidelity}}$)** | 0.25 | Composite alignment fidelity ($0.60 \times \text{alignment} + 0.40 \times \text{consistency}$). |
| **Operational Volume ($S_{\text{volume}}$)** | 0.20 | Distinct session count, normalized linearly: $\min(1.0, \frac{\text{distinct\_sessions} - 2}{5})$. |
| **Automation Impact ($S_{\text{impact}}$)** | 0.15 | Step length savings potential, normalized linearly: $\min(1.0, \frac{\text{len}(\text{pattern}) - 3}{2})$. |
| **Task Richness ($S_{\text{richness}}$)** | 0.10 | Action diversity entropy: ratio of unique verbs in the sequence. |

- **Deterministic Tie-Breaking**: Sorting guarantees identical output ordering on equivalent inputs:
  1. `ranking_score` (descending)
  2. `confidence` (descending)
  3. `occurrences` (descending)
  4. `sequence_length` (descending)
  5. `tuple(sequence)` (lexicographical descending)

### 2. Quality Tiers & Natural Explanations

Each workflow is assigned a discrete quality tier based on its ranking score:
- **`exceptional` ($\ge 0.85$)**: High automation priority; high fidelity across many sessions with substantial task length.
- **`strong` ($0.70 \le R < 0.85$)**: High value routine with solid multi-session support and consistency.
- **`moderate` ($0.55 \le R < 0.70$)**: Viable candidate; modest session support or short sequence.
- **`low` ($< 0.55$)**: Low automation priority or marginal execution consistency.

Natural text explanations summarize key drivers (e.g., *"Top-tier candidate (#1) with high multi-session adoption (7 sessions) and substantial automation impact (5 steps). Execution fidelity is 100%."*).

### 3. Noise Reduction

Low-value patterns are identified and flagged or suppressed with human-readable reasons:
- **Monotonous Single-Action Loops**: Sequences dominated by a single repeated action (e.g. `view_dashboard x 3`) are penalized in task richness and assigned suppression reason `monotonous_repeated_actions`.
- **Marginal Utility**: Candidates with ranking score below configurable `min_ranking_score` (default: 0.50 when filtering active) are assigned `marginal_ranking_score`.
- **Short / Weak Support**: Sequences with fewer than `min_occurrences` distinct sessions or below `min_length` are rejected.
- **Legitimate Workflows Preserved**: Valid multi-step workflows that happen to contain repeated actions (e.g. `open_email -> download_attachment -> review_file -> review_file -> reply_email`) maintain high entropy ($> 0.60$) and are preserved.

### 4. Duplicate & Overlapping Pattern Detection

When multiple candidates describe essentially the same workflow, deduplication selects the canonical representative and suppresses variants:
- **Exact Duplicates**: Identical action sequences are pruned; the canonical pattern retains all session IDs with `suppression_reason = "exact_duplicate"`.
- **Overlapping Shadows**: Shorter sub-sequences whose supporting sessions are $\ge 70\%$ contained within a longer accepted workflow are suppressed with `suppression_reason = "overlapping_shadow"` and linked via `representative_pattern_id`.
- **Near-Duplicate Variants**: Sequences with $\ge 80\%$ alignment similarity that share $\ge 50\%$ session overlap are suppressed with `suppression_reason = "similar_variant_overlap"`.
- **Representative Selection**: The canonical pattern is selected via candidate sorting by `confidence` (ensuring uncorrupted sequences are chosen over noisy variants) and `ranking_score`.
- **Independent Sub-Sequence Protection**: If a sub-sequence occurs independently in $\ge \text{min\_occurrences}$ sessions outside the longer workflow, it is recognized as a legitimate standalone workflow and retained.

---

## Deterministic Synthetic Evaluation Dataset

`discovery/evaluation.py` defines 24 standardized test scenarios with explicit ground truth:

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
11. `scenario_11_single_session_repetition_rejected`: Pattern repeated 3 times in 1 session; rejected.
12. `scenario_12_adjacent_step_transpositions`: Adjacent step reordering tolerated via Damerau alignment.
13. `scenario_13_shared_prefix_distinct_workflows`: Billing and Support workflows kept separate.
14. `scenario_14_excessive_variation_rejected`: Excessive variation (>60% edit distance) rejected.
15. `scenario_15_mixture_exact_and_local`: 4 sessions combining exact, embedded, and inserted actions.
16. `scenario_16_similar_looking_distinct_workflows`: Workflows differing by a critical operational verb kept separate.

### Phase 8.3 Ranking, Noise & Duplicate Scenarios (17–24)
17. `scenario_17_exact_duplicates`: Multiple session pairs yielding duplicate candidate sequences; exactly one canonical retained.
18. `scenario_18_overlapping_patterns`: 4-step workflow vs 3-step prefix shadow; shadow suppressed with representative pointer.
19. `scenario_19_short_valid_workflows`: Concise 3-step high-frequency workflow across 5 sessions; retained with high rank.
20. `scenario_20_frequent_common_action_noise`: Monotonous click loops across 6 sessions; suppressed as noise.
21. `scenario_21_similar_distinct_workflows`: Same verbs applied in different business domains (`review_contract` vs `review_ticket`); both preserved.
22. `scenario_22_support_volume_ranking`: Two valid workflows with different session adoption (7 sessions vs 2 sessions); 7-session flow ranks #1.
23. `scenario_23_repeated_actions_in_valid_workflow`: Legitimate repetitive workflow (`inspect -> download -> review -> review -> approve`); preserved as valid.
24. `scenario_24_marginal_rejection`: High-noise low-consistency candidate filtered out under noise filtering.

---

## Comparative Benchmark Results (Phase 8.1 vs. Phase 8.2 vs. Phase 8.3)

Evaluated across the 24-scenario benchmark dataset using `.venv/bin/python -m discovery.evaluation`:

| Metric | Phase 8.1 Baseline | Phase 8.2 Smarter Detector | Phase 8.3 (Ranking & Noise Reduction) |
|--------|--------------------|----------------------------|---------------------------------------|
| **Precision** | 91.30% (0.9130) | 91.67% (0.9167) | **100.0%** (1.0000) |
| **Recall** | 95.45% (0.9545) | **100.0%** (1.0000) | **100.0%** (1.0000) |
| **F1 Score** | 0.9333 | 0.9565 | **1.0000** |
| **True Positives (TP)** | 21 | **22** (All ground-truth found) | **22** (All ground-truth found) |
| **False Positives (FP)** | 2 (Embedded noise & monotonous loops) | 2 (Monotonous loops) | **0** (All noise suppressed) |
| **False Negatives (FN)** | 1 (Failed embedded noise) | **0** | **0** |
| **True Negatives (TN)** | 5 | 5 | **7** |
| **Accuracy** | 89.66% | 93.10% | **100.0%** |
| **Duplicates Suppressed**| 0 | 114 | **123** (Exact, shadow, & variant deduplicated) |

---

## Limitations & Trade-offs

1. **Heuristic Ranking vs. Calibrated Probability**: The ranking score ($R \in [0.0, 1.0]$) represents a multi-factor operational utility heuristic; it is not a statistical probability of workflow correctness.
2. **Subsumption Session Overlap Cutoff**: Overlapping shadows require $\ge 70\%$ session overlap with the candidate super-sequence to be suppressed. Sub-sequences with independent utility across separate sessions are deliberately preserved.
3. **Monotonous Noise Guard**: Actions repeated $> 50\%$ in a sequence are penalized, but structured workflows with intentional loops (e.g. multi-review flows) require distinct enclosing actions to maintain acceptable entropy.
4. **Local Scale**: Candidate generation and deduplication scales comfortably up to hundreds of sessions ($<0.05$s execution). Massive enterprise session corpora ($>10,000$ daily sessions) will benefit from prefix tree or suffix array indexing in future phases.

---

## Reproducing Evaluation and Tests

```bash
# Run the 24-scenario synthetic comparative benchmark (Phase 8.1 vs 8.2 vs 8.3)
.venv/bin/python3 -m discovery.evaluation

# Run Phase 8.3 test suite (ranking, noise reduction, duplicate detection)
.venv/bin/python3 -m unittest backend.test_phase8_3 -v

# Run Phase 8.2 test suite (local alignment & smarter detection)
.venv/bin/python3 -m unittest backend.test_phase8_2 -v

# Run Phase 8.1 regression test suite (confidence scoring)
.venv/bin/python3 -m unittest backend.test_phase8_1 -v

# Run full backend regression suite (282 tests, 0 failures)
.venv/bin/python3 -m unittest discover -s backend -p "test_*.py" -v

# Run frontend lint, typecheck, and build
npm --prefix frontend run lint
frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json
npm --prefix frontend run build
```
