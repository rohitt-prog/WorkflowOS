# WorkFlowOS — Discovery Module & Pattern Intelligence (Phases 2, 8.1, 8.2, 8.3, & 8.4)

The **Discovery** module observes recorded user activity events, identifies recurring workflows across user sessions, evaluates pattern quality against a deterministic ground-truth benchmark, calculates transparent confidence scores, ranks patterns by operational utility, suppresses noise, detects duplicate variants, and generates fully grounded, explainable discovery decisions.

Discovery is a deterministic system — no LLMs, probabilistic guessing, or external APIs are used in pattern matching, ranking, duplicate detection, or explainability synthesis.

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
explanation.py   — Synthesizes fully grounded, non-hallucinatory WorkflowExplanation objects from empirical metrics
    ↓
service.py       — Orchestrates sequence fetch + repetition detection + confidence scoring + ranking + explanations
    ↓
models.py        — Pydantic models: DiscoveredWorkflow, DiscoveryResult, WorkflowExplanation, ConfidenceBreakdown, RankingBreakdown
    ↓
backend/routes/discovery.py  — GET /api/discovery/repeated (with min_confidence, min_ranking_score, filter_noise, include_suppressed)
    ↓
evaluation.py    — Deterministic 10-scenario synthetic benchmark harness & explainability verification suite
```

---

## Module Files

| File | Purpose |
|------|---------|
| `alignment.py` | Semi-global local alignment DP with Damerau transposition extension & pairwise LCS |
| `detector.py` | `RepetitionDetector` class + `detect_repeated_workflows()` with local alignment, shadow pruning, and ranking |
| `confidence.py` | Calibrated deterministic signal calculation, confidence scoring, and explanations |
| `ranking.py` | Deterministic utility ranking, quality-tier categorization, noise suppression, and deduplication |
| `explanation.py`| Structured, non-hallucinatory explainability engine generating empirical `WorkflowExplanation` records |
| `models.py` | `DiscoveredWorkflow`, `DiscoveryResult`, `WorkflowExplanation`, `ConfidenceBreakdown`, and `RankingBreakdown` Pydantic models |
| `sequence.py` | `build_session_sequences()` and `fetch_session_sequences()` with session isolation |
| `service.py` | `DiscoveryService` — wires event retrieval, session extraction, detection, ranking, and explanations |
| `evaluation.py` | Deterministic 10-scenario synthetic evaluation dataset, explainability audit, and comparative benchmark runner |

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

## Phase 8.4 — Explainable Discovery

Phase 8.4 adds an explainability engine that explains discovery, confidence, ranking, and suppression decisions with 100% deterministic, grounded evidence.

### 1. Architectural Philosophy: Zero Hallucination, 100% Grounded Evidence

WorkFlowOS strictly separates observed evidence, algorithmic measurements, and heuristic utility scores:
- **No LLM Hallucinations**: Explanations are synthesized directly from actual computed metrics (session counts, alignment edit distances, entropy scores, and deduplication overlap). No generative text models are involved in explanation synthesis.
- **Empirical Grounding**: If the alignment algorithm observed 0 transpositions, the explanation reports 0 transpositions. If a sequence was suppressed for overlapping with a canonical parent, the exact overlap ratio and canonical ID are cited.
- **Explicit Heuristic Disclaimer**: Confidence and utility scores are transparently labeled as operational heuristics—never misrepresented as calibrated statistical probabilities.

---

### 2. Structured Explainability Data Model

The explainability model is represented by `WorkflowExplanation` in `discovery/explanation.py` and included in `DiscoveredWorkflow`:

```python
class WorkflowExplanation(BaseModel):
    summary: str                           # High-level human-readable discovery summary
    detection_reason: str                  # Empirical justification for qualifying as a repeated pattern
    supporting_sessions_count: int         # Total distinct supporting sessions
    supporting_session_ids: List[str]      # Privacy-masked session identifiers (e.g. "s_a1b2c3d4...")
    occurrence_evidence: OccurrenceEvidence # Session count, qualification thresholds, and multi-session ratio
    sequence_evidence: SequenceEvidence     # Exact vs approximate replay counts, insertions, deletions, transpositions
    consistency_evidence: ConsistencyEvidence # Order consistency ratio, exact replay ratio, variation ratio
    confidence_explanation: ConfidenceFactorBreakdown # Positive/negative drivers across 5 confidence signals
    ranking_explanation: RankingFactorBreakdown       # Primary drivers, limiting factors, and utility breakdown
    quality_explanation: str               # Human-readable justification for the assigned quality tier
    suppression_explanation: Optional[SuppressionEvidence] = None # Detailed rationale if candidate was suppressed
    representative_explanation: Optional[str] = None # Rationale if selected as canonical representative
    limitations: List[str]                 # Transparent disclaimers regarding heuristic scoring and scope
