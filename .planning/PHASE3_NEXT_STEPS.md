# Next Steps: Your Phase 3 Plan

**Date:** March 8, 2026  
**Current State:** Phase 1 + Phase 2 complete, ready for Phase 3 migrations  
**Goal:** Migrate remaining calculation logic from legacy code into FastAPI backend

---

## Before You Start: Answer These Questions

1. **Which metrics are your immediate priority?**
   - [ ] Beta calculation
   - [ ] Risk-free rate
   - [ ] TSR & Franking credits
   - [ ] Sector aggregations
   - [ ] All of the above

2. **Do you have access to:**
   - [ ] Market returns data (for beta calculation)?
   - [ ] ASX/external Rf data source?
   - [ ] Precomputed sector beta tables?
   - [ ] All needed in PostgreSQL already?

3. **API vs Batch Mode:**
   - [ ] Real-time HTTP endpoints (synchronous)?
   - [ ] Background batch jobs (async with CLI)?
   - [ ] Both?

4. **Validation Requirements:**
   - [ ] Need to compare results against legacy output?
   - [ ] Have test datasets ready?
   - [ ] Know expected outputs?

---

## Quickstart: First Beta Service (Day 1-2)

### Step 0: Verify Prerequisites
```bash
# Check your schema has these tables
psql -U postgres -d cissa -c "
  SELECT table_name FROM information_schema.tables 
  WHERE table_schema='cissa' 
  AND table_name IN ('fundamentals', 'timeseries', 'beta_lookup', 'metrics_outputs')
"

# If any are missing, you'll need to create them
```

### Step 1: Create Service File
Create `backend/app/services/beta_service.py` using the template from MIGRATION_EXAMPLES.md

Key tasks:
- [ ] Copy `BetaService` class structure
- [ ] Adjust `_fetch_returns()` query to match your actual schema
- [ ] Implement `_calculate_spot_beta()` with your exact formula
- [ ] Implement `_get_fallback_beta()` to match your beta lookup table
- [ ] Add logging at each step

### Step 2: Create Pydantic Models
Update `backend/app/models/schemas.py` with Beta request/response schemas:
```python
class CalculateBetaRequest(BaseModel):
    dataset_id: UUID
    error_tolerance: Optional[float] = 0.5
    beta_rounding: Optional[float] = 0.05

class CalculateBetaResponse(BaseModel):
    dataset_id: UUID
    results_count: int
    results: List[MetricResultItem]
    status: str = "success"
```

### Step 3: Create API Endpoint
Add to `backend/app/api/v1/endpoints/metrics.py`:
```python
@router.post("/api/v1/metrics/calculate-beta")
async def calculate_beta(request: CalculateBetaRequest, db = Depends(get_db)):
    service = BetaService(db)
    return await service.calculate_beta(...)
```

### Step 4: Test
```bash
# Start API
./start-api.sh

# Test endpoint
curl -X POST http://localhost:8000/api/v1/metrics/calculate-beta \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "YOUR_DATASET_UUID",
    "error_tolerance": 0.5,
    "beta_rounding": 0.05
  }'

# Check results in database
psql -U postgres -d cissa -c "
  SELECT COUNT(*), metric_name FROM cissa.metrics_outputs 
  WHERE metric_name LIKE '%Beta%' 
  GROUP BY metric_name
"
```

### Step 5: Compare Against Legacy
```python
# Extract legacy output
legacy_results = pd.read_csv('example-calculations/outputs/beta_2023.csv')

# Query new results
import requests
response = requests.post(
    'http://localhost:8000/api/v1/metrics/calculate-beta',
    json={'dataset_id': 'UUID', 'error_tolerance': 0.5}
)
new_results = pd.DataFrame(response.json()['results'])

# Compare
comparison = legacy_results.merge(
    new_results,
    on=['ticker', 'fiscal_year'],
    suffixes=('_legacy', '_new')
)
comparison['diff'] = abs(comparison['value_legacy'] - comparison['value_new'])
print(comparison[comparison['diff'] > 0.01])  # Show differences > 0.01
```

---

## Full Phase 3 Roadmap

