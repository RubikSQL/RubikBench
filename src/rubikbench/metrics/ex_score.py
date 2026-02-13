"""
Execution Accuracy (EX) Score.

Measures whether predicted SQL results exactly match ground truth results.
"""

from typing import List, Dict, Any, Tuple
from collections import Counter

from .utils import norm_val, norm_row


def _warn_large_result(label: str, count: int, query_id: str = "") -> None:
    if count > 1000:
        qid = f" ({query_id})" if query_id else ""
        print(f"\033[33m[WARN]{qid} {label} has {count} rows (>1000); evaluation may be slow or OOM. \033[0m")


def row_encode(row: Dict[str, Any], ndigits: int = 3) -> Tuple:
    """Convert a row to a sorted tuple for multiset comparison."""
    vals = [norm_val(v, ndigits) for v in row.values()]
    vals = sorted(vals, key=lambda x: (str(type(x)), str(x)))
    return tuple(vals)


def ex_ordered(pd: List[Dict[str, Any]], gt: List[Dict[str, Any]], ndigits: int = 3, dedup: bool = True) -> float:
    """
    Check if predicted rows exactly match ground truth rows with order preserved.

    This metric compares rows in order, treating duplicates as significant
    unless dedup is True.

    Args:
        pd: Predicted query results as list of dictionaries.
        gt: Ground truth query results as list of dictionaries.
        ndigits: Number of decimal places for float comparison.
        dedup: If True, drop duplicate rows before comparison.
               If False, preserve duplicates for stricter evaluation.

    Returns:
        1 if exact ordered match, 0 otherwise.
    """
    pd_res = [norm_row(row, ndigits) for row in (pd or [])]
    gt_res = [norm_row(row, ndigits) for row in (gt or [])]
    if dedup:
        pd_res = list(dict.fromkeys(pd_res))
        gt_res = list(dict.fromkeys(gt_res))
    return 1.0 if pd_res == gt_res else 0.0


def ex_unordered(pd: List[Dict[str, Any]], gt: List[Dict[str, Any]], ndigits: int = 3, fixed: bool = True, dedup: bool = True) -> float:
    """
    Check if predicted rows match ground truth rows regardless of order.

    This metric considers row multiplicity (multiset comparison) but ignores
    the order of rows and columns within each row.

    Args:
        pd: Predicted query results as list of dictionaries.
        gt: Ground truth query results as list of dictionaries.
        ndigits: Number of decimal places for float comparison.
        fixed: The BIRD's EX implementation has a bug where it does not handle
               duplicate rows correctly. Set this to False to mimic that behavior.
               (Default: True). Note: when dedup=True, this parameter has no effect
               since duplicates are already removed.
        dedup: If True, drop duplicate rows before comparison.
               If False, preserve duplicates (use 'fixed' to control multiset vs set).

    Returns:
        1 if match, 0 otherwise.
    """
    pd_res = [row_encode(r, ndigits) for r in (pd or [])]
    gt_res = [row_encode(r, ndigits) for r in (gt or [])]
    if dedup:
        return 1.0 if set(pd_res) == set(gt_res) else 0.0
    elif fixed:
        return 1.0 if Counter(pd_res) == Counter(gt_res) else 0.0
    else:
        return 1.0 if set(pd_res) == set(gt_res) else 0.0


def ex_match(pd: List[Dict[str, Any]], gt: List[Dict[str, Any]], ndigits: int = 3, ordered: bool = False, fixed: bool = True, dedup: bool = True) -> float:
    """
    Check if predicted rows match ground truth rows.

    Args:
        pd: Predicted query results as list of dictionaries.
        gt: Ground truth query results as list of dictionaries.
        ndigits: Number of decimal places for float comparison.
        ordered: If True, compare in order; if False, use multiset comparison.
        fixed: The BIRD's EX implementation has a bug where it does not handle
               duplicate rows correctly for unordered comparison.
               Set this to False to mimic that behavior.
               (Default: True). Note: when dedup=True, this parameter has no effect.
        dedup: If True, drop duplicate rows before comparison.
               If False, preserve duplicates for stricter evaluation.

    Returns:
        1 if exact match, 0 otherwise.

    Example:
        >>> pred = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        >>> gt = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        >>> ex_match(pred, gt)
        1
    """
    pd_rows = pd or []
    gt_rows = gt or []

    _warn_large_result("Prediction", len(pd_rows))
    _warn_large_result("Ground truth", len(gt_rows))

    if ordered:
        return ex_ordered(pd_rows, gt_rows, ndigits, dedup=dedup)
    else:
        return ex_unordered(pd_rows, gt_rows, ndigits, fixed=fixed, dedup=dedup)
