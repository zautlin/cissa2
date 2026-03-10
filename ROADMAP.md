# ROADMAP - CISSA Financial Data Pipeline

**Project Goal:** Build a comprehensive financial metrics calculation system that ingests fundamentals data, computes L1/L2/L3 metrics, and exposes them via RESTful API endpoints.

**Current Status:** Phases 1-8 complete. Phase 09 in-progress (Cost of Equity). Short-term focus: complete Phase 09 quality fixes + Phase 10.

---

## Phase Overview

| Phase | Name | Status | Effort | Key Output |
|-------|------|--------|--------|-----------|
| 1-5 | Fundamentals ETL | ✅ Complete | - | Raw financial data in DB |
| 06 | L1 Basic Metrics | ✅ Complete | - | 12 basic calculations |
| 07 | L1 Beta Calculation | ✅ Complete | - | Rolling OLS regression (9K records) |
| 08 | L1 Risk-Free Rate | ✅ Complete | - | Geometric mean rates (21.5K records) |
| **09** | **Cost of Equity (KE)** | 🔧 Bug Fix Needed | Small | Remove Beta duplication, refactor endpoint |
| 10 | [TBD] | Planned | TBD | TBD |

---

## Phase 09: Cost of Equity - Quality Fix

**Goal:** Fix endpoint design consistency and remove metric calculation duplication.

**Current State:**
- KE calculation works but has 2 issues:
  1. Endpoint uses `/calculate-enhanced` (inconsistent with `/beta/calculate`, `/rates/calculate` pattern)
  2. EnhancedMetricsService still has deprecated `_calculate_beta()` method causing confusion

**Tasks:**
1. Refactor endpoint from `/calculate-enhanced` to `/cost-of-equity/calculate` (already done in endpoints file)
2. Verify CostOfEquityService exists and doesn't recalculate Beta (already done)
3. Update shell script `run-l1-cost-of-equity-calc.sh` endpoint call to `/cost-of-equity/calculate`
4. Clean up EnhancedMetricsService or deprecate it (decide: keep for future L3 metrics or remove)
5. Verify no duplicate Beta records inserted, all KE calculations correct

**Success Criteria:**
- ✓ Endpoint follows resource-first URL pattern
- ✓ Shell script calls correct endpoint
- ✓ All KE calculations work correctly
- ✓ Total KE records = ~12.6K (1 per ticker + fiscal_year combination with Beta + Rf data)

**Estimated Effort:** 1-2 hours

---

## Phase 10: [Requires Investigation]

**Goal:** TBD - Implement next set of metrics from legacy pipeline.

**Prerequisites:**
- Phase 09 complete and verified
- Legacy code analysis to identify Phase 10 metrics

**Placeholder:** To be determined after Phase 09 quality review.

---

## Architecture Principles

All phases should follow these patterns:

### API Endpoints
Resource-first pattern: `/api/v1/metrics/{resource}/calculate`

Examples:
- POST `/api/v1/metrics/beta/calculate` (Phase 07)
- POST `/api/v1/metrics/rates/calculate` (Phase 08)
- POST `/api/v1/metrics/cost-of-equity/calculate` (Phase 09)

### Service Layer
One service per phase: `phase0X_metric_name_service.py`

Location: `backend/app/services/`

Examples:
- `phase07_beta_calculation_service.py`
- `phase08_risk_free_rate_service.py`
- `phase09_cost_of_equity_service.py`

### Shell Scripts
One script per metric: `run-l1-{metric}-calc.sh`

Location: `backend/scripts/`

Examples:
- `run-l1-beta-calc.sh`
- `run-l1-rf-calc.sh`
- `run-l1-cost-of-equity-calc.sh`

### Database
All results → `cissa.metrics_outputs` table

Metadata: `{"metric_level": "L1|L2|L3", "calculation_source": "phase0X_service_name"}`

---

## Known Issues & Decisions

### 1. **Phase 09 Endpoint Pattern Inconsistency** ✅ FIXED

**Issue:** Phase 09 originally used `/calculate-enhanced` while Phase 07/08 use resource-first pattern.

