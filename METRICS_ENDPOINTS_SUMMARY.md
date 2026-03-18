# CISSA Metrics API Endpoints - Comprehensive Summary

## Overview
The CISSA backend provides comprehensive endpoints for calculating and querying metrics across multiple phases. All endpoints are under the `/api/v1/metrics` prefix.

---

## 1. RUNTIME METRICS ORCHESTRATION ENDPOINT

### POST /runtime-metrics
**Purpose:** Orchestrate Phase 3+ runtime metrics calculation (main entry point for post-ingestion metrics)

**HTTP Method:** POST

**URL Path:** `/api/v1/metrics/runtime-metrics`

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `dataset_id` | UUID | Yes | Dataset ID to calculate metrics for |
| `param_set_id` | UUID | Yes | Parameter set ID for storing results |
| `parameter_id` | UUID | No | Specific parameter ID to use (optional, falls back to is_active=true) |

**Request Format:** Query parameters only (no request body)

**Execution Order:**
1. Beta Rounding (parallel with Risk-Free Rate)
2. Risk-Free Rate (parallel with Beta Rounding)
3. Cost of Equity (sequential, depends on Beta & Rf)

**Response Schema:**
```json
{
  "success": boolean,
  "execution_time_seconds": float,
  "dataset_id": UUID,
  "param_set_id": UUID,
  "parameter_id": UUID,
  "timestamp": ISO 8601 timestamp,
  "metrics_completed": {
    "beta_rounding": {
      "status": "success|error",
      "records_inserted": integer,
      "time_seconds": float,
      "message": string
    },
    "risk_free_rate": {
      "status": "success|error",
      "records_inserted": integer,
      "time_seconds": float,
      "message": string
    },
    "cost_of_equity": {
      "status": "success|error",
      "records_inserted": integer,
      "time_seconds": float,
      "message": string
    }
  },
  "error": string (if failed)
}
```

**Expected Results:** ~33,000 total records (11,000 per metric)

**Example Request:**
```bash
POST /api/v1/metrics/runtime-metrics?dataset_id=550e8400-e29b-41d4-a716-446655440000&param_set_id=660e8400-e29b-41d4-a716-446655440001
```

---

## 2. BETA CALCULATION ENDPOINTS

### POST /beta/calculate (DEPRECATED)
**Purpose:** Calculate beta using legacy runtime calculation (60+ seconds)

**HTTP Method:** POST

**URL Path:** `/api/v1/metrics/beta/calculate`

**Request Body:**
```json
{
  "dataset_id": "UUID (required)",
  "param_set_id": "UUID (required)"
}
```

**Parameters Used from param_set:**
- `beta_rounding`: Rounding increment (e.g., 0.1)
- `beta_relative_error_tolerance`: Error tolerance as % (e.g., 40.0)
- `cost_of_equity_approach`: "FIXED" or "Floating"

**Response Schema:**
```json
{
  "dataset_id": UUID,
  "param_set_id": UUID,
  "results_count": integer,
  "results": [
    {
      "ticker": string,
      "fiscal_year": integer,
      "value": float
    }
  ],
  "status": "success|error|cached",
  "message": string
}
```

**Note:** DEPRECATED - Use `/beta/calculate-from-precomputed` instead for 6,000x faster performance

---

### POST /beta/calculate-from-precomputed (RECOMMENDED)
**Purpose:** Calculate beta using pre-computed values (instant <10ms when precomputed exists)

**HTTP Method:** POST

**URL Path:** `/api/v1/metrics/beta/calculate-from-precomputed`

**Request Body:**
```json
{
  "dataset_id": "UUID (required)",
  "param_set_id": "UUID (required)"
}
```

**Parameters Used from param_set:**
- `beta_rounding`: Rounding increment (e.g., 0.1, 0.05, 0.01)
- `cost_of_equity_approach`: "FIXED" or "Floating"

**Algorithm:**
1. Check if pre-computed Beta exists (param_set_id=NULL in metrics_outputs)
2. If YES: Apply user-selected rounding + approach, store with param_set_id, return instantly
3. If NO: Fall back to legacy runtime calculation (60 seconds)

**Performance:**
- With pre-computed Beta: <10 milliseconds
- Without pre-computed Beta: ~60 seconds (fallback to legacy)
- Expected speedup: 6,000x faster

**Response Schema:**
```json
{
  "dataset_id": UUID,
  "param_set_id": UUID,
  "results_count": integer,
  "results": [],
  "status": "precomputed|fallback_legacy|error",
  "message": string
}
```

