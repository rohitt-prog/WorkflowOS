"""
WorkFlowOS Phase 8.3: Smarter Sequence Detection with Pattern Ranking & Noise Reduction

Features:
1. Local sequence alignment finding repeated workflows embedded inside longer, noisy sessions.
2. Multi-session candidate extraction (full sessions, pairwise LCS, and frequent n-grams).
3. Strict distinct-session occurrence tracking.
4. Deterministic multi-signal utility ranking score (R in [0.0, 1.0]) evaluating automation usefulness.
5. Quality tier classification: 'exceptional', 'strong', 'moderate', and 'low'.
6. Deterministic noise filtering for low-entropy/monotonous loops and marginal candidates.
7. Exact duplicate and overlapping shadow pattern detection with pointer to primary representative.
8. Deterministic output ordering by ranking_score descending, occurrences descending, length descending.
"""

import difflib
import logging
from typing import Dict, List, Optional, Set, Tuple

from discovery.alignment import (
    compute_longest_common_subsequence,
    local_sequence_alignment,
)
from discovery.confidence import calculate_pattern_confidence
from discovery.models import DiscoveredWorkflow, DiscoveryResult
from discovery.ranking import (
    SuppressionReason,
    assess_candidate_noise,
    calculate_ranking_score,
    generate_ranking_explanation,
)
from discovery.explanation import build_workflow_explanation

logger = logging.getLogger(__name__)

# Known deterministic labels for canonical workflows (deterministic display labels)
KNOWN_WORKFLOW_LABELS: Dict[Tuple[str, ...], str] = {
    (
        "open_email",
        "download_attachment",
        "search_customer",
        "update_customer",
        "send_message",
    ): "Customer Request Processing",
    (
        "search_customer",
        "update_customer",
        "send_message",
    ): "Customer Account Tier Update",
    (
        "open_email",
        "download_attachment",
    ): "Attachment Retrieval Routine",
    (
        "open_email",
        "download_attachment",
        "record_payment",
        "send_receipt",
        "archive_thread",
    ): "Billing & Payment Processing",
    (
        "open_email",
        "download_attachment",
        "create_ticket",
        "assign_agent",
        "send_acknowledgement",
    ): "Support Ticket Routine",
    (
        "create_order",
        "process_payment",
        "pack_items",
        "dispatch_delivery",
    ): "Order Fulfillment Routine",
    (
        "create_order",
        "cancel_order",
        "refund_payment",
        "restock_items",
    ): "Order Cancellation Routine",
    (
        "open_document",
        "add_review_comment",
        "add_review_comment",
        "submit_approval",
    ): "Document Review & Approval Routine",
    (
        "open_document",
        "edit_document",
        "export_document",
    ): "Document Editing Routine",
}


def is_subsequence(sub: List[str], super_seq: List[str]) -> bool:
    """
    Checks if 'sub' is an ordered subsequence of 'super_seq'.
    """
    if not sub:
        return True
    if len(sub) > len(super_seq):
        return False
    it = iter(super_seq)
    return all(x in it for x in sub)


def compute_sequence_similarity(seq_a: List[str], seq_b: List[str]) -> float:
    """
    Computes a deterministic similarity score between two event type sequences
    using difflib.SequenceMatcher.
    Returns a float between 0.0 (completely dissimilar) and 1.0 (identical).
    """
    if not seq_a and not seq_b:
        return 1.0
    if not seq_a or not seq_b:
        return 0.0
    if seq_a == seq_b:
        return 1.0

    matcher = difflib.SequenceMatcher(None, seq_a, seq_b)
    return round(matcher.ratio(), 4)


