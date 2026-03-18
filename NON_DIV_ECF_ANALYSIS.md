# Non Div ECF Calculation: Flow Analysis

## Summary

Non Div ECF is **calculated during data ingestion** as part of the automatic L1 metrics calculation phase, not on-demand at runtime. It follows a **two-phase execution pattern** within the ingestion pipeline.

---

## Phase Architecture

### Phase 1: Base Metrics (Fundamentals-based)
Read directly from the `fundamentals` table and stored in `metrics_outputs`:

1. Calc MC (Market Cap)
2. Calc Assets (Operating Assets)
3. Calc OA (Operating Assets Detail) - depends on Calc Assets
4. Calc Op Cost (Operating Cost)
5. Calc Non Op Cost (Non-Operating Cost)
6. Calc Tax Cost (Tax Cost)
7. Calc XO Cost (Extraordinary Cost)
8. Calc ECF (Economic Cash Flow)
9. Calc EE (Economic Equity)
10. Calc FY TSR (Fiscal Year TSR)

### Phase 2: Derived Metrics (Metrics_outputs-dependent)
Depend on Phase 1 results being committed to `metrics_outputs`:

1. **Non Div ECF** - Depends on Calc ECF being in metrics_outputs
2. **Calc FY TSR PREL** - Depends on Calc FY TSR being in metrics_outputs

---

## Non Div ECF Calculation Details

### SQL Function Signature
```sql
CREATE OR REPLACE FUNCTION cissa.fn_calc_non_div_ecf(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  non_div_ecf NUMERIC
)
```

### Calculation Logic
```sql
SELECT
  mo.ticker,
  mo.fiscal_year,
  (COALESCE(mo.output_metric_value, 0) + COALESCE(f.numeric_value, 0)) AS non_div_ecf
FROM cissa.metrics_outputs mo
LEFT JOIN cissa.fundamentals f
  ON mo.ticker = f.ticker
   AND mo.fiscal_year = f.fiscal_year
   AND mo.dataset_id = f.dataset_id
   AND f.metric_name = 'DIVIDENDS'
WHERE
  mo.dataset_id = p_dataset_id
  AND mo.output_metric_name = 'Calc ECF'
```

**Formula:** `Non Div ECF = Calc ECF + DIVIDENDS`

**Dependencies:**
- Calc ECF from metrics_outputs (Phase 1 output)
- DIVIDENDS from fundamentals (raw input data)

---

## Ingestion Orchestration Flow

### Entry Point
File: `/backend/database/etl/ingestion.py`, class `Ingester`

```python
def load_dataset(self, csv_path: str, ...) -> Dict[str, Any]:
    # ... ingestion steps ...
    # At end of ingestion, auto-trigger L1 metrics
    self._auto_calculate_l1_metrics(dataset_id)
```

### Async Metrics Calculation
Method: `_auto_calculate_l1_metrics(dataset_id)` (line 214-244)

- Runs `asyncio.run()` to bridge sync ingestion with async metrics service
- Calls `calculate_batch_metrics()` with two-phase execution
- Returns results summary {status, calculated, failed, errors}

### Two-Phase Execution
Method: `MetricsService.calculate_batch_metrics()` (line 494-647)

**PHASE 1 Execution (lines 567-591):**
```python
# PHASE 1: Calculate base metrics (10 metrics reading from fundamentals)
phase1_metrics = [
    "Calc MC", "Calc Assets", "Calc OA", "Calc Op Cost",
    "Calc Non Op Cost", "Calc Tax Cost", "Calc XO Cost",
    "LAG_MC", "Calc ECF", "Calc EE", "Calc FY TSR"
]

# Loop and execute each metric
for metric_name in phase1_metrics:
    row_count = await self._execute_sql_function(metric_name, dataset_id)
    # Results inserted into metrics_outputs via multi-row INSERT
```

**Database Commit (line 591):**
```python
logger.info("Database commit after PHASE 1 - metrics_outputs now contains base metric results")
```

**PHASE 2 Execution (lines 593-619):**
```python
# PHASE 2: Calculate derived metrics (2 metrics reading from metrics_outputs)
phase2_metrics = [
    "Non Div ECF",           # Depends on Calc ECF in metrics_outputs
    "Calc FY TSR PREL"       # Depends on Calc FY TSR in metrics_outputs
]

# Loop and execute each metric
for metric_name in phase2_metrics:
    row_count = await self._execute_sql_function(metric_name, dataset_id)
    # Results inserted into metrics_outputs
```

---

## METRIC_FUNCTIONS Mapping

File: `/backend/app/services/metrics_service.py` (lines 15-44)

