"""
WorkFlowOS Phase 15: Confidence Calibration Metrics

Evaluates the correspondence between model/heuristic confidence scores
and empirical prediction correctness.

Note: On small synthetic benchmark datasets, these metrics evaluate
directional alignment and distribution, NOT statistical production calibration.
"""

from dataclasses import dataclass
from typing import Dict, List, Any
import statistics


@dataclass(frozen=True)
class CalibrationMetrics:
    """Confidence distribution and calibration metrics."""
    sample_count: int
    mean_confidence: float
    min_confidence: float
    max_confidence: float
    median_confidence: float
    correct_mean_confidence: float
    incorrect_mean_confidence: float
    calibration_delta: float
    note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "mean_confidence": self.mean_confidence,
            "min_confidence": self.min_confidence,
            "max_confidence": self.max_confidence,
            "median_confidence": self.median_confidence,
            "correct_mean_confidence": self.correct_mean_confidence,
            "incorrect_mean_confidence": self.incorrect_mean_confidence,
            "calibration_delta": self.calibration_delta,
            "note": self.note,
        }


def calculate_confidence_calibration(
    predictions: List[Dict[str, Any]],
) -> CalibrationMetrics:
    """
    Computes confidence distribution and directional calibration metrics.

    Args:
        predictions: List of dicts, each containing:
                     - 'confidence': float in [0.0, 1.0]
                     - 'is_correct': bool (True if matched ground truth, False otherwise)
    """
    if not predictions:
        return CalibrationMetrics(
            sample_count=0,
            mean_confidence=0.0,
            min_confidence=0.0,
            max_confidence=0.0,
            median_confidence=0.0,
            correct_mean_confidence=0.0,
            incorrect_mean_confidence=0.0,
            calibration_delta=0.0,
            note="No prediction samples available for calibration analysis.",
        )

    confidences = [float(p.get("confidence", 0.0)) for p in predictions]
    correct_confs = [
        float(p.get("confidence", 0.0)) for p in predictions if p.get("is_correct")
    ]
    incorrect_confs = [
        float(p.get("confidence", 0.0)) for p in predictions if not p.get("is_correct")
    ]

    mean_conf = round(statistics.mean(confidences), 4)
    min_conf = round(min(confidences), 4)
    max_conf = round(max(confidences), 4)
    median_conf = round(statistics.median(confidences), 4)

    correct_mean = (
        round(statistics.mean(correct_confs), 4) if correct_confs else 0.0
    )
    incorrect_mean = (
        round(statistics.mean(incorrect_confs), 4) if incorrect_confs else 0.0
    )
    delta = round(correct_mean - incorrect_mean, 4)

    note = (
        f"Evaluated across {len(predictions)} benchmark predictions. "
        "Small synthetic dataset: demonstrates heuristic directional separation; "
        "does not establish production-scale probability calibration."
    )

    return CalibrationMetrics(
        sample_count=len(predictions),
        mean_confidence=mean_conf,
        min_confidence=min_conf,
        max_confidence=max_conf,
        median_confidence=median_conf,
        correct_mean_confidence=correct_mean,
        incorrect_mean_confidence=incorrect_mean,
        calibration_delta=delta,
        note=note,
    )
