# WorkFlowOS — Evaluation & Benchmarking System (Phase 15)

## 1. Benchmark Purpose

Phase 15 provides an objective, reproducible evaluation harness for WorkFlowOS. It benchmarks the quality, reliability, safety, and performance of existing system pipelines (Phases 1 through 14) against explicit ground truth specifications.

> **Notice**: This benchmark evaluates deterministic system behavior on a controlled synthetic dataset. It does not establish real-world production accuracy.

---

## 2. Dataset Structure

The benchmark suite defines 10 operational scenarios (**Scenarios A through J**) representing realistic desktop activity patterns:

- **Scenario A (Customer Support)**: Canonical 5-step workflow repeated across 3 user sessions (`open_email`, `download_attachment`, `search_customer`, `update_customer`, `send_message`).
- **Scenario B (Repeated Minor Variation)**: Canonical workflow repeated with an optional step omitted (`download_attachment`).
- **Scenario C (Similar but Distinct)**: Two structurally similar workflows (`search_customer -> update_customer -> send_message` vs `search_customer -> cancel_order -> send_message`) that must remain separate.
- **Scenario D (Noise Insertion)**: Canonical workflow embedded with non-workflow navigation clicks (`view_notifications`, `click_settings`).
- **Scenario E (Short Sequence Negative)**: 2-step sequences below the `min_length=3` threshold; must be rejected.
- **Scenario F (Single Occurrence Negative)**: 1-occurrence workflow below the `min_occurrences=2` threshold; must be rejected.
- **Scenario G (Multiple Sessions Isolation)**: Disjoint sub-sequences across sessions verifying session isolation.
- **Scenario H (Mutating Workflow)**: Workflow with mutating steps enforcing mandatory approval.
- **Scenario I (Unknown Action Safety)**: Workflow containing an unregistered action (`unknown_custom_action_xyz`); must fail closed.
- **Scenario J (Unknown Application Safety)**: Workflow targeting an unregistered application; must be rejected.

---

## 3. Ground Truth

Every scenario in `evaluation/datasets/scenarios.py` defines deterministic `GroundTruth` expectations:
- `expected_detected`: `bool`
- `expected_workflows`: List of `ExpectedWorkflow` definitions
- `requires_approval`: `bool`
- `is_executable`: `bool`
- `fail_closed`: `bool`

Ground truth is completely deterministic and synthetic without LLM generation or PII.

---

## 4. Evaluated Metrics

### 4.1 Discovery Classification
- **Precision**: $\frac{\text{TP}}{\text{TP} + \text{FP}}$
- **Recall**: $\frac{\text{TP}}{\text{TP} + \text{FN}}$
- **F1 Score**: $\frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$
- **Accuracy**: $\frac{\text{TP} + \text{TN}}{\text{TP} + \text{FP} + \text{FN} + \text{TN}}$

### 4.2 Ranking
- **Top-1 Accuracy**: Proportion where expected workflow is ranked #1.
- **Top-k Recall**: Proportion where expected workflow is in top-$k$ ($k=3$).
- **Mean Reciprocal Rank (MRR)**: $\frac{1}{N} \sum_{i=1}^N \frac{1}{\text{rank}_i}$

### 4.3 Confidence Calibration
- Mean confidence for correct predictions vs mean confidence for incorrect predictions ($\Delta = \text{Mean}_{\text{correct}} - \text{Mean}_{\text{incorrect}}$).

### 4.4 Explainability
- Structural coverage of explanation fields: $\frac{\text{explanations\_present}}{\text{explanations\_expected}}$.

### 4.5 Safety & Privacy
- Zero approval bypass enforcement.
- Fail-closed handling for unknown actions and unknown applications.
- Secret scanning of all benchmark outputs and serialized records.
- Verification of PII redaction and retention window calculation.

---

## 5. Workflow Matching Rules

Predicted workflows are matched to ground truth using action sequence similarity calculated via `difflib.SequenceMatcher`:
- Match threshold: $\ge 0.80$ similarity to ground truth sequence.
- Distinct session constraint: Minimum 2 distinct session occurrences required for detection.

---

## 6. Reproducibility & Benchmark Command

To execute the complete benchmark suite:

```bash
python -m evaluation.run
```

Or using the virtual environment:

```bash
.venv/bin/python -m evaluation.run
```

The benchmark runner uses a fixed deterministic seed (`seed=42`) and outputs:
- Machine-readable JSON: `evaluation/reports/benchmark_results.json`
- Human-readable Markdown: `evaluation/reports/phase15_report.md`

---

## 7. Limitations

1. **Synthetic Scenarios**: The benchmark dataset contains 10 structured synthetic scenarios; it is not a statistical sample of arbitrary enterprise workflows.
2. **Local Hardware Timing**: Latencies reflect local development hardware (macOS / Apple Silicon) and do not represent cloud infrastructure SLAs.
3. **Deterministic Scope**: Generative LLM responses are decoupled from offline benchmark suites to guarantee 100% deterministic test execution.
4. **Mock Execution**: Automation execution tests run using `NoOpExecutor` to prevent side-effects on real third-party services.
