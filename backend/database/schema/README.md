# Database Schema - Quick Reference

**Last Updated**: 2026-03-03  
**Database**: PostgreSQL 16  
**Version**: 1.0

---

## Overview

The financial data pipeline uses a 12-table PostgreSQL schema organized into 6 layers:

| Layer | Purpose | Tables |
|-------|---------|--------|
| **Reference** | Static lookup data | companies, metrics_catalog, fiscal_year_mapping |
| **Versioning** | Data lineage & audit | dataset_versions |
| **Raw Data** | Pre-validation staging | raw_data, raw_data_validation_log |
| **Cleaned Data** | Final fact tables | fundamentals, imputation_audit_trail |
| **Configuration** | Tunable parameters | parameters, parameter_sets |
| **Downstream** | Analysis outputs | metrics_outputs, optimization_outputs |

**Total Tables**: 12  
**Indexes**: 30+  
**Triggers**: 4 (auto-update `updated_at`)

---

## Schema Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     REFERENCE LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│ companies                  metrics_catalog    fiscal_year_mapping│
│ (ticker, name, sector)     (metric_name)      (ticker, FY→date) │
└─────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│                    VERSIONING LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│ dataset_versions (dataset_id, status, quality_metadata)         │
└─────────────────────────────────────────────────────────────────┘
                                    ↓
        ┌─────────────────────────────────────────────┐
        │      STAGE 1: INGESTION                     │
        ├─────────────────────────────────────────────┤
        │ raw_data (validation_status, rejection_reason)
        │ raw_data_validation_log (optional audit)     │
        └─────────────────────────────────────────────┘
                                    ↓
        ┌─────────────────────────────────────────────┐
        │      STAGE 2: PROCESSING                    │
        ├─────────────────────────────────────────────┤
        │ fundamentals (imputation_source, confidence) │
        │ imputation_audit_trail (optional audit)      │
        └─────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│                    CONFIGURATION LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│ parameters (config keys)    parameter_sets (config bundles)     │
└─────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│                   DOWNSTREAM LAYER (OUTPUTS)                    │
├─────────────────────────────────────────────────────────────────┤
│ metrics_outputs (ROE, ROIC, etc.)                               │
│ optimization_outputs (valuations, portfolio opt., etc.)         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Table Descriptions

### Reference Layer

#### **companies**
Master list of all companies in the dataset.

| Column | Type | Notes |
|--------|------|-------|
| company_id | UUID | Primary Key |
| ticker | VARCHAR(10) | UNIQUE, e.g., "ANZ", "NAB" |
| name | VARCHAR(255) | Full company name |
| sector | VARCHAR(100) | Industry sector |
| bics_levels | TEXT | BICS classification (JSON array) |
| currency | VARCHAR(3) | ISO currency code (AUD, USD, etc.) |
| created_at | TIMESTAMP | Auto-populated |

**Indexes**: ticker (UNIQUE), sector

**Lifecycle**: Immutable - loaded once from Base.csv

**Example Query**:
```sql
SELECT * FROM companies WHERE sector = 'Banking' ORDER BY name;
```

---

#### **metrics_catalog**
Definition of all available metrics.

| Column | Type | Notes |
|--------|------|-------|
| metric_id | BIGINT | Primary Key |
| metric_name | VARCHAR(255) | UNIQUE, e.g., "Revenue", "Net Income" |
| metric_type | VARCHAR(20) | FISCAL or MONTHLY |
| unit | VARCHAR(50) | Unit (AUD, %, ratio, etc.) |
| description | TEXT | Metric definition |
| created_at | TIMESTAMP | Auto-populated |

**Indexes**: metric_name (UNIQUE), metric_type

**Lifecycle**: Static, grows as new metrics added

**Example Query**:
```sql
SELECT * FROM metrics_catalog WHERE metric_type = 'FISCAL';
```

---

#### **fiscal_year_mapping**
Maps (company, fiscal year) → fiscal year period end date.

| Column | Type | Notes |
|--------|------|-------|
| fiscal_year_mapping_id | BIGINT | Primary Key |
| ticker | VARCHAR(10) | FK → companies.ticker |
| fiscal_year | INTEGER | FY number (e.g., 2024) |
| fy_period_date | DATE | FY period end date (e.g., 2024-06-30) |
| created_at | TIMESTAMP | Auto-populated |

**Indexes**: (ticker, fiscal_year) UNIQUE, ticker, fiscal_year

**Lifecycle**: Static, loaded once from FY Dates.csv

**Example Query**:
```sql
SELECT * FROM fiscal_year_mapping WHERE ticker = 'ANZ' ORDER BY fiscal_year;
```

---

### Versioning Layer

#### **dataset_versions**
Master audit table tracking each Bloomberg upload and its processing stages.

