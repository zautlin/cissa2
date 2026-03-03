# Data Ingestion Validation Guide

## Overview

This document provides a reference guide for visually inspecting the database tables to confirm that data was properly ingested through the three-stage ETL pipeline into the `cissa` schema.

---

## Data Ingestion Sequence

The pipeline ingests data in the following order:

### **Stage 0: Reference Tables (One-Time Setup)**

These tables are populated once from the input data files and remain relatively static.

#### **1. companies**
- **Source File**: `/home/ubuntu/cissa/input-data/ASX/extracted-worksheets/Base.csv`
- **Expected Records**: 500
- **Contains**: ASX company master data
- **Key Columns**: 
  - `ticker` (unique identifier, e.g., "BHP AU Equity")
  - `name` (company name)
  - `sector` (market sector classification)
  - `bics_level_1`, `bics_level_2`, `bics_level_3`, `bics_level_4` (detailed industry classification)
  - `currency` (typically "AUD")
- **What to Look For**:
  - 500 unique ticker values
  - Company names that are recognizable ASX stocks (BHP, CBA, RIO, CSL, etc.)
  - 12 unique sectors
  - All records have same currency (AUD)

##### **SCHEMA REFINEMENTS NEEDED:**
- ✅ **ADD**: `fy_report_month` (INTEGER, e.g., 6 for June) - tracks which month each company's fiscal year ends in (from Base.csv)
- ✅ **ADD**: `begin_year` (INTEGER) - tracks the first year this company data is available for (from Base.csv)
- ✅ **ADD**: `geography` (TEXT NOT NULL DEFAULT 'Australia') - tracks which market/geography the company is listed in (from Base.csv); supports future expansion to US/UK markets; kept as single column (not junction table) since each company has one primary listing geography
- ✅ **REMOVE**: `active` column - redundant since all companies should be active by default; if needed, use soft deletes or a separate decommissioned_at timestamp instead
- ✅ **KEEP**: All other columns as-is

#### **2. fiscal_year_mapping**
- **Source File**: `/home/ubuntu/cissa/input-data/ASX/extracted-worksheets/FY Dates.csv`
- **Expected Records**: ~10,900
- **Contains**: Mapping of (ticker, fiscal_year) combinations to their fiscal period end dates
- **Key Columns**:
  - `ticker` (e.g., "BHP AU Equity")
  - `fiscal_year` (e.g., 2002, 2003, ..., 2023)
  - `fy_period_date` (DATE when that fiscal year ends for that company)
