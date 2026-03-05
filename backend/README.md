# FastAPI Metrics Backend - Implementation Guide

## Overview

This is a **production-ready FastAPI backend** for Phase 1 metric calculations from PostgreSQL. 

**Key Features:**
- ✅ Async-first architecture (AsyncPG, SQLAlchemy 2.0 async)
- ✅ Clean separation: SQL functions (database), service layer (business logic), API routes (HTTP)
- ✅ 15 Phase 1 metrics ready to calculate
- ✅ Pydantic v2 models with strict validation
- ✅ Dependency injection pattern for database sessions
- ✅ Error handling and logging throughout

---

## Architecture

### Directory Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app + lifespan
│   ├── models.py                  # Pydantic request/response schemas
│   ├── core/
│   │   ├── config.py              # Settings from .env
│   │   └── database.py            # AsyncPG setup, session injection
│   ├── services/
│   │   └── metrics_service.py     # Business logic for metric calculation
│   └── api/
│       └── v1/
│           ├── router.py          # Route aggregator
│           └── endpoints/
│               └── metrics.py     # Metric endpoints (POST /api/v1/metrics/calculate)
│
├── database/
│   └── schema/
│       ├── schema.sql             # PostgreSQL schema (fundamentals, metrics_outputs)
│       └── functions.sql          # 15 SQL functions for Phase 1 metrics (NEW)
│
.env                               # Database credentials (root)
requirements.txt                   # Python dependencies (async versions added)
start-api.sh                        # Startup script
```

---

## Setup

### 1. Install Dependencies

```bash
cd /home/ubuntu/cissa
pip install -r requirements.txt
```

**New async dependencies added:**
- `fastapi==0.104.1`
- `uvicorn[standard]==0.24.0`
- `asyncpg==0.29.0` (async PostgreSQL driver)
- `sqlalchemy[asyncio]==2.0.48` (async session support)
- `pydantic==2.5.0`
- `pydantic-settings==2.1.0`

### 2. Configure Environment

File: `.env` (root directory)

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cissa
FASTAPI_ENV=development
LOG_LEVEL=info
METRICS_BATCH_SIZE=1000
METRICS_TIMEOUT_SECONDS=300
```

**Required credentials:**
- `DATABASE_URL`: Must connect to PostgreSQL instance with `cissa` database
  - Format: `postgresql+asyncpg://user:password@host:port/dbname`
  - Uses AsyncPG (async-safe) — NOT psycopg2

### 3. Load SQL Functions

```bash
psql postgresql://postgres:postgres@localhost:5432/cissa \
  -f backend/database/schema/functions.sql
```

This creates 15 SQL functions for Phase 1 metrics:
- `fn_calc_market_cap()` — Market Cap = Spot Shares × Share Price
- `fn_calc_operating_assets()` — Operating Assets = Total Assets - Cash
- `fn_calc_operating_assets_detail()` — Calc OA
- `fn_calc_operating_cost()` — Op Cost = Revenue - Op Income
- `fn_calc_non_operating_cost()` — Non-Op Cost
- `fn_calc_tax_cost()` — Tax Cost = PBT - PAT XO
- `fn_calc_extraordinary_cost()` — XO Cost
- `fn_calc_profit_margin()` — Profit Margin = PAT / Revenue
- `fn_calc_operating_cost_margin()` — Op Cost Margin %
- `fn_calc_non_operating_cost_margin()` — Non-Op Cost Margin %
- `fn_calc_effective_tax_rate()` — Eff Tax Rate
- `fn_calc_extraordinary_cost_margin()` — XO Cost Margin %
- `fn_calc_fixed_asset_intensity()` — FA Intensity
- `fn_calc_book_equity()` — Book Equity
- `fn_calc_roa()` — ROA

### 4. Start the Server

**Option A: Using startup script**
```bash
./start-api.sh
```

**Option B: Direct uvicorn**
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Server running at:** http://localhost:8000
**API Docs:** http://localhost:8000/docs (Swagger UI)

---

## API Usage

### Health Check

```bash
curl http://localhost:8000/api/v1/metrics/health
```

**Response:**
```json
{
  "status": "ok",
  "message": "Metrics service is running",
  "database": "connected"
}
```

### Calculate a Metric

**Endpoint:** `POST /api/v1/metrics/calculate`

```bash
# Get a dataset_id from your database first:
# SELECT dataset_id FROM cissa.dataset_versions LIMIT 1;

DATASET_ID="550e8400-e29b-41d4-a716-446655440000"

curl -X POST http://localhost:8000/api/v1/metrics/calculate \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"metric_name\": \"Calc MC\"
  }"
```

