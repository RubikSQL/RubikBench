"""
Utility functions for metric calculations.
"""

from typing import Any, Dict, Tuple
from decimal import Decimal
import re


def norm_val(v: Any, ndigits: int = 3) -> Any:
    """
    Normalize a value for comparison.

    Args:
        v: Value to normalize.
        ndigits: Number of decimal places for rounding floats.

    Returns:
        Normalized value.
    """
    try:
        if isinstance(v, float):
            return round(v, ndigits)
        if isinstance(v, Decimal):
            return round(float(v), ndigits)
    except Exception:
        pass
    return v


def norm_row(row: Dict[str, Any], ndigits: int = 3) -> Tuple[Any, ...]:
    """
    Normalize a row dictionary to a tuple for comparison.

    Args:
        row: Dictionary representing a database row.
        ndigits: Number of decimal places for rounding floats.

    Returns:
        Tuple of normalized values.
    """
    return tuple(norm_val(v, ndigits) for v in row.values())


def strip_comments(sql: str) -> str:
    """Remove SQL comments from a query string."""
    if not sql:
        return ""
    sql = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql


def has_order_by(sql: str) -> bool:
    """Check if a SQL query contains ORDER BY clause."""
    s = strip_comments(sql or "")
    return bool(re.search(r"\border\s+by\b", s, flags=re.IGNORECASE))
