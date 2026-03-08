# Migration Examples: Legacy → FastAPI Backend

This document provides concrete code examples showing how to migrate calculation logic from the legacy `example-calculations/` codebase into the modern FastAPI backend.

---

## Example 1: Beta Calculation Migration

### Current Legacy Code (executors/beta.py)

```python
def calculate_slope(df, error_tolerance, beta_rounding):
    """Rolling OLS to calculate beta from returns"""
    result['slope_wo_rounding'] = round((result['slope'] * 2/3) + 1/3, 4)
    result['adjusted_slope'] = result.apply(
        lambda x: round((((x['slope'] * 2/3) + 1/3) / beta_rounding), 4) * beta_rounding
        if error_tolerance >= x['rel_std_err'] else np.nan, axis=1
    )
    return result
```

### Proposed FastAPI Service (backend/app/services/beta_service.py)

```python
# Structure following established pattern
class BetaService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MetricsRepository(session)
    
    async def calculate_beta(
        self,
        dataset_id: UUID,
        error_tolerance: float = 0.5,
        beta_rounding: float = 0.05
    ) -> CalculateBetaResponse:
        """
        Calculate beta for all tickers using rolling OLS.
        
        1. Fetch market returns vs company returns
        2. Run rolling regression per ticker
        3. Calculate adjusted beta with error tolerance
        4. Store results in metrics_outputs
        """
        try:
            # Fetch return data from fundamentals/timeseries tables
            returns_df = await self._fetch_returns(dataset_id)
            
            # Calculate spot beta (rolling OLS)
            spot_beta_df = await self._calculate_spot_beta(
                returns_df,
                error_tolerance,
                beta_rounding
            )
            
            # Get fallback beta (sector precomputed)
            fallback_beta = await self._get_fallback_beta(dataset_id)
            
            # Merge with 4-tier fallback
            beta_results = self._apply_beta_fallback(
                spot_beta_df,
                fallback_beta
            )
            
            # Calculate rolling average
            beta_results['Calc Beta'] = (
                beta_results.groupby('ticker')['Calc Spot Beta']
                .expanding().mean()
                .values
            )
            
            # Store in database
            records_inserted = await self.repo.create_outputs_batch(
                metric_name="Calc Beta",
                records=beta_results.to_dict('records')
            )
            
            return CalculateBetaResponse(
                dataset_id=dataset_id,
                results_count=records_inserted,
                message=f"Beta calculated for {records_inserted} records"
            )
        
        except Exception as e:
            logger.error(f"Beta calculation failed: {e}")
            raise
    
    async def _fetch_returns(self, dataset_id: UUID) -> pd.DataFrame:
        """Fetch market & company returns from database"""
        # Query timeseries table
        query = """
        SELECT ticker, date, market_return, company_return
        FROM cissa.timeseries
        WHERE dataset_id = :dataset_id
        ORDER BY ticker, date
        """
        result = await self.session.execute(text(query), {"dataset_id": str(dataset_id)})
        rows = result.fetchall()
        return pd.DataFrame(rows)
    
    async def _calculate_spot_beta(
        self,
        returns_df: pd.DataFrame,
        error_tolerance: float,
        beta_rounding: float
    ) -> pd.DataFrame:
        """Run rolling OLS for each ticker"""
        # Extract pure calculation logic from legacy code
        results = []
        for ticker, group in returns_df.groupby('ticker'):
            # Run rolling OLS (60-month window)
            model = RollingOLS(
                group['company_return'],
                group['market_return'],
                window=60
            )
            result = model.fit()
            
            # Apply adjustment formula: (slope * 2/3) + 1/3
            params = pd.DataFrame(result.params).rename(columns={'market_return': 'slope'})
            adjusted = round((params['slope'] * 2/3) + 1/3, 4) / beta_rounding * beta_rounding
            
            # Filter by error tolerance
            params['Calc Spot Beta'] = adjusted if error_tolerance >= result.bse else np.nan
            results.append(params)
        
        return pd.concat(results)
    
    async def _get_fallback_beta(self, dataset_id: UUID) -> Dict[str, float]:
        """
        4-tier fallback logic:
        1. Company Adjusted Beta
        2. Sector Beta (precomputed)
        3. Sector Average Beta
        4. Market Beta (1.0)
        """
        # Query precomputed beta table
        query = """
        SELECT ticker, sector, company_beta, sector_beta, sector_avg_beta
        FROM cissa.beta_lookup
        WHERE dataset_id = :dataset_id
        """
        result = await self.session.execute(text(query), {"dataset_id": str(dataset_id)})
        return {row.ticker: row for row in result.fetchall()}
    
    def _apply_beta_fallback(self, spot_beta: pd.DataFrame, fallback: Dict) -> pd.DataFrame:
        """Apply 4-tier fallback if spot beta is NaN"""
        def get_beta(ticker, spot):
            if pd.notna(spot):
                return spot
            elif ticker in fallback:
                row = fallback[ticker]
                return row.company_beta or row.sector_beta or row.sector_avg_beta or 1.0
            return 1.0
        
        spot_beta['Calc Beta'] = spot_beta.apply(
            lambda row: get_beta(row['ticker'], row['Calc Spot Beta']),
            axis=1
        )
        return spot_beta
```

