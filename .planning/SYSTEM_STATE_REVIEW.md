# CISSA System State Review - March 8, 2026

## Current Architecture Overview

You have a **two-tier metrics system** built with FastAPI + PostgreSQL:

### Layer 1: Phase 1 Metrics (Completed ✅)
- **15 SQL Functions** calculating core metrics from fundamentals table
- **Metrics Examples:** Market Cap, Operating Assets, Profit Margins, Tax Rates, ROA, Book Equity
- **Implementation:** Pure SQL (PostgreSQL functions, immutable)
- **API:** POST `/api/v1/metrics/calculate` endpoint
- **Storage:** Results → `cissa.metrics_outputs` table

### Layer 2: Phase 2 L2 Metrics (Recently Completed ✅)
- **Advanced calculations** using L1 metrics as inputs
- **Metrics Examples:** Economic Profit, ROE, Cost of Equity, Economic Equity
- **Implementation:** Python service layer (fetch L1 → calculate → store L2)
- **API:** POST `/api/v1/metrics/calculate-l2` endpoint
- **CLI:** `run_l2_metrics.py` for batch processing

---

## Your Legacy Codebase

In `/home/ubuntu/cissa/example-calculations/` you have:

### Calculation Engines
1. **`executors/metrics.py`** — Original metric calculation logic
2. **`executors/fvecf.py`** — Free cash flow calculations
3. **`executors/beta.py`** — Beta calculations
4. **`executors/rates.py`** — Risk-free rate calculations
5. **`generate_l2_metrics.py`** — L2 metrics generation
6. **`generate_sector_metrics.py`** — Sector aggregations

### Data Management
- **`upload_data_to_db.py`** — Historical data loading script
- **`config/parameters.py`** — Parameter definitions

### Advanced Features
- **SOWC** (State of the World) — LLM + RAG based analysis
- **Goal Seek** — Excel goal seek integration
- **Web Scraping** — Data collection from web

---

## What You Want to Do

> "Move the older code into this new setup with the backend db and the API"

This means:
1. **Migrate calculation logic** from `example-calculations/executors/` into the FastAPI service layer
2. **Expose via API endpoints** instead of standalone scripts
3. **Keep database consistency** (store results in PostgreSQL)
4. **Maintain calculation accuracy** (formulas must match original)

---

## Current State: What's Already Migrated

| Calculation | Status | Location |
|-------------|--------|----------|
| Market Cap | ✅ Done | SQL function `fn_calc_market_cap` |
| Operating Assets | ✅ Done | SQL function `fn_calc_operating_assets` |
| Cost Structure | ✅ Done | SQL functions (Op/Non-Op/Tax/XO) |
| Ratio Metrics | ✅ Done | SQL functions (Margins, ROA, etc) |
| **Economic Profit** | ⚠️ Partial | L2 service (needs validation) |
| **Economic Equity** | ⚠️ Partial | L2 service (needs validation) |
| **Cost of Equity** | ⚠️ Partial | L2 service (needs validation) |
| Beta Calculation | ❌ NOT MIGRATED | Still in `executors/beta.py` |
| Risk-Free Rate | ⚠️ COMPLEX | Uses time-series lookback, not simple |
| Franking Credits | ❌ NOT MIGRATED | Still in `executors/metrics.py` |
| TSR Calculations | ❌ NOT MIGRATED | Still in `executors/metrics.py` |
| Sector Aggregations | ❌ NOT MIGRATED | Still in `generate_sector_metrics.py` |

---

## Code Organization

### Backend Structure (Ready to Extend)
```
backend/
├── app/
│   ├── main.py                           # FastAPI app + lifespan
│   ├── core/
│   │   ├── config.py                     # Settings, logging
│   │   └── database.py                   # AsyncPG setup
│   ├── services/
│   │   ├── metrics_service.py            # Phase 1 calculations
│   │   └── l2_metrics_service.py         # Phase 2 calculations
│   ├── repositories/
│   │   └── metrics_repository.py         # Data access layer
│   ├── api/
│   │   └── v1/
│   │       ├── router.py                 # Route aggregator
│   │       └── endpoints/
│   │           └── metrics.py            # Endpoint handlers
│   └── cli/
│       └── run_l2_metrics.py             # CLI for batch processing
└── database/
    ├── schema/
    │   ├── functions.sql                 # 15 Phase 1 functions
    │   └── ... (migrations, schema)
    └── scripts/
```

### Legacy Structure (To Be Migrated)
```
example-calculations/
├── src/
│   ├── executors/
│   │   ├── metrics.py         ← Source of truth (Phase 1 + TSR/Franking)
│   │   ├── fvecf.py           ← Free Cash Flow logic
│   │   ├── beta.py            ← Beta calculation
│   │   └── rates.py           ← Risk-free rate lookup
│   ├── generate_l2_metrics.py ← L2 orchestration
│   └── config/parameters.py   ← Parameters (risk premium, tax rate, etc)
```

---

## Next Steps to Complete Migration

