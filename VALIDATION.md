# Data Ingestion Validation Guide

This document validates that data was properly ingested and processed through the CISSA ETL pipeline into the `cissa` schema. It also documents the current schema structure and data quality tracking.

## Quick Start

For the most common validation tasks, see:
- **Schema reference**: See `/backend/database/CURRENT_SCHEMA.md` for complete table descriptions
- **Schema queries**: See `/VALIDATION_QUERIES.md` for copy-paste SQL validation queries
- **Deployment**: See `/backend/database/DEPLOYMENT_GUIDE.md` for the three essential commands

---

## Current Schema Overview

The CISSA database contains **10 tables** organized into 5 phases. This section documents each table and how to validate its contents.

### Phase 1: Raw Data Ingestion

#### **dataset_versions**
**Purpose:** Track each data ingestion run with metadata and versioning

**Key Columns:**
- `dataset_id` (UUID, PK): Unique identifier for this ingestion
- `dataset_name` (TEXT): Name of the dataset (e.g., "ASX Financial Metrics")
- `version_number` (INT): Sequential version counter
- `status` (TEXT): 'processing' | 'completed' | 'failed'
- `metadata` (JSONB): Ingestion reconciliation statistics
- `processed_at` (TIMESTAMPTZ): When ingestion completed

**What to Look For:**
- At least 1 record per ingestion run
- `status` should be 'completed' after successful ingestion
- `metadata` contains:
  - `total_csv_rows`: Total rows in source file (275,343)
  - `total_rows_processed`: Rows with valid ticker/metric/period (275,343)
  - `rows_with_unparseable_values`: Rejected invalid values (485)
  - `duplicate_combinations_found`: Duplicate (ticker, metric, period) (1,000)
  - `unique_rows_in_raw_data`: Final rows stored (273,858)

**Validation Query:**
```sql
SELECT dataset_name, version_number, status, 
       (metadata->>'total_csv_rows')::int as csv_rows,
       (metadata->>'unique_rows_in_raw_data')::int as unique_rows
FROM cissa.dataset_versions
ORDER BY created_at DESC LIMIT 1;
-- Should return: at least 1 row with status='completed'
```

---

#### **raw_data**
**Purpose:** Store all ingested rows with deduplication

**Key Columns:**
- `raw_data_id` (BIGINT, PK): Identity primary key
- `dataset_id` (UUID, FK): References dataset_versions
- `ticker` (TEXT): Stock ticker symbol
- `metric_name` (TEXT): Metric identifier
- `period` (DATE): Period for this data point
- `value` (NUMERIC): The numeric value

**Special Constraints:**
- `UNIQUE (dataset_id, ticker, metric_name, period)`: Only first occurrence of duplicate is kept

**What to Look For:**
- Total rows should equal unique rows from dataset_versions metadata (273,858)
- No NULL values in ticker, metric_name, period, or value
- Date range should span multiple years (1981-2024)
- All values should be numeric (no strings or special characters)

**Validation Query:**
```sql
SELECT COUNT(*) as total_rows,
       COUNT(DISTINCT ticker) as unique_tickers,
       COUNT(DISTINCT metric_name) as unique_metrics,
       MIN(period) as earliest_period,
       MAX(period) as latest_period
FROM cissa.raw_data;
-- Should return: ~273,858 rows, ~500 tickers, 20 metrics
```

---

### Phase 2: Company Reference Data

#### **companies**
**Purpose:** Master list of all companies

**Key Columns:**
- `ticker` (TEXT, PK): Stock ticker symbol
- `company_name` (TEXT): Full company name
- `parent_index` (TEXT): NULL or "ASX200"
- `sector` (TEXT): Industry sector
- `created_at`, `updated_at` (TIMESTAMPTZ)

**What to Look For:**
- ~500 total companies
- 200 with parent_index = 'ASX200' (top 200 companies)
- ~300 with parent_index = NULL (other ASX companies)
- Recognizable company names (BHP, CBA, RIO, CSL, etc.)

**Validation Query:**
```sql
SELECT parent_index, COUNT(*) as count
FROM cissa.companies
GROUP BY parent_index
ORDER BY count DESC;
-- Should return: ASX200: 200, NULL: ~300
```

