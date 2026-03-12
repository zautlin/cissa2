# Ratio Metrics Implementation Plan

**Date:** 2026-03-12  
**Status:** Planning Phase  
**Scope:** On-the-fly ratio metric calculation API with rolling averages (1Y/3Y/5Y/10Y)

---

## Executive Summary

This plan describes how to implement a **scalable, extensible ratio metrics API** that calculates financial ratios on-the-fly based on pre-calculated L1 metrics. The system will:

- ✅ Accept metric requests with temporal window (1Y/3Y/5Y/10Y)
- ✅ Query pre-calculated metrics from `metrics_outputs` table
- ✅ Calculate rolling averages using SQL window functions
- ✅ Support ratio formulas (division, sums of multiple metrics)
- ✅ Handle parameter-dependent metrics via `param_set_id`
- ✅ Deliver sub-100ms response for 1-5 tickers
- ✅ Be extensible for 10+ ratio metrics without code duplication

---

## System Architecture

### High-Level Data Flow

```
UI Chart Request
    ↓
GET /api/v1/metrics/ratio
  ?metric=MB Ratio
  &tickers=AAPL,MSFT
  &temporal_window=3Y
  &param_set_id=base_case
    ↓
RatioMetricsService
  ├─ Load metric definition (MB Ratio config)
  ├─ Identify numerator (Calc MC) & denominator (Calc EE)
  ├─ Query metrics_outputs table (single SQL call)
  ├─ Calculate rolling averages (SQL window functions)
  └─ Return time-series data
    ↓
Response: {ticker: AAPL, data: [{year: 2001, value: 2.5}, ...]}
    ↓
UI renders chart
```

---

## 1. Metric Definition Schema (JSON Config)

### Location
**File:** `backend/app/config/ratio_metrics.json`

### Structure
```json
{
  "metrics": [
    {
      "id": "mb_ratio",
      "display_name": "MB Ratio",
      "description": "Market-to-Book Ratio (Market Cap / Economic Equity)",
      "formula_type": "ratio",
      "numerator": {
        "metric_name": "Calc MC",
        "parameter_dependent": false
      },
      "denominator": {
        "metric_name": "Calc EE",
        "parameter_dependent": false
      },
      "operation": "divide",
      "null_handling": "skip_year",
      "negative_handling": "skip_year"
    },
    {
      "id": "effective_tax_rate",
      "display_name": "Effective Tax Rate",
      "description": "Effective tax rate (Tax Cost / |PAT + XO Cost|)",
      "formula_type": "complex_ratio",
      "numerator": {
        "metric_name": "Calc Tax Cost",
        "parameter_dependent": false
      },
      "denominator": {
        "metrics": ["PAT", "Calc XO Cost"],
        "operation": "sum",
        "use_absolute_value": true
      },
      "operation": "divide",
      "null_handling": "skip_year",
      "negative_handling": "return_null"
    }
  ]
}
```

### Schema Fields

| Field | Type | Purpose |
|-------|------|---------|
| `id` | string | Unique identifier for metric (lowercase, snake_case) |
| `display_name` | string | Human-readable name for UI |
| `description` | string | Metric documentation |
| `formula_type` | enum | `"ratio"` (simple division), `"complex_ratio"` (sums/complex) |
| `numerator` | object | Metric name(s) and parameter dependency |
| `denominator` | object | Metric name(s) and parameter dependency |
| `operation` | enum | `"divide"`, `"multiply"`, etc. |
| `null_handling` | enum | `"skip_year"` (return NULL for that year), `"use_zero"` |
| `negative_handling` | enum | `"skip_year"` (return NULL), `"return_null"`, `"use_absolute"` |

### Why This Design
- ✅ **Declarative**: New metrics added without code changes
- ✅ **Flexible**: Supports simple ratios and complex operations
- ✅ **Documented**: Formula and handling rules in config
- ✅ **Type-safe**: Python dataclass validation at runtime

---

## 2. API Endpoint Design

### Endpoint
```
GET /api/v1/metrics/ratio-metrics
```

### Request Contract

**Query Parameters:**

