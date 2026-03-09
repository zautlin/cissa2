# CISSA Test Scripts - L1 Basic Metrics & Beyond

This directory contains shell scripts for testing CISSA metrics calculations across all phases.

## Scripts Overview

| Script | Purpose | Phase | Metrics | Dependencies |
|--------|---------|-------|---------|--------------|
| `run-l1-basic-metrics.sh` | Test L1 basic metrics with Phase 06 support | 1 (Phase 06) | 12 L1 (7 simple + 5 temporal) | PostgreSQL, API running |
| `test-l2-metrics.sh` | Test L2 metrics calculations | 2 | L2 derived metrics | L1 metrics, PostgreSQL, API |
| `test-l3-metrics.sh` | Test L3 enhanced metrics | 3 | 6 L3 metrics | L1/L2 metrics, PostgreSQL, API |
| `start-api.sh` | Start FastAPI backend | - | - | Python 3.10+ |
| `clear-metrics.sh` | Clear metrics_outputs table | - | - | PostgreSQL |

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
# Phase 1: Calculate L1 basic metrics (7 simple + 5 Phase 06 temporal)
./backend/scripts/run-l1-basic-metrics.sh

# Or with a specific parameter set
./backend/scripts/run-l1-basic-metrics.sh --param-set-id <uuid>

# Phase 2: Calculate L2 metrics (uses L1 results)
./backend/scripts/test-l2-metrics.sh

# Phase 3: Calculate L3 metrics (uses L1 + parameters)
./backend/scripts/test-l3-metrics.sh
```

## run-l1-basic-metrics.sh - L1 Basic Metrics Test (Phase 06 Temporal Metrics)

This script tests all **12 Phase 06 L1 metrics**:
- **7 Simple Metrics** (no parameters required)
- **5 Temporal Metrics** (parameter-sensitive)

### 12 L1 Metrics Breakdown

#### Simple Metrics (7) - No Parameters Required
1. **Calc MC** — Market Capitalization (Spot Shares × Share Price)
2. **Calc Assets** — Operating Assets (Total Assets - Cash)
3. **Calc OA** — Operating Assets Detail
4. **Calc Op Cost** — Operating Cost
5. **Calc Non Op Cost** — Non-Operating Cost
6. **Calc Tax Cost** — Tax Cost
7. **Calc XO Cost** — Extraordinary Cost

#### Temporal Metrics (5) - Phase 06 New Features
8. **ECF** — Economic Cash Flow
9. **NON_DIV_ECF** — Non-Dividend Economic Cash Flow
10. **EE** — Economic Equity
11. **FY_TSR** — Fiscal Year Total Shareholder Return (parameter-sensitive)
12. **FY_TSR_PREL** — Fiscal Year TSR Preliminary (parameter-sensitive)

### Usage

```bash
# Use default parameter set (is_default = true in parameter_sets table)
./run-l1-basic-metrics.sh

# Specify a parameter set UUID
./run-l1-basic-metrics.sh --param-set-id 660f9500-f39c-51e5-b827-557766551111
```

### Script Flow (5 Steps)

**Step 1: Check API Status**
- Verifies FastAPI backend is running on `http://localhost:8000`
- Required for all calculations

**Step 2: Get Dataset ID**
- Queries `cissa.fundamentals` table
- Retrieves first available dataset_id

**Step 3: Resolve Parameter Set ID**
- If `--param-set-id` provided: uses that parameter set
- Otherwise: fetches default parameter set (where `is_default = true`)
- **Critical for:** FY_TSR, FY_TSR_PREL calculations
- **Note:** UI will pass user's selected parameter set during metric trigger

**Step 4: Calculate All 12 L1 Metrics**
- Iterates through 7 simple metrics (no param needed)
- Iterates through 5 temporal metrics (param included in request)
- Each metric returns count of records calculated
- Errors shown immediately if metric calculation fails

**Step 5: Metrics Summary**
- Displays all calculated metrics in metrics_outputs table
- Shows min/max/avg values for each metric
- Sample of 30 records for verification

### Implementation Details for UI Integration

When triggering metric calculation from UI, the flow should be:

```javascript
// User selects parameter set in UI (e.g., "base_case", "aggressive", etc.)
const selectedParamSetId = parameterSets.find(ps => ps.name === userSelection).id;

// Call API for temporal metrics with param_set_id
POST /api/v1/metrics/calculate
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "metric_name": "FY_TSR",
  "param_set_id": selectedParamSetId  // User's choice
}

// For simple metrics, param_set_id is optional/ignored
POST /api/v1/metrics/calculate
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "metric_name": "Calc MC"
}
```

The backend (`metrics_service.py`) handles both cases:
- **Simple metrics:** Executes SQL function with dataset_id only
- **Temporal metrics:** Includes param_set_id in SQL function call

### Expected Output

Success indicators when running the script:

```
✓ API is running
✓ Found dataset_id: 550e8400-...
✓ Using default parameter set: 660f9500-...
✓ Calc MC (11000 records)
✓ Calc Assets (11000 records)
...
✓ FY_TSR (11000 records)
✓ FY_TSR_PREL (11000 records)

Metrics Summary table:
 output_metric_name | count | min_value | max_value | avg_value
--------------------|-------|-----------|-----------|----------
 Calc Assets        | 11000 |    ...    |    ...    |    ...
 Calc MC            | 11000 |    ...    |    ...    |    ...
 Calc Non Op Cost   | 11000 |    ...    |    ...    |    ...
 Calc OA            | 11000 |    ...    |    ...    |    ...
 Calc Op Cost       | 11000 |    ...    |    ...    |    ...
 Calc Tax Cost      | 11000 |    ...    |    ...    |    ...
 Calc XO Cost       | 11000 |    ...    |    ...    |    ...
 ECF                | 11000 |    ...    |    ...    |    ...
 EE                 | 11000 |    ...    |    ...    |    ...
 FY_TSR             | 11000 |    ...    |    ...    |    ...
 FY_TSR_PREL        | 11000 |    ...    |    ...    |    ...
 NON_DIV_ECF        | 11000 |    ...    |    ...    |    ...
```

