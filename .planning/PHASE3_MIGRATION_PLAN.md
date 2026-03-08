# Phase 3 Migration Plan: Complete Legacy Code to FastAPI Backend

**Goal:** Migrate Beta, Cost of Equity, and all other L2 metrics from legacy code to FastAPI Python service layer, with database results visible in metrics_outputs.

**Status:** Ready to implement

---

## What We're Migrating

Based on analysis of the legacy codebase (`example-calculations/src/`), here's what needs to be moved:

### Current Legacy Calculation Chain

```
generate_l2_metrics.py
  └─> calculation.calculate_L2_metrics_async()
      ├─> Fetches L1 metrics from database (C_MC, EE, ECF, etc.)
      ├─> Fetches annual financial data (fytsr, pat, revenue, etc.)
      ├─> Runs metrics.generate_l2_metrics() for each ticker
      │   └─> Calculates: EP, PAT_EX, FC (franking credits)
      ├─> Runs calculation.calculate_cost_of_eqity()
      │   ├─> Merges Beta + Risk-Free Rate
      │   └─> Calculates: KE (Cost of Equity) = Rf + Beta * Risk Premium
      ├─> Runs calculation.calculate_aggregated_metrics_async()
      │   └─> Calculates: ROA, ROE, Profit Margins, Ratios
      └─> Runs calculation.calculate_sector_metrics()
          └─> Aggregates by sector
```

### Metrics Being Calculated

| Metric | Formula | Input Data | Status |
|--------|---------|-----------|--------|
| **Beta** | Rolling OLS of stock returns vs market returns | Returns data (timeseries) | ⏳ TODO |
| **Risk-Free Rate (Rf)** | Lookup from precomputed table + default fallback | rf_lookup table | ⏳ TODO |
| **Cost of Equity (KE)** | Rf + Beta * Risk Premium | Beta + Rf + Risk Premium param | ⏳ TODO |
| **Economic Profit (EP)** | PAT - KE * Economic Equity | PAT + KE + EE | ⏳ TODO |
| **PAT Extraordinary (PAT_EX)** | EP / abs(EE_OPEN + KE) * EE_OPEN | EP + EE + KE | ⏳ TODO |
| **Franking Credits (FC)** | -Dividend / (1 - Tax Rate) * Tax Rate * Franking Value | Dividend + Tax params | ⏳ TODO |
| **TSR (Total Shareholder Return)** | Change in Capital / Prior Market Cap | Market Cap + Economic Cash Flow | ⏳ TODO (simple formula) |
| **ROA, ROE, Margins, Ratios** | Various ratios | L1 metrics + fundamentals | ⏳ TODO |

---

## Architecture Decision

### Option A: Keep Phase 2 L2 Service As-Is + Add Phase 3 Services
- Pro: Phase 2 stays unchanged
- Con: Overlap — Phase 2 and Phase 3 both calculating metrics
- **Decision: NOT RECOMMENDED**

### Option B: **RECOMMENDED** Replace Phase 2 L2 Service with Complete Legacy Migration
- Migrate ALL legacy L2 calculations into a single comprehensive service
- Single source of truth
- Easier to maintain
- Matches legacy calculation flow exactly

**We're going with Option B.**

---

## Phase 3 Implementation Structure

### Single Service: `EnhancedMetricsService` (replaces current L2 service)

