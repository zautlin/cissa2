# Non Div ECF Not Calculated - Investigation Findings

**Investigation Date:** March 17, 2026  
**Status:** Root cause identified  
**Severity:** High (blocks all L1 metrics during ingestion)

---

## Quick Answer

Non Div ECF is not calculated during ingestion because:
- The `_auto_calculate_l1_metrics()` function **exists but is never called** 
- Phase 1 (Calc ECF) never runs, so Phase 2 (Non Div ECF) cannot run
- The parent metric (Calc ECF) is never stored in metrics_outputs
- Phase 2 queries metrics_outputs looking for Calc ECF and finds nothing

**File:** `/backend/database/etl/ingestion.py`  
**Method:** `load_dataset()`  
**Missing:** Call to `self._auto_calculate_l1_metrics(str(dataset_id))`  
**Fix:** Add 2 lines after line 199

---

## Investigation Documents

This investigation has produced 4 comprehensive analysis documents:

### 1. NON_DIV_ECF_ROOT_CAUSE_COMPLETE.md
**Purpose:** Complete technical analysis with full code flow  
**Contents:**
- Executive summary
- Code flow for Phase 1 & 2
- Phase configuration details
- Two-phase orchestration architecture
- SQL function details
- Database state analysis
- Error handling behavior
- Summary tables

**When to read:** For complete understanding of the entire system

---

### 2. NON_DIV_ECF_QUICK_REFERENCE.md
**Purpose:** Quick lookup and reference guide  
**Contents:**
- Problem in one sentence
- File locations and line numbers
- Phase configuration tables
- SQL formula (Non Div ECF = Calc ECF + DIVIDENDS)
- Dependency chain
- Code flow comparison (broken vs. expected)
- Database state table
- Error behavior
- Quick verification query
- Workaround instructions

**When to read:** For quick understanding and code references

---

### 3. NON_DIV_ECF_CALCULATION_ROOT_CAUSE.md
**Purpose:** Detailed root cause analysis  
**Contents:**
- Root cause explanation
- Expected vs. actual flow
- Two-phase architecture details
- Non Div ECF function requirements
- Metric functions mapping
- Orchestration endpoints
- Database state after ingestion
- Missing call analysis
- Error conditions
- Commit logic verification
- Summary table

**When to read:** For detailed understanding of what should happen

---

### 4. NON_DIV_ECF_SUMMARY.txt
**Purpose:** Visual summary with ASCII diagrams  
**Contents:**
- Root cause statement
- Two-phase execution flow chart
- Code organization tree
- Database state comparison (current vs. expected)
- Phase 1 → Phase 2 dependency diagram
- SQL flow diagram
- Commit logic explanation
- Missing piece analysis
- Error handling explanation
- Verification steps

**When to read:** For visual understanding and architecture overview

---

## Key Findings Summary

| Aspect | Finding | Impact |
|--------|---------|--------|
| **Root Cause** | _auto_calculate_l1_metrics() never called | Critical |
| **Phase 1 Logic** | Correctly implemented in metrics_service.py | None |
| **Phase 2 Logic** | Correctly implemented in metrics_service.py | None |
| **Non Div ECF Placement** | Correctly in Phase 2 configuration | None |
| **SQL Function** | Correctly implemented | None |
| **Commit Logic** | Correct - each metric commits individually | None |
| **Database State** | metrics_outputs table empty after ingestion | Critical |
| **Parent Metric (Calc ECF)** | Not stored (Phase 1 never runs) | Critical |
| **Error Handling** | Silent failure (logs warning) | Moderate |
| **Workaround Available** | Manual API call works | Moderate |
| **Fix Complexity** | Low (2-line addition) | None |

---

## Code Locations Reference

### Entry Point (Missing Call)
- **File:** `/backend/database/etl/ingestion.py`
- **Method:** `load_dataset()`
- **Lines:** 146-212
- **Issue:** Doesn't call `_auto_calculate_l1_metrics()`

