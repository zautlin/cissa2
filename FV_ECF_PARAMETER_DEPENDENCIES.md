# FV ECF Parameter Dependencies - Complete Analysis

## 1. ALL FV ECF Input Parameters

### Parameters Needed for FV_ECF Calculation

| # | Parameter | Type | Source | Pre-Calculated? | Parameter-Set Dependent? | Notes |
|---|-----------|------|--------|-----------------|--------------------------|-------|
| 1 | **incl_franking** | String ("Yes"/"No") | Query param → Parameters table | Yes | Yes | Passed as query parameter to endpoint; can be overridden in parameter_sets.param_overrides |
| 2 | **frank_tax_rate** | Numeric (0-1) | Parameters table | Yes | Yes | Default 0.30 (30%); can be overridden in parameter_sets.param_overrides; converted from percentage if >1 |
| 3 | **value_franking_cr** | Numeric (0-1) | Parameters table | Yes | Yes | Default 0.75 (75%); can be overridden in parameter_sets.param_overrides; converted from percentage if >1 |

### Data Inputs (Fetched at Runtime)

| # | Data Input | Source Table | Pre-Calculated? | Notes |
|---|------------|---------------|-----------------|-------|
| 4 | **DIVIDENDS** | fundamentals | No (from input data) | Metric name: 'DIVIDENDS'; period_type='FISCAL' |
| 5 | **FRANKING** | fundamentals | No (from input data) | Metric name: 'FRANKING'; period_type='FISCAL'; indicates franking level (0-1) |
| 6 | **Non Div ECF** | metrics_outputs | Yes (Phase 06 L1) | Pre-calculated as: Calc ECF + DIVIDENDS; must exist before FV_ECF can run |
| 7 | **Calc KE (lagged)** | metrics_outputs | Yes (Phase 09 + lagging) | Metric name: 'Calc KE'; uses KE from fiscal_year-1; lagged via SQL LEFT JOIN |

---

## 2. Source & Dependency Matrix

### Parameter Table (Database)
Location: `cissa.parameters` table

Baseline parameters (schema initialization):
- `include_franking_credits_tsr` (BOOLEAN, default: false) - **NOT directly used; see "Calc Incl"**
- `tax_rate_franking_credits` (NUMERIC, default: 30.0)
- `value_of_franking_credits` (NUMERIC, default: 75.0)

**IMPORTANT:** The parameter names in the FV_ECF service are slightly different:
- `frank_tax_rate` (not `tax_rate_franking_credits`) - fetched from parameters.parameter_name = 'frank_tax_rate'
- `value_franking_cr` (not `value_of_franking_credits`) - fetched from parameters.parameter_name = 'value_franking_cr'

### Parameter Set Overrides
Location: `cissa.parameter_sets.param_overrides` (JSON)

Can override:
- `frank_tax_rate`
- `value_franking_cr`
- `incl_franking` (YES/NO)

### Fundamentals (Input Data)
Location: `cissa.fundamentals` table

Fetched metrics:
- `DIVIDENDS` - annual dividend per share
- `FRANKING` - franking ratio (0-1)

### Pre-Calculated Metrics (metrics_outputs)
Location: `cissa.metrics_outputs` table

Required metrics:
- `Non Div ECF` (output_metric_name='Non Div ECF') - **MUST be pre-calculated**
- `Calc KE` (output_metric_name='Calc KE') - **MUST be pre-calculated and lagged**

---

## 3. Dependent Metrics Analysis

### DIVIDENDS
- **Source:** fundamentals table (metric_name='DIVIDENDS')
- **Pre-calculated:** No - comes from input data
- **Parameter-dependent:** No - raw data
- **When calculated:** During data ingestion (Phase 1)

### Non Div ECF
- **Source:** metrics_outputs table (output_metric_name='Non Div ECF')
- **Pre-calculated:** Yes - Phase 06 (L1 Basic Metrics)
- **Formula:** `Calc ECF + DIVIDENDS`
- **Parameter-dependent:** No
- **Prerequisites:** 
  - Calc ECF must be calculated first
  - DIVIDENDS available in fundamentals
