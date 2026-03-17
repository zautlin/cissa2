# CISSA Codebase Exploration Report

## Overview
This report documents the structure and patterns used in the CISSA financial metrics platform, focusing on the `metrics_outputs` table, parameter management, and existing repository patterns.

---

## 1. Database Schema: `metrics_outputs` Table

### Location
- **Schema File:** `/home/ubuntu/cissa/backend/database/schema/schema.sql` (lines 314-348)
- **ORM Model:** `/home/ubuntu/cissa/backend/app/models/metrics_output.py`

### Table Structure
```sql
CREATE TABLE metrics_outputs (
  metrics_output_id BIGINT PRIMARY KEY (auto-incrementing),
  dataset_id UUID NOT NULL REFERENCES dataset_versions(dataset_id) ON DELETE CASCADE,
  param_set_id UUID NULLABLE REFERENCES parameter_sets(param_set_id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  fiscal_year INTEGER NOT NULL,
  output_metric_name TEXT NOT NULL,
  output_metric_value NUMERIC NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  UNIQUE (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
);
```

### Column Details

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `metrics_output_id` | BIGINT | NO | Primary key, auto-incrementing |
| `dataset_id` | UUID | NO | Foreign key to `dataset_versions`. Every metric must belong to a dataset. |
| `param_set_id` | UUID | **YES** | Foreign key to `parameter_sets`. NULL for pre-computed metrics. Allows same metric to exist with different parameter sets. |
| `ticker` | TEXT | NO | Stock ticker symbol (e.g., "AAPL", "BHP") |
| `fiscal_year` | INTEGER | NO | Fiscal year of the metric |
| `output_metric_name` | TEXT | NO | Name of the calculated metric (e.g., "Calc MC", "Calc Beta", "Rf_1Y") |
| `output_metric_value` | NUMERIC | NO | The calculated metric value |
| `metadata` | JSONB | NO | Flexible storage for metric-specific attributes and calculation metadata |
| `created_at` | TIMESTAMPTZ | NO | Timestamp when record was created |

### Unique Constraint
**Composite unique index:** `(dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)`

- Ensures **one row per metric** per parameter set per fiscal year per ticker
- Allows the **same metric to exist multiple times** if:
  - Different `dataset_id` (different data ingestion)
  - Different `param_set_id` (different parameter set)
- **Special case:** Pre-computed metrics have `param_set_id = NULL`

### Indexes
```sql
-- Uniqueness: one row per (dataset, params, ticker, fiscal_year, metric)
CREATE UNIQUE INDEX idx_metrics_outputs_unique 
ON metrics_outputs (dataset_id, COALESCE(param_set_id, '00000000-0000-0000-0000-000000000000'::UUID), 
                    ticker, fiscal_year, output_metric_name);

-- Pre-computed metrics (param_set_id IS NULL)
CREATE INDEX idx_metrics_outputs_precomputed 
ON metrics_outputs (dataset_id, ticker, fiscal_year, output_metric_name) 
WHERE param_set_id IS NULL;

-- Access patterns
CREATE INDEX idx_metrics_outputs_dataset ON metrics_outputs (dataset_id);
CREATE INDEX idx_metrics_outputs_param_set ON metrics_outputs (param_set_id);
CREATE INDEX idx_metrics_outputs_ticker_fy ON metrics_outputs (ticker, fiscal_year);
```

---

## 2. ORM Model: `MetricsOutput`

### Location
`/home/ubuntu/cissa/backend/app/models/metrics_output.py`

