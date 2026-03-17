# Codebase Exploration Report: CISSA Financial Data Pipeline

## Executive Summary

This report documents the structure of the CISSA financial data pipeline codebase, specifically focusing on:
1. The `metrics_outputs` table structure and columns
2. The statistics endpoint as a template for new endpoints
3. Existing repository methods for querying metrics_outputs
4. Database schema architecture
5. Services and repositories organization

---

## 1. METRICS_OUTPUTS TABLE STRUCTURE

### Database Schema Definition

**Location:** `/home/ubuntu/cissa/backend/database/schema/schema.sql` (lines 313-348)

```sql
CREATE TABLE metrics_outputs (
  metrics_output_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  dataset_id UUID NOT NULL REFERENCES dataset_versions(dataset_id) ON DELETE CASCADE,
  param_set_id UUID REFERENCES parameter_sets(param_set_id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  fiscal_year INTEGER NOT NULL,
  output_metric_name TEXT NOT NULL,
  output_metric_value NUMERIC NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
);
```

### Column Definitions

| Column Name | Data Type | Constraints | Description |
|-------------|-----------|-------------|-------------|
| `metrics_output_id` | BIGINT | PRIMARY KEY (auto-increment) | Unique row identifier |
| `dataset_id` | UUID | NOT NULL, FK to dataset_versions | Links to source dataset |
| `param_set_id` | UUID | NULLABLE, FK to parameter_sets | Parameter set used for calculation |
| `ticker` | TEXT | NOT NULL | Company ticker symbol (e.g., 'AAPL') |
| `fiscal_year` | INTEGER | NOT NULL | Fiscal year of the metric |
| `output_metric_name` | TEXT | NOT NULL | Name of calculated metric (e.g., 'Beta', 'Calc MC') |
| `output_metric_value` | NUMERIC | NOT NULL | The calculated metric value |
| `metadata` | JSONB | NOT NULL, DEFAULT={} | Flexible JSON storage for metric-specific attributes |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT=now() | Timestamp of record creation |

### Key Constraints

#### Uniqueness
- **Composite Unique Index:** `(dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)`
- Ensures one row per (dataset, params, ticker, fiscal_year, metric) combination
- Allows upserts via `ON CONFLICT` clauses
- Essential for idempotent inserts by metrics calculation service

#### Foreign Keys
- `dataset_id` → `dataset_versions(dataset_id)` with `ON DELETE CASCADE`
- `param_set_id` → `parameter_sets(param_set_id)` with `ON DELETE CASCADE` (nullable)

#### Special Handling
- When `param_set_id IS NULL`: indicates pre-computed metrics (e.g., Beta computed during ETL)
- COALESCE-based unique index: `ON metrics_outputs (dataset_id, COALESCE(param_set_id, '00000000-0000-0000-0000-000000000000'::UUID), ticker, fiscal_year, output_metric_name)`
  - Treats NULL as default UUID for uniqueness enforcement

### Indexes

```sql
-- Uniqueness
CREATE UNIQUE INDEX idx_metrics_outputs_unique 
ON metrics_outputs (dataset_id, COALESCE(param_set_id, '00000000-0000-0000-0000-000000000000'::UUID), ticker, fiscal_year, output_metric_name);

-- Pre-computed metrics (param_set_id IS NULL)
CREATE INDEX idx_metrics_outputs_precomputed 
ON metrics_outputs (dataset_id, ticker, fiscal_year, output_metric_name) 
WHERE param_set_id IS NULL;

-- Access patterns
CREATE INDEX idx_metrics_outputs_dataset ON metrics_outputs (dataset_id);
CREATE INDEX idx_metrics_outputs_param_set ON metrics_outputs (param_set_id);
CREATE INDEX idx_metrics_outputs_ticker_fy ON metrics_outputs (ticker, fiscal_year);
```

### ORM Model

**Location:** `/home/ubuntu/cissa/backend/app/models/metrics_output.py`