### Week 1: Beta Service
**Files to create/modify:**
- [ ] `backend/app/services/beta_service.py` (NEW - 200 lines)
- [ ] `backend/app/models/schemas.py` (ADD beta schemas - 30 lines)
- [ ] `backend/app/api/v1/endpoints/metrics.py` (ADD beta endpoint - 30 lines)

**Validation:**
- [ ] API returns 200 on POST /api/v1/metrics/calculate-beta
- [ ] Results stored in metrics_outputs table
- [ ] Spot beta + rolling avg calculated correctly
- [ ] Results match legacy output within 0.01% tolerance

**Time estimate:** 3-4 hours (extract → implement → test → compare)

---

### Week 2: Risk-Free Rate Service
**Files to create/modify:**
- [ ] `backend/app/services/rate_service.py` (NEW - 150 lines)
- [ ] `backend/app/models/schemas.py` (ADD rate schemas - 20 lines)
- [ ] `backend/app/api/v1/endpoints/metrics.py` (ADD rate endpoint - 20 lines)

**Challenges:**
- Need to verify where Rf lookups come from (ASX? precomputed?)
- Fallback to default if missing
- Lagged calculation (Open Rf = prior year)

**Validation:**
- [ ] API returns 200 on POST /api/v1/metrics/calculate-rf
- [ ] Results use lookup table when available
- [ ] Results use default_rf when not in lookup
- [ ] Open Rf properly lagged

**Time estimate:** 2-3 hours

---

### Week 3: TSR & Franking Service
**Files to create/modify:**
- [ ] `backend/app/services/returns_service.py` (NEW - 250 lines)
- [ ] `backend/app/models/schemas.py` (ADD returns schemas - 25 lines)
- [ ] `backend/app/api/v1/endpoints/metrics.py` (ADD returns endpoint - 30 lines)

**Challenges:**
- Depends on L1 (Market Cap, ECF) already calculated
- Franking credit adjustment complex
- Needs inception_ind flag logic

**Validation:**
- [ ] API returns 200 on POST /api/v1/metrics/calculate-returns
- [ ] TSR correct: (prior MC × returns) / prior MC
- [ ] Franking adjustment applied when requested
- [ ] Results match legacy within 0.01% tolerance

**Time estimate:** 3-4 hours

---

### Week 4: Sector Aggregations
**Files to create/modify:**
- [ ] `backend/app/services/sector_service.py` (NEW - 200 lines)
- [ ] `backend/app/models/schemas.py` (ADD sector schemas - 30 lines)
- [ ] `backend/app/api/v1/endpoints/metrics.py` (ADD sector endpoint - 30 lines)
- [ ] `backend/database/schema/sector_tables.sql` (NEW - create sector_metrics table)

**Challenges:**
- Dollar metrics = SUM aggregation
- Rate metrics = weighted average by abs(EE)
- Multiple metrics aggregated together

**Validation:**
- [ ] API returns 200 on POST /api/v1/metrics/calculate-sector
- [ ] Results grouped by sector
- [ ] Dollar metrics summed correctly
- [ ] Rate metrics weighted correctly
- [ ] Compare vs legacy sector outputs

**Time estimate:** 3-4 hours

---

## Documentation to Review First

**Before coding**, read these files from your project:

1. **`/home/ubuntu/cissa/example-calculations/src/executors/metrics.py`** (800 lines)
   - Lines 1-50: Parameter setup
   - Lines 50-150: TSR/Franking logic
   - Lines 150-250: ECF calculation
   - Lines 250+: Other ratio metrics

2. **`/home/ubuntu/cissa/example-calculations/src/executors/beta.py`** (200 lines)
   - Lines 1-50: Rolling OLS setup
   - Lines 50-100: Beta adjustment formula
   - Lines 100-150: Fallback logic

3. **`/home/ubuntu/cissa/example-calculations/src/config/parameters.py`** (100 lines)
   - Market risk premium
   - Tax rates
   - Franking parameters
   - Beta rounding

4. **`/.planning/L1_L2_METRICS_ANALYSIS.md`** (your analysis)
   - Maps legacy formulas to new implementation
   - Known differences & edge cases

---

## Key Files to Keep Updated

Every time you create a new service, update these:

### 1. `backend/app/services/__init__.py`
```python
from .metrics_service import MetricsService
from .l2_metrics_service import L2MetricsService
from .beta_service import BetaService          # ← ADD
from .rate_service import RateService          # ← ADD
from .returns_service import ReturnsService    # ← ADD
from .sector_service import SectorService      # ← ADD

__all__ = [...]
```

