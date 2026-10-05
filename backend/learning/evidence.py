"""
WorkFlowOS Phase 11: Strategy Outcome Evidence & Closed-Loop Summary

Tracks historical execution evidence for workflow + step + strategy combinations.
Enables closed-loop learning, recency weighting, success reinforcement,
failure-aware adaptation, and fallback learning.

Strict Invariants:
- Deterministic heuristic aggregation (NO ML, NO LLMs, NO external APIs).
- Never persists or leaks credentials, tokens, cookies, or secrets.
- Bounded recency windows (last 10 outcomes) to avoid runaway reinforcement.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from backend.learning.outcome import StepOutcome, ExecutionOutcomeStatus, FailureCategory

RECENT_WINDOW_SIZE = 10


def _current_iso_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class StrategyOutcomeEvidence(BaseModel):
    """
    Empirical reliability record for a specific workflow + step + strategy triplet.
    """
    workflow_id: str = Field(..., description="Canonical workflow ID")
    step_action: str = Field(..., description="Action verb type (e.g. 'update_customer')")
    strategy: str = Field(..., description="Strategy evaluated: API, INTEGRATION, BROWSER, MANUAL")
    attempts: int = Field(default=0, ge=0, description="Total recorded execution attempts")
    successes: int = Field(default=0, ge=0, description="Total successful step executions")
    failures: int = Field(default=0, ge=0, description="Total failed step executions")
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Empirical success ratio in [0.0, 1.0]")
    recent_outcomes: List[str] = Field(
        default_factory=list,
        description=f"Bounded window of the most recent {RECENT_WINDOW_SIZE} outcome states"
    )
    recent_successes: int = Field(default=0, ge=0, description="Count of successes in recent window")
    recent_failures: int = Field(default=0, ge=0, description="Count of failures in recent window")
    fallback_count: int = Field(default=0, ge=0, description="Times this strategy executed as fallback")
    last_outcome: Optional[str] = Field(default=None, description="Most recent outcome: SUCCESS, FAILED, etc.")
    last_failure_category: Optional[str] = Field(default=None, description="Failure category of most recent failure")
    last_error_message: Optional[str] = Field(default=None, description="Sanitized error message of last failure")
    average_duration: Optional[float] = Field(default=None, ge=0.0, description="Mean step execution duration in seconds")
    updated_at: str = Field(default_factory=_current_iso_timestamp, description="ISO timestamp of last evidence update")


class ClosedLoopSummary(BaseModel):
    """
    Executive closed-loop intelligence summary for a workflow.
    """
    workflow_id: str
    workflow_name: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    partial_executions: int = 0
    cancelled_executions: int = 0
    paused_executions: int = 0
    strategy_evidence: List[StrategyOutcomeEvidence] = Field(default_factory=list)
    adaptations: List[str] = Field(default_factory=list)
    explanation: str = "New workflow with baseline strategy evidence."


def update_strategy_evidence(
    current: Optional[StrategyOutcomeEvidence],
    step_outcome: StepOutcome,
    workflow_id: str,
) -> StrategyOutcomeEvidence:
    """
    Updates or initializes a StrategyOutcomeEvidence record from a StepOutcome.
    Handles recency bounding, fallback tracking, and duration averaging.
    """
    now_iso = _current_iso_timestamp()
    strat = step_outcome.strategy.upper()
    action = step_outcome.action.lower()

    if current is None:
        current = StrategyOutcomeEvidence(
            workflow_id=workflow_id,
            step_action=action,
            strategy=strat,
            attempts=0,
            successes=0,
            failures=0,
            success_rate=0.0,
            recent_outcomes=[],
            recent_successes=0,
            recent_failures=0,
            fallback_count=0,
            updated_at=now_iso,
        )

    # Status check
    status = step_outcome.status
    is_success = (status == ExecutionOutcomeStatus.SUCCESS)
    is_failure = (status == ExecutionOutcomeStatus.FAILED)
    # CANCELLED, PAUSED, and NOT_EXECUTED are non-execution / user interruption states, NOT technical failures
    is_not_run = (status in (
        ExecutionOutcomeStatus.CANCELLED,
        ExecutionOutcomeStatus.PAUSED,
        ExecutionOutcomeStatus.NOT_EXECUTED,
    ))

    new_attempts = current.attempts + (0 if is_not_run else 1)
    new_successes = current.successes + (1 if is_success else 0)
    new_failures = current.failures + (1 if is_failure else 0)
    new_fallback_count = current.fallback_count + (1 if (step_outcome.is_fallback and not is_not_run) else 0)

    # Recency window: only actual executions (SUCCESS or FAILED) enter recency outcomes
    new_recent = list(current.recent_outcomes)
    if not is_not_run:
        new_recent.append(status.value)
        if len(new_recent) > RECENT_WINDOW_SIZE:
            new_recent = new_recent[-RECENT_WINDOW_SIZE:]

    rec_succ = sum(1 for s in new_recent if s == ExecutionOutcomeStatus.SUCCESS.value)
    rec_fail = sum(1 for s in new_recent if s == ExecutionOutcomeStatus.FAILED.value)

    # Success rate (clamped in [0.0, 1.0])
    effective_runs = new_successes + new_failures
    new_success_rate = round(new_successes / effective_runs, 4) if effective_runs > 0 else 0.0

    # Failure category and error message
    last_fail_cat = current.last_failure_category
    last_err_msg = current.last_error_message
    if is_failure:
        last_fail_cat = step_outcome.failure_category.value if step_outcome.failure_category else FailureCategory.UNKNOWN.value
        last_err_msg = step_outcome.error_message

    # Duration average
    avg_dur = current.average_duration
    if step_outcome.duration_seconds is not None and step_outcome.duration_seconds >= 0:
        if avg_dur is None:
            avg_dur = round(step_outcome.duration_seconds, 3)
        else:
            avg_dur = round((avg_dur * current.attempts + step_outcome.duration_seconds) / max(1, new_attempts), 3)

    return current.model_copy(update={
        "attempts": new_attempts,
        "successes": new_successes,
        "failures": new_failures,
        "success_rate": new_success_rate,
        "recent_outcomes": new_recent,
        "recent_successes": rec_succ,
        "recent_failures": rec_fail,
        "fallback_count": new_fallback_count,
        "last_outcome": status.value if not is_not_run else (current.last_outcome or status.value),
        "last_failure_category": last_fail_cat,
        "last_error_message": last_err_msg,
        "average_duration": avg_dur,
        "updated_at": now_iso,
    })


def synthesize_closed_loop_summary(
    workflow_id: str,
    workflow_name: str,
    evidence_list: List[StrategyOutcomeEvidence],
    total_execs: int,
    succ_execs: int,
    fail_execs: int,
    part_execs: int,
    canc_execs: int,
    paus_execs: int,
) -> ClosedLoopSummary:
    """
    Synthesizes a transparent, deterministic ClosedLoopSummary with actionable adaptation insights.
    """
    adaptations: List[str] = []

    # Analyze evidence per step
    steps_map: Dict[str, Dict[str, StrategyOutcomeEvidence]] = {}
    for ev in evidence_list:
        steps_map.setdefault(ev.step_action, {})[ev.strategy] = ev

    for action, strats in steps_map.items():
        # Check if multiple strategies have telemetry
        if len(strats) >= 2:
            # Check if one strategy has failures and another has higher reliability
            failing = [s for s, ev in strats.items() if ev.recent_failures > 0 or (ev.attempts >= 3 and ev.success_rate < 0.60)]
            reliable = [s for s, ev in strats.items() if ev.attempts >= 2 and ev.success_rate >= 0.80 and ev.recent_failures == 0]
            if failing and reliable:
                fail_strat = failing[0]
                rel_strat = reliable[0]
                fail_ev = strats[fail_strat]
                rel_ev = strats[rel_strat]
                adaptations.append(
                    f"{rel_strat} strategy is currently preferred for '{action}' due to stronger reliability "
                    f"({rel_ev.success_rate*100:.0f}% over {rel_ev.attempts} runs) compared to {fail_strat} "
                    f"({fail_ev.recent_failures} recent failure(s), {fail_ev.success_rate*100:.0f}% success)."
                )

        # Single strategy insights
        for strat, ev in strats.items():
            if ev.recent_failures >= 2:
                adaptations.append(
                    f"Caution on '{action}' ({strat}): {ev.recent_failures} recent failure(s) detected "
                    f"(category: {ev.last_failure_category or 'UNKNOWN'}). Fallback is recommended."
                )
            elif ev.attempts >= 5 and ev.success_rate >= 0.90:
                adaptations.append(
                    f"Reinforced confidence on '{action}' ({strat}): {ev.successes}/{ev.attempts} successful executions ({ev.success_rate*100:.0f}%)."
                )

    if not adaptations:
        if total_execs == 0:
            explanation = "New workflow with baseline strategy evidence. No execution outcomes recorded yet."
        else:
            explanation = (
                f"Recorded {total_execs} execution(s) ({succ_execs} successful, {fail_execs} failed). "
                "All automated steps operate within nominal historical reliability bounds."
            )
    else:
        explanation = (
            f"Closed-loop telemetry across {total_execs} execution(s) has adapted planning for "
            f"{len(adaptations)} step condition(s). Evidence is actively fed into the Automation Planner."
        )

    return ClosedLoopSummary(
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        total_executions=total_execs,
        successful_executions=succ_execs,
        failed_executions=fail_execs,
        partial_executions=part_execs,
        cancelled_executions=canc_execs,
        paused_executions=paus_execs,
        strategy_evidence=evidence_list,
        adaptations=adaptations,
        explanation=explanation,
    )
