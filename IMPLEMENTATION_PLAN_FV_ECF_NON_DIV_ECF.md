# Implementation Plan: FV ECF and Non Div ECF Fix

**Date:** March 2026  
**Status:** In Development  
**Phases:** A (Non Div ECF), B (FV ECF Refactor), C (Integration)

---

## Executive Summary

This document outlines the implementation plan to:
1. **Fix Non Div ECF calculation** - Move from Phase 1 Group 3 to Phase 2, ensure it stores in metrics_outputs
2. **Refactor FV ECF service** - Implement correct multi-year formulas matching Excel specifications
3. **Integrate FV ECF** - Connect to runtime-metrics pipeline with proper parameter handling

**Timeline:** Sequential execution of Phases A → B → C  
**Validation:** Test outputs against user-provided reference data

---

## Phase A: Fix Non Div ECF Calculation

### A1: Diagnose Group 3 Execution Issue

**Objective:** Determine why Non Div ECF is listed in orchestration but not calculated

**Investigation Steps:**

1. **Check orchestration.py Group 3 execution:**
   - File: `/backend/app/api/v1/endpoints/orchestration.py:138-181`
   - Group 3 definition: Line 146 = `["Calc OA", "Calc ECF", "Non Div ECF"]`
   - Verify metrics are actually being passed to calculation loop

2. **Review metrics_service.py Phase 1 configuration:**
   - File: `/backend/app/services/metrics_service.py:523-540`
   - Verify "Non Div ECF" is in Phase 1 assignment (currently shows Phase 2)
   - This may be the mismatch: orchestration says Phase 1, metrics_service says Phase 2

3. **Check error handling:**
   - Look for silent catch blocks around Non Div ECF execution
   - Verify logging captures failures

4. **Test manual execution:**
   ```bash
   # Call the metric calculation endpoint directly
   curl -X POST http://localhost:8000/api/v1/metrics/calculate \
     -H "Content-Type: application/json" \
     -d '{
       "dataset_id": "YOUR_DATASET_ID",
       "metric_name": "Non Div ECF"
     }'
   ```

### A2: Move Non Div ECF to Phase 2

**Objective:** Logically separate derived metrics (Phase 2) from base metrics (Phase 1)

**Changes Required:**

1. **Update `/backend/app/api/v1/endpoints/orchestration.py`:**
   - **Line 146:** Remove "Non Div ECF" from Group 3
     ```python
     # BEFORE:
     ["Calc OA", "Calc ECF", "Non Div ECF"],
     
     # AFTER:
     ["Calc OA", "Calc ECF"],
     ```
   
   - **Lines 187-209 (Phase 2):** Add Non Div ECF alongside Beta pre-computation
     ```python
     # Add after Phase 1 succeeds (after line 182 await session.commit())
     # Call fn_calc_non_div_ecf for each dataset-metric pair
     ```

2. **Update `/backend/app/services/metrics_service.py` (if needed):**
   - Verify L1_METRICS_PHASES dictionary has:
     ```python
     "Non Div ECF": (2, False),  # Phase 2, no param_set_id needed
     ```
   - Should already be correct per exploration findings

3. **Orchestration logic:**
   - Phase 1: 12 metrics (remove Non Div ECF) → 11 metrics
   - Phase 2: Beta pre-computation + Non Div ECF calculation → 2 items
   - Update response model to reflect: "Phase 1 (11/11)", "Phase 2 (2 items complete)"

### A3: Verify Non Div ECF Calculates & Stores

**Testing Steps:**

1. **Run full pipeline:**
   ```bash
   python backend/database/etl/pipeline.py \
     --input "input-data/ASX/raw-data/Bloomberg Download data.xlsx" \
     --mode full
   ```

2. **Check metrics_outputs after Stage 3:**
   ```sql
   SELECT 
     COUNT(*) as non_div_ecf_count,
     COUNT(DISTINCT ticker) as unique_tickers,
     MIN(fiscal_year) as start_year,
     MAX(fiscal_year) as end_year
   FROM cissa.metrics_outputs
   WHERE dataset_id = '{dataset_id}'
     AND output_metric_name = 'Non Div ECF';
   ```