```python
class MetricsOutput(Base):
    """ORM model for metrics_outputs table"""
    __tablename__ = "metrics_outputs"
    __table_args__ = (
        Index("idx_metrics_outputs_unique", "dataset_id", "param_set_id", 
              "ticker", "fiscal_year", "output_metric_name", unique=True),
        Index("idx_metrics_outputs_dataset", "dataset_id"),
        Index("idx_metrics_outputs_param_set", "param_set_id"),
        Index("idx_metrics_outputs_ticker_fy", "ticker", "fiscal_year"),
        {"schema": "cissa"},
    )

    metrics_output_id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("cissa.dataset_versions.dataset_id", ondelete="CASCADE"),
        nullable=False,
    )
    param_set_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cissa.parameter_sets.param_set_id", ondelete="CASCADE"),
        nullable=True,
    )
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    output_metric_name: Mapped[str] = mapped_column(String, nullable=False)
    output_metric_value: Mapped[float] = mapped_column(Numeric, nullable=False)
    metric_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False, name="metadata")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
```

---

## 2. STATISTICS ENDPOINT AS TEMPLATE

### Endpoint Structure

**Location:** `/home/ubuntu/cissa/backend/app/api/v1/endpoints/statistics.py`

#### Route Definition
```python
router = APIRouter(prefix="/api/v1/metrics", tags=["statistics"])

@router.get("/statistics", response_model=Union[DatasetStatistics, AllDatasetsStatistics])
async def get_dataset_statistics(
    dataset_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db)
)
```

#### Key Characteristics

1. **Optional Query Parameters**
   - `dataset_id`: Optional UUID parameter
   - When provided → returns single dataset statistics
   - When omitted → returns statistics for all datasets

2. **Dependency Injection**
   - Uses `Depends(get_db)` to inject AsyncSession
   - Clean separation between route and service logic

3. **Response Models**
   - Union types: `DatasetStatistics | AllDatasetsStatistics`
   - Pydantic models for validation and documentation

4. **Error Handling**
   - HTTPException with status codes
   - Detailed logging at each step
   - Graceful degradation (returns NULL values for missing data)

### Request/Response Pattern

#### Request
```
GET /api/v1/metrics/statistics?dataset_id=550e8400-e29b-41d4-a716-446655440000
```

#### Response (Single Dataset)
```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "dataset_created_at": "2026-03-12T10:15:30Z",
  "country": "Australia",
  "companies": {"count": 250},
  "sectors": {"count": 12},
  "data_coverage": {"min_year": 2002, "max_year": 2023},
  "raw_metrics": {"count": 15}
}
```

#### Response (All Datasets)
```json
{
  "datasets": {
    "550e8400-e29b-41d4-a716-446655440000": {
      "dataset_id": "...",
      "dataset_created_at": "...",
      ...
    },
    "550e8400-e29b-41d4-a716-446655440001": {...}
  }
}
```

### Endpoint Architecture Pattern

```
Request → Route Handler → Service → Repository → Database
                ↓
            Validation
                ↓
            Business Logic
                ↓
            Caching
                ↓
            Response Model
```

---

## 3. RESPONSE MODELS (Pydantic Schemas)

**Location:** `/home/ubuntu/cissa/backend/app/models/statistics.py`

```python
class CompaniesStats(BaseModel):
    count: Optional[int] = Field(None, description="...")

class SectorsStats(BaseModel):
    count: Optional[int] = Field(None, description="...")

class DataCoverage(BaseModel):
    min_year: Optional[int] = Field(None, description="...")
    max_year: Optional[int] = Field(None, description="...")

class RawMetricsStats(BaseModel):
    count: Optional[int] = Field(None, description="...")

class DatasetStatistics(BaseModel):
    dataset_id: str
    dataset_created_at: Optional[datetime]
    country: Optional[str]
    companies: CompaniesStats
    sectors: SectorsStats
    data_coverage: DataCoverage
    raw_metrics: RawMetricsStats

class AllDatasetsStatistics(BaseModel):
    datasets: Dict[str, DatasetStatistics]
```

