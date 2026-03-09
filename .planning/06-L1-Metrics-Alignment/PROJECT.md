# PROJECT.md — Phase 06: L1 Metrics Alignment

**Phase Goal:** Align all 12 L1 metrics with legacy system calculations using pure PostgreSQL stored procedures. Fix 5 missing temporal metrics (ECF, NON_DIV_ECF, EE, FY_TSR, FY_TSR_PREL) that require window functions and inception year logic.

**Status:** Planning phase — Ready for execution  
**Last Updated:** 2026-03-09  
**Project:** CISSA Financial Data Pipeline

---

## What Exists (Brownfield Context)

### Current Database State
- **Backend deployed:** FastAPI service with 15 L1 metric calculations
- **7 simple metrics:** Already implemented in `backend/database/schema/functions.sql` (lines 9-98)
  - C_MC (Market Cap)
  - C_ASSETS (Operating Assets)
  - OA (Operating Assets Detail)
  - OP_COST (Operating Cost)
  - NON_OP_COST (Non-Operating Cost)
  - TAX_COST (Tax Cost)
  - XO_COST (Extraordinary Cost)
- **metrics_outputs table:** Fresh and empty, ready for testing (cleared after Phase 05)
- **parameter_sets table:** Baseline defined, but missing franking-related parameters

### Current Metric Units Coverage
- **Defined in metric_units.json:** 20 entries (all input metrics)
- **Missing output metrics:** 11 of 12 L1 output metrics NOT defined
  - C_MC and FY_TSR are the ONLY two output metrics currently in metric_units.json
  - Missing: C_ASSETS, OA, OP_COST, NON_OP_COST, TAX_COST, XO_COST, ECF, NON_DIV_ECF, EE, FY_TSR_PREL

### Legacy Reference Implementation
- **Source:** `example-calculations/src/executors/metrics.py` (lines 9-98)
- **Approach:** Python groupby + apply with explicit formulas
- **Key discovery:** `fytsr` (lowercase) is INPUT data from Bloomberg fundamentals, NOT a calculated output
  - This eliminates circular dependency between ECF and FY_TSR
  - Pure SQL solution is feasible

### Database Schema
- **fundamentals table:** Contains all input metrics (SPOT_SHARES, SHARE_PRICE, REVENUE, etc.)
- **companies table:** References company data including `begin_year` (for inception logic)
- **metrics_outputs table:** Stores calculated metrics with UNIQUE constraint on (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)

---

## What Needs Changing

### 1. Missing SQL Functions (5 temporal metrics)
**Current gap:** Only 7 simple metrics implemented; 5 temporal metrics missing entirely

**Impact:** 
- ECF, NON_DIV_ECF, EE, FY_TSR, FY_TSR_PREL cannot be calculated
- End users cannot access temporal metrics from API
- metrics_outputs table has no records for these metrics

**Fix required:**
- Implement 5 new SQL functions using PostgreSQL window functions (LAG, SUM OVER, etc.)
- Handle inception year logic: `fiscal_year > companies.begin_year` determines if temporal metrics are calculated
- Resolve circular dependency: Use historical `fytsr` from fundamentals as input to ECF formula

**Effort:** 6-8 hours (Task 3)

---

### 2. Metric Units Configuration (11 missing entries)
**Current gap:** metric_units.json only defines input metrics and 2 output metrics (C_MC, FY_TSR)

**Impact:**
- Cannot log/track units for 11 L1 output metrics
- API responses lack unit metadata
- Future queries cannot filter/group by unit

**Missing metric units:**
- Cost metrics: C_ASSETS, OA, OP_COST, NON_OP_COST, TAX_COST, XO_COST (all "millions" AUD)
- Temporal metrics: ECF, NON_DIV_ECF, EE (all "millions" AUD)
- Ratio metrics: FY_TSR_PREL (dimensionless / ratio)

**Fix required:** Add 11 entries to metric_units.json with appropriate units

**Effort:** 30 min (Task 1)

---

### 3. Parameter Set Configuration (Franking parameters)
**Current gap:** parameter_sets table initialized with empty param_overrides for "base_case"

**Impact:**
- FY_TSR calculation requires 3 parameters: incl_franking, frank_tax_rate, value_franking_cr
- Current parameters table has generic defaults but no franking-specific overrides
- Queries for FY_TSR are parameter-sensitive (same ticker/year produces different results for different parameter sets)

**Missing parameter configuration:**
- incl_franking: whether to include franking credits (values: "Yes" or "No")
- frank_tax_rate: tax rate for franking calculation (typical: 0.30 for 30% Australian tax)
- value_franking_cr: value of franking credit (typical: 0.75 for 75% valuation)

**Fix required:** Document required parameters and their defaults; ensure parameter_sets table can store these overrides

**Effort:** 1-2 hours (Task 2)

---

### 4. API Integration (metrics_service.py)
**Current gap:** Service layer wired for 7 simple metrics only; no support for new 5 temporal metrics

**Impact:**
- POST /api/v1/metrics/calculate cannot request temporal metrics
- METRIC_FUNCTIONS mapping doesn't include ECF, NON_DIV_ECF, EE, FY_TSR, FY_TSR_PREL
- metrics_outputs table receives no records for these metrics

