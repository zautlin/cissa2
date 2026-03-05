# CISSA Database Schema Reference

Complete reference guide to the CISSA database schema. For the full SQL definitions, see `/backend/database/schema/schema.sql`.

## Schema Overview

The CISSA database consists of **10 tables** organized into 5 logical phases:

| Phase | Purpose | Tables | Key Focus |
|-------|---------|--------|-----------|
| 1: Raw Data | Source data storage | `raw_data`, `dataset_versions` | Unique constraint on (ticker, metric, period) |
| 2: Companies | Company reference | `companies`, `metric_units` | ASX200 parent index assignment |
| 3: Cleaned Data | Processed facts | `fundamentals`, `imputation_audit_trail` | Metadata JSONB for imputation tracking |
| 4: Downstream | Analysis outputs | `metrics_outputs`, `optimization_outputs` | Versioned parameter sets |
| 5: Configuration | Tunable parameters | `parameters`, `parameter_sets` | Parameter overrides per analysis run |

---

## Phase 1: Raw Data Ingestion

### dataset_versions
**Purpose:** Track each data ingestion run with metadata and versioning

**Key Columns:**
- `dataset_id` (UUID, PK): Unique identifier for this ingestion
- `dataset_name` (TEXT): Name of the dataset (e.g., "ASX Financial Metrics")
- `version_number` (INT): Sequential version counter
- `status` (TEXT): 'processing' | 'completed' | 'failed'
- `metadata` (JSONB): Ingestion reconciliation details
- `processed_at` (TIMESTAMPTZ): When ingestion completed
- `created_at`, `updated_at` (TIMESTAMPTZ): Timestamps

**Metadata Structure:**
```json
{
  "total_csv_rows": 275343,
  "total_rows_processed": 275343,
  "rows_with_unparseable_values": 485,
  "duplicate_combinations_found": 1000,
  "unique_rows_in_raw_data": 273858,
  "file_name": "financial_metrics_fact_table.xlsx",
  "encoding": "utf-8"
}
```

**Indexes:**
- `dataset_versions_pkey`: Primary key on dataset_id
- `idx_dataset_versions_name`: On dataset_name
- `idx_dataset_versions_status`: On status

**Relationships:**
- `raw_data` → references `dataset_versions(dataset_id)` ON DELETE CASCADE
- `imputation_audit_trail` → references `dataset_versions(dataset_id)` ON DELETE CASCADE

---

### raw_data
**Purpose:** Store all ingested rows from the source file, with deduplication

**Key Columns:**
- `raw_data_id` (BIGINT, PK): Identity primary key
- `dataset_id` (UUID, FK): References dataset_versions
- `ticker` (TEXT, NOT NULL): Stock ticker symbol (e.g., "BHP", "CBA")
- `metric_name` (TEXT, NOT NULL): Metric identifier (e.g., "Revenue", "Company TSR (Monthly)")
- `period` (DATE, NOT NULL): Period for this data point
- `value` (NUMERIC, NOT NULL): The numeric value
- `created_at` (TIMESTAMPTZ): When inserted

**Unique Constraint:**
- `UNIQUE (dataset_id, ticker, metric_name, period)`: Only first occurrence of duplicate (ticker, metric, period) is kept

**Indexes:**
- `raw_data_pkey`: Primary key on raw_data_id
- `idx_raw_data_dataset_id`: On dataset_id
- `idx_raw_data_ticker_metric`: On (ticker, metric_name)
- `idx_raw_data_period`: On period

**Row Count Example:**
- 273,858 rows from 275,343 CSV rows (485 rejected, ~1,000 duplicates removed)

---

## Phase 2: Company Reference Data

### companies
**Purpose:** Master list of all companies in the dataset

**Key Columns:**
- `ticker` (TEXT, PK): Stock ticker symbol
- `company_name` (TEXT, NOT NULL): Full company name
- `parent_index` (TEXT): NULL | "ASX200" (top 200 companies)
- `sector` (TEXT): Industry sector (e.g., "Financials", "Industrials", "Energy")
- `created_at`, `updated_at` (TIMESTAMPTZ)

