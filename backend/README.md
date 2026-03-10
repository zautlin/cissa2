# FastAPI Metrics Backend - Complete Implementation Guide

## Overview

This is a **production-ready FastAPI backend** for multi-phase metric calculations, supporting L1 (basic), L2 (advanced), and specialized calculations (Beta, Risk-Free Rate, Cost of Equity, Economic Profit, Future Value ECF). Built on PostgreSQL with async-first architecture.

**Key Features:**
- ✅ Async-first architecture (AsyncPG, SQLAlchemy 2.0 async)
- ✅ Clean 3-tier architecture: Repositories (data access) → Services (business logic) → API (HTTP)
- ✅ Support for multiple metric phases: L1, L2, Beta, Risk-Free Rate, Cost of Equity
- ✅ Flexible querying with `GET /api/v1/metrics/get_metrics/` endpoint
- ✅ Pydantic v2 models with strict validation
- ✅ Dependency injection pattern for database sessions
- ✅ Comprehensive error handling and structured logging
- ✅ ~283k+ metrics queryable per dataset

---

## Architecture

### Directory Structure

```
backend/
├── app/
│   ├── main.py                          # FastAPI app + lifespan
│   ├── models/
│   │   ├── __init__.py                  # Export all models
│   │   ├── schemas.py                   # Pydantic request/response schemas
│   │   ├── metrics_output.py            # SQLAlchemy ORM model for metrics_outputs table
│   │   └── ...
│   ├── core/
│   │   ├── config.py                    # Settings from .env, logger setup
│   │   └── database.py                  # AsyncPG setup, async session injection
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── metrics_repository.py        # Data access for metrics calculations
│   │   └── metrics_query_repository.py  # Data access for querying metrics (NEW)
│   ├── services/
│   │   ├── metrics_service.py           # L1 metrics calculation logic
│   │   ├── l2_metrics_service.py        # L2 metrics calculation
│   │   ├── beta_calculation_service.py  # Phase 07: Beta calculation
│   │   ├── risk_free_rate_service.py    # Phase 08: Risk-free rate calculation
│   │   ├── cost_of_equity_service.py    # Phase 09: Cost of equity (KE)
│   │   ├── economic_profit_service.py   # Phase 10a: EP, PAT_EX, XO_COST_EX, FC
│   │   └── fv_ecf_service.py            # Phase 10b: Future Value ECF metrics
│   └── api/
│       └── v1/
│           ├── router.py                # Route aggregator
│           └── endpoints/
│               └── metrics.py           # All metric endpoints
│
├── database/
│   └── schema/
│       ├── schema.sql                   # PostgreSQL schema (tables, constraints)
│       └── functions.sql                # SQL functions for Phase 1 metrics (optional)
│
├── tests/
│   └── test_metrics_query.py            # Unit tests for metrics query
│
├── requirements.txt                     # Python dependencies
├── start-api.sh                         # Startup script
└── README.md                            # This file
```

---

## Setup

### 1. Install Dependencies

```bash
cd /home/ubuntu/cissa
pip install -r requirements.txt
```

**Key async dependencies:**
- `fastapi==0.104.1+`
- `uvicorn[standard]==0.24.0+`
- `asyncpg==0.29.0+` (async PostgreSQL driver)
- `sqlalchemy[asyncio]==2.0.48+` (async ORM with async session support)
- `pydantic==2.5.0+` (v2 with strict validation)
- `pydantic-settings==2.1.0+`

### 2. Configure Environment

File: `.env` (root directory)

```env
# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cissa

# API Configuration
FASTAPI_ENV=development
LOG_LEVEL=info

# Optional Performance Tuning
METRICS_BATCH_SIZE=1000
METRICS_TIMEOUT_SECONDS=300
```

**DATABASE_URL Format:**
- Uses `postgresql+asyncpg://` driver (async-safe, NOT psycopg2)
- Format: `postgresql+asyncpg://user:password@host:port/dbname`
- Example: `postgresql+asyncpg://postgres:postgres@localhost:5432/cissa`

