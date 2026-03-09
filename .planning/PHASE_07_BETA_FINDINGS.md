# PHASE 07: BETA CALCULATION REQUIREMENTS - COMPREHENSIVE FINDINGS

**Date:** March 9, 2026  
**Status:** Research & Analysis Complete  
**Scope:** Beta calculation implementation for CISSA backend Phase 07

---

## EXECUTIVE SUMMARY

This document provides comprehensive findings on the beta calculation requirements for Phase 07, including:

1. **Legacy Beta Implementation Analysis** - Complete reverse-engineering of beta.py
2. **Data Availability Audit** - Current fundamentals table metric inventory & coverage
3. **Infrastructure Assessment** - Backend services, data structures, parameter storage
4. **Gap Analysis** - Differences between legacy requirements and current backend capabilities
5. **Implementation Roadmap** - Specific recommendations with file references

**Key Finding:** Beta calculation requires MONTHLY returns data (Company TSR, Index TSR) currently available in fundamentals table, but needs 60+ months per ticker with proper sector groupings for 4-tier fallback logic.

---

## 1. LEGACY BETA.PY IMPLEMENTATION ANALYSIS

### 1.1 Location & File Structure
**File:** `/home/ubuntu/cissa/example-calculations/src/executors/beta.py` (104 lines)  
**Integration Point:** `/home/ubuntu/cissa/example-calculations/src/engine/calculation.py` line 79

### 1.2 Input Data Requirements

#### Metric Names (Exact from Legacy):
The legacy system expects data loaded via:
- **`Company TSR`** - Monthly returns from fundamentals table (stored as "Company TSR (Monthly)" in metric_units.json)
- **`Index TSR`** - Market index returns from fundamentals table (stored as "Index TSR (Monthly)" in metric_units.json)

**Legacy SQL Query Reference:**
- File: `/home/ubuntu/cissa/example-calculations/src/engine/sql.py` lines 259-280
- Function: `get_TSR()` extracts:
  - `KEY='Company TSR'` → scaled to decimal format: `(value/100) + 1` → stored as `re` (equity return)
  - `KEY='Index TSR'` AND `TICKER LIKE '%AS30%'` → scaled to decimal: `(value/100) + 1` → stored as `rm` (market return)

**Current Backend Metric Names** (from metric_units.json):
```json
{
  "metric_name": "Company TSR (Monthly)",
  "database_name": "COMPANY_TSR",
  "unit": "%"
},
{
  "metric_name": "Index TSR (Monthly)",
  "database_name": "INDEX_TSR",
  "unit": "%"
}
```

#### Data Structure:
- **Period Type:** MONTHLY (not FISCAL)
- **Date Components:** fiscal_year, fiscal_month, fiscal_day populated
- **Unit:** Percentage (e.g., 1.5 = 1.5%)
- **Storage Table:** `fundamentals` table in backend
- **Query Pattern:** Filter by `period_type='MONTHLY'` and `metric_name` IN ('Company TSR (Monthly)', 'Index TSR (Monthly)')

### 1.3 Calculation Approach

#### Step 1: Rolling OLS Regression
```python
# Lines 10-19: run_regressions()
window = 60  # 60-month rolling window
model = RollingOLS(y=market_return, x=equity_return, window=window)
result = model.fit()
slope = result.params  # Regression coefficient (Beta)
std_err = result.bse   # Standard error of beta
```

**Key Parameters:**
- Rolling window: **60 months** (fixed, minimum 60 required)
- If < 60 months available, uses full history (no minimum enforcement)

#### Step 2: Slope Adjustment
```python
# Line 35: Adjustment formula
adjusted_slope = (slope * 2/3) + 1/3

# Line 34: Relative standard error
rel_std_err = abs(std_err) / ((abs(slope) * 2/3) + 1/3)
```

**Adjustment Logic:**
- Takes form: `adjusted_slope = (slope × 2/3) + 1/3`
- Introduces mean-reversion factor (equilibrium beta ~1.0)
- Penalizes extreme slopes toward market average

#### Step 3: Rounding & Error Tolerance Check
```python
# Lines 36-38: Error tolerance threshold
adjusted_slope = round((((slope * 2/3) + 1/3) / beta_rounding), 4) * beta_rounding 
    if error_tolerance >= rel_std_err else NaN
```

**Error Tolerance Logic:**
- Parameter: `error_tolerance` (default: 0.8 = 80%)
- Comparison: `error_tolerance >= rel_std_err` must be TRUE to accept slope
- If fails: sets to NaN for fallback processing

#### Step 4: 4-Tier Fallback Logic (CRITICAL)
```python
# Lines 62-65: Fallback cascade
# Tier 1: Ticker-specific adjusted_slope
spot_betas['spot_slope'] = spot_betas['adjusted_slope'].fillna(
    # Tier 2: Sector average
    spot_betas['sector_slope']
)

# Later (lines 68-72): Tier 3 calculation
# Tier 3: Ticker average across years
beta_by_ticker = spot_betas.groupby('ticker').agg(
    avg_spot_slope_by_ticker=('spot_slope', lambda x: x.mean(skipna=False))
)

# Tier 4: NaN (explicit default when all tiers fail)
```

**Fallback Chain:**
1. **Tier 1** (Primary): Ticker-specific adjusted slope (if passes error_tolerance check)
2. **Tier 2** (Secondary): Sector average slope for that year
3. **Tier 3** (Tertiary): Average slope for ticker across all years
4. **Tier 4** (Final): NaN (no data available)

