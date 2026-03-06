# Step 2: Risk Free Rate (RF) Analysis

## Current Status

❌ **Risk Free Rate NOT yet implemented as stored proc in backend**

## What Legacy System Does

### Legacy Function Flow: `calculate_rates_async()` (rates.py)

The legacy system calculates risk-free rate (`rf`) through a complex multi-step process:

```python
# rates.py, line 64-66
def calculate_rates_async(fy_dates, inputs, monthly_rates, monthly_rf):
    groups = monthly_rates.groupby('ticker')
    df = groups.apply(lambda x: generate_annual_rates(x, monthly_rf, fy_dates, inputs))
    return df
```

**Key function: `generate_annual_rates()` (lines 39-47)**

```python
def generate_annual_rates(group, monthly_rf, fy_dates, inputs):
    tsr = group
    monthly_rates_pct = calculate_annual_rf(monthly_rf, inputs)  # Step 1: Calculate annual RF
    monthly_prel = get_return_rates(monthly_rates_pct, tsr)       # Step 2: Join with TSR
    annual_rates = calculate_annual_rates(monthly_prel, fy_dates) # Step 3: Convert to annual
    logger.info("annual_rates: Successfully Created!!")
    return annual_rates
```

### Step-by-Step Breakdown

#### Step 1: `calculate_annual_rf()` (lines 19-26)
Calculates annual risk-free rate from monthly rates:

```python
def calculate_annual_rf(monthly_rates, inputs):
    # Formula: geometric mean of 12 monthly rates
    monthly_rates['rf_1y_raw'] = np.power(
        monthly_rates['rf_prel'].rolling(12).apply(lambda x: x.prod()), 
        1 / 12
    ) - 1
    
    # Round using beta_rounding parameter, then round again (banker's rounding)
    monthly_rates['rf_1y'] = np.round(
        np.round(
            (monthly_rates['rf_1y_raw'] / inputs["beta_rounding"]), 0
        ) * inputs["beta_rounding"], 
        4
    )
    
    # Final RF: Either FIXED (benchmark - risk_premium) or from 1-year calculation
    monthly_rates['rf'] = (
        inputs["benchmark"] - inputs["risk_premium"] 
        if inputs["approach_to_ke"] == 'FIXED' 
        else monthly_rates['rf_1y']
    )
    return monthly_rates
```

**Key Inputs from parameter set:**
- `beta_rounding`: Rounding precision (typically 0.5%)
- `approach_to_ke`: 'FIXED' or 'DYNAMIC' (determines RF calculation method)
- `benchmark`: Fixed RF if approach is 'FIXED' (e.g., 0.04 = 4%)
- `risk_premium`: Market risk premium (e.g., 0.06 = 6%)

**Outputs:**
- `rf_1y`: 1-year rolling geometric mean of monthly RF rates
- `rf`: Final annual risk-free rate (FIXED or DYNAMIC)

#### Step 2: `get_return_rates()` (lines 9-16)
Joins risk-free rates with TSR (Total Stock Return) data:

```python
def get_return_rates(risk_free_rates, tsr):
    # Create yr_mth = "MMYYYY" for joining
    risk_free_rates['yr_mth'] = pd.to_datetime(risk_free_rates['date']).dt.strftime('%m%Y')
    tsr['yr_mth'] = pd.to_datetime(tsr['date']).dt.strftime('%m%Y')
    
    # Join on (ticker, yr_mth)
    rates = pd.merge(tsr, risk_free_rates[['yr_mth', 'rf']], how="inner", on=['yr_mth'])
    
    # Extract relevant columns
    rates = rates[['ticker', 'yr_mth', 'rf', 'rm', 're']]
    
    # Calculate excess return: re - rf (used for beta calculation)
    rates['re_rf'] = rates['re'] - rates['rf']
    
    return rates
```

#### Step 3: `calculate_annual_rates()` (lines 29-36)
Converts monthly rates to annual rates using fiscal year mapping:

```python
def calculate_annual_rates(monthly_rates, fy_dates):
    # Map month to fiscal year
    fy_dates['yr_mth'] = pd.to_datetime(fy_dates['date']).dt.strftime('%m%Y')
    
    # Join on (ticker, yr_mth)
    annual_rates = pd.merge(
        fy_dates[["ticker", "yr_mth", 'date']], 
        monthly_rates, 
        how="inner", 
        on=['yr_mth', 'ticker']
    )
    
    # Extract fiscal year
    annual_rates['fy_year'] = pd.to_datetime(fy_dates['date']).dt.strftime('%Y')
    
    # Final columns
    annual_rates = annual_rates[['ticker', 'fy_year', 'rf', 'rm']]
    
    # Remove null RF values
    annual_rates = annual_rates[annual_rates['rf'].notnull()]
    
    return annual_rates
```

---

## Where RF is Used in L2 Metrics

### In `calculate_cost_of_eqity()` (calculation.py, lines 187-190)

```python
def calculate_cost_of_eqity(betas, inputs, risk_free_rate):
    # Join beta with risk_free_rate on (ticker, fy_year)
    cost_of_eq = pd.merge(betas, risk_free_rate, on=['ticker', 'fy_year'], how="inner")
    
    # Calculate Cost of Equity (Ke):
    # Ke = RF + Beta × Risk Premium
    cost_of_eq['ke'] = cost_of_eq['rf'] + cost_of_eq['beta'] * inputs['risk_premium']
    
    return cost_of_eq
```

**Formula:** `Ke = rf + beta × risk_premium`

