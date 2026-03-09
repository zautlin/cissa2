# Codebase Structure

**Analysis Date:** 2026-03-09

## Directory Layout

```
/home/ubuntu/cissa/
├── backend/                          # Main Python backend application
│   ├── app/                          # FastAPI application code
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app entry point with lifespan
│   │   ├── core/                     # Infrastructure & configuration
│   │   │   ├── __init__.py
│   │   │   ├── config.py             # Settings (Pydantic) + logger factory
│   │   │   └── database.py           # DatabaseManager + AsyncSession dependency
│   │   ├── api/                      # API routing
│   │   │   ├── __init__.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py         # Aggregates all v1 endpoints
│   │   │       └── endpoints/
│   │   │           ├── __init__.py
│   │   │           └── metrics.py    # Metric calculation endpoints (L1, L2, L3)
│   │   ├── services/                 # Business logic layer
│   │   │   ├── __init__.py
│   │   │   ├── metrics_service.py    # L1 metric calculations
│   │   │   ├── l2_metrics_service.py # L2 metric calculations (pandas-based)
│   │   │   └── enhanced_metrics_service.py  # L3 enhanced metrics (Phase 3)
│   │   ├── repositories/             # Data access layer
│   │   │   ├── __init__.py
│   │   │   └── metrics_repository.py # MetricsRepository (queries + DataFrame returns)
│   │   ├── models/                   # Domain models
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py            # Pydantic request/response models
│   │   │   ├── metrics_output.py     # SQLAlchemy ORM model for metrics_outputs table
│   │   │   └── __pycache__/
│   │   ├── cli/                      # Command-line entry points
│   │   │   ├── __init__.py
│   │   │   ├── run_l2_metrics.py     # CLI for L2 metrics calculation
│   │   │   └── run_enhanced_metrics.py  # CLI for L3 enhanced metrics
│   │   ├── models.py                 # Backward compatibility re-exports
│   │   └── __pycache__/
│   ├── database/                     # ETL pipeline for data ingestion
│   │   ├── config/
│   │   ├── etl/                      # ETL stage scripts
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py           # Master orchestrator (main ETL entry point)
│   │   │   ├── config.py             # ETL database connection config
│   │   │   ├── ingestion.py          # Stage 1: Excel → raw_data (Ingester class)
│   │   │   ├── processing.py         # Stage 2: raw_data → fundamentals (DataQualityProcessor)
│   │   │   ├── validators.py         # Numeric validation helpers
│   │   │   ├── fy_aligner.py         # Fiscal year alignment logic
│   │   │   ├── imputation_engine.py  # 7-step imputation cascade
│   │   │   └── __pycache__/
│   │   ├── schema/
│   │   │   └── schema_manager.py     # Database schema management
│   │   ├── queries.py                # Raw SQL query functions
│   │   └── ingestion_process/        # ETL execution logs
│   │       └── logs/
│   └── scripts/                      # Utility scripts
├── example-calculations/             # Example metric calculations (reference)
│   └── src/
├── input-data/                       # Input Excel files location
│   └── ASX/
├── .planning/                        # GSD planning documents
│   ├── codebase/                     # Architecture & structure docs (generated)
│   │   ├── ARCHITECTURE.md
│   │   ├── STRUCTURE.md
│   │   ├── CONVENTIONS.md
│   │   ├── TESTING.md
│   │   ├── STACK.md
│   │   ├── INTEGRATIONS.md
│   │   └── CONCERNS.md
│   └── phases/                       # Phase implementation plans
│       ├── 04-auto-trigger-l1/
│       └── 05-rename-l2-metrics/
├── .env                              # Environment configuration (secrets - not committed)
├── requirements.txt                  # Python dependencies
├── README.md                         # Project documentation
├── DEVELOPER_GUIDE.md               # Development setup guide
└── .git/                             # Git repository
```

## Directory Purposes

**`backend/app/`:**
- Purpose: Main FastAPI application code organized by layer
- Contains: API endpoints, services, repositories, models, CLI commands
- Key files: `main.py` (app factory), `core/config.py` (settings), `core/database.py` (session management)

**`backend/app/core/`:**
- Purpose: Application infrastructure (settings, database, logging)
- Contains: Pydantic Settings class, AsyncSession factory, logger factory
- Key files: `config.py` (environment + logging), `database.py` (connection pooling)

**`backend/app/api/v1/`:**
- Purpose: HTTP API definition with versioning
- Contains: Router aggregation and endpoint definitions
- Key files: `router.py` (combines all v1 endpoints), `endpoints/metrics.py` (metric calculation routes)

