# Phase 07: Beta Calculation Implementation Plan

**Status**: Ready for Implementation  
**Last Updated**: 2026-03-09  
**Phase Goal**: Port legacy beta calculation into async Python backend service with parameter sensitivity

---

## Executive Summary

This document provides the complete implementation plan for Phase 07, detailing:
- Architecture and design patterns
- Code structure for each task
- Step-by-step implementation guide
- Integration points with existing systems
- Testing strategy and validation approach

**Key Design Decisions**:
1. Synchronous API with inline processing (no job queueing)
2. Upsert logic: Skip if results already exist (dataset_id + param_set_id + ticker + fiscal_year + metric)
3. Dynamic window for RollingOLS: Use min(60, available_months) if <60 months available
4. Replicate legacy algorithm exactly (no optimizations)

---

## Part 1: Architecture & Design

### 1.1 Data Flow

```
POST /api/v1/metrics/beta/calculate
  ↓
BetaCalculationService.calculate_beta_async()
  ├─ Fetch monthly returns (COMPANY_TSR, INDEX_TSR)
  ├─ Calculate rolling OLS slopes (60-month window)
  ├─ Transform slopes: adjusted = (slope * 2/3) + 1/3
  ├─ Filter by error tolerance
  ├─ Round by beta_rounding
  ├─ Annualize: group by fiscal_year
  ├─ Generate sector averages
  ├─ Apply 4-tier fallback logic
  ├─ Apply approach_to_ke logic (FIXED vs Floating)
  └─ Store in metrics_outputs
  ↓
Return: {status: "success", results_count: N, metrics: [...]}
```

### 1.2 Service Architecture

**Service Layer**: `BetaCalculationService`
- Location: `/home/ubuntu/cissa/backend/app/services/beta_calculation_service.py`
- Responsibilities:
  - Fetch data from `cissa.fundamentals`
  - Execute OLS regression via statsmodels
  - Apply transformations and fallback logic
  - Store results via MetricsRepository
- Dependencies:
  - AsyncSession (from sqlalchemy.ext.asyncio)
  - pandas, numpy, statsmodels
  - MetricsRepository
  - Logger

**API Layer**: Endpoint in `metrics.py`
- Location: `/home/ubuntu/cissa/backend/app/api/v1/endpoints/metrics.py`
- Endpoint: `POST /api/v1/metrics/beta/calculate`
- Request body: `{dataset_id: UUID, param_set_id: UUID}`
- Response: `{status: str, results_count: int, message: str}`

**Repository Layer**: MetricsRepository (existing)
- Location: `/home/ubuntu/cissa/backend/app/repositories/metrics_repository.py`
- Methods used: `batch_insert_metrics()` for storing results

### 1.3 Key Dependencies

**New Dependencies to Add**:
```
statsmodels>=0.14.0  # For RollingOLS regression
```

**Existing Dependencies**:
- pandas (already in requirements.txt)
- numpy (already in requirements.txt)
- sqlalchemy async (already in requirements.txt)

---

## Part 2: Implementation Tasks

### Task 1: Research & Data Validation

**Objective**: Validate data structure and completeness before service implementation

**Subtasks**:

1. **Query and analyze monthly returns data**
   - Script location: Create ad-hoc query script (not part of permanent codebase)
   - Verify COMPANY_TSR and INDEX_TSR in fundamentals table
   - Check data completeness by ticker and sector
   - Identify tickers with <60 months

2. **Validate sector mapping**
   - Query companies table
   - Verify all tickers have sector assignment (except special cases like AS30 Index)
   - Check for null sectors

3. **Data quality checks**
   - Check for null numeric_value in returns data
   - Check for duplicate (ticker, fiscal_year, fiscal_month) records
   - Verify fiscal_month is in range 1-12

**Acceptance Criteria**:
- [ ] Data validation script runs without errors
- [ ] All tickers with <60 months identified
- [ ] Sector mapping complete for non-index tickers
- [ ] No data quality blockers identified
- [ ] Documentation of findings in markdown

**Deliverable**: Analysis report (ad-hoc, not stored)

---

### Task 2: Database Parameters & Metric Units

**Objective**: Ensure all required database configuration is in place

**Subtasks**:

1. **Verify parameters exist** (should already be in place from schema)
   - Verify: `cost_of_equity_approach` parameter exists (value="Floating")
   - Verify: `beta_rounding` parameter exists (value=0.1)
   - Verify: `beta_relative_error_tolerance` parameter exists (value=40.0)
   - Write verification script to confirm

2. **Add "Beta" to metric_units** (if not present)
   - Check if "Beta" exists in `cissa.metric_units` table
   - If missing: Insert `{metric_name: "Beta", unit: "%"}`

