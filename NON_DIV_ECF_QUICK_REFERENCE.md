# Non Div ECF Calculation - Quick Reference

## The Problem in One Sentence

**The `_auto_calculate_l1_metrics()` function exists in the codebase but is never called during data ingestion, so Non Div ECF is never calculated.**

---

## File Locations

| File | What's There | Lines |
|------|--------------|-------|
| `/backend/database/etl/ingestion.py` | Entry point; defines metrics functions | 214-244, 246-335 |
| `/backend/app/services/metrics_service.py` | Two-phase orchestration logic | 494-647 |
| `/backend/app/services/metrics_service.py` | Phase configuration | 523-540 |
| `/backend/database/schema/functions.sql` | Non Div ECF SQL function | 454-480 |
| `/backend/app/api/v1/endpoints/orchestration.py` | Runtime API endpoint | 263-322 |

---

## Phase Configuration

### METRIC_FUNCTIONS Mapping
From `/backend/app/services/metrics_service.py`, lines 21-44:

```python
"Calc ECF": ("fn_calc_ecf", "ecf", False),              # Phase 1
"Non Div ECF": ("fn_calc_non_div_ecf", "non_div_ecf", False),  # Phase 2 ← Depends on Phase 1
```

### L1_METRICS_PHASES Dictionary
From `/backend/app/services/metrics_service.py`, lines 523-540:

```python
# PHASE 1: Base metrics (read from fundamentals)
"Calc ECF": (1, False),

# PHASE 2: Derived metrics (read from metrics_outputs)
"Non Div ECF": (2, False),  # ← Requires Calc ECF in metrics_outputs
```

---

## SQL Formula

### Non Div ECF = Calc ECF + DIVIDENDS

From `/backend/database/schema/functions.sql`, lines 462-475:

```sql
SELECT
  mo.ticker,
  mo.fiscal_year,
  (COALESCE(mo.output_metric_value, 0) + COALESCE(f.numeric_value, 0)) AS non_div_ecf
FROM cissa.metrics_outputs mo
LEFT JOIN cissa.fundamentals f
  ON mo.ticker = f.ticker
   AND mo.fiscal_year = f.fiscal_year
   AND mo.dataset_id = f.dataset_id
   AND f.metric_name = 'DIVIDENDS'
 WHERE
   mo.dataset_id = p_dataset_id
   AND mo.output_metric_name = 'Calc ECF'  ← CRITICAL REQUIREMENT
```

---

## Dependency Chain

```
Raw Data (CSV)
    ↓
Fundamentals Table
    ↓
Phase 1: Calc ECF (fn_calc_ecf)
    ↓
    ├─→ metrics_outputs (Calc ECF rows)
    │
    ├─ Database Commit ← REQUIRED before Phase 2
    │
    ↓
Phase 2: Non Div ECF (fn_calc_non_div_ecf)
    ├─→ Reads from metrics_outputs (Calc ECF)
    └─→ Reads from Fundamentals (DIVIDENDS)
    ↓
    └─→ metrics_outputs (Non Div ECF rows)
```

---

## Code Flow

### Current (Broken)
```
ingestion.load_dataset()
  ├─ Load raw_data ✓
  ├─ Update metadata ✓
  └─ ✗ MISSING: Call to _auto_calculate_l1_metrics()
  
Result: metrics_outputs table is EMPTY
```

### Expected (What Should Happen)
```
ingestion.load_dataset()
  ├─ Load raw_data ✓
  ├─ Update metadata ✓
  ├─ Call _auto_calculate_l1_metrics() ← MISSING
  │  ├─ Call calculate_batch_metrics()
  │  │  ├─ PHASE 1: Calculate all base metrics
  │  │  │  ├─ Calc MC ✓
  │  │  │  ├─ Calc Assets ✓
  │  │  │  ├─ ...
  │  │  │  ├─ Calc ECF ✓ (inserts to metrics_outputs)
  │  │  │  └─ Commit Phase 1 ✓
  │  │  │
  │  │  └─ PHASE 2: Calculate derived metrics
  │  │     ├─ Non Div ECF ✓ (reads Calc ECF from metrics_outputs)
  │  │     └─ Calc FY TSR PREL ✓
  │  │
  │  └─ Return metrics result
  │
  └─ Return with l1_metrics in result dict

Result: metrics_outputs table is POPULATED
```

---

## Current Database State After Ingestion

| Table | Status | Why |
|-------|--------|-----|
| companies | ✓ Populated | Loaded from Base.csv |
| fiscal_year_mapping | ✓ Populated | Loaded from FY Dates.csv |
| raw_data | ✓ Populated | Loaded from CSV |
| dataset_versions | ✓ Populated | Metadata inserted |
| imputation_audit_trail | ✓ Populated | Duplicates logged |
| **metrics_outputs** | **✗ EMPTY** | **Phase 1 & 2 never run** |

---

## Error Behavior

When Phase 2 runs without Phase 1 data:

```python
# fn_calc_non_div_ecf executes
SELECT ... FROM metrics_outputs WHERE output_metric_name = 'Calc ECF'

# Result: No rows (Calc ECF never inserted)

# Non Div ECF calculation returns 0 rows

# Code logs: "Non Div ECF: 0 rows calculated (parent metric may not exist)"

# Pipeline continues (SILENT FAILURE)
```

---

## Two-Phase Execution Details

### Phase 1 Loop (metrics_service.py, lines 567-591)

```python
for metric_name in phase1_metrics:
    row_count = await self._execute_sql_function(metric_name, dataset_id)
    # Each call:
    # 1. Executes SQL function
    # 2. Gets results
    # 3. Inserts to metrics_outputs via _insert_metric_results_with_metadata()
    # 4. Calls await self.session.commit() at line 399
```

**Key Point:** Each Phase 1 metric is committed individually, ensuring data is visible for the next metric and for Phase 2.

### Between Phase 1 & Phase 2

```
Phase 1 Complete
    ↓
All 11 metrics committed to metrics_outputs
    ↓
Database state ready for Phase 2 reads
    ↓
Phase 2 Begins
```

### Phase 2 Loop (metrics_service.py, lines 593-619)

```python
if phase2_metrics:
    for metric_name in phase2_metrics:
        row_count = await self._execute_sql_function(metric_name, dataset_id)
        # At this point:
        # - metrics_outputs contains Phase 1 results
        # - Non Div ECF can read Calc ECF
        # - Query returns rows
```

---

## Quick Verification Query

To verify if Non Div ECF is being calculated:

```sql
SELECT COUNT(*) as count, output_metric_name
FROM metrics_outputs
WHERE dataset_id = 'YOUR_DATASET_ID'
  AND output_metric_name IN ('Calc ECF', 'Non Div ECF')
GROUP BY output_metric_name;
```

**Expected After Proper Ingestion:**
```
 count | output_metric_name
-------+--------------------
  100+ | Calc ECF
  100+ | Non Div ECF
```

**Current (Broken):**
```
 count | output_metric_name
-------+--------------------
    0  | (no rows)
```

---

## Workaround (Until Fix Applied)

After ingestion, manually trigger metric calculation:

```bash
curl -X POST http://localhost:8000/api/v1/metrics/calculate-l1 \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "YOUR_DATASET_ID",
    "param_set_id": "YOUR_PARAM_SET_ID",
    "concurrency": 4,
    "max_retries": 3
  }'
```

This will:
1. Calculate Phase 1 metrics (Calc ECF)
2. Insert to metrics_outputs
3. Calculate Phase 2 metrics (Non Div ECF)
4. Return results

**Execution Time:** ~20-30 seconds

---

## The Fix

**File:** `/backend/database/etl/ingestion.py`

**Location:** End of `load_dataset()` method (after line 199)

**Add:**
```python
# Trigger automatic L1 metrics calculation
metrics_result = self._auto_calculate_l1_metrics(str(dataset_id))
result['l1_metrics'] = metrics_result
```

**Result:** Metrics calculated automatically during ingestion, Non Div ECF available immediately.

---

## Test Cases

### Test 1: Phase 1 Metrics Inserted
```sql
SELECT COUNT(*) FROM metrics_outputs
WHERE dataset_id = 'test_dataset'
  AND output_metric_name = 'Calc ECF'
  AND output_metric_value IS NOT NULL;
```
Expected: > 0

### Test 2: Phase 2 Metrics Inserted
```sql
SELECT COUNT(*) FROM metrics_outputs
WHERE dataset_id = 'test_dataset'
  AND output_metric_name = 'Non Div ECF'
  AND output_metric_value IS NOT NULL;
```
Expected: > 0

### Test 3: Non Div ECF Formula Verification
```sql
SELECT 
  mo.ticker,
  mo.fiscal_year,
  mo.output_metric_value as non_div_ecf,
  (SELECT output_metric_value FROM metrics_outputs mo2
   WHERE mo2.dataset_id = mo.dataset_id
     AND mo2.ticker = mo.ticker
     AND mo2.fiscal_year = mo.fiscal_year
     AND mo2.output_metric_name = 'Calc ECF') as calc_ecf,
  (SELECT numeric_value FROM fundamentals f
   WHERE f.dataset_id = mo.dataset_id
     AND f.ticker = mo.ticker
     AND f.fiscal_year = mo.fiscal_year
     AND f.metric_name = 'DIVIDENDS') as dividends
FROM metrics_outputs mo
WHERE dataset_id = 'test_dataset'
  AND output_metric_name = 'Non Div ECF'
LIMIT 5;
```
Expected: non_div_ecf ≈ calc_ecf + dividends (within floating point precision)

---

## Summary

| Aspect | Status |
|--------|--------|
| Root Cause | Missing function call in ingestion |
| Function Exists | Yes |
| Function Called | **No** |
| Phase 1 Logic | Correct |
| Phase 2 Logic | Correct |
| Database Commit Logic | Correct |
| Non Div ECF in Phase 2 | Yes |
| Metrics Calculated | No |
| metrics_outputs Populated | No |
| Fix Complexity | Low (1 line addition) |
| Impact | All L1 metrics unavailable |