| Column | Type | Notes |
|--------|------|-------|
| dataset_id | UUID | Primary Key |
| dataset_name | VARCHAR(255) | e.g., "ASX_Q4_2024" |
| version_number | INTEGER | e.g., 1, 2, ... |
| status | VARCHAR(50) | PENDING, INGESTING, INGESTED, PROCESSING, PROCESSED, ERROR |
| error_message | TEXT | Error details if status = ERROR |
| quality_metadata | JSONB | Quality stats (imputation counts, etc.) |
| created_at | TIMESTAMP | Auto-populated |
| updated_at | TIMESTAMP | Auto-updated by trigger |

**Indexes**: dataset_id (PK), status, created_at

**Lifecycle**: One row per upload; never deleted

**Status Flow**: PENDING → INGESTING → INGESTED → PROCESSING → PROCESSED

**Example Query**:
```sql
SELECT dataset_id, dataset_name, status, quality_metadata 
FROM dataset_versions 
ORDER BY created_at DESC LIMIT 10;
```

---

### Raw Data Layer

#### **raw_data**
Immutable raw ingestion staging table with validation metadata.

| Column | Type | Notes |
|--------|------|-------|
| raw_data_id | BIGINT | Primary Key |
| dataset_id | UUID | FK → dataset_versions.dataset_id |
| ticker | VARCHAR(10) | FK → companies.ticker |
| metric_name | VARCHAR(255) | FK → metrics_catalog.metric_name |
| period | VARCHAR(50) | e.g., "2024-06", "2024-01-01" |
| period_type | VARCHAR(20) | ANNUAL, MONTHLY, QUARTERLY |
| raw_string_value | TEXT | Original value from Excel |
| numeric_value | NUMERIC | Extracted numeric (NULL if invalid) |
| validation_status | VARCHAR(20) | VALID, REJECTED |
| rejection_reason | TEXT | Why validation failed (NULL if VALID) |
| created_at | TIMESTAMP | Auto-populated |

**Indexes**: (dataset_id, ticker, metric_name), dataset_id, ticker, validation_status

**Lifecycle**: Current version only; deleted after processing

**Validation Rules**:
- Non-numeric markers: "N/A", "NA", "TBD", "-", "--" → REJECTED
- Currency symbols, thousands separators → Parsed or REJECTED
- Valid range: -999,999,999,999 to +999,999,999,999

**Example Query**:
```sql
SELECT * FROM raw_data 
WHERE dataset_id = 'xxx' AND validation_status = 'REJECTED'
LIMIT 20;
```

---

#### **raw_data_validation_log** (Optional)
Audit trail of validation decisions (skip if not needed).

| Column | Type | Notes |
|--------|------|-------|
| validation_log_id | BIGINT | Primary Key |
| raw_data_id | BIGINT | FK → raw_data.raw_data_id |
| validation_rule | VARCHAR(255) | Rule applied |
| passed | BOOLEAN | TRUE if passed |
| details | JSONB | Validation details |
| created_at | TIMESTAMP | Auto-populated |

**Lifecycle**: Optional; can be truncated after audit period

---

### Cleaned Data Layer

#### **fundamentals**
**THE SINGLE SOURCE OF TRUTH** - cleaned, FY-aligned, imputed financial data.

| Column | Type | Notes |
|--------|------|-------|
| fundamentals_id | BIGINT | Primary Key |
| dataset_id | UUID | FK → dataset_versions.dataset_id |
| ticker | VARCHAR(10) | FK → companies.ticker |
| metric_name | VARCHAR(255) | FK → metrics_catalog.metric_name |
| fiscal_year | INTEGER | FY (e.g., 2024) |
| value | NUMERIC | Cleaned final value |
| imputation_source | VARCHAR(50) | RAW, FORWARD_FILL, BACKWARD_FILL, INTERPOLATE, SECTOR_MEDIAN, MARKET_MEDIAN, MISSING |
| confidence_level | NUMERIC | 0.0-1.0 (1.0 = RAW, 0.5-0.9 = imputed) |
| data_quality_flags | JSONB | Quality metadata |
| created_at | TIMESTAMP | Auto-populated |

**Indexes**: 
- (dataset_id, ticker, metric_name, fiscal_year) UNIQUE
- (dataset_id, ticker, fiscal_year)
- imputation_source
- confidence_level

**Lifecycle**: Immutable once written; one row per (dataset, ticker, metric, FY)

**Imputation Sources** (7-step cascade):
1. **RAW**: Value present in raw_data
2. **FORWARD_FILL**: Last non-null value carried forward
3. **BACKWARD_FILL**: Next non-null value carried backward for early gaps
4. **INTERPOLATE**: Linear interpolation between anchor years
5. **SECTOR_MEDIAN**: Median of peers in same sector
6. **MARKET_MEDIAN**: Median of all companies
7. **MISSING**: Genuinely unresolvable (no downstream calculation)

