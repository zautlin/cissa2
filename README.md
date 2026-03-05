# CISSA - Financial Data Pipeline

**Status**: ✅ Production Ready  
**Last Updated**: 2026-03-05

## Overview

CISSA is a comprehensive financial data pipeline that ingests, validates, and processes Australian Securities Exchange (ASX) company financial data using the CISSA valuation methodology. It handles:

- **Data Ingestion**: Bloomberg Excel data → CSV extraction → numeric validation
- **Data Processing**: Fiscal year alignment → 7-step imputation cascade → cleaned fundamentals table
- **Data Quality**: Automatic duplicate detection, validation logging, and audit trails
- **Downstream Analysis**: Metrics computation and portfolio optimization

The legacy repository for this work is located in: `https://github.com/rozettatechnology/basos-ds`

---

## Architecture

### Three-Stage Pipeline

```
┌─────────────────────────────────────────────────────────┐
│ STAGE 1: DATA EXTRACTION & VALIDATION                   │
├─────────────────────────────────────────────────────────┤
│ • Excel → CSV extraction (24 worksheets)                │
│ • CSV denormalization (metrics pivot)                   │
│ • Numeric validation (reject unparseable values)        │
│ • Duplicate detection & audit logging                   │
│ Output: raw_data table (~275k rows)                     │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ STAGE 2: DATA CLEANING & ALIGNMENT                      │
├─────────────────────────────────────────────────────────┤
│ • FY alignment (extract fiscal years)                   │
│ • 7-step imputation cascade:                            │
│   - RAW values                                          │
│   - FORWARD_FILL / BACKWARD_FILL                        │
│   - INTERPOLATE / SECTOR_MEDIAN / MARKET_MEDIAN         │
│   - MISSING (unresolvable gaps)                         │
│ Output: fundamentals table (~187k rows, 100% filled)    │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ STAGE 3: DOWNSTREAM CONSUMPTION                         │
├─────────────────────────────────────────────────────────┤
│ • Metrics outputs (ROE, ROIC, FCF, valuations)          │
│ • Portfolio optimization (using CISSA methodology)      │
└─────────────────────────────────────────────────────────┘
```

### Database Schema

**10 Tables in `cissa` schema:**

| Layer | Tables | Purpose |
|-------|--------|---------|
| **Reference** | companies, fiscal_year_mapping | Immutable lookup data |
| **Versioning** | dataset_versions | Data lineage & audit trail |
| **Raw** | raw_data | Staging area with validation |
| **Cleaned** | fundamentals, imputation_audit_trail | Final fact table & quality logs |
| **Config** | parameters, parameter_sets | CISSA methodology parameters |
| **Output** | metrics_outputs, optimization_outputs | Downstream analysis results |

---

## Quick Start

### Prerequisites

