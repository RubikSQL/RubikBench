# RubikBench

[中文](README.zh.md)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![HuggingFace Dataset](https://img.shields.io/badge/🤗-Dataset-yellow.svg)](https://huggingface.co/datasets/Magolor/RubikBench)

> **Database Homepage**: [RubikBench](https://huggingface.co/datasets/Magolor/RubikBench)

RubikBench is an enterprise-scale financial database designed for realistic Natural Language to SQL (NL2SQL) research and evaluation.

The RubikBench database contains the **financial** data of *APEX*, a hypothetical international **automobile** manufacturing and sales company. As a financial database, it is designed to support various analytical queries related to the company's operations, sales, and financial performance. This (imaginary) company operates mainly in China, the United States, and Europe. Therefore the database is bilingual, with both English and Chinese values, and uses three currencies: CNY, USD, and EUR.

While the data values are synthesized, the schemas and structural patterns are closely modeled after actual enterprise financial databases, ensuring practical relevance for NL2SQL system development and evaluation. The database is specifically designed to reflect the complexities encountered in real-world enterprise environments, including wide table schemas, domain-specific knowledge, diverse metrics and data calibers, etc.

Meanwhile, we provide a full NL2SQL evaluation toolkit, the `rubikbench` python package and CLI, which helps researchers easily evaluate their systems on RubikBench as well as other popular databases such as BirdSQL (MINIDEV) and KaggleDBQA.

<br/>

## 1. Quick Start

### 1.1 Installation

```bash
# Clone the repository
git clone https://github.com/Magolor/RubikBench.git
cd RubikBench

# Install dependencies
pip install -e .

# AgentHeaven Init
ahvn setup
```

It is recommended to install [fzf](https://github.com/junegunn/fzf) for better CLI experience.

<br/>

### 1.2 Download Database

```bash
# Download RubikBench from HuggingFace (default)
rubikbench setup

# Download BirdSQL MINIDEV from Google Drive
rubikbench setup -B BirdSQL

# Download KaggleDBQA from Google Drive
rubikbench setup -B KaggleDBQA

# Download to a custom location
rubikbench setup --data <your_data_path>

# Alternatively, clone the full HuggingFace dataset (including parquet files and stats)
# git lfs install
git clone https://huggingface.co/datasets/Magolor/RubikBench ./data/RubikBench
```

**Note**: `rubikbench setup` downloads the database archive and, for RubikBench, also prepares the lightweight query metadata file `./data/RubikBench/queries/RubikBench.json`, so a full dataset clone is optional for CLI evaluation. Use `--remove-zip` to delete the downloaded archive after extraction.

<br/>

### 1.3 Run Evaluation

```bash
# Generate a submission template (uses the default RubikBench queries path)
rubikbench template -out submission.json

# It is recommended to test against a certain type (e.g. lang-english) of queries
rubikbench template --tags lang-english -out submissions/template.json

# You can also specify a custom SQL placeholder (default is empty string)
rubikbench template --tags lang-english -out submissions/template.json --sql "SELECT 1+1;"

# Now fill in your SQL predictions in submission.json
# For example:
# {
#     "Q00001": "SELECT SUM(ptd_amt_a_cny) FROM INCOME_ALL WHERE period = '202506'",
#     "Q00002": "SELECT ...",
#     ...
# }

# Then evaluate
rubikbench eval submission.json

# Or provide the submission path explicitly via --input-file
rubikbench eval --input-file submission.json

# Evaluate specific queries or difficulty levels
rubikbench eval submission.json --ids Q00001 --ids Q00002
rubikbench eval submission.json --split simple

# Enable verbose output (progress bar)
rubikbench eval submission.json --verbose

# Save detailed results
rubikbench eval submission.json --output-file results.json
```

> **Note**: `rubikbench eval` only evaluates queries that exist in the submission file. If you want to evaluate a subset of queries, make sure to include only those keys in the submission file. When including keys with empty or null SQL, those queries will be marked as failed.
> The CLI always reports both ordered and unordered scores where applicable; there is no separate CLI mode switch for `eval`.
> It is generally recommended to generate a template on a specific subset of queries (e.g. by tags or difficulty levels) to get more meaningful results.
> For example, the default `submissions/template.json` is obtained via: `rubikbench template --tags lang-english -out submissions/template.json`.

<br/>

### 1.4 Python API Example

```python
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
```

<br/>

### 1.5 RubikBench Browser CLI

> **Note**: The browser CLI is primarily optimized for RubikBench. It also works for other datasets when query metadata and database paths are available, but the best terminal browsing experience is still on RubikBench.

When [fzf](https://github.com/junegunn/fzf) is installed, you can use:

```bash
rubikbench browse [-B RubikBench] [--split/-s simple/moderate/challenging/nightmare/unknown] [--tags/-t tag1] [--tags/-t tag2] ...
```

to interactively browse and filter queries via a terminal UI. It supports filtering by:
- Difficulty levels
- Tags
- Keywords in questions (partial match)

Use mouse to scroll through long questions.
Type keywords to filter questions in real time.
Use `TAB` to toggle preview containing query information, SQL and execution results (`rubikbench exec`).
Use `CTRL+E` to open a pager for easier inspection and copying.
Use `CTRL+D` to copy the current selected query preview to clipboard.

<br/>

## 2. RubikBench Database Statistics

### 2.1 Overview

- **Total Size**: ~ 38 GB (DuckDB) / ~ 11 GB (parquet)
- **Total Tables**: 20 tables
- **Total Records**: ~ 901.53 million rows
- **Time Coverage**: Monthly from January 2020 to December 2025 (72 months)
- **Languages**: Bilingual (English and Chinese)
- **Database Format**: DuckDB Native (recommended), parquet (for HuggingFace)
    - Formats like sqlite are not supported as they do not compress the data. The full, uncompressed size of data can be over 500GB.

<br/>

### 2.2 Table Statistics

| Table Name | Rows | Columns | Period | Region | Customer | Dealer | Product | Contract | Project | Revenue | Expense |
|------------|----------------|---------|--------|--------|----------|--------|---------|----------|---------|---------|---------|
| **INCOME_ALL** | 12.41M | 61 | 72 | ✓ | ✓ |   | ✓ |   |   | ✓ |   |
| INCOME_ACCESSORY | 3.37M | 61 | 72 | ✓ | ✓ |   | ✓ |   |   | ✓ |   |
| INCOME_CYBVEHSYS | 0.99M | 61 | 72 | ✓ | ✓ |   | ✓ |   |   | ✓ |   |
| INCOME_GALMOTGRO | 1.72M | 61 | 72 | ✓ | ✓ |   | ✓ |   |   | ✓ |   |
| INCOME_NOVDYN | 1.42M | 61 | 72 | ✓ | ✓ |   | ✓ |   |   | ✓ |   |
| INCOME_SERVICE | 1.48M | 61 | 72 | ✓ | ✓ |   | ✓ |   |   | ✓ |   |
| INCOME_SHIMOTCOR | 1.13M | 61 | 72 | ✓ | ✓ |   | ✓ |   |   | ✓ |   |
| INCOME_TYRAUTGRO | 1.04M | 61 | 72 | ✓ | ✓ |   | ✓ |   |   | ✓ |   |
| INCOME_WEYMOTCOR | 1.25M | 61 | 72 | ✓ | ✓ |   | ✓ |   |   | ✓ |   |
| **BUDGET_AND_FORECAST_ALL** | 96.58M | 37 | 72 | ✓ |   |   | ✓ |   |   | ✓ | ✓ |
| BUDGET_AND_FORECAST_ACCESSORY | 30.18M | 37 | 72 | ✓ |   |   | ✓ |   |   | ✓ | ✓ |
| BUDGET_AND_FORECAST_CYBVEHSYS | 8.50M | 37 | 72 | ✓ |   |   | ✓ |   |   | ✓ | ✓ |
| BUDGET_AND_FORECAST_GALMOTGRO | 11.23M | 37 | 72 | ✓ |   |   | ✓ |   |   | ✓ | ✓ |
| BUDGET_AND_FORECAST_NOVDYN | 10.46M | 37 | 72 | ✓ |   |   | ✓ |   |   | ✓ | ✓ |
| BUDGET_AND_FORECAST_SERVICE | 9.48M | 37 | 72 | ✓ |   |   | ✓ |   |   | ✓ | ✓ |
| BUDGET_AND_FORECAST_SHIMOTCOR | 8.86M | 37 | 72 | ✓ |   |   | ✓ |   |   | ✓ | ✓ |
| BUDGET_AND_FORECAST_TYRAUTGRO | 8.51M | 37 | 72 | ✓ |   |   | ✓ |   |   | ✓ | ✓ |
| BUDGET_AND_FORECAST_WEYMOTCOR | 9.35M | 37 | 72 | ✓ |   |   | ✓ |   |   | ✓ | ✓ |
| **PROFIT_AND_LOSS** | 161.74M | 67 | 72 | ✓ | ✓ | ✓ | ✓ |   |   | ✓ | ✓ |
| **SALES_LEDGER** | 521.81M | 55 | 72 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

<br/>

### 2.3 Entity Statistics

| Dimension | Hierarchy Levels | Total Entities |
|-----------|------------------|----------------|
| **Period** | 1 | 72 months (202001-202512) |
| **Region** | 6 | 2 overseas/domestic, 11 sales regions, 22 countries, 37 national areas, 46 provinces, 47 cities |
| **Product** | 4 | 3 (Lv0), 19 (Lv1), 93 (Lv2), 353 (Lv3) |
| **Customer** | 4 | 4 (Lv1), 9 (Lv2), 14 (Lv3), 22 (Lv4) |
| **Dealer** | 3 | 3 (Lv1), 5 (Lv2), 9 (Lv3) including 'Direct Sales' |
| **Report Item** | 4 | 2 (Lv0), 6 (Lv1), 10 (Lv2), 22 (Lv3) |
| **Contract/Project** | 2 | 40,756 distinct contracts, 46,895 distinct projects |
| **Caliber** | 1 | 2 calibers (A, B) |
| **Currency** | 1 | 3 currencies (CNY, EUR, USD) |

<br/>

### 2.4 Database Explanation

RubikBench is a database containing the **financial** data of *APEX*, an (imaginary) international **automobile** manufacturing and sales company. As a financial database, it is designed to support various analytical queries related to the company's operations, sales, and financial performance. This (imaginary) company operates mainly in China, the United States, and Europe. Therefore the database is bilingual, with both English and Chinese values, and uses three currencies: CNY, USD, and EUR.

Specifically, there are **6 key dimensions**: *Period* (time, monthly), *Product*, *Region*, *Customer*, *Dealer*, and *Report Item* (revenues and expenses). Also, there are extra dimensions including: *Contract*, *Project*, *Currency*, and *Caliber*.

The minimal granularity of the data is a **payment** of a **project**. Each **project** happens between APEX and a **customer** at a specific **region**, with an optional **dealer**, over a **period** of time. Payments of a project can be distributed over multiple months in that time period. Each project may contain multiple **products**. Each **contract** may contain multiple projects.

RubikBench contains **20 tables** of **4 major categories**, all of them are aggregated views over the fact table (which is not exposed directly):
- The `INCOME` tables, which contain data aggregated over **project** and **dealer**, and only include revenues. The INCOME tables are the smallest tables in RubikBench, aiming for quick analytical queries.
- The `BUDGET_AND_FORECAST` tables, which contain data aggregated over **project**, **customer**, and **dealer**. These tables contain only amt/forecast/budget/target values. Notice that the semantics of these values could be counter-intuitive: while the target value is the target for monthly revenues and expenses in `YYYYMM`, as one would expect, the forecast value of `YYYYMM` is the forecast of `YYYY12` (yearly) based on the information available at the end of `YYYYMM`, and the budget of `YYYYMM` is a constant yearly budget value duplicated for each month in the year.
- The `PROFIT_AND_LOSS` table, which contains data aggregated only over **project**. It contains the most comprehensive dimensions and measures, including both revenues and expenses. It is the largest table in RubikBench, aiming to support detailed financial analysis.
- The `SALES_LEDGER` table, which contains the lowest-granularity data, i.e. payment-level data. It is designed to support detailed audit and traceability of sales. However, it is limited to sales-related revenues and expenses only.

The products of APEX are divided into **3 major divisions**: *Automobiles*, *Accessories*, and *Services*.
- *Automobiles* are produced by enterprise brand groups, which are **6 sub-brands** under APEX. Each brand group has its own `INCOME` and `BUDGET_AND_FORECAST` tables.
- *Accessories* and *Services* each have their own `INCOME` and `BUDGET_AND_FORECAST` tables. Accessories only have equipment revenues and costs, while services only have service revenues and costs.

The default Caliber is code *A*, which clearly separates equipment and service report items, reflecting the real financial statistics. However, to facilitate cooperation between different divisions, there is also Caliber *B*, which moves 5% of service revenue to equipment revenue.

Notice that due to historical reasons as well as query efficiency expectations, currencies and calibers are organized differently across different tables. For example, for the `INCOME` and `PROFIT_AND_LOSS` tables, different currencies and calibers are stored in different columns as column-name suffixes (e.g. `_cny_a`, `_usd_a`, `_eur_b`, etc.); while for the `SALES_LEDGER` and `BUDGET_AND_FORECAST` tables, `caliber` and `currency` are separate columns that **must** be filtered on in query predicates to avoid duplicated results.

Financial amounts present both `ptd` (monthly) values and `ytd` (year-to-date) values. For example, `ptd` of `YYYYMM` means the amount for that month, while `ytd` of `YYYYMM` means the cumulative amount from `YYYY01` to `YYYYMM` (inclusive). Furthermore, `_py` columns contain previous-year data, which means that, for example, `ytd` previous-year columns with `period='YYYYMM'` contain cumulative amounts from `YYYY-1 01` to `YYYY-1 MM`, etc.

<br/>

## 3. RubikBench Query Statistics

RubikBench v0.9.2 contains **3198** fully human-verified queries covering diverse financial analysis scenarios, with comprehensive annotations including difficulty levels, query tags, and user context profiles. The queries are written in both English (1,689) and Chinese (1,509), reflecting the bilingual nature of the database.

<br/>

### 3.1 Difficulty Distribution

| Difficulty | Count | % | Avg. SQL Length | Min SQL Length | Max SQL Length |
|------------|------:|---:|---------------:|---------------:|---------------:|
| **Simple** | 1,047 | 32.7% | 218 chars | 11 chars | 1,240 chars |
| **Moderate** | 1,531 | 47.9% | 641 chars | 213 chars | 3,492 chars |
| **Challenging** | 415 | 13.0% | 1,755 chars | 339 chars | 3,635 chars |
| **Nightmare** | 205 | 6.4% | 1,881 chars | 579 chars | 4,183 chars |

<br/>

### 3.2 Table Coverage

Queries span all 4 major table categories (a query may reference multiple tables):

| Table Category | Queries | Individual Tables |
|----------------|--------:|:---|
| **INCOME_\*** | 1,615 | INCOME_ALL (581), INCOME_WEYMOTCOR (153), INCOME_SHIMOTCOR (142), INCOME_TYRAUTGRO (132), INCOME_ACCESSORY (130), INCOME_NOVDYN (122), INCOME_SERVICE (121), INCOME_GALMOTGRO (120), INCOME_CYBVEHSYS (118) |
| **BUDGET_AND_FORECAST_\*** | 724 | BUDGET_AND_FORECAST_ALL (124), BUDGET_AND_FORECAST_WEYMOTCOR (97), BUDGET_AND_FORECAST_TYRAUTGRO (85), BUDGET_AND_FORECAST_SERVICE (81), BUDGET_AND_FORECAST_SHIMOTCOR (79), BUDGET_AND_FORECAST_NOVDYN (77), BUDGET_AND_FORECAST_ACCESSORY (72), BUDGET_AND_FORECAST_CYBVEHSYS (54), BUDGET_AND_FORECAST_GALMOTGRO (53) |
| **PROFIT_AND_LOSS** | 408 | — |
| **SALES_LEDGER** | 367 | — |

<br/>

### 3.3 SQL Feature Distribution

| SQL Feature | Queries | % |
|-------------|--------:|---:|
| `GROUP BY` | 2,296 | 71.8% |
| `ORDER BY` | 2,139 | 66.9% |
| `CASE WHEN` | 1,409 | 44.1% |
| `COALESCE` | 876 | 27.4% |
| Subquery | 768 | 24.0% |
| Window Function (`OVER`) | 746 | 23.3% |
| `LIMIT` | 635 | 19.9% |
| CTE (`WITH`) | 438 | 13.7% |
| `HAVING` | 334 | 10.4% |
| `DISTINCT` | 260 | 8.1% |
| `JOIN` | 94 | 2.9% |
| `CAST` | 86 | 2.7% |
| `UNION` | 28 | 0.9% |

<br/>

### 3.4 Query Occupations

Each query includes a simulated user profile with an occupation field, representing different roles that would typically interact with financial data:

| Occupation | Count | % | Description |
|------------|------:|---:|-------------|
| **Sales** | 707 | 22.1% | Sales representatives and managers |
| **Finance** | 675 | 21.1% | Financial analysts and accountants |
| **Management** | 559 | 17.5% | Executive and strategic decision-makers |
| **Guest** | 363 | 11.4% | External users with limited access |
| **Developer** | 356 | 11.1% | Technical users and system developers |
| **Unspecified** | 538 | 16.8% | No specific occupation context |

<br/>

## 4. Query & Submission Formats

### 4.1 Query Structure

Each query in `RubikBench.json` follows this structure:

```json
{
    "benchmark": "RubikBench",
    "database": "RubikBench",
    "id": "Q00001",
    "question": "Show revenue for China, Q2 2025.",
    "context": {
        "query_time": 202509,
        "user_profile": {
            "occupation": null,
            "caliber": "A",
            "currency": null,
            "region": {},
            "department": {},
            "preferences": []
        }
    },
    "schema": null,
    "dialect": "duckdb",
    "sql": "SELECT ... FROM ... WHERE ...",
    "sql.1": "SELECT ... FROM ... WHERE ...",
    ...,
    "metadata": {
        "difficulty": "simple",
        "query_tags": [
            "level-simple",
            "lang-english",
            "type-basic",
            "value-amount",
            "period-quarterly"
        ],
        "order-relevant": false,
        "verified": true
    }
}
```

Explanation of fields:
- **benchmark**: Name of the benchmark (e.g. `RubikBench`)
- **database**: Name of the database (e.g. `RubikBench`)
- **id**: Unique query identifier
- **question**: Natural language question
- **context**: Contextual information (e.g. query time, user profile)
- **schema**: Optional schema information (`null` if not provided). If provided, the SQL output should use the table/column names as given in the schema.
- **dialect**: SQL dialect of the ground-truth SQL (e.g. `duckdb` for RubikBench, `sqlite` for BirdSQL / KaggleDBQA)
- **sql, sql.1, ...**: One or more ground-truth SQL queries (all acceptable; the maximum matching score across variants is used during evaluation)
- **metadata**: Additional metadata including:
    - **difficulty**: Difficulty level (`simple`, `moderate`, `challenging`, `nightmare`)
    - **query_tags**: List of tags describing query characteristics. See `query_tags.yaml` for all possible tags. Notice that the query tags are annotated with the aid of LLMs and may contain errors. Contributions to improve the annotations are welcome.
    - **order-relevant**: Whether the query result is order-relevant (it could be `true`/`false`, or `null` if unlabeled, in which case the evaluator will auto-detect based on the `ORDER BY` clause in the standard ground-truth SQL)
    - **verified**: Whether the ground-truth SQL has been human-verified. This is always true for official RubikBench queries. Contributions to add more verified queries, alternative SQLs, or corrections to existing queries are welcome.

During NL2SQL evaluation, only `database`, `question`, `context`, `schema`, and `dialect` should be used as input to the NL2SQL system. The benchmark, id, ground-truth SQL(s), and metadata are only used for evaluation and analysis. The dataset-aware CLI also uses the `benchmark` and `database` metadata to auto-resolve database paths for multi-database benchmarks.

<br/>

### 4.2 Submission Format

Submit predictions as a JSON file mapping query IDs to SQL strings:

```json
{
    "Q00001": "SELECT SUM(...) FROM INCOME_ALL WHERE ...",
    "Q00002": "SELECT ... FROM ..."
}
```

<br/>

### 4.3 Filtering Queries

```python
from rubikbench.queries import QuerySet

queries = QuerySet("./data/RubikBench/queries/RubikBench.json")

# Filter by difficulty
simple = queries.filter(difficulty="simple")
moderate = queries.filter(difficulty=["moderate", "challenging"])

# Filter by specific IDs
subset = queries.filter(ids=["Q00001", "Q00002", "Q00003"])

# Filter by tags
monthly = queries.filter(tags=["period-monthly"])

# Combine filters
subset = queries.filter(difficulty="simple", verified_only=True)

# Stable random sampling:
#   Randomly sample n queries.
#   We use AgentHeaven's hash-based sampling for reproducibility. This means that for a fixed seed,
#   if you sample n queries, and then sample m > n queries, the n sampled queries will
#   always be included in the m sampled queries. This is also robust with regards to changes
#   in the query set (e.g. adding new queries will not drastically change the sampled queries).
#   To run sampling with filter conditions, first filter the queries, then manually call:
#   `ahvn.utils.basic.rnd_utils.StableRNG(seed=seed).hash_sample(filtered_queries_subset, k=n_samples)`
sample = queries.sample(n=10, seed=42)
for query in sample:
    print(query["id"], query["question"])
print()
sample = queries.sample(n=20, seed=42)
for query in sample:
    print(query["id"], query["question"])
print()
```

<br/>

## 5. Evaluation

### 5.1 Understanding Evaluation Metrics

RubikBench computes **5 metric variants** for each query (unordered SF is deprecated):

| Metric | Description |
|--------|-------------|
| **EX** | Exact Match - binary (0 or 1) |
| **BF** | Bipartite F-beta - continuous score [0, 1] |
| **SF** | Soft F-beta (ordered only) - continuous score [0, 1] |

Each metric has **Ordered (o)** and **Unordered (u)** variants where applicable:
- **Ordered (`o`)**: Respects row order (only for queries that are order-relevant)
- **Unordered (`u`)**: Ignores row order (multiset comparison). Note: SF unordered is not supported as it is not well-defined.

The evaluation report shows:
- **N**: Total number of queries evaluated
- **C**: Number of compilable SQLs (no execution error)
- **compilable**: C/N rate
- **scores**: Success rate (queries with score ≥ 99.99%) / N

Notice that all the ground-truth results in the built-in benchmarks are guaranteed to have at most 1000 rows. If a prediction or ground truth result exceeds **1000** rows, **a warning will be printed** and evaluation will proceed (but may be slow or out-of-memory, and BF falls back to SF for slow cases). For custom datasets, ground-truth queries returning more than 1000 rows are discouraged due to evaluation efficiency. Consider adding `LIMIT` clauses where appropriate.

Though we attempt to imitate BIRD's evaluation, the original implementation of BIRD's EX and SF metrics is buggy, because it deduplicates rows by treating a table as a *set* of rows. We correct this behavior by treating a table as a *multiset* of rows instead. The CLI therefore defaults to strict multiset evaluation (`--no-dedup`), while low-level metric helpers and `RubikBenchEvaluator` keep `dedup=True` unless you explicitly pass `dedup=False`. Use `--dedup` in the CLI if you want to mimic BIRD's original behavior more closely.

<br/>

#### EX (Execution Accuracy)

Binary 0/1 metric checking whether predicted results exactly match ground truth.

The **unordered** EX score behaves similarly to [BIRD-SQL EX Accuracy](https://github.com/AlibabaResearch/DAMO-ConvAI/blob/main/bird/llm/src/evaluation.py#L26), which only compares whether the two sets of rows are identical (each row is considered an ordered tuple, with column names ignored). As RubikBench mainly involves numerical computation, we round all floating point numbers to 3 decimal places before comparison to reduce floating point precision issues.

```python
from rubikbench.metrics import ex_match

# Unordered comparison (default, with dedup)
score = ex_match(pd_rows, gt_rows)  # Returns 0 or 1

# Ordered comparison (respects row order)
score = ex_match(pd_rows, gt_rows, ordered=True)

# Strict evaluation: preserve duplicates
score = ex_match(pd_rows, gt_rows, dedup=False)

# Mimic BIRD's buggy behavior for unordered comparison (legacy)
score = ex_match(pd_rows, gt_rows, ordered=False, fixed=False, dedup=False)
```

- **ordered=False** (default): Multiset comparison, ignores row order
- **ordered=True**: Row-by-row positional comparison
- **dedup=True** (default): Drop duplicate rows before comparison
- **dedup=False**: Preserve duplicates for strict evaluation

<br/>

#### SF (Soft F-beta Score)

The soft F-beta score is a more lenient metric that gives partial credit for partially correct rows. Only the **ordered** variant is supported.

The **ordered** SF (β=1.0) score behaves similarly to [BIRD-SQL Mini-Dev Soft F1-Score](https://github.com/bird-bench/mini_dev?tab=readme-ov-file#soft-f1-score-evaluation), which computes the cell-level precision and recall between the predicted and ground-truth table, where a cell is only allowed to match cells in the same row. Again, we round all floating point numbers to 3 decimal places before comparison to reduce floating point precision issues.

```python
from rubikbench.metrics import soft_fbeta_score

# Ordered matching (only supported mode)
score = soft_fbeta_score(pd_rows, gt_rows, beta=1.0, ordered=True)

# Strict evaluation: preserve duplicates
score = soft_fbeta_score(pd_rows, gt_rows, beta=1.0, ordered=True, dedup=False)
```

- **β=1.0** (default): Balanced precision/recall
- Partial credit for partially correct rows
- **ordered=True**: Match by position; unordered calls raise an error
- **dedup=True** (default): Drop duplicate rows before scoring
- **dedup=False**: Preserve duplicates for strict evaluation

<br/>

#### BF (Bipartite F-beta Score)

The **Bipartite F-beta score ($BF_{\beta}$)** is a utility-oriented metric for evaluating NL2SQL systems that addresses limitations of exact execution accuracy (EX). Unlike EX, which treats any deviation as a complete failure, $BF_{\beta}$ provides partial credit for semantically correct results, even when they differ in formatting, column order, or include benign extra columns/rows.

This metric is motivated by practical NL2SQL applications where:
- **Recall matters more than precision** (retrieving all required information is more important than avoiding minor extra content)
- **Formatting variations are acceptable** (e.g. different column aliases, additional rank columns in sorted results)
- **Row order should be conditionally enforced** (only when the ground truth contains `ORDER BY` or the query is labelled as order-relevant)

BF is an even more flexible version of SF that uses optimal bipartite matching to align predicted and ground-truth rows instead of computing cell-level precision/recall. This allows BF to better handle cases with extra/missing rows and columns, as well as unordered results.

```python
from rubikbench.metrics import bfbeta_score

# Auto-detect order mode from SQL
score = bfbeta_score(pd_rows, gt_rows, beta=2.0)

# Explicit order mode
score = bfbeta_score(pd_rows, gt_rows, beta=2.0, ordered=True)

# Detect order mode from ground truth SQL
gt_sql = "SELECT ... ORDER BY ..."
score = bfbeta_score(pd_rows, gt_rows, sql=gt_sql, beta=2.0, ordered=None)

# Strict evaluation: preserve duplicates
score = bfbeta_score(pd_rows, gt_rows, beta=2.0, dedup=False)
```

**Parameters:**
- **β=2.0** (default): Favors recall over precision (use β=1.0 for balanced precision/recall)
- **ordered=True**: Uses non-intersecting DP matching (for `ORDER BY` queries)
- **ordered=False**: Uses Hungarian algorithm for bipartite matching (unordered queries)
- **ordered=None** (default): Auto-detect based on the `ORDER BY` clause in ground-truth SQL
- **dedup=True** (default): Drop duplicate rows before scoring
- **dedup=False**: Preserve duplicates for strict evaluation

**Mathematical Formulation**

Given predicted result rows $P = \langle p_1, \dots, p_n \rangle$ and ground truth $G = \langle g_1, \dots, g_m \rangle$, where each row is an unordered multiset of values, we first compute the row-wise $F_\beta$ score for each pair $(p_i, g_j)$:

$$
\begin{aligned}
\text{Pre}_{i,j} &= \frac{1}{|p_i|}\sum_{c \in p_i} \mathbb{I}[c \in g_j] \\
\text{Rec}_{i,j} &= \frac{1}{|g_j|}\sum_{c \in g_j} \mathbb{I}[c \in p_i] \\
w^\beta_{i,j} &= \frac{(1+\beta^2) \cdot \text{Pre}_{i,j} \cdot \text{Rec}_{i,j}}{\beta^2 \cdot \text{Pre}_{i,j} + \text{Rec}_{i,j}}
\end{aligned}
$$

This yields a weighted bipartite graph $\boldsymbol{w}^\beta(P,G)$. The final score uses maximum-weight alignment:

- **Unordered queries** ($Q_{\text{unordered}}$): Weighted Bipartite Matching ($WBM$) via the Hungarian algorithm
- **Ordered queries** ($Q_{\text{ordered}}$): Non-Intersecting WBM ($WBM_{NI}$) via dynamic programming

Finally, the overall Bipartite F-beta score across all queries is computed as:

$$
\text{BF}_{\beta}(P,G) = \frac{1}{|Q|}\left(\sum_{q \in Q_\text{unordered}} \frac{WBM(\boldsymbol{w}^\beta)}{\max(|P|, |G|)} + \sum_{q \in Q_\text{ordered}} \frac{WBM_{NI}(\boldsymbol{w}^\beta)}{\max(|P|, |G|)} \right)
$$

<br/>

### 5.2 Multiple SQL Ground Truths

Queries can have multiple valid SQLs. For example, when asking for two different values, should they be organized as rows or columns? When asking for quarterly trends, should the periods be named `202503`, `202506`, `202509`, `202512` or `Q1`, `Q2`, `Q3`, `Q4`? For such cases, RubikBench allows multiple ground-truth SQLs per query, labelled as `sql`, `sql.1`, `sql.2`, etc. Typically, those SQLs may have different outputs; sometimes different SQLs still produce the same output.

When evaluating, the submission SQL is compared against **all** ground-truth SQL variants, and the **best score** is taken as the final score for that query.

```json
{
    "id": "Q00001",
    "sql": "SELECT SUM(ytd_amt) FROM SALES_LEDGER WHERE sales_region_name_en = 'China'",
    "sql.1": "SELECT sum(ytd_amt) AS 'YTD Amount' FROM SALES_LEDGER WHERE sales_region_name_zh = '中国'",
    "sql.2": "SELECT SUM(ytd_amt) FROM SALES_LEDGER WHERE overseas_flag_name_en = 'Domestic'"
}
```

The evaluator takes the **maximum score** across all SQL variants for a query with multiple ground truths.

> **Warning**: Though multiple SQL ground truths may exist, there may still be many valid SQLs not covered in the ground truth. Therefore, we recommend using the **Bipartite F-beta (BF)** metric as the primary evaluation metric, as it is more tolerant of minor variations in result formatting than Exact Match (EX) or Soft F-beta (SF).

<br/>

## 6. Advanced CLI Usage

### 6.1 CLI Commands Overview

RubikBench provides a comprehensive CLI for evaluation:

```bash
# Show all commands
rubikbench --help

# Show command-specific help
rubikbench eval --help
rubikbench exec --help
rubikbench template --help
rubikbench info --help
rubikbench setup --help
rubikbench test --help
rubikbench browse --help
```

<br/>

### 6.2 Setup Commands

#### Download Database

```bash
# Download RubikBench from HuggingFace (default)
rubikbench setup

# Download BirdSQL MINIDEV from Google Drive
rubikbench setup -B BirdSQL

# Download BirdSQL without the official corrections file
rubikbench setup -B BirdSQL --birdsql-no-corrections

# Download KaggleDBQA from Google Drive
rubikbench setup -B KaggleDBQA

# Download to a custom location
rubikbench setup --data <your_data_path>

# Force re-download even if files exist
rubikbench setup --force

# Remove archives after extraction
rubikbench setup --remove-zip
```

**Default paths (RubikBench)**:
- **Data directory**: `./data/RubikBench/`
- **Queries file**: `./data/RubikBench/queries/RubikBench.json`
- **Database file**: `./data/RubikBench/databases/RubikBench.duckdb`

**Default paths (BirdSQL)**:
- **Data directory**: `./data/BirdSQL/`
- **Queries file**: `./data/BirdSQL/queries/BirdSQL.json`
- **Databases directory**: `./data/BirdSQL/databases/*.sqlite`

**Default paths (KaggleDBQA)**:
- **Data directory**: `./data/KaggleDBQA/`
- **Queries file**: `./data/KaggleDBQA/queries/KaggleDBQA.json`
- **Databases directory**: `./data/KaggleDBQA/databases/*.sqlite`

#### Test Database Connection

```bash
# Test the default RubikBench database
rubikbench test

# Test any specific database file (provider auto-detected from extension)
rubikbench test -db ./data/BirdSQL/databases/financial.sqlite
```

> **Note**: BirdSQL and KaggleDBQA each contain multiple SQLite databases, so `rubikbench test -B BirdSQL` and `rubikbench test -B KaggleDBQA` still require an explicit `-db` path.

<br/>

### 6.3 Query Information

```bash
# Show overall statistics for the default RubikBench queries file
rubikbench info

# Show statistics for another dataset
rubikbench info -B BirdSQL

# Show statistics for a custom queries file
rubikbench info -q ./data/RubikBench/queries/RubikBench.json
```

<br/>

### 6.4 Submission Template

#### Generate Full Template

```bash
# Generate a template for all queries (uses default RubikBench paths)
rubikbench template

# Generate to a custom output file
rubikbench template -out my_submission.json

# Generate a template for another built-in dataset
rubikbench template -B BirdSQL -out birdsql_submission.json
```

#### Generate Filtered Template

```bash
# Only simple queries
rubikbench template --split simple -out simple_only.json

# Filter by tags (any tag matches)
rubikbench template --tags lang-english -out english_only.json

# Multiple tags
rubikbench template -t lang-english -t type-basic -out filtered.json

# Specific queries
rubikbench template --ids Q00001 --ids Q00002 -out subset.json

# Combine filters (multiple difficulty levels and tags)
rubikbench template -s simple -s moderate -t lang-english -out combined.json

# Use a custom queries file
rubikbench template -q ./data/RubikBench/queries/RubikBench.json --split challenging

# Specify a custom SQL placeholder (default is empty string)
rubikbench template --split simple --sql "SELECT 1+1;" -out template_with_default.json

# Combine all features
rubikbench template -q ./data/RubikBench/queries/RubikBench.json -t lang-english -s simple -out submission.json --sql "SELECT * FROM INCOME_ALL LIMIT 1;"
```

<br/>

### 6.5 Evaluation Commands

#### Basic Evaluation

```bash
# Evaluate with default RubikBench paths
rubikbench eval submission.json

# Evaluate with verbose output (progress bar)
rubikbench eval submission.json --verbose

# Evaluate using --input-file instead of the positional argument
rubikbench eval --input-file submission.json
```

#### Filtered Evaluation

```bash
# Evaluate only specific queries
rubikbench eval submission.json --ids Q00001 --ids Q00002 --ids Q00003

# Evaluate by difficulty (using --split)
rubikbench eval submission.json --split simple

# Multiple difficulty levels
rubikbench eval submission.json -s simple -s moderate

# Use custom queries or database paths
rubikbench eval submission.json -q ./data/RubikBench/queries/RubikBench.json -db ./data/RubikBench/databases/RubikBench.duckdb
```

#### Advanced Options

```bash
# Custom beta parameters
rubikbench eval submission.json --bf-beta 3.0 --sf-beta 0.5
rubikbench eval submission.json -bfb 3.0 -sfb 0.5

# Mimic BIRD-style evaluation by dropping duplicate rows before scoring
rubikbench eval submission.json --dedup

# Specify SQL dialect (auto-convert to the target database dialect)
rubikbench eval submission.json --dialect postgres

# Save detailed results
rubikbench eval submission.json --output-file detailed_results.json

# Enable verbose output (progress bar)
rubikbench eval submission.json --verbose
```

**CLI Option Abbreviations**:

| Full Option | Abbreviation | Description |
|-------------|--------------|-------------|
| `--dataset`, `--benchmark` | `-B` | Select the built-in dataset |
| `--input-file` | `-in` | Submission file path (alternative to positional argument) |
| `--queries` | `-q` | Queries file path |
| `--database` | `-db` | Database file path |
| `--output-file` | `-out` | Output JSON path |
| `--ids` | `-i` | Specific query IDs |
| `--split` | `-s` | Filter by difficulty |
| `--bf-beta` | `-bfb` | Beta for BF score |
| `--sf-beta` | `-sfb` | Beta for SF score |
| `--dedup` | | Drop duplicate rows before scoring (BIRD-style behavior) |
| `--no-dedup` | | Preserve duplicates for strict evaluation (CLI default) |
| `--verbose` | `-v` | Enable progress bar |

> **Note**: For BirdSQL and KaggleDBQA, the combined queries files (`BirdSQL.json`, `KaggleDBQA.json`) include benchmark/database metadata, so `rubikbench eval ... -B BirdSQL` and `rubikbench eval ... -B KaggleDBQA` can auto-resolve the correct SQLite database per query. If you use a custom queries file without that metadata, provide `-db` explicitly.

<br/>

### 6.6 Single Query Evaluation

Evaluate and debug individual queries:

```bash
# Evaluate a single RubikBench query against your SQL
rubikbench exec Q00001 \
  "SELECT SUM(ptd_amt_a_cny) FROM INCOME_ALL WHERE period = '202506'"

# Use a custom database path
rubikbench exec Q00001 \
  "SELECT SUM(ptd_amt_a_cny) FROM INCOME_ALL WHERE period = '202506'" \
  -db /path/to/RubikBench.duckdb

# Execute the ground-truth SQL and display the question only
rubikbench exec Q00001

# Execute a SQL string directly
rubikbench exec "SELECT COUNT(*) AS cnt FROM SALES_LEDGER;"
```

When a query file contains `benchmark` and `database` metadata, `rubikbench exec` can also auto-resolve the correct database for multi-database benchmarks.

<br/>

## 7. SQL Dialects

For convenience, RubikBench integrates [SQLGlot](https://github.com/tobymao/sqlglot) to convert SQL queries from other dialects to the target evaluation database.

```bash
# CLI: Specify source dialect
rubikbench eval submission.json -q ./data/RubikBench/queries/RubikBench.json --dialect postgres

# Python API
evaluator = RubikBenchEvaluator(
    db=db,
    queries=queries,
    src="oracle"  # Your SQL dialect
)
```

Or, use the conversion function directly:

```python
from rubikbench.dialect import convert_sql

# Convert Oracle SQL to DuckDB
duckdb_sql = convert_sql(
    "SELECT * FROM users WHERE ROWNUM <= 10",
    source_dialect="oracle",
    target_dialect="duckdb"  # default
)
# Result: "SELECT * FROM users LIMIT 10"
```

For SQL formatting and pretty-printing:

```python
from ahvn.utils.db import prettify_sql

# Prettify a SQL query for better readability
sql = "/* Comments */ SELECT name, COUNT(*) as cnt FROM users WHERE age>18 GROUP BY name ORDER BY cnt DESC"
pretty_sql = prettify_sql(sql, dialect="sqlite", comments=False)
print(pretty_sql)
# Result:
# SELECT
#   `name`,
#   COUNT(*) AS `cnt`
# FROM `users`
# WHERE
#   `age` > 18
# GROUP BY
#   `name`
# ORDER BY
#   `cnt` DESC
```

**Parameters:**
- **query** (`str`): The SQL query to prettify
- **dialect** (`str`): The SQL dialect to use (default: `sqlite`)
- **comments** (`bool`): Whether to keep comments in the output (default: `True`)
- **prefer_backticks** (`bool`): Whether to prefer backticks for identifier quoting when supported (default: `True`)

The `prettify_sql` function uses SQLGlot to format queries with proper indentation, keyword casing, and structural organization. It now prefers backticks by default when the target dialect supports them, while dialects such as DuckDB and PostgreSQL continue to use their native identifier quoting. Pass `prefer_backticks=False` to disable this preference. If formatting fails, it returns the original query stripped of whitespace.

> **Warning**: SQLGlot may not perfectly convert all SQL constructs between dialects, especially for complex queries. Always verify the converted SQL against the target database to ensure correctness.

<br/>

## 8. Integrating External Benchmarks

RubikBench supports a pluggable benchmark architecture. Each benchmark lives under `src/rubikbench/benchmarks/` and exposes a common API so the CLI can treat all benchmarks identically.

### 8.1 Currently Supported Benchmarks

| Benchmark | Database | Source | Setup Command |
| --- | --- | --- | --- |
| **RubikBench** | DuckDB | [GitHub](https://github.com/RubikSQL/RubikBench), [HuggingFace](https://huggingface.co/datasets/Magolor/RubikBench) | `rubikbench setup` |
| **BirdSQL** (MINIDEV) | SQLite | [GitHub](https://github.com/bird-bench/mini_dev), [Google Drive](https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG), [Corrections](https://drive.google.com/file/d/1iWlYVknwK5wGli5lnwg4stvNzMogjhwj) | `rubikbench setup -B BirdSQL` |
| **KaggleDBQA** | SQLite | [GitHub](https://github.com/Chia-Hsuan-Lee/KaggleDBQA), [Google Drive](https://drive.google.com/file/d/1YM3ZK-yyUflnUKWNuduVZxGdwEnQr77c/view?usp=drive_link) | `rubikbench setup -B KaggleDBQA` |

<br/>

### 8.2 How It Works

All benchmark modules follow the same pattern:

1. **Module location**: `src/rubikbench/benchmarks/<name>.py`
2. **Constants and helpers**: Each module defines `DEFAULT_DATA_DIR`, a resolver for default query/database paths, and any source-specific identifiers.
3. **Unified API**: Each module exposes a `setup(data_dir, *, force, remove_zip)` function that handles downloading, extracting, and converting queries.
4. **Query conversion**: External benchmarks convert their native query format into the unified JSON format used by RubikBench (see section 4 for query schema).
5. **Registry**: `benchmarks/__init__.py` registers all benchmarks and exposes helper functions such as `default_data_dir`, `default_queries_path`, and `resolve_db_path`, so the CLI dispatches purely by dataset name.

After setup, all downstream commands (`eval`, `exec`, `info`, `template`, `browse`) work in the same way. For built-in datasets, prefer `-B/--dataset` and let the CLI choose the default queries path and, when metadata is available, auto-resolve the correct database.

<br/>

### 8.3 Example: Evaluating on BirdSQL

```bash
# 1. Download and prepare BirdSQL MINIDEV
rubikbench setup -B BirdSQL

# Or use the original BirdSQL queries without corrections
# rubikbench setup -B BirdSQL --birdsql-no-corrections

# 2. Generate a submission template for BirdSQL queries
rubikbench template -B BirdSQL -out submissions/birdsql.json

# 3. (Fill in your predicted SQL in birdsql.json)

# 4. Evaluate
rubikbench eval submissions/birdsql.json -B BirdSQL --dialect sqlite --verbose

# To imitate BirdSQL's original evaluation behavior more closely, use --dedup
# rubikbench eval submissions/birdsql.json -B BirdSQL --dialect sqlite --dedup --verbose

# Or evaluate against a specific BirdSQL database explicitly
# rubikbench eval submissions/birdsql.json \
#     -q ./data/BirdSQL/queries/financial.json \
#     -db ./data/BirdSQL/databases/financial.sqlite \
#     --dialect sqlite \
#     --verbose

# Test connectivity to a SQLite database if you want
rubikbench test -db ./data/BirdSQL/databases/financial.sqlite
```

> **Note**: Certain queries in BIRD MINIDEV contain a very large SQL result, which may lead to slow evaluation. This typically requires 5 to 10 minutes to complete a full evaluation.

<br/>

### 8.4 Evaluating on KaggleDBQA

```bash
# 1. Download and prepare KaggleDBQA
rubikbench setup -B KaggleDBQA

# 2. Generate a submission template for KaggleDBQA queries
rubikbench template -B KaggleDBQA -out submissions/kaggledbqa.json

# 3. (Fill in your predicted SQL in kaggledbqa.json)

# 4. Evaluate
rubikbench eval submissions/kaggledbqa.json -B KaggleDBQA --dialect sqlite --verbose
```

<br/>

### 8.5 Contributing a New Benchmark

To add support for a new benchmark:

1. Create `src/rubikbench/benchmarks/<name>.py` with:
   - `DEFAULT_DATA_DIR = pj("./data", "<Name>")`
   - `def resolve_db(data_dir: str, db_name: str) -> str`
   - `def setup(data_dir: str, *, force: bool = False, remove_zip: bool = False) -> None`
2. Register it in `src/rubikbench/benchmarks/__init__.py`:
   - Import the `setup` function and the database resolver
   - Add an entry to the `BENCHMARKS` dict
   - Add default-path metadata so the shared CLI helpers can discover the dataset
3. The `setup()` function should:
   - Download the raw data into `data_dir/download/`
   - Extract and organize files into `data_dir/raw/`
   - Convert queries to the unified JSON format in `data_dir/queries/`
   - Normalize database files into `data_dir/databases/`

<br/>

## 9. Update Log

- [2026-04] **RubikBench v0.9.3**:
    - Added MD5 checksum verification for all downloaded benchmark data.
    - Migrated internal utilities to [AgentHeaven](https://github.com/Magolor/AgentHeaven).

- [2025-02] **RubikBench v0.9.2**:
    - Added 3198 queries and query statistics (schema-grounded queries to be added).
    - Integrated BirdSQL MINIDEV benchmark and KaggleDBQA benchmark into RubikBench CLI.
    - Released the RubikBench evaluation toolkit as the open-source Python package [rubikbench](https://pypi.org/project/rubikbench/).

- [2026-02] Updated **RubikBench v0.9.1** database on HuggingFace: [RubikBench](https://huggingface.co/datasets/Magolor/RubikBench).
    - Added support for `.parquet` format.
    - More realistic business logic, reduced the number of products per project.
    - Diversified between `SALES_LEDGER` and `PROFIT_AND_LOSS`.
    - Fixed some geographical region errors.
    - Re-generated all projects and contracts.
    - Expanded to 9 dealers.
    - Fixed `ytd` / `ptd` values.

- [2026-01] Initial release of **RubikBench v0.9** database on HuggingFace: [RubikBench](https://huggingface.co/datasets/Magolor/RubikBench).

<br/>

## 10. Citation

If you find Rubik or RubikBench useful, please cite:

```bibtex
@misc{chen2025rubiksqllifelonglearningagentic,
      title={Rubik: Bridging the NL2SQL Research-to-Production Gap via Lifelong Learning Agentic Knowledge Base},
      author={Zui Chen and Han Li and Xinhao Zhang and Xiaoyu Chen and Chunyin Dong and Yifeng Wang and Xin Cai and Su Zhang and Ziqi Li and Chi Ding and Jinxu Li and Shuai Wang and Dousheng Zhao and Sanhai Gao and Guangyi Liu},
      year={2025},
      eprint={2508.17590},
      archivePrefix={arXiv},
      primaryClass={cs.DB},
      url={https://arxiv.org/abs/2508.17590},
}
```

<br/>