| Parameter | Type | Required | Default | Example |
|-----------|------|----------|---------|---------|
| `metric` | string | YES | - | `"mb_ratio"` |
| `tickers` | string[] | YES | - | `["AAPL", "MSFT"]` |
| `temporal_window` | enum | NO | `"1Y"` | `"3Y"` |
| `param_set_id` | UUID | NO | "base_case" | `"a1b2c3d4-..."` |
| `dataset_id` | UUID | YES | - | `"e5e7c8a0-..."` |
| `start_year` | int | NO | - | `2015` |
| `end_year` | int | NO | - | `2023` |

**Example Request:**
```
GET /api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=AAPL,MSFT&temporal_window=3Y&dataset_id=e5e7c8a0-...&param_set_id=base_case
```

### Response Contract

**Success (200 OK):**
```json
{
  "metric": "mb_ratio",
  "display_name": "MB Ratio",
  "temporal_window": "3Y",
  "data": [
    {
      "ticker": "AAPL",
      "time_series": [
        {"year": 2003, "value": 2.45},
        {"year": 2004, "value": 2.67},
        {"year": 2005, "value": 2.89},
        ...
      ]
    },
    {
      "ticker": "MSFT",
      "time_series": [
        {"year": 2003, "value": 1.92},
        {"year": 2004, "value": 2.15},
        ...
      ]
    }
  ]
}
```

**Error (400 Bad Request):**
```json
{
  "error": "Unknown metric: invalid_metric. Available metrics: mb_ratio, effective_tax_rate, ...",
  "status": "error"
}
```

**Error (404 Not Found):**
```json
{
  "error": "No data found for ticker AAPL in dataset ...",
  "status": "not_found"
}
```

---

## 3. SQL Strategy (Window Functions for Rolling Averages)

### Rolling Average Calculation

For temporal window W (1Y, 3Y, 5Y, 10Y):

```sql
-- Generic rolling average pattern
SELECT
  ticker,
  fiscal_year,
  AVG(metric_value) 
    OVER (
      PARTITION BY ticker 
      ORDER BY fiscal_year 
      ROWS BETWEEN (W-1) PRECEDING AND CURRENT ROW
    ) AS rolling_avg_value
FROM metrics_outputs
WHERE dataset_id = :dataset_id
  AND param_set_id = :param_set_id
  AND output_metric_name = :metric_name
ORDER BY ticker, fiscal_year;
```

### Ratio Calculation (Simple Division)

```sql
-- MB Ratio = C_MC (rolling avg) / EE (rolling avg)
WITH calc_mc_rolling AS (
  SELECT
    ticker,
    fiscal_year,
    AVG(output_metric_value) 
      OVER (
        PARTITION BY ticker 
        ORDER BY fiscal_year 
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW  -- For 3Y
      ) AS calc_mc_rolling_avg
  FROM cissa.metrics_outputs
  WHERE dataset_id = :dataset_id
    AND param_set_id = :param_set_id
    AND output_metric_name = 'Calc MC'
),
calc_ee_rolling AS (
  SELECT
    ticker,
    fiscal_year,
    AVG(output_metric_value) 
      OVER (
        PARTITION BY ticker 
        ORDER BY fiscal_year 
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW  -- For 3Y
      ) AS calc_ee_rolling_avg
  FROM cissa.metrics_outputs
  WHERE dataset_id = :dataset_id
    AND param_set_id = :param_set_id
    AND output_metric_name = 'Calc EE'
)
SELECT
  m.ticker,
  m.fiscal_year,
  CASE
    WHEN c.calc_ee_rolling_avg IS NULL THEN NULL
    WHEN c.calc_ee_rolling_avg = 0 THEN NULL
    WHEN c.calc_mc_rolling_avg IS NULL THEN NULL
    ELSE c.calc_mc_rolling_avg / c.calc_ee_rolling_avg
  END AS mb_ratio
FROM calc_mc_rolling m
FULL OUTER JOIN calc_ee_rolling c 
  ON m.ticker = c.ticker AND m.fiscal_year = c.fiscal_year
ORDER BY m.ticker, m.fiscal_year;
```