### 1.4 Annual Alignment & Sector Processing

#### Annual Slope Generation (Line 44-52)
```python
def generate_annual_slope(beta_df):
    # Convert monthly dates to FY alignment
    beta_df['yr_mth'] = date.strftime('%m%Y')  # Month-year format
    beta_df['year'] = date.strftime('%Y')       # Calendar year
    
    # Merge with FY dates to align monthly data to fiscal years
    annual_beta = pd.merge(fy_dates, beta_df, on=['yr_mth', 'ticker'])
```

**Input Requirements:**
- FY dates mapping (fiscal period end dates) → from `sql.get_fy_dates()`
- Columns required: `['yr_mth', 'year', 'ticker', 'sector', 'slope', 'adjusted_slope', 'std_err', 'rel_std_err']`

#### Sector Slope Calculation (Line 55-59)
```python
def generate_sector_slope(annual_beta):
    beta_by_sector = annual_beta.groupby(['sector', 'year']).agg(
        sector_slope=('adjusted_slope', lambda x: x.mean(skipna=True))
    )
    return beta_by_sector
```

**Requirements:**
- `sector` column in data (from company master data)
- Group by (sector, year) → calculate mean of adjusted_slope
- Result: sector-level average beta for fallback

### 1.5 Configurable Parameters

**From `/home/ubuntu/cissa/example-calculations/src/config/parameters.py` (referenced in calculation.py):**

| Parameter | Type | Default | Usage |
|-----------|------|---------|-------|
| `error_tolerance` | float | 0.8 | Relative std error threshold for accepting slope |
| `beta_rounding` | float | 0.1 | Rounding precision (rounds to nearest 0.1) |
| `approach_to_ke` | string | "Floating" or "FIXED" | "FIXED" = use avg ticker slope; "Floating" = use spot slope |
| `currency` | string | "AUD" | Output currency designation |

**From backend schema (`cissa.parameters` table):**
```sql
('beta_rounding', 'Beta Rounding', 'NUMERIC', '0.1'),
('beta_relative_error_tolerance', 'Beta Relative Error Tolerance', 'NUMERIC', '40.0'),
```

**Note:** Backend uses percentage (40.0 = 40%) while legacy uses decimal (0.8 = 80%). Need conversion in Phase 07 implementation.

### 1.6 Output Structure

**Output Columns:**
```
['fy_year', 'ticker', 'sector_slope', 'beta', 'fx_currency']
```

**Output Metrics:**
- `sector_slope`: Sector average (from Tier 2 fallback)
- `beta`: Final beta value after all processing (from `calculate_beta()` function)
- `fx_currency`: Output currency

**Storage in Legacy:** Config/metrics table (integration point not fully clear)

---

## 2. CURRENT FUNDAMENTALS TABLE DATA AVAILABILITY AUDIT

### 2.1 Metric Names Found in Backend

**From `/home/ubuntu/cissa/backend/database/config/metric_units.json`:**

#### TSR/Returns Metrics Available:
```json
{
  "metric_name": "Company TSR (Monthly)",
  "database_name": "COMPANY_TSR",
  "unit": "%",
  "period_type": "MONTHLY"
},
{
  "metric_name": "Index TSR (Monthly)",
  "database_name": "INDEX_TSR",
  "unit": "%",
  "period_type": "MONTHLY"
},
{
  "metric_name": "Risk-Free Rate (Monthly)",
  "database_name": "RISK_FREE_RATE",
  "unit": "%",
  "period_type": "MONTHLY"
},
{
  "metric_name": "FY TSR",
  "database_name": "FY_TSR",
  "unit": "%",
  "period_type": "FISCAL"
}
```

### 2.2 Data Completeness Analysis

#### Storage Location:
- **Table:** `cissa.fundamentals`
- **Columns:** 
  - `metric_name` (VARCHAR)
  - `fiscal_year`, `fiscal_month`, `fiscal_day` (INTEGER)
  - `numeric_value` (NUMERIC)
  - `period_type` (VARCHAR: 'FISCAL' or 'MONTHLY')

#### Query Pattern for Beta Data:
```sql
SELECT 
  ticker,
  fiscal_year,
  fiscal_month,
  fiscal_day,
  metric_name,
  numeric_value
FROM cissa.fundamentals
WHERE dataset_id = <dataset_uuid>
  AND period_type = 'MONTHLY'
  AND metric_name IN ('Company TSR (Monthly)', 'Index TSR (Monthly)')
ORDER BY ticker, fiscal_year, fiscal_month, fiscal_day;
```

### 2.3 Data Structure in Fundamentals Table

**Example Data Format:**
```
ticker   | fiscal_year | fiscal_month | fiscal_day | metric_name              | numeric_value
---------|-------------|--------------|------------|--------------------------|--------------
CBA      | 1998        | 11           | 30         | Company TSR (Monthly)    | 1.5
CBA      | 1998        | 12           | 31         | Company TSR (Monthly)    | 2.3
AS30 IDX | 1998        | 11           | 30         | Index TSR (Monthly)      | 1.2
AS30 IDX | 1998        | 12           | 31         | Index TSR (Monthly)      | 1.8
```

