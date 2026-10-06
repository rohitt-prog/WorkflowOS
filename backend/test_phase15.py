"""
WorkFlowOS Phase 15: Unit Test Suite for Evaluation & Benchmarking

Tests:
1. Benchmark dataset loading and Scenario A through J presence.
2. Ground truth specifications validity and completeness.
3. Mathematical correctness of Precision, Recall, F1, and Accuracy metrics.
4. Ranking metrics calculation (Top-1, Top-k, MRR).
5. Confidence calibration calculation.
6. Explainability coverage metric correctness.
7. Safety benchmark invariants:
   - Unknown action fails closed (read_only=False, mutating=False, requires_approval=True, rejected).
   - Unknown application fails closed (rejected).
   - Known mutating actions require approval.
   - Known read-only actions do not require approval.
8. Privacy redaction and retention invariants.
9. Absence of exposed credentials/secrets in benchmark output.
10. Deterministic reproducibility across repeated benchmark executions.
"""

import unittest
import json

from evaluation.datasets.scenarios import (
    get_benchmark_scenarios,
    get_scenario_by_id,
    BenchmarkScenario,
)
from evaluation.metrics.classification import (
    calculate_classification_metrics,
    ClassificationMetrics,
)
from evaluation.metrics.ranking import (
    calculate_ranking_metrics,
    RankingMetrics,
)
from evaluation.metrics.calibration import (
    calculate_confidence_calibration,
    CalibrationMetrics,
)
from evaluation.metrics.explainability import (
    calculate_explainability_coverage,
    ExplainabilityMetrics,
)
from evaluation.benchmarks.discovery import run_discovery_benchmark
from evaluation.benchmarks.learning import run_learning_benchmark
from evaluation.benchmarks.planning import run_planning_benchmark
from evaluation.benchmarks.closed_loop import run_closed_loop_benchmark
from evaluation.benchmarks.execution import run_execution_benchmark
from evaluation.benchmarks.safety import run_safety_benchmark, scan_for_secrets
from evaluation.benchmarks.end_to_end import run_end_to_end_benchmark
from evaluation.run import run_all_benchmarks