### 3. (Optional) Load SQL Functions

If using Phase 1 SQL functions:

```bash
psql postgresql://postgres:postgres@localhost:5432/cissa \
  -f backend/database/schema/functions.sql
```

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

**Server running at:**
- API: http://localhost:8000
- Swagger UI (interactive docs): http://localhost:8000/docs
- ReDoc (alternative docs): http://localhost:8000/redoc

---

## API Endpoints

### Health Check

**GET** `/api/v1/metrics/health`

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

---

### Query Metrics (Flexible Retrieval)

**GET** `/api/v1/metrics/get_metrics/`

Query metrics from database with optional filtering. Perfect for UI consumption and charting.

**Parameters:**
- `dataset_id` (required, UUID): Dataset to retrieve metrics from
- `parameter_set_id` (required, UUID): Parameter set used for calculations
- `ticker` (optional, string): Filter by ticker (case-insensitive)
- `metric_name` (optional, string): Filter by metric name (case-insensitive)

**Examples:**

Get all metrics:
```bash
curl "http://localhost:8000/api/v1/metrics/get_metrics/?dataset_id=c753dc4f-d547-436a-bb14-4128fa4a2281&parameter_set_id=380e6916-125e-4fb2-8c33-a13773dc51af"
```

Filter by ticker:
```bash
curl "http://localhost:8000/api/v1/metrics/get_metrics/?dataset_id=c753dc4f-d547-436a-bb14-4128fa4a2281&parameter_set_id=380e6916-125e-4fb2-8c33-a13773dc51af&ticker=1208%20HK%20Equity"
```

Filter by metric name:
```bash
curl "http://localhost:8000/api/v1/metrics/get_metrics/?dataset_id=c753dc4f-d547-436a-bb14-4128fa4a2281&parameter_set_id=380e6916-125e-4fb2-8c33-a13773dc51af&metric_name=Beta"
```

Filter by both:
```bash
curl "http://localhost:8000/api/v1/metrics/get_metrics/?dataset_id=c753dc4f-d547-436a-bb14-4128fa4a2281&parameter_set_id=380e6916-125e-4fb2-8c33-a13773dc51af&ticker=AAPL&metric_name=ECF"
```

**Response:**
```json
{
  "dataset_id": "c753dc4f-d547-436a-bb14-4128fa4a2281",
  "parameter_set_id": "380e6916-125e-4fb2-8c33-a13773dc51af",
  "results_count": 283612,
  "results": [
    {
      "dataset_id": "c753dc4f-d547-436a-bb14-4128fa4a2281",
      "parameter_set_id": "380e6916-125e-4fb2-8c33-a13773dc51af",
      "ticker": "1208 HK Equity",
      "fiscal_year": 1981,
      "metric_name": "Rf",
      "value": 0.1,
      "unit": null
    },
    {
      "dataset_id": "c753dc4f-d547-436a-bb14-4128fa4a2281",
      "parameter_set_id": "380e6916-125e-4fb2-8c33-a13773dc51af",
      "ticker": "1208 HK Equity",
      "fiscal_year": 1995,
      "metric_name": "Beta",
      "value": 1.02241,
      "unit": "%"
    }
  ],
  "filters_applied": {
    "metric_name": "Beta"
  },
  "status": "success",
  "message": "Retrieved 9189 metrics with filters: metric_name=Beta"
}
```

**Ordering:** Results are always ordered by:
1. ticker (ascending)
2. fiscal_year (ascending)
3. metric_name (ascending)

**Units:** Fetched from `metric_units` table via LEFT JOIN. May be `null` if unit not defined.

**Empty Results:** Returns HTTP 200 with empty array and informational message (not an error).

---

### Calculate L1 Metrics

**POST** `/api/v1/metrics/calculate`

Calculate Level 1 (basic) metrics for a dataset.

