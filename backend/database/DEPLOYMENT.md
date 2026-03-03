# Financial Data Pipeline - Deployment Guide

**Last Updated**: 2026-03-03  
**Database**: PostgreSQL 16  
**Python Version**: 3.8+

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Database Setup](#database-setup)
3. [Python Environment](#python-environment)
4. [Step-by-Step Deployment](#step-by-step-deployment)
5. [Verification Checklist](#verification-checklist)
6. [Troubleshooting](#troubleshooting)
7. [Quick Reset](#quick-reset)
8. [Production Considerations](#production-considerations)

---

## Prerequisites

Ensure you have the following installed and configured:

### System Requirements
- **PostgreSQL 16+** (check: `psql --version`)
- **Python 3.8+** (check: `python3 --version`)
- **Git** (for cloning/version control)
- **Unix-like shell** (bash/zsh on Linux/Mac; WSL2 on Windows)

### Database Requirements
- PostgreSQL server running and accessible
- Database created: `rozetta` (or your target database name)
- Superuser or admin credentials available
- Port 5432 (or configured port) accessible

### Data Files Required
Located in `input-data/ASX/`:
```
input-data/ASX/
├── extracted-worksheets/
│   ├── Base.csv                          # Company master data
│   ├── FY Dates.csv                      # Fiscal year mappings
│   └── (other metric CSVs)
└── consolidated-data/
    └── financial_metrics_fact_table.csv  # Consolidated metrics
```

---

## Database Setup

### Step 1: Verify PostgreSQL Installation

```bash
# Check PostgreSQL version
psql --version

# Connect to PostgreSQL (default: localhost, port 5432)
psql -U postgres -c "SELECT version();"
```

**Expected output**: PostgreSQL 16.x running

### Step 2: Create Target Database (if not exists)

```bash
# Connect as superuser
psql -U postgres

# Inside psql:
CREATE DATABASE rozetta ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8';
\q
```

### Step 3: Create Database Schema

```bash
# Navigate to project root
cd /home/ubuntu/cissa

# Execute schema creation script
psql -U postgres -d rozetta -f backend/database/schema/schema.sql

# Expected output: 
# CREATE TABLE
# CREATE INDEX
# CREATE TRIGGER
# ... (repeated 30+ times)
```

**Verify schema was created:**
```bash
psql -U postgres -d rozetta -c "
SELECT COUNT(*) as table_count 
FROM information_schema.tables 
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
"
```

**Expected output**: `table_count: 12`

### Step 4: Verify Indexes and Triggers

```bash
# Check indexes
psql -U postgres -d rozetta -c "
SELECT COUNT(*) as index_count 
FROM information_schema.tables t 
JOIN information_schema.statistics s 
  ON t.table_name = s.table_name
WHERE t.table_schema = 'public';
"

# Check triggers
psql -U postgres -d rozetta -c "
SELECT COUNT(*) as trigger_count 
FROM information_schema.triggers 
WHERE trigger_schema = 'public';
"
```

**Expected output**: 
- `index_count`: ~30
- `trigger_count`: 4 (one for each table with `updated_at`)

---

## Python Environment

### Step 1: Create Virtual Environment

```bash
# Navigate to project root
cd /home/ubuntu/cissa

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Verify activation (should show "venv" prefix in prompt)
```

### Step 2: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install required packages
pip install pandas sqlalchemy psycopg2-binary

# Verify installation
python3 -c "import pandas, sqlalchemy, psycopg2; print('All packages installed!')"
```

### Step 3: Configure Database Connection

Create or update `backend/database/etl/config.py`:

```python
import os
from sqlalchemy import create_engine

# Database connection parameters
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")
DB_NAME = os.getenv("DB_NAME", "rozetta")

# PostgreSQL connection URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# Test connection
def test_connection():
    try:
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            print("✓ Database connection successful")
            return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()
```

**Test the connection:**
```bash
python3 backend/database/etl/config.py
```

**Expected output**: `✓ Database connection successful`

---

## Step-by-Step Deployment

### Step 1: Load Reference Data (One-Time)

Reference data includes companies, metrics, and fiscal year mappings. This typically needs to be loaded only once (or when source files change).

```bash
# Activate virtual environment
source venv/bin/activate

# Run Python script to load reference data
python3 << 'EOF'
from backend.database.etl.ingestion import Ingester
from backend.database.etl.config import engine

ingester = Ingester(engine)

# Load reference tables
print("Loading reference data...")
ingester.load_reference_tables(
    base_csv="input-data/ASX/extracted-worksheets/Base.csv",
    fy_dates_csv="input-data/ASX/extracted-worksheets/FY Dates.csv",
    metrics_csv="input-data/ASX/consolidated-data/financial_metrics_fact_table.csv"
)
print("✓ Reference data loaded successfully")

# Verify loaded counts
from sqlalchemy import text
with engine.connect() as conn:
    companies = conn.execute(text("SELECT COUNT(*) FROM companies")).scalar()
    metrics = conn.execute(text("SELECT COUNT(*) FROM metrics_catalog")).scalar()
    fy_mappings = conn.execute(text("SELECT COUNT(*) FROM fiscal_year_mapping")).scalar()
    
    print(f"  Companies: {companies}")
    print(f"  Metrics: {metrics}")
    print(f"  FY Mappings: {fy_mappings}")
EOF
```

**Expected output**:
```
Loading reference data...
✓ Reference data loaded successfully
  Companies: 20-30
  Metrics: 20-30
  FY Mappings: 300+
```

### Step 2: Create Dataset Version

For each Bloomberg data upload, create a new dataset version record:

```bash
python3 << 'EOF'
from backend.database.etl.config import engine
from sqlalchemy import text
from datetime import datetime

dataset_name = f"ASX_Bloomberg_{datetime.now().strftime('%Y%m%d')}"

with engine.begin() as conn:
    result = conn.execute(text("""
        INSERT INTO dataset_versions (dataset_name, version_number, status, created_at)
        VALUES (:name, 1, 'PENDING', NOW())
        RETURNING dataset_id
    """), {"name": dataset_name})
    
    dataset_id = result.scalar()
    print(f"Created dataset version: {dataset_id}")
    print(f"Dataset name: {dataset_name}")
    
    # Store this for subsequent steps
    with open("/tmp/dataset_id.txt", "w") as f:
        f.write(dataset_id)
EOF
```

**Expected output**:
```
Created dataset version: 550e8400-e29b-41d4-a716-446655440000
Dataset name: ASX_Bloomberg_20260303
```

### Step 3: Stage 1 - Ingest Raw Data

Load raw financial data from CSV into `raw_data` table with validation:

```bash
python3 << 'EOF'
from backend.database.etl.ingestion import Ingester
from backend.database.etl.config import engine

# Read dataset_id from previous step
with open("/tmp/dataset_id.txt", "r") as f:
    dataset_id = f.read().strip()

ingester = Ingester(engine)

print(f"Starting ingestion for dataset: {dataset_id}")
result = ingester.load_dataset(
    dataset_id=dataset_id,
    csv_path="input-data/ASX/consolidated-data/financial_metrics_fact_table.csv",
    base_csv_path="input-data/ASX/extracted-worksheets/Base.csv",
    fy_dates_csv_path="input-data/ASX/extracted-worksheets/FY Dates.csv"
)

print("✓ Ingestion complete")
print(f"  Total rows ingested: {result.get('total_rows')}")
print(f"  Valid rows: {result.get('valid_rows')}")
print(f"  Invalid rows: {result.get('invalid_rows')}")
print(f"  Dataset status: INGESTED")
EOF
```

**Expected output**:
```
Starting ingestion for dataset: 550e8400-e29b-41d4-a716-446655440000
✓ Ingestion complete
  Total rows ingested: 50000
  Valid rows: 48500
  Invalid rows: 1500
  Dataset status: INGESTED
```

### Step 4: Stage 2 - Process (FY Align + Impute)

Run the 7-step imputation cascade and write cleaned data to `fundamentals` table:

```bash
python3 << 'EOF'
from backend.database.etl.processing import DataQualityProcessor
from backend.database.etl.config import engine

# Read dataset_id from previous step
with open("/tmp/dataset_id.txt", "r") as f:
    dataset_id = f.read().strip()

processor = DataQualityProcessor(engine)

print(f"Starting processing for dataset: {dataset_id}")
print("  - FY aligning data...")
print("  - Running 7-step imputation cascade...")

result = processor.process_dataset(dataset_id=dataset_id)

print("✓ Processing complete")
print(f"  Fundamentals rows: {result.get('fundamentals_rows')}")
print(f"  Imputation sources:")
for source, count in result.get('imputation_sources', {}).items():
    print(f"    {source}: {count}")
print(f"  Dataset status: PROCESSED")
EOF
```

**Expected output**:
```
Starting processing for dataset: 550e8400-e29b-41d4-a716-446655440000
  - FY aligning data...
  - Running 7-step imputation cascade...
✓ Processing complete
  Fundamentals rows: 48000
  Imputation sources:
    RAW: 35000
    FORWARD_FILL: 5000
    INTERPOLATED: 4000
    SECTOR_MEDIAN: 3000
    MARKET_MEDIAN: 1000
    MISSING: 0
  Dataset status: PROCESSED
```

### Step 5: Verify Output

Query the cleaned data to ensure pipeline executed correctly:

```bash
# Connect to database
psql -U postgres -d rozetta << 'EOF'

-- Show imputation source distribution
SELECT imputation_source, COUNT(*) as count 
FROM fundamentals 
GROUP BY imputation_source 
ORDER BY count DESC;

-- Show sample data
SELECT dataset_id, ticker, metric_name, fiscal_year, value, imputation_source
FROM fundamentals
LIMIT 10;

-- Show data by company
SELECT ticker, COUNT(DISTINCT metric_name) as metric_count
FROM fundamentals
GROUP BY ticker
ORDER BY metric_count DESC
LIMIT 10;

-- Show quality summary
SELECT 
    COUNT(*) as total_rows,
    COUNT(DISTINCT ticker) as companies,
    COUNT(DISTINCT metric_name) as metrics,
    COUNT(DISTINCT fiscal_year) as fiscal_years
FROM fundamentals;

EOF
```

**Expected output** (sample):
```
imputation_source | count
------------------+-------
RAW               | 35000
FORWARD_FILL      |  5000
INTERPOLATED      |  4000
SECTOR_MEDIAN     |  3000
MARKET_MEDIAN     |  1000
(5 rows)

 dataset_id              | ticker | metric_name      | fiscal_year | value   | imputation_source
------------------------+--------+------------------+-------------+---------+------------------
 550e8400-...            | ASX    | Revenue          | 2023        | 1000000 | RAW
 550e8400-...            | ASX    | Net Income       | 2023        | 150000  | FORWARD_FILL
 ...
```

---

## Verification Checklist

Before declaring the deployment complete, verify:

- [ ] PostgreSQL 16 is running and accessible
- [ ] Database `rozetta` exists
- [ ] 12 tables created in schema
- [ ] ~30 indexes created
- [ ] 4 triggers created for `updated_at` columns
- [ ] Reference data loaded (companies, metrics, fiscal_year_mapping)
- [ ] At least 1 dataset_version record exists with status 'PROCESSED'
- [ ] `raw_data` table populated with ~50,000 rows
- [ ] `fundamentals` table populated with ~45,000+ rows
- [ ] Imputation sources distributed across all 6 steps
- [ ] No Python import errors when loading ETL modules
- [ ] Database connection test passes

---

## Troubleshooting

### Issue: "psql: command not found"

**Solution**: Install PostgreSQL client tools or add to PATH:
```bash
# macOS with Homebrew
brew install postgresql

# Linux (Ubuntu/Debian)
sudo apt-get install postgresql-client

# Verify installation
which psql
```

### Issue: "FATAL: role 'postgres' does not exist"

**Solution**: Use correct PostgreSQL user:
```bash
# List available users
psql -U <username> -c "\du"

# Connect with correct user
psql -U <correct_username> -d rozetta
```

### Issue: "FATAL: database 'rozetta' does not exist"

**Solution**: Create the database first:
```bash
psql -U postgres -c "CREATE DATABASE rozetta;"
```

### Issue: "could not translate host name 'localhost' to address"

**Solution**: Check PostgreSQL is running and configure host:
```bash
# Start PostgreSQL (varies by OS)
# macOS: brew services start postgresql
# Linux: sudo systemctl start postgresql
# Windows: net start PostgreSQL

# Try connecting with socket
psql -U postgres -h /tmp
```

### Issue: "ModuleNotFoundError: No module named 'sqlalchemy'"

**Solution**: Install Python dependencies:
```bash
source venv/bin/activate
pip install pandas sqlalchemy psycopg2-binary
```

### Issue: "ImportError: libpq.so.5 not found"

**Solution**: Install PostgreSQL development libraries:
```bash
# macOS
brew install libpq

# Linux (Ubuntu/Debian)
sudo apt-get install libpq-dev

# Add to PATH if needed
export LD_LIBRARY_PATH=/usr/local/opt/libpq/lib:$LD_LIBRARY_PATH
```

### Issue: Permission denied running Python scripts

**Solution**: Make scripts executable:
```bash
chmod +x backend/database/etl/*.py
```

---

## Quick Reset

To completely reset the database (WARNING: deletes all data):

```bash
# Step 1: Destroy all tables
psql -U postgres -d rozetta -f backend/database/schema/destroy_schema.sql

# Step 2: Recreate schema
psql -U postgres -d rozetta -f backend/database/schema/schema.sql

# Step 3: Restart deployment from "Step 1: Load Reference Data" above
```

---

## Production Considerations

### Security

- [ ] **Database credentials**: Store in environment variables or secure vaults (AWS Secrets Manager, HashiCorp Vault)
- [ ] **Connection pooling**: Configure SQLAlchemy pool size for production (`pool_size=20, max_overflow=40`)
- [ ] **SSL/TLS**: Enable SSL for PostgreSQL connections in production
- [ ] **User permissions**: Create dedicated database user with minimal required permissions

### Performance

- [ ] **Batch loading**: For large datasets (>1M rows), use COPY instead of INSERT
- [ ] **Index maintenance**: Run `REINDEX` and `VACUUM ANALYZE` regularly
- [ ] **Partitioning**: Consider table partitioning by dataset_id or fiscal_year for very large datasets
- [ ] **Query optimization**: Use `EXPLAIN ANALYZE` to identify slow queries

### Monitoring & Logging

- [ ] **ETL logs**: Capture ingestion/processing logs with timestamps
- [ ] **Error handling**: Log all validation failures and imputation decisions
- [ ] **Data quality**: Track quality_metadata in dataset_versions for trending
- [ ] **Performance metrics**: Monitor pipeline execution time and resource usage

### Backup & Recovery

- [ ] **Database backups**: Schedule regular PostgreSQL backups (daily/weekly)
- [ ] **Point-in-time recovery**: Test restore procedures
- [ ] **Data archival**: Archive old dataset versions after N months
- [ ] **Rollback procedure**: Document how to roll back to previous dataset version

### Scaling

- [ ] **Read replicas**: Set up PostgreSQL read replicas for downstream queries
- [ ] **Sharding**: For multi-region deployments, consider horizontal sharding
- [ ] **Caching**: Use Redis for frequently accessed metrics_outputs
- [ ] **Async processing**: For Stage 2 processing, consider async job queues (Celery, etc.)

---

## Next Steps

1. **Deploy test run**: Follow steps 1-5 with sample data
2. **Verify output**: Check quality metrics and imputation distribution
3. **Set up monitoring**: Configure logging and alerts
4. **Document environment**: Record specific configurations and credentials (securely)
5. **Schedule recurring loads**: Set up cron jobs or workflow orchestration for new Bloomberg uploads

---

## Support & Documentation

- **Schema Documentation**: See `SCHEMA_REFERENCE.md`
- **Usage Examples**: See `USAGE.md`
- **Sample Queries**: See `queries.py`
- **Implementation Details**: See `IMPLEMENTATION_PLAN.md`

---

**Last Updated**: 2026-03-03  
**Maintained By**: Data Engineering Team
