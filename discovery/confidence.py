"""
WorkFlowOS Phase 8.1: Deterministic Discovery Confidence Scoring

Calculates transparent, bounded, and deterministic confidence scores for
discovered workflow patterns. Combines five orthogonal empirical signals:
1. Repetition Support (S_rep): Observation volume across distinct sessions (weight 0.30)
2. Sequence Similarity (S_sim): Alignment quality across matched sessions (weight 0.25)
3. Action Diversity (S_div): Task variety / entropy to penalize monotonous loops (weight 0.20)
4. Sequence Length / Complexity (S_len): Structural viability and intentionality (weight 0.15)
5. Session Consistency (S_cons): Proportion of exact replay instances (weight 0.10)
"""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


# Signal weights strictly sum to 1.00
SIGNAL_WEIGHTS = {
    "repetition_support": 0.30,
    "sequence_similarity": 0.25,
    "action_diversity": 0.20,
    "sequence_length": 0.15,
    "session_consistency": 0.10,
}

CONFIDENCE_TIER_HIGH = 0.80
CONFIDENCE_TIER_MEDIUM = 0.65


class ConfidenceBreakdown(BaseModel):
    """
    Structured breakdown of the five deterministic signals contributing to the confidence score.
    Each signal is normalized to [0.0, 1.0].
    """
    repetition_support: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Observation volume across distinct sessions (weight: 0.30)"
    )
    sequence_similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Average structural alignment across matched sessions (weight: 0.25)"
    )
    action_diversity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Ratio of unique actions in sequence; penalizes monotonous single-action loops (weight: 0.20)"
    )
    sequence_length: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Viability and complexity of the workflow sequence (weight: 0.15)"
    )
    session_consistency: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of exact 1.0 replay matches across participating sessions (weight: 0.10)"
    )
    raw_signals: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Underlying raw empirical measurements before normalization"
    )


def compute_repetition_support_signal(occurrences: int, min_required: int = 2) -> float:
    """
    Calculates S_rep in [0.0, 1.0].
    - Under min_required (2): 0.0 (insufficient evidence)
    - At min_required (2): 0.50 (minimum viable sample support)
    - 3 occurrences: 0.67
    - 4 occurrences: 0.83
    - 5+ occurrences: 1.00 (saturated empirical support)
    """
    if occurrences < min_required:
        return 0.0
    if occurrences >= 5:
        return 1.0
    # Linear interpolation between 2 and 5 occurrences
    return round(0.50 + 0.50 * ((occurrences - min_required) / 3.0), 4)


def compute_sequence_similarity_signal(avg_similarity: float, min_threshold: float = 0.80) -> float:
    """
    Calculates S_sim in [0.0, 1.0].
    - Below min_threshold: 0.0
    - At min_threshold (0.80): 0.60
    - At 1.00 (exact match): 1.00
    - Linear mapping across the [min_threshold, 1.00] window.
    """
    if avg_similarity < min_threshold:
        return 0.0
    if avg_similarity >= 1.0:
        return 1.0
    ratio = (avg_similarity - min_threshold) / (1.0 - min_threshold)
    return round(0.60 + 0.40 * ratio, 4)


def compute_action_diversity_signal(sequence: List[str]) -> float:
    """
    Calculates S_div in [0.0, 1.0].
    Penalizes monotonous repetitive actions (e.g. view_dashboard x 3) while
    rewarding workflows that combine distinct operational steps.
    - If length <= 1: 0.0
    - If all steps are identical (e.g. unique == 1): 0.10 (severe low-entropy penalty)
    - Otherwise: maps (unique - 1) / (length - 1) linearly to [0.10, 1.00].
    """
    length = len(sequence)
    if length <= 1:
        return 0.0
    unique_count = len(set(sequence))
    if unique_count <= 1:
        return 0.10
    if unique_count >= length:
        return 1.00

    # Scale between 0.10 and 1.00 based on proportion of distinct actions
    entropy_ratio = (unique_count - 1) / (length - 1)
    return round(0.10 + 0.90 * entropy_ratio, 4)


def compute_sequence_length_signal(length: int, min_length: int = 3) -> float:
    """
    Calculates S_len in [0.0, 1.0].
    - Below min_length (3): 0.0
    - At min_length (3): 0.60 (minimally viable)
    - At length 4: 0.80
    - At length >= 5: 1.00 (complete multi-step workflow)
    """
    if length < min_length:
        return 0.0
    if length >= 5:
        return 1.00
    return round(0.60 + 0.40 * ((length - min_length) / 2.0), 4)


def compute_session_consistency_signal(session_similarities: List[float]) -> float:
    """
    Calculates S_cons in [0.0, 1.0].
    Measures the ratio of exact matches (similarity == 1.0) among matched sessions.
    - If all sessions are exact replicas: 1.00
    - If no sessions are exact replicas: 0.50
    """
    if not session_similarities:
        return 0.50
    exact_count = sum(1 for s in session_similarities if s >= 0.999)
    exact_ratio = exact_count / len(session_similarities)
    return round(0.50 + 0.50 * exact_ratio, 4)


