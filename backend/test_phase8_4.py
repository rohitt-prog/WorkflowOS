"""
WorkFlowOS Phase 8.4 Test Suite: Explainable Discovery

Comprehensive tests covering:
1. Explainability Model Validation & Serialization
2. Detection Explanations (Exact matches, inserted noise, adjacent transpositions)
3. Confidence & Ranking Factors (Strengths, limits, quality tier reasons)
4. Suppression & Duplicate Explanations (Monotonous loops, marginal quality, shadows, variants)
5. Representative Selection & Independent Sub-Sequence Preservation
6. Similar but Distinct Workflows with Grounded Explanations
7. Deterministic Stability (Identical inputs -> identical explanations)
8. Privacy & Sensitive Data Exclusion (Masked session IDs, no credential leaks)
9. FastAPI Route Integration & Response Schema Compatibility
10. Phase 8.1, 8.2, and 8.3 Regression Behavior
"""

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from discovery.detector import RepetitionDetector, get_deterministic_label
from discovery.explanation import (
    OccurrenceEvidence,
    SequenceEvidence,
    ConsistencyEvidence,
    ConfidenceFactorBreakdown,
    RankingFactorBreakdown,
    SuppressionEvidence,
    WorkflowExplanation,
    build_workflow_explanation,
    mask_session_id,
)
from discovery.models import DiscoveredWorkflow, DiscoveryResult
from discovery.ranking import QualityTier, SuppressionReason
from discovery.evaluation import (
    build_complete_benchmark_dataset,
    validate_workflow_explanations,
)


class TestExplainabilityModelValidation(unittest.TestCase):
    """Verifies that explainability models enforce data contracts and validation."""

    def test_workflow_explanation_serialization_and_deserialization(self):
        exp = WorkflowExplanation(
            summary="Ranked #1 · 5-step workflow with 90/100 exceptional quality.",
            detection_reason="Qualified across 4 sessions with 100% exact replays.",
            supporting_sessions=["session_101", "session_102"],
            occurrence_evidence=OccurrenceEvidence(
                distinct_sessions_observed=2,
                min_sessions_required=2,
                threshold_satisfied=True,
                repetition_description="Observed across 2 sessions (satisfies >= 2 threshold).",
            ),
            sequence_evidence=SequenceEvidence(
                canonical_sequence=["open_email", "search_customer", "send_message"],
                sequence_length=3,
                unique_actions_count=3,
                action_diversity_ratio=1.0,
                average_alignment_score=1.0,
                exact_match_sessions_count=2,
                approximate_match_sessions_count=0,
                total_insertions_observed=0,
                total_deletions_observed=0,
                total_transpositions_observed=0,
                variations_summary="Zero structural variations observed.",
            ),
            consistency_evidence=ConsistencyEvidence(
                exact_replay_percentage=100.0,
                is_fully_consistent=True,
                consistency_description="100.0% of supporting sessions executed in identical order.",
            ),
            confidence_explanation="High confidence (90%): identical sequence alignment.",
            confidence_factors=ConfidenceFactorBreakdown(
                score=0.90,
                tier="high",
                primary_strengths=["Identical sequence alignment"],
                limiting_factors=[],
            ),
            ranking_explanation="Rank #1: Top tier candidate.",
            ranking_factors=RankingFactorBreakdown(
                score=0.90,
                rank=1,
                tier="exceptional",
                primary_drivers=["High confidence", "Flawless fidelity"],
                limiting_factors=[],
            ),
            quality_explanation="Exceptional quality (90/100): High automation priority.",
            suppression_explanation=None,
            suppression_evidence=None,
            representative_explanation="Selected as canonical representative workflow.",
            limitations=["Heuristic Ranking disclaimer", "Empirical Scope disclaimer"],
        )

        data = exp.model_dump()
        self.assertIn("summary", data)
        self.assertIn("sequence_evidence", data)
        self.assertEqual(data["sequence_evidence"]["sequence_length"], 3)
        self.assertEqual(len(data["limitations"]), 2)

        # Roundtrip deserialization
        restored = WorkflowExplanation.model_validate(data)
        self.assertEqual(restored.summary, exp.summary)
        self.assertEqual(restored.sequence_evidence.canonical_sequence, ["open_email", "search_customer", "send_message"])

    def test_mask_session_id_privacy(self):
        self.assertEqual(mask_session_id("session_101"), "session_101")
        self.assertEqual(mask_session_id("user.john.doe@company.com"), "***@company.com")
        long_hash = "a1b2c3d4e5f678901234567890abcdef"
        masked_hash = mask_session_id(long_hash)
        self.assertTrue(masked_hash.startswith("a1b2c3..."))
        self.assertNotIn("1234567890", masked_hash)


