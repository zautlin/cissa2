# REQUIREMENTS.md — Phase 06: L1 Metrics Alignment

**Phase Goal:** Align all 12 L1 metrics with legacy system calculations using pure PostgreSQL stored procedures.

**Requirements Tracking:** Each requirement (REQ-XXX) corresponds to work that must be completed for Phase 06 success.

---

## REQUIREMENT GROUPS

### Group A: SQL Functions (Temporal Metrics Implementation)

#### REQ-A1: Implement LAG_MC Window Function
- **Description:** Create SQL function to calculate previous year market cap using LAG window function
- **Acceptance Criteria:**
  - Function: `fn_calc_lag_mc(p_dataset_id UUID)` returns (ticker, fiscal_year, lag_mc)
  - Uses `LAG(C_MC, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year)`
  - Handles NULL for first year in each ticker's sequence
  - Query performance: < 2 seconds for 11,000 records
- **Dependencies:** C_MC metric already calculated
- **Files Modified:** `backend/database/schema/functions.sql`
- **Effort Estimate:** 1 hour

#### REQ-A2: Implement ECF (Economic Cash Flow) Function
- **Description:** Create SQL function for economic cash flow with inception year logic
- **Formula:** `ECF = LAG_MC × (1 + fytsr/100) - C_MC` (when INCEPTION_IND == 1)
- **Acceptance Criteria:**
  - Function: `fn_calc_ecf(p_dataset_id UUID)` returns (ticker, fiscal_year, ecf)
  - Uses LAG_MC from metrics_outputs
  - Uses fytsr from fundamentals (input data, not calculated)
  - Only calculates when fiscal_year > companies.begin_year
  - NULL for inception year itself (expected behavior)
  - Results match legacy Python implementation
- **Dependencies:** LAG_MC, companies.begin_year defined
- **Files Modified:** `backend/database/schema/functions.sql`
- **Effort Estimate:** 2 hours

#### REQ-A3: Implement NON_DIV_ECF Function
- **Description:** Create SQL function for non-dividend economic cash flow
- **Formula:** `NON_DIV_ECF = ECF + DIVIDENDS`
- **Acceptance Criteria:**
  - Function: `fn_calc_non_div_ecf(p_dataset_id UUID)` returns (ticker, fiscal_year, non_div_ecf)
  - Joins metrics_outputs (ECF) with fundamentals (DIVIDENDS)
  - NULL propagates correctly if ECF is NULL
  - Query performance: < 2 seconds
- **Dependencies:** ECF metric calculated
- **Files Modified:** `backend/database/schema/functions.sql`
- **Effort Estimate:** 1 hour

#### REQ-A4: Implement EE (Economic Equity) Function
- **Description:** Create SQL function for cumulative economic equity with inception logic
- **Formula (component):** `IF INCEPTION_IND == 0: EE = TOTAL_EQUITY - MINORITY_INTEREST ELSE IF INCEPTION_IND == 1: EE = PROFIT_AFTER_TAX - ECF`
- **Formula (cumulative):** `EE_cumulative = SUM(EE_component) OVER (PARTITION BY ticker ORDER BY fiscal_year)`
- **Acceptance Criteria:**
  - Function: `fn_calc_ee(p_dataset_id UUID)` returns (ticker, fiscal_year, ee)
  - Uses inception logic: fiscal_year > companies.begin_year
  - Cumulative sum resets per ticker (not per dataset)
  - Partitions by BOTH ticker AND dataset_id in window function
  - Handles NULL inception years (begin_year IS NULL) gracefully
  - Results match legacy Python cumsum implementation
  - NUMERIC precision maintained over 60+ years
- **Dependencies:** ECF metric calculated, companies.begin_year NOT NULL
- **Files Modified:** `backend/database/schema/functions.sql`
- **Effort Estimate:** 2 hours

