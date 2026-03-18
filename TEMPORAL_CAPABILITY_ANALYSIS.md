# CISSA Temporal Capability Analysis

## Executive Summary

**Temporal capability** in CISSA refers to the ability to calculate metrics at different time horizons or using different rolling window periods. It is NOT about a single time dimension but rather how calculations aggregate or normalize data across multiple fiscal years.

### Key Concept
Temporal capability enables metrics to be computed with **rolling windows** of different lengths (1Y, 3Y, 5Y, 10Y), where each window represents the number of years used in averaging or aggregation calculations.

---

## 1. What "Temporal Capability" Means in CISSA

### Definition
**Temporal capability** = The ability to calculate metrics using rolling time-series windows to smooth volatility and capture different trend horizons.

### NOT About
- Real-time streaming (all calculations are batch-based)
- Intraday or sub-daily periods (all data is fiscal-year or monthly)
- Point-in-time snapshots at arbitrary dates (all data aligned to fiscal year ends)

### IS About
**Rolling windows** that aggregate data across multiple years:
- **1Y (Single Year)**: No rolling average, just current year value
- **3Y (3-Year Rolling)**: Average of current year + 2 prior years
- **5Y (5-Year Rolling)**: Average of current year + 4 prior years  
- **10Y (10-Year Rolling)**: Average of current year + 9 prior years

---

## 2. Temporal Capability Implementation by Metric Type

### A. Beta (Phase 07) - Pre-computed with Rolling OLS

**Temporal Strategy:** Rolling monthly windows (60-month lookback for OLS regression)

**Implementation:**
- **Monthly rolling window**: 60 consecutive months of returns
- **Window shifts monthly**: Each calendar month gets its own 60-month OLS calculation
- **Result stored**: One Beta value per fiscal year (annualized from monthly calculations)
- **Pre-computation timing**: Calculated at data ingestion (Pipeline Phase 07), not at runtime
- **Data granularity**: Monthly COMPANY_TSR and INDEX_TSR → 60-month OLS slopes

**SQL Pattern:**
```python
# From beta_precomputation_service.py
"Calculate rolling OLS slopes (60-month window)"
# Window: ROWS BETWEEN 59 PRECEDING AND CURRENT ROW
```

**Storage Schema:**
```sql
metrics_outputs(
  dataset_id UUID,
  param_set_id UUID (NULL for pre-computed),
  ticker TEXT,
  fiscal_year INTEGER,  -- One value per fiscal year
  output_metric_name TEXT,  -- "Calc Beta"
  output_metric_value NUMERIC,  -- Single annualized value
  metadata JSONB  -- Stores {fixed_beta_raw, floating_beta_raw}
)
```

### B. Risk-Free Rate (Phase 08) - Rolling 12-Month Geometric Mean

**Temporal Strategy:** Rolling monthly windows (12-month lookback for geometric mean)

**Implementation:**
- **Monthly rolling window**: 12 consecutive calendar months of bond yields
- **Window shifts monthly**: Each calendar month gets its own 12-month geometric mean
- **Result extraction**: December value extracted for each fiscal year
- **Calculation**: Rf_1Y_Raw = (∏monthly_rates)^(1/12) - 1
- **Rounding**: Applied to get Rf_1Y (rounded to nearest 0.5%)
- **Approach logic**:
  - **Fixed**: Calc Rf = Benchmark - Risk Premium (constant across years)
  - **Floating**: Calc Rf = Rf_1Y (varies by year, dynamic)

**From risk_free_rate_service.py:**
```python
# Calculate rolling 12-month geometric mean
df["rf_1y_raw"] = df["rf_prel"].rolling(window=12).apply(
    lambda x: (np.prod(1 + x) ** (1 / len(x))) - 1
)
```

**Storage Schema:**
Same as Beta - one Calc Rf per (dataset, param_set, ticker, fiscal_year)

### C. Cost of Equity (Phase 09) - Combines Pre-computed Values

**Temporal Strategy:** Uses pre-computed Beta and Rf values (no new temporal aggregation)

**Implementation:**
- **Calculation**: KE = Rf + Beta × RiskPremium
- **Timing**: Runtime aggregation of pre-computed Phase 07 and Phase 08 results
- **Temporal pattern**: Inherits rolling windows from underlying Beta and Rf metrics

**From cost_of_equity_service.py:**
```python
# Vectorized calculation, no temporal windowing
ke_df['ke'] = rf_df['rf_value'] + beta_df['beta_value'] * risk_premium
```

