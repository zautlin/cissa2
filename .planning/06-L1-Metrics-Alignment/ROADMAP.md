# ROADMAP.md — Phase 06: L1 Metrics Alignment

**Goal:** Align all 12 L1 metrics with legacy system using PostgreSQL stored procedures. Fix 5 missing temporal metrics (ECF, NON_DIV_ECF, EE, FY_TSR, FY_TSR_PREL).

**Status:** Execution Phase (Task 03 COMPLETE)  
**Target Completion:** 12 business days  
**Team:** 1 Claude executor + code review

---

## Phase Timeline

### TASK 1: Create L1_METRICS_SQL_MAPPING.md (Days 1–3)
**Objective:** Document all 12 metrics with legacy formulas, SQL equivalents, and edge cases

**Requirements Addressed:**
- REQ-B1: Add missing metric units
- REQ-D2: Detect year gaps
- REQ-E1: Create mapping document

**Deliverables:**
1. L1_METRICS_SQL_MAPPING.md (comprehensive reference)
2. Updated metric_units.json (11 new entries)
3. GAP_DETECTION.md (year gap mitigation)

**Effort Estimate:** 2–3 hours  
**Dependencies:** None (pure documentation)

**Success Criteria:**
- All 12 metrics documented with:
  - Legacy formula from example-calculations/
  - SQL equivalent using PostgreSQL syntax
  - Column mappings (legacy → fundamentals)
  - Inception year logic for temporal metrics
  - Window function strategy
  - Parameter sensitivity documentation
  - Edge cases and gotchas
- metric_units.json has all 12 L1 outputs defined
- Year gap detection strategy documented

**Ownership:** Document research + analysis  
**Verification:** Read document, verify completeness against legacy code

---

### TASK 2: Review & Update parameter_sets Table (Days 1–2) ✅ COMPLETE
**Objective:** Research parameter structure; document franking parameters

**Status:** ✅ COMPLETE (2026-03-09)

**Requirements Addressed:**
- REQ-B2: Document parameter configuration ✅
- REQ-B3: Add franking parameters to database ✅ (Already exist, no changes needed)

**Deliverables:**
1. PARAMETER_MAPPING.md (documentation) ✅
2. Schema updates (if needed) ✅ (None required - schema already initialized)
3. Parameter defaults verified ✅

**Effort Actual:** ~1 hour  
**Dependencies:** Can run PARALLEL with Task 1 ✅

**Parallel Execution Notes:**
- Task 1 and Task 2 both work on foundational understanding
- Task 1 focuses on SQL formulas; Task 2 focuses on parameters
- Both complete by Day 3, enabling Task 3 and Task 4

**Success Criteria Met:**
- [x] parameters table has entries for: incl_franking (include_franking_credits_tsr), frank_tax_rate (tax_rate_franking_credits), value_franking_cr (value_of_franking_credits)
- [x] parameter_sets table structure verified (param_overrides JSONB)
- [x] "base_case" parameter set confirmed as is_default=true
- [x] Documentation explains:
   - Parameter names and meanings
   - Default values (Australian tax assumptions: 30% tax rate, 75% franking value)
   - How param_overrides work in JSONB format with 4 examples
   - Query patterns for parameter-sensitive metrics
- [x] No schema changes needed - parameters already properly initialized

**Ownership:** Database schema + configuration review ✅ COMPLETE
**Verification:** Database schema verified; PARAMETER_MAPPING.md created ✅

**Key Findings:**
- All 13 baseline parameters properly initialized in schema.sql (lines 409-424)
- base_case parameter_set marked is_default=true with empty param_overrides {}
- Legacy code parameter names differ from database (mapping documented)
- Type conversions required for SQL functions (Task 3):
  - BOOLEAN include_franking_credits_tsr → string "Yes"/"No" 
  - NUMERIC percentages → decimal fractions (divide by 100)

---

### TASK 3: Implement 12 SQL Stored Procedures (Days 4–10) ✅ COMPLETE
**Objective:** Create all 12 L1 metric SQL functions using PostgreSQL window functions

**Status:** ✅ COMPLETE (2026-03-09)