- **Status:** Currently not calculated in production; must be implemented before FV_ECF

### Calc KE (Lagged)
- **Source:** metrics_outputs table (output_metric_name='Calc KE'), lagged to prior fiscal year
- **Pre-calculated:** Yes - Phase 09 (Cost of Equity Service)
- **Formula:** `Rf + Beta × Equity Risk Premium`
- **Parameter-dependent:** Yes (equity_risk_premium parameter)
- **Lagging mechanism:** 
  - SQL LEFT JOIN: `ke.fiscal_year = ke_lagged.fiscal_year + 1`
  - ke_open = KE from fiscal_year-1
  - Used as opening KE value for the year
- **Status:** Fully implemented

### Calc Open KE (vs Calc KE)
- **Calc KE:** Current year cost of equity
- **Calc Open KE (ke_open):** Prior year cost of equity (lagged by 1 year)
- **Implementation:** Done via SQL LEFT JOIN in `_fetch_lagged_ke()` method
- **How it works:**
  ```sql
  FROM metrics_outputs ke                           -- Current year's KE
  LEFT JOIN metrics_outputs ke_lagged              -- Prior year's KE
    ON ke.ticker = ke_lagged.ticker
    AND ke.fiscal_year = ke_lagged.fiscal_year + 1  -- Join condition
  ```

---

## 4. FV_ECF Formula Components

### Excel Formula Structure (from user)

```
For each interval (1, 3, 5, 10):
  For seq in range(interval, 0, -1):
    fv_interval = (seq - 1) * (-1)  # Results in: 0, -1, -2, ...
    power = interval + fv_interval - 1
    
    IF incl_franking == "Yes" THEN:
      TEMP = (
        -DIVIDENDS.shift(fv_interval)
        + NON_DIV_ECF.shift(fv_interval)
        - (DIVIDENDS.shift(fv_interval) / (1 - frank_tax_rate))
          × frank_tax_rate × value_franking_cr × FRANKING.shift(fv_interval)
      ) × (1 + Calc_Open_KE)^power × scale_by
    ELSE:
      TEMP = (DIVIDENDS + NON_DIV_ECF) × (1 + Calc_Open_KE)^fv_interval × scale_by
  
  FV_ECF = SUM(all TEMP columns).shift(interval - 1)
```

### What "Calc Incl" Means

**Answer:** `Calc Incl` is NOT a metric name. It's shorthand notation in the Excel formula meaning:
- **incl_franking** parameter value (YES/NO)
- Determines whether franking credit adjustment is applied
- NOT a pre-calculated metric
- It's a BOOLEAN parameter stored in:
  - Query parameters to endpoint: `incl_franking` parameter
  - Parameters table: `incl_franking` (no baseline, but added via parameter_sets.param_overrides)
  - Parameter sets: `param_overrides['incl_franking']`

**Note:** The schema has `include_franking_credits_tsr` (for TSR calculation), but FV_ECF uses `incl_franking` parameter directly from the endpoint query parameter.

---

## 5. FV_ECF Calculation Requirements

### Prerequisites (Must Exist Before FV_ECF Calculation)

1. **Phase 06 (L1 Basic Metrics):**
   - ✓ DIVIDENDS (in fundamentals)
   - ✓ FRANKING (in fundamentals)
   - ✗ Calc ECF (in metrics_outputs) - REQUIRED for Non Div ECF
   - ✗ Non Div ECF (in metrics_outputs) - **NOT YET IMPLEMENTED**

2. **Phase 09 (Cost of Equity):**
   - ✓ Calc KE (in metrics_outputs, dataset_id + param_set_id scoped)

### Runtime Processing Flow