### Model Definition
```python
class MetricsOutput(Base):
    """
    ORM model for metrics_outputs table.
    Represents calculated metrics derived from fundamentals + parameter sets.
    One row per (dataset, param_set, ticker, fiscal_year, metric).
    """
    __tablename__ = "metrics_outputs"
    __table_args__ = (
        Index("idx_metrics_outputs_unique", "dataset_id", "param_set_id", "ticker", 
              "fiscal_year", "output_metric_name", unique=True),
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

### Key Characteristics
- Uses SQLAlchemy 2.0 declarative mapping style
- `param_set_id` is **optional** (nullable) to support pre-computed metrics
- `metadata` column allows flexible storage of calculation-specific data
- Automatic timestamps via `server_default=func.now()`
- Uses `ondelete="CASCADE"` for referential integrity

---

## 3. Repository Pattern: `MetricsRepository`

### Location
`/home/ubuntu/cissa/backend/app/repositories/metrics_repository.py`

### Key Methods

#### `get_l1_metrics(dataset_id, param_set_id) -> pd.DataFrame`
Fetches L1 metrics for a dataset and parameter set combination.
```python
query = select(MetricsOutput).where(
    MetricsOutput.dataset_id == dataset_id,
    MetricsOutput.param_set_id == param_set_id,
)
```

#### `create_metric_output(...) -> MetricsOutput`
Creates a single metric output record.
```python
metric_output = MetricsOutput(
    dataset_id=dataset_id,
    param_set_id=param_set_id,
    ticker=ticker,
    fiscal_year=fiscal_year,
    output_metric_name=metric_name,
    output_metric_value=metric_value,
    metadata=metadata or {},
)
self._session.add(metric_output)
```

#### `create_metric_outputs_batch(records) -> int`
Batch insert multiple metric output records.
- Converts list of dicts to `MetricsOutput` instances
- Uses `session.add_all()` for efficiency
- Returns count of inserted records

#### `get_by_id(metrics_output_id) -> MetricsOutput | None`
Get a single metric output by primary key.

#### `list_by_dataset_and_param_set(dataset_id, param_set_id, metric_name=None, offset=0, limit=100)`
List metric outputs with optional filtering by metric name and pagination.

### Pattern Notes
- Uses async/await for all database operations
- Uses SQLAlchemy ORM for type safety
- Provides both single and batch operations
- Returns instances for ORM operations, DataFrames for analysis

---

## 4. Query Repository: `MetricsQueryRepository`

### Location
`/home/ubuntu/cissa/backend/app/repositories/metrics_query_repository.py`

### Purpose
Provides flexible querying of metrics_outputs with filtering and unit information joining.

### Key Method: `get_metrics(...)`
```python
async def get_metrics(
    self,
    dataset_id: UUID,
    parameter_set_id: UUID,
    ticker: str | None = None,
    metric_name: str | None = None,
) -> list[dict]:
```

**Returns:**
```python
[
    {
        "dataset_id": UUID,
        "parameter_set_id": UUID,
        "ticker": str,
        "fiscal_year": int,
        "metric_name": str,
        "value": float,
        "unit": Optional[str]  # From metric_units join
    },
    ...
]
```

**Query Pattern:**
- Builds dynamic WHERE clauses based on provided filters
- LEFT JOINs with `metric_units` table for unit information
- Case-insensitive matching via `LOWER()` function
- Orders by ticker → fiscal_year → metric_name
- Uses raw SQL with text() for flexibility

---

## 5. Parameter Management

### Location
- **Endpoint:** `/home/ubuntu/cissa/backend/app/api/v1/endpoints/parameters.py`
- **Service:** `/home/ubuntu/cissa/backend/app/services/parameter_service.py`
- **Repository:** `/home/ubuntu/cissa/backend/app/repositories/parameter_repository.py`
- **Schema (request/response models):** `/home/ubuntu/cissa/backend/app/models/schemas.py`

### Parameter Set Structure
```python
class ParameterSetResponse(BaseModel):
    param_set_id: UUID
    param_set_name: Optional[str]
    is_active: bool                  # Only one can be active
    is_default: bool                 # Only one can be default
    created_at: datetime
    updated_at: datetime
    parameters: dict[str, Any]       # Merged: baseline + overrides
    status: str
    message: Optional[str]
