# Codebase Exploration Summary

**Date:** March 17, 2026  
**Project:** CISSA Financial Data Pipeline  
**Scope:** Understanding metrics_outputs table and endpoint architecture

---

## Key Findings

### 1. METRICS_OUTPUTS Table (Database Layer)

**Location:** `/home/ubuntu/cissa/backend/database/schema/schema.sql` (lines 313-348)

**Structure:**
- **Primary Key:** `metrics_output_id` (BIGINT, auto-increment)
- **Foreign Keys:** 
  - `dataset_id` → dataset_versions (NOT NULL, CASCADE delete)
  - `param_set_id` → parameter_sets (NULLABLE, CASCADE delete)
- **Data Columns:**
  - `ticker` (TEXT) - Company ticker
  - `fiscal_year` (INTEGER) - Fiscal year
  - `output_metric_name` (TEXT) - Metric name (e.g., 'Beta', 'Calc MC')
  - `output_metric_value` (NUMERIC) - Metric value
  - `metadata` (JSONB) - Flexible JSON for metric attributes
  - `created_at` (TIMESTAMPTZ) - Record creation time

**Unique Constraint:** `(dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)`
- Enables idempotent inserts via `ON CONFLICT`
- One row per (dataset, params, ticker, fiscal_year, metric) combination
- Supports NULL param_set_id for pre-computed metrics

**Indexes (5 total):**
1. Unique index with COALESCE for NULL handling
2. Filtered index for pre-computed metrics (param_set_id IS NULL)
3. Single-column indexes on: dataset_id, param_set_id, ticker_fy

---

### 2. Statistics Endpoint (Architecture Template)

**Files:**
- Route: `/home/ubuntu/cissa/backend/app/api/v1/endpoints/statistics.py` (120 lines)
- Service: `/home/ubuntu/cissa/backend/app/services/statistics_service.py` (156 lines)
- Repository: `/home/ubuntu/cissa/backend/app/repositories/statistics_repository.py` (160 lines)
- Models: `/home/ubuntu/cissa/backend/app/models/statistics.py` (43 lines)

**Pattern:**
```
GET /api/v1/metrics/statistics?dataset_id=<uuid>

Route Handler
    ↓ (async)
Service (with caching + business logic)
    ↓ (async)
Repository (data access)
    ↓ (raw SQL or ORM)
Database
```

**Key Features:**
- Optional query parameter → different response types
- 1-hour TTL caching with expiration checks
- Parallel execution using `asyncio.gather()`
- Graceful degradation (NULL values on errors)
- Comprehensive logging and error handling

---

### 3. Existing Repository Methods (metrics_outputs)

**File:** `/home/ubuntu/cissa/backend/app/repositories/metrics_repository.py` (175 lines)

**Available Methods:**

1. `get_l1_metrics(dataset_id, param_set_id)` → DataFrame
   - Queries L1 metrics, returns Pandas DataFrame
   - Columns: ticker, fiscal_year, output_metric_name, output_metric_value

2. `create_metric_output(...)` → MetricsOutput
   - Single record creation
   - Returns ORM model instance

3. `create_metric_outputs_batch(records)` → int
   - Batch insert (efficient for bulk operations)
   - Returns count of inserted records

4. `get_by_id(metrics_output_id)` → MetricsOutput | None
   - Query by primary key

5. `list_by_dataset_and_param_set(...)` → list[MetricsOutput]
   - Query with optional filtering and pagination
   - Supports metric_name filter, offset/limit

---

### 4. ORM Model (metrics_output.py)

**Location:** `/home/ubuntu/cissa/backend/app/models/metrics_output.py` (68 lines)

```python
class MetricsOutput(Base):
    __tablename__ = "metrics_outputs"
    __table_args__ = (
        Index(..., unique=True),  # Uniqueness constraint
        Index(..., dataset_id),   # Access pattern
        Index(..., param_set_id), # Access pattern
        Index(..., ticker, fiscal_year), # Access pattern
        {"schema": "cissa"},
    )
    
    metrics_output_id: int (PK)
    dataset_id: UUID (FK, NOT NULL)
    param_set_id: UUID | None (FK, NULLABLE)
    ticker: str
    fiscal_year: int
    output_metric_name: str
    output_metric_value: float
    metric_metadata: dict (mapped to "metadata" column)
    created_at: datetime
```

---

### 5. Service/Repository Architecture

**Pattern (3-layer design):**

```
Layer 1: Route Handler (endpoints/*.py)
├── Handles HTTP requests/responses
├── Parameter validation
├── Dependency injection (AsyncSession)
└── Error handling

Layer 2: Service (services/*.py)
├── Business logic
├── Caching (TTL-based)
├── Orchestration of repository calls
└── Response model building

Layer 3: Repository (repositories/*.py)
├── Database queries (raw SQL or ORM)
├── Parameter binding
├── Result mapping
└── No business logic
```

---

### 6. Database Schema Organization (12 Tables)

**Phase 1: Reference Tables**
- companies, fiscal_year_mapping, metric_units

**Phase 2: Versioning**
- dataset_versions

**Phase 3: Raw Data**
- raw_data (immutable staging)

**Phase 4: Cleaned Data**
- fundamentals (fact table, cleaned/aligned/imputed)
- imputation_audit_trail

