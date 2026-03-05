# Financial Metrics Denormalized Fact Table

## Overview

A single consolidated fact table (`financial_metrics_fact_table.csv`) created by denormalizing all Bloomberg financial data metrics into a common dimensional format.

**File:** `/home/ubuntu/cissa/input-data/ASX/consolidated-data/financial_metrics_fact_table.csv`  
**Status:** ✅ Ready for PostgreSQL loading  
**Size:** 15.45 MB  
**Total Records:** 275,343 (140,670 fiscal + 134,673 monthly)

---

## Schema

The fact table contains the following columns:

| Column | Type | Description |
|--------|------|-------------|
| **Ticker** | String | Company/Index identifier (e.g., "BHP AU Equity") |
| **Period** | String | Time period (e.g., "FY 2002" for fiscal or ISO date "YYYY-MM-DD" for monthly) |
| **Period_Type** | String | Type of period: `FISCAL` or `MONTHLY` |
| **Metric** | String | Canonical metric name (database_name, uppercase) - see metric_units reference |
| **Value** | String/Numeric | The actual measurement value |
| **Currency** | String | Currency code (2 currencies: AUD, other) |

---

## Data Dimensions

### Tickers
- **Total:** 568 unique tickers
- **Companies:** 500 active companies
- **Indices/Series:** 68 (indices and risk-free rates)

### Metrics (20 Total)

All metrics are stored with their canonical `database_name` value in the Metric column. The mapping between human-readable names and database names is maintained in the `metric_units` reference table.

#### Annual Financial Metrics (14 metrics - Period_Type = FISCAL)

| metric_name | worksheet_name | database_name | unit |
|---|---|---|---|
| Revenue | Revenue.csv | **REVENUE** | millions |
| Operating Income | Op Income.csv | **OPERATING_INCOME** | millions |
| Profit Before Tax | PBT.csv | **PROFIT_BEFORE_TAX** | millions |
| Profit After Tax | PAT.csv | **PROFIT_AFTER_TAX** | millions |
| Profit After Tax (Exc) | PAT XO.csv | **PROFIT_AFTER_TAX_EX** | millions |
| Cash | Cash.csv | **CASH** | millions |
| Fixed Assets | FA.csv | **FIXED_ASSETS** | millions |
| Goodwill | GW.csv | **GOODWILL** | millions |
| Market Cap | MC.csv | **MARKET_CAP** | millions |
| Minority Interest | MI.csv | **MINORITY_INTEREST** | millions |
| Dividends | Div.csv | **DIVIDENDS** | millions |
| Franking | Franking.csv | **FRANKING** | millions |
| Total Assets | Total Assets.csv | **TOTAL_ASSETS** | millions |
| Total Equity | Total Equity.csv | **TOTAL_EQUITY** | millions |

#### TSR & Share Metrics (3 metrics - Period_Type = FISCAL)

| metric_name | worksheet_name | database_name | unit |
|---|---|---|---|
| FY TSR | FY TSR.csv | **FY_TSR** | % |
| Spot Shares | Spot Shares.csv | **SPOT_SHARES** | number of shares |
| Share Price | Share Price.csv | **SHARE_PRICE** | millions |

#### Monthly Performance Metrics (3 metrics - Period_Type = MONTHLY)

| metric_name | worksheet_name | database_name | unit |
|---|---|---|---|
| Company TSR (Monthly) | Company TSR.csv | **COMPANY_TSR** | % |
| Index TSR (Monthly) | Index TSR.csv | **INDEX_TSR** | % |
| Risk-Free Rate (Monthly) | Rf.csv | **RISK_FREE_RATE** | % |

### Periods

#### Fiscal Periods
- **22 unique fiscal years:** FY 2002 through FY 2023
- **Format:** "FY YYYY" (e.g., "FY 2002")
- **Coverage:** Most companies have data for 20-22 years

#### Monthly Periods
- **541 unique calendar months**
- **Format:** ISO 8601 date format (YYYY-MM-DD)
- **Example:** "1981-11-30", "1981-12-31", "1982-01-29"
- **Source:** Converted from Excel date serials during denormalization
- **Note:** These represent calendar month endpoints, not individual daily trading data

### Currencies
- **2 unique currency codes:**
  - **AUD** (Australian Dollar) - primary for ASX companies
  - Other currencies for indices/series

---

## Record Distribution

| Period Type | Records | Details |
|-------------|---------|---------|
| **FISCAL** | 140,670 | 568 entities × 17 fiscal metrics × 22 years (approximately) |
| **MONTHLY** | 134,673 | 568 entities × 3 monthly metrics × 541 months (approximately) |
| **TOTAL** | **275,343** | - |