#### REQ-A5: Implement FY_TSR Function
- **Description:** Create SQL function for fiscal year total shareholder return with franking parameters
- **Formula:** Complex conditional with franking adjustments (see PROJECT.md for full formula)
- **Acceptance Criteria:**
  - Function: `fn_calc_fy_tsr(p_dataset_id UUID, p_param_set_id UUID)` returns (ticker, fiscal_year, fy_tsr)
  - Handles franking parameter variations (incl_franking, frank_tax_rate, value_franking_cr)
  - LAG_MC > 0 check (return NULL if not)
  - Only calculates when fiscal_year > companies.begin_year
  - Joins parameter_sets for param overrides
  - Results match legacy Python implementation exactly
  - Parameter sensitivity documented (same ticker/year produces different results per param_set)
- **Dependencies:** LAG_MC, ECF, companies.begin_year, parameter_sets configured
- **Files Modified:** `backend/database/schema/functions.sql`
- **Effort Estimate:** 3 hours

#### REQ-A6: Implement FY_TSR_PREL Function
- **Description:** Create SQL function for preliminary fiscal year TSR (simple arithmetic on FY_TSR)
- **Formula:** `FY_TSR_PREL = FY_TSR + 1` (when INCEPTION_IND == 1)
- **Acceptance Criteria:**
  - Function: `fn_calc_fy_tsr_prel(p_dataset_id UUID, p_param_set_id UUID)` returns (ticker, fiscal_year, fy_tsr_prel)
  - Simple arithmetic on FY_TSR metric
  - Only populated when FY_TSR is not NULL
  - NULL propagation correct
- **Dependencies:** FY_TSR metric calculated
- **Files Modified:** `backend/database/schema/functions.sql`
- **Effort Estimate:** 1 hour

---

### Group B: Configuration (Metrics Units & Parameters)

#### REQ-B1: Add Missing Metric Units to metric_units.json
- **Description:** Populate metric_units.json with 11 missing L1 output metrics
- **Metrics to Add:**
  - C_ASSETS: unit = "millions"
  - OA: unit = "millions"
  - OP_COST: unit = "millions"
  - NON_OP_COST: unit = "millions"
  - TAX_COST: unit = "millions"
  - XO_COST: unit = "millions"
  - ECF: unit = "millions"
  - NON_DIV_ECF: unit = "millions"
  - EE: unit = "millions"
  - FY_TSR_PREL: unit = "dimensionless" or "ratio"
- **Acceptance Criteria:**
  - All 11 entries added with correct units
  - metric_units.json validates as valid JSON
  - Database schema initialization loads all 12 output metrics
  - metric_units table has 31 total entries (20 input + 12 output - 1 overlap FY_TSR)
- **Files Modified:** `backend/database/config/metric_units.json`
- **Effort Estimate:** 30 min

#### REQ-B2: Document Parameter Set Configuration for Franking
- **Description:** Research and document required parameters for FY_TSR calculation
- **Acceptance Criteria:**
  - Document parameter names: incl_franking, frank_tax_rate, value_franking_cr
  - Document default values used in legacy system (or reasonable Australian tax defaults)
  - Verify parameter_sets table structure supports JSONB param_overrides
  - Create example param_override structure for franking scenarios
  - Document that parameter_sets.is_default=true uses baseline parameters
  - Verify "base_case" parameter set exists and is marked is_default=true
- **Files Modified:** `.planning/06-L1-Metrics-Alignment/PARAMETER_MAPPING.md` (new)
- **Effort Estimate:** 1.5 hours

#### REQ-B3: Add Franking Parameters to Database (if needed)
- **Description:** Ensure parameters table has entries for franking-related parameters
- **Acceptance Criteria:**
  - parameters table has rows for: incl_franking, frank_tax_rate, value_franking_cr
  - Each parameter has default_value set
  - parameter_sets.param_overrides can reference these parameters by name
  - "base_case" param_set has empty param_overrides (uses parameter defaults)
- **Files Modified:** `backend/database/schema/schema.sql` (initialization section)
- **Effort Estimate:** 1 hour (if needed; depends on Task 2 findings)

---

### Group C: API Integration & Wiring

#### REQ-C1: Update METRIC_FUNCTIONS Mapping in metrics_service.py
- **Description:** Add 5 temporal metrics to METRIC_FUNCTIONS mapping
- **Acceptance Criteria:**
  - METRIC_FUNCTIONS includes all 12 L1 metrics (not just current 7)
  - New entries: ECF, NON_DIV_ECF, EE, FY_TSR, FY_TSR_PREL
  - Mapping format: "Metric Name" → (fn_name, return_column_name)
  - Service layer can call all 12 SQL functions without errors
  - Batch insert in metrics_service._insert_metrics_batch handles all 12 metrics
