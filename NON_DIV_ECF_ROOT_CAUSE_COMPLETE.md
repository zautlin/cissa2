╔════════════════════════════════════════════════════════════════════════════════════════╗
║                   NON DIV ECF NOT CALCULATED - COMPREHENSIVE ANALYSIS                  ║
║                                ROOT CAUSE IDENTIFIED                                    ║
╚════════════════════════════════════════════════════════════════════════════════════════╝

EXECUTIVE SUMMARY
═════════════════════════════════════════════════════════════════════════════════════════

The function _auto_calculate_l1_metrics() is DEFINED in the codebase but NEVER CALLED 
during data ingestion. This is a simple omission in the orchestration flow.

✗ Function exists:        ingestion.py, lines 214-244 & 246-335
✗ Function never called:  Missing from load_dataset() method
✗ Result:                metrics_outputs table empty after ingestion
✗ Impact:                Non Div ECF cannot be calculated (parent metric missing)


DELIVERABLE SUMMARY
═════════════════════════════════════════════════════════════════════════════════════════

1. EXACT CODE FLOW FOR PHASE 1 AND PHASE 2
   Location: /backend/app/services/metrics_service.py, lines 494-647
   
   Phase 1 (Lines 567-591):
   - Executes 11 base metrics reading from fundamentals table
   - Each metric is calculated via fn_calc_XXX() SQL function
   - Results inserted into metrics_outputs via multi-row INSERT
   - Each insertion includes: await self.session.commit()
   - Calc ECF is one of the Phase 1 metrics
   
   Between Phase 1 & 2:
   - All Phase 1 metrics are committed and visible in metrics_outputs
   - Database ready for Phase 2 to read Phase 1 results
   
   Phase 2 (Lines 593-619):
   - Executes 2 derived metrics
   - Non Div ECF is one of the Phase 2 metrics
   - Reads from metrics_outputs where output_metric_name = 'Calc ECF'
   - Also reads from fundamentals for DIVIDENDS
   
2. WHETHER NON DIV ECF IS INCLUDED IN PHASE 2
   ✓ YES - Correctly marked in L1_METRICS_PHASES dictionary (line 538)
   "Non Div ECF": (2, False)  # Phase 2, doesn't need param_set_id
   
3. POTENTIAL ISSUES PREVENTING NON DIV ECF CALCULATION
   
   Issue #1: _auto_calculate_l1_metrics() Never Called
   ├─ Location: Missing from load_dataset() method
   ├─ Impact: Phase 1 never runs, so Phase 2 never runs
   └─ Severity: CRITICAL
   
   Issue #2: If Phase 1 Ran Alone (hypothetical)
   ├─ Problem: Non Div ECF reads metrics_outputs for Calc ECF
   ├─ If Calc ECF not committed: Query returns 0 rows
   ├─ Result: Silent failure - logs warning but continues
   └─ Severity: Mitigated by correct commit logic (each metric commits)
   
   Issue #3: Silent Failure Error Handling
   ├─ Location: metrics_service.py, lines 599-610
   ├─ Behavior: Returns 0 rows but doesn't raise exception
   ├─ Logging: "Non Div ECF: 0 rows calculated (parent metric may not exist)"
   └─ Severity: Design intent, not a bug
   
4. DATABASE STATE AFTER PHASE 1 (Calc ECF properly committed?)
   
   Current State (Broken):
   ├─ Phase 1 never runs
   ├─ metrics_outputs table: EMPTY
   ├─ Calc ECF: NOT IN DATABASE
   └─ Result: Phase 2 cannot find parent metric
   
   Expected State (If calling _auto_calculate_l1_metrics):
   ├─ Phase 1 completes with 11 metrics
   ├─ Each Phase 1 metric individually committed to metrics_outputs
   ├─ Calc ECF inserted and committed (visible in metrics_outputs)
   ├─ All Phase 1 rows committed before Phase 2 starts
   └─ Result: Phase 2 can read Calc ECF successfully
   
   Commit Logic Verification:
   ├─ Each metric execution in Phase 1 calls:
   ├─   await self._insert_metric_results_with_metadata(...)
   ├─     which calls: await self.session.commit() at line 399
   ├─ Result: Data is visible for next metric's query
   └─ Conclusion: Commit logic is CORRECT
   
5. ERROR CONDITIONS AND SKIP LOGIC
   
   Current Behavior:
   ├─ No Phase 1 execution = No metrics calculated
   ├─ No Phase 2 execution = Non Div ECF not even attempted
   ├─ Result: metrics_outputs table completely empty
   
   Hypothetical: Phase 2 Runs Without Phase 1 Data
   ├─ Query: SELECT ... FROM metrics_outputs WHERE output_metric_name = 'Calc ECF'
   ├─ Result: 0 rows returned
   ├─ Logged: "Non Div ECF: 0 rows calculated (parent metric may not exist)"
   ├─ Pipeline: Continues with failed_count += 1
   ├─ No exception: Code doesn't crash, just logs warning
   └─ Status: Silent failure (GRACEFUL DEGRADATION)


