# Schema Reference Documentation

**Purpose**: Comprehensive reference for all 12 tables, columns, constraints, and relationships.

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Reference Tables](#reference-tables)
3. [Versioning & Tracking](#versioning--tracking)
4. [Raw Data (Staging)](#raw-data-staging)
5. [Cleaned Data (Fact Table)](#cleaned-data-fact-table)
6. [Configuration](#configuration)
7. [Downstream Outputs](#downstream-outputs)
8. [Relationships & Dependencies](#relationships--dependencies)
9. [Query Examples](#query-examples)

---

## Quick Reference

### Table Directory

| Layer | Table | Rows | Purpose |
|-------|-------|------|---------|
| **Reference** | companies | ~30 | Master list of ASX companies |
| | metrics_catalog | ~30 | All available metrics |
| | fiscal_year_mapping | ~300+ | FY date mappings (ticker × fiscal_year) |
| **Versioning** | dataset_versions | 1+ | Track each Bloomberg upload |
| **Raw** | raw_data | 50,000+ | Validated raw ingestion (one row per ticker/metric/period) |
| **Cleaned** | fundamentals | 45,000+ | Final fact table (one row per ticker/metric/fiscal_year) |
| | imputation_audit_trail | 1,000+ | (Optional) Detailed imputation audit |
| **Config** | parameters | 10+ | Tunable parameters |
| | parameter_sets | 3+ | Named parameter bundles |
| **Downstream** | metrics_outputs | 50,000+ | Computed output metrics |
| | optimization_outputs | 100+ | Optimization results |

---

## Reference Tables

### `companies`

Master list of ASX companies from Base.csv. Immutable.

| Column | Type | Constraint | Example |
|--------|------|-----------|---------|
| company_id | UUID | PK | 550e8400-e29b-41d4-a716-446655440000 |
| **ticker** | TEXT | UNIQUE NOT NULL | "BHP AU Equity" |
| name | TEXT | NOT NULL | "BHP GROUP LTD" |
| sector | TEXT | | "Materials" |
| bics_level_1 | TEXT | | "Materials" |
| bics_level_2 | TEXT | | "Metals & Mining" |
| bics_level_3 | TEXT | | "Iron Ore Mining" |
| bics_level_4 | TEXT | | "Iron" |
| currency | TEXT | DEFAULT 'AUD' | "AUD" |
| active | BOOLEAN | DEFAULT true | true |
| created_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 12:00:00+00 |

**Indexes**:
- PK: company_id
- UNIQUE: ticker
- idx_companies_ticker
- idx_companies_sector

**Queries**:
```sql
-- Get all active companies
SELECT ticker, name, sector FROM companies WHERE active = TRUE;

-- Find companies in Materials sector
SELECT ticker, name FROM companies WHERE sector = 'Materials';
```

---

### `metrics_catalog`

Master list of all available metrics with their properties.

| Column | Type | Constraint | Example |
|--------|------|-----------|---------|
| metric_id | BIGINT | PK GENERATED | 1 |
| **metric_name** | TEXT | UNIQUE NOT NULL | "Revenue" |
| display_name | TEXT | | "Total Revenue (AUD M)" |
| **metric_type** | TEXT | CHECK IN (FISCAL, MONTHLY) | "FISCAL" |
| description | TEXT | | "Total company revenue" |
| unit | TEXT | | "Million AUD" |
| data_type | TEXT | DEFAULT 'NUMERIC' | "NUMERIC" |
| active | BOOLEAN | DEFAULT true | true |
| created_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 12:00:00+00 |

**Indexes**:
- PK: metric_id
- UNIQUE: metric_name
- idx_metrics_type
- idx_metrics_active

**Queries**:
```sql
-- Get all FISCAL metrics
SELECT metric_name, display_name, unit FROM metrics_catalog WHERE metric_type = 'FISCAL';

-- Find metrics for a company report
SELECT metric_name FROM metrics_catalog WHERE active = TRUE ORDER BY metric_name;
```

---

### `fiscal_year_mapping`

Maps (ticker, fiscal_year) to fiscal period end date. Used for FY alignment.

| Column | Type | Constraint | Example |
|--------|------|-----------|---------|
| fy_mapping_id | BIGINT | PK GENERATED | 1 |
| **ticker** | TEXT | NOT NULL | "BHP AU Equity" |
| **fiscal_year** | INTEGER | NOT NULL | 2023 |
| fy_period_date | DATE | NOT NULL | 2023-06-30 |
| created_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 12:00:00+00 |

**Indexes**:
- PK: fy_mapping_id
- UNIQUE: (ticker, fiscal_year)
- idx_fy_mapping_ticker

**Purpose**: During Stage 2 (imputation), we look up fy_period_date to know which calendar period to pull raw data from for each fiscal year.

**Queries**:
```sql
-- Get fiscal year end date for company
SELECT fiscal_year, fy_period_date FROM fiscal_year_mapping 
WHERE ticker = 'BHP AU Equity' ORDER BY fiscal_year;

-- Check if all companies have FY mapping for 2023
SELECT COUNT(DISTINCT ticker) FROM fiscal_year_mapping WHERE fiscal_year = 2023;
```

---

## Versioning & Tracking

### `dataset_versions`

Master audit table for each Bloomberg data upload. Tracks status and metadata throughout the pipeline.

| Column | Type | Constraint | Example |
|--------|------|-----------|---------|
| **dataset_id** | UUID | PK DEFAULT gen_random_uuid() | 550e8400-e29b-41d4-a716-446655440000 |
| dataset_name | TEXT | NOT NULL | "ASX_Q4_2024" |
| version_number | INTEGER | NOT NULL | 1 |
| source_file | TEXT | | "raw-data/Bloomberg Download data.xlsx" |
| **status** | TEXT | CHECK IN (PENDING, INGESTING, INGESTED, PROCESSING, PROCESSED, ERROR) | "PROCESSED" |
| ingestion_timestamp | TIMESTAMPTZ | | 2026-03-03 10:00:00+00 |
| ingestion_completed_at | TIMESTAMPTZ | | 2026-03-03 10:05:00+00 |
| total_raw_rows | INTEGER | | 50000 |
| validation_rejected_rows | INTEGER | | 120 |
| validation_reject_summary | JSONB | DEFAULT '{}' | {"non_numeric_marker: '#REF!'": 100, "cannot parse": 20} |
| processing_timestamp | TIMESTAMPTZ | | 2026-03-03 10:05:00+00 |
| processing_completed_at | TIMESTAMPTZ | | 2026-03-03 10:15:00+00 |
| quality_metadata | JSONB | DEFAULT '{}' | {"RAW": 40000, "SECTOR_MEDIAN": 500, "fill_rate": 0.996} |
| created_by | TEXT | | "system" |
| notes | TEXT | | "Q4 2024 ASX financial data" |
| created_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 09:00:00+00 |
| updated_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 10:15:00+00 |

**Indexes**:
- PK: dataset_id
- UNIQUE: (dataset_name, version_number)
- idx_dataset_versions_status
- idx_dataset_versions_created

**Triggers**:
- trigger_dataset_versions_updated - AUTO updates updated_at on any change

**Status Lifecycle**:
```
PENDING → INGESTING → INGESTED → PROCESSING → PROCESSED
                          ↓
                        ERROR (at any stage)
```

**Queries**:
```sql
-- Get latest dataset version for ASX
SELECT dataset_id, version_number, status, processing_completed_at
FROM dataset_versions
WHERE dataset_name = 'ASX_Q4_2024'
ORDER BY version_number DESC
LIMIT 1;

-- Monitor processing progress
SELECT dataset_id, status, 
       EXTRACT(EPOCH FROM (NOW() - ingestion_timestamp)) / 60 AS minutes_elapsed
FROM dataset_versions
WHERE status IN ('INGESTING', 'PROCESSING');

-- View quality stats
SELECT dataset_id, quality_metadata->>'RAW' AS raw_count,
       quality_metadata->>'fill_rate' AS fill_rate
FROM dataset_versions WHERE status = 'PROCESSED';
```

---

## Raw Data (Staging)

### `raw_data`

Immutable raw ingestion table with validation tracking. One row per (dataset, ticker, metric, period).

| Column | Type | Constraint | Example |
|--------|------|-----------|---------|
| raw_data_id | BIGINT | PK GENERATED | 1000 |
| **dataset_id** | UUID | FK → dataset_versions | 550e8400-e29b-41d4-a716-446655440000 |
| **ticker** | TEXT | NOT NULL | "BHP AU Equity" |
| **metric_name** | TEXT | NOT NULL | "Revenue" |
| **period** | TEXT | NOT NULL | "FY 2023" |
| period_type | TEXT | CHECK IN (FISCAL, MONTHLY) | "FISCAL" |
| raw_string_value | TEXT | NOT NULL | "12345.67" |
| numeric_value | NUMERIC | | 12345.67 |
| currency | TEXT | | "AUD" |
| validation_status | TEXT | CHECK IN (VALID, REJECTED, FLAGGED) | "VALID" |
| rejection_reason | TEXT | | NULL |
| created_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 12:00:00+00 |

**Indexes**:
- PK: raw_data_id
- UNIQUE: (dataset_id, ticker, metric_name, period)
- idx_raw_data_dataset
- idx_raw_data_ticker
- idx_raw_data_metric

**Purpose**: Stores all raw values from Excel, with validation pre-checks. Non-numeric values stored as NULL with rejection_reason.

**Queries**:
```sql
-- See what was rejected during ingestion
SELECT ticker, metric_name, period, raw_string_value, rejection_reason
FROM raw_data
WHERE dataset_id = '550e8400...' AND validation_status = 'REJECTED'
ORDER BY ticker, metric_name;

-- Validation failure summary
SELECT rejection_reason, COUNT(*) AS count
FROM raw_data
WHERE dataset_id = '550e8400...' AND validation_status = 'REJECTED'
GROUP BY rejection_reason
ORDER BY count DESC;

-- Get raw value for specific metric
SELECT ticker, period, raw_string_value, numeric_value
FROM raw_data
WHERE dataset_id = '550e8400...' AND metric_name = 'Revenue'
ORDER BY ticker, period;
```

---

## Cleaned Data (Fact Table)

### `fundamentals`

**THE** final cleaned, FY-aligned, imputed fact table. One row per (dataset, ticker, metric, fiscal_year).

This is the **single source of truth** for all downstream analysis.

| Column | Type | Constraint | Example |
|--------|------|-----------|---------|
| fundamentals_id | BIGINT | PK GENERATED | 100000 |
| **dataset_id** | UUID | FK → dataset_versions | 550e8400-e29b-41d4-a716-446655440000 |
| **ticker** | TEXT | NOT NULL | "BHP AU Equity" |
| **metric_name** | TEXT | NOT NULL | "Revenue" |
| **fiscal_year** | INTEGER | NOT NULL | 2023 |
| **value** | NUMERIC | NOT NULL | 12345.67 |
| currency | TEXT | | "AUD" |
| **imputation_source** | TEXT | CHECK IN (RAW, FORWARD_FILL, BACKWARD_FILL, INTERPOLATED, SECTOR_MEDIAN, MARKET_MEDIAN, MISSING) | "RAW" |
| confidence_level | TEXT | | "HIGH" |
| data_quality_flags | JSONB | DEFAULT '{}' | {"estimated": false} |
| created_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 12:00:00+00 |

**Indexes**:
- PK: fundamentals_id
- UNIQUE: (dataset_id, ticker, metric_name, fiscal_year)
- idx_fundamentals_dataset
- idx_fundamentals_ticker
- idx_fundamentals_metric
- idx_fundamentals_fiscal_year
- idx_fundamentals_imputation_source
- idx_fundamentals_dataset_ticker_fy (composite)
- idx_fundamentals_ticker_metric_fy (composite)

**Imputation Sources** (in priority order):
- **RAW**: Valid value from raw data
- **FORWARD_FILL**: Carried forward from previous fiscal year
- **BACKWARD_FILL**: Filled from first known value
- **INTERPOLATED**: Linear interpolation between two known values
- **SECTOR_MEDIAN**: Median of peer companies in same sector
- **MARKET_MEDIAN**: Median of all companies
- **MISSING**: Could not be resolved; NULL value

**Confidence Levels**:
- HIGH: RAW (actual data)
- MEDIUM: FORWARD_FILL, BACKWARD_FILL, INTERPOLATED
- LOW: SECTOR_MEDIAN, MARKET_MEDIAN
- NULL: MISSING

**Queries**:
```sql
-- Get all metrics for company in fiscal year
SELECT metric_name, value, imputation_source, confidence_level
FROM fundamentals
WHERE dataset_id = '550e8400...' AND ticker = 'BHP AU Equity' AND fiscal_year = 2023
ORDER BY metric_name;

-- Revenue trend for company
SELECT fiscal_year, value
FROM fundamentals
WHERE dataset_id = '550e8400...' AND ticker = 'BHP AU Equity' AND metric_name = 'Revenue'
ORDER BY fiscal_year;

-- Data quality by metric
SELECT metric_name, imputation_source, COUNT(*) AS count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY metric_name), 2) AS pct
FROM fundamentals
WHERE dataset_id = '550e8400...'
GROUP BY metric_name, imputation_source
ORDER BY metric_name, count DESC;

-- Find all imputed values (not raw)
SELECT ticker, metric_name, fiscal_year, value, imputation_source
FROM fundamentals
WHERE dataset_id = '550e8400...' AND imputation_source != 'RAW'
ORDER BY ticker, metric_name, fiscal_year;
```

---

### `imputation_audit_trail` (Optional)

Detailed audit trail of imputation decisions. Can be queried to understand why a specific value was chosen.

| Column | Type | Constraint | Example |
|--------|------|-----------|---------|
| audit_id | BIGINT | PK GENERATED | 1 |
| dataset_id | UUID | FK → dataset_versions | 550e8400-e29b-41d4-a716-446655440000 |
| ticker | TEXT | NOT NULL | "BHP AU Equity" |
| metric_name | TEXT | NOT NULL | "Cash" |
| fiscal_year | INTEGER | NOT NULL | 2015 |
| raw_value | NUMERIC | | NULL |
| raw_status | TEXT | CHECK IN (PRESENT, MISSING, INVALID) | "MISSING" |
| imputation_steps_applied | TEXT[] | | {"FORWARD_FILL"} |
| final_imputation_source | TEXT | | "FORWARD_FILL" |
| final_value | NUMERIC | | 2616.95 |
| peer_reference_data | JSONB | DEFAULT '{}' | {"sector_median": 2500.0, "market_median": 2400.0} |
| created_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 12:00:00+00 |

**Indexes**:
- PK: audit_id
- idx_imputation_audit_dataset
- idx_imputation_audit_ticker_fy

**Queries**:
```sql
-- Understand imputation for specific value
SELECT * FROM imputation_audit_trail
WHERE dataset_id = '550e8400...' AND ticker = 'BHP AU Equity' 
  AND metric_name = 'Cash' AND fiscal_year = 2015;

-- Show peer references used in imputation
SELECT ticker, metric_name, fiscal_year, final_value,
       peer_reference_data->>'sector_median' AS sector_median,
       peer_reference_data->>'market_median' AS market_median
FROM imputation_audit_trail
WHERE dataset_id = '550e8400...' AND final_imputation_source IN ('SECTOR_MEDIAN', 'MARKET_MEDIAN');
```

---

## Configuration

### `parameters`

Tunable parameters for metric calculations and optimization.

| Column | Type | Constraint | Example |
|--------|------|-----------|---------|
| parameter_id | BIGINT | PK GENERATED | 1 |
| **parameter_name** | TEXT | UNIQUE NOT NULL | "discount_rate" |
| display_name | TEXT | | "Discount Rate" |
| description | TEXT | | "WACC used for valuation" |
| value_type | TEXT | CHECK IN (NUMERIC, TEXT, BOOLEAN, JSONB) | "NUMERIC" |
| default_value | TEXT | | "0.08" |
| current_value | TEXT | | "0.08" |
| unit | TEXT | | "Percentage (0.00-1.00)" |
| min_value | NUMERIC | | 0.00 |
| max_value | NUMERIC | | 1.00 |
| active | BOOLEAN | DEFAULT true | true |
| created_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 12:00:00+00 |
| updated_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 12:00:00+00 |

**Triggers**:
- trigger_parameters_updated - AUTO updates updated_at on change

**Queries**:
```sql
-- Get all active parameters
SELECT parameter_name, current_value, unit FROM parameters WHERE active = TRUE;

-- Get parameter with its default and current values
SELECT parameter_name, default_value, current_value, (current_value != default_value) AS is_tweaked
FROM parameters WHERE parameter_name = 'discount_rate';
```

---

### `parameter_sets`

Named bundles of parameter configurations for reproducibility and scenario planning.

| Column | Type | Constraint | Example |
|--------|------|-----------|---------|
| **param_set_id** | UUID | PK DEFAULT gen_random_uuid() | 550e8400-e29b-41d4-a716-446655440000 |
| **param_set_name** | TEXT | UNIQUE NOT NULL | "conservative_valuation" |
| description | TEXT | | "Conservative assumptions for valuation" |
| is_default | BOOLEAN | DEFAULT false | false |
| is_active | BOOLEAN | DEFAULT true | true |
| **param_overrides** | JSONB | DEFAULT '{}' | {"discount_rate": 0.10, "inflation": 0.02} |
| created_by | TEXT | | "analyst_1" |
| created_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 12:00:00+00 |
| updated_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 12:00:00+00 |

**Triggers**:
- trigger_parameter_sets_updated - AUTO updates updated_at on change

**Predefined Sets** (suggested):
- "base_case" (is_default = true)
- "conservative_valuation"
- "bull_case"

**Queries**:
```sql
-- Get default parameter set
SELECT param_set_id, param_set_name, param_overrides FROM parameter_sets WHERE is_default = TRUE;

-- Get all parameter sets
SELECT param_set_name, description, param_overrides FROM parameter_sets WHERE is_active = TRUE;

-- Extract specific parameter from set
SELECT param_set_name, param_overrides->>'discount_rate' AS discount_rate
FROM parameter_sets WHERE is_active = TRUE;
```

---

## Downstream Outputs

### `metrics_outputs`

Computed metric outputs based on fundamentals + parameter sets.

| Column | Type | Constraint | Example |
|--------|------|-----------|---------|
| metrics_output_id | BIGINT | PK GENERATED | 1000 |
| **dataset_id** | UUID | FK → dataset_versions | 550e8400-e29b-41d4-a716-446655440000 |
| **param_set_id** | UUID | FK → parameter_sets | 550e8400-e29b-41d4-a716-446655440001 |
| **ticker** | TEXT | NOT NULL | "BHP AU Equity" |
| **fiscal_year** | INTEGER | NOT NULL | 2023 |
| **output_metric_name** | TEXT | NOT NULL | "ROE" |
| output_metric_value | NUMERIC | NOT NULL | 0.15 |
| confidence_interval_lower | NUMERIC | | 0.12 |
| confidence_interval_upper | NUMERIC | | 0.18 |
| computation_method | TEXT | | "PAT / Total Equity" |
| derivation_notes | TEXT | | "Computed from fundamentals" |
| metadata | JSONB | DEFAULT '{}' | {"calculation_date": "2026-03-03"} |
| created_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 12:00:00+00 |

**Indexes**:
- PK: metrics_output_id
- UNIQUE: (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
- idx_metrics_outputs_dataset
- idx_metrics_outputs_param_set
- idx_metrics_outputs_ticker_fy

**Purpose**: Allows computing same dataset with different parameter sets and comparing results.

---

### `optimization_outputs`

Results from optimization algorithms.

| Column | Type | Constraint | Example |
|--------|------|-----------|---------|
| optimization_id | UUID | PK DEFAULT gen_random_uuid() | 550e8400-e29b-41d4-a716-446655440000 |
| **dataset_id** | UUID | FK → dataset_versions | 550e8400-e29b-41d4-a716-446655440000 |
| **param_set_id** | UUID | FK → parameter_sets | 550e8400-e29b-41d4-a716-446655440001 |
| **ticker** | TEXT | NOT NULL | "BHP AU Equity" |
| optimization_type | TEXT | NOT NULL | "valuation" |
| objective_function | TEXT | | "Maximize intrinsic value" |
| **optimization_status** | TEXT | CHECK IN (PENDING, RUNNING, COMPLETED, ERROR) | "COMPLETED" |
| result_summary | JSONB | DEFAULT '{}' | {"intrinsic_value": 45.50, "upside_downside": "15%"} |
| constraint_details | JSONB | DEFAULT '{}' | {"min_price": 40, "max_price": 50} |
| solver_metadata | JSONB | DEFAULT '{}' | {"algorithm": "gradient_descent", "iterations": 1000} |
| error_message | TEXT | | NULL |
| created_by | TEXT | | "analyst_1" |
| created_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 12:00:00+00 |
| updated_at | TIMESTAMPTZ | DEFAULT now() | 2026-03-03 12:00:00+00 |

**Triggers**:
- trigger_optimization_outputs_updated - AUTO updates updated_at on change

**Status Lifecycle** (allows async processing):
```
PENDING → RUNNING → COMPLETED
            ↓
          ERROR
```

**Queries**:
```sql
-- Monitor optimization job queue
SELECT optimization_type, optimization_status, COUNT(*) AS count
FROM optimization_outputs
WHERE dataset_id = '550e8400...'
GROUP BY optimization_type, optimization_status;

-- Get completed optimizations
SELECT optimization_id, optimization_type, ticker, result_summary
FROM optimization_outputs
WHERE dataset_id = '550e8400...' AND optimization_status = 'COMPLETED'
ORDER BY updated_at DESC;

-- Extract optimization result
SELECT ticker, result_summary->>'intrinsic_value' AS intrinsic_value,
       result_summary->>'upside_downside' AS upside_downside
FROM optimization_outputs
WHERE dataset_id = '550e8400...' AND optimization_status = 'COMPLETED';
```

---

## Relationships & Dependencies

### Data Flow Diagram

```
companies, metrics_catalog, fiscal_year_mapping (Reference)
                    ↓
            raw_data (Stage 1: Ingest)
                    ↓
          fundamentals (Stage 2: Process)
                    ↓
        parameters + parameter_sets (Config)
                    ↓
    ┌──────────────────────┬──────────────────────┐
    ↓                      ↓
metrics_outputs     optimization_outputs
```

### Foreign Key Relationships

| From | To | Column | Constraint |
|------|--|----|-----------|
| raw_data | dataset_versions | dataset_id | REFERENCES dataset_versions.dataset_id ON DELETE CASCADE |
| fundamentals | dataset_versions | dataset_id | REFERENCES dataset_versions.dataset_id ON DELETE CASCADE |
| imputation_audit_trail | dataset_versions | dataset_id | REFERENCES dataset_versions.dataset_id ON DELETE CASCADE |
| metrics_outputs | dataset_versions | dataset_id | REFERENCES dataset_versions.dataset_id ON DELETE CASCADE |
| metrics_outputs | parameter_sets | param_set_id | REFERENCES parameter_sets.param_set_id |
| optimization_outputs | dataset_versions | dataset_id | REFERENCES dataset_versions.dataset_id ON DELETE CASCADE |
| optimization_outputs | parameter_sets | param_set_id | REFERENCES parameter_sets.param_set_id |

---

## Query Examples

### Time-Series Queries

```sql
-- Revenue trend for BHP over all fiscal years
SELECT fiscal_year, value
FROM fundamentals
WHERE dataset_id = '550e8400...' 
  AND ticker = 'BHP AU Equity' 
  AND metric_name = 'Revenue'
ORDER BY fiscal_year;
```

### Comparison Queries

```sql
-- Compare company metrics across two fiscal years
SELECT metric_name, fiscal_year, value, imputation_source
FROM fundamentals
WHERE dataset_id = '550e8400...' 
  AND ticker = 'BHP AU Equity'
  AND fiscal_year IN (2022, 2023)
ORDER BY metric_name, fiscal_year;
```

### Audit & Quality Queries

```sql
-- Data quality by metric
SELECT metric_name, imputation_source, COUNT(*) AS count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY metric_name), 2) AS pct
FROM fundamentals
WHERE dataset_id = '550e8400...'
GROUP BY metric_name, imputation_source
ORDER BY metric_name, pct DESC;

-- Find all imputed (non-raw) values
SELECT ticker, metric_name, fiscal_year, value, imputation_source, confidence_level
FROM fundamentals
WHERE dataset_id = '550e8400...' 
  AND imputation_source != 'RAW'
ORDER BY ticker, metric_name, fiscal_year;
```

---

**END OF SCHEMA REFERENCE**