### D. Ratio Metrics (L1 & L2) - Multi-Window Support

**Temporal Strategy:** Explicit multi-window support with SQL window functions

**Implementation:**
- **1Y**: ROWS BETWEEN 0 PRECEDING AND CURRENT ROW (current year only)
- **3Y**: ROWS BETWEEN 2 PRECEDING AND CURRENT ROW (3-year rolling average)
- **5Y**: ROWS BETWEEN 4 PRECEDING AND CURRENT ROW (5-year rolling average)
- **10Y**: ROWS BETWEEN 9 PRECEDING AND CURRENT ROW (10-year rolling average)

**Example - Market-to-Book Ratio (MB_Ratio):**
```sql
-- Numerator: Calc MC with rolling average
numerator_rolling AS (
    SELECT
        ticker,
        fiscal_year,
        AVG(output_metric_value) OVER (
            PARTITION BY ticker 
            ORDER BY fiscal_year 
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW  -- For 3Y window
        ) AS numerator_value,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year) AS year_rank
    FROM metrics_outputs
    WHERE output_metric_name = 'Calc MC'
)

-- Then: numerator_value / denominator_value for final ratio
```

**From ratio_metrics_calculator.py:**
```python
# Temporal window mapping
"1Y": ("ROWS BETWEEN 0 PRECEDING AND CURRENT ROW", 1),
"3Y": ("ROWS BETWEEN 2 PRECEDING AND CURRENT ROW", 3),
"5Y": ("ROWS BETWEEN 4 PRECEDING AND CURRENT ROW", 5),
"10Y": ("ROWS BETWEEN 9 PRECEDING AND CURRENT ROW", 10)
```

### E. Revenue Growth & EE Growth - Rolling Averages

**Temporal Strategy:** Rolling averages on base metrics, then year-over-year growth

**Implementation (Revenue Growth):**
```sql
WITH revenue_data AS (
    SELECT ticker, fiscal_year, numeric_value AS revenue
    FROM fundamentals
),
revenue_rolling AS (
    SELECT
        ticker,
        fiscal_year,
        AVG(revenue) OVER (
            PARTITION BY ticker 
            ORDER BY fiscal_year 
            ROWS BETWEEN :rows_between PRECEDING AND CURRENT ROW
        ) AS revenue_rolling_avg
    FROM revenue_data
),
revenue_with_lag AS (
    SELECT
        ticker,
        fiscal_year,
        revenue_rolling_avg,
        LAG(revenue_rolling_avg) OVER (
            PARTITION BY ticker 
            ORDER BY fiscal_year
        ) AS prior_year_avg_revenue
    FROM revenue_rolling
)
SELECT
    ticker,
    fiscal_year,
    CASE
        WHEN prior_year_avg_revenue IS NULL THEN NULL
        WHEN ABS(prior_year_avg_revenue) = 0 THEN NULL
        ELSE (revenue_rolling_avg - prior_year_avg_revenue) / ABS(prior_year_avg_revenue)
    END AS revenue_growth
```

**Temporal Pattern:**
1. Calculate rolling average for specified window (1Y, 3Y, 5Y, or 10Y)
2. Lag the rolling average by one year
3. Calculate period-over-period growth: (Current - Prior) / Prior

---

## 3. Database Schema for Temporal Metrics

### Core Temporal Structure

**fundamentals table** (source data, granular):
```sql
CREATE TABLE fundamentals (
  fundamentals_id BIGINT PRIMARY KEY,
  dataset_id UUID,
  ticker TEXT,
  metric_name TEXT,
  fiscal_year INTEGER,
  fiscal_month INTEGER,  -- NULL for FISCAL periods
  fiscal_day INTEGER,    -- NULL for FISCAL periods
  numeric_value NUMERIC,
  period_type TEXT CHECK (period_type IN ('FISCAL', 'MONTHLY')),
  imputed BOOLEAN,
  metadata JSONB,
  created_at TIMESTAMPTZ
);

-- Temporal indexes
CREATE INDEX idx_fundamentals_ticker_metric_fy 
  ON fundamentals (ticker, metric_name, fiscal_year);
CREATE INDEX idx_fundamentals_ticker_period_type 
  ON fundamentals (ticker, period_type);
```

