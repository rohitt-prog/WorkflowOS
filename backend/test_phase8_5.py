"""
WorkFlowOS Phase 8.5 Test Suite: Discovery Quality & Robustness

Comprehensive tests covering:
1. Optional steps: Omission of variable steps is tolerated and identified deterministically.
2. Intermediate noise: Bounded noise tolerance handles inserted clicks without swallowing long stretches.
3. Partial executions: Tracks partial executions without inflating distinct-session occurrence counts.
4. Variable session positions: Workflows detected at prefix, middle, or suffix positions in sessions.
5. Intra-session repetitions: Extra executions within the same session tracked separately from distinct sessions.
6. Single-session rejection: 3 repetitions in 1 session rejected without multi-session support.
7. Generic repeated action noise: Suppresses monotonous loops and 2-action ping-pong navigation loops.
8. Independent subsequences: Legitimate shorter workflows are preserved when supported by independent sessions.
9. Deterministic representative selection: Shuffled input orders and ties break deterministically.
10. Multiple valid workflows in same session: Co-occurring workflows do not starve each other.
11. Similar verbs on distinct entities: Distinct business workflows with matching verbs are not falsely merged.
12. Explainability consistency: Explanations accurately expose optional steps, partial support, and intra-reps.
13. Backward compatibility: Validates Phase 8.1, 8.2, 8.3, and 8.4 regressions across the full benchmark.
14. API serialization: Endpoints return clean JSON with all Phase 8.5 fields.
"""

import unittest
from fastapi.testclient import TestClient

from backend.main import app
from discovery.detector import RepetitionDetector, get_deterministic_label
from discovery.alignment import local_sequence_alignment, find_all_local_occurrences
from discovery.models import DiscoveredWorkflow, DiscoveryResult
from discovery.ranking import assess_candidate_noise, SuppressionReason
from discovery.evaluation import (
    build_synthetic_evaluation_dataset,
    build_phase8_2_evaluation_dataset,
    build_phase8_3_evaluation_dataset,
    build_phase8_5_evaluation_dataset,
    build_phase8_5_benchmark_dataset,
    evaluate_discovery_engine,
    validate_workflow_explanations,
)


