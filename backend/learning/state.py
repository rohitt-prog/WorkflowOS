from typing import Dict, Any, Optional, Tuple
from backend.learning.models import RecommendationStatus, WorkflowLearningState


def compute_learning_score(
    approval_count: int,
    rejection_count: int,
    edit_count: int,
    successful_execution_count: int,
    failed_execution_count: int,
    intervention_count: int,
    recovery_count: int,
) -> float:
    """
    Computes a deterministic bounded learning score in [0.0, 1.0].
    
    Formula:
        Raw = 0.50 (neutral prior)
            + 0.10 * approval_count
            + 0.08 * edit_count
            + 0.15 * successful_execution_count
            + 0.05 * recovery_count
            - 0.20 * rejection_count
            - 0.15 * failed_execution_count
            - 0.05 * intervention_count
            
        Score = clamp(Raw, 0.0, 1.0)
    """
    raw_score = (
        0.50
        + (0.10 * approval_count)
        + (0.08 * edit_count)
        + (0.15 * successful_execution_count)
        + (0.05 * recovery_count)
        - (0.20 * rejection_count)
        - (0.15 * failed_execution_count)
        - (0.05 * intervention_count)
    )
    clamped = max(0.0, min(1.0, raw_score))
    return round(clamped, 4)


def determine_recommendation_status(
    learning_score: float,
    approval_count: int,
    rejection_count: int,
    edit_count: int,
    execution_count: int,
    successful_execution_count: int,
    failed_execution_count: int,
) -> RecommendationStatus:
    """
    Assigns a deterministic recommendation status based on accumulated evidence.
    
    Rules:
    - NEW: No human feedback or execution history yet recorded.
    - RECOMMENDED: High learning score (>= 0.70), at least 1 approval, at least 1 successful
      execution, and positive evidence outweighs negative evidence.
    - DEPRIORITIZED: Low learning score (< 0.40), or repeated rejections (>= 2) without
      compensating successes, or multiple execution failures (>= 2) with 0 successes.
    - LEARNING: Active evidence accumulating, but neither qualified as RECOMMENDED nor DEPRIORITIZED.
    """
    total_interactions = (
        approval_count + rejection_count + edit_count + execution_count
    )
    if total_interactions == 0:
        return RecommendationStatus.NEW

    positive_signals = approval_count + edit_count + successful_execution_count
    negative_signals = rejection_count + failed_execution_count

    # Recovery / strong recommendation condition
    if (
        learning_score >= 0.70
        and (approval_count + edit_count) >= 1
        and successful_execution_count >= 1
        and positive_signals > negative_signals
    ):
        return RecommendationStatus.RECOMMENDED

    # Deprioritization condition
    if (
        learning_score < 0.40
        or (rejection_count >= 2 and positive_signals <= negative_signals)
        or (failed_execution_count >= 2 and successful_execution_count == 0)
    ):
        return RecommendationStatus.DEPRIORITIZED

    return RecommendationStatus.LEARNING