### Key Principles
- **Nullable Fields:** Use `Optional[T]` for fields that may be missing
- **Field Descriptions:** All fields have descriptions for OpenAPI documentation
- **Composition:** Nest related stats in sub-models
- **Type Safety:** Leverages Pydantic for automatic validation

---

## 4. METRICS REPOSITORY METHODS

**Location:** `/home/ubuntu/cissa/backend/app/repositories/metrics_repository.py`

### Existing Methods

#### 1. `get_l1_metrics()`
```python
async def get_l1_metrics(
    self, 
    dataset_id: UUID, 
    param_set_id: UUID,
) -> pd.DataFrame
```
- Queries L1 metrics for a dataset and parameter set
- Returns DataFrame with columns: ticker, fiscal_year, output_metric_name, output_metric_value
- Used by higher-level metric calculation services

#### 2. `create_metric_output()`
```python
async def create_metric_output(
    self,
    dataset_id: UUID,
    param_set_id: UUID,
    ticker: str,
    fiscal_year: int,
    metric_name: str,
    metric_value: float,
    metadata: dict | None = None,
) -> MetricsOutput
```
- Creates a single metric output record
- Returns the created ORM model instance
- Used during metric calculation workflows

#### 3. `create_metric_outputs_batch()`
```python
async def create_metric_outputs_batch(
    self,
    records: list[dict],
) -> int
```
- Batch insert metric output records
- Accepts list of dicts with keys: dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata
- Returns count of inserted records
- Efficient for bulk operations (e.g., calculating all L1 metrics)

#### 4. `get_by_id()`
```python
async def get_by_id(self, metrics_output_id: int) -> MetricsOutput | None
```
- Retrieves a single metric output by primary key
- Returns ORM model or None

#### 5. `list_by_dataset_and_param_set()`
```python
async def list_by_dataset_and_param_set(
    self,
    dataset_id: UUID,
    param_set_id: UUID,
    metric_name: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[MetricsOutput]
```
- Lists metric outputs with filtering
- Optional metric_name filter
- Supports pagination (offset/limit)
- Returns list of ORM models

### SQL Query Patterns

All repository methods use SQLAlchemy's async API:

```python
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# Pattern 1: ORM-based queries
query = select(MetricsOutput).where(...)
result = await self._session.execute(query)

# Pattern 2: Raw SQL with text()
query = text("""SELECT ... FROM cissa.metrics_outputs WHERE ...""")
result = await self.db.execute(query, {"param": value})
```

---

## 5. STATISTICS SERVICE (Business Logic)

**Location:** `/home/ubuntu/cissa/backend/app/services/statistics_service.py`

### Service Architecture

```python
class StatisticsService:
    _cache: dict[str, CachedStatistics] = {}
    _cache_ttl_seconds = 3600  # 1 hour
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = StatisticsRepository(db)
```

#### Key Methods

1. **`async get_statistics(dataset_id: UUID) -> DatasetStatistics`**
   - Checks cache first
   - Queries repository methods in parallel (sort of)
   - Builds response model
   - Caches result

2. **`async get_all_statistics() -> AllDatasetsStatistics`**
   - Fetches all dataset IDs
   - Creates tasks for each dataset (parallel)
   - Uses `asyncio.gather()` for concurrent execution
   - Handles exceptions gracefully

3. **`_get_from_cache()` / `_set_cache()`**
   - Simple dict-based cache with TTL support
   - Checks expiration before returning

### Parallel Execution Pattern

