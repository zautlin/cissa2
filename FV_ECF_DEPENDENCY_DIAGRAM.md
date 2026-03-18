# FV ECF Parameter & Data Dependency Diagram

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FV_ECF Calculation Service                            │
│                     (Phase 10b - L2 Metrics Layer)                           │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT SOURCES
═════════════════════════════════════════════════════════════════════════════

┌─────────────────────────┐
│   ENDPOINT PARAMETERS   │
├─────────────────────────┤
│ POST /l2-fv-ecf/        │
│ calculate?              │
│  dataset_id = <UUID>    │
│  param_set_id = <UUID>  │
│  incl_franking = Yes/No │
└──────────────┬──────────┘
               │
               ▼
        ┌──────────────┐
        │ incl_franking│ (default: "Yes")
        └──────────────┘


┌──────────────────────────────┐
│  PARAMETERS TABLE            │
│  cissa.parameters            │
├──────────────────────────────┤
│ parameter_name               │
│ default_value                │
├──────────────────────────────┤
│ frank_tax_rate          → 0.30
│ value_franking_cr       → 0.75
│ (13 total baseline params)   │
└──────────────┬───────────────┘
               │
               ▼
        ┌──────────────────────────┐
        │ frank_tax_rate = 0.30    │
        │ value_franking_cr = 0.75 │
        └──────────────────────────┘


┌──────────────────────────────┐
│  PARAMETER_SETS TABLE        │
│  cissa.parameter_sets        │
├──────────────────────────────┤
│ param_set_id = <UUID>        │
│ param_overrides (JSON)       │
│  {                           │
│    "frank_tax_rate": 0.25,   │
│    "value_franking_cr": 0.80,│
│    "incl_franking": "Yes"    │
│  }                           │
└──────────────┬───────────────┘
               │ (LEFT JOIN to get overrides)
               ▼
        ┌──────────────────────────┐
        │ Final Parameters:         │
        │  incl_franking = "Yes"    │
        │  frank_tax_rate = 0.25    │ (overridden)
        │  value_franking_cr = 0.80 │ (overridden)
        └──────────────────────────┘


┌──────────────────────────────────────┐
│  FUNDAMENTALS TABLE                  │
│  cissa.fundamentals                  │
├──────────────────────────────────────┤
│ dataset_id, ticker, fiscal_year      │
│ metric_name, numeric_value           │
├──────────────────────────────────────┤
│ DIVIDENDS (metric_name)         ─┐   │
│ FRANKING (metric_name)          ─┼──→│
│ (raw input data)                 │   │
└────────────────┬─────────────────┘   │
                 │                      │
                 ▼                      │
        ┌────────────────────────┐      │
        │ DIVIDENDS (by ticker)  │      │
        │ FRANKING (0-1 ratio)   │◄─────┘
        └────────────────────────┘


┌──────────────────────────────────────┐
│  METRICS_OUTPUTS TABLE               │
│  cissa.metrics_outputs               │
├──────────────────────────────────────┤
│ dataset_id, param_set_id             │
│ ticker, fiscal_year                  │
│ output_metric_name, output_metric    │
├──────────────────────────────────────┤
│ Non Div ECF              ◄─── MISSING │
│  (output_metric_name)     (NOT YET    │
│                           IMPLEMENTED)│
│                                       │
│ Calc KE                  ◄─── Ready  │
│  (output_metric_name)     (Phase 09)  │
│                                       │
│ Calc KE (lagged -1Y)     ◄─── Ready  │
│  (via SQL LEFT JOIN)      (Runtime    │
│                            computed)  │
└──────────────┬──────────────────────┬─┘
               │                      │
               ▼                      ▼
        ┌─────────────────┐   ┌───────────────┐
        │ Non Div ECF     │   │ Calc KE       │
        │ (MISSING)       │   │ (from Phase 09)
        └─────────────────┘   └───────┬───────┘
                                      │
                                      │ SQL LEFT JOIN:
                                      │ ke.fiscal_year = 
                                      │ ke_lagged.fiscal_year + 1
                                      │
                                      ▼
                              ┌───────────────┐
                              │ ke_open       │
                              │ (KE from -1Y) │
                              └───────────────┘


═════════════════════════════════════════════════════════════════════════════

FV_ECF CALCULATION FLOW
═════════════════════════════════════════════════════════════════════════════

Step 1: Fetch & Join Data
────────────────────────────────────────────────────────────────────────────

┌──────────────────────┐
│ FUNDAMENTALS         │
│ (DIVIDENDS, FRANKING)│
└──────┬───────────────┘
       │
       │ LEFT JOIN on (ticker, fiscal_year)
       │
       ▼
┌──────────────────────┐
│ Merged DataFrame:    │
│ ticker               │
│ fiscal_year          │
│ dividend             │
│ franking             │
│ non_div_ecf          │ (from metrics_outputs)
└──────┬───────────────┘
       │
       │ LEFT JOIN on (ticker, fiscal_year)
       │
       ▼
┌──────────────────────┐
│ Final DataFrame:     │
│ ticker               │
│ fiscal_year          │
│ dividend             │
│ franking             │
│ non_div_ecf          │
│ ke_open              │ (lagged KE from -1Y)
└──────────────────────┘


