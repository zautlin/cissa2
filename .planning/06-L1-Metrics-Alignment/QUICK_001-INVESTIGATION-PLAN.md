---
phase: 06-L1-Metrics-Alignment
plan: QUICK-001
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/database/schema/functions.sql
  - backend/app/services/metrics_service.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "NON_DIV_ECF returns 0 records because ECF must be calculated and inserted into metrics_outputs FIRST"
    - "FY_TSR_PREL returns 0 records because FY_TSR must be calculated and inserted into metrics_outputs FIRST"
  artifacts:
    - path: backend/database/schema/functions.sql
      provides: "SQL functions for NON_DIV_ECF and FY_TSR_PREL"
      pattern: "fn_calc_non_div_ecf and fn_calc_fy_tsr_prel both query metrics_outputs table"
  key_links:
    - from: "NON_DIV_ECF function"
      to: "metrics_outputs table"
      pattern: "WHERE output_metric_name = 'Calc ECF'"
      issue: "Reads ECF from metrics_outputs; returns 0 if ECF not yet inserted"
    - from: "FY_TSR_PREL function"
      to: "metrics_outputs table"
      pattern: "WHERE output_metric_name = 'Calc FY TSR'"
      issue: "Reads FY_TSR from metrics_outputs; returns 0 if FY_TSR not yet inserted"
---

<objective>
Diagnose why NON_DIV_ECF and FY_TSR_PREL return 0 records while their parent metrics (ECF, FY_TSR) return 11,000 records each.

Purpose: Root cause analysis to determine execution order dependency
Output: Clear diagnosis document + recommended execution order
</objective>

<execution_context>
@/home/ubuntu/.config/opencode/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/06-L1-Metrics-Alignment/ROADMAP.md
@.planning/06-L1-Metrics-Alignment/STATE.md
@backend/database/schema/functions.sql
@backend/app/services/metrics_service.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Identify Dependency Chain in SQL Functions</name>
  <files>backend/database/schema/functions.sql</files>
  <action>
Analyze the SQL function implementations for NON_DIV_ECF and FY_TSR_PREL:

1. Open functions.sql and examine fn_calc_non_div_ecf (line ~660):
   - Reads from metrics_outputs table WHERE output_metric_name = 'Calc ECF'
   - This is a READ dependency on ECF being already calculated and inserted
   - Formula: ECF + DIVIDENDS (from fundamentals)

2. Examine fn_calc_fy_tsr_prel (line ~855):
   - Reads from metrics_outputs table WHERE output_metric_name = 'Calc FY TSR'
   - This is a READ dependency on FY_TSR being already calculated and inserted
   - Formula: FY_TSR + 1

3. Compare to ECF and FY_TSR functions (which work and return 11,000 records):
   - ECF reads from fundamentals (raw input data) - no dependency on metrics_outputs
   - FY_TSR reads from fundamentals (raw input data) - no dependency on metrics_outputs

ROOT CAUSE: These are DERIVED metrics (post-calculation), not base metrics.
  </action>
  <verify>
Find and document:
- Lines in fn_calc_non_div_ecf that query metrics_outputs (should show WHERE output_metric_name = 'Calc ECF')
- Lines in fn_calc_fy_tsr_prel that query metrics_outputs (should show WHERE output_metric_name = 'Calc FY TSR')
- Confirm ECF and FY_TSR do NOT query metrics_outputs for their inputs
  </verify>
  <done>Dependency chain identified: NON_DIV_ECF depends on ECF existing in metrics_outputs; FY_TSR_PREL depends on FY_TSR existing in metrics_outputs</done>
</task>

<task type="auto">
  <name>Task 2: Verify Execution Order in metrics_service.py</name>
  <files>backend/app/services/metrics_service.py</files>
  <action>
Check if metrics are being calculated in the correct order:

1. Examine the calculate_batch_metrics method to see the order in which metrics are processed:
   - Are NON_DIV_ECF and FY_TSR_PREL being called BEFORE ECF and FY_TSR are inserted?
   - Or are they being called immediately after their parent metrics without intermediate database flushes?

