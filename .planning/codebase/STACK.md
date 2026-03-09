# Technology Stack

**Analysis Date:** 2026-03-09

## Languages

**Primary:**
- Python 3.10+ - FastAPI backend, business logic, CLI scripts, database operations

**Secondary:**
- SQL - PostgreSQL stored procedures, schema definitions, data transformations

## Runtime

**Environment:**
- Python 3.10+ (runtime for backend)
- PostgreSQL 16+ (database)

**Package Manager:**
- pip (Python)
- Lockfile: `requirements.txt` present

## Frameworks

**Core:**
- FastAPI 0.109.0 - HTTP API framework with async support
- Uvicorn 0.27.0 - ASGI server (async-capable)

**Database/ORM:**
- SQLAlchemy 2.0.48 - ORM with async support (`sqlalchemy[asyncio]`)
- AsyncPG 0.30.0 - Async PostgreSQL driver (replaces psycopg2 for production)
- psycopg2-binary 2.9.11 - Sync PostgreSQL driver (fallback/migration)

**Data Processing:**
- Pandas 3.0.1 - Data manipulation and analysis
- NumPy - Numerical computations (implicit dependency via Pandas)

**Validation/Configuration:**
- Pydantic 2.10.0 - Request/response schema validation
- Pydantic-Settings 2.4.0 - Environment configuration management
- python-dotenv 1.2.2 - Load .env files at startup

**File Handling:**
- Openpyxl 3.1.5 - Excel file parsing and generation (.xlsx support)

## Key Dependencies

**Critical:**
- SQLAlchemy 2.0.48 - Core ORM; enables async database operations via `sqlalchemy[asyncio]`
- AsyncPG 0.30.0 - High-performance async database driver; must connect to PostgreSQL
- Pydantic 2.10.0 - Request validation; enforces schema contracts on all API endpoints
- FastAPI 0.109.0 - HTTP framework; routes defined in `backend/app/api/v1/endpoints/metrics.py`

**Infrastructure:**
- Uvicorn 0.27.0 - ASGI server; runs on port 8000 by default
- python-dotenv 1.2.2 - Loads `DATABASE_URL` and other settings from `.env`

## Configuration

**Environment:**
- `.env` file (root: `/home/ubuntu/cissa/.env`) - Contains `DATABASE_URL` and runtime settings
- Configuration class: `backend/app/core/config.py` (uses `pydantic-settings`)
- Environment variables loaded on module import via `load_dotenv()`

**Required Configuration:**
- `DATABASE_URL` - PostgreSQL connection string (format: `postgresql+asyncpg://user:password@host:port/database`)
- `FASTAPI_ENV` - Environment mode (`development` | `production`)
- `LOG_LEVEL` - Logging verbosity (`info` | `debug` | `warning`)
- `WORKERS` - Number of uvicorn workers (default: 1)
- `METRICS_BATCH_SIZE` - Batch size for metric calculations (default: 1000)
- `METRICS_TIMEOUT_SECONDS` - Calculation timeout (default: 300)

**Build:**
- `requirements.txt` - pip dependencies specification
- `backend/app/main.py` - FastAPI app creation and lifespan management
- Async engine initialization in `backend/app/core/database.py`

## Platform Requirements

**Development:**
- Python 3.10+
- PostgreSQL 16+ instance accessible via `DATABASE_URL`
- `.env` file with valid `DATABASE_URL`
- pip package manager

**Production:**
- Python 3.10+
- PostgreSQL 16+ (remote or containerized)
- AsyncPG driver (async-safe, production-ready)
- Uvicorn ASGI server
- Deployment target: Docker container or VM with Python runtime
- Port 8000 exposed for HTTP traffic

**Database Requirements:**
- PostgreSQL 16+ with `cissa` schema
- SQL functions: 15 metric calculation functions in `cissa` schema (created via `backend/database/schema/functions.sql`)
- Tables: `companies`, `fundamentals`, `dataset_versions`, `parameter_sets`, `metrics_outputs` (created via `backend/database/schema/schema.sql`)

---

*Stack analysis: 2026-03-09*