### Proposed API Endpoint (backend/app/api/v1/endpoints/metrics.py)

```python
@router.post("/api/v1/metrics/calculate-beta")
async def calculate_beta(
    request: CalculateBetaRequest,  # {dataset_id, error_tolerance, beta_rounding}
    db: AsyncSession = Depends(get_db)
) -> CalculateBetaResponse:
    """
    Calculate beta for all tickers in dataset.
    
    POST /api/v1/metrics/calculate-beta
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "error_tolerance": 0.5,
        "beta_rounding": 0.05
    }
    
    Returns:
    {
        "dataset_id": "550e8400-...",
        "results_count": 150,
        "results": [
            {"ticker": "BHP", "fiscal_year": 2023, "metric_name": "Calc Beta", "value": 0.85},
            ...
        ]
    }
    """
    service = BetaService(db)
    return await service.calculate_beta(
        dataset_id=request.dataset_id,
        error_tolerance=request.error_tolerance or 0.5,
        beta_rounding=request.beta_rounding or 0.05
    )
```

---

## Example 2: Risk-Free Rate Service Migration

### Current Legacy Code (executors/rates.py)

```python
def fetch_rates_from_db(ticker, fy_year):
    """Lookup Rf from precomputed table"""
    query = f"""
    SELECT date, rf_value
    FROM cissa.rf_lookup
    WHERE ticker = '{ticker}' AND fiscal_year = {fy_year}
    """
    # If no match: fallback to default_rf parameter (e.g., 5.0%)
```

### Proposed FastAPI Service (backend/app/services/rate_service.py)

```python
from functools import lru_cache
from datetime import datetime, timedelta

class RateService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._rf_cache = {}  # Simple date-based cache
    
    async def calculate_rf(
        self,
        dataset_id: UUID,
        default_rf: float = 5.0
    ) -> CalculateRfResponse:
        """
        Calculate risk-free rate (Rf) with fallback.
        
        1. For each ticker/fiscal_year:
           - Query precomputed rf_lookup table
           - If found: use that value
           - If not found: use default_rf parameter
        2. Calculate Calc Open Rf (lagged by 1 year)
        3. Store results
        """
        try:
            # Fetch fundamentals to get list of tickers/years
            fundamentals_df = await self._fetch_fundamentals(dataset_id)
            
            # Fetch precomputed rates or get default
            rf_df = await self._get_rates_with_fallback(
                fundamentals_df,
                default_rf
            )
            
            # Calculate open rates (lagged)
            rf_df['Calc Open Rf'] = rf_df.groupby('ticker')['Calc Rf'].shift(1)
            
            # Store results
            records_inserted = await self.repo.create_outputs_batch(
                metric_name="Calc Rf",
                records=rf_df.to_dict('records')
            )
            
            return CalculateRfResponse(
                dataset_id=dataset_id,
                results_count=records_inserted,
                message=f"Risk-free rate calculated for {records_inserted} records"
            )
        
        except Exception as e:
            logger.error(f"Rate calculation failed: {e}")
            raise
    
    async def _get_rates_with_fallback(
        self,
        fundamentals_df: pd.DataFrame,
        default_rf: float
    ) -> pd.DataFrame:
        """Get Rf from precomputed table, or use default"""
        # Get unique ticker/year combinations
        unique_pairs = fundamentals_df[['ticker', 'fiscal_year']].drop_duplicates()
        
        # Build parameterized query to avoid N+1 problem
        placeholders = ','.join(['(:ticker_%d, :year_%d)' % (i, i) for i in range(len(unique_pairs))])
        params = {}
        for i, (_, row) in enumerate(unique_pairs.iterrows()):
            params[f'ticker_{i}'] = row['ticker']
            params[f'year_{i}'] = row['fiscal_year']
        
        query = f"""
        SELECT ticker, fiscal_year, rf_value as calc_rf
        FROM cissa.rf_lookup
        WHERE (ticker, fiscal_year) IN ({placeholders})
        """
        
        result = await self.session.execute(text(query), params)
        found_rates = pd.DataFrame(result.fetchall())
        
        # Left join with fundamentals, fill missing with default
        merged = fundamentals_df.merge(
            found_rates,
            on=['ticker', 'fiscal_year'],
            how='left'
        )
        merged['Calc Rf'] = merged['calc_rf'].fillna(default_rf)
        
        return merged[['ticker', 'fiscal_year', 'Calc Rf']]
    
    async def _fetch_fundamentals(self, dataset_id: UUID) -> pd.DataFrame:
        """Get list of tickers/fiscal_years in dataset"""
        query = """
        SELECT DISTINCT ticker, fiscal_year
        FROM cissa.fundamentals
        WHERE dataset_id = :dataset_id
        """
        result = await self.session.execute(text(query), {"dataset_id": str(dataset_id)})
        return pd.DataFrame(result.fetchall())

@router.post("/api/v1/metrics/calculate-rf")
async def calculate_rf(
    request: CalculateRfRequest,
    db: AsyncSession = Depends(get_db)
) -> CalculateRfResponse:
    """Calculate risk-free rate with fallback defaults"""
    service = RateService(db)
    return await service.calculate_rf(
        dataset_id=request.dataset_id,
        default_rf=request.default_rf or 5.0
    )
```

