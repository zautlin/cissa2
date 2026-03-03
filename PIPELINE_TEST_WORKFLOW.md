# Financial Data Pipeline - Complete Test Workflow

**Last Updated**: 2026-03-03  
**Status**: Ready for Manual Testing  
**Python Environment**: `/home/ubuntu/miniconda3/envs/cissa_env/`

---

## Overview

This document provides step-by-step instructions to manually test the complete financial data pipeline from schema deployment through data processing and verification.

**Prerequisites**: All Python packages installed in `cissa_env` conda environment

---

## Quick Reference: Python Interpreter & PostgreSQL

### Python Interpreter
```bash
PYTHON="/home/ubuntu/miniconda3/envs/cissa_env/bin/python3"
```

### PostgreSQL Credentials Setup

**IMPORTANT**: Set these environment variables once at the start of your testing session:

```bash
export PGPASSWORD='5VbL7dK4jM8sN6cE2fG'
export PGHOST='localhost'
export PGUSER='postgres'
```

After setting these, all `psql` commands will connect without prompting for a password.

**Quick setup command:**
```bash
export PGPASSWORD='5VbL7dK4jM8sN6cE2fG' PGHOST='localhost' PGUSER='postgres'
```

---

## Phase 1: Database Setup

### Step 1.1: Verify Database Connection

Test that the environment variables from `.env` are loaded correctly:

```bash
/home/ubuntu/miniconda3/envs/cissa_env/bin/python3 /home/ubuntu/cissa/backend/database/etl/config.py
```

**Expected Output**:
```
✓ Database connection successful
```

**If connection fails**, check:
- PostgreSQL is running: `pg_isready -h localhost -p 5432`
- Credentials in `/home/ubuntu/datahex-local/.env` are correct
- Database `rozetta` exists (see Step 1.3 if needed)

---

### Step 1.2: Deploy Schema to Database

Create all 12 tables, 30 indexes, and 4 triggers:

```bash
psql -h localhost -U postgres -d rozetta -f /home/ubuntu/cissa/backend/database/schema/schema.sql
```

**Expected Output**:
```
CREATE TABLE
CREATE INDEX
CREATE TRIGGER
... (repeated ~40+ times)
```

**If schema deployment fails**, check:
- PostgreSQL credentials match `.env` file
- Database `rozetta` exists and is empty
- Run `destroy_schema.sql` first if tables already exist (requires manual confirmation)

---

### Step 1.3: Create Database (If Needed)

Only run this if the `rozetta` database doesn't exist:

```bash
psql -h localhost -U postgres -c "CREATE DATABASE rozetta ENCODING 'UTF8';"
```

Then proceed to Step 1.2.

---

### Step 1.4: Verify Schema Deployment

Check that all 12 tables were created:

```bash
psql -h localhost -U postgres -d rozetta -c "
SELECT COUNT(*) as table_count 
FROM information_schema.tables 
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"
```

**Expected Output**:
```
 table_count
-------------
          12
(1 row)
```

---

### Step 1.5: Verify Indexes and Triggers

Check indexes:

```bash
psql -h localhost -U postgres -d rozetta -c "
SELECT COUNT(DISTINCT indexname) as index_count 
FROM pg_indexes 
WHERE schemaname = 'public';"
```

**Expected Output**: ~30 indexes

Check triggers:

```bash
psql -h localhost -U postgres -d rozetta -c "
SELECT COUNT(*) as trigger_count 
FROM information_schema.triggers 
WHERE trigger_schema = 'public';"
```

**Expected Output**: 4 triggers

---

## Phase 2: Load Reference Data

Reference data (companies, metrics, fiscal year mappings) needs to be loaded once. This is static lookup data.

### Step 2.1: Load Reference Tables

