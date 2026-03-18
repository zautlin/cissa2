# CISSA Metrics API - Quick Reference Guide

## The Main Post-Ingestion Endpoint

```bash
POST /api/v1/metrics/runtime-metrics?dataset_id=<UUID>&param_set_id=<UUID>
```

This single endpoint orchestrates all Phase 3+ runtime metrics:
1. **Beta Rounding** - Applies parameter set rounding to pre-computed beta
2. **Risk-Free Rate** - Calculates Rf based on bond yields
3. **Cost of Equity** - Computes KE = Rf + Beta × RiskPremium

**Response includes:**
- Execution time: 45-50 seconds
- Records per metric: ~11,000
- Total records: ~33,000
- Detailed status for each sub-metric

---

## Individual Metric Endpoints

### Beta Calculation
```bash
POST /api/v1/metrics/beta/calculate-from-precomputed
Body: {"dataset_id": "UUID", "param_set_id": "UUID"}
Performance: <10ms (with precomputed) or 60s (fallback)
```

### Risk-Free Rate
```bash
POST /api/v1/metrics/rates/calculate
Body: {"dataset_id": "UUID", "param_set_id": "UUID"}
Performance: 10-15 seconds
```

### Cost of Equity
```bash
POST /api/v1/metrics/cost-of-equity/calculate
Body: {"dataset_id": "UUID", "param_set_id": "UUID"}
Performance: 10-15 seconds
```

### Core L2 Metrics (EP, PAT_EX, XO_COST_EX, FC)
```bash
POST /api/v1/metrics/l2-core/calculate
Body: {"dataset_id": "UUID", "param_set_id": "UUID"}
Performance: 5-10 seconds
```

### FV_ECF Metrics (1Y, 3Y, 5Y, 10Y)
```bash
POST /api/v1/metrics/l2-fv-ecf/calculate?dataset_id=<UUID>&param_set_id=<UUID>&incl_franking=Yes
Performance: 10-15 seconds
```

---

## Query Endpoints

### Get All Metrics
```bash
GET /api/v1/metrics/get_metrics/?dataset_id=<UUID>&parameter_set_id=<UUID>
```

### Get Metrics by Ticker
```bash
GET /api/v1/metrics/get_metrics/?dataset_id=<UUID>&parameter_set_id=<UUID>&ticker=AAPL
```

### Get Metrics by Name
```bash
GET /api/v1/metrics/get_metrics/?dataset_id=<UUID>&parameter_set_id=<UUID>&metric_name=Calc ECF
```

### Get Ratio Metrics
```bash
GET /api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=AAPL,MSFT&dataset_id=<UUID>&temporal_window=3Y
```

---

## Key Parameters by Endpoint

### Beta Endpoints
- `beta_rounding` - Rounding increment (0.1, 0.05, 0.01)
- `beta_relative_error_tolerance` - Error tolerance % (40.0)
- `cost_of_equity_approach` - "FIXED" or "Floating"

### Risk-Free Rate Endpoint
- `cost_of_equity_approach` - "FIXED" or "FLOATING"
- `beta_rounding` - Rounding increment (0.005)
- `benchmark` - Benchmark return (for FIXED approach)
- `risk_premium` - Risk premium amount

### Cost of Equity Endpoint
- `equity_risk_premium` - Risk premium (0.05 for 5%)
- `cost_of_equity_approach` - "FIXED" or "FLOATING"
- `beta_rounding` - Beta rounding (0.005)
- `benchmark` - Benchmark return

### L2 Endpoints
- `incl_franking` - "Yes" or "No"
- `frank_tax_rate` - Franking tax rate (0.30)
- `value_franking_cr` - Franking credit value (0.75)

---

## Example Workflow: Complete Post-Ingestion Metrics

