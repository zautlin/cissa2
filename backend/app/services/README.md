# Services Architecture

The services layer contains the business logic for calculating financial metrics in the CISSA pipeline. Each service is organized around a specific domain or calculation phase.

## Service Catalog

### Phase-Based Services (Recommended)

These services implement specific calculation phases in the pipeline. They follow a consistent pattern: fetch data, vectorize calculations with Pandas, and batch-insert results.

| Service | Phase | Calculates | Input Sources | Output Level |
|---------|-------|-----------|----------------|--------------|
| **RiskFreeRateService** | 08 | Rf, Rf_1Y, Rf_1Y_Raw | Market data (GACGB10) | L1 |
| **BetaService** | 07 | Beta | Historical returns data | L1 |
| **CostOfEquityService** | 09 | KE (Cost of Equity) | Beta, Rf_1Y, Risk Premium | L1 |
| **EconomicProfitService** | 10a | EP, PAT_EX, XO_COST_EX, FC | Fundamentals, EE, KE (lagged) | L2 |

### Generic Services (Legacy)

These services provide generic metric calculation interfaces. They are used for simpler metrics that don't require complex orchestration.

| Service | Purpose | Recommended Use |
|---------|---------|-----------------|
| **MetricsService** | Generic L1 metric calculation via SQL functions | Ad-hoc metric queries, simple calculations |
| **L2MetricsService** | Generic L2 metric orchestration | Legacy support, general L2 calculations |

---

## Detailed Service Documentation

### RiskFreeRateService

**File:** `risk_free_rate_service.py` (Phase 08)

**Purpose:** Calculates risk-free rate (Rf) metrics using historical bond yields.

**Metrics Calculated:**
- `Rf`: Risk-free rate
- `Rf_1Y`: 1-year risk-free rate (geometric mean of monthly yields)
- `Rf_1Y_Raw`: Raw 1-year risk-free rate

**Input Data:**
- Market data source: GACGB10 Index (Australian 10-year government bonds)
- Historical monthly yield data

**Output:**
- `cissa.metrics_outputs` table with `metric_level="L1"`

**Implementation Details:**
- Geometric mean calculation for monthly yields
- Handles missing data gracefully
- Vectorized Pandas operations
- Batch database inserts (1000 records per batch)

**API Endpoint:** `POST /api/v1/metrics/calculate-risk-free-rate`

**Example Usage:**
```python
from app.services import RiskFreeRateCalculationService

service = RiskFreeRateCalculationService(session)
result = await service.calculate_risk_free_rates(
    dataset_id=uuid_obj,
    param_set_id=uuid_obj
)
# Returns: {"status": "success", "records_inserted": 1000, "message": "..."}
```

---

### BetaService

**File:** `beta_calculation_service.py` (Phase 07)

**Purpose:** Calculates Beta coefficient using rolling OLS regression on monthly stock returns.

**Metrics Calculated:**
- `Beta`: Systematic risk measure relative to market index

**Input Data:**
- Historical monthly stock returns
- Market index returns
- Rolling window: typically 60 months

**Output:**
- `cissa.metrics_outputs` table with `metric_level="L1"`

**Implementation Details:**
- Rolling OLS regression (60-month window)
- Handles missing data periods
- Vectorized NumPy/Pandas operations
- Batch database inserts

**API Endpoint:** `POST /api/v1/metrics/calculate-beta`

**Example Usage:**
```python
from app.services import BetaCalculationService

service = BetaCalculationService(session)
result = await service.calculate_beta(
    dataset_id=uuid_obj,
    param_set_id=uuid_obj
)
```

---

### CostOfEquityService

**File:** `cost_of_equity_service.py` (Phase 09)

**Purpose:** Calculates Cost of Equity (KE) using the Capital Asset Pricing Model (CAPM).

**Formula:**
```
KE = Rf + Beta × RiskPremium
```

