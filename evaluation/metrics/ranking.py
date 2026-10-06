"""
WorkFlowOS Phase 15: Ranking Metrics

Implements deterministic evaluation metrics for ranking quality (Phase 8 pattern ranking):
- Top-1 Accuracy: Proportion of test instances where the most relevant workflow is ranked #1.
- Top-k Recall: Proportion where the ground truth workflow appears within the top-k positions.
- Mean Reciprocal Rank (MRR): Average of reciprocal ranks (1 / rank) for ground-truth items.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass(frozen=True)
class RankingMetrics:
    """Standard ranking evaluation metrics."""
    top_1_accuracy: float
    top_k_recall: float
    mrr: float
    k: int
    total_queries: int
    successful_rankings: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "top_1_accuracy": self.top_1_accuracy,
            "top_k_recall": self.top_k_recall,
            "mrr": self.mrr,
            "k": self.k,
            "total_queries": self.total_queries,
            "successful_rankings": self.successful_rankings,
        }


def calculate_ranking_metrics(
    rank_positions: List[Optional[int]],
    k: int = 3,
) -> RankingMetrics:
    """
    Computes Top-1 accuracy, Top-k recall, and MRR.

    Args:
        rank_positions: List of 1-based ranks where the expected ground truth item appeared.
                       None indicates the expected item was not found in the ranked list.
        k: Threshold for top-k recall.
    """
    if not rank_positions:
        return RankingMetrics(
            top_1_accuracy=0.0,
            top_k_recall=0.0,
            mrr=0.0,
            k=k,
            total_queries=0,
            successful_rankings=0,
        )

    total_queries = len(rank_positions)
    top_1_matches = 0
    top_k_matches = 0
    reciprocal_rank_sum = 0.0
    successful_rankings = 0

    for pos in rank_positions:
        if pos is not None and pos > 0:
            successful_rankings += 1
            if pos == 1:
                top_1_matches += 1
            if pos <= k:
                top_k_matches += 1
            reciprocal_rank_sum += 1.0 / float(pos)

    top_1_acc = round(top_1_matches / total_queries, 4)
    top_k_rec = round(top_k_matches / total_queries, 4)
    mrr_score = round(reciprocal_rank_sum / total_queries, 4)

    return RankingMetrics(
        top_1_accuracy=top_1_acc,
        top_k_recall=top_k_rec,
        mrr=mrr_score,
        k=k,
        total_queries=total_queries,
        successful_rankings=successful_rankings,
    )