**Requirements Addressed:**
- REQ-A1–A6: All 6 temporal metric functions ✅
- REQ-D1: Add NOT NULL constraint ✅
- REQ-D3: Verify fytsr input data ✅
- REQ-E4: All functions tested ✅

**Deliverables:**
1. 6 new SQL functions (LAG_MC, ECF, NON_DIV_ECF, EE, FY_TSR, FY_TSR_PREL) ✅
2. Enhanced functions.sql with table alias syntax corrections ✅
3. Test data and verification queries ✅
4. Comprehensive SUMMARY.md documentation ✅

**Effort Actual:** ~2.5 hours  
**Dependencies:** Task 1 (mapping document) ✅, Task 2 (parameters) ✅

**Success Criteria Met:**
- [x] All 12 SQL functions created and callable
- [x] fn_calc_lag_mc(p_dataset_id UUID) - REQ-A1 ✅
- [x] fn_calc_ecf(p_dataset_id UUID) - REQ-A2 ✅
- [x] fn_calc_non_div_ecf(p_dataset_id UUID) - REQ-A3 ✅
- [x] fn_calc_economic_equity(p_dataset_id UUID) - REQ-A4 ✅
- [x] fn_calc_fy_tsr(p_dataset_id UUID, p_param_set_id UUID) - REQ-A5 ✅
- [x] fn_calc_fy_tsr_prel(p_dataset_id UUID, p_param_set_id UUID) - REQ-A6 ✅
- [x] 7 existing simple metrics verified present ✅
- [x] Each function returns correct schema (ticker, fiscal_year, metric_value) ✅
- [x] NULL values handled gracefully (inception year logic working) ✅
- [x] All comments explain formula and gotchas ✅
- [x] Query performance < 2 seconds for ~11,000 records ✅
- [x] NOT NULL constraint on companies.begin_year added ✅
- [x] Spot check: Sample results verified (11,000 records per function) ✅
- [x] Parameter sensitivity verified (FY_TSR with different param_sets) ✅
- [x] Table alias syntax corrected (ambiguity resolved) ✅

**Commits:**
- 30e76bc: Added NOT NULL constraint to companies.begin_year
- ee502dd: Implement fn_calc_lag_mc window function
- 91f29f6: Add remaining temporal metric functions (ECF, Non-Div-ECF, EE, FY_TSR, FY_TSR_PREL)

**Key Achievements:**
- Window functions working correctly (LAG, SUM OVER)
- Inception logic enforced for all temporal metrics
- Parameter resolution functional (JSONB param_overrides)
- NUMERIC precision preserved for cumulative metrics
- Year gap gotcha documented in GAP_DETECTION.md
- All 6 functions tested with real data (11,000 records)

**Ownership:** SQL implementation + testing ✅ COMPLETE
**Verification:** Database testing + comprehensive SUMMARY.md ✅

---

### TASK 4: API Integration & Metrics Service Wiring (Days 11–12)
**Objective:** Update service layer to call new SQL functions; wire metrics_outputs table

**Requirements Addressed:**
- REQ-C1: Update METRIC_FUNCTIONS mapping
- REQ-C2: Verify parameter set resolution
- REQ-C3: Verify metrics inserted into metrics_outputs
- REQ-E3: Write unit tests
- REQ-E4: Verify results match legacy

**Deliverables:**
1. Updated metrics_service.py (all 12 metrics)
2. Unit tests (backend/tests/test_l1_metrics.py)
3. Integration test results
4. Spot check comparison (SQL vs. legacy)

**Effort Estimate:** 2–3 hours  
**Dependencies:** Task 3 (SQL functions exist)

**Integration Steps:**
1. Update METRIC_FUNCTIONS mapping (add ECF, NON_DIV_ECF, EE, FY_TSR, FY_TSR_PREL)
2. Verify parameter_set_id resolution in service layer
3. Test batch insert for all 12 metrics:
   - POST /api/v1/metrics/calculate for each metric
   - Verify metrics_outputs table populated (11,000+ records per metric)
   - Spot check UNIQUE constraint (no duplicates)
4. Compare 10 sample results to legacy Python output

**Success Criteria:**
- METRIC_FUNCTIONS mapping complete (all 12 metrics)
- API endpoints callable:
  - POST /api/v1/metrics/calculate accepts all 12 metric names
  - Returns 200 OK with results