**Where:**
- `Rf`: Risk-free rate (from Phase 08)
- `Beta`: Systematic risk (from Phase 07)
- `RiskPremium`: Market risk premium (from parameter_sets)

**Metrics Calculated:**
- `Calc KE`: Cost of Equity

**Input Data:**
- Phase 07: Beta values from `cissa.metrics_outputs`
- Phase 08: Rf_1Y values from `cissa.metrics_outputs`
- Parameter set: Risk premium per country/market

**Output:**
- `cissa.metrics_outputs` table with `metric_level="L1"` and `output_metric_name="Calc KE"`

**Prerequisites:**
- Phase 07 (Beta) must be completed
- Phase 08 (Risk-free rate) must be completed

**Implementation Details:**
- No recalculation of Beta or Rf (reuses existing outputs)
- Vectorized Pandas operations (no row-by-row iteration)
- Batch database inserts (1000 records per batch)
- Metadata includes: `calculation_source: "cost_of_equity_service"`

**API Endpoint:** `POST /api/v1/metrics/calculate-cost-of-equity`

**Example Usage:**
```python
from app.services import CostOfEquityService

service = CostOfEquityService(session)
result = await service.calculate_cost_of_equity(
    dataset_id=uuid_obj,
    param_set_id=uuid_obj
)
# Returns: {"status": "success", "records_inserted": 9189, "message": "..."}
```

**Database Verification:**
```sql
SELECT COUNT(*), output_metric_name
FROM cissa.metrics_outputs
WHERE output_metric_name = 'Calc KE'
GROUP BY output_metric_name;
```

---

### EconomicProfitService

**File:** `economic_profit_service.py` (Phase 10a)

**Purpose:** Calculates core L2 metrics including Economic Profit (EP) and related metrics.

**Metrics Calculated:**
1. **EP** (Economic Profit): `pat - (ke_open × ee_open)`
2. **PAT_EX** (Adjusted Profit): `(ep / |ee_open + ke_open|) × ee_open`
3. **XO_COST_EX** (Adjusted XO Cost): `patxo - pat_ex`
4. **FC** (Franking Credit): Conditional based on `incl_franking` parameter

**Input Data:**
- Fundamentals table: `PROFIT_AFTER_TAX`, `PROFIT_AFTER_TAX_EX`, `DIVIDENDS`
- Metrics outputs (Phase 06): `EE` (Economic Equity)
- Metrics outputs (Phase 09): `Calc KE` (Cost of Equity)
- Lagged versions: Created via LEFT JOIN on prior fiscal year

**Output:**
- `cissa.metrics_outputs` table with `metric_level="L2"`
- Expected: ~7,078 base records × 4 metrics = ~28,312 total records

**Prerequisites:**
- Phase 06 (L1 Basic Metrics: PAT, PATXO, EE) must be completed
- Phase 09 (Cost of Equity: KE) must be completed

**Key Implementation Details:**

**Lagged Data Handling:**
- Creates "opened" versions: `fiscal_year + 1`, with `_open` suffix
- LEFT JOIN preserves NaN for missing prior years (matches legacy behavior)
- Only rows with complete lagged data produce non-NaN metrics

**NaN Handling:**
- Calculations include NaN rows (results in NaN)
- Insert logic skips NaN metric values (database column is NOT NULL)
- Preserves legacy approach: calculate all rows, insert valid ones

**Vectorized Calculations:**
- All math operations on Pandas Series (no row-by-row iteration)
- Batch database inserts (1000 records per batch)

**Metadata:**
- Each record includes: `calculation_source: "economic_profit_service"`

**Parameters Used:**
- `incl_franking`: "Yes" or "No" (from parameter_sets)
- `frank_tax_rate`: Franking tax rate (e.g., 0.30)
- `value_franking_cr`: Franking credit value (e.g., 0.75)

**API Endpoint:** `POST /api/v1/metrics/l2-core/calculate`