- **Files Modified:** `backend/app/services/metrics_service.py`
- **Effort Estimate:** 1 hour

#### REQ-C2: Verify Parameter Set Resolution in API
- **Description:** Ensure API correctly resolves param_set_id for metrics calculations
- **Acceptance Criteria:**
  - Service layer queries parameter_sets correctly
  - Default param_set ("base_case") used if none specified
  - param_set_id included in metrics_outputs insert
  - Parameter-sensitive metrics (FY_TSR) use correct param_set_id
  - API documentation specifies param_set_id handling
- **Files Modified:** `backend/app/services/metrics_service.py`, `backend/app/api/v1/endpoints/metrics.py`
- **Effort Estimate:** 1.5 hours

#### REQ-C3: Verify Metrics Inserted into metrics_outputs
- **Description:** Test that all 12 L1 metrics successfully insert into metrics_outputs table
- **Acceptance Criteria:**
  - API call: POST /api/v1/metrics/calculate for each of 12 metrics returns 200 OK
  - metrics_outputs table populated with ~11,000 records per metric (for ~1000 companies × ~10 years)
  - UNIQUE constraint on (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name) enforced
  - No constraint violations during batch insert
  - Spot check: Sample values match legacy Python output
- **Files Modified:** None (verification only)
- **Effort Estimate:** 2 hours (testing + debugging)

---

### Group D: Data Quality & Validation

#### REQ-D1: Add NOT NULL Constraint to companies.begin_year
- **Description:** Ensure all companies have begin_year defined (required for inception logic)
- **Acceptance Criteria:**
  - ALTER TABLE companies ADD CONSTRAINT chk_begin_year_not_null CHECK (begin_year IS NOT NULL)
  - Existing data validated (no NULLs in begin_year)
  - Future data ingestion enforces NOT NULL
  - ERR if new company added without begin_year
- **Files Modified:** `backend/database/schema/schema.sql` (ALTER TABLE statement)
- **Effort Estimate:** 30 min

#### REQ-D2: Detect Year Gaps in Temporal Metrics
- **Description:** Identify and handle fiscal year gaps in LAG calculations
- **Acceptance Criteria:**
  - Documentation: explain year gap detection using `fiscal_year - ROW_NUMBER()`
  - Example: if ticker has years 2015, 2016, 2017, 2020 (skip 2018-2019), LAG shifts incorrectly
  - Solution: filter or warn if gap detected
  - Function comments explain the gotcha and mitigation
  - Test dataset includes year gaps; verify LAG behavior documented
- **Files Modified:** `backend/database/schema/functions.sql` (comments), `.planning/06-L1-Metrics-Alignment/GAP_DETECTION.md` (new)
- **Effort Estimate:** 1 hour

#### REQ-D3: Verify fytsr Input Data Exists
- **Description:** Confirm Bloomberg fundamentals include fytsr input data (not calculated)
- **Acceptance Criteria:**
  - Query fundamentals: SELECT DISTINCT metric_name WHERE metric_name = 'FY_TSR' returns rows
  - fytsr values present for years with inception_ind == 1
  - fytsr used AS-IS in ECF formula (no recalculation)
  - Documentation clarifies that fytsr is INPUT, not OUTPUT
- **Files Modified:** None (verification only)
- **Effort Estimate:** 30 min

---

### Group E: Documentation & Testing

#### REQ-E1: Create L1_METRICS_SQL_MAPPING.md
- **Description:** Comprehensive mapping document for all 12 metrics
- **Content:**
  - Legacy formula (from example-calculations/)
  - SQL equivalent (PostgreSQL syntax)
  - Column mappings (legacy → fundamentals)
  - Inception year logic for temporal metrics
  - Window function strategy
  - Parameter sensitivity (for FY_TSR)
  - Gotchas and edge cases
- **Files Created:** `.planning/06-L1-Metrics-Alignment/L1_METRICS_SQL_MAPPING.md`
- **Effort Estimate:** 2.5 hours