### 2. `backend/app/api/v1/router.py`
```python
from .endpoints import metrics

router = APIRouter()
router.include_router(metrics.router, prefix="/metrics")

@router.get("/health")
async def health():
    return {"status": "ok"}
```

### 3. `.planning/ROADMAP.md`
Update Phase 3 progress as you complete services

---

## Development Workflow for Each Service

### Create Service
```bash
# 1. Create file
touch backend/app/services/{feature}_service.py

# 2. Copy template from MIGRATION_EXAMPLES.md
# 3. Adjust for your schema/formulas
# 4. Add logging
```

### Create Schemas
```bash
# 1. Edit backend/app/models/schemas.py
# 2. Add CalculateXRequest and CalculateXResponse classes
# 3. Follow Pydantic v2 patterns from existing schemas
```

### Create Endpoint
```bash
# 1. Edit backend/app/api/v1/endpoints/metrics.py
# 2. Add @router.post("/calculate-{feature}") function
# 3. Include docstring with example
```

### Test
```bash
# 1. Start API: ./start-api.sh
# 2. Call endpoint: curl http://localhost:8000/api/v1/metrics/calculate-{feature}
# 3. Verify in database: psql ... -c "SELECT ..."
# 4. Compare against legacy: python compare_results.py
```

### Commit
```bash
git add backend/app/services/{feature}_service.py
git add backend/app/models/schemas.py
git add backend/app/api/v1/endpoints/metrics.py
git commit -m "feat({feature}): add {feature} calculation service and API endpoint"
git push
```

---

## Troubleshooting

### "Service returns 0 results"
- [ ] Check dataset_id exists in database
- [ ] Check fundamentals table has data for that dataset
- [ ] Check _fetch_* methods query the right tables
- [ ] Add debug logging: `logger.debug(f"Query returned {len(rows)} rows")`

### "Results don't match legacy output"
- [ ] Check formula translation (e.g., division vs multiplication)
- [ ] Verify NULL handling (legacy skips NaN, do you?)
- [ ] Check data types (float vs int rounding)
- [ ] Print first 5 rows: `print(results.head())` and compare manually

### "Database connection timeout"
- [ ] Check PostgreSQL is running: `psql -U postgres -d cissa -c "SELECT 1"`
- [ ] Check .env DATABASE_URL is correct
- [ ] Check port 5432 is open
- [ ] Restart API: `./start-api.sh`

### "Import errors (ModuleNotFoundError)"
- [ ] Check file path matches import path
- [ ] Check __init__.py files exist in all directories
- [ ] Check service is added to backend/app/services/__init__.py
- [ ] Run from project root: `cd /home/ubuntu/cissa`

---

## Success Criteria for Phase 3 Completion

✅ Phase 3 is complete when:

- [ ] All 4 services created (beta, rate, returns, sector)
- [ ] All 4 services have API endpoints
- [ ] All endpoints tested and return 200
- [ ] Results stored in metrics_outputs table
- [ ] Results validated against legacy output (within tolerance)
- [ ] No breaking changes to Phase 1/Phase 2 endpoints
- [ ] All services logged at INFO level
- [ ] Code follows established patterns (Service/Repo/Endpoint)
- [ ] Commits created for each service
- [ ] Documentation updated (this file)

---

## Next Action Items

**TODAY:**
1. Read SYSTEM_STATE_REVIEW.md completely
2. Read MIGRATION_EXAMPLES.md and understand the pattern
3. Decide: Which metric to start with? (Recommend: Beta)
4. Answer the 4 questions at top of this document

**TOMORROW:**
1. Review legacy code (e.g., executors/beta.py)
2. Verify your database schema matches template queries
3. Create `backend/app/services/beta_service.py`
4. Test with curl

**THIS WEEK:**
1. Complete Beta service
2. Start Risk-Free Rate service
3. Create tests/validation

---

## Questions? 

Check:
1. SYSTEM_STATE_REVIEW.md (architecture overview)
2. MIGRATION_EXAMPLES.md (concrete code examples)
3. existing code in backend/app/services/l2_metrics_service.py (working example)
4. project git history: `git log --oneline | head -20`
