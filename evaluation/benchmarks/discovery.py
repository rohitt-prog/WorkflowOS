"""
WorkFlowOS Phase 15: Discovery & Ranking Benchmark

Evaluates Phase 2 sequence detection and Phase 8 intelligence (confidence calibration,
ranking, explainability, and robustness) against Scenarios A through J.

Uses existing Phase 2/8 RepetitionDetector without altering algorithms.
"""

from typing import Dict, List, Any, Optional
import difflib

from discovery.detector import RepetitionDetector, compute_sequence_similarity
from discovery.models import DiscoveryResult, DiscoveredWorkflow
from evaluation.datasets.scenarios import get_benchmark_scenarios, BenchmarkScenario
from evaluation.metrics.classification import calculate_classification_metrics, ClassificationMetrics
from evaluation.metrics.ranking import calculate_ranking_metrics, RankingMetrics
from evaluation.metrics.calibration import calculate_confidence_calibration, CalibrationMetrics
from evaluation.metrics.explainability import calculate_explainability_coverage, ExplainabilityMetrics


def run_discovery_benchmark(
    scenarios: Optional[List[BenchmarkScenario]] = None,
    similarity_match_threshold: float = 0.8,
) -> Dict[str, Any]:
    """
    Executes discovery benchmark across defined scenarios.

    Measures:
    - Precision, Recall, F1, Accuracy, TP, FP, FN, TN
    - Confidence distribution and directional calibration
    - Ranking metrics (Top-1 accuracy, MRR)
    - Explainability coverage
    - Robustness (noise, partial, short, single-session rejection)
    """
    active_scenarios = scenarios or get_benchmark_scenarios()
    detector = RepetitionDetector(min_length=3, min_occurrences=2, similarity_threshold=0.8)

    tp = 0
    fp = 0
    fn = 0
    tn = 0

    predictions_for_calibration: List[Dict[str, Any]] = []
    ranking_positions: List[Optional[int]] = []
    explainability_records: List[Dict[str, Any]] = []
    robustness_results: Dict[str, Any] = {}
    scenario_details: List[Dict[str, Any]] = []

    for scen in active_scenarios:
        res: DiscoveryResult = detector.detect(scen.session_sequences, include_suppressed=True)
        detected_workflows = res.workflows

        scen_tp = 0
        scen_fp = 0
        scen_fn = 0
        scen_tn = 0

        # Collect explainability records
        for dw in detected_workflows:
            has_expl = dw.explanation is not None
            has_seq_ev = False
            has_conf_expl = False
            has_rank_expl = False

            if has_expl and dw.explanation:
                has_seq_ev = dw.explanation.sequence_evidence is not None
                has_conf_expl = bool(dw.explanation.confidence_factors) or bool(dw.explanation.human_readable_summary)
                has_rank_expl = bool(dw.explanation.ranking_factors) or bool(dw.explanation.tier_rationale)

            explainability_records.append({
                "component": "discovery",
                "checks": {
                    "explanation_present": has_expl,
                    "sequence_evidence": has_seq_ev,
                    "confidence_explanation": has_conf_expl,
                    "ranking_explanation": has_rank_expl,
                },
            })

        if not scen.ground_truth.expected_detected:
            # Negative scenario
            if len(detected_workflows) == 0:
                scen_tn = 1
                tn += 1
            else:
                scen_fp = len(detected_workflows)
                fp += len(detected_workflows)
                for dw in detected_workflows:
                    predictions_for_calibration.append({
                        "confidence": dw.confidence,
                        "is_correct": False,
                    })
        else:
            # Positive scenario: match against expected workflows
            unmatched_detected = list(enumerate(detected_workflows))
            matched_detected_indices = set()

            for exp_wf in scen.ground_truth.expected_workflows:
                best_sim = 0.0
                best_match_idx = None

                for idx, det_wf in enumerate(detected_workflows):
                    if idx in matched_detected_indices:
                        continue
                    sim = compute_sequence_similarity(exp_wf.sequence, det_wf.sequence)
                    if sim > best_sim:
                        best_sim = sim
                        best_match_idx = idx

                if best_match_idx is not None and best_sim >= similarity_match_threshold:
                    scen_tp += 1
                    tp += 1
                    matched_detected_indices.add(best_match_idx)
                    matched_dw = detected_workflows[best_match_idx]

                    # Confidence calibration entry
                    predictions_for_calibration.append({
                        "confidence": matched_dw.confidence,
                        "is_correct": True,
                    })

                    # Ranking evaluation: 1-based rank in detected workflows
                    ranking_positions.append(best_match_idx + 1)
                else:
                    scen_fn += 1
                    fn += 1
                    ranking_positions.append(None)

            # Any extra detected workflows that didn't match ground truth are False Positives
            extra_fps = len(detected_workflows) - len(matched_detected_indices)
            if extra_fps > 0:
                scen_fp += extra_fps
                fp += extra_fps
                for idx, det_wf in enumerate(detected_workflows):
                    if idx not in matched_detected_indices:
                        predictions_for_calibration.append({
                            "confidence": det_wf.confidence,
                            "is_correct": False,
                        })

        # Track robustness categories
        if scen.category in ("robustness", "variation", "threshold_negative", "frequency_negative", "isolation"):
            robustness_results[scen.code] = {
                "name": scen.name,
                "category": scen.category,
                "expected_detected": scen.ground_truth.expected_detected,
                "actual_detected": len(detected_workflows) > 0,
                "workflows_count": len(detected_workflows),
                "passed": (len(detected_workflows) > 0) == scen.ground_truth.expected_detected,
            }

        scenario_details.append({
            "scenario_id": scen.scenario_id,
            "code": scen.code,
            "category": scen.category,
            "tp": scen_tp,
            "fp": scen_fp,
            "fn": scen_fn,
            "tn": scen_tn,
            "detected_count": len(detected_workflows),
            "expected_count": len(scen.ground_truth.expected_workflows),
        })

    # Calculate metrics
    clf_metrics: ClassificationMetrics = calculate_classification_metrics(tp, fp, fn, tn)
    rank_metrics: RankingMetrics = calculate_ranking_metrics(ranking_positions, k=3)
    calib_metrics: CalibrationMetrics = calculate_confidence_calibration(predictions_for_calibration)
    expl_metrics: ExplainabilityMetrics = calculate_explainability_coverage(explainability_records)

    robustness_passed_count = sum(1 for r in robustness_results.values() if r["passed"])
    robustness_total_count = len(robustness_results)
    robustness_rate = (
        round(robustness_passed_count / robustness_total_count, 4)
        if robustness_total_count > 0
        else 1.0
    )

    return {
        "classification": clf_metrics.to_dict(),
        "ranking": rank_metrics.to_dict(),
        "calibration": calib_metrics.to_dict(),
        "explainability": expl_metrics.to_dict(),
        "robustness": {
            "passed_tests": robustness_passed_count,
            "total_tests": robustness_total_count,
            "robustness_rate": robustness_rate,
            "tests": robustness_results,
        },
        "scenario_details": scenario_details,
    }
