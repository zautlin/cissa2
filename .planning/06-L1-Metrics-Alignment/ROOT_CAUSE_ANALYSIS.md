# ROOT CAUSE ANALYSIS: NON_DIV_ECF & FY_TSR_PREL Zero Records

**Date:** 2026-03-09  
**Status:** DIAGNOSED  
**Severity:** HIGH (Blocks data integrity)  

---

## Executive Summary

**Finding:** NON_DIV_ECF and FY_TSR_PREL return 0 records because they are **DERIVED METRICS** that depend on their parent metrics (ECF and FY_TSR) being already calculated and inserted into `metrics_outputs` table BEFORE they run.

**Current behavior:** All 12 metrics calculated simultaneously in single batch → derived metrics run when parent metrics not yet in database → return 0 rows.

**Root cause:** SQL function implementation reads from `metrics_outputs` table instead of base data.

---

## Technical Evidence

### SQL Functions - Dependency Pattern

#### fn_calc_non_div_ecf (Line 660-683)
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
  AND mo.output_metric_name = 'Calc ECF'  ← READS ECF FROM metrics_outputs
ORDER BY mo.ticker, mo.fiscal_year;
```

**Key issue:** Line 680 filters for `output_metric_name = 'Calc ECF'` → reads ECF from metrics_outputs table

**When ECF is calculated:** Function returns 11,000 rows ✓  
**When ECF not yet inserted:** Function returns 0 rows ✗

---

#### fn_calc_fy_tsr_prel (Line 855-874)
```sql
SELECT
  mo.ticker,
  mo.fiscal_year,
  (COALESCE(mo.output_metric_value, 0) + 1) AS fy_tsr_prel
FROM cissa.metrics_outputs mo
WHERE
  mo.dataset_id = p_dataset_id
  AND mo.param_set_id = p_param_set_id
  AND mo.output_metric_name = 'Calc FY TSR'  ← READS FY_TSR FROM metrics_outputs
ORDER BY mo.ticker, mo.fiscal_year;
```

**Key issue:** Line 871 filters for `output_metric_name = 'Calc FY TSR'` → reads FY_TSR from metrics_outputs table

**When FY_TSR is calculated:** Function returns 11,000 rows ✓  
**When FY_TSR not yet inserted:** Function returns 0 rows ✗

---

### Comparison: Base Metrics vs. Derived Metrics

| Metric | Type | Data Source | Dependency | Status |
|--------|------|-------------|-----------|--------|
| C_MC, C_ASSETS, OA, OP_COST, etc. | **Base** | `fundamentals` table | None | 11,000 ✓ |
| LAG_MC, ECF, EE, FY_TSR | **Base Temporal** | `fundamentals` + window functions | None | 11,000 ✓ |
| **NON_DIV_ECF** | **DERIVED** | `metrics_outputs` (ECF) | Depends on ECF | **0 ✗** |
| **FY_TSR_PREL** | **DERIVED** | `metrics_outputs` (FY_TSR) | Depends on FY_TSR | **0 ✗** |

---

## Root Cause: Batch Execution Order

### Current Execution Flow (BROKEN)
```
CALCULATE ALL 12 METRICS SIMULTANEOUSLY:
├─ fn_calc_market_cap()           → calculates from fundamentals ✓
├─ fn_calc_operating_assets()     → calculates from fundamentals ✓
├─ ...
├─ fn_calc_ecf()                  → calculates from fundamentals ✓
├─ fn_calc_fy_tsr()               → calculates from fundamentals ✓
├─ fn_calc_non_div_ecf()          → QUERIES metrics_outputs FOR ECF (NOT YET INSERTED) → 0 rows ✗
└─ fn_calc_fy_tsr_prel()          → QUERIES metrics_outputs FOR FY_TSR (NOT YET INSERTED) → 0 rows ✗

