# Bloomberg Financial Data - Cleaned CSV Extract

**Source:** `raw-data/Bloomberg Download data.xlsx`  
**Extracted:** 2026-03-03  
**Status:** ✅ Cleaned and verified

## Summary

23 cleaned CSV files extracted from Bloomberg financial data Excel workbook.

- **Total Data Rows:** 10,744
- **Total Files:** 23
- **Total Size:** 9.5 MB
- **All headers cleaned** ✓

## File Structure

All CSV files follow a consistent structure:
```
Header Row: Num, Ticker, Name, [company-specific or date columns]...
Data Rows: Company data with metrics or values
```

### 1. Dimension Tables (3 files)

Companies master data and fiscal year information:

- **Base.csv** (500 companies × 12 attributes)
  - Num, Ticker, Name, FY Report Month, Data FX, Begin Year, Sector, BICS Name, BICS 1, BICS 2, BICS 3, BICS 4

- **FY Dates.csv** (500 companies × 33 fiscal years)
  - Fiscal year end dates (Excel date serial numbers)
  - Covers FY 2002 - FY 2027

- **FY Period.csv** (500 companies × 33 fiscal years)
  - Fiscal period labels (e.g., "FY1 2002")

### 2. Financial Metrics - Standard Format (14 files)

Each file contains 500 companies × 26 years (FY 2002-2027):

| File | Description |
|------|-------------|
| Revenue.csv | Annual revenue |
| Op Income.csv | Operating income |
| PBT.csv | Profit before tax |
| PAT.csv | Profit after tax |
| PAT XO.csv | Profit after tax (excluding items) |
| Cash.csv | Cash balances |
| FA.csv | Fixed assets |
| GW.csv | Goodwill |
| MC.csv | Market capitalization (26 cols) |
| MI.csv | Minority interest |
| Div.csv | Dividends |
| Franking.csv | Franking credits |
| FY TSR.csv | Fiscal year total shareholder return |
| Spot Shares.csv | Shares outstanding |
| Share Price.csv | Share price |

### 3. Financial Metrics - Extended Format (2 files)

Extended data with more years/periods:

- **Total Assets.csv** (500 companies × 53 columns)
- **Total Equity.csv** (500 companies × 53 columns)

### 4. Daily Performance Metrics (3 files)

High-frequency daily data with 510 date columns:

- **Company TSR.csv** (500 companies × 510 trading days)
  - Daily total shareholder return percentages
  - Note: Contains #N/A for companies with incomplete history

- **Index TSR.csv** (122 indices × 510 trading days)
  - Daily index returns

- **Rf.csv** (122 risk-free rate series × 510 trading days)
  - Daily risk-free rates

## Data Quality

✅ **Cleaned:**
- Removed 30,935 unnecessary header/note rows
- Removed Excel column reference header rows
- Removed blank and error rows
- Preserved all actual data

⚠️ **Known Issues:**
- #N/A values exist in Company TSR.csv (expected for newer companies without full history)
- Empty trailing columns in some files (especially FY Dates/Period)
- Numeric date serial numbers in FY Dates (use FY Period for labels)

## Usage Examples

### Load to PostgreSQL

```sql
-- Load companies master
\COPY companies(num, ticker, name, fy_report_month, data_fx, begin_year, sector, bics_name, bics_1, bics_2, bics_3, bics_4) 
FROM 'Base.csv' WITH (FORMAT CSV, HEADER);

-- Load fiscal dates
\COPY fiscal_years(num, ticker, name, data_fx, fy_2002, fy_2003, ...) 
FROM 'FY Dates.csv' WITH (FORMAT CSV, HEADER);

-- Load metrics
\COPY financial_metrics(num, ticker, name, data_fx, fy_2002, fy_2003, ...) 
FROM 'Revenue.csv' WITH (FORMAT CSV, HEADER);
```

### Date Format

Daily trading dates in the consolidated fact table are stored in **ISO 8601 format (YYYY-MM-DD)**, converted from the original Excel date serials for PostgreSQL compatibility. Fiscal period labels remain in format "FY YYYY" (e.g., "FY 2002").

## Files Summary

| Category | Files | Total Rows | Purpose |
|----------|-------|-----------|---------|
| Dimension | 3 | 1,500 | Company master data |
| Standard Metrics | 14 | 7,000 | Annual financial data |
| Extended Metrics | 2 | 1,000 | Additional annual data |
| Daily Metrics | 3 | 744 | High-frequency performance data |
| **TOTAL** | **23** | **10,744** | - |

## Next Steps

1. **Load to PostgreSQL** - Use COPY command for bulk loading
2. **Normalize Data** - Consider pivoting annual metrics to normalized format
3. **Handle #N/A** - Map to NULL in database (already excluded from consolidated fact table)

---

*For details on cleaning process, see CLEANING_SUMMARY.txt*
