# CISSA Test Scripts - Phase 3 L3 Enhanced Metrics

This directory contains shell scripts for testing CISSA metrics calculations across all phases.

## Scripts Overview

| Script | Purpose | Phase | Dependencies |
|--------|---------|-------|--------------|
| `test-metrics.sh` | Test L1 metrics calculations | 1 | PostgreSQL, API running |
| `test-l2-metrics.sh` | Test L2 metrics calculations | 2 | L1 metrics, PostgreSQL, API |
| `test-l3-metrics.sh` | Test L3 enhanced metrics | 3 | L1/L2 metrics, PostgreSQL, API |
| `start-api.sh` | Start FastAPI backend | - | Python 3.10+ |
| `clear-metrics.sh` | Clear metrics_outputs table | - | PostgreSQL |

## Getting Started

### 1. Prerequisites

Ensure you have:
- PostgreSQL running with `cissa` database populated
- Python 3.10+ with FastAPI installed
- `.env` file in project root with database credentials

### 2. Start the Database and API

```bash
# Start PostgreSQL (if not already running)
sudo systemctl start postgresql

# Start the FastAPI backend (if not running)
./backend/scripts/start-api.sh

# The script will run on http://localhost:8000
```

### 3. Run the Tests in Order

```bash
# Phase 1: Calculate L1 metrics
./backend/scripts/test-metrics.sh

# Phase 2: Calculate L2 metrics (uses L1 results)
./backend/scripts/test-l2-metrics.sh

# Phase 3: Calculate L3 metrics (uses L1 + parameters)
./backend/scripts/test-l3-metrics.sh
```

## test-l3-metrics.sh - Detailed Guide

The Phase 3 test script performs 9 steps:

### Step 1: Check API Status
- Verifies FastAPI backend is running on `http://localhost:8000`
- Auto-starts API if not already running
- Required for all calculations

### Step 2: Ensure L1 Metrics
- Runs `test-metrics.sh` to ensure all 15 L1 metrics are calculated
- L1 metrics are prerequisite for L3 calculations
- Covers: Calc MC, Calc Assets, ROA, etc.

### Step 3: Get Dataset ID
- Queries `cissa.fundamentals` table
- Returns first available dataset_id
- Example: `550e8400-e29b-41d4-a716-446655440000`

### Step 4: Get Parameter Set ID
- Queries `cissa.parameter_sets` table
- Prefers `base_case` parameter set
- Falls back to first available if base_case not found

### Step 5: Verify L1 Metrics
- Confirms L1 metrics exist for all tickers
- Checks for `Calc MC` metric (simplest L1 metric)
- Ensures database is ready for L3 calculations

### Step 6: Show Parameter Set Details
- Displays parameter set name, ID, and creation timestamp
- Confirms which parameters will be used for L3 calculations

### Step 7: Calculate L3 Enhanced Metrics
- **Main step** — Calls API endpoint `/api/v1/metrics/calculate-enhanced`
- Calculates 6 L3 metrics per ticker-fiscal_year:
  - **Beta** (placeholder = 1.0)
  - **Calc Rf** (risk-free rate from parameters)
  - **Calc KE** (cost of equity = Rf + Beta × Risk Premium)
  - **ROA** (return on assets)
  - **ROE** (return on equity)
  - **Profit Margin**
- Results stored in `cissa.metrics_outputs` with metadata `{"metric_level": "L3"}`

### Step 8: Show L3 Metrics Summary
- Groups L3 metrics by type (Beta, Calc Rf, etc.)
- Shows count, min/max/avg values
- Helps verify calculation succeeded and values are reasonable

### Step 9: Show Sample L3 Records
- Displays 18 sample records (3 tickers × 6 metrics)
- Shows: ticker, fiscal_year, metric_name, value, created_at
- Confirms data format and storage

### Bonus: Data Quality Checks
- **Coverage:** Shows which metrics, tickers, fiscal years present
- **By Ticker:** Sample 5 tickers with record counts and year coverage

## Expected Output

### Success Indicators

When the script completes successfully, you'll see:

```
✓ API is running
✓ L1 metrics ready (250 tickers)
✓ Found dataset_id: 550e8400-...
✓ Found param_set_id: 660f9500-...
✓ Found L1 metrics for 250 tickers
✓ L3 metrics calculated successfully
  - Records inserted: 1500
  - Metrics calculated: Beta, Calc Rf, Calc KE, ROA, ROE, Profit Margin
```

### Sample Data Table

```
 ticker | fiscal_year | output_metric_name | output_metric_value | created_at
--------|-------------|-------------------|---------------------|--------------------
 AAPL   |        2023 | Beta               |                 1.0 | 2025-03-08 23:42:10
 AAPL   |        2023 | Calc KE            |                0.125 | 2025-03-08 23:42:10
 AAPL   |        2023 | Calc Rf            |                0.075 | 2025-03-08 23:42:10
 AAPL   |        2023 | Profit Margin      |              0.184 | 2025-03-08 23:42:10
 AAPL   |        2023 | ROA                |                0.02 | 2025-03-08 23:42:10
 AAPL   |        2023 | ROE                |                 1.4 | 2025-03-08 23:42:10
```

All values are stored as **decimals** (0.05 = 5%, not 5).

## Troubleshooting

### "API is not running"
```bash
# Start it manually
./backend/scripts/start-api.sh

# Or start with uvicorn directly
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### "No datasets found"
```bash
# Check if fundamentals table is populated
psql -U postgres -d cissa -c "SELECT COUNT(*) FROM cissa.fundamentals;"