**Request Body:**
```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "metric_name": "Calc MC",
  "param_set_id": "660e8400-e29b-41d4-a716-446655440001"  // optional
}
```

**Supported L1 Metrics:**

| Category | Metric Names |
|----------|--------------|
| Simple Calculations | `Calc MC`, `Calc Assets`, `Calc OA`, `Calc Op Cost`, `Calc Non Op Cost`, `Calc Tax Cost`, `Calc XO Cost` |
| Temporal Metrics | `ECF`, `NON_DIV_ECF`, `EE`, `FY_TSR`, `FY_TSR_PREL` |
| Profitability Ratios | `Profit Margin`, `Op Cost Margin %`, `Non-Op Cost Margin %`, `Eff Tax Rate`, `XO Cost Margin %` |
| Other | `FA Intensity`, `Book Equity`, `ROA` |

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
  "status": "success",
  "message": "Calculated 150 Calc MC records"
}
```

---

### Calculate L2 Metrics

**POST** `/api/v1/metrics/calculate-l2`

Calculate Level 2 (complex) metrics.

**Request Body:**
```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

**Prerequisites:**
- L1 metrics must be calculated first
- dataset_id must exist in `dataset_versions`
- param_set_id must exist in `parameter_sets`

---

### Phase 07: Calculate Beta

**POST** `/api/v1/metrics/beta/calculate`

Calculate beta using 60-month rolling OLS regression on monthly returns.

**Request Body:**
```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

**Algorithm:**
1. Fetch monthly COMPANY_TSR and INDEX_TSR from fundamentals
2. Calculate 60-month rolling OLS slopes
3. Transform slopes: `adjusted = (slope × 2/3) + 1/3`
4. Filter by relative error tolerance
5. Round by beta_rounding parameter
6. Annualize and apply 4-tier fallback logic
7. Apply cost_of_equity_approach (FIXED or Floating)
8. Store in metrics_outputs

**Parameters from param_set:**
- `beta_rounding`: Rounding increment (e.g., 0.1)
- `beta_relative_error_tolerance`: Error tolerance as % (e.g., 40.0)
- `cost_of_equity_approach`: "FIXED" or "Floating"

**Response:**
```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "param_set_id": "660e8400-e29b-41d4-a716-446655440001",
  "results_count": 1234,
  "status": "success",
  "message": "Beta calculation successful: 1234 records"
}
```

**Caching:** Returns cached results if already calculated for this dataset + param_set.

---

### Phase 08: Calculate Risk-Free Rate

**POST** `/api/v1/metrics/rates/calculate`

Calculate risk-free rate (Rf, Rf_1Y, Rf_1Y_Raw) using monthly bond yields.

**Request Body:**
```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

**Algorithm:**
1. Fetch monthly RISK_FREE_RATE data (GACGB10 Index for Australia)
2. Group by fiscal year (12 months per year)
3. Calculate geometric mean: `Rf_1Y_Raw = (∏monthly_rates)^(1/12) - 1`
4. Apply rounding: `Rf_1Y = round((Rf_1Y_Raw / beta_rounding), 0) × beta_rounding`
5. Apply approach:
   - FIXED: `Rf = benchmark - risk_premium`
   - Floating: `Rf = Rf_1Y`
6. Expand to all companies and store

**Output Metrics:**
- `Rf_1Y_Raw`: Raw annualized 1-year rate (geometric mean, no rounding)
- `Rf_1Y`: Rounded annualized 1-year rate
- `Rf`: Final risk-free rate

**Parameters from param_set:**
- `bond_index_by_country`: JSON mapping country→bond ticker
- `beta_rounding`: Rounding increment
- `cost_of_equity_approach`: "FIXED" or "Floating"
- `fixed_benchmark_return_wealth_preservation`: Benchmark return
- `equity_risk_premium`: Risk premium

**Caching:** Returns cached results if already calculated.

---

### Phase 09: Calculate Cost of Equity

**POST** `/api/v1/metrics/cost-of-equity/calculate`

