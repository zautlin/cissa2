# Architecture

**Analysis Date:** 2026-03-09

## Pattern Overview

**Overall:** Layered + Event-Driven Architecture (FastAPI API + Async Services + PostgreSQL-backed ETL)

**Key Characteristics:**
- **Async-first** FastAPI application with SQLAlchemy AsyncSession for non-blocking database operations
- **Three-layer stack** separating API endpoints, business logic (services), and data access (repositories)
- **ETL pipeline** orchestrates data ingestion, validation, and processing in stages
- **Metric calculation layers** (L1 basic → L2 derived → L3 enhanced) with automatic triggering via database functions
- **Configuration-driven** environment variables via Pydantic Settings with `.env` file loading

## Layers

**API Layer (Presentation):**
- Purpose: HTTP request handling, request validation, response serialization
- Location: `backend/app/api/v1/endpoints/metrics.py`
- Contains: FastAPI route handlers with request/response models
- Depends on: Services layer for business logic
- Used by: HTTP clients via FastAPI `Depends()` injection

**Service Layer (Business Logic):**
- Purpose: Orchestrate metric calculations, coordinate repositories, enforce business rules
- Location: `backend/app/services/` (metrics_service.py, l2_metrics_service.py, enhanced_metrics_service.py)
- Contains: MetricsService (L1), L2MetricsService (L2 with pandas operations), EnhancedMetricsService (L3)
- Depends on: Repository layer for data access, database connection
- Used by: API endpoints and CLI commands

**Repository Layer (Data Access):**
- Purpose: Abstract database queries, provide clean data interfaces to services
- Location: `backend/app/repositories/metrics_repository.py`
- Contains: MetricsRepository (queries metrics_outputs table, returns DataFrames for service calculations)
- Depends on: SQLAlchemy ORM models, AsyncSession
- Used by: Services to fetch and insert metric data

**Core/Infrastructure Layer:**
- Purpose: Configuration, database connection pooling, logging, dependency management
- Location: `backend/app/core/` (config.py, database.py)
- Contains: Settings (Pydantic), DatabaseManager (AsyncSession factory), async session dependency
- Depends on: Environment configuration, SQLAlchemy
- Used by: All other layers via get_settings(), get_db() dependency injection

**ETL Pipeline Layer (Data Ingestion):**
- Purpose: Extract, validate, transform, and load raw financial data
- Location: `backend/database/etl/` (ingestion.py, processing.py, pipeline.py, validators.py, imputation_engine.py, fy_aligner.py)
- Contains: Ingester, DataQualityProcessor, imputation logic, FY alignment
- Depends on: SQLAlchemy engine (sync), raw Excel/CSV files
- Used by: Pipeline orchestrator scripts

**Database Models Layer:**
- Purpose: Define ORM schema mapping to PostgreSQL tables
- Location: `backend/app/models/metrics_output.py` (ORM models)
- Contains: MetricsOutput SQLAlchemy ORM class with mapped columns, indexes, foreign keys
- Depends on: SQLAlchemy declarative base
- Used by: Services and repositories for type-safe queries

**Request/Response Models Layer:**
- Purpose: Define Pydantic schemas for request validation and response serialization
- Location: `backend/app/models/schemas.py`
- Contains: CalculateMetricsRequest, CalculateMetricsResponse, CalculateL2Request, CalculateL2Response, CalculateEnhancedMetricsRequest, CalculateEnhancedMetricsResponse
- Depends on: Pydantic v2 with ConfigDict
- Used by: API endpoints for validation and response marshalling

## Data Flow

**L1 Metrics Calculation Flow (via API POST /api/v1/metrics/calculate):**

1. HTTP POST request → `metrics.py` endpoint with CalculateMetricsRequest (dataset_id, metric_name)
2. FastAPI calls `MetricsService.calculate_metric(dataset_id, metric_name)`
3. Service validates metric_name against METRIC_FUNCTIONS dict
4. Service calls `session.execute()` with raw SQL to invoke PostgreSQL function (e.g., `cissa.fn_calc_market_cap(dataset_id)`)
5. PostgreSQL function returns (ticker, fiscal_year, value) tuples
6. Service converts results to MetricResultItem objects
7. Service calls `_insert_metric_results()` to batch-insert into metrics_outputs table (1000 rows per batch)
8. Service commits transaction and returns CalculateMetricsResponse with results array
9. FastAPI serializes response to JSON and returns HTTP 200

