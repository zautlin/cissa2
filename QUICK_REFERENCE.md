# CISSA Codebase - Quick Reference

## 📍 QUICK FILE LOCATIONS

| What | Where |
|------|-------|
| **API Documentation** | `/home/ubuntu/cissa/backend/README.md` |
| **All Endpoints** | `/home/ubuntu/cissa/backend/app/api/v1/endpoints/metrics.py` |
| **Database Schemas** | `/home/ubuntu/cissa/backend/database/schema/schema.sql` |
| **Parameters Table** | SQL: `cissa.parameters` (13 baseline params) |
| **Parameter Sets Table** | SQL: `cissa.parameter_sets` (UUID-based bundles) |
| **Request/Response Models** | `/home/ubuntu/cissa/backend/app/models/schemas.py` |
| **FastAPI Setup** | `/home/ubuntu/cissa/backend/app/main.py` |
| **Database Connection** | `/home/ubuntu/cissa/backend/app/core/database.py` |

---

## 🔌 ENDPOINT QUICK REFERENCE

### Health Check
```
GET /api/v1/metrics/health
```

### Calculate L1 Metrics
```
POST /api/v1/metrics/calculate
{
  "dataset_id": "UUID",
  "metric_name": "string",
  "param_set_id": "UUID" (optional)
}
```

### Query Metrics (Most Flexible)
```
GET /api/v1/metrics/get_metrics/?dataset_id=UUID&parameter_set_id=UUID&ticker=?&metric_name=?
```

### Calculate Phase 07 (Beta)
```
POST /api/v1/metrics/beta/calculate
{
  "dataset_id": "UUID",
  "param_set_id": "UUID"
}
```

### Calculate Phase 08 (Risk-Free Rate)
```
POST /api/v1/metrics/rates/calculate
{
  "dataset_id": "UUID",
  "param_set_id": "UUID"
}
```

### Calculate Phase 09 (Cost of Equity)
```
POST /api/v1/metrics/cost-of-equity/calculate
{
  "dataset_id": "UUID",
  "param_set_id": "UUID"
}
```

---

## 📊 DATABASE SCHEMA SUMMARY

### parameters Table
- `parameter_id` (BIGINT, PK, auto-increment)
- `parameter_name` (TEXT, UNIQUE)
- `display_name` (TEXT)
- `value_type` (TEXT)
- `default_value` (TEXT)
- `created_at`, `updated_at` (TIMESTAMPTZ)

**13 Baseline Parameters:**
1. country (Australia)
2. currency_notation (A$m)
3. cost_of_equity_approach (Floating/FIXED)
4. include_franking_credits_tsr (false)
5. fixed_benchmark_return_wealth_preservation (7.5)
6. equity_risk_premium (5.0)
7. tax_rate_franking_credits (30.0)
8. value_of_franking_credits (75.0)
9. risk_free_rate_rounding (0.5)
10. beta_rounding (0.1)
11. last_calendar_year (2019)
12. beta_relative_error_tolerance (40.0)
13. terminal_year (60)

### parameter_sets Table
- `param_set_id` (UUID, PK, default gen_random_uuid())
- `param_set_name` (TEXT, UNIQUE)
- `description` (TEXT)
- `is_default` (BOOLEAN)
- `is_active` (BOOLEAN)
- `param_overrides` (JSONB) ← **Parameter values stored here**
- `created_by` (TEXT)
- `created_at`, `updated_at` (TIMESTAMPTZ)

**Default Parameter Set:**
- param_set_name: "base_case"
- is_default: true
- param_overrides: `{}` (uses all 13 baseline defaults)

### metrics_outputs Table
- `metrics_output_id` (BIGINT, PK, auto-increment)
- `dataset_id` (UUID, FK → dataset_versions)
- `param_set_id` (UUID, FK → parameter_sets) ← **Stores which params were used**
- `ticker` (TEXT)
- `fiscal_year` (INTEGER)
- `output_metric_name` (TEXT)
- `output_metric_value` (NUMERIC)
- `metadata` (JSONB)
- `created_at` (TIMESTAMPTZ)

**Unique Index:** (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)

---

## 🏗️ FASTAPI APPLICATION STRUCTURE