**`backend/app/services/`:**
- Purpose: Business logic for metric calculations
- Contains: L1MetricsService, L2MetricsService, EnhancedMetricsService
- Key files: `metrics_service.py` (SQL function calls), `l2_metrics_service.py` (pandas calculations)

**`backend/app/repositories/`:**
- Purpose: Data access layer abstracting database queries
- Contains: MetricsRepository with query and insert methods
- Key files: `metrics_repository.py` (metrics_outputs table access)

**`backend/app/models/`:**
- Purpose: Domain and ORM models
- Contains: Pydantic schemas for requests/responses, SQLAlchemy ORM classes
- Key files: `schemas.py` (CalculateMetricsRequest, CalculateMetricsResponse, etc.), `metrics_output.py` (MetricsOutput ORM)

**`backend/app/cli/`:**
- Purpose: Command-line entry points for metric calculations
- Contains: CLI scripts for L2 metrics, enhanced metrics
- Key files: `run_l2_metrics.py`, `run_enhanced_metrics.py`

**`backend/database/etl/`:**
- Purpose: Data ingestion and transformation pipeline
- Contains: Excel loading, validation, imputation, fiscal year alignment
- Key files: `pipeline.py` (orchestrator), `ingestion.py` (Ingester), `processing.py` (DataQualityProcessor)

**`.planning/codebase/`:**
- Purpose: Generated codebase documentation for GSD phases
- Contains: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, STACK.md, INTEGRATIONS.md, CONCERNS.md
- Generated by: `/gsd-map-codebase` orchestrator

## Key File Locations

**Entry Points:**
- `backend/app/main.py`: FastAPI application factory with lifespan (startup/shutdown)
- `backend/app/cli/run_l2_metrics.py`: CLI entry point for L2 metrics calculation
- `backend/database/etl/pipeline.py`: ETL orchestrator for data ingestion

**Configuration:**
- `backend/app/core/config.py`: Pydantic Settings with environment variable loading
- `backend/app/core/database.py`: SQLAlchemy AsyncSession factory and connection management
- `.env`: Environment variables (DATABASE_URL, fastapi_env, etc.)

**Core Logic:**
- `backend/app/services/metrics_service.py`: L1 metric SQL function calls and batch insertion
- `backend/app/services/l2_metrics_service.py`: L2 metric pandas calculations
- `backend/app/services/enhanced_metrics_service.py`: L3 enhanced metric calculations

**Data Models:**
- `backend/app/models/schemas.py`: Pydantic request/response models
- `backend/app/models/metrics_output.py`: SQLAlchemy ORM for metrics_outputs table

**Data Access:**
- `backend/app/repositories/metrics_repository.py`: MetricsRepository with query methods
- `backend/database/etl/ingestion.py`: Ingester class for Excel → raw_data
- `backend/database/etl/processing.py`: DataQualityProcessor for fundamentals transformation

**Testing:**
- No test directory detected (test coverage to be added)

## Naming Conventions

**Files:**
- `_service.py`: Business logic service classes (e.g., `metrics_service.py`, `l2_metrics_service.py`)
- `_repository.py`: Data access repository classes (e.g., `metrics_repository.py`)
- `_output.py`: ORM model files (e.g., `metrics_output.py`)
- `.py`: General Python modules

**Directories:**
- `api/`: HTTP API routing and endpoints
- `services/`: Business logic and orchestration
- `repositories/`: Data access abstraction
- `models/`: Domain models (schemas + ORM)
- `core/`: Infrastructure (config, database, logging)
- `cli/`: Command-line entry points
- `etl/`: Data extraction, transformation, loading

**Classes:**
- `MetricsService`: Service for L1 metric calculations
- `L2MetricsService`: Service for L2 metric calculations
- `EnhancedMetricsService`: Service for L3 enhanced metric calculations
- `MetricsRepository`: Repository for metrics_outputs table
- `MetricsOutput`: SQLAlchemy ORM model for metrics_outputs table
- `Ingester`: ETL class for Excel data ingestion
- `DataQualityProcessor`: ETL class for data cleaning and transformation
- `DatabaseManager`: Connection pool manager for AsyncSession

**Functions:**
- `get_settings()`: Cached singleton Settings instance
- `get_db()`: FastAPI dependency that yields AsyncSession
- `get_logger(name)`: Logger factory function
- `calculate_metric()`: Service method for metric calculation
- `calculate_l2_metrics()`: Service method for L2 calculation