```bash
/home/ubuntu/miniconda3/envs/cissa_env/bin/python3 << 'EOF'
from backend.database.etl.ingestion import Ingester
from backend.database.etl.config import engine

print("Loading reference data...")
ingester = Ingester(engine)

ingester.load_reference_tables(
    base_csv="/home/ubuntu/cissa/input-data/ASX/extracted-worksheets/Base.csv",
    fy_dates_csv="/home/ubuntu/cissa/input-data/ASX/extracted-worksheets/FY Dates.csv",
    metrics_csv="/home/ubuntu/cissa/input-data/ASX/consolidated-data/financial_metrics_fact_table.csv"
)

print("✓ Reference data loaded successfully")
EOF
```

**Expected Output**:
```
Loading reference data...
✓ Reference data loaded successfully
```

---

### Step 2.2: Verify Reference Data Loaded

```bash
psql -h localhost -U postgres -d rozetta << 'EOF'
SELECT COUNT(*) as companies FROM companies;
SELECT COUNT(*) as metrics FROM metrics_catalog;
SELECT COUNT(*) as fy_mappings FROM fiscal_year_mapping;
EOF
```

**Expected Output**:
```
 companies
-----------
   ~500
(1 row)

   metrics
-----------
   ~30
(1 row)

 fy_mappings
-----------
   ~6000
(1 row)
```

---

## Phase 3: Full Pipeline Test (Per Dataset)

Each Bloomberg upload creates a new dataset. Follow these steps to process one complete dataset.

### Step 3.1: Create Dataset Version

Create a new dataset version record and capture the UUID:

```bash
/home/ubuntu/miniconda3/envs/cissa_env/bin/python3 << 'EOF'
from backend.database.etl.config import engine
from sqlalchemy import text
from datetime import datetime

dataset_name = f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

with engine.begin() as conn:
    result = conn.execute(text("""
        INSERT INTO dataset_versions (dataset_name, version_number, status)
        VALUES (:name, 1, 'PENDING')
        RETURNING dataset_id
    """), {"name": dataset_name})
    
    dataset_id = result.scalar()
    print(f"Created dataset version:")
    print(f"  Dataset ID: {dataset_id}")
    print(f"  Dataset Name: {dataset_name}")
    print(f"\n⚠️  COPY AND SAVE THIS UUID - YOU'LL NEED IT FOR THE NEXT STEPS")
EOF
```

**Expected Output**:
```
Created dataset version:
  Dataset ID: 550e8400-e29b-41d4-a716-446655440000
  Dataset Name: TEST_20260303_120000

⚠️  COPY AND SAVE THIS UUID - YOU'LL NEED IT FOR THE NEXT STEPS
```

**Save the dataset ID** from the output. You'll need it for the next steps.

---

### Step 3.2: Stage 1 - Ingest Raw Data

Replace `<<DATASET_ID>>` with the UUID from Step 3.1:

```bash
/home/ubuntu/miniconda3/envs/cissa_env/bin/python3 << 'EOF'
from backend.database.etl.ingestion import Ingester
from backend.database.etl.config import engine
import sys

# CHANGE THIS: Replace with your dataset ID from Step 3.1
DATASET_ID = "<<DATASET_ID>>"

if DATASET_ID == "<<DATASET_ID>>":
    print("ERROR: Replace <<DATASET_ID>> with the actual UUID from Step 3.1")
    sys.exit(1)

print(f"Starting Stage 1 ingestion for dataset: {DATASET_ID}")
print("This will take ~1-2 minutes with sample data (~275K rows)...")

ingester = Ingester(engine)
result = ingester.load_dataset(
    dataset_id=DATASET_ID,
    csv_path="/home/ubuntu/cissa/input-data/ASX/consolidated-data/financial_metrics_fact_table.csv",
    base_csv_path="/home/ubuntu/cissa/input-data/ASX/extracted-worksheets/Base.csv",
    fy_dates_csv_path="/home/ubuntu/cissa/input-data/ASX/extracted-worksheets/FY Dates.csv"
)

print("\n✓ Stage 1 Ingestion Complete")
print(f"  Total rows: {result['total_rows']:,}")
print(f"  Valid rows: {result['valid_rows']:,}")
print(f"  Invalid rows: {result['invalid_rows']:,}")
print(f"  Valid %: {100.0 * result['valid_rows'] / result['total_rows']:.1f}%")
EOF
```