def get_deterministic_label(sequence: List[str]) -> str:
    """
    Assigns a human-readable deterministic display label based on the sequence.
    Avoids LLMs for Phase 2/8.3, using explicit rule matching.
    """
    seq_tuple = tuple(sequence)
    if seq_tuple in KNOWN_WORKFLOW_LABELS:
        return KNOWN_WORKFLOW_LABELS[seq_tuple]

    # Partial match check for primary 5-step workflow
    primary_key = (
        "open_email",
        "download_attachment",
        "search_customer",
        "update_customer",
        "send_message",
    )
    if all(step in sequence for step in primary_key):
        return "Customer Request Processing"

    return "Repeated Workflow"


class RepetitionDetector:
    """
    Deterministic repetition detector for finding recurring event sequences across sessions.
    Enhanced in Phase 8.3 with local alignment, multi-signal pattern ranking,
    noise filtering, and duplicate/shadow suppression.
    """

    def __init__(
        self,
        min_length: int = 3,
        min_occurrences: int = 2,
        similarity_threshold: float = 0.8,
        min_confidence: Optional[float] = None,
        min_ranking_score: Optional[float] = None,
        filter_noise: bool = False,
        include_suppressed: bool = False,
        max_candidate_length: int = 15,
    ):
        self.min_length = min_length
        self.min_occurrences = min_occurrences
        self.similarity_threshold = similarity_threshold
        self.min_confidence = min_confidence
        self.min_ranking_score = min_ranking_score
        self.filter_noise = filter_noise
        self.include_suppressed = include_suppressed
        self.max_candidate_length = max_candidate_length

    def _generate_candidate_patterns(
        self, qualified_sessions: Dict[str, List[str]]
    ) -> List[Tuple[str, ...]]:
        """
        Extracts candidate pattern sequences from qualified sessions using:
        1. Exact full session sequences
        2. Pairwise Longest Common Subsequences (LCS)
        3. Contiguous n-grams of viable lengths
        """
        candidates: Set[Tuple[str, ...]] = set()
        session_list = list(qualified_sessions.values())
        num_sessions = len(session_list)

        # 1. Full session sequences
        for s in session_list:
            if len(s) <= self.max_candidate_length:
                candidates.add(tuple(s))

        # 2. Pairwise LCS across distinct sessions
        for i in range(num_sessions):
            for j in range(i + 1, min(num_sessions, i + 25)):
                lcs = compute_longest_common_subsequence(session_list[i], session_list[j])
                if len(lcs) >= self.min_length:
                    candidates.add(tuple(lcs))

        # 3. Frequent contiguous n-grams from sessions
        for s in session_list:
            length = len(s)
            for k in range(self.min_length, min(length + 1, min(10, self.max_candidate_length + 1))):
                for start in range(0, length - k + 1):
                    candidates.add(tuple(s[start : start + k]))

        # Deterministic candidate sorting: length desc, diversity desc, lexicographical tuple
        sorted_candidates = sorted(
            candidates,
            key=lambda c: (len(c), len(set(c)), c),
            reverse=True,
        )
        return sorted_candidates

    def detect(
        self,
        session_sequences: Dict[str, List[str]],
        include_suppressed: Optional[bool] = None,
        min_ranking_score: Optional[float] = None,
        filter_noise: Optional[bool] = None,
    ) -> DiscoveryResult:
        """
        Analyzes session sequences to find repeated patterns meeting criteria:
        - len(sequence) >= min_length
        - occurrences across distinct sessions >= min_occurrences
        - similarity >= similarity_threshold (via local alignment)
        - confidence >= min_confidence (if specified)
        - ranking_score >= min_ranking_score (if specified)
        """
        effective_include_suppressed = (
            include_suppressed if include_suppressed is not None else self.include_suppressed
        )
        effective_min_ranking = (
            min_ranking_score if min_ranking_score is not None else self.min_ranking_score
        )
        effective_filter_noise = (
            filter_noise if filter_noise is not None else self.filter_noise
        )

        # Filter sessions by minimum required event count
        qualified_sessions = {
            sid: seq
            for sid, seq in session_sequences.items()
            if len(seq) >= self.min_length
        }

        if len(qualified_sessions) < self.min_occurrences:
            logger.info(
                f"Insufficient qualified sessions for repetition detection "
                f"({len(qualified_sessions)} < {self.min_occurrences})."
            )
            return DiscoveryResult(detected=False, workflows=[], suppressed_workflows=[], total_candidates_evaluated=0)

        # Step 1: Generate candidates
        candidate_patterns = self._generate_candidate_patterns(qualified_sessions)

        # Step 2: Evaluate candidates against sessions with local alignment
        evaluated_candidates = []

        for pattern_tuple in candidate_patterns:
            pattern = list(pattern_tuple)
            matched_sessions: List[Tuple[str, Any]] = []

            for sid, seq in qualified_sessions.items():
                align_res = local_sequence_alignment(
                    pattern=pattern,
                    target=seq,
                    similarity_threshold=self.similarity_threshold,
                )
                if align_res.is_match:
                    # Each session ID can only match ONCE per candidate pattern
                    matched_sessions.append((sid, align_res))

            # Verify occurrence threshold across distinct sessions
            if len(matched_sessions) >= self.min_occurrences:
                sim_list = [ar.similarity for _, ar in matched_sessions]
                alignment_results = [ar for _, ar in matched_sessions]
                avg_similarity = round(
                    sum(sim_list) / len(sim_list),
                    4,
                )
                exact_count = sum(1 for ar in alignment_results if ar.similarity >= 0.999)
                session_ids = [sid for sid, _ in matched_sessions]

                # Phase 8.1 Confidence Scoring
                confidence, breakdown, tier, explanation = calculate_pattern_confidence(
                    sequence=pattern,
                    occurrences=len(matched_sessions),
                    avg_similarity=avg_similarity,
                    session_similarities=sim_list,
                    min_length=self.min_length,
                    min_occurrences=self.min_occurrences,
                    similarity_threshold=self.similarity_threshold,
                )

                # Phase 8.3 Ranking Scoring
                session_consistency = round(
                    0.50 + 0.50 * (exact_count / len(matched_sessions)), 4
                ) if matched_sessions else 0.50

                r_score, r_breakdown, r_tier, r_expl = calculate_ranking_score(
                    sequence=pattern,
                    occurrences=len(matched_sessions),
                    avg_similarity=avg_similarity,
                    confidence=confidence,
                    session_consistency=session_consistency,
                    min_length=self.min_length,
                    min_occurrences=self.min_occurrences,
                )

                evaluated_candidates.append({
                    "sequence": pattern,
                    "occurrences": len(matched_sessions),
                    "similarity": avg_similarity,
                    "exact_count": exact_count,
                    "session_ids": session_ids,
                    "alignment_results": alignment_results,
                    "session_similarities": sim_list,
                    "confidence": confidence,
                    "confidence_tier": tier,
                    "confidence_breakdown": breakdown,
                    "confidence_explanation": explanation,
                    "ranking_score": r_score,
                    "ranking_breakdown": r_breakdown,
                    "quality_tier": r_tier,
                    "ranking_explanation": r_expl,
                    "session_consistency": session_consistency,
                    "is_duplicate": False,
                    "representative_pattern_id": None,
                    "representative_workflow": None,
                    "suppression_reason": None,
                })

        # Initial sort by confidence & ranking:
        # Highest confidence first, ranking_score desc, occurrences desc, length desc, exact_count desc, tuple desc
        evaluated_candidates.sort(
            key=lambda c: (
                c["confidence"],
                c["ranking_score"],
                c["occurrences"],
                len(c["sequence"]),
                c["exact_count"],
                tuple(c["sequence"]),
            ),
            reverse=True,
        )

        # Step 3: Noise Reduction, Duplicate Detection, and Shadow Pruning
        accepted_metadata: List[Dict] = []
        suppressed_candidates: List[Dict] = []

        for cand in evaluated_candidates:
            c_seq = cand["sequence"]
            c_actions = set(c_seq)
            c_sessions = set(cand["session_ids"])

            # 3A. Noise Assessment
            noise_reason = assess_candidate_noise(
                sequence=c_seq,
                occurrences=cand["occurrences"],
                confidence=cand["confidence"],
                ranking_score=cand["ranking_score"],
                min_occurrences=self.min_occurrences,
                min_ranking_score=effective_min_ranking,
                filter_noise=effective_filter_noise,
            )
            if noise_reason:
                cand["is_duplicate"] = False
                cand["suppression_reason"] = noise_reason
                suppressed_candidates.append(cand)
                continue

            # 3B. Exact Duplicate Check
            is_exact_dup = False
            for acc in accepted_metadata:
                if acc["sequence"] == c_seq:
                    cand["is_duplicate"] = True
                    cand["suppression_reason"] = SuppressionReason.EXACT_DUPLICATE.value
                    cand["representative_pattern_id"] = get_deterministic_label(acc["sequence"])
                    cand["representative_workflow"] = acc
                    is_exact_dup = True
                    break
            if is_exact_dup:
                suppressed_candidates.append(cand)
                continue

            # 3C. Shadow Pruning & Overlap Resolution
            is_redundant = False
            rep_label: Optional[str] = None
            rep_reason: Optional[str] = None
            rep_workflow_dict: Optional[Dict[str, Any]] = None

            # Subsumption Case 1: Multi-parent complete session coverage across accepted super-sequences
            sub_covered_sessions = set()
            covering_label: Optional[str] = None
            covering_acc: Optional[Dict[str, Any]] = None
            for acc in accepted_metadata:
                a_seq = acc["sequence"]
                a_sessions = set(acc["session_ids"])
                if len(c_seq) < len(a_seq) and is_subsequence(c_seq, a_seq):
                    sub_covered_sessions.update(c_sessions & a_sessions)
                    if not covering_label:
                        covering_label = get_deterministic_label(a_seq)
                        covering_acc = acc

            independent_outside_super = c_sessions - sub_covered_sessions
            if (
                len(c_sessions) > 0
                and len(independent_outside_super) < self.min_occurrences
                and (len(sub_covered_sessions) / len(c_sessions)) >= 0.80
            ):
                is_redundant = True
                rep_label = covering_label
                rep_reason = SuppressionReason.OVERLAPPING_SHADOW.value
                rep_workflow_dict = covering_acc

            if not is_redundant:
                for acc in accepted_metadata:
                    a_seq = acc["sequence"]
                    a_actions = set(a_seq)
                    a_sessions = set(acc["session_ids"])

                    # If c has sufficient independent sessions outside a, it cannot be subsumed by a
                    independent_sessions = c_sessions - a_sessions
                    if len(independent_sessions) >= self.min_occurrences:
                        continue

                    # Subsumption Case 2: c_seq is a strict subsequence of a_seq with majority session overlap
                    if len(c_seq) < len(a_seq) and is_subsequence(c_seq, a_seq):
                        sess_overlap = len(c_sessions & a_sessions) / len(c_sessions)
                        if sess_overlap >= 0.70:
                            is_redundant = True
                            rep_label = get_deterministic_label(a_seq)
                            rep_reason = SuppressionReason.OVERLAPPING_SHADOW.value
                            rep_workflow_dict = acc
                            break

                    # Subsumption Case 3: Near-duplicate variant with high alignment and session overlap
                    sim = compute_sequence_similarity(c_seq, a_seq)
                    sess_overlap = len(c_sessions & a_sessions) / len(c_sessions)
                    if sim >= 0.85 and sess_overlap >= 0.75:
                        is_redundant = True
                        rep_label = get_deterministic_label(a_seq)
                        rep_reason = SuppressionReason.SIMILAR_VARIANT_OVERLAP.value
                        rep_workflow_dict = acc
                        break

                    # Subsumption Case 4: c_seq and a_seq share majority actions and sessions (shadow pattern)
                    if len(c_seq) <= len(a_seq):
                        act_overlap = len(c_actions & a_actions) / len(c_actions)
                        if act_overlap >= 0.60 and sess_overlap >= 0.60:
                            is_redundant = True
                            rep_label = get_deterministic_label(a_seq)
                            rep_reason = SuppressionReason.OVERLAPPING_SHADOW.value
                            rep_workflow_dict = acc
                            break

            if is_redundant:
                cand["is_duplicate"] = True
                cand["suppression_reason"] = rep_reason or SuppressionReason.OVERLAPPING_SHADOW.value
                cand["representative_pattern_id"] = rep_label
                cand["representative_workflow"] = rep_workflow_dict
                suppressed_candidates.append(cand)
            else:
                accepted_metadata.append(cand)

        # 3D. Optional Confidence Filter
        if self.min_confidence is not None:
            filtered_accepted = []
            for w in accepted_metadata:
                if w["confidence"] >= self.min_confidence:
                    filtered_accepted.append(w)
                else:
                    w["suppression_reason"] = "LOW_CONFIDENCE"
                    w["is_duplicate"] = False
                    suppressed_candidates.append(w)
            accepted_metadata = filtered_accepted

        # 3E. Deterministic Final Ordering & Rank Assignment
        # Sort by ranking_score desc, occurrences desc, length desc, confidence desc, tuple desc
        accepted_metadata.sort(
            key=lambda w: (
                round(w["ranking_score"], 4),
                w["occurrences"],
                len(w["sequence"]),
                round(w["confidence"], 4),
                tuple(w["sequence"]),
            ),
            reverse=True,
        )

        accepted_workflows: List[DiscoveredWorkflow] = []
        for rank_idx, cand in enumerate(accepted_metadata, start=1):
            cand["rank"] = rank_idx
            # Regenerate explanation with assigned rank
            cand["ranking_explanation"] = generate_ranking_explanation(
                rank=rank_idx,
                score=cand["ranking_score"],
                tier=cand["quality_tier"],
                occurrences=cand["occurrences"],
                sequence=cand["sequence"],
                breakdown=cand["ranking_breakdown"],
            )

            # Phase 8.4 Structured Explainability Model
            cand["explanation"] = build_workflow_explanation(
                sequence=cand["sequence"],
                occurrences=cand["occurrences"],
                avg_similarity=cand["similarity"],
                session_ids=cand["session_ids"],
                confidence=cand["confidence"],
                confidence_tier=cand["confidence_tier"],
                confidence_breakdown=cand["confidence_breakdown"],
                confidence_explanation=cand["confidence_explanation"],
                rank=rank_idx,
                ranking_score=cand["ranking_score"],
                quality_tier=cand["quality_tier"],
                ranking_breakdown=cand["ranking_breakdown"],
                ranking_explanation=cand["ranking_explanation"],
                alignment_results=cand.get("alignment_results"),
                session_similarities=cand.get("session_similarities"),
                is_duplicate=False,
                suppression_reason=None,
                representative_pattern_id=get_deterministic_label(cand["sequence"]),
                min_length=self.min_length,
                min_occurrences=self.min_occurrences,
                similarity_threshold=self.similarity_threshold,
                min_ranking_score=effective_min_ranking,
            )

            accepted_workflows.append(
                DiscoveredWorkflow(
                    label=get_deterministic_label(cand["sequence"]),
                    sequence=cand["sequence"],
                    occurrences=cand["occurrences"],
                    similarity=cand["similarity"],
                    session_ids=cand["session_ids"],
                    confidence=cand["confidence"],
                    confidence_tier=cand["confidence_tier"],
                    confidence_breakdown=cand["confidence_breakdown"],
                    confidence_explanation=cand["confidence_explanation"],
                    rank=cand["rank"],
                    ranking_score=cand["ranking_score"],
                    quality_tier=cand["quality_tier"],
                    ranking_breakdown=cand["ranking_breakdown"],
                    ranking_explanation=cand["ranking_explanation"],
                    is_duplicate=cand["is_duplicate"],
                    representative_pattern_id=cand["representative_pattern_id"],
                    suppression_reason=cand["suppression_reason"],
                    explanation=cand["explanation"],
                )
            )

        suppressed_workflows: List[DiscoveredWorkflow] = []
        for cand in suppressed_candidates:
            # Phase 8.4 Structured Explainability Model for Suppressed Candidates
            cand["explanation"] = build_workflow_explanation(
                sequence=cand["sequence"],
                occurrences=cand["occurrences"],
                avg_similarity=cand["similarity"],
                session_ids=cand["session_ids"],
                confidence=cand["confidence"],
                confidence_tier=cand["confidence_tier"],
                confidence_breakdown=cand["confidence_breakdown"],
                confidence_explanation=cand["confidence_explanation"],
                rank=None,
                ranking_score=cand["ranking_score"],
                quality_tier=cand["quality_tier"],
                ranking_breakdown=cand["ranking_breakdown"],
                ranking_explanation=cand["ranking_explanation"],
                alignment_results=cand.get("alignment_results"),
                session_similarities=cand.get("session_similarities"),
                is_duplicate=cand.get("is_duplicate", False),
                suppression_reason=cand.get("suppression_reason"),
                representative_pattern_id=cand.get("representative_pattern_id"),
                representative_workflow=cand.get("representative_workflow"),
                min_length=self.min_length,
                min_occurrences=self.min_occurrences,
                similarity_threshold=self.similarity_threshold,
                min_ranking_score=effective_min_ranking,
            )

            suppressed_workflows.append(
                DiscoveredWorkflow(
                    label=get_deterministic_label(cand["sequence"]),
                    sequence=cand["sequence"],
                    occurrences=cand["occurrences"],
                    similarity=cand["similarity"],
                    session_ids=cand["session_ids"],
                    confidence=cand["confidence"],
                    confidence_tier=cand["confidence_tier"],
                    confidence_breakdown=cand["confidence_breakdown"],
                    confidence_explanation=cand["confidence_explanation"],
                    rank=None,
                    ranking_score=cand["ranking_score"],
                    quality_tier=cand["quality_tier"],
                    ranking_breakdown=cand["ranking_breakdown"],
                    ranking_explanation=cand["ranking_explanation"],
                    is_duplicate=cand["is_duplicate"],
                    representative_pattern_id=cand["representative_pattern_id"],
                    suppression_reason=cand["suppression_reason"],
                    explanation=cand["explanation"],
                )
            )

        detected = len(accepted_workflows) > 0
        logger.info(
            f"Repetition detection completed: detected={detected}, "
            f"workflows_found={len(accepted_workflows)}, "
            f"suppressed_candidates={len(suppressed_workflows)}"
        )
        return DiscoveryResult(
            detected=detected,
            workflows=accepted_workflows,
            suppressed_workflows=suppressed_workflows if effective_include_suppressed else [],
            total_candidates_evaluated=len(evaluated_candidates),
        )


def detect_repeated_workflows(
    session_sequences: Dict[str, List[str]],
    min_length: int = 3,
    min_occurrences: int = 2,
    similarity_threshold: float = 0.8,
    min_confidence: Optional[float] = None,
    min_ranking_score: Optional[float] = None,
    filter_noise: bool = False,
    include_suppressed: bool = False,
) -> DiscoveryResult:
    """
    Convenience function to run the RepetitionDetector.
    """
    detector = RepetitionDetector(
        min_length=min_length,
        min_occurrences=min_occurrences,
        similarity_threshold=similarity_threshold,
        min_confidence=min_confidence,
        min_ranking_score=min_ranking_score,
        filter_noise=filter_noise,
        include_suppressed=include_suppressed,
    )
    return detector.detect(session_sequences)


