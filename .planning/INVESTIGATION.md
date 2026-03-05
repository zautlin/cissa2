# Investigation: Migrating Calculation Scripts to New Backend

## Overview

Your project has two distinct systems:
1. **Legacy System** (`example-calculations/`): Python scripts using outdated data sources
2. **New Backend** (`backend/database/`): PostgreSQL schema with structured pipeline

The goal is to rewrite scripts like `generate_l1_metrics.py` to use the new backend's data model instead of legacy sources.

## Current State Analysis

### Legacy System Architecture (`example-calculations/`)

**Main entry point:** `generate_l2_metrics.py`
```
generate_l2_metrics()
  └─> calculate_L2_metrics_async()  [from calculation.py]
      ├─> thread_basic_metrics()
      │   └─> metrics.generate_l1_metrics_async()  [from executors/metrics.py]
      │       └─> generate_l1_metrics()  [per ticker]
      ├─> thread_beta_calculation()
      └─> thread_rates_calculation()
  └─> ld.load_L2_metrics_to_db()  [old database]
```

**Key data sources (legacy):**
- `annual_data` → SQL queries to old database
- `monthly_data` → SQL queries to old database  
- `rates` & `monthly_rf` → Manual CSV/Excel loads

**L1 Metric Calculations (line-by-line):**
```python
C_MC = spot_shares * share_price              # Market Cap
C_ASSETS = total_assets - cash                # Operating Assets
OA = C_ASSETS - fixed_assets - goodwill       # Operating Assets Detail
OP_COST = revenue - operating_income          # Operating Costs
NON_OP_COST = operating_income - PBT
TAX_COST = PBT - PAT_XO
XO_COST = PAT_XO - PAT
ECF = LAG_MC * (1 + FY_TSR / 100) - C_MC     # Economic Cash Flow (simplified)
EE = cumsum(PAT - ECF)                        # Economic Equity
```

---

## New Backend Architecture (`backend/database/`)

### Schema Structure (PostgreSQL)

**Three-tier pipeline:**

1. **Raw Data** (`raw_data`)
   - Immutable ingestion: all CSV rows as-is
   - Fields: `dataset_id`, `ticker`, `metric_name`, `period`, `numeric_value`

2. **Cleaned Data** (`fundamentals`) — **Main data source**
   - Cleaned, FY-aligned, imputed values
   - Fields: `dataset_id`, `ticker`, `metric_name`, `fiscal_year`, `numeric_value`, `imputed`
   - One row per (dataset, ticker, metric, fiscal_year)

3. **Outputs** (`metrics_outputs`)
   - Computed metrics from fundamentals + parameters
   - Fields: `dataset_id`, `param_set_id`, `ticker`, `fiscal_year`, `output_metric_name`, `output_metric_value`

**Configuration:**
- `parameters` → Master tunable parameters (risk_premium, tax_rate, franking, etc.)
- `parameter_sets` → Named bundles of parameter configurations
- `companies` → Master ticker list with sector, country, FY month

---

## Market Cap Example: From Legacy → New

### Legacy Implementation
```python
# From metrics.py line 29
group = group.assign(C_MC=lambda data: (data['shrouts'] * data['price']))
# shrouts = spot_shares (from old database)
# price = share_price (from old database)
```

**Data source:** SQL query to legacy tables
```sql
SELECT ticker, fy_year, shrouts, price FROM annual_data
```

---

### New Backend Implementation (Proposed)

**Option 1: SQL Stored Procedure (SIMPLE — start here)**

```sql
-- Function: Calculate Market Cap from fundamentals
CREATE OR REPLACE FUNCTION cissa.fn_market_cap(
  p_dataset_id UUID,
  p_param_set_id UUID
)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  calc_mc NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  WITH shares AS (
    SELECT ticker, fiscal_year, numeric_value as spot_shares
    FROM cissa.fundamentals
    WHERE dataset_id = p_dataset_id
      AND metric_name = 'Spot Shares'
      AND period_type = 'FISCAL'
  ),
  prices AS (
    SELECT ticker, fiscal_year, numeric_value as share_price
    FROM cissa.fundamentals
    WHERE dataset_id = p_dataset_id
      AND metric_name = 'Share Price'
      AND period_type = 'FISCAL'
  )
  SELECT 
    s.ticker,
    s.fiscal_year,
    (s.spot_shares * p.share_price) as calc_mc
  FROM shares s
  JOIN prices p USING (ticker, fiscal_year);
END;
$$ LANGUAGE plpgsql;

-- Usage:
SELECT * FROM cissa.fn_market_cap(
  p_dataset_id := '550e8400-e29b-41d4-a716-446655440000',
  p_param_set_id := '660e8400-e29b-41d4-a716-446655440001'
) WHERE ticker = 'NAB';
```

**Option 2: FastAPI Endpoint (for complex calculations)**

