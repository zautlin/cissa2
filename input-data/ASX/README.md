# Bloomberg Financial Data - ASX Data Pipeline

**Source:** `raw-data/Bloomberg Download data.xlsx`  
**Extracted:** 2026-03-03  
**Status:** ✅ Cleaned, denormalized, and ingested into PostgreSQL

## Summary

Bloomberg financial data extracted from Excel workbook, transformed through a denormalization pipeline, and consolidated into a unified fact table for PostgreSQL ingestion.

- **Total Records:** 275,343 (140,670 fiscal + 134,673 monthly)
- **Metrics:** 20 unique financial metrics
- **File Size:** 15.45 MB (consolidated fact table)
- **Data Quality:** ✅ Verified against metric_units reference table

## Pipeline Architecture

### Stage 1: Extract (01_extract_excel_to_csv.py)
Extracts 23 worksheets from Bloomberg Excel workbook into individual CSV files:

**Dimension Tables (3 files):**
- `Base.csv` - 500 companies with attributes (Num, Ticker, Name, Sector, BICS codes, etc.)
- `FY Dates.csv` - Fiscal year end dates (Excel serials)
- `FY Period.csv` - Fiscal period labels (e.g., "FY1 2002")

**Metric CSV Files (20 files):**
- 17 Annual financial metrics (fiscal year data)
- 3 Monthly performance metrics (calendar months from Excel date serials)

### Stage 2: Denormalize (02_denormalize_metrics.py)
Transforms all 20 metric CSV files from WIDE format (one row per entity, columns per period) to LONG format (one row per entity-period-metric combination).

**Key Features:**
- Uses `metric_units.json` configuration for accurate file mapping
- Maps `worksheet_name` (actual CSV filename) → `database_name` (canonical DB value)
- Converts Excel date serials to ISO 8601 format (YYYY-MM-DD) for monthly metrics
- Produces single consolidated fact table

**Output:**
- `consolidated-data/financial_metrics_fact_table.csv` - 275,343 records ready for PostgreSQL

### Stage 3: Ingest (ingestion.py)
Loads fact table into PostgreSQL with full reconciliation tracking:
- Creates `raw_data` table with full numeric validation
- Validates all metrics against `metric_units` reference table
- Tracks reconciliation statistics (processed, rejected, duplicates)
- Stores metadata in `dataset_versions` table

---

## Metric Configuration (metric_units.json)

All 20 metrics are configured in `/home/ubuntu/cissa/backend/database/config/metric_units.json`. This configuration maps:

| Field | Purpose | Example |
|-------|---------|---------|
| `metric_name` | Human-readable display name (used in config/docs) | "Operating Income" |
| `worksheet_name` | Actual CSV filename in extracted-worksheets/ | "Op Income.csv" |
| `database_name` | Canonical uppercase value stored in database | "OPERATING_INCOME" |
| `unit` | Measurement unit for the metric | "millions", "%", "number of shares" |

### Why Three Names?

- **metric_name**: Used for human-readable documentation and configuration
- **worksheet_name**: Source of truth for actual filenames (handles abbreviations like "Op Income.csv", "PBT.csv", "Div.csv")
- **database_name**: Canonical normalized form stored in database (enforces consistency)

This separation allows:
1. ✅ Reliable file discovery (worksheet_name is explicit, not derived)
2. ✅ Normalized database values (database_name in uppercase)
3. ✅ Human-friendly documentation (metric_name for readability)

---

## Complete Metric List (20 Total)

### Annual Financial Metrics (14 - Period_Type = FISCAL)

