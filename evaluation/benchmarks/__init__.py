"""
Benchmark suites for WorkFlowOS Phase 15.
"""

from evaluation.benchmarks.discovery import run_discovery_benchmark
from evaluation.benchmarks.ai_generation import run_ai_generation_benchmark
from evaluation.benchmarks.learning import run_learning_benchmark
from evaluation.benchmarks.planning import run_planning_benchmark
from evaluation.benchmarks.closed_loop import run_closed_loop_benchmark
from evaluation.benchmarks.execution import run_execution_benchmark
from evaluation.benchmarks.safety import run_safety_benchmark
from evaluation.benchmarks.end_to_end import run_end_to_end_benchmark
from evaluation.benchmarks.performance import run_performance_benchmark

__all__ = [
    "run_discovery_benchmark",
    "run_ai_generation_benchmark",
    "run_learning_benchmark",
    "run_planning_benchmark",
    "run_closed_loop_benchmark",
    "run_execution_benchmark",
    "run_safety_benchmark",
    "run_end_to_end_benchmark",
    "run_performance_benchmark",
]
