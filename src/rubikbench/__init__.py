"""RubikBench: Enterprise-scale NL2SQL Benchmark."""

__version__ = "0.9.1"
__author__ = "RubikSQL Team"

from .evaluate import RubikBenchEvaluator
from .queries import QuerySet

__all__ = [
    "RubikBenchEvaluator",
    "QuerySet",
    "__version__",
]