| metric_name | worksheet_name | database_name | unit |
|---|---|---|---|
| Revenue | Revenue.csv | REVENUE | millions |
| Operating Income | Op Income.csv | OPERATING_INCOME | millions |
| Profit Before Tax | PBT.csv | PROFIT_BEFORE_TAX | millions |
| Profit After Tax | PAT.csv | PROFIT_AFTER_TAX | millions |
| Profit After Tax (Exc) | PAT XO.csv | PROFIT_AFTER_TAX_EX | millions |
| Cash | Cash.csv | CASH | millions |
| Fixed Assets | FA.csv | FIXED_ASSETS | millions |
| Goodwill | GW.csv | GOODWILL | millions |
| Market Cap | MC.csv | MARKET_CAP | millions |
| Minority Interest | MI.csv | MINORITY_INTEREST | millions |
| Dividends | Div.csv | DIVIDENDS | millions |
| Franking | Franking.csv | FRANKING | millions |
| Total Assets | Total Assets.csv | TOTAL_ASSETS | millions |
| Total Equity | Total Equity.csv | TOTAL_EQUITY | millions |

### TSR Metrics (3 - Period_Type = FISCAL)

| metric_name | worksheet_name | database_name | unit |
|---|---|---|---|
| FY TSR | FY TSR.csv | FY_TSR | % |
| Spot Shares | Spot Shares.csv | SPOT_SHARES | number of shares |
| Share Price | Share Price.csv | SHARE_PRICE | millions |

### Monthly Performance Metrics (3 - Period_Type = MONTHLY)

| metric_name | worksheet_name | database_name | unit |
|---|---|---|---|
| Company TSR (Monthly) | Company TSR.csv | COMPANY_TSR | % |
| Index TSR (Monthly) | Index TSR.csv | INDEX_TSR | % |
| Risk-Free Rate (Monthly) | Rf.csv | RISK_FREE_RATE | % |

---

## Data Dimensions

### Tickers
- **Total:** 568 unique tickers
- **Companies:** 500 active companies
- **Indices/Series:** 68 (indices and risk-free rate series)

### Periods

#### Fiscal Periods
- **22 unique fiscal years:** FY 2002 through FY 2023
- **Format:** "FY YYYY" (e.g., "FY 2002")
- **Coverage:** Most companies have data for 20-22 years

#### Monthly Periods
- **541 unique periods** (calendar months from Excel date serials)
- **Format:** ISO 8601 (YYYY-MM-DD)
- **Range:** Multiple years of monthly data
- **Conversion:** Excel date serials → ISO dates during denormalization

### Currencies
2 unique currency codes:
- **AUD** (Australian Dollar) - primary for ASX companies
- Other currencies for international indices/series

---

## File Structure

### Consolidated Fact Table

**File:** `consolidated-data/financial_metrics_fact_table.csv`

```
Ticker,Period,Period_Type,Metric,Value,Currency
BHP AU Equity,FY 2002,FISCAL,REVENUE,30390.0379,AUD
BHP AU Equity,FY 2003,FISCAL,REVENUE,26823.8732,AUD
BHP AU Equity,1981-11-30,MONTHLY,COMPANY_TSR,9.054,AUD
BHP AU Equity,1981-12-31,MONTHLY,COMPANY_TSR,-2.814,AUD
```

### Directory Structure

```
input-data/ASX/
├── raw-data/
│   └── Bloomberg Download data.xlsx    # Original source file
├── extracted-worksheets/
│   ├── Base.csv                        # Company master data
│   ├── FY Dates.csv                    # Fiscal year dates
│   ├── FY Period.csv                   # Fiscal year labels
│   ├── Revenue.csv                     # Financial metrics (20 total)
│   ├── Op Income.csv
│   ├── PBT.csv
│   ├── ... (17 more metric files)
│   └── Rf.csv
├── consolidated-data/
│   └── financial_metrics_fact_table.csv # Denormalized output (275,343 records)
├── 01_extract_excel_to_csv.py          # Extraction script
├── 02_denormalize_metrics.py           # Denormalization script
├── README.md                           # This file
├── FACT_TABLE_DOCUMENTATION.md         # Complete technical reference
├── QUICK_REFERENCE.txt                 # Quick lookup guide
└── DENORMALIZATION_COMPLETE.txt        # Transformation summary
```

