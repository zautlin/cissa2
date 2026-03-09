# L1_METRICS_SQL_MAPPING.md — Complete Metric Reference Guide

**Document Purpose:** Comprehensive mapping of all 12 L1 metrics with legacy formulas, SQL equivalents, column mappings, inception logic, window function patterns, and edge cases.

**Date Created:** 2026-03-09  
**Source of Truth:** `example-calculations/src/executors/metrics.py` (lines 9-98)  
**Current Implementation:** `backend/database/schema/functions.sql`

---

## Overview

This document catalogs all 12 Level 1 (L1) metrics used in the CISSA financial analysis pipeline. These metrics are calculated from Bloomberg fundamentals data stored in PostgreSQL.

**Key Facts:**
- **7 Simple metrics:** No window functions required; calculated from input data only
- **5 Temporal metrics:** Require window functions (LAG, SUM OVER) and inception year logic
- **Inception logic:** Temporal metrics only calculated when `fiscal_year > companies.begin_year`
- **Parameter sensitivity:** FY_TSR output varies by parameter_set; metrics_outputs.UNIQUE constraint allows multiple rows per (ticker, fiscal_year)
- **Critical insight:** `fytsr` is INPUT data from Bloomberg, not calculated—eliminates circular dependency

---

## 12 L1 Metrics Inventory

### Simple Metrics (7) — No Window Functions

#### 1. **C_MC** — Market Cap (Calc MC)

| Aspect | Details |
|--------|---------|
| **Legacy Formula** | `C_MC = SPOT_SHARES × SHARE_PRICE` |
| **SQL Equivalent** | `SELECT ticker, fiscal_year, f1.numeric_value * f2.numeric_value FROM fundamentals f1 JOIN fundamentals f2 WHERE f1.metric_name = 'SPOT_SHARES' AND f2.metric_name = 'SHARE_PRICE'` |
| **SQL Function** | `fn_calc_market_cap(p_dataset_id UUID)` |
| **Input Metrics** | SPOT_SHARES (shares count), SHARE_PRICE (AUD) |
| **Output Data Type** | NUMERIC(18,2) — millions AUD |
| **Output Metric Name** | `Calc MC` |
| **Inception Year Logic** | Calculated for all fiscal years (no inception restriction) |
| **Special Handling** | NULL if either input is NULL; INNER JOIN filters automatically |
| **Edge Cases** | Zero share price (rare); missing data for either metric |
| **Performance** | < 500ms for ~11,000 records |
| **Reference Lines** | metrics.py line 29 |

**Legacy Code Context:**
```python
group = group.assign(C_MC=lambda data: (data['shrouts'] * data['price']))
```

**Database Mapping:**
| Legacy Column | Fundamentals Metric | Notes |
|---------------|-------------------|-------|
| shrouts | SPOT_SHARES | Count of shares outstanding |
| price | SHARE_PRICE | Market price per share |

---

#### 2. **C_ASSETS** — Operating Assets (Calc Assets)

| Aspect | Details |
|--------|---------|
| **Legacy Formula** | `C_ASSETS = TOTAL_ASSETS - CASH` |
| **SQL Equivalent** | `SELECT ticker, fiscal_year, f1.numeric_value - f2.numeric_value FROM fundamentals f1 JOIN fundamentals f2 WHERE f1.metric_name = 'TOTAL_ASSETS' AND f2.metric_name = 'CASH'` |
| **SQL Function** | `fn_calc_operating_assets(p_dataset_id UUID)` |
| **Input Metrics** | TOTAL_ASSETS, CASH (both millions AUD) |
| **Output Data Type** | NUMERIC(18,2) — millions AUD |
| **Output Metric Name** | `Calc Assets` |
| **Inception Year Logic** | Calculated for all fiscal years |
| **Special Handling** | NULL if either input is NULL; can be negative (rare) |
| **Edge Cases** | Cash > Total Assets (indicates data error); negative values possible |
| **Performance** | < 500ms for ~11,000 records |
| **Reference Lines** | metrics.py line 31 |

**Legacy Code Context:**
```python
group = (group.assign(C_ASSETS=lambda data: (data['assets'] - data['cash']))
```

**Database Mapping:**
| Legacy Column | Fundamentals Metric |
|---------------|-------------------|
| assets | TOTAL_ASSETS |
| cash | CASH |

---

#### 3. **OA** — Operating Assets Detail (Calc OA)

| Aspect | Details |
|--------|---------|
| **Legacy Formula** | `OA = C_ASSETS - FIXED_ASSETS - GOODWILL` |
| **SQL Equivalent** | `SELECT mo.ticker, mo.fiscal_year, mo.output_metric_value - f1.numeric_value - f2.numeric_value FROM metrics_outputs mo JOIN fundamentals f1, f2 WHERE mo.output_metric_name = 'Calc Assets' AND f1.metric_name = 'FIXED_ASSETS' AND f2.metric_name = 'GOODWILL'` |
| **SQL Function** | `fn_calc_operating_assets_detail(p_dataset_id UUID)` |
| **Input Metrics** | C_ASSETS (output from step 2), FIXED_ASSETS, GOODWILL (all millions AUD) |
| **Output Data Type** | NUMERIC(18,2) — millions AUD |
| **Output Metric Name** | `Calc OA` |
| **Inception Year Logic** | Calculated for all fiscal years |
| **Dependency** | **CRITICAL:** Requires C_ASSETS to be inserted into metrics_outputs first |
| **Special Handling** | Joins metrics_outputs (reads previously calculated C_ASSETS); can result in negative values |
| **Edge Cases** | Fixed assets + goodwill > C_ASSETS (indicates intangible-heavy company); negative OA possible |
| **Performance** | < 500ms for ~11,000 records (joins on metrics_outputs) |
| **Reference Lines** | metrics.py line 32 |