```
FastAPI App
├── Main (app/main.py)
│   ├── Lifespan context manager
│   ├── CORS middleware
│   └── Router inclusion
│
├── Router (api/v1/router.py)
│   └── Includes metrics endpoints router
│
├── Endpoints (api/v1/endpoints/metrics.py) ← 771 lines
│   ├── GET /health
│   ├── POST /calculate (L1 metrics)
│   ├── GET /dataset/{dataset_id}/metrics/{metric_name}
│   ├── POST /calculate-l2
│   ├── POST /beta/calculate
│   ├── POST /rates/calculate
│   ├── POST /cost-of-equity/calculate
│   ├── POST /l2-core/calculate
│   ├── POST /l2-fv-ecf/calculate
│   └── GET /get_metrics/ ← Most flexible query endpoint
│
├── Core
│   ├── database.py → AsyncSession setup
│   └── config.py → Settings from .env
│
├── Models
│   ├── schemas.py → Pydantic request/response models
│   └── metrics_output.py → SQLAlchemy ORM
│
├── Services
│   ├── metrics_service.py
│   ├── beta_calculation_service.py
│   ├── risk_free_rate_service.py
│   ├── cost_of_equity_service.py
│   ├── economic_profit_service.py
│   └── fv_ecf_service.py
│
├── Repositories
│   ├── metrics_repository.py
│   └── metrics_query_repository.py
│
└── Database
    └── schema/schema.sql
```

---

## 🔄 REQUEST/RESPONSE PATTERN

### Standard Response Format
```json
{
  "dataset_id": "UUID",
  "param_set_id": "UUID",
  "results_count": 1234,
  "results": [
    {
      "ticker": "string",
      "fiscal_year": 2023,
      "metric_name": "string",
      "value": 123.45
    }
  ],
  "status": "success|error|cached",
  "message": "optional message"
}
```

### Standard Error Response
```json
{
  "status": "error",
  "message": "Error description",
  "results_count": 0,
  "results": []
}
```

---

## 📖 PARAMETER LOADING PATTERN

All services follow this pattern:

```python
async def _load_parameters_from_db(self, param_set_id: UUID) -> dict:
    # 1. Get parameter_set overrides
    result = await session.execute(
        text("SELECT param_overrides FROM cissa.parameter_sets WHERE param_set_id = :id"),
        {"id": param_set_id}
    )
    overrides = result.scalar() or {}
    
    # 2. Get baseline defaults
    result = await session.execute(
        text("SELECT parameter_name, default_value FROM cissa.parameters")
    )
    defaults = {row[0]: row[1] for row in result}
    
    # 3. Merge (overrides take precedence)
    return {**defaults, **overrides}
```

**Services using this:**
- BetaCalculationService
- RiskFreeRateCalculationService
- CostOfEquityService
- EconomicProfitService
- FVECFService

---

## 🎯 PARAMETER SENSITIVITY BY PHASE

| Phase | Service | Uses Parameters | Key Parameters |
|-------|---------|-----------------|-----------------|
| L1 | MetricsService | Partial | beta_rounding, cost_of_equity_approach |
| L2 | L2MetricsService | Yes | risk_premium, country |
| 07 (Beta) | BetaCalculationService | Yes | beta_rounding, beta_relative_error_tolerance |
| 08 (Rf) | RiskFreeRateCalculationService | Yes | bond_index, cost_of_equity_approach |
| 09 (KE) | CostOfEquityService | Yes | equity_risk_premium |
| 10a (EP) | EconomicProfitService | Yes | incl_franking, frank_tax_rate, value_franking_cr |
| 10b (FV_ECF) | FVECFService | Yes | incl_franking, frank_tax_rate, value_franking_cr |

---

## 🚀 GETTING STARTED

### Start the API
```bash
cd /home/ubuntu/cissa/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Access Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

### Query a Metric
```bash
curl "http://localhost:8000/api/v1/metrics/get_metrics/?dataset_id=<UUID>&parameter_set_id=<UUID>"
```

### Health Check
```bash
curl "http://localhost:8000/api/v1/metrics/health"
```

---

## 💾 DATABASE CONNECTION

**URL Format:**
```
postgresql+asyncpg://user:password@host:port/dbname
```

**Example from .env:**
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cissa
```

---

## 📝 KEY INSIGHTS

1. **Parameter Sets are Flexible:** Each analysis run uses a specific `param_set_id` which maps to:
   - Baseline defaults from `parameters` table
   - JSON overrides from `parameter_sets.param_overrides`

2. **Metrics are Versioned:** Every metric result stores the `param_set_id` used, enabling reproducibility

3. **Async-First:** Uses AsyncPG + SQLAlchemy 2.0 async for non-blocking I/O

4. **Three-Tier Architecture:**
   - API Layer: Validates requests/responses
   - Service Layer: Implements business logic
   - Repository Layer: Handles database operations

5. **Consistent Response Format:** All endpoints follow standard success/error patterns