---

## Data Sources for Risk Free Rate

The legacy system requires:

1. **Monthly Risk-Free Rates** - From bond market data
   - Loaded via `ld.get_monthly_wide_format(bondIndex=inputs['bondIndex'])`
   - Format: ticker, date, rf_prel (preliminary RF values)
   - Variables used: `monthly_rf` in code

2. **Fiscal Year Mapping** - To align monthly to annual
   - Loaded via `ld.load_dataset_for_processing()`
   - Contains: ticker, date, and fiscal year assignments
   - Allows grouping monthly data by fiscal year end

3. **Parameter Set** - Configuration for RF calculation
   - `approach_to_ke`: 'FIXED' or 'DYNAMIC'
   - `benchmark`: Fixed RF value if FIXED approach (e.g., 0.04)
   - `risk_premium`: Market risk premium (e.g., 0.06)
   - `beta_rounding`: Rounding precision for intermediate calculations

---

## Why RF Cannot Be a Simple Stored Proc

The risk-free rate calculation is **not suitable for PostgreSQL stored procedure** because:

1. **Requires External Data Sources:**
   - Monthly bond market data (not in fundamentals table)
   - Fiscal year calendar mapping
   - Parameter set configuration (approach_to_ke, benchmark, risk_premium)

2. **Complex Time-Series Processing:**
   - 12-month rolling geometric mean calculation
   - Multiple rounding operations (banker's rounding)
   - Conditional logic based on `approach_to_ke` parameter

3. **Input Data Not in Database:**
   - Legacy system loads from external CSV files via `ld.load_dataset_for_processing()`
   - Monthly bond rates come from `ld.get_monthly_wide_format()`
   - These are not stored in our cissa schema yet

---

## Implementation Options for Backend

### Option A: Add RF as Python Async Service (RECOMMENDED)
**Where:** `backend/app/services/rates_service.py`

```python
async def calculate_risk_free_rate(
    dataset_id: UUID,
    param_set_id: UUID,
    inputs: dict
) -> DataFrame:
    """
    Calculate risk-free rate for all tickers in dataset.
    
    Output: DataFrame with columns [ticker, fy_year, rf]
    Inserted into metrics_outputs with output_metric_name = 'Risk Free Rate'
    """
    # 1. Load parameter set (approach_to_ke, benchmark, risk_premium, beta_rounding)
    # 2. Load monthly bond rates from external source
    # 3. Calculate annual RF using parameters
    # 4. Insert into metrics_outputs table
    pass
```

**Pros:**
- Can handle complex time-series logic
- Can load external data sources
- Matches legacy behavior exactly
- Can be called before beta calculation (dependency)

**Cons:**
- Requires external data source integration
- More complex than stored proc

### Option B: Store RF as Fixed Value in Parameter Set (SIMPLER)
**Where:** `parameter_sets` table

If `approach_to_ke = 'FIXED'`:
```
rf = benchmark - risk_premium
```

This becomes a constant per parameter set.

**Pros:**
- Very simple
- No external data required
- Can calculate directly from parameters

**Cons:**
- Only works for FIXED approach
- Loses DYNAMIC approach (monthly calculations)

---

## Data Model for Storing RF

### In `metrics_outputs` table:
```sql
INSERT INTO metrics_outputs 
  (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value)
VALUES
  ('ca5aa18e...', 'cea206e7...', 'ABC', 2023, 'Risk Free Rate', 0.035),
  ('ca5aa18e...', 'cea206e7...', 'ABC', 2022, 'Risk Free Rate', 0.032),
  ...
```

**Note:** RF is typically the same for all tickers in same fiscal year (macro variable)
- Could be same value across all tickers
- Depends on whether we're modeling country-specific or global RF

---

## Current Backend Status

**Metrics_outputs table columns:**
```
dataset_id UUID - which data set
param_set_id UUID - which parameters used
ticker TEXT - company ticker
fiscal_year INTEGER - fiscal year
output_metric_name TEXT - 'Risk Free Rate', 'Beta', etc.
output_metric_value NUMERIC - the calculated value
```

**All infrastructure is ready to store RF** - just need the calculation service.

---

## Recommended Next Step

### Implement RF as Python Async Service

**Location:** Create `backend/app/services/rates_service.py`

**Function signature:**
```python
async def calculate_risk_free_rate_async(
    dataset_id: UUID,
    param_set_id: UUID
) -> dict:
    """
    Calculate Risk Free Rate for a dataset and parameter set.
    
    Returns: {
        'status': 'success' | 'error',
        'results_count': int,
        'metric_name': 'Risk Free Rate'
    }
    """
```

**Implementation details:**
1. Load parameter set (get approach_to_ke, benchmark, risk_premium)
2. If FIXED approach: `rf = benchmark - risk_premium`
3. If DYNAMIC approach: Load monthly bond data and calculate 12-month geometric mean
4. Insert results into metrics_outputs table

**Integration point:** Call in metrics orchestration pipeline BEFORE beta calculation

---

## Summary

| Aspect | Status | Notes |
|--------|--------|-------|
| Legacy Implementation | ✅ Exists | calculate_rates_async() in rates.py |
| Backend Stored Proc | ❌ Not suitable | Requires external data + complex logic |
| Backend Async Service | ⏳ To implement | Recommended approach |
| Data Model | ✅ Ready | metrics_outputs table exists |
| Infrastructure | ✅ Ready | Parameter sets table has configs |

**Decision:** Implement as Python async service in backend (not stored proc)