THEN INSERT ALL RESULTS:
└─ INSERT 10 successful metrics + 2 empty metrics → metrics_outputs
```

**Problem:** Derived metrics queries metrics_outputs table BEFORE that table has been populated with parent metrics.

---

## Recommended Fixes

### OPTION A: Two-Phase Batch (RECOMMENDED - Simple, Low Risk)

**Approach:** Split calculation into two sequential batches with database commit between them.

```
PHASE 1: Calculate & Insert Base Metrics (10 metrics)
├─ C_MC, C_ASSETS, OA, OP_COST, NON_OP_COST, TAX_COST, XO_COST
├─ LAG_MC, ECF, EE, FY_TSR
└─ INSERT all 10 into metrics_outputs → COMMIT ✓

PHASE 2: Calculate & Insert Derived Metrics (2 metrics)
├─ NON_DIV_ECF (now reads ECF from metrics_outputs - FOUND)
├─ FY_TSR_PREL (now reads FY_TSR from metrics_outputs - FOUND)
└─ INSERT both into metrics_outputs → COMMIT ✓
```

**Pros:**
- Minimal code change (add phase grouping + commit between)
- Works immediately
- Maintains current SQL function structure
- Easy to understand and maintain

**Cons:**
- Two database round trips (negligible: 2 seconds + 1 second = 3 seconds)
- Slightly longer total execution time (but acceptable)

**Implementation Location:** `backend/app/services/metrics_service.py` in `calculate_batch_metrics()` method

---

### OPTION B: Refactor SQL Functions (Advanced - Better Long-term)

**Approach:** Rewrite fn_calc_non_div_ecf and fn_calc_fy_tsr_prel to read from fundamentals instead of metrics_outputs.

**For NON_DIV_ECF:**
```sql
CREATE OR REPLACE FUNCTION cissa.fn_calc_non_div_ecf(p_dataset_id UUID)
RETURNS TABLE (ticker TEXT, fiscal_year INTEGER, non_div_ecf NUMERIC) AS $$
BEGIN
  RETURN QUERY
  SELECT
    ecf.ticker,
    ecf.fiscal_year,
    ecf.ecf + COALESCE(div.numeric_value, 0) AS non_div_ecf
  FROM (SELECT * FROM fn_calc_ecf(p_dataset_id)) ecf
  LEFT JOIN fundamentals div
    ON ecf.ticker = div.ticker
    AND ecf.fiscal_year = div.fiscal_year
    AND ecf.dataset_id = p_dataset_id
    AND div.metric_name = 'DIVIDENDS'
  WHERE ecf.dataset_id = p_dataset_id;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

**Pros:**
- Single batch for all 12 metrics (no phase split needed)
- More maintainable long-term
- Better SQL architecture
- Derived metrics become composable functions

**Cons:**
- More refactoring required (~50 lines of SQL)
- Risk of edge cases (nested function calls)
- Requires testing each modified function

---

### OPTION C: Combined Materialized View (Alternative)

**Approach:** Use PostgreSQL materialized view to pre-calculate derived metrics.

```sql
CREATE MATERIALIZED VIEW mv_l1_metrics AS
SELECT * FROM fn_calc_market_cap(...)
UNION ALL
SELECT * FROM fn_calc_non_div_ecf(...)  -- Can read ECF from base metrics
UNION ALL
...;

REFRESH MATERIALIZED VIEW mv_l1_metrics;
```

**Pros:**
- Pure SQL solution
- Can be scheduled separately
- Good for production caching

**Cons:**
- More complex SQL
- Requires managing materialized view refresh
- Harder to debug issues

---

## Immediate Workaround (For Current Test Run)

### Option 1: Manual Two-Step Execution
```bash
# Step 1: Calculate base metrics
curl -X POST /api/v1/metrics/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "your-dataset-id",
    "metric_names": ["Calc MC", "Calc Assets", "Calc OA", "Calc Op Cost", 
                     "Calc Non Op Cost", "Calc Tax Cost", "Calc XO Cost",
                     "LAG_MC", "ECF", "EE", "FY_TSR"]
  }'

# Step 2: Wait for database commit, then calculate derived metrics
curl -X POST /api/v1/metrics/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "your-dataset-id",
    "metric_names": ["NON_DIV_ECF", "FY_TSR_PREL"]
  }'
```