**Legacy Code Context:**
```python
.assign(OA=lambda data: (data['C_ASSETS'] - data['fixedassets'] - data['goodwill']))
```

**Database Mapping:**
| Legacy Column | Source | Notes |
|---------------|--------|-------|
| C_ASSETS | metrics_outputs | Previously calculated |
| fixedassets | FIXED_ASSETS | From fundamentals |
| goodwill | GOODWILL | From fundamentals |

---

#### 4. **OP_COST** — Operating Cost

| Aspect | Details |
|--------|---------|
| **Legacy Formula** | `OP_COST = REVENUE - OPERATING_INCOME` |
| **SQL Equivalent** | `SELECT ticker, fiscal_year, f1.numeric_value - f2.numeric_value FROM fundamentals f1 JOIN fundamentals f2 WHERE f1.metric_name = 'REVENUE' AND f2.metric_name = 'OPERATING_INCOME'` |
| **SQL Function** | `fn_calc_operating_cost(p_dataset_id UUID)` |
| **Input Metrics** | REVENUE, OPERATING_INCOME (millions AUD) |
| **Output Data Type** | NUMERIC(18,2) — millions AUD |
| **Output Metric Name** | `Calc OP Cost` |
| **Inception Year Logic** | Calculated for all fiscal years |
| **Special Handling** | NULL if either input NULL; can be negative if operating margin > 100% |
| **Edge Cases** | Negative operating cost (operating income > revenue); zero revenue |
| **Performance** | < 500ms for ~11,000 records |
| **Reference Lines** | metrics.py line 33 |

**Legacy Code Context:**
```python
group = group.assign(OP_COST=lambda data: (data['revenue'] - data['opincome']))
```

---

#### 5. **NON_OP_COST** — Non-Operating Cost

| Aspect | Details |
|--------|---------|
| **Legacy Formula** | `NON_OP_COST = OPERATING_INCOME - PROFIT_BEFORE_TAX` |
| **SQL Equivalent** | `SELECT ticker, fiscal_year, f1.numeric_value - f2.numeric_value FROM fundamentals f1 JOIN fundamentals f2 WHERE f1.metric_name = 'OPERATING_INCOME' AND f2.metric_name = 'PROFIT_BEFORE_TAX'` |
| **SQL Function** | `fn_calc_non_operating_cost(p_dataset_id UUID)` |
| **Input Metrics** | OPERATING_INCOME, PROFIT_BEFORE_TAX (millions AUD) |
| **Output Data Type** | NUMERIC(18,2) — millions AUD |
| **Output Metric Name** | `Calc NON OP Cost` |
| **Inception Year Logic** | Calculated for all fiscal years |
| **Special Handling** | Can be negative (PBT > OI indicates non-op income, e.g., gains on investments) |
| **Edge Cases** | Highly negative values (significant non-op income) |
| **Performance** | < 500ms for ~11,000 records |
| **Reference Lines** | metrics.py line 34 |

---

#### 6. **TAX_COST** — Tax Cost

| Aspect | Details |
|--------|---------|
| **Legacy Formula** | `TAX_COST = PROFIT_BEFORE_TAX - PROFIT_AFTER_TAX_EXCL_XORD` |
| **SQL Equivalent** | `SELECT ticker, fiscal_year, f1.numeric_value - f2.numeric_value FROM fundamentals f1 JOIN fundamentals f2 WHERE f1.metric_name = 'PROFIT_BEFORE_TAX' AND f2.metric_name = 'PROFIT_AFTER_TAX_EX'` |
| **SQL Function** | `fn_calc_tax_cost(p_dataset_id UUID)` |
| **Input Metrics** | PROFIT_BEFORE_TAX, PROFIT_AFTER_TAX_EX (millions AUD) |
| **Output Data Type** | NUMERIC(18,2) — millions AUD |
| **Output Metric Name** | `Calc TAX Cost` |
| **Inception Year Logic** | Calculated for all fiscal years |
| **Special Handling** | Can be negative (tax benefit/credit situations) |
| **Edge Cases** | Negative tax cost (tax refunds, losses carried forward) |
| **Performance** | < 500ms for ~11,000 records |
| **Reference Lines** | metrics.py line 35 |

---

#### 7. **XO_COST** — Extraordinary/Exceptional Cost

| Aspect | Details |
|--------|---------|
| **Legacy Formula** | `XO_COST = PROFIT_AFTER_TAX_EX - PROFIT_AFTER_TAX` |
| **SQL Equivalent** | `SELECT ticker, fiscal_year, f1.numeric_value - f2.numeric_value FROM fundamentals f1 JOIN fundamentals f2 WHERE f1.metric_name = 'PROFIT_AFTER_TAX_EX' AND f2.metric_name = 'PROFIT_AFTER_TAX'` |
| **SQL Function** | `fn_calc_extraordinary_cost(p_dataset_id UUID)` |
| **Input Metrics** | PROFIT_AFTER_TAX_EX, PROFIT_AFTER_TAX (millions AUD) |
| **Output Data Type** | NUMERIC(18,2) — millions AUD |
| **Output Metric Name** | `Calc XO Cost` |
| **Inception Year Logic** | Calculated for all fiscal years |
| **Special Handling** | Usually zero or small; can be positive (exceptional costs) or negative (exceptional gains) |
| **Edge Cases** | Large one-off items (asset write-downs, restructuring) |
| **Performance** | < 500ms for ~11,000 records |
| **Reference Lines** | metrics.py line 36 |

