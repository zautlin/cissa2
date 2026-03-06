# L1 vs L2 Metrics: Dependency Analysis

## Current Architecture

### L1 Metrics (SQL-based - Stored Procedures)
- **Location:** `backend/database/schema/functions.sql`
- **Execution:** PostgreSQL stored procedures
- **Dependencies:** `fundamentals` table (raw Bloomberg data)
- **Output:** Inserted into `metrics_outputs` table by FastAPI service
- **Examples:**
  - Calc MC (Market Cap) = Spot Shares × Share Price
  - Calc Assets = Total Assets - Cash
  - Calc Op Cost = Revenue - Operating Income
  - ROA (Return on Assets) = PAT / Calc Assets

### L2 Metrics (Python-based - Regression/Complex Calculations)
- **Location:** `example-calculations/src/engine/calculation.py`
- **Execution:** Python with threading/regression algorithms
- **Dependencies:** **BOTH L1 metrics AND fundamentals data**
- **Examples:**
  - Betas (regression over time periods: 1Y, 3Y, 5Y, 10Y)
  - Cost of Equity (calculated from betas + risk parameters)
  - Multi-year projections (fv_ecf - future value equity free cash flow)
  - Sector aggregations and ratios

## Critical Dependency Discovery

Looking at `calculate_L2_metrics_async()` (line 139-184):

```python
# Line 143-145: L2 NEEDS BOTH L1 METRICS AND RAW DATA
l1_metrics = sql.get_general_metrics_from_db(guid=param.GUID)  # <- L1 output
annual_data = sql.get_annual_wide_format(inputs['country'])    # <- fundamentals

# Line 153: MERGES L1 + fundamentals
general_metrics = fmt.merge_metrics([annual_data, l1_metrics], on=['ticker', 'fy_year'])

# Line 163-167: Regression calculation using merged data
l2_metrics_list.append(thread_generate_l2_metrics(all_l1_metrics, inputs))

# Line 175-178: Complex pivoting and aggregation
all_metrics = fmt.merge_metrics([l2_metrics, fv_ecf], on=['ticker', 'fy_year'])
```

## Answer: L2 Depends on L1

**YES, L2 metrics REQUIRE L1 metrics to be calculated first.**

### Why?
1. **Data enrichment:** L1 metrics transform raw fundamentals into derived metrics (e.g., Calc Assets)
2. **Regression inputs:** L2 calculations (betas, cost of equity) use BOTH:
   - Historical L1 metrics (to identify trends/correlations)
   - Raw annual data (spot values for regressions)
3. **Time-series construction:** L1 outputs are merged with prior-year data for regression windows (1Y, 3Y, 5Y, 10Y)

### Timeline Constraints
```
┌─────────────────────────────────────────────┐
│ 1. User clicks "Calculate Metrics" in UI    │
└────────────┬────────────────────────────────┘
             ↓
┌─────────────────────────────────────────────┐
│ 2. Backend executes L1 stored procedures    │
│    (fn_calc_market_cap, fn_calc_assets...)  │
│    → Inserts results into metrics_outputs   │
│    ✅ PARALLELIZABLE (independent queries)  │
└────────────┬────────────────────────────────┘
             ↓ (MUST WAIT FOR L1)
┌─────────────────────────────────────────────┐
│ 3. Backend runs Python L2 calculation       │
│    - Fetches L1 from metrics_outputs        │
│    - Merges with fundamentals               │
│    - Runs regression/threading              │
│    → Inserts results into metrics_outputs   │
│    ⚠️  SEQUENTIAL (depends on L1)           │
└─────────────────────────────────────────────┘
             ↓
┌─────────────────────────────────────────────┐
│ 4. UI refreshes to show L1 + L2 metrics     │
└─────────────────────────────────────────────┘
```

## Recommended Implementation

### Option 1: Sequential (RECOMMENDED - Simplest)
1. User clicks "Calculate Metrics"
2. Backend (FastAPI) executes all L1 stored procedures synchronously
3. Polls `metrics_outputs` to confirm L1 completion
4. Enqueues L2 calculation as background task (Celery/APScheduler)
5. L2 task executes Python calculation, inserts results
6. UI polls for completion status

