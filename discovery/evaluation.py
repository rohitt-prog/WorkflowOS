"""
WorkFlowOS Phase 8.1: Discovery Evaluation Framework & Synthetic Dataset

Defines:
1. Deterministic synthetic evaluation dataset covering 8 distinct operational scenarios.
2. Ground-truth workflow definitions and expected detection outcomes.
3. Rigorous evaluation harness calculating Precision, Recall, F1, TP, FP, FN, and TN.
4. Baseline benchmark execution for the existing Phase 2 RepetitionDetector.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
import json

from discovery.detector import RepetitionDetector, detect_repeated_workflows, compute_sequence_similarity
from discovery.models import DiscoveryResult, DiscoveredWorkflow
from discovery.sequence import build_session_sequences


@dataclass
class GroundTruthWorkflow:
    """Expected workflow specification within an evaluation scenario."""
    sequence: List[str]
    min_occurrences: int
    label: Optional[str] = None


@dataclass
class EvaluationScenario:
    """A single deterministic test scenario with explicit ground truth."""
    scenario_id: str
    name: str
    description: str
    session_sequences: Dict[str, List[str]]
    expected_detected: bool
    expected_workflows: List[GroundTruthWorkflow] = field(default_factory=list)
    raw_events: Optional[List[Dict[str, Any]]] = None
    category: str = "general"


def build_synthetic_evaluation_dataset() -> List[EvaluationScenario]:
    """
    Constructs the 8 deterministic evaluation scenarios mandated by Phase 8.1.
    All data is completely synthetic with no PII.
    """
    scenarios: List[EvaluationScenario] = []

    # -------------------------------------------------------------------------
    # Scenario 1: Identical Repeated Workflows
    # Canonical customer inquiry processing repeated exactly across 4 distinct sessions.
    # -------------------------------------------------------------------------
    canonical_5_step = [
        "open_email",
        "download_attachment",
        "search_customer",
        "update_customer",
        "send_message",
    ]
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_1_identical_repeated",
            name="Identical Repeated Workflows",
            description="Exact 5-step canonical sequence repeated across 4 separate user sessions.",
            session_sequences={
                "session_101": list(canonical_5_step),
                "session_102": list(canonical_5_step),
                "session_103": list(canonical_5_step),
                "session_104": list(canonical_5_step),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=4, label="Customer Request Processing")
            ],
            category="repeated_exact",
        )
    )

    # -------------------------------------------------------------------------
    # Scenario 2: Similar Sequences with Minor Variations
    # 3 sessions: 2 exact, 1 session with an extra intermediate view step (similarity >= 0.8).
    # -------------------------------------------------------------------------
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_2_minor_variations",
            name="Similar Sequences with Minor Variations",
            description="3 sessions where 1 session contains an extra inspect step (similarity ~0.83).",
            session_sequences={
                "session_201": [
                    "search_customer",
                    "update_customer",
                    "send_message",
                ],
                "session_202": [
                    "search_customer",
                    "view_customer_notes",
                    "update_customer",
                    "send_message",
                ],
                "session_203": [
                    "search_customer",
                    "update_customer",
                    "send_message",
                ],
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(
                    sequence=["search_customer", "update_customer", "send_message"],
                    min_occurrences=3,
                    label="Customer Account Tier Update",
                )
            ],
            category="variation",
        )
    )

    # -------------------------------------------------------------------------
    # Scenario 3: Unrelated Actions that Should NOT Form a Workflow
    # Disparate, arbitrary system actions across sessions that share no structural overlap.
    # -------------------------------------------------------------------------
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_3_unrelated_actions",
            name="Unrelated Actions (Noise Only)",
            description="Completely distinct random actions across sessions that should never form a workflow.",
            session_sequences={
                "session_301": ["open_settings", "export_log", "view_dashboard"],
                "session_302": ["delete_cache", "refresh_feed", "edit_profile"],
                "session_303": ["print_page", "scroll_down", "zoom_in"],
            },
            expected_detected=False,
            expected_workflows=[],
            category="negative_noise",
        )
    )

    # -------------------------------------------------------------------------
    # Scenario 4: Incomplete Sequences (Below min_length or truncated)
    # Very short action bursts (lengths 1 and 2) that do not reach meaningful length.
    # -------------------------------------------------------------------------
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_4_incomplete_sequences",
            name="Incomplete / Truncated Sequences",
            description="Sessions with 1 or 2 actions only (below minimum workflow length threshold).",
            session_sequences={
                "session_401": ["open_email"],
                "session_402": ["open_email", "download_attachment"],
                "session_403": ["open_email"],
            },
            expected_detected=False,
            expected_workflows=[],
            category="negative_incomplete",
        )
    )

    # -------------------------------------------------------------------------
    # Scenario 5: Interleaved Activity from Separate Sessions
    # Events from 2 distinct sessions arriving interleaved in time.
    # When correctly grouped by session_id, they form a repeated 3-step workflow.
    # -------------------------------------------------------------------------
    interleaved_events = [
        {"session_id": "session_alpha", "timestamp": "2026-10-04T10:00:00Z", "event_type": "search_customer"},
        {"session_id": "session_beta", "timestamp": "2026-10-04T10:00:01Z", "event_type": "search_customer"},
        {"session_id": "session_alpha", "timestamp": "2026-10-04T10:00:02Z", "event_type": "update_customer"},
        {"session_id": "session_beta", "timestamp": "2026-10-04T10:00:03Z", "event_type": "update_customer"},
        {"session_id": "session_alpha", "timestamp": "2026-10-04T10:00:04Z", "event_type": "send_message"},
        {"session_id": "session_beta", "timestamp": "2026-10-04T10:00:05Z", "event_type": "send_message"},
    ]
    interleaved_session_seqs = build_session_sequences(interleaved_events)
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_5_interleaved_sessions",
            name="Interleaved Multi-Session Activity",
            description="Events interleaved across sessions in chronological stream; must partition cleanly.",
            session_sequences=interleaved_session_seqs,
            raw_events=interleaved_events,
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(
                    sequence=["search_customer", "update_customer", "send_message"],
                    min_occurrences=2,
                    label="Customer Account Tier Update",
                )
            ],
            category="interleaved",
        )
    )

    # -------------------------------------------------------------------------
    # Scenario 6: Frequent Common Actions (Monotonous Low-Entropy Noise)
    # Repeated single trivial actions (e.g. repeated page refreshes or clicks)
    # that meet length & repetition artificially but lack structural diversity.
    # -------------------------------------------------------------------------
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_6_frequent_common_actions",
            name="Frequent Common Actions (Low-Entropy Repetition)",
            description="Monotonous repetitive action (view_dashboard repeated 3x); trivial action noise.",
            session_sequences={
                "session_601": ["view_dashboard", "view_dashboard", "view_dashboard"],
                "session_602": ["view_dashboard", "view_dashboard", "view_dashboard"],
                "session_603": ["view_dashboard", "view_dashboard", "view_dashboard"],
            },
            # Ground truth: Monotonous identical single-action repetition should NOT be an automated workflow
            expected_detected=False,
            expected_workflows=[],
            category="negative_common_noise",
        )
    )

    # -------------------------------------------------------------------------
    # Scenario 7: Patterns with Occasional Missing or Reordered Actions
    # 3 sessions:
    # 701: open_email -> download_attachment -> search_customer -> update_customer -> send_message
    # 702: open_email -> search_customer -> update_customer -> send_message (missing download)
    # 703: open_email -> download_attachment -> update_customer -> search_customer -> send_message (swapped CRM)
    # -------------------------------------------------------------------------
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_7_missing_or_reordered",
            name="Patterns with Missing or Reordered Steps",
            description="Core 5-step flow with 1 session missing an action and 1 session with swapped adjacent steps.",
            session_sequences={
                "session_701": [
                    "open_email",
                    "download_attachment",
                    "search_customer",
                    "update_customer",
                    "send_message",
                ],
                "session_702": [
                    "open_email",
                    "search_customer",
                    "update_customer",
                    "send_message",
                ],
                "session_703": [
                    "open_email",
                    "download_attachment",
                    "update_customer",
                    "search_customer",
                    "send_message",
                ],
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=2, label="Customer Request Processing")
            ],
            category="variation_reordered",
        )
    )

    # -------------------------------------------------------------------------
    # Scenario 8: Similar but Distinct Workflows (Must NOT be Merged)
    # Workflow A (Billing): open_email -> download_attachment -> record_payment -> send_receipt -> archive_thread (2 sessions)
    # Workflow B (Support): open_email -> download_attachment -> create_ticket -> assign_agent -> send_acknowledgement (2 sessions)
    # Both share 2 prefix steps, but diverged in remaining 3 steps.
    # Ground truth: Exactly 2 distinct workflows must be discovered; merging them is a False Positive.
    # -------------------------------------------------------------------------
    workflow_billing = [
        "open_email",
        "download_attachment",
        "record_payment",
        "send_receipt",
        "archive_thread",
    ]
    workflow_support = [
        "open_email",
        "download_attachment",
        "create_ticket",
        "assign_agent",
        "send_acknowledgement",
    ]
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_8_distinct_workflows_no_merge",
            name="Similar but Distinct Workflows (No Incorrect Merge)",
            description="Two separate workflows sharing prefix steps; must be discovered as two distinct patterns.",
            session_sequences={
                "session_801": list(workflow_billing),
                "session_802": list(workflow_billing),
                "session_803": list(workflow_support),
                "session_804": list(workflow_support),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=workflow_billing, min_occurrences=2, label="Billing Workflow"),
                GroundTruthWorkflow(sequence=workflow_support, min_occurrences=2, label="Support Workflow"),
            ],
            category="distinct_multi_pattern",
        )
    )

    return scenarios


@dataclass
class EvaluationReport:
    """Comprehensive evaluation metrics report."""
    total_scenarios: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    scenario_details: List[Dict[str, Any]] = field(default_factory=list)


def evaluate_discovery_engine(
    detector: Optional[RepetitionDetector] = None,
    dataset: Optional[List[EvaluationScenario]] = None,
    similarity_match_threshold: float = 0.8,
) -> EvaluationReport:
    """
    Evaluates the Discovery Engine against the synthetic dataset.

    Definition of Evaluation Metrics:
    - True Positive (TP): An expected ground-truth workflow is detected by the engine with
      sequence similarity >= similarity_match_threshold to the ground-truth sequence.
    - False Positive (FP):
      a) The engine detected a workflow in a negative scenario where NO workflow was expected.
      b) The engine detected an extra spurious workflow that does not match any expected workflow.
      c) Two distinct workflows were improperly merged into a single bastardized pattern.
    - False Negative (FN): An expected ground-truth workflow was NOT detected by the engine.
    - True Negative (TN): A negative scenario where no workflow was expected, and the engine
      correctly reported detected=False with 0 workflows.
    """
    active_detector = detector or RepetitionDetector(min_length=3, min_occurrences=2, similarity_threshold=0.8)
    scenarios = dataset or build_synthetic_evaluation_dataset()

    tp = 0
    fp = 0
    fn = 0
    tn = 0
    scenario_details: List[Dict[str, Any]] = []

    for scenario in scenarios:
        result: DiscoveryResult = active_detector.detect(scenario.session_sequences)
        detected_workflows = result.workflows

        scen_tp = 0
        scen_fp = 0
        scen_fn = 0
        scen_tn = 0

        if not scenario.expected_detected:
            # Negative scenario
            if len(detected_workflows) == 0:
                scen_tn += 1
                tn += 1
            else:
                # Detected workflows when none were expected -> False Positives
                scen_fp += len(detected_workflows)
                fp += len(detected_workflows)
        else:
            # Positive scenario: match detected against expected ground truth
            expected_remaining = list(scenario.expected_workflows)
            matched_detected_indices = set()

            for exp_wf in expected_remaining:
                found_match = False
                for d_idx, det_wf in enumerate(detected_workflows):
                    if d_idx in matched_detected_indices:
                        continue
                    sim = compute_sequence_similarity(exp_wf.sequence, det_wf.sequence)
                    if sim >= similarity_match_threshold:
                        found_match = True
                        matched_detected_indices.add(d_idx)
                        break

                if found_match:
                    scen_tp += 1
                    tp += 1
                else:
                    scen_fn += 1
                    fn += 1

            # Any detected workflow that did not match an expected ground truth is a False Positive
            unmatched_detected = len(detected_workflows) - len(matched_detected_indices)
            if unmatched_detected > 0:
                scen_fp += unmatched_detected
                fp += unmatched_detected

        scenario_details.append({
            "scenario_id": scenario.scenario_id,
            "name": scenario.name,
            "category": scenario.category,
            "expected_detected": scenario.expected_detected,
            "actual_detected": result.detected,
            "expected_count": len(scenario.expected_workflows),
            "actual_count": len(detected_workflows),
            "tp": scen_tp,
            "fp": scen_fp,
            "fn": scen_fn,
            "tn": scen_tn,
            "detected_sequences": [w.sequence for w in detected_workflows],
        })

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 0.0
    total_decisions = tp + fp + fn + tn
    accuracy = round((tp + tn) / total_decisions, 4) if total_decisions > 0 else 0.0

    return EvaluationReport(
        total_scenarios=len(scenarios),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=precision,
        recall=recall,
        f1_score=f1,
        accuracy=accuracy,
        scenario_details=scenario_details,
    )


if __name__ == "__main__":
    detector_default = RepetitionDetector(min_length=3, min_occurrences=2, similarity_threshold=0.8)
    report = evaluate_discovery_engine(detector=detector_default)

    print("=================================================================")
    print("         WORKFLOWOS DISCOVERY ENGINE EVALUATION (PHASE 8.1)      ")
    print("=================================================================")
    print(f"Total Scenarios Evaluated: {report.total_scenarios}")
    print(f"True Positives (TP):       {report.true_positives}")
    print(f"False Positives (FP):      {report.false_positives}")
    print(f"False Negatives (FN):      {report.false_negatives}")
    print(f"True Negatives (TN):       {report.true_negatives}")
    print(f"Precision:                 {report.precision:.4f} ({report.precision*100:.1f}%)")
    print(f"Recall:                    {report.recall:.4f} ({report.recall*100:.1f}%)")
    print(f"F1 Score:                  {report.f1_score:.4f}")
    print(f"Accuracy:                  {report.accuracy:.4f} ({report.accuracy*100:.1f}%)")
    print("-----------------------------------------------------------------")
    print("Scenario Breakdown & Confidence Scores:")
    for d in report.scenario_details:
        status_str = "PASS" if (d["fp"] == 0 and d["fn"] == 0) else "WARN"
        print(f"  [{status_str}] {d['scenario_id']}: TP={d['tp']}, FP={d['fp']}, FN={d['fn']}, TN={d['tn']}")

    print("\n-----------------------------------------------------------------")
    print("Detected Pattern Confidence Breakdown:")
    for scenario in build_synthetic_evaluation_dataset():
        res = detector_default.detect(scenario.session_sequences)
        if res.workflows:
            print(f"\nScenario: {scenario.scenario_id}")
            for wf in res.workflows:
                print(f"  -> [{wf.confidence_tier.upper()}] Confidence: {wf.confidence:.4f} ({int(wf.confidence*100)}%)")
                print(f"     Label: {wf.label} | Occurrences: {wf.occurrences} | Avg Sim: {wf.similarity:.4f}")
                print(f"     Explanation: {wf.confidence_explanation}")
                if wf.confidence_breakdown:
                    b = wf.confidence_breakdown
                    print(f"     Signals: Rep={b.repetition_support:.2f}, Sim={b.sequence_similarity:.2f}, "
                          f"Div={b.action_diversity:.2f}, Len={b.sequence_length:.2f}, Cons={b.session_consistency:.2f}")

    print("\n=================================================================")
    print("   COMPARATIVE BENCHMARK: DEFAULT VS HIGH-CONFIDENCE FILTER (>=0.80)")
    print("=================================================================")
    report_hc = evaluate_discovery_engine(detector=RepetitionDetector(min_confidence=0.80))
    print(f"Metric                 | Default Baseline | High Confidence (>=0.80)")
    print(f"-----------------------|------------------|-------------------------")
    print(f"Precision              | {report.precision:.4f} ({report.precision*100:.1f}%)   | {report_hc.precision:.4f} ({report_hc.precision*100:.1f}%)")
    print(f"Recall                 | {report.recall:.4f} ({report.recall*100:.1f}%)  | {report_hc.recall:.4f} ({report_hc.recall*100:.1f}%)")
    print(f"F1 Score               | {report.f1_score:.4f}           | {report_hc.f1_score:.4f}")
    print(f"False Positives (FP)   | {report.false_positives}                | {report_hc.false_positives}")
    print(f"False Negatives (FN)   | {report.false_negatives}                | {report_hc.false_negatives}")
    print("=================================================================")

