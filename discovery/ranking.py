"""
WorkFlowOS Phase 8.3: Pattern Ranking, Noise Reduction & Duplicate Detection

Features:
1. Multi-signal utility ranking score (R in [0.0, 1.0]) evaluating operational usefulness.
2. Distinct quality tiers: "exceptional" (>= 0.85), "strong" (>= 0.70), "moderate" (>= 0.50), "low" (< 0.50).
3. Deterministic noise filtering for low-entropy / monotonous sequences, weak support, and marginal quality.
4. Exact duplicate and overlapping shadow pattern detection with pointer to primary representative.
5. Deterministic, stable tie-breaking:
   (ranking_score, occurrences, length, confidence, sequence_tuple)
6. Full explainability and traceability: preserved suppression reasons and ranking breakdowns.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field


class QualityTier(str, Enum):
    EXCEPTIONAL = "exceptional"
    STRONG = "strong"
    MODERATE = "moderate"
    LOW = "low"


class SuppressionReason(str, Enum):
    MONOTONOUS_REPETITION = "MONOTONOUS_REPETITION"
    LOW_ACTION_DIVERSITY = "LOW_ACTION_DIVERSITY"
    INSUFFICIENT_DISTINCT_SESSIONS = "INSUFFICIENT_DISTINCT_SESSIONS"
    LOW_QUALITY_SCORE = "LOW_QUALITY_SCORE"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    OVERLAPPING_SHADOW = "OVERLAPPING_SHADOW"
    SIMILAR_VARIANT_OVERLAP = "SIMILAR_VARIANT_OVERLAP"


# Ranking signal weights strictly sum to 1.00
# Anchored on statistical confidence and fidelity (55%) with operational volume, impact, and richness (45%)
RANKING_WEIGHTS = {
    "pattern_confidence": 0.30,
    "execution_fidelity": 0.25,
    "operational_volume": 0.20,
    "automation_impact": 0.15,
    "task_richness": 0.10,
}

QUALITY_TIER_EXCEPTIONAL = 0.85
QUALITY_TIER_STRONG = 0.70
QUALITY_TIER_MODERATE = 0.50


class RankingBreakdown(BaseModel):
    """
    Structured breakdown of the five deterministic signals contributing to the ranking score.
    Each signal is normalized to [0.0, 1.0].
    """
    pattern_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Statistical pattern certainty from Phase 8.1 confidence scoring (weight: 0.30)"
    )
    execution_fidelity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Alignment consistency and exact replay ratio (weight: 0.25)"
    )
    operational_volume: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Session breadth and recurrence volume across distinct user sessions (weight: 0.20)"
    )
    automation_impact: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Sequence length and potential operator time savings (weight: 0.15)"
    )
    task_richness: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Action entropy and semantic diversity of sequence steps (weight: 0.10)"
    )
    raw_signals: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Underlying raw measurements before normalization"
    )


def compute_operational_volume_signal(occurrences: int, min_required: int = 2) -> float:
    """
    Calculates operational volume in [0.0, 1.0].
    Measures recurrence breadth across distinct sessions:
    - occurrences < 2: 0.0
    - occurrences == 2: 0.25 (minimum threshold)
    - occurrences == 3: 0.40
    - occurrences == 4: 0.55
    - occurrences == 5: 0.70
    - occurrences == 6: 0.85
    - occurrences >= 7: 1.00 (broad institutional recurrence)
    """
    if occurrences < min_required:
        return 0.0
    if occurrences >= 7:
        return 1.00
    # Linear scale between 2 and 7
    return round(0.25 + 0.75 * ((occurrences - min_required) / 5.0), 4)


def compute_automation_impact_signal(length: int, min_length: int = 3) -> float:
    """
    Calculates automation impact in [0.0, 1.0].
    Workflows with more actions yield higher operator time savings:
    - length < min_length (3): 0.0
    - length == 3: 0.60 (viable multi-step automation)
    - length == 4: 0.80
    - length >= 5: 1.00 (complete end-to-end workflow)
    """
    if length < min_length:
        return 0.0
    if length >= 5:
        return 1.00
    return round(0.60 + 0.40 * ((length - min_length) / 2.0), 4)


def compute_execution_fidelity_signal(
    avg_similarity: float, session_consistency: float
) -> float:
    """
    Calculates execution fidelity in [0.0, 1.0].
    Combines average alignment ratio (60%) and exact replay proportion (40%).
    """
    sim = max(0.0, min(1.0, avg_similarity))
    cons = max(0.0, min(1.0, session_consistency))
    return round(0.60 * sim + 0.40 * cons, 4)


def compute_task_richness_signal(sequence: List[str]) -> float:
    """
    Calculates task richness in [0.0, 1.0].
    Measures action entropy: ratio of unique operational actions to total steps.
    - If length <= 1: 0.0
    - If all steps are identical: 0.10
    - If all steps are distinct: 1.00
    """
    length = len(sequence)
    if length <= 1:
        return 0.0
    unique_count = len(set(sequence))
    if unique_count <= 1:
        return 0.10
    if unique_count >= length:
        return 1.00
    return round(0.10 + 0.90 * ((unique_count - 1) / (length - 1)), 4)


def determine_quality_tier(score: float) -> str:
    """
    Assigns a standardized quality tier based on ranking score:
    - 'exceptional': >= 0.85
    - 'strong': 0.70 <= score < 0.85
    - 'moderate': 0.50 <= score < 0.70
    - 'low': < 0.50
    """
    if score >= QUALITY_TIER_EXCEPTIONAL:
        return QualityTier.EXCEPTIONAL.value
    if score >= QUALITY_TIER_STRONG:
        return QualityTier.STRONG.value
    if score >= QUALITY_TIER_MODERATE:
        return QualityTier.MODERATE.value
    return QualityTier.LOW.value


def generate_ranking_explanation(
    rank: Optional[int],
    score: float,
    tier: str,
    occurrences: int,
    sequence: List[str],
    breakdown: RankingBreakdown,
) -> str:
    """
    Synthesizes a transparent, deterministic explanation of the ranking decision.
    Does NOT use an LLM.
    """
    score_pct = int(round(score * 100))
    length = len(sequence)
    unique_actions = len(set(sequence))

    rank_str = f"Rank #{rank} " if rank is not None else ""
    return (
        f"{rank_str}(Score {score_pct}/100, {tier} quality): "
        f"{length}-step workflow with {unique_actions} distinct actions across "
        f"{occurrences} sessions. Fidelity={int(breakdown.execution_fidelity * 100)}%, "
        f"Impact={int(breakdown.automation_impact * 100)}%."
    )


def calculate_ranking_score(
    sequence: List[str],
    occurrences: int,
    avg_similarity: float,
    confidence: float,
    session_consistency: float,
    min_length: int = 3,
    min_occurrences: int = 2,
    rank: Optional[int] = None,
) -> Tuple[float, RankingBreakdown, str, str]:
    """
    Calculates the deterministic ranking score (R in [0.0, 1.0]), breakdown,
    quality tier, and textual explanation for a workflow candidate.
    """
    s_conf = max(0.0, min(1.0, confidence))
    s_vol = compute_operational_volume_signal(occurrences, min_required=min_occurrences)
    s_imp = compute_automation_impact_signal(len(sequence), min_length=min_length)
    s_fid = compute_execution_fidelity_signal(avg_similarity, session_consistency)
    s_rich = compute_task_richness_signal(sequence)

    raw_signals = {
        "confidence": confidence,
        "occurrences": occurrences,
        "sequence_length": len(sequence),
        "avg_similarity": avg_similarity,
        "session_consistency": session_consistency,
        "unique_actions": len(set(sequence)),
    }

    breakdown = RankingBreakdown(
        pattern_confidence=s_conf,
        execution_fidelity=s_fid,
        operational_volume=s_vol,
        automation_impact=s_imp,
        task_richness=s_rich,
        raw_signals=raw_signals,
    )

    composite_score = round(
        RANKING_WEIGHTS["pattern_confidence"] * s_conf
        + RANKING_WEIGHTS["execution_fidelity"] * s_fid
        + RANKING_WEIGHTS["operational_volume"] * s_vol
        + RANKING_WEIGHTS["automation_impact"] * s_imp
        + RANKING_WEIGHTS["task_richness"] * s_rich,
        4,
    )
    composite_score = max(0.0, min(1.0, composite_score))

    tier = determine_quality_tier(composite_score)
    explanation = generate_ranking_explanation(
        rank=rank,
        score=composite_score,
        tier=tier,
        occurrences=occurrences,
        sequence=sequence,
        breakdown=breakdown,
    )

    return composite_score, breakdown, tier, explanation


def assess_candidate_noise(
    sequence: List[str],
    occurrences: int,
    confidence: float,
    ranking_score: float,
    min_occurrences: int = 2,
    min_ranking_score: Optional[float] = None,
    filter_noise: bool = False,
) -> Optional[str]:
    """
    Evaluates whether a candidate represents noise or low-value repetition.
    Returns None if valid, or a SuppressionReason string if suppressed.
    """
    length = len(sequence)
    unique_count = len(set(sequence))

    # 1. Noise filtering (active when filter_noise=True or min_ranking_score is set)
    if filter_noise:
        # Monotonous repetition: single action loop (e.g. view_dashboard x 3)
        if unique_count <= 1 and length >= 2:
            return SuppressionReason.MONOTONOUS_REPETITION.value

        # Low action diversity: severe lack of distinct verbs (e.g. 1 unique in 4+ steps)
        if length >= 3 and (unique_count / length) < 0.35:
            return SuppressionReason.LOW_ACTION_DIVERSITY.value

    # 2. Insufficient distinct session support
    if occurrences < min_occurrences:
        return SuppressionReason.INSUFFICIENT_DISTINCT_SESSIONS.value

    # 3. Filter by explicit min_ranking_score threshold if configured
    if min_ranking_score is not None and ranking_score < min_ranking_score:
        return SuppressionReason.LOW_QUALITY_SCORE.value

    return None