---

## Data Quality

### Characteristics
- ✅ **Complete:** All source metric data preserved
- ✅ **Clean:** Empty cells excluded
- ✅ **Consistent:** Uniform structure across all metrics
- ✅ **Normalized:** All metrics stored with canonical database_name values
- ✅ **Validated:** All metrics have corresponding entries in metric_units table
- ⚠️ **Mixed currencies:** Currency varies by company/index
- ⚠️ **Sparse data:** Some companies/indices have missing periods

### Known Issues
- Some #N/A values excluded from monthly metrics
- Empty ticker records (rare) from data quality issues
- Blank/empty currency values for some index records
- Some companies have incomplete year coverage in fiscal data

---

## Sample Records

```
Ticker,Period,Period_Type,Metric,Value,Currency
BHP AU Equity,FY 2002,FISCAL,REVENUE,30390.0379,AUD
BHP AU Equity,FY 2003,FISCAL,REVENUE,26823.8732,AUD
BHP AU Equity,FY 2002,FISCAL,CASH,2660.6318999999999,AUD
BHP AU Equity,FY 2003,FISCAL,CASH,2313.6552999999999,AUD
BHP AU Equity,1981-11-30,MONTHLY,COMPANY_TSR,9.054,AUD
BHP AU Equity,1981-12-31,MONTHLY,COMPANY_TSR,-2.814,AUD
ASX Index,1981-11-30,MONTHLY,INDEX_TSR,8.123,AUD
1208 HK Equity,FY 2002,FISCAL,REVENUE,10362.1962,
```

**Notes:**
- Metric column shows canonical database_name (REVENUE, CASH, COMPANY_TSR, etc.)
- All values are stored as text strings, convert to DECIMAL for calculations
- Currency may be empty for index/series records
- Monthly periods are calendar month endpoints in ISO format (YYYY-MM-DD)

---

## Metric Units Reference Table

The `metric_units` table (in PostgreSQL) provides the authoritative mapping between display names and database names:

### Structure
```sql
CREATE TABLE metric_units (
    metric_units_id SERIAL PRIMARY KEY,
    metric_name VARCHAR(255) NOT NULL UNIQUE,
    unit VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Configuration Source
- **File:** `backend/database/config/metric_units.json`
- **Purpose:** Maps metric_name ↔ worksheet_name ↔ database_name ↔ unit
- **Population:** Via `schema_manager.py init_metric_units()`
- **Usage:** Validation during data ingestion

### Why Three Names?

| Name | Purpose | Example |
|------|---------|---------|
| **metric_name** | Human-readable display name for documentation and config | "Operating Income" |
| **worksheet_name** | Actual CSV filename in extracted-worksheets/ (source of truth) | "Op Income.csv" |
| **database_name** | Canonical uppercase value stored in raw_data.metric_name column | "OPERATING_INCOME" |
| **unit** | Measurement unit for the metric | "millions", "%", "number of shares" |

This separation enables:
1. ✅ **Reliable file discovery:** worksheet_name is explicit, not derived
2. ✅ **Normalized database values:** database_name enforces consistency
3. ✅ **Human-friendly documentation:** metric_name for readability
4. ✅ **Validation:** All metrics validated against metric_units during ingestion

### Complete Reference

```json
[
  {
    "metric_name": "Revenue",
    "worksheet_name": "Revenue.csv",
    "database_name": "REVENUE",
    "unit": "millions"
  },
  {
    "metric_name": "Operating Income",
    "worksheet_name": "Op Income.csv",
    "database_name": "OPERATING_INCOME",
    "unit": "millions"
  },
  ...
  {
    "metric_name": "Company TSR (Monthly)",
    "worksheet_name": "Company TSR.csv",
    "database_name": "COMPANY_TSR",
    "unit": "%"
  }
]
```

---

## PostgreSQL Schema

### Create Table

```sql
CREATE TABLE financial_metrics (
    ticker VARCHAR(50) NOT NULL,
    period VARCHAR(20) NOT NULL,
    period_type VARCHAR(10) NOT NULL,
    metric VARCHAR(100) NOT NULL,
    value VARCHAR(50),
    currency VARCHAR(10),
    PRIMARY KEY (ticker, period, period_type, metric)
);

CREATE INDEX idx_ticker ON financial_metrics(ticker);
CREATE INDEX idx_period ON financial_metrics(period);
CREATE INDEX idx_metric ON financial_metrics(metric);
CREATE INDEX idx_currency ON financial_metrics(currency);
CREATE INDEX idx_period_type ON financial_metrics(period_type);
```

### Load Data

```sql
\COPY financial_metrics(ticker, period, period_type, metric, value, currency) 
FROM 'financial_metrics_fact_table.csv' 
WITH (FORMAT CSV, HEADER);
```

### Verify Load

```sql
SELECT COUNT(*) FROM financial_metrics;  -- Should be 275,343

