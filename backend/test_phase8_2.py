"""
WorkFlowOS Phase 8.2 Test Suite — Smarter Sequence Detection with Local Alignment

Covers:
1. Local sequence alignment algorithm (insertions, deletions, transpositions, prefix/suffix noise).
2. Embedded repeated workflow discovery within longer noisy sessions.
3. Intermediate inserted actions between workflow steps.
4. Missing steps tolerance within calibrated limits.
5. Small adjacent step transpositions (Damerau extension).
6. Distinct-session occurrence counting (single session repetitions cannot inflate occurrences).
7. Duplicate candidate prevention and shadow pruning.
8. Shared-prefix workflow separation (Billing vs. Support).
9. Similar-looking workflows with divergent actions separation (Update vs. Delete).
10. Excessive sequence variation rejection.
11. Order determinism across different session dictionary input orders.
12. FastAPI /api/discovery/repeated API compatibility and confidence integration.
"""

import unittest
from unittest.mock import patch
from typing import Dict, List

from fastapi.testclient import TestClient

from backend.main import app
from discovery.alignment import (
    compute_longest_common_subsequence,
    local_sequence_alignment,
)
from discovery.detector import (
    RepetitionDetector,
    detect_repeated_workflows,
    is_subsequence,
)
from discovery.evaluation import (
    build_phase8_2_evaluation_dataset,
    build_full_evaluation_dataset,
    evaluate_discovery_engine,
)
from discovery.models import DiscoveredWorkflow, DiscoveryResult


class TestLocalSequenceAlignment(unittest.TestCase):
    """Unit tests for the local_sequence_alignment DP implementation."""

    def setUp(self):
        self.canonical = ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"]

    def test_exact_match_embedded_in_noise(self):
        target = ["login", "view_home"] + self.canonical + ["logout", "cleanup"]
        res = local_sequence_alignment(self.canonical, target)
        self.assertTrue(res.is_match)
        self.assertEqual(res.similarity, 1.0)
        self.assertEqual(res.start_idx, 2)
        self.assertEqual(res.end_idx, 7)
        self.assertEqual(res.aligned_target, self.canonical)
        self.assertEqual(res.matches, 5)
        self.assertEqual(res.insertions, 0)
        self.assertEqual(res.deletions, 0)

    def test_single_inserted_action_between_steps(self):
        target = ["open_email", "view_dashboard", "download_attachment", "search_customer", "update_customer", "send_message"]
        res = local_sequence_alignment(self.canonical, target)
        self.assertTrue(res.is_match)
        self.assertGreater(res.similarity, 0.90)
        self.assertEqual(res.insertions, 1)
        self.assertEqual(res.matches, 5)

    def test_single_missing_action(self):
        # download_attachment omitted
        target = ["open_email", "search_customer", "update_customer", "send_message"]
        res = local_sequence_alignment(self.canonical, target)
        self.assertTrue(res.is_match)
        self.assertGreater(res.similarity, 0.85)
        self.assertEqual(res.deletions, 1)
        self.assertEqual(res.matches, 4)

    def test_adjacent_step_transposition(self):
        # update_customer and search_customer swapped
        target = ["open_email", "download_attachment", "update_customer", "search_customer", "send_message"]
        res = local_sequence_alignment(self.canonical, target)
        self.assertTrue(res.is_match)
        self.assertGreaterEqual(res.similarity, 0.95)
        self.assertEqual(res.transpositions, 2)

    def test_unrelated_actions_rejected(self):
        target = ["open_settings", "export_log", "view_dashboard", "refresh_feed"]
        res = local_sequence_alignment(self.canonical, target)
        self.assertFalse(res.is_match)
        self.assertEqual(res.similarity, 0.0)

    def test_longest_common_subsequence(self):
        s1 = ["open_email", "noise1", "download_attachment", "search_customer", "update_customer", "send_message"]
        s2 = ["open_email", "download_attachment", "noise2", "search_customer", "update_customer", "send_message"]
        lcs = compute_longest_common_subsequence(s1, s2)
        self.assertEqual(lcs, self.canonical)

    def test_is_subsequence_helper(self):
        self.assertTrue(is_subsequence(["a", "b", "c"], ["a", "x", "b", "y", "c"]))
        self.assertFalse(is_subsequence(["b", "a"], ["a", "b", "c"]))
        self.assertTrue(is_subsequence([], ["a", "b"]))


