#!/usr/bin/env python3
"""RubikBench CLI."""

import sys
from pathlib import Path
from typing import Dict, Optional

import click

from rubikbench import RubikBenchEvaluator, QuerySet, __version__
from rubikbench.dialect import get_supported_dialects, safe_sql
from rubikbench.benchmarks import BENCHMARKS, BENCHMARK_NAMES, resolve_db_path

# Color utilities
try:
    from ahvn.utils.basic.color_utils import (
        color_success,
        color_error,
        color_warning,
        color_info,
        color_debug,
        color_magenta,
        color_grey,
        print_success,
        print_error,
        print_warning,
        print_info,
    )

    HAS_COLORS = True
except ImportError:
    HAS_COLORS = False
    from sys import stderr

    # Fallback to simple string functions
    def color_success(s, console=True):
        return str(s)

    def color_error(s, console=True):
        return str(s)

    def color_warning(s, console=True):
        return str(s)

    def color_info(s, console=True):
        return str(s)

    def color_debug(s, console=True):
        return str(s)

    def color_magenta(s, console=True):
        return str(s)

    def print_success(*args, **kwargs):
        print(*args, **kwargs)

    def print_error(*args, **kwargs):
        f = kwargs.pop("file", stderr)
        print(*args, file=f, **kwargs)

    def print_warning(*args, **kwargs):
        f = kwargs.pop("file", stderr)
        print(*args, file=f, **kwargs)

    def print_info(*args, **kwargs):
        f = kwargs.pop("file", stderr)
        print(*args, file=f, **kwargs)


# Default paths (RubikBench)
DEFAULT_DATA_DIR = "./data/RubikBench"
DEFAULT_QUERIES_PATH = "./data/RubikBench/queries/RubikBench.json"
DEFAULT_DB_NAME = "RubikBench.duckdb"
DEFAULT_DB_PATH = "./data/RubikBench/databases/RubikBench.duckdb"

# Display formatting
BANNER_WIDTH = 70

# Provider auto-detection
_PROVIDER_MAP = {
    ".duckdb": "duckdb",
    ".sqlite": "sqlite",
    ".sqlite3": "sqlite",
    ".db": "sqlite",
}


def _detect_provider(db_path: str) -> str:
    """Detect provider from file extension."""
    ext = Path(db_path).suffix.lower()
    return _PROVIDER_MAP.get(ext, "duckdb")


def _banner(title: str, console: bool = True) -> str:
    """Centered title banner."""
    title_len = len(title)
    if title_len >= BANNER_WIDTH - 4:
        # Title too long, just use simple borders
        return color_warning(f"{'=' * 3} {title} {'=' * 3}", console)

    total_padding = BANNER_WIDTH - title_len
    left_pad = total_padding // 2
    right_pad = total_padding - left_pad

    return color_warning(f"{'=' * left_pad} {title} {'=' * right_pad}", console)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__)
def cli():
    """RubikBench: Enterprise-scale NL2SQL Benchmark"""
    pass


SUPPORTED_BENCHMARKS = BENCHMARK_NAMES


@cli.command()
@click.option(
    "--benchmark",
    "-B",
    type=click.Choice(SUPPORTED_BENCHMARKS, case_sensitive=False),
    default="RubikBench",
    help="Benchmark to set up (default: RubikBench)",
)
@click.option("--data", "-d", default=None, help="Directory to store benchmark data (default depends on benchmark)")
@click.option("--force", "-f", is_flag=True, help="Force re-download even if files exist")
@click.option("--remove-zip", "-rm", is_flag=True, help="Remove downloaded archive after extraction")
@click.option("--birdsql-no-corrections", is_flag=True, default=False, help="BirdSQL: skip applying corrections to queries")
def setup(benchmark: str, data: Optional[str], force: bool, remove_zip: bool, birdsql_no_corrections: bool):
    """Set up benchmark datasets."""
    from importlib import import_module

    mod = import_module(f"rubikbench.benchmarks.{benchmark.lower()}")
    data_path = Path(data) if data else mod.DEFAULT_DATA_DIR
    setup_fn = BENCHMARKS[benchmark.lower()]
    kwargs = dict(force=force, remove_zip=remove_zip)
    if benchmark.lower() == "birdsql":
        kwargs["no_corrections"] = birdsql_no_corrections
    setup_fn(data_path, **kwargs)