### Ratio Calculation (Complex: Sum in Denominator)

```sql
-- Effective Tax Rate = Tax Cost / |PAT + XO Cost|
WITH tax_cost_rolling AS (
  SELECT
    ticker,
    fiscal_year,
    AVG(output_metric_value) 
      OVER (
        PARTITION BY ticker 
        ORDER BY fiscal_year 
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW  -- For 3Y
      ) AS tax_cost_rolling_avg
  FROM cissa.metrics_outputs
  WHERE dataset_id = :dataset_id
    AND param_set_id = :param_set_id
    AND output_metric_name = 'Calc Tax Cost'
),
pat_rolling AS (
  SELECT
    ticker,
    fiscal_year,
    AVG(output_metric_value) 
      OVER (
        PARTITION BY ticker 
        ORDER BY fiscal_year 
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
      ) AS pat_rolling_avg
  FROM cissa.metrics_outputs
  WHERE dataset_id = :dataset_id
    AND param_set_id = :param_set_id
    AND output_metric_name = 'PAT'  -- Note: verify this metric name
),
xo_cost_rolling AS (
  SELECT
    ticker,
    fiscal_year,
    AVG(output_metric_value) 
      OVER (
        PARTITION BY ticker 
        ORDER BY fiscal_year 
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
      ) AS xo_cost_rolling_avg
  FROM cissa.metrics_outputs
  WHERE dataset_id = :dataset_id
    AND param_set_id = :param_set_id
    AND output_metric_name = 'Calc XO Cost'
)
SELECT
  t.ticker,
  t.fiscal_year,
  CASE
    WHEN ABS(p.pat_rolling_avg + x.xo_cost_rolling_avg) = 0 THEN NULL
    WHEN ABS(p.pat_rolling_avg + x.xo_cost_rolling_avg) IS NULL THEN NULL
    WHEN t.tax_cost_rolling_avg IS NULL THEN NULL
    ELSE t.tax_cost_rolling_avg / ABS(p.pat_rolling_avg + x.xo_cost_rolling_avg)
  END AS effective_tax_rate
FROM tax_cost_rolling t
FULL OUTER JOIN pat_rolling p ON t.ticker = p.ticker AND t.fiscal_year = p.fiscal_year
FULL OUTER JOIN xo_cost_rolling x ON t.ticker = x.ticker AND t.fiscal_year = x.fiscal_year
ORDER BY t.ticker, t.fiscal_year;
```

### Key SQL Patterns

1. **Window Function for Rolling Average:**
   - 1Y: `ROWS BETWEEN 0 PRECEDING AND CURRENT ROW` (just current)
   - 3Y: `ROWS BETWEEN 2 PRECEDING AND CURRENT ROW` (current + 2 prior)
   - 5Y: `ROWS BETWEEN 4 PRECEDING AND CURRENT ROW`
   - 10Y: `ROWS BETWEEN 9 PRECEDING AND CURRENT ROW`

2. **NULL Handling:**
   - Check for NULL values in each metric before division
   - Check for zero denominators (return NULL if true)
   - Use `FULL OUTER JOIN` to capture all years even if one metric missing

3. **Negative Denominator Handling:**
   - `ABS(denominator) = 0` → return NULL
   - `ABS(denominator) IS NULL` → return NULL

---

## 4. Service Layer Architecture

### File Structure
```
backend/app/
├── services/
│   ├── ratio_metrics_service.py          # Main service
│   └── ratio_metrics_calculator.py       # SQL builder
├── models/
│   └── ratio_metrics.py                  # Pydantic models
├── repositories/
│   └── ratio_metrics_repository.py       # Data access
├── api/v1/endpoints/
│   └── ratio_metrics.py                  # API endpoint
└── config/
    └── ratio_metrics.json                # Metric definitions
```

### RatioMetricsService Class Structure