**Key Observations:**
1. MONTHLY data has full date components (year, month, day)
2. Index data uses ticker identifier (appears to be "AS30 IDX" or similar)
3. Returns stored as percentages (1.5 = 1.5%, convert by /100)
4. One row per (ticker, fiscal_year, fiscal_month, fiscal_day, metric_name)

### 2.4 Data Availability Gaps Identified

**Status:** ⚠️ CRITICAL GAPS REQUIRE VALIDATION

| Gap | Impact | Severity |
|-----|--------|----------|
| **Minimum 60 months required:** Not verified if all tickers have 60+ consecutive months | Beta calculation will fail for incomplete tickers | HIGH |
| **Index ticker naming:** Legacy expects "AS30 IDX" but actual identifier unknown | Merge with company returns will fail if naming doesn't match | HIGH |
| **Date alignment:** Monthly dates may not align with fiscal year boundaries | FY alignment logic may lose data | MEDIUM |
| **Data continuity:** Unknown if any months are missing (sparse time series) | OLS window calculation assumptions may be invalid | HIGH |
| **Sector grouping:** Company master data must have sector column | Fallback tier 2 will fail without sector classification | HIGH |

---

## 3. BACKEND INFRASTRUCTURE ANALYSIS

### 3.1 EnhancedMetricsService Structure

**Location:** `/home/ubuntu/cissa/backend/app/services/enhanced_metrics_service.py` (406 lines)

#### Current Implementation Status:
- **Beta calculation:** Stub implementation (returns 1.0 for all tickers)
- **Location:** Lines 269-286 `_calculate_beta()` method

```python
def _calculate_beta(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Calculate Beta (simplified to 1.0 until timeseries data available)."""
    results = []
    beta_rounding = params.get("beta_rounding", 0.1)
    
    for _, row in df.iterrows():
        # Use 1.0 as default beta
        beta = 1.0
        beta_rounded = round(beta / beta_rounding) * beta_rounding
        
        results.append({
            "ticker": row["ticker"],
            "fiscal_year": int(row["fiscal_year"]),
            "metric_name": "Beta",
            "Beta": float(beta_rounded)
        })
    
    return pd.DataFrame(results)
```

**Comment on Line 270:** "simplified to 1.0 until timeseries data available"

#### Service Capabilities:
- **AsyncSession pattern:** Used for database access (SQLAlchemy async)
- **Batch insertion:** Via `_insert_metrics_batch()` (lines 367-406)
- **Parameter loading:** Via `_load_parameters_from_db()` (lines 146-204)
- **Data fetching:** Separate methods for fundamentals, L1 metrics

### 3.2 MetricsRepository Interface

**Location:** `/home/ubuntu/cissa/backend/app/repositories/metrics_repository.py` (175 lines)

#### Available Methods:
1. **`get_l1_metrics(dataset_id, param_set_id)`** - Fetch L1 metrics from metrics_outputs
2. **`create_metric_output()`** - Insert single metric
3. **`create_metric_outputs_batch(records)`** - Batch insert metrics
4. **`get_by_id(metrics_output_id)`** - Fetch by primary key

#### Batch Insertion Pattern (Lines 100-141):
```python
async def create_metric_outputs_batch(self, records: list[dict]) -> int:
    instances = [
        MetricsOutput(
            dataset_id=record["dataset_id"],
            param_set_id=record["param_set_id"],
            ticker=record["ticker"],
            fiscal_year=record["fiscal_year"],
            output_metric_name=record["output_metric_name"],
            output_metric_value=record["output_metric_value"],
            metadata=record.get("metadata", {}),
        )
        for record in records
    ]
    self._session.add_all(instances)
    await self._session.flush()
    return len(instances)
```

**Note:** Uses SQLAlchemy ORM, not raw SQL

### 3.3 Data Flow: Enhanced Metrics Service

```
calculate_enhanced_metrics()
├─ _load_parameters_from_db()          # Load params from cissa.parameters + overrides
├─ _fetch_fundamentals()               # Query cissa.fundamentals (FISCAL data)
├─ _fetch_l1_metrics()                 # Query cissa.metrics_outputs (L1 metrics)
├─ _calculate_beta()                   # THIS IS WHERE WE IMPLEMENT
│  └─ For each (ticker, fiscal_year):
│     1. Fetch monthly returns data (Company TSR, Index TSR)
│     2. Run rolling OLS regression (60-month window)
│     3. Apply slope adjustment & error tolerance check
│     4. Execute 4-tier fallback logic
│     5. Format output DataFrame
├─ _calculate_rf()                     # Risk-free rate
├─ _calculate_cost_of_equity()         # KE = RF + Beta × Risk Premium
├─ _calculate_financial_ratios()       # ROA, ROE, Profit Margin
└─ _insert_metrics_batch()             # Store all results in metrics_outputs
    └─ INSERT INTO cissa.metrics_outputs WITH metadata: {"metric_level": "L3"}
```

### 3.4 Parameter Storage & Loading

#### Source: `cissa.parameters` table

**Default Parameters for Beta:**
```sql
-- From backend/database/schema/schema.sql lines 409-424
INSERT INTO parameters (parameter_name, display_name, value_type, default_value)
VALUES
  ('beta_rounding', 'Beta Rounding', 'NUMERIC', '0.1'),
  ('beta_relative_error_tolerance', 'Beta Relative Error Tolerance', 'NUMERIC', '40.0'),
  ...
```