@cli.command()
@click.option(
    "--database",
    "-db",
    default=None,
    type=click.Path(exists=True),
    help=f"Path to database file (default: {DEFAULT_DB_PATH})",
)
def test(database: Optional[str]):
    """Test database connectivity."""
    if database is None:
        db_path = Path(DEFAULT_DB_PATH)
        if not db_path.exists():
            click.echo(click.style(f"✗ Database not found at default location: {db_path}", fg="red"))
            click.echo("  Run 'rubikbench setup' to download the database")
            sys.exit(1)
        database = str(db_path)

    from ahvn.utils.db import Database

    db_provider = _detect_provider(database)
    click.echo(f"Testing database: {database}")
    click.echo(f"  Provider: {db_provider}")

    try:
        db = Database(provider=db_provider, database=database)
        result = db.execute("SELECT 1+1 AS result")
        rows = result.to_list()
        assert rows and rows[0]["result"] == 2, "Unexpected result"

        tables = db.db_tabs()
        click.echo(click.style("✓ Connection successful", fg="green"))
        click.echo(f"  Tables: {len(tables)}")
        db.close()
    except Exception as e:
        click.echo(click.style(f"✗ Test failed: {e}", fg="red"))
        sys.exit(1)


@cli.command("eval")
@click.argument("submission", type=click.Path(exists=True))
@click.option("--input-file", "-in", type=click.Path(exists=True), help="Path to submission JSON file (alternative to positional argument)")
@click.option("--queries", "-q", default=None, type=click.Path(exists=True), help=f"Path to queries JSON file (default: {DEFAULT_QUERIES_PATH})")
@click.option(
    "--database",
    "-db",
    default=None,
    type=click.Path(exists=True),
    help="Path to database file; provider auto-detected from extension (default: auto-inferred from queries)",
)
@click.option("--output-file", "-out", default=None, type=click.Path(), help="Output path for detailed results (JSON)")
@click.option("--ids", "-i", multiple=True, help="Specific query IDs to evaluate")
@click.option(
    "--split", "-s", type=click.Choice(["simple", "moderate", "challenging", "nightmare", "unknown"]), multiple=True, help="Filter by difficulty level"
)
@click.option("--dialect", default=None, help=f"SQL dialect of submission (supported: {', '.join(get_supported_dialects())})")
@click.option("--bf-beta", "-bfb", default=2.0, type=float, help="Beta for BF score")
@click.option("--sf-beta", "-sfb", default=1.0, type=float, help="Beta for SF score")
@click.option("--ordered", "-o", is_flag=True, default=True, help="Use ordered evaluation (default: True)")
@click.option("--unordered", "-u", is_flag=True, default=False, help="Use unordered evaluation (overrides --ordered)")
@click.option("--dedup/--no-dedup", default=False, help="Drop duplicate rows before scoring (default: True). Use --dedup for leisure evaluation.")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose output (progress bar, detailed info)")
def evaluate(
    submission: Optional[str],
    input_file: Optional[str],
    queries: Optional[str],
    database: Optional[str],
    output_file: Optional[str],
    ids: tuple,
    split: tuple,
    dialect: str,
    bf_beta: float,
    sf_beta: float,
    ordered: bool,
    unordered: bool,
    dedup: bool,
    verbose: bool,
):
    """Evaluate a SQL submission. SUBMISSION: path to JSON {query_id: sql, ...}."""
    # Determine submission file (input_file takes precedence over positional argument)
    submission_file = input_file or submission
    if submission_file is None:
        click.echo(click.style("✗ Submission file required. Provide as argument or use --input-file/-in", fg="red"))
        sys.exit(1)

    # Use default paths if not specified
    if queries is None:
        queries = DEFAULT_QUERIES_PATH
        if not Path(queries).exists():
            click.echo(click.style(f"✗ Queries file not found at default location: {queries}", fg="red"))
            sys.exit(1)

    # Determine unordered flag (unordered overrides ordered)
    use_unordered = unordered or not ordered
    from ahvn.utils.db import Database

    # Load queries first (needed for multi-db resolution)
    query_set = QuerySet(queries)

    # ── Database resolution ──────────────────────────────────────────────
    db = None
    db_resolver = None

    # tgt_dialect will be determined alongside database resolution
    tgt_dialect = "duckdb"  # default

    if database is not None:
        # Explicit single-database mode
        db_provider = _detect_provider(database)
        tgt_dialect = db_provider  # provider name matches dialect name
        try:
            db = Database(provider=db_provider, database=database)
        except Exception as e:
            click.echo(click.style(f"✗ Database error: {e}", fg="red"))
            sys.exit(1)
        click.echo(f"Database: {database}")
    else:
        # Try to auto-resolve from query metadata (benchmark + database fields)
        sample_q = next(iter(query_set), None)
        has_meta = sample_q is not None and sample_q.get("benchmark") and sample_q.get("database")

        if has_meta:
            # Multi-database mode: build a resolver with connection cache
            _db_cache: Dict[str, Database] = {}

            def _resolve(query):
                bm = query.get("benchmark", "")
                db_name = query.get("database", "")
                cache_key = f"{bm}:{db_name}"
                if cache_key not in _db_cache:
                    db_path = resolve_db_path(bm, db_name)
                    if not db_path.exists():
                        raise FileNotFoundError(
                            f"Database not found: {db_path}  " f"(benchmark={bm!r}, database={db_name!r}). " f"Run 'rubikbench setup -B {bm}' first."
                        )
                    provider = _detect_provider(str(db_path))
                    _db_cache[cache_key] = Database(provider=provider, database=str(db_path))
                return _db_cache[cache_key]

            db_resolver = _resolve
            # Infer target dialect from the first query's resolved database
            first_db_path = resolve_db_path(
                sample_q.get("benchmark", ""),
                sample_q.get("database", ""),
            )
            tgt_dialect = _detect_provider(str(first_db_path))
            # Summarise which databases will be used
            benchmarks_found = set()
            dbs_found = set()
            for q in query_set:
                bm = q.get("benchmark", "")
                db_name = q.get("database", "")
                if bm:
                    benchmarks_found.add(bm)
                if db_name:
                    dbs_found.add(db_name)
            click.echo(f"Database: auto-resolve from query metadata ({len(dbs_found)} databases across {', '.join(sorted(benchmarks_found))})")
        else:
            # Fall back to default RubikBench database
            db_path_default = Path(DEFAULT_DB_PATH)
            if not db_path_default.exists():
                click.echo(click.style(f"✗ Database not found at default location: {db_path_default}", fg="red"))
                click.echo("  Provide --database or run 'rubikbench setup'")
                sys.exit(1)
            db_provider = _detect_provider(str(db_path_default))
            tgt_dialect = db_provider
            try:
                db = Database(provider=db_provider, database=str(db_path_default))
            except Exception as e:
                click.echo(click.style(f"✗ Database error: {e}", fg="red"))
                sys.exit(1)
            database = str(db_path_default)
            click.echo(f"Database: {database}")

    click.echo(f"Evaluating submission: {submission_file}")
    click.echo(f"Queries file: {queries}")
    if dialect is None:
        dialect = tgt_dialect
        click.echo(f"SQL dialect: {dialect} (default, use `--dialect` to specify your submission sql dialect)")
    else:
        click.echo(f"SQL dialect: {dialect}")
    if use_unordered:
        click.echo("Mode: Unordered evaluation")
    else:
        click.echo("Mode: Ordered evaluation")
    click.echo(f"Dedup: {'enabled' if dedup else 'disabled'}")

    click.echo(f"Loaded {len(query_set)} queries")

    # Create evaluator
    click.echo(f"Target dialect: {tgt_dialect}")
    evaluator = RubikBenchEvaluator(
        db=db,
        queries=query_set,
        bf_beta=bf_beta,
        sf_beta=sf_beta,
        ndigits=3,  # Default precision
        src=dialect,
        tgt=tgt_dialect,
        unordered=use_unordered,
        db_resolver=db_resolver,
        dedup=dedup,
    )

    # Filter options
    query_ids = list(ids) if ids else None
    split_filter = list(split) if split else None

    # Run evaluation
    try:
        report = evaluator.evaluate_submission(submission_file, query_ids=query_ids, difficulty=split_filter, progress=verbose)
    except Exception as e:
        click.echo(click.style(f"✗ Evaluation failed: {e}", fg="red"))
        sys.exit(1)
    finally:
        if db is not None:
            db.close()
        if db_resolver is not None:
            # Close all cached connections
            for cached_db in _db_cache.values():
                try:
                    cached_db.close()
                except Exception:
                    pass

    # Print results using table_display
    from ahvn.utils.db import table_display
    from sys import stdout

    console = hasattr(stdout, "isatty") and stdout.isatty() and HAS_COLORS

    click.echo(_banner("EVALUATION RESULTS", console))

    # Overall metrics summary
    click.echo(f"\n{color_info('Total queries (N):', console)} {report.N['overall']}")
    click.echo(f"{color_info('Compilable (C):', console)} {report.C['overall']}")
    click.echo(f"{color_info('Compilable rate (C/N):', console)} {report.compilable['overall']:5.2%}")

    # Format scores with color based on performance
    def _format_score(score: Optional[float]) -> str:
        if score is None:
            return color_grey("N/A", console)
        if score >= 0.8:
            return color_success(f"{score:5.2%}", console)
        elif score >= 0.6:
            return color_warning(f"{score:5.2%}", console)
        elif score >= 0.2:
            return f"{score:5.2%}"
        else:
            return color_grey(f"{score:5.2%}", console)

    # Overall scores table
    click.echo(f"\n{color_warning('Overall Scores', console)}")
    click.echo(
        table_display(
            [
                {
                    "Metric": color_info("EX", console),
                    "Unordered": _format_score(report.scores["overall"]["exu"]),
                    "Ordered": _format_score(report.scores["overall"]["exo"]),
                },
                {
                    "Metric": color_info(f"SF (β={sf_beta:.1f})", console),
                    "Unordered": color_grey("N/A", console),
                    "Ordered": _format_score(report.scores["overall"].get("sfo")),
                },
                {
                    "Metric": color_info(f"BF (β={bf_beta:.1f})", console),
                    "Unordered": _format_score(report.scores["overall"]["bfu"]),
                    "Ordered": _format_score(report.scores["overall"]["bfo"]),
                },
            ]
        )
    )

    # By difficulty table
    difficulties = [k for k in report.N.keys() if k != "overall"]
    if difficulties:
        click.echo(f"\n{color_warning('Scores by Difficulty', console)}")

        # Get the list of difficulty levels in order
        diff_levels = ["simple", "moderate", "challenging", "nightmare", "unknown"]
        if "nightmare" in difficulties:
            diff_levels.append("nightmare")
        if "unknown" in difficulties:
            diff_levels.append("unknown")
        # Filter to only those that exist
        diff_levels = [d for d in diff_levels if d in difficulties]

        # Build rows: each metric type as a separate row
        metric_rows = [
            {
                "Metric": color_info("EX Unordered", console),
                **{
                    (color_error(diff) if diff == "nightmare" else diff): _format_score(report.scores[diff]["exu"]) if diff in report.scores else "N/A"
                    for diff in diff_levels
                },
            },
            {
                "Metric": color_info("EX Ordered", console),
                **{
                    (color_error(diff) if diff == "nightmare" else diff): _format_score(report.scores[diff]["exo"]) if diff in report.scores else "N/A"
                    for diff in diff_levels
                },
            },
            {
                "Metric": color_info(f"SF (β={sf_beta:.1f}) Ordered", console),
                **{
                    (color_error(diff) if diff == "nightmare" else diff): _format_score(report.scores[diff]["sfo"]) if diff in report.scores else "N/A"
                    for diff in diff_levels
                },
            },
            {
                "Metric": color_info(f"BF (β={bf_beta:.1f}) Unordered", console),
                **{
                    (color_error(diff) if diff == "nightmare" else diff): _format_score(report.scores[diff]["bfu"]) if diff in report.scores else "N/A"
                    for diff in diff_levels
                },
            },
            {
                "Metric": color_info(f"BF (β={bf_beta:.1f}) Ordered", console),
                **{
                    (color_error(diff) if diff == "nightmare" else diff): _format_score(report.scores[diff]["bfo"]) if diff in report.scores else "N/A"
                    for diff in diff_levels
                },
            },
        ]
        click.echo(table_display(metric_rows))

    # Save detailed results
    if output_file:
        report.to_json(output_file)
        click.echo(f"\nDetailed results saved to: {output_file}")

    # Show failed queries
    failed = [r for r in report.results if not r.success]
    if failed:
        click.echo(f"\nFailed queries ({len(failed)}, showing up to 10):")
        for r in failed[:10]:
            click.echo(f"  {r.query_id}: {r.pred_error}")

    # Show GT failures
    if report.gt_failures:
        click.echo(f"\nGround truth failures ({len(report.gt_failures)}, showing up to 10):")
        for gf in report.gt_failures[:10]:
            click.echo(f"  {gf['query_id']}: {gf['error']}")