**Expected Output**:
```
Starting Stage 1 ingestion for dataset: 550e8400-e29b-41d4-a716-446655440000
This will take ~1-2 minutes with sample data (~275K rows)...

✓ Stage 1 Ingestion Complete
  Total rows: 275,344
  Valid rows: 274,500
  Invalid rows: 844
  Valid %: 99.7%
```

---

### Step 3.3: Verify Raw Data Loaded

```bash
psql -h localhost -U postgres -d rozetta -c "
SELECT COUNT(*) as raw_data_rows FROM raw_data;"
```

**Expected Output**: ~275,000 rows

---

### Step 3.4: Stage 2 - Process (FY Align + Impute)

Replace `<<DATASET_ID>>` with the UUID from Step 3.1:

```bash
/home/ubuntu/miniconda3/envs/cissa_env/bin/python3 << 'EOF'
from backend.database.etl.processing import DataQualityProcessor
from backend.database.etl.config import engine
import sys

# CHANGE THIS: Replace with your dataset ID from Step 3.1
DATASET_ID = "<<DATASET_ID>>"

if DATASET_ID == "<<DATASET_ID>>":
    print("ERROR: Replace <<DATASET_ID>> with the actual UUID from Step 3.1")
    sys.exit(1)

print(f"Starting Stage 2 processing for dataset: {DATASET_ID}")
print("FY aligning and running 7-step imputation cascade...")
print("This will take ~2-3 minutes...")

processor = DataQualityProcessor(engine)
result = processor.process_dataset(dataset_id=DATASET_ID)

print("\n✓ Stage 2 Processing Complete")
print(f"  Fundamentals rows: {result['fundamentals_rows']:,}")
print(f"  Pipeline status: {result['status']}")

print("\nImputation source distribution:")
for source in ['RAW', 'FORWARD_FILL', 'BACKWARD_FILL', 'INTERPOLATE', 'SECTOR_MEDIAN', 'MARKET_MEDIAN', 'MISSING']:
    count = result['imputation_sources'].get(source, 0)
    if count > 0:
        pct = 100.0 * count / result['fundamentals_rows']
        print(f"  {source:<20} {count:>8,} ({pct:>5.1f}%)")
EOF
```

**Expected Output**:
```
Starting Stage 2 processing for dataset: 550e8400-e29b-41d4-a716-446655440000
FY aligning and running 7-step imputation cascade...
This will take ~2-3 minutes...

✓ Stage 2 Processing Complete
  Fundamentals rows: 268,500
  Pipeline status: PROCESSED

Imputation source distribution:
  RAW                      189,200 ( 70.4%)
  FORWARD_FILL              42,300 ( 15.8%)
  INTERPOLATE               21,500 (  8.0%)
  SECTOR_MEDIAN              12,800 (  4.8%)
  MARKET_MEDIAN               2,700 (  1.0%)
  MISSING                        0 (  0.0%)
```

---

## Phase 4: Data Quality Verification

### Step 4.1: Check Imputation Distribution

```bash
psql -h localhost -U postgres -d rozetta << 'EOF'
SELECT 
    imputation_source,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
FROM fundamentals
GROUP BY imputation_source
ORDER BY count DESC;
EOF
```

**Expected Output**:
```
imputation_source | count  | percentage
------------------+--------+----------
RAW               | 189200 |      70.40
FORWARD_FILL      |  42300 |      15.80
INTERPOLATE       |  21500 |       8.00
SECTOR_MEDIAN     |  12800 |       4.80
MARKET_MEDIAN     |   2700 |       1.00
(5 rows)
```

---

### Step 4.2: Check Confidence Levels

```bash
psql -h localhost -U postgres -d rozetta << 'EOF'
SELECT 
    COUNT(*) as total_rows,
    ROUND(AVG(confidence_level), 3) as avg_confidence,
    MIN(confidence_level) as min_confidence,
    MAX(confidence_level) as max_confidence,
    COUNT(CASE WHEN confidence_level >= 0.9 THEN 1 END) as high_confidence,
    COUNT(CASE WHEN confidence_level < 0.9 AND confidence_level >= 0.7 THEN 1 END) as medium_confidence,
    COUNT(CASE WHEN confidence_level < 0.7 THEN 1 END) as low_confidence
FROM fundamentals;
EOF
```