**L2 Metrics Calculation Flow (via API POST /api/v1/metrics/calculate-l2):**

1. HTTP POST request → `metrics.py` endpoint with CalculateL2Request (dataset_id, param_set_id)
2. FastAPI calls `L2MetricsService.calculate_l2_metrics(dataset_id, param_set_id, inputs)`
3. Service fetches L1 metrics from metrics_outputs table using MetricsRepository → returns pandas DataFrame
4. Service fetches fundamentals data from fundamentals table → returns pandas DataFrame
5. Service calls pure calculation function (`_calculate_l2_metrics_pure()`) which:
   - Pivots L1 metrics to columns (Calc MC, ROA, etc.)
   - Performs pandas operations (arithmetic, ratios, regressions)
   - Returns results DataFrame with (ticker, fiscal_year, metric_name, value)
6. Service batch-inserts results into metrics_outputs table with metadata {"metric_level": "L2"}
7. Service commits and returns CalculateL2Response

**ETL Data Ingestion Flow (via `database/etl/pipeline.py` orchestrator):**

1. Pipeline orchestrator reads Bloomberg Excel file path from CLI argument
2. Calls Ingester.load_excel_to_raw_data():
   - Opens Excel workbook, reads 24 worksheets
   - Denormalizes metrics (pivots columns to rows)
   - Validates numeric values (rejects non-parseable strings)
   - Inserts into raw_data table with validation audit trail
3. Pipeline calls DataQualityProcessor.process_fundamentals():
   - Fetches raw_data from database
   - Applies FY alignment (extracts fiscal year from period strings)
   - Runs 7-step imputation cascade (RAW → FORWARD_FILL → BACKWARD_FILL → INTERPOLATE → SECTOR_MEDIAN → MARKET_MEDIAN → MISSING)
   - Inserts clean data into fundamentals table
4. Pipeline auto-triggers L1 metrics via SQL functions (invoked in database)
5. Pipeline signals L2 metrics auto-calculation (can be async)

**State Management:**

- **Database State**: Single source of truth in PostgreSQL (raw_data → fundamentals → metrics_outputs tables)
- **Session State**: AsyncSession instances created per request, disposed after request completes
- **Service State**: Stateless services instantiated per request with injected AsyncSession
- **Application State**: Global DatabaseManager singleton manages engine and session factory; Settings singleton via @lru_cache()

## Key Abstractions

**MetricsService (L1 Metric Calculation):**
- Purpose: Execute SQL functions for L1 metrics, insert results into database
- Examples: `backend/app/services/metrics_service.py`
- Pattern: Service orchestrates SQL function calls, batch inserts results
- Key method: `calculate_metric(dataset_id, metric_name)` → calls SQL function → inserts to metrics_outputs

**L2MetricsService (L2 Metric Calculation):**
- Purpose: Fetch L1 metrics/fundamentals, run pure Python calculation, persist results
- Examples: `backend/app/services/l2_metrics_service.py`
- Pattern: Service fetches data via repository, calls pure calculation function, batch-inserts results
- Key method: `calculate_l2_metrics(dataset_id, param_set_id, inputs)` → pandas operations → metrics_outputs

**MetricsRepository (Data Abstraction):**
- Purpose: Abstract raw SQL queries for metrics data, provide clean DataFrame interface
- Examples: `backend/app/repositories/metrics_repository.py`
- Pattern: Repository returns pandas DataFrames for service calculations
- Key method: `get_l1_metrics(dataset_id, param_set_id)` → returns DataFrame

**DatabaseManager (Connection Pooling):**
- Purpose: Manage async SQLAlchemy engine lifecycle, provide session dependency for injection
- Examples: `backend/app/core/database.py`
- Pattern: Singleton instance created at app startup, destroyed at shutdown
- Key methods: `initialize()` creates engine, `get_session()` yields async sessions, `close()` disposes engine

**Ingester (ETL Data Loading):**
- Purpose: Extract Excel data, validate numerics, insert into raw_data table
- Examples: `backend/database/etl/ingestion.py`
- Pattern: Orchestrates Excel reading, CSV denormalization, numeric validation, duplicate detection
- Key method: `load_excel_to_raw_data(excel_path)` → validates → inserts to raw_data

**DataQualityProcessor (ETL Data Cleaning):**
- Purpose: Apply FY alignment, imputation cascade, transform raw_data → fundamentals
- Examples: `backend/database/etl/processing.py`
- Pattern: Fetches raw_data, applies 7-step imputation logic, inserts clean data
- Key method: `process_fundamentals()` → imputation → inserts to fundamentals

