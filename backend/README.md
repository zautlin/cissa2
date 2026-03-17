# FastAPI Metrics Backend

A production-ready FastAPI backend for multi-phase financial metric calculations, supporting L1 (basic), L2 (advanced), and specialized metrics (Beta, Risk-Free Rate, Cost of Equity, Economic Profit, Future Value ECF).

**Key Features:**
- ✅ Async-first architecture (AsyncPG, SQLAlchemy 2.0)
- ✅ Clean 3-tier architecture: Repositories → Services → API
- ✅ ~283k+ metrics queryable per dataset
- ✅ Multi-window temporal queries (1Y, 3Y, 5Y, 10Y in one request)
- ✅ Flexible metric querying with optional filtering
- ✅ Dataset statistics with 1-hour caching
- ✅ Pydantic v2 models with strict validation
- ✅ Comprehensive error handling and structured logging

---

## Setup

### Install Dependencies
```bash
cd /home/ubuntu/cissa
pip install -r requirements.txt
```

**Key async dependencies:**
- `fastapi==0.104.1+` - Web framework
- `uvicorn[standard]==0.24.0+` - ASGI server
- `asyncpg==0.29.0+` - Async PostgreSQL driver
- `sqlalchemy[asyncio]==2.0.48+` - Async ORM
- `pydantic==2.5.0+` - Validation

### Configure Environment

File: `.env` (root directory)
```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/cissa
FASTAPI_ENV=development
LOG_LEVEL=info
```

### Start the Server