```python
class RatioMetricsService:
    """Service for calculating ratio metrics on-the-fly"""
    
    def __init__(self, session: AsyncSession, repo: RatioMetricsRepository):
        self.session = session
        self.repo = repo
        self.metric_config = load_ratio_metrics_config()
    
    async def calculate_ratio_metric(
        self,
        metric_id: str,
        tickers: List[str],
        dataset_id: UUID,
        temporal_window: str = "1Y",
        param_set_id: Optional[UUID] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> RatioMetricsResponse:
        """Main entry point for ratio metric calculation"""
        
        # Step 1: Validate metric exists in config
        metric_def = self._get_metric_definition(metric_id)
        
        # Step 2: Resolve param_set_id (default to base_case if needed)
        param_set_id = await self._resolve_param_set_id(param_set_id)
        
        # Step 3: Build and execute SQL query
        sql_query = self._build_ratio_query(
            metric_def,
            tickers,
            dataset_id,
            param_set_id,
            temporal_window,
            start_year,
            end_year
        )
        
        # Step 4: Execute query and parse results
        results = await self.repo.execute_ratio_query(sql_query)
        
        # Step 5: Format response
        return self._format_response(metric_def, temporal_window, results)
    
    def _build_ratio_query(
        self,
        metric_def: MetricDefinition,
        tickers: List[str],
        dataset_id: UUID,
        param_set_id: UUID,
        temporal_window: str,
        start_year: Optional[int],
        end_year: Optional[int]
    ) -> str:
        """Build parameterized SQL query from metric definition"""
        
        # Delegate to RatioMetricsCalculator
        calculator = RatioMetricsCalculator(metric_def, temporal_window)
        return calculator.build_query(
            tickers,
            dataset_id,
            param_set_id,
            start_year,
            end_year
        )
    
    def _get_metric_definition(self, metric_id: str) -> MetricDefinition:
        """Load metric definition from config"""
        # Return MetricDefinition dataclass instance
    
    async def _resolve_param_set_id(self, param_set_id: Optional[UUID]) -> UUID:
        """Get default param_set_id if not provided"""
        # Query parameter_sets table for is_default=true
```

### RatioMetricsCalculator Class

```python
class RatioMetricsCalculator:
    """Builds SQL queries for ratio metric calculations"""
    
    def __init__(self, metric_def: MetricDefinition, temporal_window: str):
        self.metric_def = metric_def
        self.temporal_window = temporal_window
        self.rows_between = self._calculate_rows_between(temporal_window)
    
    def build_query(
        self,
        tickers: List[str],
        dataset_id: UUID,
        param_set_id: UUID,
        start_year: Optional[int],
        end_year: Optional[int]
    ) -> str:
        """Build complete SQL query"""
        
        if self.metric_def.formula_type == "ratio":
            return self._build_simple_ratio_query(...)
        elif self.metric_def.formula_type == "complex_ratio":
            return self._build_complex_ratio_query(...)
    
    def _build_simple_ratio_query(self, ...) -> str:
        """Build query for numerator / denominator"""
        # Template SQL with CTEs
    
    def _build_complex_ratio_query(self, ...) -> str:
        """Build query for complex operations (sum in denominator)"""
        # Template SQL with multiple CTEs
    
    def _calculate_rows_between(self, temporal_window: str) -> str:
        """Convert 1Y/3Y/5Y/10Y to SQL ROWS BETWEEN clause"""
        # "3Y" → "ROWS BETWEEN 2 PRECEDING AND CURRENT ROW"
```

### Pydantic Models

```python
# In backend/app/models/ratio_metrics.py

class TimeSeries(BaseModel):
    year: int
    value: float

class TickerData(BaseModel):
    ticker: str
    time_series: List[TimeSeries]

class RatioMetricsResponse(BaseModel):
    metric: str
    display_name: str
    temporal_window: str
    data: List[TickerData]

class MetricDefinition(BaseModel):
    id: str
    display_name: str
    description: str
    formula_type: Literal["ratio", "complex_ratio"]
    numerator: Dict[str, Any]
    denominator: Dict[str, Any]
    operation: str
    null_handling: str
    negative_handling: str
```

---

## 5. API Endpoint Implementation

### File: `backend/app/api/v1/endpoints/ratio_metrics.py`