```bash
# 1. Calculate all runtime metrics at once
curl -X POST "http://localhost:8000/api/v1/metrics/runtime-metrics?dataset_id=550e8400-e29b-41d4-a716-446655440000&param_set_id=660e8400-e29b-41d4-a716-446655440001"

# Response will show:
# - beta_rounding: status, records_inserted, time_seconds
# - risk_free_rate: status, records_inserted, time_seconds
# - cost_of_equity: status, records_inserted, time_seconds

# 2. Query results
curl "http://localhost:8000/api/v1/metrics/get_metrics/?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001&metric_name=Calc KE"

# 3. Calculate L2 metrics
curl -X POST "http://localhost:8000/api/v1/metrics/l2-core/calculate" \
  -H "Content-Type: application/json" \
  -d '{"dataset_id": "550e8400-e29b-41d4-a716-446655440000", "param_set_id": "660e8400-e29b-41d4-a716-446655440001"}'

# 4. Calculate FV_ECF
curl -X POST "http://localhost:8000/api/v1/metrics/l2-fv-ecf/calculate?dataset_id=550e8400-e29b-41d4-a716-446655440000&param_set_id=660e8400-e29b-41d4-a716-446655440001&incl_franking=Yes"
```

---

## Endpoint Summary Table

| Purpose | Endpoint | Method | Time |
|---------|----------|--------|------|
| All Phase 3+ metrics | `/runtime-metrics` | POST | 45-50s |
| Beta only | `/beta/calculate-from-precomputed` | POST | <10ms |
| Risk-free rate only | `/rates/calculate` | POST | 10-15s |
| Cost of equity only | `/cost-of-equity/calculate` | POST | 10-15s |
| Core L2 metrics | `/l2-core/calculate` | POST | 5-10s |
| FV_ECF metrics | `/l2-fv-ecf/calculate` | POST | 10-15s |
| Query metrics | `/get_metrics/` | GET | <1s |
| Query ratio metrics | `/ratio-metrics` | GET | <1s |

---

## Important Notes

1. **Runtime Metrics Orchestration is the primary endpoint** for post-ingestion calculations
   - All three metrics (Beta, Rf, KE) run in coordinated fashion
   - Individual endpoints also available if you need specific metrics

2. **Parameter Set ID is crucial**
   - All endpoints require a valid parameter set ID
   - Parameters define rounding, approach (FIXED/Floating), risk premiums, etc.
   - Create/modify parameter sets via `/api/v1/parameters` endpoints

3. **Pre-computed Beta provides 6000x speedup**
   - Pre-computed during ingestion (Phase 2)
   - First calculation <10ms, fallback ~60s if not precomputed

4. **Query endpoints are fast**
   - Use them to retrieve calculated metrics
   - Supports filtering by ticker, metric name
   - Can retrieve multiple metrics at once

5. **Phase Dependencies**
   - L1 Basic Metrics (Phase 1): Must calculate with `/calculate` endpoint first
   - Runtime Metrics (Phase 3+): Depend on precomputed Beta from Phase 2
   - L2 Metrics: Depend on L1 metrics and runtime metrics

---

## Response Status Values

- `success` - Operation completed successfully
- `error` - Operation failed with error message
- `cached` - Results returned from cache (beta only)
- `precomputed` - Using pre-computed values (beta only)
- `fallback_legacy` - Fell back to legacy calculation (beta only)

---

## Metric Names for Queries

### Runtime Metrics
- `Calc Beta` or `Beta`
- `Calc Rf` or `Rf`
- `Calc KE`

### L2 Metrics
- `EP` - Economic Profit
- `PAT_EX` - Adjusted Profit
- `XO_COST_EX` - Adjusted XO Cost
- `FC` - Franking Credit
- `FV_ECF_1Y`, `FV_ECF_3Y`, `FV_ECF_5Y`, `FV_ECF_10Y`

### L1 Metrics
- `Calc MC` - Market Capitalization
- `Calc ECF` - Economic Cash Flow
- `Calc EE` - Economic Equity
- `Calc Assets`
- `Calc OA` - Operating Assets
- And more...

---

## Health Check

```bash
GET /api/v1/metrics/health
Response: {"status": "ok", "message": "Metrics service is running", "database": "connected"}
```

