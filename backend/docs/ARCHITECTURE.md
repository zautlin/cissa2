# CISSA Codebase - Database Schema & API Structure Analysis

## 1. DATABASE SCHEMA OVERVIEW

### Location
- **Schema Definition**: `/home/ubuntu/cissa/backend/database/schema/schema.sql`
- **Schema Name**: `cissa` (separate from public schema)
- **Database**: PostgreSQL 16+
- **Total Tables**: 11
- **Total Indexes**: 25+
- **Total Triggers**: 4 (auto-update timestamps)

---

## 2. TABLE STRUCTURE

### Phase 1: Reference Tables (Immutable Lookup Data)

#### `companies`
- **Purpose**: Master list of companies from Base.csv
- **Primary Key**: `company_id` (UUID)
- **Key Columns**:
  - `ticker` (TEXT, UNIQUE) - Company identifier
  - `name` (TEXT) - Company name
  - `sector`, `bics_level_1-4` (TEXT) - Classification
  - `currency` (TEXT, default 'AUD')
  - `country` (TEXT, default 'Australia')
  - `parent_index` (TEXT) - e.g., 'ASX200' for top 200 by market cap
  - `fy_report_month` (DATE) - Fiscal year end month
  - `begin_year` (INTEGER) - First year of available data
- **Indexes**: ticker, sector, country, parent_index
- **Use Case**: Dimension table for all financial data

#### `fiscal_year_mapping`
- **Purpose**: Maps (ticker, fiscal_year) to fiscal period end date (FY Dates.csv)
- **Primary Key**: `fy_mapping_id` (BIGINT IDENTITY)
- **Key Columns**:
  - `ticker` (TEXT, NOT NULL)
  - `fiscal_year` (INTEGER, NOT NULL)
  - `fy_period_date` (DATE) - Fiscal period end date
- **Indexes**: UNIQUE(ticker, fiscal_year), ticker
- **Use Case**: FY alignment during processing

#### `metric_units`
- **Purpose**: Reference table mapping metric names to measurement units
- **Primary Key**: `metric_units_id` (BIGINT IDENTITY)
- **Key Columns**:
  - `metric_name` (TEXT, UNIQUE) - Metric identifier (e.g., "Revenue", "Company TSR (Monthly)")
  - `unit` (TEXT) - Unit of measurement ("millions", "%", "number of shares", etc.)
- **Indexes**: metric_name
- **Triggers**: Auto-update `updated_at` timestamp
- **Population**: From backend/database/config/metric_units.json during initialization

---

### Phase 2: Versioning & Tracking

#### `dataset_versions`
- **Purpose**: Master audit table for each data ingestion run
- **Primary Key**: `dataset_id` (UUID)
- **Key Columns**:
  - `dataset_name` (TEXT) - Name of dataset (auto-calculated)
  - `version_number` (INTEGER) - Increments per hash change
  - `source_file` (TEXT) - Source file name
  - `source_file_hash` (TEXT) - SHA hash for duplicate detection
  - `metadata` (JSONB) - Ingestion/processing stats
  - `created_by` (TEXT, default 'admin')
  - `created_at`, `updated_at` (TIMESTAMPTZ)
- **Indexes**: UNIQUE(dataset_name, source_file_hash), created_at
- **Triggers**: Auto-update `updated_at` timestamp
- **Use Case**: Track all data versions and prevent duplicate ingestion

---

### Phase 3: Raw Data (Staging)

#### `raw_data`
- **Purpose**: Immutable raw ingestion table - source of truth for all financial data
- **Primary Key**: `raw_data_id` (BIGINT IDENTITY)
- **Key Columns**:
  - `dataset_id` (UUID, FK → dataset_versions)
  - `ticker` (TEXT)
  - `metric_name` (TEXT)
  - `period` (TEXT)
  - `period_type` (TEXT) - CHECK('FISCAL' or 'MONTHLY')
  - `raw_string_value` (TEXT) - Original CSV value
  - `numeric_value` (NUMERIC) - Parsed value
  - `currency` (TEXT)
  - `created_at` (TIMESTAMPTZ)