**Variables:**
- `METRIC_FUNCTIONS`: Dict mapping metric names to SQL function names (in metrics_service.py)
- `router`: APIRouter instances in endpoint files
- `session`: AsyncSession instance (injected via Depends)
- `db_manager`: DatabaseManager singleton

## Where to Add New Code

**New API Endpoint (L1/L2/L3 metric calculation):**
- Endpoint definition: `backend/app/api/v1/endpoints/metrics.py` (add new @router.post() or @router.get())
- Request/Response schema: `backend/app/models/schemas.py` (add new Pydantic models)
- Service logic: `backend/app/services/metrics_service.py` or `l2_metrics_service.py` (add new method)
- Test file: `backend/tests/endpoints/test_metrics.py` (create if not exists)

**New Service Class (metric calculation logic):**
- Implementation: `backend/app/services/` (create `new_feature_service.py`)
- Inject repository: Use `MetricsRepository(session)` for data access
- Follow pattern: Async methods with error handling in try-except, return dict with status/message/results
- Test file: `backend/tests/services/test_new_feature_service.py`

**New Database Query:**
- If fetching from metrics_outputs: Add method to `backend/app/repositories/metrics_repository.py`
- If raw SQL needed: Use `text()` queries in service methods with parameter binding
- Example: `query = text("SELECT ... FROM cissa.table WHERE id = :id")`

**New ETL Stage/Transformation:**
- Create script in `backend/database/etl/` (e.g., `new_stage.py`)
- Follow Ingester/DataQualityProcessor pattern: class with async methods
- Register in PipelineOrchestrator in `pipeline.py`
- Log progress via PipelineLogger

**New CLI Command:**
- Create file in `backend/app/cli/` (e.g., `run_new_command.py`)
- Use `async def main()` with argparse for CLI args
- Import from `backend.app.core.database` and `backend.app.services`
- Entry point: `python -m backend.app.cli.run_new_command --arg1 <value>`

**Configuration Change:**
- Add new setting to `Settings` class in `backend/app/core/config.py` (with type and default)
- Reference in code: `settings = get_settings(); settings.new_setting`
- Environment variable: Set in `.env` file (not committed)

## Special Directories

**`backend/app/__pycache__/`:**
- Purpose: Python bytecode cache
- Generated: Yes (automatic on import)
- Committed: No (in .gitignore)

**`backend/database/etl/backend/`:**
- Purpose: Appears to be legacy/duplicate structure
- Status: May be artifact from previous setup; review for cleanup
- Committed: Check .gitignore

**`backend/database/ingestion_process/logs/`:**
- Purpose: ETL pipeline execution logs
- Generated: Yes (at runtime)
- Committed: No

**`.planning/codebase/`:**
- Purpose: Generated GSD codebase documentation
- Generated: Yes (by `/gsd-map-codebase`)
- Committed: Yes (reference for other GSD commands)

## Project Configuration Files

**Root Level:**
- `requirements.txt`: Python package dependencies (pip format)
- `.env`: Environment configuration (DATABASE_URL, LOG_LEVEL, etc.) - secret, not committed
- `.gitignore`: Files excluded from version control
- `README.md`: Project overview and quick start
- `DEVELOPER_GUIDE.md`: Development setup instructions

**Backend Code:**
- `backend/app/main.py`: FastAPI app configuration (no separate config file; uses core/config.py)
- `backend/database/etl/config.py`: ETL-specific database connection config

## Module Imports Pattern

**Circular import prevention:**
- Models layer (`models/schemas.py`) has no dependencies on other app layers
- Repositories layer (`repositories/metrics_repository.py`) depends only on models
- Services layer depends on repositories but not on API layer
- API layer depends on services and models

**Relative imports in app:**
- From endpoint: `from ....services.metrics_service import MetricsService` (4 levels up to app/)
- From service: `from ..models import MetricsOutput` (2 levels up to app/)
- From repository: `from ..models.metrics_output import MetricsOutput` (2 levels up)

**Absolute imports from CLI:**
- CLI scripts use `sys.path.insert(0, "/home/ubuntu/cissa")` then `from backend.app.*`
- Ensures CLI can run from any directory

**FastAPI Depends pattern:**
- Inject `AsyncSession`: `db: AsyncSession = Depends(get_db)` in endpoint
- `get_db()` is dependency in `backend/app/core/database.py`
- Each request gets fresh session, closed in finally block

---

*Structure analysis: 2026-03-09*