**Example Query**:
```sql
SELECT ticker, metric_name, fiscal_year, value, imputation_source
FROM fundamentals
WHERE dataset_id = 'xxx' AND ticker = 'ANZ'
ORDER BY fiscal_year DESC;
```

---

#### **imputation_audit_trail** (Optional)
Detailed audit of imputation decisions (skip if not needed).

| Column | Type | Notes |
|--------|------|-------|
| imputation_audit_id | BIGINT | Primary Key |
| fundamentals_id | BIGINT | FK → fundamentals.fundamentals_id |
| step | INTEGER | Step number in cascade (1-7) |
| source_value | NUMERIC | Value at this step (NULL if no value) |
| method | VARCHAR(255) | Method used (FORWARD_FILL, INTERPOLATE, etc.) |
| confidence_score | NUMERIC | 0.0-1.0 score for this step |
| comparables_used | JSONB | For SECTOR_MEDIAN: which peers used |
| created_at | TIMESTAMP | Auto-populated |

**Lifecycle**: Optional; can be pruned after analysis

---

### Configuration Layer

#### **parameters**
Individual configuration parameters.

| Column | Type | Notes |
|--------|------|-------|
| parameter_id | BIGINT | Primary Key |
| parameter_key | VARCHAR(255) | UNIQUE, e.g., "MIN_CONFIDENCE", "IMPUTATION_STEPS" |
| parameter_value | TEXT | Value (JSON for complex types) |
| data_type | VARCHAR(50) | STRING, INTEGER, NUMERIC, BOOLEAN, JSON |
| description | TEXT | Parameter description |
| created_at | TIMESTAMP | Auto-populated |
| updated_at | TIMESTAMP | Auto-updated by trigger |

**Example Query**:
```sql
SELECT * FROM parameters ORDER BY parameter_key;
```

---

#### **parameter_sets**
Bundles of parameters for different scenarios.

| Column | Type | Notes |
|--------|------|-------|
| parameter_set_id | BIGINT | Primary Key |
| parameter_set_name | VARCHAR(255) | UNIQUE, e.g., "CONSERVATIVE", "AGGRESSIVE" |
| description | TEXT | Scenario description |
| parameters_json | JSONB | Parameters for this set |
| created_at | TIMESTAMP | Auto-populated |
| updated_at | TIMESTAMP | Auto-updated by trigger |

**Example Query**:
```sql
SELECT * FROM parameter_sets;
```

---

### Downstream Layer

#### **metrics_outputs**
Computed metrics derived from fundamentals.

| Column | Type | Notes |
|--------|------|-------|
| metrics_output_id | BIGINT | Primary Key |
| dataset_id | UUID | FK → dataset_versions.dataset_id |
| ticker | VARCHAR(10) | FK → companies.ticker |
| fiscal_year | INTEGER | FY |
| metric_name | VARCHAR(255) | e.g., "ROE", "ROIC", "FCF" |
| metric_value | NUMERIC | Computed value |
| parameter_set_id | BIGINT | FK → parameter_sets.parameter_set_id |
| created_at | TIMESTAMP | Auto-populated |
| updated_at | TIMESTAMP | Auto-updated by trigger |

**Indexes**: (dataset_id, ticker, fiscal_year), parameter_set_id

**Lifecycle**: Recalculated when parameter_sets change

**Example Query**:
```sql
SELECT ticker, fiscal_year, metric_name, metric_value
FROM metrics_outputs
WHERE dataset_id = 'xxx' AND metric_name = 'ROE'
ORDER BY ticker, fiscal_year DESC;
```

---

#### **optimization_outputs**
Portfolio optimization & valuation outputs.

| Column | Type | Notes |
|--------|------|-------|
| optimization_output_id | BIGINT | Primary Key |
| dataset_id | UUID | FK → dataset_versions.dataset_id |
| optimization_scenario | VARCHAR(255) | e.g., "Max Sharpe Ratio", "Min Variance" |
| ticker | VARCHAR(10) | FK → companies.ticker |
| allocation_weight | NUMERIC | Portfolio weight (0.0-1.0) |
| expected_return | NUMERIC | Projected return % |
| volatility | NUMERIC | Risk estimate |
| valuation_multiple | NUMERIC | e.g., P/E, EV/EBITDA |
| parameter_set_id | BIGINT | FK → parameter_sets.parameter_set_id |
| created_at | TIMESTAMP | Auto-populated |
| updated_at | TIMESTAMP | Auto-updated by trigger |

**Indexes**: (dataset_id, optimization_scenario), ticker, parameter_set_id

**Lifecycle**: Regenerated when parameters or fundamentals change