```

### Parameter Merging Logic
1. **Baseline parameters** stored in `cissa.parameters` table (13 total)
2. **Overrides** stored in `parameter_sets.param_overrides` (JSONB)
3. **Merged result** = baseline + overrides (overrides take precedence)

### Endpoint Patterns

#### GET `/api/v1/parameters/active`
- Returns the currently active parameter set
- Used by UI on page load to get user's current working parameters

#### GET `/api/v1/parameters/{param_set_id}`
- Retrieves a specific parameter set by UUID
- Returns merged parameters

#### POST `/api/v1/parameters/{param_set_id}/update`
- **Creates a NEW parameter set** with updated values
- Does NOT modify existing sets
- Request includes:
  - `parameters` (dict): Updates to apply
  - `set_as_active` (bool): Make new set active
  - `set_as_default` (bool): Make new set default

#### POST `/api/v1/parameters/{param_set_id}/set-active`
- Activates a parameter set without creating a new one
- Deactivates all others

#### POST `/api/v1/parameters/{param_set_id}/set-default`
- Sets parameter set as default
- Unsets previous default

---

## 6. Parameter Repository Methods

### Location
`/home/ubuntu/cissa/backend/app/repositories/parameter_repository.py`

### Key Methods

#### `get_baseline_parameters() -> dict[str, Any]`
Fetches all 13 baseline parameters from `cissa.parameters` table.
```python
SELECT parameter_name, default_value, value_type FROM cissa.parameters
```

#### `get_parameter_set_by_id(param_set_id: UUID) -> dict | None`
Fetches a parameter set with all its properties.
```python
SELECT param_set_id, param_set_name, is_active, is_default, 
       param_overrides, created_at, updated_at
FROM cissa.parameter_sets
WHERE param_set_id = :param_set_id
```

#### `get_active_parameter_set() -> dict | None`
Fetches the currently active parameter set.

#### `get_default_parameter_set() -> dict | None`
Fetches the default parameter set.

#### `create_parameter_set(...) -> UUID`
Creates a new parameter set and returns its ID.

#### `set_active_parameter_set(param_set_id: UUID)`
- Deactivates all other parameter sets
- Activates the specified one

#### `set_default_parameter_set(param_set_id: UUID)`
- Unsets all defaults
- Sets the specified one as default

#### `update_parameter_set_overrides(param_set_id, updated_overrides)`
Updates the JSONB overrides for an existing set.

---

## 7. Current Parameter Endpoints

### File
`/home/ubuntu/cissa/backend/app/api/v1/endpoints/parameters.py`

### Endpoints Summary

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/parameters/active` | Get currently active parameter set |
| GET | `/api/v1/parameters/{param_set_id}` | Get specific parameter set |
| POST | `/api/v1/parameters/{param_set_id}/update` | Update parameters (creates new set) |
| POST | `/api/v1/parameters/{param_set_id}/set-active` | Activate a parameter set |
| POST | `/api/v1/parameters/{param_set_id}/set-default` | Set as default |

### Error Handling Patterns
- Uses FastAPI `HTTPException` with appropriate status codes
- 404 for "not found" errors
- 422 for validation errors
- 500 for internal errors
- Logs errors via `get_logger()`

---

## 8. Metrics Service Architecture

### Location
`/home/ubuntu/cissa/backend/app/services/metrics_service.py`

### Key Pattern: Metric Function Mapping
```python
METRIC_FUNCTIONS = {
    "Calc MC": ("fn_calc_market_cap", "calc_mc", False),
    "Calc ECF": ("fn_calc_ecf", "ecf", False),
    "Calc FY TSR": ("fn_calc_fy_tsr", "fy_tsr", True),  # Requires param_set_id
    # ... more metrics
}
```

Format: `"Display Name" → (function_name, output_column_name, requires_param_set_id)`

### Calculation Flow
1. Validate metric name exists in `METRIC_FUNCTIONS`
2. Resolve `param_set_id` (use default if not provided for parameter-sensitive metrics)
3. Call SQL function: `SELECT * FROM cissa.fn_metric_name(:dataset_id, :param_set_id)`
4. Insert results into `metrics_outputs` using ON CONFLICT UPSERT pattern
5. Return response