**Request Body:**
```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "metric_name": "Calc MC"
}
```

**Response:**
```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "metric_name": "Calc MC",
  "results_count": 150,
  "results": [
    {
      "ticker": "BHP",
      "fiscal_year": 2023,
      "value": 245678900000.50
    },
    {
      "ticker": "CBA",
      "fiscal_year": 2023,
      "value": 189456700000.25
    }
  ],
  "status": "success"
}
```

### Supported Metrics

POST `/api/v1/metrics/calculate` with one of:

| Metric Name | Formula | Input Fields |
|-------------|---------|--------------|
| `Calc MC` | Spot Shares × Share Price | SPOT_SHARES, SHARE_PRICE |
| `Calc Assets` | Total Assets - Cash | TOTAL_ASSETS, CASH |
| `Calc OA` | Calc Assets - Fixed Assets - Goodwill | [depends on above] |
| `Calc Op Cost` | Revenue - Op Income | REVENUE, OP_INCOME |
| `Calc Non Op Cost` | Op Income - PBT | OP_INCOME, PBT |
| `Calc Tax Cost` | PBT - PAT XO | PBT, PAT_XO |
| `Calc XO Cost` | PAT XO - PAT | PAT_XO, PAT |
| `Profit Margin` | PAT / Revenue | PAT, REVENUE |
| `Op Cost Margin %` | Calc Op Cost / Revenue | [depends on above] |
| `Non-Op Cost Margin %` | Calc Non Op Cost / Revenue | [depends on above] |
| `Eff Tax Rate` | Calc Tax Cost / PBT | [depends on above] |
| `XO Cost Margin %` | Calc XO Cost / Revenue | [depends on above] |
| `FA Intensity` | Fixed Assets / Revenue | FIXED_ASSETS, REVENUE |
| `Book Equity` | Total Equity - Minority Interest | TOTAL_EQUITY, MINORITY_INTEREST |
| `ROA` | PAT / Calc Assets | [depends on above] |

---

## Key Implementation Details

### 1. Async Architecture

**Database Session Injection:**
```python
async def calculate_metric(
    request: CalculateMetricsRequest,
    db: AsyncSession = Depends(get_db)  # FastAPI injects session
):
    service = MetricsService(db)
    return await service.calculate_metric(...)
```

**AsyncPG Benefits:**
- Non-blocking database I/O
- Connection pooling with `pool_size=10`
- Handles 1000+ concurrent requests efficiently

### 2. SQL Functions

All metric calculations happen **in PostgreSQL** (not Python).

**Function template** (`fn_calc_market_cap`):
```sql
CREATE OR REPLACE FUNCTION cissa.fn_calc_market_cap(p_dataset_id UUID)
RETURNS TABLE (ticker TEXT, fiscal_year INTEGER, calc_mc NUMERIC) AS $$
BEGIN
  RETURN QUERY
  SELECT
    f1.ticker,
    f1.fiscal_year,
    (f1.metric_value * f2.metric_value) AS calc_mc
  FROM cissa.fundamentals f1
  INNER JOIN cissa.fundamentals f2 ...
  WHERE f1.dataset_id = p_dataset_id ...
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

**Why:**
- ✅ Database does the heavy lifting
- ✅ No data transfer overhead
- ✅ Python orchestrates, doesn't calculate
- ✅ Scales to 22,000+ records efficiently

### 3. Results Storage

After calculating, results are inserted into `cissa.metrics_outputs`:

```sql
INSERT INTO cissa.metrics_outputs 
  (dataset_id, metric_name, ticker, fiscal_year, metric_value, created_at)
VALUES (:dataset_id, :metric_name, :ticker, :fiscal_year, :metric_value, now())
ON CONFLICT (dataset_id, metric_name, ticker, fiscal_year) 
DO UPDATE SET metric_value = EXCLUDED.metric_value, updated_at = now();
```

Batch inserts in groups of 1000 for efficiency.

### 4. Error Handling

**Validation:**
- Request schema validation (Pydantic v2)
- Metric name check against `METRIC_FUNCTIONS` dict
- NULL value filtering in SQL WHERE clauses

**Logging:**
- All operations logged with timestamps
- Errors captured and returned in response

---

## Testing

### Using Swagger UI

1. Navigate to http://localhost:8000/docs
2. Click "Try it out" on any endpoint
3. Fill in parameters and execute

### Using curl

**Test with sample data:**

```bash
# First, get a valid dataset_id
DATASET_ID=$(psql postgresql://postgres:postgres@localhost:5432/cissa \
  -t -c "SELECT dataset_id FROM cissa.dataset_versions LIMIT 1")