SELECT DISTINCT metric FROM financial_metrics ORDER BY metric;
-- Should show all 20 database_name values (REVENUE, OPERATING_INCOME, etc.)

SELECT DISTINCT period_type FROM financial_metrics;
-- Should show: FISCAL, MONTHLY
```

---

## Usage Examples

### Query 1: All metrics for a company in a fiscal year (using database_name)

```sql
SELECT 
    metric,
    value,
    currency
FROM financial_metrics
WHERE ticker = 'BHP AU Equity'
  AND period = 'FY 2023'
  AND period_type = 'FISCAL'
ORDER BY metric;
```

### Query 2: Highest revenue companies (using database_name REVENUE)

```sql
SELECT 
    ticker,
    value,
    currency
FROM financial_metrics
WHERE metric = 'REVENUE'
  AND period = 'FY 2023'
  AND period_type = 'FISCAL'
ORDER BY CAST(value AS DECIMAL) DESC
LIMIT 10;
```

### Query 3: Get daily stock returns for a company (using database_name COMPANY_TSR)

```sql
SELECT 
    ticker,
    period,
    value,
    currency
FROM financial_metrics
WHERE metric = 'COMPANY_TSR'
  AND ticker = 'BHP AU Equity'
  AND period_type = 'MONTHLY'
ORDER BY period DESC
LIMIT 20;
```

### Query 4: Compare metrics across companies for a year

```sql
SELECT 
    ticker,
    metric,
    value,
    currency
FROM financial_metrics
WHERE period = 'FY 2023'
  AND period_type = 'FISCAL'
  AND metric IN ('REVENUE', 'PROFIT_AFTER_TAX', 'TOTAL_ASSETS')
ORDER BY ticker, metric;
```

### Query 5: Cash balance time series for a company

```sql
SELECT 
    period,
    value,
    currency
FROM financial_metrics
WHERE ticker = 'BHP AU Equity'
  AND metric = 'CASH'
  AND period_type = 'FISCAL'
ORDER BY period;
```

### Query 6: Compare fiscal metrics between two years

```sql
SELECT 
    f1.ticker,
    f1.value as fy2022,
    f2.value as fy2023,
    (CAST(f2.value AS DECIMAL) - CAST(f1.value AS DECIMAL)) as change,
    ROUND(((CAST(f2.value AS DECIMAL) - CAST(f1.value AS DECIMAL)) / 
           CAST(f1.value AS DECIMAL) * 100)::NUMERIC, 2) as pct_change
FROM financial_metrics f1
JOIN financial_metrics f2 
    ON f1.ticker = f2.ticker
    AND f1.metric = f2.metric
WHERE f1.metric = 'REVENUE'
  AND f1.period = 'FY 2022'
  AND f2.period = 'FY 2023'
  AND f1.period_type = 'FISCAL'
  AND f2.period_type = 'FISCAL'
ORDER BY pct_change DESC;
```

### Query 7: Count records by period type

```sql
SELECT 
    period_type,
    COUNT(*) as record_count,
    COUNT(DISTINCT ticker) as unique_tickers,
    COUNT(DISTINCT metric) as unique_metrics
FROM financial_metrics
GROUP BY period_type
ORDER BY period_type;
```

---

## Data Transformation & Format Details

### Date Format

**Fiscal Periods:** Format "FY YYYY" (e.g., "FY 2002")
- Represents annual fiscal year data
- 22 unique values (FY 2002 through FY 2023)

**Monthly Periods:** ISO 8601 format (YYYY-MM-DD)
- Converted from Excel date serials during denormalization
- Represents calendar month endpoints
- Example: "1981-11-30", "1981-12-31", "1982-01-29"
- NOT individual daily trading dates

### Converting Value to Numeric

```sql
SELECT 
    ticker,
    period,
    metric,
    CAST(value AS DECIMAL) as numeric_value,
    currency
FROM financial_metrics
WHERE value ~ '^\d+\.?\d*$'  -- Matches numeric strings
ORDER BY numeric_value DESC;
```

### Excel Serial Date Conversion

If you need to work with the original Excel serial dates:

```sql
-- Convert ISO date back to Excel serial
SELECT 
    period,
    (DATE '1899-12-30' + (period::DATE - '1899-12-30'::DATE))::TEXT as excel_serial