class TestEvidenceGroundedDetectionExplanations(unittest.TestCase):
    """Verifies that explanations are grounded in real sequence alignment metrics."""

    def setUp(self):
        self.detector = RepetitionDetector(min_length=3, min_occurrences=2, similarity_threshold=0.8)

    def test_scenario_1_exact_repeated_sequence_explanation(self):
        """1. Exact repeated sequence has grounded 100% fidelity explanation."""
        sessions = {
            "session_01": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
            "session_02": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
            "session_03": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        self.assertEqual(len(res.workflows), 1)

        wf = res.workflows[0]
        self.assertIsNotNone(wf.explanation)
        exp = wf.explanation

        # Verify factual alignment evidence
        self.assertEqual(exp.occurrence_evidence.distinct_sessions_observed, 3)
        self.assertEqual(exp.sequence_evidence.sequence_length, 5)
        self.assertEqual(exp.sequence_evidence.exact_match_sessions_count, 3)
        self.assertEqual(exp.sequence_evidence.approximate_match_sessions_count, 0)
        self.assertEqual(exp.sequence_evidence.total_insertions_observed, 0)
        self.assertEqual(exp.sequence_evidence.total_transpositions_observed, 0)
        self.assertEqual(exp.consistency_evidence.exact_replay_percentage, 100.0)
        self.assertTrue(exp.consistency_evidence.is_fully_consistent)
        self.assertIn("100% exact match", exp.detection_reason)
        self.assertIn("Zero structural variations", exp.sequence_evidence.variations_summary)

    def test_scenario_2_inserted_actions_explanation(self):
        """2. Similar sequences with inserted actions have grounded insertion explanations."""
        sessions = {
            "session_01": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
            "session_02": ["open_email", "download_attachment", "random_note", "search_customer", "update_customer", "send_message"],
            "session_03": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        self.assertEqual(len(res.workflows), 1)

        wf = res.workflows[0]
        self.assertIsNotNone(wf.explanation)
        exp = wf.explanation

        # 2 exact sessions, 1 session with 1 inserted step
        self.assertEqual(exp.sequence_evidence.exact_match_sessions_count, 2)
        self.assertEqual(exp.sequence_evidence.approximate_match_sessions_count, 1)
        self.assertGreaterEqual(exp.sequence_evidence.total_insertions_observed, 1)
        self.assertIn("inserted", exp.sequence_evidence.variations_summary.lower())
        self.assertFalse(exp.consistency_evidence.is_fully_consistent)
        self.assertAlmostEqual(exp.consistency_evidence.exact_replay_percentage, 66.7, delta=0.5)

    def test_scenario_3_adjacent_transposition_explanation(self):
        """3. Adjacent step reordering tolerated with grounded transposition explanation."""
        sessions = {
            "session_01": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
            "session_02": ["open_email", "search_customer", "download_attachment", "update_customer", "send_message"],  # swap steps 1 and 2
            "session_03": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        self.assertEqual(len(res.workflows), 1)

        wf = res.workflows[0]
        self.assertIsNotNone(wf.explanation)
        exp = wf.explanation

        self.assertGreaterEqual(exp.sequence_evidence.total_transpositions_observed, 1)
        self.assertIn("adjacent step", exp.sequence_evidence.variations_summary.lower())
        self.assertIn("transposition", exp.detection_reason.lower() + exp.sequence_evidence.variations_summary.lower())

    def test_scenario_4_high_confidence_limited_session_support(self):
        """4. High confidence with limited session support explains the trade-off."""
        sessions = {
            "session_01": ["open_document", "edit_document", "save_document", "export_document", "close_document"],
            "session_02": ["open_document", "edit_document", "save_document", "export_document", "close_document"],
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        wf = res.workflows[0]
        exp = wf.explanation

        # 2 sessions is the minimum threshold: volume signal is modest, but similarity is 1.0
        self.assertGreaterEqual(wf.confidence, 0.80)
        self.assertEqual(exp.occurrence_evidence.distinct_sessions_observed, 2)
        # Limiting factor must explicitly note limited session volume
        all_limits = exp.confidence_factors.limiting_factors + exp.ranking_factors.limiting_factors
        self.assertTrue(any("2 sessions" in lim or "volume" in lim.lower() for lim in all_limits))

    def test_scenario_5_low_confidence_inconsistent_sessions(self):
        """5. Inconsistent sessions note session variations in consistency evidence."""
        sessions = {
            "session_01": ["search_customer", "note_a", "update_customer", "note_b", "send_message"],
            "session_02": ["search_customer", "update_customer", "send_message"],
            "session_03": ["search_customer", "note_c", "update_customer", "send_message"],
        }
        res = self.detector.detect(sessions)
        self.assertTrue(res.detected)
        wf = res.workflows[0]
        exp = wf.explanation

        self.assertLess(exp.consistency_evidence.exact_replay_percentage, 100.0)
        self.assertFalse(exp.consistency_evidence.is_fully_consistent)
        self.assertIn("variations", exp.consistency_evidence.consistency_description.lower())


class TestSuppressionAndDuplicateExplanations(unittest.TestCase):
    """Verifies that candidate suppressions are grounded and explainable."""

    def test_monotonous_repeated_actions_suppression_explanation(self):
        """7. Monotonous single-action loops are suppressed with explicit reasons and evidence."""
        sessions = {
            "session_01": ["view_dashboard", "view_dashboard", "view_dashboard"],
            "session_02": ["view_dashboard", "view_dashboard", "view_dashboard"],
            "session_03": ["view_dashboard", "view_dashboard", "view_dashboard"],
        }
        detector = RepetitionDetector(min_length=3, filter_noise=True, min_ranking_score=0.70)
        res = detector.detect(sessions, include_suppressed=True)

        self.assertFalse(res.detected)
        self.assertGreater(len(res.suppressed_workflows), 0)

        supp = res.suppressed_workflows[0]
        self.assertEqual(supp.suppression_reason, SuppressionReason.MONOTONOUS_REPETITION.value)
        self.assertIsNotNone(supp.explanation)
        self.assertIn("monotonous", supp.explanation.summary.lower())
        self.assertIn("view_dashboard", supp.explanation.suppression_explanation)
        self.assertIsNotNone(supp.explanation.suppression_evidence)
        self.assertIn("1 unique action", supp.explanation.suppression_evidence.measured_value)

    def test_exact_duplicate_suppression_and_representative_link(self):
        """8. Exact duplicate candidates link to the canonical representative with clear rationale."""
        sessions = {
            "session_01": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
            "session_02": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
            "session_03": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
        }
        detector = RepetitionDetector(min_length=3, filter_noise=True)
        res = detector.detect(sessions, include_suppressed=True)

        self.assertTrue(res.detected)
        canonical = res.workflows[0]

        # Check suppressed candidates for overlapping shadows or duplicates
        self.assertGreater(len(res.suppressed_workflows), 0)
        shadow = res.suppressed_workflows[0]
        self.assertIsNotNone(shadow.representative_pattern_id)
        self.assertEqual(shadow.representative_pattern_id, canonical.label)
        self.assertIsNotNone(shadow.explanation)
        self.assertIn(canonical.label, shadow.explanation.suppression_explanation)

    def test_valid_subsequence_with_independent_sessions_preserved(self):
        """9. Valid sub-sequence with independent sessions is not suppressed and explains independence."""
        sessions = {
            # Super-workflow in sessions 1, 2
            "session_01": ["step_a", "step_b", "step_c", "step_d", "step_e"],
            "session_02": ["step_a", "step_b", "step_c", "step_d", "step_e"],
            # Sub-workflow executed standalone in sessions 3, 4, 5
            "session_03": ["step_a", "step_b", "step_c"],
            "session_04": ["step_a", "step_b", "step_c"],
            "session_05": ["step_a", "step_b", "step_c"],
        }
        detector = RepetitionDetector(min_length=3, filter_noise=False)
        res = detector.detect(sessions)

        # Both the super-workflow and the sub-workflow must be preserved
        self.assertEqual(len(res.workflows), 2)
        sequences = [w.sequence for w in res.workflows]
        self.assertIn(["step_a", "step_b", "step_c", "step_d", "step_e"], sequences)
        self.assertIn(["step_a", "step_b", "step_c"], sequences)

        # Both must have valid explainability structures
        for wf in res.workflows:
            self.assertIsNotNone(wf.explanation)
            self.assertTrue(wf.explanation.occurrence_evidence.threshold_satisfied)

    def test_similar_looking_distinct_workflows_distinct_explanations(self):
        """10. Two similar-looking but distinct workflows have distinct explainability profiles."""
        sessions = {
            "session_01": ["open_doc", "read_clause", "update_contract", "sign_doc"],
            "session_02": ["open_doc", "read_clause", "update_contract", "sign_doc"],
            "session_03": ["open_doc", "read_clause", "reject_contract", "sign_doc"],
            "session_04": ["open_doc", "read_clause", "reject_contract", "sign_doc"],
        }
        detector = RepetitionDetector(min_length=3, filter_noise=False)
        res = detector.detect(sessions)

        self.assertEqual(len(res.workflows), 2)
        wf_update = next(w for w in res.workflows if "update_contract" in w.sequence)
        wf_reject = next(w for w in res.workflows if "reject_contract" in w.sequence)

        self.assertIn("update_contract", wf_update.explanation.sequence_evidence.canonical_sequence)
        self.assertIn("reject_contract", wf_reject.explanation.sequence_evidence.canonical_sequence)
        self.assertNotEqual(wf_update.explanation.supporting_sessions, wf_reject.explanation.supporting_sessions)


class TestExplainabilityAPIAndDeterminism(unittest.TestCase):
    """Verifies API backward compatibility, determinism, and full benchmark pass."""

    def setUp(self):
        self.client = TestClient(app)

    @patch("backend.routes.discovery.discovery_service.get_repeated_workflows")
    def test_api_repeated_workflows_returns_explanation(self, mock_get_repeated):
        mock_exp = build_workflow_explanation(
            sequence=["open_email", "download_attachment", "search_customer"],
            occurrences=3,
            avg_similarity=1.0,
            session_ids=["s1", "s2", "s3"],
            confidence=0.92,
            confidence_tier="high",
            confidence_breakdown=None,
            confidence_explanation="High confidence: identical alignment.",
            rank=1,
            ranking_score=0.88,
            quality_tier="exceptional",
            ranking_breakdown=None,
            ranking_explanation="Rank #1: Top tier.",
            is_duplicate=False,
            representative_pattern_id="Customer Request Processing",
        )
        mock_wf = DiscoveredWorkflow(
            label="Customer Request Processing",
            sequence=["open_email", "download_attachment", "search_customer"],
            occurrences=3,
            similarity=1.0,
            session_ids=["s1", "s2", "s3"],
            confidence=0.92,
            confidence_tier="high",
            rank=1,
            ranking_score=0.88,
            quality_tier="exceptional",
            is_duplicate=False,
            explanation=mock_exp,
        )
        mock_supp_exp = build_workflow_explanation(
            sequence=["open_email", "download_attachment"],
            occurrences=3,
            avg_similarity=1.0,
            session_ids=["s1", "s2", "s3"],
            confidence=0.80,
            confidence_tier="medium",
            confidence_breakdown=None,
            confidence_explanation="Medium confidence.",
            rank=None,
            ranking_score=0.60,
            quality_tier="moderate",
            ranking_breakdown=None,
            ranking_explanation="Rank none.",
            is_duplicate=True,
            suppression_reason="OVERLAPPING_SHADOW",
            representative_pattern_id="Customer Request Processing",
        )
        mock_suppressed = DiscoveredWorkflow(
            label="Customer Request Processing",
            sequence=["open_email", "download_attachment"],
            occurrences=3,
            similarity=1.0,
            session_ids=["s1", "s2", "s3"],
            confidence=0.80,
            is_duplicate=True,
            representative_pattern_id="Customer Request Processing",
            suppression_reason="OVERLAPPING_SHADOW",
            explanation=mock_supp_exp,
        )
        mock_get_repeated.return_value = DiscoveryResult(
            detected=True,
            workflows=[mock_wf],
            suppressed_workflows=[mock_suppressed],
            total_candidates_evaluated=5,
        )

        response = self.client.get("/api/discovery/repeated?include_suppressed=true")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["detected"])
        self.assertEqual(len(data["workflows"]), 1)
        wf = data["workflows"][0]
        self.assertIn("explanation", wf)
        exp = wf["explanation"]
        self.assertIn("summary", exp)
        self.assertIn("detection_reason", exp)
        self.assertIn("sequence_evidence", exp)
        self.assertIn("consistency_evidence", exp)
        self.assertIn("limitations", exp)
        self.assertEqual(exp["sequence_evidence"]["sequence_length"], 3)
        self.assertEqual(exp["occurrence_evidence"]["distinct_sessions_observed"], 3)

        # Suppressed workflow validation
        self.assertEqual(len(data["suppressed_workflows"]), 1)
        sw = data["suppressed_workflows"][0]
        self.assertIn("explanation", sw)
        sexp = sw["explanation"]
        self.assertEqual(sw["suppression_reason"], "OVERLAPPING_SHADOW")
        self.assertIsNotNone(sexp["suppression_explanation"])
        self.assertEqual(sw["representative_pattern_id"], "Customer Request Processing")

    def test_deterministic_explanation_generation(self):
        """Identical session inputs must produce 100% identical explanation objects."""
        sessions = {
            "session_1": ["open_email", "download_attachment", "search_customer", "update_customer"],
            "session_2": ["open_email", "download_attachment", "search_customer", "update_customer"],
        }
        det1 = RepetitionDetector(min_length=3)
        det2 = RepetitionDetector(min_length=3)

        res1 = det1.detect(sessions)
        res2 = det2.detect(sessions)

        self.assertEqual(res1.workflows[0].explanation.model_dump(), res2.workflows[0].explanation.model_dump())

    def test_full_benchmark_dataset_explainability_audit(self):
        """All 24 synthetic benchmark scenarios have mathematically consistent explanations."""
        dataset = build_complete_benchmark_dataset()
        detector = RepetitionDetector(min_length=3, min_occurrences=2, similarity_threshold=0.8, filter_noise=True, min_ranking_score=0.70)

        all_workflows = []
        for sc in dataset:
            res = detector.detect(sc.session_sequences, include_suppressed=True)
            all_workflows.extend(res.workflows)

        audit = validate_workflow_explanations(all_workflows)
        self.assertEqual(audit["workflows_evaluated"], 22)
        self.assertEqual(audit["workflows_with_explanations"], 22)
        self.assertEqual(audit["explainability_validity_rate"], 1.0)
        self.assertEqual(audit["checks_passed"], audit["total_checks"])


class TestPhase84RegressionAndPrivacy(unittest.TestCase):
    """Verifies that privacy boundaries and Phase 8.1/8.2/8.3 contracts remain intact."""

    def test_privacy_no_unmasked_credentials_in_explanations(self):
        """Explanations must never contain sensitive credentials, secrets, or raw emails."""
        sessions = {
            "user.sensitive@example.com": ["open_email", "download_attachment", "search_customer"],
            "session_clean_002": ["open_email", "download_attachment", "search_customer"],
        }
        detector = RepetitionDetector(min_length=3)
        res = detector.detect(sessions)
        self.assertTrue(res.detected)
        wf = res.workflows[0]
        self.assertIsNotNone(wf.explanation)

        # Check masked sessions
        self.assertIn("***@example.com", wf.explanation.supporting_sessions)
        self.assertNotIn("user.sensitive@example.com", wf.explanation.supporting_sessions)

        # Ensure explanation text does not leak raw tokens or passwords
        exp_json = wf.explanation.model_dump_json()
        self.assertNotIn("user.sensitive", exp_json)
        self.assertNotIn("password", exp_json.lower())
        self.assertNotIn("token", exp_json.lower().replace("transposition", ""))

    def test_phase8_1_confidence_fields_backward_compatibility(self):
        """Phase 8.1 confidence fields and breakdowns must remain present and accurate."""
        sessions = {
            "session_01": ["open_email", "download_attachment", "search_customer"],
            "session_02": ["open_email", "download_attachment", "search_customer"],
        }
        detector = RepetitionDetector(min_length=3)
        res = detector.detect(sessions)
        self.assertTrue(res.detected)
        wf = res.workflows[0]

        self.assertIsNotNone(wf.confidence)
        self.assertIsNotNone(wf.confidence_tier)
        self.assertIsNotNone(wf.confidence_breakdown)
        self.assertIsNotNone(wf.confidence_explanation)
        self.assertGreaterEqual(wf.confidence, 0.70)

    def test_phase8_2_local_alignment_backward_compatibility(self):
        """Phase 8.2 embedded workflow extraction and local alignment remain functional."""
        canonical = ["step_a", "step_b", "step_c", "step_d", "step_e"]
        sessions = {
            "s1": ["login", "view_home"] + list(canonical) + ["logout"],
            "s2": ["refresh_feed", "open_browser"] + list(canonical),
            "s3": list(canonical) + ["close_tab", "archive_session"],
        }
        detector = RepetitionDetector(min_length=4)
        res = detector.detect(sessions)
        self.assertTrue(res.detected)
        wf = res.workflows[0]
        self.assertEqual(wf.sequence, canonical)
        self.assertIsNotNone(wf.explanation)
        self.assertEqual(wf.explanation.sequence_evidence.sequence_length, 5)

    def test_phase8_3_ranking_and_quality_tiers_backward_compatibility(self):
        """Phase 8.3 utility scores, ranks, and quality tiers remain present and deterministic."""
        sessions = {
            "s1": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
            "s2": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
            "s3": ["open_email", "download_attachment", "search_customer", "update_customer", "send_message"],
        }
        detector = RepetitionDetector(min_length=3)
        res = detector.detect(sessions)
        self.assertTrue(res.detected)
        wf = res.workflows[0]

        self.assertEqual(wf.rank, 1)
        self.assertIsNotNone(wf.ranking_score)
        self.assertIn(wf.quality_tier, ["exceptional", "strong", "moderate", "low"])
        self.assertIsNotNone(wf.ranking_breakdown)
        self.assertFalse(wf.is_duplicate)


if __name__ == "__main__":
    unittest.main()