**Expected Output**:
```
total_rows | avg_confidence | min_confidence | max_confidence | high_confidence | medium_confidence | low_confidence
-----------+----------------+----------------+----------------+-----------------+-------------------+----------------
    268500 |          0.854 |            0.5 |            1.0 |          210000 |             58000 |            500
(1 row)
```

---

### Step 4.3: Spot Check Sample Data

```bash
psql -h localhost -U postgres -d rozetta << 'EOF'
SELECT 
    ticker,
    metric_name,
    fiscal_year,
    value,
    imputation_source,
    confidence_level
FROM fundamentals
LIMIT 20;
EOF
```

**Expected Output**: 20 rows of cleaned financial data with proper values

---

### Step 4.4: Check Dataset Version Status

```bash
psql -h localhost -U postgres -d rozetta << 'EOF'
SELECT 
    dataset_id,
    dataset_name,
    status,
    version_number,
    created_at,
    updated_at
FROM dataset_versions
ORDER BY created_at DESC
LIMIT 1;
EOF
```

**Expected Output**:
```
dataset_id           | dataset_name        | status    | version_number | created_at          | updated_at
---------------------+---------------------+-----------+----------------+---------------------+---------------------
550e8400-e29b-41d... | TEST_20260303_1... | PROCESSED |              1 | 2026-03-03 12:00:00 | 2026-03-03 12:05:00
(1 row)
```

---

### Step 4.5: Check Quality Metadata

```bash
psql -h localhost -U postgres -d rozetta << 'EOF'
SELECT 
    dataset_id,
    quality_metadata
FROM dataset_versions
ORDER BY created_at DESC
LIMIT 1;
EOF
```

**Expected Output**:
```
dataset_id           | quality_metadata
---------------------+--------------------------------------------------
550e8400-e29b-41d... | {"total_raw_values": 275344, "valid_raw_values": 
                     | 274500, "imputation_attempts": 274500, 
                     | "successful_imputations": 268500, ...}
```

---

## Phase 5: Data Analysis Queries

Use these queries to explore the cleaned data:

### Query 5.1: Companies with Most Data

```bash
psql -h localhost -U postgres -d rozetta << 'EOF'
SELECT 
    ticker,
    COUNT(DISTINCT metric_name) as metrics,
    COUNT(DISTINCT fiscal_year) as fiscal_years,
    COUNT(*) as total_data_points,
    ROUND(AVG(confidence_level), 3) as avg_confidence
FROM fundamentals
GROUP BY ticker
ORDER BY total_data_points DESC
LIMIT 10;
EOF
```

---

### Query 5.2: Metrics with Most Data

```bash
psql -h localhost -U postgres -d rozetta << 'EOF'
SELECT 
    metric_name,
    COUNT(DISTINCT ticker) as companies,
    COUNT(DISTINCT fiscal_year) as fiscal_years,
    COUNT(*) as total_data_points,
    ROUND(AVG(confidence_level), 3) as avg_confidence
FROM fundamentals
GROUP BY metric_name
ORDER BY total_data_points DESC
LIMIT 10;
EOF
```

---

### Query 5.3: Time Series for One Company

Replace `ANZ` with any ticker:

```bash
psql -h localhost -U postgres -d rozetta << 'EOF'
SELECT 
    fiscal_year,
    metric_name,
    value,
    imputation_source,
    confidence_level
FROM fundamentals
WHERE ticker = 'ANZ AU Equity'
ORDER BY fiscal_year DESC, metric_name
LIMIT 20;
EOF
```

---

### Query 5.4: Sector Summary

