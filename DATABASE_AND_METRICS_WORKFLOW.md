# CISSA Database & Metrics Workflow

This document outlines the complete workflow for setting up the CISSA database, ingesting data, calculating pre-computed metrics, and running runtime metrics calculations.

## Overview

The workflow consists of 5 main stages:

1. **Database Setup** - Create PostgreSQL database schema and functions
2. **Schema Initialization** - Initialize database schema (optional destroy if needed)
3. **Data Ingestion & Pre-Computation** - Load Bloomberg data and calculate pre-computed metrics
4. **Runtime Metrics Calculation** - Calculate runtime metrics via API endpoint

---

## Step 1: Database Creation (One-time Setup)

**Prerequisites:**
- PostgreSQL server running locally on `localhost:5432`
- Database credentials configured in `.env` file
- `DATABASE_URL` environment variable set (format: `postgresql://user:password@host:port/database`)

**Command:**
```bash
createdb -U postgres rozetta
```

**Notes:**
- This creates an empty PostgreSQL database named `rozetta`
- Only needs to be done once per environment
- Database name should match the `DATABASE_URL` in `.env`

**Time:** < 1 second

---

## Step 2: Schema Initialization

**Purpose:** Create database schema, tables, indexes, and PostgreSQL functions for metrics calculations.

**Command:**
```bash
python backend/database/schema/schema_manager.py init
```

**What it does:**
- Creates all required tables:
  - `cissa.dataset_versions` - Dataset metadata
  - `cissa.metrics_outputs` - Calculated metrics storage
  - `cissa.fundamentals` - Fundamental data (market cap, TSR, dividends, etc.)
  - `cissa.parameter_sets` - Parameter configurations
  - `cissa.parameters` - Individual parameter values
  - Other supporting tables
- Creates indexes for query optimization
- Creates PostgreSQL functions for complex calculations
- Sets up constraints and relationships

**Output:** Schema initialization messages showing table creation progress

**Time:** 2-5 seconds

**Note:** This is idempotent and safe to run multiple times (existing objects are not recreated if they already exist).

---

## Step 3: Schema Reset (Optional - Destroy & Reinitialize)

**Purpose:** Clear all data and reset database to clean state when you need to start over.

### 3a. Destroy Existing Schema

**Command:**
```bash
python backend/database/schema/schema_manager.py destroy --confirm
```

**What it does:**
- Drops all tables, indexes, functions, and schemas from CISSA
- Removes all data permanently
- Does NOT drop the database itself

**Output:** Destruction confirmation messages

**Time:** 1-2 seconds

**⚠️ Warning:** This is destructive and irreversible. All data will be lost.

### 3b. Reinitialize Schema

After destruction, reinitialize the schema:

```bash
python backend/database/schema/schema_manager.py init
```

**Result:** Clean database ready for fresh data ingestion.

---

## Step 4: Data Ingestion & Pre-Computed Metrics Calculation

**Purpose:** Load Bloomberg data and calculate pre-computed (L0) metrics that don't depend on parameters.

### Prerequisites:
- Schema initialized (Step 2 completed)
- Bloomberg Excel file available at specified path
- Example file: `input-data/ASX/raw-data/Bloomberg Download data.xlsx`

### Command:

```bash
python backend/database/etl/pipeline.py \
  --input "input-data/ASX/raw-data/Bloomberg Download data.xlsx" \
  --mode full
```

### What it does:

**Phase 1: Data Ingestion**
- Reads Bloomberg data from Excel file
- Validates and cleans data
- Loads into `cissa.fundamentals` table
- Creates dataset version record

**Phase 2: Pre-Computed Metrics (L0)**
- Calculates metrics that are independent of parameters:
  - **Calc MC** - Market Capitalization (from Bloomberg data)
  - **Calc Assets** - Total Assets
  - **Calc OA** - Operating Assets
  - **Calc Op Cost** - Operating Costs
  - **Calc Non Op Cost** - Non-Operating Costs
  - **Calc Tax Cost** - Tax Costs
  - **Calc XO Cost** - Extraordinary/Other Costs
  - **Calc ECF** - Equity Cash Flow
  - **Non Div ECF** - Non-Dividend ECF
  - **Calc EE** - Employee Equity
  - **Calc FY TSR** - Fiscal Year Total Shareholder Return
  - **Calc FY TSR PREL** - Preliminary TSR
- Stores in `cissa.metrics_outputs` table

**Output:**
```
ETL Pipeline: Starting data ingestion...
Loading Bloomberg data from: input-data/ASX/raw-data/Bloomberg Download data.xlsx
✓ Ingested 500 tickers × ~20 years = ~10,000 fundamentals records
✓ Pre-computed metrics calculated: 13 metrics
✓ Total L0 metrics records: ~130,000
ETL Pipeline: Complete
```

