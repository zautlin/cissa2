# NON DIV ECF NOT BEING CALCULATED - ROOT CAUSE ANALYSIS

## ISSUE SUMMARY
Non Div ECF is not being calculated during ingestion because the `_auto_calculate_l1_metrics()` function is DEFINED but NEVER CALLED in the ingestion pipeline.

---

## ROOT CAUSE

### Location: /backend/database/etl/ingestion.py

**The Problem:**
1. Function `_auto_calculate_l1_metrics()` is defined at lines 214-244
2. Function is NEVER invoked from `load_dataset()`
3. Therefore, NO metrics are calculated during ingestion

**Evidence:**
```python
# ingestion.py, lines 146-212
def load_dataset(self, csv_path: str, ...) -> Dict[str, Any]:
    """Load a complete dataset"""
    
    # ... data loading steps ...
    
    # Load and ingest raw data
    result = self._load_raw_data(dataset_id, csv_path)
    
    # Update dataset_versions with metadata
    self._update_dataset_metadata(dataset_id, result)
    
    # MISSING CALL HERE:
    # self._auto_calculate_l1_metrics(dataset_id)
    
    return { ... }  # Returns WITHOUT metrics calculation results
```

The function exists (lines 214-244, 246-335) but is never called.

---

## EXPECTED FLOW (What SHOULD happen)

### Phase 1: Base Metrics (Reads from fundamentals)
1. Calc MC
2. Calc Assets  
3. Calc OA
4. Calc Op Cost
5. Calc Non Op Cost
6. Calc Tax Cost
7. Calc XO Cost
8. LAG_MC
9. Calc ECF ← CRITICAL: Must be stored in metrics_outputs BEFORE Phase 2
10. Calc EE
11. Calc FY TSR

### Database Commit After Phase 1
All Phase 1 results are committed to metrics_outputs table.

### Phase 2: Derived Metrics (Reads from metrics_outputs)
1. **Non Div ECF** ← REQUIRES Calc ECF from Phase 1 in metrics_outputs
2. Calc FY TSR PREL ← REQUIRES Calc FY TSR from Phase 1 in metrics_outputs

---

## TWO-PHASE ARCHITECTURE

### File: /backend/app/services/metrics_service.py (lines 494-647)

The `calculate_batch_metrics()` method implements the correct two-phase logic:

**PHASE 1 (lines 567-591):**
```python
phase1_metrics = [
    "Calc MC", "Calc Assets", "Calc OA", "Calc Op Cost",
    "Calc Non Op Cost", "Calc Tax Cost", "Calc XO Cost",
    "LAG_MC", "Calc ECF", "Calc EE", "Calc FY TSR"
]

for metric_name in phase1_metrics:
    row_count = await self._execute_sql_function(metric_name, dataset_id)
    # Each result is inserted to metrics_outputs via _insert_metric_results_with_metadata()
    # Each call includes: await self.session.commit() at line 399
```

**Between Phase 1 & 2 (line 591):**
```python
logger.info("Database commit after PHASE 1 - metrics_outputs now contains base metric results")
```

**PHASE 2 (lines 593-619):**
```python
if phase2_metrics:
    logger.info("PHASE 2: Calculating 2 derived metrics (now reading from metrics_outputs)")
    
    for metric_name in phase2_metrics:
        row_count = await self._execute_sql_function(metric_name, dataset_id)
        # At this point, metrics_outputs contains Phase 1 results
```

### L1_METRICS_PHASES Configuration (lines 523-540)

```python
L1_METRICS_PHASES = {
    # PHASE 1: Base metrics (read from fundamentals)
    "Calc MC": (1, False),
    "Calc Assets": (1, False),
    "Calc OA": (1, False),
    "Calc Op Cost": (1, False),
    "Calc Non Op Cost": (1, False),
    "Calc Tax Cost": (1, False),
    "Calc XO Cost": (1, False),
    "LAG_MC": (1, False),
    "Calc ECF": (1, False),
    "Calc EE": (1, True),     # Parameter-sensitive
    "Calc FY TSR": (1, True), # Parameter-sensitive
    
    # PHASE 2: Derived metrics (read from metrics_outputs)
    "Non Div ECF": (2, False),      # ← Depends on Calc ECF
    "Calc FY TSR PREL": (2, True),  # ← Depends on Calc FY TSR
}
```