Calculate Cost of Equity (KE) using: `KE = Rf + Beta × RiskPremium`

**Request Body:**
```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

**Prerequisites:**
- Phase 07 (Beta) must be calculated
- Phase 08 (Risk-Free Rate) must be calculated

**Response:**
```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "param_set_id": "660e8400-e29b-41d4-a716-446655440001",
  "results_count": 1234,
  "metrics_calculated": ["Calc KE"],
  "status": "success",
  "message": "Cost of Equity calculation successful"
}
```

---

### Phase 10a: Calculate Core L2 Metrics

**POST** `/api/v1/metrics/l2-core/calculate`

Calculate Economic Profit (EP), Adjusted Profit (PAT_EX), Adjusted XO Cost (XO_COST_EX), and Franking Credit (FC).

**Request Body:**
```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "param_set_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

**Metrics Calculated:**
- `EP`: Economic Profit = `pat - (ke_open × ee_open)`
- `PAT_EX`: Adjusted Profit = `(ep / |ee_open + ke_open|) × ee_open`
- `XO_COST_EX`: Adjusted XO Cost = `patxo - pat_ex`
- `FC`: Franking Credit (conditional on `incl_franking` parameter)

**Prerequisites:**
- Phase 06 (L1 Basic Metrics) must be calculated
- Phase 09 (Cost of Equity) must be calculated

**Parameters from param_set:**
- `incl_franking`: "Yes" or "No"
- `frank_tax_rate`: Franking tax rate
- `value_franking_cr`: Franking credit value

---

### Phase 10b: Calculate Future Value ECF Metrics

**POST** `/api/v1/metrics/l2-fv-ecf/calculate`

Calculate Future Value Economic Cash Flow metrics for 1Y, 3Y, 5Y, and 10Y horizons.

**Query Parameters:**
- `dataset_id` (required, UUID)
- `param_set_id` (required, UUID)
- `incl_franking` (optional, default "Yes"): Include franking credit adjustments

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/metrics/l2-fv-ecf/calculate?dataset_id=550e8400-e29b-41d4-a716-446655440000&param_set_id=660e8400-e29b-41d4-a716-446655440001&incl_franking=Yes"
```

**Metrics Calculated:**
- `FV_ECF_1Y`: 1-year future value economic cash flow
- `FV_ECF_3Y`: 3-year future value economic cash flow
- `FV_ECF_5Y`: 5-year future value economic cash flow
- `FV_ECF_10Y`: 10-year future value economic cash flow

**Response:**
```json
{
  "status": "success",
  "total_calculated": 9189,
  "total_inserted": 36756,
  "intervals_summary": {
    "1Y": 9189,
    "3Y": 9189,
    "5Y": 9189,
    "10Y": 9189
  },
  "duration_seconds": 12.34,
  "message": "Calculated and stored 36756 FV_ECF metric values"
}
```

---

## Key Implementation Details

### 1. Async Architecture

**Database Session Injection:**
```python
async def get_metrics(
    dataset_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db)  # FastAPI injects async session
):
    repo = MetricsQueryRepository(db)
    records = await repo.get_metrics(dataset_id=dataset_id)
    return records
