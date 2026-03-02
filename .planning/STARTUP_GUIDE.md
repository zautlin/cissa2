# CISSA Backend Startup Guide

**Status:** ✅ Phase 1 Integration Complete

**Date:** 2026-03-02

---

## What's Been Set Up

**Database Infrastructure:**
- PostgreSQL 15.13 container via Docker Compose
- Complete schema with 18 tables in `USR` schema
- Automatic initialization on container startup
- All migrations and DDL in `db/schema/migrations/000_complete_schema.sql`

**Python Package:**
- `setup.py` for installation
- `requirements.txt` with 18 dependencies
- `src/` package structure with:
  - `config/` - Environment-based configuration
  - `api/` - FastAPI application framework
  - `services/` - Metrics worker for async job processing

**API Framework:**
- FastAPI application ready to run
- CORS middleware configured
- 9 endpoints defined for data upload and metrics calculation
- Health check endpoint available

**Sample Data:**
- Bloomberg financial data (4.2 MB) in `data/` directory
- Ready for ingestion into database

---

## Quick Start (5 minutes)

### 1. Start PostgreSQL Database

```bash
cd db/
docker-compose up -d
```

**What this does:**
- Starts PostgreSQL 15.13 container named `cissa-postgres`
- Mounts `schema/migrations/` directory
- Automatically runs `000_complete_schema.sql` to create all tables
- Makes database available on `localhost:5432`

**Verify database is ready:**
```bash
# Check container status
docker-compose ps

# Expected output: postgres healthy in ~10 seconds
# You should see:
# NAME           STATUS
# cissa-postgres running (healthy)
```

### 2. Install Python Dependencies

```bash
cd ..  # Back to repo root
pip install -r requirements.txt
```

**Expected output:**
- 18 packages installed (pandas, fastapi, sqlalchemy, pydantic, etc.)
- May take 2-3 minutes on first install
- Python 3.14+ required

**Troubleshooting dependency build issues:**
If you see build errors for `pydantic-core`:
- This is a known issue with Python 3.14 prebuilts
- Try: `pip install --pre pydantic-core` (use prerelease)
- Or: `conda install pydantic` (use conda package)
- Full pip install can proceed with warnings

### 3. Start the API Server

```bash
python -m src.api.main
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     CISSA API service starting...
INFO:     Database health: ok
INFO:     Metrics worker started
```

**If database connection fails:**
- Verify postgres container is running: `docker-compose ps`
- Check logs: `docker-compose logs postgres`
- Port conflict? Change in `docker-compose.yml` ports: `"5433:5432"`

### 4. Test the API

Open browser or use curl:

```bash
# Health check endpoint
curl http://localhost:8000/api/v1/health

# Expected response:
# {
#   "status": "healthy",
#   "database": "ok",
#   "timestamp": "2026-03-02T15:20:00.000000Z"
# }
```

**Swagger UI Documentation:**
```
http://localhost:8000/docs
```

---

## Database Management

### Connect to Database CLI

```bash
docker-compose exec postgres psql -U postgres -d cissa
```

**Useful commands:**
```sql
-- List all tables in USR schema
\dt "USR".*

-- Check table structure
\d "USR".company

-- Count rows
SELECT COUNT(*) FROM "USR".company;

-- View data versions (for tracking uploaded files)
SELECT version_name, uploaded_at FROM "USR".data_versions;
```

### Stop Database

```bash
docker-compose down
```

This stops the container but **preserves data**.

### Reset Database (DELETE ALL DATA)

```bash
docker-compose down -v
docker-compose up -d
```

This removes the container and volume. Fresh database created on startup.

### View Logs

```bash
docker-compose logs -f postgres
```

---

## Configuration

### Environment Variables

Database connection uses these env vars (with fallbacks):

```bash
# For local development (DEFAULT - no need to set)
export DEPLOYMENT_MODE=local
export DB_HOST=localhost
export DB_NAME=cissa
export DB_USER=postgres
export DB_PORT=5432
export DB_PASSWORD=postgres   # Password for API → DB connection

# For production AWS RDS
export DEPLOYMENT_MODE=production
export DB_HOST=your-rds-endpoint.region.rds.amazonaws.com
export DB_NAME=cissa
export DB_USER=postgres
export DB_PASSWORD=your-secure-password
export DB_PORT=5432
```