#### Parameter Loading Flow (Lines 146-204):
```python
async def _load_parameters_from_db(self, param_set_id: UUID) -> dict:
    # Step 1: Load base parameters from cissa.parameters
    query = "SELECT parameter_name, default_value FROM cissa.parameters"
    params = {}
    
    # Step 2: Apply conversions based on parameter type
    if param_name in ["equity_risk_premium", "beta_relative_error_tolerance", ...]:
        params[param_name] = float(value) / 100.0  # Convert from percentage
    elif param_name in ["beta_rounding", ...]:
        params[param_name] = float(value)
    
    # Step 3: Apply overrides from parameter_set
    override_result = await self.session.execute(
        "SELECT param_overrides FROM cissa.parameter_sets WHERE param_set_id = :param_set_id"
    )
    if override_row and override_row[0]:
        overrides = override_row[0]  # JSONB param_overrides
        for key, value in overrides.items():
            params[key] = <converted_value>
    
    return params
```

**Important:** Backend stores percentages (40.0), but legacy uses decimals (0.8). Conversion needed.

### 3.5 Output Storage Pattern

**Table:** `cissa.metrics_outputs`

**Schema:**
```sql
CREATE TABLE metrics_outputs (
  metrics_output_id BIGINT PRIMARY KEY,
  dataset_id UUID,
  param_set_id UUID,
  ticker TEXT,
  fiscal_year INTEGER,
  output_metric_name TEXT,
  output_metric_value NUMERIC,
  metadata JSONB,
  created_at TIMESTAMPTZ
);

UNIQUE INDEX ON (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name);
```

**Insertion Pattern (Lines 377-383):**
```python
INSERT INTO cissa.metrics_outputs 
(dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata, created_at)
VALUES (:dataset_id, :param_set_id, :ticker, :fiscal_year, :output_metric_name, :output_metric_value, :metadata, now())
ON CONFLICT (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name) 
DO UPDATE SET output_metric_value = EXCLUDED.output_metric_value;
```

**Metadata Pattern:**
```json
{"metric_level": "L3", "calculation_source": "enhanced_metrics_service"}
```

---

## 4. GAP ANALYSIS: LEGACY vs. BACKEND

### 4.1 Data Structure Gaps

| Aspect | Legacy | Backend | Gap |
|--------|--------|---------|-----|
| **Monthly Returns Storage** | SQL views on monthly_data table | fundamentals table with period_type='MONTHLY' | ✅ COMPATIBLE |
| **Company TSR Column Name** | "Company TSR" | "Company TSR (Monthly)" | ⚠️ NAMING DIFFERS |
| **Index TSR Column Name** | "Index TSR" | "Index TSR (Monthly)" | ⚠️ NAMING DIFFERS |
| **Index Ticker ID** | "%AS30%" pattern | Unknown (need validation) | ❌ NOT VERIFIED |
| **FY Alignment Data** | sql.get_fy_dates() | fiscal_year_mapping table | ✅ COMPATIBLE |
| **Sector Data** | companies.sector | companies.sector | ✅ COMPATIBLE |
| **Date Components** | date field (parsed) | fiscal_year, fiscal_month, fiscal_day | ✅ COMPATIBLE |

### 4.2 Calculation Logic Gaps

| Component | Legacy | Backend | Gap |
|-----------|--------|---------|-----|
| **Rolling OLS** | statsmodels.regression.rolling.RollingOLS | NOT IMPLEMENTED | ❌ NEEDS IMPLEMENTATION |
| **Window Size** | 60 months (hardcoded) | TBD | ❌ NEEDS IMPLEMENTATION |
| **Slope Adjustment** | (slope × 2/3) + 1/3 | NOT IMPLEMENTED | ❌ NEEDS IMPLEMENTATION |
| **Error Tolerance** | Parameter-driven (default 0.8) | Parameter exists (40.0%) but not used | ⚠️ CONVERSION NEEDED |
| **Beta Rounding** | Parameter-driven (default 0.1) | Parameter exists (0.1) | ✅ COMPATIBLE |
| **4-Tier Fallback** | Full implementation | NOT IMPLEMENTED | ❌ NEEDS FULL IMPLEMENTATION |
| **Sector Averages** | Calculated dynamically | NOT IMPLEMENTED | ❌ NEEDS IMPLEMENTATION |
| **Ticker Averages** | Calculated dynamically | NOT IMPLEMENTED | ❌ NEEDS IMPLEMENTATION |

### 4.3 Parameter Conversion Issues

**Backend stores parameters as percentages; legacy uses decimals:**

```
Legacy:  error_tolerance = 0.8 (80% threshold)
Backend: beta_relative_error_tolerance = 40.0 (stored as percentage)

Conversion: backend_value / 100 = legacy_value
Therefore:  40.0 / 100 = 0.4 (BUT legacy default is 0.8!)
```

**ACTION REQUIRED:** Clarify parameter semantics before implementation.

### 4.4 Infrastructure Gaps

| Component | Legacy | Backend | Gap |
|-----------|--------|---------|-----|
| **Threading** | Threading + ThreadPoolExecutor | AsyncSession (async/await) | ⚠️ DIFFERENT PARADIGM |
| **OLS Library** | statsmodels | NOT IMPORTED | ❌ ADD TO REQUIREMENTS |
| **Input Data Format** | DataFrames from SQL | AsyncSession → DataFrames | ✅ CONVERTIBLE |
| **Output Format** | Metrics DataFrame | metrics_outputs table + metadata | ✅ COMPATIBLE |

