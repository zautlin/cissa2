# Testing & Verification Guide

## Overview

This guide shows you how to:
1. **Start the API** and test it
2. **Calculate metrics** and see results
3. **View metrics_outputs table**
4. **Clear the table** for fresh calculations

---

## Quick Start (3 Steps)

### 1. Start the API
```bash
./start-api.sh
```

Expected output:
```
[1/4] Installing Python dependencies...
[2/4] Checking PostgreSQL connection...
[3/4] Loading SQL functions into database...
[4/4] Starting FastAPI server...
  Server running at: http://localhost:8000
  API Docs at: http://localhost:8000/docs
```

### 2. Run the Test Script
In another terminal:
```bash
./test-metrics.sh
```

This will:
- ✅ Check API is running
- ✅ Get a dataset_id from fundamentals
- ✅ Calculate Market Cap (Calc MC)
- ✅ Show results in metrics_outputs table
- ✅ Display sample data

### 3. View Results in Database
```bash
clear-metrics.sh
```

---

## Manual Testing

### Option A: Using curl

**1. Get a dataset_id:**
```bash
psql ${DATABASE_URL} -t -c "
  SELECT DISTINCT dataset_id FROM cissa.fundamentals LIMIT 1;
"
```

Example output: `550e8400-e29b-41d4-a716-446655440000`

**2. Calculate Market Cap:**
```bash
DATASET_ID="550e8400-e29b-41d4-a716-446655440000"

curl -X POST http://localhost:8000/api/v1/metrics/calculate \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"metric_name\": \"Calc MC\"
  }" | python3 -m json.tool
```

**Expected response:**
```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "metric_name": "Calc MC",
  "results_count": 150,
  "results": [
    {
      "ticker": "BHP",
      "fiscal_year": 2023,
      "value": 245678900000.50
    },
    ...
  ],
  "status": "success"
}
```

### Option B: Using Swagger UI

1. Open browser: http://localhost:8000/docs
2. Find endpoint: **POST /api/v1/metrics/calculate**
3. Click "Try it out"
4. Fill in:
   ```json
   {
     "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
     "metric_name": "Calc MC"
   }
   ```
5. Click "Execute"
6. See response in browser

---

## Verify in Database

### Check metrics_outputs table

```bash
psql ${DATABASE_URL} << 'EOF'
SELECT 
  metric_name,
  COUNT(*) as count,
  MIN(metric_value) as min_value,
  MAX(metric_value) as max_value
FROM cissa.metrics_outputs
GROUP BY metric_name
ORDER BY metric_name;
EOF
```

Expected output for Calc MC:
```
 metric_name | count | min_value  |  max_value
─────────────┼───────┼────────────┼────────────
 Calc MC     |   150 | 1234567890 | 987654321000
```

### View sample records

```bash
DATASET_ID="550e8400-e29b-41d4-a716-446655440000"

psql ${DATABASE_URL} << EOF
SELECT 
  ticker,
  fiscal_year,
  metric_name,
  metric_value,
  created_at
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND metric_name = 'Calc MC'
LIMIT 10;
EOF
```

---

## Clear metrics_outputs (For Fresh Tests)

### Automated (Safe)

```bash
./clear-metrics.sh
```

This script:
- Shows current record count
- Shows breakdown by metric
- Asks for confirmation before deleting
- Verifies deletion was successful

### Manual SQL

```bash
psql ${DATABASE_URL} \
  -c "TRUNCATE TABLE cissa.metrics_outputs;"
```

---

## Test All Metrics

```bash
DATASET_ID="550e8400-e29b-41d4-a716-446655440000"

for METRIC in \
  "Calc MC" \
  "Calc Assets" \
  "Calc Assets" \
  "Calc Op Cost" \
  "Calc Non Op Cost" \
  "Profit Margin" \
  "Op Cost Margin %" \
  "FA Intensity" \
  "Book Equity" \
  "ROA"
do
  echo "Calculating $METRIC..."
  curl -s -X POST http://localhost:8000/api/v1/metrics/calculate \
    -H "Content-Type: application/json" \
    -d "{\"dataset_id\": \"$DATASET_ID\", \"metric_name\": \"$METRIC\"}" \
    | python3 -m json.tool | grep -E "metric_name|results_count"
done
```

---

## Full Testing Workflow

```bash
# Step 1: Clear old data
./clear-metrics.sh

# Step 2: Start the API (if not running)
./start-api.sh &

# Step 3: Run the full test
./test-metrics.sh

# Step 4: View detailed results
psql ${DATABASE_URL} \
  -c "SELECT * FROM cissa.metrics_outputs LIMIT 20;"

# Step 5: Stop the API
pkill -f "uvicorn"
```

---

## Troubleshooting

### Issue: "API is not running"
**Fix:** Start the API first
```bash
./start-api.sh
```

### Issue: "No datasets found in fundamentals"
**Fix:** Check if fundamentals table has data
```bash
psql ${DATABASE_URL} \
  -c "SELECT COUNT(*) FROM cissa.fundamentals WHERE metric_name = 'SPOT_SHARES';"
```

### Issue: "Error calculating metric"
**Fix:** Check API logs and PostgreSQL functions exist
```bash
psql ${DATABASE_URL} \
  -c "SELECT COUNT(*) FROM information_schema.routines WHERE routine_name LIKE 'fn_calc%';"
```

Should return: `15`

### Issue: "Connection refused"
**Fix:** Make sure PostgreSQL is running and credentials are correct
```bash
psql ${DATABASE_URL} -c "SELECT 1;"
```

---

## Database Connection String

**For any manual queries:**
```
${DATABASE_URL}
```

**Schema:** `cissa`  
**Key tables:**
- `cissa.fundamentals` — Input metrics (SPOT_SHARES, SHARE_PRICE, etc)
- `cissa.metrics_outputs` — Calculated results
- `cissa.dataset_versions` — Dataset metadata

---

## API Endpoints

```
GET  /                                    — Root (API info)
GET  /api/v1/metrics/health               — Health check
POST /api/v1/metrics/calculate            — Calculate a metric
GET  /api/v1/metrics/dataset/{id}/metrics/{name} — Get or calculate metric
```

**Interactive docs:** http://localhost:8000/docs

---

## Next: Ready for UI Integration

Once you've verified the API works:

1. **UI Button:** Add button to frontend that calls POST `/api/v1/metrics/calculate`
2. **User Flow:** User selects metric → Click "Calculate" → Results appear
3. **Clear Button:** Add "Clear Results" button that calls clear-metrics.sh

---