```python
# backend/app/endpoints/calculations.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/calculations", tags=["calculations"])

@router.post("/market-cap")
async def calculate_market_cap(
    dataset_id: UUID,
    param_set_id: UUID,
    session: AsyncSession = Depends(get_db)
) -> dict:
    """Calculate Market Cap from spot shares and share price"""
    result = await session.execute("""
        SELECT ticker, fiscal_year, 
               SUM(spot_shares * share_price) as calc_mc
        FROM v_market_cap_calc
        WHERE dataset_id = :dataset_id
        GROUP BY ticker, fiscal_year
    """, {"dataset_id": dataset_id})
    
    return {
        "dataset_id": str(dataset_id),
        "param_set_id": str(param_set_id),
        "rows": result.mappings().all()
    }
```

**Option 3: Python Migration Script**

```python
# backend/scripts/calculate_l1_metrics.py
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import Fundamentals, MetricsOutput

async def calculate_market_cap(
    session: AsyncSession,
    dataset_id: UUID,
    param_set_id: UUID
):
    """Calculate market cap from fundamentals"""
    
    # Query spot shares and prices
    stmt = select(Fundamentals).filter(
        Fundamentals.dataset_id == dataset_id,
        Fundamentals.metric_name.in_(['Spot Shares', 'Share Price']),
        Fundamentals.period_type == 'FISCAL'
    )
    
    results = await session.execute(stmt)
    fundamentals = results.scalars().all()
    
    # Group by ticker and FY
    by_ticker_fy = {}
    for row in fundamentals:
        key = (row.ticker, row.fiscal_year)
        if key not in by_ticker_fy:
            by_ticker_fy[key] = {}
        by_ticker_fy[key][row.metric_name] = row.numeric_value
    
    # Calculate and insert
    for (ticker, fy), metrics in by_ticker_fy.items():
        if 'Spot Shares' in metrics and 'Share Price' in metrics:
            mc = metrics['Spot Shares'] * metrics['Share Price']
            
            output = MetricsOutput(
                dataset_id=dataset_id,
                param_set_id=param_set_id,
                ticker=ticker,
                fiscal_year=fy,
                output_metric_name='Calc MC',
                output_metric_value=mc
            )
            session.add(output)
    
    await session.commit()
```

---

## Migration Strategy: 3-Phase Approach

### Phase 1: Simple Metrics (SQL-Only)
**Timeline: 1-2 weeks**
- Stored procedures for basic calculations
- No interdependencies
- Direct mapping from fundamentals

**Metrics to migrate:**
- Market Cap (C_MC)
- Operating Assets (C_ASSETS, OA)
- Cost components (OP_COST, NON_OP_COST, TAX_COST, XO_COST)
- FY TSR (from historical data)

**Approach:**
```sql
-- Each metric = one function
fn_market_cap()
fn_operating_assets()
fn_cost_components()
-- Store outputs to metrics_outputs table
```

---

### Phase 2: Intermediate Metrics (Python + SQL)
**Timeline: 3-4 weeks**
- Calculations with temporal logic (lags, cumulative sums)
- Economic Cash Flow (ECF) — uses prior year market cap
- Economic Equity (EE) — cumulative calculation

**Approach:**
```python
# FastAPI endpoint that:
# 1. Queries Phase 1 outputs from metrics_outputs
# 2. Applies temporal logic (groupby ticker, sort by fy)
# 3. Inserts Phase 2 results
# 4. Can be scheduled as background job
```

---

### Phase 3: Complex Optimization (Full Backend Integration)
**Timeline: 4-6 weeks**
- Black-Litterman model, Beta calculations, FVECF
- Optimization loops
- Full project migration to FastAPI

**Out of scope for now** ✓

---

## Starting Point: Market Cap Example

### Step 1: Create SQL Function

```sql
CREATE OR REPLACE FUNCTION cissa.fn_calculate_market_cap(
  p_dataset_id UUID
)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  market_cap NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  WITH pivot_data AS (
    SELECT 
      ticker,
      fiscal_year,
      metric_name,
      numeric_value
    FROM cissa.fundamentals
    WHERE dataset_id = p_dataset_id
      AND metric_name IN ('Spot Shares', 'Share Price')
      AND period_type = 'FISCAL'
  )
  SELECT 
    ticker,
    fiscal_year,
    MAX(CASE WHEN metric_name = 'Spot Shares' THEN numeric_value END) * 
    MAX(CASE WHEN metric_name = 'Share Price' THEN numeric_value END) AS market_cap
  FROM pivot_data
  GROUP BY ticker, fiscal_year;
END;
$$ LANGUAGE plpgsql;
```

### Step 2: Python Script to Call Function & Store Results