```
backend/app/services/enhanced_metrics_service.py
├── Core calculation steps:
│   ├── 1. Fetch L1 metrics (from Phase 1)
│   ├── 2. Fetch fundamentals + timeseries data
│   ├── 3. Calculate Beta (rolling OLS)
│   ├── 4. Calculate Risk-Free Rate (lookup + fallback)
│   ├── 5. Calculate Cost of Equity (KE = Rf + Beta * Risk Premium)
│   ├── 6. Calculate Economic Profit (EP, PAT_EX, FC)
│   ├── 7. Calculate TSR & Franking
│   ├── 8. Calculate Ratios (ROA, ROE, Margins, etc.)
│   └── 9. Store results in metrics_outputs
│
├── Private methods (pure calculation):
│   ├── _calculate_beta_rolling_ols()
│   ├── _calculate_rf_with_fallback()
│   ├── _calculate_cost_of_equity()
│   ├── _calculate_economic_profit()
│   ├── _calculate_ratios()
│   └── _calculate_tsr_with_franking()
│
├── Data fetch methods:
│   ├── _fetch_l1_metrics()
│   ├── _fetch_fundamentals()
│   ├── _fetch_timeseries_returns()
│   ├── _fetch_rf_lookup()
│   └── _fetch_market_returns()
│
└── Storage method:
    └── _insert_metrics_batch()
```

### New Pydantic Schemas

```python
class CalculateEnhancedMetricsRequest(BaseModel):
    dataset_id: UUID
    param_set_id: UUID
    
    # Parameters from legacy config/parameters.py
    error_tolerance: float = 0.8          # Beta adjustment
    approach_to_ke: str = "Floating"      # "FIXED" or "Floating"
    beta_rounding: float = 0.1
    risk_premium: float = 0.05
    country: str = "AUS"
    currency: str = "AUD"
    incl_franking: str = "Yes"            # "Yes" or "No"
    frank_tax_rate: float = 0.3
    value_franking_cr: float = 0.75
    benchmark_return: float = 0.075
    exchange: str = "ASX"
    franking: float = 1.0
    
class CalculateEnhancedMetricsResponse(BaseModel):
    dataset_id: UUID
    results_count: int
    metrics_calculated: List[str]
    status: str = "success"
    message: Optional[str] = None
```

### New API Endpoint

```python
@router.post("/api/v1/metrics/calculate-enhanced")
async def calculate_enhanced_metrics(
    request: CalculateEnhancedMetricsRequest,
    db: AsyncSession = Depends(get_db)
) -> CalculateEnhancedMetricsResponse:
    """
    Calculate all Phase 3 metrics (Beta, KE, EP, Ratios, etc.)
    """
    service = EnhancedMetricsService(db)
    return await service.calculate_enhanced_metrics(request)
```

---

## Execution Steps

### Step 1: Understand Legacy Code (30 min)
- Read `example-calculations/src/executors/metrics.py` (L1/L2 formulas)
- Read `example-calculations/src/executors/beta.py` (rolling OLS)
- Read `example-calculations/src/executors/rates.py` (Rf lookup)
- Read `example-calculations/src/engine/calculation.py` (orchestration)
- Note: Focus on formulas, not legacy data structures

### Step 2: Create Service Skeleton (1 hour)
- Create `backend/app/services/enhanced_metrics_service.py`
- Copy Phase 2 service as template
- Add all method stubs (not implemented yet)
- Add logging throughout

### Step 3: Implement Data Fetching (1 hour)
- `_fetch_l1_metrics()` — Query L1 from metrics_outputs (already exists in Phase 2)
- `_fetch_fundamentals()` — Query fundamentals table (already exists in Phase 2)
- `_fetch_timeseries_returns()` — Query market returns from timeseries table
- `_fetch_rf_lookup()` — Query precomputed rates from rf_lookup table