### Option 2: Direct SQL Query
```sql
-- Insert NON_DIV_ECF after ECF exists in metrics_outputs
INSERT INTO metrics_outputs 
SELECT 
  dataset_id, param_set_id, ticker, fiscal_year, 'Non-Div ECF', value
FROM fn_calc_non_div_ecf('your-dataset-id')
WHERE (ticker, fiscal_year) IN (
  SELECT DISTINCT ticker, fiscal_year 
  FROM metrics_outputs 
  WHERE output_metric_name = 'Calc ECF'
);

-- Insert FY_TSR_PREL after FY_TSR exists
INSERT INTO metrics_outputs 
SELECT 
  dataset_id, param_set_id, ticker, fiscal_year, 'FY TSR Prel', value
FROM fn_calc_fy_tsr_prel('your-dataset-id', 'your-param-set-id')
WHERE (ticker, fiscal_year) IN (
  SELECT DISTINCT ticker, fiscal_year 
  FROM metrics_outputs 
  WHERE output_metric_name = 'Calc FY TSR'
);
```

---

## Impact Assessment

### Current State (BROKEN)
```
metrics_outputs after batch run:
├─ Calc MC: 11,000 records ✓
├─ Calc Assets: 11,000 records ✓
├─ Calc OA: 11,000 records ✓
├─ LAG_MC: 10,500 records ✓
├─ ECF: 6,954 records ✓
├─ EE: 11,000 records ✓
├─ FY_TSR: 6,954 records ✓
├─ Non-Div ECF: 0 records ✗ (depends on ECF)
└─ FY_TSR Prel: 0 records ✗ (depends on FY_TSR)

Total: 73,408 records (should be 83,362)
Missing: 9,954 derived metric records
```

### After Fix (Option A)
```
metrics_outputs after Phase 1 + Phase 2:
├─ Calc MC: 11,000 records ✓
├─ ... [all 10 base metrics]
├─ ECF: 6,954 records ✓
├─ FY_TSR: 6,954 records ✓
├─ Non-Div ECF: 6,954 records ✓ (now reads from ECF)
└─ FY_TSR Prel: 6,954 records ✓ (now reads from FY_TSR)

Total: 83,362 records ✓ (expected)
Coverage: 100% (all 12 metrics complete)
```

---

## Recommended Next Steps

1. **Immediate:** Implement Option A (two-phase batch)
   - Modify `calculate_batch_metrics()` in metrics_service.py
   - Add metric grouping logic (base metrics vs. derived metrics)
   - Add database commit between phases
   - Estimated effort: 30-60 minutes

2. **Testing:** Verify fix
   - Run test suite (backend/tests/test_l1_metrics.py)
   - Run spot-check verification again
   - Confirm NON_DIV_ECF and FY_TSR_PREL return 6,954 records each

3. **Documentation:** Update
   - Add comment in metrics_service.py explaining metric dependencies
   - Update STATE.md with dependency graph
   - Add gotcha to API documentation

4. **Future:** Consider Option B (refactor to single batch)
   - After Phase 06 stabilizes
   - Could be Phase 07 optimization task
   - Would eliminate two-phase requirement

---

## References

- **SQL Functions:** `backend/database/schema/functions.sql` (lines 660-683, 855-874)
- **Service Layer:** `backend/app/services/metrics_service.py` (METRIC_FUNCTIONS mapping)
- **Test Results:** `SPOT_CHECK_RESULTS.md` (current output record counts)
- **Phase Context:** `STATE.md` (metric dependency documentation)

---

## Approval

- [ ] Root cause diagnosis confirmed
- [ ] Recommended fix (Option A) approved
- [ ] Ready for implementation in Phase 06.5