**Indexes:**
- `companies_pkey`: Primary key on ticker
- `idx_companies_sector`: On sector
- `idx_companies_parent_index`: On parent_index

**Record Count:**
- ~500 companies total (200 in ASX200, ~300 other ASX companies)

---

### metric_units
**Purpose:** Define the unit of measurement for each metric

**Key Columns:**
- `metric_id` (BIGINT, PK): Identity primary key
- `metric_name` (TEXT, NOT NULL, UNIQUE): Metric identifier
- `unit` (TEXT, NOT NULL): Unit of measurement
- `created_at` (TIMESTAMPTZ)

**Unit Breakdown:**
- 14 financial metrics → "millions" (Revenue, Cash, Total Assets, etc.)
- 3 TSR metrics → "%" (FY TSR, Company TSR Monthly, Index TSR Monthly)
- 1 Risk-Free Rate → "%"
- 1 Spot Shares → "number of shares"
- 1 Share Price → "millions"

**Total:** 20 unique metrics

**Indexes:**
- `metric_units_pkey`: Primary key on metric_id
- `idx_metric_units_name`: On metric_name

---

## Phase 3: Cleaned Data

### fundamentals
**Purpose:** Final cleaned, FY-aligned, imputed fact table - Single source of truth for all downstream analysis

**Key Columns:**
- `fundamental_id` (BIGINT, PK): Identity primary key
- `dataset_id` (UUID, FK): References dataset_versions
- `ticker` (TEXT, NOT NULL, FK): References companies
- `metric_name` (TEXT, NOT NULL): Metric identifier
- `fiscal_year` (INT, NOT NULL): Fiscal year (1981-2024)
- `fiscal_month` (INT): 1-12 for MONTHLY records, NULL for FISCAL records
- `fiscal_day` (INT): 1-31 for MONTHLY records, NULL for FISCAL records
- `period_type` (TEXT): 'FISCAL' | 'MONTHLY' (determines whether month/day are populated)
- `value` (NUMERIC, NOT NULL): The final value (never NULL after imputation)
- `metadata` (JSONB): Imputation tracking details
- `created_at` (TIMESTAMPTZ)

**Metadata Structure (per row):**
```json
{
  "imputation_step": "FORWARD_FILL",
  "confidence_level": 0.95,
  "source": "raw_data or imputed"
}
```

**Indexes:**
- `fundamentals_pkey`: Primary key on fundamental_id
- `idx_fundamentals_dataset`: On dataset_id
- `idx_fundamentals_ticker_metric`: On (ticker, metric_name)
- `idx_fundamentals_period_type`: On period_type
- `idx_fundamentals_fiscal_year`: On fiscal_year

**Row Count Example:**
- ~273,858 total rows (after imputation fills gaps)
- ~140,670 FISCAL rows
- ~133,188 MONTHLY rows

**Key Characteristics:**
- Rows with NULL fiscal_month/fiscal_day = FISCAL period records
- Rows with all fiscal components populated = MONTHLY period records
- NO NULL values in the `value` column (all gaps imputed)
- One row per (dataset, ticker, metric, fiscal_year, fiscal_month, fiscal_day)

---

### imputation_audit_trail
**Purpose:** Audit trail of imputation decisions and data quality issues

**Key Columns:**
- `audit_id` (BIGINT, PK): Identity primary key
- `dataset_id` (UUID, FK): References dataset_versions
- `ticker` (TEXT, NOT NULL): Stock ticker symbol
- `metric_name` (TEXT, NOT NULL): Metric identifier
- `fiscal_year` (INTEGER, NULLABLE): Fiscal year; NULL for data quality issues without clear year mapping
- `imputation_step` (TEXT, NOT NULL): Classification of the issue/imputation
- `original_value` (NUMERIC): Original value before imputation (NULL for duplicates/invalid values)
- `imputed_value` (NUMERIC, NOT NULL): Value used in fundamentals table
- `metadata` (JSONB): Additional context as JSON
- `created_at` (TIMESTAMPTZ)