---

## NON DIV ECF FUNCTION REQUIREMENTS

### File: /backend/database/schema/functions.sql (lines 454-480)

```sql
CREATE OR REPLACE FUNCTION cissa.fn_calc_non_div_ecf(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  non_div_ecf NUMERIC
) AS $$
BEGIN
  RETURN QUERY
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
   ORDER BY mo.ticker, mo.fiscal_year;
END;
```

**Critical Requirement:**
- Queries metrics_outputs table for rows where `output_metric_name = 'Calc ECF'`
- If Calc ECF is not in metrics_outputs, fn_calc_non_div_ecf returns ZERO ROWS
- This is why Phase 2 must come AFTER Phase 1 is committed

**Formula:** Non Div ECF = Calc ECF + DIVIDENDS

---

## METRIC_FUNCTIONS MAPPING

### File: /backend/app/services/metrics_service.py (lines 21-44)

```python
METRIC_FUNCTIONS = {
    # L1 Temporal Metrics (5)
    "Calc ECF": ("fn_calc_ecf", "ecf", False),
    "Non Div ECF": ("fn_calc_non_div_ecf", "non_div_ecf", False),  ← Marked as Phase 2
    "Calc EE": ("fn_calc_economic_equity", "ee", True),
    "Calc FY TSR": ("fn_calc_fy_tsr", "fy_tsr", True),
    "Calc FY TSR PREL": ("fn_calc_fy_tsr_prel", "fy_tsr_prel", True),
}
```

Tuple format: (sql_function_name, output_column_name, requires_param_set_id)

---

## ORCHESTRATION ENDPOINT

### File: /backend/app/api/v1/endpoints/orchestration.py

**Group 3 Configuration (lines 143-148):**
```python
phase_1_groups = [
    ["Calc OA", "Calc ECF", "Non Div ECF"],  ← Non Div ECF is IN the groups list!
]
```

**However**, this orchestration endpoint is for RUNTIME calculation via API, not ingestion!

**Entry Point:** POST /api/v1/metrics/calculate-l1
**Purpose:** Orchestrate pre-computed metrics via HTTP API
**When Called:** Manually by user, NOT during ingestion

---

## ACTUAL ORCHESTRATION FLOW (What Happens Now)

### Pipeline Flow:
1. Pipeline calls `ingester.load_dataset()` (pipeline.py line 466)
2. Ingester performs data validation and loads raw_data table
3. Ingester returns without calling `_auto_calculate_l1_metrics()`
4. Pipeline checks for `result.get('l1_metrics')` (pipeline.py line 501) - EMPTY!
5. Pipeline logs: "L1 Metrics: Not calculated (upgrade required)" (pipeline.py line 515)

---

## DATABASE STATE AFTER INGESTION

### Tables Populated:
- ✓ companies (reference table)
- ✓ fiscal_year_mapping (reference table)
- ✓ raw_data (all imported data)
- ✓ dataset_versions (metadata)
- ✓ imputation_audit_trail (duplicates)
- ✗ metrics_outputs (EMPTY - no Phase 1 or Phase 2 metrics calculated)

### Consequences:
- All metrics including Calc ECF are NOT calculated
- Non Div ECF cannot be calculated (parent metric missing)
- No L1 metrics are available for downstream analysis
- User must manually call orchestration API to calculate metrics

---

## MISSING CALL

The solution is simple: Add this line at the END of load_dataset():

```python
# At the end of load_dataset(), after line 199:
# self._update_dataset_metadata(dataset_id, result)

# ADD THIS:
metrics_result = self._auto_calculate_l1_metrics(str(dataset_id))
result['l1_metrics'] = metrics_result
```