@cli.command("exec")
@click.argument("query_id", default=None, required=False)
@click.argument("sql", default=None, required=False)
@click.option("--queries", "-q", default=None, type=click.Path(exists=True), help=f"Path to queries JSON file (default: {DEFAULT_QUERIES_PATH})")
@click.option("--database", "-db", default=None, type=click.Path(exists=True), help=f"Path to database file (default: {DEFAULT_DB_PATH})")
@click.option("--dialect", default="duckdb", help="SQL dialect")
@click.option("--ordered", "-o", is_flag=True, default=True, help="Use ordered evaluation (default: True)")
@click.option("--unordered", "-u", is_flag=True, default=False, help="Use unordered evaluation (overrides --ordered)")
@click.option("--dedup/--no-dedup", default=True, help="Drop duplicate rows before scoring (default: True). Use --no-dedup for strict evaluation.")
def exec_cmd(
    query_id: Optional[str], sql: Optional[str], queries: Optional[str], database: Optional[str], dialect: str, ordered: bool, unordered: bool, dedup: bool
):
    """Execute and optionally evaluate a SQL query."""
    from ahvn.utils.db import Database, table_display

    from sys import stdout

    console = hasattr(stdout, "isatty") and stdout.isatty() and HAS_COLORS

    # Handle the case where only one argument is provided
    # If query_id is provided but sql is not, check if query_id looks like a SQL statement
    if query_id is not None and sql is None:
        stripped_arg = query_id.strip()
        # Heuristic: treat as SQL if it contains SQL keywords or whitespace,
        # otherwise assume it's a query ID (works for both "Q00001" and numeric IDs like "195")
        _sql_indicators = ("SELECT", "INSERT", "UPDATE", "DELETE", "WITH", "CREATE", "DROP", "ALTER")
        if " " in stripped_arg or stripped_arg.upper().startswith(_sql_indicators):
            sql = stripped_arg
            query_id = None

    # Always strip SQL if it's provided
    if sql is not None:
        sql = sql.strip()

    # Validate that at least one argument is provided
    if query_id is None and sql is None:
        click.echo(color_error("✗ At least one of QUERY_ID or SQL must be specified", console))
        sys.exit(1)

    # Use default paths if not specified
    if queries is None and query_id is not None:
        queries = DEFAULT_QUERIES_PATH
        if not Path(queries).exists():
            click.echo(color_error(f"✗ Queries file not found at default location: {queries}", console))
            sys.exit(1)

    if database is None:
        db_path = Path(DEFAULT_DB_PATH)
        if not db_path.exists():
            click.echo(color_error(f"✗ Database not found at default location: {db_path}", console))
            click.echo("  Run 'rubikbench setup' to download the database")
            sys.exit(1)
        database = str(db_path)

    # Determine unordered flag (unordered overrides ordered)
    use_unordered = unordered or not ordered

    # Load database
    db_provider = _detect_provider(database)
    try:
        db = Database(provider=db_provider, database=database)
    except Exception as e:
        click.echo(color_error(f"✗ Database error: {e}", console))
        sys.exit(1)

    # Case 1: SQL only
    if sql is not None and query_id is None:
        _execute_sql_only(db, sql)
        db.close()
        return

    # Load queries for query_id lookups
    query_set = QuerySet(queries)
    query_data = None
    if query_id:
        for q in query_set:
            if q["id"] == query_id:
                query_data = q
                break
        if query_data is None:
            click.echo(color_error(f"✗ Query ID not found: {query_id}", console))
            db.close()
            sys.exit(1)

    _show_query_info(query_data)
    click.echo()
    gt_sql = query_data.get("sql", "")

    from sys import stdout

    console = hasattr(stdout, "isatty") and stdout.isatty() and HAS_COLORS

    click.echo(_banner("GROUND TRUTH SQL", console))
    click.echo(gt_sql)
    click.echo()

    # Execute ground truth
    click.echo(_banner("GROUND TRUTH TABLE", console))
    _execute_and_display(db, gt_sql)
    click.echo()

    if sql is None:
        return

    click.echo(_banner("PREDICTED SQL", console))
    click.echo(sql)
    click.echo()

    # Execute predicted
    click.echo(_banner("PREDICTED TABLE", console))
    _execute_and_display(db, sql)
    click.echo()

    # Create evaluator and compute scores
    evaluator = RubikBenchEvaluator(
        db=db,
        queries=query_set,
        ndigits=3,
        src=dialect,
        unordered=use_unordered,
        dedup=dedup,
    )

    result = evaluator.evaluate_query(query_id, sql)
    db.close()

    # Display scores
    click.echo(_banner("EVALUATION SCORES", console))

    if result.success:
        # Format scores with color based on performance
        def _format_score(score: Optional[float]) -> str:
            if score is None:
                return color_grey("N/A", console)
            if score >= 0.8:
                return color_success(f"{score:5.2%}", console)
            elif score >= 0.6:
                return color_warning(f"{score:5.2%}", console)
            elif score >= 0.2:
                return f"{score:5.2%}"
            else:
                return color_grey(f"{score:5.2%}", console)

        click.echo(
            table_display(
                [
                    {"Metric": color_info("EX", console), "Ordered": _format_score(result.exo), "Unordered": _format_score(result.exu)},
                    {"Metric": color_info("BF", console), "Ordered": _format_score(result.bfo), "Unordered": _format_score(result.bfu)},
                    {"Metric": color_info("SF", console), "Ordered": _format_score(result.sfo), "Unordered": color_grey("N/A", console)},
                ]
            )
        )
    else:
        click.echo(color_error(f"Error: {result.pred_error}", console))