```
FV_ECF Calculation (_fetch_lagged_ke):
  1. FETCH Calc KE for current fiscal_year
  2. FETCH Calc KE for prior fiscal_year (fiscal_year - 1)
  3. LEFT JOIN to get ke_open (KE from prior year)
  4. Rows without prior year KE will have ke_open = NULL (NaN)

FV_ECF Calculation (_calculate_fv_ecf_for_interval):
  1. For each ticker group (to respect ticker boundaries)
  2. Create scale_by = 1 if ke_open > 0 else 0
  3. For each sequence in interval:
     a. Shift dividend, non_div_ecf, franking by fv_interval
     b. Calculate TEMP with vectorized pandas operations
     c. Build TEMP columns
  4. Sum all TEMP columns
  5. Shift result by (interval - 1)
  6. Skip rows with NaN values

Storage:
  - Insert into metrics_outputs (dataset_id, param_set_id scoped)
  - One record per interval per ticker-year
  - Total: 4 intervals × number of ticker-year combinations
```

### What Gets Calculated vs What's Pre-Calculated

**Pre-Calculated (Must Exist):**
- `Calc KE` - Yes (Phase 09)
- `Non Div ECF` - Needs implementation (Phase 06, currently missing)
- Parameters (frank_tax_rate, value_franking_cr, incl_franking) - Yes

**Calculated at Runtime (During FV_ECF):**
- Lagged KE (ke_open) - Done via SQL JOIN
- All TEMP values - Vectorized pandas operations
- FV_ECF sums - Pandas sum and shift
- Shifted final result - Pandas shift

**Never Pre-Calculated (Always Runtime):**
- Year shifts (.shift() operations)
- Power calculations ((1 + ke_open)^power)
- Final sums and shifts

---

## 6. Alternative Formula (If Needed)

From economic_profit_service.py comments, an alternative formula exists:

```
PAT_EX = (EP / |EE_open + KE_open|) × EE_open
XO_COST_EX = PATXO - PAT_EX
```

This uses:
- **Calc PAT (PROFIT_AFTER_TAX)** - from fundamentals
- **Calc EE (ECONOMIC_EQUITY)** - from metrics_outputs, lagged
- **Calc KE (COST_OF_EQUITY)** - from metrics_outputs, lagged

**Is this needed for FV_ECF?**
- NO - FV_ECF does NOT use PAT_EX or PROFIT_AFTER_TAX
- These are for economic profit calculations (Phase 10a)
- FV_ECF only uses: DIVIDENDS, FRANKING, Non Div ECF, Calc KE (lagged)

---

## 7. Pre-Calculation Feasibility Analysis

### Can FV_ECF Be Pre-Calculated?

**SHORT ANSWER:** Partially. Components are pre-calculated, but final values need runtime generation.

### What CAN Be Pre-Calculated

1. ✓ **Parameters** (frank_tax_rate, value_franking_cr, incl_franking)
   - Stored in parameter_sets table
   - No computation needed

2. ✓ **Fundamentals Data** (DIVIDENDS, FRANKING)
   - Already in database
   - No computation needed

3. ✓ **Lagged KE** (ke_open)
   - Can be pre-joined and stored as separate table
   - SQL: LEFT JOIN on (ticker, fiscal_year-1)
   - Could reduce runtime overhead

### What CANNOT Be Pre-Calculated (Requires Runtime)

1. ✗ **Year Shifting** (.shift() operations)
   - Requires sequential ordered data per ticker
   - Pandas groupby().shift() is inherently runtime
   - Cannot serialize/store shifts without duplicating all data

2. ✗ **Power Calculations** ((1 + ke_open)^power)
   - Power varies by interval and sequence
   - Results vary by ke_open value
   - Could pre-calculate only for common ke_open values (not practical)

3. ✗ **Final Sums and Shifts** 
   - Sum(TEMP columns) requires all shifted columns in memory
   - Final .shift(interval-1) requires sequential context

### Optimization Opportunities

1. **Pre-cache lagged KE** for faster runtime execution
2. **Vectorize all operations** (already done in service)
3. **Batch database inserts** (already done - 1000 records per batch)
4. **Optimize shift operations** using rolling window functions

---

## 8. Complete Input Parameter Matrix

### Final Comprehensive List