```bash
psql -h localhost -U postgres -d rozetta << 'EOF'
SELECT 
    c.sector,
    COUNT(DISTINCT f.ticker) as companies,
    COUNT(DISTINCT f.metric_name) as metrics,
    COUNT(*) as total_data_points,
    ROUND(AVG(f.confidence_level), 3) as avg_confidence
FROM fundamentals f
JOIN companies c ON f.ticker = c.ticker
GROUP BY c.sector
ORDER BY companies DESC
LIMIT 10;
EOF
```

---

## Phase 6: Cleanup (Optional)

### Step 6.1: Reset Database (Destroy All Tables)

**WARNING**: This permanently deletes all data. Only run if you want to start over.

First, uncomment the confirmation line in the destroy script:

```bash
sed -i 's/^-- CONFIRM_DESTRUCTION:/CONFIRM_DESTRUCTION:/' /home/ubuntu/cissa/backend/database/schema/destroy_schema.sql
```

Then destroy:

```bash
psql -h localhost -U postgres -d rozetta -f /home/ubuntu/cissa/backend/database/schema/destroy_schema.sql
```

Then restore the confirmation requirement:

```bash
sed -i 's/^CONFIRM_DESTRUCTION:/-- CONFIRM_DESTRUCTION:/' /home/ubuntu/cissa/backend/database/schema/destroy_schema.sql
```

---

## Troubleshooting

### Issue: Database connection fails

**Solution**: Verify environment variables are loaded:
```bash
/home/ubuntu/miniconda3/envs/cissa_env/bin/python3 << 'EOF'
from pathlib import Path
from dotenv import load_dotenv
import os

env_path = Path("/home/ubuntu/datahex-local/.env")
load_dotenv(env_path)

print(f"POSTGRES_USER: {os.getenv('POSTGRES_USER')}")
print(f"POSTGRES_PASSWORD: {'*' * len(os.getenv('POSTGRES_PASSWORD', ''))}")
print(f"POSTGRES_DB: {os.getenv('POSTGRES_DB')}")
print(f"POSTGRES_PORT: {os.getenv('POSTGRES_PORT')}")
EOF
```

---

### Issue: "Table already exists" error during schema deployment

**Solution**: Drop existing tables first:
```bash
psql -h localhost -U postgres -d rozetta -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

Then redeploy schema.

---

### Issue: Ingestion is slow or times out

**Solution**: Try with smaller dataset first:
```bash
head -1000 /home/ubuntu/cissa/input-data/ASX/consolidated-data/financial_metrics_fact_table.csv > /tmp/small_dataset.csv
# Then modify the ingestion script to use /tmp/small_dataset.csv
```

---

### Issue: Processing fails with "metric not found"

**Solution**: Ensure reference data was loaded in Phase 2. If not, run Step 2.1 again.

---

## Success Criteria

Pipeline is working correctly if:

- ✅ Schema deployed with 12 tables
- ✅ 30 indexes created
- ✅ 4 triggers created
- ✅ Reference data loaded (~500 companies, ~30 metrics)
- ✅ Dataset version created successfully
- ✅ Stage 1: ~275K rows ingested, ~99.7% valid
- ✅ Stage 2: ~268K fundamentals rows created
- ✅ Imputation sources distributed across all 6 steps
- ✅ Average confidence level >= 0.8
- ✅ Dataset status = 'PROCESSED'
- ✅ Quality metadata populated
- ✅ Sample queries return data

---

## Next Steps

1. **Test with your own data**: Replace CSV paths with your Bloomberg data
2. **Automate the pipeline**: Create a cron job or workflow orchestration
3. **Add monitoring**: Set up alerts for failed datasets
4. **Build downstream analysis**: Implement metrics_outputs and optimization_outputs
5. **Set up API layer**: Create FastAPI endpoints for data access

---

## Support

For detailed documentation:
- **Deployment guide**: See `backend/database/DEPLOYMENT.md`
- **Usage examples**: See `backend/database/USAGE.md`
- **Schema reference**: See `backend/database/SCHEMA_REFERENCE.md`
- **SQL queries**: See `backend/database/queries.py`

---

**Last Updated**: 2026-03-03  
**Tested with**: Python 3.14, PostgreSQL 18.3, pandas, sqlalchemy, psycopg2-binary