---

#### **metric_units**
**Purpose:** Define the unit of measurement for each metric

**Key Columns:**
- `metric_id` (BIGINT, PK): Identity primary key
- `metric_name` (TEXT, UNIQUE): Metric identifier
- `unit` (TEXT): Unit of measurement (millions, %, number of shares, etc.)

**What to Look For:**
- Exactly 20 metrics defined
- Units should be consistent (e.g., all financial metrics in "millions")

**Validation Query:**
```sql
SELECT COUNT(*) as total_metrics,
       COUNT(DISTINCT unit) as unique_units
FROM cissa.metric_units;
-- Should return: 20 metrics, 5 unique units
```

---

### Phase 3: Cleaned Data

#### **fundamentals**
**Purpose:** Final cleaned, imputed fact table - Single source of truth

**Key Columns:**
- `fundamental_id` (BIGINT, PK): Identity primary key
- `dataset_id` (UUID, FK): References dataset_versions
- `ticker` (TEXT, FK): References companies
- `metric_name` (TEXT): Metric identifier
- `fiscal_year` (INT): Fiscal year (1981-2024)
- `fiscal_month` (INT): 1-12 for MONTHLY, NULL for FISCAL
- `fiscal_day` (INT): 1-31 for MONTHLY, NULL for FISCAL
- `period_type` (TEXT): 'FISCAL' | 'MONTHLY'
- `value` (NUMERIC): Final value (NEVER NULL after imputation)
- `metadata` (JSONB): Imputation tracking
- `created_at` (TIMESTAMPTZ)

**What to Look For:**
- ~273,858 total rows
- **NO NULL values** in the `value` column (all gaps imputed)
- FISCAL records have NULL fiscal_month and fiscal_day
- MONTHLY records have all fiscal components populated
- ~140,670 FISCAL rows, ~133,188 MONTHLY rows
- metadata contains `imputation_step` and `confidence_level`

**Critical Validations:**
```sql
-- Verify NO NULL values in fundamentals
SELECT COUNT(*) as null_values
FROM cissa.fundamentals
WHERE value IS NULL;
-- Should return: 0

-- Verify FISCAL records have NULL month/day
SELECT COUNT(*) as fiscal_with_month_day
FROM cissa.fundamentals
WHERE period_type = 'FISCAL' AND (fiscal_month IS NOT NULL OR fiscal_day IS NOT NULL);
-- Should return: 0

-- Verify period type distribution
SELECT period_type, COUNT(*) as count
FROM cissa.fundamentals
GROUP BY period_type;
-- Should return: FISCAL: ~140K, MONTHLY: ~133K
```

---

#### **imputation_audit_trail**
**Purpose:** Audit trail of imputation decisions and data quality issues

**Key Columns:**
- `audit_id` (BIGINT, PK): Identity primary key
- `dataset_id` (UUID, FK): References dataset_versions
- `ticker` (TEXT): Stock ticker symbol
- `metric_name` (TEXT): Metric identifier
- `fiscal_year` (INTEGER, NULLABLE): Fiscal year; NULL for ambiguous data quality issues
- `imputation_step` (TEXT): Classification of issue/imputation
- `original_value` (NUMERIC): Value before imputation (NULL for duplicates)
- `imputed_value` (NUMERIC): Value used in fundamentals
- `metadata` (JSONB): Additional context
- `created_at` (TIMESTAMPTZ)

**Imputation Steps:**
- `FORWARD_FILL`: Previous valid value carried forward
- `BACKWARD_FILL`: Next valid value carried backward
- `INTERPOLATE`: Linear interpolation between valid values
- `SECTOR_MEDIAN`: Filled with sector median
- `MARKET_MEDIAN`: Filled with market median
- `MISSING`: Gap that couldn't be imputed
- `DATA_QUALITY_DUPLICATE`: Duplicate record (only first occurrence kept)
- `DATA_QUALITY_INVALID_VALUE`: Non-numeric value that couldn't be parsed
- `DATA_QUALITY_MISSING`: Missing value in source data

**Metadata Examples:**

For duplicates:
```json
{
  "period": "2024-03-29",
  "num_occurrences": 2
}
```