### Phase 06 Documentation

For detailed Phase 06 implementation:
- `.planning/06-L1-Metrics-Alignment/L1_METRICS_SQL_MAPPING.md` — SQL formula reference
- `.planning/06-L1-Metrics-Alignment/PARAMETER_MAPPING.md` — Parameter structure
- `.planning/06-L1-Metrics-Alignment/GAP_DETECTION.md` — Year gap handling

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

### "No parameter sets found" (for temporal metrics)
```bash
# Check existing parameter sets
psql -U postgres -d cissa -c "SELECT param_set_id, param_set_name, is_default FROM cissa.parameter_sets;"

# Create a default parameter set if needed
psql -U postgres -d cissa -c "
INSERT INTO cissa.parameter_sets (param_set_name, is_default, created_at)
VALUES ('base_case', true, NOW());
"
```

### FY_TSR / FY_TSR_PREL metrics fail
```bash
# Verify parameter set exists and has is_default = true
psql -U postgres -d cissa -c "
SELECT param_set_id, param_set_name, is_default FROM cissa.parameter_sets;
"

# If no default, specify one explicitly:
./backend/scripts/run-l1-basic-metrics.sh --param-set-id <uuid>

# Check API logs for specific error
tail -50 /tmp/api.log | grep -i "FY_TSR"
```

### "L1 metric calculation failed"
- Check API logs: `grep -i 'Calc MC\|ECF\|FY_TSR' /tmp/api.log`
- Verify metric exists in METRIC_FUNCTIONS: `grep -A 15 "METRIC_FUNCTIONS =" backend/app/services/metrics_service.py`
- Query database to check if SQL functions exist: `psql -U postgres -d cissa -c "\df cissa.fn_calc_*"`

## Manual Testing

If you prefer to run steps manually:

```bash
# 1. Start services
sudo systemctl start postgresql
./backend/scripts/start-api.sh

# 2. Get test data
DATASET_ID=$(psql "$DATABASE_URL_CLI" -t -c "SELECT dataset_id FROM cissa.fundamentals LIMIT 1;" | xargs)
PARAM_SET_ID=$(psql "$DATABASE_URL_CLI" -t -c "SELECT param_set_id FROM cissa.parameter_sets WHERE is_default = true LIMIT 1;" | xargs)

# 3. Call API for simple L1 metric (no parameters)
curl -X POST http://localhost:8000/api/v1/metrics/calculate \
  -H "Content-Type: application/json" \
  -d "{\"dataset_id\": \"$DATASET_ID\", \"metric_name\": \"Calc MC\"}"

# 4. Call API for temporal L1 metric (with parameters)
curl -X POST http://localhost:8000/api/v1/metrics/calculate \
  -H "Content-Type: application/json" \
  -d "{\"dataset_id\": \"$DATASET_ID\", \"metric_name\": \"FY_TSR\", \"param_set_id\": \"$PARAM_SET_ID\"}"

# 5. Query results
psql "$DATABASE_URL_CLI" -c "
SELECT ticker, fiscal_year, output_metric_name, output_metric_value
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
ORDER BY output_metric_name, ticker, fiscal_year
LIMIT 30;
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

After successful L1 basic metrics testing:

1. **Review Phase 06 Implementation:**
   - `.planning/06-L1-Metrics-Alignment/L1_METRICS_SQL_MAPPING.md` — All 12 L1 metric formulas
   - `.planning/06-L1-Metrics-Alignment/PARAMETER_MAPPING.md` — Parameter structure
   - `.planning/06-L1-Metrics-Alignment/STATE.md` — Implementation status

2. **Test L2 Metrics (Phase 2):**
   ```bash
   ./backend/scripts/test-l2-metrics.sh
   ```

3. **Test L3 Enhanced Metrics (Phase 3):**
   ```bash
   ./backend/scripts/test-l3-metrics.sh
   ```

4. **UI Integration for Temporal Metrics:**
   - Temporal metrics (FY_TSR, FY_TSR_PREL) require user's selected parameter set
   - When user triggers calculation in UI, pass their param_set_id to `/api/v1/metrics/calculate`
   - See "Implementation Details for UI Integration" section above

## File Locations

```
backend/
├── scripts/
│   ├── run-l1-basic-metrics.sh       ← Phase 06 L1 basic metrics test
│   ├── test-l2-metrics.sh            ← Phase 2 L2 metrics test
│   ├── test-l3-metrics.sh            ← Phase 3 L3 enhanced metrics test
│   ├── README.md                     ← This file
│   ├── start-api.sh
│   └── clear-metrics.sh
├── app/
│   ├── services/
│   │   ├── metrics_service.py        ← L1 metric calculations
│   │   ├── l2_metrics_service.py     ← L2 metric calculations
│   │   └── enhanced_metrics_service.py  ← L3 calculations
│   ├── api/v1/endpoints/
│   │   └── metrics.py                ← /calculate, /calculate-l2, /calculate-enhanced endpoints
│   └── cli/
│       └── run_enhanced_metrics.py   ← CLI for testing L3
└── database/
    └── schema/
        ├── functions.sql             ← 21 metric calculation functions (7 L1 simple + 5 L1 temporal + 8 L2 legacy + 1 support)
        └── schema.sql                ← metrics_outputs table definition
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

**Last Updated:** 2025-03-09  
**Phase:** 1 (Phase 06 L1 Temporal Metrics)  
**Status:** Ready for Testing