**Example Usage:**
```python
from app.services import EconomicProfitService

service = EconomicProfitService(session)
result = await service.calculate_core_l2_metrics(
    dataset_id=uuid_obj,
    param_set_id=uuid_obj
)
# Returns: {"status": "success", "records_calculated": 7078, "records_inserted": 28312, "message": "..."}
```

**Database Verification:**
```sql
-- Count L2 metrics by type
SELECT output_metric_name, COUNT(*) as count
FROM cissa.metrics_outputs
WHERE output_metric_name IN ('EP', 'PAT_EX', 'XO_COST_EX', 'FC')
GROUP BY output_metric_name
ORDER BY output_metric_name;

-- Verify EP formula: EP = PAT - (KE_open * EE_open)
SELECT 
    mo_ep.ticker,
    mo_ep.fiscal_year,
    mo_ep.output_metric_value as ep_db,
    f.numeric_value as pat,
    mo_ke.output_metric_value as ke_open,
    mo_ee.output_metric_value as ee_open,
    (f.numeric_value - (mo_ke.output_metric_value * mo_ee.output_metric_value)) as ep_calculated
FROM cissa.metrics_outputs mo_ep
LEFT JOIN cissa.fundamentals f
    ON mo_ep.ticker = f.ticker 
    AND mo_ep.fiscal_year = f.fiscal_year 
    AND f.metric_name = 'PROFIT_AFTER_TAX'
LEFT JOIN cissa.metrics_outputs mo_ke
    ON mo_ep.ticker = mo_ke.ticker 
    AND mo_ep.fiscal_year - 1 = mo_ke.fiscal_year 
    AND mo_ke.output_metric_name = 'Calc KE'
LEFT JOIN cissa.metrics_outputs mo_ee
    ON mo_ep.ticker = mo_ee.ticker 
    AND mo_ep.fiscal_year - 1 = mo_ee.fiscal_year 
    AND mo_ee.output_metric_name = 'EE'
WHERE mo_ep.output_metric_name = 'EP'
LIMIT 10;
```

---

### MetricsService

**File:** `metrics_service.py` (Generic)

**Purpose:** Generic service layer for calculating L1 metrics via SQL functions.

**Supported Metrics:**
- **Simple L1** (7): Calc MC, Calc Assets, Calc OA, Calc Op Cost, Calc Non Op Cost, Calc Tax Cost, Calc XO Cost
- **Temporal L1** (5): ECF, NON_DIV_ECF, EE, FY_TSR (param-sensitive), FY_TSR_PREL (param-sensitive)
- **Legacy L2+** (6): Profit Margin, Op Cost Margin %, Eff Tax Rate, FA Intensity, Book Equity, ROA

**Implementation:**
- Maps metric names to SQL functions
- Executes SQL function from database
- Returns results from specified column

**API Endpoint:** `POST /api/v1/metrics/calculate-metric`

**Note:** This is a legacy generic service. For new phases, use phase-specific services.

---

### L2MetricsService

**File:** `l2_metrics_service.py` (Generic)

**Purpose:** Generic orchestration layer for L2 metric calculations.

**Approach:**
- Fetches L1 metrics + fundamentals
- Combines inputs via Pandas merge
- Calculates derived L2 metrics (Asset Efficiency, Operating Leverage, etc.)
- Inserts results into database

**Note:** This is a legacy generic service. For new phases, use phase-specific services like `EconomicProfitService`.

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    CISSA Pipeline Flow                       │
└─────────────────────────────────────────────────────────────┘

Raw Market Data
      ↓
   Phase 08
   Risk-Free Rate Service
   ├─ Input: Market yields (GACGB10)
   ├─ Output: Rf, Rf_1Y, Rf_1Y_Raw (L1)
   └─ → cissa.metrics_outputs