---

### POST /beta/precompute-for-ingestion
**Purpose:** Pre-compute Beta for entire dataset during ETL ingestion (Stage 3)

**HTTP Method:** POST

**URL Path:** `/api/v1/metrics/beta/precompute-for-ingestion`

**Request Body:**
```json
{
  "dataset_id": "UUID (required)",
  "param_set_id": "UUID (required)"
}
```

**Parameters Used:**
- `beta_relative_error_tolerance`: Error tolerance as % (from param_set)

**Algorithm:**
1. Calculate 60-month rolling OLS slopes
2. Transform slopes: adjusted = (slope × 2/3) + 1/3
3. Filter by relative error tolerance
4. DO NOT ROUND - store raw transformed values
5. Annualize: calculate sector medians
6. Apply 4-tier fallback logic
7. Calculate BOTH approaches (FIXED and Floating)
8. Store with param_set_id=NULL and comprehensive metadata

**Metadata Stored:**
- `fixed_beta_raw`: Unrounded FIXED approach beta
- `floating_beta_raw`: Unrounded Floating approach beta
- `spot_slope_raw`: Raw unrounded slope value
- `fallback_tier_used`: Which fallback tier was used (1-4)
- `monthly_raw_slopes`: Array of monthly slopes

**Expected Response Time:** 60-80 seconds

**Response Schema:**
```json
{
  "dataset_id": UUID,
  "param_set_id": UUID,
  "results_count": integer,
  "status": "success|error",
  "message": string
}
```

---

## 3. RISK-FREE RATE ENDPOINT

### POST /rates/calculate
**Purpose:** Calculate risk-free rate at runtime using monthly bond yields

**HTTP Method:** POST

**URL Path:** `/api/v1/metrics/rates/calculate`

**Request Body:**
```json
{
  "dataset_id": "UUID (required)",
  "param_set_id": "UUID (required)"
}
```

**Risk-Free Rate Calculation Algorithm:**
1. Fetch monthly RISK_FREE_RATE data (GACGB10 Index for Australia)
2. Calculate rolling 12-month geometric mean: `Rf_1Y_Raw = (∏monthly_rates)^(1/12) - 1`
3. Apply rounding: `Rf_1Y = round((Rf_1Y_Raw / beta_rounding), 0) × beta_rounding`
4. Apply approach:
   - FIXED: `Rf = benchmark - risk_premium` (static)
   - FLOATING: `Rf = Rf_1Y` (dynamic, uses latest monthly data)

**Parameters Used from param_set:**
- `cost_of_equity_approach`: "FIXED" or "FLOATING"
- `beta_rounding`: Rounding increment (e.g., 0.005 for 0.5%)
- `benchmark`: Benchmark return for FIXED approach
- `risk_premium`: Risk premium amount

**Response Schema:**
```json
{
  "dataset_id": UUID,
  "param_set_id": UUID,
  "value": float,
  "status": "success|error",
  "timestamp": ISO 8601,
  "message": string,
  "results_count": integer (optional),
  "results": [] (optional)
}
```

---

## 4. COST OF EQUITY ENDPOINT

### POST /cost-of-equity/calculate
**Purpose:** Calculate Cost of Equity: KE = Rf + Beta × RiskPremium

**HTTP Method:** POST

**URL Path:** `/api/v1/metrics/cost-of-equity/calculate`

**Request Body:**
```json
{
  "dataset_id": "UUID (required)",
  "param_set_id": "UUID (required)"
}
```

**Calculation Flow:**
1. Fetch pre-computed Beta from Phase 2 (param_set_id=NULL)
2. Apply param_set-specific rounding and approach
3. Calculate Risk-Free Rate at runtime
4. Calculate KE = Rf + Beta × RiskPremium

**Prerequisites:**
- Phase 2 (Beta pre-computation) must be completed
- Monthly bond yield data must exist in fundamentals
- param_set_id must exist with proper parameter overrides

**Parameters Used from param_set:**
- `cost_of_equity_approach`: "FIXED" or "FLOATING"
- `equity_risk_premium`: Risk premium multiplier (e.g., 0.05 for 5%)
- `beta_rounding`: Rounding for Beta (e.g., 0.005 for 0.5%)
- `benchmark`: Benchmark return for FIXED Rf approach

**Response Schema:**
```json
{
  "dataset_id": UUID,
  "param_set_id": UUID,
  "value": float,
  "metrics_calculated": ["Calc KE"],
  "status": "success|error",
  "timestamp": ISO 8601,
  "message": string
}
```