**Imputation Steps (CHECK constraint):**
- `'FORWARD_FILL'`: Previous valid value carried forward
- `'BACKWARD_FILL'`: Next valid value carried backward
- `'INTERPOLATE'`: Linear interpolation between valid values
- `'SECTOR_MEDIAN'`: Filled with sector median value
- `'MARKET_MEDIAN'`: Filled with market median value
- `'MISSING'`: Gap that couldn't be imputed
- `'DATA_QUALITY_DUPLICATE'`: Duplicate record (only first occurrence kept)
- `'DATA_QUALITY_INVALID_VALUE'`: Non-numeric value that couldn't be parsed
- `'DATA_QUALITY_MISSING'`: Missing value in source data

**Metadata Structure Examples:**

For duplicates (DATA_QUALITY_DUPLICATE):
```json
{
  "period": "2024-03-29",
  "num_occurrences": 2
}
```

For invalid values (DATA_QUALITY_INVALID_VALUE):
```json
{
  "raw_value": "nan",
  "reason": "non_numeric"
}
```

**Indexes:**
- `imputation_audit_trail_pkey`: Primary key on audit_id
- `idx_imputation_audit_dataset`: On dataset_id
- `idx_imputation_audit_ticker_fy`: On (ticker, fiscal_year)
- `idx_imputation_audit_step`: On imputation_step

**Record Count Example:**
- ~1,000 DATA_QUALITY_DUPLICATE entries
- ~485 DATA_QUALITY_INVALID_VALUE entries
- ~500-1000 imputation entries (FORWARD_FILL, INTERPOLATE, etc.)

**Key Characteristics:**
- One row per imputed (ticker, fiscal_year, metric)
- Raw data rows DO NOT appear here (only imputed/quality-issue rows)
- Enables traceability of every transformation and data quality decision
- Allows analysis of which metrics/companies required most imputation

---

## Phase 4: Downstream Analysis Outputs

### metrics_outputs
**Purpose:** Store calculated metrics from analysis runs

**Key Columns:**
- `metrics_output_id` (BIGINT, PK): Identity primary key
- `dataset_id` (UUID, FK): References dataset_versions
- `parameter_set_id` (BIGINT, FK): References parameter_sets
- `ticker` (TEXT, NOT NULL, FK): References companies
- `metric_name` (TEXT, NOT NULL): Name of calculated metric
- `fiscal_year` (INT, NOT NULL): Fiscal year
- `calculated_value` (NUMERIC, NOT NULL): The calculated result
- `created_at` (TIMESTAMPTZ)

**Indexes:**
- `metrics_outputs_pkey`: Primary key on metrics_output_id
- `idx_metrics_outputs_dataset`: On dataset_id
- `idx_metrics_outputs_parameter_set`: On parameter_set_id

---

### optimization_outputs
**Purpose:** Store optimization results and recommendations

**Key Columns:**
- `optimization_output_id` (BIGINT, PK): Identity primary key
- `metrics_output_id` (BIGINT, FK): References metrics_outputs
- `optimization_type` (TEXT, NOT NULL): Type of optimization
- `result` (JSONB, NOT NULL): Optimization result details
- `created_at` (TIMESTAMPTZ)

**Indexes:**
- `optimization_outputs_pkey`: Primary key on optimization_output_id
- `idx_optimization_outputs_metrics`: On metrics_output_id

---

## Phase 5: Configuration & Parameters

### parameters
**Purpose:** Master list of tunable parameters for metric calculations

**Key Columns:**
- `parameter_id` (BIGINT, PK): Identity primary key
- `parameter_name` (TEXT, NOT NULL, UNIQUE): Parameter identifier
- `display_name` (TEXT, NOT NULL): Human-readable name
- `value_type` (TEXT): Data type of parameter
- `default_value` (TEXT, NOT NULL): Default value
- `created_at`, `updated_at` (TIMESTAMPTZ)

