# CISSA Deployment Guide

This guide covers the three essential commands for managing the CISSA data pipeline: destroying the schema, initializing it, and ingesting data.

## Prerequisites

- PostgreSQL 13+ running and accessible
- Python 3.10+ installed
- CISSA repository cloned with dependencies installed (`pip install -r requirements.txt`)
- Environment variables configured (see `backend/database/README.md`)

---

## Command 1: Destroy Schema (Reset Database)

**Purpose:** Completely remove all tables, triggers, and indexes from the CISSA schema. Use this when you need a clean slate or want to remove all data.

### Command

```bash
python backend/database/schema/schema_manager.py destroy --confirm
```

### What It Does

1. Drops all tables in the `cissa` schema (with CASCADE to remove dependencies)
2. Removes all indexes and triggers
3. Removes all stored functions
4. Removes the schema itself (if empty)
5. Does NOT delete the PostgreSQL database or other schemas

### Expected Output

```
Connecting to database...
Connected!

Destroying CISSA schema...
Schema destroyed successfully.
```

### Duration

- Typically 1-5 seconds
- Longer if the database is very large (>1GB of data)

### Troubleshooting

**Issue: "Connection refused"**
- Check that PostgreSQL is running
- Verify DATABASE_URL environment variable is set correctly
- See `backend/database/README.md` for configuration details

**Issue: "Schema does not exist"**
- This is normal if schema_manager.py destroy has already run
- Proceed with `init` to create a fresh schema

**Issue: "Permission denied"**
- Verify your PostgreSQL user has permission to drop schemas
- May need to run as a superuser or owner of the schema

### When to Use

- **Starting fresh:** Before running a new full ingestion
- **Testing:** To verify schema creation logic
- **Cleanup:** When old data no longer needed
- **Troubleshooting:** If schema becomes corrupted

---

## Command 2: Initialize Schema (Create Schema)

**Purpose:** Create all tables, indexes, triggers, and load baseline parameter data into an empty database.

### Command

```bash
python backend/database/schema/schema_manager.py init
```

### What It Does

1. Executes `/backend/database/schema/schema.sql` which creates:
   - All 10 tables (dataset_versions, raw_data, companies, metric_units, fundamentals, imputation_audit_trail, parameters, parameter_sets, metrics_outputs, optimization_outputs)
   - 25+ indexes for query performance
   - 4 triggers for auto-updating timestamps
   - CHECK constraints for data validation
   - UNIQUE constraints for deduplication

2. Loads 13 baseline parameters (e.g., inflation rate, risk-free rate, etc.)

3. Creates the default `base_case` parameter set

4. Sets up the `cissa` schema from scratch

### Expected Output

```
Connecting to database...
Connected!

Initializing CISSA schema...
Schema initialized successfully.
Created tables, indexes, and triggers.
Loaded baseline parameters.
```

### Duration

- Typically 5-15 seconds
- Includes validation of all constraints and indexes

### Expected Schema State After Init

| Component | Count | Status |
|-----------|-------|--------|
| Tables | 10 | Created ✓ |
| Indexes | 25+ | Created ✓ |
| Triggers | 4 | Active ✓ |
| Parameters | 13 | Loaded ✓ |
| Parameter Sets | 1 | Created (base_case) ✓ |
| Data Rows | 0 | Empty (ready for ingestion) ✓ |

### Verification Query

After running `init`, verify the schema was created correctly:

```sql
-- Check that all tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'cissa' 
ORDER BY table_name;

-- Should return: dataset_versions, raw_data, companies, metric_units, 
-- fundamentals, imputation_audit_trail, parameters, parameter_sets, 
-- metrics_outputs, optimization_outputs

-- Check baseline parameters were loaded
SELECT COUNT(*) FROM cissa.parameters;
-- Should return: 13

-- Check default parameter set was created
SELECT * FROM cissa.parameter_sets WHERE set_name = 'base_case';
-- Should return 1 row
```

### Troubleshooting

**Issue: "Schema already exists"**
- Run Command 1 (destroy) first to remove existing schema
- Then run `init` again