For imputations:
```json
{
  "imputation_step": "FORWARD_FILL",
  "confidence_level": 0.95
}
```

**What to Look For:**
- DATA_QUALITY_DUPLICATE: ~1,000 entries (duplicates found and logged)
- DATA_QUALITY_INVALID_VALUE: ~485 entries (unparseable values)
- FORWARD_FILL/BACKWARD_FILL/INTERPOLATE: various imputation entries
- `fiscal_year` should be NULL for data quality issues without clear year
- `metadata` should contain period/date for duplicates
- No rows should have NULL `imputed_value` (value is always required)

**Validation Query:**
```sql
SELECT imputation_step, COUNT(*) as count
FROM cissa.imputation_audit_trail
GROUP BY imputation_step
ORDER BY count DESC;

-- Expected approximate distribution:
-- DATA_QUALITY_DUPLICATE: ~1,000
-- FORWARD_FILL: ~100-200
-- INTERPOLATE: ~50-100
-- Other steps: ~50-100
```

**Check for Duplicate Records:**
```sql
-- See all duplicates with period details
SELECT 
    ticker,
    metric_name,
    COUNT(*) as duplicate_count,
    metadata->>'period' as period
FROM cissa.imputation_audit_trail
WHERE imputation_step = 'DATA_QUALITY_DUPLICATE'
GROUP BY ticker, metric_name, metadata->>'period'
ORDER BY duplicate_count DESC
LIMIT 20;
```

---

### Phase 4: Downstream Analysis Outputs

#### **metrics_outputs**
**Purpose:** Store calculated metrics from analysis runs

**What to Look For:**
- Should have entries after running analysis/optimization code
- References should be valid (FK to dataset_versions, parameter_sets, companies)
- Values should be numeric and reasonable for the metric type

---

#### **optimization_outputs**
**Purpose:** Store optimization results

**What to Look For:**
- Should be populated after running optimization analysis
- Results should be stored as JSONB and be retrievable
- Should reference valid metrics_outputs

---

### Phase 5: Configuration & Parameters

#### **parameters**
**Purpose:** Master list of tunable parameters

**What to Look For:**
- Should have 13 baseline parameters loaded during initialization
- Parameters should have reasonable default values

**Validation Query:**
```sql
SELECT COUNT(*) as parameter_count
FROM cissa.parameters;
-- Should return: 13
```

---

#### **parameter_sets**
**Purpose:** Versioned parameter overrides

**What to Look For:**
- Should have at least 1 default parameter set (base_case)
- Parameter overrides should be stored as JSONB
- References should be valid (FK to dataset_versions)

**Validation Query:**
```sql
SELECT set_name, COUNT(*) as count
FROM cissa.parameter_sets
GROUP BY set_name;
-- Should return: at least base_case
```

---

## Data Quality Validation
   - `dataset_id` (UUID linking back to dataset_versions)
   - `ticker` (company ticker)
   - `metric_name` (which metric this value is for)
   - `period` (time period, e.g., "FY 2002", "2023-09-30")
   - `period_type` ("FISCAL" or "MONTHLY")
   - `raw_string_value` (original string from CSV, e.g., "2,660.63") - preserved for audit/debugging
   - `numeric_value` (parsed numeric value, e.g., 2660.63; never NULL in this table)
   - `currency` (e.g., "AUD")