def _show_query_info(query_data: dict) -> None:
    """Display query information."""
    from sys import stdout

    console = hasattr(stdout, "isatty") and stdout.isatty() and HAS_COLORS

    click.echo(_banner("QUERY INFORMATION", console))

    benchmark = query_data.get("benchmark", "N/A")
    database: str = query_data.get("database", "N/A")
    query_id = query_data.get("id", "N/A")
    metadata = query_data.get("metadata", {})
    difficulty = metadata.get("difficulty", "N/A")

    click.echo(f"{color_info('Benchmark:', console)} {benchmark}")
    click.echo(f"{color_info('Database:', console)} {database}")
    click.echo(f"{color_info('Query ID:', console)} {color_magenta(query_id, console)}")

    # Color-code difficulty
    diff_colors = {"simple": color_success, "moderate": color_warning, "challenging": color_error}
    diff_color = diff_colors.get(difficulty, lambda x, c=True: str(x))
    click.echo(f"{color_info('Difficulty:', console)} {diff_color(difficulty, console)}")

    # Dialect
    dialect = query_data.get("dialect", "N/A")
    click.echo(f"{color_info('Dialect:', console)} {dialect}")

    # Order-relevant
    order_relevant = metadata.get("order-relevant")
    if order_relevant is True:
        click.echo(f"{color_info('Order-Relevant:', console)} {color_warning('Yes', console)}")
    elif order_relevant is False:
        click.echo(f"{color_info('Order-Relevant:', console)} No")

    # Verified
    verified = metadata.get("verified", False)
    if verified:
        click.echo(f"{color_info('Verified:', console)} {color_success('Yes', console)}")
    else:
        click.echo(f"{color_info('Verified:', console)} No")

    # Tags
    tags = metadata.get("query_tags", [])
    if tags:
        click.echo(f"{color_info('Tags:', console)} {', '.join(tags)}")

    # Context section
    context = query_data.get("context", {})
    if context:
        click.echo(f"\n{color_info('Context:', console)}")

        # Query time
        query_time = context.get("query_time")
        if query_time:
            # Format period: 202012 -> 2020-12
            qt_str = str(query_time)
            if len(qt_str) == 6:
                qt_str = f"{qt_str[:4]}-{qt_str[4:]}"
            click.echo(f"  Query Time: {qt_str}")

        # User profile
        profile = context.get("user_profile", {})
        if profile:
            occupation = profile.get("occupation", "")
            caliber = profile.get("caliber", "")
            currency = profile.get("currency", "")
            if occupation:
                click.echo(f"  Occupation: {occupation}")
            if caliber:
                click.echo(f"  Caliber: {caliber}")
            if currency:
                click.echo(f"  Currency: {currency}")

            # Region
            region = profile.get("region", {})
            if region:
                region_parts = []
                for key, val in region.items():
                    label = key.replace("_name_en", "").replace("_", " ").title()
                    if isinstance(val, list):
                        region_parts.append(f"{label}: {', '.join(val)}")
                    else:
                        region_parts.append(f"{label}: {val}")
                if region_parts:
                    click.echo(f"  Region: {'; '.join(region_parts)}")

            # Department
            dept = profile.get("department", {})
            if dept:
                dept_parts = []
                for key, val in dept.items():
                    label = key.replace("_name_en", "").replace("_", " ").title()
                    if isinstance(val, list):
                        dept_parts.append(f"{label}: {', '.join(val)}")
                    else:
                        dept_parts.append(f"{label}: {val}")
                if dept_parts:
                    click.echo(f"  Department: {'; '.join(dept_parts)}")

            # Preferences
            prefs = profile.get("preferences", [])
            if prefs:
                click.echo(f"  Preferences: {', '.join(prefs)}")

    # Question
    question = query_data.get("question", "")
    if question:
        click.echo(f"\n{color_info('Question:', console)}")
        # Wrap question text for better display
        import textwrap

        wrapped = textwrap.fill(question, width=68)
        for line in wrapped.split("\n"):
            click.echo(f"  {line}")