### Metrics Calculation Function (Defined but Unused)
- **File:** `/backend/database/etl/ingestion.py`
- **Method:** `_auto_calculate_l1_metrics()`
- **Lines:** 214-244, 246-335
- **Status:** Exists but never invoked

### Two-Phase Orchestration
- **File:** `/backend/app/services/metrics_service.py`
- **Method:** `calculate_batch_metrics()`
- **Lines:** 494-647
- **Phase 1 Loop:** Lines 567-591
- **Phase 2 Loop:** Lines 593-619

### Phase Configuration
- **File:** `/backend/app/services/metrics_service.py`
- **Dictionary:** `L1_METRICS_PHASES`
- **Lines:** 523-540
- **Phase 1 Metrics:** 11 total
- **Phase 2 Metrics:** 2 total (Non Div ECF, Calc FY TSR PREL)

### SQL Functions
- **File:** `/backend/database/schema/functions.sql`
- **Calc ECF:** Lines 392-448 (Phase 1 - reads fundamentals)
- **Non Div ECF:** Lines 454-480 (Phase 2 - reads metrics_outputs)

### Runtime Orchestration (Manual Workaround)
- **File:** `/backend/app/api/v1/endpoints/orchestration.py`
- **Endpoint:** `POST /api/v1/metrics/calculate-l1`
- **Lines:** 263-322
- **Purpose:** Runtime calculation via API (not used during ingestion)

---

## Database State Analysis

### After Ingestion (Current - Broken)
```
companies ......................... POPULATED (from Base.csv)
fiscal_year_mapping .............. POPULATED (from FY Dates.csv)
raw_data ......................... POPULATED (from CSV)
dataset_versions ................. POPULATED (metadata)
imputation_audit_trail ........... POPULATED (duplicates log)
metrics_outputs .................. EMPTY ✗ (Phase 1 & 2 never run)
```

### After Ingestion (Expected - Fixed)
```
companies ......................... POPULATED
fiscal_year_mapping .............. POPULATED
raw_data ......................... POPULATED
dataset_versions ................. POPULATED
imputation_audit_trail ........... POPULATED
metrics_outputs .................. POPULATED ✓
  ├─ 11 Phase 1 metrics
  └─ 2 Phase 2 metrics (including Non Div ECF)
```

---

## The Fix

**Location:** `/backend/database/etl/ingestion.py`, method `load_dataset()`, after line 199

**Add these lines:**
```python
# Trigger automatic L1 metrics calculation
metrics_result = self._auto_calculate_l1_metrics(str(dataset_id))
result['l1_metrics'] = metrics_result
```

**Impact:**
- Phase 1 metrics automatically calculated
- Calc ECF inserted into metrics_outputs
- Phase 1 results committed to database
- Phase 2 metrics automatically calculated
- Non Div ECF successfully reads Calc ECF
- metrics_outputs populated with all L1 metrics
- No manual API calls required

---

## Verification Steps

### Step 1: Verify Metrics Are Calculated
```sql
SELECT COUNT(*) FROM metrics_outputs
WHERE dataset_id = 'YOUR_DATASET_ID'
  AND output_metric_name IN ('Calc ECF', 'Non Div ECF');
```
Expected: > 0 rows

### Step 2: Verify Phase 1 Metrics
```sql
SELECT DISTINCT output_metric_name FROM metrics_outputs
WHERE dataset_id = 'YOUR_DATASET_ID'
ORDER BY output_metric_name;
```
Expected: Should include 'Calc ECF' and 11 other Phase 1 metrics