---

### Temporal Metrics (5) — Require Window Functions & Inception Logic

**Key Concept:** Temporal metrics introduce time-series dependencies within each company's sequence. They require:
1. **Window functions** (LAG, SUM OVER) to access historical data
2. **Inception logic** (`fiscal_year > companies.begin_year`) to determine eligibility
3. **Careful ordering** by fiscal_year within each ticker
4. **NULL handling** for inception year (no LAG_MC available)

---

#### 8. **LAG_MC** — Previous Year Market Cap (Helper Metric)

| Aspect | Details |
|--------|---------|
| **Legacy Formula** | `LAG_MC = LAG(C_MC, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year)` |
| **SQL Equivalent** | `SELECT ticker, fiscal_year, LAG(calc_mc, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year) AS lag_mc FROM (SELECT ... from fn_calc_market_cap(...))` |
| **Window Pattern** | `LAG(metric_value, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year)` |
| **First Appearance** | metrics.py line 30 |
| **Purpose** | Provides previous year's market cap for temporal metric calculations |
| **Result for First Year** | NULL (no prior year available) |
| **Result for Year 2+** | Previous fiscal year's C_MC value |
| **Not a stored metric** | LAG_MC is a calculated intermediate; not inserted into metrics_outputs as its own metric |
| **Used by** | ECF, NON_DIV_ECF (indirectly), EE, FY_TSR, FY_TSR_PREL |
| **Performance** | Negligible; window function scanned once over sorted data |

**Legacy Code Context:**
```python
group['LAG_MC'] = group.groupby('ticker')['C_MC'].shift(1)
```

---

#### 8. **ECF** — Economic Cash Flow (Temporal)

| Aspect | Details |
|--------|---------|
| **Legacy Formula** | `IF INCEPTION_IND == 1: ECF = LAG_MC × (1 + fytsr/100) - C_MC ELSE: NULL` |
| **SQL Equivalent** | `SELECT ticker, fiscal_year, CASE WHEN (fiscal_year > companies.begin_year) THEN LAG(c_mc) OVER (...) * (1 + f.numeric_value / 100.0) - current_c_mc ELSE NULL END FROM fundamentals f JOIN companies c WHERE f.metric_name = 'FY_TSR'` |
| **SQL Function** | `fn_calc_ecf(p_dataset_id UUID)` |
| **Input Data** | LAG_MC (window function over C_MC), fytsr (input metric), C_MC, companies.begin_year |
| **Output Data Type** | NUMERIC(18,2) — millions AUD |
| **Output Metric Name** | `Calc ECF` |
| **Window Pattern** | `LAG(C_MC, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year)` |
| **Inception Year Logic** | `CASE WHEN fiscal_year > companies.begin_year THEN ... ELSE NULL END` |
| **Special Handling** | **CRITICAL:** fytsr is INPUT data from fundamentals (not calculated) |
| **NULL Cases** | Inception year (fiscal_year == begin_year); missing LAG_MC; missing fytsr |
| **Edge Cases** | Division by 100 for percentage; LAG_MC = 0 (would cause zero return, handled naturally) |
| **Performance** | < 2 seconds for ~11,000 records (single window scan + 2 joins) |
| **Reference Lines** | metrics.py lines 30, 37-38, 84-88 |

**Legacy Code Context:**
```python
def calculate_economic_cash_flow(row):
    ecf = np.nan
    if row["INCEPTION_IND"] == 1:
        ecf = row['LAG_MC'] * (1 + row["fytsr"] / 100) - row['C_MC']
    return ecf

group['ECF'] = group.apply(calculate_economic_cash_flow, axis=1)
```

**Interpretation:** ECF measures the change in economic value from prior year, adjusted for historical total shareholder return. Positive ECF indicates value growth; negative indicates value decline.

---

#### 9. **NON_DIV_ECF** — Economic Cash Flow (Excluding Dividends)

| Aspect | Details |
|--------|---------|
| **Legacy Formula** | `NON_DIV_ECF = ECF + DIVIDENDS` |
| **SQL Equivalent** | `SELECT mo.ticker, mo.fiscal_year, mo.output_metric_value + f.numeric_value FROM metrics_outputs mo JOIN fundamentals f WHERE mo.output_metric_name = 'Calc ECF' AND f.metric_name = 'DIVIDENDS'` |
| **SQL Function** | `fn_calc_non_div_ecf(p_dataset_id UUID)` |
| **Input Data** | ECF (output metric), DIVIDENDS (input metric) |
| **Output Data Type** | NUMERIC(18,2) — millions AUD |
| **Output Metric Name** | `Calc NON DIV ECF` |
| **Inception Year Logic** | NULL if ECF is NULL (inherited from ECF) |
| **Dependency** | **CRITICAL:** Requires ECF to be inserted into metrics_outputs first |
| **NULL Cases** | If ECF is NULL (inception year); if DIVIDENDS is NULL (rare) |
| **Edge Cases** | Large dividend payments can reverse ECF sign |
| **Performance** | < 500ms for ~11,000 records (single join to metrics_outputs) |
| **Reference Lines** | metrics.py line 39 |

