from ahvn.utils.db import Database
from rubikbench import RubikBenchEvaluator, QuerySet
from rubikbench.benchmarks import default_database_path, default_queries_path

db = Database(provider="duckdb", database=default_database_path("RubikBench"))
queries = QuerySet(default_queries_path("RubikBench"))

# Create a full template (empty SQL placeholders)
# queries.create_template("submission_full.json")  # Uncomment to create full template

# Sample 10 queries and create a template with placeholder SQL
sample_queries = queries.sample(n=10, seed=42)
sample_queries.create_template("./submissions/sample.json", placeholder="SELECT 1+1;")

# Evaluate submissions
evaluator = RubikBenchEvaluator(
    db=db,
    queries=queries,
    bf_beta=2.0,
    sf_beta=1.0,
    src="duckdb",   # Your SQL dialect, if not DuckDB, SQL will be converted automatically via SQLGlot to DuckDB
    dedup=False,     # Match the CLI's strict default behavior
)
report = evaluator.evaluate_submission(submission="./submissions/sample.json")

# Access results by difficulty
print(f"Overall BF2 Ordered: {report.scores['overall']['bfo']:5.2%}")
print(f"Simple BF2 ordered: {report.scores['simple']['bfo']:5.2%}")
print(f"Moderate BF2 ordered: {report.scores['moderate']['bfo']:5.2%}")
print(f"Challenging BF2 ordered: {report.scores['challenging']['bfo']:5.2%}")

# Access summary statistics
print(f"Total queries: {report.N['overall']}")
print(f"Compilable: {report.C['overall']}")
print(f"Compilable rate: {report.compilable['overall']:5.2%}")