COMPLETE CODE FLOW ANALYSIS
═════════════════════════════════════════════════════════════════════════════════════════

ORCHESTRATION ENDPOINT (orchestration.py, lines 80-256)
├─ POST /api/v1/metrics/calculate-l1
├─ Purpose: RUNTIME orchestration via API
├─ When Called: Manually by user (NOT during ingestion)
├─ Behavior: Makes HTTP calls to metric endpoints
├─ Non Div ECF: Included in Group 3 of parallelized execution
└─ Status: Works correctly but not used during ingestion


INGESTION ORCHESTRATION (ingestion.py, lines 146-212)
├─ Method: load_dataset()
├─ Entry Point: Called from pipeline.py line 466
├─ Steps:
│  ├─ Load reference tables (companies, fy_mapping)
│  ├─ Load raw data from CSV
│  ├─ Validate metrics against metric_units
│  ├─ Create dataset_versions entry
│  ├─ Update metadata
│  └─ ✗ MISSING: Call to _auto_calculate_l1_metrics()
└─ Result: Returns without metrics data


METRICS CALCULATION (ingestion.py, lines 214-335)
├─ Function: _auto_calculate_l1_metrics()
├─ Status: EXISTS but NEVER CALLED
├─ Implementation:
│  ├─ Bridges sync ingestion with async metrics service
│  ├─ Uses asyncio.run() to create event loop
│  ├─ Creates async engine and session
│  ├─ Calls MetricsService.calculate_batch_metrics()
│  └─ Returns status dict
└─ Problem: NEVER INVOKED


TWO-PHASE ORCHESTRATION (metrics_service.py, lines 494-647)
├─ Method: calculate_batch_metrics()
├─ Receives: dataset_id, optional metric_names list
├─ Configuration: L1_METRICS_PHASES dictionary defines phase assignment
├─ Phase 1 Execution (lines 567-591):
│  ├─ Metric Loop:
│  │  ├─ for metric_name in phase1_metrics:
│  │  ├─   row_count = await self._execute_sql_function(metric_name, dataset_id)
│  │  ├─   Insert to metrics_outputs
│  │  └─   Commit transaction
│  ├─ 11 Metrics Calculated:
│  │  ├─ Calc MC, Calc Assets, Calc OA
│  │  ├─ Calc Op Cost, Calc Non Op Cost, Calc Tax Cost, Calc XO Cost
│  │  ├─ LAG_MC, Calc ECF, Calc EE, Calc FY TSR
│  └─ All results committed and visible
├─ Phase 2 Execution (lines 593-619):
│  ├─ Conditional: if phase2_metrics:
│  ├─ Metric Loop:
│  │  ├─ for metric_name in phase2_metrics:
│  │  ├─   row_count = await self._execute_sql_function(metric_name, dataset_id)
│  │  └─   Insert to metrics_outputs
│  ├─ 2 Metrics Calculated:
│  │  ├─ Non Div ECF (reads Calc ECF from metrics_outputs)
│  │  └─ Calc FY TSR PREL (reads Calc FY TSR from metrics_outputs)
│  └─ Results inserted
└─ Return: Status dict with calculated, failed, errors


SQL FUNCTION EXECUTION (metrics_service.py, lines 240-327)
├─ Method: _execute_sql_function()
├─ Parameters: metric_name, dataset_id
├─ Process:
│  ├─ Look up function in METRIC_FUNCTIONS dict
│  ├─ Get function_name, column_name, needs_param_set flag
│  ├─ Handle parameter-sensitive metrics if needed
│  ├─ Execute: SELECT ... FROM cissa.fn_calc_XXX(:dataset_id)
│  ├─ Fetch all rows
│  ├─ Create MetricResultItem objects
│  ├─ Call _insert_metric_results_with_metadata()
│  └─ Return row count
└─ Commit: Happens in _insert_metric_results_with_metadata()


BATCH INSERT OPTIMIZATION (metrics_service.py, lines 329-400)
├─ Method: _insert_metric_results_with_metadata()
├─ Optimization:
│  ├─ Before: 10,000+ individual INSERT statements
│  ├─ After: Single multi-row INSERT statement
│  ├─ Performance: ~10 seconds → ~1 second
├─ Batch Processing:
│  ├─ batch_size = 1000
│  ├─ Loop: for i in range(0, len(results), batch_size):
│  ├─ Build multi-row VALUES clause
│  ├─ Execute single multi-row INSERT
│  └─ Process next batch
├─ Transaction Handling:
│  ├─ All batches in same transaction
│  ├─ Single commit at end: await self.session.commit()
│  └─ Ensures all rows inserted atomically
└─ Concurrency: Safe for parallel Phase 1 metrics (if implemented)


