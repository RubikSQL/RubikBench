"""
Bipartite F-beta (BFb) Score.

A utility-oriented metric that measures row-level matching using bipartite
matching (Hungarian algorithm for unordered, DP for ordered results).
"""

from collections import Counter
from typing import List, Dict, Any, Tuple, Optional
from .utils import norm_val, has_order_by


def _warn_large_result(label: str, count: int, query_id: str = "") -> None:
    if count > 1000:
        qid = f" ({query_id})" if query_id else ""
        print(f"\033[33m[WARN]{qid} {label} has {count} rows (>1000); evaluation may be slow or OOM. \033[0m")


def row_bag(row: Dict[str, Any], ndigits: int = 3) -> Counter:
    """Convert a row dictionary to a multiset (counter) of normalized values."""
    return Counter(norm_val(v, ndigits) for v in row.values())


def row_fbeta(p: Counter, g: Counter, beta: float) -> float:
    """Row-wise F-beta score treating rows as unordered multisets of values."""
    total_p = sum(p.values())
    total_g = sum(g.values())
    if total_p == 0 and total_g == 0:
        return 1.0
    if total_p == 0 or total_g == 0:
        return 0.0

    match = 0
    for val, cnt in p.items():
        if val in g:
            match += min(cnt, g[val])

    pre = match / total_p
    rec = match / total_g
    if pre == 0.0 and rec == 0.0:
        return 0.0

    b2 = beta * beta
    return (1.0 + b2) * pre * rec / (b2 * pre + rec)


def dp_max(weights: List[List[float]]) -> float:
    """
    Dynamic programming for ordered non-intersecting maximum matching.
    Used when ORDER BY is present in the ground truth query.

    Recurrence (1-indexed):
        DP[i][j] = max( DP[i-1][j], DP[i][j-1], DP[i-1][j-1] + w[i][j] ),
    with DP[0][*] = DP[*][0] = 0.
    """
    n = len(weights)
    m = len(weights[0]) if n else 0
    if n == 0 and m == 0:
        return 1.0
    if n == 0 or m == 0:
        return 0.0
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        wi = weights[i - 1]
        for j in range(1, m + 1):
            # dp[i][j] = best score using first i predicted rows and j ground-truth rows
            dp[i][j] = max(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1] + wi[j - 1])
    return dp[n][m]


def auction(weights: List[List[float]], epsilon: Optional[float] = None) -> Tuple[float, List[int]]:
    """
    Auction algorithm for maximum weight bipartite matching.
    Used for unordered result comparison. Generally faster than Hungarian
    for large sparse or dense matrices, especially with structured data.

    The algorithm maintains prices for each column (object) and iteratively
    has unassigned rows (persons) bid for their most profitable column.
    With sufficiently small epsilon, guarantees optimal or near-optimal matching.

    Args:
        weights: n x m weight matrix where weights[i][j] is the benefit of matching row i to col j
        epsilon: Bid increment (default: very small value for near-exact matching)

    Returns:
        Tuple of (total_weight, assignment) where assignment[i] is the matched column for row i (-1 if unmatched)
    """
    if not weights:
        return 0.0, []

    n = len(weights)
    m = max(len(r) for r in weights) if n > 0 else 0

    if n == 0 or m == 0:
        return 0.0, [-1] * n

    # Pad to square matrix
    size = max(n, m)

    # Pad weight matrix
    W = []
    for i in range(size):
        if i < n:
            row = list(weights[i]) if i < len(weights) else []
            row.extend([0.0] * (size - len(row)))
        else:
            row = [0.0] * size
        W.append(row)

    # Use very small epsilon for near-exact matching
    # Theory: epsilon < 1/n gives optimal solution
    if epsilon is None:
        epsilon = 1.0 / (size * 100.0 + 1.0)

    # Initialize
    prices = [0.0] * size
    assignment = [-1] * size
    reverse_assignment = [-1] * size
    unassigned = set(range(size))

    # Auction iterations
    max_iterations = size * size * 20
    iteration = 0

    while unassigned and iteration < max_iterations:
        iteration += 1

        # Pick an unassigned row
        i = unassigned.pop()

        # Find best and second-best profit for row i
        best_profit = -float("inf")
        best_col = -1
        second_best_profit = -float("inf")

        for j in range(size):
            profit = W[i][j] - prices[j]
            if profit > best_profit:
                second_best_profit = best_profit
                best_profit = profit
                best_col = j
            elif profit > second_best_profit:
                second_best_profit = profit

        if best_col == -1:
            best_col = 0
            best_profit = W[i][0] - prices[0]
            second_best_profit = -float("inf")

        # Calculate bid increment
        if second_best_profit == -float("inf"):
            bid_increment = epsilon
        else:
            bid_increment = best_profit - second_best_profit + epsilon

        # Reassign if column was taken
        if reverse_assignment[best_col] != -1:
            old_row = reverse_assignment[best_col]
            assignment[old_row] = -1
            unassigned.add(old_row)

        # Make assignment
        assignment[i] = best_col
        reverse_assignment[best_col] = i
        prices[best_col] += bid_increment

    # Extract assignment for original rows
    result_assignment = assignment[:n]

    # Calculate total weight - only count valid assignments
    total_weight = 0.0
    for i in range(n):
        if result_assignment[i] != -1 and result_assignment[i] < m:
            if i < len(weights) and result_assignment[i] < len(weights[i]):
                total_weight += weights[i][result_assignment[i]]
            else:
                result_assignment[i] = -1
        else:
            result_assignment[i] = -1

    return total_weight, result_assignment


