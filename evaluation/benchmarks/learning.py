"""
WorkFlowOS Phase 15: Adaptive Learning Benchmark

Evaluates Phase 9 adaptive learning formulas, state transitions, and
evidence accumulation without modifying production algorithms:
- Formula verification:
  L = clamp(0.50 + 0.10*A + 0.08*E_edit + 0.15*X_succ + 0.05*C_rec - 0.20*R - 0.15*X_fail - 0.05*I, 0, 1)
- State transitions (NEW, LEARNING, RECOMMENDED, DEPRIORITIZED)
- Clamping invariants (bounded strictly in [0.0, 1.0])
- Deprioritization and recovery trajectories
"""

from typing import Dict, List, Any

from backend.learning.state import (
    compute_learning_score,
    determine_recommendation_status,
    generate_learning_explanation,
)
from backend.learning.models import RecommendationStatus


def run_learning_benchmark() -> Dict[str, Any]:
    """
    Executes deterministic evaluation of the Phase 9 learning engine.
    """
    test_cases = [
        {
            "name": "Neutral Prior",
            "params": {
                "approval_count": 0,
                "rejection_count": 0,
                "edit_count": 0,
                "successful_execution_count": 0,
                "failed_execution_count": 0,
                "intervention_count": 0,
                "recovery_count": 0,
            },
            "expected_score": 0.50,
            "expected_status": RecommendationStatus.NEW,
        },
        {
            "name": "Approvals Increment",
            "params": {
                "approval_count": 2,
                "rejection_count": 0,
                "edit_count": 0,
                "successful_execution_count": 0,
                "failed_execution_count": 0,
                "intervention_count": 0,
                "recovery_count": 0,
            },
            "expected_score": 0.70,
            "expected_status": RecommendationStatus.LEARNING,
        },
        {
            "name": "Edit Approvals Increment",
            "params": {
                "approval_count": 1,
                "rejection_count": 0,
                "edit_count": 2,
                "successful_execution_count": 0,
                "failed_execution_count": 0,
                "intervention_count": 0,
                "recovery_count": 0,
            },
            "expected_score": 0.76,
            "expected_status": RecommendationStatus.LEARNING,
        },
        {
            "name": "Successful Executions to Recommended",
            "params": {
                "approval_count": 1,
                "rejection_count": 0,
                "edit_count": 0,
                "successful_execution_count": 2,
                "failed_execution_count": 0,
                "intervention_count": 0,
                "recovery_count": 0,
            },
            "expected_score": 0.90,
            "expected_status": RecommendationStatus.RECOMMENDED,
        },
        {
            "name": "Rejection Deprioritization",
            "params": {
                "approval_count": 0,
                "rejection_count": 2,
                "edit_count": 0,
                "successful_execution_count": 0,
                "failed_execution_count": 0,
                "intervention_count": 0,
                "recovery_count": 0,
            },
            "expected_score": 0.10,
            "expected_status": RecommendationStatus.DEPRIORITIZED,
        },
        {
            "name": "Execution Failure Deprioritization",
            "params": {
                "approval_count": 0,
                "rejection_count": 0,
                "edit_count": 0,
                "successful_execution_count": 0,
                "failed_execution_count": 2,
                "intervention_count": 0,
                "recovery_count": 0,
            },
            "expected_score": 0.20,
            "expected_status": RecommendationStatus.DEPRIORITIZED,
        },
        {
            "name": "Lower Bound Clamp (0.0)",
            "params": {
                "approval_count": 0,
                "rejection_count": 5,
                "edit_count": 0,
                "successful_execution_count": 0,
                "failed_execution_count": 3,
                "intervention_count": 2,
                "recovery_count": 0,
            },
            "expected_score": 0.0,
            "expected_status": RecommendationStatus.DEPRIORITIZED,
        },
        {
            "name": "Upper Bound Clamp (1.0)",
            "params": {
                "approval_count": 5,
                "rejection_count": 0,
                "edit_count": 2,
                "successful_execution_count": 5,
                "failed_execution_count": 0,
                "intervention_count": 0,
                "recovery_count": 2,
            },
            "expected_score": 1.0,
            "expected_status": RecommendationStatus.RECOMMENDED,
        },
        {
            "name": "Recovery Path from Deprioritized",
            "params": {
                "approval_count": 3,
                "rejection_count": 2,
                "edit_count": 0,
                "successful_execution_count": 3,
                "failed_execution_count": 0,
                "intervention_count": 0,
                "recovery_count": 1,
            },
            "expected_score": 0.90,
            "expected_status": RecommendationStatus.RECOMMENDED,
        },
    ]

    total_tests = len(test_cases)
    score_passed = 0
    status_passed = 0
    explanations_generated = 0
    details: List[Dict[str, Any]] = []

    for tc in test_cases:
        p = tc["params"]
        score = compute_learning_score(
            approval_count=p["approval_count"],
            rejection_count=p["rejection_count"],
            edit_count=p["edit_count"],
            successful_execution_count=p["successful_execution_count"],
            failed_execution_count=p["failed_execution_count"],
            intervention_count=p["intervention_count"],
            recovery_count=p["recovery_count"],
        )

        total_exec = p["successful_execution_count"] + p["failed_execution_count"]
        status = determine_recommendation_status(
            learning_score=score,
            approval_count=p["approval_count"],
            rejection_count=p["rejection_count"],
            edit_count=p["edit_count"],
            execution_count=total_exec,
            successful_execution_count=p["successful_execution_count"],
            failed_execution_count=p["failed_execution_count"],
        )

        expl = generate_learning_explanation(
            status=status,
            score=score,
            approval_count=p["approval_count"],
            rejection_count=p["rejection_count"],
            edit_count=p["edit_count"],
            execution_count=total_exec,
            successful_execution_count=p["successful_execution_count"],
            failed_execution_count=p["failed_execution_count"],
            intervention_count=p["intervention_count"],
            recovery_count=p["recovery_count"],
        )

        is_score_ok = round(score, 2) == round(tc["expected_score"], 2)
        is_status_ok = status == tc["expected_status"]
        has_expl = bool(expl and len(expl) > 10)

        if is_score_ok:
            score_passed += 1
        if is_status_ok:
            status_passed += 1
        if has_expl:
            explanations_generated += 1

        details.append({
            "test_case": tc["name"],
            "calculated_score": score,
            "expected_score": tc["expected_score"],
            "score_match": is_score_ok,
            "assigned_status": status.value,
            "expected_status": tc["expected_status"].value,
            "status_match": is_status_ok,
            "has_explanation": has_expl,
        })

    score_accuracy = round(score_passed / total_tests, 4) if total_tests > 0 else 0.0
    status_accuracy = round(status_passed / total_tests, 4) if total_tests > 0 else 0.0
    explanation_coverage = round(explanations_generated / total_tests, 4) if total_tests > 0 else 0.0

    return {
        "total_test_cases": total_tests,
        "score_accuracy": score_accuracy,
        "status_accuracy": status_accuracy,
        "explanation_coverage": explanation_coverage,
        "formula_verified": score_passed == total_tests,
        "all_passed": (score_passed == total_tests) and (status_passed == total_tests),
        "details": details,
    }