**Legacy Code Context:**
```python
group = group.assign(NON_DIV_ECF=lambda data: (data['ECF'] + data['dividend']))
```

**Interpretation:** NON_DIV_ECF includes dividend payments in the economic cash flow calculation; reflects full shareholder returns including distributions.

---

#### 10. **EE** — Economic Equity (Cumulative, Temporal)

| Aspect | Details |
|--------|---------|
| **Legacy Formula** | **Component:** `IF INCEPTION_IND == 0: EE_comp = TOTAL_EQUITY - MINORITY_INTEREST ELSE IF INCEPTION_IND == 1: EE_comp = PROFIT_AFTER_TAX - ECF` |
|  | **Cumulative:** `EE_cumsum = SUM(EE_comp) OVER (PARTITION BY ticker ORDER BY fiscal_year)` |
| **SQL Equivalent** | `WITH ee_component AS (SELECT ticker, fiscal_year, CASE WHEN (fiscal_year <= companies.begin_year) THEN f1.numeric_value - f2.numeric_value ELSE f3.numeric_value - mo_ecf.output_metric_value END AS ee_comp FROM ...) SELECT ticker, fiscal_year, SUM(ee_comp) OVER (PARTITION BY ticker ORDER BY fiscal_year) AS ee_cumsum` |
| **SQL Function** | `fn_calc_economic_equity(p_dataset_id UUID)` |
| **Input Data** | ECF (output metric), TOTAL_EQUITY, MINORITY_INTEREST, PROFIT_AFTER_TAX (input metrics), companies.begin_year |
| **Output Data Type** | NUMERIC(18,2) — millions AUD |
| **Output Metric Name** | `Calc EE` |
| **Window Pattern** | **Two windows:** `SUM(...) OVER (PARTITION BY ticker ORDER BY fiscal_year)` for cumulative; LAG implied in inception condition |
| **Inception Year Logic** | **Dual logic:** `IF fiscal_year <= begin_year THEN use equity ELSE use profit - ecf` |
| **Special Handling** | **CRITICAL:** Cumulative sum resets per ticker; PARTITION BY must include ticker only (not dataset_id) so entire company history is one cumsum stream |
| **NULL Cases** | First year: uses equity method (not NULL); subsequent years: NULL if ECF is NULL |
| **Edge Cases** | Very old companies (60+ years): cumsum accumulates rounding errors; NUMERIC type mitigates this |
| **Performance** | < 2 seconds for ~11,000 records (two window scans + multiple joins) |
| **Reference Lines** | metrics.py lines 37, 40, 91-97 |

**Legacy Code Context:**
```python
group['INCEPTION_IND'] = group.apply(is_inception_year, axis=1)
def calculate_economic_equity(row):
    ee = np.nan
    if row["INCEPTION_IND"] == 0:
        ee = row['eqiity'] - row['mi']          # Note: 'eqiity' is typo in legacy code
    elif row["INCEPTION_IND"] == 1:
        ee = row['pat'] - row['ECF']
    return ee

group['EE'] = group.apply(calculate_economic_equity, axis=1).cumsum()
```

**Interpretation:** EE tracks cumulative economic equity over company's history. Starting at book equity (year 0), then accumulating annual changes (profit - ECF).

---

#### 11. **FY_TSR** — Fiscal Year Total Shareholder Return (Parameter-Sensitive)

| Aspect | Details |
|--------|---------|
| **Legacy Formula** | `IF LAG_MC > 0 AND INCEPTION_IND == 1 THEN: IF incl_franking == "Yes" THEN adjusted_change = (C_MC - LAG_MC + ECF - dividend / (1 - frank_tax_rate)) * frank_tax_rate * value_franking_cr; FY_TSR = adjusted_change / LAG_MC ELSE: FY_TSR = (C_MC - LAG_MC + ECF) / LAG_MC ELSE: NULL` |
| **SQL Equivalent** | Complex CASE statement; see SQL Function section below |
| **SQL Function** | `fn_calc_fy_tsr(p_dataset_id UUID, p_param_set_id UUID)` |
| **Parameters** | incl_franking ("Yes" / "No"), frank_tax_rate (0-1), value_franking_cr (0-1) |
| **Input Data** | LAG_MC, C_MC, ECF, DIVIDENDS, companies.begin_year, parameter_sets.param_overrides |
| **Output Data Type** | NUMERIC(18,6) — dimensionless ratio (not percentage) |
| **Output Metric Name** | `Calc FY TSR` |
| **Window Pattern** | `LAG(C_MC, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year)` |
| **Inception Year Logic** | `AND fiscal_year > companies.begin_year` |
| **Parameter Sensitivity** | **CRITICAL:** Same (ticker, fiscal_year) produces different FY_TSR for different param_set_id; metrics_outputs.UNIQUE constraint allows this |
| **NULL Cases** | LAG_MC <= 0; inception year; missing required inputs |
| **Edge Cases** | Division by (1 - frank_tax_rate) if frank_tax_rate = 1.0 (mathematical singularity); LAG_MC = 0 (edge case) |
| **Performance** | < 2 seconds for ~11,000 records × N parameter sets |
| **Reference Lines** | metrics.py lines 47-63 |

