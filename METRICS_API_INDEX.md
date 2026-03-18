# CISSA Metrics API - Complete Documentation Index

This document serves as the master index for all metrics API endpoint documentation.

## Quick Navigation

### For First-Time Users
Start here: **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)**
- Main post-ingestion endpoint: `/runtime-metrics`
- Individual metric endpoints
- Example curl requests
- Key parameters summary

### For API Users & Developers
Main Reference: **[METRICS_ENDPOINTS_SUMMARY.md](METRICS_ENDPOINTS_SUMMARY.md)**
- All 13 endpoints documented in detail
- Complete parameter specifications
- Request/response schemas
- Algorithm descriptions
- Performance benchmarks

### For Source Code Navigation
Source Reference: **[ENDPOINTS_SOURCE_FILES.md](ENDPOINTS_SOURCE_FILES.md)**
- Source file locations with line numbers
- Service implementation files
- Request/response model definitions
- Database access layer files
- Test file references

---

## The Main Post-Ingestion Endpoint

**Endpoint:** `POST /api/v1/metrics/runtime-metrics`

**Query Parameters:**
- `dataset_id` (UUID, required) - Dataset to calculate metrics for
- `param_set_id` (UUID, required) - Parameter set for storing results
- `parameter_id` (UUID, optional) - Specific parameter ID (falls back to is_active)

**What it does:**
Orchestrates all Phase 3+ runtime metrics calculation in this order:
1. **Beta Rounding** - Applies parameter-specific rounding to pre-computed beta
2. **Risk-Free Rate** - Calculates Rf using rolling 12-month geometric mean of bond yields
3. **Cost of Equity** - Calculates KE = Rf + Beta × RiskPremium

**Performance:** 45-50 seconds
**Records Generated:** ~33,000 total (11,000 per metric)

**Example:**
```bash
POST /api/v1/metrics/runtime-metrics?dataset_id=550e8400-e29b-41d4-a716-446655440000&param_set_id=660e8400-e29b-41d4-a716-446655440001
```

---

## All Metrics Endpoints (13 Total)

### 1. Beta Calculation Endpoints (3)

| Endpoint | Method | Status | Performance |
|----------|--------|--------|-------------|
| `/beta/calculate` | POST | DEPRECATED | 60+ seconds |
| `/beta/calculate-from-precomputed` | POST | RECOMMENDED | <10ms or 60s |
| `/beta/precompute-for-ingestion` | POST | ETL ONLY | 60-80 seconds |

**Parameters:**
- `beta_rounding`: 0.1, 0.05, 0.01
- `beta_relative_error_tolerance`: 40.0 (%)
- `cost_of_equity_approach`: "FIXED" or "Floating"

### 2. Risk-Free Rate Endpoint (1)

| Endpoint | Method | Performance |
|----------|--------|-------------|
| `/rates/calculate` | POST | 10-15 seconds |

**Algorithm:** Rolling 12-month geometric mean of bond yields
**Parameters:**
- `cost_of_equity_approach`: "FIXED" or "FLOATING"
- `beta_rounding`: 0.005
- `benchmark`: Benchmark return (FIXED approach)
- `risk_premium`: Risk premium amount

### 3. Cost of Equity Endpoint (1)

| Endpoint | Method | Performance |
|----------|--------|-------------|
| `/cost-of-equity/calculate` | POST | 10-15 seconds |

**Formula:** KE = Rf + Beta × RiskPremium
**Parameters:**
- `equity_risk_premium`: 0.05 (5%)
- `cost_of_equity_approach`: "FIXED" or "FLOATING"
- `beta_rounding`: 0.005
- `benchmark`: Benchmark return

### 4. L2 Metrics Endpoints (2)

| Endpoint | Method | Metrics | Performance |
|----------|--------|---------|-------------|
| `/l2-core/calculate` | POST | EP, PAT_EX, XO_COST_EX, FC | 5-10 seconds |
| `/l2-fv-ecf/calculate` | POST | FV_ECF_1Y, 3Y, 5Y, 10Y | 10-15 seconds |

**Parameters:**
- `incl_franking`: "Yes" or "No"
- `frank_tax_rate`: 0.30
- `value_franking_cr`: 0.75