---

## Example 3: TSR & Franking Credits Migration

### Current Legacy Code (executors/metrics.py - Simplified)

```python
def calculate_fy_tsr(row, inputs):
    """TSR = Change in Capital / Prior MC, adjusted for franking credits"""
    incl_franking = inputs['incl_franking']
    frank_tax_rate = inputs['frank_tax_rate']
    value_franking_cr = inputs['value_franking_cr']
    
    lag_mc = row['LAG_MC']
    if lag_mc > 0 and row["INCEPTION_IND"] == 1:
        if incl_franking == "Yes":
            # Adjust dividend for franking credit
            div = row['dividend'] / (1 - frank_tax_rate)
            change_in_cap = row['C_MC'] - row['LAG_MC'] + row['ECF'] - div
            adjusted_change = change_in_cap * frank_tax_rate * value_franking_cr
            fy_tsr = adjusted_change / lag_mc
        else:
            change_in_cap = row['C_MC'] - row['LAG_MC'] + row['ECF']
            fy_tsr = change_in_cap / lag_mc
    
    return fy_tsr
```

### Proposed FastAPI Service (backend/app/services/returns_service.py)

```python
class ReturnsService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate_returns(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        include_franking: bool = True,
        frank_tax_rate: float = 0.30,
        value_franking_cr: float = 1.0
    ) -> CalculateReturnsResponse:
        """
        Calculate FY TSR with optional franking credit adjustment.
        
        Depends on:
        - Prior year Market Cap (from L1)
        - Current year Market Cap (from L1)
        - Economic Cash Flow (from L2)
        - Dividends (from fundamentals)
        """
        try:
            # Fetch L1 metrics (MC, ECF already calculated)
            l1_metrics = await self._fetch_l1_metrics(dataset_id)
            
            # Fetch fundamentals (dividends, inception flags)
            fundamentals = await self._fetch_fundamentals(dataset_id)
            
            # Merge data
            merged = l1_metrics.merge(fundamentals, on=['ticker', 'fiscal_year'])
            
            # Calculate TSR with franking adjustment
            tsr_results = self._calculate_tsr_with_franking(
                merged,
                include_franking,
                frank_tax_rate,
                value_franking_cr
            )
            
            # Store results
            records_inserted = await self.repo.create_outputs_batch(
                metric_name="Calc FY TSR",
                records=tsr_results.to_dict('records')
            )
            
            return CalculateReturnsResponse(
                dataset_id=dataset_id,
                results_count=records_inserted,
                message=f"TSR calculated for {records_inserted} records"
            )
        
        except Exception as e:
            logger.error(f"TSR calculation failed: {e}")
            raise
    
    def _calculate_tsr_with_franking(
        self,
        df: pd.DataFrame,
        include_franking: bool,
        frank_tax_rate: float,
        value_franking_cr: float
    ) -> pd.DataFrame:
        """Pure calculation function matching legacy logic"""
        
        def calc_tsr(row):
            lag_mc = row['prior_market_cap']
            if pd.isna(lag_mc) or lag_mc <= 0:
                return np.nan
            
            if row['inception_ind'] != 1:
                return np.nan
            
            if include_franking:
                # Adjust dividend for franking credit value
                div_adjusted = row['dividend'] / (1 - frank_tax_rate) if row['dividend'] > 0 else 0
                change_in_cap = (
                    row['market_cap'] - lag_mc +
                    row['ecf'] - div_adjusted
                )
                adjusted_change = change_in_cap * frank_tax_rate * value_franking_cr
                return adjusted_change / lag_mc
            else:
                # No franking adjustment
                change_in_cap = row['market_cap'] - lag_mc + row['ecf']
                return change_in_cap / lag_mc
        
        df['Calc FY TSR'] = df.apply(calc_tsr, axis=1)
        
        # Also calculate franking credit impact separately
        if include_franking:
            df['Calc FC'] = (
                -(row['dividend'] / (1 - frank_tax_rate)) * frank_tax_rate * value_franking_cr
                for _, row in df.iterrows()
            )
        
        return df[['ticker', 'fiscal_year', 'Calc FY TSR', 'Calc FC']]
```

