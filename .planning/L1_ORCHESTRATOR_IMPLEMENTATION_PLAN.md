# L1 Metrics Orchestrator Implementation Plan

**Date**: March 16, 2026  
**Status**: Ready for Implementation  
**Target Performance**: 8-10 minutes → <1 minute (40-60 seconds realistic)

---

## Executive Summary

This plan outlines implementation of a Python-based orchestrator to parallelize L1 metric calculations and batch insert database operations, targeting 85-90% performance improvement.

**Key Changes**:
1. Create async orchestrator script with semaphore-limited concurrency
2. Fix individual row INSERT anti-pattern with batch/multi-row inserts
3. Create API endpoint for triggering orchestrator from UI
4. Full end-to-end testing with 500-ticker dataset

**Performance Breakdown**:
- **Batch insert optimization**: 80-90% improvement (10s → 1s per metric)
- **Phase 1 parallelization**: 3-4x speedup within phase (12 metrics done concurrently in groups)
- **Phases 2-4**: Sequential only (dependencies require this)
- **Expected total**: 40-60 seconds for full L1 calculation run

---

## Architecture Overview

### Phase Execution Order (MUST MAINTAIN)

```
Phase 1: Basic Metrics (12 metrics) - PARALLELIZED
├─ Simple metrics (7): MC, Assets, OA, Op Cost, Non Op Cost, Tax Cost, XO Cost
├─ Temporal metrics (5): ECF, Non Div ECF, EE, FY TSR, FY TSR PREL
└─ Concurrency: 4 parallel groups (3-4 metrics per group)

Phase 2: Beta Calculation (1 metric) - SEQUENTIAL
└─ Metric: Beta (no parallelization needed, single metric)

Phase 3: Cost of Equity (2 metrics) - SEQUENTIAL
├─ Dependency: Requires Beta from Phase 2
└─ Metrics: KE (depends on Beta)

Phase 4: Risk-Free Rate (2 metrics) - SEQUENTIAL
└─ Metrics: Rf
```

### Concurrency Strategy

