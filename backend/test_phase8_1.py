"""
WorkFlowOS Phase 8.1 Test Suite — Discovery Evaluation & Confidence Scoring

Covers:
1. Deterministic signal formulas (repetition, similarity, diversity, length, consistency).
2. Composite confidence score bounds [0.0, 1.0] and tier categorization.
3. Edge case handling (insufficient evidence, zero occurrences, empty sequences).
4. RepetitionDetector integration and confidence sorting.
5. Session isolation and multi-session grouping.
6. Backward compatibility of DiscoveredWorkflow and DiscoveryResult models.
7. FastAPI route /api/discovery/repeated integration with confidence fields and min_confidence filter.
8. Synthetic evaluation dataset and benchmark metrics verification.
"""

import unittest
from unittest.mock import AsyncMock, patch
from typing import Dict, List

from fastapi.testclient import TestClient

from backend.main import app
from discovery.confidence import (
    SIGNAL_WEIGHTS,
    ConfidenceBreakdown,
    calculate_pattern_confidence,
    compute_action_diversity_signal,
    compute_repetition_support_signal,
    compute_sequence_length_signal,
    compute_sequence_similarity_signal,
    compute_session_consistency_signal,
    determine_confidence_tier,
    generate_confidence_explanation,
)
from discovery.detector import RepetitionDetector, detect_repeated_workflows
from discovery.evaluation import (
    build_synthetic_evaluation_dataset,
    evaluate_discovery_engine,
)
from discovery.models import DiscoveredWorkflow, DiscoveryResult
from discovery.sequence import build_session_sequences


class TestConfidenceSignals(unittest.TestCase):
    """Unit tests for individual deterministic confidence signals."""

    def test_weights_sum_to_one(self):
        total_weight = sum(SIGNAL_WEIGHTS.values())
        self.assertAlmostEqual(total_weight, 1.0, places=6)

    def test_repetition_support_signal(self):
        self.assertEqual(compute_repetition_support_signal(0), 0.0)
        self.assertEqual(compute_repetition_support_signal(1), 0.0)
        self.assertEqual(compute_repetition_support_signal(2), 0.50)
        self.assertAlmostEqual(compute_repetition_support_signal(3), 0.6667, places=3)
        self.assertAlmostEqual(compute_repetition_support_signal(4), 0.8333, places=3)
        self.assertEqual(compute_repetition_support_signal(5), 1.0)
        self.assertEqual(compute_repetition_support_signal(10), 1.0)

    def test_sequence_similarity_signal(self):
        self.assertEqual(compute_sequence_similarity_signal(0.75, min_threshold=0.80), 0.0)
        self.assertEqual(compute_sequence_similarity_signal(0.80, min_threshold=0.80), 0.60)
        self.assertAlmostEqual(compute_sequence_similarity_signal(0.90, min_threshold=0.80), 0.80, places=3)
        self.assertEqual(compute_sequence_similarity_signal(1.0, min_threshold=0.80), 1.0)
        self.assertEqual(compute_sequence_similarity_signal(1.05, min_threshold=0.80), 1.0)

    def test_action_diversity_signal(self):
        # Empty or single action
        self.assertEqual(compute_action_diversity_signal([]), 0.0)
        self.assertEqual(compute_action_diversity_signal(["view"]), 0.0)

        # Monotonous repetitive action (all steps identical) -> harsh penalty (0.10)
        monotonous_3 = ["view_dashboard", "view_dashboard", "view_dashboard"]
        self.assertEqual(compute_action_diversity_signal(monotonous_3), 0.10)

        # Partial diversity: 2 unique out of 3
        partial_3 = ["search_customer", "update_customer", "update_customer"]
        self.assertAlmostEqual(compute_action_diversity_signal(partial_3), 0.55, places=2)

        # High diversity: 3 unique out of 3
        full_3 = ["search_customer", "update_customer", "send_message"]
        self.assertEqual(compute_action_diversity_signal(full_3), 1.0)

        # High diversity: 5 unique out of 5
        full_5 = ["open_email", "download", "search", "update", "send"]
        self.assertEqual(compute_action_diversity_signal(full_5), 1.0)

    def test_sequence_length_signal(self):
        self.assertEqual(compute_sequence_length_signal(1), 0.0)
        self.assertEqual(compute_sequence_length_signal(2), 0.0)
        self.assertEqual(compute_sequence_length_signal(3), 0.60)
        self.assertEqual(compute_sequence_length_signal(4), 0.80)
        self.assertEqual(compute_sequence_length_signal(5), 1.00)
        self.assertEqual(compute_sequence_length_signal(8), 1.00)

    def test_session_consistency_signal(self):
        # Empty fallback
        self.assertEqual(compute_session_consistency_signal([]), 0.50)
        # All exact matches
        self.assertEqual(compute_session_consistency_signal([1.0, 1.0, 1.0]), 1.00)
        # No exact matches
        self.assertEqual(compute_session_consistency_signal([0.85, 0.88, 0.90]), 0.50)
        # 1 exact out of 2
        self.assertEqual(compute_session_consistency_signal([1.0, 0.85]), 0.75)

    def test_confidence_tiers(self):
        self.assertEqual(determine_confidence_tier(0.95), "high")
        self.assertEqual(determine_confidence_tier(0.80), "high")
        self.assertEqual(determine_confidence_tier(0.799), "medium")
        self.assertEqual(determine_confidence_tier(0.65), "medium")
        self.assertEqual(determine_confidence_tier(0.649), "low")
        self.assertEqual(determine_confidence_tier(0.20), "low")

    def test_insufficient_evidence_handling(self):
        score, breakdown, tier, explanation = calculate_pattern_confidence(
            sequence=["step_1"],
            occurrences=1,
            avg_similarity=1.0,
        )
        self.assertEqual(score, 0.0)
        self.assertEqual(tier, "low")
        self.assertEqual(breakdown.repetition_support, 0.0)
        self.assertIn("Insufficient evidence", explanation)