**Decision:** Standardize all to resource-first pattern.

**Resolution:** 
- Endpoint changed to `/cost-of-equity/calculate`
- Service: `Phase09CostOfEquityService`
- Shell script updated with correct endpoint

### 2. **Phase 09 Service Architecture** ✅ VERIFIED

**Issue:** Initial concern about Beta recalculation in enhanced_metrics_service.

**Decision:** Create dedicated `Phase09CostOfEquityService` that fetches existing Beta/Rf instead of recalculating.

**Resolution:**
- `phase09_cost_of_equity_service.py` implemented
- Fetches Beta from Phase 07 results
- Fetches Rf_1Y from Phase 08 results
- Calculates KE = Rf + Beta × RiskPremium
- No duplicate Beta records inserted

### 3. **Enhanced Metrics Service Legacy** ⚠️ DECISION NEEDED

**Issue:** `EnhancedMetricsService` has deprecated Beta calculation method.

**Current State:** 
- Still imported in endpoints
- Has `_calculate_beta()` that returns default 1.0
- Also has Rf and Financial Ratios calculations

**Options:**
- **Option A:** Remove from codebase (replaced by Phase-specific services)
- **Option B:** Keep for L3 metrics (future financial ratios calculations)
- **Option C:** Deprecate but keep as reference

**Recommendation:** Option A (remove) - all Phase 09 metrics now in dedicated service

---

## Migration Path: Phase 08 → Phase 09 → Phase 10

### Phase 08 Output (Risk-Free Rate)
```
metrics_outputs:
  - Rf_1Y_Raw: Raw annualized 1-year rate
  - Rf_1Y: Rounded annualized 1-year rate  
  - Rf: Final risk-free rate (after approach logic)
```

### Phase 09 Input → Process → Output

```
Phase 07 (Beta) + Phase 08 (Rf_1Y) → KE Calculation → Phase 09 (Calc KE)

Expected Volume:
  - ~9,200 Beta records (Phase 07)
  - ~21,500 Rf records (Phase 08, across 3 metric types)
  - ~12,600 KE records (Phase 09, 1 per ticker-year with both Beta + Rf)
```

### Phase 10 (TBD)
- Depends on Phase 09 completion
- Likely candidates: WACC, Terminal Value, or Advanced Ratios
- To be determined after legacy code review

---

## Performance Baselines

| Operation | Records | Expected Time | Status |
|-----------|---------|---------------|--------|
| Phase 07 Beta (OLS) | 9,200 | 15-20s | ✅ Verified |
| Phase 08 Rf (Geometric mean) | 21,500 | 10-15s | ✅ Verified |
| Phase 09 KE (Vectorized) | 12,600 | 5-10s | ⚠️ To verify |

---

## Database State

### Current Metrics in metrics_outputs

| Metric | Phase | Count | Status |
|--------|-------|-------|--------|
| C_MC, C_ASSETS, OA, OP_COST, NON_OP_COST, TAX_COST, XO_COST | 06 | 77,000 | ✅ |
| ECF, NON_DIV_ECF, EE, FY_TSR, FY_TSR_PREL | 06 | 44,408 | ✅ |
| Beta | 07 | 9,200 | ✅ |
| Rf_1Y_Raw, Rf_1Y, Rf | 08 | 21,500 | ✅ |
| **Calc KE** | **09** | **~12,600** | **🔧 In progress** |

**Total:** 161,600+ records across 5 phases

---

## Next Steps

1. **Complete Phase 09 quality fix** (2-3 hours)
   - Verify endpoint refactoring
   - Update shell script
   - Run integration tests
   - Verify KE record count

2. **Identify Phase 10 metrics** (4-8 hours)
   - Review legacy code for next priority metrics
   - Analyze Phase 10 data requirements
   - Estimate effort and dependencies

3. **Plan Phase 10** (2-4 hours)
   - Define success criteria
   - Identify data sources
   - Design API endpoints
   - Create Phase 10 project plan

---

**Last Updated:** 2026-03-10  
**Project Maintainer:** OpenCode  
**Repository:** /home/ubuntu/cissa