def _execute_sql_only(db, sql: str, label: str = "SQL") -> dict:
    """Execute SQL and display results."""
    from sys import stdout

    console = hasattr(stdout, "isatty") and stdout.isatty() and HAS_COLORS

    click.echo(_banner(label, console))
    click.echo(sql)

    return _execute_and_display(db, sql)


def _execute_and_display(db, sql: str) -> dict:
    """Execute SQL, display and return result."""
    from ahvn.utils.db import table_display
    from sys import stdout

    console = hasattr(stdout, "isatty") and stdout.isatty() and HAS_COLORS

    try:
        sql = safe_sql(sql)
        result = db.execute(sql)
        rows = result.to_list()

        if rows:
            # Display as table
            click.echo(table_display(rows))
        else:
            click.echo(f"{color_debug('  (empty result)', console)}")
        click.echo()

        return {"success": True, "rows": rows}

    except Exception as e:
        click.echo(color_error(f"\nError: {e}", console))
        click.echo()
        return {"success": False, "error": str(e)}


@cli.command("template")
@click.option("--queries", "-q", default=None, type=click.Path(exists=True), help=f"Path to queries JSON file (default: {DEFAULT_QUERIES_PATH})")
@click.option("--output-file", "-out", default="submission_template.json", help="Output path for submission template")
@click.option("--ids", "-i", multiple=True, help="Specific query IDs to include")
@click.option(
    "--split", "-s", type=click.Choice(["simple", "moderate", "challenging", "nightmare", "unknown"]), multiple=True, help="Filter by difficulty level"
)
@click.option("--tags", "-t", multiple=True, help="Filter by query tags (any tag matches)")
@click.option("--sql", default="", help="Custom default SQL placeholder (default: empty string)")
def template(queries: Optional[str], output_file: str, ids: tuple, split: tuple, tags: tuple, sql: str):
    """Generate a submission template JSON."""
    # Use default path if not specified
    if queries is None:
        queries = DEFAULT_QUERIES_PATH
        if not Path(queries).exists():
            click.echo(click.style(f"✗ Queries file not found at default location: {queries}", fg="red"))
            sys.exit(1)
    query_set = QuerySet(queries)

    # Apply filters
    if ids:
        query_set = query_set.filter(ids=list(ids))
    if split:
        query_set = query_set.filter(difficulty=list(split))
    if tags:
        query_set = query_set.filter(tags=list(tags))

    # Create template using QuerySet method
    query_set.create_template(output_file, placeholder=sql)

    click.echo(f"Generated submission template: {output_file}")
    click.echo(f"Total queries: {len(query_set)}")

    # Show breakdown if filtered
    if split:
        click.echo(f"Difficulty filter: {', '.join(split)}")
    if tags:
        click.echo(f"Tag filter: {', '.join(tags)}")
    if ids:
        click.echo(f"ID filter: {len(ids)} IDs specified")
    if sql:
        click.echo(f"Custom SQL placeholder: {sql}")