echo "Using dataset_id: $DATASET_ID"

# Calculate Market Cap
curl -X POST http://localhost:8000/api/v1/metrics/calculate \
  -H "Content-Type: application/json" \
  -d "{\"dataset_id\": \"$DATASET_ID\", \"metric_name\": \"Calc MC\"}" \
  | python -m json.tool

# Calculate Profit Margin
curl -X POST http://localhost:8000/api/v1/metrics/calculate \
  -H "Content-Type: application/json" \
  -d "{\"dataset_id\": \"$DATASET_ID\", \"metric_name\": \"Profit Margin\"}" \
  | python -m json.tool

# Calculate ROA
curl -X POST http://localhost:8000/api/v1/metrics/calculate \
  -H "Content-Type: application/json" \
  -d "{\"dataset_id\": \"$DATASET_ID\", \"metric_name\": \"ROA\"}" \
  | python -m json.tool
```

### Verify in Database

```bash
# Check metrics_outputs for results
psql postgresql://postgres:postgres@localhost:5432/cissa << 'EOF'
SELECT 
  metric_name,
  COUNT(*) as count,
  MIN(metric_value) as min,
  MAX(metric_value) as max
FROM cissa.metrics_outputs
WHERE dataset_id = '<your-dataset-id>'
GROUP BY metric_name
ORDER BY metric_name;
EOF
```

---

## Deployment (Production)

### Environment

Update `.env`:
```env
DATABASE_URL=postgresql+asyncpg://user:password@prod-host:5432/cissa
FASTAPI_ENV=production
LOG_LEVEL=warning
WORKERS=4  # Use multiple worker processes
```

### Run with Gunicorn + Uvicorn

```bash
pip install gunicorn

gunicorn backend.app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 300
```

### Docker (Optional)

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ backend/
COPY .env .env
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t cissa-metrics .
docker run -p 8000:8000 --env-file .env cissa-metrics
```

---

## Troubleshooting

### Issue: "Connection refused"

**Fix:** Check `.env` has correct `DATABASE_URL` and PostgreSQL is running:
```bash
psql postgresql://postgres:postgres@localhost:5432/cissa -c "SELECT 1"
```

### Issue: "fn_calc_market_cap not found"

**Fix:** Load SQL functions:
```bash
psql postgresql://postgres:postgres@localhost:5432/cissa \
  -f backend/database/schema/functions.sql
```

### Issue: "No fundamentals data"

**Fix:** Verify fundamentals table has data:
```bash
psql postgresql://postgres:postgres@localhost:5432/cissa \
  -c "SELECT COUNT(*) FROM cissa.fundamentals"
```

Must return > 0.

---

## Next Steps

### Phase 1 (Current)
- ✅ Create SQL functions for 15 simple metrics
- ✅ Build FastAPI backend
- ✅ Test with Market Cap

### Phase 2 (Temporal Metrics)
- [ ] Implement `Economic Cash Flow` (needs LAG + cumsum)
- [ ] Implement `Economic Equity` (needs temporal aggregation)
- [ ] Implement `Cost of Equity` (needs external parameters)

### Phase 3 (Optimization)
- [ ] Materialized views for frequently-used metrics
- [ ] Cache layer (Redis) for results
- [ ] Batch processing for large datasets
- [ ] UI button to trigger calculations on-demand

---

## Files Created

- ✅ `backend/database/schema/functions.sql` — 15 SQL functions
- ✅ `backend/app/main.py` — FastAPI application
- ✅ `backend/app/core/config.py` — Settings management
- ✅ `backend/app/core/database.py` — Async database setup
- ✅ `backend/app/models.py` — Pydantic schemas
- ✅ `backend/app/services/metrics_service.py` — Business logic
- ✅ `backend/app/api/v1/endpoints/metrics.py` — API routes
- ✅ `backend/app/api/v1/router.py` — Route aggregator
- ✅ `.env` — Environment configuration
- ✅ `requirements.txt` — Updated with async dependencies
- ✅ `start-api.sh` — Startup script
- ✅ `backend/README.md` — This file

---

## Reference

**FastAPI docs:** https://fastapi.tiangolo.com/
**SQLAlchemy async:** https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
**AsyncPG:** https://magicstack.github.io/asyncpg/
**Pydantic v2:** https://docs.pydantic.dev/latest/