---

## 5. L2 CORE METRICS ENDPOINT

### POST /l2-core/calculate
**Purpose:** Calculate Phase 10a Core L2 Metrics: EP, PAT_EX, XO_COST_EX, FC

**HTTP Method:** POST

**URL Path:** `/api/v1/metrics/l2-core/calculate`

**Request Body:**
```json
{
  "dataset_id": "UUID (required)",
  "param_set_id": "UUID (required)"
}
```

**Metrics Calculated:**
- EP: Economic Profit = pat - (ke_open × ee_open)
- PAT_EX: Adjusted Profit = (ep / |ee_open + ke_open|) × ee_open
- XO_COST_EX: Adjusted XO Cost = patxo - pat_ex
- FC: Franking Credit = conditionally based on incl_franking parameter

**Prerequisites:**
- Phase 06 (L1 Basic Metrics) must be calculated
- Phase 09 (Cost of Equity) must be calculated

**Parameters Used from param_set:**
- `incl_franking`: "Yes" or "No"
- `frank_tax_rate`: Franking tax rate (e.g., 0.30)
- `value_franking_cr`: Franking credit value (e.g., 0.75)

**Response Schema:**
```json
{
  "dataset_id": UUID,
  "param_set_id": UUID,
  "results_count": integer,
  "metrics_calculated": ["EP", "PAT_EX", "XO_COST_EX", "FC"],
  "status": "success|error",
  "message": string
}
```

---

## 6. FV_ECF METRICS ENDPOINT

### POST /l2-fv-ecf/calculate
**Purpose:** Calculate Phase 10b Future Value Economic Cash Flow (FV_ECF) Metrics

**HTTP Method:** POST

**URL Path:** `/api/v1/metrics/l2-fv-ecf/calculate`

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `dataset_id` | UUID | Yes | Dataset ID |
| `param_set_id` | UUID | Yes | Parameter set ID |
| `incl_franking` | string | No | "Yes" (include franking) or "No" (exclude), default="Yes" |

**Metrics Calculated:**
- FV_ECF_1Y: 1-year future value economic cash flow
- FV_ECF_3Y: 3-year future value economic cash flow
- FV_ECF_5Y: 5-year future value economic cash flow
- FV_ECF_10Y: 10-year future value economic cash flow

**Prerequisites:**
- Phase 06 (L1 Basic Metrics) must be calculated
- Phase 09 (Cost of Equity) must be calculated

**Parameters Used from param_set:**
- `frank_tax_rate`: Franking tax rate
- `value_franking_cr`: Franking credit value

**Response Schema:**
```json
{
  "status": "success|error",
  "total_calculated": integer,
  "total_inserted": integer,
  "intervals_summary": {
    "1Y": integer,
    "3Y": integer,
    "5Y": integer,
    "10Y": integer
  },
  "duration_seconds": float,
  "message": string
}
```

---

## 7. METRICS QUERY/RETRIEVAL ENDPOINTS

### GET /get_metrics/
**Purpose:** Query metrics from database with flexible filtering

**HTTP Method:** GET

**URL Path:** `/api/v1/metrics/get_metrics/`

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `dataset_id` | UUID | Yes | Dataset ID |
| `parameter_set_id` | UUID | Yes | Parameter set ID |
| `ticker` | string | No | Filter by ticker symbol (case-insensitive, e.g., "AAPL") |
| `metric_name` | string | No | Filter by metric name (case-insensitive, e.g., "Calc ECF", "Beta") |

**Response Schema:**
```json
{
  "dataset_id": UUID,
  "parameter_set_id": UUID,
  "results_count": integer,
  "results": [
    {
      "dataset_id": UUID,
      "parameter_set_id": UUID,
      "ticker": string,
      "fiscal_year": integer,
      "metric_name": string,
      "value": float,
      "unit": string (nullable)
    }
  ],
  "filters_applied": {
    "ticker": string (optional),
    "metric_name": string (optional)
  },
  "status": "success|error",
  "message": string (nullable)
}
```

**Example Requests:**
```
GET /api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001

GET /api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001&ticker=AAPL

GET /api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001&metric_name=Calc ECF

GET /api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001&ticker=AAPL&metric_name=Calc ECF
```

---

### GET /ratio-metrics
**Purpose:** Calculate ratio metrics with rolling averages

**HTTP Method:** GET

