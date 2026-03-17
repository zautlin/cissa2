# Metrics Outputs Endpoint Template & Quick Reference

This document provides a quick reference for building new endpoints that query the `metrics_outputs` table, using the statistics endpoint as a template.

---

## Quick Summary: metrics_outputs Table

| Column | Type | Key Feature |
|--------|------|------------|
| `metrics_output_id` | BIGINT | Primary key (auto-increment) |
| `dataset_id` | UUID | **Required filter** - FK to dataset_versions |
| `param_set_id` | UUID | **Required filter** - FK to parameter_sets (nullable for pre-computed) |
| `ticker` | TEXT | Company ticker (can be used as filter) |
| `fiscal_year` | INTEGER | Fiscal year (can be used as filter) |
| `output_metric_name` | TEXT | Metric name (e.g., 'Beta', 'Calc MC') |
| `output_metric_value` | NUMERIC | The calculated value |
| `metadata` | JSONB | Flexible JSON storage |
| `created_at` | TIMESTAMPTZ | Record creation timestamp |

**Unique Constraint:** `(dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)`

---

## Pattern: Creating a New Endpoint

### Step 1: Create Response Pydantic Models

**File:** `backend/app/models/your_endpoint_model.py`

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class MetricRecord(BaseModel):
    """Single metric output record"""
    ticker: str = Field(..., description="Company ticker")
    fiscal_year: int = Field(..., description="Fiscal year")
    output_metric_name: str = Field(..., description="Metric name")
    output_metric_value: float = Field(..., description="Metric value")
    metadata: Optional[dict] = Field(None, description="Flexible JSON metadata")
    created_at: Optional[datetime] = Field(None, description="Record creation time")

class YourEndpointResponse(BaseModel):
    """Response model for your endpoint"""
    dataset_id: UUID = Field(..., description="Dataset ID")
    param_set_id: UUID = Field(..., description="Parameter set ID")
    results_count: int = Field(..., description="Number of results")
    results: List[MetricRecord] = Field(..., description="Metric records")
    filters_applied: Optional[dict] = Field(None, description="Applied filters")
    status: str = Field(..., description="success | error")
    message: Optional[str] = Field(None, description="Status message")
```

### Step 2: Create Repository Methods

**File:** `backend/app/repositories/your_endpoint_repository.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from uuid import UUID
from typing import List, Optional

class YourEndpointRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def query_metrics(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        ticker: Optional[str] = None,
        metric_name: Optional[str] = None,
    ) -> List[dict]:
        """
        Query metrics with optional filtering
        
        Args:
            dataset_id: Dataset ID (required)
            param_set_id: Parameter set ID (required)
            ticker: Optional ticker filter
            metric_name: Optional metric name filter
        
        Returns:
            List of metric records as dicts
        """
        query = text("""
            SELECT 
                ticker,
                fiscal_year,
                output_metric_name,
                output_metric_value,
                metadata,
                created_at
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
              AND param_set_id = :param_set_id
        """)
        
        params = {
            "dataset_id": str(dataset_id),
            "param_set_id": str(param_set_id),
        }
        
        # Add optional filters
        if ticker:
            query = text(str(query) + " AND ticker ILIKE :ticker")
            params["ticker"] = f"%{ticker}%"
        
        if metric_name:
            query = text(str(query) + " AND output_metric_name ILIKE :metric_name")
            params["metric_name"] = f"%{metric_name}%"
        
        query = text(str(query) + " ORDER BY ticker, fiscal_year, output_metric_name")
        
        result = await self.db.execute(query, params)
        rows = result.fetchall()
        
        # Convert rows to dicts
        return [dict(row._mapping) for row in rows]
```

### Step 3: Create Service with Caching (Optional)

**File:** `backend/app/services/your_endpoint_service.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional, List

from app.repositories.your_endpoint_repository import YourEndpointRepository
from app.models.your_endpoint_model import MetricRecord, YourEndpointResponse
from app.core.config import get_logger

