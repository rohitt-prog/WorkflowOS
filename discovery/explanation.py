"""
WorkFlowOS Phase 8.4: Explainable Discovery

Provides structured, deterministic, and transparent explainability models
and generation functions for discovered workflows.

Features:
1. Explain why a pattern qualified as a repeated workflow with real thresholds and counts.
2. Ground explanations strictly in observed empirical evidence (no LLMs, no hallucinated steps).
3. Sequence alignment evidence detailing exact replays, tolerated insertions, deletions, and transpositions.
4. Session consistency breakdown distinguishing identical replays from approximate variations.
5. Structured confidence drivers and limiting factors.
6. Structured ranking utility drivers and quality tier rationales.
7. Explicit suppression explanations with measured values vs. thresholds and canonical representative links.
8. Clear identification of limitations, distinguishing observed facts from heuristic interpretations.
9. Privacy-preserving safe session identifiers.
"""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from discovery.ranking import (
    QualityTier,
    SuppressionReason,
    RANKING_WEIGHTS,
    QUALITY_TIER_EXCEPTIONAL,
    QUALITY_TIER_STRONG,
    QUALITY_TIER_MODERATE,
)
from discovery.confidence import (
    SIGNAL_WEIGHTS as CONFIDENCE_WEIGHTS,
    CONFIDENCE_TIER_HIGH,
    CONFIDENCE_TIER_MEDIUM,
)
from discovery.alignment import LocalAlignmentResult


class OccurrenceEvidence(BaseModel):
    """
    Evidence detailing session adoption and occurrence count thresholds.
    """
    distinct_sessions_observed: int = Field(
        ...,
        description="Count of distinct sessions where this pattern was observed"
    )
    min_sessions_required: int = Field(
        ...,
        description="Configured minimum distinct sessions threshold (min_occurrences)"
    )
    threshold_satisfied: bool = Field(
        ...,
        description="Whether the candidate met or exceeded the distinct session requirement"
    )
    repetition_description: str = Field(
        ...,
        description="Human-readable summary of repetition volume and threshold satisfaction"
    )


class SequenceEvidence(BaseModel):
    """
    Empirical sequence evidence derived from local sequence alignment.
    """
    canonical_sequence: List[str] = Field(
        ...,
        description="Canonical ordered sequence of action verbs"
    )
    sequence_length: int = Field(
        ...,
        description="Total number of steps in the canonical sequence"
    )
    unique_actions_count: int = Field(
        ...,
        description="Number of distinct action verbs in the sequence"
    )
    action_diversity_ratio: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Ratio of unique action verbs to total sequence length"
    )
    average_alignment_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Mean local alignment similarity across all supporting sessions"
    )
    exact_match_sessions_count: int = Field(
        ...,
        ge=0,
        description="Number of sessions that executed the exact sequence (100% match)"
    )
    approximate_match_sessions_count: int = Field(
        ...,
        ge=0,
        description="Number of sessions that matched with tolerated structural variations"
    )
    total_insertions_observed: int = Field(
        default=0,
        ge=0,
        description="Total inserted intermediate actions across all matched sessions"
    )
    total_deletions_observed: int = Field(
        default=0,
        ge=0,
        description="Total omitted actions across all matched sessions"
    )
    total_transpositions_observed: int = Field(
        default=0,
        ge=0,
        description="Total adjacent step swaps across all matched sessions"
    )
    variations_summary: str = Field(
        ...,
        description="Concise description of observed alignment variations or lack thereof"
    )


class ConsistencyEvidence(BaseModel):
    """
    Evidence evaluating the structural consistency of session replays.
    """
    exact_replay_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of supporting sessions that are exact 100% replays"
    )
    is_fully_consistent: bool = Field(
        ...,
        description="True if 100% of supporting sessions were exact replays"
    )
    consistency_description: str = Field(
        ...,
        description="Human-readable evaluation of session consistency"
    )


class ConfidenceFactorBreakdown(BaseModel):
    """
    Structured breakdown of factors influencing the confidence score.
    """
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Composite confidence score"
    )
    tier: str = Field(
        ...,
        description="Assigned confidence tier: 'high', 'medium', or 'low'"
    )
    primary_strengths: List[str] = Field(
        default_factory=list,
        description="Top empirical factors supporting high confidence"
    )
    limiting_factors: List[str] = Field(
        default_factory=list,
        description="Factors that reduced or penalized confidence"
    )