### Step 4: Implement Beta Calculation (2-3 hours)
- Port `executors/beta.py` logic to Python (don't use statsmodels — too heavy)
- Implement rolling OLS using numpy or sklearn
- Implement 4-tier fallback logic
- Test: Compare against legacy output

### Step 5: Implement Risk-Free Rate (1 hour)
- Port `executors/rates.py` lookup logic
- Add fallback to default_rf parameter
- Test: Verify lookups work, defaults applied

### Step 6: Implement Cost of Equity (30 min)
- Port `calculation.calculate_cost_of_eqity()` formula
- Formula: KE = Rf + Beta * Risk Premium
- Test: Verify calculations match legacy

### Step 7: Implement Economic Profit & Other L2 Metrics (2 hours)
- Port `metrics.generate_l2_metrics()` formulas
- Calculate: EP, PAT_EX, FC, TSR, ROA, ROE, Margins, etc.
- Test: Compare against legacy output

### Step 8: Add Schemas & Endpoint (30 min)
- Create Pydantic models for request/response
- Create FastAPI endpoint
- Wire service to endpoint

### Step 9: Test End-to-End (1-2 hours)
- Start API
- Call endpoint with test dataset
- Verify results in metrics_outputs
- Compare vs legacy output
- Measure performance

### Step 10: Clean Up & Document (30 min)
- Add docstrings
- Update __init__.py files
- Update project documentation

---

## Data Requirement Checklist

Before starting, verify you have these tables populated:

```bash
# Check fundamentals
psql -U postgres -d cissa -c "SELECT COUNT(*) FROM cissa.fundamentals;"

# Check L1 metrics (Phase 1 output)
psql -U postgres -d cissa -c "SELECT COUNT(*) FROM cissa.metrics_outputs WHERE output_metric_name LIKE 'Calc %';"

# Check timeseries returns (for Beta)
psql -U postgres -d cissa -c "SELECT COUNT(*) FROM cissa.timeseries WHERE metric_type='MARKET_RETURN';"

# Check risk-free rate lookups
psql -U postgres -d cissa -c "SELECT COUNT(*) FROM cissa.rf_lookup;"
```

If any are 0, those need to be loaded first.

---

## Success Criteria

✅ Phase 3 migration is complete when:

- [ ] EnhancedMetricsService created and functional
- [ ] Beta calculated via rolling OLS (statsmodels or numpy)
- [ ] Rf calculated from lookup + fallback
- [ ] KE calculated from Rf + Beta + Risk Premium
- [ ] EP, PAT_EX, FC calculated
- [ ] TSR calculated with franking adjustment
- [ ] Ratios calculated (ROA, ROE, Margins, etc.)
- [ ] API endpoint returns 200 on request
- [ ] Results stored in metrics_outputs table
- [ ] Results validated against legacy output (within 0.01% tolerance)
- [ ] Performance acceptable (< 30 seconds for typical dataset)
- [ ] Code properly logged at INFO/DEBUG level
- [ ] No breaking changes to Phase 1 or Phase 2

---

## Files to Create/Modify

### Create
- `backend/app/services/enhanced_metrics_service.py` (400-500 lines)

### Modify
- `backend/app/models/schemas.py` (add CalculateEnhancedMetricsRequest/Response)
- `backend/app/api/v1/endpoints/metrics.py` (add POST /calculate-enhanced endpoint)
- `backend/app/services/__init__.py` (import EnhancedMetricsService)

---

## Timeline

| Task | Time | Owner |
|------|------|-------|
| Understand legacy code | 30 min | You |
| Create service skeleton | 1 hour | Claude |
| Implement data fetching | 1 hour | Claude |
| Implement Beta | 2-3 hours | Claude |
| Implement Rf | 1 hour | Claude |
| Implement KE | 30 min | Claude |
| Implement L2 Metrics | 2 hours | Claude |
| Add schemas & endpoint | 30 min | Claude |
| Test & validate | 1-2 hours | You |
| Total | ~10-12 hours | — |

**Total with breaks: 1-2 working days**

---

## Next Steps

1. **Confirm you want to proceed** with this approach
2. **Verify data exists** using the checklist above
3. **I will create the service** starting with implementation
4. **You will validate results** against legacy output when done
5. **We will identify what's leftover** after migration

---

## Questions for You Before We Start

1. Do you have market returns data in `cissa.timeseries` table? If not, can we load sample data?
2. Do you have risk-free rate lookups in `cissa.rf_lookup` table? Or use hardcoded default?
3. Should Cost of Equity (KE) approach be "FIXED" (benchmark - risk_premium) or "Floating" (calculated)?
4. Do you want franking credits included (incl_franking = "Yes") by default?
5. Is there a specific fiscal year range to focus on, or all available data?