3. **Verify parameter_sets support**
   - Confirm "base_case" parameter_set exists
   - Verify param_overrides JSONB support works

4. **Update metric_units.json** (backend config)
   - Add Beta entry to `/home/ubuntu/cissa/backend/database/config/metric_units.json`
   - Entry: `{metric_name: "Beta", unit: "%", is_output_metric: true}`

**Acceptance Criteria**:
- [ ] All 3 beta parameters in parameters table
- [ ] "Beta" metric in metric_units table
- [ ] metric_units.json updated
- [ ] Verification script passes
- [ ] Parameter loading in service works with beta parameters

**Files to Modify**:
- `/home/ubuntu/cissa/backend/database/config/metric_units.json` — Add Beta entry

**Files to Review**:
- `/home/ubuntu/cissa/backend/database/schema/schema.sql` — Verify parameter initialization
- `/home/ubuntu/cissa/backend/app/services/enhanced_metrics_service.py` — Reference for parameter loading

**Estimated Effort**: 2-3 hours

---

### Task 3: Implement BetaCalculationService

**Objective**: Create the core service that replicates legacy beta calculation logic

**Location**: `/home/ubuntu/cissa/backend/app/services/beta_calculation_service.py` (NEW FILE)

**Class Structure**:

```python
class BetaCalculationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MetricsRepository(session)
        self.logger = get_logger(__name__)
    
    async def calculate_beta_async(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
    ) -> dict:
        """Main orchestration method"""
        
    async def _load_parameters_from_db(self, param_set_id: UUID) -> dict:
        """Load parameters from database with overrides"""
        
    async def _fetch_monthly_returns(self, dataset_id: UUID) -> pd.DataFrame:
        """Fetch COMPANY_TSR and INDEX_TSR from fundamentals"""
        
    def _calculate_rolling_ols(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate 60-month rolling OLS slopes"""
        
    def _transform_slopes(
        self,
        df: pd.DataFrame,
        error_tolerance: float,
        beta_rounding: float
    ) -> pd.DataFrame:
        """Apply transformation, error filtering, rounding"""
        
    def _annualize_slopes(self, beta_df: pd.DataFrame) -> pd.DataFrame:
        """Group by fiscal_year to get annual slopes"""
        
    def _generate_sector_slopes(self, annual_beta: pd.DataFrame) -> pd.DataFrame:
        """Calculate sector averages by year"""
        
    def _apply_4tier_fallback(
        self,
        annual_beta: pd.DataFrame,
        sector_slopes: pd.DataFrame
    ) -> pd.DataFrame:
        """Apply fallback logic: ticker → sector → ticker_avg → NaN"""
        
    def _apply_approach_to_ke(
        self,
        spot_betas: pd.DataFrame,
        approach_to_ke: str,
        beta_rounding: float
    ) -> pd.DataFrame:
        """Apply FIXED vs Floating logic"""
```

**Implementation Details**:

#### Method 1: `_fetch_monthly_returns()`

**Input**: dataset_id (UUID)

**Output**: DataFrame with columns:
- ticker: str
- fiscal_year: int
- fiscal_month: int
- company_tsr: float (Company TSR monthly %)
- index_tsr: float (Index TSR monthly %)

**SQL Query**:
```sql
SELECT
    c.ticker,
    c.fiscal_year,
    c.fiscal_month,
    c.numeric_value as company_tsr
FROM cissa.fundamentals c
WHERE c.dataset_id = :dataset_id
AND c.metric_name = 'COMPANY_TSR'
AND c.period_type = 'MONTHLY'

INNER JOIN (
    SELECT ticker, fiscal_year, fiscal_month, numeric_value as index_tsr
    FROM cissa.fundamentals
    WHERE dataset_id = :dataset_id
    AND metric_name = 'INDEX_TSR'
    AND period_type = 'MONTHLY'
) i ON c.ticker = c.ticker
       AND c.fiscal_year = i.fiscal_year
       AND c.fiscal_month = i.fiscal_month
WHERE i.ticker = 'AS30 Index'

ORDER BY c.ticker, c.fiscal_year, c.fiscal_month
```

**Key Logic**:
- Filter for INDEX_TSR where ticker = 'AS30 Index' (market returns)
- Inner join to ensure both company and market returns exist for same month
- Return only months where both exist

#### Method 2: `_calculate_rolling_ols()`

**Input**: DataFrame with company_tsr and index_tsr columns

**Output**: DataFrame with columns:
- ticker: str
- fiscal_year: int
- fiscal_month: int
- slope: float (raw OLS slope)
- std_err: float (standard error from OLS)

