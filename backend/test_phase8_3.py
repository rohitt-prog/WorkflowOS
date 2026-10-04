"""
WorkFlowOS Phase 8.3 Test Suite — Pattern Ranking, Noise Reduction & Duplicate Detection

Covers:
1. Pattern ranking calculation, signal normalization, and weights.
2. Quality tier assignment and deterministic explanations.
3. Stable tie-breaking and order determinism.
4. Noise reduction: monotonous repetition, low action entropy, and weak quality.
5. Preserving valid workflows with legitimate repeated actions.
6. Preserving short valid workflows.
7. Exact duplicate detection and representative assignment.
8. Subsequence shadow overlap detection and representative pointer.
9. Independent session support preservation (subsequences with distinct sessions not pruned).
10. Separation of similar-looking distinct workflows and shared-prefix workflows.
11. Traceability: suppression reasons, representative IDs, and audit records.
12. Discovery API route compatibility, min_ranking_score, and include_suppressed query params.
13. Evaluation benchmark integrity across all 24 scenarios.
"""

import unittest
from unittest.mock import patch
from typing import Dict, List

from fastapi.testclient import TestClient

from backend.main import app
from discovery.detector import (
    RepetitionDetector,
    detect_repeated_workflows,
)
from discovery.evaluation import (
    build_phase8_3_evaluation_dataset,
    build_complete_benchmark_dataset,
    evaluate_discovery_engine,
)
from discovery.models import DiscoveredWorkflow, DiscoveryResult
from discovery.ranking import (
    RANKING_WEIGHTS,
    QualityTier,
    SuppressionReason,
    assess_candidate_noise,
    calculate_ranking_score,
    compute_automation_impact_signal,
    compute_execution_fidelity_signal,
    compute_operational_volume_signal,
    compute_task_richness_signal,
    determine_quality_tier,
    generate_ranking_explanation,
)