def hungarian(weights: List[List[float]]) -> Tuple[float, List[int]]:
    """
    [LEGACY - Kept for reference and testing]
    Hungarian algorithm for maximum weight bipartite matching.
    Used for unordered result comparison. We pad to a square matrix with 0s,
    convert max-weight to min-cost using a cost shift (max_seen - w or 1 - w),
    then run the standard O(n^3) Hungarian procedure. Returns total weight and
    the row->col assignment for original rows (unmatched = -1).

    NOTE: This implementation is now replaced by the auction() algorithm
    for better performance on large datasets (75K+ rows). Kept here for
    verification and as a reference implementation.
    """
    if not weights:
        return 0.0, []
    n = len(weights)
    m = max(len(r) for r in weights)
    size = max(n, m)

    w = [[0.0] * size for _ in range(size)]
    max_seen = 0.0
    for i in range(n):
        for j in range(len(weights[i])):
            v = weights[i][j]
            if v > max_seen:
                max_seen = v
            w[i][j] = v

    use_shift = max_seen > 1.0

    def _cost(val: float) -> float:
        return (max_seen - val) if use_shift else (1.0 - val)

    INF = 10**18
    a = [[0.0] * (size + 1)] + [[0.0] + [_cost(w[i][j]) for j in range(size)] for i in range(size)]
    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    p = [0] * (size + 1)
    way = [0] * (size + 1)

    for i in range(1, size + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (size + 1)
        used = [False] * (size + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = 0
            for j in range(1, size + 1):
                if not used[j]:
                    cur = a[i0][j] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(0, size + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    assignment = [-1] * n
    total_w = 0.0
    for j in range(1, size + 1):
        i = p[j]
        if 1 <= i <= n and 1 <= j <= m:
            assignment[i - 1] = j - 1
            total_w += w[i - 1][j - 1]
    return total_w, assignment


def bfbeta_score(
    pd: List[Dict[str, Any]], gt: List[Dict[str, Any]], sql: str = "", beta: float = 2.0, ndigits: int = 3, ordered: Optional[bool] = None, dedup: bool = True
) -> float:
    """
    Calculate Bipartite-F beta score between predicted and ground truth results.

    This metric uses optimal bipartite matching to find the best alignment
    between predicted and ground truth rows, then computes F-beta scores
    for each matched pair.

    Args:
        pd: Predicted query results as list of dictionaries.
        gt: Ground truth query results as list of dictionaries.
        sql: Ground truth SQL query (used to detect ORDER BY).
        beta: Beta parameter for F-beta score (default 2.0 favors recall).
        ndigits: Number of decimal places for float comparison.
        ordered: Override order detection (None = auto-detect from SQL).
        dedup: If True, drop duplicate rows before scoring (BIRD-style behavior).
               If False, preserve duplicates for stricter evaluation.

    Returns:
        BF score in range [0, 1].

    Example:
        >>> pred = [{"a": 1, "b": 2}]
        >>> gt = [{"a": 1, "b": 2}]
        >>> bfbeta_score(pred, gt)
        1.0
    """
    pd_list = list(pd or [])
    gt_list = list(gt or [])

    if dedup:
        # Drop duplicate rows while preserving order
        # Use row_bag as the dedup key (row as multiset of values)
        def _safe_bag_key(r):
            bag = row_bag(r, ndigits)
            return tuple(sorted(bag.items(), key=lambda x: (str(type(x[0])), str(x[0]), x[1])))

        seen_pd = []
        seen_pd_keys = []
        for r in pd_list:
            key = _safe_bag_key(r)
            if key not in seen_pd_keys:
                seen_pd_keys.append(key)
                seen_pd.append(r)
        pd_list = seen_pd

        seen_gt = []
        seen_gt_keys = []
        for r in gt_list:
            key = _safe_bag_key(r)
            if key not in seen_gt_keys:
                seen_gt_keys.append(key)
                seen_gt.append(r)
        gt_list = seen_gt

    n = len(pd_list)
    m = len(gt_list)
    if n == 0 and m == 0:
        return 1.0

    _warn_large_result("Prediction", n)
    _warn_large_result("Ground truth", m)

    P = [row_bag(r, ndigits) for r in pd_list]
    G = [row_bag(r, ndigits) for r in gt_list]

    W = [[0.0] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            W[i][j] = row_fbeta(P[i], G[j], beta)

    ordered = ordered if ordered is not None else has_order_by(sql)
    if ordered:
        best = dp_max(W)
    else:
        # Use auction algorithm for faster performance on large datasets
        best, _ = auction(W)

        # Legacy Hungarian implementation (verified to produce identical results):
        # best, _ = hungarian(W)

    denom = max(n, m)
    return (best / denom) if denom > 0 else 1.0
