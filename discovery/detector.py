"""
WorkFlowOS Phase 8.2: Smarter Sequence Detection with Local Alignment

Features:
1. Local sequence alignment finding repeated workflows embedded inside longer, noisy sessions.
2. Tolerates inserted actions (extra intermediate steps), missing actions (deletions),
   and small adjacent step transpositions (e.g. A->B vs B->A) within strict, calibrated bounds.
3. Multi-session candidate extraction (full sessions, pairwise LCS, and frequent n-grams).
4. Strict distinct-session occurrence tracking (prevents a single session with internal repetitions
   from inflating occurrences).
5. Shadow pruning & deduplication to separate genuinely distinct workflows (e.g. shared-prefix workflows)
   from redundant sub-slices or noisy variants.
6. Deterministic output ordering by confidence descending, occurrences descending, length descending.
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
    Avoids LLMs for Phase 2/8.2, using explicit rule matching.
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
    Enhanced in Phase 8.2 with local alignment, pairwise LCS candidate generation,
    and distinct-session occurrence tracking.
    """

    def __init__(
        self,
        min_length: int = 3,
        min_occurrences: int = 2,
        similarity_threshold: float = 0.8,
        min_confidence: Optional[float] = None,
        max_candidate_length: int = 15,
    ):
        self.min_length = min_length
        self.min_occurrences = min_occurrences
        self.similarity_threshold = similarity_threshold
        self.min_confidence = min_confidence
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

    def detect(self, session_sequences: Dict[str, List[str]]) -> DiscoveryResult:
        """
        Analyzes session sequences to find repeated patterns meeting criteria:
        - len(sequence) >= min_length
        - occurrences across distinct sessions >= min_occurrences
        - similarity >= similarity_threshold (via local alignment)
        - confidence >= min_confidence (if specified)
        """
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
            return DiscoveryResult(detected=False, workflows=[])

        # Step 1: Generate candidates
        candidate_patterns = self._generate_candidate_patterns(qualified_sessions)

        # Step 2: Evaluate candidates against sessions with local alignment
        evaluated_candidates = []

        for pattern_tuple in candidate_patterns:
            pattern = list(pattern_tuple)
            matched_sessions: List[Tuple[str, float]] = []

            for sid, seq in qualified_sessions.items():
                align_res = local_sequence_alignment(
                    pattern=pattern,
                    target=seq,
                    similarity_threshold=self.similarity_threshold,
                )
                if align_res.is_match:
                    # Each session ID can only match ONCE per candidate pattern
                    matched_sessions.append((sid, align_res.similarity))

            # Verify occurrence threshold across distinct sessions
            if len(matched_sessions) >= self.min_occurrences:
                avg_similarity = round(
                    sum(sim for _, sim in matched_sessions) / len(matched_sessions),
                    4,
                )
                exact_count = sum(1 for _, sim in matched_sessions if sim >= 0.999)
                session_ids = [sid for sid, _ in matched_sessions]
                sim_list = [sim for _, sim in matched_sessions]

                confidence, breakdown, tier, explanation = calculate_pattern_confidence(
                    sequence=pattern,
                    occurrences=len(matched_sessions),
                    avg_similarity=avg_similarity,
                    session_similarities=sim_list,
                    min_length=self.min_length,
                    min_occurrences=self.min_occurrences,
                    similarity_threshold=self.similarity_threshold,
                )

                evaluated_candidates.append({
                    "sequence": pattern,
                    "occurrences": len(matched_sessions),
                    "similarity": avg_similarity,
                    "exact_count": exact_count,
                    "session_ids": session_ids,
                    "confidence": confidence,
                    "confidence_tier": tier,
                    "confidence_breakdown": breakdown,
                    "confidence_explanation": explanation,
                })

        # Sort evaluated candidates deterministically:
        # Highest confidence first, occurrences desc, length desc, exact_count desc, tuple desc
        evaluated_candidates.sort(
            key=lambda c: (
                c["confidence"],
                c["occurrences"],
                len(c["sequence"]),
                c["exact_count"],
                tuple(c["sequence"]),
            ),
            reverse=True,
        )

        # Step 3: Deduplication and Shadow Pruning
        accepted_workflows: List[DiscoveredWorkflow] = []
        accepted_metadata: List[Dict] = []

        for cand in evaluated_candidates:
            c_seq = cand["sequence"]
            c_actions = set(c_seq)
            c_sessions = set(cand["session_ids"])
            is_redundant = False

            # Subsumption Case 1: If c_seq is completely covered across its supporting sessions
            # by already-accepted longer workflows that contain c_seq as a subsequence
            sub_covered_sessions = set()
            for acc in accepted_metadata:
                a_seq = acc["sequence"]
                a_sessions = set(acc["session_ids"])
                if len(c_seq) < len(a_seq) and is_subsequence(c_seq, a_seq):
                    sub_covered_sessions.update(c_sessions & a_sessions)

            if len(c_sessions) > 0 and (len(sub_covered_sessions) / len(c_sessions)) >= 0.80:
                is_redundant = True

            if not is_redundant:
                for acc in accepted_metadata:
                    a_seq = acc["sequence"]
                    a_actions = set(a_seq)
                    a_sessions = set(acc["session_ids"])

                    # If c has sufficient independent sessions outside a, it cannot be subsumed by a
                    independent_sessions = c_sessions - a_sessions
                    if len(independent_sessions) >= self.min_occurrences:
                        continue

                    # Check action and session overlaps
                    act_overlap = len(c_actions & a_actions) / len(c_actions)
                    sess_overlap = len(c_sessions & a_sessions) / len(c_sessions)

                    # Subsumption Case 2: c_seq is a strict subsequence of a_seq with high session overlap
                    if len(c_seq) < len(a_seq) and is_subsequence(c_seq, a_seq):
                        if sess_overlap >= 0.70:
                            is_redundant = True
                            break

                    # Subsumption Case 3: c_seq and a_seq share majority actions and sessions (shadow pattern)
                    if act_overlap >= 0.60 and sess_overlap >= 0.60:
                        is_redundant = True
                        break

            if not is_redundant:
                accepted_metadata.append(cand)
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
                    )
                )

        # Optional confidence threshold filtering
        if self.min_confidence is not None:
            accepted_workflows = [
                w for w in accepted_workflows if w.confidence >= self.min_confidence
            ]

        # Order final candidates deterministically
        accepted_workflows.sort(
            key=lambda w: (w.confidence, w.occurrences, len(w.sequence), tuple(w.sequence)),
            reverse=True,
        )

        detected = len(accepted_workflows) > 0
        logger.info(
            f"Repetition detection completed: detected={detected}, "
            f"workflows_found={len(accepted_workflows)}"
        )
        return DiscoveryResult(detected=detected, workflows=accepted_workflows)


def detect_repeated_workflows(
    session_sequences: Dict[str, List[str]],
    min_length: int = 3,
    min_occurrences: int = 2,
    similarity_threshold: float = 0.8,
    min_confidence: Optional[float] = None,
) -> DiscoveryResult:
    """
    Convenience function to run the RepetitionDetector.
    """
    detector = RepetitionDetector(
        min_length=min_length,
        min_occurrences=min_occurrences,
        similarity_threshold=similarity_threshold,
        min_confidence=min_confidence,
    )
    return detector.detect(session_sequences)