**metrics_outputs table** (calculated results):
```sql
CREATE TABLE metrics_outputs (
  metrics_output_id BIGINT PRIMARY KEY,
  dataset_id UUID,
  param_set_id UUID,  -- NULL = pre-computed (temporal aggregation done at ingestion)
  ticker TEXT,
  fiscal_year INTEGER,  -- One row per fiscal year (temporal aggregation point)
  output_metric_name TEXT,
  output_metric_value NUMERIC,
  metadata JSONB,  -- Stores intermediate temporal values
  created_at TIMESTAMPTZ
);

-- Temporal uniqueness: one metric per fiscal year
UNIQUE (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)

-- Temporal indexes
CREATE INDEX idx_metrics_outputs_ticker_fy ON metrics_outputs (ticker, fiscal_year);
CREATE INDEX idx_metrics_outputs_precomputed 
  ON metrics_outputs (dataset_id, ticker, fiscal_year, output_metric_name) 
  WHERE param_set_id IS NULL;
```

### Key Temporal Fields

1. **fiscal_year**: Core temporal dimension (every record has this)
2. **fiscal_month**, **fiscal_day**: Sub-fiscal granularity for monthly data
3. **period_type**: Distinguishes FISCAL vs MONTHLY data
4. **metadata JSONB**: Stores intermediate calculations:
   - Beta: `{fixed_beta_raw, floating_beta_raw, monthly_raw_slopes}`
   - Rf: `{rf_1y_raw, rf_1y_rounded, approach}`
   - Ratio metrics: `{numerator_rolling_avg, denominator_rolling_avg}`

---

## 4. Shared Utilities & Base Classes for Temporal Metrics

### Temporal Calculation Utilities

**1. RatioMetricsCalculator** (SQL window functions)
```python
# Location: backend/app/services/ratio_metrics_calculator.py

class RatioMetricsCalculator:
    def _calculate_rows_between(temporal_window: str) -> tuple[str, int]:
        """
        Converts temporal window to SQL ROWS BETWEEN clause.
        Returns: (sql_rows_between, min_years_required)
        
        Example:
        - "3Y" → ("ROWS BETWEEN 2 PRECEDING AND CURRENT ROW", 3)
        - min_years_required used to calculate year_rank threshold
        """
        mapping = {
            "1Y": ("ROWS BETWEEN 0 PRECEDING AND CURRENT ROW", 1),
            "3Y": ("ROWS BETWEEN 2 PRECEDING AND CURRENT ROW", 3),
            "5Y": ("ROWS BETWEEN 4 PRECEDING AND CURRENT ROW", 5),
            "10Y": ("ROWS BETWEEN 9 PRECEDING AND CURRENT ROW", 10)
        }
```

**2. RevenueGrowthCalculator** (Growth calculation pattern)
```python
# Location: backend/app/services/revenue_growth_calculator.py

class RevenueGrowthCalculator:
    def _calculate_rows_between(temporal_window: str) -> str:
        """Maps temporal window to SQL ROWS BETWEEN integer"""
        mapping = {
            "1Y": "0",   # No rolling average
            "3Y": "2",   # 3-year rolling
            "5Y": "4",   # 5-year rolling
            "10Y": "9"   # 10-year rolling
        }
```

**3. EEGrowthCalculator** (Same pattern as RevenueGrowthCalculator)
```python
# Location: backend/app/services/ee_growth_calculator.py
# Identical temporal mapping structure
```

### Service Layer Orchestrators

**RatioMetricsService**
```python
# Handles both single-window and multi-window queries
async def calculate_ratio_metric(
    metric_id, tickers, dataset_id,
    temporal_window: str = "1Y"  # Single window
)

async def calculate_ratio_metric_multi_window(
    metric_id, tickers, dataset_id,
    temporal_windows: List[str]  # Multiple windows
)
```

### No Base Class Hierarchy
- **CISSA does not use OOP inheritance** for temporal metrics
- Each metric type implements temporal logic independently
- Shared utilities are **stateless functions** in calculators
- Pattern: Calculator builds SQL → Service executes → Repository stores

---

## 5. Examples of Metric Calculation at Different Time Periods

### Example 1: Market-to-Book Ratio (3-Year Rolling)

**Setup:** Dataset from 2001-2020, ticker = AAPL

