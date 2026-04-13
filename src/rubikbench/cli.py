#!/usr/bin/env python3
"""RubikBench CLI — multi-dataset design following AgentHeaven patterns."""

import shutil
import subprocess
import sys
from typing import Annotated, Any, Dict, List, Optional, Tuple

import click
import typer
import typer.main as _typer_main

from ahvn.utils.basic.cli_utils import AliasedTyper, CLIOutput
from ahvn.utils.basic.color_utils import (
    color_debug,
    color_error,
    color_grey,
    color_info,
    color_magenta,
    color_success,
    color_warning,
)
from ahvn.utils.basic.file_utils import exists_file
from ahvn.utils.basic.path_utils import get_file_ext
from ahvn.utils.db import Database, escape_sql_binds, table_display

from rubikbench import QuerySet, RubikBenchEvaluator, __version__
from rubikbench.benchmarks import (
    BENCHMARK_NAMES,
    BENCHMARKS,
    benchmark_key,
    default_data_dir,
    default_database_path,
    default_queries_path,
    normalize_benchmark_name,
    resolve_db_path,
)
from rubikbench.dialect import get_supported_dialects

DEFAULT_DATASET = "RubikBench"
BANNER_WIDTH = 70
SUPPORTED_BENCHMARKS = BENCHMARK_NAMES

_PROVIDER_MAP = {
    ".duckdb": "duckdb",
    ".sqlite": "sqlite",
    ".sqlite3": "sqlite",
    ".db": "sqlite",
}