**Baseline Parameters:** 13 initialized on schema creation

**Indexes:**
- `parameters_pkey`: Primary key on parameter_id
- `idx_parameters_name`: On parameter_name

---

### parameter_sets
**Purpose:** Versioned parameter overrides for specific analysis runs

**Key Columns:**
- `parameter_set_id` (BIGINT, PK): Identity primary key
- `set_name` (TEXT, NOT NULL): Name of this parameter set (e.g., "base_case", "bear_case")
- `dataset_id` (UUID, FK): References dataset_versions
- `base_parameters_json` (JSONB, NOT NULL): JSON object with parameter overrides
- `created_at`, `updated_at` (TIMESTAMPTZ)

**Default Parameter Set:**
- `base_case`: Default parameter set created on schema initialization

**Indexes:**
- `parameter_sets_pkey`: Primary key on parameter_set_id
- `idx_parameter_sets_dataset`: On dataset_id

---

## Data Flow Summary

```
Input CSV
    ↓
dataset_versions (tracking)
    ↓
raw_data (with deduplication)
    ↓
companies & metric_units (reference)
    ↓
fundamentals (cleaned, imputed)
    ↓
imputation_audit_trail (quality tracking)
    ↓
parameters & parameter_sets (config)
    ↓
metrics_outputs (calculated metrics)
    ↓
optimization_outputs (analysis results)
```

---

## Key Design Patterns

### 1. Duplicate Detection (Implemented in raw_data)
- UNIQUE constraint on (dataset_id, ticker, metric_name, period)
- First occurrence wins (ON CONFLICT DO NOTHING)
- Duplicates logged in `imputation_audit_trail` with metadata containing period and occurrence count

### 2. Nullable Fiscal Year (In imputation_audit_trail)
- `fiscal_year` can be NULL for data quality issues without clear fiscal year mapping
- Allows tracking of data quality issues that span multiple years or have ambiguous dates

### 3. Metadata JSONB Tracking
- `fundamentals.metadata`: Tracks imputation method and confidence per row
- `imputation_audit_trail.metadata`: Stores period/occurrence details for duplicates
- `dataset_versions.metadata`: Stores ingestion reconciliation statistics
- `parameter_sets.base_parameters_json`: Stores parameter overrides

### 4. Cascading Deletes
- `raw_data` and `imputation_audit_trail` cascade delete when `dataset_versions` is deleted
- Ensures consistency when removing old ingestion runs

### 5. Auto-Updating Timestamps
- Triggers update `updated_at` when fundamentals, parameters, or parameter_sets change
- Enables tracking of when data was last modified

---

## Common Queries

### Find all duplicates detected in latest ingestion
```sql
SELECT 
    ticker,
    metric_name,
    COUNT(*) as duplicate_count,
    JSON_AGG(metadata) as period_details
FROM cissa.imputation_audit_trail
WHERE imputation_step = 'DATA_QUALITY_DUPLICATE'
GROUP BY ticker, metric_name
ORDER BY duplicate_count DESC;
```

### Check data quality by metric
```sql
SELECT 
    metric_name,
    COUNT(DISTINCT ticker) as companies_affected,
    SUM(CASE WHEN imputation_step LIKE 'DATA_QUALITY_%' THEN 1 ELSE 0 END) as quality_issues,
    SUM(CASE WHEN imputation_step LIKE 'FORWARD_FILL%' THEN 1 ELSE 0 END) as forward_fills
FROM cissa.imputation_audit_trail
GROUP BY metric_name
ORDER BY quality_issues DESC;
```

### Verify fundamentals has no NULL values
```sql
SELECT 
    period_type,
    COUNT(*) as total_records,
    SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) as null_values
FROM cissa.fundamentals
GROUP BY period_type;
```

---

## For More Information

- Full SQL definitions: See `/backend/database/schema/schema.sql`
- Data validation queries: See `/VALIDATION_QUERIES.md`
- Schema initialization: Run `python backend/database/schema/schema_manager.py init`