- **Indexes**: dataset, ticker, metric, UNIQUE(dataset_id, ticker, metric_name, period)
- **Use Case**: Immutable record of all input data (no filtering/validation)

---

### Phase 4: Cleaned Data (Fact Table)

#### `fundamentals`
- **Purpose**: Final cleaned, FY-aligned, imputed fact table - single source of truth for downstream analysis
- **Primary Key**: `fundamentals_id` (BIGINT IDENTITY)
- **Key Columns**:
  - `dataset_id` (UUID, FK → dataset_versions)
  - `ticker` (TEXT)
  - `metric_name` (TEXT)
  - `fiscal_year` (INTEGER)
  - `fiscal_month` (INTEGER, nullable)
  - `fiscal_day` (INTEGER, nullable)
  - `numeric_value` (NUMERIC) - Cleaned, aligned, imputed value
  - `currency` (TEXT)
  - `period_type` (TEXT) - 'FISCAL' or 'MONTHLY'
  - `imputed` (BOOLEAN) - Whether value was imputed
  - `metadata` (JSONB) - Imputation step and confidence level
  - `created_at`, `updated_at` (TIMESTAMPTZ)
- **Uniqueness**: UNIQUE(dataset_id, ticker, metric_name, fiscal_year, COALESCE(fiscal_month, 0), COALESCE(fiscal_day, 0))
  - Uses COALESCE to treat NULL month/day as 0 for FISCAL records
- **Indexes**: dataset, ticker, metric, fiscal_year, period_type, composite indexes for common queries
- **Use Case**: Single source of truth for all downstream metric calculations

#### `imputation_audit_trail`
- **Purpose**: Detailed audit of imputation decisions and data quality issues
- **Primary Key**: `audit_id` (BIGINT IDENTITY)
- **Key Columns**:
  - `dataset_id` (UUID, FK → dataset_versions)
  - `ticker` (TEXT)
  - `metric_name` (TEXT)
  - `fiscal_year` (INTEGER, nullable) - For data quality issues without clear FY mapping
  - `imputation_step` (TEXT) - CHECK constraint with values:
    - `FORWARD_FILL`, `BACKWARD_FILL`, `INTERPOLATE`
    - `SECTOR_MEDIAN`, `MARKET_MEDIAN`
    - `MISSING`, `DATA_QUALITY_DUPLICATE`, `DATA_QUALITY_INVALID_VALUE`, `DATA_QUALITY_MISSING`
  - `original_value` (NUMERIC, nullable)
  - `imputed_value` (NUMERIC)
  - `metadata` (JSONB) - Period/date and context
  - `created_at` (TIMESTAMPTZ)
- **Indexes**: dataset, ticker_fy, imputation_step
- **Use Case**: Traceability of imputation decisions for data quality review

---

### Phase 5: Configuration & Parameters

#### `parameters`
- **Purpose**: Master list of baseline tunable parameters for metric calculations
- **Primary Key**: `parameter_id` (BIGINT IDENTITY)
- **Key Columns**:
  - `parameter_name` (TEXT, UNIQUE) - Parameter identifier
  - `display_name` (TEXT)
  - `value_type` (TEXT)
  - `default_value` (TEXT)
  - `created_at`, `updated_at` (TIMESTAMPTZ)
- **Indexes**: parameter_name
- **Triggers**: Auto-update `updated_at` timestamp
- **Baseline Parameters** (13 total, initialized on schema creation):
  1. `country` - 'Australia'
  2. `currency_notation` - 'A$m'
  3. `cost_of_equity_approach` - 'Floating'
  4. `include_franking_credits_tsr` - false
  5. `fixed_benchmark_return_wealth_preservation` - 7.5
  6. `equity_risk_premium` - 5.0
  7. `tax_rate_franking_credits` - 30.0
  8. `value_of_franking_credits` - 75.0
  9. `risk_free_rate_rounding` - 0.5
  10. `beta_rounding` - 0.1
  11. `last_calendar_year` - 2019
  12. `beta_relative_error_tolerance` - 40.0
  13. `terminal_year` - 60