**Legacy Code Context:**
```python
def calculate_fy_tsr(row, inputs):
    incl_franking = inputs['incl_franking']
    frank_tax_rate = inputs['frank_tax_rate']
    value_franking_cr = inputs['value_franking_cr']
    fy_tsr = np.nan
    lag_mc = row['LAG_MC']
    if lag_mc > 0:
        if row["INCEPTION_IND"] == 1:
            if incl_franking == "Yes":
                div = row['dividend'] / (1 - frank_tax_rate)
                change_in_cap = row['C_MC'] - row['LAG_MC'] + row['ECF'] - div
                adjusted_change = change_in_cap * frank_tax_rate * value_franking_cr
                fy_tsr = adjusted_change / lag_mc
            else:
                change_in_cap = row['C_MC'] - row['LAG_MC'] + row['ECF']
                fy_tsr = change_in_cap / lag_mc
    return fy_tsr

group['FY_TSR'] = group.apply(lambda data: calculate_fy_tsr(data, inputs), axis=1)
```

**Interpretation:** FY_TSR measures total shareholder return (capital appreciation + economic cash flow) as a percentage of prior year market cap. Franking adjustment inflates returns when franking credits are valued.

---

#### 12. **FY_TSR_PREL** — Fiscal Year TSR (Preliminary)

| Aspect | Details |
|--------|---------|
| **Legacy Formula** | `IF INCEPTION_IND == 1: FY_TSR_PREL = FY_TSR + 1 ELSE: NULL` |
| **SQL Equivalent** | `SELECT mo.ticker, mo.fiscal_year, mo.output_metric_value + 1 FROM metrics_outputs mo WHERE mo.output_metric_name = 'Calc FY TSR' AND mo.param_set_id = p_param_set_id` |
| **SQL Function** | `fn_calc_fy_tsr_prel(p_dataset_id UUID, p_param_set_id UUID)` |
| **Input Data** | FY_TSR (output metric) |
| **Output Data Type** | NUMERIC(18,6) — dimensionless ratio (1.0 = 0% return, 1.05 = 5% return) |
| **Output Metric Name** | `Calc FY TSR PREL` |
| **Inception Year Logic** | NULL if FY_TSR is NULL (inherited) |
| **Parameter Sensitivity** | Inherits from FY_TSR; per-param_set metric |
| **Dependency** | **CRITICAL:** Requires FY_TSR to be inserted into metrics_outputs first |
| **NULL Cases** | If FY_TSR is NULL |
| **Edge Cases** | None (simple arithmetic) |
| **Performance** | < 500ms for ~11,000 records (single join to metrics_outputs) |
| **Reference Lines** | metrics.py lines 66-70 |

**Legacy Code Context:**
```python
def calculate_fy_tsr_prel(row):
    fy_tsr_prel = np.nan
    if row["INCEPTION_IND"] == 1:
        fy_tsr_prel = row['FY_TSR'] + 1
    return fy_tsr_prel

group['FY_TSR_PREL'] = group.apply(calculate_fy_tsr_prel, axis=1)
```

**Interpretation:** FY_TSR_PREL is a convenience metric; adds 1 to FY_TSR to convert from return format (0.05 = 5% return) to growth factor format (1.05 = value grows to 105% of prior).

---

## Database Column Mapping Table

Complete mapping from legacy Python column names to PostgreSQL fundamentals metrics and database schema:

| Legacy Column | Python Variable | Fundamentals Metric | Database Type | Input/Output | Notes |
|---------------|-----------------|-------------------|----------------|-------------|-------|
| shrouts | SPOT_SHARES | SPOT_SHARES | NUMERIC(18,2) | Input | Share count outstanding |
| price | SHARE_PRICE | SHARE_PRICE | NUMERIC(18,2) | Input | Per-share market price |
| revenue | REVENUE | REVENUE | NUMERIC(18,2) | Input | Top-line sales |
| opincome | OPERATING_INCOME | OPERATING_INCOME | NUMERIC(18,2) | Input | Operating profit |
| pbt | PROFIT_BEFORE_TAX | PROFIT_BEFORE_TAX | NUMERIC(18,2) | Input | Profit before tax |
| patxo | PROFIT_AFTER_TAX_EX | PROFIT_AFTER_TAX_EX | NUMERIC(18,2) | Input | PAT excl. extraordinary items |
| pat | PROFIT_AFTER_TAX | PROFIT_AFTER_TAX | NUMERIC(18,2) | Input | Net income |
| assets | TOTAL_ASSETS | TOTAL_ASSETS | NUMERIC(18,2) | Input | Balance sheet total |
| cash | CASH | CASH | NUMERIC(18,2) | Input | Cash & equivalents |
| fixedassets | FIXED_ASSETS | FIXED_ASSETS | NUMERIC(18,2) | Input | Property, plant, equipment |
| goodwill | GOODWILL | GOODWILL | NUMERIC(18,2) | Input | Intangible assets |
| eqiity | TOTAL_EQUITY | TOTAL_EQUITY | NUMERIC(18,2) | Input | Shareholders' equity (note: typo in legacy) |
| mi | MINORITY_INTEREST | MINORITY_INTEREST | NUMERIC(18,2) | Input | Non-controlling interests |
| dividend | DIVIDENDS | DIVIDENDS | NUMERIC(18,2) | Input | Cash dividends paid |
| **fytsr** | **FY_TSR** | **FY_TSR** | **NUMERIC(6,2)** | **Input** | **KEY:** Bloomberg input data (not calculated) |
| inception | begin_year | companies.begin_year | INTEGER | Reference | Company founding year |
| C_MC | Calc MC | (calculated) | NUMERIC(18,2) | Output | Market cap |
| LAG_MC | (window function) | (calculated) | NUMERIC(18,2) | Intermediate | Previous year's C_MC |
| C_ASSETS | Calc Assets | (calculated) | NUMERIC(18,2) | Output | Operating assets |
| OA | Calc OA | (calculated) | NUMERIC(18,2) | Output | Operating assets detail |
| OP_COST | Calc OP Cost | (calculated) | NUMERIC(18,2) | Output | Operating expenses |
| NON_OP_COST | Calc NON OP Cost | (calculated) | NUMERIC(18,2) | Output | Non-operating expenses |
| TAX_COST | Calc TAX Cost | (calculated) | NUMERIC(18,2) | Output | Tax expense |
| XO_COST | Calc XO Cost | (calculated) | NUMERIC(18,2) | Output | Extraordinary items |
| ECF | Calc ECF | (calculated, temporal) | NUMERIC(18,2) | Output | Economic cash flow |
| NON_DIV_ECF | Calc NON DIV ECF | (calculated, temporal) | NUMERIC(18,2) | Output | ECF + dividends |
| EE | Calc EE | (calculated, temporal, cumsum) | NUMERIC(18,2) | Output | Economic equity (cumulative) |
| FY_TSR | Calc FY TSR | (calculated, temporal, param-sensitive) | NUMERIC(18,6) | Output | Total shareholder return |
| FY_TSR_PREL | Calc FY TSR PREL | (calculated, temporal, param-sensitive) | NUMERIC(18,6) | Output | TSR + 1 (growth factor form) |