**Algorithm**:
```python
from statsmodels.regression.rolling import RollingOLS

# For each ticker:
for ticker in df['ticker'].unique():
    ticker_df = df[df['ticker'] == ticker].sort_values(['fiscal_year', 'fiscal_month'])
    
    # Prepare data: convert TSR % to returns (divide by 100, add 1)
    x = ticker_df['index_tsr'] / 100 + 1  # Market returns (independent var)
    y = ticker_df['company_tsr'] / 100 + 1  # Company returns (dependent var)
    
    # Dynamic window: 60 months if available, else all available months
    window = 60 if len(x) > 60 else len(x)
    
    # Run rolling OLS
    model = RollingOLS(y, x, window=window)
    result = model.fit()
    
    # Extract slopes and standard errors
    params = result.params  # slope values
    bse = result.bse  # standard errors
```

**Key Logic**:
- Convert TSR percentages to growth factors (TSR/100 + 1)
- Use dynamic window size based on data availability
- Extract both slope and standard error from OLS result
- Maintain (ticker, fiscal_year, fiscal_month) in output

#### Method 3: `_transform_slopes()`

**Input**: DataFrame from _calculate_rolling_ols()

**Output**: DataFrame with columns:
- ticker: str
- fiscal_year: int
- fiscal_month: int
- slope: float
- std_err: float
- rel_std_err: float (relative standard error)
- adjusted_slope: float (or NaN if filtered)

**Algorithm** (from legacy line 28-38):
```python
# Calculate relative standard error
df['rel_std_err'] = abs(df['std_err']) / ((abs(df['slope']) * 2 / 3) + 1 / 3)

# Apply transformation
df['slope_transformed'] = (df['slope'] * 2 / 3) + 1 / 3

# Filter by error tolerance and round
df['adjusted_slope'] = df.apply(
    lambda x: round((x['slope_transformed'] / beta_rounding), 4) * beta_rounding
    if error_tolerance >= x['rel_std_err']
    else np.nan,
    axis=1
)

return df[['ticker', 'fiscal_year', 'fiscal_month', 'slope', 'std_err', 'rel_std_err', 'adjusted_slope']]
```

**Key Logic**:
- relative_std_err = |std_err| / |(slope * 2/3 + 1/3)|
- If rel_std_err > error_tolerance: set adjusted_slope = NaN
- Apply transformation formula: (slope * 2/3 + 1/3)
- Round by beta_rounding (typically 0.1)

#### Method 4: `_annualize_slopes()`

**Input**: DataFrame with adjusted_slope by (ticker, fiscal_year, fiscal_month)

**Output**: DataFrame with columns:
- ticker: str
- fiscal_year: int (annualized year)
- sector: str
- adjusted_slope: float
- slope: float (original)
- std_err: float
- rel_std_err: float

**Algorithm** (from legacy line 44-52):
```python
# Get fiscal year dates mapping (from companies table)
# For each (ticker, fiscal_year): find the last month that belongs to that fiscal year

# Group by ticker, fiscal_year and take last month's values
annual_beta = df.groupby(['ticker', 'fiscal_year']).tail(1)

# Merge with sector information from companies table
annual_beta = annual_beta.merge(
    companies[['ticker', 'sector']],
    on='ticker'
)

return annual_beta[['ticker', 'fiscal_year', 'sector', 'adjusted_slope', 'slope', 'std_err', 'rel_std_err']]
```

**Key Logic**:
- For each (ticker, fiscal_year), take the last month's adjusted_slope value
- Add sector information from companies table
- Result: One row per (ticker, fiscal_year)

#### Method 5: `_generate_sector_slopes()`

**Input**: DataFrame from _annualize_slopes() with one row per (ticker, fiscal_year, sector)

**Output**: DataFrame with columns:
- sector: str
- fiscal_year: int
- sector_slope: float (mean adjusted_slope for sector that year)

**Algorithm** (from legacy line 55-59):
```python
sector_slopes = (
    df.groupby(['sector', 'fiscal_year'])
    .agg({'adjusted_slope': lambda x: x.mean(skipna=True)})
    .rename(columns={'adjusted_slope': 'sector_slope'})
    .reset_index()
)

return sector_slopes
```

**Key Logic**:
- Group by (sector, fiscal_year)
- Calculate mean of adjusted_slope (skip NaN)
- Result: One row per (sector, fiscal_year)

#### Method 6: `_apply_4tier_fallback()`

**Input**: 
- annual_beta: DataFrame with adjusted_slope by (ticker, fiscal_year)
- sector_slopes: DataFrame with sector_slope by (sector, fiscal_year)