### Phase 3 Plan (Your Next Work)

#### Priority 1: Risk-Free Rate Service
- **File:** Add `backend/app/services/rate_service.py`
- **Migration from:** `example-calculations/src/executors/rates.py`
- **Challenge:** Non-deterministic (uses time-series lookback, external data)
- **Approach:** 
  - Async task service (not stored proc)
  - Cache results for same-date queries
  - Query ASX/external rate source once per run

#### Priority 2: Beta Calculation Service
- **File:** Add `backend/app/services/beta_service.py`
- **Migration from:** `example-calculations/src/executors/beta.py`
- **Challenge:** 4-tier fallback logic (company → sector → sector avg → 1.0)
- **Approach:**
  - Query precomputed beta table
  - Implement fallback cascade
  - Return spot + rolling average

#### Priority 3: TSR & Franking Calculations
- **File:** Add `backend/app/services/returns_service.py`
- **Migration from:** `example-calculations/src/executors/metrics.py` (lines 50-150)
- **Challenge:** Depends on Economic Cash Flow (ECF)
- **Approach:**
  - TSR = (Prior MC × FY TSR) / Prior MC
  - Franking adjustment for dividend credit

#### Priority 4: Sector Aggregations
- **File:** Add `backend/app/services/sector_service.py`
- **Migration from:** `example-calculations/src/generate_sector_metrics.py`
- **Approach:**
  - GroupBy sector, aggregate dollar metrics (SUM)
  - Aggregate rate metrics (weighted by abs EE)
  - Store in `cissa.sector_metrics` table

---

## Key Patterns Already Established

### Service Layer Pattern
All calculations follow this structure:

```python
class [Feature]Service:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate(self, dataset_id: UUID, ...) -> Response:
        # Fetch prerequisites
        # Calculate
        # Store results
        # Return response
```

### API Endpoint Pattern
```python
@router.post("/api/v1/metrics/calculate-[feature]")
async def calculate_[feature](
    request: CalculateRequest,
    db: AsyncSession = Depends(get_db)
) -> CalculateResponse:
    service = [Feature]Service(db)
    return await service.calculate(...)
```

### Repository Pattern
```python
class MetricsRepository:
    async def get_l1_metrics(self, dataset_id: UUID) -> DataFrame:
        # Fetch from DB
    
    async def create_outputs_batch(self, records: List[Dict]) -> int:
        # Batch insert with UPSERT
```

---

## How to Continue

### Option A: Review Your Existing Code First
1. Read through `example-calculations/src/executors/metrics.py` to understand all formulas
2. Check `example-calculations/src/config/parameters.py` for parameter defaults
3. Review `L1_L2_METRICS_ANALYSIS.md` for calculation validation

### Option B: Start with Gap Analysis
1. Create a checklist of ALL metrics you want exposed via API
2. Mark which are already in Phase 1/Phase 2
3. Prioritize remaining ones

### Option C: Begin with Specific Metric
1. Pick ONE metric from legacy code (e.g., Beta)
2. Extract calculation logic
3. Create service + endpoint
4. Add tests
5. Repeat for next metric

---

## Technical Debt & Considerations

### Things Working Well
- ✅ AsyncPG + SQLAlchemy 2.0 (modern, fast)
- ✅ Pydantic v2 validation
- ✅ Service/Repository layer separation
- ✅ Error handling with logging
- ✅ Batch inserts for performance

### Things to Watch
- ⚠️ Phase 2 L2 metrics need validation against legacy output
- ⚠️ Risk-free rate service needs external data source (ASX?)
- ⚠️ Beta calculation needs precomputed tables
- ⚠️ Sector aggregations need proper weighted averaging logic

---

## Recommended Migration Path

```
Week 1: Beta Service
├── Extract beta logic from executors/beta.py
├── Create backend/app/services/beta_service.py
├── Add endpoint POST /api/v1/metrics/calculate-beta
└── Validate against legacy output

Week 2: Risk-Free Rate Service
├── Extract rate lookup logic from executors/rates.py
├── Create backend/app/services/rate_service.py
├── Add caching layer (same date = cached)
└── Add endpoint POST /api/v1/metrics/calculate-rf

Week 3: TSR & Franking
├── Extract from executors/metrics.py
├── Depends on ECF (already in L2)
├── Create backend/app/services/returns_service.py
└── Add endpoint POST /api/v1/metrics/calculate-returns

Week 4: Sector Aggregations
├── Extract from generate_sector_metrics.py
├── Create backend/app/services/sector_service.py
├── Add endpoint POST /api/v1/metrics/calculate-sector
└── Full Phase 3 complete
```

---

## Questions to Help Focus

1. **Which metrics are highest priority?** (Beta? Risk-Free Rate? All of them?)
2. **Do you have external data sources** for rates/market data, or use what's in DB?
3. **Should these be real-time HTTP endpoints** or background batch jobs?
4. **Do you want CLI scripts** (like run_l2_metrics.py) for each metric group?
5. **Any validation data** we can compare new implementation against legacy?