### Typical Results for ASX Dataset:
- **Tickers:** 500
- **Years per ticker:** ~20 (varies by company)
- **Fundamentals records:** ~10,000
- **Pre-computed metric records:** ~130,000 (13 metrics × all ticker-year pairs)
- **Dataset ID:** Auto-generated UUID (e.g., `5f8bfdfd-dc59-451d-a236-856c6a509b71`)

### Time: 2-5 minutes

---

## Step 5: Runtime Metrics Calculation

**Purpose:** Calculate parameter-dependent metrics in real-time via API endpoint.

After data ingestion and pre-computation, you'll have:
- `dataset_id` - From data ingestion (e.g., `5f8bfdfd-dc59-451d-a236-856c6a509b71`)
- `param_set_id` - From schema init (e.g., `18c57790-cb6a-47df-99dd-843db9306282`)

### Phases Executed (in sequence):

| Phase | Name | Metrics | Records | Time |
|-------|------|---------|---------|------|
| 1 | Beta Rounding | Calc Beta Rounded | 11,000 | ~1.5s |
| 2 | Risk-Free Rate | Calc Rf | 10,905 | ~7.9s |
| 3 | Cost of Equity | Calc KE | 10,905 | ~1.6s |
| 4 | FV ECF | 4 intervals (1Y/3Y/5Y/10Y) | 42,120 | ~51.9s |
| 5 | TER & TER-KE | 8 metrics (4 intervals each) | 89,660 | ~14.4s |
| 6 | TER Alpha | 12 metrics (4 intervals each) | 131,780 | ~23.9s |
| | | **TOTAL** | **~296,370** | **~101.2s** |

### Metrics Calculated by Phase:

**Phase 1 - Beta Rounding (1.5s)**
- `Calc Beta Rounded` (11,000 records)
- Pre-computed Beta with parameter-specific rounding applied

**Phase 2 - Risk-Free Rate (7.9s)**
- `Calc Rf` (10,905 records)
- Calculated from benchmark rates and risk premium parameter

**Phase 3 - Cost of Equity (1.6s)**
- `Calc KE` (10,905 records)
- Formula: `Calc Rf + Calc Beta Rounded × Risk Premium`

**Phase 4 - Future Value of Equity Cash Flow (51.9s)**
- `Calc 1Y FV ECF`, `Calc 3Y FV ECF`, `Calc 5Y FV ECF`, `Calc 10Y FV ECF`
- 42,120 records total (4 intervals with varying coverage)
- Projects equity cash flows forward

**Phase 5 - Total Expense Ratio (14.4s)**
- `Calc 1Y TER`, `Calc 3Y TER`, `Calc 5Y TER`, `Calc 10Y TER` (4 metrics)
- `Calc 1Y TER-KE`, `Calc 3Y TER-KE`, `Calc 5Y TER-KE`, `Calc 10Y TER-KE` (4 metrics)
- 89,660 records total
- Measures total expense ratio and TER adjusted for cost of equity

**Phase 6 - TER Alpha (23.9s)** ✓ New in Phase 10d
- `Calc 1Y/3Y/5Y/10Y Load RA MM` (4 metrics) - Portfolio-level risk adjustment
- `Calc 1Y/3Y/5Y/10Y WC TERA` (4 metrics) - Wealth creation adjustment
- `Calc 1Y/3Y/5Y/10Y TER Alpha` (4 metrics) - Risk-adjusted performance
- 131,780 records total (includes NULL rows for insufficient history)
- Risk-adjusted performance metric comparing actual TER to cost of equity

### Command:

```bash
curl -X POST \
  "http://localhost:8000/api/v1/metrics/runtime-metrics?dataset_id=5f8bfdfd-dc59-451d-a236-856c6a509b71&param_set_id=18c57790-cb6a-47df-99dd-843db9306282" \
  -H "Content-Type: application/json" | python -m json.tool
```

**Parameters:**
- `dataset_id` - UUID from Step 4 data ingestion
- `param_set_id` - UUID from Step 2 schema initialization

### Response Example:

```json
{
    "success": true,
    "execution_time_seconds": 101.24,
    "dataset_id": "5f8bfdfd-dc59-451d-a236-856c6a509b71",
    "param_set_id": "18c57790-cb6a-47df-99dd-843db9306282",
    "metrics_completed": {
        "beta_rounding": {
            "status": "success",
            "records_inserted": 11000,
            "time_seconds": 1.55
        },
        "risk_free_rate": {
            "status": "success",
            "records_inserted": 10905,
            "time_seconds": 7.87
        },
        "cost_of_equity": {
            "status": "success",
            "records_inserted": 10905,
            "time_seconds": 1.61
        },
        "fv_ecf": {
            "status": "success",
            "records_inserted": 42120,
            "time_seconds": 51.86,
            "intervals_summary": {
                "1Y": 10405,
                "3Y": 9905,
                "5Y": 8905,
                "10Y": 6405
            }
        },
        "ter": {
            "status": "unknown",
            "records_inserted": 89660,
            "time_seconds": 14.35
        },
        "ter_alpha": {
            "status": "success",
            "records_inserted": 131780,
            "time_seconds": 23.94
        }
    }
}
```

