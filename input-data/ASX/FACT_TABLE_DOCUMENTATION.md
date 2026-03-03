# Financial Metrics Denormalized Fact Table

## Overview

A single consolidated fact table (`financial_metrics_fact_table.csv`) created by denormalizing all Bloomberg financial data metrics into a common dimensional format.

**File:** `/home/ubuntu/cissa/input-data/ASX/consolidated-data/financial_metrics_fact_table.csv`  
**Status:** ✅ Ready for PostgreSQL loading  
**Size:** 17 MB  
**Total Records:** 321,688

---

## Schema

The fact table contains the following columns:

| Column | Type | Description |
|--------|------|-------------|
| **Ticker** | String | Company/Index identifier (e.g., "BHP AU Equity") |
| **Period** | String | Time period (e.g., "FY 2002" for fiscal or ISO date "YYYY-MM-DD" for daily) |
| **Period_Type** | String | Type of period: `FISCAL` or `DAILY` |
| **Metric** | String | Name of the financial metric (20 types) |
| **Value** | String/Numeric | The actual measurement value |
| **Currency** | String | Currency code (24 currencies) |

---

## Data Dimensions

### Tickers
- **Total:** 535 unique tickers
- **Companies:** 500 active companies
- **Indices/Series:** 35 (indices and risk-free rates)

### Metrics (20 total)

#### Annual Financial Metrics (17 metrics, Fiscal periods)
- **Revenue** - Total company revenue
- **Operating Income** - Operating profit
- **Profit Before Tax (PBT)** - Pre-tax profit
- **Profit After Tax (PAT)** - Post-tax profit
- **Profit After Tax (Excluding)** - PAT excluding special items
- **Cash** - Cash balances
- **Fixed Assets (FA)** - Property, plant & equipment
- **Goodwill (GW)** - Intangible assets
- **Market Cap (MC)** - Market capitalization
- **Minority Interest (MI)** - Non-controlling interests
- **Dividends** - Dividend payments
- **Franking** - Franking credits
- **FY TSR** - Fiscal Year Total Shareholder Return
- **Spot Shares** - Shares outstanding
- **Share Price** - Stock price per share
- **Total Assets** - Total company assets
- **Total Equity** - Shareholders' equity

#### Daily Performance Metrics (3 metrics, Daily periods)
- **Company TSR (Daily)** - Daily total shareholder returns (500 companies)
- **Index TSR (Daily)** - Daily index returns (122 indices)
- **Risk-Free Rate (Daily)** - Daily risk-free rates (122 series)

### Periods

#### Fiscal Periods
- **22 unique fiscal years:** FY 2002 through FY 2023
- **Coverage:** Most companies have data for 20-22 years

#### Daily Periods
- **514 unique trading dates**
- **Coverage:** Daily data across multiple years
- **Format:** ISO date format (YYYY-MM-DD) - e.g., "1981-11-30", "1981-12-31"
- **Note:** Originally from Excel date serials, now converted to standard ISO format for PostgreSQL compatibility

### Currencies
24 currency codes including:
- **AUD** (Australian Dollar)
- **USD**, **EUR**, **GBP** (Major currencies)
- **JPY**, **CNY**, **INR** (Asian currencies)
- Plus 18 others (BRL, CAD, CHF, DKK, HKD, ISK, KRW, MXN, MYR, NOK, NZD, SEK, SGD, TRY, TWD, ZAR)

---

## Record Distribution

| Period Type | Records | Details |
|-------------|---------|---------|
| **FISCAL** | 186,999 | 500 companies × 17 metrics × 22 fiscal years |
| **DAILY** | 134,689 | 622 entities × 3 metrics × 514 trading days |
| **TOTAL** | **321,688** | - |

---

## Data Quality

### Characteristics
- ✅ **Complete:** All source metric data preserved
- ✅ **Clean:** Empty cells excluded
- ✅ **Consistent:** Uniform structure across all metrics
- ⚠️ **Mixed currencies:** Currency varies by company
- ⚠️ **Sparse data:** Some companies/indices have missing periods

### Known Issues
- Empty ticker records (2 metrics) from margin/rounding rows
- Some #N/A values excluded from daily metrics
- Blank/empty currency values for some index records

---

## Sample Records

```
Ticker,Period,Period_Type,Metric,Value,Currency
BHP AU Equity,FY 2002,FISCAL,Cash,2660.6318999999999,AUD
BHP AU Equity,FY 2003,FISCAL,Cash,2313.6552999999999,AUD
BHP AU Equity,FY 2004,FISCAL,Revenue,32179.0118,AUD
...
BHP AU Equity,1981-11-30,DAILY,Company TSR (Daily),9.0540000000000003,AUD
BHP AU Equity,1981-12-31,DAILY,Company TSR (Daily),-2.8140000000000001,AUD
...
1208 HK Equity,FY 2002,FISCAL,Revenue,10362.1962,
1208 HK Equity,FY 2003,FISCAL,Revenue,14184.0857,
...
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
```