3. **Verify data quality:**
   ```sql
   -- Should match Calc ECF row counts
   SELECT 
     (SELECT COUNT(*) FROM cissa.metrics_outputs 
      WHERE output_metric_name = 'Calc ECF' 
        AND dataset_id = '{dataset_id}') as ecf_rows,
     (SELECT COUNT(*) FROM cissa.metrics_outputs 
      WHERE output_metric_name = 'Non Div ECF' 
        AND dataset_id = '{dataset_id}') as non_div_ecf_rows;
   ```

4. **Sample data inspection:**
   ```sql
   SELECT ticker, fiscal_year, output_metric_value
   FROM cissa.metrics_outputs
   WHERE dataset_id = '{dataset_id}'
     AND output_metric_name = 'Non Div ECF'
   LIMIT 20;
   ```

---

## Phase B: Refactor FV ECF Service

### B1: Rewrite Calculation Logic

**Location:** `/backend/app/services/fv_ecf_service.py`

**Formula Implementation:**

#### 1Y FV ECF (Starting fiscal_year > begin_year)
```
FV_ECF_1Y[t] = (
  -DIVIDENDS[t] 
  - (DIVIDENDS[t] / (1 - tax_rate)) * tax_rate * franking_credit_value * FRANKING[t]  [if incl_franking]
  + Non_Div_ECF[t]
) * (1 + Calc_Open_Ke[t])^0

Simplified: FV_ECF_1Y[t] = ECF_base[t] * 1  (since ^0 = 1)
```

#### 3Y FV ECF (Starting fiscal_year >= begin_year + 2)
```
FV_ECF_3Y[t] = 
  ECF_base[t] * (1 + Calc_Open_Ke[t])^2 +
  ECF_base[t-1] * (1 + Calc_Open_Ke[t])^1 +
  ECF_base[t-2] * (1 + Calc_Open_Ke[t])^0
```

#### 5Y FV ECF (Starting fiscal_year >= begin_year + 4)
```
FV_ECF_5Y[t] = 
  ECF_base[t] * (1 + Calc_Open_Ke[t])^4 +
  ECF_base[t-1] * (1 + Calc_Open_Ke[t])^3 +
  ECF_base[t-2] * (1 + Calc_Open_Ke[t])^2 +
  ECF_base[t-3] * (1 + Calc_Open_Ke[t])^1 +
  ECF_base[t-4] * (1 + Calc_Open_Ke[t])^0
```

#### 10Y FV ECF (Starting fiscal_year >= begin_year + 9)
```
FV_ECF_10Y[t] = sum(
  ECF_base[t-i] * (1 + Calc_Open_Ke[t])^(10-1-i) 
  for i in range(0, 10)
)
```

Where:
```
ECF_base[t] = -DIVIDENDS[t] - franking_adjustment[t] + Non_Div_ECF[t]
franking_adjustment[t] = (DIVIDENDS[t] / (1 - tax_rate)) * tax_rate * franking_credit_value * FRANKING[t]
                        (only if incl_franking = "Yes")
Calc_Open_Ke[t] = Calc_KE[t-1]  (prior year's cost of equity)
```

### B2: Fix Data Fetching

**Update methods in FVECFService:**

1. **`_fetch_fundamentals_data()`**
   - Change: Fetch DIVIDENDS (currently correct)
   - Change: Fetch FRANKING (currently correct)
   - **Remove:** Non Div ECF calculation inline
   - **Reason:** Non Div ECF is now calculated and stored in Phase A

2. **`_fetch_non_div_ecf_data()`** (NEW METHOD)
   ```python
   async def _fetch_non_div_ecf_data(self, dataset_id: UUID) -> pd.DataFrame:
       """
       Fetch Non Div ECF from metrics_outputs.
       Returns DataFrame with columns: ticker, fiscal_year, non_div_ecf
       """
       query = text("""
           SELECT 
               ticker,
               fiscal_year,
               output_metric_value AS non_div_ecf
           FROM cissa.metrics_outputs
           WHERE dataset_id = :dataset_id
             AND output_metric_name = 'Non Div ECF'
           ORDER BY ticker, fiscal_year
       """)
       # Execute and return DataFrame
   ```

