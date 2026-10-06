"""
WorkFlowOS Phase 15: Classification Metrics

Implements deterministic evaluation metrics for binary and multi-class
classification tasks (e.g., workflow detection, state transitions):
- Precision
- Recall
- F1 Score
- Accuracy
- Confusion Matrix Counts (TP, FP, FN, TN)
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class ClassificationMetrics:
    """Standard classification evaluation metrics."""
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1: float
    accuracy: float
    total_samples: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "accuracy": self.accuracy,
            "total_samples": self.total_samples,
        }


def calculate_classification_metrics(
    true_positives: int,
    false_positives: int,
    false_negatives: int,
    true_negatives: int,
) -> ClassificationMetrics:
    """
    Calculates deterministic precision, recall, F1 score, and accuracy.

    Handles zero-denominator cases safely without division-by-zero errors.
    All scores are rounded to 4 decimal places.
    """
    tp = max(0, int(true_positives))
    fp = max(0, int(false_positives))
    fn = max(0, int(false_negatives))
    tn = max(0, int(true_negatives))
    total = tp + fp + fn + tn

    # Precision = TP / (TP + FP)
    if (tp + fp) > 0:
        precision = round(tp / (tp + fp), 4)
    else:
        precision = 0.0

    # Recall = TP / (TP + FN)
    if (tp + fn) > 0:
        recall = round(tp / (tp + fn), 4)
    else:
        recall = 0.0

    # F1 = 2 * (Precision * Recall) / (Precision + Recall)
    if (precision + recall) > 0:
        f1 = round(2.0 * (precision * recall) / (precision + recall), 4)
    else:
        f1 = 0.0

    # Accuracy = (TP + TN) / Total
    if total > 0:
        accuracy = round((tp + tn) / total, 4)
    else:
        accuracy = 0.0

    return ClassificationMetrics(
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=precision,
        recall=recall,
        f1=f1,
        accuracy=accuracy,
        total_samples=total,
    )