**Output**: DataFrame with columns:
- ticker: str
- fiscal_year: int
- sector: str
- adjusted_slope: float
- sector_slope: float
- spot_slope: float (final value after fallback)
- ticker_avg: float (for later use in FIXED approach)

**Algorithm** (from legacy line 62-73):
```python
# Tier 1: Use adjusted_slope if available
spot_betas = annual_beta.merge(sector_slopes, on=['sector', 'fiscal_year'], how='inner')
spot_betas['spot_slope'] = spot_betas['adjusted_slope'].fillna(spot_betas['sector_slope'])

# Tier 2: If spot_slope still NaN, use sector average (already done above via inner join)

# Tier 3: Calculate ticker average across all years (for later use)
ticker_avg = spot_betas.groupby('ticker')['spot_slope'].mean()  # skipna=False (keep NaN if all NaN)
spot_betas = spot_betas.merge(
    ticker_avg.rename('ticker_avg'),
    left_on='ticker',
    right_index=True
)

return spot_betas
```

**Key Logic**:
- spot_slope = adjusted_slope if not NaN, else sector_slope
- If adjusted_slope and sector_slope both NaN: spot_slope = NaN
- Calculate ticker_avg = mean of spot_slope across all fiscal_years (skipna=False)
- Result: One row per (ticker, fiscal_year) with fallback values

#### Method 7: `_apply_approach_to_ke()`

**Input**:
- spot_betas: DataFrame from _apply_4tier_fallback()
- approach_to_ke: str ("FIXED" or "Floating")
- beta_rounding: float

**Output**: DataFrame with columns:
- ticker: str
- fiscal_year: int
- beta: float

**Algorithm** (from legacy line 84-89):
```python
spot_betas['beta'] = spot_betas.apply(
    lambda x: (
        np.round(x['ticker_avg'] / beta_rounding, 4) * beta_rounding
        if approach_to_ke == 'FIXED'
        else np.round(x['spot_slope'] / beta_rounding, 4) * beta_rounding
    ),
    axis=1
)

return spot_betas[['ticker', 'fiscal_year', 'beta']]
```

**Key Logic**:
- FIXED: Use ticker_avg (average across all years)
- Floating: Use spot_slope (per-year value)
- Apply rounding: round(value / beta_rounding, 4) * beta_rounding

#### Method 8: Main `calculate_beta_async()`

**Algorithm** (orchestration):
```python
async def calculate_beta_async(self, dataset_id, param_set_id):
    try:
        # 1. Load parameters
        params = await self._load_parameters_from_db(param_set_id)
        
        # 2. Check if results already exist (upsert logic)
        existing_count = await self.repo.count_metrics_by_dataset_param(
            dataset_id, param_set_id, metric_name="Beta"
        )
        if existing_count > 0:
            return {
                "status": "cached",
                "results_count": existing_count,
                "message": f"Using cached results for dataset={dataset_id}, param_set={param_set_id}"
            }
        
        # 3. Fetch monthly returns
        monthly_df = await self._fetch_monthly_returns(dataset_id)
        if monthly_df.empty:
            return {"status": "error", "results_count": 0, "message": "No monthly returns data"}
        
        # 4. Calculate OLS slopes
        ols_df = self._calculate_rolling_ols(monthly_df)
        
        # 5. Transform and filter
        transformed_df = self._transform_slopes(
            ols_df,
            params['beta_relative_error_tolerance'],
            params['beta_rounding']
        )
        
        # 6. Annualize
        annual_df = self._annualize_slopes(transformed_df)
        
        # 7. Generate sector slopes
        sector_slopes = self._generate_sector_slopes(annual_df)
        
        # 8. Apply fallback logic
        spot_betas = self._apply_4tier_fallback(annual_df, sector_slopes)
        
        # 9. Apply approach_to_ke
        final_betas = self._apply_approach_to_ke(
            spot_betas,
            params['cost_of_equity_approach'],
            params['beta_rounding']
        )
        
        # 10. Format and store results
        results_to_store = final_betas.copy()
        results_to_store['output_metric_name'] = 'Beta'
        results_to_store['output_metric_value'] = results_to_store['beta']
        results_to_store = results_to_store[['ticker', 'fiscal_year', 'output_metric_name', 'output_metric_value']]
        
        # 11. Store in metrics_outputs
        await self.repo.batch_insert_metrics(
            dataset_id,
            param_set_id,
            results_to_store
        )
        
        return {
            "status": "success",
            "results_count": len(final_betas),
            "message": f"Calculated beta for {len(final_betas)} records"
        }
        
    except Exception as e:
        self.logger.error(f"Beta calculation failed: {e}")
        return {"status": "error", "results_count": 0, "message": str(e)}
```

