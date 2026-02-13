"""
Soft F-beta (SFb) Score.

A row-by-row soft matching metric that calculates element-level overlap
between predicted and ground truth results. Only the ordered variant is
supported; unordered soft matching is deprecated.
"""

from typing import List, Dict, Any, Tuple

from .utils import norm_val, norm_row


def _warn_large_result(label: str, count: int, query_id: str = "") -> None:
    if count > 1000:
        qid = f" ({query_id})" if query_id else ""
        print(f"\033[33m[WARN]{qid} {label} has {count} rows (>1000); evaluation may be slow or OOM. \033[0m")


def row_match(pd: Tuple[Any, ...], gt: Tuple[Any, ...]) -> Tuple[float, float, float]:
    """
    Calculate the matching metrics for a single row pair.

    Args:
        pd: Predicted row values as tuple.
        gt: Ground truth row values as tuple.

    Returns:
        Tuple of (match_percentage, pd_only_percentage, gt_only_percentage).
    """
    total_columns = len(gt)
    if total_columns == 0:
        return (1.0, 0.0, 0.0) if len(pd) == 0 else (0.0, 1.0, 0.0)

    matches = 0
    element_in_pd_only = 0
    element_in_gt_only = 0

    for pd_val in pd:
        if pd_val in gt:
            matches += 1
        else:
            element_in_pd_only += 1

    for gt_val in gt:
        if gt_val not in pd:
            element_in_gt_only += 1

    match_percentage = matches / total_columns
    pd_only_percentage = element_in_pd_only / total_columns
    gt_only_percentage = element_in_gt_only / total_columns

    return match_percentage, pd_only_percentage, gt_only_percentage


def fbeta_ordered(pd: List[Tuple[Any, ...]], gt: List[Tuple[Any, ...]], beta: float, dedup: bool = True) -> float:
    """
    Calculate F-beta score based on ordered soft row matching.

    Rows are matched by position (1st pred with 1st gt, etc.).

    Args:
        pd: Predicted results as list of tuples.
        gt: Ground truth results as list of tuples.
        beta: Beta parameter for F-beta calculation.
        dedup: If True, drop duplicate rows before scoring (BIRD-style behavior).
               If False, preserve duplicates for stricter evaluation.

    Returns:
        F-beta score in range [0, 1].
    """
    if not pd and not gt:
        return 1.0

    if dedup:
        # Drop duplicates while preserving order
        pd = list(dict.fromkeys(pd))
        gt = list(dict.fromkeys(gt))

    match_scores = []
    pd_only_scores = []
    gt_only_scores = []

    for i, gt_row in enumerate(gt):
        if i >= len(pd):
            match_scores.append(0)
            gt_only_scores.append(1)
            continue

        pred_row = pd[i]
        match_score, pd_only_score, gt_only_score = row_match(pred_row, gt_row)
        match_scores.append(match_score)
        pd_only_scores.append(pd_only_score)
        gt_only_scores.append(gt_only_score)

    for i in range(len(pd) - len(gt)):
        match_scores.append(0)
        pd_only_scores.append(1)
        gt_only_scores.append(0)

    tp = sum(match_scores)
    fp = sum(pd_only_scores)
    fn = sum(gt_only_scores)

    precision = tp / (tp + fp) if tp + fp > 0 else 0
    recall = tp / (tp + fn) if tp + fn > 0 else 0

    beta_sqr = beta * beta
    fbeta_score = (1 + beta_sqr) * precision * recall / (beta_sqr * precision + recall) if precision + recall > 0 else 0
    return fbeta_score


def soft_fbeta_score(
    pd: List[Dict[str, Any]], gt: List[Dict[str, Any]], beta: float = 1.0, ndigits: int = 3, ordered: bool = True, dedup: bool = True
) -> float:
    """
    Calculate soft F-beta score between predicted and ground truth results.

    This metric performs element-level comparison within rows, providing
    partial credit for partially correct results. Only ordered comparison
    is supported; unordered soft matching is deprecated and will raise.

    Args:
        pd: Predicted query results as list of dictionaries.
        gt: Ground truth query results as list of dictionaries.
        beta: Beta parameter for F-beta score (default 1.0 = F1).
        ndigits: Number of decimal places for float comparison.
        ordered: If True, match rows by position; if False, use best matching.
        dedup: If True, drop duplicate rows before scoring (BIRD-style behavior).
               If False, preserve duplicates for stricter evaluation.

    Returns:
        SF score in range [0, 1].

    Example:
        >>> pred = [{"a": 1, "b": 2}]
        >>> gt = [{"a": 1, "b": 3}]  # Partial match
        >>> soft_fbeta_score(pred, gt)  # Returns partial score
        0.5
    """
    pd_rows = pd or []
    gt_rows = gt or []

    _warn_large_result("Prediction", len(pd_rows))
    _warn_large_result("Ground truth", len(gt_rows))

    pd_norm = [norm_row(row, ndigits) for row in pd_rows]
    gt_norm = [norm_row(row, ndigits) for row in gt_rows]

    if not ordered:
        raise ValueError("unordered soft_fbeta_score is deprecated and unsupported")

    return fbeta_ordered(pd_norm, gt_norm, beta, dedup=dedup)