class RankingFactorBreakdown(BaseModel):
    """
    Structured breakdown of factors influencing the ranking score and rank.
    """
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Composite utility ranking score"
    )
    rank: Optional[int] = Field(
        default=None,
        description="Assigned 1-based rank among discovered patterns"
    )
    tier: str = Field(
        ...,
        description="Assigned quality tier: 'exceptional', 'strong', 'moderate', or 'low'"
    )
    primary_drivers: List[str] = Field(
        default_factory=list,
        description="Top signals driving the ranking score"
    )
    limiting_factors: List[str] = Field(
        default_factory=list,
        description="Signals limiting or depressing the ranking score"
    )


class SuppressionEvidence(BaseModel):
    """
    Structured details explaining why a candidate was suppressed, filtered, or deduplicated.
    """
    is_suppressed: bool = Field(
        default=False,
        description="True if the candidate was filtered, suppressed, or deduplicated"
    )
    suppression_reason: Optional[str] = Field(
        default=None,
        description="Machine-readable suppression reason code"
    )
    threshold_criterion: Optional[str] = Field(
        default=None,
        description="Configured rule or threshold applied during evaluation"
    )
    measured_value: Optional[str] = Field(
        default=None,
        description="Actual measured metric that triggered suppression"
    )
    representative_pattern_id: Optional[str] = Field(
        default=None,
        description="Identifier of the canonical representative workflow if duplicate/shadow"
    )
    representative_rationale: Optional[str] = Field(
        default=None,
        description="Rationale explaining why the representative was chosen over this candidate"
    )


class WorkflowExplanation(BaseModel):
    """
    Comprehensive, structured, and validated explainability model for a discovered workflow candidate.
    Grounded exclusively in computed metrics and observed events.
    """
    summary: str = Field(
        ...,
        description="Concise human-readable explanation of why this workflow was discovered"
    )
    detection_reason: str = Field(
        ...,
        description="Detailed criteria explaining why the candidate qualified as a repeated workflow"
    )
    supporting_sessions: List[str] = Field(
        ...,
        description="Safe identifiers of sessions that executed this pattern"
    )
    occurrence_evidence: OccurrenceEvidence = Field(
        ...,
        description="Session occurrence counts and threshold satisfaction evidence"
    )
    sequence_evidence: SequenceEvidence = Field(
        ...,
        description="Sequence alignment, similarity, and structural variation evidence"
    )
    consistency_evidence: ConsistencyEvidence = Field(
        ...,
        description="Session replay consistency metrics"
    )
    confidence_explanation: str = Field(
        ...,
        description="Natural-language summary of the confidence score rationale"
    )
    confidence_factors: ConfidenceFactorBreakdown = Field(
        ...,
        description="Structured strengths and limiting factors for confidence"
    )
    ranking_explanation: str = Field(
        ...,
        description="Natural-language summary of the ranking score and rank rationale"
    )
    ranking_factors: RankingFactorBreakdown = Field(
        ...,
        description="Structured drivers and limiting factors for ranking"
    )
    quality_explanation: str = Field(
        ...,
        description="Detailed explanation of the assigned quality tier"
    )
    suppression_explanation: Optional[str] = Field(
        default=None,
        description="Explanation of why this candidate was suppressed or deduplicated, if applicable"
    )
    suppression_evidence: Optional[SuppressionEvidence] = Field(
        default=None,
        description="Structured suppression metrics and representative links"
    )
    representative_explanation: Optional[str] = Field(
        default=None,
        description="Why this pattern was chosen as representative, or why it was subsumed by another"
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Explicit uncertainties, empirical scope boundaries, and heuristic disclaimers"
    )


def mask_session_id(session_id: str) -> str:
    """
    Sanitizes session identifiers to prevent exposing sensitive internal tokens or PII
    while preserving deterministic readability.
    """
    if not session_id:
        return "session_unknown"
    # If session looks like an email or sensitive string, mask local part
    if "@" in session_id:
        parts = session_id.split("@")
        return f"***@{parts[1]}"
    # If session contains a long token (hex/hash > 20 chars), truncate securely
    if len(session_id) > 20 and not session_id.startswith("session_"):
        return f"{session_id[:6]}...{session_id[-4:]}"
    return session_id