## Entry Points

**FastAPI Server:**
- Location: `backend/app/main.py` (FastAPI app with lifespan context manager)
- Triggers: `uvicorn` server startup (when `python -m backend.app.main` or `uvicorn backend.app.main:app`)
- Responsibilities:
  - Configure CORS middleware
  - Initialize DatabaseManager on startup
  - Register API v1 router
  - Provide `/` root endpoint and `/api/v1/metrics/health` health check
  - Close database connections on shutdown

**L2 Metrics CLI:**
- Location: `backend/app/cli/run_l2_metrics.py`
- Triggers: `python -m backend.app.cli.run_l2_metrics --dataset-id <uuid> --param-set-id <uuid>`
- Responsibilities:
  - Parse CLI arguments (dataset_id, param_set_id)
  - Create async session from global factory
  - Instantiate L2MetricsService
  - Call calculate_l2_metrics() and return exit code

**Enhanced Metrics CLI:**
- Location: `backend/app/cli/run_enhanced_metrics.py`
- Triggers: `python -m backend.app.cli.run_enhanced_metrics --dataset-id <uuid> --param-set-id <uuid>`
- Responsibilities:
  - Parse CLI arguments
  - Instantiate EnhancedMetricsService
  - Call calculate_enhanced_metrics() for Phase 3 metrics

**ETL Pipeline Orchestrator:**
- Location: `backend/database/etl/pipeline.py`
- Triggers: `python backend/database/etl/pipeline.py --input <excel_file> [--mode full|step-by-step]`
- Responsibilities:
  - Parse Excel file path from CLI
  - Orchestrate complete pipeline: ingestion → processing → metrics calculation
  - Log pipeline execution to file and console
  - Return exit code (0 success, 1 error)

## Error Handling

**Strategy:** Async exception propagation with service-layer error wrapping + API-layer HTTP exception conversion

**Patterns:**

1. **Service Layer Error Wrapping:**
   - Try-catch in service methods catches database/calculation errors
   - Wraps errors in response dict with `status: "error"` and descriptive message
   - Returns error response instead of raising exception
   - Example: `backend/app/services/metrics_service.py` lines 107-115

2. **API Layer HTTP Conversion:**
   - Endpoint receives error response from service
   - Checks `response.status == "error"`
   - Raises `HTTPException(status_code=400, detail=message)` for client errors
   - Raises `HTTPException(status_code=500, ...)` for server errors
   - Example: `backend/app/api/v1/endpoints/metrics.py` lines 75-76

3. **Database Session Error Recovery:**
   - AsyncSession context manager in database.py catches session errors
   - Calls `await session.rollback()` on exception
   - Logs error with context
   - Re-raises exception for handler to catch
   - Example: `backend/app/core/database.py` lines 54-57

4. **ETL Pipeline Error Logging:**
   - Pipeline orchestrator wraps each stage in try-except
   - Logs errors to both file and console
   - Continues to next stage on non-critical errors (partial success)
   - Example: `backend/database/etl/pipeline.py` sections

## Cross-Cutting Concerns

**Logging:** 
- Framework: Python `logging` module with custom PipelineLogger in ETL
- Approach: Per-module loggers via `get_logger(__name__)` in `backend/app/core/config.py`
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Pipeline uses file + console handlers for dual output

**Validation:**
- Request validation: Pydantic models (CalculateMetricsRequest, etc.) in schemas.py
- Metric name validation: METRIC_FUNCTIONS dict lookup in MetricsService.calculate_metric()
- Numeric validation: ETL validators.py validates numeric strings from Excel before insertion
- Duplicate detection: Ingester.load_excel_to_raw_data() logs duplicates to audit trail

**Authentication:**
- Current: None (open API with CORS allow_origins=["*"])
- Future: Can add Keycloak/OIDC via FastAPI middleware/Depends()

**Async/Concurrency:**
- All database operations use AsyncSession from SQLAlchemy
- Services are stateless, can be instantiated per request
- Batch operations use loop-based inserts (not bulk operations) for transactional consistency
- CLI scripts use `asyncio.run()` to execute async functions

**Database Connection Pooling:**
- SQLAlchemy create_async_engine with pool_size=10, max_overflow=20
- pool_pre_ping=True to test stale connections
- Timeout 10s for connection, 60s for command
- Automatic connection recycling on app restart

---

*Architecture analysis: 2026-03-09*