NON DIV ECF SPECIFIC FLOW
═════════════════════════════════════════════════════════════════════════════════════════

When Non Div ECF Phase 2 Executes (in hypothetical working scenario):

1. Call _execute_sql_function("Non Div ECF", dataset_id)
   
2. Look up in METRIC_FUNCTIONS:
   "Non Div ECF" → ("fn_calc_non_div_ecf", "non_div_ecf", False)
   
3. Execute query:
   SELECT ticker, fiscal_year, non_div_ecf AS value
   FROM cissa.fn_calc_non_div_ecf(:dataset_id)
   
4. Function fn_calc_non_div_ecf executes:
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
     AND mo.output_metric_name = 'Calc ECF'  ← CRITICAL
   ORDER BY mo.ticker, mo.fiscal_year
   
5. For each returned row:
   - Ticker, fiscal_year, value are extracted
   - MetricResultItem created
   
6. Insert results:
   INSERT INTO metrics_outputs (...)
   VALUES (...multiple rows..., 'Non Div ECF', value, ...)
   ON CONFLICT (...) DO UPDATE SET ...
   
7. Commit results:
   await self.session.commit()
   
8. Return row count to Phase 2 loop
   
9. Phase 2 result: Non Div ECF successfully calculated and stored


CURRENT BEHAVIOR (Broken)
═════════════════════════════════════════════════════════════════════════════════════════

1. Pipeline calls ingester.load_dataset()
2. Ingester loads raw_data table
3. Ingester updates metadata
4. Ingester returns (WITHOUT calling _auto_calculate_l1_metrics)
5. Pipeline logs: "L1 Metrics: Not calculated (upgrade required)"
6. metrics_outputs table remains EMPTY
7. User manually calls /api/v1/metrics/calculate-l1 endpoint
8. Phase 1 and 2 metrics calculated at runtime
9. metrics_outputs finally populated


EXPECTED BEHAVIOR (After Fix)
═════════════════════════════════════════════════════════════════════════════════════════

1. Pipeline calls ingester.load_dataset()
2. Ingester loads raw_data table
3. Ingester updates metadata
4. Ingester calls _auto_calculate_l1_metrics() ← THE FIX
5. Async orchestration begins:
   a. Phase 1 executes: 11 metrics calculated
   b. All Phase 1 results committed to metrics_outputs
   c. Phase 2 executes: 2 derived metrics calculated
   d. Non Div ECF successfully reads Calc ECF from metrics_outputs
6. metrics_outputs populated with all L1 metrics
7. Pipeline logs successful metric calculation
8. Metrics immediately available for downstream analysis
9. No manual API calls required


THE FIX
═════════════════════════════════════════════════════════════════════════════════════════

Location: /backend/database/etl/ingestion.py
Method:   load_dataset()
Line:     After line 199

Change from:
    def load_dataset(self, csv_path: str, ...) -> Dict[str, Any]:
        ...
        result = self._load_raw_data(dataset_id, csv_path)
        self._update_dataset_metadata(dataset_id, result)
        return {
            'dataset_id': str(dataset_id),
            ...
        }

To:
    def load_dataset(self, csv_path: str, ...) -> Dict[str, Any]:
        ...
        result = self._load_raw_data(dataset_id, csv_path)
        self._update_dataset_metadata(dataset_id, result)
        
        # ✓ ADD THESE LINES:
        metrics_result = self._auto_calculate_l1_metrics(str(dataset_id))
        result['l1_metrics'] = metrics_result
        
        return {
            'dataset_id': str(dataset_id),
            ...
        }

Impact:
- Phase 1 metrics automatically calculated
- Calc ECF inserted into metrics_outputs
- Phase 2 metrics automatically calculated
- Non Div ECF successfully reads parent metric
- No manual API calls required
- metrics_outputs populated during ingestion


VERIFICATION STEPS
═════════════════════════════════════════════════════════════════════════════════════════

Step 1: Verify Phase 1 Results
SELECT COUNT(*) FROM metrics_outputs
WHERE dataset_id = 'test_dataset'
  AND output_metric_name IN ('Calc MC', 'Calc Assets', 'Calc ECF', ...);
Expected: 100+ rows per Phase 1 metric

Step 2: Verify Phase 2 Results
SELECT COUNT(*) FROM metrics_outputs
WHERE dataset_id = 'test_dataset'
  AND output_metric_name IN ('Non Div ECF', 'Calc FY TSR PREL');
Expected: 100+ rows for each Phase 2 metric

