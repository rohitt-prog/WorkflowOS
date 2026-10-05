"""
WorkFlowOS Phase 10: Strategy Scorer

Implements deterministic, bounded heuristic scoring for automation strategies.
Combines capability, reliability, Phase 9 learning state, priority, credentials,
and failure/safety penalties into a score in [0.0, 1.0].

CRITICAL: Strategy scores are deterministic heuristic suitability scores, NOT probabilities.
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from automation.planner.models import (
    AutomationStrategyType,
    StrategyScoreBreakdown,
    StrategyCandidate,
)
from backend.learning.models import WorkflowLearningState, RecommendationStatus

logger = logging.getLogger(__name__)

# Base priority scores reflecting the WorkFlowOS architectural hierarchy
PRIORITY_WEIGHTS: Dict[AutomationStrategyType, float] = {
    AutomationStrategyType.API: 0.25,
    AutomationStrategyType.INTEGRATION: 0.20,
    AutomationStrategyType.SEMANTIC_UI: 0.15,
    AutomationStrategyType.BROWSER: 0.10,
    AutomationStrategyType.MANUAL: 0.00,
}

# Cold-start reliability baselines when no historical telemetry is recorded yet
COLD_START_RELIABILITY: Dict[AutomationStrategyType, float] = {
    AutomationStrategyType.API: 0.20,
    AutomationStrategyType.INTEGRATION: 0.18,
    AutomationStrategyType.SEMANTIC_UI: 0.15,
    AutomationStrategyType.BROWSER: 0.12,
    AutomationStrategyType.MANUAL: 0.05,
}


class StrategyScorer:
    """
    Deterministic scoring engine evaluating automation strategies.
    Produces an explainable StrategyScoreBreakdown and StrategyCandidate.
    """

    def score_strategy(
        self,
        strategy: AutomationStrategyType,
        is_available: bool,
        rejection_reason: Optional[str],
        action: str,
        application: str,
        is_mutating: bool,
        requires_credentials: bool,
        credentials_available: bool,
        learning_state: Optional[WorkflowLearningState] = None,
        history: Optional[Dict[str, Any]] = None,
    ) -> StrategyCandidate:
        """
        Calculates the heuristic suitability score for a strategy candidate.
        """
        selection_reasons: List[str] = []
        hist = history or {}

        # 1. Capability Score (0.0 - 0.30)
        if not is_available:
            capability_score = 0.0
        elif strategy == AutomationStrategyType.MANUAL:
            capability_score = 0.10
            selection_reasons.append("Universal manual execution fallback")
        else:
            capability_score = 0.30
            selection_reasons.append(f"Native {strategy.value} capability for action '{action}' on '{application}'")

        # 2. Priority Score (0.0 - 0.25)
        priority_score = PRIORITY_WEIGHTS.get(strategy, 0.0)
        if priority_score > 0 and is_available:
            selection_reasons.append(f"Architectural priority weight (+{priority_score:.2f})")

        # 3. Reliability Score (0.0 - 0.25)
        # Extract execution telemetry for this strategy
        raw_successes = hist.get(f"{strategy.value.lower()}_successes")
        if raw_successes is None:
            raw_successes = hist.get("successes", 0)
        try:
            successes = int(raw_successes or 0)
        except (ValueError, TypeError):
            successes = 0

        raw_failures = hist.get(f"{strategy.value.lower()}_failures")
        if raw_failures is None:
            raw_failures = hist.get("failures", 0)
        try:
            failures = int(raw_failures or 0)
        except (ValueError, TypeError):
            failures = 0
        total_runs = successes + failures

        if total_runs > 0:
            success_rate = successes / total_runs
            reliability_score = round(success_rate * 0.25, 4)
            selection_reasons.append(
                f"Historical reliability: {successes}/{total_runs} successful runs ({success_rate*100:.1f}%)"
            )
        else:
            reliability_score = COLD_START_RELIABILITY.get(strategy, 0.10)
            if is_available and strategy != AutomationStrategyType.MANUAL:
                selection_reasons.append(f"Baseline reliability for new strategy (+{reliability_score:.2f})")

        # 4. Learning Score from Phase 9 (0.0 - 0.15)
        learning_score = 0.0
        if learning_state is not None:
            # Base contribution from bounded Phase 9 learning score [0.0, 1.0]
            base_learn = learning_state.learning_score * 0.10
            bonus = 0.0
            if learning_state.recommendation_status == RecommendationStatus.RECOMMENDED:
                bonus = 0.05
                selection_reasons.append("Workflow is in Phase 9 RECOMMENDED state (+0.05)")
            elif learning_state.recommendation_status == RecommendationStatus.DEPRIORITIZED:
                bonus = -0.05
            learning_score = round(max(0.0, min(0.15, base_learn + bonus)), 4)
            if base_learn > 0:
                selection_reasons.append(
                    f"Phase 9 learning score {learning_state.learning_score:.2f} contributes +{learning_score:.2f}"
                )
        else:
            learning_score = 0.05  # neutral baseline

        # 5. Credential Score (0.0 - 0.10)
        if not requires_credentials:
            credential_score = 0.10
            if is_available and strategy != AutomationStrategyType.MANUAL:
                selection_reasons.append("No external credentials required")
        elif credentials_available:
            credential_score = 0.10
            selection_reasons.append("Required credentials verified and available")
        else:
            credential_score = 0.0

        # 6. Failure Penalty (0.0 - 0.50)
        failure_penalty = 0.0
        if total_runs > 0:
            failure_rate = failures / total_runs
            failure_penalty = round(failure_rate * 0.40, 4)
            # Recent failure flag
            last_failed = hist.get(f"{strategy.value.lower()}_last_failed", hist.get("last_failed", False))
            if last_failed:
                failure_penalty = round(min(0.50, failure_penalty + 0.10), 4)
        elif learning_state and learning_state.last_failed_step == action:
            # Step recently failed in workflow learning state
            failure_penalty = 0.05

        # 7. Safety Penalty (0.0 - 0.50)
        safety_penalty = 0.0
        if requires_credentials and not credentials_available:
            safety_penalty += 0.25
        if is_mutating:
            if strategy in (AutomationStrategyType.BROWSER, AutomationStrategyType.SEMANTIC_UI):
                # Browser UI mutating actions carry slightly higher execution risk than API
                safety_penalty += 0.05
            elif strategy == AutomationStrategyType.MANUAL:
                # Manual intervention for mutating action has no safety deduction
                pass

        # Raw Score Sum
        raw_score = round(
            capability_score
            + priority_score
            + reliability_score
            + learning_score
            + credential_score
            - failure_penalty
            - safety_penalty,
            4
        )

        # Clamped Final Score
        if not is_available:
            final_score = 0.0
        else:
            final_score = round(max(0.0, min(1.0, raw_score)), 4)

        breakdown = StrategyScoreBreakdown(
            capability_score=capability_score,
            priority_score=priority_score,
            reliability_score=reliability_score,
            learning_score=learning_score,
            credential_score=credential_score,
            failure_penalty=failure_penalty,
            safety_penalty=safety_penalty,
            raw_score=raw_score,
            final_score=final_score,
        )

        # Build candidate rejection reason if unavailable or poor score
        cand_rej = rejection_reason
        if not cand_rej and not is_available:
            cand_rej = f"Strategy '{strategy.value}' is not capable for this action"
        elif not cand_rej and failure_penalty > 0.20:
            cand_rej = f"High failure rate ({failures}/{total_runs} failed) incurs substantial penalty"
        elif not cand_rej and requires_credentials and not credentials_available:
            cand_rej = "Required credentials are missing or disconnected"

        return StrategyCandidate(
            strategy=strategy,
            is_available=is_available,
            score=final_score,
            score_breakdown=breakdown,
            selection_reasons=selection_reasons if is_available else [],
            rejection_reason=cand_rej if not is_available or final_score < 0.20 else None,
            metadata={
                "action": action,
                "application": application,
                "is_mutating": is_mutating,
                "total_runs": total_runs,
                "successes": successes,
                "failures": failures,
            }
        )


# Global singleton scorer
strategy_scorer = StrategyScorer()