```python
async def get_all_statistics(self) -> AllDatasetsStatistics:
    dataset_ids = await self.repo.get_all_dataset_ids()
    
    # Create tasks for all datasets (concurrent)
    tasks = [self.get_statistics(dataset_id) for dataset_id in dataset_ids]
    
    # Execute all in parallel
    stats_list = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle exceptions gracefully
    datasets_dict = {}
    for dataset_id, stats in zip(dataset_ids, stats_list):
        if isinstance(stats, Exception):
            # Include dataset with null stats on error
            datasets_dict[str(dataset_id)] = DatasetStatistics(...)
        else:
            datasets_dict[str(dataset_id)] = stats
```

---

## 6. STATISTICS REPOSITORY (Data Access)

**Location:** `/home/ubuntu/cissa/backend/app/repositories/statistics_repository.py`

### Query Methods

```python
class StatisticsRepository:
    async def get_company_count(dataset_id: UUID) -> Optional[int]
    async def get_sector_count(dataset_id: UUID) -> Optional[int]
    async def get_raw_metrics_count(dataset_id: UUID) -> Optional[int]
    async def get_data_coverage(dataset_id: UUID) -> tuple[Optional[int], Optional[int]]
    async def get_dataset_info(dataset_id: UUID) -> tuple[Optional[str], Optional[str]]
    async def get_all_dataset_ids() -> list[UUID]
```

### Query Examples

```sql
-- Company count (from fundamentals, not companies table)
SELECT COUNT(DISTINCT ticker)
FROM cissa.fundamentals
WHERE dataset_id = :dataset_id AND period_type = 'FISCAL'

-- Sector count (cross-join with companies)
SELECT COUNT(DISTINCT c.sector)
FROM cissa.companies c
WHERE c.ticker IN (
    SELECT DISTINCT ticker FROM cissa.fundamentals
    WHERE dataset_id = :dataset_id AND period_type = 'FISCAL'
)

-- Data coverage
SELECT MIN(fiscal_year), MAX(fiscal_year)
FROM cissa.fundamentals
WHERE dataset_id = :dataset_id AND period_type = 'FISCAL'

-- Dataset info
SELECT created_at FROM cissa.dataset_versions WHERE dataset_id = :dataset_id
```

---

## 7. DATABASE SCHEMA ARCHITECTURE

### 12 Tables Organized in Phases

```
Phase 1: Reference Tables (Immutable)
├── companies (master list from Base.csv)
├── fiscal_year_mapping (FY dates from FY Dates.csv)
└── metric_units (metric → unit mappings)

Phase 2: Versioning & Tracking
└── dataset_versions (audit table for each ingestion)

Phase 3: Raw Data (Staging)
└── raw_data (all rows from source CSV as-is)

Phase 4: Cleaned Data (Fact Table)
├── fundamentals (cleaned, aligned, imputed data)
└── imputation_audit_trail (audit of imputation decisions)

Phase 5: Configuration & Parameters
├── parameters (tunable parameter master list)
└── parameter_sets (named bundles of configurations)

Phase 6: Downstream Outputs
├── metrics_outputs (computed metrics from fundamentals + parameters)
└── optimization_outputs (results from optimization algorithms)
```

### Key Relationships

```
dataset_versions (1) ──→ (N) fundamentals
dataset_versions (1) ──→ (N) raw_data
dataset_versions (1) ──→ (N) metrics_outputs
dataset_versions (1) ──→ (N) optimization_outputs
dataset_versions (1) ──→ (N) imputation_audit_trail

parameter_sets (1) ──→ (N) metrics_outputs
parameter_sets (1) ──→ (N) optimization_outputs
```

### Total Schema Coverage
- 11 tables total (12 before removal of metrics_catalog, raw_data_validation_log)
- 25+ indexes
- 4 auto-update timestamp triggers
- 13 baseline parameters (initialized at schema creation)
- 1 default parameter_set ("base_case")

---

## 8. API ENDPOINT ORGANIZATION

### Router Structure

**Location:** `/home/ubuntu/cissa/backend/app/api/v1/router.py`

```python
from fastapi import APIRouter
from .endpoints import metrics, parameters, orchestration, statistics

router = APIRouter()
router.include_router(metrics.router)
router.include_router(parameters.router)
router.include_router(orchestration.router)
router.include_router(statistics.router)
```

