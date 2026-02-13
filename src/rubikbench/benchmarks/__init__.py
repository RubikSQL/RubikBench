"""Benchmark setup registry."""

from pathlib import Path
from typing import Optional

from .rubikbench import setup as setup_rubikbench, resolve_db as _resolve_rubikbench
from .birdsql import setup as setup_birdsql, resolve_db as _resolve_birdsql
from .kaggledbqa import setup as setup_kaggledbqa, resolve_db as _resolve_kaggledbqa

BENCHMARKS = {
    "rubikbench": setup_rubikbench,
    "birdsql": setup_birdsql,
    "kaggledbqa": setup_kaggledbqa,
}

BENCHMARK_NAMES = ["RubikBench", "BirdSQL", "KaggleDBQA"]

_DB_RESOLVERS = {
    "rubikbench": _resolve_rubikbench,
    "birdsql": _resolve_birdsql,
    "kaggledbqa": _resolve_kaggledbqa,
}

_DEFAULT_DATA_DIRS = {
    "rubikbench": Path("./data/RubikBench"),
    "birdsql": Path("./data/BirdSQL"),
    "kaggledbqa": Path("./data/KaggleDBQA"),
}


def resolve_db_path(benchmark: str, database: str, data_dir: Optional[Path] = None) -> Path:
    """Resolve database file path from benchmark + database name."""
    key = benchmark.lower()
    if key not in _DB_RESOLVERS:
        raise KeyError(f"Unknown benchmark: {benchmark!r}")
    base = data_dir or _DEFAULT_DATA_DIRS[key]
    path = _DB_RESOLVERS[key](base, database)
    return path


__all__ = ["BENCHMARKS", "BENCHMARK_NAMES", "resolve_db_path"]