**Acceptance Criteria**:
- [ ] All methods implemented with proper error handling
- [ ] Async/await used throughout
- [ ] Parameter loading includes override support
- [ ] Data validation at each step
- [ ] Upsert logic prevents duplicate calculations
- [ ] Results stored correctly in metrics_outputs
- [ ] Logging at key steps

**Files to Create**:
- `/home/ubuntu/cissa/backend/app/services/beta_calculation_service.py` (NEW)

**Files to Modify**:
- `/home/ubuntu/cissa/requirements.txt` — Add `statsmodels>=0.14.0`
- `/home/ubuntu/cissa/backend/app/services/__init__.py` — Export BetaCalculationService

**Estimated Effort**: 16-20 hours

---

### Task 4: API Integration & Endpoint

**Objective**: Create HTTP endpoint for triggering beta calculation

**Location**: `/home/ubuntu/cissa/backend/app/api/v1/endpoints/metrics.py` (MODIFY)

**Endpoint Definition**:

```python
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from ..dependencies import get_session
from ...services.beta_calculation_service import BetaCalculationService

router = APIRouter()

@router.post("/beta/calculate")
async def calculate_beta(
    dataset_id: UUID,
    param_set_id: UUID,
    session: AsyncSession = Depends(get_session)
) -> dict:
    """
    Calculate beta metrics for a dataset using specified parameters.
    
    **Request**:
    - dataset_id (UUID): Dataset ID for the calculation
    - param_set_id (UUID): Parameter set ID (defines error_tolerance, beta_rounding, approach_to_ke)
    
    **Response**:
    ```json
    {
        "status": "success|error|cached",
        "results_count": 12345,
        "message": "Calculated beta for 12345 records"
    }
    ```
    
    **Behavior**:
    - Checks if results already exist (dataset_id + param_set_id + metric="Beta")
    - If exists: Returns cached results (upsert behavior)
    - If not exists: Calculates and stores results
    - Processing is synchronous and inline
    
    **Parameters**:
    - error_tolerance (beta_relative_error_tolerance): 40.0 (at 0.4 runtime)
    - beta_rounding: 0.1
    - approach_to_ke (cost_of_equity_approach): "Floating" or "FIXED"
    
    **Errors**:
    - 404: Dataset not found
    - 400: Invalid parameters
    - 500: Calculation error
    """
    try:
        service = BetaCalculationService(session)
        result = await service.calculate_beta_async(dataset_id, param_set_id)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Integration Points**:

1. **Dependency Injection**:
   - Use `get_session` dependency from existing FastAPI setup
   - Pass AsyncSession to BetaCalculationService

2. **Error Handling**:
   - Dataset not found: 404
   - Invalid param_set_id: 400
   - Calculation errors: 500 with error message

3. **Response Format**:
   - Must return JSON with status, results_count, message
   - Consistent with existing metrics endpoints

**Testing the Endpoint**:
```bash
# Request
curl -X POST http://localhost:8000/api/v1/metrics/beta/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "380e6916-125e-4fb2-8c33-a13773dc51af",
    "param_set_id": "380e6916-125e-4fb2-8c33-a13773dc51af"
  }'

# Expected Response
{
  "status": "success",
  "results_count": 12345,
  "message": "Calculated beta for 12345 records"
}
```

**Acceptance Criteria**:
- [ ] Endpoint callable via HTTP POST
- [ ] Request validation (dataset_id and param_set_id required, valid UUIDs)
- [ ] Results stored in metrics_outputs
- [ ] Upsert logic works (cached results returned on second call)
- [ ] Error handling for missing data
- [ ] Logging of requests/responses
- [ ] Response format consistent with existing endpoints

**Files to Modify**:
- `/home/ubuntu/cissa/backend/app/api/v1/endpoints/metrics.py` — Add beta endpoint

**Estimated Effort**: 4-6 hours

---

### Task 5: Testing & Verification

**Objective**: Test beta calculation against expected outputs and validate correctness

**Location**: `/home/ubuntu/cissa/backend/tests/test_beta_calculation.py` (NEW FILE)

**Test Structure**:

```python
import pytest
import pandas as pd
import numpy as np
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.beta_calculation_service import BetaCalculationService