**Why Semaphore with max_concurrency=4?**
- FastAPI has limited worker threads; unbounded parallelism causes queuing
- PostgreSQL connection pool is finite (prevent exhaustion)
- 4 concurrent is ~4x faster than sequential while remaining stable
- Allows error isolation (failed metrics don't cascade)

**Implementation**:
```python
semaphore = asyncio.Semaphore(4)

async def call_metric_api(metric_id):
    async with semaphore:
        return await http_client.post(url, json=payload)
```

---

## Implementation Phases

### Phase 1: Create Python Orchestrator Script

**File**: `backend/scripts/orchestrate_l1_metrics.py`

**Features**:
- ✅ Async HTTP client using `httpx` (already in requirements)
- ✅ Semaphore-limited concurrency (max 4 parallel requests)
- ✅ Phase 1 parallelization: 4 groups of metrics
- ✅ Phases 2-4: Sequential execution with dependency checking
- ✅ Retry logic: Exponential backoff (3 attempts max)
- ✅ Error aggregation: Continue on failures, report at end
- ✅ Progress logging: Simple console output with timing
- ✅ CLI interface: `python orchestrate_l1_metrics.py --dataset-id X --param-set-id Y`

**Pseudocode Structure**:
```python
async def orchestrate_l1_metrics(dataset_id, param_set_id):
    phase_results = {}
    
    # Phase 1: Parallelized basic metrics
    phase_1_groups = [
        [metric1, metric2, metric3],
        [metric4, metric5, metric6],
        [metric7, metric8, metric9],
        [metric10, metric11, metric12]
    ]
    phase_1_results = await run_phase_1_parallelized(phase_1_groups)
    phase_results['phase_1'] = phase_1_results
    
    # Phase 2: Sequential beta
    phase_2_results = await call_metric_api('beta', dataset_id, param_set_id)
    phase_results['phase_2'] = phase_2_results
    
    # Phase 3: Sequential cost of equity (depends on beta)
    phase_3_results = await call_metric_api('cost_of_equity', dataset_id, param_set_id)
    phase_results['phase_3'] = phase_3_results
    
    # Phase 4: Sequential risk-free rate
    phase_4_results = await call_metric_api('risk_free_rate', dataset_id, param_set_id)
    phase_results['phase_4'] = phase_4_results
    
    return phase_results
```

**Error Handling**:
- Catch HTTP errors, log them, retry with exponential backoff
- Max 3 attempts per metric
- If all retries fail, aggregate error and continue to next phase
- Report all failures at end with summary

**Logging Format**:
```
2026-03-16 14:23:45 [PHASE 1] Starting basic metrics (12 metrics, 4 concurrent)...
2026-03-16 14:23:47 [PHASE 1] Group 1/4 - completed in 2.1s (metrics: MC, Assets, OA)
2026-03-16 14:23:49 [PHASE 1] Group 2/4 - completed in 2.0s (metrics: Op Cost, Non Op Cost, Tax Cost)
2026-03-16 14:23:51 [PHASE 1] Group 3/4 - completed in 2.1s (metrics: XO Cost, ECF, Non Div ECF)
2026-03-16 14:23:53 [PHASE 1] Group 4/4 - completed in 2.2s (metrics: EE, FY TSR, FY TSR PREL)
2026-03-16 14:23:53 [PHASE 1] ✓ Completed in 8.4s (all 12 metrics successful)
2026-03-16 14:23:54 [PHASE 2] Starting beta calculation...
2026-03-16 14:23:56 [PHASE 2] ✓ Completed in 2.1s (beta successful)
...
```

**CLI Usage**:
```bash
python backend/scripts/orchestrate_l1_metrics.py \
  --dataset-id 523eeffd-9220-4d27-927b-e418f9c21d8a \
  --param-set-id 71a0caa6-b52c-4c5e-b550-1048b7329719
```

---

### Phase 2: Fix Batch Inserts

**Files to modify**:
1. `backend/app/services/metrics_service.py` (lines 176-237)
2. `backend/app/services/cost_of_equity_service.py` (similar pattern)
3. `backend/app/services/risk_free_rate_service.py` (similar pattern)

**Current Anti-Pattern** (SLOW):
```python
# For each value in 10,000+ records, execute individual INSERT
for value_dict in values:
    await session.execute(insert_query, value_dict)
```

**New Pattern** (FAST - Multi-row INSERT):
```python
# Execute single INSERT with all rows at once
if values:
    stmt = insert(MetricsOutput).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=['ticker_id', 'metric_id', 'fiscal_year'],
        set_={"value": stmt.excluded.value, "updated_at": stmt.excluded.updated_at}
    )
    await session.execute(stmt)
```

**Expected Improvement**:
- Before: 10,000+ individual INSERTs (~10 seconds for 10,000 rows)
- After: 1 multi-row INSERT (~1 second for 10,000 rows)
- **Improvement**: 80-90% faster insert operations

**Testing Strategy**:
- Test each service individually with small dataset (10 tickers)
- Verify ON CONFLICT (DO UPDATE) logic still works
- Confirm no data loss or duplication
- Measure insert time before/after

---

### Phase 3: Create API Endpoint

**File**: `backend/app/api/v1/endpoints/orchestration.py` (NEW)

**Endpoint**:
```
POST /api/v1/metrics/calculate-l1
Content-Type: application/json

{
  "dataset_id": "523eeffd-9220-4d27-927b-e418f9c21d8a",
  "param_set_id": "71a0caa6-b52c-4c5e-b550-1048b7329719"
}

Response:
{
  "success": true,
  "execution_time_seconds": 47.2,
  "phases": {
    "phase_1": {"status": "success", "metrics": 12, "time_seconds": 8.4},
    "phase_2": {"status": "success", "metrics": 1, "time_seconds": 2.1},
    "phase_3": {"status": "success", "metrics": 2, "time_seconds": 3.2},
    "phase_4": {"status": "success", "metrics": 2, "time_seconds": 2.1}
  },
  "errors": []
}
```

**Implementation**:
- Accept dataset_id and param_set_id in request body
- Call orchestrator script (or import orchestrate function)
- Run synchronously (client waits for completion)
- Return timing stats and status for each phase
- Include error details if any metrics failed

---

### Phase 4: Full Integration Testing

**Test Dataset**: 500 tickers × 20 years

**Validation Steps**:
1. ✅ Run orchestrator CLI with full dataset
2. ✅ Verify all metrics calculate successfully
3. ✅ Measure total execution time (target: <1 minute, realistic: 40-60s)
4. ✅ Spot-check results against sequential baseline
5. ✅ Verify no duplicate/missing records in database
6. ✅ Test error scenarios (invalid dataset_id, network errors, etc.)

**Success Criteria**:
- [ ] Total execution time < 1 minute
- [ ] All 12 Phase 1 metrics successful
- [ ] All Phase 2-4 metrics successful
- [ ] Results match sequential baseline calculation
- [ ] No duplicate or missing records
- [ ] Error handling works (retries, aggregation)

---

## Task Breakdown & Dependencies

### Task 1: Create Orchestrator Script (2-3 hours)
- [ ] Create `backend/scripts/orchestrate_l1_metrics.py`
- [ ] Implement async HTTP client with httpx
- [ ] Implement semaphore for concurrency control (max 4)
- [ ] Implement Phase 1 parallelization (4 groups)
- [ ] Implement Phases 2-4 sequential execution
- [ ] Add retry logic (exponential backoff, max 3 attempts)
- [ ] Add progress logging with timing
- [ ] Add CLI argument parsing (--dataset-id, --param-set-id)
- [ ] Test with small dataset (10 tickers) locally
- **Dependencies**: None (can run in parallel with other tasks)

### Task 2: Fix Batch Inserts (2-3 hours)
- [ ] Fix `metrics_service.py` multi-row INSERT
- [ ] Fix `cost_of_equity_service.py` multi-row INSERT
- [ ] Fix `risk_free_rate_service.py` multi-row INSERT
- [ ] Test each service individually
- [ ] Verify ON CONFLICT logic still works
- [ ] Measure performance improvement
- **Dependencies**: None (can run in parallel with Task 1)

### Task 3: Create API Endpoint (1-2 hours)
- [ ] Create `backend/app/api/v1/endpoints/orchestration.py`
- [ ] Implement POST /api/v1/metrics/calculate-l1 endpoint
- [ ] Call orchestrator function (import from script or refactor)
- [ ] Return formatted response with timing stats
- [ ] Add error handling and logging
- [ ] Update FastAPI app to include new router
- **Dependencies**: Requires Task 1 (orchestrator) to be mostly complete

### Task 4: Full Integration Testing (1-2 hours)
- [ ] Run orchestrator with full 500-ticker dataset
- [ ] Measure total execution time
- [ ] Validate results against baseline
- [ ] Test error scenarios
- [ ] Document final performance metrics
- **Dependencies**: Requires Tasks 1, 2, 3 to be complete

---

## Key Implementation Details

### HTTP Client Setup (httpx)
```python
import httpx
import asyncio

async def call_metric_api(base_url, metric_endpoint, payload, semaphore):
    async with semaphore:
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(f"{base_url}/{metric_endpoint}", json=payload)
            return response.json()
```

### Retry Logic (Exponential Backoff)
```python
async def call_with_retry(func, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        try:
            return await func()
        except Exception as e:
            if attempt == max_attempts:
                raise
            wait_time = 2 ** (attempt - 1)  # 1s, 2s, 4s
            await asyncio.sleep(wait_time)
```

### Metric API Endpoints (Implied by existing bash scripts)
- Phase 1 (Basic): Multiple individual endpoints for each metric
- Phase 2: `/api/v1/metrics/calculate-beta`
- Phase 3: `/api/v1/metrics/calculate-cost-of-equity`
- Phase 4: `/api/v1/metrics/calculate-risk-free-rate`

*Note: Will need to verify actual endpoint paths from FastAPI routing*

---

## Configuration

### Environment Variables
```
# .env (existing)
DATABASE_URL=postgresql://...
API_BASE_URL=http://localhost:8000  # Used by orchestrator to call own APIs
ORCHESTRATOR_CONCURRENCY=4  # Semaphore limit
```

### Database Connection
- Orchestrator is CLI script, uses httpx to call API endpoints
- Does NOT use SQLAlchemy directly (avoids connection pool conflicts)
- Each API endpoint handles its own database session

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| API endpoints become bottleneck under concurrency | Medium | Test with 4 concurrent requests; monitor response times |
| Database connection pool exhaustion | Medium | Each endpoint manages its own session; semaphore limits client concurrency |
| Phase dependencies break (e.g., Beta not calculated before KE) | High | Strict sequential execution for Phases 2-4; validate phase results before continuing |
| Data corruption during batch insert | Medium | Test ON CONFLICT logic; validate results against sequential baseline |
| Orchestrator crashes mid-execution | Medium | Add checkpoint/resume logic (optional Phase 2 enhancement) |

---

## Success Metrics

### Performance
- ✅ Target: Total execution < 1 minute
- ✅ Realistic: 40-60 seconds
- ✅ Measurement: Phase 1 (8-10s) + Phase 2 (2-3s) + Phase 3 (3-5s) + Phase 4 (2-3s) = 15-21s minimum

### Correctness
- ✅ All 17 metrics calculate successfully
- ✅ Results match sequential baseline
- ✅ No duplicate or missing records in database
- ✅ Error handling works as expected

### Maintainability
- ✅ Clean, documented code
- ✅ Easy CLI usage for operations team
- ✅ API endpoint ready for UI integration

---

## Next Steps

1. **Review this plan** with team
2. **Implement Task 1** (Orchestrator script) - Start here
3. **Implement Task 2** (Batch inserts) - Can run in parallel
4. **Implement Task 3** (API endpoint) - Depends on Task 1
5. **Execute Task 4** (Full integration testing)
6. **Validate results** and celebrate performance gains!

---

## Appendix: Existing Bash Scripts (Reference)

### Phase 1: Basic Metrics
- `backend/scripts/run-l1-basic-metrics.sh`
- Calls multiple metric calculation endpoints sequentially
- Takes ~4-5 minutes

### Phase 2: Beta
- `backend/scripts/run-l1-beta-calc.sh`
- Single metric calculation
- Takes ~2 minutes

### Phase 3: Cost of Equity
- `backend/scripts/run-l1-cost-of-equity-calc.sh`
- Single metric calculation (depends on Phase 2 Beta)
- Takes ~2 minutes

### Phase 4: Risk-Free Rate
- `backend/scripts/run-l1-rf-calc.sh`
- Single metric calculation
- Takes ~2 minutes

**Total**: 8-10 minutes sequentially

---

**Document Version**: 1.0  
**Last Updated**: 2026-03-16  
**Status**: Ready for Implementation
