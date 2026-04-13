"""Benchmark setup registry."""

from typing import Optional

from ahvn.utils.basic.path_utils import pj

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

_BENCHMARK_CANONICAL = {
    "rubikbench": "RubikBench",
    "birdsql": "BirdSQL",
    "kaggledbqa": "KaggleDBQA",
}

_DEFAULT_DATA_DIRS = {
    "rubikbench": pj("./data", "RubikBench"),
    "birdsql": pj("./data", "BirdSQL"),
    "kaggledbqa": pj("./data", "KaggleDBQA"),
}

_DEFAULT_QUERY_FILES = {
    "rubikbench": "RubikBench.json",
    "birdsql": "BirdSQL.json",
    "kaggledbqa": "KaggleDBQA.json",
}

_DEFAULT_PRIMARY_DATABASES = {
    "rubikbench": "RubikBench",
    "birdsql": None,
    "kaggledbqa": None,
}


def benchmark_key(benchmark: Optional[str], default: str = "RubikBench") -> str:
    key = str(benchmark or default).strip().lower()
    if key not in _BENCHMARK_CANONICAL:
        raise KeyError(f"Unknown benchmark: {benchmark!r}")
    return key


def normalize_benchmark_name(benchmark: Optional[str], default: str = "RubikBench") -> str:
    return _BENCHMARK_CANONICAL[benchmark_key(benchmark, default=default)]


def default_data_dir(benchmark: Optional[str]) -> str:
    return _DEFAULT_DATA_DIRS[benchmark_key(benchmark)]


def default_queries_path(benchmark: Optional[str]) -> str:
    key = benchmark_key(benchmark)
    return pj(default_data_dir(key), "queries", _DEFAULT_QUERY_FILES[key])


def default_database_path(benchmark: Optional[str]) -> Optional[str]:
    key = benchmark_key(benchmark)
    database = _DEFAULT_PRIMARY_DATABASES[key]
    if not database:
        return None
    return resolve_db_path(_BENCHMARK_CANONICAL[key], database, data_dir=default_data_dir(key))


def resolve_db_path(benchmark: str, database: str, data_dir: Optional[str] = None) -> str:
    """Resolve database file path from benchmark + database name."""
    key = benchmark_key(benchmark)
    base = data_dir or _DEFAULT_DATA_DIRS[key]
    return _DB_RESOLVERS[key](base, database)


__all__ = [
    "BENCHMARKS",
    "BENCHMARK_NAMES",
    "benchmark_key",
    "normalize_benchmark_name",
    "default_data_dir",
    "default_queries_path",
    "default_database_path",
    "resolve_db_path",
]