class TestPhase82SmarterSequenceDetection(unittest.TestCase):
    """Integration tests for Phase 8.2 smarter sequence detection in RepetitionDetector."""

    def setUp(self):
        self.detector = RepetitionDetector(min_length=3, min_occurrences=2, similarity_threshold=0.8)
        self.canonical = ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"]

    def test_embedded_workflow_discovered_across_noisy_sessions(self):
        sessions = {
            "s1": ["login", "view_home"] + list(self.canonical) + ["logout"],
            "s2": ["refresh_feed", "open_browser"] + list(self.canonical),
            "s3": list(self.canonical) + ["close_tab", "archive_session"],
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        self.assertEqual(len(res.workflows), 1)
        wf = res.workflows[0]
        self.assertEqual(wf.sequence, self.canonical)
        self.assertEqual(wf.occurrences, 3)
        self.assertEqual(wf.similarity, 1.0)
        self.assertEqual(wf.confidence_tier, "high")

    def test_inserted_actions_tolerated_and_canonical_preserved(self):
        sessions = {
            "s1": list(self.canonical),
            "s2": ["open_email", "view_dashboard", "download_attachment", "search_customer", "update_customer", "send_message"],
            "s3": ["open_email", "download_attachment", "search_customer", "view_profile", "update_customer", "send_message"],
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        self.assertEqual(len(res.workflows), 1)
        wf = res.workflows[0]
        self.assertEqual(wf.sequence, self.canonical)
        self.assertEqual(wf.occurrences, 3)
        self.assertGreater(wf.similarity, 0.90)

    def test_single_session_repetition_does_not_count_as_repeated_workflow(self):
        # Repeated 3 times in s1, but s2 has unrelated actions
        sessions = {
            "s1": [
                "search_customer", "update_customer", "send_message",
                "search_customer", "update_customer", "send_message",
                "search_customer", "update_customer", "send_message",
            ],
            "s2": ["edit_profile", "change_theme", "export_data"],
        }
        res = self.detector.detect(sessions)
        # Must be rejected because distinct supporting sessions = 1 < min_occurrences (2)
        self.assertFalse(res.detected)
        self.assertEqual(len(res.workflows), 0)

    def test_adjacent_step_transposition_discovered(self):
        sessions = {
            "s1": list(self.canonical),
            "s2": ["open_email", "download_attachment", "update_customer", "search_customer", "send_message"],
            "s3": list(self.canonical),
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        self.assertEqual(len(res.workflows), 1)
        wf = res.workflows[0]
        self.assertEqual(wf.sequence, self.canonical)
        self.assertEqual(wf.occurrences, 3)
        self.assertGreater(wf.similarity, 0.95)

    def test_shared_prefix_workflows_not_merged(self):
        workflow_billing = ["open_email", "download_attachment", "record_payment", "send_receipt", "archive_thread"]
        workflow_support = ["open_email", "download_attachment", "create_ticket", "assign_agent", "send_acknowledgement"]
        sessions = {
            "b1": list(workflow_billing),
            "b2": list(workflow_billing),
            "s1": list(workflow_support),
            "s2": list(workflow_support),
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        # Exactly 2 distinct workflows must be discovered
        self.assertEqual(len(res.workflows), 2)
        found_sequences = [w.sequence for w in res.workflows]
        self.assertIn(workflow_billing, found_sequences)
        self.assertIn(workflow_support, found_sequences)

    def test_similar_looking_workflows_not_merged(self):
        wf_update = ["search_customer", "update_customer", "send_message", "log_audit"]
        wf_delete = ["search_customer", "delete_customer", "send_message", "log_audit"]
        sessions = {
            "u1": list(wf_update),
            "u2": list(wf_update),
            "d1": list(wf_delete),
            "d2": list(wf_delete),
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        self.assertEqual(len(res.workflows), 2)
        found_sequences = [w.sequence for w in res.workflows]
        self.assertIn(wf_update, found_sequences)
        self.assertIn(wf_delete, found_sequences)

    def test_excessive_sequence_variation_rejected(self):
        sessions = {
            "s1": list(self.canonical),
            "s2": ["open_email", "browse_catalog", "add_to_cart", "checkout", "send_message"],
            "s3": ["open_email", "view_faq", "submit_feedback", "rate_app", "send_message"],
        }
        res = self.detector.detect(sessions)
        self.assertFalse(res.detected)
        self.assertEqual(len(res.workflows), 0)

    def test_order_determinism(self):
        sessions_a = {
            "s1": ["login", "view_home"] + list(self.canonical) + ["logout"],
            "s2": ["refresh_feed", "open_browser"] + list(self.canonical),
            "s3": list(self.canonical) + ["close_tab", "archive_session"],
        }
        # Inverted session key order
        sessions_b = {
            "s3": sessions_a["s3"],
            "s2": sessions_a["s2"],
            "s1": sessions_a["s1"],
        }
        res_a = self.detector.detect(sessions_a)
        res_b = self.detector.detect(sessions_b)
        self.assertEqual(len(res_a.workflows), len(res_b.workflows))
        self.assertEqual(res_a.workflows[0].sequence, res_b.workflows[0].sequence)
        self.assertEqual(res_a.workflows[0].confidence, res_b.workflows[0].confidence)
        self.assertEqual(res_a.workflows[0].occurrences, res_b.workflows[0].occurrences)


class TestPhase82EvaluationAndAPI(unittest.TestCase):
    """Tests evaluating Phase 8.2 datasets and API backwards compatibility."""

    def test_phase8_2_evaluation_dataset_completeness(self):
        dataset_8_2 = build_phase8_2_evaluation_dataset()
        self.assertEqual(len(dataset_8_2), 8)
        scenario_ids = [s.scenario_id for s in dataset_8_2]
        self.assertIn("scenario_9_embedded_subsequence_with_noise", scenario_ids)
        self.assertIn("scenario_10_interleaved_inserted_actions", scenario_ids)
        self.assertIn("scenario_11_single_session_repetition_rejected", scenario_ids)
        self.assertIn("scenario_12_adjacent_step_transpositions", scenario_ids)
        self.assertIn("scenario_13_shared_prefix_distinct_workflows", scenario_ids)
        self.assertIn("scenario_14_excessive_variation_rejected", scenario_ids)
        self.assertIn("scenario_15_mixture_exact_and_local", scenario_ids)
        self.assertIn("scenario_16_similar_looking_distinct_workflows", scenario_ids)

    def test_full_dataset_benchmark_metrics(self):
        full_dataset = build_full_evaluation_dataset()
        self.assertEqual(len(full_dataset), 16)
        report = evaluate_discovery_engine(dataset=full_dataset)
        # Recall must be 100% on the 16-scenario dataset
        self.assertEqual(report.recall, 1.0)
        self.assertEqual(report.false_negatives, 0)
        self.assertGreaterEqual(report.precision, 0.90)
        self.assertGreaterEqual(report.f1_score, 0.95)

    @patch("backend.routes.discovery.discovery_service.get_repeated_workflows")
    def test_api_endpoint_backward_compatibility(self, mock_get_repeated):
        mock_wf = DiscoveredWorkflow(
            label="Customer Request Processing",
            sequence=["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
            occurrences=3,
            similarity=0.9697,
            session_ids=["s1", "s2", "s3"],
            confidence=0.8682,
            confidence_tier="high",
            confidence_explanation="High confidence: valid repetition and alignment.",
        )
        mock_get_repeated.return_value = DiscoveryResult(detected=True, workflows=[mock_wf])

        client = TestClient(app)
        resp = client.get("/api/discovery/repeated")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["detected"])
        self.assertEqual(len(data["workflows"]), 1)
        wf = data["workflows"][0]
        self.assertEqual(wf["label"], "Customer Request Processing")
        self.assertEqual(wf["occurrences"], 3)
        self.assertEqual(wf["similarity"], 0.9697)
        self.assertEqual(wf["confidence"], 0.8682)
        self.assertEqual(wf["confidence_tier"], "high")


if __name__ == "__main__":
    unittest.main()