```

**Benefits:**
- Non-blocking database I/O using AsyncPG
- Connection pooling with configurable `pool_size`
- Handles 1000+ concurrent requests efficiently
- Full async/await support throughout stack

### 2. Three-Tier Architecture

**Repository Layer** (Data Access)
- `MetricsQueryRepository`: Query metrics with flexible filtering
- `MetricsRepository`: Insert/update metrics in database

**Service Layer** (Business Logic)
- `MetricsService`: L1 metric calculations
- `BetaCalculationService`: Phase 07 beta calculations
- `RiskFreeRateCalculationService`: Phase 08 risk-free rate
- `CostOfEquityService`: Phase 09 cost of equity
- `EconomicProfitService`: Phase 10a economic profit
- `FVECFService`: Phase 10b future value ECF

**API Layer** (HTTP Endpoints)
- Clean request/response validation
- Comprehensive error handling
- Structured logging

### 3. Results Storage

Metrics are stored in `cissa.metrics_outputs`:

```sql
CREATE TABLE cissa.metrics_outputs (
    dataset_id UUID NOT NULL,
    param_set_id UUID NOT NULL,
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    output_metric_name TEXT NOT NULL,
    output_metric_value NUMERIC NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
);
```

Batch inserts in groups of 1000+ for efficiency.

### 4. Error Handling

**Validation:**
- Pydantic v2 strict request validation
- UUID format validation
- Database constraint violations caught gracefully

**Logging:**
- Structured logging with timestamps
- All operations logged (INFO, WARNING, ERROR)
- Context included (dataset_id, param_set_id, operation)

**HTTP Responses:**
- 200 OK: Successful operations
- 400 Bad Request: Validation errors, missing prerequisites
- 500 Internal Server Error: Unexpected database/system errors

---

## Testing

### Using Swagger UI

1. Navigate to http://localhost:8000/docs
2. Expand any endpoint
3. Click "Try it out"
4. Fill in parameters and execute

### Using curl

**Get all metrics for a dataset:**
```bash
curl "http://localhost:8000/api/v1/metrics/get_metrics/?dataset_id=c753dc4f-d547-436a-bb14-4128fa4a2281&parameter_set_id=380e6916-125e-4fb2-8c33-a13773dc51af" | jq '.'
```

**Filter by metric:**
```bash
curl "http://localhost:8000/api/v1/metrics/get_metrics/?dataset_id=c753dc4f-d547-436a-bb14-4128fa4a2281&parameter_set_id=380e6916-125e-4fb2-8c33-a13773dc51af&metric_name=Beta" | jq '.results_count, .message'
```

**Verify results in database:**
```bash
psql postgresql://postgres:postgres@localhost:5432/cissa << 'EOF'
SELECT 
  metric_name,
  COUNT(*) as count,
  MIN(value) as min,
  MAX(value) as max
FROM cissa.metrics_outputs
WHERE dataset_id = 'c753dc4f-d547-436a-bb14-4128fa4a2281'
GROUP BY metric_name
ORDER BY metric_name;
EOF
```

### Run Unit Tests

```bash
pytest backend/tests/test_metrics_query.py -v
```

---

## Deployment (Production)

### Environment

Update `.env`:
```env
DATABASE_URL=postgresql+asyncpg://user:password@prod-host:5432/cissa
FASTAPI_ENV=production
LOG_LEVEL=warning
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

### Docker

**Dockerfile:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ backend/
COPY .env .env
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build and run:**
```bash
docker build -t cissa-metrics .
docker run -p 8000:8000 --env-file .env cissa-metrics
```

---

## Troubleshooting

### Issue: "Connection refused"

**Fix:** Verify PostgreSQL is running and DATABASE_URL is correct:
```bash
psql postgresql://postgres:postgres@localhost:5432/cissa -c "SELECT 1"
```

### Issue: 404 on GET /api/v1/metrics/get_metrics/

**Fix:** Ensure you're using correct dataset_id and parameter_set_id:
```bash
# Query valid dataset_id and parameter_set_id
psql postgresql://postgres:postgres@localhost:5432/cissa << 'EOF'
SELECT DISTINCT dataset_id, param_set_id 
FROM cissa.metrics_outputs 
LIMIT 5;
EOF
```

### Issue: "No metrics found" with valid UUIDs

**Fix:** Check that metrics_outputs has data:
```bash
psql postgresql://postgres:postgres@localhost:5432/cissa << 'EOF'
SELECT COUNT(*) as total_metrics FROM cissa.metrics_outputs;
EOF
```

### Issue: Slow queries on get_metrics endpoint

