# Financial Data Pipeline - Complete Implementation Plan

**Status**: In Progress  
**Date**: 2026-03-03  
**Database**: PostgreSQL 16  
**Target Structure**: `backend/database/` with modular organization

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Data Flow & Lifecycle](#data-flow--lifecycle)
4. [Schema Design Details](#schema-design-details)
5. [Directory Structure](#directory-structure)
6. [Refactored DQ Pipeline](#refactored-dq-pipeline)
7. [Deployment Steps](#deployment-steps)
8. [Deliverables](#deliverables)
9. [Usage Examples](#usage-examples)

---

## Executive Summary

### What We're Building

A PostgreSQL-based financial data pipeline that:
1. **Ingests** Bloomberg ASX data (Excel → CSV → validation)
2. **Processes** data (FY alignment + 7-step imputation cascade)
3. **Stores** cleaned fundamentals in a single fact table
4. **Powers** downstream analysis (metrics outputs, optimizations)

### Key Design Principles

- ✅ **Single UUID-based dataset versioning** - one `dataset_id` flows through entire pipeline
- ✅ **Immutable raw data** - raw_data table never updated, only inserted/deleted
- ✅ **Cleaned-only downstream** - metrics_outputs and optimization_outputs depend on `fundamentals` table
- ✅ **7-step imputation cascade** - handles missing data (no plugs/overrides initially)
- ✅ **Full audit trail** - tracks imputation source, quality metrics, validation failures
- ✅ **PostgreSQL 16** - optimized for modern Postgres features

---

## Architecture Overview

### Three-Stage Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│ STAGE 1: EXTRACTION & VALIDATION                                 │
├──────────────────────────────────────────────────────────────────┤
│ Input:  Bloomberg Excel Download data.xlsx                       │
│ Process:                                                          │
│  1. 01_extract_excel_to_csv.py                                   │
│  2. 02_denormalize_metrics.py                                    │
│  3. validator.py (numeric pre-check)                             │
│ Output: raw_data table (with validation_status + rejection_reason)
│ Status:  dataset_versions.status = 'INGESTED'                    │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ STAGE 2: CLEANING & ALIGNMENT (POST-EXTRACTION)                  │
├──────────────────────────────────────────────────────────────────┤
│ Process:                                                          │
│  1. fy_aligner.py - FY alignment (calendar year → fiscal year)   │
│  2. dq_engine.py - 7-step imputation cascade                     │
│     - RAW values                                                  │
│     - FORWARD_FILL (carry last value forward)                    │
│     - BACKWARD_FILL (fill early gaps)                            │
│     - INTERPOLATE (linear between anchors)                       │
│     - SECTOR_MEDIAN (peer median by sector)                      │
│     - MARKET_MEDIAN (all companies median)                       │
│     - MISSING (genuinely unresolvable)                           │
│  3. Write fundamentals table (with imputation_source tracking)   │
│ Output: fundamentals table (cleaned, aligned, imputed)           │
│ Status:  dataset_versions.status = 'PROCESSED'                   │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ STAGE 3: DOWNSTREAM CONSUMPTION                                  │
├──────────────────────────────────────────────────────────────────┤
│ metrics_outputs:                                                  │
│  - Depends on: fundamentals + dataset_id + param_set_id          │
│  - Computes: ROE, ROIC, FCF, etc.                                │
│                                                                   │
│ optimization_outputs:                                            │
│  - Depends on: fundamentals + dataset_id + param_set_id          │
│  - Computes: valuations, portfolio optimization, etc.            │
└──────────────────────────────────────────────────────────────────┘
```

### Database Schema Layers

| Layer | Purpose | Tables |
|-------|---------|--------|
| **Reference** | Immutable lookup data | companies, metrics_catalog, fiscal_year_mapping |
| **Versioning** | Track data lineage | dataset_versions |
| **Raw Data** | Staging area (validation) | raw_data |
| **Cleaned Data** | Final fact table | fundamentals, imputation_audit_trail |
| **Configuration** | Tunable parameters | parameters, parameter_sets |
| **Downstream** | Analysis outputs | metrics_outputs, optimization_outputs |

**Total: 12 tables**

---

## Data Flow & Lifecycle

### Lifecycle of a Dataset

```
1. User uploads new Bloomberg Excel
   ↓
2. Extract & denormalize (existing scripts)
   ├─ 01_extract_excel_to_csv.py → extracted-worksheets/
   ├─ 02_denormalize_metrics.py → consolidated-data/financial_metrics_fact_table.csv
   ↓
3. Create dataset_versions record
   ├─ dataset_id (UUID) generated automatically
   ├─ status = 'PENDING'
   ↓
4. Ingest stage (Stage 1)
   ├─ Load Base.csv → companies table (reference)
   ├─ Load FY Dates.csv → fiscal_year_mapping (reference)
   ├─ Load financial_metrics_fact_table.csv → raw_data table
   ├─ Each value validated (numeric_value extracted, rejection_reason set if invalid)
   ├─ Update dataset_versions.status = 'INGESTED'
   ↓
5. Process stage (Stage 2)
   ├─ FY-align raw data (calendar year → fiscal year)
   ├─ Run 7-step imputation cascade
   ├─ Write fundamentals table (value + imputation_source + confidence_level)
   ├─ Log imputation statistics → dataset_versions.quality_metadata
   ├─ Update dataset_versions.status = 'PROCESSED'
   ↓
6. Ready for downstream (Stage 3)
   ├─ metrics_outputs queries: WHERE dataset_id = ?
   ├─ optimization_outputs queries: WHERE dataset_id = ?
   ├─ All analysis depends on cleaned fundamentals
   ↓
7. Future datasets (v2, v3, ...)
   ├─ Repeat steps 1-6 with version_number incremented
   ├─ Can compare versions (dataset_id_v1 vs dataset_id_v2)
```

### Dataset Status Lifecycle

```
PENDING → INGESTING → INGESTED → PROCESSING → PROCESSED
                          ↓
                        ERROR (at any stage)
```

---

## Schema Design Details

### 12 Tables Overview

#### **Reference Tables (Immutable)**

1. **companies** - Master list from Base.csv
   - Columns: company_id (UUID), ticker (UNIQUE), name, sector, bics_levels, currency
   - Purpose: One-to-many base for all data
   - Lifetime: Forever (never deleted)

2. **metrics_catalog** - All available metrics
   - Columns: metric_id (BIGINT), metric_name (UNIQUE), metric_type (FISCAL/MONTHLY), unit, description
   - Purpose: Defines what metrics exist and their properties
   - Lifetime: Grows over time as new metrics added

3. **fiscal_year_mapping** - FY dates from FY Dates.csv
   - Columns: ticker, fiscal_year, fy_period_date
   - Purpose: Maps (ticker, fiscal_year) → fy_period_date for alignment
   - Lifetime: Static per company (rarely changes)

#### **Versioning & Tracking**

4. **dataset_versions** - Master audit table
   - Columns: dataset_id (UUID PK), dataset_name, version_number, status, timestamps, metadata (JSONB)
   - Purpose: Track each Bloomberg upload, processing stages, quality metrics
   - Lifetime: One row per data load

#### **Raw Data (Staging)**

5. **raw_data** - Immutable raw ingestion
   - Columns: dataset_id, ticker, metric_name, period, period_type, raw_string_value, numeric_value, validation_status, rejection_reason
   - Purpose: Stores validated raw values from Excel
   - Lifetime: Kept for current version, can be deleted after processing
   - Query Pattern: "Show me what was rejected and why"

#### **Cleaned Data (Fact Table)**

6. **fundamentals** - FINAL cleaned, aligned, imputed fact table
   - Columns: dataset_id, ticker, metric_name, fiscal_year, value, imputation_source, confidence_level, data_quality_flags (JSONB)
   - Purpose: The single source of truth for all downstream analysis
   - Lifetime: One row per (dataset, ticker, metric, fiscal_year) - **never changes**
   - Query Pattern: "Get all metrics for company X in FY 2023"
   - Indexes: UNIQUE (dataset_id, ticker, metric_name, fiscal_year), composite (dataset_id, ticker, fiscal_year)

7. **imputation_audit_trail** - Optional detailed audit
   - Columns: dataset_id, ticker, metric_name, fiscal_year, raw_value, imputation_steps_applied, final_value, peer_reference_data (JSONB)
   - Purpose: Detailed lineage of imputation decisions
   - Lifetime: One row per imputed value (optional, skip initially)

#### **Configuration**

8. **parameters** - Tunable parameters
   - Columns: parameter_id, parameter_name (UNIQUE), value_type (NUMERIC/TEXT/BOOLEAN/JSONB), default_value, current_value, unit, constraints
   - Purpose: Define all knobs users can tweak
   - Example: "risk_free_rate", "discount_rate", "inflation_assumption"

9. **parameter_sets** - Named bundles of parameters
   - Columns: param_set_id (UUID), param_set_name (UNIQUE), param_overrides (JSONB), is_default
   - Purpose: Group parameters into scenarios (e.g., "conservative_valuation", "base_case", "bull_case")
   - Example: param_overrides = {"discount_rate": 0.08, "risk_free_rate": 0.04}

#### **Downstream Outputs**

10. **metrics_outputs** - Computed metrics
    - Columns: dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, computation_method, metadata (JSONB)
    - Purpose: Results of metric calculations (ROE, ROIC, FCF, etc.)
    - Uniqueness: (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
    - Purpose: Allows comparing same dataset with different parameter sets

11. **optimization_outputs** - Optimization results
    - Columns: dataset_id, param_set_id, ticker, optimization_type, status, result_summary (JSONB), constraint_details (JSONB), solver_metadata (JSONB)
    - Purpose: Results of optimization algorithms (valuation, portfolio, risk)
    - Status: PENDING → RUNNING → COMPLETED (or ERROR)

#### **Validation & Audit**

12. **raw_data_validation_log** - Validation failures (optional)
    - Columns: dataset_id, ticker, metric_name, period, raw_value, rejection_reason
    - Purpose: Audit trail of values rejected during ingestion
    - Query Pattern: "How many #REF! values did we have?"

---

## Directory Structure

### Current State
```
/home/ubuntu/cissa/
├── input-data/
│   └── ASX/
│       ├── 01_extract_excel_to_csv.py
│       ├── 02_denormalize_metrics.py
│       ├── raw-data/
│       │   └── Bloomberg Download data.xlsx
│       ├── extracted-worksheets/
│       │   ├── Base.csv
│       │   ├── FY Dates.csv
│       │   ├── Revenue.csv
│       │   ├── ... (other metrics)
│       └── consolidated-data/
│           └── financial_metrics_fact_table.csv
├── reference-dq-scripts/
│   ├── dq_engine.py
│   ├── fy_aligner.py
│   └── validator.py
└── README.md
```

### Target State (New Backend Structure)
```
/home/ubuntu/cissa/
├── backend/
│   ├── database/
│   │   ├── schema/
│   │   │   ├── schema.sql                    # Create all 12 tables, indexes, triggers
│   │   │   ├── destroy_schema.sql            # Safe table cleanup (with warnings)
│   │   │   └── README.md                     # Schema overview
│   │   │
│   │   ├── etl/
│   │   │   ├── __init__.py
│   │   │   ├── ingestion.py                  # Stage 1: CSV loading, validation
│   │   │   ├── processing.py                 # Stage 2: FY alignment, imputation
│   │   │   ├── validators.py                 # Numeric validation (from reference-dq-scripts/validator.py)
│   │   │   ├── fy_aligner.py                 # FY alignment (refactored)
│   │   │   └── imputation_engine.py          # 7-step cascade (refactored from dq_engine.py)
│   │   │
│   │   ├── config.py                         # DB connection, environment vars
│   │   ├── models.py                         # SQLAlchemy ORM models (optional, for type hints)
│   │   ├── queries.py                        # Sample queries for common patterns
│   │   │
│   │   ├── DEPLOYMENT.md                     # Step-by-step deployment guide
│   │   ├── SCHEMA_REFERENCE.md               # Comprehensive table documentation
│   │   └── USAGE.md                          # How to use the ETL pipeline
│   │
│   └── api/
│       └── (future API endpoints here)
│
├── input-data/
│   └── ASX/
│       ├── 01_extract_excel_to_csv.py        # (unchanged)
│       ├── 02_denormalize_metrics.py         # (unchanged)
│       └── ... (data files)
│
└── README.md
```

### Key Changes

**Old**: `reference-dq-scripts/` → **New**: `backend/database/etl/`

| Old | New | Refactoring |
|-----|-----|-------------|
| `dq_engine.py` | `imputation_engine.py` | Extract 7-step cascade into reusable `class ImputationCascade` |
| `fy_aligner.py` | `fy_aligner.py` | Refactor into `class FYAligner` with clean API |
| `validator.py` | `validators.py` | Extract `validate_numeric()` into utilities |
| (new) | `ingestion.py` | New: load_raw_data(), load_reference_tables() |
| (new) | `processing.py` | New: orchestrate Stage 2 (FY align + impute) |

---

## Refactored DQ Pipeline

### Naming Convention

**Modules** (Python files):
- `ingestion.py` - Stage 1 (CSV loading, validation)
- `processing.py` - Stage 2 orchestrator (FY align + impute)
- `validators.py` - Utility functions (numeric validation, checks)
- `fy_aligner.py` - FY alignment logic
- `imputation_engine.py` - 7-step imputation cascade

**Classes** (in each module):
- `Ingester` - Handles raw data loading
- `DataQualityProcessor` - Orchestrates Stage 2 (FY align + impute)
- `FYAligner` - Maps calendar years to fiscal years
- `ImputationCascade` - Executes 7-step imputation

**Functions** (utilities):
- `validate_numeric(raw_value: str) → (float, bool, str)` - Pre-check if numeric
- `run_ingestion(dataset_id, csv_path, db_engine) → dict` - Load raw data
- `run_processing(dataset_id, db_engine) → dict` - FY align + impute

### API Design

```python
# --- STAGE 1: INGESTION ---
from backend.database.etl.ingestion import Ingester

ingester = Ingester(db_engine)
result = ingester.load_dataset(
    dataset_id="550e8400-e29b-41d4-a716-446655440000",
    csv_path="input-data/ASX/consolidated-data/financial_metrics_fact_table.csv",
    base_csv_path="input-data/ASX/extracted-worksheets/Base.csv",
    fy_dates_csv_path="input-data/ASX/extracted-worksheets/FY Dates.csv"
)
print(result)
# Output: {
#   "status": "INGESTED",
#   "total_rows": 50000,
#   "rejected_rows": 120,
#   "validation_summary": {"non_numeric_markers": 100, "parse_errors": 20}
# }

# --- STAGE 2: PROCESSING (FY ALIGN + IMPUTE) ---
from backend.database.etl.processing import DataQualityProcessor

processor = DataQualityProcessor(db_engine)
result = processor.process_dataset(dataset_id="550e8400-e29b-41d4-a716-446655440000")
print(result)
# Output: {
#   "status": "PROCESSED",
#   "fundamentals_rows": 45000,
#   "imputation_stats": {
#       "raw": 40000,
#       "forward_fill": 2000,
#       "backward_fill": 1500,
#       "interpolated": 800,
#       "sector_median": 500,
#       "market_median": 200,
#       "missing": 0
#   },
#   "fill_rate": 0.996
# }

# --- UTILITIES ---
from backend.database.etl.validators import validate_numeric

numeric_val, is_valid, reason = validate_numeric("1,234.56")
# Output: (1234.56, True, None)

numeric_val, is_valid, reason = validate_numeric("#REF!")
# Output: (None, False, "non-numeric marker: '#REF!'")
```

---

## Deployment Steps

### Prerequisites

- PostgreSQL 16+ (or 14+)
- Python 3.8+
- pandas, sqlalchemy, psycopg2
- CSV files in `input-data/ASX/`

### Step-by-Step Deployment

```
1. CREATE SCHEMA (one-time)
   Command: psql -U postgres -d rozetta -f backend/database/schema/schema.sql
   Expected: 12 tables created, 25+ indexes created
   Verify: 
     SELECT COUNT(*) FROM information_schema.tables 
     WHERE table_schema = 'public' AND table_name LIKE '%dataset%';
   
2. LOAD REFERENCE DATA (one-time per source)
   Python:
     from backend.database.etl.ingestion import Ingester
     ingester = Ingester(db_engine)
     ingester.load_reference_tables(
       base_csv="input-data/ASX/extracted-worksheets/Base.csv",
       fy_dates_csv="input-data/ASX/extracted-worksheets/FY Dates.csv",
       metrics_csv="input-data/ASX/consolidated-data/financial_metrics_fact_table.csv"
     )
   Expected: ~20-30 companies, ~20-30 metrics, ~300+ FY mappings
   
3. CREATE DATASET VERSION (per upload)
   SQL:
     INSERT INTO dataset_versions (dataset_name, version_number, status)
     VALUES ('ASX_Q4_2024', 1, 'PENDING')
     RETURNING dataset_id;
   Output: dataset_id (copy this UUID)
   
4. STAGE 1: INGEST RAW DATA
   Python:
     ingester = Ingester(db_engine)
     result = ingester.load_dataset(
       dataset_id="xxx-xxx-xxx-xxx",
       csv_path="input-data/ASX/consolidated-data/financial_metrics_fact_table.csv",
       base_csv_path="input-data/ASX/extracted-worksheets/Base.csv",
       fy_dates_csv_path="input-data/ASX/extracted-worksheets/FY Dates.csv"
     )
     print(result)
   Expected: ~50,000 raw_data rows, validation_status tracked
   Update: dataset_versions.status = 'INGESTED'
   
5. STAGE 2: PROCESS (FY ALIGN + IMPUTE)
   Python:
     processor = DataQualityProcessor(db_engine)
     result = processor.process_dataset(dataset_id="xxx-xxx-xxx-xxx")
     print(result)
   Expected: ~45,000 fundamentals rows with imputation_source tracked
   Update: dataset_versions.status = 'PROCESSED'
   
6. VERIFY OUTPUT
   SQL:
     SELECT imputation_source, COUNT(*) 
     FROM fundamentals 
     WHERE dataset_id = 'xxx'
     GROUP BY imputation_source;
   Expected: Mix of RAW, FORWARD_FILL, INTERPOLATED, etc.
   
7. READY FOR DOWNSTREAM
   - metrics_outputs can now compute from fundamentals
   - optimization_outputs can now run analyses
```

### Quick Reset (Debugging)

```
1. Destroy all tables:
   psql -U postgres -d rozetta -f backend/database/schema/destroy_schema.sql
   
2. Recreate all tables:
   psql -U postgres -d rozetta -f backend/database/schema/schema.sql
   
3. Restart pipeline at Step 2 (Load Reference Data)
```

---

## Deliverables

### Phase 1: Documentation (THIS FILE)
- ✅ IMPLEMENTATION_PLAN.md (this file)

### Phase 2: Database Schema
- `backend/database/schema/schema.sql` - Create 12 tables, indexes, triggers (~600 lines)
- `backend/database/schema/destroy_schema.sql` - Safe cleanup (~100 lines)
- `backend/database/schema/README.md` - Schema overview

### Phase 3: Refactored ETL Pipeline
- `backend/database/etl/__init__.py` - Package initialization
- `backend/database/etl/ingestion.py` - Stage 1: CSV loading + validation (~300 lines)
- `backend/database/etl/processing.py` - Stage 2 orchestrator (~200 lines)
- `backend/database/etl/validators.py` - Numeric validation utilities (~100 lines)
- `backend/database/etl/fy_aligner.py` - FY alignment logic (~150 lines, refactored)
- `backend/database/etl/imputation_engine.py` - 7-step cascade (~400 lines, refactored)
- `backend/database/etl/config.py` - Database connection config (~50 lines)

### Phase 4: Documentation & Examples
- `backend/database/DEPLOYMENT.md` - Step-by-step deployment (~300 lines)
- `backend/database/SCHEMA_REFERENCE.md` - Comprehensive table docs (~800 lines)
- `backend/database/USAGE.md` - How to use the ETL pipeline (~200 lines)
- `backend/database/queries.py` - Sample queries for common patterns (~100 lines)

### Phase 5: Cleanup
- Remove or archive `reference-dq-scripts/` (old code now refactored into etl/)

---

## Usage Examples

### Example 1: Load a New Bloomberg Dataset

```python
from sqlalchemy import create_engine
from backend.database.etl.ingestion import Ingester
from backend.database.etl.processing import DataQualityProcessor

# Create DB connection
engine = create_engine("postgresql://postgres:changeme@localhost/rozetta")

# Create dataset version
from sqlalchemy import text
with engine.begin() as conn:
    result = conn.execute(text("""
        INSERT INTO dataset_versions (dataset_name, version_number, status)
        VALUES ('ASX_Q4_2024', 1, 'PENDING')
        RETURNING dataset_id
    """))
    dataset_id = result.scalar()

print(f"Created dataset: {dataset_id}")

# Stage 1: Ingest
ingester = Ingester(engine)
ingest_result = ingester.load_dataset(
    dataset_id=dataset_id,
    csv_path="input-data/ASX/consolidated-data/financial_metrics_fact_table.csv",
    base_csv_path="input-data/ASX/extracted-worksheets/Base.csv",
    fy_dates_csv_path="input-data/ASX/extracted-worksheets/FY Dates.csv"
)
print(f"Ingestion result: {ingest_result}")

# Stage 2: Process
processor = DataQualityProcessor(engine)
process_result = processor.process_dataset(dataset_id=dataset_id)
print(f"Processing result: {process_result}")

# All done!
print(f"Dataset {dataset_id} ready for downstream analysis")
```

### Example 2: Query Fundamentals

```python
import pandas as pd
from sqlalchemy import create_engine, text

engine = create_engine("postgresql://postgres:changeme@localhost/rozetta")

# Get all metrics for BHP over time
df = pd.read_sql(text("""
    SELECT fiscal_year, metric_name, value, imputation_source
    FROM fundamentals
    WHERE dataset_id = :dataset_id AND ticker = 'BHP AU Equity'
    ORDER BY fiscal_year, metric_name
"""), engine, params={"dataset_id": "550e8400-e29b-41d4-a716-446655440000"})

print(df)
```

### Example 3: Audit Imputation

```python
# Show what was imputed for a specific metric
df = pd.read_sql(text("""
    SELECT ticker, fiscal_year, value, imputation_source
    FROM fundamentals
    WHERE dataset_id = :dataset_id 
      AND metric_name = 'Cash'
      AND imputation_source != 'RAW'
    ORDER BY ticker, fiscal_year
"""), engine, params={"dataset_id": dataset_id})

print(f"Imputed values for Cash metric:")
print(df)
```

---

## Next Steps

1. ✅ **Review this plan** - Confirm directory structure, naming conventions, API design
2. **Generate schema.sql** - Create all tables, indexes, triggers
3. **Generate destroy_schema.sql** - Safe cleanup script
4. **Refactor ETL scripts** - Organize into backend/database/etl/ with clean API
5. **Generate documentation** - DEPLOYMENT.md, SCHEMA_REFERENCE.md, USAGE.md
6. **Test deployment** - Run through all steps with sample data
7. **Archive old code** - Move reference-dq-scripts/ to archive or delete

---

**Ready to proceed to Phase 2?**