**Key Observations:**
- All input metrics stored in fundamentals table with metric_name and numeric_value columns
- All output metrics stored in metrics_outputs table
- fytsr is Bloomberg input data (not a calculated output)
- Temporal metrics inherit inception logic from ECF forward
- Parameter-sensitive metrics (FY_TSR, FY_TSR_PREL) linked to parameter_sets via param_set_id

---

## Inception Year Logic — Critical for Temporal Metrics

### Concept
Inception year logic determines when a company's economic data becomes "meaningful" for calculation purposes. The key insight is:

```
INCEPTION_IND = 1  if  fiscal_year > companies.begin_year
INCEPTION_IND = 0  if  fiscal_year <= companies.begin_year
```

### Purpose
- **Inception year (fiscal_year == begin_year):** Use balance-sheet equity as starting point
- **Post-inception years (fiscal_year > begin_year):** Use change-in-equity formula

### SQL Implementation
```sql
-- Naive approach (single column comparison):
CASE 
  WHEN t1.fiscal_year > c.begin_year THEN 1
  ELSE 0
END

-- Better approach (with NULL handling):
CASE 
  WHEN c.begin_year IS NULL THEN 0  -- Handle NULL begin_year
  WHEN t1.fiscal_year > c.begin_year THEN 1
  ELSE 0
END
```

### Impact on Each Metric

| Metric | Behavior if INCEPTION_IND == 0 | Behavior if INCEPTION_IND == 1 |
|--------|---------|---------|
| Simple metrics (C_MC, C_ASSETS, etc.) | Calculated normally | Calculated normally |
| LAG_MC | Not used | Accessed via window function |
| ECF | NULL | Calculated using LAG_MC |
| NON_DIV_ECF | NULL | Calculated using ECF + DIVIDENDS |
| EE | Uses equity method: TOTAL_EQUITY - MINORITY_INTEREST | Uses change method: PROFIT_AFTER_TAX - ECF |
| FY_TSR | NULL | Calculated (if LAG_MC > 0) |
| FY_TSR_PREL | NULL | Calculated as FY_TSR + 1 |

### Important: NULL begin_year Handling
**Current Risk:** If `companies.begin_year IS NULL`, inception logic breaks.
**Mitigation:** This phase adds `NOT NULL` constraint (REQ-D1) to ensure all companies have begin_year defined.

---

## Window Function Patterns

PostgreSQL window functions are used extensively in temporal metrics. Here are the key patterns:

### Pattern 1: Previous Row Lookup (LAG)
**Used by:** ECF, FY_TSR, FY_TSR_PREL (indirectly via LAG_MC)

```sql
SELECT
  ticker,
  fiscal_year,
  calc_mc,
  LAG(calc_mc, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year) AS lag_mc
FROM metric_base
```

**Behavior:**
- Sorts data by fiscal_year within each ticker
- For each row, retrieves value from 1 row prior
- First row in sequence returns NULL (no prior value)
- Result for year 2020: Value from 2019 (if both exist)

**Gotcha:** Year gaps (e.g., missing 2018-2019) cause LAG to shift incorrectly (see GAP_DETECTION.md)

### Pattern 2: Cumulative Sum (SUM OVER)
**Used by:** EE (Economic Equity)

```sql
WITH ee_component AS (
  SELECT
    ticker,
    fiscal_year,
    CASE
      WHEN fiscal_year <= c.begin_year THEN (e.numeric_value - mi.numeric_value)
      ELSE (pat.numeric_value - ecf.output_metric_value)
    END AS ee_comp
  FROM ...
)
SELECT
  ticker,
  fiscal_year,
  SUM(ee_comp) OVER (PARTITION BY ticker ORDER BY fiscal_year) AS ee_cumsum
FROM ee_component
```

**Behavior:**
- Accumulates values from first row to current row within each partition
- PARTITION BY ticker ensures reset per company
- ORDER BY fiscal_year ensures chronological order
- Row 1: Sum of row 1 value
- Row 2: Sum of rows 1-2
- Row N: Sum of rows 1 through N