**Calculation Flow:**
```
Fiscal Year Data Points:
2001: Revenue, Book Equity, Market Cap
2002: Revenue, Book Equity, Market Cap
2003: Revenue, Book Equity, Market Cap  ← First result year for 3Y window
2004: Revenue, Book Equity, Market Cap
...

3-Year Rolling Average (3Y window):
Year 2003: AVG(2001-2003 values)  [first full 3-year window]
Year 2004: AVG(2002-2004 values)  [shifts forward by 1 year]
Year 2005: AVG(2003-2005 values)  [continues rolling]
...
Year 2020: AVG(2018-2020 values)  [last full window]
```

**SQL (Simplified):**
```sql
WITH mc_rolling AS (
    SELECT
        fiscal_year,
        AVG(output_metric_value) OVER (
            ORDER BY fiscal_year 
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW  -- 3-year window
        ) AS mc_avg,
        ROW_NUMBER() OVER (ORDER BY fiscal_year) AS year_rank
    FROM metrics_outputs
    WHERE ticker = 'AAPL'
      AND output_metric_name = 'Calc MC'
),
ee_rolling AS (
    SELECT
        fiscal_year,
        AVG(output_metric_value) OVER (
            ORDER BY fiscal_year 
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ) AS ee_avg,
        ROW_NUMBER() OVER (ORDER BY fiscal_year) AS year_rank
    FROM metrics_outputs
    WHERE ticker = 'AAPL'
      AND output_metric_name = 'Calc EE'
)
SELECT
    m.fiscal_year,
    CASE
        WHEN e.ee_avg IS NULL OR e.ee_avg = 0 THEN NULL
        ELSE m.mc_avg / e.ee_avg
    END AS mb_ratio
FROM mc_rolling m
JOIN ee_rolling e ON m.fiscal_year = e.fiscal_year
WHERE m.year_rank >= 3  -- First result in 2003 (year_rank=3)
ORDER BY m.fiscal_year;
```

### Example 2: Revenue Growth (5-Year Rolling)

**Calculation Pattern:**
```
Base Data:
2001: Revenue = 1000
2002: Revenue = 1100
2003: Revenue = 1200
2004: Revenue = 1400
2005: Revenue = 1600

5-Year Rolling Average:
2005: AVG(2001-2005) = (1000+1100+1200+1400+1600)/5 = 1260
2006: AVG(2002-2006) = ...

Growth Calculation:
2006 Growth = (AVG_2006 - AVG_2005) / ABS(AVG_2005)
```

### Example 3: Beta (60-Month Rolling OLS)

**Monthly Data Input:**
```
2020-01: COMPANY_TSR, INDEX_TSR
2020-02: COMPANY_TSR, INDEX_TSR
...
2020-12: COMPANY_TSR, INDEX_TSR
2021-01: COMPANY_TSR, INDEX_TSR
...
```

**Rolling Window Application:**
```
Window 1 (2015-01 to 2019-12): OLS(60 months) → slope → Beta_2019
Window 2 (2015-02 to 2020-01): OLS(60 months) → slope → Beta_2020-01
...
Window 60 (2015-12 to 2020-11): OLS(60 months) → slope → Beta_2020-11

Annualization:
Aggregate monthly slopes to annual Beta (one per fiscal year)
Apply transformation: adjusted = (slope * 2/3) + 1/3
```

### Example 4: Risk-Free Rate (12-Month Rolling Geometric Mean)

**Monthly Bond Yield Data:**
```
2020-01: Rf_PREL = 0.025
2020-02: Rf_PREL = 0.026
...
2020-12: Rf_PREL = 0.028

Rolling 12-Month Geometric Mean:
Jan 2020: (product of Jan 2019 - Dec 2019)^(1/12) - 1 = Rf_1Y
Feb 2020: (product of Feb 2019 - Jan 2020)^(1/12) - 1 = Rf_1Y
...
Dec 2020: (product of Jan 2020 - Dec 2020)^(1/12) - 1 = Rf_1Y ← Used for FY2020

Approach Application:
- Fixed: Calc Rf = Benchmark - RiskPremium (same for all years)
- Floating: Calc Rf = Rf_1Y_2020 (dynamic, varies by year)
```

---

## 6. How Parameters Affect Temporal Calculations

### A. Pre-Computed Temporal Metrics (Phase 07 & 08)

Parameters loaded at **data ingestion time** (not runtime):

```python
# From beta_precomputation_service.py
params = {
    'beta_relative_error_tolerance': 40.0,  # % tolerance
    'cost_of_equity_approach': 'Floating'   # 'FIXED' or 'Floating'
}
```