### 5. Query/Retrieval Endpoints (2)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/get_metrics/` | GET | Flexible metrics query |
| `/ratio-metrics` | GET | Ratio metrics with rolling windows |

**Query Parameters:**
- `dataset_id` (required)
- `parameter_set_id` (required)
- `ticker` (optional) - Filter by ticker
- `metric_name` (optional) - Filter by metric name
- `temporal_window` (optional) - 1Y, 3Y, 5Y, 10Y

### 6. L1 Metrics Endpoints (2)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/calculate` | POST | Single L1 metric calculation |
| `/calculate-l2` | POST | Batch L2 metrics calculation |

**Supported L1 Metrics (12):**
- Simple: Calc MC, Calc Assets, Calc OA, Calc Op Cost, Calc Non Op Cost, Calc Tax Cost, Calc XO Cost
- Temporal: Calc ECF, Non Div ECF, Calc EE, Calc FY TSR, Calc FY TSR PREL

### 7. Health Check Endpoint (1)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Service health check |

**Response:**
```json
{
  "status": "ok",
  "message": "Metrics service is running",
  "database": "connected"
}
```

---

## API Documentation by Category

### Beta Calculation Details
- **Main Endpoint:** POST `/runtime-metrics`
  - Sub-component: Beta Rounding
- **Standalone:** POST `/beta/calculate-from-precomputed` (RECOMMENDED)
- **Standalone:** POST `/beta/calculate` (DEPRECATED)
- **Pre-ingestion:** POST `/beta/precompute-for-ingestion`

**Key Concepts:**
- Pre-computed Beta: Calculated during Phase 2 (ingestion)
- Raw Values: Stored with `param_set_id=NULL`
- Metadata: `fixed_beta_raw`, `floating_beta_raw`, `fallback_tier_used`
- Performance: 6,000x faster with precomputed (milliseconds vs minutes)

### Risk-Free Rate Details
- **Calculation:** Rolling 12-month geometric mean
- **Data Source:** Bond index (GACGB10 Index for Australia)
- **Approaches:**
  - FIXED: Benchmark - Risk Premium (static)
  - FLOATING: Rf_1Y (dynamic, year-specific)
- **Rounding:** Applied based on beta_rounding parameter

### Cost of Equity Details
- **Formula:** KE = Rf + Beta × RiskPremium
- **Dependencies:**
  - Pre-computed Beta (Phase 2)
  - Runtime Risk-Free Rate (Phase 3)
- **Execution:** Sequential after Beta + Rf completion

### L2 Metrics Details
- **Core Metrics (Phase 10a):**
  - EP: Economic Profit = pat - (ke_open × ee_open)
  - PAT_EX: Adjusted Profit
  - XO_COST_EX: Adjusted XO Cost
  - FC: Franking Credit (conditional on incl_franking)

- **FV_ECF Metrics (Phase 10b):**
  - 1-year, 3-year, 5-year, 10-year horizons
  - Includes optional franking adjustments

---

## Source Code Organization

```
/home/ubuntu/cissa/backend/app/
├── api/v1/
│   ├── endpoints/
│   │   ├── metrics.py (1176 lines) - ALL ENDPOINTS
│   │   ├── orchestration.py - L1 orchestration
│   │   ├── parameters.py - Parameter management
│   │   └── statistics.py - Statistics endpoints
│   └── router.py - Router aggregation
├── services/
│   ├── runtime_metrics_orchestration_service.py (342 lines)
│   ├── beta_rounding_service.py
│   ├── beta_calculation_service.py
│   ├── beta_precomputation_service.py
│   ├── risk_free_rate_service.py (1087 lines)
│   ├── cost_of_equity_service.py (604+ lines)
│   ├── economic_profit_service.py
│   ├── fv_ecf_service.py
│   ├── metrics_service.py
│   ├── l2_metrics_service.py
│   └── ratio_metrics_service.py
├── models/
│   └── schemas.py (263 lines) - All request/response models
├── repositories/
│   ├── metrics_query_repository.py
│   ├── metrics_repository.py
│   ├── parameter_repository.py
│   └── [other repositories]
└── main.py - FastAPI app setup
```

---

## Parameter Sets

Parameter sets control all metric calculations. Key parameters:

**Beta Parameters:**
```json
{
  "beta_rounding": 0.1,
  "beta_relative_error_tolerance": 40.0,
  "cost_of_equity_approach": "Floating"
}
```