### Endpoint Prefixes

| Module | Prefix | Tags |
|--------|--------|------|
| `metrics.py` | `/api/v1/metrics` | metrics |
| `parameters.py` | `/api/v1/parameters` | parameters |
| `orchestration.py` | `/api/v1/orchestration` | orchestration |
| `statistics.py` | `/api/v1/metrics` | statistics |

### File Structure
```
backend/app/
├── api/
│   └── v1/
│       ├── endpoints/
│       │   ├── metrics.py (996 lines - comprehensive)
│       │   ├── parameters.py
│       │   ├── orchestration.py
│       │   ├── statistics.py (120 lines - clean, focused)
│       │   └── __init__.py
│       ├── router.py
│       └── __init__.py
├── services/
│   ├── statistics_service.py (156 lines)
│   ├── metrics_service.py
│   ├── l2_metrics_service.py
│   ├── beta_calculation_service.py
│   ├── cost_of_equity_service.py
│   ├── ratio_metrics_service.py
│   ├── parameter_service.py
│   └── ... (17 service files total)
├── repositories/
│   ├── statistics_repository.py (160 lines)
│   ├── metrics_repository.py (175 lines)
│   ├── metrics_query_repository.py
│   ├── parameter_repository.py
│   ├── ratio_metrics_repository.py
│   └── ... (14 repository files total)
├── models/
│   ├── statistics.py (43 lines - Pydantic schemas)
│   ├── metrics_output.py (68 lines - SQLAlchemy ORM)
│   ├── ratio_metrics.py
│   └── schemas.py (Request/Response models)
└── core/
    ├── database.py (AsyncPG configuration)
    └── config.py (Settings, logging)
```

---

## 9. DATABASE CONNECTION & SESSION MANAGEMENT

**Location:** `/home/ubuntu/cissa/backend/app/core/database.py`

### AsyncPG Configuration

```python
class DatabaseManager:
    async def initialize(self):
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            connect_args={
                "timeout": 10,
                "command_timeout": 60,
            }
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
```

