# Temporal Capability Quick Reference

## What is "Temporal Capability"?

**Rolling window calculations** across multiple fiscal years to smooth volatility and capture different trend horizons.

```
1Y = Current year only (no rolling average)
3Y = Average of current year + 2 prior years
5Y = Average of current year + 4 prior years
10Y = Average of current year + 9 prior years
```

---

## Metrics Temporal Patterns

| Metric | Window Type | Calculation | Storage | Timing |
|--------|-------------|-------------|---------|--------|
| **Beta** | 60-month rolling OLS on monthly returns | `slope * 2/3 + 1/3` annualized per FY | `metrics_outputs` (param_set_id=NULL) | Pre-computed at ingestion |
| **Calc Rf** | 12-month rolling geometric mean | `(∏ rates)^(1/12) - 1` per FY month, extracted at FY end | `metrics_outputs` (param_set_id=NULL) | Pre-computed at ingestion |
| **Calc KE** | Combines Beta + Rf | `Rf + Beta × RiskPremium` | `metrics_outputs` (param_set_id=NULL) | Pre-computed at ingestion |
| **Ratio Metrics** (MB, ROE, etc.) | 1Y/3Y/5Y/10Y rolling AVG | `AVG(...) OVER (ROWS BETWEEN)` per ticker/FY | On-demand, not stored | Runtime calculation |
| **Revenue Growth** | 1Y/3Y/5Y/10Y rolling AVG | `(AVG_current - AVG_prior) / AVG_prior` | On-demand, not stored | Runtime calculation |
| **EE Growth** | 1Y/3Y/5Y/10Y rolling AVG | Same as Revenue Growth | On-demand, not stored | Runtime calculation |

---

## Database Core Fields (All Temporal Metrics)

```sql
-- fundamentals table (source data - granular)
fiscal_year INTEGER          -- Core temporal dimension
fiscal_month INTEGER         -- NULL for FISCAL records
fiscal_day INTEGER           -- NULL for FISCAL records
period_type TEXT             -- 'FISCAL' or 'MONTHLY'
numeric_value NUMERIC        -- The time-series value

-- metrics_outputs table (calculated results - aggregated)
fiscal_year INTEGER          -- Temporal aggregation point
param_set_id UUID            -- NULL = pre-computed, else = runtime
output_metric_name TEXT      -- "Calc Beta", "Calc MC", etc.
output_metric_value NUMERIC  -- Single value per FY
metadata JSONB               -- Intermediate temporal values
```

---

## Key Service Classes

| Class | Location | Purpose | Temporal Pattern |
|-------|----------|---------|------------------|
| `RatioMetricsCalculator` | `services/ratio_metrics_calculator.py` | Builds SQL window functions | `_calculate_rows_between(window)` maps 1Y/3Y/5Y/10Y |
| `RevenueGrowthCalculator` | `services/revenue_growth_calculator.py` | Revenue growth queries | Rolling avg + lag-based growth |
| `EEGrowthCalculator` | `services/ee_growth_calculator.py` | EE growth queries | Rolling avg + lag-based growth |
| `BetaPrecomputationService` | `services/beta_precomputation_service.py` | Phase 07: Pre-compute Beta | 60-month rolling OLS |
| `RiskFreeRateCalculationService` | `services/risk_free_rate_service.py` | Phase 08: Pre-compute Rf | 12-month rolling geometric mean |
| `CostOfEquityService` | `services/cost_of_equity_service.py` | Phase 09: Combine Beta + Rf | Vectorized: Rf + Beta × premium |
| `RatioMetricsService` | `services/ratio_metrics_service.py` | Ratio metric orchestration | Routes to single/multi-window calculators |

---

## SQL Window Function Pattern (All Ratio Metrics)

```sql
-- For any temporal window (1Y, 3Y, 5Y, 10Y)
SELECT
    ticker,
    fiscal_year,
    AVG(metric_value) OVER (
        PARTITION BY ticker 
        ORDER BY fiscal_year 
        ROWS BETWEEN N PRECEDING AND CURRENT ROW  -- N = window_size - 1
    ) AS rolling_value,
    ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year) AS year_rank
FROM source_table
WHERE year_rank >= MIN_YEARS_REQUIRED  -- Filters incomplete windows

-- Example for 3Y window:
-- ROWS BETWEEN 2 PRECEDING AND CURRENT ROW (2 + current = 3 years)
-- MIN_YEARS_REQUIRED = 3, so first result in year_rank=3 (3rd data point)
```

---

## Parameter Effects on Temporal Calculation

### Pre-Computed Metrics (Phase 07, 08)