FROM financial_metrics
WHERE period_type = 'MONTHLY'
LIMIT 5;
```

---

## File Statistics

| Metric | Count |
|--------|-------|
| Total Records | 275,343 |
| Fiscal Records | 140,670 |
| Monthly Records | 134,673 |
| Unique Tickers | 568 |
| Unique Metrics | 20 |
| Unique Periods | 563 (22 fiscal + 541 monthly) |
| Unique Currencies | 2 |
| File Size | 15.45 MB |

---

## Creation Process

### Source Files Processed
- **3 Dimension tables:** Base.csv, FY Dates.csv, FY Period.csv
- **20 Metric CSV files:** 
  - 14 annual financial metrics (500 companies × 22 fiscal years)
  - 3 TSR/Share metrics (500 companies × 22 fiscal years)
  - 3 monthly metrics (568 entities × 541 months)

### Denormalization Logic

Each metric CSV file was transformed from wide format (one row per entity, columns per period) to long format (one row per entity-period-metric combination).

**Pipeline:**
1. Extract worksheets from Excel → Individual CSV files in extracted-worksheets/
2. Load metric_units.json configuration
3. For each metric file:
   - Use worksheet_name from config to find actual CSV file
   - Read WIDE format data (Ticker, Period1, Period2, ...)
   - Transform to LONG format (Ticker, Period, Metric, Value)
   - Convert Excel date serials to ISO dates (for monthly metrics)
   - Map metric_name to database_name for canonical storage
4. Consolidate all records into single fact table
5. Output: financial_metrics_fact_table.csv

**Example Transformation:**
```
# Wide format (original CSV file):
Ticker,Data FX,FY 2002,FY 2003,FY 2004
BHP AU Equity,AUD,30390.04,26823.87,32179.01

# Long format (fact table):
Ticker,Period,Period_Type,Metric,Value,Currency
BHP AU Equity,FY 2002,FISCAL,REVENUE,30390.04,AUD
BHP AU Equity,FY 2003,FISCAL,REVENUE,26823.87,AUD
BHP AU Equity,FY 2004,FISCAL,REVENUE,32179.01,AUD
```

---

## Ingestion & Validation

### Pipeline Stages

**Stage 1A: Extract**
- Read from `raw-data/Bloomberg Download data.xlsx`
- Output: 23 CSV files in `extracted-worksheets/`

**Stage 1B: Denormalize**
- Read all 20 metric CSV files using metric_units.json mapping
- Use worksheet_name for reliable file discovery
- Transform WIDE → LONG format
- Output: `consolidated-data/financial_metrics_fact_table.csv` (275,343 records)

**Stage 1C: Ingest**
- Load CSV into raw_data table
- Validate metrics against metric_units table
- Track reconciliation statistics
- Store metadata in dataset_versions table

### Validation Queries

```sql
-- Verify all metrics have defined units
SELECT COUNT(DISTINCT metric) as metrics_in_data
FROM raw_data;  -- Should be 20

SELECT COUNT(*) FROM metric_units;  -- Should be 20

-- Check for metrics without units
SELECT DISTINCT rd.metric_name
FROM raw_data rd
LEFT JOIN metric_units mu ON rd.metric_name = mu.metric_name
WHERE mu.metric_name IS NULL;  -- Should return 0 rows

-- Verify period types
SELECT DISTINCT period_type, COUNT(*) as record_count
FROM raw_data
GROUP BY period_type;
-- Should show: FISCAL: 140,670, MONTHLY: 134,673
```

---

## Related Files

- **financial_metrics_fact_table.csv** - The consolidated denormalized fact table
- **Base.csv** - Company master data (dimension table)
- **FY Dates.csv** - Fiscal year end dates (dimension table)
- **FY Period.csv** - Fiscal period labels (dimension table)
- **Individual metric CSV files** - Original source files in extracted-worksheets/
- **metric_units.json** - Metric configuration (metric_name ↔ database_name ↔ worksheet_name ↔ unit)

---

## Notes

- Fact table is ready for immediate loading into PostgreSQL
- All original data preserved; no records lost in denormalization
- Empty cells and #N/A values excluded for cleaner table
- Monthly dates in ISO format (YYYY-MM-DD) for PostgreSQL compatibility
- All metrics stored with canonical database_name values (uppercase)
- Metric names should be queried using database_name values (REVENUE, not "Revenue")
- Currency field may be empty for index/series records
- Multiple entities may have same metric for same period (normal)

---

*Denormalized fact table created from 20 Bloomberg financial metrics files*  
*Metric configuration managed via metric_units.json*  
*For questions, see README.md and QUICK_REFERENCE.txt*