3. **`_fetch_lagged_ke()`** (KEEP existing)
   - Already correctly lags Calc KE by 1 year
   - Verify it returns ke_open (prior year KE)

4. **`_join_data()`** (UPDATE)
   ```python
   def _join_data(self, fundamentals_df, non_div_ecf_df, ke_df):
       """
       Join fundamentals + Non Div ECF + lagged KE on (ticker, fiscal_year).
       """
       # Join all three sources
       merged = fundamentals_df.merge(non_div_ecf_df, on=['ticker', 'fiscal_year'], how='left')
       merged = merged.merge(ke_df, on=['ticker', 'fiscal_year'], how='left')
       return merged
   ```

### B3: Implement Temporal Windows

**Validation logic before calculation:**

```python
def _validate_temporal_window(self, df: pd.DataFrame, interval: int) -> pd.DataFrame:
    """
    Filter rows to only those with sufficient historical data for the interval.
    
    - 1Y: fiscal_year > begin_year (needs current year only)
    - 3Y: fiscal_year >= begin_year + 2 (needs 3 years of data)
    - 5Y: fiscal_year >= begin_year + 4
    - 10Y: fiscal_year >= begin_year + 9
    """
    # Group by ticker, get begin_year
    # Filter where fiscal_year >= begin_year + (interval - 1)
    # Return filtered df
```

### B4: Update Calculation Method

**Rewrite `_calculate_fv_ecf_for_interval()`:**

```python
def _calculate_fv_ecf_for_interval(
    self,
    df: pd.DataFrame,
    interval: int,
    params: dict
) -> pd.DataFrame:
    """
    Calculate FV_ECF for specific interval (1, 3, 5, or 10 years).
    
    Algorithm:
    1. Validate temporal window (sufficient historical data exists)
    2. Group by ticker
    3. For each row in window:
       a. Get current year and prior (interval-1) years
       b. Calculate ECF_base for each year
       c. Multiply by (1 + ke_open)^power for each year
       d. Sum all terms
    4. Return result rows
    """
    # Implementation details follow formula in B1
```

**Key differences from current code:**
- Current: Uses shifts within grouped data
- New: Explicit historical year lookback for each calculation
- Current: Single power calculation
- New: Different power for each historical year term
- Current: Complex loop structure
- New: Clearer year-by-year computation

---

## Phase C: Integration

### C1: Confirm Runtime-Only Approach

**Decision:** Keep FV ECF as runtime-only metric

**Reasoning:**
- All parameters pre-calculated ✓
- Fundamentals data available ✓
- Non Div ECF available after Phase A ✓
- Calc KE available ✓
- **BUT:** Multi-year lookback requires sequential processing (ticker-specific)
- Pre-calculation would require storing all 4 intervals, duplication of Calc KE logic

**Alternative:** Could pre-calculate alongside Cost of Equity if needed

### C2: Update Runtime-Metrics Orchestration

**Endpoint:** `POST /api/v1/metrics/runtime-metrics`

**Current execution order (from orchestration):**
```
1. Beta Rounding
2. Risk-Free Rate
3. Cost of Equity
[ADD HERE:]
4. FV ECF (1Y, 3Y, 5Y, 10Y)
```

**Changes needed:**
- Ensure Calc KE is available before FV ECF runs
- FV ECF depends on: Calc KE, Non Div ECF, DIVIDENDS, FRANKING
- Update orchestration response to include FV ECF timing

### C3: Parameter Handling

**FV ECF parameters:**
- `incl_franking` (from param_set_id overrides)
- `frank_tax_rate` (from parameters table or param_set overrides)
- `value_franking_cr` (from parameters table or param_set overrides)

**No changes needed:** These already exist and work correctly

---

## Data Validation & Testing

### Test 1: Non Div ECF Storage
```bash
# After Phase A completion
SELECT COUNT(*) FROM cissa.metrics_outputs 
WHERE output_metric_name = 'Non Div ECF' 
  AND dataset_id = '{dataset_id}';
# Expected: ~9,189 rows (matches Calc ECF)
```