class TestPhase15EvaluationSuite(unittest.TestCase):
    """Phase 15 Evaluation & Benchmarking Unit Tests."""

    def test_01_dataset_loads_all_required_scenarios(self):
        """Verify Scenarios A through J load correctly with valid metadata."""
        scenarios = get_benchmark_scenarios()
        self.assertEqual(len(scenarios), 10, "Expected exactly 10 canonical scenarios (A through J)")

        expected_codes = [f"SCENARIO_{letter}" for letter in "ABCDEFGHIJ"]
        actual_codes = [s.code for s in scenarios]
        self.assertEqual(actual_codes, expected_codes, "Scenarios A through J must all be present")

        for s in scenarios:
            self.assertTrue(s.scenario_id, f"Scenario {s.code} missing scenario_id")
            self.assertTrue(s.name, f"Scenario {s.code} missing name")
            self.assertTrue(s.description, f"Scenario {s.code} missing description")
            self.assertTrue(len(s.session_sequences) > 0, f"Scenario {s.code} missing session sequences")
            self.assertIsNotNone(s.ground_truth, f"Scenario {s.code} missing ground truth")

    def test_02_ground_truth_validity(self):
        """Verify ground truth specifications are mathematically and logically sound."""
        scen_a = get_scenario_by_id("SCENARIO_A")
        self.assertIsNotNone(scen_a)
        self.assertTrue(scen_a.ground_truth.expected_detected)
        self.assertEqual(len(scen_a.ground_truth.expected_workflows), 1)
        self.assertEqual(len(scen_a.ground_truth.expected_workflows[0].sequence), 5)

        scen_e = get_scenario_by_id("SCENARIO_E")
        self.assertIsNotNone(scen_e)
        self.assertFalse(scen_e.ground_truth.expected_detected, "Short sequence must expect detected=False")

        scen_f = get_scenario_by_id("SCENARIO_F")
        self.assertIsNotNone(scen_f)
        self.assertFalse(scen_f.ground_truth.expected_detected, "Single occurrence must expect detected=False")

        scen_i = get_scenario_by_id("SCENARIO_I")
        self.assertIsNotNone(scen_i)
        self.assertTrue(scen_i.ground_truth.fail_closed, "Unknown action must specify fail_closed=True")
        self.assertFalse(scen_i.ground_truth.is_executable, "Unknown action must not be executable")

        scen_j = get_scenario_by_id("SCENARIO_J")
        self.assertIsNotNone(scen_j)
        self.assertFalse(scen_j.ground_truth.is_executable, "Unknown app must not be executable")

    def test_03_classification_metrics_math(self):
        """Verify Precision, Recall, F1, and Accuracy calculations and edge cases."""
        # Standard case
        m = calculate_classification_metrics(
            true_positives=8, false_positives=2, false_negatives=0, true_negatives=10
        )
        self.assertEqual(m.precision, 0.8)       # 8 / (8 + 2)
        self.assertEqual(m.recall, 1.0)          # 8 / (8 + 0)
        self.assertEqual(m.f1, 0.8889)          # 2 * 0.8 * 1.0 / 1.8
        self.assertEqual(m.accuracy, 0.9)        # (8 + 10) / 20

        # Perfect case
        m_perf = calculate_classification_metrics(
            true_positives=5, false_positives=0, false_negatives=0, true_negatives=5
        )
        self.assertEqual(m_perf.precision, 1.0)
        self.assertEqual(m_perf.recall, 1.0)
        self.assertEqual(m_perf.f1, 1.0)
        self.assertEqual(m_perf.accuracy, 1.0)

        # Zero denominator safety
        m_zero = calculate_classification_metrics(
            true_positives=0, false_positives=0, false_negatives=0, true_negatives=0
        )
        self.assertEqual(m_zero.precision, 0.0)
        self.assertEqual(m_zero.recall, 0.0)
        self.assertEqual(m_zero.f1, 0.0)
        self.assertEqual(m_zero.accuracy, 0.0)

    def test_04_ranking_metrics_math(self):
        """Verify Top-1, Top-k, and MRR calculations."""
        ranks = [1, 2, 1, None]
        rm = calculate_ranking_metrics(ranks, k=3)
        self.assertEqual(rm.total_queries, 4)
        self.assertEqual(rm.top_1_accuracy, 0.5)     # 2 out of 4
        self.assertEqual(rm.top_k_recall, 0.75)      # 3 out of 4 (ranks 1, 2, 1 <= 3)
        # MRR: (1/1 + 1/2 + 1/1 + 0) / 4 = 2.5 / 4 = 0.625
        self.assertEqual(rm.mrr, 0.625)

        # Empty ranks
        rm_empty = calculate_ranking_metrics([])
        self.assertEqual(rm_empty.top_1_accuracy, 0.0)
        self.assertEqual(rm_empty.mrr, 0.0)

    def test_05_confidence_calibration(self):
        """Verify calibration calculations and delta computation."""
        preds = [
            {"confidence": 0.90, "is_correct": True},
            {"confidence": 0.80, "is_correct": True},
            {"confidence": 0.40, "is_correct": False},
        ]
        calib = calculate_confidence_calibration(preds)
        self.assertEqual(calib.sample_count, 3)
        self.assertEqual(calib.correct_mean_confidence, 0.85)
        self.assertEqual(calib.incorrect_mean_confidence, 0.40)
        self.assertEqual(calib.calibration_delta, 0.45)
        self.assertTrue("synthetic" in calib.note.lower())

    def test_06_explainability_coverage(self):
        """Verify explainability coverage calculation."""
        records = [
            {
                "component": "discovery",
                "checks": {
                    "field_1": True,
                    "field_2": True,
                    "field_3": False,
                },
            },
            {
                "component": "planning",
                "checks": {
                    "field_1": True,
                    "field_4": True,
                },
            },
        ]
        expl = calculate_explainability_coverage(records)
        self.assertEqual(expl.explanations_present, 4)
        self.assertEqual(expl.explanations_expected, 5)
        self.assertEqual(expl.explanation_coverage, 0.8)

    def test_07_safety_benchmark_invariants(self):
        """Verify fail-closed safety invariants."""
        res = run_safety_benchmark()
        self.assertTrue(res["zero_approval_bypass"], "Approval must NEVER be bypassed")
        self.assertEqual(res["safety_compliance_rate"], 1.0, "All safety checks must pass 100%")

        # Sub-checks
        checks = res["checks"]
        self.assertTrue(checks["unknown_action_not_read_only"])
        self.assertTrue(checks["unknown_action_not_mutating"])
        self.assertTrue(checks["unknown_action_requires_approval"])
        self.assertTrue(checks["unknown_action_execution_rejected"])
        self.assertTrue(checks["unknown_app_execution_rejected"])
        self.assertTrue(checks["known_mutating_action_mutating"])
        self.assertTrue(checks["known_mutating_action_requires_approval"])
        self.assertTrue(checks["known_read_only_action_read_only"])
        self.assertTrue(checks["known_read_only_action_no_approval"])
        self.assertTrue(checks["privacy_redaction_engine"])
        self.assertTrue(checks["privacy_collection_gate"])
        self.assertTrue(checks["privacy_retention_valid"])

    def test_08_learning_formula_verification(self):
        """Verify exact Phase 9 learning formula and recommendation state transitions."""
        lrn = run_learning_benchmark()
        self.assertTrue(lrn["formula_verified"], "Phase 9 learning formula must match exactly")
        self.assertEqual(lrn["score_accuracy"], 1.0)
        self.assertEqual(lrn["status_accuracy"], 1.0)

    def test_09_planning_benchmark_hierarchy(self):
        """Verify strategy priority hierarchy and zero approval bypass."""
        pln = run_planning_benchmark()
        self.assertEqual(pln["strategy_selection_accuracy"], 1.0)
        self.assertEqual(pln["fallback_safety_rate"], 1.0)
        self.assertTrue(pln["zero_approval_bypass"])

    def test_10_closed_loop_outcome_taxonomy(self):
        """Verify failure taxonomy classification and outcome statuses."""
        cl = run_closed_loop_benchmark()
        self.assertEqual(cl["taxonomy_classification_accuracy"], 1.0)
        self.assertEqual(cl["lifecycle_status_accuracy"], 1.0)
        self.assertTrue(cl["idempotency_verified"])
        self.assertTrue(cl["zero_false_failures_on_paused_or_cancelled"])

    def test_11_execution_benchmark_rejection(self):
        """Verify execution engine refuses unapproved and unsupported workflows."""
        exc = run_execution_benchmark()
        self.assertEqual(exc["unapproved_rejection_rate"], 1.0)
        self.assertEqual(exc["unsupported_action_rejection_rate"], 1.0)
        self.assertTrue(exc["idempotency_passed"])

    def test_12_secret_scanning_clean(self):
        """Verify benchmark output does not leak passwords, tokens, or URIs."""
        # Test scanner itself
        leak = scan_for_secrets("Here is my secret token: ghp_1234567890abcdefghijklmnopqrstuvwxyz")
        self.assertTrue(len(leak) > 0, "Secret scanner must detect GitHub PAT")

        # Test full benchmark run output
        results = run_all_benchmarks(seed=42)
        json_dump = json.dumps(results)
        found_in_results = scan_for_secrets(json_dump)
        self.assertEqual(len(found_in_results), 0, f"Benchmark output contains secrets: {found_in_results}")

    def test_13_end_to_end_pipeline(self):
        """Verify all 10 stages of the end-to-end benchmark complete successfully."""
        e2e = run_end_to_end_benchmark()
        self.assertEqual(e2e["end_to_end_success"], 1.0)
        self.assertEqual(e2e["passed_stages"], e2e["total_stages"])

    def test_14_reproducibility_across_runs(self):
        """Verify benchmark produces identical results when executed twice with fixed seed."""
        run1 = run_all_benchmarks(seed=42)
        run2 = run_all_benchmarks(seed=42)

        # Compare deterministic sections (ignore timestamps)
        self.assertEqual(run1["discovery"], run2["discovery"])
        self.assertEqual(run1["ranking"], run2["ranking"])
        self.assertEqual(run1["learning"], run2["learning"])
        self.assertEqual(run1["planning"], run2["planning"])
        self.assertEqual(run1["closed_loop"], run2["closed_loop"])
        self.assertEqual(run1["safety"], run2["safety"])
        self.assertEqual(run1["end_to_end"], run2["end_to_end"])


if __name__ == "__main__":
    unittest.main()
