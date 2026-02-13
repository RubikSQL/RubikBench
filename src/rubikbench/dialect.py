"""SQL dialect conversion via sqlglot."""

from ahvn.utils.db import prettify_sql
import sqlglot


def safe_sql(sql: str) -> str:
    return sql.replace(":", r"\:").strip()


# Mapping of common dialect names to sqlglot dialect names
DIALECT_MAP = {
    "duckdb": "duckdb",
    "postgres": "postgres",
    "postgresql": "postgres",
    "pg": "postgres",
    "mysql": "mysql",
    "sqlite": "sqlite",
    "oracle": "oracle",
    "sqlserver": "tsql",
    "tsql": "tsql",
    "mssql": "tsql",
    "bigquery": "bigquery",
    "snowflake": "snowflake",
    "redshift": "redshift",
    "hive": "hive",
    "spark": "spark",
    "presto": "presto",
    "trino": "trino",
}


def normalize_dialect(dialect: str) -> str:
    """
    Normalize dialect name to sqlglot-compatible name.

    Args:
        dialect: Input dialect name (case-insensitive).

    Returns:
        Normalized dialect name.

    Raises:
        ValueError: If dialect is not supported.
    """
    dialect_lower = dialect.lower().strip()

    if dialect_lower in DIALECT_MAP:
        return DIALECT_MAP[dialect_lower]

    # Check if it's already a valid sqlglot dialect
    try:
        sqlglot.Dialect.get_or_raise(dialect_lower)
        return dialect_lower
    except Exception:
        pass

    supported = sorted(set(DIALECT_MAP.values()))
    raise ValueError(f"Unsupported dialect: {dialect}. " f"Supported dialects: {', '.join(supported)}")


def convert_sql(sql: str, source_dialect: str, target_dialect: str = "duckdb", pretty: bool = False) -> str:
    """
    Convert SQL from one dialect to another.

    Args:
        sql: SQL query string.
        source_dialect: Source database dialect.
        target_dialect: Target database dialect (default: duckdb).
        pretty: Format the output SQL for readability.

    Returns:
        Converted SQL string.

    Example:
        >>> sql = "SELECT TOP 10 * FROM users"
        >>> convert_sql(sql, "tsql", "duckdb")
        'SELECT * FROM users LIMIT 10'
    """
    source = normalize_dialect(source_dialect)
    target = normalize_dialect(target_dialect)

    if source == target:
        return sql

    try:
        converted = sqlglot.transpile(sql, read=source, write=target, pretty=pretty)
        return converted[0] if converted else sql
    except Exception as e:
        raise ValueError(f"Failed to convert SQL from {source} to {target}: {e}")


def validate_sql(sql: str, dialect: str = "duckdb") -> bool:
    """
    Validate SQL syntax for a given dialect.

    Args:
        sql: SQL query string.
        dialect: Target dialect for validation.

    Returns:
        True if SQL is valid, False otherwise.
    """
    if not sql or not sql.strip():
        return False
    dialect = normalize_dialect(dialect)
    try:
        result = sqlglot.parse(sql, dialect=dialect)
        return len(result) > 0 and result[0] is not None
    except Exception:
        return False


def get_supported_dialects() -> list:
    """
    Get list of supported SQL dialects.

    Returns:
        List of supported dialect names.
    """
    return sorted(set(DIALECT_MAP.values()))