#### `parameter_sets`
- **Purpose**: Named bundles of parameter configurations for reproducibility
- **Primary Key**: `param_set_id` (UUID)
- **Key Columns**:
  - `param_set_name` (TEXT, UNIQUE) - e.g., 'base_case', 'conservative_valuation'
  - `description` (TEXT)
  - `is_default` (BOOLEAN) - Only one can be true
  - `is_active` (BOOLEAN) - Currently active set
  - `param_overrides` (JSONB) - Parameter name → override value mapping
  - `created_by` (TEXT)
  - `created_at`, `updated_at` (TIMESTAMPTZ)
- **Indexes**: is_default, is_active
- **Triggers**: Auto-update `updated_at` timestamp
- **Default Set**: 'base_case' created on schema initialization (is_default=true, is_active=true)
- **Use Case**: Store parameter configurations for consistent, reproducible calculations

---

### Phase 6: Downstream Outputs

#### `metrics_outputs`
- **Purpose**: Computed metrics derived from fundamentals + parameter sets
- **Primary Key**: `metrics_output_id` (BIGINT IDENTITY)
- **Key Columns**:
  - `dataset_id` (UUID, FK → dataset_versions)
  - `param_set_id` (UUID, FK → parameter_sets)
  - `ticker` (TEXT)
  - `fiscal_year` (INTEGER)
  - `output_metric_name` (TEXT)
  - `output_metric_value` (NUMERIC)
  - `metadata` (JSONB) - Metric-specific attributes
  - `created_at` (TIMESTAMPTZ)