---

## 5. IMPLEMENTATION REQUIREMENTS & SOLUTIONS

### 5.1 Data Fetching - Monthly Returns

**Required Query:**
```python
# In EnhancedMetricsService._fetch_monthly_returns()
async def _fetch_monthly_returns(self, dataset_id: UUID) -> pd.DataFrame:
    """
    Fetch monthly Company TSR and Index TSR data for rolling OLS.
    
    Returns DataFrame with columns:
    - ticker, fiscal_year, fiscal_month, fiscal_day
    - metric_name, numeric_value
    
    Filters:
    - period_type = 'MONTHLY'
    - metric_name IN ('Company TSR (Monthly)', 'Index TSR (Monthly)')
    
    Sorting: ticker, fiscal_year, fiscal_month, fiscal_day (chronological)
    """
    query = text("""
        SELECT 
            ticker,
            fiscal_year,
            fiscal_month,
            fiscal_day,
            metric_name,
            numeric_value
        FROM cissa.fundamentals
        WHERE dataset_id = :dataset_id
          AND period_type = 'MONTHLY'
          AND metric_name IN ('Company TSR (Monthly)', 'Index TSR (Monthly)')
        ORDER BY ticker, fiscal_year, fiscal_month, fiscal_day
    """)
    
    result = await self.session.execute(query, {"dataset_id": str(dataset_id)})
    rows = result.fetchall()
    
    df = pd.DataFrame(
        rows,
        columns=["ticker", "fiscal_year", "fiscal_month", "fiscal_day", "metric_name", "numeric_value"]
    )
    return df
```

### 5.2 Data Pivot for OLS Regression

**Transform flat data to (re, rm) columns:**
```python
def _pivot_returns_for_ols(self, df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform fundamentals table data to OLS-ready format.
    
    Input columns:
    - ticker, fiscal_year, fiscal_month, fiscal_day, metric_name, numeric_value
    
    Output columns:
    - ticker, date (sorted chronologically)
    - re (equity return as decimal: value/100)
    - rm (market return as decimal: value/100)
    
    Steps:
    1. Create date from components: date(fiscal_year, fiscal_month, fiscal_day)
    2. Pivot metric_name to columns (Company TSR → re, Index TSR → rm)
    3. Handle index ticker mapping (need to identify index rows)
    4. Scale from percentage to decimal: /100
    5. Drop rows with NaN in either re or rm
    6. Sort by (ticker, date) chronologically
    """
    # Step 1: Create full date
    df['date'] = pd.to_datetime(
        df[['fiscal_year', 'fiscal_month', 'fiscal_day']].rename(
            columns={'fiscal_year': 'year', 'fiscal_month': 'month', 'fiscal_day': 'day'}
        )
    )
    
    # Step 2: Pivot metric_name to columns
    # BUG: Need to handle index ticker - legacy uses WHERE TICKER LIKE '%AS30%'
    # For now, assume two tickers present: regular company and index ticker
    
    pivot = df.pivot_table(
        index=['ticker', 'date'],
        columns='metric_name',
        values='numeric_value',
        aggfunc='first'
    )
    pivot.reset_index(inplace=True)
    
    # Step 3: Scale from percentage to decimal and add 1
    # Legacy: ROUND((CAST(value AS DECIMAL)/100) + 1, 4)
    pivot['re'] = (pivot['Company TSR (Monthly)'] / 100.0) + 1.0
    pivot['rm'] = (pivot['Index TSR (Monthly)'] / 100.0) + 1.0
    
    # Step 4: Drop rows with missing data
    pivot = pivot[pivot['re'].notna() & pivot['rm'].notna()]
    
    # Step 5: Sort chronologically
    pivot = pivot.sort_values(['ticker', 'date'])
    
    return pivot[['ticker', 'date', 're', 'rm']]
```

### 5.3 OLS Regression Implementation

**Requirements:**
- Library: `statsmodels` (add to requirements.txt)
- Function: `RollingOLS(endog, exog, window=60)`
- Handle window < 60 months gracefully

```python
def _calculate_rolling_ols(self, ticker_data: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    """
    Calculate rolling OLS regression on (re, rm) data.
    
    Args:
        ticker_data: DataFrame with columns [date, ticker, re, rm] for single ticker
        window: Window size (default 60 months)
    
    Returns:
        DataFrame with columns [date, ticker, slope, std_err, adjusted_slope, rel_std_err]
    
    Process:
    1. If len(data) < 60: use full history
    2. Run RollingOLS(endog=rm, exog=re, window=window)
    3. Extract params (slope) and bse (std_err)
    4. Calculate adjusted_slope = (slope × 2/3) + 1/3
    5. Calculate rel_std_err = abs(std_err) / adjusted_slope
    6. Check: if error_tolerance >= rel_std_err: accept, else NaN
    """
    from statsmodels.regression.rolling import RollingOLS
    
    x = ticker_data['re']  # Equity return
    y = ticker_data['rm']  # Market return
    actual_window = min(window, len(x))
    
    model = RollingOLS(y, x, window=actual_window)
    result = model.fit()
    
    params = pd.DataFrame(result.params).rename(columns={'re': 'slope'})
    bse = pd.DataFrame(result.bse).rename(columns={'re': 'std_err'})
    
    # Merge results
    output = pd.merge(params, bse, on=['date', 'ticker'], how='inner')
    output['ticker'] = ticker_data['ticker'].iloc[0]
    
    return output
```