class TestRepetitionDetectorConfidenceIntegration(unittest.TestCase):
    """Tests integrating confidence scoring within RepetitionDetector."""

    def setUp(self):
        self.detector = RepetitionDetector(min_length=3, min_occurrences=2, similarity_threshold=0.8)

    def test_strong_repeated_pattern_yields_high_confidence(self):
        canonical = ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"]
        sessions = {
            "s1": list(canonical),
            "s2": list(canonical),
            "s3": list(canonical),
            "s4": list(canonical),
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        self.assertEqual(len(res.workflows), 1)
        wf = res.workflows[0]
        self.assertGreaterEqual(wf.confidence, 0.90)
        self.assertEqual(wf.confidence_tier, "high")
        self.assertIsNotNone(wf.confidence_breakdown)
        self.assertEqual(wf.confidence_breakdown.action_diversity, 1.0)
        self.assertEqual(wf.confidence_breakdown.sequence_length, 1.0)
        self.assertIn("High confidence", wf.confidence_explanation)

    def test_monotonous_repetitive_noise_is_penalized(self):
        monotonous = ["view_dashboard", "view_dashboard", "view_dashboard"]
        sessions = {
            "s1": list(monotonous),
            "s2": list(monotonous),
            "s3": list(monotonous),
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        wf = res.workflows[0]
        # Dragged down by diversity penalty
        self.assertEqual(wf.confidence_breakdown.action_diversity, 0.10)
        self.assertLess(wf.confidence, 0.70)
        self.assertEqual(wf.confidence_tier, "medium")
        self.assertIn("low-entropy penalty", wf.confidence_explanation)

    def test_min_confidence_filter(self):
        # A mixed set of sessions where one pattern is strong and one is low-entropy
        strong = ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"]
        sessions = {
            "s1": list(strong),
            "s2": list(strong),
            "s3": list(strong),
            "s4": list(strong),
        }
        # Detector with min_confidence=0.90 should keep the strong pattern
        detector_high = RepetitionDetector(min_confidence=0.90)
        res_high = detector_high.detect(sessions)
        self.assertEqual(len(res_high.workflows), 1)

        # Detector with min_confidence=0.99 should filter it out
        detector_strict = RepetitionDetector(min_confidence=0.99)
        res_strict = detector_strict.detect(sessions)
        self.assertEqual(len(res_strict.workflows), 0)
        self.assertFalse(res_strict.detected)

    def test_workflows_sorted_by_confidence_descending(self):
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
        self.assertEqual(len(res.workflows), 2)
        # First workflow must have higher or equal confidence
        self.assertGreaterEqual(res.workflows[0].confidence, res.workflows[1].confidence)

    def test_session_isolation_in_sequence_building(self):
        interleaved_events = [
            {"session_id": "session_A", "timestamp": "2026-10-04T10:00:00Z", "event_type": "open_email"},
            {"session_id": "session_B", "timestamp": "2026-10-04T10:00:01Z", "event_type": "open_email"},
            {"session_id": "session_A", "timestamp": "2026-10-04T10:00:02Z", "event_type": "download_attachment"},
            {"session_id": "session_B", "timestamp": "2026-10-04T10:00:03Z", "event_type": "download_attachment"},
            {"session_id": "session_A", "timestamp": "2026-10-04T10:00:04Z", "event_type": "archive_thread"},
            {"session_id": "session_B", "timestamp": "2026-10-04T10:00:05Z", "event_type": "archive_thread"},
        ]
        seqs = build_session_sequences(interleaved_events)
        self.assertEqual(len(seqs), 2)
        self.assertEqual(seqs["session_A"], ["open_email", "download_attachment", "archive_thread"])
        self.assertEqual(seqs["session_B"], ["open_email", "download_attachment", "archive_thread"])

        res = self.detector.detect(seqs)
        self.assertTrue(res.detected)
        self.assertEqual(len(res.workflows), 1)
        self.assertEqual(set(res.workflows[0].session_ids), {"session_A", "session_B"})


class TestBackwardCompatibilityAndAPI(unittest.TestCase):
    """Verifies backward compatibility with Phase 2 models and FastAPI routes."""

    def test_discovered_workflow_model_backward_compatibility(self):
        # Instantiating DiscoveredWorkflow with only Phase 2 fields should not fail
        legacy_data = {
            "label": "Test Legacy",
            "sequence": ["a", "b", "c"],
            "occurrences": 3,
            "similarity": 0.95,
            "session_ids": ["s1", "s2", "s3"],
        }
        wf = DiscoveredWorkflow(**legacy_data)
        self.assertEqual(wf.label, "Test Legacy")
        self.assertEqual(wf.sequence, ["a", "b", "c"])
        self.assertEqual(wf.occurrences, 3)
        self.assertEqual(wf.similarity, 0.95)
        # Defaults populated gracefully
        self.assertEqual(wf.confidence, 0.80)
        self.assertIsNone(wf.confidence_breakdown)
        self.assertIsNone(wf.confidence_explanation)

    @patch("backend.routes.discovery.discovery_service.get_repeated_workflows")
    def test_api_repeated_route_with_confidence(self, mock_get_repeated):
        mock_wf = DiscoveredWorkflow(
            label="Customer Account Tier Update",
            sequence=["search_customer", "update_customer", "send_message"],
            occurrences=3,
            similarity=0.95,
            session_ids=["s1", "s2", "s3"],
            confidence=0.82,
            confidence_tier="high",
            confidence_breakdown=ConfidenceBreakdown(
                repetition_support=0.67,
                sequence_similarity=0.90,
                action_diversity=1.0,
                sequence_length=0.60,
                session_consistency=0.83,
                raw_signals={"occurrences": 3},
            ),
            confidence_explanation="High confidence: valid repetition and alignment.",
        )
        mock_get_repeated.return_value = DiscoveryResult(
            detected=True,
            workflows=[mock_wf],
        )

        client = TestClient(app)
        resp = client.get("/api/discovery/repeated")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["detected"])
        self.assertEqual(len(data["workflows"]), 1)
        wf_data = data["workflows"][0]
        # Phase 2 fields preserved
        self.assertEqual(wf_data["label"], "Customer Account Tier Update")
        self.assertEqual(wf_data["occurrences"], 3)
        self.assertEqual(wf_data["similarity"], 0.95)
        # Phase 8.1 fields populated
        self.assertEqual(wf_data["confidence"], 0.82)
        self.assertEqual(wf_data["confidence_tier"], "high")
        self.assertEqual(wf_data["confidence_breakdown"]["action_diversity"], 1.0)
        self.assertIn("High confidence", wf_data["confidence_explanation"])

    @patch("backend.routes.discovery.discovery_service.get_repeated_workflows")
    def test_api_min_confidence_filter_query_param(self, mock_get_repeated):
        mock_get_repeated.return_value = DiscoveryResult(detected=False, workflows=[])
        client = TestClient(app)
        resp = client.get("/api/discovery/repeated?min_confidence=0.85")
        self.assertEqual(resp.status_code, 200)
        mock_get_repeated.assert_called_once_with(
            min_length=3,
            min_occurrences=2,
            similarity_threshold=0.8,
            min_confidence=0.85,
        )


class TestEvaluationDatasetBenchmark(unittest.TestCase):
    """Verifies synthetic evaluation dataset and benchmark calculation."""

    def test_synthetic_dataset_integrity(self):
        scenarios = build_synthetic_evaluation_dataset()
        self.assertEqual(len(scenarios), 8)
        scenario_ids = [s.scenario_id for s in scenarios]
        self.assertIn("scenario_1_identical_repeated", scenario_ids)
        self.assertIn("scenario_2_minor_variations", scenario_ids)
        self.assertIn("scenario_3_unrelated_actions", scenario_ids)
        self.assertIn("scenario_4_incomplete_sequences", scenario_ids)
        self.assertIn("scenario_5_interleaved_sessions", scenario_ids)
        self.assertIn("scenario_6_frequent_common_actions", scenario_ids)
        self.assertIn("scenario_7_missing_or_reordered", scenario_ids)
        self.assertIn("scenario_8_distinct_workflows_no_merge", scenario_ids)

        for s in scenarios:
            self.assertTrue(len(s.session_sequences) > 0)
            for sid, seq in s.session_sequences.items():
                self.assertIsInstance(seq, list)
                for verb in seq:
                    # Synthetic verbs only: no PII
                    self.assertRegex(verb, r"^[a-z_]+$")

    def test_evaluation_benchmark_runs_without_error(self):
        report = evaluate_discovery_engine()
        self.assertEqual(report.total_scenarios, 8)
        self.assertEqual(report.true_positives, 6)
        self.assertEqual(report.false_negatives, 0)
        self.assertEqual(report.true_negatives, 2)
        self.assertAlmostEqual(report.recall, 1.0, places=2)
        self.assertGreater(report.precision, 0.80)
        self.assertGreater(report.f1_score, 0.90)


if __name__ == "__main__":
    unittest.main()
