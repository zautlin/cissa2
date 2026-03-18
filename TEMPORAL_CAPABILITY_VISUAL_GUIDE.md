# Temporal Capability - Visual Architecture Guide

## 1. Timeline of Temporal Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     RAW DATA INGESTION & TEMPORAL PROCESSING                 │
└─────────────────────────────────────────────────────────────────────────────┘

  2001   2002   2003   2004   2005   2006  ... 2019   2020   2021
   │      │      │      │      │      │          │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼          ▼      ▼      ▼
┌──────────────────────────────────────────────────────────────────┐
│                    FUNDAMENTALS (Monthly & Fiscal)               │
│  Period Type: FISCAL (one per year) + MONTHLY (12 per year)     │
│  Example: 2001-2020 revenue, shares, TSR data                   │
└──────────────────────────────────────────────────────────────────┘
   │      │      │      │      │      │          │      │      │
   │      │      │      │      │      │          │      │      │
   └──────┴──────┴──────┴──────┴──────┴──────────┴──────┴──────┘
           │
           ▼ (Pipeline Phase 07-09)
┌──────────────────────────────────────────────────────────────────┐
│              ROLLING WINDOW APPLICATION (Monthly)                │
│                                                                   │
│  Beta:  60-month rolling OLS on monthly returns                 │
│  Rf:    12-month rolling geometric mean on bond yields          │
│  KE:    Combine Beta + Rf + RiskPremium                         │
└──────────────────────────────────────────────────────────────────┘
   │
   ▼ Annualize to Fiscal Year
┌──────────────────────────────────────────────────────────────────┐
│         METRICS_OUTPUTS (Pre-Computed, param_set_id=NULL)       │
│                                                                   │
│  2001: Beta=1.1,  Rf=0.03, KE=0.085                             │
│  2002: Beta=1.15, Rf=0.035, KE=0.0925                           │
│  ...                                                             │
│  2020: Beta=1.2,  Rf=0.025, KE=0.080                            │
└──────────────────────────────────────────────────────────────────┘
   │      │      │      │      │      │          │      │      │
   │      │      │      │      │      │          │      │      │
   └──────┴──────┴──────┴──────┴──────┴──────────┴──────┴──────┘
           │
           └─────────────────────────┐
                                     ▼ (Runtime - User Query)
                         ┌─────────────────────────────────┐
                         │  RUNTIME SECOND-STAGE ROLLING   │
                         │  AVERAGE (1Y, 3Y, 5Y, 10Y)      │
                         │                                  │
                         │  SELECT AVG(...) OVER (         │
                         │    ROWS BETWEEN ... AND CURRENT │
                         │  )                              │
                         └─────────────────────────────────┘
                                     │
                                     ▼
                         ┌─────────────────────────────────┐
                         │    USER API RESPONSE             │
                         │  (Ratio Metrics, Growth, etc.)   │
                         └─────────────────────────────────┘
```

---

## 2. Rolling Window Sizes - Visual Representation

```
FISCAL YEARS: 2001 | 2002 | 2003 | 2004 | 2005 | 2006 | 2007 | 2008 | ...

1Y WINDOW (Spot Value):
                                      │2003│
                                      └────┘
                          Result:     Value_2003

3Y ROLLING AVERAGE:
                          │2001│2002│2003│
                          └────┬────┬────┘
                              Average of 3 years

                                       │2002│2003│2004│
                                       └────┬────┬────┘
                                           Average of 3 years

                                               │2003│2004│2005│
                                               └────┬────┬────┘
                                                   Average of 3 years

5Y ROLLING AVERAGE:
                 │2001│2002│2003│2004│2005│
                 └────┬────┬────┬────┬────┘
                  Average of 5 years (first result at 2005)

10Y ROLLING AVERAGE:
    │2001│2002│2003│2004│2005│2006│2007│2008│2009│2010│
    └────┬────┬────┬────┬────┬────┬────┬────┬────┬────┘
      Average of 10 years (first result at 2010)
