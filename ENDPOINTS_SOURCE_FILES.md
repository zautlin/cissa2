# CISSA Metrics Endpoints - Source Code File Locations

## Main Endpoint Files

### Metrics Endpoints (All HTTP routes)
**File:** `/home/ubuntu/cissa/backend/app/api/v1/endpoints/metrics.py`
- Contains all metric calculation endpoints
- Lines 45-1176 (1176 total lines)
- Includes: runtime-metrics, beta, risk-free rate, cost-of-equity, L2 metrics endpoints

**Key Functions:**
- `health_check()` - Line 46
- `calculate_metric()` - Line 56 (L1 metrics)
- `calculate_l2_metrics()` - Line 138 (L2 metrics)
- `calculate_beta()` - Line 212 (legacy, deprecated)
- `calculate_beta_from_precomputed()` - Line 300 (recommended)
- `precompute_beta_for_ingestion()` - Line 431 (ETL ingestion)
- `calculate_risk_free_rate()` - Line 518
- `calculate_cost_of_equity()` - Line 594
- `calculate_core_l2_metrics()` - Line 672 (EP, PAT_EX, etc.)
- `calculate_fv_ecf_metrics()` - Line 761 (FV_ECF metrics)
- `get_metrics()` - Line 858 (query endpoint)
- `get_ratio_metrics()` - Line 1001
- `calculate_runtime_metrics()` - Line 1089 (MAIN POST-INGESTION ENDPOINT)

### Router Configuration
**File:** `/home/ubuntu/cissa/backend/app/api/v1/router.py`
- Aggregates all endpoint routers
- Lines 1-11 (11 lines)
- Includes metrics, parameters, orchestration, statistics routers

---

## Service Implementation Files

### Runtime Metrics Orchestration Service
**File:** `/home/ubuntu/cissa/backend/app/services/runtime_metrics_orchestration_service.py`
- Orchestrates Phase 3+ runtime metrics calculation
- Lines 1-342 (342 lines)

**Key Classes/Methods:**
- `RuntimeMetricsOrchestrationService` - Main orchestration service
- `orchestrate_runtime_metrics()` - Lines 46-213 (main orchestration)
- `_resolve_parameter_id()` - Lines 215-258
- `_orchestrate_beta_rounding()` - Lines 260-284
- `_orchestrate_risk_free_rate()` - Lines 286-310
- `_orchestrate_cost_of_equity()` - Lines 312-336

### Beta Calculation Services
**Files:**
1. `/home/ubuntu/cissa/backend/app/services/beta_calculation_service.py` - Runtime beta calculation (legacy)
2. `/home/ubuntu/cissa/backend/app/services/beta_precomputation_service.py` - Pre-computation during ingestion
3. `/home/ubuntu/cissa/backend/app/services/beta_rounding_service.py` - Apply rounding to precomputed beta

### Risk-Free Rate Service
**File:** `/home/ubuntu/cissa/backend/app/services/risk_free_rate_service.py`
- Risk-free rate calculation using bond yields
- Lines 1-1087 (1087 lines, multiple calculation methods)

**Key Classes:**
- `RiskFreeRateCalculationService`

### Cost of Equity Service
**File:** `/home/ubuntu/cissa/backend/app/services/cost_of_equity_service.py`
- Cost of equity calculation: KE = Rf + Beta × RiskPremium
- Lines 1-604+ (604+ lines)

**Key Classes:**
- `CostOfEquityService`

### L2 Metrics Services
**Files:**
1. `/home/ubuntu/cissa/backend/app/services/l2_metrics_service.py` - L2 metrics batch calculation
2. `/home/ubuntu/cissa/backend/app/services/economic_profit_service.py` - Economic profit and related metrics
3. `/home/ubuntu/cissa/backend/app/services/fv_ecf_service.py` - FV_ECF metrics calculation

### Additional Services
- `/home/ubuntu/cissa/backend/app/services/metrics_service.py` - Basic L1 metrics calculation
- `/home/ubuntu/cissa/backend/app/services/ratio_metrics_service.py` - Ratio metrics with rolling windows
- `/home/ubuntu/cissa/backend/app/services/parameter_service.py` - Parameter set management

---

## Request/Response Models (Schemas)

### Main Schema File
**File:** `/home/ubuntu/cissa/backend/app/models/schemas.py`
- Contains all Pydantic request/response models
- Lines 1-263 (263 lines)