### Step 3: Verify Formula
```sql
SELECT 
  mo.output_metric_value as non_div_ecf,
  COALESCE((SELECT output_metric_value FROM metrics_outputs mo2
   WHERE mo2.dataset_id = mo.dataset_id
     AND mo2.ticker = mo.ticker
     AND mo2.fiscal_year = mo.fiscal_year
     AND mo2.output_metric_name = 'Calc ECF'), 0) as calc_ecf,
  COALESCE((SELECT numeric_value FROM fundamentals f
   WHERE f.dataset_id = mo.dataset_id
     AND f.ticker = mo.ticker
     AND f.fiscal_year = mo.fiscal_year
     AND f.metric_name = 'DIVIDENDS'), 0) as dividends
FROM metrics_outputs mo
WHERE dataset_id = 'YOUR_DATASET_ID'
  AND output_metric_name = 'Non Div ECF'
LIMIT 5;
```
Expected: non_div_ecf ≈ calc_ecf + dividends

---

## Workaround (Until Fix Applied)

After ingestion completes, manually trigger metrics calculation:

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
1. Calculate all Phase 1 metrics
2. Insert Calc ECF into metrics_outputs
3. Calculate Phase 2 metrics (including Non Div ECF)
4. Populate metrics_outputs with all L1 metrics

**Execution time:** ~20-30 seconds

---

## Summary

| Aspect | Status | Notes |
|--------|--------|-------|
| **Function exists** | ✓ Yes | ingestion.py:214-244, 246-335 |
| **Function called** | ✗ No | Missing from load_dataset() |
| **Phase 1 logic** | ✓ Correct | metrics_service.py:567-591 |
| **Phase 2 logic** | ✓ Correct | metrics_service.py:593-619 |
| **Commit logic** | ✓ Correct | Each metric commits after insert |
| **Non Div ECF config** | ✓ Yes | In Phase 2 dictionary |
| **SQL function** | ✓ Works | fn_calc_non_div_ecf exists |
| **Calc ECF in DB** | ✗ No | Phase 1 never runs |
| **Non Div ECF calculated** | ✗ No | Phase 2 never runs |
| **metrics_outputs populated** | ✗ No | Empty after ingestion |
| **Error handling** | ✓ Graceful | Silent failure on 0 rows |
| **Fix complexity** | ✓ Low | 2-line addition |
| **Workaround available** | ✓ Yes | Manual API call |

---

## Investigation Conclusion

**Root Cause:** Missing function call in ingestion orchestration

**Impact:** All L1 metrics unavailable after ingestion

**Solution:** Add 2 lines to call _auto_calculate_l1_metrics()

**Complexity:** Very low (< 5 minutes to implement)

**Testing:** Simple SQL query to verify metrics in database

**Documentation:** All documentation created and referenced above

---

## Document Map

Choose your reading path:

**For Quick Understanding:**
1. Start here (this file)
2. Read: NON_DIV_ECF_QUICK_REFERENCE.md

**For Complete Understanding:**
1. Start here (this file)
2. Read: NON_DIV_ECF_SUMMARY.txt (visual overview)
3. Read: NON_DIV_ECF_ROOT_CAUSE_COMPLETE.md (detailed analysis)

**For Implementation:**
1. Review: NON_DIV_ECF_QUICK_REFERENCE.md (code locations)
2. Refer to: NON_DIV_ECF_ROOT_CAUSE_COMPLETE.md (database state)
3. Execute the fix (2-line addition)
4. Run verification steps

**For System Design Review:**
1. Read: NON_DIV_ECF_ROOT_CAUSE_COMPLETE.md (sections on architecture)
2. Review: Code flow diagrams in NON_DIV_ECF_SUMMARY.txt

---

**Created:** March 17, 2026  
**Absolute File Paths:**
- `/home/ubuntu/cissa/NON_DIV_ECF_FINDINGS_INDEX.md` (this file)
- `/home/ubuntu/cissa/NON_DIV_ECF_QUICK_REFERENCE.md`
- `/home/ubuntu/cissa/NON_DIV_ECF_ROOT_CAUSE_COMPLETE.md`
- `/home/ubuntu/cissa/NON_DIV_ECF_CALCULATION_ROOT_CAUSE.md`
- `/home/ubuntu/cissa/NON_DIV_ECF_SUMMARY.txt`
