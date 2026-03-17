# CISSA Architecture Refactoring: Runtime Rf/KE Calculation

## Executive Summary

Refactor the metrics calculation system from **pre-computing all L1 metrics during ingestion** to a **hybrid approach**:
- **Pre-compute only:** Phase 1 (10 basic metrics) + Phase 2 (Beta with raw components in metadata)
- **Calculate at runtime:** Phase 3 (Cost of Equity) + Phase 4 (Risk-Free Rate)

This allows runtime selection of calculation approaches (fixed/floating beta, different bond indices) and rounding preferences without re-running the entire ingestion pipeline.

---

## Architecture Changes

### Current State (4 Phases Pre-Computed)
```
Ingestion Pipeline:
├─ Phase 1: 10 basic metrics (Calc MC, Calc Assets, Calc Op Cost, etc.) → stored
├─ Phase 2: Calc Beta (36-month rolling OLS) → stored with param_set_id=NULL
├─ Phase 4: Calc Rf (12-month rolling geometric mean) → stored
└─ Phase 3: Calc KE (Rf + Beta × RiskPremium) → stored
```

### Target State (2 Phases Pre-Computed)
```
Ingestion Pipeline:
├─ Phase 1: 10 basic metrics → stored (unchanged)
└─ Phase 2: Calc Beta → stored with param_set_id=NULL + raw components in metadata

Runtime API:
├─ GET /api/v1/metrics/risk-free-rate/calculate → Rf = 12-month rolling geometric mean
└─ GET /api/v1/metrics/cost-of-equity/calculate → KE = Rf + Beta × RiskPremium
```

---

## Phase 1 Metrics (Pre-Computed, Unchanged)

These 10 metrics are read from fundamentals and stored:

1. **Calc MC** - Market Capitalization
2. **Calc Assets** - Total Operating Assets
3. **Calc Op Cost** - Operating Cost
4. **Calc Non Op Cost** - Non-Operating Cost
5. **Calc Tax Cost** - Tax Cost
6. **Calc XO Cost** - Extraordinary Cost
7. **Calc ECF** - Economic Cash Flow
8. **Non Div ECF** - Non-Dividend ECF
9. **Calc EE** - Economic Equity
10. **Calc FY TSR** - Fiscal Year TSR

**Note:** Calc OA and Calc FY TSR PREL are Phase 2 temporal metrics but currently excluded from pre-computation phase grouping due to orchestrator parallelization. These will be handled separately in Phase 2 or as part of Phase 1 expansion.

---

## Phase 2: Beta Pre-Computation

**What changes:**
- Beta is still pre-computed during ingestion
- Stored with `param_set_id = NULL` (not tied to specific parameter set)
- Metadata includes raw beta components for runtime calculation:
  - `fixed_beta_raw` - Beta from fixed approach
  - `floating_beta_raw` - Beta from floating approach
  - `spot_slope_raw` - Raw slope at spot date
  - `fallback_tier_used` - Which tier was used as fallback
  - `monthly_raw_slopes` - Monthly rolling slopes
- `output_metric_value` = `fixed_beta_raw` (default for pre-computed)

**Runtime calculation flow:**
```
User Request with param_set_id + approach (fixed/floating) + rounding
  ↓
[Beta Service] Fetch pre-computed Beta from metrics_outputs (param_set_id=NULL)
  ↓
[Beta Rounding Service] Apply user's rounding to selected approach's raw value
  ↓
Return rounded Beta
```

---

## Phase 3: Risk-Free Rate (Runtime-Only)

**Currently:** Pre-computed during ingestion
**Target:** Runtime-only calculation

**Moved to:** `/api/v1/metrics/rates/calculate` (existing endpoint, refactored)

**Calculation Flow:**
```
Request: {dataset_id, param_set_id, approach: "fixed|floating", rounding}
  ↓
[Rf Service] Fetch monthly bond yields from fundamentals
  ↓
[Rf Service] Calculate 12-month rolling geometric mean
  ↓
[Rf Service] Apply approach logic:
     - Fixed: Rf = Benchmark Return - Risk Premium (static)
     - Floating: Rf = 12-month rolling mean (dynamic)
  ↓
[Rf Service] Apply rounding
  ↓
Return Rf value
```

**Why Runtime?**
- User may want to change bond indices per parameter set
- Approach (fixed vs floating) is parameter-set specific
- Rounding preference may vary
- Recalculation from raw bond data is fast (<1s for 100 tickers)

---

## Phase 4: Cost of Equity (Runtime-Only)

**Currently:** Pre-computed during ingestion
**Target:** Runtime-only calculation