### Query Pattern for Metrics
```python
query_sql = f"""
SELECT ticker, fiscal_year, output_metric_value
FROM cissa.{function_name}(:dataset_id, :param_set_id)
"""
result = await self._session.execute(text(query_sql), params)
rows = result.fetchall()
```

---

## 9. Existing Data Existence Checking Patterns

### Pattern 1: Direct Query with Fetchone
```python
query = text("SELECT param_set_id FROM cissa.parameter_sets WHERE is_default = true LIMIT 1")
result = await self._session.execute(query)
row = result.fetchone()
if not row:
    raise ValueError("No active parameter set found")
```

### Pattern 2: ORM Select with Count
```python
query = select(MetricsOutput).where(
    MetricsOutput.dataset_id == dataset_id,
    MetricsOutput.param_set_id == param_set_id,
)
result = await self._session.execute(query)
rows = result.fetchall()
if not rows:
    return {"status": "error", "message": "No metrics found"}
```

### Pattern 3: Check Before Proceeding
Used in L2MetricsService:
```python
l1_metrics_df = await self._fetch_l1_metrics_raw(dataset_id, param_set_id)
if l1_metrics_df.empty:
    return {
        "status": "error",
        "message": "No L1 metrics found - L2 requires L1 to be calculated first"
    }
```

---

## 10. Service Layer Pattern

### Typical Structure
```python
class CalculationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = RepositoryClass(session)
        self.logger = get_logger(__name__)
    
    async def calculate_something(self, dataset_id: UUID, param_set_id: UUID):
        try:
            # 1. Validate inputs
            # 2. Fetch data via repository
            if not data:
                logger.warning("No data found")
                return {"status": "error", "message": "..."}
            
            # 3. Calculate/process
            results = await self._calculate_pure(data)
            
            # 4. Insert results
            inserted = await self.repository.insert_results(results)
            
            # 5. Return response
            return {"status": "success", "results_count": inserted}
        
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}
```

### Key Characteristics
- Always uses `try/except` for error handling
- Logs at key steps (debug/info for flow, warning/error for issues)
- Returns structured dict responses that can be converted to Pydantic models
- Separates concerns: data access (repo), calculation, persistence

---

## 11. Metrics Endpoints

### Location
`/home/ubuntu/cissa/backend/app/api/v1/endpoints/metrics.py`

### Key Endpoints

#### POST `/api/v1/metrics/calculate`
- Calculates a metric for a dataset
- Request: `{dataset_id, metric_name, param_set_id?}`
- Calls `MetricsService.calculate_metric()`
- Returns `CalculateMetricsResponse`

#### GET `/api/v1/metrics/get_metrics/`
- Queries metrics_outputs with filtering
- Parameters: `dataset_id, parameter_set_id, ticker?, metric_name?`
- Uses `MetricsQueryRepository.get_metrics()`
- Returns `GetMetricsResponse` with unit information

#### POST `/api/v1/metrics/calculate-l2`
- Calculates L2 metrics
- Requires: L1 metrics already calculated
- Uses `L2MetricsService.calculate_l2_metrics()`

---

## 12. Response Models (Schemas)

### Location
`/home/ubuntu/cissa/backend/app/models/schemas.py`

### Metric Record Response
```python
class MetricRecord(BaseModel):
    dataset_id: UUID
    parameter_set_id: UUID
    ticker: str
    fiscal_year: int
    metric_name: str
    value: float
    unit: Optional[str]  # From metric_units join

class GetMetricsResponse(BaseModel):
    dataset_id: UUID
    parameter_set_id: UUID
    results_count: int
    results: list[MetricRecord]
    filters_applied: dict
    status: str
    message: Optional[str]
```

### Calculation Response
```python
class CalculateMetricsResponse(BaseModel):
    dataset_id: UUID
    metric_name: str
    results_count: int
    results: list[MetricResultItem]
    status: str
    message: Optional[str]
```

---