def synthesize_detection_reason(
    label: str,
    sequence: List[str],
    occurrences: int,
    avg_similarity: float,
    min_occurrences: int,
    similarity_threshold: float,
    exact_count: int,
    insertions: int,
    transpositions: int,
) -> str:
    """
    Synthesizes an evidence-grounded explanation of why this sequence qualified.
    """
    length = len(sequence)
    sim_pct = int(round(avg_similarity * 100))
    min_sim_pct = int(round(similarity_threshold * 100))

    if exact_count == occurrences:
        match_desc = "identical sequence execution (100% exact match across all sessions)"
    else:
        var_parts = []
        if insertions > 0:
            var_parts.append(f"{insertions} tolerated inserted actions")
        if transpositions > 0:
            var_parts.append(f"{transpositions} adjacent step order swaps")
        var_text = f" with {', '.join(var_parts)}" if var_parts else ""
        match_desc = (
            f"local alignment similarity averaging {sim_pct}% "
            f"({exact_count}/{occurrences} exact replays{var_text})"
        )

    return (
        f"Qualified as a repeated workflow because the {length}-step sequence was observed "
        f"in {occurrences} distinct user sessions (configured threshold: >= {min_occurrences}) "
        f"with {match_desc}. The observed similarity exceeds the {min_sim_pct}% alignment threshold."
    )


def synthesize_sequence_evidence(
    sequence: List[str],
    alignment_results: Optional[List[LocalAlignmentResult]],
    session_similarities: Optional[List[float]],
    avg_similarity: float,
    occurrences: int,
) -> SequenceEvidence:
    """
    Extracts structural sequence metrics and alignment variation evidence.
    """
    length = len(sequence)
    unique_count = len(set(sequence))
    diversity_ratio = round(unique_count / length, 4) if length > 0 else 0.0

    if alignment_results:
        exact_count = sum(1 for ar in alignment_results if ar.similarity >= 0.999)
        approx_count = len(alignment_results) - exact_count
        tot_ins = sum(ar.insertions for ar in alignment_results)
        tot_del = sum(ar.deletions for ar in alignment_results)
        tot_trans = sum(ar.transpositions for ar in alignment_results)
    elif session_similarities:
        exact_count = sum(1 for s in session_similarities if s >= 0.999)
        approx_count = len(session_similarities) - exact_count
        tot_ins = 0
        tot_del = 0
        tot_trans = 0
    else:
        exact_count = occurrences if avg_similarity >= 0.999 else 0
        approx_count = occurrences - exact_count
        tot_ins = 0
        tot_del = 0
        tot_trans = 0

    if exact_count == occurrences:
        var_summary = "Zero structural variations observed across all supporting sessions (100% exact sequence match)."
    else:
        parts = []
        if tot_ins > 0:
            parts.append(f"{tot_ins} inserted intermediate noise steps")
        if tot_trans > 0:
            parts.append(f"{tot_trans} adjacent step transpositions")
        if tot_del > 0:
            parts.append(f"{tot_del} omitted steps")
        if not parts:
            parts.append("minor character/verb alignment variances")
        var_summary = (
            f"Observed {', '.join(parts)} across {approx_count} approximate session replays."
        )

    return SequenceEvidence(
        canonical_sequence=sequence,
        sequence_length=length,
        unique_actions_count=unique_count,
        action_diversity_ratio=diversity_ratio,
        average_alignment_score=round(avg_similarity, 4),
        exact_match_sessions_count=exact_count,
        approximate_match_sessions_count=approx_count,
        total_insertions_observed=tot_ins,
        total_deletions_observed=tot_del,
        total_transpositions_observed=tot_trans,
        variations_summary=var_summary,
    )