```bash
# Option A: Using startup script
./start-api.sh

# Option B: Direct uvicorn
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Server running at:**
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

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

### Dataset Statistics

**GET** `/api/v1/metrics/statistics`

Get comprehensive dataset statistics with 1-hour caching.

**Query Parameters:**
- `dataset_id` (optional, UUID): Filter by specific dataset
- If omitted: Returns statistics for ALL datasets

**Example 1: Specific Dataset**
```bash
curl "http://localhost:8000/api/v1/metrics/statistics?dataset_id=550e8400-e29b-41d4-a716-446655440000"
```

**Example 2: All Datasets**
```bash
curl "http://localhost:8000/api/v1/metrics/statistics"
```

**Response (Single Dataset):**
```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "dataset_created_at": "2026-03-16T03:59:42.223155Z",
  "country": "Australia",
  "companies": {"count": 535},
  "sectors": {"count": 12},
  "data_coverage": {"min_year": 1981, "max_year": 2023},
  "raw_metrics": {"count": 20}
}
```

**Response (All Datasets):**
```json
{
  "datasets": {
    "550e8400-e29b-41d4-a716-446655440000": {
      "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
      "country": "Australia",
      "companies": {"count": 535},
      "sectors": {"count": 12},
      "data_coverage": {"min_year": 1981, "max_year": 2023},
      "raw_metrics": {"count": 20}
    },
    "660e8400-e29b-41d4-a716-446655440001": {
      "dataset_id": "660e8400-e29b-41d4-a716-446655440001",
      "country": "USA",
      "companies": {"count": 200},
      ...
    }
  }
}
```

**Use Cases:**
- Dashboard initialization: Get dataset summary on page load
- Metadata display: Show companies, sectors, coverage, country
- Multi-dataset support: Compare across datasets

---

### Query Metrics

**GET** `/api/v1/metrics/get_metrics/`

Query metrics with optional filtering by ticker and/or metric name. Returns metrics with unit information.

**Query Parameters:**
- `dataset_id` (required, UUID)
- `parameter_set_id` (required, UUID)
- `ticker` (optional): Filter by ticker (case-insensitive)
- `metric_name` (optional): Filter by metric name (case-insensitive)

**Examples:**

All metrics for a dataset:
```bash
curl "http://localhost:8000/api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001"
```

Filter by ticker:
```bash
curl "http://localhost:8000/api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001&ticker=BHP%20AU%20Equity"
```

Filter by metric name:
```bash
curl "http://localhost:8000/api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001&metric_name=Beta"
```

Filter by both:
```bash
curl "http://localhost:8000/api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001&ticker=BHP%20AU%20Equity&metric_name=Beta"
```

**Response:**
```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "parameter_set_id": "660e8400-e29b-41d4-a716-446655440001",
  "results_count": 20,
  "results": [
    {
      "ticker": "BHP AU Equity",
      "fiscal_year": 2003,
      "metric_name": "Beta",
      "value": 1.25,
      "unit": "%"
    }
  ],
  "filters_applied": {"metric_name": "Beta"},
  "status": "success",
  "message": "Retrieved 20 metrics with filters: metric_name=Beta"
}
```

**Notes:**
- Results ordered by: ticker → fiscal_year → metric_name
- Units fetched from `metric_units` table via LEFT JOIN (may be null)
- Empty results return HTTP 200 with informational message (not an error)

---

### Ratio Metrics

**GET** `/api/v1/metrics/ratio-metrics`

Calculate financial ratios with rolling averages over temporal windows. Ratios calculated on-the-fly using SQL window functions.

**Query Parameters:**
- `metric` (required): `mb_ratio`, `roee`, `roa`, `profit_margin`, `op_cost_margin`, `non_op_cost_margin`, `xo_cost_margin`, `etr`, `fa_intensity`, `gw_intensity`, `oa_intensity`, `asset_intensity`, `econ_eq_mult`
- `tickers` (required): Comma-separated (e.g., `BHP%20AU%20Equity,RIO%20AU%20Equity`)
- `dataset_id` (required, UUID)
- `temporal_window` (optional, default=`1Y`): Single (`1Y`) or comma-separated (`1Y,3Y,5Y,10Y`)
- `param_set_id` (optional): Parameter set UUID
- `start_year` (optional): Filter from year onwards
- `end_year` (optional): Filter up to year

**Temporal Windows:**
Assuming data starts in fiscal year 2002:
- `1Y`: Annual values, first result year 2003
- `3Y`: 3-year rolling average, first result year 2005
- `5Y`: 5-year rolling average, first result year 2007
- `10Y`: 10-year rolling average, first result year 2012

**Examples:**

Single ticker, 1Y MB Ratio:
```bash
curl "http://localhost:8000/api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=BHP%20AU%20Equity&dataset_id=523eeffd-9220-4d27-927b-e418f9c21d8a&param_set_id=71a0caa6-b52c-4c5e-b550-1048b7329719"
```

Multiple tickers, single window:
```bash
curl "http://localhost:8000/api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=BHP%20AU%20Equity,RIO%20AU%20Equity&dataset_id=523eeffd-9220-4d27-927b-e418f9c21d8a&param_set_id=71a0caa6-b52c-4c5e-b550-1048b7329719&temporal_window=1Y"
```

Multiple windows in one request (multi-window feature):
```bash
curl "http://localhost:8000/api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=BHP%20AU%20Equity&dataset_id=523eeffd-9220-4d27-927b-e418f9c21d8a&param_set_id=71a0caa6-b52c-4c5e-b550-1048b7329719&temporal_window=1Y,3Y,5Y,10Y"
```

With year filter:
```bash
curl "http://localhost:8000/api/v1/metrics/ratio-metrics?metric=roee&tickers=BHP%20AU%20Equity&dataset_id=523eeffd-9220-4d27-927b-e418f9c21d8a&param_set_id=71a0caa6-b52c-4c5e-b550-1048b7329719&temporal_window=1Y&start_year=2010&end_year=2015"
```

**Response (Single Window):**
```json
{
  "metric": "mb_ratio",
  "display_name": "MB Ratio",
  "temporal_window": "1Y",
  "data": [
    {
      "ticker": "BHP AU Equity",
      "time_series": [
        {"year": 2003, "value": 1.2116482122958967},
        {"year": 2004, "value": 1.6324947466480935},
        {"year": 2005, "value": 2.1555443848919094}
      ]
    }
  ]
}
```

**Response (Multiple Windows):**
```json
{
  "metric": "mb_ratio",
  "display_name": "MB Ratio",
  "windows": [
    {
      "temporal_window": "1Y",
      "data": [
        {
          "ticker": "BHP AU Equity",
          "time_series": [
            {"year": 2003, "value": 1.2116482122958967},
            {"year": 2004, "value": 1.6324947466480935}
          ]
        }
      ]
    },
    {
      "temporal_window": "3Y",
      "data": [
        {
          "ticker": "BHP AU Equity",
          "time_series": [
            {"year": 2005, "value": 1.6902125865453}
          ]
        }
      ]
    }
  ]
}
```

**Key Benefits:**
- Single API call retrieves all windows instead of 4 separate requests
- Nested structure enables easy multi-line charting
- Reduces latency and server load
- Invalid windows skipped with warning logs

**Format Response with jq:**
```bash
curl -s "http://localhost:8000/api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=BHP%20AU%20Equity&dataset_id=523eeffd-9220-4d27-927b-e418f9c21d8a&param_set_id=71a0caa6-b52c-4c5e-b550-1048b7329719&temporal_window=1Y" | \
jq -r '.data[] | "\(.ticker)\n" + (.time_series | map("\(.year): \(.value | tostring)") | join("\n"))'
```

**Error Handling:**

Invalid metric:
```bash
curl "http://localhost:8000/api/v1/metrics/ratio-metrics?metric=invalid&tickers=BHP%20AU%20Equity&dataset_id=523eeffd-9220-4d27-927b-e418f9c21d8a"
```
Response: `HTTP 400 - Unknown metric: invalid`

Invalid temporal window:
```bash
curl "http://localhost:8000/api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=BHP%20AU%20Equity&dataset_id=523eeffd-9220-4d27-927b-e418f9c21d8a&temporal_window=2Y"
```
Response: `HTTP 422 - String should match pattern '^(1Y|3Y|5Y|10Y)$'`

---

## Metric Definitions

### Market-to-Book Ratio (MB Ratio)

**Formula:** Market Cap / Economic Equity  
**Components:** Both from `metrics_outputs` table  
**Use Case:** Valuation multiple - identifies overvalued/undervalued companies  
**Interpretation:** >1.0 = premium to book, <1.0 = discount to book

---

### Return on Economic Equity (ROEE)

**Formula:** Profit After Tax (Exclusive) / Opening Economic Equity (prior year)  
**Components:** Fundamentals (numerator) + Metrics (denominator, 1-year shifted)  
**Use Case:** Return on equity - measures profit generation relative to shareholder capital  
**Interpretation:** 0.15 = 15% return on prior-year equity

---

### Return on Assets (ROA)

**Formula:** Profit After Tax (Exclusive) / Opening Assets (prior year)  
**Components:** Fundamentals (numerator) + Metrics (denominator, 1-year shifted)  
**Use Case:** Asset efficiency - measures profit per dollar of assets  
**Interpretation:** 0.20 = 20% return on prior-year assets

---

### Profit Margin

**Formula:** Profit After Tax (Exclusive) / Revenue  
**Use Case:** Profitability - percentage of revenue becoming profit  
**Interpretation:** 0.15 = 15% profit margin

---

### Operating Cost Margin

**Formula:** Operating Costs / Revenue  
**Use Case:** Cost efficiency - percentage of revenue going to operations  
**Interpretation:** 0.40 = 40% of revenue spent on operations

---

### Non-Operating Cost Margin

**Formula:** Non-Operating Costs / Revenue  
**Use Case:** Non-core expenses - percentage of revenue from non-core costs  

---

### XO Cost Margin

**Formula:** Extraordinary Costs / Revenue  
**Use Case:** One-off expenses - percentage of revenue from extraordinary items  

---

### Effective Tax Rate (ETR)

**Formula:** Tax Costs / |Profit After Tax (Exclusive) + Extraordinary Costs|  
**Use Case:** Tax efficiency - effective tax rate paid  
**Interpretation:** 0.25 = 25% effective tax rate

---

### Fixed Asset Intensity (FA Intensity)

**Formula:** Opening Fixed Assets (prior year) / Revenue  
**Use Case:** Asset efficiency - capital intensity of fixed assets  
**Interpretation:** 0.5 = $0.50 fixed assets per $1 revenue

---

### Goodwill Intensity (GW Intensity)

**Formula:** Opening Goodwill (prior year) / Revenue  
**Use Case:** Acquisition reliance - extent of intangible asset reliance  
**Interpretation:** 0.2 = $0.20 goodwill per $1 revenue

---

### Operating Asset Intensity (OA Intensity)

**Formula:** Opening Operating Assets (prior year) / Revenue  
**Use Case:** Operational efficiency - capital intensity of operations  
**Interpretation:** 0.6 = $0.60 operating assets per $1 revenue

---

### Asset Intensity

**Formula:** Opening Total Assets (prior year) / Revenue  
**Use Case:** Capital efficiency - total capital intensity  
**Interpretation:** 1.0 = $1.00 total assets per $1 revenue

---

### Economic Equity Multiple (Econ Eq Mult)

**Formula:** Opening Total Assets (prior year) / ABS(Opening Economic Equity, prior year)  
**Use Case:** Leverage - ratio of assets to equity (capital structure)  
**Interpretation:** 3.0 = Assets are 3x the equity (3:1 leverage ratio)

---

## Parameters Management

### Get Active Parameter Set

**GET** `/api/v1/parameters/active`

```bash
curl http://localhost:8000/api/v1/parameters/active
```

---

### Get Specific Parameter Set

**GET** `/api/v1/parameters/{param_set_id}`

```bash
curl http://localhost:8000/api/v1/parameters/550e8400-e29b-41d4-a716-446655440000
```

---

### Update Parameters

**POST** `/api/v1/parameters/{param_set_id}/update`

```bash
curl -X POST http://localhost:8000/api/v1/parameters/550e8400-e29b-41d4-a716-446655440000/update \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "tax_rate_franking_credits": 35.0,
      "beta_rounding": 0.2
    },
    "set_as_active": true,
    "set_as_default": false
  }'