```python
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/ratio-metrics")
async def get_ratio_metrics(
    metric: str = Query(..., description="Metric ID (e.g., 'mb_ratio')"),
    tickers: str = Query(..., description="Comma-separated ticker list (e.g., 'AAPL,MSFT')"),
    dataset_id: UUID = Query(..., description="Dataset ID"),
    temporal_window: str = Query("1Y", regex="^(1Y|3Y|5Y|10Y)$"),
    param_set_id: Optional[UUID] = Query(None, description="Parameter set ID (defaults to base_case)"),
    start_year: Optional[int] = Query(None),
    end_year: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session)
) -> RatioMetricsResponse:
    """
    Calculate ratio metrics with rolling averages.
    
    Example:
        GET /api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=AAPL,MSFT&temporal_window=3Y&dataset_id=...
    
    Returns time-series data for each ticker.
    """
    
    try:
        # Parse comma-separated tickers
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
        
        # Initialize service
        repo = RatioMetricsRepository(session)
        service = RatioMetricsService(session, repo)
        
        # Calculate metric
        result = await service.calculate_ratio_metric(
            metric_id=metric,
            tickers=ticker_list,
            dataset_id=dataset_id,
            temporal_window=temporal_window,
            param_set_id=param_set_id,
            start_year=start_year,
            end_year=end_year
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating ratio metric: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## 6. Extensibility Pattern

### Adding New Ratio Metrics

To add a new ratio metric, follow these steps:

**Step 1: Add to `ratio_metrics.json`**
```json
{
  "id": "pe_ratio",
  "display_name": "P/E Ratio",
  "description": "Price-to-Earnings Ratio",
  "formula_type": "ratio",
  "numerator": {
    "metric_name": "Calc MC",
    "parameter_dependent": false
  },
  "denominator": {
    "metric_name": "PAT",  // Profit After Tax
    "parameter_dependent": false
  },
  "operation": "divide",
  "null_handling": "skip_year",
  "negative_handling": "return_null"
}
```

**Step 2: No code changes needed!**
- The metric definition is automatically picked up by `RatioMetricsService`
- `RatioMetricsCalculator` generates the SQL dynamically
- API endpoint works without modification

**Step 3: (Optional) Add validation if needed**
- If metric has special requirements, add to `MetricDefinition` class
- Update `RatioMetricsCalculator` if special SQL logic needed

---

## 7. Implementation Tasks (Breakdown)

### Phase 1: Foundation (2-3 hours)

- [ ] **Task 1.1**: Create `backend/app/config/ratio_metrics.json`
  - Define MB Ratio metric
  - Add placeholder for additional metrics

- [ ] **Task 1.2**: Create Pydantic models (`backend/app/models/ratio_metrics.py`)
  - `MetricDefinition`
  - `TimeSeries`
  - `TickerData`
  - `RatioMetricsResponse`

- [ ] **Task 1.3**: Create `RatioMetricsRepository` class
  - `async def execute_ratio_query(sql: str) -> List[Dict]`
  - Handles async database execution

### Phase 2: Service Layer (3-4 hours)

- [ ] **Task 2.1**: Create `RatioMetricsCalculator` class
  - `build_query()` method
  - `_build_simple_ratio_query()` for division
  - `_build_complex_ratio_query()` for sums
  - Window function generation

- [ ] **Task 2.2**: Create `RatioMetricsService` class
  - `calculate_ratio_metric()` main method
  - Metric config loading
  - Parameter set resolution
  - Response formatting

- [ ] **Task 2.3**: Unit test SQL query generation
  - Test MB Ratio query generation
  - Test rolling average window functions
  - Test NULL handling

### Phase 3: API Endpoint (1-2 hours)

- [ ] **Task 3.1**: Create API endpoint
  - `GET /api/v1/metrics/ratio-metrics`
  - Request validation
  - Error handling

- [ ] **Task 3.2**: Integration test
  - End-to-end request/response
  - Performance benchmark (sub-100ms target)

### Phase 4: Documentation & Iteration (1 hour)

- [ ] **Task 4.1**: Document metric addition process
- [ ] **Task 4.2**: Add logging for debugging
- [ ] **Task 4.3**: Prepare for metric additions (Effective Tax Rate, etc.)

---

## 8. Performance Considerations

### Query Optimization

1. **Indexes** (already exist):
   - `idx_metrics_outputs_unique(dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)`
   - `idx_metrics_outputs_ticker_fy(ticker, fiscal_year)`

2. **Query Strategy**:
   - Use CTEs to pre-calculate rolling averages
   - Single JOIN between numerator/denominator rolling averages
   - Filter by (dataset_id, param_set_id, tickers) early

3. **Expected Performance**:
   - Single ticker: <50ms
   - 5 tickers: <100ms
   - (Assuming PostgreSQL on localhost with indexes)

### Caching Strategy (Optional Future)

- UI-level caching: Cache response in browser for same query
- API-level caching: Redis cache for frequently accessed metrics
- TTL: 24 hours (metrics data doesn't change frequently)

---

## 9. Example: MB Ratio Implementation

### Config Entry
```json
{
  "id": "mb_ratio",
  "display_name": "MB Ratio",
  "description": "Market-to-Book Ratio",
  "formula_type": "ratio",
  "numerator": {
    "metric_name": "Calc MC",
    "parameter_dependent": false
  },
  "denominator": {
    "metric_name": "Calc EE",
    "parameter_dependent": false
  },
  "operation": "divide",
  "null_handling": "skip_year",
  "negative_handling": "return_null"
}
```

### Example Request/Response

**Request:**
```
GET /api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=AAPL,MSFT&dataset_id=e5e7c8a0-...&temporal_window=3Y
```

**Response:**
```json
{
  "metric": "mb_ratio",
  "display_name": "MB Ratio",
  "temporal_window": "3Y",
  "data": [
    {
      "ticker": "AAPL",
      "time_series": [
        {"year": 2003, "value": 2.45},
        {"year": 2004, "value": 2.67},
        {"year": 2005, "value": 2.89}
      ]
    },
    {
      "ticker": "MSFT",
      "time_series": [
        {"year": 2003, "value": 1.92},
        {"year": 2004, "value": 2.15},
        {"year": 2005, "value": 2.38}
      ]
    }
  ]
}
```

---

## 10. Implementation Checklist

**Pre-Implementation:**
- [ ] Confirm L1 metric names in `metrics_outputs` table (Calc MC, Calc EE, PAT, etc.)
- [ ] Verify `param_set_id` behavior (does base_case always exist?)
- [ ] Test window function syntax on target PostgreSQL version

**Implementation:**
- [ ] Phase 1: Foundation (config + models + repository)
- [ ] Phase 2: Service layer (calculator + service)
- [ ] Phase 3: API endpoint
- [ ] Phase 4: Testing + documentation

**Post-Implementation:**
- [ ] Performance benchmarking (aim for <100ms)
- [ ] Add logging for debugging
- [ ] Document metric addition process
- [ ] Plan for next 10+ metrics (Effective Tax Rate, PE Ratio, etc.)

---

## 11. Questions & Assumptions

### Assumptions Made
1. L1 metrics `Calc MC` and `Calc EE` already exist in `metrics_outputs` table
2. `PAT` (Profit After Tax) metric exists (for Effective Tax Rate)
3. PostgreSQL window functions (`AVG() OVER()`) are available
4. `param_set_id` always resolves to a valid UUID (defaults to base_case)
5. Sub-100ms response time is achievable with single SQL query + local indexes

### Questions to Verify
1. What is the exact metric name for Profit After Tax in `metrics_outputs`? (`PAT` or `Calc PAT`?)
2. Should the API support filtering by year range (start_year/end_year) or always return full history?
3. Do we need request rate limiting or caching strategy?
4. Should response include metadata (data completeness, actual window size)?

---

## 12. Next Steps

Once you approve this plan:

1. **Confirm metric names** in `metrics_outputs` table (especially `PAT`)
2. **Answer verification questions** (above)
3. **Begin Phase 1 implementation** (config + models + repository)
4. **Iteratively add metrics** as needed

Would you like me to proceed with implementation, or do you have adjustments to this plan?