| Parameter | Effect | Default |
|-----------|--------|---------|
| `beta_relative_error_tolerance` | Filters rolling OLS slopes above this % error | 40.0 |
| `cost_of_equity_approach` | Fixed (constant Rf) vs Floating (year-specific Rf) | Floating |
| `beta_rounding` | Rounding increment applied AFTER rolling window | 0.1 |

### Runtime Metrics (Ratio, Revenue Growth, EE Growth)

| Parameter | Effect |
|-----------|--------|
| `temporal_window` | Selects 1Y, 3Y, 5Y, or 10Y rolling window |
| `parameter_dependent` | If True, filters metrics_outputs by param_set_id |

---

## Pre-Computed vs Runtime Patterns

### Pre-Computed (param_set_id = NULL)
- **When:** Data ingestion (Pipeline Phase 07-09)
- **Metrics:** Beta, Calc Rf, Calc KE, L1 metrics
- **Calculation:** Happens ONCE per dataset
- **Storage:** `metrics_outputs` with param_set_id=NULL
- **Retrieval:** O(1) table lookup

### Runtime (param_set_id specified)
- **When:** User API query
- **Metrics:** Ratio metrics, Revenue/EE Growth
- **Calculation:** On-demand with SQL window functions
- **Storage:** Not stored (calculated in-flight)
- **Retrieval:** Varies 0-5s depending on dataset size

---

## Temporal Metadata in metrics_outputs

```json
{
  "Beta": {
    "fixed_beta_raw": 1.25,
    "floating_beta_raw": 1.2,
    "monthly_raw_slopes": [0.5, 0.51, ...]
  },
  "Calc Rf": {
    "rf_1y_raw": 0.035,
    "rf_1y_rounded": 0.035,
    "approach": "Floating"
  },
  "Ratio Metrics": {
    "numerator_rolling_avg": 150.0,
    "denominator_rolling_avg": 100.0,
    "year_rank": 3
  }
}
```

---

## Example: 3-Year Rolling MB Ratio

```sql
-- Fiscal years: 2001-2020
-- Window: 3Y rolling average

2001: Calc MC = 100, Calc EE = 50         ← No result (year_rank=1)
2002: Calc MC = 110, Calc EE = 55         ← No result (year_rank=2)
2003: Calc MC = 120, Calc EE = 60         ← FIRST RESULT (year_rank=3)
      MB_3Y = AVG(100,110,120) / AVG(50,55,60) = 110/55 = 2.0

2004: Calc MC = 130, Calc EE = 65
      MB_3Y = AVG(110,120,130) / AVG(55,60,65) = 120/60 = 2.0

2005: Calc MC = 140, Calc EE = 70
      MB_3Y = AVG(120,130,140) / AVG(60,65,70) = 130/65 = 2.0

...continues rolling forward through 2020
```

---

## API Endpoints for Temporal Metrics

### Single Window
```
GET /api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=AAPL&temporal_window=3Y&dataset_id=...
```

### Multiple Windows
```
GET /api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=AAPL&temporal_window=1Y,3Y,5Y&dataset_id=...
```

### Response Structure (Multi-Window)
```json
{
  "metric": "mb_ratio",
  "temporal_windows": ["1Y", "3Y", "5Y"],
  "data": [
    {
      "temporal_window": "1Y",
      "tickers": [
        {
          "ticker": "AAPL",
          "time_series": [
            {"year": 2003, "value": 2.5},
            {"year": 2004, "value": 2.4}
          ]
        }
      ]
    },
    {
      "temporal_window": "3Y",
      "tickers": [...]
    },
    ...
  ]
}
```

---

## Key Distinctions

| Aspect | Details |
|--------|---------|
| **Granularity** | Finest = monthly, stored = fiscal_year aggregation |
| **Aggregation** | Rolling averages (not cumulative), computed per window size |
| **Storage** | Pre-computed (once) or on-demand (runtime) |
| **Horizon** | 1Y (spot), 3Y, 5Y, 10Y (rolling smoothing) |
| **Parameters** | Window selection, rounding, approach (Fixed/Floating) |
| **Uniqueness** | One row per (dataset, ticker, fiscal_year, metric) in metrics_outputs |

---

## Files to Read for More Details

1. **Schema**: `/backend/database/schema/schema.sql` - fundame fundamentals & metrics_outputs structure
2. **Beta**: `/backend/app/services/beta_precomputation_service.py` - 60-month rolling OLS
3. **Rf**: `/backend/app/services/risk_free_rate_service.py` - 12-month rolling geometric mean
4. **Ratio Metrics**: `/backend/app/services/ratio_metrics_calculator.py` - Window function pattern
5. **Revenue Growth**: `/backend/app/services/revenue_growth_calculator.py` - Growth calculation pattern
6. **API**: `/backend/app/api/v1/endpoints/metrics.py` - Temporal window query parameter