**New Endpoint:** `/api/v1/metrics/cost-of-equity/calculate` (existing endpoint, refactored to runtime)

**Calculation Flow:**
```
Request: {dataset_id, param_set_id}
  ↓
[KE Service] Fetch pre-computed Beta (param_set_id=NULL) + apply param_set rounding
  ↓
[KE Service] Calculate Rf for this param_set (calls Rf Service)
  ↓
[KE Service] Calculate KE = Rf + Beta × RiskPremium
  ↓
Return KE value
```

**Why Runtime?**
- Depends on Beta being rounded first (which depends on param_set)
- Depends on Rf calculation (which is now runtime)
- Cannot be pre-computed without knowing user's parameter choices

---

## Implementation Tasks

### 1. Fix Beta Metadata Storage Bug
**File:** `backend/app/services/beta_precomputation_service.py`
**Status:** Code is correct, but verify metadata is being stored in database
**Action:** 
- Re-run ingestion pipeline after orchestrator fix
- Verify metadata JSON contains all raw components

### 2. Fix Orchestrator Dependency Ordering
**File:** `backend/app/api/v1/endpoints/orchestration.py`
**Status:** COMPLETED
**Change:** Reordered Phase 1 groups so `Calc OA` runs AFTER `Calc Assets` is inserted

### 3. Remove Phase 3 & 4 from Orchestrator
**File:** `backend/app/api/v1/endpoints/orchestration.py`
**Changes:**
- Remove Phase 4 (Risk-Free Rate) calculation block
- Remove Phase 3 (Cost of Equity) calculation block
- Update `phase_1_groups` comment to note dependency: "Calc OA depends on Calc Assets"
- Update response model to remove Phase 3/4 results
- Update endpoint docstring to reflect new 2-phase process
- Update total expected metrics from 17 to 12

**Before (lines 206-263):**
```python
# Phase 4 and Phase 3 blocks entirely removed
# Update overall stats calculation
total_successful = len(phase_1_successful) + len(phase_2_successful)
total_failed = len(phase_1_failed) + len(phase_2_failed)
```

### 4. Refactor Risk-Free Rate Service
**File:** `backend/app/services/risk_free_rate_service.py`
**Current:** Pre-computed, stores to metrics_outputs
**Target:** Runtime calculation, returns value without storage

**Changes:**
- Add new public method: `async def calculate_risk_free_rate_runtime(dataset_id, param_set_id) -> float`
- Keep existing method for backward compatibility but deprecate
- New method should:
  - Fetch monthly bond yields
  - Calculate rolling 12-month geometric mean
  - Apply approach logic (fixed/floating)
  - Apply rounding from param_set
  - Return single float value (not store to DB)

**Key Parameters from param_set:**
- `cost_of_equity_approach` - "Fixed" or "Floating"
- `equity_risk_premium` - Risk premium amount
- `beta_rounding` - Rounding precision
- `fixed_benchmark_return_wealth_preservation` - For fixed approach

### 5. Refactor Cost of Equity Service
**File:** `backend/app/services/cost_of_equity_service.py`
**Current:** Pre-computed, fetches Beta & Rf from metrics_outputs and calculates
**Target:** Runtime calculation, returns value without storage

**Changes:**
- Add new public method: `async def calculate_cost_of_equity_runtime(dataset_id, param_set_id) -> float`
- Keep existing method for backward compatibility but deprecate
- New method should:
  - Fetch pre-computed Beta with `param_set_id=NULL`
  - Get Beta metadata and apply param_set rounding
  - Call `RiskFreeRateCalculationService.calculate_risk_free_rate_runtime()`
  - Calculate KE = Rf + Beta × RiskPremium
  - Return single float value (not store to DB)

**Key equation:**
```
KE = Rf + Beta_rounded × (Risk_Premium from param_set)
```

### 6. Update Beta Calculation Endpoint
**File:** `backend/app/api/v1/endpoints/metrics.py`
**Current:** `/api/v1/metrics/beta/calculate` endpoint
**Target:** Support runtime mode with param_set_id

**Endpoint logic:**
```python
@router.post("/beta/calculate")
async def calculate_beta(request: CalculateBetaRequest):
    # request has: dataset_id, param_set_id
    
    # Try to fetch pre-computed Beta
    beta = fetch_precomputed_beta(dataset_id, param_set_id=NULL)
    
    if not beta:
        # Fallback: Calculate at runtime
        beta = await beta_service.calculate_beta_runtime(dataset_id)
    
    # Apply rounding from param_set
    beta_rounded = await beta_rounding_service.apply_rounding(
        beta, 
        param_set_id,
        approach=request.approach  # "fixed" or "floating"
    )
    
    return {
        "dataset_id": dataset_id,
        "param_set_id": param_set_id,
        "value": beta_rounded,
        "approach": request.approach,
        "rounding": rounding_value,
        "calculation_timestamp": now()
    }
```