@cli.command("info")
@click.option("--queries", "-q", default=None, type=click.Path(exists=True), help=f"Path to queries JSON file (default: {DEFAULT_QUERIES_PATH})")
def info(queries: Optional[str]):
    """Show query set statistics."""
    # Use default path if not specified
    if queries is None:
        queries = DEFAULT_QUERIES_PATH
        if not Path(queries).exists():
            click.echo(click.style(f"✗ Queries file not found at default location: {queries}", fg="red"))
            sys.exit(1)
    query_set = QuerySet(queries)
    stats = query_set.get_statistics()

    click.echo("\nQuery Set Statistics")
    click.echo("=" * 40)
    click.echo(f"Total queries: {stats['total']}")
    click.echo(f"Verified queries: {stats['verified_count']}")

    click.echo("\nBy Difficulty:")
    for diff in ["simple", "moderate", "challenging", "nightmare", "unknown"]:
        count = stats["by_difficulty"].get(diff, 0)
        avg_len = stats.get("sql_length_by_difficulty", {}).get(diff, {}).get("avg_length", 0)
        if diff == "nightmare" and count == 0:
            continue
        if diff == "unknown" and count == 0:
            continue
        if avg_len > 0:
            click.echo(f"  {diff}: {count} (avg SQL length: {avg_len:.0f} chars)")
        else:
            click.echo(f"  {diff}: {count}")

    click.echo("\nBy Dialect:")
    for dialect, count in sorted(stats["by_dialect"].items()):
        click.echo(f"  {dialect}: {count}")

    # Count order-relevant queries
    # 1. Explicitly labeled as order-relevant (True)
    explicit_order_relevant = sum(1 for q in query_set if q.get("metadata", {}).get("order-relevant") is True)

    # 2. Deduced + labeled (True OR null with ORDER BY in SQL)
    deduced_order_relevant = 0
    for q in query_set:
        order_relevant_flag = q.get("metadata", {}).get("order-relevant")
        if order_relevant_flag is True:
            deduced_order_relevant += 1
        elif order_relevant_flag is None:
            sql = q.get("sql", "").upper()
            if "ORDER BY" in sql:
                deduced_order_relevant += 1

    click.echo(f"\nOrder-relevant queries (explicit): {explicit_order_relevant}")
    click.echo(f"Order-relevant queries (deduced + explicit): {deduced_order_relevant}")

    click.echo("\nTop Tags:")
    sorted_tags = sorted(stats["tags"].items(), key=lambda x: -x[1])[:10]
    for tag, count in sorted_tags:
        click.echo(f"  {tag}: {count}")


