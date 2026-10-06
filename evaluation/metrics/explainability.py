"""
WorkFlowOS Phase 15: Explainability Coverage Metrics

Measures structural coverage of explanatory evidence across WorkFlowOS components:
- Discovery evidence (session support, sequence alignment)
- Confidence explanation (frequency, consistency, entropy)
- Ranking explanation (utility breakdown, tier rationale)
- Learning explanation (feedback and execution history rationale)
- Automation strategy explanation (selection and fallback rationale)

Formula:
    explanation_coverage = explanations_present / explanations_expected
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass(frozen=True)
class ExplainabilityMetrics:
    """Structural explanation coverage metrics."""
    explanations_present: int
    explanations_expected: int
    explanation_coverage: float
    field_coverage: Dict[str, float] = field(default_factory=dict)
    component_breakdown: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "explanations_present": self.explanations_present,
            "explanations_expected": self.explanations_expected,
            "explanation_coverage": self.explanation_coverage,
            "field_coverage": self.field_coverage,
            "component_breakdown": self.component_breakdown,
        }


def calculate_explainability_coverage(
    evaluations: List[Dict[str, Any]],
) -> ExplainabilityMetrics:
    """
    Computes structural explanation coverage from a collection of component evaluation records.

    Each record in evaluations is expected to have:
        - 'component': str (e.g. 'discovery', 'planning', 'learning')
        - 'checks': Dict[str, bool] (e.g. {'confidence_explanation': True, 'ranking_explanation': True})
    """
    if not evaluations:
        return ExplainabilityMetrics(
            explanations_present=0,
            explanations_expected=0,
            explanation_coverage=0.0,
            field_coverage={},
            component_breakdown={},
        )

    total_present = 0
    total_expected = 0
    field_counts: Dict[str, Dict[str, int]] = {}
    component_breakdown: Dict[str, Dict[str, int]] = {}

    for ev in evaluations:
        comp = ev.get("component", "general")
        checks = ev.get("checks", {})
        if comp not in component_breakdown:
            component_breakdown[comp] = {"present": 0, "expected": 0}

        for field_name, is_present in checks.items():
            total_expected += 1
            component_breakdown[comp]["expected"] += 1

            if field_name not in field_counts:
                field_counts[field_name] = {"present": 0, "expected": 0}
            field_counts[field_name]["expected"] += 1

            if is_present:
                total_present += 1
                component_breakdown[comp]["present"] += 1
                field_counts[field_name]["present"] += 1

    coverage = round(total_present / total_expected, 4) if total_expected > 0 else 0.0

    field_coverage = {
        fname: round(fstats["present"] / fstats["expected"], 4)
        for fname, fstats in field_counts.items()
        if fstats["expected"] > 0
    }

    return ExplainabilityMetrics(
        explanations_present=total_present,
        explanations_expected=total_expected,
        explanation_coverage=coverage,
        field_coverage=field_coverage,
        component_breakdown=component_breakdown,
    )