### Test 2: FV ECF Calculation
```bash
# Run the refactored service
curl -X POST http://localhost:8000/api/v1/metrics/l2-fv-ecf/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "{dataset_id}",
    "param_set_id": "{param_set_id}",
    "incl_franking": "Yes"
  }'
```

### Test 3: Output Validation
```bash
# Check stored results
SELECT 
  COUNT(*) as total_rows,
  COUNT(DISTINCT ticker) as unique_tickers,
  COUNT(DISTINCT SUBSTRING(output_metric_name, 1, 9)) as intervals
FROM cissa.metrics_outputs
WHERE dataset_id = '{dataset_id}'
  AND output_metric_name LIKE 'FV ECF%';
  
# Expected: 
# - total_rows: ~36,756 (9,189 × 4 intervals)
# - unique_tickers: ~500
# - intervals: 4 (1Y, 3Y, 5Y, 10Y)
```

### Test 4: Reference Data Validation
Once user provides reference data:
```bash
# Compare calculated values to expected
SELECT 
  ticker,
  fiscal_year,
  output_metric_value as calculated,
  {expected_value} as expected,
  ABS(output_metric_value - {expected_value}) as variance
FROM cissa.metrics_outputs
WHERE output_metric_name = 'FV ECF_1Y'
  AND ticker = '{test_ticker}'
ORDER BY fiscal_year;
```

---

## Dependencies & Blockers

### Blocking Non Div ECF Fix
- None identified (ready to proceed)

### Blocking FV ECF Refactor
- **Phase A must complete first** (Non Div ECF must be in metrics_outputs)

### Blocking Integration
- None (both metrics will be independently available)

---

## Rollback Plan

If issues occur:

1. **Non Div ECF issues:**
   - Revert orchestration.py changes
   - Keep Non Div ECF in Phase 1 Group 3
   - Investigate why Group 3 doesn't execute

2. **FV ECF issues:**
   - Keep existing fv_ecf_service.py as backup
   - Revert to previous version if calculations don't match reference data
   - Re-run tests with original code

3. **Integration issues:**
   - Remove FV ECF from runtime-metrics orchestration
   - Run metrics separately until issue resolved

---

## Success Criteria

### Phase A Complete When:
- [ ] Non Div ECF appears in metrics_outputs
- [ ] Row counts match Calc ECF
- [ ] Sample data values are reasonable

### Phase B Complete When:
- [ ] FV ECF calculations match user's reference data
- [ ] All 4 intervals (1Y/3Y/5Y/10Y) produce values
- [ ] Temporal windows work correctly (early years return NULL)

### Phase C Complete When:
- [ ] FV ECF integrates into runtime-metrics flow
- [ ] Parameter handling works correctly
- [ ] End-to-end pipeline executes without errors

---

## Files to Modify

1. **`/backend/app/api/v1/endpoints/orchestration.py`**
   - Remove Non Div ECF from Phase 1 Group 3
   - Add Non Div ECF to Phase 2 execution

2. **`/backend/app/services/fv_ecf_service.py`**
   - Complete refactoring with new formulas
   - Add proper multi-year lookback logic
   - Update data fetching methods

3. **`/backend/app/api/v1/endpoints/metrics.py`** (if needed)
   - Verify FV ECF endpoint integration
   - Update response models if needed

---

## Timeline

- **Phase A:** 1-2 hours (investigation + fix + testing)
- **Phase B:** 3-4 hours (refactoring + testing)
- **Phase C:** 1-2 hours (integration + end-to-end testing)

**Total:** 5-8 hours of development + validation with reference data

---

## Next Steps

1. ✅ This document created
2. ⏳ Begin Phase A: Diagnose and fix Non Div ECF
3. ⏳ Test Phase A changes
4. ⏳ Begin Phase B: Refactor FV ECF
5. ⏳ Test Phase B with reference data
6. ⏳ Complete Phase C: Integration testing

Ready to proceed with Phase A?