Historical Returns
      ↓
   Phase 07
   Beta Service
   ├─ Input: Stock returns, market returns
   ├─ Output: Beta (L1)
   └─ → cissa.metrics_outputs

   Phase 09: Cost of Equity Service
   ├─ Inputs:
   │  ├─ Phase 07: Beta (from metrics_outputs)
   │  ├─ Phase 08: Rf_1Y (from metrics_outputs)
   │  └─ Parameters: Risk Premium
   ├─ Formula: KE = Rf + Beta × RiskPremium
   ├─ Output: Calc KE (L1)
   └─ → cissa.metrics_outputs

Fundamentals Data
      ↓
   Phase 06 (SQL Functions)
   ├─ Output: PAT, PATXO, EE, etc. (L1)
   └─ → cissa.metrics_outputs

   Phase 10a: Economic Profit Service
   ├─ Inputs:
   │  ├─ Phase 06: PAT, PATXO (from fundamentals)
   │  ├─ Phase 06: EE (from metrics_outputs)
   │  ├─ Phase 09: Calc KE (from metrics_outputs, lagged)
   │  └─ Parameters: incl_franking, frank_tax_rate
   ├─ Formulas:
   │  ├─ EP = PAT - (KE_open × EE_open)
   │  ├─ PAT_EX = (EP / |EE_open + KE_open|) × EE_open
   │  ├─ XO_COST_EX = PATXO - PAT_EX
   │  └─ FC = (conditional on incl_franking)
   ├─ Output: EP, PAT_EX, XO_COST_EX, FC (L2)
   └─ → cissa.metrics_outputs

   Future Phases:
   ├─ Phase 10b: FV ECF Metrics
   ├─ Phase 10c: Financial Ratios
   └─ Phase 11: Valuation Models
```

---

## Database Schema Overview

### Key Tables

**cissa.metrics_outputs**
```sql
-- Stores all calculated metrics (L1, L2, etc.)
CREATE TABLE cissa.metrics_outputs (
    output_id UUID PRIMARY KEY,
    ticker VARCHAR NOT NULL,
    fiscal_year INT NOT NULL,
    output_metric_name VARCHAR NOT NULL,    -- e.g., "Calc KE", "EP", "Beta"
    output_metric_value NUMERIC NOT NULL,   -- Calculated metric value
    dataset_id UUID,
    metric_level VARCHAR,                   -- "L1", "L2", "L3", etc.
    metadata JSONB,                         -- {"calculation_source": "cost_of_equity_service"}
    created_at TIMESTAMP DEFAULT NOW()
);

-- Key columns for service usage:
CREATE INDEX idx_metrics_outputs_ticker_fiscal_year 
    ON cissa.metrics_outputs(ticker, fiscal_year);
CREATE INDEX idx_metrics_outputs_metric_name 
    ON cissa.metrics_outputs(output_metric_name);