**Example Query**:
```sql
SELECT ticker, allocation_weight, expected_return, volatility
FROM optimization_outputs
WHERE dataset_id = 'xxx' AND optimization_scenario = 'Max Sharpe Ratio'
ORDER BY allocation_weight DESC;
```

---

## Key Design Features

### 1. Single Source of Truth
The **fundamentals** table is the only table downstream analyses should query. All analysis depends on cleaned, validated, imputed data.

### 2. Immutable Raw Data
The **raw_data** table is never updated - only inserted then deleted. This preserves the original data for debugging.

### 3. UUID-Based Versioning
Each Bloomberg upload gets a unique `dataset_id` (UUID). This UUID flows through the entire pipeline:
```
dataset_versions.dataset_id 
  → raw_data.dataset_id 
  → fundamentals.dataset_id 
  → metrics_outputs.dataset_id 
  → optimization_outputs.dataset_id
```

### 4. Status Tracking
`dataset_versions.status` tracks pipeline progress:
```
PENDING → INGESTING → INGESTED → PROCESSING → PROCESSED
```

If any stage fails, status = ERROR and error_message is populated.

### 5. Quality Metadata
`dataset_versions.quality_metadata` (JSONB) stores:
```json
{
  "total_raw_values": 50000,
  "valid_raw_values": 48500,
  "invalid_raw_values": 1500,
  "imputation_attempts": 48500,
  "successful_imputations": 48500,
  "imputation_sources": {
    "RAW": 35000,
    "FORWARD_FILL": 5000,
    "INTERPOLATED": 4000,
    "SECTOR_MEDIAN": 3000,
    "MARKET_MEDIAN": 1000,
    "MISSING": 0
  }
}
```

### 6. Confidence Scoring
Each imputed value has a `confidence_level` (0.0-1.0):
- **1.0** = RAW (no imputation)
- **0.9+** = FORWARD_FILL, BACKWARD_FILL (high confidence)
- **0.8-0.9** = INTERPOLATE (medium-high confidence)
- **0.6-0.8** = SECTOR_MEDIAN (medium confidence)
- **0.5-0.6** = MARKET_MEDIAN (lower confidence)
- **0.0** = MISSING (no value)

### 7. Auto-Updated Timestamps
4 tables auto-update `updated_at` when modified:
- dataset_versions
- parameters
- parameter_sets
- metrics_outputs
- optimization_outputs

---

## Common Queries

### Get latest dataset
```sql
SELECT * FROM dataset_versions 
WHERE status = 'PROCESSED' 
ORDER BY created_at DESC LIMIT 1;
```

### All metrics for a company
```sql
SELECT metric_name, fiscal_year, value, imputation_source
FROM fundamentals
WHERE dataset_id = 'xxx' AND ticker = 'ANZ'
ORDER BY fiscal_year DESC, metric_name;
```

### Imputation distribution
```sql
SELECT imputation_source, COUNT(*) FROM fundamentals
WHERE dataset_id = 'xxx'
GROUP BY imputation_source ORDER BY COUNT(*) DESC;
```

### Low-confidence data
```sql
SELECT ticker, metric_name, fiscal_year, value, confidence_level
FROM fundamentals
WHERE dataset_id = 'xxx' AND confidence_level < 0.7
ORDER BY confidence_level;
```

---

## File Structure

```
backend/database/
├── schema/
│   ├── schema.sql                    # Create all 12 tables & indexes
│   ├── destroy_schema.sql            # Safe cleanup
│   └── README.md                     # THIS FILE
├── etl/
│   ├── config.py                     # DB connection
│   ├── validators.py                 # Numeric validation
│   ├── fy_aligner.py                 # FY alignment
│   ├── imputation_engine.py          # 7-step cascade
│   ├── ingestion.py                  # Stage 1
│   ├── processing.py                 # Stage 2 orchestrator
│   └── __init__.py                   # Package init
├── DEPLOYMENT.md                     # Deployment guide
├── USAGE.md                          # Python usage examples
├── SCHEMA_REFERENCE.md               # Detailed table docs
└── queries.py                        # Sample SQL queries
```

---

## Next Steps

1. **Deploy Schema**: `psql -U postgres -d rozetta -f schema.sql`
2. **Load Reference**: See USAGE.md Pattern 1
3. **Test Pipeline**: See DEPLOYMENT.md steps 1-5
4. **Query Results**: See USAGE.md common patterns
5. **Monitor Quality**: See USAGE.md Pattern 5 (Validation Report)

---

**Last Updated**: 2026-03-03  
**Maintained By**: Data Engineering Team  
**See Also**: IMPLEMENTATION_PLAN.md, DEPLOYMENT.md, USAGE.md, SCHEMA_REFERENCE.md