- Python 3.14+ and [Anaconda/Miniconda](https://docs.conda.io/projects/miniconda/en/latest/)
- PostgreSQL 16+ (running and accessible)
- Bloomberg ASX data Excel file

### Installation

1. **Install Miniconda** (if not already installed):
   ```bash
   cd /tmp
   wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
   bash Miniconda3-latest-Linux-x86_64.sh -b -p ~/miniconda3
   source ~/miniconda3/bin/activate
   ```

2. **Clone the repository**:
   ```bash
   git clone https://github.com/rozettatechnology/cissa
   cd cissa
   ```

3. **Create and activate the virtual environment**:
   ```bash
   source ~/miniconda3/bin/activate
   conda create -n cissa_env python=3.12 -y
   conda activate cissa_env
   ```

4. **Install required packages**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Activate environment for future sessions**:
   ```bash
   source ~/miniconda3/bin/activate
   conda activate cissa_env
   ```

### Three Essential Commands

#### 1️⃣ Delete Schema and All Data

Completely removes the `cissa` schema and all its data from the database:

```bash
cd /home/ubuntu/cissa/backend/database/schema
python schema_manager.py destroy --confirm
```

**When to use**: Before re-ingesting fresh data or resetting the database.

---

#### 2️⃣ Re-initialize Schema

Creates a fresh schema with all tables, indexes, triggers, and baseline parameters:

```bash
cd /home/ubuntu/cissa/backend/database/schema
python schema_manager.py init
```

**When to use**: After deletion, or when setting up a new environment.

---

#### 3️⃣ Ingest and Process Data

Runs the complete 3-stage pipeline from Excel extraction through data processing:

```bash
cd /home/ubuntu/cissa/backend/database/etl
python pipeline.py \
  --input "input-data/ASX/raw-data/Bloomberg Download data.xlsx" \
  --mode full
```

**When to use**: Load new data into the system.

**Output:**
- Stage 1B: ~275k raw rows ingested, ~1k duplicates detected & logged
- Stage 2: ~187k cleaned rows, 100% data fill rate
- Pipeline completion with statistics

---

## Recent Enhancements

### Data Quality System (v2.1)

✅ **Duplicate Detection & Audit Trail**
- Automatically detects duplicate `(ticker, metric_name, period)` combinations during ingestion
- Logs all duplicates to `imputation_audit_trail` table for review
- Uses `ON CONFLICT DO NOTHING` to keep first occurrence, skip duplicates
- Stores period and occurrence metadata in JSONB format
- User sees clear notice: "⚠ Data Quality Notice: X duplicate records detected and logged"

**Example duplicate audit trail query:**
```sql
SELECT ticker, metric_name, period, num_occurrences
FROM (
  SELECT ticker, metric_name, 
    (metadata->>'period') as period,
    (metadata->>'num_occurrences')::int as num_occurrences
  FROM imputation_audit_trail
  WHERE imputation_step = 'DATA_QUALITY_DUPLICATE'
) sub
ORDER BY ticker, period
LIMIT 20;
```

---

## Database Configuration

### Environment Variables

Configuration is loaded from `.env` file (located in `/home/ubuntu/datahex-local/`):

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<password>
POSTGRES_DB=rozetta
```

All queries automatically use the `cissa` schema (set via `search_path` in connection).

---

## Documentation

- **[DEPLOYMENT_GUIDE.md](backend/database/DEPLOYMENT_GUIDE.md)** - Detailed deployment instructions
- **[CURRENT_SCHEMA.md](backend/database/CURRENT_SCHEMA.md)** - Complete schema reference
- **[VALIDATION_QUERIES.md](VALIDATION_QUERIES.md)** - Post-ingestion validation SQL
- **[VALIDATION.md](VALIDATION.md)** - Schema and data validation guide

---

## Troubleshooting

### Database Connection Issues

```bash
# Test connection
python backend/database/etl/config.py
# Expected: ✓ Database connection successful
```

### Schema Already Exists Error

```bash
# Delete schema first, then reinitialize
cd backend/database/schema
python schema_manager.py destroy --confirm
python schema_manager.py init
```

### Pipeline Ingestion Fails

Check the pipeline log for details. Common issues:
- Missing input file (verify path)
- Database connection problem (check environment variables)
- Duplicate data detected (normal - will log to audit trail and continue)

---

## Project Structure

```
cissa/
├── README.md (this file)
├── requirements.txt
├── input-data/
│   └── ASX/
│       ├── raw-data/ (Bloomberg Excel files)
│       ├── extracted-worksheets/ (CSV exports)
│       └── consolidated-data/ (merged metrics)
├── backend/
│   └── database/
│       ├── etl/
│       │   ├── pipeline.py (orchestrator)
│       │   ├── ingestion.py (Stage 1)
│       │   ├── processing.py (Stage 2)
│       │   ├── fy_aligner.py (fiscal year alignment)
│       │   ├── imputation_engine.py (7-step cascade)
│       │   ├── config.py (database connection)
│       │   └── validators.py (numeric validation)
│       ├── schema/
│       │   ├── schema.sql (table definitions)
│       │   ├── schema_manager.py (initialization tool)
│       │   └── destroy_schema.sql (cleanup)
│       ├── DEPLOYMENT_GUIDE.md
│       ├── CURRENT_SCHEMA.md
│       └── USAGE.md
└── VALIDATION_QUERIES.md
```

---

## Contributing

When modifying the pipeline:

1. Update schema.sql if tables/columns change
2. Add validation queries to VALIDATION_QUERIES.md
3. Test with fresh data ingestion
4. Commit changes with clear messages describing data quality or pipeline improvements

---

## License

[License information to be added]
