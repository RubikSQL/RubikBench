"""Evaluation pipeline for RubikBench."""

import time
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime

from ahvn.utils.db import Database, escape_sql_binds
from ahvn.utils.basic.serialize_utils import load_json, save_json

from .queries import QuerySet
from .dialect import convert_sql, normalize_dialect
from .metrics import ex_match, bfbeta_score, soft_fbeta_score, has_order_by

_MAX_ROWS = 1000
_DEFAULT_TIMEOUT = 300


def normalize_submission_data(submission_data: Any) -> Dict[str, str]:
    """Validate and normalize a submission mapping."""
    if not isinstance(submission_data, dict):
        raise TypeError("Submission must be a JSON object mapping query IDs to SQL strings.")

    normalized: Dict[str, str] = dict()
    for query_id, sql in submission_data.items():
        if not isinstance(query_id, str) or not query_id.strip():
            raise TypeError("Submission keys must be non-empty query ID strings.")
        if sql is None:
            normalized[query_id] = ""
            continue
        if not isinstance(sql, str):
            raise TypeError(
                f"Submission value for {query_id!r} must be a SQL string or null, got {type(sql).__name__}."
            )
        normalized[query_id] = sql
    return normalized


def is_ordered(query: Dict[str, Any], unordered: bool = False) -> bool:
    if unordered:
        return False
    order_relevant = query.get("metadata", {}).get("order-relevant")
    if order_relevant is True:
        return True
    elif order_relevant is False:
        return False
    return has_order_by(query.get("sql", ""))


def get_all_sqls(query: Dict[str, Any]) -> List[str]:
    sqls = []
    if "sql" in query:
        sqls.append(query["sql"])
    for key in sorted(query.keys()):
        if key.startswith("sql.") and key[4:].isdigit():
            sqls.append(query[key])
    return sqls if sqls else [""]


@dataclass
class EvaluationResult:
    query_id: str
    success: bool
    pd_sql: str
    gt_sql: str
    pd_rows: Optional[List[Dict[str, Any]]] = None
    gt_rows: Optional[List[Dict[str, Any]]] = None
    pred_error: Optional[str] = None
    gt_error: Optional[str] = None
    ordered: bool = False
    exo: float = 0.0
    exu: float = 0.0
    sfo: float = 0.0
    sfu: Optional[float] = None
    bfo: float = 0.0
    bfu: float = 0.0
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationReport:
    N: Dict[str, int] = field(default_factory=dict)
    C: Dict[str, int] = field(default_factory=dict)
    compilable: Dict[str, float] = field(default_factory=dict)
    A: Dict[str, Dict[str, int]] = field(default_factory=dict)
    scores: Dict[str, Dict[str, float]] = field(default_factory=dict)
    gt_failures: List[Dict[str, str]] = field(default_factory=list)
    results: List[EvaluationResult] = field(default_factory=list)
    timestamp: str = ""
    config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        metric_keys = ["exo", "exu", "sfo", "bfo", "bfu"]
        if not self.N:
            self.N = {"overall": 0}
        if not self.C:
            self.C = {"overall": 0}
        if not self.compilable:
            self.compilable = {"overall": 0.0}
        if not self.A:
            self.A = {"overall": {k: 0 for k in metric_keys}}
        if not self.scores:
            self.scores = {"overall": {k: 0.0 for k in metric_keys}}

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["results"] = [r.to_dict() for r in self.results]
        return d

    def to_json(self, path: str, indent: int = 4):
        save_json(self.to_dict(), path, indent=indent)


