# FastAPI-First L2 Metrics Refactor

## The Change

Moving from a standalone Python script that queries databases and saves results, to **FastAPI orchestrating clean data + pure calculation**.

### Old Way ❌
```
example-calculations/src/generate_l2_metrics.py
  ├─ Hardcoded GUID in config
  ├─ Loads data via raw SQL (sql.get_general_metrics_from_db)
  ├─ Mixes data fetching + calculation in same script
  ├─ Runs calculation locally
  ├─ Saves results back to DB via loaders
  └─ Hard to test, hard to reuse, tied to legacy patterns
```

### New Way ✅
```
FastAPI Service Layer (backend/app/services/metrics_service.py)
  ├─ Receives dataset_id, param_set_id (no GUID)
  ├─ Fetches L1 metrics via async SQLAlchemy ORM query
  ├─ Fetches fundamentals via async SQLAlchemy ORM query
  ├─ Converts ORM objects → pandas DataFrames
  ├─ Calls PURE calculation function (takes DataFrames, returns DataFrame)
  ├─ Inserts results via ORM
  └─ Repeatable, testable, async-ready, no GUID coupling

Pure Calculation (example-calculations/src/engine/calculation.py)
  ├─ Takes: l1_metrics_df, annual_data_df, inputs
  ├─ Returns: results_df (ready to insert)
  ├─ No database access
  ├─ No SQL queries
  ├─ No side effects (pure function)
  └─ Easy to unit test with mock DataFrames
```

## What This Enables

### 1. Sync Endpoint (Simple)
```python
@router.post("/metrics/calculate")
async def calculate_metrics(
    request: CalculationRequest,  # {dataset_id, param_set_id, inputs}
    session: AsyncSession = Depends(get_async_session),
):
    service = MetricsService(session)
    results = await service.calculate_l2_metrics(
        request.dataset_id,
        request.param_set_id,
        request.inputs
    )
    return {"status": "complete", "metrics_inserted": len(results)}
```

- ✅ Caller gets results immediately
- ❌ Blocks if L2 takes > 30s

### 2. Async Background Task (Best for UI)
```python
@router.post("/metrics/calculate")
async def calculate_metrics(
    request: CalculationRequest,
    session: AsyncSession = Depends(get_async_session),
    background_tasks: BackgroundTasks,
):
    job_id = str(uuid.uuid4())
    
    # Enqueue background task
    background_tasks.add_task(
        calculate_l2_metrics_job,
        job_id, request.dataset_id, request.param_set_id, request.inputs, session
    )
    
    # Return immediately
    return {"status": "calculating", "job_id": job_id}

async def calculate_l2_metrics_job(job_id, dataset_id, param_set_id, inputs, session):
    service = MetricsService(session)
    await service.calculate_l2_metrics(dataset_id, param_set_id, inputs)
    # UI polls GET /metrics/status/{job_id} until complete
```

- ✅ Returns immediately (non-blocking)
- ✅ Can run Sync or Async endpoints
- ✅ Can have fallback to sync if needed

### 3. CLI Script for Batch Processing
```python
# backend/app/cli/metrics_cli.py
async def batch_calculate_metrics():
    async with async_session_factory() as session:
        service = MetricsService(session)
        
        # For each dataset/param_set
        for dataset_id, param_set_id in datasets:
            results = await service.calculate_l2_metrics(
                dataset_id, param_set_id, default_inputs
            )
            print(f"Calculated {len(results)} metrics")
```

## Refactoring Steps

### Step 1: Create ORM Model
```python
# backend/app/models/metrics_output.py
class MetricsOutput(Base):
    __tablename__ = "metrics_outputs"
    
    metrics_output_id: Mapped[UUID] = mapped_column(primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_versions.dataset_id"))
    param_set_id: Mapped[UUID] = mapped_column(ForeignKey("parameter_sets.param_set_id"))
    ticker: Mapped[str]
    output_metric_name: Mapped[str]
    fiscal_year: Mapped[int]
    output_metric_value: Mapped[float | None]
    created_at: Mapped[datetime]
```