def synthesize_confidence_factors(
    score: float,
    tier: str,
    occurrences: int,
    avg_similarity: float,
    sequence: List[str],
    exact_count: int,
    raw_signals: Optional[Dict[str, Any]] = None,
) -> ConfidenceFactorBreakdown:
    """
    Extracts structured positive and limiting factors for confidence scoring.
    """
    length = len(sequence)
    unique_count = len(set(sequence))
    strengths: List[str] = []
    limits: List[str] = []

    # Repetition volume
    if occurrences >= 5:
        strengths.append(f"Saturated multi-session support ({occurrences} distinct sessions)")
    elif occurrences >= 3:
        strengths.append(f"Solid session adoption ({occurrences} distinct sessions)")
    elif occurrences == 2:
        limits.append(f"Minimal repetition volume (2 sessions, the minimum required threshold)")

    # Alignment quality
    if avg_similarity >= 0.999:
        strengths.append("Perfect structural alignment (100% similarity across sessions)")
    elif avg_similarity >= 0.90:
        strengths.append(f"High sequence alignment ({int(avg_similarity * 100)}% average similarity)")
    else:
        limits.append(f"Moderate alignment variation ({int(avg_similarity * 100)}% similarity)")

    # Action diversity
    if unique_count == length and length >= 3:
        strengths.append(f"High task diversity ({unique_count}/{length} distinct action verbs)")
    elif unique_count <= 1 and length >= 2:
        limits.append(f"Monotonous action penalty (all {length} steps are identical action)")
    elif (unique_count / length) < 0.60:
        limits.append(f"Lower action diversity ({unique_count}/{length} distinct action verbs)")

    # Sequence length
    if length >= 5:
        strengths.append(f"Substantial sequence length ({length} steps indicate strong procedural intent)")
    elif length == 3:
        limits.append("Short workflow sequence (3 steps, minimal complexity)")

    # Consistency
    if exact_count == occurrences and occurrences > 0:
        strengths.append("Flawless session consistency (100% exact replays)")
    elif exact_count < occurrences:
        limits.append(f"Session variation detected ({occurrences - exact_count} sessions required local alignment tolerances)")

    return ConfidenceFactorBreakdown(
        score=score,
        tier=tier,
        primary_strengths=strengths,
        limiting_factors=limits,
    )


def synthesize_ranking_factors(
    score: float,
    rank: Optional[int],
    tier: str,
    breakdown: Any,
    occurrences: int,
    sequence: List[str],
) -> RankingFactorBreakdown:
    """
    Extracts structured drivers and limiting factors for ranking utility.
    """
    drivers: List[str] = []
    limits: List[str] = []

    if breakdown:
        s_conf = getattr(breakdown, "pattern_confidence", 0.0)
        s_fid = getattr(breakdown, "execution_fidelity", 0.0)
        s_vol = getattr(breakdown, "operational_volume", 0.0)
        s_imp = getattr(breakdown, "automation_impact", 0.0)
        s_rich = getattr(breakdown, "task_richness", 0.0)

        # High signals
        if s_conf >= 0.85:
            drivers.append(f"High pattern confidence ({int(s_conf * 100)}%)")
        if s_fid >= 0.85:
            drivers.append(f"High execution fidelity ({int(s_fid * 100)}%)")
        if s_vol >= 0.70:
            drivers.append(f"Broad operational adoption ({occurrences} sessions)")
        if s_imp >= 0.80:
            drivers.append(f"High automation impact ({len(sequence)} steps provide substantial time savings)")
        if s_rich >= 0.90:
            drivers.append("High action entropy and task richness")

        # Limiting signals
        if s_vol <= 0.40:
            limits.append(f"Limited operational volume ({occurrences} sessions)")
        if s_imp <= 0.40:
            limits.append(f"Modest step length savings potential ({len(sequence)} steps)")
        if s_fid < 0.75:
            limits.append(f"Alignment variance across sessions ({int(s_fid * 100)}% fidelity)")
        if s_rich < 0.60:
            limits.append("Reduced action entropy due to repeated step types")

    if not drivers:
        drivers.append("Satisfies baseline discovery criteria")

    return RankingFactorBreakdown(
        score=score,
        rank=rank,
        tier=tier,
        primary_drivers=drivers,
        limiting_factors=limits,
    )