**Effect on Temporal Calculation:**
- **beta_relative_error_tolerance**: Filters out high-error rolling OLS results
  - Only slopes with relative error < 40% are kept
  - Applied during rolling window processing (filter happens mid-calculation)
  - Missing values → sector median imputation → market median fallback

- **cost_of_equity_approach**: Determines Rf temporal pattern
  - **FIXED**: Constant Rf across all years (benchmark - risk_premium)
  - **Floating**: Year-specific Rf from rolling 12-month window
  - Applied AFTER rolling calculation (post-processing)

### B. Runtime Temporal Parameters (Phase 07 Runtime)

When Beta is calculated at runtime (not pre-computed):

```python
# From beta_rounding_service.py
params = {
    'beta_rounding': 0.1,              # Rounding increment
    'cost_of_equity_approach': 'Floating',
    'beta_relative_error_tolerance': 40.0
}
```

**Effect on Temporal Calculation:**
- **beta_rounding**: Applied AFTER rolling OLS calculation
  - Example: raw_beta = 1.27 with rounding=0.1 → 1.3
  - Rounds each year's annualized beta independently

### C. Ratio Metrics Parameters

No direct parameter effect on temporal windows. Parameters only affect:
- **parameter_dependent=True**: Metrics from metrics_outputs filtered by param_set_id
- **parameter_dependent=False**: Metrics from fundamentals (parameter-agnostic)

Example (MB Ratio):
```python
numerator = MetricComponent(
    metric_name="Calc MC",
    metric_source=MetricSource.METRICS_OUTPUTS,
    parameter_dependent=False  # No param_set_id filter
)
denominator = MetricComponent(
    metric_name="Calc EE",
    metric_source=MetricSource.METRICS_OUTPUTS,
    parameter_dependent=False
)
```

### D. Multi-Window Parameter (API Level)

```python
# From endpoints/metrics.py
temporal_window: str = Query(
    "1Y",
    description="Temporal window(s): single value (1Y) or comma-separated (1Y,3Y,5Y)"
)

# Parsed as: ["1Y", "3Y", "5Y"]
# Creates separate rolling window calculation for each
```

**Multi-window behavior:**
- No parameter override needed
- API accepts comma-separated list
- Service calculates each window independently
- Results grouped by window in response

---

## 7. Pre-Calculated vs Runtime Metric Patterns

### Pattern 1: Pre-Calculated (Stored with param_set_id=NULL)

**Metrics:** Beta, Risk-Free Rate, Cost of Equity, L1 metrics

**When Used:**
- During ETL data ingestion pipeline (phases 07, 08, 09)
- After all fundamentals are cleaned and aligned
- Temporal calculation happens ONCE per dataset

**Temporal Pattern:**
1. **Load fundamentals** (all historical data)
2. **Apply rolling window** to monthly data
3. **Annualize** to fiscal year
4. **Store in metrics_outputs** with param_set_id=NULL
5. **Runtime retrieval** is O(1) lookup (table scan only)

**Example - Beta Pre-computation:**
```python
# Location: beta_precomputation_service.py

async def precompute_beta_async(dataset_id):
    # 1. Fetch monthly returns
    monthly_df = await self._fetch_monthly_returns(dataset_id)
    
    # 2. Calculate 60-month rolling OLS slopes
    ols_df = self._calculate_rolling_ols(monthly_df)
    
    # 3. Annualize to fiscal year
    annualized = self._annualize_slopes(ols_df)
    
    # 4. Store with param_set_id=NULL
    await self._store_precomputed_beta(dataset_id, annualized)
    # metadata includes: {fixed_beta_raw, floating_beta_raw, monthly_raw_slopes}
```

**Storage:**
```
metrics_outputs:
  dataset_id: UUID (data ingestion version)
  param_set_id: NULL (pre-computed marker)
  ticker: AAPL
  fiscal_year: 2020
  output_metric_name: Calc Beta
  output_metric_value: 1.2
  metadata: {fixed_beta_raw: 1.25, floating_beta_raw: 1.2, ...}
```

### Pattern 2: Runtime Calculation (Specific param_set_id)

**Metrics:** Ratio metrics, Revenue Growth, EE Growth, Optimizations

**When Used:**
- When user queries metrics endpoint
- Temporal window is dynamic (1Y, 3Y, 5Y, 10Y)
- Can test multiple scenarios with different parameters

**Temporal Pattern:**
1. **Query API** with tickers + temporal_window
2. **Build SQL query** (window functions with ROWS BETWEEN)
3. **Execute query** (0-5 seconds depending on dataset size)
4. **Return results** as time-series with rolling averages