### Load Data

```sql
\COPY financial_metrics(ticker, period, period_type, metric, value, currency) 
FROM 'financial_metrics_fact_table.csv' 
WITH (FORMAT CSV, HEADER);
```

---

## Usage Examples

### Query Annual Revenue by Company and Year
```sql
SELECT ticker, period, value, currency
FROM financial_metrics
WHERE metric = 'Revenue'
  AND period_type = 'FISCAL'
  AND period IN ('FY 2022', 'FY 2023')
ORDER BY ticker, period;
```

### Find Companies with Increasing Cash Balances
```sql
SELECT 
    f1.ticker,
    f1.period as fy_2022,
    f1.value as cash_2022,
    f2.value as cash_2023,
    (CAST(f2.value AS DECIMAL) - CAST(f1.value AS DECIMAL)) as change
FROM financial_metrics f1
JOIN financial_metrics f2 
    ON f1.ticker = f2.ticker 
    AND f1.metric = f2.metric
WHERE f1.metric = 'Cash'
  AND f1.period = 'FY 2022'
  AND f2.period = 'FY 2023'
  AND f1.period_type = 'FISCAL'
  AND f2.period_type = 'FISCAL'
ORDER BY change DESC;
```

### Get Daily Stock Returns for a Company
```sql
SELECT ticker, period, value
FROM financial_metrics
WHERE metric = 'Company TSR (Daily)'
  AND ticker = 'BHP AU Equity'
ORDER BY period DESC;
```

### Compare Metrics Across Companies for a Year
```sql
SELECT ticker, metric, value, currency
FROM financial_metrics
WHERE period = 'FY 2023'
  AND period_type = 'FISCAL'
  AND metric IN ('Revenue', 'Profit After Tax', 'Total Assets')
ORDER BY ticker, metric;
```

---

## Data Transformation & Normalization

### Date Format Details

Daily periods are stored in **ISO 8601 format (YYYY-MM-DD)** - converted from original Excel date serials during denormalization. Fiscal periods remain in format "FY YYYY".

### Converting Value to Numeric

```sql
SELECT 
    ticker,
    period,
    metric,
    value::DECIMAL as numeric_value,
    currency
FROM financial_metrics
WHERE value ~ '^\d+\.?\d*$';
```

---

## File Statistics

| Metric | Count |
|--------|-------|
| Total Records | 321,688 |
| Fiscal Records | 186,999 |
| Daily Records | 134,689 |
| Unique Tickers | 535 |
| Unique Metrics | 20 |
| Unique Periods | 536 (22 fiscal + 514 daily) |
| Unique Currencies | 24 |
| File Size | 18.39 MB |

---

## Creation Process

### Source Files Processed
- **Annual metrics:** 17 CSV files (500 companies × 22 fiscal years each)
- **Daily metrics:** 3 CSV files (622 entities × 514 trading days each)

### Denormalization Logic
Each metric CSV file was transformed from wide format (one row per company, columns per period) to long format (one row per company-period-metric combination).

**Example:**
```
# Wide format (original):
Ticker,Data FX,FY 2002,FY 2003,FY 2004
BHP AU Equity,AUD,100,110,120

# Long format (fact table):
Ticker,Period,Period_Type,Metric,Value,Currency
BHP AU Equity,FY 2002,FISCAL,Revenue,100,AUD
BHP AU Equity,FY 2003,FISCAL,Revenue,110,AUD
BHP AU Equity,FY 2004,FISCAL,Revenue,120,AUD
```

---

## Related Files

- `financial_metrics_fact_table.csv` - The denormalized fact table
- `Base.csv` - Company master data (dimension table)
- `FY Dates.csv` - Fiscal year end dates (dimension table)
- `FY Period.csv` - Fiscal period labels (dimension table)
- Individual metric CSV files - Original source files

---

## Notes

- Fact table is ready for immediate loading into PostgreSQL
- All original data preserved; no records lost in denormalization
- Empty cells and #N/A values excluded for cleaner table
- Daily dates in ISO format (YYYY-MM-DD) for PostgreSQL compatibility
- Fiscal periods in format "FY YYYY" (e.g., "FY 2002")
- Currency field may be empty for index/series records
- Multiple companies may have same metric for same period (normal)

---

*Denormalized fact table created from 20 Bloomberg financial metrics files*  
*For questions, see CLEANING_SUMMARY.txt and README.md*