```

---

### Set Parameter Set as Active

**POST** `/api/v1/parameters/{param_set_id}/set-active`

```bash
curl -X POST http://localhost:8000/api/v1/parameters/550e8400-e29b-41d4-a716-446655440000/set-active
```

---

### Set Parameter Set as Default

**POST** `/api/v1/parameters/{param_set_id}/set-default`

```bash
curl -X POST http://localhost:8000/api/v1/parameters/550e8400-e29b-41d4-a716-446655440000/set-default
```

---

## Architecture

### Directory Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app + lifespan
│   ├── models/
│   │   ├── schemas.py             # Pydantic request/response models
│   │   └── metrics_output.py      # SQLAlchemy ORM model
│   ├── core/
│   │   ├── config.py              # Settings, logger setup
│   │   └── database.py            # AsyncPG setup, async session injection
│   ├── repositories/
│   │   ├── metrics_repository.py        # Metric calculations
│   │   ├── metrics_query_repository.py  # Metric queries
│   │   └── ratio_metrics_repository.py  # Ratio calculations
│   ├── services/
│   │   ├── metrics_service.py           # L1 metrics
│   │   ├── l2_metrics_service.py        # L2 metrics
│   │   ├── beta_calculation_service.py  # Phase 07
│   │   ├── risk_free_rate_service.py    # Phase 08
│   │   ├── cost_of_equity_service.py    # Phase 09
│   │   ├── economic_profit_service.py   # Phase 10a
│   │   ├── fv_ecf_service.py            # Phase 10b
│   │   └── ratio_metrics_service.py     # Ratio calculations
│   └── api/
│       └── v1/
│           ├── router.py          # Route aggregator
│           └── endpoints/
│               └── metrics.py     # All endpoints
│
├── database/
│   └── schema/
│       ├── schema.sql        # PostgreSQL schema
│       └── functions.sql     # SQL functions
│
├── tests/                    # Unit tests
├── requirements.txt          # Dependencies
├── start-api.sh             # Startup script
└── README.md                # This file
```