class TestPatternRankingCalculation(unittest.TestCase):
    """Unit tests for utility ranking score calculations and signal normalization."""

    def test_ranking_weights_sum_to_one(self):
        total_weight = sum(RANKING_WEIGHTS.values())
        self.assertAlmostEqual(total_weight, 1.00, places=4)

    def test_operational_volume_signal_normalization(self):
        self.assertEqual(compute_operational_volume_signal(1), 0.0)
        self.assertEqual(compute_operational_volume_signal(2), 0.25)
        self.assertEqual(compute_operational_volume_signal(7), 1.0)
        self.assertEqual(compute_operational_volume_signal(12), 1.0)
        # Monotonically non-decreasing
        self.assertLess(compute_operational_volume_signal(3), compute_operational_volume_signal(5))

    def test_automation_impact_signal_normalization(self):
        self.assertEqual(compute_automation_impact_signal(2), 0.0)
        self.assertEqual(compute_automation_impact_signal(3), 0.60)
        self.assertEqual(compute_automation_impact_signal(4), 0.80)
        self.assertEqual(compute_automation_impact_signal(5), 1.00)
        self.assertEqual(compute_automation_impact_signal(8), 1.00)

    def test_execution_fidelity_signal_normalization(self):
        self.assertEqual(compute_execution_fidelity_signal(1.0, 1.0), 1.0)
        self.assertEqual(compute_execution_fidelity_signal(0.0, 0.0), 0.0)
        # 60% similarity, 40% consistency
        fidelity = compute_execution_fidelity_signal(0.80, 0.50)
        self.assertAlmostEqual(fidelity, 0.60 * 0.80 + 0.40 * 0.50, places=3)

    def test_task_richness_signal_entropy(self):
        # Monotonous
        self.assertEqual(compute_task_richness_signal(["view", "view", "view"]), 0.10)
        # All distinct
        self.assertEqual(compute_task_richness_signal(["a", "b", "c"]), 1.00)
        # Partial
        self.assertAlmostEqual(
            compute_task_richness_signal(["a", "b", "b", "c"]),
            0.10 + 0.90 * ((3 - 1) / (4 - 1)),
            places=3,
        )

    def test_calculate_ranking_score_bounds_and_tiers(self):
        seq = ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"]
        score, breakdown, tier, explanation = calculate_ranking_score(
            sequence=seq,
            occurrences=4,
            avg_similarity=1.0,
            confidence=0.94,
            session_consistency=1.0,
            rank=1,
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        self.assertGreaterEqual(score, 0.85)
        self.assertEqual(tier, QualityTier.EXCEPTIONAL.value)
        self.assertIn("Rank #1", explanation)
        self.assertIn("Score", explanation)
        self.assertIn("exceptional", explanation)
        self.assertIn("Fidelity=100%", explanation)

    def test_quality_tier_boundaries(self):
        self.assertEqual(determine_quality_tier(0.92), QualityTier.EXCEPTIONAL.value)
        self.assertEqual(determine_quality_tier(0.85), QualityTier.EXCEPTIONAL.value)
        self.assertEqual(determine_quality_tier(0.75), QualityTier.STRONG.value)
        self.assertEqual(determine_quality_tier(0.70), QualityTier.STRONG.value)
        self.assertEqual(determine_quality_tier(0.55), QualityTier.MODERATE.value)
        self.assertEqual(determine_quality_tier(0.50), QualityTier.MODERATE.value)
        self.assertEqual(determine_quality_tier(0.40), QualityTier.LOW.value)


class TestNoiseReductionAndFiltering(unittest.TestCase):
    """Unit tests for noise assessment and suppression."""

    def test_monotonous_repetition_suppressed_when_filter_enabled(self):
        seq = ["view_dashboard", "view_dashboard", "view_dashboard"]
        reason = assess_candidate_noise(
            sequence=seq,
            occurrences=3,
            confidence=0.65,
            ranking_score=0.45,
            min_occurrences=2,
            filter_noise=True,
        )
        self.assertEqual(reason, SuppressionReason.MONOTONOUS_REPETITION.value)

    def test_monotonous_repetition_not_suppressed_when_filter_disabled(self):
        # Backward compatibility: without filter_noise, returns None
        seq = ["view_dashboard", "view_dashboard", "view_dashboard"]
        reason = assess_candidate_noise(
            sequence=seq,
            occurrences=3,
            confidence=0.65,
            ranking_score=0.45,
            min_occurrences=2,
            filter_noise=False,
        )
        self.assertIsNone(reason)

    def test_low_action_diversity_suppressed_when_filter_enabled(self):
        # 1 unique action in 4 steps (diversity = 0.25 < 0.35)
        seq = ["click", "click", "click", "click"]
        reason = assess_candidate_noise(
            sequence=seq,
            occurrences=3,
            confidence=0.60,
            ranking_score=0.40,
            filter_noise=True,
        )
        self.assertEqual(reason, SuppressionReason.MONOTONOUS_REPETITION.value)

    def test_legitimate_repeated_actions_preserved(self):
        # 3 unique actions in 4 steps (diversity = 0.75 >= 0.35)
        seq = ["open_doc", "add_comment", "add_comment", "submit_approval"]
        reason = assess_candidate_noise(
            sequence=seq,
            occurrences=3,
            confidence=0.85,
            ranking_score=0.76,
            filter_noise=True,
        )
        self.assertIsNone(reason)

    def test_short_valid_workflow_preserved(self):
        # 3 unique actions in 3 steps
        seq = ["search_customer", "update_customer", "send_message"]
        reason = assess_candidate_noise(
            sequence=seq,
            occurrences=3,
            confidence=0.85,
            ranking_score=0.75,
            filter_noise=True,
        )
        self.assertIsNone(reason)

    def test_min_ranking_score_filter(self):
        seq = ["action_a", "action_b", "action_c"]
        reason = assess_candidate_noise(
            sequence=seq,
            occurrences=2,
            confidence=0.70,
            ranking_score=0.55,
            min_ranking_score=0.70,
        )
        self.assertEqual(reason, SuppressionReason.LOW_QUALITY_SCORE.value)


class TestDuplicateAndOverlapResolution(unittest.TestCase):
    """Tests identifying duplicates, overlapping shadows, and preserving distinct workflows."""

    def setUp(self):
        self.detector = RepetitionDetector(
            min_length=3,
            min_occurrences=2,
            similarity_threshold=0.8,
            filter_noise=True,
            include_suppressed=True,
        )

    def test_exact_duplicates_collapsed_and_suppressed_candidate_tracked(self):
        canonical = ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"]
        sessions = {
            "s1": list(canonical),
            "s2": list(canonical),
            "s3": list(canonical),
        }
        res = self.detector.detect(sessions, include_suppressed=True)
        self.assertTrue(res.detected)
        self.assertEqual(len(res.workflows), 1)
        self.assertEqual(res.workflows[0].sequence, canonical)
        self.assertEqual(res.workflows[0].rank, 1)
        self.assertFalse(res.workflows[0].is_duplicate)

        # Check that sub-slices were suppressed with representative pointers
        self.assertGreater(len(res.suppressed_workflows), 0)
        for sw in res.suppressed_workflows:
            self.assertTrue(sw.is_duplicate)
            self.assertEqual(sw.representative_pattern_id, "Customer Request Processing")

    def test_overlapping_shadow_suppressed_when_no_independent_sessions(self):
        canonical = ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"]
        sessions = {
            "s1": list(canonical),
            "s2": list(canonical),
            "s3": list(canonical),
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        self.assertEqual(len(res.workflows), 1)
        self.assertEqual(res.workflows[0].sequence, canonical)

    def test_subsequence_with_independent_sessions_not_suppressed(self):
        # Long workflow in s1..s4, Short workflow in s5..s6 (2 independent sessions outside s1..s4)
        wf_long = ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"]
        wf_short = ["search_customer", "update_customer", "send_message"]
        sessions = {
            "s1": list(wf_long),
            "s2": list(wf_long),
            "s3": list(wf_long),
            "s4": list(wf_long),
            "s5": list(wf_short),
            "s6": list(wf_short),
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        # Both must be preserved!
        self.assertEqual(len(res.workflows), 2)
        sequences = [w.sequence for w in res.workflows]
        self.assertIn(wf_long, sequences)
        self.assertIn(wf_short, sequences)
        # wf_long must be Rank #1
        self.assertEqual(res.workflows[0].sequence, wf_long)
        self.assertEqual(res.workflows[0].rank, 1)
        self.assertEqual(res.workflows[1].sequence, wf_short)
        self.assertEqual(res.workflows[1].rank, 2)

    def test_similar_looking_distinct_workflows_not_merged(self):
        wf_fulfill = ["create_order", "process_payment", "pack_items", "dispatch_delivery"]
        wf_cancel = ["create_order", "cancel_order", "refund_payment", "restock_items"]
        sessions = {
            "f1": list(wf_fulfill),
            "f2": list(wf_fulfill),
            "c1": list(wf_cancel),
            "c2": list(wf_cancel),
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        self.assertEqual(len(res.workflows), 2)
        sequences = [w.sequence for w in res.workflows]
        self.assertIn(wf_fulfill, sequences)
        self.assertIn(wf_cancel, sequences)

    def test_variable_support_ranking_order(self):
        wf_high = ["search_customer", "update_customer", "send_message"]
        wf_low = ["open_document", "edit_document", "export_document"]
        sessions = {
            "h1": list(wf_high),
            "h2": list(wf_high),
            "h3": list(wf_high),
            "h4": list(wf_high),
            "h5": list(wf_high),
            "h6": list(wf_high),
            "l1": list(wf_low),
            "l2": list(wf_low),
        }
        res = self.detector.detect(sessions)
        self.assertEqual(len(res.workflows), 2)
        self.assertEqual(res.workflows[0].sequence, wf_high)
        self.assertEqual(res.workflows[0].rank, 1)
        self.assertGreater(res.workflows[0].ranking_score, res.workflows[1].ranking_score)
        self.assertEqual(res.workflows[1].sequence, wf_low)
        self.assertEqual(res.workflows[1].rank, 2)


class TestPhase83EvaluationAndAPI(unittest.TestCase):
    """Tests evaluating Phase 8.3 datasets and API endpoints."""

    def test_phase8_3_evaluation_dataset_completeness(self):
        ds_8_3 = build_phase8_3_evaluation_dataset()
        self.assertEqual(len(ds_8_3), 8)
        scenario_ids = [s.scenario_id for s in ds_8_3]
        self.assertIn("scenario_17_exact_duplicates", scenario_ids)
        self.assertIn("scenario_18_overlapping_shadow_subsequence", scenario_ids)
        self.assertIn("scenario_19_short_valid_workflow", scenario_ids)
        self.assertIn("scenario_20_frequent_common_action_noise", scenario_ids)
        self.assertIn("scenario_21_distinct_business_workflows", scenario_ids)
        self.assertIn("scenario_22_variable_support_ranking", scenario_ids)
        self.assertIn("scenario_23_legitimate_repeated_actions", scenario_ids)
        self.assertIn("scenario_24_weak_marginal_pattern", scenario_ids)

    def test_complete_benchmark_dataset_metrics(self):
        complete_dataset = build_complete_benchmark_dataset()
        self.assertEqual(len(complete_dataset), 24)

        # Evaluate Phase 8.3 detector with noise filtering and ranking threshold
        detector = RepetitionDetector(
            min_length=3,
            min_occurrences=2,
            similarity_threshold=0.8,
            filter_noise=True,
            min_ranking_score=0.70,
        )
        report = evaluate_discovery_engine(detector=detector, dataset=complete_dataset)

        self.assertEqual(report.recall, 1.0)
        self.assertEqual(report.precision, 1.0)
        self.assertEqual(report.f1_score, 1.0)
        self.assertEqual(report.accuracy, 1.0)
        self.assertEqual(report.false_positives, 0)
        self.assertEqual(report.false_negatives, 0)
        self.assertGreater(report.duplicate_suppressions, 50)

    @patch("backend.routes.discovery.discovery_service.get_repeated_workflows")
    def test_api_ranking_and_suppressed_fields(self, mock_get_repeated):
        mock_wf = DiscoveredWorkflow(
            label="Customer Request Processing",
            sequence=["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
            occurrences=3,
            similarity=1.0,
            session_ids=["s1", "s2", "s3"],
            confidence=0.92,
            confidence_tier="high",
            rank=1,
            ranking_score=0.88,
            quality_tier="exceptional",
            ranking_explanation="Rank #1 (Score 88/100, exceptional quality): 5-step workflow with 5 distinct actions.",
            is_duplicate=False,
        )
        mock_suppressed = DiscoveredWorkflow(
            label="Customer Request Processing",
            sequence=["open_email", "download_attachment", "search_customer"],
            occurrences=3,
            similarity=1.0,
            session_ids=["s1", "s2", "s3"],
            confidence=0.80,
            is_duplicate=True,
            representative_pattern_id="Customer Request Processing",
            suppression_reason="OVERLAPPING_SHADOW",
        )
        mock_get_repeated.return_value = DiscoveryResult(
            detected=True,
            workflows=[mock_wf],
            suppressed_workflows=[mock_suppressed],
            total_candidates_evaluated=12,
        )

        client = TestClient(app)
        resp = client.get("/api/discovery/repeated?include_suppressed=true&min_ranking_score=0.75")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["detected"])
        self.assertEqual(len(data["workflows"]), 1)
        wf = data["workflows"][0]
        self.assertEqual(wf["rank"], 1)
        self.assertEqual(wf["ranking_score"], 0.88)
        self.assertEqual(wf["quality_tier"], "exceptional")
        self.assertFalse(wf["is_duplicate"])

        self.assertEqual(len(data["suppressed_workflows"]), 1)
        sw = data["suppressed_workflows"][0]
        self.assertTrue(sw["is_duplicate"])
        self.assertEqual(sw["suppression_reason"], "OVERLAPPING_SHADOW")
        self.assertEqual(sw["representative_pattern_id"], "Customer Request Processing")


if __name__ == "__main__":
    unittest.main()