def generate_learning_explanation(
    status: RecommendationStatus,
    score: float,
    approval_count: int,
    rejection_count: int,
    edit_count: int,
    execution_count: int,
    successful_execution_count: int,
    failed_execution_count: int,
    intervention_count: int,
    recovery_count: int,
    last_failed_step: Optional[str] = None,
    last_failure_reason: Optional[str] = None,
    last_rejection_reason: Optional[str] = None,
) -> str:
    """
    Generates a deterministic human-readable explanation of why the workflow has
    its current learning score and recommendation status.
    """
    if status == RecommendationStatus.NEW:
        return "New workflow candidate with no prior feedback or execution history."

    if status == RecommendationStatus.RECOMMENDED:
        parts = ["Recommended because"]
        evidence = []
        tot_approvals = approval_count + edit_count
        if tot_approvals > 0:
            evidence.append(f"it was approved {tot_approvals} times" + (f" ({edit_count} with edits)" if edit_count else ""))
        if successful_execution_count > 0:
            evidence.append(f"successfully executed {successful_execution_count} times")
        if recovery_count > 0:
            evidence.append(f"recovered from {recovery_count} interruptions")
        parts.append(" and ".join(evidence))
        parts.append(f"with a high reliability learning score of {score:.2f}.")
        return " ".join(parts)

    if status == RecommendationStatus.DEPRIORITIZED:
        if failed_execution_count >= 2 or (failed_execution_count > 0 and successful_execution_count == 0):
            step_detail = f" at step '{last_failed_step}'" if last_failed_step else ""
            reason_detail = f" ({last_failure_reason})" if last_failure_reason else ""
            interv_detail = " and required operator intervention" if intervention_count > 0 else ""
            return (
                f"Deprioritized because workflow execution failed {failed_execution_count} times"
                f"{step_detail}{reason_detail}{interv_detail} (learning score: {score:.2f})."
            )
        if rejection_count >= 2:
            reason_str = f" ('{last_rejection_reason}')" if last_rejection_reason else ""
            return (
                f"Deprioritized because this workflow was rejected {rejection_count} times by operator"
                f"{reason_str} (learning score: {score:.2f})."
            )
        return (
            f"Deprioritized due to accumulated negative feedback and execution penalties "
            f"(learning score: {score:.2f})."
        )

    # LEARNING
    evidence = []
    tot_approvals = approval_count + edit_count
    if tot_approvals > 0:
        evidence.append(f"{tot_approvals} approval{'s' if tot_approvals != 1 else ''}")
    if rejection_count > 0:
        evidence.append(f"{rejection_count} rejection{'s' if rejection_count != 1 else ''}")
    if execution_count > 0:
        evidence.append(f"{successful_execution_count}/{execution_count} successful execution{'s' if execution_count != 1 else ''}")
    if intervention_count > 0:
        evidence.append(f"{intervention_count} intervention{'s' if intervention_count != 1 else ''}")

    joined_evidence = ", ".join(evidence) if evidence else "limited interactions"
    return f"Still learning from operational telemetry: {joined_evidence} (learning score: {score:.2f})."


def recalculate_learning_state(
    current_state: WorkflowLearningState,
    last_rejection_reason: Optional[str] = None,
) -> WorkflowLearningState:
    """
    Recalculates the learning_score, recommendation_status, and learning_explanation
    from the current state's counters.
    """
    score = compute_learning_score(
        approval_count=current_state.approval_count,
        rejection_count=current_state.rejection_count,
        edit_count=current_state.edit_count,
        successful_execution_count=current_state.successful_execution_count,
        failed_execution_count=current_state.failed_execution_count,
        intervention_count=current_state.intervention_count,
        recovery_count=current_state.recovery_count,
    )
    status = determine_recommendation_status(
        learning_score=score,
        approval_count=current_state.approval_count,
        rejection_count=current_state.rejection_count,
        edit_count=current_state.edit_count,
        execution_count=current_state.execution_count,
        successful_execution_count=current_state.successful_execution_count,
        failed_execution_count=current_state.failed_execution_count,
    )
    explanation = generate_learning_explanation(
        status=status,
        score=score,
        approval_count=current_state.approval_count,
        rejection_count=current_state.rejection_count,
        edit_count=current_state.edit_count,
        execution_count=current_state.execution_count,
        successful_execution_count=current_state.successful_execution_count,
        failed_execution_count=current_state.failed_execution_count,
        intervention_count=current_state.intervention_count,
        recovery_count=current_state.recovery_count,
        last_failed_step=current_state.last_failed_step,
        last_failure_reason=current_state.last_failure_reason,
        last_rejection_reason=last_rejection_reason,
    )

    from datetime import datetime, timezone
    return current_state.model_copy(update={
        "learning_score": score,
        "recommendation_status": status,
        "learning_explanation": explanation,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