@cli.command("browse")
@click.option("--queries", "-q", default=None, type=click.Path(exists=True), help=f"Path to queries JSON file (default: {DEFAULT_QUERIES_PATH})")
@click.option("--database", "-db", default=None, type=click.Path(exists=True), help=f"Path to database file (default: {DEFAULT_DB_PATH})")
@click.option(
    "--split", "-s", type=click.Choice(["simple", "moderate", "challenging", "nightmare", "unknown"]), multiple=True, help="Filter by difficulty level"
)
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
def browse(
    queries: Optional[str],
    database: Optional[str],
    split: tuple,
    tags: tuple,
):
    """Interactively browse queries using fzf."""

    import sys
    import shutil
    import subprocess
    from pathlib import Path

    if shutil.which("fzf") is None:
        click.echo(
            click.style(
                "✗ fzf is required but not found. Install: https://github.com/junegunn/fzf",
                fg="red",
            )
        )
        sys.exit(1)

    rubikbench_path = shutil.which("rubikbench")
    if rubikbench_path is None:
        click.echo(click.style("✗ rubikbench executable not found on PATH", fg="red"))
        sys.exit(1)

    if queries is None:
        queries = DEFAULT_QUERIES_PATH
    queries = Path(queries).resolve()
    if not queries.exists():
        click.echo(click.style(f"✗ Queries file not found: {queries}", fg="red"))
        sys.exit(1)

    if database is None:
        database = Path(DEFAULT_DB_PATH)
    database = Path(database).resolve()
    if not database.exists():
        click.echo(
            click.style(
                f"✗ Database not found: {database}\n" "  Run 'rubikbench setup' first.",
                fg="red",
            )
        )
        sys.exit(1)

    query_set = QuerySet(str(queries))

    if split:
        query_set = query_set.filter(difficulty=list(split))
    if tags:
        query_set = query_set.filter(tags=list(tags))

    if len(query_set) == 0:
        click.echo(click.style("No queries match the filter criteria.", fg="yellow"))
        return

    fzf_lines = []

    for q in query_set:
        qid = q["id"]

        diff = q.get("metadata", {}).get("difficulty", "?")
        diff_short = {"simple": "S", "moderate": "M", "challenging": "C", "nightmare": "N", "unknown": "?"}.get(diff, "?")

        question = q.get("question", "").replace("\n", " ").strip()

        tags_str = " ".join(q.get("metadata", {}).get("query_tags", []))

        context = q.get("context", {})
        profile = context.get("user_profile", {})
        currency = profile.get("currency", "")

        region_words = " ".join(v if isinstance(v, str) else " ".join(v) for v in profile.get("region", {}).values())
        dept_words = " ".join(v if isinstance(v, str) else " ".join(v) for v in profile.get("department", {}).values())

        search_blob = " ".join(
            x
            for x in [
                qid,
                question,
                tags_str,
                currency,
                region_words,
                dept_words,
            ]
            if x
        )

        visible = f"[{qid}-{diff_short}] {question}"

        fzf_lines.append(f"{qid}\t{visible}\t{search_blob}")

    fzf_input = "\n".join(fzf_lines)

    preview_cmd = f"{rubikbench_path} exec {{1}} " f'-q "{queries}" -db "{database}" 2>&1'

    fzf_cmd = [
        "fzf",
        "--ansi",
        "--extended",  # word-based AND matching
        "--no-sort",
        "--layout=reverse",
        "--border",
        "--prompt=Search queries> ",
        f"--header=Total: {len(query_set)} | CTRL-E: Pager | CTRL-D: Copy Preview | TAB: Toggle Preview",
        "--delimiter=\t",
        "--with-nth=2",
        f"--preview={preview_cmd}",
        "--preview-window=right:50%:wrap:follow",
        "--bind=tab:toggle-preview",
        "--bind=ctrl-e:execute(echo {1} | " f'{rubikbench_path} exec {{1}} -q "{queries}" -db "{database}" | ${{PAGER:-less}})',
    ]

    # Clipboard helpers
    copy_tool = None
    notify_cmd = "true"  # Default to doing nothing if notification fails

    if shutil.which("pbcopy"):
        copy_tool = "pbcopy"
        # macOS native notification
        notify_cmd = 'osascript -e "display notification \\"Result copied to clipboard\\" with title \\"RubikBench\\""'
    elif shutil.which("xclip"):
        copy_tool = "xclip -selection clipboard"
        if shutil.which("notify-send"):
            notify_cmd = 'notify-send "RubikBench" "Result copied to clipboard"'

    copy_binding = ""
    if copy_tool:
        # execute-silent keeps the UI stable
        copy_binding = f"ctrl-d:execute-silent({preview_cmd} | {copy_tool} && {notify_cmd})"
        fzf_cmd.append(f"--bind={copy_binding}")

    try:
        subprocess.run(
            fzf_cmd,
            input=fzf_input,
            text=True,
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    cli()