### Timing:
- **Total wall-clock time:** ~101 seconds (1m41s)
- **Phases run sequentially** - each phase depends on previous results
- **Bottleneck:** Phase 4 (FV ECF) at ~52 seconds

### Verifying Results:

Query specific metrics from the database:

```bash
# Get TER Alpha values for a specific company/year
psql postgresql://user:password@localhost/rozetta -c "
  SELECT ticker, fiscal_year, output_metric_name, output_metric_value
  FROM cissa.metrics_outputs
  WHERE dataset_id = '5f8bfdfd-dc59-451d-a236-856c6a509b71'
    AND param_set_id = '18c57790-cb6a-47df-99dd-843db9306282'
    AND ticker = 'CSL AU Equity'
    AND output_metric_name LIKE '%TER Alpha%'
  ORDER BY fiscal_year, output_metric_name;
"
```

---

## Complete Workflow Example

Here's how to run the entire workflow from scratch:

```bash
# Step 1: Create database (one-time)
createdb -U postgres rozetta

# Step 2: Initialize schema
python backend/database/schema/schema_manager.py init

# Step 3: (Optional) Destroy and reinit if needed
# python backend/database/schema/schema_manager.py destroy --confirm
# python backend/database/schema/schema_manager.py init

# Step 4: Ingest data and pre-compute metrics
python backend/database/etl/pipeline.py \
  --input "input-data/ASX/raw-data/Bloomberg Download data.xlsx" \
  --mode full

# Step 5: Start backend server
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Step 6: Calculate runtime metrics (replace with actual IDs from Step 4 output)
curl -X POST \
  "http://localhost:8000/api/v1/metrics/runtime-metrics?dataset_id=5f8bfdfd-dc59-451d-a236-856c6a509b71&param_set_id=18c57790-cb6a-47df-99dd-843db9306282" \
  -H "Content-Type: application/json" | python -m json.tool
```

**Total time:** ~2-5 minutes (dominated by data ingestion and runtime metrics calculation)

---

## Troubleshooting

### Issue: "database does not exist"
**Solution:** Run `createdb -U postgres rozetta`

### Issue: "relation does not exist"
**Solution:** Reinitialize schema: `python backend/database/schema/schema_manager.py init`

### Issue: Runtime metrics returns error
**Solution:** 
1. Verify dataset_id and param_set_id are correct
2. Check backend server is running on port 8000
3. Ensure database is populated with pre-computed metrics

### Issue: No data after ingestion
**Solution:** 
1. Verify Excel file path is correct and file exists
2. Check Excel file format matches expected Bloomberg schema
3. Review ETL logs for parsing errors

---

## Key Parameters

Store these from outputs for later use:

| Parameter | Example | From Step |
|-----------|---------|-----------|
| `dataset_id` | `5f8bfdfd-dc59-451d-a236-856c6a509b71` | 4 (Data Ingestion) |
| `param_set_id` | `18c57790-cb6a-47df-99dd-843db9306282` | 2 (Schema Init) |
| `database_url` | `postgresql://postgres:pass@localhost/rozetta` | .env file |

---

## Additional Commands

### View Available Parameters

```bash
psql postgresql://user:password@localhost/rozetta -c "
  SELECT param_set_id, is_active, created_at
  FROM cissa.parameter_sets
  ORDER BY created_at DESC;
"
```

### Check Dataset Status

```bash
psql postgresql://user:password@localhost/rozetta -c "
  SELECT dataset_id, created_at, (
    SELECT COUNT(*) FROM cissa.metrics_outputs 
    WHERE dataset_id = cissa.dataset_versions.dataset_id
  ) as metric_records
  FROM cissa.dataset_versions
  ORDER BY created_at DESC;
"
```

### Count Metrics by Type

```bash
psql postgresql://user:password@localhost/rozetta -c "
  SELECT output_metric_name, COUNT(*) as count
  FROM cissa.metrics_outputs
  WHERE dataset_id = '5f8bfdfd-dc59-451d-a236-856c6a509b71'
  GROUP BY output_metric_name
  ORDER BY count DESC;
"
```

---

## Architecture Notes

- **Database:** PostgreSQL (async queries via asyncpg)
- **Backend:** FastAPI (Python async framework)
- **Data Flow:** Bloomberg Excel → ETL → Pre-computed metrics (L0) → Runtime metrics (L1+)
- **Calculations:** Vectorized Pandas operations with single multi-row database inserts for performance
- **Orchestration:** Sequential phase execution (FAIL-SOFT - later phases continue if earlier phases error)