## 13. Key Database Relationships

### Foreign Keys in metrics_outputs
1. **dataset_id** → `dataset_versions.dataset_id`
   - Cascade delete: if dataset is deleted, all its metrics are deleted
   - Ensures all metrics belong to a valid dataset

2. **param_set_id** → `parameter_sets.param_set_id`
   - Nullable: allows pre-computed metrics without parameter set
   - Cascade delete: if parameter set is deleted, associated metrics are deleted

### Related Tables
- **metric_units**: Maps metric names to their units (LEFT JOIN)
- **dataset_versions**: Master record for each data ingestion
- **parameter_sets**: Named bundles of parameter configurations

---

## 14. Summary: Key Takeaways for Development

### For Checking Metrics Existence
1. **Query pattern:**
   ```python
   query = text("""
       SELECT COUNT(*) FROM cissa.metrics_outputs
       WHERE dataset_id = :dataset_id 
       AND param_set_id = :param_set_id
   """)
   ```

2. **Filter by metric name:** Add `AND output_metric_name = :metric_name`

3. **Return structure:** Use `fetchone()[0]` to get count or `fetchall()` to get records

### For Creating Metrics
1. Use `MetricsRepository.create_metric_outputs_batch()` for bulk inserts
2. Respect unique constraint: `(dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)`
3. Use ON CONFLICT UPSERT pattern for idempotent inserts

### For Querying Metrics
1. Always provide both `dataset_id` and `param_set_id`
2. Use `MetricsQueryRepository.get_metrics()` for flexible filtering
3. Join with `metric_units` for unit information

### For Parameter Management
1. Merged parameters = baseline + overrides
2. Creating new parameter set doesn't modify existing ones
3. Only one parameter set can be active at a time
4. Default and active are independent flags

### For Service Pattern
1. Services use repositories for data access
2. Always validate inputs before processing
3. Return structured responses with status and message
4. Log at DEBUG/INFO for flow, WARNING/ERROR for issues
5. Use try/except for all async operations

---

## 15. File Structure Summary

```
backend/
├── app/
│   ├── api/v1/
│   │   └── endpoints/
│   │       ├── parameters.py          (5 endpoints)
│   │       ├── metrics.py             (10+ endpoints)
│   │       └── ...
│   ├── models/
│   │   ├── metrics_output.py          (ORM model)
│   │   ├── schemas.py                 (Request/response models)
│   │   └── ...
│   ├── repositories/
│   │   ├── metrics_repository.py      (CRUD for metrics_outputs)
│   │   ├── metrics_query_repository.py (Query with filtering)
│   │   ├── parameter_repository.py    (Parameter set access)
│   │   └── ...
│   └── services/
│       ├── metrics_service.py         (Metric calculation logic)
│       ├── parameter_service.py       (Parameter management)
│       ├── l2_metrics_service.py      (L2 calculation)
│       └── ...
└── database/
    └── schema/
        ├── schema.sql                 (Table definitions)
        └── ...
```

---

## Appendix: SQL Queries for Common Operations

### Check Metrics Existence
```sql
SELECT COUNT(*) FROM cissa.metrics_outputs
WHERE dataset_id = '...' AND param_set_id = '...'
AND output_metric_name = 'Calc MC';
```

### Get All Metrics for Dataset + Parameter Set
```sql
SELECT DISTINCT output_metric_name
FROM cissa.metrics_outputs
WHERE dataset_id = '...' AND param_set_id = '...'
ORDER BY output_metric_name;
```

### Check Pre-Computed Metrics
```sql
SELECT * FROM cissa.metrics_outputs
WHERE dataset_id = '...' AND param_set_id IS NULL;
```

### Count Metrics by Status
```sql
SELECT COUNT(*) as total_metrics,
       COUNT(DISTINCT ticker) as unique_tickers,
       COUNT(DISTINCT output_metric_name) as unique_metrics
FROM cissa.metrics_outputs
WHERE dataset_id = '...' AND param_set_id = '...';
```