- **What to Look For**:
  - Multiple fiscal years per company (roughly 20+ years of history)
  - ~500 companies × ~20 fiscal years = ~10,000 mappings
  - Dates make sense (e.g., BHP's FY 2002 ends in 2002, FY 2003 ends in 2003)
  - Some companies may have fewer years of history (NULL or missing entries)

---

### **Stage 1: Dataset Version & Raw Data (Per Ingestion Run)**

#### **4. dataset_versions**
- **Created By**: `Ingester.load_dataset()` at start of each pipeline run
- **Expected Records**: 1 per unique dataset (same dataset_name + source_file_hash = same version)
- **Contains**: Metadata and audit trail for each data ingestion
- **Key Columns**:
   - `dataset_id` (UUID, PRIMARY KEY, unique identifier for this ingestion)
   - `dataset_name` (auto-generated: `<geography>_<start_year>_<end_year>_<num_companies>`, e.g., "AU_2002_2023_500")
   - `version_number` (increments each time same dataset_name is re-uploaded with different source_file_hash)
   - `source_file` (full file path, e.g., "/home/ubuntu/cissa/input-data/ASX/raw-data/Bloomberg Download data.xlsx")
   - `source_file_hash` (SHA256 hash of the source file; used to detect duplicates and track versions)
   - `metadata` (JSONB, flexible; captures validation step outputs, e.g., `{validation_passed: 5000, validation_failed: 0, ...}`)
   - `created_by` (TEXT NOT NULL DEFAULT 'admin'; will integrate with user authentication in future)
   - `created_at` (TIMESTAMPTZ NOT NULL DEFAULT now())
   - `updated_at` (TIMESTAMPTZ NOT NULL DEFAULT now())
- **What to Look For**:
   - At least 1 record (from our test run)
   - `dataset_name` follows format: `<geography>_<start_year>_<end_year>_<num_companies>` (calculated from data)
   - `version_number` increments only when same dataset_name is re-uploaded with different source_file_hash
   - `source_file_hash` prevents re-ingesting the same file twice
   - `metadata` contains validation statistics

##### **SCHEMA REFINEMENTS NEEDED:**
- ✅ **UPDATE**: `dataset_name` generation logic - auto-calculate from data as `<geography>_<start_year>_<end_year>_<num_companies>` and always enforce this naming convention
- ✅ **KEEP**: `dataset_id` as PRIMARY KEY (UUID)
- ✅ **ADD**: `source_file_hash` (TEXT NOT NULL) - SHA256 hash of source file for duplicate detection and versioning
- ✅ **ADD**: `version_number` (INTEGER) - increments when same dataset_name is re-uploaded with different file hash
- ✅ **UPDATE**: `source_file` to store full file path (not just filename)
- ✅ **REMOVE**: `status`, `ingestion_timestamp`, `processing_completed_at`, `processing_timestamp`
- ✅ **REPLACE**: `total_raw_rows`, `validation_rejected_rows`, `validation_reject_summary` → use flexible `metadata` (JSONB) instead
- ✅ **REPLACE**: `quality_metadata` → use `metadata` (JSONB)
- ✅ **ADD**: `created_by` (TEXT NOT NULL DEFAULT 'admin') - tracks who initiated the ingestion (future: integrate with user authentication)
- ✅ **REMOVE**: `notes`
- ✅ **KEEP/ADD**: `created_at`, `updated_at` (TIMESTAMPTZ NOT NULL DEFAULT now())
- ✅ **ADD CONSTRAINT**: UNIQUE (dataset_name, source_file_hash) to prevent duplicate ingestions

#### **5. raw_data**
- **Source File**: `/home/ubuntu/cissa/input-data/ASX/consolidated-data/financial_metrics_fact_table.csv`
- **Expected Records**: 
   - Sample test: ~5,000 rows
   - Full dataset: ~275,000 rows
- **Contains**: Raw ingested financial data (only successfully validated/parsed rows; rejected rows go to separate log)
- **Key Columns**:
   - `raw_data_id` (BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY)
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

Use this checklist when visually inspecting the database:

### Reference Tables
- [ ] `companies`: 500 rows, all unique tickers, 12 sectors, includes fy_report_month and begin_year
- [ ] `fiscal_year_mapping`: ~10,900 rows, dates make sense

### Ingestion Run
- [ ] `dataset_versions`: 1+ rows, dataset_name follows format, source_file_hash populated
- [ ] `raw_data`: 5,000+ rows (sample) or 275,000+ (full), mix of FISCAL/MONTHLY period types

### Processing Results
- [ ] `fundamentals`: Has rows (>0), multiple tickers and fiscal years
- [ ] `imputation_audit_trail`: Shows distribution of imputation methods

---

## Typical Row Counts (Reference)

| Table | Expected | Sample Test | Full Dataset |
|-------|----------|-------------|--------------|
| companies | 500 | 500 | 500 |
| fiscal_year_mapping | ~10,900 | ~10,900 | ~10,900 |
| dataset_versions | 1+ | 1 | 1 |
| raw_data | variable | 5,000 | ~275,000 |
| raw_data_validation_log | 0-low | 0 | 0-low |
| fundamentals | variable | 0-1,000 | ~50,000-100,000 |
| imputation_audit_trail | variable | 0-500 | ~10,000-50,000 |

---

## How to Query These Tables

### Connect to Database
```bash
export PGPASSWORD='5VbL7dK4jM8sN6cE2fG'
psql -h localhost -U postgres -d rozetta
```

### View Table Structure
```sql
-- In psql, use \d to describe a table
\d cissa.companies
\d cissa.raw_data
\d cissa.fundamentals
```

### Count Rows
```sql
SELECT COUNT(*) FROM cissa.companies;
SELECT COUNT(*) FROM cissa.raw_data;
SELECT COUNT(*) FROM cissa.fundamentals;
```

### Sample Data
```sql
SELECT * FROM cissa.companies LIMIT 5;
SELECT * FROM cissa.raw_data LIMIT 10;
SELECT * FROM cissa.fundamentals LIMIT 10;
```

### View Dataset Version Info
```sql
SELECT dataset_name, version_number, status, total_raw_rows, validation_rejected_rows 
FROM cissa.dataset_versions;
```

---

## Notes

- All tables are in the `cissa` schema (separate from `public`)
- Queries automatically use `cissa` schema due to connection string `search_path=cissa`
- Tables are immutable in design: `raw_data` is never updated, only inserted/deleted
- `fundamentals` is the single source of truth for clean, processed data
- Each pipeline run creates a new `dataset_versions` row with unique `dataset_id`
- All timestamps are in UTC (`TIMESTAMPTZ` type)

---

## Last Updated

Generated: 2026-03-03  
Pipeline Status: ✅ Deployed and tested successfully
