"""
Benchmark evaluation datasets for WorkFlowOS.
"""

from evaluation.datasets.scenarios import (
    GroundTruth,
    BenchmarkScenario,
    get_benchmark_scenarios,
    get_scenario_by_id,
)

__all__ = [
    "GroundTruth",
    "BenchmarkScenario",
    "get_benchmark_scenarios",
    "get_scenario_by_id",
]