**Current Setup:**
- `db/.env.local` provides Docker environment variables
- `src/config/parameters.py` reads DEPLOYMENT_MODE and configures database URL
- `src/api/main.py` uses DATABASE_URL for connections

---

## File Structure

```
cissa/
├── requirements.txt              # Python dependencies
├── setup.py                      # Package configuration
├── db/
│   ├── docker-compose.yml        # PostgreSQL container definition
│   ├── .env.local               # Docker environment variables
│   └── schema/migrations/
│       └── 000_complete_schema.sql   # Database schema (906 lines, 18 tables)
├── src/
│   ├── __init__.py              # Package marker
│   ├── config/
│   │   ├── __init__.py
│   │   └── parameters.py        # Configuration (env-based)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── models.py            # Pydantic request/response schemas
│   │   └── handlers.py          # Endpoint handler functions
│   └── services/
│       ├── __init__.py
│       └── metrics_worker.py    # Async metrics calculation worker
└── data/
    └── Bloomberg Download data.xlsx  # Sample financial data (4.2 MB)
```

---

## What Works Now

✅ **Database:**
- PostgreSQL running in Docker
- All 18 tables created
- Schemas and indexes ready
- Connection pooling available

✅ **API Framework:**
- FastAPI application starts
- CORS middleware configured
- 9 endpoints defined
- Health check responds
- Swagger documentation available

✅ **Configuration:**
- Environment-based settings
- Hardcoded production values removed
- Local development defaults work
- Password can be env var or fallback

✅ **Package Structure:**
- Proper Python package layout
- All imports resolve
- Ready for `pip install -e .`

---

## What's NOT Yet Working

❌ **Data Ingestion:**
- `src/upload_data_to_db.py` exists but requires engine modules
- Excel parsing logic in `src/engine/xls.py` not yet copied

❌ **Metrics Calculation:**
- Calculation endpoints defined but engine not present
- `src/engine/calculation.py` not yet copied

❌ **Optimization:**
- Portfolio optimization module not yet copied

---

## Next Steps (Phase 2)

After verifying this setup works:

1. **Copy Engine Modules** (Phase 2)
   - Copy `src/engine/` from basos-ds
   - Implement data ingestion workflow
   - Test end-to-end with Excel files

2. **Set Up Testing** (Phase 2)
   - Copy `test/` directory
   - Run pytest suite
   - Add API integration tests

3. **Run Data Pipeline** (Phase 2)
   - Upload Bloomberg data to database
   - Calculate L1 metrics
   - Verify API can query results

---

## Troubleshooting

### Port 5432 Already in Use

**Error:** `Ports are not available: exposing port TCP 0.0.0.0:5432`

**Solution:**
```bash
# Option 1: Find what's using port 5432
lsof -i :5432

# Option 2: Use different port in docker-compose.yml
# Change ports: - "5433:5432"
# Then: export DB_PORT=5433
```

### API Won't Connect to Database

**Error:** `Error: connect ECONNREFUSED 127.0.0.1:5432`

**Solution:**
```bash
# Verify postgres is running
docker-compose ps

# Check logs
docker-compose logs postgres

# Restart database
docker-compose down
docker-compose up -d

# Wait 10 seconds for health check
sleep 10
```

### Python Dependency Conflicts

**Error:** `ERROR: pip's dependency resolver does not currently take into account...`

**Solution:**
- This is usually just a warning
- Dependencies are compatible
- If import fails, try: `pip install --upgrade setuptools pip`

### Can't Import pydantic

**Error:** `ModuleNotFoundError: No module named 'pydantic'`

**Solution:**
```bash
# Verify installation
pip list | grep pydantic

# If missing, install
pip install pydantic==2.5.0

# Or use conda
conda install pydantic
```

---

## Command Reference

```bash
# Start everything
cd db/
docker-compose up -d
cd ..
pip install -r requirements.txt
python -m src.api.main

# Database access
docker-compose -C db exec postgres psql -U postgres -d cissa

# Stop everything
docker-compose -C db down

# Check status
docker-compose -C db ps

# View logs
docker-compose -C db logs -f postgres
```

---

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review logs: `docker-compose logs postgres` or API console
3. Verify files exist: `ls -la db/ src/ data/`
4. Check Python version: `python --version` (need 3.14+)
5. Verify dependencies: `pip list | grep -E "fastapi|pydantic|psycopg2"`

---

**Backend Infrastructure Phase: COMPLETE ✅**

Ready to proceed to Phase 2: Data Ingestion Pipeline
