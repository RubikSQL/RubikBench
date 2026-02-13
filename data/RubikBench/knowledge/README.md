# RubikBench

## Database Description

RubikBench is a database containing the **financial** data of *APEX*, an (imaginary) international **automobile** manufacturing and sales company. As a financial database, it is designed to support various analytical queries related to the company's operations, sales, and financial performance. This (imaginary) company operates mainly in China, the United States, and Europe. Therefore the database is bilingual, with both English and Chinese values, and uses three currencies: CNY, USD, and EUR.

Specifically, there are **6 key dimensions**: *Period* (time, monthly), *Product*, *Region*, *Customer*, *Dealer*, and *Report Item* (revenues and expenses). Also, there are extra dimensions including: *Contract*, *Project*, *Currency*, and *Caliber*.

The minimal granularity of the data is a **payment** of a **project**. Each **project** happens between APEX and a **customer** at a specific **region**, with an optional **dealer**, over a **period** of time. Payments of a project can be distributed over multiple months in that time period. Each project may contain multiple **products**. Each **contract** may contain multiple projects.

RubikBench contains **20 tables** of **4 major categories**, all of them are aggregated views over the fact table (which is not exposed directly):
- The `INCOME` tables, which contain data aggregated over **project** and **dealer**, and only includes revenues. The INCOME tables are the smallest tables in RubikBench, aiming for quick analytical queries.
- The `BUDGET_AND_FORECAST` tables, which contain data aggregated over **project**, **customer**, and **dealer**. These tables contain amt/forecast/budget/target values. Notice that the semantics of these values could be counter-intuitive: While the target value is the target for monthly revenues and expenses in `YYYYMM`, as one would expect; the forecast value of `YYYYMM` is the forecast of `YYYY12` (yearly) based on the information available at the end of `YYYYMM`; the budget of `YYYYMM` is a constant value indicating the yearly budget duplicated for each month in the year.
- The `PROFIT_AND_LOSS` table, which contains data aggregated only over **project**. It contains the most comprehensive dimensions and measures, including both revenues and expenses. It is the largest table in RubikBench, aiming to support detailed financial analysis.
- The `SALES_LEDGER` table, which contains the lowest granularity data, i.e., payment-level data. It is designed to support detailed audit and traceability of sales. However, it is limited to sales-related revenues and expenses only.

The products of APEX are divided into **3 major divisions**: *Automobiles*, *Accessories*, and *Services*.
- *Automobiles* are produced by enterprise brand groups, which are **6 sub-brands** under APEX. Each brand group has its own `INCOME` and `BUDGET_AND_FORECAST` tables.
- *Accessories* and *Services* each have their own `INCOME` and `BUDGET_AND_FORECAST` tables. Accessories only have equipment revenues and costs, while services only have service revenues and costs.

The default Caliber is code *A*, which clearly separates equipment and service report items, reflecting the real financial statistics. However, to facilitate the cooperation between different divisions, there are also Caliber *B*, which moves 5% of service revenue to equipment revenue.

Notice that due to historical reasons as well as query efficiency expectations, currencies and calibers are organized differently across different tables. For example, for the INCOME and PROFIT_AND_LOSS tables, different currencies and calibers are stored in different columns as column name suffixes (e.g., `_cny_a`, `_usd_a`, `_eur_b`, etc.); while for the SALES_LEDGER and BUDGET_AND_FORECAST tables, `caliber` and `currency` are separate columns that MUST be filtered on in the query predicates to avoid duplicated results.

Financial amounts presents both `ptd` (monthly) values and `ytd` (year-to-date) values. For example, `ptd` of `YYYYMM` means the amount for that month, while `ytd` of `YYYYMM` means the cumulative amount from `YYYY01` to `YYYYMM` (inclusive). Furthermore, `_py` columns contain previous year data, which means that, for exammple, `ytd` py columns with `period='YYYYMM'` contain cumulative amounts from `YYYY-1 01` to `YYYY-1 MM`, etc.

<br/>