**Issue: "Syntax error in schema.sql"**
- Verify `/backend/database/schema/schema.sql` is not corrupted
- Ensure PostgreSQL version is 13 or higher (some SQL features may not be available in earlier versions)

**Issue: "Permission denied creating schema"**
- Verify PostgreSQL user has CREATE permission on the database
- May need to run as superuser or database owner

### When to Use

- **Fresh deployment:** First time setting up CISSA
- **After destroy:** Always run `init` after `destroy` to prepare for new data
- **Testing:** To reset to a known good state
- **CI/CD pipelines:** Standard initialization step before data loading

---

## Command 3: Ingest Data (Load and Process)

**Purpose:** Load raw data from an Excel file, validate it, detect duplicates, and run the complete 3-stage pipeline to produce cleaned, imputed, and aligned facts.

### Command

```bash
python backend/database/etl/pipeline.py --input "input-data/ASX/raw-data/Bloomberg Download data.xlsx" --mode full
```

### Command Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--input` | Yes | Path to the input Excel file (absolute or relative to project root) |
| `--mode` | No | Execution mode: `full` (default) or `validate` |

### What It Does

The `pipeline.py` orchestrates a complete 3-stage ETL process:

#### Stage 1: Ingestion & Deduplication
- Reads the Excel file
- Extracts ticker, metric_name, period, and value columns
- Validates all values are numeric (rejects 485 invalid values)
- **Detects duplicates:** Uses UNIQUE constraint to keep only first (ticker, metric, period)
- Logs duplicates to `imputation_audit_trail` with metadata
- Inserts ~273,858 unique rows into `raw_data`
- Creates entry in `dataset_versions` with metadata (counts, reconciliation)
- **Output:** `raw_data` table populated, duplicates logged

#### Stage 2: Data Processing
- Loads data from `raw_data`
- Converts to wide format (one metric column per row)
- Identifies FISCAL vs MONTHLY periods based on regex patterns
- Maps metrics to companies via lookup
- Creates audit trail entries for any parsing issues
- **Output:** Intermediate processed format, ready for imputation

#### Stage 3: Imputation & FY Alignment
- Identifies gaps in data (missing years, missing metrics)
- Applies imputation strategies:
  - Forward fill for recent data
  - Backward fill for early data
  - Interpolation for middle gaps
  - Sector/market median for large gaps
- Aligns all data to fiscal years
- Creates `fundamentals` table with:
  - No NULL values in `value` column
  - FISCAL records (fiscal_month/day = NULL)
  - MONTHLY records (all components populated)
- Creates audit trail entries for all imputations
- **Output:** `fundamentals` table with ~273,858 clean, imputed rows

### Expected Output

```
Loading data pipeline...
[Stage 1] Ingestion & Deduplication
  Connecting to database...
  Loading Excel file: input-data/ASX/raw-data/Bloomberg Download data.xlsx
  Total rows in file: 275,343
  Valid rows: 274,858 (rejected 485 invalid values)
  Duplicate combinations found: ~1,000
  Unique rows inserted to raw_data: 273,858
  Duration: 120 seconds

[Stage 2] Data Processing
  Loading from raw_data...
  Converting to wide format...
  Identifying FISCAL vs MONTHLY periods...
  Duration: 45 seconds

[Stage 3] Imputation & FY Alignment
  Processing 273,858 rows...
  Forward fills: 234
  Backward fills: 156
  Interpolations: 89
  Sector median: 42
  Market median: 18
  Final fundamentals rows: 273,858
  Audit trail entries: ~500
  Duration: 78 seconds

Total pipeline duration: ~243 seconds (4 minutes)
Pipeline completed successfully!
Ingested dataset version: v1
```

### Duration

Typical end-to-end runtime:
- **Stage 1 (Ingestion):** 120-180 seconds
- **Stage 2 (Processing):** 30-60 seconds
- **Stage 3 (Imputation):** 60-120 seconds
- **Total:** 210-360 seconds (3.5-6 minutes)

Duration depends on:
- File size (275K rows is standard)
- CPU/memory available
- Database performance
- Complexity of imputation needed

### Expected Data State After Ingestion