class TestPhase85DiscoveryQualityAndRobustness(unittest.TestCase):
    """Core verification for Phase 8.5 discovery quality and robustness."""

    def setUp(self):
        self.detector = RepetitionDetector(
            min_length=3,
            min_occurrences=2,
            similarity_threshold=0.80,
            filter_noise=True,
            min_ranking_score=0.70,
        )
        self.client = TestClient(app)

    def test_optional_steps_detection(self):
        """Scenario A: Step present in some sessions but omitted in another is detected as optional."""
        canonical_5 = [
            "open_email",
            "download_attachment",
            "search_customer",
            "update_customer",
            "send_message",
        ]
        session_seqs = {
            "s1": list(canonical_5),
            "s2": ["open_email", "search_customer", "update_customer", "send_message"],  # omitted download_attachment
            "s3": list(canonical_5),
        }

        result = self.detector.detect(session_seqs)
        self.assertTrue(result.detected)
        self.assertEqual(len(result.workflows), 1)

        wf = result.workflows[0]
        self.assertEqual(wf.sequence, canonical_5)
        self.assertEqual(wf.occurrences, 3)
        self.assertIn("download_attachment", wf.optional_steps)
        self.assertIsNotNone(wf.explanation)
        self.assertIn("download_attachment", wf.explanation.sequence_evidence.optional_steps)
        self.assertIn("optional steps: download_attachment", wf.explanation.detection_reason)

    def test_intermediate_bounded_noise_tolerance(self):
        """Scenario B: 1-2 intermediate noise actions are tolerated, but excessive noise (>3) is bounded."""
        canonical_5 = [
            "open_email",
            "download_attachment",
            "search_customer",
            "update_customer",
            "send_message",
        ]
        # Bounded noise (1-2 clicks): should be tolerated
        session_seqs_bounded = {
            "s1": ["open_email", "download_attachment", "view_notifications", "search_customer", "update_customer", "send_message"],
            "s2": list(canonical_5),
            "s3": ["open_email", "download_attachment", "search_customer", "click_settings", "update_customer", "send_message"],
        }
        res_bounded = self.detector.detect(session_seqs_bounded)
        self.assertTrue(res_bounded.detected)
        self.assertEqual(len(res_bounded.workflows), 1)
        self.assertEqual(res_bounded.workflows[0].sequence, canonical_5)

        # Excessive noise (>3 consecutive noise actions between steps): should NOT match
        session_seqs_excessive = {
            "s1": list(canonical_5),
            "s2": [
                "open_email",
                "download_attachment",
                "noise_1",
                "noise_2",
                "noise_3",
                "noise_4",  # 4 consecutive insertions exceeds max_consecutive_insertions=3
                "search_customer",
                "update_customer",
                "send_message",
            ],
        }
        # Alignment check directly
        align = local_sequence_alignment(
            pattern=canonical_5,
            target=session_seqs_excessive["s2"],
            similarity_threshold=0.80,
            max_consecutive_insertions=3,
        )
        self.assertFalse(align.is_match)
        self.assertGreater(align.max_consecutive_insertions, 3)

    def test_partial_workflow_execution_tracking(self):
        """Scenario C: Partial execution does not count as full replay, but is tracked as partial support."""
        canonical_5 = [
            "open_email",
            "download_attachment",
            "search_customer",
            "update_customer",
            "send_message",
        ]
        session_seqs = {
            "s1": list(canonical_5),
            "s2": list(canonical_5),
            "s3": ["open_email", "download_attachment", "search_customer"],  # 3 of 5 steps
        }

        result = self.detector.detect(session_seqs)
        self.assertTrue(result.detected)
        self.assertEqual(len(result.workflows), 1)

        wf = result.workflows[0]
        # Full occurrences should strictly be 2 (s1, s2)
        self.assertEqual(wf.occurrences, 2)
        self.assertEqual(set(wf.session_ids), {"s1", "s2"})
        # Partial support should record s3
        self.assertEqual(wf.partial_support_count, 1)
        self.assertIn("s3", wf.partial_support_session_ids)
        self.assertIsNotNone(wf.explanation)
        self.assertEqual(wf.explanation.occurrence_evidence.partial_support_count, 1)
        self.assertIn("1 session(s) demonstrated partial workflow completion", wf.explanation.detection_reason)

    def test_workflow_position_in_session(self):
        """Scenario D: Workflow matches regardless of whether it appears at start, middle, or end of session."""
        canonical_5 = [
            "open_email",
            "download_attachment",
            "search_customer",
            "update_customer",
            "send_message",
        ]
        session_seqs = {
            "s1_start": list(canonical_5) + ["review_notes", "logout"],
            "s2_middle": ["login", "view_calendar"] + list(canonical_5) + ["close_window"],
            "s3_end": ["open_slack", "read_chat", "check_inbox"] + list(canonical_5),
        }

        result = self.detector.detect(session_seqs)
        self.assertTrue(result.detected)
        self.assertEqual(len(result.workflows), 1)

        wf = result.workflows[0]
        self.assertEqual(wf.sequence, canonical_5)
        self.assertEqual(wf.occurrences, 3)
        self.assertEqual(wf.similarity, 1.0)
        self.assertEqual(wf.explanation.sequence_evidence.exact_match_sessions_count, 3)

    def test_intra_session_repetitions(self):
        """Scenario E: Multiple executions in one session tracked as intra-session reps without inflating distinct sessions."""
        wf_doc_edit = ["open_document", "edit_document", "export_document"]
        session_seqs = {
            "s1": ["open_document", "edit_document", "export_document", "check_slack", "open_document", "edit_document", "export_document"],
            "s2": list(wf_doc_edit),
        }

        result = self.detector.detect(session_seqs)
        self.assertTrue(result.detected)
        self.assertEqual(len(result.workflows), 1)

        wf = result.workflows[0]
        self.assertEqual(wf.occurrences, 2)  # distinct sessions: s1, s2
        self.assertEqual(wf.intra_session_repetitions, 1)
        self.assertIsNotNone(wf.explanation)
        self.assertEqual(wf.explanation.occurrence_evidence.intra_session_repetitions, 1)
        self.assertIn("1 intra-session repetition(s) were observed", wf.explanation.detection_reason)

    def test_single_session_repetition_rejected(self):
        """Scenario 11 Regression: Multiple repetitions in only 1 session must not qualify as a discovered workflow."""
        session_seqs = {
            "s1_only": [
                "search_customer", "update_customer", "send_message",
                "search_customer", "update_customer", "send_message",
                "search_customer", "update_customer", "send_message",
            ],
            "s2_unrelated": ["edit_profile", "change_theme", "export_data"],
        }

        result = self.detector.detect(session_seqs)
        self.assertFalse(result.detected)
        self.assertEqual(len(result.workflows), 0)

    def test_generic_repeated_actions_suppressed(self):
        """Scenario F: Generic repeated loops (monotonous and alternating ping-pong) are suppressed."""
        # 1. Monotonous 1-action loop
        monotonous_seqs = {
            "s1": ["view_dashboard", "view_dashboard", "view_dashboard"],
            "s2": ["view_dashboard", "view_dashboard", "view_dashboard"],
        }
        res_mono = self.detector.detect(monotonous_seqs)
        self.assertFalse(res_mono.detected)
        self.assertEqual(len(res_mono.workflows), 0)

        # 2. Alternating 2-action ping-pong loop (open_tab, search_tab x 3)
        alternating_seqs = {
            "s1": ["open_tab", "search_tab", "open_tab", "search_tab", "open_tab", "search_tab"],
            "s2": ["open_tab", "search_tab", "open_tab", "search_tab", "open_tab", "search_tab"],
        }
        res_alt = self.detector.detect(alternating_seqs)
        self.assertFalse(res_alt.detected)
        self.assertEqual(len(res_alt.workflows), 0)

        # 3. Legitimate repeated action in high-diversity workflow MUST NOT be suppressed
        legit_repeated = ["open_document", "add_review_comment", "add_review_comment", "submit_approval"]
        res_legit = self.detector.detect({
            "s1": list(legit_repeated),
            "s2": list(legit_repeated),
            "s3": list(legit_repeated),
        })
        self.assertTrue(res_legit.detected)
        self.assertEqual(len(res_legit.workflows), 1)
        self.assertEqual(res_legit.workflows[0].sequence, legit_repeated)

    def test_independent_subsequences_preserved(self):
        """Scenario G: Shorter valid workflow is preserved when supported by independent sessions."""
        canonical_5 = [
            "open_email",
            "download_attachment",
            "search_customer",
            "update_customer",
            "send_message",
        ]
        crm_short_3 = ["search_customer", "update_customer", "send_message"]
        session_seqs = {
            "s1": list(canonical_5),
            "s2": list(canonical_5),
            "s3": list(crm_short_3),
            "s4": list(crm_short_3),
        }

        result = self.detector.detect(session_seqs)
        self.assertTrue(result.detected)
        self.assertEqual(len(result.workflows), 2)

        sequences = [w.sequence for w in result.workflows]
        self.assertIn(canonical_5, sequences)
        self.assertIn(crm_short_3, sequences)

    def test_deterministic_representative_selection(self):
        """Scenario 8 requirement: Representative selection is 100% deterministic regardless of session ordering."""
        canonical_5 = [
            "open_email",
            "download_attachment",
            "search_customer",
            "update_customer",
            "send_message",
        ]
        # Order 1: s1, s2, s3
        seqs_order1 = {
            "session_alpha": list(canonical_5),
            "session_beta": list(canonical_5),
            "session_gamma": list(canonical_5),
        }
        # Order 2: reversed keys and insertion order
        seqs_order2 = {
            "session_gamma": list(canonical_5),
            "session_beta": list(canonical_5),
            "session_alpha": list(canonical_5),
        }

        res1 = self.detector.detect(seqs_order1)
        res2 = self.detector.detect(seqs_order2)

        self.assertEqual(res1.workflows[0].label, res2.workflows[0].label)
        self.assertEqual(res1.workflows[0].sequence, res2.workflows[0].sequence)
        self.assertEqual(res1.workflows[0].ranking_score, res2.workflows[0].ranking_score)
        self.assertEqual(res1.workflows[0].confidence, res2.workflows[0].confidence)

    def test_multiple_valid_workflows_same_session(self):
        """Scenario I: Multiple valid workflows co-occurring in the same session do not starve each other."""
        wf_order = ["create_order", "process_payment", "pack_items", "dispatch_delivery"]
        wf_doc = ["open_document", "edit_document", "export_document"]

        session_seqs = {
            "s1": wf_order + ["browse_catalog", "check_metrics", "read_slack", "export_log"] + wf_doc,
            "s2": wf_order + ["manage_settings", "zoom_meeting", "take_notes", "save_preferences"] + wf_doc,
        }

        result = self.detector.detect(session_seqs)
        self.assertTrue(result.detected)
        self.assertEqual(len(result.workflows), 2)

        sequences = [w.sequence for w in result.workflows]
        self.assertIn(wf_order, sequences)
        self.assertIn(wf_doc, sequences)

    def test_similar_verbs_on_distinct_entities_kept_separate(self):
        """Scenario H: Customer Profile Management vs Product Catalog Update are kept separate."""
        wf_customer = ["search_customer", "open_customer", "update_customer"]
        wf_product = ["search_product", "open_product", "update_product"]

        session_seqs = {
            "s1": list(wf_customer),
            "s2": list(wf_customer),
            "s3": list(wf_product),
            "s4": list(wf_product),
        }

        result = self.detector.detect(session_seqs)
        self.assertTrue(result.detected)
        self.assertEqual(len(result.workflows), 2)

        labels = {w.label for w in result.workflows}
        self.assertIn("Customer Profile Management", labels)
        self.assertIn("Product Catalog Update", labels)

    def test_explanation_consistency(self):
        """Validates all Phase 8.5 discovered workflows have consistent explanations matching metrics."""
        dataset = build_phase8_5_benchmark_dataset()
        all_discovered = []
        for sc in dataset:
            res = self.detector.detect(sc.session_sequences, include_suppressed=True)
            all_discovered.extend(res.workflows)

        audit = validate_workflow_explanations(all_discovered)
        self.assertGreater(audit["workflows_evaluated"], 0)
        self.assertEqual(audit["workflows_evaluated"], audit["workflows_with_explanations"])
        self.assertEqual(audit["explainability_validity_rate"], 1.0)

    def test_backward_compatibility_regression(self):
        """Verifies that Phase 8.1, 8.2, 8.3, and 8.4 scenarios pass with high accuracy."""
        dataset = build_phase8_5_benchmark_dataset()
        report = evaluate_discovery_engine(detector=self.detector, dataset=dataset)

        self.assertEqual(report.total_scenarios, 33)
        self.assertGreaterEqual(report.precision, 0.90)
        self.assertGreaterEqual(report.recall, 0.95)
        self.assertGreaterEqual(report.f1_score, 0.94)
        self.assertGreaterEqual(report.accuracy, 0.90)

    from unittest.mock import patch

    @patch("backend.routes.discovery.discovery_service.get_repeated_workflows")
    def test_api_serialization(self, mock_get_repeated):
        """FastAPI route returns clean JSON with all Phase 8.5 fields."""
        canonical_5 = [
            "open_email",
            "download_attachment",
            "search_customer",
            "update_customer",
            "send_message",
        ]
        mock_wf = DiscoveredWorkflow(
            label="Customer Request Processing",
            sequence=canonical_5,
            occurrences=3,
            similarity=0.96,
            session_ids=["s1", "s2", "s3"],
            confidence=0.88,
            confidence_tier="high",
            rank=1,
            ranking_score=0.85,
            quality_tier="exceptional",
            optional_steps=["download_attachment"],
            partial_support_count=1,
            partial_support_session_ids=["s_partial"],
            intra_session_repetitions=2,
            explanation=None,
        )
        mock_get_repeated.return_value = DiscoveryResult(
            detected=True,
            workflows=[mock_wf],
            suppressed_workflows=[],
            total_candidates_evaluated=10,
        )

        response = self.client.get("/api/discovery/repeated")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["detected"])
        self.assertEqual(len(data["workflows"]), 1)
        wf = data["workflows"][0]

        # Verify Phase 8.5 fields are present in response JSON
        self.assertIn("optional_steps", wf)
        self.assertEqual(wf["optional_steps"], ["download_attachment"])
        self.assertIn("partial_support_count", wf)
        self.assertEqual(wf["partial_support_count"], 1)
        self.assertIn("intra_session_repetitions", wf)
        self.assertEqual(wf["intra_session_repetitions"], 2)
        self.assertIn("partial_support_session_ids", wf)
        self.assertEqual(wf["partial_support_session_ids"], ["s_partial"])


if __name__ == "__main__":
    unittest.main()