```

#### Detailed Evidence Sub-Models:
- **`OccurrenceEvidence`**: Captures `distinct_sessions_count`, `min_occurrences_threshold`, `total_session_pool_size`, and `session_support_ratio`.
- **`SequenceEvidence`**: Captures `sequence_length`, `average_similarity`, `exact_replays`, `approximate_replays`, `total_insertions`, `total_deletions`, and `total_transpositions`.
- **`ConsistencyEvidence`**: Tracks `order_consistency_ratio`, `exact_replay_ratio`, and `variation_ratio`.
- **`ConfidenceFactorBreakdown`**: Lists explicit `positive_factors`, `negative_factors`, and `score_breakdown` mapping the 5 Phase 8.1 signals.
- **`RankingFactorBreakdown`**: Lists `primary_drivers`, `limiting_factors`, and `signal_scores` explaining utility score $R \in [0.0, 1.0]$.
- **`SuppressionEvidence`**: Tracks `suppression_reason`, `measured_threshold`, `actual_value`, and optional `canonical_representative_id`.

---

### 3. Detection & Sequence Evidence

Detection explanations detail exactly why a sequence qualified:
- **Threshold Confirmation**: Confirms that distinct sessions $\ge \text{min\_occurrences}$ (default: 2) and pattern length $\ge \text{min\_length}$ (default: 3).
- **Exact vs. Approximate Replay**: Discloses how many sessions matched identically versus how many required local alignment tolerance.
- **Structural Variations**: Pinpoints exact counts of intermediate noise insertions, omitted steps, or adjacent step transpositions observed during local alignment.

*Example Output:*
> *"Qualified as a repeated workflow because the 5-step sequence was observed in 3 distinct user sessions (configured threshold: >= 2) with local alignment similarity averaging 94% (1/3 exact replays with 2 tolerated inserted actions). The observed similarity exceeds the 80% alignment threshold."*

---

### 4. Confidence & Ranking Explanations

- **Confidence Drivers**: Explains contributions from sequence repetition, multi-session consistency, step alignment, and length bonus. Distinguishes high-confidence flows with limited session counts (e.g. 2 sessions, 100% exact match) from flows with high session volume.
- **Ranking Drivers**: Highlights which signals drove the utility score (e.g., high step savings, high action entropy) and which signals limited the score (e.g., lower session count or imperfect alignment).
- **Quality Tier Rationale**: Explains whether a pattern is `exceptional`, `strong`, `moderate`, or `low` priority for automation.

---

### 5. Suppression & Duplicate Explanations

When candidates are suppressed or deduplicated, full evidence is preserved when `include_suppressed=true`:
- `monotonous_repeated_actions`: Reports unique action count and dominant verb percentage exceeding threshold.
- `marginal_ranking_score`: Reports measured ranking utility score failing the 0.50 threshold.
- `insufficient_occurrences`: Reports session count failing the required minimum.
- `exact_duplicate`: Points to canonical representative ID that merged the redundant candidate.
- `overlapping_shadow`: Reports the candidate sequence length, canonical parent length, and session overlap ratio ($\ge 70\%$).
- `similar_variant_overlap`: Reports alignment similarity ($\ge 80\%$) and session overlap ($\ge 50\%$) that caused deduplication to the higher-confidence representative.

*Example Shadow Suppression Output:*
> *"Suppressed as an overlapping shadow of canonical workflow 'Customer Request Processing'. This 4-step sequence is a strict sub-slice of the longer workflow and lacks sufficient independent session executions outside it."*
> - **Measured**: `4 steps (subsequence of 5-step workflow)`
> - **Criterion**: `Session overlap < 70% with super-sequence OR >= 2 independent sessions`

---

### 6. Privacy & Sensitive Data Safeguards

- **Session Masking**: Session identifiers are cryptographically hashed using SHA-256 and truncated to safe prefixed tokens (e.g. `s_4a8b1c9f...`), preventing exposure of internal user IDs or raw session keys.
- **Zero Event Payload Exposure**: Explanations operate solely on action verbs, step indices, alignment edit distances, and normalized scores. Keystrokes, clipboard data, query strings, URLs, file names, and authentication credentials are strictly excluded.

---

### 7. Frontend Explainability Experience

In the Next.js discovery interface (`DiscoveryView.tsx`):
- **Concise Card View**: Displays rank, automation score, confidence, quality badge, sequence tags, and a 1-sentence detection summary.
- **"Why was this detected?" Drawer**: An expandable accordion revealing:
  - **Fidelity & Consistency**: Exact vs. approximate replay counts, observed insertions/deletions/transpositions, and session consistency bars.
  - **Scoring Drivers & Limitations**: Green positive driver tags, amber limiting factor tags, and transparent heuristic scoring disclaimers.
  - **Suppressed Candidates Inspector**: Toggleable view of suppressed patterns with color-coded rejection badges, measured vs. criterion metrics, and links to canonical representatives.

---

## Deterministic Synthetic Evaluation Dataset

`discovery/evaluation.py` defines standardized test scenarios with explicit ground truth (evaluated through the 10-scenario synthetic benchmark harness):

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

### Phase 8.3 & 8.4 Ranking, Noise, Duplicate & Explainability Scenarios (17–24)
17. `scenario_17_exact_duplicates`: Multiple session pairs yielding duplicate candidate sequences; exactly one canonical retained with duplicate link.
18. `scenario_18_overlapping_patterns`: 4-step workflow vs 3-step prefix shadow; shadow suppressed with measured overlap evidence.
19. `scenario_19_short_valid_workflows`: Concise 3-step high-frequency workflow across 5 sessions; retained with high rank and volume explanation.
20. `scenario_20_frequent_common_action_noise`: Monotonous click loops across 6 sessions; suppressed as noise with entropy evidence.
21. `scenario_21_similar_distinct_workflows`: Same verbs applied in different business domains (`review_contract` vs `review_ticket`); both preserved with distinct domain explanations.
22. `scenario_22_support_volume_ranking`: Two valid workflows with different session adoption (7 sessions vs 2 sessions); 7-session flow ranks #1 with volume driver.
23. `scenario_23_repeated_actions_in_valid_workflow`: Legitimate repetitive workflow (`inspect -> download -> review -> review -> approve`); preserved as valid with high-entropy explanation.
24. `scenario_24_marginal_rejection`: High-noise low-consistency candidate filtered out under noise filtering with utility threshold evidence.

### Phase 8.5 Discovery Quality & Robustness Scenarios (25–33)
25. `scenario_25_optional_step_omission` (Category A): 5-step workflow where 1 session omits `download_attachment`; flow qualifies with `optional_steps` cleanly detected and explained.
26. `scenario_26_intermediate_bounded_noise` (Category B): 1-2 extraneous navigation clicks inserted between steps; bounded noise tolerance preserves workflow while bounding consecutive noise to $\le 3$.
27. `scenario_27_partial_execution_tracking` (Category C): 2 full sessions + 1 session executing only 3 of 5 steps; qualifies on 2 full sessions, with partial execution recorded in `partial_support_count` without inflating distinct session counts.
28. `scenario_28_variable_workflow_positions` (Category D): Canonical 5-step workflow at prefix (s1), middle (s2), and suffix (s3); local alignment matches independently of absolute position offset.
29. `scenario_29_intra_session_repetition` (Category E): Document editing executed twice in session 1 and once in session 2; qualifies across 2 distinct sessions, with `intra_session_repetitions = 1` recorded.
30. `scenario_30_generic_alternating_navigation_loop` (Category F): Alternating ping-pong loop (`open_tab, search_tab` x 3); active noise reduction suppresses generic repetitive navigation.
31. `scenario_31_independent_subsequences_preserved` (Category G): 3-step sub-slice appears inside 5-step flow in sessions 1-2, but independently in sessions 3-4; both are preserved without incorrect suppression.
32. `scenario_32_distinct_entity_sequences` (Category H): Similar verbs applied to distinct entities (`Customer Profile Management` vs `Product Catalog Update`); preserved as two distinct business routines.
33. `scenario_33_multiple_valid_workflows_same_session` (Category I): Order Fulfillment and Document Editing routines executed in the same sessions; neither swallows nor starves the other.

---

## Phase 8.5 — Discovery Quality & Robustness Architecture

Phase 8.5 focuses strictly on improving discovery fidelity when real user sessions contain optional steps, bounded noise, partial executions, variable positioning, and intra-session repetitions, while eliminating generic navigation false positives:

### 1. Robust Temporal Matching with Bounded Noise
- **Bounded Tolerance**: Intermediate insertions between workflow steps are tolerated up to `max_consecutive_insertions = 3`. This accommodates brief user distractions or UI notifications without allowing arbitrary unrelated work to be absorbed into a workflow.
- **Penalization**: Insertions reduce alignment similarity via the semi-global DP ratio $\frac{2 \cdot \text{matches}}{m + \text{window\_len}}$. Stretches with $> 3$ consecutive extraneous actions fail alignment criteria (`is_match = False`).

### 2. Deterministic Optional Step Detection
- Traceback through the dynamic programming matrix records `matched_pattern_indices` and `missing_pattern_indices`.
- Any pattern step present in at least one supporting session but missing in another is tagged as an optional step (`optional_steps`).
- Does not use statistical guesswork; optional steps are grounded directly in the alignment traceback.

### 3. Partial Workflow Execution Tracking
- Distinguishes between **full replay** (similarity $\ge 0.80$, coverage $\ge 0.70$), **approximate replay** (similarity $\ge 0.80$ with tolerated insertions/transpositions), and **partial support** (coverage $\in [0.35, 0.80)$, similarity $\ge 0.40$).
- Partial executions contribute supporting evidence (`partial_support_count`, `partial_support_session_ids`), but **never inflate the distinct-session qualification threshold** (`min_occurrences`).

### 4. Intra-Session Repetition Modeling
- Workflows repeating multiple times within a single session are identified via non-overlapping sub-window discovery (`find_all_local_occurrences`).
- Distinct session support remains mandatory (`occurrences` tracks distinct session IDs only).
- Additional executions are modeled separately as `intra_session_repetitions` and highlighted in explainability outputs.

### 5. False Positive Suppression for Common Navigation Patterns
- In addition to 1-action monotonous loops (`view_dashboard x 3`), Phase 8.5 suppresses 2-action alternating ping-pong cycles (`open_tab, search_tab, open_tab, search_tab`).
- Legitimate workflows containing intentional step repetitions (e.g. document reviews with multiple review comments) maintain high entropy ($> 0.35$) and are explicitly preserved.

### 6. Deterministic Representative Selection
- Candidate sorting strictly enforces a deterministic 6-factor tie-break key:
  $$(\text{confidence}, \text{ranking\_score}, \text{occurrences}, \text{length}, \text{exact\_count}, \text{tuple}(\text{sequence}))$$
- Eliminates any non-deterministic ordering caused by Python hash seeds, dictionary iterations, or set traversals.

---

## Comparative Benchmark Results (Phase 8.1 vs. Phase 8.2 vs. Phase 8.3/8.4 vs. Phase 8.5)

Evaluated across the full 33-scenario benchmark dataset using `.venv/bin/python -m discovery.evaluation`:

| Metric | Phase 8.1 Baseline | Phase 8.2 Smarter Detector | Phase 8.3/8.4 Ranked & Clean | Phase 8.5 Discovery Quality & Robustness |
|--------|--------------------|----------------------------|------------------------------|------------------------------------------|
| **Precision** | 90.32% (0.9032) | 91.67% (0.9167) | **97.06%** (0.9706) | **97.06%** (0.9706) |
| **Recall** | 84.85% (0.8485) | **100.0%** (1.0000) | **100.0%** (1.0000) | **100.0%** (1.0000) |
| **F1 Score** | 0.8750 | 0.9565 | **0.9851** | **0.9851** |
| **True Positives (TP)** | 28 | **33** | **33** | **33** |
| **False Positives (FP)** | 3 | 3 | **1** | **1** |
| **False Negatives (FN)** | 5 | **0** | **0** | **0** |
| **True Negatives (TN)** | 5 | 5 | **7** | **7** |
| **Accuracy** | 80.49% | 92.68% | **97.56%** | **97.56%** |
| **Duplicates Suppressed**| 0 | 184 | **186** | **186** |
| **Exact Replay Count** | 61 | 87 | 81 | **81** |
| **Approximate Replay Count** | 22 | 10 | 10 | **10** |
| **Partial Support Count** | 0 | 15 | 15 | **15** |
| **Optional-Step Count** | 0 | 2 | 2 | **2** |
| **Intra-Session Repetitions** | 0 | 1 | 1 | **1** |
| **Avg Alignment Similarity** | 0.9842 | 0.9923 | 0.9918 | **0.9918** |
| **Candidates Evaluated (Before/After)** | 64 / 31 | 220 / 36 | 220 / 34 | **220 / 34** |
| **Explainability Audit** | N/A | N/A | 100.0% (272/272 checks) | **100.0%** (272/272 checks passed) |

---

## Synthetic Evaluation Disclaimer & Limitations

1. **Synthetic Nature of Benchmarks**:
   - All 33 evaluation scenarios are **completely synthetic and deterministically constructed** to ensure repeatable regression testing.
   - Benchmark precision, recall, and F1 scores reflect performance on structured synthetic event streams and **do not imply equivalent accuracy on uncurated, chaotic production activity streams**.
2. **Heuristic Nature of Scoring**:
   - Ranking utility ($R \in [0.0, 1.0]$) and confidence scores are operational heuristics prioritizing automation return-on-investment; they are **not calibrated Bayesian probabilities**.
3. **Partial Execution Ambiguity**:
   - A short sequence prefix can represent a legitimately abandoned workflow or an unrelated user task. WorkFlowOS requires at least `min_occurrences` full/approximate distinct sessions before associating partial execution evidence with a workflow.
4. **Semantic Equivalence vs. String Verbs**:
   - Discovery matches based on normalized action verb identifiers (e.g. `open_email`, `search_customer`). It does not perform semantic NLP inference across unstructured text or synonyms.

---

## Phase 9 — Adaptive Learning Signal in Discovery

Phase 9 integrates feedback and execution telemetry downstream of Phase 8 without altering Phase 8 confidence or ranking calculations:

```
Discovery Candidate
       ↓