---

## Troubleshooting

### Database Connection Issues

Check DATABASE_URL in `.env`:
```bash
echo $DATABASE_URL
# Should output: postgresql+asyncpg://postgres:password@host:port/dbname
```

### Slow Queries

Check parameter set ID and temporal window:
```bash
# ✅ Fast: 1Y window (no rolling average)
curl "...&temporal_window=1Y"

# ⚠️ Slower: 10Y window (requires 10 years of data)
curl "...&temporal_window=10Y"
```

### Empty Results

Verify dataset has data:
```bash
curl "http://localhost:8000/api/v1/metrics/statistics?dataset_id=YOUR_ID"
```

Check if metric exists:
```bash
curl "http://localhost:8000/api/v1/metrics/get_metrics/?dataset_id=YOUR_ID&parameter_set_id=YOUR_PARAM_ID&metric_name=YOUR_METRIC"
```

---

## Performance

- **Health check:** <1ms
- **Statistics (first call):** ~800ms (database query)
- **Statistics (cached):** <1ms (in-memory, 1-hour TTL)
- **Get metrics:** Depends on result size (typically 10-100ms)
- **Ratio metrics (1Y):** 50-200ms
- **Ratio metrics (10Y):** 200-500ms
- **Multi-window ratio metrics:** Time of slowest window + ~10ms overhead

---

## Contributing

When adding new metrics:

1. Add metric definition to `metric_units.json`
2. Implement calculation in service layer
3. Add endpoint in `endpoints/metrics.py`
4. Update this README with examples
5. Add tests in `tests/`

---

## License

Proprietary - CISSA Project