**Why recommended:** Clear dependencies, easy to debug, L2 can run async without blocking UI

### Option 2: Parallel L1, Then Async L2
1. User clicks "Calculate Metrics"
2. Backend spawns N parallel L1 stored procedures (they're independent)
3. Waits for all L1 to complete
4. Spawns L2 as background task
5. Returns immediately with "Calculating..." status

**Tradeoff:** More complex but faster for user experience

### Option 3: Interleaved (NOT RECOMMENDED)
- Run L1 procedures one-by-one
- Start L2 as soon as first batch of L1 completes
- Risks incomplete L1 data in L2 regressions

## Implementation Architecture

### Layer 1: Service Layer (metrics_service.py)
```python
class MetricsService:
    async def calculate_l1_metrics(self, dataset_id: UUID, param_set_id: UUID) -> int:
        """Execute L1 stored procedures, return count of metrics created"""
        # List all L1 functions from functions.sql
        # Execute each function sequentially (or in parallel if independent)
        # Insert results into metrics_outputs
        
    async def queue_l2_calculation(self, dataset_id: UUID, param_set_id: UUID, inputs: dict) -> str:
        """Enqueue L2 calculation as background task, return job_id"""
        # Validate that L1 is complete
        # Create calculation job record in database
        # Enqueue to Celery/APScheduler
        # Return job_id for polling
```

### Layer 2: Background Task (tasks.py or Celery)
```python
async def calculate_l2_metrics_job(job_id: str, dataset_id: UUID, param_set_id: UUID, inputs: dict):
    """Background task to calculate L2 metrics"""
    # 1. Fetch L1 metrics from metrics_outputs where dataset_id and param_set_id
    # 2. Fetch fundamentals from fundamentals table where dataset_id
    # 3. Call example-calculations.src.engine.calculation.calculate_L2_metrics_async(inputs)
    # 4. Insert L2 results into metrics_outputs with (dataset_id, param_set_id, ticker)
    # 5. Update job_id status to "complete"
```

### Layer 3: API Endpoints (metrics_routes.py)
```python
@router.post("/metrics/calculate", response_model=CalculationResponse)
async def calculate_metrics(
    request: CalculationRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """POST request to trigger L1 + L2 metrics calculation"""
    # Validate dataset exists
    # Execute L1 (synchronous)
    # Enqueue L2 (async)
    # Return {"status": "calculating", "job_id": "..."}

@router.get("/metrics/status/{job_id}", response_model=StatusResponse)
async def get_calculation_status(
    job_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    """GET request to poll calculation progress"""
    # Query job_status table
    # Return {"status": "calculating|complete|failed", "progress": "..."}
```

## Data Flow Diagram

```
User UI (React)
    │
    ├─── POST /api/metrics/calculate
    │    {dataset_id, param_set_id, inputs}
    │
    └──→ FastAPI Endpoint
         │
         ├─→ 1. Service Layer: Execute L1 Stored Procedures
         │    ├─ fn_calc_market_cap(dataset_id)
         │    ├─ fn_calc_operating_assets(dataset_id)
         │    ├─ ... [all L1 functions]
         │    └─ Results → INSERT into metrics_outputs
         │
         ├─→ 2. Wait for L1 Completion
         │    └─ SELECT COUNT(*) FROM metrics_outputs
         │       WHERE dataset_id = ? AND metric_level = 'L1'
         │
         ├─→ 3. Background Task Queue: Enqueue L2 Job
         │    └─ Celery/APScheduler:
         │       calculate_l2_metrics_job(job_id, dataset_id, param_set_id)
         │
         └─→ 4. Return Immediately
              {"status": "calculating", "job_id": "abc-123"}
              
User polls GET /api/metrics/status/{job_id}
    └─→ Returns: {"status": "complete", "progress": "100%"}
```

## Next Steps

1. **Create FastAPI service layer** for metrics calculation
2. **Create background task** for L2 calculation (Celery or APScheduler)
3. **Create database tables** for job tracking (calculation_jobs, job_status)
4. **Wire up example-calculations** to use dataset_id/param_set_id instead of GUID
5. **Create React UI** endpoints to trigger and poll calculation

Would you like me to create the FastAPI service and routes for this workflow?