### 7. Update Risk-Free Rate Endpoint
**File:** `backend/app/api/v1/endpoints/metrics.py`
**Current:** `/api/v1/metrics/rates/calculate` (pre-computed)
**Target:** `/api/v1/metrics/rates/calculate` (runtime-only)

**New endpoint logic:**
```python
@router.post("/rates/calculate")
async def calculate_risk_free_rate(request: CalculateRiskFreeRateRequest):
    # request has: dataset_id, param_set_id
    
    # Always calculate at runtime (no pre-computed version)
    rf_value = await risk_free_rate_service.calculate_risk_free_rate_runtime(
        dataset_id,
        param_set_id
    )
    
    return {
        "dataset_id": dataset_id,
        "param_set_id": param_set_id,
        "value": rf_value,
        "calculation_timestamp": now()
    }
```

### 8. Create/Update Cost of Equity Endpoint
**File:** `backend/app/api/v1/endpoints/metrics.py`
**Current:** `/api/v1/metrics/cost-of-equity/calculate` (pre-computed)
**Target:** `/api/v1/metrics/cost-of-equity/calculate` (runtime-only)

**New endpoint logic:**
```python
@router.post("/cost-of-equity/calculate")
async def calculate_cost_of_equity(request: CalculateCostOfEquityRequest):
    # request has: dataset_id, param_set_id
    
    # Always calculate at runtime
    ke_value = await cost_of_equity_service.calculate_cost_of_equity_runtime(
        dataset_id,
        param_set_id
    )
    
    return {
        "dataset_id": dataset_id,
        "param_set_id": param_set_id,
        "value": ke_value,
        "calculation_timestamp": now()
    }
```

### 9. Update Request/Response Models
**File:** `backend/app/models/schemas.py`

Add/update models:
```python
# For runtime calculations
class CalculateRiskFreeRateRequest(BaseModel):
    dataset_id: UUID
    param_set_id: UUID

class CalculateRiskFreeRateResponse(BaseModel):
    dataset_id: UUID
    param_set_id: UUID
    value: float
    calculation_timestamp: datetime
    approach: Optional[str] = None

class CalculateCostOfEquityRequest(BaseModel):
    dataset_id: UUID
    param_set_id: UUID

class CalculateCostOfEquityResponse(BaseModel):
    dataset_id: UUID
    param_set_id: UUID
    value: float
    calculation_timestamp: datetime
```

### 10. Update Unit Tests
**Files:** `backend/tests/unit/test_*.py`

**New tests to add:**
- `test_risk_free_rate_runtime_calculation.py`
- `test_cost_of_equity_runtime_calculation.py`
- `test_orchestrator_phase_12_only.py`

**Test scenarios:**
1. Runtime Rf calculation with fixed approach
2. Runtime Rf calculation with floating approach
3. Runtime KE calculation with different beta approaches
4. Runtime KE calculation with different risk premiums
5. Orchestrator with Phase 1 + Phase 2 only
6. Pre-computed Beta + Runtime Rf + Runtime KE chain

### 11. Integration Tests
**Files:** `backend/tests/integration/test_*.py`

**E2E flow to test:**
```
1. Run ingestion (Phase 1 + Phase 2 only)
   → Verify metrics_outputs has Phase 1 metrics + Beta metadata
   
2. Call /api/v1/metrics/beta/calculate with param_set_id
   → Returns rounded Beta for that param_set
   
3. Call /api/v1/metrics/rates/calculate with param_set_id
   → Returns Rf calculated at runtime
   
4. Call /api/v1/metrics/cost-of-equity/calculate with param_set_id
   → Returns KE = Rf + Beta × RiskPremium (all runtime/rounded)
   
5. Verify results are consistent across multiple calls
```

---

## Execution Order

### Phase A: Preparation (Current)
1. ✅ Fix orchestrator dependency ordering (Phase 1 groups)
2. Verify Beta metadata is stored correctly

### Phase B: Orchestrator Simplification
3. Remove Phase 3 & 4 from orchestrator (reduce to 2 phases)
4. Update orchestrator documentation

### Phase C: Runtime Service Implementation
5. Refactor Risk-Free Rate service (add runtime calculation)
6. Refactor Cost of Equity service (add runtime calculation)