class RubikBenchEvaluator:

    def __init__(
        self,
        db: Optional[Database] = None,
        queries: Optional[QuerySet] = None,
        bf_beta: float = 2.0,
        sf_beta: float = 1.0,
        ndigits: int = 3,
        src: str = "duckdb",
        tgt: str = "duckdb",
        unordered: bool = False,
        timeout: Optional[float] = _DEFAULT_TIMEOUT,
        db_resolver: Optional[Any] = None,
        dedup: bool = False,
    ):
        self.db = db
        self.queries = queries
        self.bf_beta = bf_beta
        self.sf_beta = sf_beta
        self.ndigits = ndigits
        self.src = normalize_dialect(src)
        self.tgt = normalize_dialect(tgt)
        self.unordered = unordered
        self.timeout = timeout
        self._db_resolver = db_resolver
        self.dedup = dedup

    def _get_db(self, query: Optional[Dict[str, Any]] = None) -> Database:
        if self._db_resolver is not None and query is not None:
            return self._db_resolver(query)
        if self.db is not None:
            return self.db
        raise RuntimeError("No database provided and db_resolver returned None")

    def exec_sql(self, sql: str, db: Optional[Database] = None) -> Dict[str, Any]:
        _db = db or self.db
        start = time.time()
        try:
            sql = escape_sql_binds(sql)
            result = _db.execute(sql, safe=True)
            elapsed = (time.time() - start) * 1000
            if hasattr(result, "error_type") and result.error_type:
                return {"error": str(result.error_type), "time_ms": elapsed}
            if not hasattr(result, "to_list"):
                return {"error": f"Unexpected result type: {type(result).__name__}", "time_ms": elapsed}
            return {"rows": result.to_list(), "time_ms": elapsed}
        except Exception as e:
            return {"error": str(e), "time_ms": (time.time() - start) * 1000}

    def convert_sql(self, sql: str) -> str:
        if self.src == self.tgt:
            return sql
        return convert_sql(sql, self.src, self.tgt)

    def evaluate_query(self, query_id: str, pd_sql: Optional[str] = None) -> EvaluationResult:
        if pd_sql is None:
            pd_sql = ""
        query = self.queries.get(query_id)
        if query is None:
            return EvaluationResult(query_id=query_id, success=False, pd_sql=pd_sql, gt_sql="", pred_error=f"Query ID not found: {query_id}")

        ordered = is_ordered(query, self.unordered)
        gt_sqls = get_all_sqls(query)

        try:
            db = self._get_db(query)
        except Exception as e:
            return EvaluationResult(
                query_id=query_id, success=False, pd_sql=pd_sql, gt_sql=gt_sqls[0], ordered=ordered, pred_error=f"DB resolution failed: {e}"
            )

        try:
            converted_pd_sql = self.convert_sql(pd_sql)
        except Exception as e:
            return EvaluationResult(
                query_id=query_id, success=False, pd_sql=pd_sql, gt_sql=gt_sqls[0], ordered=ordered, pred_error=f"SQL conversion failed: {e}"
            )

        pred_result = self.exec_sql(converted_pd_sql, db=db)
        if "error" in pred_result:
            return EvaluationResult(
                query_id=query_id,
                success=False,
                pd_sql=pd_sql,
                gt_sql=gt_sqls[0],
                ordered=ordered,
                pred_error=pred_result["error"],
                execution_time_ms=pred_result.get("time_ms", 0),
            )

        pd = pred_result["rows"]
        best_metrics = {}
        best_gt_sql = gt_sqls[0]
        best_gt_rows = None
        gt_error = None

        for gt_sql in gt_sqls:
            gt_result = self.exec_sql(gt_sql, db=db)
            if "error" in gt_result:
                gt_error = f"GT execution failed: {gt_result['error']}"
                continue

            gt = gt_result["rows"]
            try:
                bf_overflow = len(pd) > _MAX_ROWS or len(gt) > _MAX_ROWS

                exo = ex_match(pd, gt, ndigits=self.ndigits, ordered=True, dedup=self.dedup)
                exu = ex_match(pd, gt, ndigits=self.ndigits, ordered=False, dedup=self.dedup)

                if bf_overflow:
                    # BF falls back to SF with BF's beta
                    bfo = soft_fbeta_score(pd, gt, beta=self.bf_beta, ndigits=self.ndigits, ordered=True, dedup=self.dedup)
                    bfu = bfo
                    sfo = soft_fbeta_score(pd, gt, beta=self.sf_beta, ndigits=self.ndigits, ordered=True, dedup=self.dedup)
                else:
                    _t0 = time.time()
                    bfo = bfbeta_score(pd, gt, gt_sql, beta=self.bf_beta, ndigits=self.ndigits, ordered=True, dedup=self.dedup)
                    if time.time() - _t0 > 10.0:
                        bfu = soft_fbeta_score(pd, gt, beta=self.bf_beta, ndigits=self.ndigits, ordered=True, dedup=self.dedup)
                    else:
                        bfu = bfbeta_score(pd, gt, gt_sql, beta=self.bf_beta, ndigits=self.ndigits, ordered=False, dedup=self.dedup)
                    sfo = soft_fbeta_score(pd, gt, beta=self.sf_beta, ndigits=self.ndigits, ordered=True, dedup=self.dedup)

                if not best_metrics or exo > best_metrics.get("exo", 0):
                    best_metrics = {"exo": exo, "exu": exu, "bfo": bfo, "bfu": bfu, "sfo": sfo}
                    best_gt_sql = gt_sql
                    best_gt_rows = gt
            except Exception as e:
                gt_error = f"Metric calculation failed: {e}"
                continue

        if not best_metrics:
            return EvaluationResult(
                query_id=query_id,
                success=False,
                pd_sql=pd_sql,
                gt_sql=gt_sqls[0],
                ordered=ordered,
                pred_error=gt_error or "No valid ground truth SQL",
                gt_error=gt_error,
                execution_time_ms=pred_result.get("time_ms", 0),
            )

        return EvaluationResult(
            query_id=query_id,
            success=True,
            pd_sql=pd_sql,
            gt_sql=best_gt_sql,
            pd_rows=pd,
            gt_rows=best_gt_rows,
            ordered=ordered,
            gt_error=gt_error,
            exo=best_metrics["exo"],
            exu=best_metrics["exu"],
            bfo=best_metrics["bfo"],
            bfu=best_metrics["bfu"],
            sfo=best_metrics["sfo"],
            sfu=None,
            execution_time_ms=pred_result.get("time_ms", 0),
        )

    def evaluate_submission(
        self,
        submission: Union[str, Dict[str, str]],
        query_ids: Optional[List[str]] = None,
        difficulty: Optional[Union[str, List[str]]] = None,
        progress: bool = True,
    ) -> EvaluationReport:
        if isinstance(submission, str):
            submission_data = load_json(submission, strict=True)
        else:
            submission_data = submission
        submission_data = normalize_submission_data(submission_data)

        filtered_queries = self.queries
        if query_ids is not None:
            filtered_queries = filtered_queries.filter(ids=query_ids)
        if difficulty is not None:
            filtered_queries = filtered_queries.filter(difficulty=difficulty)

        results: List[EvaluationResult] = []
        query_list = list(filtered_queries)
        if progress:
            try:
                from tqdm import tqdm

                query_list = tqdm(query_list, desc="Evaluating")
            except ImportError:
                pass

        for query in query_list:
            query_id = query["id"]
            if query_id not in submission_data:
                continue

            pd_sql = submission_data.get(query_id) or ""
            if not pd_sql:
                result = EvaluationResult(
                    query_id=query_id,
                    success=False,
                    pd_sql=pd_sql,
                    gt_sql=query.get("sql", ""),
                    ordered=is_ordered(query, self.unordered),
                    pred_error="No prediction provided",
                )
            else:
                try:
                    result = self.evaluate_query(query_id, pd_sql)
                except Exception as e:
                    result = EvaluationResult(
                        query_id=query_id,
                        success=False,
                        pd_sql=pd_sql,
                        gt_sql=query.get("sql", ""),
                        ordered=is_ordered(query, self.unordered),
                        pred_error=f"Unexpected error: {e}",
                    )
            results.append(result)
        report = self.aggregate(results)
        report.config = {
            "bf_beta": self.bf_beta,
            "sf_beta": self.sf_beta,
            "ndigits": self.ndigits,
            "src": self.src,
            "unordered": self.unordered,
            "dedup": self.dedup,
            "query_ids": query_ids,
            "difficulty": difficulty,
        }
        return report

    def aggregate(self, results: List[EvaluationResult]) -> EvaluationReport:
        report = EvaluationReport(results=results, timestamp=datetime.now().isoformat())

        # Collect GT failures
        for r in results:
            if r.gt_error:
                report.gt_failures.append({"query_id": r.query_id, "error": r.gt_error})

        results_by_diff: Dict[str, List[EvaluationResult]] = {"overall": results}
        for r in results:
            query = self.queries.get(r.query_id)
            if query:
                diff = query.get("metadata", {}).get("difficulty", "unknown")
                results_by_diff.setdefault(diff, []).append(r)

        metric_keys = ["exo", "exu", "sfo", "bfo", "bfu"]
        for diff, diff_results in results_by_diff.items():
            diff_N = len(diff_results)
            diff_C = sum(1 for r in diff_results if r.success)
            report.N[diff] = diff_N
            report.C[diff] = diff_C
            report.compilable[diff] = diff_C / diff_N if diff_N > 0 else 0.0
            report.A[diff] = {k: 0 for k in metric_keys}
            report.scores[diff] = {k: 0.0 for k in metric_keys}
            for key in metric_keys:
                perfect = sum(1 for r in diff_results if r.success and getattr(r, key) is not None and getattr(r, key) >= 0.9999)
                report.A[diff][key] = perfect
                report.scores[diff][key] = perfect / diff_N if diff_N > 0 else 0.0
        return report