Phase 8 Confidence  (Calibrated pattern strength in [0.0, 1.0])
       ↓
Phase 8 Ranking     (Composite automation utility score R in [0.0, 1.0])
       ↓
Phase 9 Learning    (Bounded score L in [0.0, 1.0] from human review & execution telemetry)
       ↓
Recommendation Decision (NEW | LEARNING | RECOMMENDED | DEPRIORITIZED)
```

### Deterministic Learning Score Formula

$$L = \text{clamp}\Big(0.50 + 0.10 \cdot A + 0.08 \cdot E_{\text{edit}} + 0.15 \cdot X_{\text{succ}} + 0.05 \cdot C_{\text{rec}} - 0.20 \cdot R - 0.15 \cdot X_{\text{fail}} - 0.05 \cdot I,\ 0.0,\ 1.0\Big)$$

- $A$: Operator approval count ($+0.10$ each)
- $E_{\text{edit}}$: Edit and approve count ($+0.08$ each)
- $X_{\text{succ}}$: Successful execution count ($+0.15$ each)
- $C_{\text{rec}}$: Successful recovery count ($+0.05$ each)
- $R$: Rejection count ($-0.20$ each)
- $X_{\text{fail}}$: Failed execution count ($-0.15$ each)
- $I$: Intervention required count ($-0.05$ each)

### Recommendation Status Rules

- **NEW**: Total interactions $= 0$. Preserves discovery of new candidates without suppression.
- **RECOMMENDED**: $L \ge 0.70$, $A + E_{\text{edit}} \ge 1$, $X_{\text{succ}} \ge 1$, and positive signals outweigh negative signals.
- **DEPRIORITIZED**: $L < 0.40$, or ($R \ge 2$ with no successful executions), or ($X_{\text{fail}} \ge 2$ with 0 successes). Reversible upon future positive evidence.
- **LEARNING**: Active evidence accumulating between initial candidate and decisive status.

---

## Reproducing Evaluation and Tests

```bash
# Run the 33-scenario synthetic comparative benchmark with Phase 8.5 metrics
.venv/bin/python3 -m discovery.evaluation

# Run Phase 8.5 test suite (robustness, optional steps, partial execution, intra-session reps)
.venv/bin/python3 -m unittest backend.test_phase8_5 -v

# Run Phase 8.4 test suite (explainability, empirical validation, privacy safeguards)
.venv/bin/python3 -m unittest backend.test_phase8_4 -v

# Run Phase 8.3 test suite (ranking, noise reduction, duplicate detection)
.venv/bin/python3 -m unittest backend.test_phase8_3 -v

# Run Phase 8.2 test suite (local alignment & smarter detection)
.venv/bin/python3 -m unittest backend.test_phase8_2 -v

# Run Phase 8.1 regression test suite (confidence scoring)
.venv/bin/python3 -m unittest backend.test_phase8_1 -v

# Run full backend regression suite (314 tests, 0 failures)
.venv/bin/python3 -m unittest discover -s backend -p "test_*.py" -v

# Run frontend lint and production build
npm --prefix frontend run lint
npm --prefix frontend run build
```
