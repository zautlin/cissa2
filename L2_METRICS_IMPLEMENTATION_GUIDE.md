# L2 Metrics Implementation - Step-by-Step Testing Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ FastAPI Endpoint (POST /api/v1/metrics/calculate-l2)        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ MetricsService.calculate_l2_metrics()                       │
│  ├─ _fetch_l1_metrics(dataset_id, param_set_id)            │
│  │  └─ Query metrics_outputs where level='L1'              │
│  ├─ _fetch_fundamentals(dataset_id, country)              │
│  │  └─ Query fundamentals table                             │
│  ├─ Call pure calculate_L2_metrics(l1_df, annual_df)       │
│  │  └─ Returns results_df                                   │
│  └─ _insert_l2_metrics(dataset_id, param_set_id, results)  │
│     └─ Insert into metrics_outputs                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ Pure Calculation Function                                   │
│ example_calculations.src.engine.calculation.calculate_L2... │
│ (NO database access - just math)                            │
└─────────────────────────────────────────────────────────────┘
```

## Testing Flow (Single Process)

### 1. **Setup Phase** (5 minutes)
```bash
# Step 1a: Start PostgreSQL
docker-compose up -d postgres  # if using Docker

# Step 1b: Verify database
psql postgresql://postgres:PASSWORD@localhost:5432/rozetta -c "\d cissa.metrics_outputs"

# Step 1c: Load sample dataset and L1 metrics (if not already present)
python backend/scripts/seed_test_data.py  # (optional)
```

### 2. **Test L1 Metrics** (Prerequisite)
```bash
# Make sure L1 metrics exist for your test dataset
curl -X POST http://localhost:8000/api/v1/metrics/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "YOUR_DATASET_ID",
    "metric_name": "Calc MC"
  }'

# Verify L1 results in database
psql postgresql://postgres:PASSWORD@localhost:5432/rozetta \
  -c "SELECT COUNT(*) FROM cissa.metrics_outputs 
      WHERE dataset_id = 'YOUR_DATASET_ID';"
```

### 3. **Test L2 Calculation via CLI** (Simplest)
```bash
# Run CLI script (this calls the pure function)
cd /home/ubuntu/cissa
python backend/app/cli/run_l2_metrics.py \
  --dataset-id YOUR_DATASET_ID \
  --param-set-id YOUR_PARAM_SET_ID \
  --country AUS

# Expected output:
# ✓ Fetched 150 L1 metrics for ticker BHP
# ✓ Fetched 150 fundamentals records
# ✓ Calculated 1500 L2 metrics (10 metrics × 150 years)
# ✓ Inserted 1500 L2 metrics into metrics_outputs
# ✓ Complete in 45.2 seconds
```

### 4. **Test L2 Calculation via API** (HTTP)
```bash
# Start FastAPI server
cd /home/ubuntu/cissa/backend
uvicorn app.main:app --reload --port 8000

# In another terminal, call the endpoint
curl -X POST http://localhost:8000/api/v1/metrics/calculate-l2 \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "YOUR_DATASET_ID",
    "param_set_id": "YOUR_PARAM_SET_ID",
    "inputs": {
      "country": "AUS",
      "currency": "AUD",
      "error_tolerance": 0.8,
      "approach_to_ke": "Floating",
      "beta_rounding": 0.1,
      "risk_premium": 0.05,
      "benchmark_return": 0.075,
      "incl_franking": "Yes",
      "frank_tax_rate": 0.3,
      "value_franking_cr": 0.75
    }
  }'

# Expected response:
# {
#   "status": "success",
#   "dataset_id": "YOUR_DATASET_ID",
#   "param_set_id": "YOUR_PARAM_SET_ID",
#   "metrics_inserted": 1500,
#   "calculation_time_seconds": 45.2,
#   "message": "Calculated L2 metrics for 1 ticker across 60 years"
# }
```

### 5. **Verify Results in Database**
```bash
# Count L2 metrics inserted
psql postgresql://postgres:PASSWORD@localhost:5432/rozetta \
  -c "SELECT metric_name, COUNT(*) as count
      FROM cissa.metrics_outputs
      WHERE dataset_id = 'YOUR_DATASET_ID'
      AND metric_level = 'L2'
      GROUP BY metric_name
      ORDER BY count DESC;"