def synthesize_quality_explanation(tier: str, score: float, rank: Optional[int]) -> str:
    """
    Provides natural-language explanation of quality tier assignment.
    """
    score_pct = int(round(score * 100))
    rank_str = f"Ranked #{rank} with " if rank else ""

    if tier == QualityTier.EXCEPTIONAL.value:
        return (
            f"{rank_str}Exceptional quality ({score_pct}/100): High automation value, "
            f"demonstrating strong multi-session adoption, high execution fidelity, and substantial procedural impact."
        )
    elif tier == QualityTier.STRONG.value:
        return (
            f"{rank_str}Strong quality ({score_pct}/100): Solid automation candidate with "
            f"consistent execution across sessions and meaningful operational impact."
        )
    elif tier == QualityTier.MODERATE.value:
        return (
            f"{rank_str}Moderate quality ({score_pct}/100): Viable workflow pattern, but "
            f"limited by shorter sequence length, fewer supporting sessions, or minor variations."
        )
    else:
        return (
            f"{rank_str}Low quality ({score_pct}/100): Marginal automation priority due to "
            f"insufficient session adoption, low action diversity, or high alignment variation."
        )


def synthesize_suppression_explanation(
    reason: Optional[str],
    sequence: List[str],
    occurrences: int,
    ranking_score: float,
    min_occurrences: int,
    min_ranking_score: Optional[float],
    rep_label: Optional[str],
    rep_workflow: Optional[Dict[str, Any]],
) -> Tuple[Optional[str], Optional[SuppressionEvidence]]:
    """
    Generates structured and human-readable explanations for candidate suppression.
    """
    if not reason:
        return None, None

    length = len(sequence)
    unique_count = len(set(sequence))
    diversity_ratio = unique_count / length if length > 0 else 0.0

    criterion = None
    measured = None
    rep_rationale = None
    text_expl = None

    if reason == SuppressionReason.MONOTONOUS_REPETITION.value:
        criterion = "Unique actions > 1 in sequence"
        measured = f"{unique_count} unique action ({sequence[0]} repeated {length} times)"
        text_expl = (
            f"Suppressed as monotonous UI loop noise: the single action '{sequence[0]}' "
            f"was repeated {length} consecutive times. This represents repetitive UI polling or clicks "
            f"rather than an automation-ready business workflow."
        )

    elif reason == SuppressionReason.LOW_ACTION_DIVERSITY.value:
        criterion = "Action diversity ratio >= 0.35"
        measured = f"Diversity ratio {diversity_ratio:.2f} ({unique_count}/{length} distinct actions)"
        text_expl = (
            f"Suppressed due to low action diversity ({unique_count} distinct actions across {length} steps). "
            f"Sequences dominated by repetitive verbs fail the minimum semantic diversity threshold."
        )

    elif reason == SuppressionReason.LOW_QUALITY_SCORE.value:
        threshold_val = min_ranking_score if min_ranking_score is not None else 0.50
        criterion = f"Ranking utility score >= {threshold_val:.2f}"
        measured = f"Utility score {ranking_score:.2f}"
        text_expl = (
            f"Suppressed because utility score ({ranking_score:.2f}) is below the operational threshold "
            f"({threshold_val:.2f}). Sequence exhibits insufficient session adoption or consistency."
        )

    elif reason == SuppressionReason.INSUFFICIENT_DISTINCT_SESSIONS.value:
        criterion = f"Distinct supporting sessions >= {min_occurrences}"
        measured = f"{occurrences} distinct sessions"
        text_expl = (
            f"Suppressed due to insufficient session support: observed in {occurrences} distinct sessions "
            f"(configured threshold requires >= {min_occurrences})."
        )

    elif reason == SuppressionReason.EXACT_DUPLICATE.value:
        criterion = "Unique action sequence tuple"
        measured = "100% identical sequence to existing candidate"
        rep_rationale = "Canonical representative retains all combined session occurrences and highest confidence."
        text_expl = (
            f"Suppressed as an exact duplicate of canonical pattern '{rep_label}'. "
            f"All {occurrences} supporting sessions are represented by the canonical workflow."
        )

    elif reason == SuppressionReason.OVERLAPPING_SHADOW.value:
        criterion = "Session overlap < 70% with super-sequence OR >= 2 independent sessions"
        super_len = len(rep_workflow["sequence"]) if rep_workflow and "sequence" in rep_workflow else "longer"
        measured = f"{length} steps (subsequence of {super_len}-step workflow)"
        rep_rationale = (
            f"Canonical pattern '{rep_label}' provides longer, complete end-to-end automation "
            f"({super_len} steps vs {length} steps) across the same user sessions."
        )
        text_expl = (
            f"Suppressed as an overlapping shadow of canonical workflow '{rep_label}'. "
            f"This {length}-step sequence is a strict sub-slice of the longer workflow and lacks "
            f"sufficient independent session executions outside it."
        )

    elif reason == SuppressionReason.SIMILAR_VARIANT_OVERLAP.value:
        criterion = "Sequence similarity < 80% or session overlap < 50%"
        measured = "High sequence alignment (>= 80%) and majority session overlap"
        rep_conf = rep_workflow.get("confidence", 0.0) if rep_workflow else 0.0
        rep_rationale = (
            f"Canonical pattern '{rep_label}' exhibits higher confidence ({rep_conf:.2f} vs {ranking_score:.2f}) "
            f"and cleaner session replay alignment."
        )
        text_expl = (
            f"Suppressed as a near-duplicate variant of canonical workflow '{rep_label}'. "
            f"The canonical representative was selected due to higher confidence and replay fidelity."
        )

    else:
        criterion = "Discovery filter"
        measured = reason
        text_expl = f"Candidate was filtered out: {reason}."

    evidence = SuppressionEvidence(
        is_suppressed=True,
        suppression_reason=reason,
        threshold_criterion=criterion,
        measured_value=measured,
        representative_pattern_id=rep_label,
        representative_rationale=rep_rationale,
    )
    return text_expl, evidence