```

---

## 3. Service Layer Temporal Routing

```
┌──────────────────────────────────────────────────────────┐
│              USER API REQUEST                             │
│  GET /api/v1/metrics/ratio-metrics?                      │
│    metric=mb_ratio&                                       │
│    temporal_window=1Y,3Y,5Y&                             │
│    tickers=AAPL,MSFT                                      │
└──────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────┐
│        RatioMetricsService                               │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Is multi-window? (3 windows requested)             │ │
│  │ → Yes: calculate_ratio_metric_multi_window()       │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
              │
              ├─────────────┬──────────────┬──────────────┐
              ▼             ▼              ▼              ▼
         ┌─────────┐   ┌─────────┐   ┌─────────┐   (Other windows)
         │RatiCals │   │RatioCalc│   │RatioCalc│
         │(1Y)     │   │(3Y)     │   │(5Y)     │
         └────┬────┘   └────┬────┘   └────┬────┘
              │             │              │
              ├─────────────┼──────────────┤
              ▼             ▼              ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │ SQL Builder  │ │ SQL Builder  │ │ SQL Builder  │
    │ (0 ROWS)     │ │ (2 ROWS)     │ │ (4 ROWS)     │
    │ BETWEEN      │ │ BETWEEN      │ │ BETWEEN      │
    └──────────────┘ └──────────────┘ └──────────────┘
              │             │              │
              └─────────────┼──────────────┘
                            ▼
                  ┌──────────────────┐
                  │ Aggregate Results │
                  │ (by window)       │
                  └──────────────────┘
                            │
                            ▼
                  ┌──────────────────────────────┐
                  │ RatioMetricsMultiWindowResponse
                  │ {                            │
                  │   metric: "mb_ratio",        │
                  │   temporal_windows: [        │
                  │     "1Y", "3Y", "5Y"         │
                  │   ],                         │
                  │   data: [                    │
                  │     {window: "1Y", ...},     │
                  │     {window: "3Y", ...},     │
                  │     {window: "5Y", ...}      │
                  │   ]                          │
                  │ }                            │
                  └──────────────────────────────┘
```

---

## 4. Pre-Computed vs Runtime Execution Model

```
                        DATA INGESTION PIPELINE
                       (One-time, per dataset)

        ┌─────────────────────────────────────────────────┐
        │          PHASE 07: BETA CALCULATION             │
        ├─────────────────────────────────────────────────┤
        │ Input: Monthly COMPANY_TSR + INDEX_TSR          │
        │ Temporal: 60-month rolling OLS (monthly basis)  │
        │ Output: One Beta per fiscal_year                │
        │ Storage: metrics_outputs (param_set_id=NULL)    │
        │ Time: ≈60 seconds                               │
        └─────────────────────────────────────────────────┘
                        │
                        ▼
        ┌─────────────────────────────────────────────────┐
        │      PHASE 08: RISK-FREE RATE CALCULATION       │
        ├─────────────────────────────────────────────────┤
        │ Input: Monthly bond yields (GACGB10 Index)      │
        │ Temporal: 12-month rolling geometric mean       │
        │ Output: One Calc Rf per fiscal_year             │
        │ Storage: metrics_outputs (param_set_id=NULL)    │
        │ Time: ≈30 seconds                               │
        └─────────────────────────────────────────────────┘
                        │
                        ▼
        ┌─────────────────────────────────────────────────┐
        │     PHASE 09: COST OF EQUITY CALCULATION        │
        ├─────────────────────────────────────────────────┤
        │ Input: Calc Beta + Calc Rf (both pre-computed)  │
        │ Temporal: None (combines phase 07 + 08 results) │
        │ Calc: KE = Rf + Beta × RiskPremium              │
        │ Output: One Calc KE per fiscal_year             │
        │ Storage: metrics_outputs (param_set_id=NULL)    │
        │ Time: ≈5 seconds                                │
        └─────────────────────────────────────────────────┘
                        │
                        ▼
        ┌─────────────────────────────────────────────────┐
        │     metrics_outputs Table (Fully Populated)     │
        │   (Ready for retrieval, O(1) lookup time)       │
        └─────────────────────────────────────────────────┘

====================================================================

                          USER QUERY TIME
                    (Dynamic, per request)

        ┌─────────────────────────────────────────────────┐
        │   User requests: /ratio-metrics?                │
        │   temporal_window=1Y,3Y,5Y                       │
        ├─────────────────────────────────────────────────┤
        │ For each window:                                │
        │   1. RatioMetricsCalculator.build_query()       │
        │   2. Parametrize ROWS BETWEEN clause            │
        │   3. Execute SQL window function query          │
        │   4. Format results                             │
        │                                                 │
        │ Temporal Pattern:                               │
        │   - Window size determines window_size-1 rows   │
        │   - year_rank filter ensures complete windows   │
        │   - Rolling AVG OVER (ORDER BY fiscal_year)     │
        └─────────────────────────────────────────────────┘
                        │
                        ▼
        ┌─────────────────────────────────────────────────┐
        │          Ratio Metrics Response                 │
        │  (NOT stored, computed on-demand)               │
        │  Time: 0.5-5 seconds (depends on dataset size)  │
        └─────────────────────────────────────────────────┘