| # | Input | Category | Source | Status | Notes |
|----|-------|----------|--------|--------|-------|
| 1 | incl_franking | Parameter | Endpoint query / param_sets | ✓ Implemented | String: "Yes"/"No" |
| 2 | frank_tax_rate | Parameter | parameters table / param_sets | ✓ Implemented | Numeric: 0-1; default 0.30 |
| 3 | value_franking_cr | Parameter | parameters table / param_sets | ✓ Implemented | Numeric: 0-1; default 0.75 |
| 4 | DIVIDENDS | Fundamental | fundamentals table | ✓ Available | From input data |
| 5 | FRANKING | Fundamental | fundamentals table | ✓ Available | From input data |
| 6 | Non Div ECF | Metric | metrics_outputs | ✗ NOT IMPLEMENTED | Phase 06 dependency |
| 7 | Calc KE (current) | Metric | metrics_outputs | ✓ Available | Phase 09 pre-calculated |
| 8 | Calc KE (lagged -1Y) | Computed | metrics_outputs + SQL JOIN | ✓ Available | Runtime: SQL LEFT JOIN |

---

## 9. Critical Implementation Blocker

### Current Status
**Non Div ECF is NOT being calculated and NOT available in metrics_outputs**

### Impact
- FV_ECF cannot be calculated without Non Div ECF
- Fetch will return empty results or NULL values
- INSERT statement will be skipped for rows with NaN

### Resolution
1. Implement Calc ECF calculation (Phase 06 pre-requisite)
2. Implement Non Div ECF calculation: `Calc ECF + DIVIDENDS`
3. Verify both are in metrics_outputs before running FV_ECF

### Code Location
- FV_ECF Service: `/home/ubuntu/cissa/backend/app/services/fv_ecf_service.py`
- Fetch Query (line 339-348): Queries metrics_outputs for 'Non Div ECF'
- Default: Sets to None if not found (line 357)

---

## 10. Summary Table: Where Each Component Comes From

```
FV_ECF_Y Inputs
├── Parameters (3)
│   ├── incl_franking → Endpoint query param / parameter_sets table
│   ├── frank_tax_rate → parameters table (parameter_name='frank_tax_rate')
│   └── value_franking_cr → parameters table (parameter_name='value_franking_cr')
│
├── Fundamentals (2)
│   ├── DIVIDENDS → fundamentals table (metric_name='DIVIDENDS')
│   └── FRANKING → fundamentals table (metric_name='FRANKING')
│
├── Pre-Calculated Metrics (2)
│   ├── Non Div ECF → metrics_outputs (output_metric_name='Non Div ECF') [NOT YET IMPL]
│   └── Calc KE (lagged) → metrics_outputs (output_metric_name='Calc KE') via SQL JOIN
│
└── Computed at Runtime
    ├── ke_open (lagged KE) → SQL LEFT JOIN on metrics_outputs
    ├── scale_by = IF(ke_open > 0, 1, 0) → Vectorized Pandas
    ├── TEMP columns → Shift + multiply + sum operations
    └── FV_ECF_Y → Final shift by (interval - 1)
```

---

## References

### Source Files
- `/home/ubuntu/cissa/backend/app/services/fv_ecf_service.py` - Main implementation
- `/home/ubuntu/cissa/backend/app/services/economic_profit_service.py` - Related PAT_EX reference
- `/home/ubuntu/cissa/backend/app/services/metrics_service.py` - Metric definitions
- `/home/ubuntu/cissa/backend/app/api/v1/endpoints/metrics.py` - API endpoint
- `/home/ubuntu/cissa/example-calculations/src/executors/fvecf.py` - Legacy example

### Parameters
- `/home/ubuntu/cissa/backend/database/schema/schema.sql` - 13 baseline parameters
- Parameter_set_id is crucial - scopes all metric calculations

### Key Classes
- `FVECFService` - Orchestrates FV_ECF calculation
- `MetricsService` - Routes metric calculations
- `EconomicProfitService` - Related Phase 10a metrics
