# RubikBench

[English](README.en.md)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![HuggingFace Dataset](https://img.shields.io/badge/🤗-Dataset-yellow.svg)](https://huggingface.co/datasets/Magolor/RubikBench)

> **数据库主页**: [RubikBench](https://huggingface.co/datasets/Magolor/RubikBench)

RubikBench 是一个面向真实自然语言转 SQL（NL2SQL）研究与评测的企业级金融数据库。

RubikBench 数据库包含一个假想的国际**汽车**制造与销售公司 *APEX* 的**财务**数据。作为财务数据库，它被设计用于支持与公司运营、销售和财务表现相关的各种分析型查询。这个虚构公司主要在中国、美国和欧洲运营。因此，数据库同时包含中英文值，并使用三种货币：CNY、USD 和 EUR。

虽然数据值是合成的，但其 schema 与结构模式都紧密参照真实企业财务数据库建模，因此对 NL2SQL 系统的开发与评测具有实际意义。该数据库专门设计来反映真实企业环境中的复杂性，包括宽表 schema、领域知识、多样化指标与不同口径等。

同时，我们还提供完整的 NL2SQL 评测工具链，即 `rubikbench` Python 包与 CLI，帮助研究者方便地在 RubikBench 上进行评测，也可以评测 BirdSQL（MINIDEV）和 KaggleDBQA 等其他常见数据库基准。

<br/>

## 1. 快速开始

### 1.1 安装

```bash
# 克隆仓库
git clone https://github.com/Magolor/RubikBench.git
cd RubikBench

# 安装依赖
pip install -e .

# 初始化 AgentHeaven
ahvn setup
```

建议安装 [fzf](https://github.com/junegunn/fzf)，以获得更好的 CLI 使用体验。

<br/>

### 1.2 下载数据库

```bash
# 从 HuggingFace 下载 RubikBench（默认）
rubikbench setup

# 从 Google Drive 下载 BirdSQL MINIDEV
rubikbench setup -B BirdSQL

# 从 Google Drive 下载 KaggleDBQA
rubikbench setup -B KaggleDBQA

# 下载到自定义目录
rubikbench setup --data <your_data_path>

# 或者直接克隆完整 HuggingFace 数据集（包含 parquet 文件和统计信息）
# git lfs install
git clone https://huggingface.co/datasets/Magolor/RubikBench ./data/RubikBench
```

**说明**：`rubikbench setup` 会下载数据库压缩包；对于 RubikBench，还会额外准备轻量级查询元数据文件 `./data/RubikBench/queries/RubikBench.json`，因此进行 CLI 评测并不一定需要完整克隆整个数据集。使用 `--remove-zip` 可以在解压后删除下载的压缩包。

<br/>

### 1.3 运行评测

```bash
# 生成提交模板（使用默认的 RubikBench queries 路径）
rubikbench template -out submission.json

# 通常建议先在某一类查询上测试，例如英文查询
rubikbench template --tags lang-english -out submissions/template.json

# 也可以指定自定义 SQL 占位符（默认为空字符串）
rubikbench template --tags lang-english -out submissions/template.json --sql "SELECT 1+1;"

# 然后在 submission.json 中填入你的 SQL 预测结果
# 例如：
# {
#     "Q00001": "SELECT SUM(ptd_amt_a_cny) FROM INCOME_ALL WHERE period = '202506'",
#     "Q00002": "SELECT ...",
#     ...
# }

# 开始评测
rubikbench eval submission.json

# 也可以通过 --input-file 显式传入提交文件
rubikbench eval --input-file submission.json

# 评测指定查询或指定难度
rubikbench eval submission.json --ids Q00001 --ids Q00002
rubikbench eval submission.json --split simple

# 打开详细输出（进度条）
rubikbench eval submission.json --verbose

# 保存详细结果
rubikbench eval submission.json --output-file results.json
```

> **说明**：`rubikbench eval` 只会评测提交文件中实际存在的 query key。如果你只想评测某个子集，请确保提交文件里只保留这些 key。若某些 key 对应的 SQL 为空或为 null，这些查询会被记为失败。
> CLI 在可用时会同时输出 ordered 和 unordered 两类分数；`eval` 命令本身不再提供单独的模式切换参数。
> 一般建议先基于某个特定子集（例如按 tags 或难度）生成模板，这样得到的结果更有意义。
> 例如，默认的 `submissions/template.json` 可以通过 `rubikbench template --tags lang-english -out submissions/template.json` 生成。

<br/>

### 1.4 Python API 示例

```python
from ahvn.utils.db import Database
from rubikbench import RubikBenchEvaluator, QuerySet
from rubikbench.benchmarks import default_database_path, default_queries_path

db = Database(provider="duckdb", database=default_database_path("RubikBench"))
queries = QuerySet(default_queries_path("RubikBench"))

# 创建完整模板（空 SQL 占位）
# queries.create_template("submission_full.json")  # 取消注释即可生成完整模板

# 抽样 10 条查询，并创建带占位 SQL 的模板
sample_queries = queries.sample(n=10, seed=42)
sample_queries.create_template("./submissions/sample.json", placeholder="SELECT 1+1;")

# 评测提交
evaluator = RubikBenchEvaluator(
    db=db,
    queries=queries,
    bf_beta=2.0,
    sf_beta=1.0,
    src="duckdb",   # 你的 SQL 方言；如果不是 DuckDB，会自动通过 SQLGlot 转成 DuckDB
    dedup=False,     # 与 CLI 的严格默认行为保持一致
)
report = evaluator.evaluate_submission(submission="./submissions/sample.json")

# 访问不同难度下的结果
print(f"Overall BF2 Ordered: {report.scores['overall']['bfo']:5.2%}")
print(f"Simple BF2 ordered: {report.scores['simple']['bfo']:5.2%}")
print(f"Moderate BF2 ordered: {report.scores['moderate']['bfo']:5.2%}")
print(f"Challenging BF2 ordered: {report.scores['challenging']['bfo']:5.2%}")

# 访问汇总统计
print(f"Total queries: {report.N['overall']}")
print(f"Compilable: {report.C['overall']}")
print(f"Compilable rate: {report.compilable['overall']:5.2%}")
```

<br/>

### 1.5 RubikBench 浏览 CLI

> **说明**：浏览 CLI 主要针对 RubikBench 做了优化。对于其他数据集，只要 query 元数据和数据库路径可用，也可以工作；但最佳的终端浏览体验仍然是在 RubikBench 上。

安装好 [fzf](https://github.com/junegunn/fzf) 后，可以使用：

```bash
rubikbench browse [-B RubikBench] [--split/-s simple/moderate/challenging/nightmare/unknown] [--tags/-t tag1] [--tags/-t tag2] ...
```

通过终端 UI 交互式浏览并筛选查询。支持按以下条件过滤：
- 难度级别
- 标签
- 问题中的关键词（部分匹配）

可以用鼠标滚动查看较长的问题文本。
输入关键词可实时过滤查询。
使用 `TAB` 切换预览，预览中包含 query 信息、SQL 和执行结果（`rubikbench exec`）。
使用 `CTRL+E` 打开 pager，便于详细查看和复制。
使用 `CTRL+D` 将当前选中 query 的预览复制到剪贴板。

<br/>

## 2. RubikBench 数据库统计

### 2.1 总览

- **总大小**：约 38 GB（DuckDB）/ 约 11 GB（parquet）
- **总表数**：20 张表
- **总记录数**：约 9.0153 亿行
- **时间覆盖范围**：从 2020 年 1 月到 2025 年 12 月，共 72 个月
- **语言**：中英双语
- **数据库格式**：DuckDB Native（推荐）、parquet（用于 HuggingFace）
    - sqlite 等格式不适合承载该数据，因为它们没有压缩能力。完整未压缩数据体积可能超过 500GB。

<br/>

### 2.2 表统计

| 表名 | 行数 | 列数 | Period | Region | Customer | Dealer | Product | Contract | Project | Revenue | Expense |
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

### 2.3 实体统计

| 维度 | 层级数 | 实体总数 |
|-----------|------------------|----------------|
| **Period** | 1 | 72 个月（202001-202512） |
| **Region** | 6 | 2 个内外销标记、11 个销售大区、22 个国家、37 个 national area、46 个省、47 个城市 |
| **Product** | 4 | 3（Lv0）、19（Lv1）、93（Lv2）、353（Lv3） |
| **Customer** | 4 | 4（Lv1）、9（Lv2）、14（Lv3）、22（Lv4） |
| **Dealer** | 3 | 3（Lv1）、5（Lv2）、9（Lv3），包含 `Direct Sales` |
| **Report Item** | 4 | 2（Lv0）、6（Lv1）、10（Lv2）、22（Lv3） |
| **Contract/Project** | 2 | 40,756 个合同、46,895 个项目 |
| **Caliber** | 1 | 2 个口径（A、B） |
| **Currency** | 1 | 3 种货币（CNY、EUR、USD） |

<br/>

### 2.4 数据库说明

RubikBench 包含一个假想国际**汽车**制造与销售公司 *APEX* 的**财务**数据。作为财务数据库，它被设计用于支持与公司运营、销售及财务表现相关的各种分析型查询。这个虚构公司主要在中国、美国和欧洲运营，因此数据库同时包含中英文值，并使用三种货币：CNY、USD 和 EUR。

具体来说，它包含 **6 个核心维度**：*Period*（时间，按月）、*Product*、*Region*、*Customer*、*Dealer* 和 *Report Item*（收入与费用）。此外，还有一些附加维度，包括 *Contract*、*Project*、*Currency* 和 *Caliber*。

数据的最小粒度是一笔**项目**上的**付款**。每个**项目**发生在 APEX 与某个**客户**之间，位于某个特定**地区**，可选地关联一个**经销商**，并发生在某个时间**期间**内。一个项目的付款可以分布在该期间内的多个自然月。每个项目可以包含多个**产品**，每个**合同**也可以包含多个项目。

RubikBench 包含 **20 张表**，分属 **4 类主要表**，这些表都是对底层事实表（未直接暴露）的聚合视图：
- `INCOME` 系列表：按**项目**和**经销商**聚合，只包含收入。它们是 RubikBench 中最小的一组表，适合快速分析型查询。
- `BUDGET_AND_FORECAST` 系列表：按**项目**、**客户**和**经销商**聚合，只包含 amt/forecast/budget/target 等值。需要注意，这些值的语义可能有些反直觉：`YYYYMM` 的 target 表示当月收入与费用目标；而 `YYYYMM` 的 forecast 实际表示截至 `YYYYMM` 月末对 `YYYY12` 全年的预测；`YYYYMM` 的 budget 则是年度预算在每个月上的重复值。
- `PROFIT_AND_LOSS` 表：只按**项目**聚合，维度和指标最为全面，同时包含收入与费用。它是 RubikBench 中最大的一张表，适合精细化财务分析。
- `SALES_LEDGER` 表：粒度最低，为付款级别数据，适合做销售审计和追踪，但只覆盖销售相关的收入和费用。

APEX 的产品分为 **3 大事业部**：*Automobiles*、*Accessories* 和 *Services*。
- *Automobiles* 由企业品牌集团生产，APEX 下共有 **6 个子品牌**。每个品牌组都有自己的 `INCOME` 和 `BUDGET_AND_FORECAST` 表。
- *Accessories* 与 *Services* 各自也有自己的 `INCOME` 和 `BUDGET_AND_FORECAST` 表。Accessories 只包含设备相关收入与成本，Services 只包含服务相关收入与成本。

默认口径是 *A*，它严格区分设备类与服务类报表项，更贴近真实财务统计。为了便于跨事业部协同，也提供了口径 *B*，其定义是将 5% 的服务收入转移到设备收入中。

需要注意的是，受历史原因和查询效率要求影响，不同表中的货币与口径组织方式并不一致。例如，在 `INCOME` 和 `PROFIT_AND_LOSS` 表中，不同货币和口径会编码进不同列的列名后缀（如 `_cny_a`、`_usd_a`、`_eur_b` 等）；而在 `SALES_LEDGER` 与 `BUDGET_AND_FORECAST` 表中，`caliber` 与 `currency` 是独立列，查询时**必须**在谓词中显式过滤，否则会出现重复结果。

财务金额同时提供 `ptd`（当月值）和 `ytd`（年累计值）。例如，`YYYYMM` 的 `ptd` 表示该月金额，而 `YYYYMM` 的 `ytd` 表示从 `YYYY01` 到 `YYYYMM`（含）的累计金额。此外，带 `_py` 的列表示上一年数据。比如，当 `period='YYYYMM'` 时，`ytd` 的上一年列表示从 `YYYY-1 01` 到 `YYYY-1 MM` 的累计金额。

<br/>

## 3. RubikBench 查询统计

RubikBench v0.9.2 包含 **3198** 条经过完整人工核验的查询，覆盖多种金融分析场景，并带有完整标注，包括难度级别、query tags 和用户上下文画像。查询同时使用英文（1,689 条）和中文（1,509 条）编写，以匹配数据库的双语属性。

<br/>

### 3.1 难度分布

| 难度 | 数量 | 占比 | 平均 SQL 长度 | 最短 SQL 长度 | 最长 SQL 长度 |
|------------|------:|---:|---------------:|---------------:|---------------:|
| **Simple** | 1,047 | 32.7% | 218 chars | 11 chars | 1,240 chars |
| **Moderate** | 1,531 | 47.9% | 641 chars | 213 chars | 3,492 chars |
| **Challenging** | 415 | 13.0% | 1,755 chars | 339 chars | 3,635 chars |
| **Nightmare** | 205 | 6.4% | 1,881 chars | 579 chars | 4,183 chars |

<br/>

### 3.2 表覆盖情况

查询覆盖全部 4 大类表（单条查询可能同时涉及多张表）：

| 表类别 | 查询数 | 具体表 |
|----------------|--------:|:---|
| **INCOME_\*** | 1,615 | INCOME_ALL (581), INCOME_WEYMOTCOR (153), INCOME_SHIMOTCOR (142), INCOME_TYRAUTGRO (132), INCOME_ACCESSORY (130), INCOME_NOVDYN (122), INCOME_SERVICE (121), INCOME_GALMOTGRO (120), INCOME_CYBVEHSYS (118) |
| **BUDGET_AND_FORECAST_\*** | 724 | BUDGET_AND_FORECAST_ALL (124), BUDGET_AND_FORECAST_WEYMOTCOR (97), BUDGET_AND_FORECAST_TYRAUTGRO (85), BUDGET_AND_FORECAST_SERVICE (81), BUDGET_AND_FORECAST_SHIMOTCOR (79), BUDGET_AND_FORECAST_NOVDYN (77), BUDGET_AND_FORECAST_ACCESSORY (72), BUDGET_AND_FORECAST_CYBVEHSYS (54), BUDGET_AND_FORECAST_GALMOTGRO (53) |
| **PROFIT_AND_LOSS** | 408 | — |
| **SALES_LEDGER** | 367 | — |

<br/>

### 3.3 SQL 特征分布

| SQL 特征 | 查询数 | 占比 |
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

### 3.4 查询对应职业画像

每条查询都包含一个模拟用户画像，其中有 `occupation` 字段，用来表示现实中可能与这类财务数据交互的角色：

| 职业 | 数量 | 占比 | 描述 |
|------------|------:|---:|-------------|
| **Sales** | 707 | 22.1% | 销售代表与销售经理 |
| **Finance** | 675 | 21.1% | 财务分析师与会计 |
| **Management** | 559 | 17.5% | 管理层与战略决策者 |
| **Guest** | 363 | 11.4% | 权限受限的外部用户 |
| **Developer** | 356 | 11.1% | 技术用户与系统开发者 |
| **Unspecified** | 538 | 16.8% | 未指定职业背景 |

<br/>

## 4. Query 与 Submission 格式

### 4.1 Query 结构

`RubikBench.json` 中的每条 query 遵循如下结构：

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

字段说明：
- **benchmark**：基准名称（例如 `RubikBench`）
- **database**：数据库名称（例如 `RubikBench`）
- **id**：唯一查询标识符
- **question**：自然语言问题
- **context**：上下文信息（例如查询时间、用户画像）
- **schema**：可选 schema 信息（未提供时为 `null`）。如果提供，模型输出 SQL 时应使用 schema 中给出的表名和列名。
- **dialect**：ground-truth SQL 的方言（例如 RubikBench 使用 `duckdb`，BirdSQL / KaggleDBQA 使用 `sqlite`）
- **sql, sql.1, ...**：一个或多个 ground-truth SQL（都视为正确；评测时会取各个变体中的最高分）
- **metadata**：附加元数据，包括：
    - **difficulty**：难度等级（`simple`、`moderate`、`challenging`、`nightmare`）
    - **query_tags**：描述查询特征的标签列表，完整定义见 `query_tags.yaml`。这些标签借助 LLM 进行辅助标注，可能存在错误，欢迎贡献修正。
    - **order-relevant**：查询结果是否与行顺序有关（可以是 `true` / `false`，也可以是 `null`；若为 `null`，评测器会根据标准 ground-truth SQL 中是否存在 `ORDER BY` 自动判断）
    - **verified**：ground-truth SQL 是否经人工核验。RubikBench 官方查询中该字段恒为 true。也欢迎贡献更多已核验查询、等价 SQL 或现有查询修正。

在 NL2SQL 评测中，建议只将 `database`、`question`、`context`、`schema` 和 `dialect` 用作模型输入。`benchmark`、`id`、ground-truth SQL 与 metadata 主要用于评测与分析。对多数据库基准来说，CLI 还会利用 `benchmark` 和 `database` 元数据自动解析数据库路径。

<br/>

### 4.2 Submission 格式

提交文件为一个 JSON，内容是 query ID 到 SQL 字符串的映射：

```json
{
    "Q00001": "SELECT SUM(...) FROM INCOME_ALL WHERE ...",
    "Q00002": "SELECT ... FROM ..."
}
```

<br/>

### 4.3 查询过滤

```python
from rubikbench.queries import QuerySet

queries = QuerySet("./data/RubikBench/queries/RubikBench.json")

# 按难度过滤
simple = queries.filter(difficulty="simple")
moderate = queries.filter(difficulty=["moderate", "challenging"])

# 按指定 ID 过滤
subset = queries.filter(ids=["Q00001", "Q00002", "Q00003"])

# 按标签过滤
monthly = queries.filter(tags=["period-monthly"])

# 组合过滤条件
subset = queries.filter(difficulty="simple", verified_only=True)

# 稳定随机采样：
#   随机抽样 n 条查询。
#   我们使用 AgentHeaven 的基于哈希的采样方式来保证可复现性。这意味着在固定 seed 下，
#   如果你先采样 n 条，再采样 m > n 条，那么前 n 条一定包含在后 m 条中。
#   这种方式也对 query set 的增删更稳健（例如新增查询不会导致原有样本大幅变化）。
#   如果你要在过滤后的子集上做采样，请先 filter，再手动调用：
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

## 5. 评测

### 5.1 评测指标说明

RubikBench 会对每条 query 计算 **5 种指标变体**（unordered SF 已废弃）：

| 指标 | 说明 |
|--------|-------------|
| **EX** | Exact Match，二值分数（0 或 1） |
| **BF** | Bipartite F-beta，连续分数 [0, 1] |
| **SF** | Soft F-beta（仅 ordered），连续分数 [0, 1] |

每类指标在适用时都有 **Ordered (o)** 和 **Unordered (u)** 两种变体：
- **Ordered (`o`)**：考虑结果行顺序（仅对顺序敏感的查询有意义）
- **Unordered (`u`)**：忽略结果行顺序，按多重集进行比较。注意：SF 的 unordered 版本没有良好定义，因此不支持。

评测报告中会展示：
- **N**：参与评测的查询总数
- **C**：可编译 SQL 数量（即执行时没有报错）
- **compilable**：C/N 比例
- **scores**：得分达到 99.99% 以上的查询数占 N 的比例

内置 benchmark 的所有 ground-truth 结果都保证最多返回 1000 行。如果预测结果或 ground-truth 结果超过 **1000** 行，会打印**警告**，评测仍会继续（但可能较慢，甚至占用较多内存；在某些慢场景下 BF 会退化使用 SF）。对于自定义数据集，我们不建议 ground-truth 查询返回超过 1000 行，因为会影响评测效率，可考虑适当添加 `LIMIT`。

我们尽量复现 BIRD 的评测思路，但原始 BIRD 的 EX 和 SF 实现存在缺陷：它会把结果表当作“行的集合”来处理，也就是默认去重。RubikBench 修正了这一点，将结果视作“行的多重集”处理。CLI 因而默认采用严格的多重集评测（`--no-dedup`）；而底层指标函数和 `RubikBenchEvaluator` 仍然保持 `dedup=True` 的库级默认值，除非你显式传入 `dedup=False`。如果你希望尽量贴近 BIRD 原始行为，可以在 CLI 中使用 `--dedup`。

<br/>

#### EX（Execution Accuracy）

EX 是 0/1 二值指标，用于判断预测结果是否与 ground truth 完全一致。

**unordered** EX 的行为与 [BIRD-SQL EX Accuracy](https://github.com/AlibabaResearch/DAMO-ConvAI/blob/main/bird/llm/src/evaluation.py#L26) 类似：只比较两组结果行的集合是否一致（每一行被视作有序 tuple，忽略列名）。由于 RubikBench 主要涉及数值计算，我们会先将浮点数统一四舍五入到 3 位小数，再做比较，以减轻浮点精度问题。

```python
from rubikbench.metrics import ex_match

# 无序比较（默认，带 dedup）
score = ex_match(pd_rows, gt_rows)  # 返回 0 或 1

# 有序比较（保留行顺序）
score = ex_match(pd_rows, gt_rows, ordered=True)

# 严格评测：保留重复行
score = ex_match(pd_rows, gt_rows, dedup=False)

# 模拟 BIRD 原始实现中无序比较的缺陷行为
score = ex_match(pd_rows, gt_rows, ordered=False, fixed=False, dedup=False)
```

- **ordered=False**（默认）：按多重集比较，忽略行顺序
- **ordered=True**：逐行按位置比较
- **dedup=True**（默认）：比较前先去重
- **dedup=False**：保留重复行，进行更严格的比较

<br/>

#### SF（Soft F-beta Score）

Soft F-beta 是更宽松的指标，会对“部分正确”的结果给予部分分数。它只支持 **ordered** 版本。

**ordered** SF（β=1.0）与 [BIRD-SQL Mini-Dev Soft F1-Score](https://github.com/bird-bench/mini_dev?tab=readme-ov-file#soft-f1-score-evaluation) 的思想类似：它比较预测表与 ground-truth 表在单元格层面的 precision 和 recall，其中一个单元格只能与同一行中的单元格匹配。同样，我们会先把浮点数统一四舍五入到 3 位小数，以减少浮点误差带来的影响。

```python
from rubikbench.metrics import soft_fbeta_score

# 有序匹配（唯一支持的模式）
score = soft_fbeta_score(pd_rows, gt_rows, beta=1.0, ordered=True)

# 严格评测：保留重复行
score = soft_fbeta_score(pd_rows, gt_rows, beta=1.0, ordered=True, dedup=False)
```

- **β=1.0**（默认）：precision / recall 平衡
- 对“部分正确”的行给予部分分数
- **ordered=True**：按位置对齐；unordered 调用会直接报错
- **dedup=True**（默认）：打分前先去重
- **dedup=False**：保留重复行，进行更严格的评测

<br/>

#### BF（Bipartite F-beta Score）

**Bipartite F-beta score（$BF_{\beta}$）** 是一种更偏实用导向的 NL2SQL 评测指标，用于弥补 EX 的不足。与 EX 把任何偏差都视为完全失败不同，$BF_{\beta}$ 会对语义上正确但在格式、列顺序、或带有无害多余列/行的结果给予部分分数。

该指标特别适用于以下现实场景：
- **召回比精度更重要**：先拿全用户真正需要的信息，比避免少量无害冗余更重要
- **格式差异可以接受**：例如列别名不同，或排序结果中附带额外排名列
- **是否要求顺序要有条件地判断**：只有当 ground truth 显式包含 `ORDER BY`，或 query 被标注为顺序敏感时，才需要严格比较行顺序

BF 可以视为比 SF 更灵活的版本。它不再通过单元格级 precision / recall 来对齐，而是使用最优二分图匹配来对齐预测行与 ground-truth 行。因此，它更适合处理缺失/多余行、缺失/多余列以及无序结果等场景。

```python
from rubikbench.metrics import bfbeta_score

# 根据 SQL 自动判断是否考虑顺序
score = bfbeta_score(pd_rows, gt_rows, beta=2.0)

# 显式指定有序模式
score = bfbeta_score(pd_rows, gt_rows, beta=2.0, ordered=True)

# 根据 ground-truth SQL 判断顺序模式
gt_sql = "SELECT ... ORDER BY ..."
score = bfbeta_score(pd_rows, gt_rows, sql=gt_sql, beta=2.0, ordered=None)

# 严格评测：保留重复行
score = bfbeta_score(pd_rows, gt_rows, beta=2.0, dedup=False)
```

**参数说明：**
- **β=2.0**（默认）：更偏重召回；若希望 precision / recall 平衡，可使用 β=1.0
- **ordered=True**：对 `ORDER BY` 查询使用非交叉 DP 匹配
- **ordered=False**：对无序查询使用匈牙利算法做二分图匹配
- **ordered=None**（默认）：根据 ground-truth SQL 中是否出现 `ORDER BY` 自动判断
- **dedup=True**（默认）：打分前先去重
- **dedup=False**：保留重复行，进行更严格的评测

**数学定义**

设预测结果行为 $P = \langle p_1, \dots, p_n \rangle$，ground truth 为 $G = \langle g_1, \dots, g_m \rangle$，其中每一行都视作“值的无序多重集”。首先，对任意一对 $(p_i, g_j)$ 计算其行级 $F_\beta$ 分数：

$$
\begin{aligned}
\text{Pre}_{i,j} &= \frac{1}{|p_i|}\sum_{c \in p_i} \mathbb{I}[c \in g_j] \\
\text{Rec}_{i,j} &= \frac{1}{|g_j|}\sum_{c \in g_j} \mathbb{I}[c \in p_i] \\
w^\beta_{i,j} &= \frac{(1+\beta^2) \cdot \text{Pre}_{i,j} \cdot \text{Rec}_{i,j}}{\beta^2 \cdot \text{Pre}_{i,j} + \text{Rec}_{i,j}}
\end{aligned}
$$

于是可得到一个加权二分图 $\boldsymbol{w}^\beta(P,G)$。最终得分通过最大权对齐得到：

- **无序查询**（$Q_{\text{unordered}}$）：使用匈牙利算法求加权二分图匹配（$WBM$）
- **有序查询**（$Q_{\text{ordered}}$）：使用动态规划求非交叉匹配（$WBM_{NI}$）

最终，整体 Bipartite F-beta 分数定义为：

$$
\text{BF}_{\beta}(P,G) = \frac{1}{|Q|}\left(\sum_{q \in Q_\text{unordered}} \frac{WBM(\boldsymbol{w}^\beta)}{\max(|P|, |G|)} + \sum_{q \in Q_\text{ordered}} \frac{WBM_{NI}(\boldsymbol{w}^\beta)}{\max(|P|, |G|)} \right)
$$

<br/>

### 5.2 多个 SQL Ground Truth

一条查询可能对应多个合法 SQL。例如，当问题要求返回两个不同数值时，结果既可以组织成多行，也可以组织成多列；对于季度趋势，period 既可以写成 `202503`、`202506`、`202509`、`202512`，也可以写成 `Q1`、`Q2`、`Q3`、`Q4`。因此，RubikBench 允许每条 query 对应多个 ground-truth SQL，分别命名为 `sql`、`sql.1`、`sql.2` 等。这些 SQL 的输出可能不同，也可能不同 SQL 最终产生相同结果。

评测时，提交 SQL 会与**所有** ground-truth SQL 变体逐一比较，并取**最高分**作为该 query 的最终分数。

```json
{
    "id": "Q00001",
    "sql": "SELECT SUM(ytd_amt) FROM SALES_LEDGER WHERE sales_region_name_en = 'China'",
    "sql.1": "SELECT sum(ytd_amt) AS 'YTD Amount' FROM SALES_LEDGER WHERE sales_region_name_zh = '中国'",
    "sql.2": "SELECT SUM(ytd_amt) FROM SALES_LEDGER WHERE overseas_flag_name_en = 'Domestic'"
}
```

对于含有多个 ground-truth SQL 的 query，评测器会取所有变体中的**最大分数**。

> **警告**：即使已经提供多个 ground-truth SQL，仍然可能存在更多合法 SQL 未被覆盖。因此，我们建议优先参考 **Bipartite F-beta（BF）** 指标，因为它相比 Exact Match（EX）和 Soft F-beta（SF）更能容忍输出格式上的轻微差异。

<br/>

## 6. 高级 CLI 用法

### 6.1 CLI 命令总览

RubikBench 提供了一套完整 CLI 用于评测：

```bash
# 查看所有命令
rubikbench --help

# 查看子命令帮助
rubikbench eval --help
rubikbench exec --help
rubikbench template --help
rubikbench info --help
rubikbench setup --help
rubikbench test --help
rubikbench browse --help
```

<br/>

### 6.2 Setup 命令

#### 下载数据库

```bash
# 下载 RubikBench（默认）
rubikbench setup

# 下载 BirdSQL MINIDEV
rubikbench setup -B BirdSQL

# 下载 BirdSQL，但跳过官方 corrections 文件
rubikbench setup -B BirdSQL --birdsql-no-corrections

# 下载 KaggleDBQA
rubikbench setup -B KaggleDBQA

# 下载到自定义目录
rubikbench setup --data <your_data_path>

# 即使文件已存在也强制重新下载
rubikbench setup --force

# 解压完成后删除压缩包
rubikbench setup --remove-zip
```

**RubikBench 默认路径**：
- **数据目录**：`./data/RubikBench/`
- **Queries 文件**：`./data/RubikBench/queries/RubikBench.json`
- **数据库文件**：`./data/RubikBench/databases/RubikBench.duckdb`

**BirdSQL 默认路径**：
- **数据目录**：`./data/BirdSQL/`
- **Queries 文件**：`./data/BirdSQL/queries/BirdSQL.json`
- **数据库目录**：`./data/BirdSQL/databases/*.sqlite`

**KaggleDBQA 默认路径**：
- **数据目录**：`./data/KaggleDBQA/`
- **Queries 文件**：`./data/KaggleDBQA/queries/KaggleDBQA.json`
- **数据库目录**：`./data/KaggleDBQA/databases/*.sqlite`

#### 测试数据库连接

```bash
# 测试默认 RubikBench 数据库
rubikbench test

# 测试任意指定数据库文件（根据扩展名自动识别 provider）
rubikbench test -db ./data/BirdSQL/databases/financial.sqlite
```

> **说明**：BirdSQL 和 KaggleDBQA 都包含多份 SQLite 数据库，因此 `rubikbench test -B BirdSQL` 和 `rubikbench test -B KaggleDBQA` 仍然需要显式传入 `-db`。

<br/>

### 6.3 Query 信息

```bash
# 查看默认 RubikBench queries 文件的统计信息
rubikbench info

# 查看其他内置数据集的统计信息
rubikbench info -B BirdSQL

# 查看自定义 queries 文件的统计信息
rubikbench info -q ./data/RubikBench/queries/RubikBench.json
```

<br/>

### 6.4 Submission 模板

#### 生成完整模板

```bash
# 为所有查询生成模板（默认使用 RubikBench 路径）
rubikbench template

# 输出到自定义文件
rubikbench template -out my_submission.json

# 为其他内置数据集生成模板
rubikbench template -B BirdSQL -out birdsql_submission.json
```

#### 生成过滤后的模板

```bash
# 只包含 simple 查询
rubikbench template --split simple -out simple_only.json

# 按 tag 过滤（任意 tag 命中即可）
rubikbench template --tags lang-english -out english_only.json

# 多个 tag
rubikbench template -t lang-english -t type-basic -out filtered.json

# 指定查询 ID
rubikbench template --ids Q00001 --ids Q00002 -out subset.json

# 组合过滤条件（多难度 + 多标签）
rubikbench template -s simple -s moderate -t lang-english -out combined.json

# 使用自定义 queries 文件
rubikbench template -q ./data/RubikBench/queries/RubikBench.json --split challenging

# 指定自定义 SQL 占位符（默认为空字符串）
rubikbench template --split simple --sql "SELECT 1+1;" -out template_with_default.json

# 组合所有特性
rubikbench template -q ./data/RubikBench/queries/RubikBench.json -t lang-english -s simple -out submission.json --sql "SELECT * FROM INCOME_ALL LIMIT 1;"
```

<br/>

### 6.5 Evaluation 命令

#### 基础评测

```bash
# 使用默认 RubikBench 路径评测
rubikbench eval submission.json

# 打开详细输出（进度条）
rubikbench eval submission.json --verbose

# 使用 --input-file 代替位置参数
rubikbench eval --input-file submission.json
```

#### 过滤评测

```bash
# 只评测指定查询
rubikbench eval submission.json --ids Q00001 --ids Q00002 --ids Q00003

# 按难度评测
rubikbench eval submission.json --split simple

# 多个难度级别
rubikbench eval submission.json -s simple -s moderate

# 使用自定义 queries 或数据库路径
rubikbench eval submission.json -q ./data/RubikBench/queries/RubikBench.json -db ./data/RubikBench/databases/RubikBench.duckdb
```

#### 高级选项

```bash
# 自定义 beta 参数
rubikbench eval submission.json --bf-beta 3.0 --sf-beta 0.5
rubikbench eval submission.json -bfb 3.0 -sfb 0.5

# 使用 BIRD 风格评测：评分前先去重
rubikbench eval submission.json --dedup

# 指定提交 SQL 的方言（会自动转换到目标数据库方言）
rubikbench eval submission.json --dialect postgres

# 保存详细结果
rubikbench eval submission.json --output-file detailed_results.json

# 打开详细输出（进度条）
rubikbench eval submission.json --verbose
```

**CLI 参数缩写**：

| 完整参数 | 缩写 | 说明 |
|-------------|--------------|-------------|
| `--dataset`, `--benchmark` | `-B` | 选择内置数据集 |
| `--input-file` | `-in` | 提交文件路径（可替代位置参数） |
| `--queries` | `-q` | Queries 文件路径 |
| `--database` | `-db` | 数据库文件路径 |
| `--output-file` | `-out` | 输出 JSON 路径 |
| `--ids` | `-i` | 指定 query ID |
| `--split` | `-s` | 按难度过滤 |
| `--bf-beta` | `-bfb` | BF 分数的 beta 参数 |
| `--sf-beta` | `-sfb` | SF 分数的 beta 参数 |
| `--dedup` | | 打分前先去重（更接近 BIRD 原始行为） |
| `--no-dedup` | | 保留重复行，进行严格评测（CLI 默认） |
| `--verbose` | `-v` | 打开进度条 |

> **说明**：对于 BirdSQL 和 KaggleDBQA，组合查询文件（`BirdSQL.json`、`KaggleDBQA.json`）已经包含 `benchmark` / `database` 元数据，因此可以直接用 `rubikbench eval ... -B BirdSQL` 或 `rubikbench eval ... -B KaggleDBQA` 让 CLI 自动按 query 解析对应 SQLite 数据库。如果你使用的是不含这些元数据的自定义 queries 文件，则需要显式传入 `-db`。

<br/>

### 6.6 单条查询评测

可以使用以下方式对单条查询做调试与评测：

```bash
# 用你的 SQL 评测一条 RubikBench 查询
rubikbench exec Q00001 \
  "SELECT SUM(ptd_amt_a_cny) FROM INCOME_ALL WHERE period = '202506'"

# 使用自定义数据库路径
rubikbench exec Q00001 \
  "SELECT SUM(ptd_amt_a_cny) FROM INCOME_ALL WHERE period = '202506'" \
  -db /path/to/RubikBench.duckdb

# 只执行 ground-truth SQL，并显示 query 信息
rubikbench exec Q00001

# 直接执行一段 SQL
rubikbench exec "SELECT COUNT(*) AS cnt FROM SALES_LEDGER;"
```

当 query 文件中包含 `benchmark` 和 `database` 元数据时，`rubikbench exec` 也可以在多数据库 benchmark 中自动解析对应数据库。

<br/>

## 7. SQL 方言

为了方便使用，RubikBench 集成了 [SQLGlot](https://github.com/tobymao/sqlglot)，可将其他 SQL 方言转换到目标评测数据库的方言。

```bash
# CLI：指定提交 SQL 的源方言
rubikbench eval submission.json -q ./data/RubikBench/queries/RubikBench.json --dialect postgres

# Python API
evaluator = RubikBenchEvaluator(
    db=db,
    queries=queries,
    src="oracle"  # 你的 SQL 方言
)
```

也可以直接调用转换函数：

```python
from rubikbench.dialect import convert_sql

# 将 Oracle SQL 转为 DuckDB
duckdb_sql = convert_sql(
    "SELECT * FROM users WHERE ROWNUM <= 10",
    source_dialect="oracle",
    target_dialect="duckdb"  # 默认值
)
# 结果: "SELECT * FROM users LIMIT 10"
```

如果你想对 SQL 做格式化和美化输出：

```python
from ahvn.utils.db import prettify_sql

# 对 SQL 做美化，便于阅读
sql = "/* Comments */ SELECT name, COUNT(*) as cnt FROM users WHERE age>18 GROUP BY name ORDER BY cnt DESC"
pretty_sql = prettify_sql(sql, dialect="sqlite", comments=False)
print(pretty_sql)
# 结果:
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

**参数说明：**
- **query**（`str`）：待格式化的 SQL
- **dialect**（`str`）：格式化时使用的 SQL 方言（默认 `sqlite`）
- **comments**（`bool`）：是否保留注释（默认 `True`）
- **prefer_backticks**（`bool`）：在方言支持时是否优先使用反引号包裹标识符（默认 `True`）

`prettify_sql` 底层使用 SQLGlot 对查询进行格式化，包括缩进、关键字大小写和结构整理。现在它在目标方言支持时会默认优先使用反引号；而 DuckDB、PostgreSQL 等不支持该偏好的方言仍会保持各自原生的标识符引用方式。传入 `prefer_backticks=False` 可以关闭这一偏好。如果格式化失败，它会返回去除多余空白后的原始 SQL。

> **警告**：SQLGlot 不能保证完美转换所有方言特性，尤其是复杂查询。请务必在目标数据库上验证转换后的 SQL 是否正确。

<br/>

## 8. 集成外部 Benchmark

RubikBench 支持可插拔 benchmark 架构。每个 benchmark 都位于 `src/rubikbench/benchmarks/` 下，并通过统一接口暴露能力，因此 CLI 可以用一致的方式处理它们。

### 8.1 当前支持的 Benchmark

| Benchmark | 数据库 | 来源 | Setup 命令 |
| --- | --- | --- | --- |
| **RubikBench** | DuckDB | [GitHub](https://github.com/RubikSQL/RubikBench), [HuggingFace](https://huggingface.co/datasets/Magolor/RubikBench) | `rubikbench setup` |
| **BirdSQL** (MINIDEV) | SQLite | [GitHub](https://github.com/bird-bench/mini_dev), [Google Drive](https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG), [Corrections](https://drive.google.com/file/d/1iWlYVknwK5wGli5lnwg4stvNzMogjhwj) | `rubikbench setup -B BirdSQL` |
| **KaggleDBQA** | SQLite | [GitHub](https://github.com/Chia-Hsuan-Lee/KaggleDBQA), [Google Drive](https://drive.google.com/file/d/1YM3ZK-yyUflnUKWNuduVZxGdwEnQr77c/view?usp=drive_link) | `rubikbench setup -B KaggleDBQA` |

<br/>

### 8.2 工作方式

所有 benchmark 模块基本遵循同样的模式：

1. **模块位置**：`src/rubikbench/benchmarks/<name>.py`
2. **常量与辅助函数**：每个模块定义 `DEFAULT_DATA_DIR`、默认 query / database 路径解析逻辑，以及各自的数据源标识。
3. **统一 API**：每个模块都暴露 `setup(data_dir, *, force, remove_zip)`，负责下载、解压和转换 queries。
4. **查询转换**：外部 benchmark 会将原生 query 格式转换为 RubikBench 使用的统一 JSON 格式（参见第 4 节）。
5. **注册表**：`benchmarks/__init__.py` 会注册所有 benchmark，并提供 `default_data_dir`、`default_queries_path`、`resolve_db_path` 等辅助函数，CLI 因此可以只根据 dataset 名称进行统一调度。

完成 setup 后，后续命令（`eval`、`exec`、`info`、`template`、`browse`）的用法是一致的。对于内置数据集，优先使用 `-B/--dataset`，让 CLI 自动选择默认 queries 路径，并在有元数据时自动解析对应数据库。

<br/>

### 8.3 示例：在 BirdSQL 上评测

```bash
# 1. 下载并准备 BirdSQL MINIDEV
rubikbench setup -B BirdSQL

# 如果你想跳过官方 corrections，也可以这样做
# rubikbench setup -B BirdSQL --birdsql-no-corrections

# 2. 为 BirdSQL 生成提交模板
rubikbench template -B BirdSQL -out submissions/birdsql.json

# 3. （在 birdsql.json 中填入你的 SQL 预测结果）

# 4. 开始评测
rubikbench eval submissions/birdsql.json -B BirdSQL --dialect sqlite --verbose

# 如果你想更接近 BirdSQL 原始评测行为，可以使用 --dedup
# rubikbench eval submissions/birdsql.json -B BirdSQL --dialect sqlite --dedup --verbose

# 或者也可以显式指定某个 BirdSQL 数据库来评测
# rubikbench eval submissions/birdsql.json \
#     -q ./data/BirdSQL/queries/financial.json \
#     -db ./data/BirdSQL/databases/financial.sqlite \
#     --dialect sqlite \
#     --verbose

# 如有需要，也可以测试某个 SQLite 数据库的连通性
rubikbench test -db ./data/BirdSQL/databases/financial.sqlite
```

> **说明**：BIRD MINIDEV 中某些查询的 SQL 结果非常大，因此完整评测可能较慢，通常需要 5 到 10 分钟。

<br/>

### 8.4 示例：在 KaggleDBQA 上评测

```bash
# 1. 下载并准备 KaggleDBQA
rubikbench setup -B KaggleDBQA

# 2. 为 KaggleDBQA 生成提交模板
rubikbench template -B KaggleDBQA -out submissions/kaggledbqa.json

# 3. （在 kaggledbqa.json 中填入你的 SQL 预测结果）

# 4. 开始评测
rubikbench eval submissions/kaggledbqa.json -B KaggleDBQA --dialect sqlite --verbose
```

<br/>

### 8.5 贡献新的 Benchmark

如果你想添加一个新的 benchmark 支持：

1. 在 `src/rubikbench/benchmarks/<name>.py` 中创建模块，并至少包含：
   - `DEFAULT_DATA_DIR = pj("./data", "<Name>")`
   - `def resolve_db(data_dir: str, db_name: str) -> str`
   - `def setup(data_dir: str, *, force: bool = False, remove_zip: bool = False) -> None`
2. 在 `src/rubikbench/benchmarks/__init__.py` 中注册它：
   - 导入 `setup` 函数和数据库 resolver
   - 在 `BENCHMARKS` 字典中添加条目
   - 补充默认路径元数据，让共享 CLI helper 可以识别该数据集
3. `setup()` 函数应当完成以下工作：
   - 将原始数据下载到 `data_dir/download/`
   - 解压并整理到 `data_dir/raw/`
   - 将 query 转换到统一 JSON 格式并写入 `data_dir/queries/`
   - 将数据库文件规范化放入 `data_dir/databases/`

<br/>

## 9. 更新日志

- [2026-04] **RubikBench v0.9.3**：
    - 新增 MD5 校验，验证所有下载的 benchmark 数据完整性。
    - 内部工具迁移至 [AgentHeaven](https://github.com/Magolor/AgentHeaven) 框架。

- [2025-02] **RubikBench v0.9.2**：
    - 新增 3198 条查询及对应统计（schema-grounded queries 将后续补充）。
    - 在 RubikBench CLI 中集成 BirdSQL MINIDEV 和 KaggleDBQA benchmark。
    - 发布开源 Python 包 [rubikbench](https://pypi.org/project/rubikbench/)。

- [2026-02] 在 HuggingFace 更新 **RubikBench v0.9.1** 数据库：[RubikBench](https://huggingface.co/datasets/Magolor/RubikBench)。
    - 新增 `.parquet` 格式支持。
    - 业务逻辑更加真实，并减少单个项目包含的产品数量。
    - 加强 `SALES_LEDGER` 与 `PROFIT_AND_LOSS` 之间的差异化。
    - 修复部分地理区域错误。
    - 重新生成全部项目与合同。
    - 扩展到 9 个经销商。
    - 修复 `ytd` / `ptd` 数据。

- [2026-01] 在 HuggingFace 首次发布 **RubikBench v0.9** 数据库：[RubikBench](https://huggingface.co/datasets/Magolor/RubikBench)。

<br/>

## 10. 引用

如果 Rubik 或 RubikBench 对你有帮助，请引用：

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