```

---

## 5. Temporal Dimension in Database

```
FUNDAMENTALS TABLE (Source Data - Multiple Rows per Ticker/Year)
┌─────────────────────────────────────────────────────────────────┐
│ ticker │ fiscal_year │ fiscal_month │ fiscal_day │ metric_name  │
├─────────────────────────────────────────────────────────────────┤
│ AAPL   │ 2001        │ NULL         │ NULL       │ REVENUE      │ ← FISCAL
│ AAPL   │ 2001        │ 1            │ 31         │ COMPANY_TSR  │ ← MONTHLY
│ AAPL   │ 2001        │ 2            │ 28         │ COMPANY_TSR  │ ← MONTHLY
│ ...    │ ...         │ ...          │ ...        │ ...          │
│ AAPL   │ 2020        │ 12           │ 31         │ COMPANY_TSR  │ ← MONTHLY
│ AAPL   │ 2020        │ NULL         │ NULL       │ REVENUE      │ ← FISCAL
└─────────────────────────────────────────────────────────────────┘
         ▲
         │ period_type = 'FISCAL' or 'MONTHLY'
         │
         └─ Core temporal dimension: fiscal_year

METRICS_OUTPUTS TABLE (Calculated Results - One Row per Year)
┌─────────────────────────────────────────────────────────────────┐
│ ticker │ fiscal_year │ param_set_id │ output_metric_name      │
├─────────────────────────────────────────────────────────────────┤
│ AAPL   │ 2001        │ NULL         │ Calc Beta               │ ← PRE-COMPUTED
│ AAPL   │ 2001        │ NULL         │ Calc Rf                 │ ← PRE-COMPUTED
│ AAPL   │ 2001        │ NULL         │ Calc KE                 │ ← PRE-COMPUTED
│ AAPL   │ 2001        │ param123     │ Calc MC                 │ ← PARAM-SPECIFIC
│ AAPL   │ 2001        │ param456     │ Calc EE                 │ ← PARAM-SPECIFIC
│ ...    │ ...         │ ...          │ ...                     │
│ AAPL   │ 2020        │ NULL         │ Calc Beta               │
│ AAPL   │ 2020        │ NULL         │ Calc Rf                 │
└─────────────────────────────────────────────────────────────────┘
         ▲                    ▲
         │                    │
   Temporal Aggregation       └─ Parameter Set: NULL = Pre-computed
   Point: fiscal_year            else = Runtime/Parameter-specific
```

---

## 6. Temporal Window Calculation Flow (Example: 3Y Revenue Growth)

```
INPUT DATA (Fiscal Years):
┌────────────────────────────────────────────────────────────┐
│ Year │ 2001 │ 2002 │ 2003 │ 2004 │ 2005 │ 2006 │ ...     │
│      │      │      │      │      │      │      │          │
│Rev  │ 1000 │ 1100 │ 1200 │ 1400 │ 1600 │ 1800 │ ...     │
└────────────────────────────────────────────────────────────┘

STEP 1: ROLLING AVERAGE (3Y window = 2 ROWS PRECEDING)
┌────────────────────────────────────────────────────────────┐
│ Year │ 2001 │ 2002 │ 2003    │ 2004    │ 2005    │ ...    │
│      │      │      │         │         │         │        │
│Avg  │ 1000 │ 1050 │ 1100    │ 1233    │ 1400    │ ...    │
│     │      │      │(1100)   │(1233)   │(1600)   │        │
│     │      │      │3-yr avg │3-yr avg │3-yr avg │        │
│     │      │      │         │         │         │        │
│Rank │  1   │  2   │  3 ◄    │  4      │  5      │ ...    │
│     │      │      │ First   │         │         │        │
│     │      │      │ result  │         │         │        │
└────────────────────────────────────────────────────────────┘

STEP 2: LAG PRIOR YEAR AVERAGE
┌────────────────────────────────────────────────────────────┐
│ Year │ 2003 │ 2004  │ 2005    │ ...                        │
│      │      │       │         │                            │
│Avg  │ 1100 │ 1233  │ 1400    │ ...                        │
│Prior│ None │ 1100  │ 1233    │ ...  (LAG function)        │
└────────────────────────────────────────────────────────────┘

STEP 3: CALCULATE GROWTH
┌────────────────────────────────────────────────────────────┐
│ Year   │ 2003 │ 2004        │ 2005        │ ...            │
│        │      │             │             │                │
│Growth │ NULL │(1233-1100)  │(1400-1233)  │ ...            │
│       │      │  / 1100     │  / 1233     │                │
│       │      │  = 12.1%    │  = 13.5%    │                │
└────────────────────────────────────────────────────────────┘