def synthesize_representative_explanation(
    is_duplicate: bool,
    rep_label: Optional[str],
    sequence: List[str],
    occurrences: int,
    confidence: float,
    independent_sessions_count: Optional[int] = None,
) -> Optional[str]:
    """
    Explains canonical representative selection or independent sub-sequence retention.
    """
    length = len(sequence)
    if is_duplicate and rep_label:
        return (
            f"Subsumed by canonical representative '{rep_label}', which represents the primary "
            f"workflow sequence across these sessions."
        )

    if independent_sessions_count is not None and independent_sessions_count >= 2:
        return (
            f"Preserved as an independent workflow: although a sub-slice of a longer workflow, "
            f"it occurred in {independent_sessions_count} independent sessions without executing the super-sequence."
        )

    return (
        f"Selected as the canonical representative workflow for this pattern because it achieved "
        f"the highest replay confidence ({confidence:.2f}) across {occurrences} sessions."
    )


def synthesize_limitations(
    occurrences: int,
    avg_similarity: float,
    approx_count: int,
) -> List[str]:
    """
    Generates explicit limitations and empirical boundary disclaimers.
    """
    limits = [
        "Heuristic Ranking: The utility score (0.0 - 1.0) is an operational prioritization heuristic based on observed volume and structure, not a calibrated statistical probability.",
        f"Empirical Scope: Discovery is grounded strictly in permitted UI event logs across {occurrences} distinct sessions; external unmonitored human actions cannot be inferred.",
    ]
    if approx_count > 0:
        limits.append(
            f"Local Alignment Tolerances: {approx_count} supporting sessions exhibited structural variations (insertions or step reorderings); human operator review should confirm whether omitted or extra steps are non-essential."
        )
    return limits