- **What to Look For**:
   - Row count matches ingested records (rejected rows are in separate validation log, not here)
   - Mix of different tickers (BHP, RIO, CBA, CSL, etc.)
   - Mix of different metrics (Cash, Revenue, PAT, etc.)
   - Mix of period types: FISCAL (~140,000 rows) and MONTHLY (~134,000 rows) in full dataset
   - `numeric_value` always populated (no NULLs; validation failures don't reach this table)
   - Sample rows look reasonable (Cash values in thousands, Revenue in millions, etc.)

##### **SCHEMA REFINEMENTS NEEDED:**
- ✅ **KEEP**: `raw_data_id`, `dataset_id`, `ticker`, `metric_name`, `period`, `period_type`, `raw_string_value`, `numeric_value`, `currency`
- ✅ **REMOVE**: `validation_status` - all rows in this table are pre-validated; rejected rows go to separate log
- ✅ **REMOVE**: `rejection_reason` - validation failures don't reach this table
- ✅ **NOTE**: Stage 1 validation is syntactic only (numeric parsing, format checking); semantic/business validation happens in Stage 2 processing

#### **6. Processing Errors & Audit Trail** (via dataset_versions.metadata JSONB)
- **Location**: Errors are tracked in `dataset_versions.metadata` (JSONB), not in a separate table
- **Contains**: Stage 1 ingestion errors (unparseable numbers) and Stage 2 processing errors (failed alignment, imputation failures)
- **Captured in metadata**:
  ```json
  {
    "stage_1_ingestion": {
      "total_rows_ingested": 275000,
      "rows_with_valid_numbers": 274500,
      "rows_with_unparseable_values": 500
    },
    "stage_2_processing": {
      "total_rows_processed": 274500,
      "rows_successfully_aligned": 268000,
      "rows_imputed": 5000,
      "rows_failed_alignment": 1500,
      "failure_reasons": {
        "no_fiscal_year_mapping": 900,
        "ticker_not_in_companies": 600
      }
    }
  }
  ```
- **Why**: Keeps schema simple; failures are metadata, not stored rows. All raw data (including problematic rows) stays in raw_data as source of truth.

---

### **Stage 2: Processed Data (After FY Alignment & Imputation)**

#### **7. fundamentals**
- **Created By**: `DataQualityProcessor.process_dataset()` during Stage 2 processing
- **Expected Records**: 
   - Depends on FY alignment success
   - Typically fewer than raw_data (deduplicated and aligned)
   - Sample: 0-1,000 rows (if alignment issues)
   - Full: ~50,000-100,000 rows (if alignment works well)
- **Contains**: Clean, FY-aligned, imputed financial data ready for analysis
- **Key Columns**:
   - `fundamentals_id` (BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY)
   - `dataset_id` (UUID from dataset_versions)
   - `ticker` (company)
   - `fiscal_year` (INTEGER, aligned to standard fiscal year)
   - `metric_name` (which metric)
   - `numeric_value` (NUMERIC, final cleaned and imputed value)
   - `imputed` (BOOLEAN, was this value imputed?)
   - `metadata` (JSONB NOT NULL DEFAULT '{}', flexible; tracks imputation_step, confidence_level, and other data quality notes)
     - Example: `{"imputation_step": "FORWARD_FILL", "confidence": "MEDIUM", "notes": "filled from FY2024"}`
   - `created_at`, `updated_at` (TIMESTAMPTZ NOT NULL DEFAULT now())
- **What to Look For**:
   - Has rows (non-empty if FY alignment worked)
   - Multiple tickers represented
   - Multiple fiscal years per ticker
   - Mix of imputed (TRUE) and non-imputed (FALSE) values
   - `metadata` contains imputation details and confidence levels for each row
   - Values look reasonable for financial metrics

##### **SCHEMA REFINEMENTS NEEDED:**
- ✅ **ADD**: `fundamentals_id` as PRIMARY KEY (BIGINT GENERATED ALWAYS AS IDENTITY)
- ✅ **KEEP**: `dataset_id`, `ticker`, `fiscal_year`, `metric_name`, `numeric_value`, `imputed`
- ✅ **ADD**: `metadata` (JSONB NOT NULL DEFAULT '{}') - flexible; tracks imputation_step, confidence_level, and other data quality notes
- ✅ **REMOVE**: `imputation_step`, `confidence_level` (consolidated into metadata)
- ✅ **KEEP**: `created_at`, `updated_at`

#### **8. imputation_audit_trail**
- **Created By**: `DataQualityProcessor.process_dataset()` during Stage 2 processing
- **Expected Records**: Varies (only for rows that were imputed; raw data rows have no entry)
- **Contains**: Audit trail of which imputation method was used to fill each value
- **Key Columns**:
   - `audit_id` (BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY)
   - `dataset_id` (UUID from dataset_versions)
   - `ticker` (company)
   - `fiscal_year` (INTEGER, aligned fiscal year)
   - `metric_name` (which metric was imputed)
   - `imputation_step` (which method succeeded: FORWARD_FILL, BACKWARD_FILL, INTERPOLATE, SECTOR_MEDIAN, MARKET_MEDIAN, MISSING)
   - `original_value` (NUMERIC, what was in raw_data; usually NULL if data was completely missing)
   - `imputed_value` (NUMERIC, the final imputed value)
   - `created_at` (TIMESTAMPTZ NOT NULL DEFAULT now())
- **What to Look For**:
   - Shows distribution of imputation methods used (which step was needed for each gap)
   - FORWARD_FILL, BACKWARD_FILL most common (filling gaps with nearby values)
   - SECTOR_MEDIAN, MARKET_MEDIAN for larger gaps
   - MISSING for values that couldn't be filled
   - Each row represents one imputation decision made by the cascade
   - Row count ≤ fundamentals row count (only imputed rows have audit entries)

##### **SCHEMA REFINEMENTS NEEDED:**
- ✅ **ADD**: `audit_id` as PRIMARY KEY (BIGINT GENERATED ALWAYS AS IDENTITY)
- ✅ **KEEP**: `dataset_id`, `ticker`, `fiscal_year`, `metric_name`, `imputation_step`, `original_value`, `imputed_value`
- ✅ **REMOVE**: `source_record_id` (not needed; original_value provides traceability)
- ✅ **KEEP**: `created_at`
- ✅ **NOTE**: One row per imputed (ticker, fiscal_year, metric_name); raw data rows have no audit entry

---

### **Stage 3: Configuration & Parameters**

#### **9. parameters**
- **Contains**: Master list of tunable parameters for metric calculations and optimizations
- **Key Columns**:
   - `parameter_id` (BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY)
   - `parameter_name` (TEXT NOT NULL UNIQUE, e.g., "country_geography", "equity_risk_premium") - technical key
   - `display_name` (TEXT NOT NULL, e.g., "Country Index Number", "Equity Risk Premium") - user-readable name
   - `value_type` (TEXT, optional; e.g., "NUMERIC", "TEXT", "BOOLEAN") - helps with UI validation
   - `default_value` (TEXT NOT NULL) - the current parameter value
   - `created_at`, `updated_at` (TIMESTAMPTZ NOT NULL DEFAULT now())
- **Purpose**: Source of truth for baseline parameters; parameter_sets reference these via overrides
- **What to Look For**:
   - 13+ baseline parameters (listed below)
   - All parameters have parameter_name, display_name, and default_value
   - Updated when user changes a parameter (update default_value and updated_at)
- **Default Parameters (13 baseline)**:
   1. `country_geography` (TEXT): "Australia" - Primary geography/market (aligns with companies.geography)
   2. `currency_notation` (TEXT): "A$m" - Currency units and scale
   3. `cost_of_equity_approach` (TEXT): "Floating" - How to calculate cost of equity (Fixed or Floating)
   4. `include_franking_credits_tsr` (BOOLEAN): false - Include franking in TSR calculation
   5. `fixed_benchmark_return_wealth_preservation` (NUMERIC): 7.5 - Benchmark return for wealth preservation (%)
   6. `equity_risk_premium` (NUMERIC): 5.0 - ERP for cost of equity calculations (%)
   7. `tax_rate_franking_credits` (NUMERIC): 30.0 - Tax rate for franking calculation (%)
   8. `value_of_franking_credits` (NUMERIC): 75.0 - Value adjustment for franking (%)
   9. `risk_free_rate_rounding` (NUMERIC): 0.5 - Rounding increment for risk-free rate (%)
   10. `beta_rounding` (NUMERIC): 0.1 - Rounding increment for beta
   11. `last_calendar_year` (NUMERIC): 2019 - Reference calendar year (can be updated by user)
   12. `beta_relative_error_tolerance` (NUMERIC): 40.0 - Tolerance for beta estimation errors (%)
   13. `terminal_year` (NUMERIC): 60 - Terminal year for projections (can vary by user preference)

##### **SCHEMA REFINEMENTS NEEDED:**
- ✅ **KEEP**: `parameter_id`, `parameter_name`, `display_name`, `value_type`, `default_value`, `created_at`, `updated_at`
- ✅ **REMOVE**: `description`, `current_value`, `unit`, `min_value`, `max_value`, `active`
- ✅ **UPDATE PATTERN**: When user updates a parameter, update `default_value` and `updated_at` in existing row (no new ID)
- ✅ **NEW PARAM_SET**: After parameter updates, create new row in parameter_sets with name and param_overrides (only changed values)
- ✅ **DATA LOADING**: Insert 13 baseline parameters as part of schema initialization
- ✅ **UI CONVERSION**: BOOLEAN values should display as "Yes"/"No" in UI

#### **10. parameter_sets**
- **Contains**: Named bundles of parameter configurations that override baseline parameters
- **Key Columns**:
   - `param_set_id` (UUID PRIMARY KEY)
   - `param_set_name` (TEXT NOT NULL UNIQUE, e.g., "base_case", "bull_case", "bear_case", "user_scenario_1")
   - `description` (TEXT, optional notes about this scenario)
   - `is_default` (BOOLEAN, only one should be true - points to baseline parameters table)
   - `is_active` (BOOLEAN, whether this set is available for use)
   - `param_overrides` (JSONB NOT NULL DEFAULT '{}', stores ONLY changed parameter values)
     - Example: `{"equity_risk_premium": 6.0, "beta_rounding": 0.15}` (only deviations from baseline)
     - Non-listed parameters inherit from `parameters.default_value`
   - `created_by` (TEXT, who created this set)
   - `created_at`, `updated_at` (TIMESTAMPTZ NOT NULL DEFAULT now())
- **Purpose**: Groups related parameter configurations for reproducible analysis with different assumptions
- **Relationships**:
   - References `parameters` table implicitly (via param_overrides keys)
   - One default param_set points to all 13 baseline parameters
   - Additional param_sets override specific parameters
- **What to Look For**:
   - One param_set with is_default=true and param_overrides='{}' (uses all baseline values)
   - Additional param_sets with specific overrides for scenarios
   - param_set_name is descriptive and human-readable
- **Example Scenarios**:
   - `base_case`: is_default=true, param_overrides={}
   - `bull_case`: equity_risk_premium=4.0, terminal_year=70
   - `bear_case`: equity_risk_premium=6.5, terminal_year=50
   - `user_scenario_2025`: user updates equity_risk_premium=5.5 and tax_rate=32.0

##### **SCHEMA REFINEMENTS NEEDED:**
- ✅ **KEEP**: `param_set_id`, `param_set_name`, `description`, `is_default`, `is_active`, `param_overrides`, `created_by`, `created_at`, `updated_at`
- ✅ **UPDATE PATTERN**: When user updates parameters:
  1. Update `parameters.default_value` for changed parameters
  2. Create new `parameter_sets` row with param_overrides containing ONLY the changed values
  3. Update is_default=true for the new set if it should become baseline
- ✅ **NO FK TO PARAMETERS**: param_overrides is flexible JSONB; keys are parameter_names, not IDs
- ✅ **DATA LOADING**: Create default param_set (is_default=true, param_overrides={})

---

### **Stage 4: Downstream Outputs**

#### **11. metrics_outputs**
- **Source**: Computed from `fundamentals` + `parameter_sets` (by external Python process)
- **Expected Records**: Varies (depends on metrics computed and parameter sets applied)
- **Contains**: Computed metrics derived from fundamental data using parameter configurations
- **Key Columns**:
   - `metrics_output_id` (BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY)
   - `dataset_id` (UUID, links to dataset_versions for data traceability)
   - `param_set_id` (UUID, links to parameter_sets for reproducibility)
   - `ticker` (TEXT, company)
   - `fiscal_year` (INTEGER)
   - `output_metric_name` (TEXT, e.g., "pe_ratio", "dividend_yield", "valuation_multiple")
   - `output_metric_value` (NUMERIC, the computed result)
   - `metadata` (JSONB DEFAULT '{}', flexible; can store computation details if needed)
   - `created_at` (TIMESTAMPTZ NOT NULL DEFAULT now())
- **Purpose**: Stores derived metrics computed by external Python process from fundamentals
- **What to Look For**:
   - One row per (dataset, param_set, ticker, fiscal_year, metric)
   - Links to both dataset_versions and parameter_sets for full reproducibility
   - Different metrics for same ticker/fy can exist with different param_sets
   - output_metric_value contains the computed result

##### **SCHEMA REFINEMENTS NEEDED:**
- ✅ **KEEP**: `metrics_output_id`, `dataset_id`, `param_set_id`, `ticker`, `fiscal_year`, `output_metric_name`, `output_metric_value`, `metadata`, `created_at`
- ✅ **REMOVE**: `confidence_interval_lower`, `confidence_interval_upper`, `computation_method`, `derivation_notes`
- ✅ **NOTE**: Flexibility for future metadata storage via JSONB column

#### **12. optimization_outputs**
- **Source**: Results from optimization algorithms (external process)
- **Expected Records**: Varies (depends on optimization jobs run)
- **Contains**: Results from optimization runs with multi-year projections
- **Key Columns**:
   - `optimization_id` (UUID PRIMARY KEY)
   - `dataset_id` (UUID, links to dataset_versions for data traceability)
   - `param_set_id` (UUID, links to parameter_sets for reproducibility)
   - `ticker` (TEXT, company being optimized)
   - `result_summary` (JSONB NOT NULL DEFAULT '{}', hierarchical projection results)
     - Structure:
       ```json
       {
         "2000": {
           "metric1": {
             "2001": "value1",
             "2002": "value2",
             ...
           },
           "metric2": {
             "2001": "value1",
             "2002": "value2",
             ...
           }
         },
         "2001": { ... },
         ...
         "2026": { ... }
       }
       ```
     - Base year repeats from earliest to current fiscal year
     - Projected years extend up to time window N
   - `metadata` (JSONB NOT NULL DEFAULT '{}', flexible; tracks optimization type, status, constraints, solver info, errors)
     - Example: `{"optimization_type": "portfolio_allocation", "status": "COMPLETED", "constraint_type": "risk_limits", "solver": "scipy", "error": null}`
   - `created_by` (TEXT NOT NULL DEFAULT 'admin')
   - `created_at`, `updated_at` (TIMESTAMPTZ NOT NULL DEFAULT now())
- **Purpose**: Stores results from optimization algorithms with multi-year projections for analysis
- **What to Look For**:
   - result_summary contains hierarchical structure (base_year → metrics → projected_years)
   - Links to dataset_versions and parameter_sets for full reproducibility
   - metadata tracks optimization details (type, status, constraints, solver info)
   - created_by shows who initiated the optimization

##### **SCHEMA REFINEMENTS NEEDED:**
- ✅ **KEEP**: `optimization_id`, `dataset_id`, `param_set_id`, `ticker`, `result_summary`, `metadata`, `created_by`, `created_at`, `updated_at`
- ✅ **REMOVE**: `optimization_type`, `objective_function`, `optimization_status`, `constraint_details`, `solver_metadata`, `error_message` (consolidate into metadata)
- ✅ **UPDATE**: `created_by` DEFAULT 'admin'
- ✅ **NOTE**: result_summary stores hierarchical projection data; metadata stores run details (type, status, constraints, solver, errors)

---

## Data Quality Validation

### Duplicate Detection System

The pipeline includes a duplicate detection system that:
1. Identifies rows with identical (ticker, metric_name, period) combinations
2. Keeps only the first occurrence (ON CONFLICT DO NOTHING)
3. Logs all duplicates to `imputation_audit_trail` with metadata

**Verify Duplicates Were Detected:**
```sql
-- Count duplicates found
SELECT COUNT(*) as duplicates_found
FROM cissa.imputation_audit_trail
WHERE imputation_step = 'DATA_QUALITY_DUPLICATE';
-- Expected: ~1,000

-- See specific duplicates by metric
SELECT 
    metric_name,
    COUNT(*) as count,
    COUNT(DISTINCT ticker) as affected_tickers
FROM cissa.imputation_audit_trail
WHERE imputation_step = 'DATA_QUALITY_DUPLICATE'
GROUP BY metric_name
ORDER BY count DESC;
```

---

### Invalid Values Processing

The pipeline logs any non-numeric or unparseable values:

**Verify Invalid Values Were Captured:**
```sql
-- Count invalid values
SELECT COUNT(*) as invalid_values
FROM cissa.imputation_audit_trail
WHERE imputation_step = 'DATA_QUALITY_INVALID_VALUE';
-- Expected: ~485

-- Check a few examples
SELECT 
    ticker,
    metric_name,
    original_value,
    imputed_value
FROM cissa.imputation_audit_trail
WHERE imputation_step = 'DATA_QUALITY_INVALID_VALUE'
LIMIT 10;
```

---

### Imputation Coverage

Verify that the pipeline successfully imputed all necessary gaps:

**Verify All Fundamentals Have Values:**
```sql
-- Check for any NULL values (should be none)
SELECT COUNT(*) as null_count
FROM cissa.fundamentals
WHERE value IS NULL;
-- Expected: 0

-- Show distribution of imputation methods used
SELECT 
    imputation_step,
    COUNT(*) as count
FROM cissa.imputation_audit_trail
WHERE imputation_step NOT LIKE 'DATA_QUALITY_%'
GROUP BY imputation_step
ORDER BY count DESC;
```

---

## Common Queries

### Dataset Summary
```sql
SELECT 
    dataset_name,
    version_number,
    (metadata->>'unique_rows_in_raw_data')::int as raw_data_rows,
    (metadata->>'duplicate_combinations_found')::int as duplicates,
    (metadata->>'rows_with_unparseable_values')::int as invalid_values,
    processed_at
FROM cissa.dataset_versions
ORDER BY processed_at DESC LIMIT 1;
```

### Data Distribution Check
```sql
SELECT 
    'fundamentals' as table_name, COUNT(*) as rows FROM cissa.fundamentals
UNION ALL
SELECT 'raw_data', COUNT(*) FROM cissa.raw_data
UNION ALL
SELECT 'companies', COUNT(*) FROM cissa.companies
UNION ALL
SELECT 'metric_units', COUNT(*) FROM cissa.metric_units;
```

### Period Type Breakdown
```sql
SELECT period_type, COUNT(*) as count
FROM cissa.fundamentals
GROUP BY period_type
ORDER BY count DESC;
```

---

## Troubleshooting

### Issue: Fewer rows than expected in fundamentals
```sql
-- Check raw_data count
SELECT COUNT(*) FROM cissa.raw_data;

-- Check if duplicates were detected
SELECT COUNT(*) FROM cissa.imputation_audit_trail
WHERE imputation_step = 'DATA_QUALITY_DUPLICATE';

-- Check if invalid values were logged
SELECT COUNT(*) FROM cissa.imputation_audit_trail
WHERE imputation_step = 'DATA_QUALITY_INVALID_VALUE';

-- Verify reconciliation formula
-- Expected: raw_data_count + duplicates + invalid_values = csv_rows (approx)
```

### Issue: NULL values found in fundamentals.value
```sql
-- Find which rows have NULLs
SELECT ticker, metric_name, fiscal_year, fiscal_month, fiscal_day
FROM cissa.fundamentals
WHERE value IS NULL
LIMIT 10;

-- This should not happen - all values should be imputed
-- If found, re-run Stage 3 (Imputation & FY Alignment)
```

### Issue: FISCAL records have fiscal_month or fiscal_day populated
```sql
-- Find problematic records
SELECT COUNT(*) as problem_count
FROM cissa.fundamentals
WHERE period_type = 'FISCAL' 
  AND (fiscal_month IS NOT NULL OR fiscal_day IS NOT NULL);

-- This should return 0
```

---

## Related Documentation

For more detailed information, see:
- **Schema Reference**: `/backend/database/CURRENT_SCHEMA.md`
- **Validation Queries**: `/VALIDATION_QUERIES.md`
- **Deployment Guide**: `/backend/database/DEPLOYMENT_GUIDE.md`
- **README**: `/README.md`

---

## Notes

- All tables are in the `cissa` schema
- All timestamps are in UTC (TIMESTAMPTZ type)
- The `fundamentals` table is the single source of truth for clean data
- The `imputation_audit_trail` provides full traceability of all data quality decisions
- Each pipeline run creates a new `dataset_versions` entry with unique `dataset_id`
- Duplicate detection happens automatically during Stage 1 (Ingestion)
- All data quality issues are logged and queryable for analysis