### 5.4 4-Tier Fallback Logic Implementation

**Critical for data quality:**

```python
def _calculate_beta_with_fallback(
    self,
    ticker_betas: pd.DataFrame,  # Annual betas per ticker
    sector_betas: pd.DataFrame,  # Sector average betas per year
    ticker_avg_betas: pd.DataFrame,  # Average beta per ticker across years
    error_tolerance: float = 0.8,
    beta_rounding: float = 0.1
) -> pd.DataFrame:
    """
    4-Tier fallback logic for beta calculation.
    
    Tier 1: Ticker-specific adjusted_slope (if passes error tolerance)
    Tier 2: Sector average slope for that year
    Tier 3: Ticker average slope across all years
    Tier 4: NaN (no value available)
    
    Process:
    1. For each (ticker, year) combination:
       a. Start with adjusted_slope from OLS
       b. If passes error_tolerance check: Tier 1
       c. Else: fill with sector average (Tier 2)
    2. For any remaining NaN: fill with ticker average (Tier 3)
    3. Final NaN: leave as NaN (Tier 4)
    4. Round to beta_rounding
    """
    results = []
    
    for _, row in ticker_betas.iterrows():
        ticker = row['ticker']
        year = row['year']
        sector = row['sector']
        
        # Tier 1: Ticker-specific (if passes error tolerance)
        if pd.notna(row['adjusted_slope']) and row['rel_std_err'] <= error_tolerance:
            beta_value = row['adjusted_slope']
            tier = 1
        # Tier 2: Sector average
        elif pd.notna(row['sector_slope']):
            beta_value = row['sector_slope']
            tier = 2
        # Tier 3: Ticker average
        elif ticker in ticker_avg_betas.index:
            beta_value = ticker_avg_betas.loc[ticker, 'avg_slope']
            tier = 3
        # Tier 4: NaN
        else:
            beta_value = np.nan
            tier = 4
        
        # Round
        if pd.notna(beta_value):
            beta_value = round(beta_value / beta_rounding) * beta_rounding
        
        results.append({
            'ticker': ticker,
            'fiscal_year': year,
            'Beta': beta_value,
            'fallback_tier': tier,
            'sector_slope': row['sector_slope']
        })
    
    return pd.DataFrame(results)
```

### 5.5 Integration Point in EnhancedMetricsService

**Location to update:** `/home/ubuntu/cissa/backend/app/services/enhanced_metrics_service.py` lines 269-286

**Current stub:**
```python
def _calculate_beta(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Calculate Beta (simplified to 1.0 until timeseries data available)."""
    # ... stub implementation returns 1.0
```

**Will become:**
```python
async def _calculate_beta(
    self,
    dataset_id: UUID,
    fiscal_years: list,
    params: dict
) -> pd.DataFrame:
    """
    Full rolling OLS implementation with 4-tier fallback.
    
    Args:
        dataset_id: Dataset for fetching monthly returns
        fiscal_years: List of fiscal years to calculate for
        params: Parameters including beta_rounding, error_tolerance
    
    Returns:
        DataFrame with [ticker, fiscal_year, Beta, sector_slope, fallback_tier]
    """
    # Step 1: Fetch monthly returns data
    monthly_df = await self._fetch_monthly_returns(dataset_id)
    
    # Step 2: Pivot to (re, rm) format
    ols_data = self._pivot_returns_for_ols(monthly_df)
    
    # Step 3: Run rolling OLS per ticker
    all_regressions = []
    for ticker in ols_data['ticker'].unique():
        ticker_data = ols_data[ols_data['ticker'] == ticker]
        regression_results = self._calculate_rolling_ols(ticker_data, window=60)
        all_regressions.append(regression_results)
    
    monthly_betas = pd.concat(all_regressions)
    
    # Step 4: Annual alignment (merge with FY mapping)
    # [code to align monthly to fiscal years]
    annual_betas = self._align_to_fiscal_year(monthly_betas)
    
    # Step 5: Calculate sector averages
    sector_betas = annual_betas.groupby(['sector', 'year']).agg(
        sector_slope=('adjusted_slope', 'mean')
    )
    
    # Step 6: Calculate ticker averages
    ticker_avg_betas = annual_betas.groupby('ticker').agg(
        avg_slope=('adjusted_slope', 'mean')
    )
    
    # Step 7: 4-tier fallback
    final_betas = self._calculate_beta_with_fallback(
        annual_betas,
        sector_betas,
        ticker_avg_betas,
        error_tolerance=params['beta_relative_error_tolerance'] / 100.0,
        beta_rounding=params['beta_rounding']
    )
    
    return final_betas
```

---

## 6. SPECIFIC IMPLEMENTATION CHALLENGES & SOLUTIONS

### Challenge 6.1: Index Ticker Identification

**Problem:** Legacy uses `TICKER LIKE '%AS30%'` pattern. Backend identifier unknown.

**Solutions:**
1. **Query companies table for parent_index = 'ASX200'** (or similar)
2. **Search fundamentals for known index patterns:** "ASX30", "AS30 IDX", etc.
3. **Add to companies table:** Distinguish company rows vs. index rows

**Action:** Add validation query to identify index ticker(s) before OLS.

### Challenge 6.2: FY Alignment from Monthly Data