def build_workflow_explanation(
    sequence: List[str],
    occurrences: int,
    avg_similarity: float,
    session_ids: List[str],
    confidence: float,
    confidence_tier: str,
    confidence_breakdown: Any,
    confidence_explanation: str,
    rank: Optional[int],
    ranking_score: float,
    quality_tier: str,
    ranking_breakdown: Any,
    ranking_explanation: str,
    alignment_results: Optional[List[LocalAlignmentResult]] = None,
    session_similarities: Optional[List[float]] = None,
    is_duplicate: bool = False,
    suppression_reason: Optional[str] = None,
    representative_pattern_id: Optional[str] = None,
    representative_workflow: Optional[Dict[str, Any]] = None,
    independent_sessions_count: Optional[int] = None,
    min_length: int = 3,
    min_occurrences: int = 2,
    similarity_threshold: float = 0.80,
    min_ranking_score: Optional[float] = None,
) -> WorkflowExplanation:
    """
    Assembles the complete WorkflowExplanation object.
    Fully deterministic, evidence-grounded, and testable.
    """
    safe_sessions = [mask_session_id(s) for s in session_ids]
    length = len(sequence)

    # 1. Sequence Evidence
    seq_ev = synthesize_sequence_evidence(
        sequence=sequence,
        alignment_results=alignment_results,
        session_similarities=session_similarities,
        avg_similarity=avg_similarity,
        occurrences=occurrences,
    )

    # 2. Occurrence Evidence
    occ_ev = OccurrenceEvidence(
        distinct_sessions_observed=occurrences,
        min_sessions_required=min_occurrences,
        threshold_satisfied=occurrences >= min_occurrences,
        repetition_description=(
            f"Observed across {occurrences} distinct user sessions (satisfies >= {min_occurrences} requirement)."
        ),
    )

    # 3. Consistency Evidence
    exact_pct = round((seq_ev.exact_match_sessions_count / occurrences) * 100.0, 1) if occurrences > 0 else 0.0
    is_fully_cons = (seq_ev.exact_match_sessions_count == occurrences)
    cons_desc = (
        f"100.0% of supporting sessions executed the sequence in identical order."
        if is_fully_cons
        else f"{exact_pct}% of supporting sessions were exact replays; {round(100.0 - exact_pct, 1)}% exhibited tolerated local alignment variations."
    )
    cons_ev = ConsistencyEvidence(
        exact_replay_percentage=exact_pct,
        is_fully_consistent=is_fully_cons,
        consistency_description=cons_desc,
    )

    # 4. Detection Reason
    det_reason = synthesize_detection_reason(
        label=representative_pattern_id or "Workflow",
        sequence=sequence,
        occurrences=occurrences,
        avg_similarity=avg_similarity,
        min_occurrences=min_occurrences,
        similarity_threshold=similarity_threshold,
        exact_count=seq_ev.exact_match_sessions_count,
        insertions=seq_ev.total_insertions_observed,
        transpositions=seq_ev.total_transpositions_observed,
    )

    # 5. Confidence Factors
    conf_factors = synthesize_confidence_factors(
        score=confidence,
        tier=confidence_tier,
        occurrences=occurrences,
        avg_similarity=avg_similarity,
        sequence=sequence,
        exact_count=seq_ev.exact_match_sessions_count,
    )

    # 6. Ranking Factors
    rank_factors = synthesize_ranking_factors(
        score=ranking_score,
        rank=rank,
        tier=quality_tier,
        breakdown=ranking_breakdown,
        occurrences=occurrences,
        sequence=sequence,
    )

    # 7. Quality Explanation
    qual_expl = synthesize_quality_explanation(
        tier=quality_tier,
        score=ranking_score,
        rank=rank,
    )

    # 8. Suppression & Representative
    supp_expl, supp_ev = synthesize_suppression_explanation(
        reason=suppression_reason,
        sequence=sequence,
        occurrences=occurrences,
        ranking_score=ranking_score,
        min_occurrences=min_occurrences,
        min_ranking_score=min_ranking_score,
        rep_label=representative_pattern_id,
        rep_workflow=representative_workflow,
    )

    rep_expl = synthesize_representative_explanation(
        is_duplicate=is_duplicate,
        rep_label=representative_pattern_id,
        sequence=sequence,
        occurrences=occurrences,
        confidence=confidence,
        independent_sessions_count=independent_sessions_count,
    )

    # 9. Concise Summary
    if suppression_reason:
        summary = f"Candidate suppressed ({suppression_reason}): {supp_expl}"
    else:
        rank_str = f"Ranked #{rank} · " if rank else ""
        summary = (
            f"{rank_str}{length}-step workflow with {int(round(ranking_score * 100))}/100 {quality_tier} automation score "
            f"across {occurrences} sessions ({int(round(confidence * 100))}% confidence)."
        )

    # 10. Limitations
    limits = synthesize_limitations(
        occurrences=occurrences,
        avg_similarity=avg_similarity,
        approx_count=seq_ev.approximate_match_sessions_count,
    )

    return WorkflowExplanation(
        summary=summary,
        detection_reason=det_reason,
        supporting_sessions=safe_sessions,
        occurrence_evidence=occ_ev,
        sequence_evidence=seq_ev,
        consistency_evidence=cons_ev,
        confidence_explanation=confidence_explanation,
        confidence_factors=conf_factors,
        ranking_explanation=ranking_explanation,
        ranking_factors=rank_factors,
        quality_explanation=qual_expl,
        suppression_explanation=supp_expl,
        suppression_evidence=supp_ev,
        representative_explanation=rep_expl,
        limitations=limits,
    )
