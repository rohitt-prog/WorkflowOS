import difflib
import logging
from typing import Dict, List, Optional, Tuple
from discovery.confidence import calculate_pattern_confidence
from discovery.models import DiscoveredWorkflow, DiscoveryResult

logger = logging.getLogger(__name__)

# Known deterministic labels for canonical workflows (Phase 2 deterministic labeling)
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
}

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
    Avoids LLMs for Phase 2, using explicit rule matching.
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
    """

    def __init__(
        self,
        min_length: int = 3,
        min_occurrences: int = 2,
        similarity_threshold: float = 0.8,
        min_confidence: Optional[float] = None,
    ):
        self.min_length = min_length
        self.min_occurrences = min_occurrences
        self.similarity_threshold = similarity_threshold
        self.min_confidence = min_confidence

    def detect(self, session_sequences: Dict[str, List[str]]) -> DiscoveryResult:
        """
        Analyzes session sequences to find repeated patterns meeting criteria:
        - len(sequence) >= min_length
        - occurrences across distinct sessions >= min_occurrences
        - similarity >= similarity_threshold
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

        # Step 1: Count exact sequence patterns
        # Map: tuple(sequence) -> list of session_ids
        exact_clusters: Dict[Tuple[str, ...], List[str]] = {}
        for sid, seq in qualified_sessions.items():
            exact_clusters.setdefault(tuple(seq), []).append(sid)

        # Sort candidate patterns by number of exact occurrences descending, then by length descending
        sorted_patterns = sorted(
            exact_clusters.keys(),
            key=lambda p: (len(exact_clusters[p]), len(p)),
            reverse=True,
        )

        discovered_workflows: List[DiscoveredWorkflow] = []
        assigned_sessions = set()

        for pattern in sorted_patterns:
            canonical_seq = list(pattern)
            matched_sessions: List[Tuple[str, float]] = []

            # Add exact matching sessions
            for sid in exact_clusters[pattern]:
                if sid not in assigned_sessions:
                    matched_sessions.append((sid, 1.0))

            # Step 2: Check for near-match sessions using similarity threshold
            for sid, seq in qualified_sessions.items():
                if sid in assigned_sessions or any(sid == m[0] for m in matched_sessions):
                    continue
                sim = compute_sequence_similarity(canonical_seq, seq)
                if sim >= self.similarity_threshold:
                    matched_sessions.append((sid, sim))

            # Verify occurrence threshold
            if len(matched_sessions) >= self.min_occurrences:
                # Mark sessions as assigned
                for sid, _ in matched_sessions:
                    assigned_sessions.add(sid)

                avg_similarity = round(
                    sum(sim for _, sim in matched_sessions) / len(matched_sessions),
                    4,
                )
                session_ids = [sid for sid, _ in matched_sessions]
                sim_list = [sim for _, sim in matched_sessions]

                confidence, breakdown, tier, explanation = calculate_pattern_confidence(
                    sequence=canonical_seq,
                    occurrences=len(matched_sessions),
                    avg_similarity=avg_similarity,
                    session_similarities=sim_list,
                    min_length=self.min_length,
                    min_occurrences=self.min_occurrences,
                    similarity_threshold=self.similarity_threshold,
                )

                discovered_workflows.append(
                    DiscoveredWorkflow(
                        label=get_deterministic_label(canonical_seq),
                        sequence=canonical_seq,
                        occurrences=len(matched_sessions),
                        similarity=avg_similarity,
                        session_ids=session_ids,
                        confidence=confidence,
                        confidence_tier=tier,
                        confidence_breakdown=breakdown,
                        confidence_explanation=explanation,
                    )
                )

        # Optional confidence threshold filtering
        if self.min_confidence is not None:
            discovered_workflows = [
                w for w in discovered_workflows if w.confidence >= self.min_confidence
            ]

        # Order candidates by confidence descending, occurrences descending, length descending
        discovered_workflows.sort(
            key=lambda w: (w.confidence, w.occurrences, len(w.sequence)),
            reverse=True,
        )

        detected = len(discovered_workflows) > 0
        logger.info(
            f"Repetition detection completed: detected={detected}, "
            f"workflows_found={len(discovered_workflows)}"
        )
        return DiscoveryResult(detected=detected, workflows=discovered_workflows)


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
