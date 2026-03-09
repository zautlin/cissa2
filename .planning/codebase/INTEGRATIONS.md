# External Integrations

**Analysis Date:** 2026-03-09

## APIs & External Services

**No External APIs Detected**
- No third-party API integrations (Stripe, AWS, Supabase, etc.) found
- System operates as a self-contained financial metrics engine
- Data ingestion is file-based (Excel from input-data/ASX directory)

## Data Storage

**Databases:**
- PostgreSQL 16+
  - Connection: `DATABASE_URL` environment variable
  - Client: AsyncPG (async driver) via SQLAlchemy 2.0.48
  - Schema: `cissa` (isolated from public schema)
  - Tables: `companies`, `fundamentals`, `dataset_versions`, `parameter_sets`, `metrics_outputs`
  - Functions: 15 SQL functions for Phase 1 metric calculations

**File Storage:**
- Local filesystem only
  - Input data: `input-data/ASX/` directory (Excel and CSV files)
  - Schema files: `backend/database/schema/` (SQL scripts)
  - Logs: `backend/database/ingestion_process/logs/` (local log files)

**Caching:**
- None detected - no Redis, Memcached, or in-process caching layer
- Database connections use pool with `pool_size=10`, `max_overflow=20` (SQLAlchemy engine)

## Authentication & Identity

**Auth Provider:**
- None - No external authentication service (Keycloak, Auth0, etc.) integrated
- API endpoints currently open (CORS allows all origins)
- Internal token/credential system: Not implemented

**Current Security Posture:**
- CORS middleware: `allow_origins=["*"]` (development mode - all origins permitted)
- No JWT validation or role-based access control on endpoints
- Authentication ready for future integration (structure in place)

## Monitoring & Observability

**Error Tracking:**
- None detected - No Sentry, Rollbar, or external error tracking service

**Logs:**
- Local logging via Python `logging` module
- Configuration: `backend/app/core/config.py`
- Format: `'%(asctime)s - %(name)s - %(levelname)s - %(message)s'`
- Level: Configurable via `LOG_LEVEL` env var (default: `info`)
- Destination: Console/stdout (via StreamHandler)

**Health Checks:**
- Internal endpoint: `GET /api/v1/metrics/health` (returns `{"status": "ok", "database": "connected"}`)
- Manual testing via endpoint, no external monitoring service

## CI/CD & Deployment

**Hosting:**
- Not deployed - Development/test environment only
- Recommended deployment: Docker container on Linux VM, Heroku, or K8s cluster

**CI Pipeline:**
- None detected - No GitHub Actions, GitLab CI, Jenkins, or similar
- Manual deployment model

**Deployment Artifacts:**
- Docker: No Dockerfile found
- startup script: `backend/start-api.sh` (local development)
- Requirements: `requirements.txt` for pip install

## Environment Configuration

**Required env vars:**
- `DATABASE_URL` - PostgreSQL connection string (CRITICAL)
- `FASTAPI_ENV` - Environment (development/production)
- `LOG_LEVEL` - Logging level (info/debug/warning)
- `WORKERS` - Uvicorn worker count
- `METRICS_BATCH_SIZE` - Batch size for metric calculations
- `METRICS_TIMEOUT_SECONDS` - Calculation timeout

**Secrets location:**
- `.env` file at project root (`/home/ubuntu/cissa/.env`)
- Format: Key=Value pairs
- Loaded via `python-dotenv` in `backend/app/core/config.py`

**Security Note:**
- `.env` file is in `.gitignore` - secrets not committed to git
- No vault service (HashiCorp Vault, AWS Secrets Manager) integrated

## Webhooks & Callbacks

**Incoming:**
- None - API endpoints are stateless request/response only
- No webhook receiver endpoints

**Outgoing:**
- None - System does not push data to external services
- All operations are pull-based (client calls endpoints)

**Async Task Processing:**
- No message queue (RabbitMQ, Kafka, AWS SQS) detected
- All calculations are synchronous (blocking until complete)
- Uvicorn handles up to 1 worker (configurable via `WORKERS` env var)

## Data Sources

**Financial Data:**
- Source: Bloomberg ASX data (Excel files in `input-data/ASX/`)
- Ingestion: File-based (openpyxl for .xlsx parsing)
- Ingest Location: `backend/database/ingestion_process/` (CLI scripts and utilities)
- Processing: Pandas DataFrames for transformation and validation

**Reference Data:**
- `Base.csv` - Company master list (companies table)
- `FY Dates.csv` - Fiscal year period mapping
- Consolidation data: `input-data/ASX/consolidated-data/` directory

---

*Integration audit: 2026-03-09*