**Risk-Free Rate Parameters:**
```json
{
  "cost_of_equity_approach": "FLOATING",
  "beta_rounding": 0.005,
  "benchmark": 0.05,
  "risk_premium": 0.04
}
```

**Cost of Equity Parameters:**
```json
{
  "equity_risk_premium": 0.05,
  "cost_of_equity_approach": "FLOATING",
  "beta_rounding": 0.005
}
```

**L2 Metrics Parameters:**
```json
{
  "incl_franking": "Yes",
  "frank_tax_rate": 0.30,
  "value_franking_cr": 0.75
}
```

---

## Execution Phases

**Phase 1-2:** L1 Basic Metrics
- Uses: `/api/v1/metrics/calculate`
- Output: Stored in metrics_outputs

**Phase 2:** Beta Pre-computation
- Uses: `/api/v1/metrics/beta/precompute-for-ingestion`
- Executes during ETL ingestion
- Stores with `param_set_id=NULL`

**Phase 3+:** Runtime Metrics (PRIMARY POST-INGESTION)
- Uses: `/api/v1/metrics/runtime-metrics`
- Calculates: Beta (rounded), Rf, KE
- Execution time: 45-50 seconds

**Phase 10a:** Core L2 Metrics
- Uses: `/api/v1/metrics/l2-core/calculate`
- Depends on: L1 metrics + KE

**Phase 10b:** FV_ECF Metrics
- Uses: `/api/v1/metrics/l2-fv-ecf/calculate`
- Depends on: L1 metrics + KE

---

## Common Response Fields

**Success Response:**
```json
{
  "status": "success",
  "dataset_id": "UUID",
  "param_set_id": "UUID",
  "results_count": 11000,
  "message": "..."
}
```

**Status Values:**
- `success` - Operation completed successfully
- `error` - Operation failed (includes error message)
- `cached` - Results returned from cache (beta only)
- `precomputed` - Using pre-computed values (beta only)
- `fallback_legacy` - Fell back to legacy calculation (beta only)

---

## Performance Benchmarks

| Operation | Duration | Records | Rate |
|-----------|----------|---------|------|
| Beta (precomputed) | <10ms | 11,000 | instant |
| Beta (legacy) | 60s | 11,000 | 183/sec |
| Risk-Free Rate | 12s | 11,000 | 917/sec |
| Cost of Equity | 13s | 11,000 | 846/sec |
| L2 Core | 7s | varied | fast |
| FV_ECF | 12s | 36,756 | 3,063/sec |
| All Runtime Metrics | 50s | 33,000 | 660/sec |

---

## Quick Start for Integration

### Step 1: Prepare Data
```bash
# Ensure dataset_id and param_set_id exist in database
```

### Step 2: Calculate Runtime Metrics
```bash
curl -X POST "http://localhost:8000/api/v1/metrics/runtime-metrics?dataset_id=<UUID>&param_set_id=<UUID>"
```

### Step 3: Calculate L2 Metrics (Optional)
```bash
curl -X POST "http://localhost:8000/api/v1/metrics/l2-core/calculate" \
  -H "Content-Type: application/json" \
  -d '{"dataset_id": "<UUID>", "param_set_id": "<UUID>"}'
```

### Step 4: Query Results
```bash
curl "http://localhost:8000/api/v1/metrics/get_metrics/?dataset_id=<UUID>&parameter_set_id=<UUID>&metric_name=Calc%20KE"
```

---

## File References

For detailed information, see:

1. **Quick Reference** → `QUICK_REFERENCE.md`
   - Fast lookup guide with examples

2. **Full Documentation** → `METRICS_ENDPOINTS_SUMMARY.md`
   - Complete endpoint specifications
   - Algorithm details
   - Response schemas

3. **Source Files** → `ENDPOINTS_SOURCE_FILES.md`
   - File locations and line numbers
   - Function references
   - Database access details

---

## Support & Questions

For questions about specific endpoints, refer to:
1. Endpoint docstrings in `/backend/app/api/v1/endpoints/metrics.py`
2. Service implementations in `/backend/app/services/`
3. Request/response models in `/backend/app/models/schemas.py`

Last Updated: 2026-03-17