**Fix required:**
- Update METRIC_FUNCTIONS mapping to include all 12 metrics (not just 7)
- Verify service layer calls new SQL functions correctly
- Test batch insertion of temporal metric results

**Effort:** 2-3 hours (Task 4)

---

## Database Column Mapping (Legacy → Fundamentals)

| Legacy Col | Fundamentals Metric | Phase | Type |
|-----------|-------------------|-------|------|
| shrouts | SPOT_SHARES | Input | Simple |
| price | SHARE_PRICE | Input | Simple |
| revenue | REVENUE | Input | Simple |
| opincome | OPERATING_INCOME | Input | Simple |
| pbt | PROFIT_BEFORE_TAX | Input | Simple |
| patxo | PROFIT_AFTER_TAX_EX | Input | Simple |
| pat | PROFIT_AFTER_TAX | Input | Simple |
| assets | TOTAL_ASSETS | Input | Simple |
| cash | CASH | Input | Simple |
| fixedassets | FIXED_ASSETS | Input | Simple |
| goodwill | GOODWILL | Input | Simple |
| eqiity | TOTAL_EQUITY | Input | Temporal |
| mi | MINORITY_INTEREST | Input | Temporal |
| dividend | DIVIDENDS | Input | Temporal |
| **fytsr** | **FY_TSR** | **Input** | **KEY** |
| inception | companies.begin_year | Reference | Temporal |

**CRITICAL FINDING:** `fytsr` is input data from Bloomberg fundamentals, NOT calculated. This means:
- ECF formula: `ECF = LAG_MC × (1 + fytsr/100) - C_MC` uses historical FY_TSR as input
- No circular dependency between ECF and FY_TSR calculation
- Pure SQL solution is feasible

---

## Key Technical Facts

### Inception Year Logic
```sql
-- Inception indicator: 1 if fiscal_year > companies.begin_year, else 0
-- Only calculate temporal metrics when INCEPTION_IND = 1
SELECT 
  fiscal_year,
  companies.begin_year,
  (fiscal_year > companies.begin_year)::INT AS inception_ind
FROM fundamentals
JOIN companies ON fundamentals.ticker = companies.ticker
```

**Impact:** First eligible fiscal year has NULL LAG_MC (no previous year), so ECF and FY_TSR are NULL for inception year—expected behavior.

### Window Function Strategy
All 5 temporal metrics require window functions:
- **LAG_MC:** `LAG(C_MC, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year)`
- **ECF:** Uses LAG_MC + historical fytsr
- **NON_DIV_ECF:** Simple arithmetic on ECF
- **EE:** Cumulative sum with inception logic: `SUM(...) OVER (PARTITION BY ticker ORDER BY fiscal_year)`
- **FY_TSR:** Complex formula with franking adjustments
- **FY_TSR_PREL:** Simple arithmetic on FY_TSR

### Parameter Sensitivity
FY_TSR output depends on parameter_set:
- Same (ticker, fiscal_year) can have multiple FY_TSR values (one per parameter_set)
- metrics_outputs.UNIQUE constraint allows this: (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
- Queries MUST filter by param_set_id to get unique results

---

## Execution Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Year gaps in fundamentals | HIGH | Detect with `fiscal_year - ROW_NUMBER()` ; document & warn in function comments |
| NULL inception year (begin_year IS NULL) | MEDIUM | Add NOT NULL constraint during Task 1; validate during data ingestion |
| Precision drift in EE cumsum over 60+ years | LOW | Use NUMERIC type (not FLOAT); round results to 2 decimals if needed |
| Division by zero (LAG_MC = 0) | MEDIUM | Use CASE statement with explicit checks (already in legacy formula) |
| Parameter confusion in queries | MEDIUM | Always filter by param_set_id; document in API spec; add schema comments |
| Dataset isolation (multiple dataset versions) | MEDIUM | Always filter by dataset_id; use _latest views for convenience |

---

## Related Documents

- **Legacy Code:** `example-calculations/src/executors/metrics.py` (lines 9-98) — Reference formulas
- **Current SQL:** `backend/database/schema/functions.sql` — Existing 7 simple metrics (lines 9-98)
- **Schema:** `backend/database/schema/schema.sql` — Table definitions + parameter_sets initialization
- **Metric Config:** `backend/database/config/metric_units.json` — Unit definitions (currently 20 entries)
- **Service Layer:** `backend/app/services/metrics_service.py` — METRIC_FUNCTIONS mapping

---

## Success Criteria

Phase 06 is complete when:
1. ✅ All 12 L1 metrics can be calculated from a single API request
2. ✅ metrics_outputs table populated with all 12 metrics (1000+ records per metric)
3. ✅ metric_units.json defines all 12 output metrics with correct units
4. ✅ parameter_sets table configured with franking parameters
5. ✅ Temporal metrics (ECF, EE, FY_TSR) produce results matching legacy Python implementation
6. ✅ Window function logic handles year gaps and NULL inception years gracefully
7. ✅ All queries filter by dataset_id and param_set_id correctly