```sql
-- Verify ingestion completed
SELECT COUNT(*) FROM cissa.raw_data;           -- 273,858
SELECT COUNT(*) FROM cissa.fundamentals;       -- 273,858
SELECT COUNT(*) FROM cissa.companies;          -- ~500
SELECT COUNT(*) FROM cissa.metric_units;       -- 20

-- Verify duplicates were logged
SELECT COUNT(*) FROM cissa.imputation_audit_trail 
WHERE imputation_step = 'DATA_QUALITY_DUPLICATE';  -- ~1,000

-- Verify no NULL values in fundamentals
SELECT COUNT(*) FROM cissa.fundamentals WHERE value IS NULL;  -- 0

-- Verify dataset was versioned
SELECT dataset_name, version_number, status FROM cissa.dataset_versions 
ORDER BY processed_at DESC LIMIT 1;
```

### Verification Queries

After successful ingestion, run these queries to confirm data quality:

```sql
-- 1. Check period types are balanced
SELECT period_type, COUNT(*) as count
FROM cissa.fundamentals
GROUP BY period_type;
-- Expected: ~140K FISCAL, ~133K MONTHLY

-- 2. Verify no FISCAL records have month/day populated
SELECT COUNT(*) as fiscal_with_month_day
FROM cissa.fundamentals
WHERE period_type = 'FISCAL' AND (fiscal_month IS NOT NULL OR fiscal_day IS NOT NULL);
-- Expected: 0

-- 3. Verify all MONTHLY records have month/day
SELECT COUNT(*) as monthly_missing_components
FROM cissa.fundamentals
WHERE period_type = 'MONTHLY' AND (fiscal_month IS NULL OR fiscal_day IS NULL);
-- Expected: 0

-- 4. Verify ASX200 companies are marked
SELECT COUNT(DISTINCT ticker) as asx200_count
FROM cissa.companies
WHERE parent_index = 'ASX200';
-- Expected: 200
```

### Troubleshooting

**Issue: "File not found"**
```bash
# Verify file exists at specified path
ls -la "input-data/ASX/raw-data/Bloomberg Download data.xlsx"

# Use absolute path if relative path doesn't work
python backend/database/etl/pipeline.py --input "/home/ubuntu/cissa/input-data/ASX/raw-data/Bloomberg Download data.xlsx" --mode full
```

**Issue: "Connection refused"**
- Verify PostgreSQL is running
- Check DATABASE_URL is set correctly
- See `backend/database/README.md` for configuration

**Issue: "Stage 1 fails with duplicate key violation"**
- Normal if running twice on same dataset_id
- Run Command 1 (destroy) then Command 2 (init) to reset
- Then run Command 3 (ingest) again

**Issue: "Memory error during Stage 3 (Imputation)"**
- Reduce batch size or available memory
- May indicate insufficient system RAM
- Check available memory: `free -h`

**Issue: Pipeline runs but fundamentals table is empty**
- Verify raw_data has rows: `SELECT COUNT(*) FROM cissa.raw_data;`
- Check Stage 1 output for errors
- Verify metric_name and ticker columns exist in input file

### When to Use

- **Fresh data load:** After running `init` to load new data
- **Regular updates:** When new data becomes available
- **Testing ingestion:** To verify pipeline logic
- **Data refresh:** To replace old data with new version

### Monitoring Long-Running Ingestion

For large datasets or slow systems, monitor progress with:

```bash
# In another terminal, check row counts during ingestion
watch -n 5 'psql -c "SELECT COUNT(*) as raw_data_rows FROM cissa.raw_data; SELECT COUNT(*) as fundamentals_rows FROM cissa.fundamentals;"'

# Or check dataset_versions for current ingestion
psql -c "SELECT dataset_name, status, processed_at FROM cissa.dataset_versions ORDER BY processed_at DESC LIMIT 1;"
```

---

## Complete Workflow Example

Here's a typical deployment sequence:

```bash
# 1. Clean up old data
python backend/database/schema/schema_manager.py destroy --confirm

# 2. Initialize fresh schema
python backend/database/schema/schema_manager.py init

# 3. Ingest new data
python backend/database/etl/pipeline.py --input "input-data/ASX/raw-data/Bloomberg Download data.xlsx" --mode full

# 4. Verify success
psql << EOF
SELECT COUNT(*) as fundamentals_count FROM cissa.fundamentals;
SELECT COUNT(*) as duplicates_found FROM cissa.imputation_audit_trail 
WHERE imputation_step = 'DATA_QUALITY_DUPLICATE';
EOF
```

Expected total time: ~10-12 minutes
- Destroy: 1-2 seconds
- Init: 5-15 seconds
- Ingest: 3-6 minutes
- Verification: 10-30 seconds

---

## Common Deployment Scenarios

### Scenario 1: Fresh Deployment (First Time)

```bash
# Prerequisites: DB running, code cloned, dependencies installed

python backend/database/schema/schema_manager.py init
python backend/database/etl/pipeline.py --input "input-data/ASX/raw-data/Bloomberg Download data.xlsx" --mode full

# Verify
psql -c "SELECT COUNT(*) FROM cissa.fundamentals;"
```

### Scenario 2: Reload Data (Keep Schema Structure)

```bash
# If schema exists but data is stale, just reload

# Option A: Keep all old data (add new version)
python backend/database/etl/pipeline.py --input "input-data/ASX/raw-data/Bloomberg Download data.xlsx" --mode full

# Option B: Clear and reload (recommended for fresh data)
python backend/database/schema/schema_manager.py destroy --confirm
python backend/database/schema/schema_manager.py init
python backend/database/etl/pipeline.py --input "input-data/ASX/raw-data/Bloomberg Download data.xlsx" --mode full
```

### Scenario 3: Production Deployment

```bash
# With error handling and logging

set -e  # Exit on error

echo "Starting CISSA deployment at $(date)"

echo "Step 1: Destroy old schema..."
python backend/database/schema/schema_manager.py destroy --confirm || true

echo "Step 2: Initialize fresh schema..."
python backend/database/schema/schema_manager.py init

echo "Step 3: Ingest data..."
python backend/database/etl/pipeline.py \
    --input "input-data/ASX/raw-data/Bloomberg Download data.xlsx" \
    --mode full

echo "Step 4: Verify deployment..."
psql << EOF
SELECT 
    (SELECT COUNT(*) FROM cissa.fundamentals) as fundamentals_count,
    (SELECT COUNT(*) FROM cissa.raw_data) as raw_data_count,
    (SELECT COUNT(*) FROM cissa.companies) as companies_count;
EOF

echo "Deployment completed successfully at $(date)"
```

---

## Status Checking

To check the current state of your deployment:

```bash
# List all datasets and their status
psql -c "
SELECT dataset_name, version_number, status, processed_at
FROM cissa.dataset_versions
ORDER BY processed_at DESC
LIMIT 10;"

# Count all data
psql -c "
SELECT 
    'dataset_versions' as table_name, COUNT(*) as rows FROM cissa.dataset_versions
UNION ALL
SELECT 'raw_data', COUNT(*) FROM cissa.raw_data
UNION ALL
SELECT 'companies', COUNT(*) FROM cissa.companies
UNION ALL
SELECT 'metric_units', COUNT(*) FROM cissa.metric_units
UNION ALL
SELECT 'fundamentals', COUNT(*) FROM cissa.fundamentals
UNION ALL
SELECT 'imputation_audit_trail', COUNT(*) FROM cissa.imputation_audit_trail
UNION ALL
SELECT 'parameters', COUNT(*) FROM cissa.parameters
UNION ALL
SELECT 'parameter_sets', COUNT(*) FROM cissa.parameter_sets;"

# Check for data quality issues
psql -c "
SELECT imputation_step, COUNT(*) as count
FROM cissa.imputation_audit_trail
GROUP BY imputation_step
ORDER BY count DESC;"
```

---

## Related Documentation

- **Schema Details:** See `/backend/database/CURRENT_SCHEMA.md`
- **Validation Queries:** See `/VALIDATION_QUERIES.md`
- **Database Configuration:** See `/backend/database/README.md`
- **Code Structure:** See `/README.md`
- **Full SQL Definition:** See `/backend/database/schema/schema.sql`