**URL Path:** `/api/v1/metrics/ratio-metrics`

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `metric` | string | Yes | Metric ID (e.g., 'mb_ratio') |
| `tickers` | string | Yes | Comma-separated ticker list (e.g., 'AAPL,MSFT') |
| `dataset_id` | UUID | Yes | Dataset ID |
| `temporal_window` | string | No | Temporal window(s): single (1Y) or comma-separated (1Y,3Y,5Y), default="1Y" |
| `param_set_id` | UUID | No | Parameter set ID (defaults to base_case) |
| `start_year` | integer | No | Optional start year filter |
| `end_year` | integer | No | Optional end year filter |

**Supported Metrics:**
- `mb_ratio`: Market-to-Book Ratio (Market Cap / Economic Equity)

**Temporal Windows:**
- 1Y: Annual values (current year only)
- 3Y: 3-year rolling average (starts year 2003 if data from 2001)
- 5Y: 5-year rolling average (starts year 2005)
- 10Y: 10-year rolling average (starts year 2010)

**Response Schema (Single Window):**
```json
{
  "metric": string,
  "tickers": [string],
  "temporal_window": string,
  "results": [
    {
      "ticker": string,
      "fiscal_year": integer,
      "value": float
    }
  ]
}
```

**Response Schema (Multi-Window):**
```json
{
  "metric": string,
  "tickers": [string],
  "temporal_windows": [string],
  "results_by_window": {
    "1Y": [...],
    "3Y": [...],
    "5Y": [...]
  }
}
```

**Example Requests:**
```
GET /api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=AAPL,MSFT&temporal_window=3Y&dataset_id=...

GET /api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=AAPL,MSFT&temporal_window=1Y,3Y,5Y&dataset_id=...
```

---

## 8. BASIC L1 METRICS ENDPOINTS

### POST /calculate
**Purpose:** Calculate a single L1 metric for a dataset

**HTTP Method:** POST

**URL Path:** `/api/v1/metrics/calculate`

**Request Body:**
```json
{
  "dataset_id": "UUID (required)",
  "metric_name": "string (required)",
  "param_set_id": "UUID (optional, for parameter-sensitive metrics)"
}
```

**Supported L1 Metrics:**

**Simple Metrics (7):** No parameter dependencies
- Calc MC (Market Capitalization)
- Calc Assets
- Calc OA (Operating Assets)
- Calc Op Cost (Operating Cost)
- Calc Non Op Cost (Non-Operating Cost)
- Calc Tax Cost
- Calc XO Cost (Extraordinary Cost)

**Temporal Metrics (5):** Time-dependent calculations
- Calc ECF (Economic Cash Flow)
- Non Div ECF
- Calc EE (Economic Equity)
- Calc FY TSR (requires param_set_id)
- Calc FY TSR PREL (requires param_set_id)

**Response Schema:**
```json
{
  "dataset_id": UUID,
  "metric_name": string,
  "results_count": integer,
  "results": [
    {
      "ticker": string,
      "fiscal_year": integer,
      "value": float
    }
  ],
  "status": "success|error",
  "message": string (nullable)
}
```

---

### POST /calculate-l2 (L2 Metrics)
**Purpose:** Calculate L2 metrics for a dataset and parameter set

**HTTP Method:** POST

**URL Path:** `/api/v1/metrics/calculate-l2`

**Request Body:**
```json
{
  "dataset_id": "UUID (required)",
  "param_set_id": "UUID (required)"
}
```

**Prerequisites:**
- L1 metrics must be calculated and in metrics_outputs table
- dataset_id must exist in dataset_versions
- param_set_id must exist in parameter_sets

**Parameters Used:**
- `country`: "AU" (hardcoded as TODO)
- `risk_premium`: 0.06 (hardcoded as TODO)

**Response Schema:**
```json
{
  "dataset_id": UUID,
  "param_set_id": UUID,
  "results_count": integer,
  "status": "success|error",
  "message": string
}
```

---

## 9. HEALTH CHECK ENDPOINT

### GET /health
**Purpose:** Health check for metrics service

**HTTP Method:** GET

**URL Path:** `/api/v1/metrics/health`

**Response Schema:**
```json
{
  "status": "ok",
  "message": "Metrics service is running",
  "database": "connected"
}
```

---

## 10. DEPRECATED ENDPOINTS

### GET /dataset/{dataset_id}/metrics/{metric_name}
**Status:** DEPRECATED

**Purpose:** Get or calculate a metric (GET endpoint for convenience)

**HTTP Method:** GET

**URL Path:** `/api/v1/metrics/dataset/{dataset_id}/metrics/{metric_name}`