Step 2: Calculate FV_ECF (Vectorized)
────────────────────────────────────────────────────────────────────────────

For interval in [1, 3, 5, 10]:
  For ticker_group in data.groupby('ticker'):
    scale_by = WHERE(ke_open > 0, 1, 0)
    
    For seq in range(interval, 0, -1):
      fv_interval = (seq - 1) * (-1)
      power = interval + fv_interval - 1
      
      IF incl_franking == "Yes":
        TEMP = (
          -dividend.shift(fv_interval)
          + non_div_ecf.shift(fv_interval)
          - (dividend.shift(fv_interval) / (1 - frank_tax_rate))
            * frank_tax_rate * value_franking_cr * franking.shift(fv_interval)
        ) * (1 + ke_open)^power * scale_by
      ELSE:
        TEMP = (dividend + non_div_ecf) * (1 + ke_open)^fv_interval * scale_by
    
    fv_ecf_sum = SUM(all TEMP columns)
    fv_ecf_final = fv_ecf_sum.shift(interval - 1)


Step 3: Insert Results
────────────────────────────────────────────────────────────────────────────

For each non-NaN fv_ecf_value:
  INSERT INTO metrics_outputs:
    dataset_id = <original UUID>
    param_set_id = <original UUID>
    ticker = <ticker>
    fiscal_year = <fiscal_year>
    output_metric_name = f'{interval}Y_FV_ECF'
    output_metric_value = <fv_ecf_value>
    created_at = now()


═════════════════════════════════════════════════════════════════════════════

DATA DEPENDENCY TREE (What depends on what?)
═════════════════════════════════════════════════════════════════════════════

FV_ECF_1Y, FV_ECF_3Y, FV_ECF_5Y, FV_ECF_10Y (Phase 10b - L2)
│
├─── Depends on: Calc KE (Phase 09 - Runtime Metrics) ✓ Ready
│    │
│    └─── Depends on:
│         ├─ Beta (Phase 07)
│         ├─ Rf_1Y (Phase 08)
│         └─ Equity Risk Premium (parameter)
│
├─── Depends on: Non Div ECF (Phase 06 - L1 Basic Metrics) ✗ MISSING
│    │
│    └─── Depends on:
│         ├─ Calc ECF (Phase 06) ✗ MISSING
│         │  └─ Depends on:
│         │     ├─ LAG_MC (lagged market cap)
│         │     ├─ C_MC (current market cap)
│         │     └─ Calc FY TSR (parameter-dependent)
│         │
│         └─ DIVIDENDS (fundamentals) ✓ Ready
│
├─── Depends on: DIVIDENDS (fundamentals) ✓ Ready
│
└─── Depends on: FRANKING (fundamentals) ✓ Ready


═════════════════════════════════════════════════════════════════════════════

PARAMETER RESOLUTION CHAIN
═════════════════════════════════════════════════════════════════════════════

POST /l2-fv-ecf/calculate?incl_franking=Yes
                          ├─────────────────────────────────┐
                                                              │
                                            ┌─────────────────▼────────────┐
                                            │ Query Param                  │
                                            │ incl_franking = "Yes"        │
                                            └──────────────────────────────┘

SELECT * FROM parameter_sets WHERE param_set_id = <UUID>
                                            ├─────────────────────────────────┐
                                                                               │
┌────────────────────────────────────────────┐◄──────────────────────────────┘
│ param_overrides = {                        │
│   "frank_tax_rate": 0.25,  (if exists)    │
│   "value_franking_cr": 0.80 (if exists)   │
│ }                                          │
└────────────────────────────────────────────┘

SELECT * FROM parameters 
  WHERE parameter_name IN ('frank_tax_rate', 'value_franking_cr')
                                            ├─────────────────────────────────┐
                                                                               │
┌────────────────────────────────────────────┐◄──────────────────────────────┘
│ default_value:                             │
│   frank_tax_rate = 0.30                    │
│   value_franking_cr = 0.75                 │
└────────────────────────────────────────────┘

Final Params (after applying overrides):
┌────────────────────────────────────────────┐
│ incl_franking = "Yes"   (from query param) │
│ frank_tax_rate = 0.25   (overridden)       │
│ value_franking_cr = 0.80 (overridden)      │
└────────────────────────────────────────────┘


═════════════════════════════════════════════════════════════════════════════

CRITICAL BLOCKER
═════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  Non Div ECF is NOT being calculated                                   │
│                                                                          │
│  Current state:                                                         │
│    metrics_outputs.output_metric_name = 'Non Div ECF'                  │
│    → Query returns empty result set                                     │
│    → df['non_div_ecf'] = None (all rows)                              │
│    → Results in NaN values throughout calculation                      │
│    → INSERT skips NaN values                                           │
│    → FV_ECF values are 0 or missing                                    │
│                                                                          │
│  Required to unblock:                                                   │
│    1. Implement Calc ECF calculation (Phase 06)                        │
│    2. Implement Non Div ECF = Calc ECF + DIVIDENDS                    │
│    3. Store in metrics_outputs                                          │
│    4. Then FV_ECF can produce real results                             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