logger = get_logger(__name__)

class YourEndpointService:
    """Service for your endpoint with optional caching"""
    
    # Class-level cache
    _cache: dict = {}
    _cache_ttl_seconds = 3600  # 1 hour
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = YourEndpointRepository(db)
    
    def _cache_key(self, dataset_id: UUID, param_set_id: UUID):
        return f"{dataset_id}:{param_set_id}"
    
    async def query_metrics(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        ticker: Optional[str] = None,
        metric_name: Optional[str] = None,
    ) -> YourEndpointResponse:
        """
        Query metrics with business logic and optional caching
        
        Note: Cache is only used when no ticker/metric_name filters applied
        """
        # Check cache (only for non-filtered queries)
        if ticker is None and metric_name is None:
            cache_key = self._cache_key(dataset_id, param_set_id)
            if cache_key in self._cache:
                cached_data = self._cache[cache_key]
                if datetime.utcnow() - cached_data["timestamp"] < timedelta(seconds=self._cache_ttl_seconds):
                    logger.info(f"Returning cached results for {cache_key}")
                    return cached_data["response"]
        
        # Query database
        logger.info(f"Querying metrics: dataset={dataset_id}, param_set={param_set_id}")
        records = await self.repo.query_metrics(
            dataset_id=dataset_id,
            param_set_id=param_set_id,
            ticker=ticker,
            metric_name=metric_name,
        )
        
        # Convert to Pydantic models
        metric_records = [MetricRecord(**record) for record in records]
        
        # Build response
        filters_applied = {}
        if ticker:
            filters_applied["ticker"] = ticker
        if metric_name:
            filters_applied["metric_name"] = metric_name
        
        response = YourEndpointResponse(
            dataset_id=dataset_id,
            param_set_id=param_set_id,
            results_count=len(metric_records),
            results=metric_records,
            filters_applied=filters_applied if filters_applied else None,
            status="success",
            message=f"Retrieved {len(metric_records)} metrics"
        )
        
        # Cache non-filtered results
        if ticker is None and metric_name is None:
            cache_key = self._cache_key(dataset_id, param_set_id)
            self._cache[cache_key] = {
                "response": response,
                "timestamp": datetime.utcnow()
            }
            logger.info(f"Cached results for {cache_key}")
        
        return response
```

### Step 4: Create Endpoint Handler

**File:** `backend/app/api/v1/endpoints/your_endpoint.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.models.your_endpoint_model import YourEndpointResponse
from app.services.your_endpoint_service import YourEndpointService
from app.core.config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/metrics", tags=["your_endpoint"])

@router.get("/your_endpoint", response_model=YourEndpointResponse)
async def your_endpoint(
    dataset_id: UUID = Query(..., description="Dataset ID"),
    param_set_id: UUID = Query(..., description="Parameter set ID"),
    ticker: Optional[str] = Query(None, description="Optional ticker filter"),
    metric_name: Optional[str] = Query(None, description="Optional metric name filter"),
    db: AsyncSession = Depends(get_db)
):
    """
    Query metrics from metrics_outputs table
    
    **Parameters:**
    - `dataset_id` (required): UUID of the dataset
    - `param_set_id` (required): UUID of the parameter set
    - `ticker` (optional): Filter by ticker (case-insensitive)
    - `metric_name` (optional): Filter by metric name (case-insensitive)
    
    **Example Requests:**
    
    Get all metrics:
    ```
    GET /api/v1/metrics/your_endpoint?dataset_id=...&param_set_id=...
    ```
    
    Get metrics for specific ticker:
    ```
    GET /api/v1/metrics/your_endpoint?dataset_id=...&param_set_id=...&ticker=AAPL
    ```
    
    Get specific metric for all tickers:
    ```
    GET /api/v1/metrics/your_endpoint?dataset_id=...&param_set_id=...&metric_name=Beta
    ```
    """
    
    try:
        service = YourEndpointService(db)
        response = await service.query_metrics(
            dataset_id=dataset_id,
            param_set_id=param_set_id,
            ticker=ticker,
            metric_name=metric_name,
        )
        
        logger.info(
            f"Retrieved {response.results_count} metrics for dataset {dataset_id}, "
            f"param_set {param_set_id}"
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Error retrieving metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metrics: {str(e)}"
        )