class TestBetaCalculationService:
    """Test suite for BetaCalculationService"""
    
    @pytest.fixture
    async def service(self, async_session: AsyncSession):
        """Provide BetaCalculationService instance"""
        return BetaCalculationService(async_session)
    
    # Unit Tests
    def test_calculate_rolling_ols_60_months(self, service):
        """Test rolling OLS with 60+ months of data"""
        # Create test data: 70 months of returns
        data = self._create_test_returns(tickers=['TEST1'], months=70)
        result = service._calculate_rolling_ols(data)
        
        # Should have 11 rolling windows (70 - 60 + 1)
        assert len(result) == 11
        assert 'slope' in result.columns
        assert 'std_err' in result.columns
    
    def test_calculate_rolling_ols_less_than_60_months(self, service):
        """Test rolling OLS with <60 months (should use all available)"""
        data = self._create_test_returns(tickers=['TEST1'], months=50)
        result = service._calculate_rolling_ols(data)
        
        # Should have 1 window (all 50 months)
        assert len(result) == 1
        assert result['slope'].notna().all()
    
    def test_transform_slopes_error_filtering(self, service):
        """Test error tolerance filtering"""
        ols_df = pd.DataFrame({
            'ticker': ['TEST1', 'TEST1', 'TEST1'],
            'fiscal_year': [2021, 2022, 2023],
            'fiscal_month': [12, 12, 12],
            'slope': [1.5, 2.0, 0.5],
            'std_err': [0.1, 0.5, 0.01]  # Middle value should fail with error_tolerance=0.4
        })
        
        result = service._transform_slopes(ols_df, error_tolerance=0.4, beta_rounding=0.1)
        
        # Check relative_std_err calculation
        # rel_std_err = |std_err| / |(slope * 2/3 + 1/3)|
        assert result['rel_std_err'].notna().any()
        
        # Middle row should have NaN adjusted_slope (too high error)
        assert pd.isna(result.loc[1, 'adjusted_slope'])
    
    def test_transform_slopes_rounding(self, service):
        """Test beta rounding application"""
        ols_df = pd.DataFrame({
            'ticker': ['TEST1'],
            'fiscal_year': [2023],
            'fiscal_month': [12],
            'slope': [1.234],
            'std_err': [0.05]
        })
        
        result = service._transform_slopes(ols_df, error_tolerance=0.8, beta_rounding=0.1)
        
        # adjusted_slope should be rounded to nearest 0.1
        # (1.234 * 2/3 + 1/3) = 1.156 → round to 1.2
        expected = np.round(1.156 / 0.1, 4) * 0.1
        assert abs(result.loc[0, 'adjusted_slope'] - expected) < 0.001
    
    def test_annualize_slopes(self, service):
        """Test annualization of monthly slopes"""
        df = pd.DataFrame({
            'ticker': ['TEST1'] * 12,
            'fiscal_year': [2023] * 12,
            'fiscal_month': list(range(1, 13)),
            'adjusted_slope': [1.0] * 12,
            'slope': [1.5] * 12,
            'std_err': [0.1] * 12,
            'rel_std_err': [0.05] * 12
        })
        
        # Add sector info (mock companies table lookup)
        df['sector'] = 'Technology'
        
        result = service._annualize_slopes(df)
        
        # Should have 1 row per fiscal year (take last month)
        assert len(result) == 1
        assert result.loc[0, 'fiscal_year'] == 2023
        assert result.loc[0, 'fiscal_month'] == 12
    
    def test_generate_sector_slopes(self, service):
        """Test sector average calculation"""
        df = pd.DataFrame({
            'ticker': ['TECH1', 'TECH2', 'BANK1'],
            'fiscal_year': [2023, 2023, 2023],
            'sector': ['Technology', 'Technology', 'Financials'],
            'adjusted_slope': [1.2, 1.4, 0.8],
            'slope': [1.5, 1.75, 1.0],
            'std_err': [0.1] * 3,
            'rel_std_err': [0.05] * 3
        })
        
        result = service._generate_sector_slopes(df)
        
        # Should have 2 rows (Technology, Financials)
        assert len(result) == 2
        
        # Technology average: (1.2 + 1.4) / 2 = 1.3
        tech_row = result[result['sector'] == 'Technology']
        assert abs(tech_row.iloc[0]['sector_slope'] - 1.3) < 0.001
    
    def test_apply_4tier_fallback_tier1(self, service):
        """Test 4-tier fallback: tier 1 (ticker adjusted_slope available)"""
        annual_beta = pd.DataFrame({
            'ticker': ['TEST1'],
            'fiscal_year': [2023],
            'sector': ['Technology'],
            'adjusted_slope': [1.2],
            'slope': [1.5],
            'std_err': [0.1],
            'rel_std_err': [0.05]
        })
        
        sector_slopes = pd.DataFrame({
            'sector': ['Technology'],
            'fiscal_year': [2023],
            'sector_slope': [1.0]
        })
        
        result = service._apply_4tier_fallback(annual_beta, sector_slopes)
        
        # Should use adjusted_slope (tier 1)
        assert result.loc[0, 'spot_slope'] == 1.2
    
    def test_apply_4tier_fallback_tier2(self, service):
        """Test 4-tier fallback: tier 2 (sector average)"""
        annual_beta = pd.DataFrame({
            'ticker': ['TEST1'],
            'fiscal_year': [2023],
            'sector': ['Technology'],
            'adjusted_slope': [np.nan],  # Missing
            'slope': [1.5],
            'std_err': [0.1],
            'rel_std_err': [0.05]
        })
        
        sector_slopes = pd.DataFrame({
            'sector': ['Technology'],
            'fiscal_year': [2023],
            'sector_slope': [1.0]
        })
        
        result = service._apply_4tier_fallback(annual_beta, sector_slopes)
        
        # Should use sector_slope (tier 2)
        assert result.loc[0, 'spot_slope'] == 1.0
    
    def test_apply_approach_to_ke_fixed(self, service):
        """Test approach_to_ke: FIXED uses ticker average"""
        spot_betas = pd.DataFrame({
            'ticker': ['TEST1', 'TEST1', 'TEST1'],
            'fiscal_year': [2021, 2022, 2023],
            'spot_slope': [1.0, 1.2, 1.4],
            'ticker_avg': [1.2, 1.2, 1.2]
        })
        
        result = service._apply_approach_to_ke(spot_betas, 'FIXED', 0.1)
        
        # All rows should use ticker_avg
        for idx in result.index:
            assert abs(result.loc[idx, 'beta'] - 1.2) < 0.001
    
    def test_apply_approach_to_ke_floating(self, service):
        """Test approach_to_ke: Floating uses spot_slope"""
        spot_betas = pd.DataFrame({
            'ticker': ['TEST1', 'TEST1', 'TEST1'],
            'fiscal_year': [2021, 2022, 2023],
            'spot_slope': [1.0, 1.2, 1.4],
            'ticker_avg': [1.2, 1.2, 1.2]
        })
        
        result = service._apply_approach_to_ke(spot_betas, 'Floating', 0.1)
        
        # Each row should use its own spot_slope
        assert abs(result.loc[0, 'beta'] - 1.0) < 0.001
        assert abs(result.loc[1, 'beta'] - 1.2) < 0.001
        assert abs(result.loc[2, 'beta'] - 1.4) < 0.001
    
    # Integration Tests
    @pytest.mark.asyncio
    async def test_calculate_beta_async_full_flow(self, service, sample_dataset_id, sample_param_set_id):
        """Test full beta calculation flow"""
        result = await service.calculate_beta_async(sample_dataset_id, sample_param_set_id)
        
        assert result['status'] == 'success'
        assert result['results_count'] > 0
        assert 'message' in result
    
    @pytest.mark.asyncio
    async def test_calculate_beta_async_upsert(self, service, sample_dataset_id, sample_param_set_id):
        """Test upsert behavior: second call returns cached results"""
        result1 = await service.calculate_beta_async(sample_dataset_id, sample_param_set_id)
        result2 = await service.calculate_beta_async(sample_dataset_id, sample_param_set_id)
        
        assert result1['status'] == 'success'
        assert result2['status'] == 'cached'
        assert result1['results_count'] == result2['results_count']
    
    @pytest.mark.asyncio
    async def test_calculate_beta_async_missing_data(self, service):
        """Test error handling when no monthly data available"""
        fake_dataset_id = uuid4()
        fake_param_set_id = uuid4()
        
        result = await service.calculate_beta_async(fake_dataset_id, fake_param_set_id)
        
        assert result['status'] == 'error'
        assert 'No monthly returns data' in result['message']
    
    # Helper Methods
    def _create_test_returns(self, tickers: list, months: int) -> pd.DataFrame:
        """Create test monthly returns data"""
        data = []
        for ticker in tickers:
            for m in range(months):
                year = 1980 + (m // 12)
                month = (m % 12) + 1
                data.append({
                    'ticker': ticker,
                    'fiscal_year': year,
                    'fiscal_month': month,
                    'company_tsr': np.random.normal(1, 0.5),  # Random ~1% return
                    'index_tsr': np.random.normal(0.8, 0.4)   # Random ~0.8% return
                })
        return pd.DataFrame(data)
```

**Test Coverage**:

- [ ] Unit tests for each transformation step
- [ ] Error filtering (relative std error)
- [ ] Rounding logic
- [ ] 4-tier fallback (all tiers)
- [ ] approach_to_ke logic (FIXED vs Floating)
- [ ] Annualization logic
- [ ] Sector averaging
- [ ] Full integration flow
- [ ] Upsert logic
- [ ] Error handling (missing data)
- [ ] Edge cases (<60 months, all NaN, etc.)

**Test Fixtures**:

- Sample monthly returns dataset
- Sample parameter set with beta parameters
- Sample company data with sectors

**Acceptance Criteria**:
- [ ] All unit tests passing (>90% coverage)
- [ ] Integration tests passing
- [ ] Manual verification against legacy algorithm
- [ ] Edge cases handled correctly
- [ ] No regressions in existing metrics endpoints

**Files to Create**:
- `/home/ubuntu/cissa/backend/tests/test_beta_calculation.py` (NEW)
- `/home/ubuntu/cissa/backend/tests/fixtures/sample_returns.csv` (optional)

**Estimated Effort**: 12-16 hours

---

## Part 3: Validation & Verification

### Manual Verification Steps

**Step 1**: Verify parameter loading
```python
# In service initialization
params = await service._load_parameters_from_db(param_set_id)
assert params['beta_rounding'] == 0.1
assert params['beta_relative_error_tolerance'] == 0.4  # Runtime value after conversion
assert params['cost_of_equity_approach'] == 'Floating'  # or 'FIXED'
```

**Step 2**: Verify data fetch
```python
df = await service._fetch_monthly_returns(dataset_id)
# Check:
# - Columns: ticker, fiscal_year, fiscal_month, company_tsr, index_tsr
# - No NaN values
# - Data sorted by ticker, fiscal_year, fiscal_month
# - All index_tsr are from 'AS30 Index' ticker
```

**Step 3**: Compare slopes with legacy
```python
# Take sample ticker (e.g., BHP AU Equity)
# Run legacy beta.py for same ticker
# Run new service for same ticker
# Compare slope values (should match within rounding tolerance)
```

**Step 4**: Verify database storage
```sql
SELECT COUNT(*) FROM cissa.metrics_outputs
WHERE output_metric_name = 'Beta'
AND param_set_id = :param_set_id
AND dataset_id = :dataset_id;

-- Should return results_count from service response
```

---

## Part 4: Integration Checklist

**Before Starting Implementation**:
- [ ] statsmodels added to requirements.txt
- [ ] "Beta" metric added to metric_units table
- [ ] All 3 beta parameters verified in parameters table
- [ ] MetricsRepository has `batch_insert_metrics()` method
- [ ] AsyncSession dependency available in FastAPI

**During Implementation**:
- [ ] BetaCalculationService follows existing service patterns
- [ ] All methods use async/await where applicable
- [ ] Error logging at key steps
- [ ] Parameter loading matches enhanced_metrics_service pattern
- [ ] Test coverage >80%

**After Implementation**:
- [ ] API endpoint tested via curl/Postman
- [ ] Results verified in metrics_outputs table
- [ ] Upsert logic working (second call returns cached)
- [ ] No integration breaks with existing endpoints
- [ ] Documentation updated

---

## Summary Timeline

| Task | Hours | Dependencies | Status |
|------|-------|--------------|--------|
| Task 1: Data Validation | 4 | None | Ready |
| Task 2: DB Parameters | 3 | Task 1 | Ready |
| Task 3: Service Implementation | 18 | Task 2 | Ready |
| Task 4: API Endpoint | 5 | Task 3 | Ready |
| Task 5: Testing | 14 | Task 4 | Ready |
| **TOTAL** | **44 hours** | Sequential | Ready |

**Estimated Timeline**: 2-3 weeks with focused development

---

## References

**Legacy Implementation**:
- `/home/ubuntu/cissa/example-calculations/src/executors/beta.py` (104 lines)
- `/home/ubuntu/cissa/example-calculations/src/engine/sql.py` (get_TSR function)

**Backend Patterns**:
- `/home/ubuntu/cissa/backend/app/services/l2_metrics_service.py` (async service pattern)
- `/home/ubuntu/cissa/backend/app/services/enhanced_metrics_service.py` (parameter loading)
- `/home/ubuntu/cissa/backend/app/repositories/metrics_repository.py` (storage pattern)

**Database Schema**:
- `/home/ubuntu/cissa/backend/database/schema/schema.sql` (parameters, metrics_outputs)
- `/home/ubuntu/cissa/backend/database/config/metric_units.json` (metrics configuration)

---

**Document Version**: 1.0  
**Last Updated**: 2026-03-09  
**Status**: Ready for Implementation