- **Uniqueness**: UNIQUE(dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
- **Indexes**: dataset, param_set, ticker_fy
- **Use Case**: Final computed metrics for API retrieval and UI charting
- **Example Metrics**: 'Calc MC', 'Calc Assets', 'Calc ECF', 'Calc FY TSR', 'Beta', 'Cost of Equity', etc.

#### `optimization_outputs`
- **Purpose**: Results from optimization algorithms (hierarchical projections)
- **Primary Key**: `optimization_id` (UUID)
- **Key Columns**:
  - `dataset_id` (UUID, FK → dataset_versions)
  - `param_set_id` (UUID, FK → parameter_sets)
  - `ticker` (TEXT)
  - `result_summary` (JSONB) - Hierarchical {base_year: {metric: {projected_year: value}}}
    - Example: `{"2000": {"ep": {"2001": -0.0004, ...}, "market_value_equity": {...}}, "2001": {...}}`
    - Contains 18 derived metrics (ep, market_value_equity, dividend, pat, return_on_equity, etc.)
    - Typically 62 years (convergence_horizon + 2)
  - `metadata` (JSONB) - Optimization execution data:
    - convergence_status ('converged', 'diverged', 'max_iterations_reached')
    - convergence_horizon, iterations, residual
    - initial_ep, optimal_ep, observed_market_value, calculated_market_value
    - solver info, errors
  - `created_by` (TEXT, default 'admin')
  - `created_at`, `updated_at` (TIMESTAMPTZ)
- **Indexes**: Natural key (dataset_id, param_set_id, ticker, created_at DESC), dataset, param_set, ticker, GIN indexes on JSONB
- **Triggers**: Auto-update `updated_at` timestamp
- **Allows Re-optimization**: Multiple optimizations per (dataset, param_set, ticker) with different timestamps
- **Use Case**: Multi-base-year projections optimized for UI charting

---

## 3. API STRUCTURE

### Base Application
- **Framework**: FastAPI
- **Location**: `/home/ubuntu/cissa/backend/app/main.py`
- **API Title**: "CISSA Metrics API"
- **Version**: 0.1.0
- **Root Endpoint**: `GET /` - Returns API info
- **Health Check**: `GET /api/v1/metrics/health`

### API Routing Architecture
```
/api/v1/
├── /metrics/          (metrics.py)
├── /parameters/       (parameters.py)
└── /orchestration/    (orchestration.py)
```

### Middleware
- **CORS**: Enabled for all origins, credentials, methods, headers

---

## 4. ENDPOINT PATTERNS

### Metrics Endpoints (`/api/v1/metrics/`)

#### Calculate L1 Metrics
```
POST /api/v1/metrics/calculate
Request: CalculateMetricsRequest
  - dataset_id (UUID, required)
  - metric_name (str, required) - e.g., "Calc MC", "Calc Assets", "Calc ECF"
  - param_set_id (UUID, optional) - For parameter-sensitive metrics
Response: CalculateMetricsResponse
  - dataset_id, metric_name, results_count
  - results (list of MetricResultItem)
  - status ("success" or "error"), message
```

#### Get/Calculate Metric (Convenience GET)
```
GET /api/v1/metrics/dataset/{dataset_id}/metrics/{metric_name}
Query Params: param_set_id (optional)
Response: CalculateMetricsResponse
```

#### Calculate L2 Metrics
```
POST /api/v1/metrics/calculate-l2
Request: CalculateL2Request
  - dataset_id (UUID, required)
  - param_set_id (UUID, required)
Response: CalculateL2Response
  - dataset_id, param_set_id, results_count
  - results (list of L2MetricResultItem)
  - status, message
```

#### Calculate Beta (Phase 07)
```
POST /api/v1/metrics/beta/calculate
Request: CalculateBetaRequest
  - dataset_id (UUID, required)
  - param_set_id (UUID, required)
Response: CalculateBetaResponse
  - dataset_id, param_set_id, results_count
  - results (list of BetaResultItem)
  - status ("success", "error", or "cached"), message
Algorithm: 60-month rolling OLS → adjust → filter → round → apply approach
```

#### Calculate Risk-Free Rate (Phase 08)
```
POST /api/v1/metrics/rates/calculate
Request: CalculateRiskFreeRateRequest
  - dataset_id (UUID, required)
  - param_set_id (UUID, required)
Response: CalculateRiskFreeRateResponse
  - dataset_id, param_set_id, results_count
  - results (list of RiskFreeRateResultItem)
  - status ("success", "error", or "cached"), message
Output Metrics: Rf_1Y_Raw, Rf_1Y, Rf
```

#### Calculate Cost of Equity (Phase 09)
```
POST /api/v1/metrics/cost-of-equity/calculate
Request: CalculateEnhancedMetricsRequest
  - dataset_id (UUID, required)
  - param_set_id (UUID, required)
Response: CalculateEnhancedMetricsResponse
  - dataset_id, param_set_id, results_count, metrics_calculated
  - status, message
Dependencies: Phase 07 Beta + Phase 08 Risk-Free Rate
```

#### Query Metrics
```
GET /api/v1/metrics/get_metrics
Query Params:
  - dataset_id (UUID, required)
  - param_set_id (UUID, required)
  - ticker (str, optional) - Case-insensitive
  - metric_name (str, optional) - Case-insensitive
Response: GetMetricsResponse
  - dataset_id, parameter_set_id, results_count
  - results (list of MetricRecord with unit info)
  - filters_applied (dict), status, message
```

### Parameters Endpoints (`/api/v1/parameters/`)

#### Get Active Parameters
```
GET /api/v1/parameters/active
Response: ParameterSetResponse
  - param_set_id, param_set_name
  - is_active (true), is_default
  - created_at, updated_at
  - parameters (dict of merged baseline + overrides)
  - status, message
```

#### Get Parameter Set by ID
```
GET /api/v1/parameters/{param_set_id}
Response: ParameterSetResponse
  - Same as above
```

#### List All Parameter Sets
```
GET /api/v1/parameters/list
Response: ParameterSetListResponse
  - results_count, results (list of ParameterSetResponse)
  - status, message
```

#### Create/Update Parameters
```
POST /api/v1/parameters/update
Request: ParameterUpdateRequest
  - parameters (dict of updates)
  - set_as_active (bool, optional)
  - set_as_default (bool, optional)
Response: ParameterSetResponse
Creates NEW parameter_set with merged overrides
```

#### Set Active Parameter Set
```
PUT /api/v1/parameters/{param_set_id}/set-active
Response: ParameterSetResponse
Deactivates all others, activates this one
```

#### Set Default Parameter Set
```
PUT /api/v1/parameters/{param_set_id}/set-default
Response: ParameterSetResponse
Unsets previous default, sets this one
```

### Orchestration Endpoints (`/api/v1/metrics/orchestration/`)

#### Calculate L1 Orchestrator (All L1 Metrics)
```
POST /api/v1/metrics/orchestrate/calculate-l1
Request: CalculateL1OrchestratorRequest
  - dataset_id (UUID, required)
  - param_set_id (UUID, required)
  - api_url (str, optional, default "http://localhost:8000")
  - concurrency (int, optional, 1-8, default 4)
  - max_retries (int, optional, 1-5, default 3)
Response: CalculateL1OrchestratorResponse
  - success (bool), execution_time_seconds
  - dataset_id, param_set_id, timestamp
  - total_successful, total_failed, total_records_inserted
  - phases (dict of phase results)
  - errors (list of error messages)
Features:
  - 4 concurrent groups within Phase 1
  - Sequential Phase 2-4 execution
  - Automatic retry logic
  - Timing statistics
```

---

## 5. REPOSITORY & SERVICE LAYER ORGANIZATION

### Directory Structure
```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── router.py                    # Main router aggregator
│   │       └── endpoints/
│   │           ├── metrics.py               # Metric calculation endpoints
│   │           ├── parameters.py            # Parameter management endpoints
│   │           └── orchestration.py         # L1 orchestration endpoints
│   ├── models/
│   │   ├── schemas.py                       # Pydantic request/response models
│   │   ├── metrics_output.py                # SQLAlchemy ORM model
│   │   └── ratio_metrics.py                 # Ratio-specific models
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── metrics_repository.py            # Metrics CRUD operations
│   │   ├── metrics_query_repository.py      # Metrics retrieval with filtering
│   │   ├── parameter_repository.py          # Parameters data access
│   │   ├── ratio_metrics_repository.py      # Ratio metrics access
│   │   ├── ee_growth_repository.py
│   │   └── revenue_growth_repository.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── metrics_service.py               # L1 metrics orchestration
│   │   ├── l2_metrics_service.py            # L2 metrics calculation
│   │   ├── beta_calculation_service.py      # Phase 07: Beta calculation
│   │   ├── risk_free_rate_service.py        # Phase 08: Risk-free rate
│   │   ├── cost_of_equity_service.py        # Phase 09: Cost of equity
│   │   ├── parameter_service.py             # Parameter management
│   │   ├── ratio_metrics_service.py
│   │   ├── economic_profit_service.py
│   │   ├── fv_ecf_service.py
│   │   ├── ee_growth_calculator.py
│   │   ├── revenue_growth_calculator.py
│   │   ├── ratio_metrics_calculator.py
│   │   └── parameter_validator.py
│   ├── core/
│   │   ├── config.py                        # Settings, logging configuration
│   │   └── database.py                      # AsyncPG database manager
│   ├── cli/
│   └── config/
│       └── metric_units.json                # Metric unit definitions
├── database/
│   └── schema/
│       ├── schema.sql                       # Full schema definition (11 tables)
│       ├── functions.sql                    # PostgreSQL stored functions
│       ├── destroy_schema.sql               # Schema cleanup
│       └── schema_manager.py                # Schema initialization utilities
└── tests/
    ├── integration/
    ├── unit/
    └── validation/
```

### Service Layer Pattern

**Service classes handle business logic:**
```python
class MetricsService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate_metric(
        self, 
        dataset_id: UUID, 
        metric_name: str, 
        param_set_id: Optional[UUID]
    ) -> CalculateMetricsResponse:
        # 1. Validate inputs
        # 2. Resolve defaults if needed
        # 3. Call SQL function via session
        # 4. Insert results into metrics_outputs
        # 5. Return response
```

### Repository Layer Pattern

**Repository classes handle data access:**
```python
class MetricsRepository:
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def get_l1_metrics(
        self, 
        dataset_id: UUID, 
        param_set_id: UUID
    ) -> pd.DataFrame:
        # Query metrics_outputs
        # Return pandas DataFrame for manipulation
    
    async def create_metric_output(
        self, 
        dataset_id: UUID,
        param_set_id: UUID,
        ticker: str,
        fiscal_year: int,
        metric_name: str,
        metric_value: float,
        metadata: Optional[dict]
    ) -> MetricsOutput:
        # Create and insert single metric
        # Return ORM model instance
```

### Database Connection Pattern

**Async database manager with FastAPI dependency injection:**
```python
class DatabaseManager:
    async def initialize(self):
        # Create async engine with connection pooling
        # Create async session factory
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        # Dependency for FastAPI to inject sessions
        # Handles automatic cleanup and error handling

# In endpoints:
@router.post("/calculate")
async def calculate_metric(
    request: CalculateMetricsRequest,
    db: AsyncSession = Depends(get_db)
):
    service = MetricsService(db)
    response = await service.calculate_metric(...)
    return response
```

---

## 6. REQUEST/RESPONSE MODELS (Pydantic Schemas)

### Base Models

#### MetricResultItem
```python
{
  "ticker": str,
  "fiscal_year": int,
  "value": float
}
```

#### L2MetricResultItem
```python
{
  "ticker": str,
  "fiscal_year": int,
  "metric_name": str,
  "value": float
}
```

#### BetaResultItem
```python
{
  "ticker": str,
  "fiscal_year": int,
  "value": float
}
```

#### RiskFreeRateResultItem
```python
{
  "ticker": str,
  "fiscal_year": int,
  "metric_name": str,  # 'Rf', 'Rf_1Y', or 'Rf_1Y_Raw'
  "value": float
}
```

### Calculation Response Models

#### CalculateMetricsResponse
```python
{
  "dataset_id": UUID,
  "metric_name": str,
  "results_count": int,
  "results": list[MetricResultItem],
  "status": "success" | "error",
  "message": Optional[str]
}
```

#### CalculateL2Response
```python
{
  "dataset_id": UUID,
  "param_set_id": UUID,
  "results_count": int,
  "results": list[L2MetricResultItem],
  "status": "success" | "error",
  "message": Optional[str]
}
```

#### CalculateBetaResponse
```python
{
  "dataset_id": UUID,
  "param_set_id": UUID,
  "results_count": int,
  "results": list[BetaResultItem],
  "status": "success" | "error" | "cached",
  "message": Optional[str]
}
```

#### CalculateRiskFreeRateResponse
```python
{
  "dataset_id": UUID,
  "param_set_id": UUID,
  "results_count": int,
  "results": list[RiskFreeRateResultItem],
  "status": "success" | "error" | "cached",
  "message": Optional[str]
}
```

### Query Response Models

#### MetricRecord
```python
{
  "dataset_id": UUID,
  "parameter_set_id": UUID,
  "ticker": str,
  "fiscal_year": int,
  "metric_name": str,
  "value": float,
  "unit": Optional[str]  # From metric_units table
}
```

#### GetMetricsResponse
```python
{
  "dataset_id": UUID,
  "parameter_set_id": UUID,
  "results_count": int,
  "results": list[MetricRecord],
  "filters_applied": dict,
  "status": "success" | "error",
  "message": Optional[str]
}
```

### Parameter Models

#### ParameterSetResponse
```python
{
  "param_set_id": UUID,
  "param_set_name": Optional[str],
  "is_active": bool,
  "is_default": bool,
  "created_at": datetime,
  "updated_at": datetime,
  "parameters": dict[str, Any],  # Merged baseline + overrides
  "status": "success" | "error",
  "message": Optional[str]
}
```

#### ParameterSetListResponse
```python
{
  "results_count": int,
  "results": list[ParameterSetResponse],
  "status": "success" | "error",
  "message": Optional[str]
}
```

---

## 7. DATABASE FUNCTIONS (PostgreSQL)

### Function Categories
1. **Simple Metrics** (7 functions):
   - `fn_calc_market_cap()` - Spot Shares × Share Price
   - `fn_calc_operating_assets()` - Total Assets - Cash
   - `fn_calc_operating_assets_detail()` - Calc Assets - Fixed Assets - Goodwill
   - `fn_calc_operating_cost()` - Revenue - Operating Income
   - `fn_calc_non_operating_cost()` - Non-Op Income + Finance Costs
   - `fn_calc_tax_cost()` - Tax Expense
   - `fn_calc_extraordinary_cost()` - Extraordinary Expense

2. **Temporal Metrics** (5 functions):
   - `fn_calc_ecf()` - Economic Cash Flow
   - `fn_calc_non_div_ecf()` - Non-Dividend ECF
   - `fn_calc_economic_equity()` - Economic Equity
   - `fn_calc_fy_tsr()` - FY Total Shareholder Return
   - `fn_calc_fy_tsr_prel()` - FY TSR Preliminary

3. **Derived Metrics** (2 functions):
   - `fn_calc_book_equity()` - Book Equity
   - `fn_calc_roa()` - Return on Assets

### Function Pattern
```sql
CREATE OR REPLACE FUNCTION fn_calc_[metric](p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  [output_column] NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT f1.ticker, f1.fiscal_year, calculation...
  FROM cissa.fundamentals f1
  INNER JOIN cissa.fundamentals f2...
  WHERE f1.dataset_id = p_dataset_id AND ...;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

---

## 8. CONFIGURATION

### Application Settings (`core/config.py`)
```python
class Settings(BaseSettings):
    DATABASE_URL: str                    # From env variable
    fastapi_env: str = "development"
    log_level: str = "info"
    workers: int = 1
    metrics_batch_size: int = 1000
    metrics_timeout_seconds: int = 300
```

### Metric Units Configuration
- Location: `backend/database/config/metric_units.json`
- Maps metric names to units (loaded into `metric_units` table)
- Used for query response enrichment

---

## 9. KEY DESIGN PATTERNS

### 1. Dependency Injection
- FastAPI `Depends()` for injecting `AsyncSession`
- Services receive sessions in constructors
- Repositories receive sessions in constructors

### 2. Layered Architecture
```
Endpoints (Validation, HTTP)
    ↓
Services (Business Logic)
    ↓
Repositories (Data Access)
    ↓
Database (Async SQLAlchemy)
```

### 3. Parameter Override Pattern
- Baseline parameters in `parameters` table
- Overrides in `parameter_sets.param_overrides` (JSONB)
- Service merges them on retrieval

### 4. Immutable Data with Versioning
- `dataset_versions` tracks all ingestion runs
- `raw_data` stores immutable input
- `fundamentals` stores cleaned/aligned data
- All linked via `dataset_id` foreign key

### 5. Caching Strategy
- Beta and Risk-Free Rate endpoints return cached results if already calculated
- Status field indicates "success", "error", or "cached"

### 6. Temporal Data Handling
- FISCAL records: fiscal_year only, fiscal_month/day NULL
- MONTHLY records: all components populated
- Uniqueness constraint uses COALESCE(month, 0), COALESCE(day, 0)

---

## 10. SUMMARY TABLE

| Aspect | Details |
|--------|---------|
| **Schema** | cissa (PostgreSQL 16+) |
| **Tables** | 11 (3 reference, 1 versioning, 1 raw, 2 cleaned, 2 config, 2 output) |
| **Primary Data** | companies, fundamentals, metrics_outputs |
| **API Framework** | FastAPI |
| **API Base** | /api/v1/ (v1 versioning) |
| **Main Endpoints** | /metrics/, /parameters/, /orchestration/ |
| **Response Format** | JSON (Pydantic models) |
| **Async Support** | Yes (AsyncSession, async/await) |
| **Connection Pool** | 10 connections, max 20 overflow |
| **Authentication** | None (currently open) |
| **Logging** | Structured to console |
| **ORM** | SQLAlchemy async |
| **Database Driver** | AsyncPG |
| **Migration Tool** | Custom schema_manager.py |