```

**cissa.fundamentals**
```sql
-- Base company data
CREATE TABLE cissa.fundamentals (
    ticker VARCHAR NOT NULL,
    fiscal_year INT NOT NULL,
    metric_name VARCHAR NOT NULL,           -- e.g., "PROFIT_AFTER_TAX", "PROFIT_AFTER_TAX_EX"
    numeric_value NUMERIC,                  -- Fundamental value
    dataset_id UUID
);
```

**cissa.parameter_sets**
```sql
-- Configuration for metric calculations
CREATE TABLE cissa.parameter_sets (
    param_set_id UUID PRIMARY KEY,
    param_overrides JSONB NOT NULL,         -- {"risk_premium": 0.05, "incl_franking": "Yes", ...}
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Common Workflows

### 1. Calculate Phase 09 (Cost of Equity)

```python
from app.core.database import get_db_manager
from app.services import CostOfEquityService
from uuid import UUID
import asyncio

async def calculate_ke():
    db_manager = get_db_manager()
    await db_manager.initialize()
    
    async with db_manager.session_factory() as session:
        service = CostOfEquityService(session)
        result = await service.calculate_cost_of_equity(
            dataset_id=UUID("c753dc4f-d547-436a-bb14-4128fa4a2281"),
            param_set_id=UUID("380e6916-125e-4fb2-8c33-a13773dc51af")
        )
        print(f"Status: {result['status']}")
        print(f"Records inserted: {result['records_inserted']}")
    
    await db_manager.close()

asyncio.run(calculate_ke())
```

### 2. Calculate Phase 10a (Economic Profit)

```python
from app.services import EconomicProfitService

async def calculate_ep():
    db_manager = get_db_manager()
    await db_manager.initialize()
    
    async with db_manager.session_factory() as session:
        service = EconomicProfitService(session)
        result = await service.calculate_core_l2_metrics(
            dataset_id=dataset_uuid,
            param_set_id=param_set_uuid
        )
        
        if result["status"] == "success":
            print(f"Calculated: {result['records_calculated']} base records")
            print(f"Inserted: {result['records_inserted']} metric records")
    
    await db_manager.close()

asyncio.run(calculate_ep())
```

### 3. Query Results

```python
from sqlalchemy import text

async def query_metrics():
    async with db_manager.session_factory() as session:
        # Get all Cost of Equity values
        result = await session.execute(text("""
            SELECT ticker, fiscal_year, output_metric_value
            FROM cissa.metrics_outputs
            WHERE output_metric_name = 'Calc KE'
            ORDER BY ticker, fiscal_year
            LIMIT 100
        """))
        
        for row in result.fetchall():
            ticker, fy, ke = row
            print(f"{ticker} FY{fy}: KE={ke:.4f}")
```

---

## Performance Considerations

### Vectorized Operations

All phase-based services use vectorized Pandas operations:
- **Good:** Operations on entire Series/DataFrame at once
- **Avoid:** Row-by-row iteration with `.iterrows()` or `.apply()`

### Batch Database Inserts

Inserts are batched (default 1000 records per batch):
- Reduces database round trips
- Improves insertion performance
- Easier transaction management

### Connection Pooling

Database uses async connection pooling:
- Pool size: 10
- Max overflow: 20
- Pre-ping enabled (tests connections before use)

---

## Troubleshooting

### Issue: "Phase 07 Beta results not found"
**Cause:** Phase 07 must be completed before Phase 09
**Solution:** Run Beta service first

### Issue: "No matching rows after merging"
**Cause:** Input data (Beta + Rf) missing for some tickers
**Solution:** Check Phase 07 + 08 completion for all tickers

### Issue: "NaN values in output"
**Cause:** Missing lagged data (first year of data has no prior year)
**Solution:** Normal - first year rows are skipped during insert

### Issue: Slow calculation
**Cause:** Row-by-row iteration instead of vectorization
**Solution:** Use phase-specific services (properly vectorized)

---

## Future Roadmap

### Phase 10b: FV ECF Metrics
- Calculate projected Free Cash Flow ECF with 1Y, 3Y, 5Y, 10Y intervals
- Dependencies: Phase 10a (Economic Profit)

### Phase 10c: Financial Ratios
- Derive financial ratios from core L2 metrics
- Dependencies: Phase 10a (Economic Profit)

### Phase 11: Valuation Models
- DCF valuation using FV ECF projections
- Dependencies: Phase 10b (FV ECF)

---

## Contributing

When adding a new service:

1. **Follow the naming convention:** Domain-focused (e.g., `DividendPolicyService`)
2. **Inherit pattern from phase services:** Fetch, vectorize, batch-insert
3. **Use async/await:** All database operations async
4. **Document:** Update this README with service details
5. **Include metadata:** Track `calculation_source` in database metadata
6. **Add verification:** Include SQL queries to verify results
7. **Test:** Verify calculations against legacy code or external sources

---

## See Also

- `backend/app/api/v1/endpoints/metrics.py` - API endpoints
- `backend/app/models/` - Data models
- `backend/database/` - Database configuration and schema
- `example-calculations/` - Legacy calculation code reference