Step 3: Verify Non Div ECF Formula
SELECT 
  mo.ticker,
  mo.fiscal_year,
  mo.output_metric_value as non_div_ecf,
  (SELECT output_metric_value FROM metrics_outputs mo2
   WHERE mo2.dataset_id = mo.dataset_id
     AND mo2.ticker = mo.ticker
     AND mo2.fiscal_year = mo.fiscal_year
     AND mo2.output_metric_name = 'Calc ECF') as calc_ecf,
  COALESCE((SELECT numeric_value FROM fundamentals f
   WHERE f.dataset_id = mo.dataset_id
     AND f.ticker = mo.ticker
     AND f.fiscal_year = mo.fiscal_year
     AND f.metric_name = 'DIVIDENDS'), 0) as dividends
FROM metrics_outputs mo
WHERE dataset_id = 'test_dataset'
  AND output_metric_name = 'Non Div ECF'
LIMIT 5;
Expected: non_div_ecf = calc_ecf + dividends


KEY FILES AND LINE NUMBERS
═════════════════════════════════════════════════════════════════════════════════════════

Ingestion
├─ /backend/database/etl/ingestion.py:146-212     load_dataset() - ENTRY POINT
├─ /backend/database/etl/ingestion.py:214-244     _auto_calculate_l1_metrics() - MISSING CALL
└─ /backend/database/etl/ingestion.py:246-335     _async_calculate_l1_metrics() - IMPLEMENTATION

Metrics Orchestration
├─ /backend/app/services/metrics_service.py:494-647      calculate_batch_metrics() - TWO-PHASE
├─ /backend/app/services/metrics_service.py:523-540      L1_METRICS_PHASES - CONFIGURATION
├─ /backend/app/services/metrics_service.py:567-591      Phase 1 loop
├─ /backend/app/services/metrics_service.py:593-619      Phase 2 loop
├─ /backend/app/services/metrics_service.py:240-327      _execute_sql_function() - EXECUTOR
└─ /backend/app/services/metrics_service.py:329-400      _insert_metric_results_with_metadata() - INSERT & COMMIT

Database Functions
├─ /backend/database/schema/functions.sql:392-448        fn_calc_ecf() - PHASE 1, PARENT
└─ /backend/database/schema/functions.sql:454-480        fn_calc_non_div_ecf() - PHASE 2, DEPENDENT

API Endpoints (Runtime)
└─ /backend/app/api/v1/endpoints/orchestration.py:263-322    POST /api/v1/metrics/calculate-l1


SUMMARY TABLE
═════════════════════════════════════════════════════════════════════════════════════════

Aspect                              | Status      | Evidence
────────────────────────────────────────────────────────────────────────────────────────
_auto_calculate_l1_metrics exists   | ✓ Yes       | ingestion.py:214-244, 246-335
Function is called                  | ✗ NO        | Missing from load_dataset()
calculate_batch_metrics exists      | ✓ Yes       | metrics_service.py:494-647
Two-phase logic implemented         | ✓ Yes       | Lines 523-619
Phase 1 metrics in config           | ✓ Yes       | 11 metrics in PHASE 1
Phase 2 metrics in config           | ✓ Yes       | 2 metrics in PHASE 2
Non Div ECF in Phase 2              | ✓ Yes       | metrics_service.py:538
Calc ECF in Phase 1                 | ✓ Yes       | metrics_service.py:532
Database commit logic               | ✓ Correct   | Each metric commits
fn_calc_non_div_ecf exists          | ✓ Yes       | functions.sql:454-480
fn_calc_non_div_ecf reads metrics   | ✓ Yes       | WHERE output_metric_name = 'Calc ECF'
Parent metric (Calc ECF) in db      | ✗ NO        | Phase 1 never runs
Non Div ECF calculated              | ✗ NO        | Phase 2 never runs
metrics_outputs populated           | ✗ NO        | Phase 1 & 2 never run
Error handling                      | ✓ Graceful  | Silent failure on 0 rows
API endpoint works                  | ✓ Yes       | orchestration.py:263-322
Workaround available                | ✓ Yes       | Manual API call


CONCLUSION
═════════════════════════════════════════════════════════════════════════════════════════

ROOT CAUSE: Function _auto_calculate_l1_metrics() is never called during ingestion

IMPACT: Non Div ECF is not calculated during data ingestion. The parent metric 
        (Calc ECF) is never stored in metrics_outputs, so Phase 2 cannot execute.

SOLUTION: Add single function call at end of load_dataset() method

COMPLEXITY: LOW (single line addition)

FIX TIME: < 5 minutes

VERIFICATION: Query metrics_outputs table to confirm Phase 1 & 2 metrics are populated

═════════════════════════════════════════════════════════════════════════════════════════
