"""Query set management."""

from typing import List, Dict, Any, Optional, Union

from ahvn.utils.basic.serialize_utils import load_json, save_json


class QuerySet:
    """Load, filter and iterate over benchmark queries."""

    DIFFICULTY_LEVELS = ["simple", "moderate", "challenging", "nightmare", "unknown"]

    def __init__(self, queries_path: Optional[str] = None, queries: Optional[List[Dict[str, Any]]] = None):
        if queries is not None:
            self._queries = queries
        elif queries_path is not None:
            self._queries = self._load_queries(queries_path)
        else:
            self._queries = []

        # Build index for fast lookup
        self._id_index: Dict[str, int] = {q["id"]: i for i, q in enumerate(self._queries)}

    @staticmethod
    def _load_queries(path: str) -> List[Dict[str, Any]]:
        """Load queries from JSON file."""
        queries = load_json(path, strict=True)
        return queries

    def __len__(self) -> int:
        return len(self._queries)

    def __iter__(self):
        return iter(self._queries)

    def __getitem__(self, key: Union[int, str, slice]) -> Union[Dict[str, Any], "QuerySet"]:
        if isinstance(key, int):
            return self._queries[key]
        elif isinstance(key, str):
            # Lookup by query ID
            if key not in self._id_index:
                raise KeyError(f"Query ID not found: {key}")
            return self._queries[self._id_index[key]]
        elif isinstance(key, slice):
            return QuerySet(queries=self._queries[key])
        else:
            raise TypeError(f"Invalid key type: {type(key)}")

    def get(self, query_id: str, default: Any = None) -> Optional[Dict[str, Any]]:
        """Get query by ID, returning default if not found."""
        try:
            return self[query_id]
        except KeyError:
            return default

    @property
    def ids(self) -> List[str]:
        """List of all query IDs."""
        return [q["id"] for q in self._queries]

    def filter(
        self,
        ids: Optional[List[str]] = None,
        difficulty: Optional[Union[str, List[str]]] = None,
        tags: Optional[List[str]] = None,
        dialect: Optional[str] = None,
        verified_only: bool = False,
    ) -> "QuerySet":
        """
        Filter queries by various criteria.

        Args:
            ids: List of query IDs to include.
            difficulty: Difficulty level(s) to include.
            tags: Query tags to match (any tag matches).
            dialect: SQL dialect to filter by.
            verified_only: Only include verified queries.

        Returns:
            New QuerySet containing filtered queries.

        Example:
            >>> qs.filter(difficulty="simple", verified_only=True)
            >>> qs.filter(ids=["Q00001", "Q00002"])
            >>> qs.filter(tags=["period-monthly"])
        """
        result = self._queries

        # Filter by IDs
        if ids is not None:
            id_set = set(ids)
            result = [q for q in result if q["id"] in id_set]

        # Filter by difficulty
        if difficulty is not None:
            if isinstance(difficulty, str):
                difficulty = [difficulty]
            difficulty_set = set(d.lower() for d in difficulty)
            result = [q for q in result if (q.get("metadata", {}).get("difficulty") or "").lower() in difficulty_set]

        # Filter by tags
        if tags is not None:
            tag_set = set(tags)
            result = [q for q in result if tag_set.intersection(set(q.get("metadata", {}).get("query_tags", [])))]

        # Filter by dialect
        if dialect is not None:
            result = [q for q in result if q.get("dialect", "").lower() == dialect.lower()]

        # Filter by verification status
        if verified_only:
            result = [q for q in result if q.get("metadata", {}).get("verified", False)]

        return QuerySet(queries=result)

    def sample(self, n: int, seed: Optional[int] = None) -> "QuerySet":
        """
        Randomly sample n queries.
        We use hash-based sampling for reproducibility. This means that for a fixed seed,
        if you sample n queries, and then sample m > n queries, the n sampled queries will
        always be included in the m sampled queries.

        Args:
            n: Number of queries to sample.
            seed: Random seed for reproducibility.

        Returns:
            New QuerySet containing sampled queries.
        """
        from ahvn.utils.basic.rnd_utils import StableRNG

        rng = StableRNG(seed=seed)

        n = min(n, len(self._queries))
        sampled = rng.hash_sample(self._queries, k=n)
        ordered = sorted(sampled, key=lambda q: self._id_index[q["id"]])
        return QuerySet(queries=ordered)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the query set.

        Returns:
            Dictionary with query set statistics.
        """
        stats = {
            "total": len(self._queries),
            "by_difficulty": {},
            "by_dialect": {},
            "verified_count": 0,
            "tags": {},
            "sql_length_by_difficulty": {},  # Track SQL length by difficulty
        }

        for q in self._queries:
            # Count by difficulty
            diff = q.get("metadata", {}).get("difficulty", "unknown")
            stats["by_difficulty"][diff] = stats["by_difficulty"].get(diff, 0) + 1

            # Count by dialect
            dialect = q.get("dialect", "unknown")
            stats["by_dialect"][dialect] = stats["by_dialect"].get(dialect, 0) + 1

            # Count verified
            if q.get("metadata", {}).get("verified", False):
                stats["verified_count"] += 1

            # Count tags
            for tag in q.get("metadata", {}).get("query_tags", []):
                stats["tags"][tag] = stats["tags"].get(tag, 0) + 1

            # Track SQL length by difficulty
            sql = q.get("sql", "")
            sql_len = len(sql)
            if diff not in stats["sql_length_by_difficulty"]:
                stats["sql_length_by_difficulty"][diff] = {"total_length": 0, "count": 0}
            stats["sql_length_by_difficulty"][diff]["total_length"] += sql_len
            stats["sql_length_by_difficulty"][diff]["count"] += 1

        # Calculate average SQL length for each difficulty
        for diff in stats["sql_length_by_difficulty"]:
            if stats["sql_length_by_difficulty"][diff]["count"] > 0:
                stats["sql_length_by_difficulty"][diff]["avg_length"] = (
                    stats["sql_length_by_difficulty"][diff]["total_length"] / stats["sql_length_by_difficulty"][diff]["count"]
                )
            else:
                stats["sql_length_by_difficulty"][diff]["avg_length"] = 0

        return stats

    def to_list(self) -> List[Dict[str, Any]]:
        """Convert to list of query dictionaries."""
        return list(self._queries)

    def to_json(self, path: str, indent: int = 4):
        """Save queries to JSON file."""
        save_json(self._queries, path, indent=indent)

    def create_template(self, output_path: str, placeholder: str = "") -> None:
        """
        Create a submission template JSON file.

        Generates a JSON file with query IDs as keys and placeholder SQL as values.

        Args:
            output_path: Path where the template JSON will be saved.
            placeholder: Placeholder value for empty SQL fields (default: "").

        Example:
            >>> qs = QuerySet("./data/RubikBench/queries/RubikBench.json")
            >>> qs.create_template("submission.json")
            >>> # Create with a default SQL placeholder
            >>> qs.create_template("submission.json", placeholder="SELECT 1+1;")
        """
        template_data = {q["id"]: placeholder for q in self._queries}
        save_json(template_data, output_path, indent=4)