### Step 2: Create Pure Calculation Function
```python
# example-calculations/src/engine/calculation.py (REFACTORED)
def calculate_L2_metrics(
    l1_metrics_df: DataFrame,
    annual_data_df: DataFrame,
    inputs: dict
) -> DataFrame:
    """
    Pure calculation - no database access.
    Input: DataFrames already filtered by dataset_id/param_set_id
    Output: DataFrame ready to insert into metrics_outputs
    """
    # Merge L1 + fundamentals
    general_metrics = fmt.merge_metrics([annual_data_df, l1_metrics_df], ...)
    
    # Run regression/calculation
    l2_metrics = thread_generate_l2_metrics(general_metrics, inputs)
    
    # Return DataFrame with columns: [ticker, fy_year, metric_name, value]
    return l2_metrics
```

### Step 3: Create FastAPI Service
```python
# backend/app/services/metrics_service.py (NEW)
class MetricsService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate_l2_metrics(
        self, 
        dataset_id: UUID, 
        param_set_id: UUID, 
        inputs: dict
    ) -> DataFrame:
        # 1. Fetch L1
        l1_df = await self._fetch_l1_metrics(dataset_id, param_set_id)
        
        # 2. Fetch fundamentals
        annual_df = await self._fetch_fundamentals(dataset_id, inputs['country'])
        
        # 3. Call pure function
        results_df = calculate_L2_metrics(l1_df, annual_df, inputs)
        
        # 4. Insert results
        await self._insert_l2_metrics(dataset_id, param_set_id, results_df)
        
        return results_df
    
    async def _fetch_l1_metrics(self, dataset_id: UUID, param_set_id: UUID) -> DataFrame:
        result = await self.session.execute(
            select(MetricsOutput).where(
                (MetricsOutput.dataset_id == dataset_id) &
                (MetricsOutput.param_set_id == param_set_id)
            )
        )
        rows = result.scalars().all()
        return pd.DataFrame([{
            'ticker': r.ticker,
            'fy_year': r.fiscal_year,
            'metric_name': r.output_metric_name,
            'value': r.output_metric_value
        } for r in rows])
```

### Step 4: Create FastAPI Routes
```python
# backend/app/routes/metrics.py (NEW)
router = APIRouter(prefix="/metrics", tags=["Metrics"])

@router.post("/calculate", response_model=CalculationResponse)
async def calculate_metrics(
    request: CalculationRequest,
    session: AsyncSession = Depends(get_async_session),
):
    service = MetricsService(session)
    results = await service.calculate_l2_metrics(
        request.dataset_id,
        request.param_set_id,
        request.inputs
    )
    return {"status": "complete", "metrics_inserted": len(results)}
```

## Benefits Summary

| Aspect | Old | New |
|--------|-----|-----|
| **Data Fetching** | Raw SQL in script | FastAPI service layer (async) |
| **Calculation** | Mixed with DB access | Pure function (testable) |
| **Database Writes** | Direct via loaders.py | ORM via service |
| **GUID Coupling** | Yes (hardcoded) | No (dataset_id/param_set_id) |
| **Reusability** | Low (standalone script) | High (can be called from anywhere) |
| **Testing** | Hard (needs real DB) | Easy (mock DataFrames) |
| **Async Support** | No | Yes (background tasks ready) |
| **Error Handling** | Scattered | Centralized in service |
| **Code Cleanliness** | Mixed concerns | Clean separation |

## This Approach Is Ready For

✅ Sync HTTP endpoint  
✅ Async background task  
✅ CLI batch processing  
✅ Scheduled jobs (APScheduler)  
✅ Webhook triggers  
✅ Unit testing  
✅ Multi-dataset processing  
✅ Parameter variations  

## Files to Create/Modify

| File | Status | Purpose |
|------|--------|---------|
| `backend/app/models/metrics_output.py` | NEW | ORM model |
| `backend/app/services/metrics_service.py` | NEW | Orchestration layer |
| `backend/app/routes/metrics.py` | NEW | FastAPI endpoints |
| `backend/app/schemas/metrics.py` | NEW | Pydantic schemas |
| `example-calculations/src/engine/calculation.py` | REFACTOR | Remove SQL, make pure |
| `example-calculations/src/scripts/run_l2_metrics.py` | NEW | CLI script |
| `example-calculations/src/generate_l2_metrics.py` | DEPRECATED | Keep for reference |

---

**This is production-ready architecture.** Ready to start implementing?