### Dependency Injection

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection for AsyncSession in route handlers"""
    db_manager = get_db_manager()
    async for session in db_manager.get_session():
        yield session

# Usage in routes
@router.get("/endpoint")
async def handler(db: AsyncSession = Depends(get_db)):
    ...
```

### Connection Pooling
- Pool size: 10
- Max overflow: 20
- Connection timeout: 10 seconds
- Command timeout: 60 seconds

---

## 10. EXAMPLE QUERY PATTERNS

### Pattern 1: Metrics Query by Dataset + Parameter Set

**Endpoint:** `GET /api/v1/metrics/get_metrics/`

```python
async def get_metrics(
    dataset_id: UUID,
    parameter_set_id: UUID,
    ticker: Optional[str] = None,
    metric_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    repo = MetricsQueryRepository(db)
    records = await repo.get_metrics(
        dataset_id=dataset_id,
        parameter_set_id=parameter_set_id,
        ticker=ticker,
        metric_name=metric_name,
    )
    return GetMetricsResponse(
        dataset_id=dataset_id,
        parameter_set_id=parameter_set_id,
        results_count=len(records),
        results=records,
        status="success"
    )
```

### Pattern 2: Batch Insert Metrics

```python
repo = MetricsRepository(db)
records = [
    {
        "dataset_id": dataset_id,
        "param_set_id": param_set_id,
        "ticker": ticker,
        "fiscal_year": 2020,
        "output_metric_name": "Beta",
        "output_metric_value": 1.25,
        "metadata": {"approach": "FIXED"},
    },
    # ... more records
]
inserted = await repo.create_metric_outputs_batch(records)
await db.commit()
```

### Pattern 3: Caching with TTL

```python
class StatisticsService:
    _cache: dict[str, CachedStatistics] = {}
    
    def _get_from_cache(self, dataset_id: UUID):
        cache_key = str(dataset_id)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if not cached.is_expired(self._cache_ttl_seconds):
                return cached.data
            else:
                del self._cache[cache_key]
        return None
    
    def _set_cache(self, dataset_id: UUID, stats: DatasetStatistics):
        self._cache[str(dataset_id)] = CachedStatistics(stats, datetime.utcnow())
```

### Pattern 4: Parallel Async Execution

```python
async def get_all_statistics(self):
    dataset_ids = await self.repo.get_all_dataset_ids()
    
    # Create all tasks
    tasks = [self.get_statistics(dataset_id) for dataset_id in dataset_ids]
    
    # Execute concurrently
    stats_list = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Merge results
    datasets_dict = {}
    for dataset_id, stats in zip(dataset_ids, stats_list):
        if isinstance(stats, Exception):
            datasets_dict[str(dataset_id)] = DatasetStatistics(...)
        else:
            datasets_dict[str(dataset_id)] = stats
    
    return AllDatasetsStatistics(datasets=datasets_dict)
```

---

## 11. KEY FINDINGS & RECOMMENDATIONS

### Strengths of Current Architecture

1. **Clean Separation of Concerns**
   - Routes → Services → Repositories → ORM Models
   - Each layer has single responsibility
   - Easy to test and maintain

2. **Type Safety**
   - Pydantic models for validation
   - SQLAlchemy ORM with type hints
   - Optional fields for nullable data

3. **Async Throughout**
   - AsyncSession for non-blocking DB access
   - asyncio.gather() for parallel execution
   - Proper error handling with try/except blocks

4. **Comprehensive Caching**
   - Statistics service caches with TTL
   - Prevents redundant database queries
   - Clear cache method for post-import refresh

5. **Graceful Degradation**
   - Endpoints return NULL values for missing data
   - Exceptions handled without failing entire response
   - Detailed logging for debugging

### Design Patterns for New Endpoints

When creating a new endpoint for metrics_outputs queries, follow this pattern:

```
1. Create Request/Response Pydantic models in models/
2. Create Repository methods using AsyncSession + text() or ORM selects
3. Create Service class with business logic and caching
4. Create endpoint handler that:
   - Takes db: AsyncSession = Depends(get_db)
   - Creates service instance: service = YourService(db)
   - Calls service method and handles exceptions
   - Returns response model with appropriate status codes
5. Register router in api/v1/router.py
```

### For metrics_outputs Queries

**Key Considerations:**
- Always include dataset_id and param_set_id in filters (foreign keys)
- Use composite indexes for efficient queries
- Consider caching if query is expensive and data doesn't change frequently
- Handle NULL param_set_id for pre-computed metrics
- Leverage the uniqueness constraint for upserts

---

## 12. CONFIGURATION & ENVIRONMENT

### Database URL Format
```
postgresql+asyncpg://user:password@host:port/database
```

### Initialization Steps
```bash
# 1. Create schema and tables
python3 backend/database/schema/schema_manager.py create

# 2. Full initialization (includes parameters)
python3 backend/database/schema/schema_manager.py init

# 3. Load data
python3 backend/database/etl/pipeline.py

# 4. Process metrics
POST /api/v1/metrics/calculate
```

---

## Summary Table: File Locations

| Component | Location | Key File(s) |
|-----------|----------|------------|
| **Database Schema** | `backend/database/schema/` | schema.sql |
| **ORM Models** | `backend/app/models/` | metrics_output.py, statistics.py |
| **API Routes** | `backend/app/api/v1/endpoints/` | metrics.py, statistics.py |
| **Services** | `backend/app/services/` | statistics_service.py, metrics_service.py |
| **Repositories** | `backend/app/repositories/` | metrics_repository.py, statistics_repository.py |
| **DB Connection** | `backend/app/core/` | database.py, config.py |
| **API Router** | `backend/app/api/v1/` | router.py |