def determine_confidence_tier(score: float) -> str:
    """
    Categorizes the score into a human-readable confidence tier:
    - 'high': >= 0.80
    - 'medium': 0.65 <= score < 0.80
    - 'low': < 0.65
    """
    if score >= CONFIDENCE_TIER_HIGH:
        return "high"
    if score >= CONFIDENCE_TIER_MEDIUM:
        return "medium"
    return "low"


def generate_confidence_explanation(
    score: float,
    tier: str,
    occurrences: int,
    avg_similarity: float,
    sequence: List[str],
    breakdown: ConfidenceBreakdown,
) -> str:
    """
    Synthesizes a transparent, deterministic textual explanation of the confidence score.
    Does NOT use an LLM.
    """
    pct = int(round(score * 100))
    unique_count = len(set(sequence))
    length = len(sequence)

    highlights = []
    if occurrences >= 4:
        highlights.append(f"robust session support ({occurrences} sessions)")
    elif occurrences >= 2:
        highlights.append(f"valid repetition ({occurrences} sessions)")
    else:
        highlights.append(f"insufficient occurrences ({occurrences})")

    if avg_similarity >= 0.99:
        highlights.append("identical sequence alignment (100%)")
    elif avg_similarity >= 0.85:
        highlights.append(f"high sequence alignment ({int(avg_similarity * 100)}%)")
    else:
        highlights.append(f"moderate variation alignment ({int(avg_similarity * 100)}%)")

    if unique_count <= 1 and length > 1:
        highlights.append(f"low-entropy penalty (all {length} steps are identical action)")
    elif unique_count == length:
        highlights.append(f"high action variety ({unique_count}/{length} distinct steps)")
    else:
        highlights.append(f"{unique_count}/{length} distinct steps")

    explanation = f"{tier.capitalize()} confidence ({pct}%): " + ", ".join(highlights) + "."
    return explanation


def calculate_pattern_confidence(
    sequence: List[str],
    occurrences: int,
    avg_similarity: float,
    session_similarities: Optional[List[float]] = None,
    min_length: int = 3,
    min_occurrences: int = 2,
    similarity_threshold: float = 0.80,
) -> Tuple[float, ConfidenceBreakdown, str, str]:
    """
    Calculates the composite confidence score and supporting breakdown for a discovered workflow.

    Returns:
    - confidence: float bounded in [0.0, 1.0] rounded to 4 decimal places
    - breakdown: ConfidenceBreakdown
    - tier: 'high' | 'medium' | 'low'
    - explanation: Deterministic human-readable explanation
    """
    # Guard: insufficient sequence length or occurrences
    if len(sequence) < min_length or occurrences < min_occurrences:
        empty_breakdown = ConfidenceBreakdown(
            repetition_support=0.0,
            sequence_similarity=0.0,
            action_diversity=0.0,
            sequence_length=0.0,
            session_consistency=0.0,
            raw_signals={
                "occurrences": occurrences,
                "length": len(sequence),
                "unique_actions": len(set(sequence)),
                "avg_similarity": avg_similarity,
            },
        )
        return 0.0, empty_breakdown, "low", "Insufficient evidence: sequence or occurrences below discovery thresholds."

    sim_list = session_similarities if session_similarities is not None else [avg_similarity] * occurrences

    s_rep = compute_repetition_support_signal(occurrences, min_required=min_occurrences)
    s_sim = compute_sequence_similarity_signal(avg_similarity, min_threshold=similarity_threshold)
    s_div = compute_action_diversity_signal(sequence)
    s_len = compute_sequence_length_signal(len(sequence), min_length=min_length)
    s_cons = compute_session_consistency_signal(sim_list)

    raw_signals = {
        "occurrences": occurrences,
        "length": len(sequence),
        "unique_actions": len(set(sequence)),
        "avg_similarity": avg_similarity,
        "exact_matches_count": sum(1 for s in sim_list if s >= 0.999),
    }

    breakdown = ConfidenceBreakdown(
        repetition_support=s_rep,
        sequence_similarity=s_sim,
        action_diversity=s_div,
        sequence_length=s_len,
        session_consistency=s_cons,
        raw_signals=raw_signals,
    )

    composite = (
        SIGNAL_WEIGHTS["repetition_support"] * s_rep
        + SIGNAL_WEIGHTS["sequence_similarity"] * s_sim
        + SIGNAL_WEIGHTS["action_diversity"] * s_div
        + SIGNAL_WEIGHTS["sequence_length"] * s_len
        + SIGNAL_WEIGHTS["session_consistency"] * s_cons
    )

    # Strictly bound to [0.0, 1.0] and round to 4 decimal places
    confidence = round(max(0.0, min(1.0, composite)), 4)
    tier = determine_confidence_tier(confidence)
    explanation = generate_confidence_explanation(
        score=confidence,
        tier=tier,
        occurrences=occurrences,
        avg_similarity=avg_similarity,
        sequence=sequence,
        breakdown=breakdown,
    )

    return confidence, breakdown, tier, explanation