**Effect:** Produces running total of economic equity over company's history.

### Pattern 3: Row Number within Partition
**Used by:** Gap detection (diagnostic, not in production metrics)

```sql
SELECT
  ticker,
  fiscal_year,
  ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year) AS row_num,
  (fiscal_year - ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year)) AS gap_indicator
FROM metric_base
```

**Purpose:** Identifies year gaps
- If fiscal_year == 2015, 2016, 2017, 2020: ROW_NUMs are 1, 2, 3, 4
- Gap indicator: 2015-1=2014, 2016-2=2014, 2017-3=2014, 2020-4=2016
- Change in gap_indicator signals a missing year

---

## Performance & Index Requirements

### Query Execution Time Baselines

| Operation | Dataset Size | Expected Time | Achieved | Notes |
|-----------|--------------|---------------|----------|-------|
| fn_calc_market_cap | 11,000 | < 500ms | ✅ | Simple join, no window |
| fn_calc_operating_assets | 11,000 | < 500ms | ✅ | Simple join, no window |
| fn_calc_ecf (with window) | 11,000 | < 2s | To verify | LAG + 2 joins |
| fn_calc_economic_equity (cumsum) | 11,000 | < 2s | To verify | SUM OVER + 3+ joins |
| fn_calc_fy_tsr (with params) | 11,000 × N_params | < 2s per param set | To verify | LAG + joins + CASE logic |
| All 12 metrics (batch) | 132,000 | 5-10s | To verify | All together |

### Index Strategy

**Current indexes (assumed to exist):**
- `idx_fundamentals_dataset_ticker_fy` — (dataset_id, ticker, fiscal_year)
- `idx_fundamentals_ticker_metric_fy` — (ticker, metric_name, fiscal_year)
- `idx_metrics_outputs_ticker_fy` — (ticker, fiscal_year)
- `idx_companies_ticker` — (ticker)

**Recommended additional indexes (if performance degrades):**
- `idx_fundamentals_metric_name` — For rapid filtering by metric_name
- `idx_metrics_outputs_output_metric_name` — For filtering by output metric type
- `idx_parameter_sets_param_set_id` — For param_set join (likely PK, already indexed)

### Query Optimization Notes
1. **Metric filtering:** WHERE f.metric_name = 'X' runs quickly with index; avoid function calls in WHERE clause
2. **Window function cost:** LAG, SUM OVER have O(N log N) cost due to sort requirement; do once, reuse result
3. **Join order:** Filter by dataset_id early; use INNER JOIN where possible to eliminate rows quickly
4. **NUMERIC precision:** Use NUMERIC (not FLOAT) to avoid rounding errors; minimal performance impact

---

## Known Gotchas & Mitigations

### Gotcha 1: Year Gaps in LAG Window Function

**Problem:**
If a company has missing fiscal years in the fundamentals data, LAG shifts incorrectly.

**Example:**
```
Company: ACME Inc.
Fiscal Years: 2015, 2016, 2017, 2020, 2021  (missing 2018, 2019)

LAG(C_MC) OVER (PARTITION BY ticker ORDER BY fiscal_year):
- 2015: NULL (no prior)
- 2016: 2015's C_MC ✓
- 2017: 2016's C_MC ✓
- 2020: 2017's C_MC ✗ WRONG! Should be NULL or 2019's (doesn't exist)
- 2021: 2020's C_MC ✓

Effect on ECF:
- ECF(2020) = LAG_MC(2017) × (1 + fytsr(2020)/100) - C_MC(2020)
- This assumes 2020 value changed from 2017—incorrect! Missing 2018-2019 data.
```

**Mitigation (Documented in GAP_DETECTION.md):**
1. **Detection:** Query uses `fiscal_year - ROW_NUMBER()` to identify gaps
2. **Action:** Log warning in function comments; test with sample data
3. **User awareness:** Document in API specification that results may be unreliable for companies with missing years
4. **Future:** Consider NULL-filling for missing years (Phase 07+)

**Why Not Fixed:** Legacy Python implementation has same behavior; aligning with legacy is design goal.

---

### Gotcha 2: NULL inception Year (begin_year IS NULL)

**Problem:**
If companies.begin_year is NULL, inception logic fails to classify years correctly.

**Current State:** Some companies may have NULL begin_year (data quality issue).

**Impact:**
```sql
-- Broken:
CASE WHEN fiscal_year > c.begin_year THEN 1 ELSE 0 END
-- If begin_year IS NULL: Returns 0 for all years (incorrect!)

-- Fixed:
CASE WHEN c.begin_year IS NULL THEN 0
     WHEN fiscal_year > c.begin_year THEN 1
     ELSE 0 END
-- Treats NULL as "no inception" (conservative; results in no temporal metrics)
```

**Mitigation (REQ-D1):**
Add NOT NULL constraint to companies.begin_year during Task 3:
```sql
ALTER TABLE companies ADD CONSTRAINT chk_begin_year_not_null 
  CHECK (begin_year IS NOT NULL);
```

This forces data validation during ingestion; no more NULL values.

---

### Gotcha 3: Parameter Sensitivity in FY_TSR

**Problem:**
Same (ticker, fiscal_year) can produce different FY_TSR values depending on parameter_set.