# Expected output (example):
#          metric_name          | count
# ─────────────────────────────┼───────
#  Beta (1Y)                   |   150
#  Cost of Equity (1Y)         |   150
#  Beta (3Y)                   |   150
#  Cost of Equity (3Y)         |   150
#  ... more metrics ...
```

## Implementation Steps (What We'll Build)

### **Phase 1: ORM & Schemas** (15 minutes)
Files to create:
- `backend/app/models/metrics_output.py` — SQLAlchemy ORM model for metrics_outputs
- Update `backend/app/models.py` — Add L2 request/response schemas

### **Phase 2: Repository Layer** (15 minutes)
Files to create:
- `backend/app/repositories/metrics_repository.py` — Query L1 metrics and fundamentals

### **Phase 3: Service Layer** (30 minutes)
Files to create:
- `backend/app/services/l2_metrics_service.py` — Orchestration layer (fetch → calc → insert)

### **Phase 4: Pure Calculation Function** (20 minutes)
Files to modify:
- `example-calculations/src/engine/calculation.py` — Refactor to pure function

### **Phase 5: FastAPI Routes** (15 minutes)
Files to create:
- `backend/app/api/v1/endpoints/l2_metrics.py` — POST /api/v1/metrics/calculate-l2

### **Phase 6: CLI Script** (10 minutes)
Files to create:
- `backend/app/cli/run_l2_metrics.py` — CLI for testing and batch processing

### **Phase 7: Testing Guide** (5 minutes)
Files to create:
- `TESTING_L2_METRICS.md` — Complete testing instructions

## What You Can Test

### Immediate (After implementation):
1. ✅ Call CLI script with single dataset
2. ✅ Verify L2 metrics inserted into database
3. ✅ Compare L2 calculation results with old approach
4. ✅ Check calculation time and performance

### Near-term:
1. ✅ Call FastAPI endpoint from browser/curl
2. ✅ Test with multiple param_sets on same dataset
3. ✅ Test error handling (missing L1 data, invalid param_set)
4. ✅ Test with different countries/currencies

### Advanced:
1. 🔜 Background task (Celery) for long-running calculations
2. 🔜 Progress polling endpoint
3. 🔜 Batch processing multiple datasets
4. 🔜 Scheduled job (APScheduler)

## Data Requirements for Testing

Before testing, ensure you have:

1. **Dataset in `dataset_versions`**
   ```sql
   SELECT dataset_id, dataset_name FROM cissa.dataset_versions LIMIT 1;
   ```
   
2. **L1 Metrics in `metrics_outputs`**
   ```sql
   SELECT DISTINCT dataset_id, COUNT(*) 
   FROM cissa.metrics_outputs 
   WHERE metric_level = 'L1'
   GROUP BY dataset_id;
   ```
   
3. **Fundamentals data in `fundamentals`**
   ```sql
   SELECT DISTINCT dataset_id, COUNT(*) 
   FROM cissa.fundamentals 
   GROUP BY dataset_id;
   ```
   
If missing, run the data ingestion pipeline first:
```bash
python backend/app/cli/ingest_dataset.py --file path/to/data.xlsx
```

## Expected Performance

Based on current code:
- **L1 Metrics**: 3,600 metrics (150 tickers × 24 years) in ~10 seconds
- **L2 Metrics**: 1,500 metrics (1 ticker × 60 years × 10 metric types) in ~45 seconds
- **End-to-End**: L1 + L2 in ~60 seconds

## Rollback Plan (if needed)

If L2 calculation fails:
```sql
-- Delete L2 metrics for this dataset/param_set
DELETE FROM cissa.metrics_outputs
WHERE dataset_id = 'YOUR_DATASET_ID'
AND param_set_id = 'YOUR_PARAM_SET_ID'
AND metric_level = 'L2';
```

---

## Ready to Start Building?

Reply with:
- **Start**: Begin implementation (build all files)
- **Dry-run**: Show what files will be created first
- **Questions**: Ask specific questions before building

Estimated time: 90 minutes for full implementation + testing