```

### Step 5: Register Router

**File:** `backend/app/api/v1/router.py`

```python
from fastapi import APIRouter
from .endpoints import metrics, parameters, orchestration, statistics, your_endpoint

router = APIRouter()
router.include_router(metrics.router)
router.include_router(parameters.router)
router.include_router(orchestration.router)
router.include_router(statistics.router)
router.include_router(your_endpoint.router)  # ADD THIS LINE
```

---

## Common Query Patterns for metrics_outputs

### Pattern 1: Get all metrics for a dataset/param_set

```sql
SELECT ticker, fiscal_year, output_metric_name, output_metric_value
FROM cissa.metrics_outputs
WHERE dataset_id = :dataset_id
  AND param_set_id = :param_set_id
ORDER BY ticker, fiscal_year, output_metric_name
```

### Pattern 2: Filter by ticker

```sql
SELECT ticker, fiscal_year, output_metric_name, output_metric_value
FROM cissa.metrics_outputs
WHERE dataset_id = :dataset_id
  AND param_set_id = :param_set_id
  AND ticker ILIKE :ticker
ORDER BY fiscal_year DESC
```

### Pattern 3: Filter by metric name

```sql
SELECT ticker, fiscal_year, output_metric_name, output_metric_value
FROM cissa.metrics_outputs
WHERE dataset_id = :dataset_id
  AND param_set_id = :param_set_id
  AND output_metric_name ILIKE :metric_name
ORDER BY ticker, fiscal_year DESC
```

### Pattern 4: Get pre-computed metrics (param_set_id IS NULL)

```sql
SELECT ticker, fiscal_year, output_metric_name, output_metric_value
FROM cissa.metrics_outputs
WHERE dataset_id = :dataset_id
  AND param_set_id IS NULL
ORDER BY ticker, fiscal_year, output_metric_name
```

### Pattern 5: Get metrics for specific ticker + metric

```sql
SELECT fiscal_year, output_metric_value
FROM cissa.metrics_outputs
WHERE dataset_id = :dataset_id
  AND param_set_id = :param_set_id
  AND ticker = :ticker
  AND output_metric_name = :metric_name
ORDER BY fiscal_year
```

### Pattern 6: Get distinct metric names available

```sql
SELECT DISTINCT output_metric_name
FROM cissa.metrics_outputs
WHERE dataset_id = :dataset_id
  AND param_set_id = :param_set_id
ORDER BY output_metric_name
```

### Pattern 7: Count records by metric

```sql
SELECT output_metric_name, COUNT(*) as record_count
FROM cissa.metrics_outputs
WHERE dataset_id = :dataset_id
  AND param_set_id = :param_set_id
GROUP BY output_metric_name
ORDER BY record_count DESC
```

---

## Statistics Endpoint as Reference

The `/api/v1/metrics/statistics` endpoint is an excellent template. It demonstrates:

1. **Optional Query Parameters**
   - When `dataset_id` provided → single dataset statistics
   - When omitted → all datasets statistics
   - Returns different response types based on parameter

2. **Error Handling**
   - HTTPException for errors
   - Detailed logging
   - Graceful degradation (returns NULL values)

3. **Service/Repository Separation**
   - Service handles business logic and caching
   - Repository handles database queries
   - Clean layering

4. **Async Patterns**
   - Async/await throughout
   - `asyncio.gather()` for parallel execution
   - Proper exception handling

---

## Key Indexes for Performance

The metrics_outputs table has these indexes:

```sql
-- Uniqueness constraint
UNIQUE (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)