**Example:**
```
Ticker: BHP (BHP Billiton), Fiscal Year 2023
Parameter Set A (incl_franking=Yes, frank_tax_rate=0.30): FY_TSR = 0.12 (12%)
Parameter Set B (incl_franking=No, frank_tax_rate=0.30): FY_TSR = 0.08 (8%)

Both stored in metrics_outputs with same ticker/year but different param_set_id.
```

**User Pitfall:**
```sql
-- WRONG: Returns multiple rows for same (ticker, year)
SELECT * FROM metrics_outputs 
WHERE ticker = 'BHP' AND fiscal_year = 2023 AND output_metric_name = 'Calc FY TSR';

-- CORRECT: Specify param_set_id
SELECT * FROM metrics_outputs 
WHERE ticker = 'BHP' AND fiscal_year = 2023 AND output_metric_name = 'Calc FY TSR'
  AND param_set_id = '12345678-1234-1234-1234-123456789012';
```

**Mitigation:**
- Document in API specification: Always filter by param_set_id for FY_TSR and FY_TSR_PREL
- Provide default param_set_id in queries
- Add examples in README

---

### Gotcha 4: NUMERIC Precision Over 60+ Years

**Problem:**
EE is cumulative sum over 60+ years; rounding errors accumulate.

**Example:**
```
Year 1: EE_comp = 1234.567
Year 2: EE_comp = 5678.234; EE_cumsum = 1234.567 + 5678.234 = 6912.801
...
Year 60: EE_comp = 999.999; EE_cumsum = ?? (accumulated errors)

If using FLOAT: Precision loss after ~15 significant digits
If using NUMERIC: Maintains 18 digits (sufficient for 60 years)
```

**Mitigation:**
- Use NUMERIC(18,2) in all SQL functions (not FLOAT)
- Round results to 2 decimal places in output
- Test EE cumsum against legacy Python reference; log acceptable error threshold (< 0.01 AUD)

---

### Gotcha 5: LAG_MC = 0 Edge Case

**Problem:**
If LAG_MC = 0 (prior year market cap was zero), FY_TSR division by zero.

**Example:**
```sql
-- Broken (division by zero):
SELECT ... , (C_MC - LAG_MC + ECF) / LAG_MC FROM ...  -- If LAG_MC = 0, ERROR

-- Fixed (with guard):
SELECT ... , CASE WHEN LAG_MC > 0 THEN (C_MC - LAG_MC + ECF) / LAG_MC ELSE NULL END
```

**Mitigation (Already in Legacy Code):**
Legacy implementation checks `if lag_mc > 0` before calculating FY_TSR. SQL functions replicate this check.

---

### Gotcha 6: fytsr % vs. Decimal Conversion

**Problem:**
fytsr is stored as percentage (e.g., "12.5" for 12.5%); formula requires decimal (0.125).

**Example:**
```sql
-- WRONG:
ecf = LAG_MC * (1 + fytsr) - C_MC  -- If fytsr=12.5, result is inflated by 1000x

-- CORRECT:
ecf = LAG_MC * (1 + fytsr / 100) - C_MC  -- Converts 12.5 to 0.125
```

**Mitigation:**
All SQL functions include `/100` divisor. Documented in comments.

---

### Gotcha 7: Division by (1 - frank_tax_rate) Singularity

**Problem:**
FY_TSR calculation has: `div = dividend / (1 - frank_tax_rate)`
If frank_tax_rate = 1.0, denominator = 0 → division by zero.

**Valid Range:** frank_tax_rate ∈ [0, 0.45] (tax rates don't exceed 45%)

**Mitigation:**
- Document parameter constraints in parameter_sets documentation
- Add CHECK constraint in SQL (optional): `frank_tax_rate < 1.0`
- Accept as acceptable risk if parameters validated during ingestion

---

## Summary: Execution Checklist for SQL Functions

To implement all 12 metrics in PostgreSQL:

**Phase 1: Simple Metrics (7)**
- ✅ fn_calc_market_cap — Done
- ✅ fn_calc_operating_assets — Done
- ✅ fn_calc_operating_assets_detail — Done
- ✅ fn_calc_operating_cost — Done
- ✅ fn_calc_non_operating_cost — Done
- ✅ fn_calc_tax_cost — Done
- ✅ fn_calc_extraordinary_cost — Done

**Phase 2: Temporal Metrics (5)** — Task 3
- ❌ fn_calc_ecf — Requires window function + inception logic
- ❌ fn_calc_non_div_ecf — Depends on fn_calc_ecf
- ❌ fn_calc_economic_equity — Requires cumulative sum + inception logic
- ❌ fn_calc_fy_tsr — Requires window function + parameters
- ❌ fn_calc_fy_tsr_prel — Depends on fn_calc_fy_tsr

**Pre-requisites (Task 3):**
- Add NOT NULL constraint to companies.begin_year
- Verify parameter_sets table has franking parameters
- Ensure fytsr input data exists in fundamentals

---

## Related References

- **Legacy Source:** `example-calculations/src/executors/metrics.py` (lines 9-98)
- **Current SQL:** `backend/database/schema/functions.sql` (lines 9-542)
- **Database Schema:** `backend/database/schema/schema.sql`
- **Config:** `backend/database/config/metric_units.json`
- **Service Layer:** `backend/app/services/metrics_service.py`
- **Gap Detection Strategy:** `.planning/06-L1-Metrics-Alignment/GAP_DETECTION.md`
- **Parameter Configuration:** `.planning/06-L1-Metrics-Alignment/PARAMETER_MAPPING.md`