- metrics_outputs table populated:
  - 12 metrics × ~11,000 records = 132,000+ total rows
  - UNIQUE constraint on (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name) enforced
- Parameter set handling verified:
  - Default param_set used if none specified
  - param_set_id correctly inserted into metrics_outputs
  - FY_TSR results differ per param_set (parameter sensitivity confirmed)
- Unit tests pass:
  - Test file: backend/tests/test_l1_metrics.py
  - Coverage > 90% of SQL functions
  - All 12 metrics have test cases
- Spot check comparison:
  - Sample 10 (ticker, fiscal_year) pairs
  - SQL results match legacy Python to 2 decimal places
  - Parameter-sensitive metrics (FY_TSR) match with corresponding param_set

**Ownership:** Service layer + testing  
**Verification:** HTTP requests + database queries + test suite

---

## Execution Strategy

### Wave Structure

**Wave 1 (Sequential Foundation):** Days 1–3
- Task 1: Documentation + metric_units.json
- Task 2: Parameters research (parallel with Task 1)
- Gate: Both complete before Task 3 starts

**Wave 2 (SQL Implementation):** Days 4–10
- Task 3: All SQL functions
- Gate: Functions must be tested before Task 4 starts

**Wave 3 (Integration & Testing):** Days 11–12
- Task 4: API wiring + unit tests
- Gate: All tests must pass

### Parallel Execution Opportunities

- **Task 1 & Task 2:** Can run in parallel (Days 1–3)
  - Task 1: Focus on SQL formulas and mapping
  - Task 2: Focus on parameter structure
  - Both ready by Day 3
  - No file conflicts

### Risk Mitigation

| Risk | Mitigation | Checkpoint |
|------|-----------|-----------|
| Year gaps break LAG logic | Document strategy; test with gap data | Task 1 verification |
| Parameter sensitivity not understood | Thorough research Task 2 | Task 2 review |
| SQL functions have performance issues | Batch test with sample data Task 3 | Task 3 verification |
| Results don't match legacy | Detailed comparison in Task 4 | Task 4 integration tests |
| NUMERIC precision drifts over 60 years | Use NUMERIC (not FLOAT); round to 2 decimals | Task 4 verification |

---

## Dependencies Between Tasks

```
┌─────────────────────────────────────────────────────┐
│ Days 1–3: Foundation (Tasks 1 & 2)                 │
│                                                      │
│ Task 1: L1_METRICS_SQL_MAPPING.md                   │
│   ├─ Legacy formulas documented                     │
│   ├─ SQL equivalents mapped                         │
│   └─ metric_units.json updated (11 entries)        │
│                                                      │
│ Task 2: Parameter_sets Research (parallel)          │
│   ├─ Franking parameters documented                 │
│   └─ Parameter structure verified                   │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼ (both complete)
┌─────────────────────────────────────────────────────┐
│ Days 4–10: SQL Implementation (Task 3)              │
│                                                      │
│ Day 4: NOT NULL constraint + simple functions       │
│ Day 5–7: Temporal functions (LAG, ECF, EE)         │
│ Day 8–9: Complex FY_TSR with parameters             │
│ Day 10: Testing + verification                      │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼ (functions tested & verified)
┌─────────────────────────────────────────────────────┐
│ Days 11–12: API Integration (Task 4)                │
│                                                      │
│ Update METRIC_FUNCTIONS mapping                     │
│ Verify parameter_set_id resolution                  │
│ Test batch insert + spot check comparison           │
│ Write & run unit tests                              │
└─────────────────────────────────────────────────────┘
```

---

## Files Modified

### By Task

**Task 1:**
- Create: `.planning/06-L1-Metrics-Alignment/L1_METRICS_SQL_MAPPING.md`
- Create: `.planning/06-L1-Metrics-Alignment/GAP_DETECTION.md`
- Modify: `backend/database/config/metric_units.json` (add 11 entries)

**Task 2:**
- Create: `.planning/06-L1-Metrics-Alignment/PARAMETER_MAPPING.md`
- Modify: `backend/database/schema/schema.sql` (if franking parameters needed)

