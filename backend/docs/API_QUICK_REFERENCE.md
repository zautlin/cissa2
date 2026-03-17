# CISSA API & Architecture Quick Reference

## Database Tables (11 total)

| # | Table | Purpose |
|---|-------|---------|
| 1 | `companies` | Master company list (ASX200) |
| 2 | `fiscal_year_mapping` | (ticker, FY) to date mapping |
| 3 | `metric_units` | Metric name to unit lookup |
| 4 | `dataset_versions` | Audit trail for data ingestion |
| 5 | `raw_data` | Immutable raw input (all values as-is) |
| 6 | `fundamentals` | Cleaned, aligned, imputed fact table [PRIMARY] |
| 7 | `imputation_audit_trail` | Data quality and imputation log |
| 8 | `parameters` | Baseline tunable parameters (13 total) |
| 9 | `parameter_sets` | Parameter configuration bundles |
| 10 | `metrics_outputs` | Calculated metrics [MAIN OUTPUT] |
| 11 | `optimization_outputs` | Optimization results (hierarchical projections) |

---

## API Endpoints (`/api/v1/`)

### Metrics Calculation
- `POST   /metrics/calculate` - Calculate single L1 metric
- `GET    /metrics/dataset/{id}/metrics/{name}` - Get or calculate L1 metric
- `POST   /metrics/calculate-l2` - Calculate L2 metrics
- `POST   /metrics/beta/calculate` - Calculate beta (Phase 07)
- `POST   /metrics/rates/calculate` - Calculate Rf (Phase 08)
- `POST   /metrics/cost-of-equity/calculate` - Calculate KE (Phase 09)
- `GET    /metrics/get_metrics` - Query metrics with filters

### Parameters Management
- `GET    /parameters/active` - Get active param set
- `GET    /parameters/{id}` - Get param set by ID
- `GET    /parameters/list` - List all param sets
- `POST   /parameters/update` - Update/create param set
- `PUT    /parameters/{id}/set-active` - Make param set active
- `PUT    /parameters/{id}/set-default` - Make param set default

### Orchestration
- `POST   /metrics/orchestrate/calculate-l1` - Calculate all L1 metrics

### Health
- `GET    /metrics/health` - Health check
- `GET    /` - API info

---

## Key Architecture Patterns

### Layering
```
Endpoint → Service → Repository → Database
```

### Async
- FastAPI + AsyncSession (SQLAlchemy async)
- AsyncPG driver
- Connection pool: 10 base, 20 max overflow

### Dependency Injection
- FastAPI `Depends()` for AsyncSession injection
- Services receive sessions in `__init__`
- Repositories receive sessions in `__init__`

### Parameter Management
- **Baseline:** `parameters` table (13 default params)
- **Overrides:** `parameter_sets.param_overrides` (JSONB)
- **Merge on retrieval:** baseline + overrides

### Data Lineage
```
dataset_versions (versioning audit)
    ↓
raw_data (immutable input)
    ↓
fundamentals (cleaned/aligned/imputed)
    ↓
metrics_outputs (calculated outputs)
    ↓
optimization_outputs (projections)
```

### Temporal Handling
- **FISCAL:** `fiscal_year` only (month/day NULL)
- **MONTHLY:** `fiscal_year, fiscal_month, fiscal_day`
- **Uniqueness:** `COALESCE(month, 0), COALESCE(day, 0)`

### Caching
- Beta and Risk-Free Rate have caching
- Status: `"success" | "error" | "cached"`

---

## Baseline Parameters (13)

| # | Parameter | Default |
|---|-----------|---------|
| 1 | `country` | 'Australia' |
| 2 | `currency_notation` | 'A$m' |
| 3 | `cost_of_equity_approach` | 'Floating' |
| 4 | `include_franking_credits_tsr` | false |
| 5 | `fixed_benchmark_return_wealth_preservation` | 7.5 |
| 6 | `equity_risk_premium` | 5.0 |
| 7 | `tax_rate_franking_credits` | 30.0 |
| 8 | `value_of_franking_credits` | 75.0 |
| 9 | `risk_free_rate_rounding` | 0.5 |
| 10 | `beta_rounding` | 0.1 |
| 11 | `last_calendar_year` | 2019 |
| 12 | `beta_relative_error_tolerance` | 40.0 |
| 13 | `terminal_year` | 60 |

---

## Key Response Models

### MetricResultItem
```json
{ticker, fiscal_year, value}
```

### L2MetricResultItem
```json
{ticker, fiscal_year, metric_name, value}
```

### BetaResultItem
```json
{ticker, fiscal_year, value}
```

### RiskFreeRateResultItem
```json
{ticker, fiscal_year, metric_name, value}
```

### MetricRecord (with units from metric_units table)
```json
{dataset_id, parameter_set_id, ticker, fiscal_year, metric_name, value, unit}
```

### ParameterSetResponse (with merged parameters)
```json
{param_set_id, param_set_name, is_active, is_default, created_at, updated_at, parameters: dict, status, message}
```

---

## Database Functions (14 total)

### Simple Metrics (7)
- `fn_calc_market_cap()`
- `fn_calc_operating_assets()`
- `fn_calc_operating_assets_detail()`
- `fn_calc_operating_cost()`
- `fn_calc_non_operating_cost()`
- `fn_calc_tax_cost()`
- `fn_calc_extraordinary_cost()`

### Temporal Metrics (5)
- `fn_calc_ecf()`
- `fn_calc_non_div_ecf()`
- `fn_calc_economic_equity()`
- `fn_calc_fy_tsr()`
- `fn_calc_fy_tsr_prel()`

### Derived Metrics (2)
- `fn_calc_book_equity()`
- `fn_calc_roa()`

---

## File Locations

### Schema
- `/backend/database/schema/schema.sql` - 11 tables, 25+ indexes
- `/backend/database/schema/functions.sql` - 14 stored functions
- `/backend/database/schema/schema_manager.py` - Schema initialization

### API
- `/backend/app/main.py` - FastAPI app entry
- `/backend/app/api/v1/router.py` - Router aggregator
- `/backend/app/api/v1/endpoints/`
  - `metrics.py` - Metric endpoints
  - `parameters.py` - Parameter endpoints
  - `orchestration.py` - Orchestration

### Services
- `/backend/app/services/`
  - `metrics_service.py` - L1 metrics
  - `l2_metrics_service.py` - L2 metrics
  - `beta_calculation_service.py` - Phase 07
  - `risk_free_rate_service.py` - Phase 08
  - `cost_of_equity_service.py` - Phase 09
  - `parameter_service.py` - Parameters

### Repositories
- `/backend/app/repositories/`
  - `metrics_repository.py` - Metrics CRUD
  - `metrics_query_repository.py` - Query/retrieval
  - `parameter_repository.py` - Parameters

### Models
- `/backend/app/models/`
  - `schemas.py` - Pydantic models
  - `metrics_output.py` - ORM model
  - `ratio_metrics.py` - Ratio models

### Core
- `/backend/app/core/`
  - `config.py` - Settings
  - `database.py` - AsyncPG manager

---

## Configuration

### Environment Variables
- `DATABASE_URL` (required) - PostgreSQL async URL
- `fastapi_env` = "development"
- `log_level` = "info"
- `workers` = 1
- `metrics_batch_size` = 1000
- `metrics_timeout_seconds` = 300

### .env Locations Searched
1. `.env` (current directory)
2. `../.env` (parent directory)
3. `/home/ubuntu/cissa/.env` (absolute)