class BenchCLI:
    """Backend-agnostic RubikBench CLI."""

    def __init__(self):
        self.out = CLIOutput()

    @property
    def console(self) -> bool:
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    @staticmethod
    def _detect_provider(db_path: str) -> str:
        ext = get_file_ext(db_path).lower()
        return _PROVIDER_MAP.get(f".{ext}" if ext else "", "duckdb")

    def _banner(self, title: str) -> str:
        title_length = len(title)
        if title_length >= BANNER_WIDTH - 4:
            return color_warning(f"{'=' * 3} {title} {'=' * 3}", self.console)
        total_padding = BANNER_WIDTH - title_length
        left_padding = total_padding // 2
        right_padding = total_padding - left_padding
        return color_warning(f"{'=' * left_padding} {title} {'=' * right_padding}", self.console)

    def _format_score(self, score: Optional[float]) -> str:
        if score is None:
            return color_grey("N/A", self.console)
        if score >= 0.8:
            return color_success(f"{score:5.2%}", self.console)
        if score >= 0.6:
            return color_warning(f"{score:5.2%}", self.console)
        if score >= 0.2:
            return f"{score:5.2%}"
        return color_grey(f"{score:5.2%}", self.console)

    def _setup_hint(self, dataset: str) -> str:
        return f"rubikbench setup -B {dataset}"

    def _resolve_queries_path(self, dataset: str, queries: Optional[str]) -> str:
        queries_path = queries or default_queries_path(dataset)
        if exists_file(queries_path):
            return queries_path
        self.out.error(f"Queries file not found: {queries_path}")
        if queries is None:
            self.out.echo(f"  Run '{self._setup_hint(dataset)}' first.")
        sys.exit(1)

    def _resolve_default_database_path(self, dataset: str) -> str:
        database_path = default_database_path(dataset)
        if database_path is None:
            self.out.error(
                f"Dataset {dataset} has multiple databases. Provide --database, or use a queries file with benchmark/database metadata."
            )
            sys.exit(1)
        if exists_file(database_path):
            return database_path
        self.out.error(f"Database not found: {database_path}")
        self.out.echo(f"  Run '{self._setup_hint(dataset)}' first.")
        sys.exit(1)

    def _resolve_db(
        self,
        dataset: str,
        database: Optional[str],
        query_set: QuerySet,
    ) -> Tuple[Optional[Database], Any, str, Dict[str, Database]]:
        """Resolve database(s) for evaluation."""
        tgt_dialect = "duckdb"
        db_cache: Dict[str, Database] = dict()

        if database is not None:
            provider = self._detect_provider(database)
            tgt_dialect = provider
            try:
                db = Database(provider=provider, database=database)
            except Exception as e:
                self.out.error(f"Database error: {e}")
                sys.exit(1)
            self.out.echo(f"Database: {database}")
            return db, None, tgt_dialect, db_cache

        sample_query = next(iter(query_set), None)
        has_metadata = bool(sample_query and sample_query.get("benchmark") and sample_query.get("database"))

        if has_metadata:

            def _resolve(query):
                benchmark = query.get("benchmark", "")
                database_name = query.get("database", "")
                cache_key = f"{benchmark}:{database_name}"
                if cache_key not in db_cache:
                    db_path = resolve_db_path(benchmark, database_name)
                    if not exists_file(db_path):
                        raise FileNotFoundError(
                            f"Database not found: {db_path} (benchmark={benchmark!r}, database={database_name!r}). "
                            f"Run 'rubikbench setup -B {benchmark}' first."
                        )
                    provider = self._detect_provider(db_path)
                    db_cache[cache_key] = Database(provider=provider, database=db_path)
                return db_cache[cache_key]

            first_db_path = resolve_db_path(sample_query.get("benchmark", ""), sample_query.get("database", ""))
            if not exists_file(first_db_path):
                self.out.error(f"Database not found: {first_db_path}")
                self.out.echo(f"  Run 'rubikbench setup -B {sample_query.get('benchmark', dataset)}' first.")
                sys.exit(1)
            tgt_dialect = self._detect_provider(first_db_path)

            benchmarks_found = sorted({q.get("benchmark", "") for q in query_set if q.get("benchmark")})
            databases_found = {q.get("database", "") for q in query_set if q.get("database")}
            self.out.echo(
                f"Database: auto-resolve from query metadata ({len(databases_found)} databases across {', '.join(benchmarks_found)})"
            )
            return None, _resolve, tgt_dialect, db_cache

        default_db = self._resolve_default_database_path(dataset)
        provider = self._detect_provider(default_db)
        tgt_dialect = provider
        try:
            db = Database(provider=provider, database=default_db)
        except Exception as e:
            self.out.error(f"Database error: {e}")
            sys.exit(1)
        self.out.echo(f"Database: {default_db}")
        return db, None, tgt_dialect, db_cache

    def _resolve_exec_database(self, dataset: str, database: Optional[str], query_data: Optional[dict]) -> str:
        if database is not None:
            if exists_file(database):
                return database
            self.out.error(f"Database not found: {database}")
            sys.exit(1)

        if query_data and query_data.get("benchmark") and query_data.get("database"):
            db_path = resolve_db_path(query_data.get("benchmark", dataset), query_data.get("database", ""))
            if exists_file(db_path):
                return db_path
            self.out.error(f"Database not found: {db_path}")
            self.out.echo(f"  Run 'rubikbench setup -B {query_data.get('benchmark', dataset)}' first.")
            sys.exit(1)

        return self._resolve_default_database_path(dataset)

    def _execute_and_display(self, db: Database, sql: str) -> dict:
        try:
            result = db.execute(escape_sql_binds(sql))
            rows = result.to_list()
            if rows:
                self.out.echo(table_display(rows))
            else:
                self.out.echo(color_debug("  (empty result)", self.console))
            self.out.echo("")
            return {"success": True, "rows": rows}
        except Exception as e:
            self.out.error(str(e))
            self.out.echo("")
            return {"success": False, "error": str(e)}

    def _show_query_info(self, query_data: dict):
        c = self.console
        self.out.echo(self._banner("QUERY INFORMATION"))

        metadata = query_data.get("metadata", {})
        difficulty = metadata.get("difficulty", "N/A")

        self.out.echo(f"{color_info('Benchmark:', c)} {query_data.get('benchmark', 'N/A')}")
        self.out.echo(f"{color_info('Database:', c)} {query_data.get('database', 'N/A')}")
        self.out.echo(f"{color_info('Query ID:', c)} {color_magenta(query_data.get('id', 'N/A'), c)}")

        difficulty_colors = {
            "simple": color_success,
            "moderate": color_warning,
            "challenging": color_error,
        }
        diff_color = difficulty_colors.get(difficulty, lambda value, console=True: str(value))
        self.out.echo(f"{color_info('Difficulty:', c)} {diff_color(difficulty, c)}")
        self.out.echo(f"{color_info('Dialect:', c)} {query_data.get('dialect', 'N/A')}")

        order_relevant = metadata.get("order-relevant")
        if order_relevant is True:
            self.out.echo(f"{color_info('Order-Relevant:', c)} {color_warning('Yes', c)}")
        elif order_relevant is False:
            self.out.echo(f"{color_info('Order-Relevant:', c)} No")

        verified = metadata.get("verified", False)
        self.out.echo(f"{color_info('Verified:', c)} {color_success('Yes', c) if verified else 'No'}")

        tags = metadata.get("query_tags", [])
        if tags:
            self.out.echo(f"{color_info('Tags:', c)} {', '.join(tags)}")

        context = query_data.get("context", {})
        if context:
            self.out.echo(f"\n{color_info('Context:', c)}")
            query_time = context.get("query_time")
            if query_time:
                query_time_str = str(query_time)
                if len(query_time_str) == 6:
                    query_time_str = f"{query_time_str[:4]}-{query_time_str[4:]}"
                self.out.echo(f"  Query Time: {query_time_str}")

            profile = context.get("user_profile", {})
            if profile:
                for key in ("occupation", "caliber", "currency"):
                    value = profile.get(key, "")
                    if value:
                        self.out.echo(f"  {key.title()}: {value}")

                region = profile.get("region", {})
                if region:
                    region_parts = []
                    for key, value in region.items():
                        label = key.replace("_name_en", "").replace("_", " ").title()
                        region_parts.append(f"{label}: {', '.join(value) if isinstance(value, list) else value}")
                    if region_parts:
                        self.out.echo(f"  Region: {'; '.join(region_parts)}")

                department = profile.get("department", {})
                if department:
                    department_parts = []
                    for key, value in department.items():
                        label = key.replace("_name_en", "").replace("_", " ").title()
                        department_parts.append(f"{label}: {', '.join(value) if isinstance(value, list) else value}")
                    if department_parts:
                        self.out.echo(f"  Department: {'; '.join(department_parts)}")

                preferences = profile.get("preferences", [])
                if preferences:
                    self.out.echo(f"  Preferences: {', '.join(preferences)}")

        question = query_data.get("question", "")
        if question:
            import textwrap

            self.out.echo(f"\n{color_info('Question:', c)}")
            for line in textwrap.fill(question, width=68).split("\n"):
                self.out.echo(f"  {line}")

    def _print_report(self, report, bf_beta: float, sf_beta: float, output_file: Optional[str]):
        c = self.console
        self.out.echo(self._banner("EVALUATION RESULTS"))
        self.out.echo(f"\n{color_info('Total queries (N):', c)} {report.N['overall']}")
        self.out.echo(f"{color_info('Compilable (C):', c)} {report.C['overall']}")
        self.out.echo(f"{color_info('Compilable rate (C/N):', c)} {report.compilable['overall']:5.2%}")

        self.out.echo(f"\n{color_warning('Overall Scores', c)}")
        self.out.echo(
            table_display(
                [
                    {
                        "Metric": color_info("EX", c),
                        "Unordered": self._format_score(report.scores["overall"]["exu"]),
                        "Ordered": self._format_score(report.scores["overall"]["exo"]),
                    },
                    {
                        "Metric": color_info(f"SF (β={sf_beta:.1f})", c),
                        "Unordered": color_grey("N/A", c),
                        "Ordered": self._format_score(report.scores["overall"].get("sfo")),
                    },
                    {
                        "Metric": color_info(f"BF (β={bf_beta:.1f})", c),
                        "Unordered": self._format_score(report.scores["overall"]["bfu"]),
                        "Ordered": self._format_score(report.scores["overall"]["bfo"]),
                    },
                ]
            )
        )

        difficulties = [difficulty for difficulty in report.N if difficulty != "overall"]
        if difficulties:
            self.out.echo(f"\n{color_warning('Scores by Difficulty', c)}")
            diff_levels = [
                diff for diff in ["simple", "moderate", "challenging", "nightmare", "unknown"] if diff in difficulties
            ]
            metric_rows = []
            for label, key in [
                ("EX Unordered", "exu"),
                ("EX Ordered", "exo"),
                (f"SF (β={sf_beta:.1f}) Ordered", "sfo"),
                (f"BF (β={bf_beta:.1f}) Unordered", "bfu"),
                (f"BF (β={bf_beta:.1f}) Ordered", "bfo"),
            ]:
                row = {"Metric": color_info(label, c)}
                for diff in diff_levels:
                    column = color_error(diff, c) if diff == "nightmare" else diff
                    row[column] = self._format_score(report.scores[diff][key]) if diff in report.scores else "N/A"
                metric_rows.append(row)
            self.out.echo(table_display(metric_rows))

        if output_file:
            report.to_json(output_file)
            self.out.echo(f"\nDetailed results saved to: {output_file}")

        failed = [result for result in report.results if not result.success]
        if failed:
            self.out.echo(f"\nFailed queries ({len(failed)}, showing up to 10):")
            for result in failed[:10]:
                self.out.echo(f"  {result.query_id}: {result.pred_error}")

        if report.gt_failures:
            self.out.echo(f"\nGround truth failures ({len(report.gt_failures)}, showing up to 10):")
            for gt_failure in report.gt_failures[:10]:
                self.out.echo(f"  {gt_failure['query_id']}: {gt_failure['error']}")

    def do_setup(
        self,
        dataset: str,
        data: Optional[str],
        force: bool,
        remove_zip: bool,
        birdsql_no_corrections: bool = False,
    ):
        dataset = normalize_benchmark_name(dataset)
        data_path = data or default_data_dir(dataset)
        setup_fn = BENCHMARKS[benchmark_key(dataset)]
        kwargs = dict(force=force, remove_zip=remove_zip)
        if benchmark_key(dataset) == "birdsql":
            kwargs["no_corrections"] = birdsql_no_corrections
        setup_fn(data_path, **kwargs)

    def do_test(self, dataset: str = DEFAULT_DATASET, database: Optional[str] = None):
        dataset = normalize_benchmark_name(dataset)
        database_path = database or self._resolve_default_database_path(dataset)
        provider = self._detect_provider(database_path)
        self.out.echo(f"Testing database: {database_path}")
        self.out.echo(f"  Provider: {provider}")

        try:
            db = Database(provider=provider, database=database_path)
            result = db.execute("SELECT 1+1 AS result")
            rows = result.to_list()
            assert rows and rows[0]["result"] == 2, "Unexpected result"
            tables = db.db_tabs()
            self.out.success("Connection successful")
            self.out.echo(f"  Tables: {len(tables)}")
            db.close()
        except Exception as e:
            self.out.error(f"Test failed: {e}")
            sys.exit(1)

    def do_eval(
        self,
        submission: Optional[str],
        input_file: Optional[str] = None,
        dataset: str = DEFAULT_DATASET,
        queries: Optional[str] = None,
        database: Optional[str] = None,
        output_file: Optional[str] = None,
        ids: tuple = (),
        split: tuple = (),
        dialect: Optional[str] = None,
        bf_beta: float = 2.0,
        sf_beta: float = 1.0,
        dedup: bool = False,
        verbose: bool = False,
    ):
        dataset = normalize_benchmark_name(dataset)
        submission_file = input_file or submission
        if submission_file is None:
            self.out.error("Submission file required. Provide it as a positional argument or use --input-file/-in.")
            sys.exit(1)

        queries_path = self._resolve_queries_path(dataset, queries)
        query_set = QuerySet(queries_path)
        db, db_resolver, tgt_dialect, db_cache = self._resolve_db(dataset, database, query_set)

        self.out.echo(f"Dataset: {dataset}")
        self.out.echo(f"Evaluating submission: {submission_file}")
        self.out.echo(f"Queries file: {queries_path}")
        if dialect is None:
            dialect = tgt_dialect
            self.out.echo(f"SQL dialect: {dialect} (default, use --dialect to specify your submission SQL dialect)")
        else:
            self.out.echo(f"SQL dialect: {dialect}")
        self.out.echo(f"Dedup: {'enabled' if dedup else 'disabled'}")
        self.out.echo(f"Loaded {len(query_set)} queries")
        self.out.echo(f"Target dialect: {tgt_dialect}")

        evaluator = RubikBenchEvaluator(
            db=db,
            queries=query_set,
            bf_beta=bf_beta,
            sf_beta=sf_beta,
            ndigits=3,
            src=dialect,
            tgt=tgt_dialect,
            unordered=False,
            db_resolver=db_resolver,
            dedup=dedup,
        )

        query_ids = list(ids) if ids else None
        split_filter = list(split) if split else None

        try:
            report = evaluator.evaluate_submission(
                submission_file,
                query_ids=query_ids,
                difficulty=split_filter,
                progress=verbose,
            )
        except Exception as e:
            self.out.error(f"Evaluation failed: {e}")
            sys.exit(1)
        finally:
            if db is not None:
                db.close()
            for cached_db in db_cache.values():
                try:
                    cached_db.close()
                except Exception:
                    pass

        self._print_report(report, bf_beta, sf_beta, output_file)

    def do_exec(
        self,
        query_id: Optional[str] = None,
        sql: Optional[str] = None,
        dataset: str = DEFAULT_DATASET,
        queries: Optional[str] = None,
        database: Optional[str] = None,
        dialect: str = "duckdb",
        dedup: bool = False,
    ):
        dataset = normalize_benchmark_name(dataset)
        c = self.console

        if query_id is not None and sql is None:
            stripped = query_id.strip()
            sql_keywords = ("SELECT", "INSERT", "UPDATE", "DELETE", "WITH", "CREATE", "DROP", "ALTER")
            if " " in stripped or stripped.upper().startswith(sql_keywords):
                sql, query_id = stripped, None

        if sql is not None:
            sql = sql.strip()

        if query_id is None and sql is None:
            self.out.error("At least one of QUERY_ID or SQL must be specified.")
            sys.exit(1)

        query_set = None
        query_data = None
        if query_id is not None:
            queries_path = self._resolve_queries_path(dataset, queries)
            query_set = QuerySet(queries_path)
            query_data = query_set.get(query_id)
            if query_data is None:
                self.out.error(f"Query ID not found: {query_id}")
                sys.exit(1)

        database_path = self._resolve_exec_database(dataset, database, query_data)
        provider = self._detect_provider(database_path)
        try:
            db = Database(provider=provider, database=database_path)
        except Exception as e:
            self.out.error(f"Database error: {e}")
            sys.exit(1)

        self.out.echo(f"Dataset: {dataset}")
        self.out.echo(f"Database: {database_path}")

        if sql is not None and query_id is None:
            self.out.echo(self._banner("SQL"))
            self.out.echo(sql)
            self._execute_and_display(db, sql)
            db.close()
            return

        self._show_query_info(query_data)
        self.out.echo("")
        gt_sql = query_data.get("sql", "")

        self.out.echo(self._banner("GROUND TRUTH SQL"))
        self.out.echo(gt_sql)
        self.out.echo("")
        self.out.echo(self._banner("GROUND TRUTH TABLE"))
        self._execute_and_display(db, gt_sql)

        if sql is None:
            db.close()
            return

        self.out.echo(self._banner("PREDICTED SQL"))
        self.out.echo(sql)
        self.out.echo("")
        self.out.echo(self._banner("PREDICTED TABLE"))
        self._execute_and_display(db, sql)

        evaluator = RubikBenchEvaluator(db=db, queries=query_set, ndigits=3, src=dialect, unordered=False, dedup=dedup)
        result = evaluator.evaluate_query(query_id, sql)
        db.close()

        self.out.echo(self._banner("EVALUATION SCORES"))
        if result.success:
            self.out.echo(
                table_display(
                    [
                        {
                            "Metric": color_info("EX", c),
                            "Ordered": self._format_score(result.exo),
                            "Unordered": self._format_score(result.exu),
                        },
                        {
                            "Metric": color_info("BF", c),
                            "Ordered": self._format_score(result.bfo),
                            "Unordered": self._format_score(result.bfu),
                        },
                        {
                            "Metric": color_info("SF", c),
                            "Ordered": self._format_score(result.sfo),
                            "Unordered": color_grey("N/A", c),
                        },
                    ]
                )
            )
        else:
            self.out.error(f"Error: {result.pred_error}")

    def do_template(
        self,
        dataset: str = DEFAULT_DATASET,
        queries: Optional[str] = None,
        output_file: str = "submission_template.json",
        ids: tuple = (),
        split: tuple = (),
        tags: tuple = (),
        sql: str = "",
    ):
        dataset = normalize_benchmark_name(dataset)
        queries_path = self._resolve_queries_path(dataset, queries)
        query_set = QuerySet(queries_path)
        if ids:
            query_set = query_set.filter(ids=list(ids))
        if split:
            query_set = query_set.filter(difficulty=list(split))
        if tags:
            query_set = query_set.filter(tags=list(tags))

        query_set.create_template(output_file, placeholder=sql)

        self.out.echo(f"Dataset: {dataset}")
        self.out.echo(f"Generated submission template: {output_file}")
        self.out.echo(f"Total queries: {len(query_set)}")
        if split:
            self.out.echo(f"Difficulty filter: {', '.join(split)}")
        if tags:
            self.out.echo(f"Tag filter: {', '.join(tags)}")
        if ids:
            self.out.echo(f"ID filter: {len(ids)} IDs specified")
        if sql:
            self.out.echo(f"Custom SQL placeholder: {sql}")

    def do_info(self, dataset: str = DEFAULT_DATASET, queries: Optional[str] = None):
        dataset = normalize_benchmark_name(dataset)
        queries_path = self._resolve_queries_path(dataset, queries)
        query_set = QuerySet(queries_path)
        stats = query_set.get_statistics()

        self.out.echo(f"\nDataset: {dataset}")
        self.out.echo("Query Set Statistics")
        self.out.echo("=" * 40)
        self.out.echo(f"Total queries: {stats['total']}")
        self.out.echo(f"Verified queries: {stats['verified_count']}")

        self.out.echo("\nBy Difficulty:")
        for diff in ["simple", "moderate", "challenging", "nightmare", "unknown"]:
            count = stats["by_difficulty"].get(diff, 0)
            avg_len = stats.get("sql_length_by_difficulty", {}).get(diff, {}).get("avg_length", 0)
            if diff in ("nightmare", "unknown") and count == 0:
                continue
            if avg_len > 0:
                self.out.echo(f"  {diff}: {count} (avg SQL length: {avg_len:.0f} chars)")
            else:
                self.out.echo(f"  {diff}: {count}")

        self.out.echo("\nBy Dialect:")
        for dialect_name, count in sorted(stats["by_dialect"].items()):
            self.out.echo(f"  {dialect_name}: {count}")

        explicit_order_relevant = sum(1 for query in query_set if query.get("metadata", {}).get("order-relevant") is True)
        deduced_order_relevant = 0
        for query in query_set:
            order_flag = query.get("metadata", {}).get("order-relevant")
            if order_flag is True:
                deduced_order_relevant += 1
            elif order_flag is None and "ORDER BY" in query.get("sql", "").upper():
                deduced_order_relevant += 1

        self.out.echo(f"\nOrder-relevant queries (explicit): {explicit_order_relevant}")
        self.out.echo(f"Order-relevant queries (deduced + explicit): {deduced_order_relevant}")

        self.out.echo("\nTop Tags:")
        for tag, count in sorted(stats["tags"].items(), key=lambda item: -item[1])[:10]:
            self.out.echo(f"  {tag}: {count}")

    def do_browse(
        self,
        dataset: str = DEFAULT_DATASET,
        queries: Optional[str] = None,
        database: Optional[str] = None,
        split: tuple = (),
        tags: tuple = (),
    ):
        dataset = normalize_benchmark_name(dataset)

        if shutil.which("fzf") is None:
            self.out.error("fzf is required but not found. Install: https://github.com/junegunn/fzf")
            sys.exit(1)

        rubikbench_path = shutil.which("rubikbench")
        if rubikbench_path is None:
            self.out.error("rubikbench executable not found on PATH")
            sys.exit(1)

        queries_path = self._resolve_queries_path(dataset, queries)
        database_path = None
        if database is not None:
            if not exists_file(database):
                self.out.error(f"Database not found: {database}")
                sys.exit(1)
            database_path = database

        query_set = QuerySet(queries_path)
        if split:
            query_set = query_set.filter(difficulty=list(split))
        if tags:
            query_set = query_set.filter(tags=list(tags))

        if len(query_set) == 0:
            self.out.warning("No queries match the filter criteria.")
            return

        fzf_lines = []
        for query in query_set:
            query_id = query["id"]
            difficulty = query.get("metadata", {}).get("difficulty", "?")
            difficulty_short = {
                "simple": "S",
                "moderate": "M",
                "challenging": "C",
                "nightmare": "N",
                "unknown": "?",
            }.get(difficulty, "?")
            question = query.get("question", "").replace("\n", " ").strip()
            tags_str = " ".join(query.get("metadata", {}).get("query_tags", []))
            context = query.get("context", {})
            profile = context.get("user_profile", {})
            currency = profile.get("currency", "")
            region_words = " ".join(
                value if isinstance(value, str) else " ".join(value) for value in profile.get("region", {}).values()
            )
            department_words = " ".join(
                value if isinstance(value, str) else " ".join(value) for value in profile.get("department", {}).values()
            )
            search_blob = " ".join(item for item in [query_id, question, tags_str, currency, region_words, department_words] if item)
            visible = f"[{query_id}-{difficulty_short}] {question}"
            fzf_lines.append(f"{query_id}\t{visible}\t{search_blob}")

        preview_parts = [f'"{rubikbench_path}"', "exec", "{1}", "-B", dataset, "-q", f'"{queries_path}"']
        if database_path:
            preview_parts.extend(["-db", f'"{database_path}"'])
        preview_core = " ".join(preview_parts)
        preview_cmd = f"{preview_core} 2>&1"
        default_pager = "more" if sys.platform.startswith("win") else "less"
        pager_cmd = f"${{PAGER:-{default_pager}}}"

        fzf_cmd = [
            "fzf",
            "--ansi",
            "--extended",
            "--no-sort",
            "--layout=reverse",
            "--border",
            "--prompt=Search queries> ",
            f"--header=Dataset: {dataset} | Total: {len(query_set)} | CTRL-E: Pager | CTRL-D: Copy Preview | TAB: Toggle Preview",
            "--delimiter=\t",
            "--with-nth=2",
            f"--preview={preview_cmd}",
            "--preview-window=right:50%:wrap:follow",
            "--bind=tab:toggle-preview",
            f"--bind=ctrl-e:execute({preview_cmd} | {pager_cmd})",
        ]

        copy_tool = None
        notify_cmd = "true"
        if shutil.which("pbcopy"):
            copy_tool = "pbcopy"
            notify_cmd = 'osascript -e "display notification \\"Result copied to clipboard\\" with title \\"RubikBench\\""'
        elif shutil.which("xclip"):
            copy_tool = "xclip -selection clipboard"
            if shutil.which("notify-send"):
                notify_cmd = 'notify-send "RubikBench" "Result copied to clipboard"'
        elif shutil.which("clip"):
            copy_tool = "clip"

        if copy_tool:
            fzf_cmd.append(f"--bind=ctrl-d:execute-silent({preview_cmd} | {copy_tool} && {notify_cmd})")

        try:
            subprocess.run(fzf_cmd, input="\n".join(fzf_lines), text=True)
        except KeyboardInterrupt:
            pass

    def register_click(self, parent):
        ref = self
        dataset_choice = click.Choice(SUPPORTED_BENCHMARKS, case_sensitive=False)

        @parent.command()
        @click.option(
            "--dataset",
            "--benchmark",
            "-B",
            "dataset",
            type=dataset_choice,
            default=DEFAULT_DATASET,
            show_default=True,
            help="Dataset to set up.",
        )
        @click.option("--data", "-d", default=None, help="Directory where dataset files should be stored.")
        @click.option("--force", "-f", is_flag=True, help="Force re-download even if files exist.")
        @click.option("--remove-zip", "-rm", is_flag=True, help="Remove downloaded archive after extraction.")
        @click.option("--birdsql-no-corrections", is_flag=True, default=False, help="BirdSQL: skip applying official corrections.")
        def setup(dataset, data, force, remove_zip, birdsql_no_corrections):
            """Set up benchmark datasets."""
            ref.do_setup(dataset, data, force, remove_zip, birdsql_no_corrections)

        @parent.command()
        @click.option(
            "--dataset",
            "--benchmark",
            "-B",
            "dataset",
            type=dataset_choice,
            default=DEFAULT_DATASET,
            show_default=True,
            help="Dataset whose default database should be used when --database is omitted.",
        )
        @click.option("--database", "-db", default=None, type=click.Path(exists=True), help="Database file to test.")
        def test(dataset, database):
            """Test database connectivity."""
            ref.do_test(dataset, database)

        @parent.command("eval")
        @click.argument("submission", required=False, type=click.Path(exists=True))
        @click.option("--input-file", "-in", type=click.Path(exists=True), help="Submission file (alternative to the positional argument).")
        @click.option(
            "--dataset",
            "--benchmark",
            "-B",
            "dataset",
            type=dataset_choice,
            default=DEFAULT_DATASET,
            show_default=True,
            help="Dataset whose default queries/database paths should be used when explicit paths are omitted.",
        )
        @click.option("--queries", "-q", default=None, type=click.Path(exists=True), help="Queries JSON file.")
        @click.option(
            "--database",
            "-db",
            default=None,
            type=click.Path(exists=True),
            help="Database file. Multi-database datasets auto-resolve from query metadata when possible.",
        )
        @click.option("--output-file", "-out", default=None, type=click.Path(), help="Output path for detailed JSON results.")
        @click.option("--ids", "-i", multiple=True, help="Specific query IDs to evaluate.")
        @click.option(
            "--split",
            "-s",
            type=click.Choice(["simple", "moderate", "challenging", "nightmare", "unknown"]),
            multiple=True,
            help="Filter by difficulty level.",
        )
        @click.option("--dialect", default=None, help=f"Submission SQL dialect ({', '.join(get_supported_dialects())}).")
        @click.option("--bf-beta", "-bfb", default=2.0, type=float, help="Beta for BF score.")
        @click.option("--sf-beta", "-sfb", default=1.0, type=float, help="Beta for SF score.")
        @click.option("--dedup/--no-dedup", default=False, help="Drop duplicate rows before scoring.")
        @click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose output and progress bar.")
        def evaluate(submission, input_file, dataset, queries, database, output_file, ids, split, dialect, bf_beta, sf_beta, dedup, verbose):
            """Evaluate a SQL submission against the selected dataset."""
            ref.do_eval(submission, input_file, dataset, queries, database, output_file, ids, split, dialect, bf_beta, sf_beta, dedup, verbose)

        @parent.command("exec")
        @click.argument("query_id", default=None, required=False)
        @click.argument("sql", default=None, required=False)
        @click.option(
            "--dataset",
            "--benchmark",
            "-B",
            "dataset",
            type=dataset_choice,
            default=DEFAULT_DATASET,
            show_default=True,
            help="Dataset whose default queries/database paths should be used when explicit paths are omitted.",
        )
        @click.option("--queries", "-q", default=None, type=click.Path(exists=True), help="Queries JSON file.")
        @click.option(
            "--database",
            "-db",
            default=None,
            type=click.Path(exists=True),
            help="Database file. When omitted, the CLI auto-resolves from query metadata or dataset defaults.",
        )
        @click.option("--dialect", default="duckdb", help="Submission SQL dialect.")
        @click.option("--dedup/--no-dedup", default=False, help="Drop duplicate rows before scoring.")
        def exec_cmd(query_id, sql, dataset, queries, database, dialect, dedup):
            """Execute SQL or inspect/evaluate a single query."""
            ref.do_exec(query_id, sql, dataset, queries, database, dialect, dedup)

        @parent.command("template")
        @click.option(
            "--dataset",
            "--benchmark",
            "-B",
            "dataset",
            type=dataset_choice,
            default=DEFAULT_DATASET,
            show_default=True,
            help="Dataset whose default queries file should be used when --queries is omitted.",
        )
        @click.option("--queries", "-q", default=None, type=click.Path(exists=True), help="Queries JSON file.")
        @click.option("--output-file", "-out", default="submission_template.json", help="Output path for the generated template.")
        @click.option("--ids", "-i", multiple=True, help="Specific query IDs to include.")
        @click.option(
            "--split",
            "-s",
            type=click.Choice(["simple", "moderate", "challenging", "nightmare", "unknown"]),
            multiple=True,
            help="Filter by difficulty level.",
        )
        @click.option("--tags", "-t", multiple=True, help="Filter by query tags (any tag matches).")
        @click.option("--sql", default="", help="Custom default SQL placeholder.")
        def template(dataset, queries, output_file, ids, split, tags, sql):
            """Generate a submission template JSON."""
            ref.do_template(dataset, queries, output_file, ids, split, tags, sql)

        @parent.command("info")
        @click.option(
            "--dataset",
            "--benchmark",
            "-B",
            "dataset",
            type=dataset_choice,
            default=DEFAULT_DATASET,
            show_default=True,
            help="Dataset whose default queries file should be used when --queries is omitted.",
        )
        @click.option("--queries", "-q", default=None, type=click.Path(exists=True), help="Queries JSON file.")
        def info(dataset, queries):
            """Show query set statistics."""
            ref.do_info(dataset, queries)

        @parent.command("browse")
        @click.option(
            "--dataset",
            "--benchmark",
            "-B",
            "dataset",
            type=dataset_choice,
            default=DEFAULT_DATASET,
            show_default=True,
            help="Dataset whose default queries file should be used when --queries is omitted.",
        )
        @click.option("--queries", "-q", default=None, type=click.Path(exists=True), help="Queries JSON file.")
        @click.option(
            "--database",
            "-db",
            default=None,
            type=click.Path(exists=True),
            help="Optional database file override. Usually unnecessary for metadata-backed multi-database datasets.",
        )
        @click.option(
            "--split",
            "-s",
            type=click.Choice(["simple", "moderate", "challenging", "nightmare", "unknown"]),
            multiple=True,
            help="Filter by difficulty level.",
        )
        @click.option("--tags", "-t", multiple=True, help="Filter by query tags.")
        def browse(dataset, queries, database, split, tags):
            """Interactively browse queries using fzf."""
            ref.do_browse(dataset, queries, database, split, tags)

    def register_typer(self, parent):
        """Register all subcommands on a Typer app."""
        ref = self
        benchmark_names = [n.lower() for n in SUPPORTED_BENCHMARKS]
        difficulty_names = ["simple", "moderate", "challenging", "nightmare", "unknown"]

        @parent.command("setup", help="Set up benchmark datasets.")
        def setup(
            dataset: Annotated[str, typer.Option("--dataset", "--benchmark", "-B", help="Dataset to set up.")] = DEFAULT_DATASET,
            data: Annotated[Optional[str], typer.Option("--data", "-d", help="Directory where dataset files should be stored.")] = None,
            force: Annotated[bool, typer.Option("--force", "-f", help="Force re-download even if files exist.")] = False,
            remove_zip: Annotated[bool, typer.Option("--remove-zip", "-rm", help="Remove downloaded archive after extraction.")] = False,
            birdsql_no_corrections: Annotated[bool, typer.Option("--birdsql-no-corrections", help="BirdSQL: skip applying official corrections.")] = False,
        ):
            if dataset.lower() not in benchmark_names:
                ref.out.error(f"Unknown benchmark: {dataset!r}. Choose from: {', '.join(SUPPORTED_BENCHMARKS)}")
                raise SystemExit(1)
            ref.do_setup(dataset, data, force, remove_zip, birdsql_no_corrections)

        @parent.command("test", help="Test database connectivity.")
        def test(
            dataset: Annotated[str, typer.Option("--dataset", "--benchmark", "-B", help="Dataset whose default database to test.")] = DEFAULT_DATASET,
            database: Annotated[Optional[str], typer.Option("--database", "-db", help="Database file to test.")] = None,
        ):
            ref.do_test(dataset, database)

        @parent.command("eval", help="Evaluate a SQL submission against the selected dataset.")
        def evaluate(
            submission: Annotated[Optional[str], typer.Argument(help="Submission JSON file.")] = None,
            input_file: Annotated[Optional[str], typer.Option("--input-file", "-in", help="Submission file (alternative to the positional argument).")] = None,
            dataset: Annotated[str, typer.Option("--dataset", "--benchmark", "-B", help="Dataset to evaluate against.")] = DEFAULT_DATASET,
            queries: Annotated[Optional[str], typer.Option("--queries", "-q", help="Queries JSON file.")] = None,
            database: Annotated[Optional[str], typer.Option("--database", "-db", help="Database file.")] = None,
            output_file: Annotated[Optional[str], typer.Option("--output-file", "-out", help="Output path for detailed JSON results.")] = None,
            ids: Annotated[Optional[List[str]], typer.Option("--ids", "-i", help="Specific query IDs to evaluate.")] = None,
            split: Annotated[Optional[List[str]], typer.Option("--split", "-s", help="Filter by difficulty level.")] = None,
            dialect: Annotated[Optional[str], typer.Option("--dialect", help=f"Submission SQL dialect ({', '.join(get_supported_dialects())}).")] = None,
            bf_beta: Annotated[float, typer.Option("--bf-beta", "-bfb", help="Beta for BF score.")] = 2.0,
            sf_beta: Annotated[float, typer.Option("--sf-beta", "-sfb", help="Beta for SF score.")] = 1.0,
            dedup: Annotated[bool, typer.Option("--dedup/--no-dedup", help="Drop duplicate rows before scoring.")] = False,
            verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output and progress bar.")] = False,
        ):
            ref.do_eval(
                submission, input_file, dataset, queries, database, output_file,
                tuple(ids) if ids else (), tuple(split) if split else (),
                dialect, bf_beta, sf_beta, dedup, verbose,
            )

        @parent.command("exec", help="Execute SQL or inspect/evaluate a single query.")
        def exec_cmd(
            query_id: Annotated[Optional[str], typer.Argument(help="Query ID to inspect.")] = None,
            sql: Annotated[Optional[str], typer.Argument(help="SQL to execute or compare.")] = None,
            dataset: Annotated[str, typer.Option("--dataset", "--benchmark", "-B", help="Dataset.")] = DEFAULT_DATASET,
            queries: Annotated[Optional[str], typer.Option("--queries", "-q", help="Queries JSON file.")] = None,
            database: Annotated[Optional[str], typer.Option("--database", "-db", help="Database file.")] = None,
            dialect: Annotated[str, typer.Option("--dialect", help="Submission SQL dialect.")] = "duckdb",
            dedup: Annotated[bool, typer.Option("--dedup/--no-dedup", help="Drop duplicate rows before scoring.")] = False,
        ):
            ref.do_exec(query_id, sql, dataset, queries, database, dialect, dedup)

        @parent.command("template", help="Generate a submission template JSON.")
        def template(
            dataset: Annotated[str, typer.Option("--dataset", "--benchmark", "-B", help="Dataset.")] = DEFAULT_DATASET,
            queries: Annotated[Optional[str], typer.Option("--queries", "-q", help="Queries JSON file.")] = None,
            output_file: Annotated[str, typer.Option("--output-file", "-out", help="Output path for the generated template.")] = "submission_template.json",
            ids: Annotated[Optional[List[str]], typer.Option("--ids", "-i", help="Specific query IDs to include.")] = None,
            split: Annotated[Optional[List[str]], typer.Option("--split", "-s", help="Filter by difficulty level.")] = None,
            tags: Annotated[Optional[List[str]], typer.Option("--tags", "-t", help="Filter by query tags.")] = None,
            sql: Annotated[str, typer.Option("--sql", help="Custom default SQL placeholder.")] = "",
        ):
            ref.do_template(
                dataset, queries, output_file,
                tuple(ids) if ids else (), tuple(split) if split else (),
                tuple(tags) if tags else (), sql,
            )

        @parent.command("info", help="Show query set statistics.")
        def info(
            dataset: Annotated[str, typer.Option("--dataset", "--benchmark", "-B", help="Dataset.")] = DEFAULT_DATASET,
            queries: Annotated[Optional[str], typer.Option("--queries", "-q", help="Queries JSON file.")] = None,
        ):
            ref.do_info(dataset, queries)

        @parent.command("browse", help="Interactively browse queries using fzf.")
        def browse(
            dataset: Annotated[str, typer.Option("--dataset", "--benchmark", "-B", help="Dataset.")] = DEFAULT_DATASET,
            queries: Annotated[Optional[str], typer.Option("--queries", "-q", help="Queries JSON file.")] = None,
            database: Annotated[Optional[str], typer.Option("--database", "-db", help="Optional database file override.")] = None,
            split: Annotated[Optional[List[str]], typer.Option("--split", "-s", help="Filter by difficulty level.")] = None,
            tags: Annotated[Optional[List[str]], typer.Option("--tags", "-t", help="Filter by query tags.")] = None,
        ):
            ref.do_browse(dataset, queries, database, tuple(split) if split else (), tuple(tags) if tags else ())

    def register(self, parent, backend: str = "typer"):
        if backend == "typer":
            return self.register_typer(parent)
        if backend == "click":
            return self.register_click(parent)
        raise ValueError(f"Unsupported backend: {backend!r}")


# ── Typer app (default) ──────────────────────────────────────────────────────

app = AliasedTyper(
    name="rubikbench",
    help="RubikBench: Enterprise-scale NL2SQL Benchmark.",
    no_args_is_help=True,
    context_settings={
        "help_option_names": ["-h", "--help"],
        "max_content_width": 120,
    },
    invoke_without_command=True,
    add_completion=True,
)


def _version_callback(value: bool):
    if value:
        print(f"rubikbench {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-V", callback=_version_callback, is_eager=True, help="Show version and exit."),
    ] = None,
):
    """RubikBench: Enterprise-scale NL2SQL Benchmark."""
    pass


_bench_cli = BenchCLI()
_bench_cli.register_typer(app)

# Click-compatible entry point (used by setuptools console_scripts)
cli = _typer_main.get_command(app)


if __name__ == "__main__":
    app()