**Phase 5: Configuration**
- parameters (baseline params: 13 total)
- parameter_sets (named configs, 1 default "base_case")

**Phase 6: Outputs**
- **metrics_outputs** (computed metrics from fundamentals + parameters)
- optimization_outputs (optimization algorithm results)

---

### 7. Connection Management

**File:** `/home/ubuntu/cissa/backend/app/core/database.py` (79 lines)

**AsyncPG Configuration:**
- Pool size: 10
- Max overflow: 20
- Connection timeout: 10s
- Command timeout: 60s
- Pre-ping enabled for connection health

**Dependency Injection Pattern:**
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    db_manager = get_db_manager()
    async for session in db_manager.get_session():
        yield session

# Usage
@router.get("/endpoint")
async def handler(db: AsyncSession = Depends(get_db)):
    ...
```

---

## Quick Reference: Creating a New Endpoint

### Minimal Example (5 files)

**1. Models** (`backend/app/models/your_model.py`)
```python
class YourResponse(BaseModel):
    dataset_id: UUID
    results: List[dict]
    status: str
```

**2. Repository** (`backend/app/repositories/your_repo.py`)
```python
class YourRepository:
    async def query_data(self, dataset_id: UUID) -> List[dict]:
        result = await self.db.execute(text("SELECT ..."))
        return [dict(row._mapping) for row in result.fetchall()]
```

**3. Service** (`backend/app/services/your_service.py`)
```python
class YourService:
    async def get_data(self, dataset_id: UUID) -> YourResponse:
        repo = YourRepository(self.db)
        data = await repo.query_data(dataset_id)
        return YourResponse(dataset_id=dataset_id, results=data, status="success")
```

**4. Endpoint** (`backend/app/api/v1/endpoints/your_endpoint.py`)
```python
@router.get("/your-endpoint")
async def your_endpoint(
    dataset_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    service = YourService(db)
    return await service.get_data(dataset_id)
```

**5. Router** (Update `backend/app/api/v1/router.py`)
```python
from .endpoints import your_endpoint
router.include_router(your_endpoint.router)
```

---

## Performance Considerations

### Indexes for metrics_outputs

```sql
-- Uniqueness with NULL handling
UNIQUE (dataset_id, COALESCE(param_set_id, '00000000...'), ticker, fiscal_year, output_metric_name)

-- Pre-computed metrics fast path
WHERE param_set_id IS NULL

-- Single-column access patterns
dataset_id, param_set_id, (ticker, fiscal_year)
```

### Query Optimization Tips

1. **Always filter by dataset_id first** - Primary partitioning key
2. **Then filter by param_set_id** - Heavily indexed
3. **Optional filters (ticker, metric_name)** - ILIKE is fast on TEXT
4. **Avoid SELECT *** - Specify only needed columns
5. **Consider pagination** - For large result sets

---

## Key Statistics (Codebase)

| Metric | Count |
|--------|-------|
| Database Tables | 11 |
| Indexes on metrics_outputs | 5 |
| Repository Files | 14 |
| Service Files | 17 |
| API Endpoints | 996 lines (metrics.py) |
| Statistics Endpoint | 120 lines (focused) |
| Baseline Parameters | 13 |
| Cache TTL | 1 hour |

---

## Files to Reference

| Purpose | File | Lines |
|---------|------|-------|
| Table definition | schema.sql | 313-348 |
| ORM model | metrics_output.py | 68 |
| Endpoint template | statistics.py | 120 |
| Service template | statistics_service.py | 156 |
| Repository template | statistics_repository.py | 160 |
| Response models | statistics.py | 43 |
| Query examples | metrics_repository.py | 175 |
| DB connection | database.py | 79 |

---

## Generated Documentation

Two detailed guides have been created:

1. **CODEBASE_EXPLORATION_DETAILED.md** (24KB)
   - Comprehensive analysis of all 12 sections
   - Complete database architecture
   - Service/repository patterns
   - Query examples and best practices
   - Configuration details

2. **METRICS_OUTPUTS_ENDPOINT_TEMPLATE.md**
   - Step-by-step endpoint creation guide
   - Pydantic model template
   - Repository query patterns (7 examples)
   - Service caching implementation
   - Testing examples
   - Common issues and solutions

---

## Next Steps

For implementing a new metrics_outputs query endpoint:

1. **Review the template guide** (METRICS_OUTPUTS_ENDPOINT_TEMPLATE.md)
2. **Follow the 5-step pattern** (Models → Repository → Service → Endpoint → Router)
3. **Use statistics endpoint as reference** for async patterns and caching
4. **Test with Pydantic validators** for input validation
5. **Leverage existing indexes** for performance
6. **Add comprehensive logging** for debugging

---

## Conclusion

The CISSA codebase demonstrates a well-architected financial data pipeline with:
- Clean layered architecture (Route → Service → Repository → ORM)
- Type-safe Pydantic models and SQLAlchemy ORM
- Comprehensive async/await patterns
- Efficient database design with appropriate indexes
- Graceful error handling and logging
- Caching strategies for performance

The statistics endpoint serves as an excellent template for new metrics_outputs endpoints, and the existing repository methods provide a solid foundation for database queries.

---

**Exploration completed:** 2026-03-17 04:30 UTC