**Problem:** Monthly data has (fiscal_year, fiscal_month, fiscal_day); need to group by fiscal year.

**Solution:** Group-by fiscal_year directly; aggregate rolling OLS results by month-year then align to FY.

```python
# Group monthly regression results by fiscal_year, then take most recent before FY end
annual_betas = monthly_betas.groupby(['ticker', 'fiscal_year']).last().reset_index()
```

### Challenge 6.3: Sector Data Availability

**Problem:** Sector fallback requires sector column for every ticker.

**Solution:** Join with companies table to ensure sector availability.

```python
query = """
SELECT f.ticker, f.fiscal_year, c.sector, ...
FROM cissa.fundamentals f
JOIN cissa.companies c ON f.ticker = c.ticker
WHERE ...
"""
```

### Challenge 6.4: Parameter Conversion (Percentage vs. Decimal)

**Problem:** Backend stores as percentage (40.0), legacy expects decimal (0.8).

**Status:** NEED CLARIFICATION

**Options:**
1. Assume backend percentage is wrong; convert: `param_value / 100`
2. Assume backend correct; update legacy docs
3. Add explicit conversion in enhanced_metrics_service

### Challenge 6.5: Threading vs. Async

**Problem:** Legacy uses threading; backend uses async/await.

**Solution:** Use async all the way.
- Fetch data asynchronously
- Calculate OLS sequentially (statsmodels not async-safe)
- Insert batch asynchronously

```python
# Sequential OLS (can't parallelize statsmodels safely)
for ticker in ticker_list:
    regression_results = self._calculate_rolling_ols(...)

# Async insert
await self._insert_metrics_batch(dataset_id, param_set_id, results_df)
```

---

## 7. METRIC NAMES REFERENCE

### In Fundamentals Table (backend):
```
Company TSR (Monthly)        [percent] for equity returns (re)
Index TSR (Monthly)          [percent] for market returns (rm)
Risk-Free Rate (Monthly)     [percent] for risk-free rates
```

### In Legacy system:
```
Company TSR    [percent, converted to decimal (value/100 + 1) for OLS]
Index TSR      [percent, converted to decimal (value/100 + 1) for OLS]
```

### Query mapping:
- Legacy: `WHERE KEY='Company TSR'` → Backend: `WHERE metric_name='Company TSR (Monthly)'`
- Legacy: `WHERE KEY='Index TSR' AND TICKER LIKE '%AS30%'` → Backend: `WHERE metric_name='Index TSR (Monthly)' AND ticker=<index_ticker>`

---

## 8. PARAMETER SEMANTICS

### Backend Parameters Table Structure

```sql
SELECT * FROM cissa.parameters WHERE parameter_name LIKE 'beta%';

parameter_name                  | display_name                              | value_type | default_value
------------------------------|-------------------------------------------|-----------|---------------
beta_rounding                  | Beta Rounding                            | NUMERIC   | 0.1
beta_relative_error_tolerance  | Beta Relative Error Tolerance            | NUMERIC   | 40.0
```

### Interpretation Issues

**beta_relative_error_tolerance = 40.0**
- Stored as: percentage (40 = 40%)
- OR stored as: percentage basis points (40 = 0.4)?
- Legacy uses: decimal (0.8 = 80% threshold)

**RESOLUTION NEEDED:** Clarify backend semantics before implementation.

---

## 9. DATABASE DEPENDENCIES

### Required Tables
1. **fundamentals** - Monthly TSR data source
2. **companies** - Sector groupings for fallback
3. **fiscal_year_mapping** - For FY alignment
4. **parameters** - Configuration parameters
5. **parameter_sets** - Parameter overrides
6. **metrics_outputs** - Results storage

### Required Data
1. **Company TSR (Monthly)** records in fundamentals
2. **Index TSR (Monthly)** records in fundamentals
3. **Sector field** populated in companies table
4. **60+ consecutive months** of data per ticker (for OLS)

---

## 10. FILE REFERENCE SUMMARY

### Legacy Implementation
- **Core Logic:** `/home/ubuntu/cissa/example-calculations/src/executors/beta.py` (104 lines)
- **Integration:** `/home/ubuntu/cissa/example-calculations/src/engine/calculation.py` lines 78-79
- **Data Loading:** `/home/ubuntu/cissa/example-calculations/src/engine/sql.py` lines 259-280
- **Parameters:** `/home/ubuntu/cissa/example-calculations/src/config/parameters.py` lines 25-26, 113-138
- **Loaders:** `/home/ubuntu/cissa/example-calculations/src/engine/loaders.py` lines 163-172

### Backend Structure
- **Service:** `/home/ubuntu/cissa/backend/app/services/enhanced_metrics_service.py` lines 20-406
- **Repository:** `/home/ubuntu/cissa/backend/app/repositories/metrics_repository.py` lines 13-175
- **Schema:** `/home/ubuntu/cissa/backend/database/schema/schema.sql` lines 162-208 (fundamentals table)
- **Parameters:** `/home/ubuntu/cissa/backend/database/schema/schema.sql` lines 249-430 (parameters, metric_units)
- **Metrics Config:** `/home/ubuntu/cissa/backend/database/config/metric_units.json` lines 105-121