```python
METRIC_FUNCTIONS = {
    # Phase 1 - Simple Metrics (7)
    "Calc MC": ("fn_calc_market_cap", "calc_mc", False),
    "Calc Assets": ("fn_calc_operating_assets", "calc_assets", False),
    "Calc OA": ("fn_calc_operating_assets_detail", "calc_oa", False),
    "Calc Op Cost": ("fn_calc_operating_cost", "calc_op_cost", False),
    "Calc Non Op Cost": ("fn_calc_non_operating_cost", "calc_non_op_cost", False),
    "Calc Tax Cost": ("fn_calc_tax_cost", "calc_tax_cost", False),
    "Calc XO Cost": ("fn_calc_extraordinary_cost", "calc_xo_cost", False),
    
    # Phase 1 - Temporal Metrics (5)
    "Calc ECF": ("fn_calc_ecf", "ecf", False),
    "Calc EE": ("fn_calc_economic_equity", "ee", True),
    "Calc FY TSR": ("fn_calc_fy_tsr", "fy_tsr", True),
    "Calc FY TSR PREL": ("fn_calc_fy_tsr_prel", "fy_tsr_prel", True),
    
    # Phase 2 - Derived Metrics (2)
    "Non Div ECF": ("fn_calc_non_div_ecf", "non_div_ecf", False),
    # Requires param_set_id only for lookup, not for SQL function param
}
```

**Key attributes:**
- Column 1: SQL function name
- Column 2: Output column name
- Column 3: Boolean - requires parameter_set_id (False = doesn't)

---

## Batch Insert Optimization

Method: `_insert_metric_results_with_metadata()` (lines 329-400)

**Before:** 10,000+ individual INSERT statements (~10 seconds)
**After:** Single multi-row INSERT statement (~1 second)

```sql
INSERT INTO cissa.metrics_outputs 
(dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata, created_at)
VALUES 
  ('dataset-123', 'param-456', 'AAPL', 2024, 'Non Div ECF', 150000000.0, '{"metric_level": "L1"}', now()),
  ('dataset-123', 'param-456', 'MSFT', 2024, 'Non Div ECF', 250000000.0, '{"metric_level": "L1"}', now()),
  -- ... all rows in single statement
ON CONFLICT (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name) 
DO UPDATE SET output_metric_value = EXCLUDED.output_metric_value
```

---

## API Endpoints

### Orchestration Endpoint
**POST** `/api/v1/metrics/calculate-l1`

File: `/backend/app/api/v1/endpoints/orchestration.py` (lines 263-322)

Orchestrates Phase 1 & 2 pre-computation:
- Phase 1: 12 basic metrics in 4 parallelized groups
- Phase 2: Beta pre-computation (sequential)

Expected execution time: 20-30 seconds

### Runtime Metrics Endpoint
**POST** `/api/v1/metrics/runtime-metrics`

File: `/backend/app/api/v1/endpoints/metrics.py` (lines 1088-1176)

Orchestrates Phase 3+:
- Beta Rounding
- Risk-Free Rate calculation
- Cost of Equity calculation

These run **separately at runtime**, not during ingestion.

---

## Key Files & Code References

### Ingestion Pipeline
- **File:** `/backend/database/etl/ingestion.py`
  - Lines 214-244: `_auto_calculate_l1_metrics()`
  - Lines 246-335: `_async_calculate_l1_metrics()`

### Metrics Service (Two-Phase Execution)
- **File:** `/backend/app/services/metrics_service.py`
  - Lines 15-44: METRIC_FUNCTIONS mapping
  - Lines 494-647: `calculate_batch_metrics()` - Two-phase orchestration
  - Lines 402-492: `calculate_all_l1_metrics()` - Dependency order

### API Orchestration
- **File:** `/backend/app/api/v1/endpoints/orchestration.py`
  - Lines 143-209: Phase 1 & 2 grouping

### Runtime Orchestration (Phase 3+)
- **File:** `/backend/app/services/runtime_metrics_orchestration_service.py`
  - Lines 30-200: RuntimeMetricsOrchestrationService class

---

## Non Div ECF Calculation Timing

| Phase | When | Status | Dependency |
|-------|------|--------|------------|
| Ingestion | During data load | AUTOMATIC | Calc ECF |
| Runtime | On-demand via API | OPTIONAL | N/A (already computed) |

**Answer:** Non Div ECF is calculated **during ingestion as part of Phase 2 (Derived Metrics)**, NOT on-demand at runtime. The two-phase execution ensures Calc ECF is persisted to metrics_outputs before Non Div ECF attempts to read it.

---

## Documentation References

### Temporal Capability Docs
- `/TEMPORAL_CAPABILITY_README.md` - Overview of temporal metrics
- `/TEMPORAL_CAPABILITY_QUICK_REFERENCE.md` - Quick lookup
- `/TEMPORAL_CAPABILITY_ANALYSIS.md` - Detailed analysis

### Architecture Docs
- `/backend/docs/ORCHESTRATOR.md` - Orchestration implementation
- `/backend/docs/ARCHITECTURE.md` - Database schema & phases

### Implementation Plan
- `/IMPLEMENTATION_PLAN.md` - Refactoring from pre-computed to runtime metrics