```python
# backend/scripts/populate_l1_metrics.py
import asyncio
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

async def populate_market_cap_metric(
    dataset_id: UUID,
    param_set_id: UUID,
    db_url: str = "postgresql+asyncpg://..."
):
    engine = create_async_engine(db_url)
    
    async with AsyncSession(engine) as session:
        # Call SQL function
        result = await session.execute(
            text("""
                SELECT ticker, fiscal_year, market_cap
                FROM cissa.fn_calculate_market_cap(:dataset_id)
            """),
            {"dataset_id": str(dataset_id)}
        )
        
        rows = result.mappings().all()
        
        # Insert into metrics_outputs
        insert_stmt = text("""
            INSERT INTO cissa.metrics_outputs 
            (dataset_id, param_set_id, ticker, fiscal_year, 
             output_metric_name, output_metric_value)
            VALUES (:dataset_id, :param_set_id, :ticker, :fy, 
                    'Calc MC', :mc)
            ON CONFLICT DO NOTHING
        """)
        
        for row in rows:
            await session.execute(insert_stmt, {
                "dataset_id": str(dataset_id),
                "param_set_id": str(param_set_id),
                "ticker": row.ticker,
                "fy": row.fiscal_year,
                "mc": row.market_cap
            })
        
        await session.commit()
        print(f"✓ Populated {len(rows)} market cap rows")

# Usage:
# asyncio.run(populate_market_cap_metric(
#   dataset_id=UUID('550e8400-e29b-41d4-a716-446655440000'),
#   param_set_id=UUID('660e8400-e29b-41d4-a716-446655440001')
# ))
```

### Step 3: Update generate_l1_metrics.py

```python
# backend/scripts/generate_l1_metrics.py
import asyncio
from uuid import UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from backend.scripts.populate_l1_metrics import populate_market_cap_metric

async def generate_l1_metrics_async(
    dataset_id: UUID,
    param_set_id: UUID,
    parameter_set: dict
):
    """Generate L1 metrics from new backend"""
    
    # Phase 1 metrics (SQL-only)
    await populate_market_cap_metric(dataset_id, param_set_id)
    await populate_operating_assets_metric(dataset_id, param_set_id)
    await populate_cost_components_metric(dataset_id, param_set_id)
    
    print("✓ L1 metrics generated successfully")

# Usage in FastAPI endpoint:
@app.post("/api/metrics/generate-l1")
async def generate_l1(
    dataset_id: UUID,
    param_set_id: UUID = None
):
    if not param_set_id:
        # Get default parameter set
        param_set_id = UUID('660e8400-e29b-41d4-a716-446655440001')
    
    await generate_l1_metrics_async(dataset_id, param_set_id, {})
    return {"status": "success", "dataset_id": str(dataset_id)}
```

---

## Key Data Mapping: Legacy → New

| Legacy Table | Legacy Field | New Table | New Metric Name |
|--------------|--------------|-----------|-----------------|
| annual_data | shrouts | fundamentals | Spot Shares |
| annual_data | price | fundamentals | Share Price |
| annual_data | revenue | fundamentals | Revenue |
| annual_data | opincome | fundamentals | Op Income |
| annual_data | pbt | fundamentals | PBT |
| annual_data | patxo | fundamentals | PAT XO |
| annual_data | pat | fundamentals | PAT |
| annual_data | assets | fundamentals | Total Assets |
| annual_data | cash | fundamentals | Cash |
| annual_data | fixedassets | fundamentals | Fixed Assets |
| annual_data | goodwill | fundamentals | Goodwill |
| annual_data | eqiity | fundamentals | Total Equity |
| annual_data | mi | fundamentals | Minority Interest |
| annual_data | dividend | fundamentals | Div |

---

## Implementation Checklist

- [ ] **Part 1: Verify new schema exists**
  - [ ] Connect to PostgreSQL
  - [ ] Check `cissa.fundamentals` table exists
  - [ ] Verify metric names match expectations (Spot Shares, Share Price, etc.)

- [ ] **Part 2: Create SQL functions for Phase 1**
  - [ ] `fn_market_cap()` — Market Cap (Spot Shares × Share Price)
  - [ ] `fn_operating_assets()` — Total Assets - Cash
  - [ ] `fn_cost_components()` — Revenue-based cost derivations
  - [ ] Test each with sample queries

- [ ] **Part 3: Python backend integration**
  - [ ] Add models for MetricsOutput if not exist
  - [ ] Create `backend/scripts/populate_l1_metrics.py`
  - [ ] Create FastAPI endpoint `/api/metrics/generate-l1`
  - [ ] Test with sample dataset_id

- [ ] **Part 4: Replace legacy script**
  - [ ] Rewrite `generate_l1_metrics.py` to call new endpoint
  - [ ] Remove dependencies on legacy database
  - [ ] Add integration test

---

## Next Steps

1. **Confirm database structure**: Are `cissa.fundamentals` and metric names ready?
2. **Pick first metric**: Market Cap is simplest. Create the SQL function as template.
3. **Test retrieval**: Query fundamentals directly: `SELECT * FROM cissa.fundamentals WHERE metric_name IN ('Spot Shares', 'Share Price') LIMIT 10`
4. **Plan full Phase 1**: List all ~15 simple metrics, create functions, populate outputs table
5. **Iterate Phase 2**: Once Phase 1 is solid, tackle ECF/EE with temporal logic