-- Pre-computed metrics
CREATE INDEX idx_metrics_outputs_precomputed 
ON metrics_outputs (dataset_id, ticker, fiscal_year, output_metric_name) 
WHERE param_set_id IS NULL;

-- Access patterns
CREATE INDEX idx_metrics_outputs_dataset ON metrics_outputs (dataset_id);
CREATE INDEX idx_metrics_outputs_param_set ON metrics_outputs (param_set_id);
CREATE INDEX idx_metrics_outputs_ticker_fy ON metrics_outputs (ticker, fiscal_year);
```

**Query optimization tips:**
- Always filter by `dataset_id` (helps query planner)
- Filter by `param_set_id` next (both are heavily indexed)
- Optional ticker/metric_name filters are fast with ILIKE
- Use `idx_metrics_outputs_ticker_fy` for ticker/year queries

---

## Testing Your Endpoint

### Unit Test Example

```python
import pytest
from uuid import uuid4
from app.services.your_endpoint_service import YourEndpointService
from app.models.your_endpoint_model import YourEndpointResponse

@pytest.mark.asyncio
async def test_your_endpoint_query(db_session):
    """Test querying metrics"""
    dataset_id = uuid4()
    param_set_id = uuid4()
    
    # Create service
    service = YourEndpointService(db_session)
    
    # Query metrics
    response = await service.query_metrics(
        dataset_id=dataset_id,
        param_set_id=param_set_id,
    )
    
    # Assertions
    assert isinstance(response, YourEndpointResponse)
    assert response.status == "success"
    assert response.results_count >= 0
```

### Integration Test Example

```python
@pytest.mark.asyncio
async def test_endpoint_http(client):
    """Test HTTP endpoint"""
    response = client.get(
        "/api/v1/metrics/your_endpoint",
        params={
            "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
            "param_set_id": "660e8400-e29b-41d4-a716-446655440001",
            "ticker": "AAPL",
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "results" in data
```

---

## File Checklist

- [ ] Create `backend/app/models/your_endpoint_model.py`
- [ ] Create `backend/app/repositories/your_endpoint_repository.py`
- [ ] Create `backend/app/services/your_endpoint_service.py`
- [ ] Create `backend/app/api/v1/endpoints/your_endpoint.py`
- [ ] Update `backend/app/api/v1/router.py` to include router
- [ ] Create tests in `backend/tests/`
- [ ] Update OpenAPI documentation if needed
- [ ] Test endpoint manually with curl or Postman

---

## Common Issues & Solutions

### Issue: Query returns no results

**Solution:** Check that:
1. `dataset_id` and `param_set_id` are valid (exist in respective tables)
2. Metrics actually exist for that dataset/param_set
3. Filter parameters are typed correctly (use ILIKE for case-insensitive matching)

### Issue: Slow queries

**Solution:**
1. Always filter by `dataset_id` and `param_set_id` first
2. Use composite indexes efficiently
3. Avoid SELECT * (specify only needed columns)
4. Consider pagination if result sets are large

### Issue: Cache not working

**Solution:**
1. Check that filtered queries are not being cached
2. Verify cache key is consistent
3. Monitor cache TTL expiration
4. Consider using `@classmethod clear_cache()` after data imports

---

## References

- **Database Schema:** `/home/ubuntu/cissa/backend/database/schema/schema.sql` (lines 313-348)
- **ORM Model:** `/home/ubuntu/cissa/backend/app/models/metrics_output.py`
- **Statistics Service Template:** `/home/ubuntu/cissa/backend/app/services/statistics_service.py`
- **Statistics Endpoint Template:** `/home/ubuntu/cissa/backend/app/api/v1/endpoints/statistics.py`
- **Metrics Repository Reference:** `/home/ubuntu/cissa/backend/app/repositories/metrics_repository.py`