FINAL OUTPUT (Query Result):
┌────────────────────────────────────────────────────────────┐
│ year │ revenue_growth_3y                                   │
├────────────────────────────────────────────────────────────┤
│ 2003 │ NULL (no prior avg)                                │
│ 2004 │ 0.121 (12.1%)                                      │
│ 2005 │ 0.135 (13.5%)                                      │
│ ...  │ ...                                                │
└────────────────────────────────────────────────────────────┘
```

---

## 7. Metric Lifecycle: From Raw Data to User Response

```
┌────────────────────────────────────────────────────────────┐
│ STAGE 1: RAW DATA INGESTION                                │
│ ─────────────────────────────────────────────────────────  │
│ Input CSV → raw_data table (exact copy)                    │
│ Validation: Duplicate detection, type checking             │
│ No temporal processing yet                                 │
└────────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────────┐
│ STAGE 2: CLEANING & ALIGNMENT                              │
│ ─────────────────────────────────────────────────────────  │
│ FY alignment, imputation, fundamentals table              │
│ Separate FISCAL from MONTHLY data                         │
│ period_type column tracks source granularity              │
└────────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────────┐
│ STAGE 3: PRE-COMPUTED METRICS (TEMPORAL PROCESSING)        │
│ ─────────────────────────────────────────────────────────  │
│ Phase 07: Beta (60-month rolling OLS)                     │
│ Phase 08: Rf (12-month rolling geometric mean)            │
│ Phase 09: KE (combine beta + rf)                          │
│ Output: metrics_outputs with param_set_id=NULL           │
│ Storage: Permanent (one row per fiscal_year)              │
└────────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────────┐
│ STAGE 4: RUNTIME METRICS (ON-DEMAND TEMPORAL)              │
│ ─────────────────────────────────────────────────────────  │
│ User API query: temporal_window=3Y                        │
│ SQL builder: ROWS BETWEEN 2 PRECEDING AND CURRENT ROW    │
│ Execution: Window functions on pre-computed base          │
│ Output: RatioMetricsMultiWindowResponse                   │
│ Storage: NOT stored (calculated in-flight)                │
└────────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────────┐
│ FINAL: USER RESPONSE                                       │
│ ─────────────────────────────────────────────────────────  │
│ JSON: {metric, temporal_windows, data}                    │
│ Time-series per ticker per window                         │
│ Years with insufficient data: NULL                        │
└────────────────────────────────────────────────────────────┘
```

---

## 8. Parameter Effect on Temporal Calculation

```
PARAMETER SET: {beta_rounding=0.1, cost_of_equity_approach="Floating"}
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
        ┌──────────────────────┐      ┌──────────────────────┐
        │ BETA ROUNDING        │      │ COST OF EQUITY       │
        │ (Post-Window)        │      │ (Affects Rf)         │
        │                      │      │                      │
        │ raw_beta = 1.27      │      │ Floating:            │
        │ rounding = 0.1       │      │ Calc Rf = Rf_1Y      │
        │                      │      │ (Year-specific)      │
        │ rounded = 1.3        │      │                      │
        │ (Per fiscal_year)    │      │ vs Fixed:            │
        │                      │      │ Calc Rf = Benchmark  │
        │                      │      │        - Risk Premium │
        │                      │      │ (Constant)           │
        └──────────────────────┘      └──────────────────────┘
                    │                               │
                    ▼                               ▼
            ┌─────────────────────────────────────┐
            │ TEMPORAL IMPACT:                    │
            │ - Rounding applied to each year    │
            │ - Approach affects Rf variation    │
            │ - Both shape final Cost of Equity  │
            └─────────────────────────────────────┘
```

---

## 9. Uniqueness Constraint - Temporal Aggregation Point

```
BEFORE AGGREGATION (fundamentals table - many rows):
┌──────────────────────────────────────────────────────┐
│ ticker │ fiscal_year │ fiscal_month │ metric_name    │
├──────────────────────────────────────────────────────┤
│ AAPL   │ 2001        │ 1            │ COMPANY_TSR    │
│ AAPL   │ 2001        │ 2            │ COMPANY_TSR    │
│ AAPL   │ 2001        │ 3            │ COMPANY_TSR    │
│ ...    │ ...         │ ...          │ ...            │
│ AAPL   │ 2001        │ 12           │ COMPANY_TSR    │
│ AAPL   │ 2001        │ NULL         │ REVENUE        │
│ ...    │ ...         │ ...          │ ...            │
│ AAPL   │ 2020        │ NULL         │ REVENUE        │
└──────────────────────────────────────────────────────┘
(40+ rows for 2001 COMPANY_TSR + other metrics)

AFTER AGGREGATION (metrics_outputs table - one row):
┌──────────────────────────────────────────────────────┐
│ ticker │ fiscal_year │ output_metric_name │ value   │
├──────────────────────────────────────────────────────┤
│ AAPL   │ 2001        │ Calc Beta          │ 1.2     │
│ AAPL   │ 2001        │ Calc Rf            │ 0.035   │
│ AAPL   │ 2001        │ Calc KE            │ 0.085   │
│ ...    │ ...         │ ...                │ ...     │
│ AAPL   │ 2020        │ Calc Beta          │ 1.15    │
└──────────────────────────────────────────────────────┘
(One row per fiscal_year per metric)

UNIQUE KEY: (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
             └─────────────────────────────────────────────────┬──────────────────┘
                                                      Temporal aggregation point
```