#### REQ-E2: Create Parameter_Sets Usage Guide
- **Description:** Document how parameter_sets table works for FY_TSR
- **Content:**
  - parameter_sets schema structure
  - param_overrides JSONB format
  - Example overrides for franking scenarios
  - Query patterns (filter by param_set_id)
  - Parameter sensitivity: how different param_sets produce different results
- **Files Created:** `.planning/06-L1-Metrics-Alignment/PARAMETER_MAPPING.md`
- **Effort Estimate:** 1 hour

#### REQ-E3: Write Unit Tests for All 12 Metrics
- **Description:** Create test cases to verify SQL functions return expected results
- **Test Strategy:**
  - Compare SQL output to legacy Python output (reference implementation)
  - Test edge cases: NULL inception years, year gaps, zero LAG_MC, etc.
  - Test parameter sensitivity: same data with different param_sets
  - Test batch calculation: all 12 metrics in single transaction
- **Acceptance Criteria:**
  - Test file: `backend/tests/test_l1_metrics.py`
  - All 12 SQL functions have tests
  - Tests pass with sample data
  - Coverage: > 90% of SQL functions
  - Performance tests: < 2 seconds per 11,000 records
- **Files Created:** `backend/tests/test_l1_metrics.py`
- **Effort Estimate:** 3 hours

#### REQ-E4: Verify Results Match Legacy Implementation
- **Description:** Compare output of 12 SQL metrics to legacy Python output
- **Acceptance Criteria:**
  - For sample dataset (100 companies × 10 years):
    - Simple metrics (7): Exact match (NUMERIC precision)
    - Temporal metrics (5): Match to 2 decimal places (rounding acceptable)
  - Document any discrepancies and reasons
  - Parameter-sensitive metrics (FY_TSR): Test with multiple param_sets
- **Effort Estimate:** 2 hours (testing + comparison)

---

## REQUIREMENT MAPPING TO TASKS

| Requirement | Task | Priority |
|-------------|------|----------|
| REQ-A1–A6 | Task 3: Implement 12 SQL stored procedures | CRITICAL |
| REQ-B1 | Task 1: Create L1_METRICS_SQL_MAPPING.md | HIGH |
| REQ-B2–B3 | Task 2: Review & update parameter_sets table | HIGH |
| REQ-C1–C3 | Task 4: API integration - wire up metrics_service.py | CRITICAL |
| REQ-D1–D3 | Task 1–3: Data quality validation (inline) | MEDIUM |
| REQ-E1–E4 | Task 1–4: Documentation & testing (inline) | MEDIUM |

---

## Success Criteria

Phase 06 is complete when ALL requirements satisfied:

1. ✅ All 12 L1 metrics have SQL functions (REQ-A1–A6)
2. ✅ Metric units defined for all 12 outputs (REQ-B1)
3. ✅ Parameter set configuration documented (REQ-B2–B3)
4. ✅ API integration complete (REQ-C1–C3)
5. ✅ Data quality checks pass (REQ-D1–D3)
6. ✅ Documentation and tests complete (REQ-E1–E4)
7. ✅ Results match legacy implementation (REQ-E4)

---

## Dependency Chain

```
REQ-D1 (NOT NULL constraint)
  ↓
REQ-A1 (LAG_MC) ← needs C_MC (already exists)
  ↓
REQ-A2 (ECF) ← needs LAG_MC + fytsr
  ↓
REQ-A3 (NON_DIV_ECF) ← needs ECF
REQ-A4 (EE) ← needs ECF + inception logic
  ↓
REQ-A5 (FY_TSR) ← needs LAG_MC + parameter_sets (REQ-B2)
  ↓
REQ-A6 (FY_TSR_PREL) ← needs FY_TSR
  ↓
REQ-C1 (METRIC_FUNCTIONS mapping) ← needs all SQL functions
  ↓
REQ-C2 (Parameter resolution) ← needs parameter_sets configured (REQ-B2)
  ↓
REQ-C3 (Verify metrics_outputs) ← everything above
  ↓
REQ-E3 (Unit tests) ← verify against REQ-E4
  ↓
Phase 06 Complete ✅
```