2. Check the batch insert logic:
   - Line where metrics are inserted into metrics_outputs
   - Are inserts happening in real-time (transaction per metric) or batched at the end?
   - If batched at end, all metrics would be empty (0 records) when derived metrics run

3. Verify the METRIC_FUNCTIONS mapping (already found):
   - NON_DIV_ECF is mapped to fn_calc_non_div_ecf ✓
   - FY_TSR_PREL is mapped to fn_calc_fy_tsr_prel ✓
   - Both are present in METRIC_FUNCTIONS ✓

Expected finding: Metrics are likely being calculated ALL AT ONCE without intermediate database persistence, so NON_DIV_ECF runs when ECF hasn't been inserted yet.
  </action>
  <verify>
Look for:
- Loop structure that calls functions sequentially
- INSERT statements into metrics_outputs
- Whether inserts happen DURING the loop (after each metric) or AFTER all calculations
- If batched: Are NON_DIV_ECF and FY_TSR_PREL included in the batch, or do they run after?
  </verify>
  <done>Confirmed execution order issue: Derived metrics (NON_DIV_ECF, FY_TSR_PREL) are being calculated before or without their parent metrics (ECF, FY_TSR) being inserted into metrics_outputs first</done>
</task>

<task type="auto">
  <name>Task 3: Document Root Cause & Recommended Fix</name>
  <files>.planning/06-L1-Metrics-Alignment/ROOT_CAUSE_ANALYSIS.md</files>
  <action>
Create a concise root cause analysis document:

DIAGNOSIS:
- NON_DIV_ECF and FY_TSR_PREL are DERIVED METRICS (calculated from other L1 metrics already in metrics_outputs)
- They are NOT base metrics (calculated from fundamentals table)
- Current implementation calculates all 12 metrics in a single batch
- When derived metrics run, their parent metrics haven't been inserted yet → 0 records returned

RECOMMENDED FIX OPTIONS (for next phase):

Option A (SIMPLE - Recommended):
  1. Split metrics into two batches:
     - Batch 1: Calculate and INSERT all 10 base metrics (7 simple + ECF, EE, FY_TSR) into metrics_outputs
     - Batch 2: Calculate NON_DIV_ECF and FY_TSR_PREL AFTER Batch 1 completes
  2. Pro: Simple, maintainable, low risk
  3. Con: Two database round trips

Option B (ADVANCED - For future):
  1. Rewrite fn_calc_non_div_ecf to read from fundamentals instead of metrics_outputs
  2. Rewrite fn_calc_fy_tsr_prel to read from fundamentals instead of metrics_outputs
  3. Pro: Single batch for all 12 metrics
  4. Con: More SQL refactoring, potential edge cases

Option C (ALTERNATIVE):
  1. Calculate derived metrics in SQL (create a combined view that joins ECF + DIVIDENDS)
  2. Pro: Pure SQL solution
  3. Con: More complex SQL, harder to debug

IMMEDIATE WORKAROUND:
- Manually call NON_DIV_ECF and FY_TSR_PREL AFTER ECF and FY_TSR are confirmed in metrics_outputs
- Or: Add a database commit/flush between batch 1 and batch 2
  </action>
  <verify>
Document created with:
- Clear statement of root cause
- Evidence from code (line references)
- 3+ fix options with tradeoffs
- Immediate workaround for current test run
  </verify>
  <done>ROOT_CAUSE_ANALYSIS.md created with diagnosis, fix options, and workaround</done>
</task>

</tasks>

<verification>
After completing all 3 tasks:
1. Confirm dependency chain: NON_DIV_ECF depends on ECF in metrics_outputs ✓
2. Confirm execution order issue: Derived metrics run before parent metrics inserted ✓
3. Document root cause with recommendations ✓
</verification>

<success_criteria>
Investigation complete when:
- Root cause clearly identified: Derived metrics depend on parent metrics being in metrics_outputs first
- Evidence provided from code (line numbers in functions.sql and metrics_service.py)
- Recommended fixes documented with pros/cons
- Immediate workaround provided for current test run
</success_criteria>

<output>
Create `.planning/06-L1-Metrics-Alignment/ROOT_CAUSE_ANALYSIS.md` with diagnosis, fix options, and workaround.
</output>