**Fix:** Add database indexes:
```sql
CREATE INDEX idx_metrics_outputs_dataset_param 
  ON cissa.metrics_outputs(dataset_id, param_set_id);
  
CREATE INDEX idx_metrics_outputs_ticker 
  ON cissa.metrics_outputs(ticker);
  
CREATE INDEX idx_metrics_outputs_metric_name 
  ON cissa.metrics_outputs(output_metric_name);
```

---

## Performance Notes

- **Query Performance:** 283k+ metrics return in <2 seconds with proper indexing
- **Batch Operations:** Inserts use batches of 1000+ for efficiency
- **Async Concurrency:** Handles 100+ concurrent requests
- **Database Connection Pool:** Default 10 connections, configurable
- **Memory:** Streaming results for large datasets (not loading all in memory)

---

## Files in This Implementation

### Created/Updated

- ✅ `backend/app/main.py` — FastAPI application with lifespan
- ✅ `backend/app/core/config.py` — Settings and logger setup
- ✅ `backend/app/core/database.py` — Async database setup
- ✅ `backend/app/models/__init__.py` — Export all models
- ✅ `backend/app/models/schemas.py` — Pydantic request/response schemas
- ✅ `backend/app/models/metrics_output.py` — SQLAlchemy ORM models
- ✅ `backend/app/repositories/metrics_repository.py` — Metrics data access
- ✅ `backend/app/repositories/metrics_query_repository.py` — Flexible query repository (NEW)
- ✅ `backend/app/services/metrics_service.py` — L1 metrics logic
- ✅ `backend/app/services/l2_metrics_service.py` — L2 metrics logic
- ✅ `backend/app/services/beta_calculation_service.py` — Phase 07 beta
- ✅ `backend/app/services/risk_free_rate_service.py` — Phase 08 risk-free rate
- ✅ `backend/app/services/cost_of_equity_service.py` — Phase 09 KE
- ✅ `backend/app/services/economic_profit_service.py` — Phase 10a metrics
- ✅ `backend/app/services/fv_ecf_service.py` — Phase 10b FV_ECF
- ✅ `backend/app/api/v1/endpoints/metrics.py` — All metric endpoints
- ✅ `backend/app/api/v1/router.py` — Route aggregator
- ✅ `backend/tests/test_metrics_query.py` — Unit tests
- ✅ `requirements.txt` — Updated with all dependencies
- ✅ `start-api.sh` — Startup script
- ✅ `backend/README.md` — This file

### Database Tables (Not Modified, Used)

- `cissa.dataset_versions` — Dataset metadata
- `cissa.parameter_sets` — Parameter configurations
- `cissa.fundamentals` — Raw fundamental data
- `cissa.metrics_outputs` — Calculated metrics storage
- `cissa.metric_units` — Unit definitions for metrics

---

## Next Steps

### Current State
- ✅ Phase 06: L1 metrics calculation
- ✅ Phase 07: Beta calculation
- ✅ Phase 08: Risk-free rate calculation
- ✅ Phase 09: Cost of equity calculation
- ✅ Phase 10a: Economic profit and related metrics
- ✅ Phase 10b: Future value ECF metrics
- ✅ Flexible metrics query endpoint

### Future Enhancements
- [ ] Pagination support for get_metrics endpoint (for >500k records)
- [ ] Custom sorting/grouping options
- [ ] Response format options (grouped by ticker, by metric, pivot tables)
- [ ] Export functionality (CSV, Excel, Parquet)
- [ ] Caching layer (Redis) for frequent queries
- [ ] Materialized views for common metric combinations
- [ ] Real-time metrics UI dashboard integration

---

## References

- **FastAPI:** https://fastapi.tiangolo.com/
- **SQLAlchemy Async:** https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **AsyncPG:** https://magicstack.github.io/asyncpg/
- **Pydantic v2:** https://docs.pydantic.dev/latest/
- **PostgreSQL:** https://www.postgresql.org/docs/

---

**Last Updated:** March 10, 2026
**API Version:** v1
**Status:** Production-Ready