**Example - Ratio Metrics (Runtime):**
```python
# Location: ratio_metrics_service.py

async def calculate_ratio_metric(metric_id, tickers, dataset_id, temporal_window="1Y"):
    # 1. Parse temporal_window
    calculator = RatioMetricsCalculator(metric_def, temporal_window)
    
    # 2. Build parameterized SQL with window functions
    sql_query, params = calculator.build_query(tickers, dataset_id, param_set_id)
    
    # 3. Execute query
    results = await self.ratio_repo.execute_ratio_query(sql_query, params)
    
    # 4. Return formatted response
    return RatioMetricsResponse(...)
```

**SQL Structure (Runtime):**
```sql
-- Dynamically built with temporal_window parameter
SELECT
    ticker,
    fiscal_year,
    AVG(output_metric_value) OVER (
        PARTITION BY ticker 
        ORDER BY fiscal_year 
        ROWS BETWEEN :rows_between PRECEDING AND CURRENT ROW  -- Dynamic
    ) AS rolling_value,
    ...
```

### Pattern 3: Hybrid Pattern (Pre-Computed Inputs + Runtime Aggregation)

**Metrics:** Cost of Equity (depends on pre-computed Beta + Rf)

**When Used:**
- When combining multiple pre-computed metrics
- Temporal windows from inputs are maintained
- Fast because aggregation is simple math (no DB query)

**Temporal Pattern:**
```
Input 1 (Pre-computed): Calc Beta (fiscal_year → value)
Input 2 (Pre-computed): Calc Rf (fiscal_year → value)
Parameter: risk_premium

Runtime:
For each fiscal_year:
    KE = Rf[fiscal_year] + Beta[fiscal_year] × risk_premium

Storage: New metrics_outputs record with param_set_id
```

---

## 8. Summary: Temporal Capability Patterns

| Metric | Type | Temporal Window | Storage | Timing | Granularity |
|--------|------|-----------------|---------|--------|-------------|
| Beta | Pre-computed | 60-month rolling OLS | metrics_outputs (param_set_id=NULL) | Ingestion | Monthly → Annual |
| Calc Rf | Pre-computed | 12-month rolling geometric mean | metrics_outputs (param_set_id=NULL) | Ingestion | Monthly → Annual |
| Calc KE | Pre-computed | From Beta/Rf | metrics_outputs (param_set_id=NULL) | Ingestion | Annual |
| MB Ratio | Runtime | 1Y/3Y/5Y/10Y rolling avg | Not stored (calculated on-demand) | Query time | Annual |
| Revenue Growth | Runtime | 1Y/3Y/5Y/10Y rolling avg | Not stored | Query time | Annual |
| EE Growth | Runtime | 1Y/3Y/5Y/10Y rolling avg | Not stored | Query time | Annual |
| L2 Metrics | Pre-computed | Multi-period (annual) | metrics_outputs (param_set_id!=NULL) | Ingestion | Annual |

---

## 9. Key Takeaways: What Temporal Capability Means in CISSA

1. **Not real-time**: All calculations are batch-based, historical retrospective
2. **Not granular**: Finest granularity is monthly (monthly TSR), aggregated to fiscal years
3. **IS rolling windows**: Each metric can be calculated at 1Y, 3Y, 5Y, 10Y horizons
4. **IS stored systematically**: Pre-computed metrics have one row per (dataset, ticker, fiscal_year, metric_name)
5. **IS parameter-driven**: Window selection, rounding, approach choice affect temporal aggregation
6. **IS schema-driven**: fiscal_year column is the core temporal dimension in all tables
7. **IS flexible**: Runtime metrics support dynamic window selection; pre-computed metrics are fixed at ingestion

### The Temporal Architecture
```
Raw Monthly Data (fundamentals)
    ↓
Rolling Window Application (monthly ROWS BETWEEN clause)
    ↓
Annualization / Period Aggregation (fiscal_year)
    ↓
Storage in metrics_outputs (one row per fiscal_year)
    ↓
Runtime Queries (apply second-stage rolling averages via window functions)
```

This architecture enables:
- **Temporal smoothing** via rolling windows
- **Multi-horizon analysis** via 1Y/3Y/5Y/10Y selector
- **Parameter sensitivity** testing (different approaches affect temporal calculation)
- **Traceability** (metadata tracks intermediate temporal values)
