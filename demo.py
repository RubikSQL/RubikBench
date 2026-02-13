from ahvn.utils.db import Database
from rubikbench import RubikBenchEvaluator, QuerySet

db = Database(provider="duckdb", database="./data/RubikBench/databases/RubikBench.duckdb")
queries = QuerySet("./data/RubikBench/queries/RubikBench.json")

# Create a full template (empty SQL placeholders)
# queries.create_template("submission_full.json")  # Uncomment to create full template

# Sample 10 queries and create a template with placeholder SQL
sample_queries = queries.sample(n=10, seed=42)
sample_queries.create_template("./submissions/sample.json", placeholder="SELECT 1+1;")

# Evaluate submissions (default: ordered evaluation)
evaluator = RubikBenchEvaluator(
    db=db,
    queries=QuerySet("./queries/RubikBench.json"),
    bf_beta=2.0,
    sf_beta=1.0,
    src="duckdb"    # Your SQL dialect, if not DuckDB, SQL will be converted automatically via SQLGlot to DuckDB
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