---

## Example 4: Pydantic Schemas for New Metrics

### New Schemas (backend/app/models/schemas.py - Additions)

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID

# ============== BETA REQUEST/RESPONSE ==============

class CalculateBetaRequest(BaseModel):
    dataset_id: UUID
    error_tolerance: Optional[float] = Field(default=0.5, description="Error tolerance for beta adjustment")
    beta_rounding: Optional[float] = Field(default=0.05, description="Rounding precision for beta")

class CalculateBetaResponse(BaseModel):
    dataset_id: UUID
    results_count: int
    results: List[MetricResultItem]
    status: str = "success"
    message: Optional[str] = None

# ============== RISK-FREE RATE REQUEST/RESPONSE ==============

class CalculateRfRequest(BaseModel):
    dataset_id: UUID
    default_rf: Optional[float] = Field(default=5.0, description="Default Rf if not in lookup table")

class CalculateRfResponse(BaseModel):
    dataset_id: UUID
    results_count: int
    results: List[MetricResultItem]
    status: str = "success"
    message: Optional[str] = None

# ============== TSR & FRANKING REQUEST/RESPONSE ==============

class CalculateReturnsRequest(BaseModel):
    dataset_id: UUID
    param_set_id: Optional[UUID] = None
    include_franking: Optional[bool] = Field(default=True)
    frank_tax_rate: Optional[float] = Field(default=0.30)
    value_franking_cr: Optional[float] = Field(default=1.0)

class CalculateReturnsResponse(BaseModel):
    dataset_id: UUID
    results_count: int
    results: List[MetricResultItem]
    status: str = "success"
    message: Optional[str] = None

# ============== SECTOR AGGREGATION REQUEST/RESPONSE ==============

class CalculateSectorRequest(BaseModel):
    dataset_id: UUID
    metric_names: List[str] = Field(description="List of metrics to aggregate by sector")

class SectorMetricItem(BaseModel):
    sector: str
    fiscal_year: int
    metric_name: str
    value: float

class CalculateSectorResponse(BaseModel):
    dataset_id: UUID
    results_count: int
    results: List[SectorMetricItem]
    status: str = "success"
    message: Optional[str] = None
```

---

## Migration Pattern Summary

Each metric migration follows the same 5-step pattern:

1. **Extract Logic** from legacy executors/*.py
2. **Create Service** (backend/app/services/{feature}_service.py)
3. **Create Schemas** (add to backend/app/models/schemas.py)
4. **Create Endpoint** (add to backend/app/api/v1/endpoints/metrics.py)
5. **Create CLI** (add to backend/app/cli/run_{feature}.py)

This keeps everything consistent, testable, and maintainable.

---

## Key Best Practices

### 1. Separate Pure Calculation from I/O
```python
# ✅ GOOD: Pure calculation function (testable)
def _calculate_tsr_with_franking(self, df, include_franking, ...):
    return result_df

# ❌ BAD: Mixed I/O and calculation
async def calculate_tsr(self):
    rows = await self.session.execute(...)  # I/O
    result = apply_formula(rows)             # Calculation
    await self.session.execute(...)          # I/O
```

### 2. Use Batch Operations
```python
# ✅ GOOD: Batch insert 1000 at a time
await self.repo.create_outputs_batch(
    metric_name="Calc Beta",
    records=results.to_dict('records'),
    batch_size=1000
)

# ❌ BAD: Individual inserts (slow)
for record in results:
    await self.repo.insert_one(record)
```

### 3. Type Hints & Validation
```python
# ✅ GOOD: Clear types
async def calculate_beta(
    self,
    dataset_id: UUID,
    error_tolerance: float = 0.5
) -> CalculateBetaResponse:
    pass

# ❌ BAD: No type info
def calculate_beta(self, dataset_id, error_tolerance=0.5):
    pass
```

### 4. Logging Throughout
```python
logger.info(f"Starting beta calculation for {dataset_id}")
logger.debug(f"Fetched {len(returns_df)} rows")
logger.error(f"Calculation failed: {e}")
```