**Key Models:**
- `CalculateMetricsRequest` - L1 metric request (Line 14)
- `CalculateMetricsResponse` - L1 metric response (Line 28)
- `CalculateL2Request` - L2 metrics request (Line 49)
- `CalculateL2Response` - L2 metrics response (Line 66)
- `CalculateEnhancedMetricsRequest` - Enhanced metrics request (Line 96)
- `CalculateEnhancedMetricsResponse` - Enhanced metrics response (Line 110)
- `CalculateBetaRequest` - Beta request (Line 130)
- `CalculateBetaResponse` - Beta response (Line 146)
- `CalculateRiskFreeRateRequest` - Rf request (Line 162)
- `CalculateRiskFreeRateResponse` - Rf response (Line 179)
- `MetricRecord` - Single metric record (Line 199)
- `GetMetricsResponse` - Metrics query response (Line 217)
- `ParameterSetResponse` - Parameter set response (Line 241)

### Statistics Models
**File:** `/home/ubuntu/cissa/backend/app/models/statistics.py`
- Dataset statistics models

---

## Repository/Database Access Files

### Metrics Query Repository
**File:** `/home/ubuntu/cissa/backend/app/repositories/metrics_query_repository.py`
- Query metrics from database with flexible filtering
- Used by `/get_metrics/` endpoint

### Parameter Repository
**File:** `/home/ubuntu/cissa/backend/app/repositories/parameter_repository.py`
- Fetch parameter sets and individual parameters
- Used by all calculation endpoints

### Metrics Repositories
**Files:**
- `/home/ubuntu/cissa/backend/app/repositories/metrics_repository.py`
- `/home/ubuntu/cissa/backend/app/repositories/ratio_metrics_repository.py`
- `/home/ubuntu/cissa/backend/app/repositories/ee_growth_repository.py`
- `/home/ubuntu/cissa/backend/app/repositories/revenue_growth_repository.py`

---

## Main Application File

**File:** `/home/ubuntu/cissa/backend/app/main.py`
- FastAPI application setup
- Lines 1-87 (87 lines)

**Key Components:**
- FastAPI app configuration (Line 47)
- CORS middleware setup (Line 55)
- v1 router inclusion (Line 64)
- Lifespan context manager (Lines 21-43)
- Root endpoint (Lines 67-75)

---

## Database Configuration

**File:** `/home/ubuntu/cissa/backend/app/core/database.py`
- Database connection and session management

**File:** `/home/ubuntu/cissa/backend/app/core/config.py`
- Application settings and configuration

---

## Test Files (Optional Reference)

**Test Files:**
- `/home/ubuntu/cissa/backend/tests/test_risk_free_rate.py`
- `/home/ubuntu/cissa/backend/tests/test_l1_metrics.py`
- `/home/ubuntu/cissa/backend/tests/test_ratio_metrics.py`
- `/home/ubuntu/cissa/backend/tests/integration/test_beta_precomputation_e2e.py`

---

## API Documentation

### Metrics Endpoints Documentation
- In `/home/ubuntu/cissa/backend/app/api/v1/endpoints/metrics.py` (docstrings for each endpoint)
- Each endpoint has detailed docstring with:
  - Purpose
  - Prerequisites
  - Parameters
  - Example requests
  - Response format
  - Expected performance

### Example Endpoints (from docstrings):

#### POST /runtime-metrics (Line 1088-1175)
Orchestrates Phase 3+ runtime metrics:
- Beta Rounding
- Risk-Free Rate
- Cost of Equity

#### POST /beta/calculate-from-precomputed (Line 299-427)
Calculates beta using pre-computed values:
- Performance: <10ms with precomputed, 60s fallback

#### POST /rates/calculate (Line 517-586)
Calculates risk-free rate:
- Uses rolling 12-month geometric mean of bond yields

#### POST /cost-of-equity/calculate (Line 593-664)
Calculates cost of equity:
- Formula: KE = Rf + Beta × RiskPremium

#### POST /l2-core/calculate (Line 671-753)
Calculates core L2 metrics:
- EP, PAT_EX, XO_COST_EX, FC

#### POST /l2-fv-ecf/calculate (Line 760-850)
Calculates FV_ECF metrics:
- 1Y, 3Y, 5Y, 10Y intervals

#### GET /get_metrics/ (Line 857-997)
Flexible metrics query:
- Supports filtering by ticker, metric name
- Includes unit information

---

## Summary

### Total Endpoints: 13
- 1 Main Orchestration (runtime-metrics)
- 3 Beta Endpoints
- 1 Risk-Free Rate Endpoint
- 1 Cost of Equity Endpoint
- 2 L2 Metrics Endpoints
- 2 Query Endpoints
- 2 Basic L1 Endpoints
- 1 Health Check

### Total Lines of Code (Metrics Module): ~2,500+
- Endpoints: 1,176 lines
- Services: ~1,500+ lines
- Models: 263 lines
- Repositories: ~500+ lines

### Key Design Patterns:
- Async/await for all database operations
- Vectorized Pandas operations for performance
- Batch database inserts (1000 records per batch)
- Fail-fast orchestration with status tracking
- Comprehensive logging with structured messages