**Path Parameters:**
- `dataset_id`: Dataset UUID
- `metric_name`: Metric name (e.g., "Calc MC", "Calc ECF")

**Note:** Please use `GET /api/v1/metrics/get_metrics/` instead

---

## SUMMARY TABLE

| Endpoint | HTTP | URL | Purpose | Post-Ingestion? |
|----------|------|-----|---------|-----------------|
| /runtime-metrics | POST | /api/v1/metrics/runtime-metrics | **Main orchestration for Phase 3+ runtime metrics** | **YES** |
| /beta/calculate-from-precomputed | POST | /api/v1/metrics/beta/calculate-from-precomputed | Fast beta calculation (instant/60s fallback) | YES |
| /beta/precompute-for-ingestion | POST | /api/v1/metrics/beta/precompute-for-ingestion | Pre-compute beta during ETL | NO (ingestion-only) |
| /rates/calculate | POST | /api/v1/metrics/rates/calculate | Runtime risk-free rate calculation | YES |
| /cost-of-equity/calculate | POST | /api/v1/metrics/cost-of-equity/calculate | Runtime cost of equity (KE = Rf + β×RP) | YES |
| /l2-core/calculate | POST | /api/v1/metrics/l2-core/calculate | Economic profit and related L2 metrics | YES |
| /l2-fv-ecf/calculate | POST | /api/v1/metrics/l2-fv-ecf/calculate | Future value economic cash flow metrics | YES |
| /get_metrics/ | GET | /api/v1/metrics/get_metrics/ | Query metrics with flexible filtering | YES (retrieval) |
| /ratio-metrics | GET | /api/v1/metrics/ratio-metrics | Calculate ratio metrics with rolling windows | YES (retrieval) |
| /calculate | POST | /api/v1/metrics/calculate | Basic L1 metric calculation | NO (Phase 1) |
| /calculate-l2 | POST | /api/v1/metrics/calculate-l2 | L2 metrics batch calculation | NO (Phase 2) |
| /health | GET | /api/v1/metrics/health | Service health check | - |

---

## KEY PARAMETERS ACROSS ENDPOINTS

### Beta Calculation Parameters
- `beta_rounding`: Rounding increment (e.g., 0.1, 0.05, 0.01)
- `beta_relative_error_tolerance`: Error tolerance as % (e.g., 40.0)
- `cost_of_equity_approach`: "FIXED" or "Floating"

### Risk-Free Rate Parameters
- `cost_of_equity_approach`: "FIXED" or "FLOATING"
- `beta_rounding`: Rounding increment
- `benchmark`: Benchmark return (for FIXED approach)
- `risk_premium`: Risk premium amount

### Cost of Equity Parameters
- `equity_risk_premium`: Risk premium multiplier (e.g., 0.05 for 5%)
- `cost_of_equity_approach`: "FIXED" or "FLOATING"
- `beta_rounding`: Rounding for Beta
- `benchmark`: Benchmark return

### L2 Metrics Parameters
- `incl_franking`: "Yes" or "No"
- `frank_tax_rate`: Franking tax rate (e.g., 0.30)
- `value_franking_cr`: Franking credit value (e.g., 0.75)

---

## EXECUTION PERFORMANCE

| Endpoint | Expected Duration | Notes |
|----------|------------------|-------|
| /runtime-metrics | 45-50 seconds | Full orchestration of Beta + Rf + KE |
| /beta/calculate-from-precomputed | <10ms or 60s | Instant with precomputed, fallback to legacy |
| /beta/precompute-for-ingestion | 60-80 seconds | Pre-ingestion computation only |
| /rates/calculate | 10-15 seconds | Runtime calculation for ~11k records |
| /cost-of-equity/calculate | 10-15 seconds | Runtime calculation for ~11k records |
| /l2-core/calculate | 5-10 seconds | Economic profit and related metrics |
| /l2-fv-ecf/calculate | 10-15 seconds | ~9k records across 4 intervals |

---

## PHASE MAPPING

- **Phase 1 & 2:** L1 Basic Metrics (via /calculate)
- **Phase 2:** Pre-computed Beta (via /beta/precompute-for-ingestion)
- **Phase 3+:** Runtime Metrics Calculation (via /runtime-metrics)
  - Beta Rounding
  - Risk-Free Rate
  - Cost of Equity
- **Phase 10a:** Core L2 Metrics (via /l2-core/calculate)
- **Phase 10b:** FV_ECF Metrics (via /l2-fv-ecf/calculate)