---

## Data Quality

### ✅ Validated
- All 20 metrics have corresponding entries in `metric_units` reference table
- All metrics stored with canonical `database_name` values in database
- Monthly dates converted from Excel serials to ISO 8601 format
- Numeric values validated during ingestion
- Reconciliation: total_rows_processed = unique_rows_in_db + rejected + duplicates

### ⚠️ Known Characteristics
- #N/A values excluded from monthly metrics
- Empty cells excluded from fact table
- Some companies/indices have incomplete year coverage
- Currency may vary by company/index
- Duplicate (ticker, metric, period) combinations handled via UPSERT on ingestion

---

## Record Distribution

| Period Type | Records | Details |
|-------------|---------|---------|
| **FISCAL** | 140,670 | 568 entities × 14 fiscal metrics × 22 years |
| **MONTHLY** | 134,673 | 568 entities × 3 monthly metrics × 541 months |
| **TOTAL** | **275,343** | - |

---

## PostgreSQL Integration

### Load into Database

```sql
-- Data is loaded via the pipeline ingestion process
-- Which validates and stores in raw_data table
-- Then normalized into fact tables via denormalization stage

-- To verify data in raw_data:
SELECT COUNT(*) FROM raw_data;  -- Should be 275,343
SELECT DISTINCT metric_name FROM raw_data ORDER BY metric_name;
```

### Query Examples

```sql
-- All metrics for a company in a fiscal year (using database_name)
SELECT metric_name, numeric_value, currency
FROM raw_data
WHERE ticker = 'BHP AU Equity'
  AND period = 'FY 2023'
  AND period_type = 'FISCAL'
ORDER BY metric_name;

-- Highest revenue companies (using database_name REVENUE)
SELECT ticker, numeric_value, currency
FROM raw_data
WHERE metric_name = 'REVENUE'
  AND period = 'FY 2023'
ORDER BY numeric_value DESC
LIMIT 10;

-- Monthly performance data
SELECT ticker, period, numeric_value
FROM raw_data
WHERE metric_name = 'COMPANY_TSR'
  AND ticker = 'BHP AU Equity'
  AND period_type = 'MONTHLY'
ORDER BY period;
```

---

## Script Usage

### Extract Data from Excel

```bash
cd /home/ubuntu/cissa/input-data/ASX
python3 01_extract_excel_to_csv.py ./raw-data/Bloomberg\ Download\ data.xlsx ./extracted-worksheets
```

### Denormalize Metrics

```bash
cd /home/ubuntu/cissa/input-data/ASX
python3 02_denormalize_metrics.py ./extracted-worksheets ./consolidated-data/financial_metrics_fact_table.csv
```

### Verify Denormalization

```bash
# Check output
head -5 consolidated-data/financial_metrics_fact_table.csv
wc -l consolidated-data/financial_metrics_fact_table.csv  # Should be 275,344 (including header)
```

---

## Metric Units Reference Table (PostgreSQL)

The `metric_units` table provides the authoritative mapping:

```sql
CREATE TABLE metric_units (
    metric_units_id SERIAL PRIMARY KEY,
    metric_name VARCHAR(255) NOT NULL UNIQUE,
    unit VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Data:**
- Populated via `schema_manager.py init_metric_units()`
- Reads from `backend/database/config/metric_units.json`
- Stores `database_name` as the `metric_name` column value (canonical form)
- One entry per metric (20 total)

---

## Related Documentation

- **FACT_TABLE_DOCUMENTATION.md** - Complete technical reference with examples
- **QUICK_REFERENCE.txt** - Quick lookup guide and common queries
- **DENORMALIZATION_COMPLETE.txt** - Transformation details

---

*Bloomberg financial data pipeline for ASX analysis*  
*Last updated: 2026-03-05*