# Should return > 0. If empty, load data first.
```

### "No parameter sets found"
```bash
# Create a parameter set
psql -U postgres -d cissa -c "
INSERT INTO cissa.parameter_sets (param_set_name, created_at)
VALUES ('base_case', NOW());
"
```

### "L3 metric calculation failed"
- Check API logs: `grep -i 'enhanced' /tmp/api.log`
- Verify L1 metrics exist: `psql -U postgres -d cissa -c "SELECT COUNT(*) FROM cissa.metrics_outputs WHERE output_metric_name = 'Calc MC';"`
- Check database connection in `.env`

### Database Connection Issues
```bash
# Verify psql can connect
psql -U postgres -d cissa -c "SELECT VERSION();"

# If fails, check .env DATABASE_URL_CLI is correct
cat .env | grep DATABASE_URL
```

## Manual Testing

If you prefer to run steps manually:

```bash
# 1. Start services
sudo systemctl start postgresql
./backend/scripts/start-api.sh

# 2. Get test data
DATASET_ID=$(psql "$DATABASE_URL_CLI" -t -c "SELECT dataset_id FROM cissa.fundamentals LIMIT 1;" | xargs)
PARAM_SET_ID=$(psql "$DATABASE_URL_CLI" -t -c "SELECT param_set_id FROM cissa.parameter_sets LIMIT 1;" | xargs)

# 3. Call API directly
curl -X POST http://localhost:8000/api/v1/metrics/calculate-enhanced \
  -H "Content-Type: application/json" \
  -d "{\"dataset_id\": \"$DATASET_ID\", \"param_set_id\": \"$PARAM_SET_ID\"}"

# 4. Query results
psql "$DATABASE_URL_CLI" -c "
SELECT ticker, fiscal_year, output_metric_name, output_metric_value
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND metadata->>'metric_level' = 'L3'
LIMIT 20;
"
```

## CLI Testing

You can also test the L3 service using the CLI script:

```bash
# Run directly with UUIDs
python backend/app/cli/run_enhanced_metrics.py \
  550e8400-e29b-41d4-a716-446655440000 \
  660f9500-f39c-51e5-b827-557766551111

# Output:
# Enhanced Metrics Calculation Complete
# Total records inserted: 1500
# Metrics calculated: Beta, Calc Rf, Calc KE, ROA, ROE, Profit Margin
```

## Understanding L3 Metrics Output

### What Gets Calculated

For each **ticker + fiscal_year combination**, the service calculates 6 metrics:

1. **Beta** — Market sensitivity (currently placeholder = 1.0)
2. **Calc Rf** — Risk-free rate from parameter set
3. **Calc KE** — Cost of Equity = Rf + Beta × Risk Premium
4. **ROA** — Return on Assets = PAT / Total Assets
5. **ROE** — Return on Equity = PAT / Total Equity
6. **Profit Margin** — PAT / Revenue

### Data Volume

With typical data:
- 250 stocks × 5 fiscal years × 6 metrics = **7,500 L3 records**
- All stored to `cissa.metrics_outputs` table
- Tagged with metadata: `{"metric_level": "L3", "calculation_source": "enhanced_metrics_service"}`

### Parameter Conversions

Database stores parameters as **percentages**, service converts to **decimals**:

| Parameter | DB Value | Code Value | Used For |
|-----------|----------|------------|----------|
| equity_risk_premium | 5.0 | 0.05 | Calc KE |
| fixed_benchmark_return_wealth_preservation | 7.5 | 0.075 | Calc Rf |
| beta_relative_error_tolerance | 40.0 | 0.4 | Beta validation |
| tax_rate_franking_credits | 30.0 | 0.30 | Future TSR calc |

## Next Steps

After successful L3 testing:

1. **Review Phase 3 Implementation:**
   - `.planning/PHASE3_IMPLEMENTATION_SUMMARY.md`
   - `.planning/PHASE3_OUTPUT_EXAMPLE.md`

2. **Plan Phase 4 (if exists):**
   ```bash
   /gsd-plan-phase 04-phase-name
   ```

3. **Port Future Calculations:**
   - Rolling OLS for Beta (from `example-calculations/src/executors/beta.py`)
   - Economic Profit (formulas ready in Phase 3 docs)
   - TSR with Franking Credits

## File Locations

```
backend/
├── scripts/
│   ├── test-l3-metrics.sh         ← Phase 3 test script
│   ├── test-l2-metrics.sh         ← Phase 2 test script
│   ├── test-metrics.sh            ← Phase 1 test script
│   ├── README.md                  ← This file
│   ├── start-api.sh
│   └── clear-metrics.sh
├── app/
│   ├── services/
│   │   └── enhanced_metrics_service.py     ← L3 calculations
│   ├── api/v1/endpoints/
│   │   └── metrics.py             ← /calculate-enhanced endpoint
│   └── cli/
│       └── run_enhanced_metrics.py ← CLI for testing
└── database/
    └── schema/
        └── schema.sql             ← metrics_outputs table def
```

## Environment Variables

Required in `.env`:

```bash
# Database
DATABASE_URL="postgresql+asyncpg://user:pass@localhost/cissa"
DATABASE_URL_CLI="user=postgres password=pass host=localhost dbname=cissa"

# API
API_HOST="0.0.0.0"
API_PORT="8000"
```

## Support

For issues:

1. Check `.planning/PHASE3_IMPLEMENTATION_SUMMARY.md` for architecture
2. Review `.planning/PHASE3_OUTPUT_EXAMPLE.md` for expected data
3. Check API logs: `tail -50 /tmp/api.log`
4. Query database directly to verify data flow

---

**Last Updated:** 2025-03-08  
**Phase:** 3 - Enhanced Metrics Service  
**Status:** Ready for Testing