### Documentation
- **Planning:** `/home/ubuntu/cissa/.planning/LEGACY_METRICS_COMPLETE.md` lines 152-177 (Tier 4: Beta)
- **Architecture:** `/home/ubuntu/cissa/.planning/README.md` lines 78-102 (Phase structure)
- **Phase 06 Status:** `/home/ubuntu/cissa/.planning/06-L1-Metrics-Alignment/STATE.md` (Ready for Phase 07)

---

## 11. IMPLEMENTATION READINESS CHECKLIST

### Data & Schema
- [x] Monthly returns data available in fundamentals table
- [ ] Index ticker identifier verified
- [ ] Sector data populated in companies table for all tickers
- [ ] 60+ months available for primary tickers (needs validation query)
- [ ] FY alignment logic proven

### Backend Services
- [ ] statsmodels library added to requirements
- [ ] Async data fetching implemented
- [ ] OLS regression wrapper implemented
- [ ] 4-tier fallback logic implemented
- [ ] Annual alignment logic implemented
- [ ] Parameter conversion logic implemented
- [ ] Batch insertion logic adapted

### Testing
- [ ] Sample data validation (60+ months available)
- [ ] OLS regression verification (vs. legacy output)
- [ ] Fallback logic coverage (all 4 tiers)
- [ ] Parameter conversion accuracy
- [ ] Async/await error handling

### Documentation
- [ ] Beta calculation algorithm documented
- [ ] Parameter semantics clarified
- [ ] Data gaps resolved
- [ ] Migration guide created

---

## 12. NEXT STEPS (RECOMMENDED ORDER)

1. **Validate Data Availability** (Day 1)
   - Run query to count months per ticker
   - Identify index ticker identifier in fundamentals
   - Verify sector coverage in companies table
   - Check for data gaps/sparsity

2. **Clarify Parameter Semantics** (Day 1-2)
   - Confirm backend beta_relative_error_tolerance interpretation
   - Verify if backend vs. legacy values compatible
   - Update parameter_sets if needed

3. **Implement Data Fetching** (Day 2-3)
   - Add `_fetch_monthly_returns()` to EnhancedMetricsService
   - Add `_pivot_returns_for_ols()` transformation
   - Add FY alignment logic
   - Test with sample dataset

4. **Implement OLS Regression** (Day 3-4)
   - Add statsmodels to requirements.txt
   - Implement `_calculate_rolling_ols()` wrapper
   - Test window handling (< 60 months cases)
   - Validate output vs. legacy

5. **Implement 4-Tier Fallback** (Day 4-5)
   - Implement sector aggregation logic
   - Implement ticker aggregation logic
   - Implement fallback cascade
   - Implement error tracking (fallback_tier column)

6. **Integration & Testing** (Day 5-6)
   - Integrate with EnhancedMetricsService
   - Test end-to-end with async flow
   - Add unit tests for each component
   - Compare with legacy output

7. **Documentation & Deployment** (Day 6-7)
   - Create Phase 07 implementation guide
   - Update schema documentation
   - Prepare migration plan
   - Ready for code review

---

## APPENDIX A: PARAMETER MAPPING TABLE

| Legacy Parameter | Backend Parameter | Legacy Default | Backend Default | Conversion | Status |
|------------------|-------------------|-----------------|-----------------|------------|--------|
| error_tolerance | beta_relative_error_tolerance | 0.8 | 40.0 | ? / 100 | ⚠️ UNCLEAR |
| beta_rounding | beta_rounding | 0.1 | 0.1 | × 1 | ✅ CLEAR |
| approach_to_ke | cost_of_equity_approach | "Floating" | "Floating" | Direct | ✅ CLEAR |
| currency | currency_notation | "AUD" | "A$m" | Derived | ⚠️ DIFFERS |

---

## APPENDIX B: DATA FLOW DIAGRAM

```
Raw CSV Input (Company TSR.csv, Index TSR.csv)
    ↓
cissa.raw_data (all rows, unprocessed)
    ↓
[Pipeline: alignment + imputation]
    ↓
cissa.fundamentals (clean, monthly: Company TSR (Monthly), Index TSR (Monthly))
    ↓
[Phase 07: Beta Calculation]
    ├─ Fetch monthly returns (fundamentals)
    ├─ Pivot to (re, rm) columns
    ├─ Run rolling OLS per ticker (60-month window)
    ├─ Apply slope adjustment & error tolerance
    ├─ Align to fiscal years
    ├─ Calculate sector averages
    ├─ Execute 4-tier fallback
    └─ Prepare output records
    ↓
cissa.metrics_outputs (Beta, sector_slope, fallback_tier metadata)
```

---

## APPENDIX C: LEGACY SQL REFERENCES

### get_TSR() query (sql.py lines 259-280):
```sql
WITH CTSR AS (
    SELECT * FROM monthly_data WHERE KEY='Company TSR'
),
ITSR AS (
    SELECT * FROM monthly_data 
    WHERE KEY='Index TSR' AND TICKER LIKE '%AS30%'
)
SELECT
    a.ticker,
    a.date,
    ROUND((CAST(a.value AS DECIMAL)/100) + 1, 4) AS re,
    ROUND((CAST(b.value AS DECIMAL)/100) + 1, 4) AS rm
FROM CTSR a
INNER JOIN ITSR b ON a.date = b.date
ORDER BY TICKER, DATE;
```

---

**Document Version:** 1.0  
**Last Updated:** March 9, 2026  
**Status:** READY FOR PHASE 07 IMPLEMENTATION PLANNING