This would:
1. Trigger async metric calculation after ingestion
2. Calculate all Phase 1 metrics (read from fundamentals)
3. Commit Phase 1 results to metrics_outputs
4. Calculate Phase 2 metrics (including Non Div ECF)
5. Include metrics calculation status in ingestion response

---

## ERROR CONDITIONS

### Current Behavior When Non Div ECF Phase 2 Runs:

If Phase 2 somehow ran without Phase 1 being committed:

```python
# metrics_service.py, lines 599-610
if row_count > 0:
    calculated += 1
    logger.info(f"✓ {metric_name}: {row_count} records")
else:
    failed += 1
    error_msg = f"{metric_name}: 0 rows calculated (parent metric may not exist)"
    errors.append(error_msg)
    logger.warning(f"  {metric_name}: 0 rows")
```

**Error Message:** "Non Div ECF: 0 rows calculated (parent metric may not exist)"

This is a SILENT FAILURE - the code doesn't error out, just logs a warning.

---

## COMMIT LOGIC

### Phase 1 Results Are Committed:

Each metric is inserted via `_insert_metric_results_with_metadata()`:

```python
# metrics_service.py, lines 395-400
await self.session.execute(multi_row_insert)
logger.info(f"Inserted batch of {len(batch)} metric results (multi-row INSERT)")

# Commit the transaction
await self.session.commit()
logger.info(f"Committed {len(results)} metric results for {metric_name}")
```

**Each Phase 1 metric execution includes a commit!**

This ensures that when Phase 2 starts, all Phase 1 results are available in metrics_outputs.

---

## SUMMARY TABLE

| Aspect | Status | Details |
|--------|--------|---------|
| Function Defined | ✓ Yes | ingestion.py, lines 214-244, 246-335 |
| Function Called | ✗ **NO** | Never invoked from load_dataset() |
| Phase 1 Logic | ✓ Correct | metrics_service.py, lines 567-591 |
| Phase 1 Commit | ✓ Correct | Each metric commits after insert |
| Phase 2 Logic | ✓ Correct | metrics_service.py, lines 593-619 |
| Non Div ECF in Phase 2 | ✓ Yes | Correctly marked as (2, False) |
| SQL Function Query | ✓ Correct | Reads from metrics_outputs for Calc ECF |
| Metrics Returned | ✗ **0 rows** | Because Calc ECF is not in metrics_outputs (Phase 1 never ran) |
| API Endpoint | ✓ Works | /api/v1/metrics/calculate-l1 works at runtime |
| Database State | ✗ Wrong | metrics_outputs table is empty after ingestion |

---

## RECOMMENDATIONS

### Immediate Fix
Add call to `_auto_calculate_l1_metrics()` in `load_dataset()` method.

### Verification Steps
1. Run ingestion pipeline
2. Query metrics_outputs table
3. Verify "Calc ECF" rows exist
4. Verify "Non Div ECF" rows exist
5. Verify counts match non-null Calc ECF entries

### Testing
- Unit test for calculate_batch_metrics() two-phase execution
- Integration test for full ingestion → metrics flow
- Verify Non Div ECF = Calc ECF + DIVIDENDS formula

---

## KEY CODE LOCATIONS

### Ingestion Entry Point
/backend/database/etl/ingestion.py, line 146-212: load_dataset()

### Metrics Calculation (NOT CALLED)
/backend/database/etl/ingestion.py, line 214-244: _auto_calculate_l1_metrics()
/backend/database/etl/ingestion.py, line 246-335: _async_calculate_l1_metrics()

### Two-Phase Orchestration
/backend/app/services/metrics_service.py, line 494-647: calculate_batch_metrics()

### Phase Configuration
/backend/app/services/metrics_service.py, line 523-540: L1_METRICS_PHASES dictionary

### Non Div ECF SQL Function
/backend/database/schema/functions.sql, line 454-480: fn_calc_non_div_ecf()

### API Runtime Orchestration (Not called during ingestion)
/backend/app/api/v1/endpoints/orchestration.py, line 263-322: POST /api/v1/metrics/calculate-l1