### Phase D: Endpoint Updates
7. Update Beta calculation endpoint (support param_set_id)
8. Update Risk-Free Rate endpoint (runtime-only)
9. Update Cost of Equity endpoint (runtime-only)
10. Update request/response models

### Phase E: Testing & Verification
11. Add unit tests for runtime calculations
12. Add integration tests for E2E flow
13. Run test suite (target: all green)
14. Run ingestion pipeline with updated orchestrator
15. Verify Beta metadata in database

### Phase F: Rollout
16. Deploy changes
17. Update API documentation
18. Monitor runtime calculation performance

---

## Risk Mitigation

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Beta metadata not stored correctly | High | Verify after first ingestion run with fix |
| Runtime calculation slower than acceptable | Medium | Benchmark Rf + KE calculations (<1s target) |
| Parallel execution breaks after removing phases | Medium | Test orchestrator thoroughly with new groups |
| User confusion about pre-computed vs runtime | Medium | Clear API documentation & logging |
| Database migration issues | High | None needed (schema unchanged) |

### Rollback Strategy
1. Keep old orchestrator method available (don't delete)
2. Keep old Cost of Equity pre-computed endpoint (add version param)
3. If runtime is too slow, revert to Phase 3 & 4 pre-computation
4. Beta remains pre-computed (lowest risk)

---

## Performance Targets

| Calculation | Current | Target | Notes |
|---|---|---|---|
| Phase 1 pre-compute | 5-10s | <10s | Unchanged |
| Phase 2 Beta pre-compute | 15-20s | <20s | Unchanged |
| Runtime Rf calculation | N/A | <1s | New |
| Runtime KE calculation | N/A | <1s | New |
| Full orchestration | 25-35s | 20-30s | Saves Phase 3 & 4 pre-compute |

---

## Configuration Changes

### No Configuration Changes Required
- Parameter set structure remains the same
- Database schema unchanged
- API authentication/authorization unchanged

### New/Updated Parameters Used
- `cost_of_equity_approach` (existing, now used at runtime)
- `equity_risk_premium` (existing, now used at runtime)
- `beta_rounding` (existing, now used for runtime rounding)
- `fixed_benchmark_return_wealth_preservation` (existing, used for fixed Rf)

---

## Database Schema (No Changes)

```sql
cissa.metrics_outputs:
  dataset_id (UUID) - unchanged
  param_set_id (UUID) - still used, NULL for pre-computed Beta
  ticker (TEXT) - unchanged
  fiscal_year (INT) - unchanged
  output_metric_name (TEXT) - unchanged
  output_metric_value (NUMERIC) - unchanged
  metadata (JSONB) - contains Beta raw components
  created_at (TIMESTAMP) - unchanged
```

---

## Success Criteria

1. ✅ Orchestrator runs with 2 phases (Phase 1 + Phase 2 only)
2. ✅ Beta metadata contains all raw components after ingestion
3. ✅ Runtime Rf calculation completes in <1s
4. ✅ Runtime KE calculation completes in <1s
5. ✅ Can change approach/rounding per parameter set without re-running ingestion
6. ✅ End-to-end Beta → Rf → KE chain works correctly
7. ✅ All existing tests pass
8. ✅ New integration tests demonstrate the flow

---

## Documentation Updates

### API Documentation
- Update `/api/v1/metrics/calculate-l1` endpoint docs (2 phases instead of 4)
- Update `/api/v1/metrics/beta/calculate` docs (now supports param_set_id for rounding)
- Update `/api/v1/metrics/rates/calculate` docs (now runtime-only)
- Update `/api/v1/metrics/cost-of-equity/calculate` docs (now runtime-only)

### Developer Guide
- Add section: "Runtime Metric Calculations"
- Add: "How to add new runtime calculation endpoint"
- Update: "Orchestration flow" section with new 2-phase architecture

### Architecture Document
- Update: Phase 2 metadata structure with Beta raw components
- Add: Runtime calculation layer explanation
- Update: Data flow diagram

---

## Open Questions (For User)

None - all clarifications received. Ready to proceed with implementation.

---

## Timeline Estimate

| Phase | Tasks | Effort | Timeline |
|-------|-------|--------|----------|
| A | Orchestrator fix, verify Beta metadata | 30min | Today |
| B | Remove Phase 3 & 4 from orchestrator | 30min | Today |
| C | Refactor Rf & KE services | 2-3h | Tomorrow |
| D | Update endpoints & models | 2-3h | Tomorrow |
| E | Testing & verification | 4-6h | Next day |
| F | Deploy & monitor | 1-2h | Day 4 |
| **Total** | | **10-15h** | **3-4 days** |