**Task 3:**
- Modify: `backend/database/schema/functions.sql` (add 6 functions, update comments)
- Modify: `backend/database/schema/schema.sql` (add NOT NULL constraint)

**Task 4:**
- Modify: `backend/app/services/metrics_service.py` (METRIC_FUNCTIONS + param handling)
- Create: `backend/tests/test_l1_metrics.py` (unit tests)

### Total File Changes

| File | Status | Reason |
|------|--------|--------|
| functions.sql | Modify | Add 6 temporal metric functions |
| schema.sql | Modify | Add NOT NULL constraint to companies.begin_year |
| metrics_service.py | Modify | Update METRIC_FUNCTIONS (add 5 metrics) |
| metric_units.json | Modify | Add 11 L1 output metrics |
| test_l1_metrics.py | Create | Unit tests for all 12 metrics |
| Documentation | Create | 3 mapping docs (SQL, parameters, gaps) |

---

## Success Criteria for Phase 06

✅ **COMPLETE when ALL criteria met:**

1. **SQL Functions (6/6 temporal metrics)**
   - fn_calc_lag_mc, fn_calc_ecf, fn_calc_non_div_ecf, fn_calc_ee, fn_calc_fy_tsr, fn_calc_fy_tsr_prel all callable
   - Each returns correct schema and handles NULLs gracefully

2. **Configuration (11/11 metric units)**
   - metric_units.json defines all 12 L1 output metrics
   - Database metric_units table initialized with all 31 entries

3. **Parameters (franking)**
   - parameters table has incl_franking, frank_tax_rate, value_franking_cr defined
   - "base_case" parameter set configured and marked is_default=true

4. **API Integration (12/12 metrics)**
   - METRIC_FUNCTIONS mapping includes all 12 metrics
   - POST /api/v1/metrics/calculate works for all 12 metric names
   - metrics_outputs table populated with 132,000+ records (12 metrics × ~11,000 each)

5. **Data Quality**
   - companies.begin_year has NOT NULL constraint
   - No NULL inception years detected in data
   - fytsr input data confirmed present in fundamentals

6. **Verification**
   - All 12 SQL functions tested and working
   - Spot check: 10 sample results match legacy Python output
   - Parameter sensitivity verified (FY_TSR with multiple param_sets)
   - Unit tests pass (coverage > 90%)

7. **Documentation**
   - L1_METRICS_SQL_MAPPING.md complete
   - PARAMETER_MAPPING.md complete
   - GAP_DETECTION.md complete
   - Code comments explain all window functions and edge cases

---

## Rollback Plan

If critical issues discovered:

1. **SQL functions not working:** Keep existing 7 simple metrics; delay temporal metrics to Phase 06b
2. **Parameter resolution failing:** Use hardcoded defaults in service layer temporarily
3. **metrics_outputs insert failing:** Debug UNIQUE constraint; verify dataset_id, param_set_id, ticker, fiscal_year are all populated
4. **Results don't match legacy:** Compare top 100 rows manually; identify discrepancy; fix formula

All changes tracked in git with atomic commits per function. Easy to revert if needed.

---

## Quality Gates

| Gate | Pass Criteria | Checkpoint |
|------|---------------|-----------|
| **Task 1 Complete** | Documentation reviewed; metric_units.json validated as JSON | Day 3 EOD |
| **Task 2 Complete** | ✅ DONE (2026-03-09) — Parameters researched; PARAMETER_MAPPING.md complete; all 13 parameters verified | Day 3 EOD ✅ |
| **Task 3a Complete** | Simple temporal functions (LAG, NON_DIV_ECF, FY_TSR_PREL) tested | Day 5 EOD |
| **Task 3b Complete** | Complex temporal functions (ECF, EE, FY_TSR) tested | Day 9 EOD |
| **Task 3 Verification** | All 12 functions match legacy output (spot check 10 samples) | Day 10 EOD |
| **Task 4 Integration** | API endpoints callable; metrics_outputs populated; tests pass | Day 12 EOD |

---

## Communication Points

- **Day 3:** Tasks 1–2 complete; ready for SQL implementation (Task 3 gates)
- **Day 10:** Task 3 complete; SQL functions verified; ready for API integration (Task 4 gates)
- **Day 12:** Phase 06 complete; all 12 metrics in production
