# Parameter Mapping: Legacy Code → Database Parameters Table

## Current Understanding

1. **Data Architecture**: You're right — `fundamentals` table + other tables = input data for metric calculations
2. **Parameters**: Should come from `parameters` table in the database
3. **Question 3 clarification**: I was asking if you had a specific test dataset in mind, but it doesn't matter — we'll just use whatever data exists in fundamentals

---

## Parameter Mapping: Legacy Code to Database Schema

The legacy code uses these parameters (from `example-calculations/src/generate_l2_metrics.py`):

```python
inputs = {
    'identifier': identifier,                    # Dataset UUID
    'error_tolerance': 0.8,                      # Beta adjustment accuracy
    'approach_to_ke': "Floating",                # Cost of Equity approach
    'beta_rounding': 0.1,
    'risk_premium': 0.05,
    'userid': "anil.gautam",                     # Not needed in new system
    'country': "AUS",
    'currency': "AUD",
    'benchmark_return': 0.075,                   # Fixed benchmark return
    'incl_franking': 'Yes',                      # Include franking credits
    'frank_tax_rate': 0.3,
    'value_franking_cr': 0.75,
    'exchange': 'ASX',                           # Not needed — data specific
    'franking': 1,                               # Franking adjustment
    'bondIndex': "GACGB10"                       # Not needed — external data
}
```

### Mapping to Database Parameters Table

| Legacy Param | DB Parameter Name | Display Name | Current Default | New Default? |
|--------------|-------------------|--------------|-----------------|--------------|
| `approach_to_ke` | `cost_of_equity_approach` | Cost of Equity Approach | "Floating" | ✅ "Floating" |
| `incl_franking` | `include_franking_credits_tsr` | Include Franking Credits (TSR) | false | ❓ Should be true ("Yes") |
| `benchmark_return` | `fixed_benchmark_return_wealth_preservation` | Fixed Benchmark Return | 7.5 | ✅ 7.5 (or 0.075?) |
| `risk_premium` | `equity_risk_premium` | Equity Risk Premium | 5.0 | ❓ 0.05 or 5.0? |
| `frank_tax_rate` | `tax_rate_franking_credits` | Tax Rate (Franking Credits) | 30.0 | ✅ 30.0 |
| `value_franking_cr` | `value_of_franking_credits` | Value of Franking Credits | 75.0 | ✅ 75.0 |
| `beta_rounding` | `beta_rounding` | Beta Rounding | 0.1 | ✅ 0.1 |
| `error_tolerance` | `beta_relative_error_tolerance` | Beta Relative Error Tolerance | 40.0 | ❓ 0.8 or 40.0? |
| `country` | `country` | Country | "Australia" | ✅ "Australia" |
| `currency` | `currency_notation` | Currency Notation | "A$m" | ✅ "A$m" |
| NEW | `risk_free_rate_rounding` | Risk-Free Rate Rounding | 0.5 | ✅ 0.5 |

---

## Questions for Parameter Values

I need clarification on a few parameters that have unit or scale mismatches:

### 1. **Risk Premium** (`equity_risk_premium`)
   - **Legacy value:** `0.05` (5%)
   - **DB default:** `5.0` (5.0%)
   - **Question:** Is it stored as:
     - `0.05` (decimal, 5%)?
     - `5.0` (percentage, 5%)?
   - **My guess:** Probably `5.0` for readability

### 2. **Benchmark Return** (`fixed_benchmark_return_wealth_preservation`)
   - **Legacy value:** `0.075` (7.5%)
   - **DB default:** `7.5` (7.5%)
   - **Question:** Same as above — decimal or percentage?

### 3. **Beta Relative Error Tolerance** (`beta_relative_error_tolerance`)
   - **Legacy value:** `0.8` (relative error)
   - **DB default:** `40.0` (?)
   - **Question:** What does 40.0 represent? Is 0.8 correct?

### 4. **Include Franking Credits** (`include_franking_credits_tsr`)
   - **Legacy value:** `"Yes"` (string)
   - **DB default:** `false` (boolean)
   - **Question:** Should default be `true` or `false`?

### 5. **Franking Adjustment** (`franking`)
   - **Legacy value:** `1` (multiplier)
   - **DB param:** Not in parameters table yet
   - **Question:** Should we add this to parameters table with default `1.0`?

---

## Parameters NOT in Database Yet

These exist in legacy code but aren't in the DB parameters table:

| Legacy Param | Description | Default | Should Add? |
|--------------|-------------|---------|------------|
| `userid` | Audit user | "anil.gautam" | ❌ Not needed — use authenticated user |
| `exchange` | Exchange code | "ASX" | ❌ Data-specific, not configurable |
| `bondIndex` | Bond index code | "GACGB10" | ❌ External data — not configurable |
| `franking` | Franking multiplier | 1 | ❓ Yes — add as `franking_adjustment` |
| `convergence_horizon` | For projections | N/A in L2 | ❌ Only for optimization |

---

## Recommended Parameter Set

Based on legacy code and DB defaults, here's what I recommend we use:

```python
# From database parameters table
params = {
    # Cost of Equity
    'cost_of_equity_approach': 'Floating',           # Fixed or Floating
    'fixed_benchmark_return_wealth_preservation': 7.5,  # 7.5% benchmark
    'equity_risk_premium': 5.0,                      # 5% market risk premium
    
    # Franking Credits
    'include_franking_credits_tsr': True,            # Include franking
    'tax_rate_franking_credits': 30.0,               # 30% Australian tax rate
    'value_of_franking_credits': 75.0,               # 75% franking value
    'franking_adjustment': 1.0,                      # Franking multiplier (NEW)
    
    # Beta
    'beta_rounding': 0.1,                            # Round beta to 0.1
    'beta_relative_error_tolerance': 0.8,            # Error tolerance for beta (CONFIRM)
    
    # Risk-Free Rate
    'risk_free_rate_rounding': 0.5,                  # Round Rf to 0.5
    
    # Location
    'country': 'Australia',
    'currency_notation': 'A$m',
}
```

---

## Next Steps

Please answer these 5 questions:

1. ✅ **Risk Premium scale:** Is it stored as `0.05` (decimal) or `5.0` (percentage)?
2. ✅ **Benchmark Return scale:** Same — decimal or percentage?
3. ❓ **Beta Error Tolerance:** Is the DB default of `40.0` correct, or should it be `0.8`?
4. ✅ **Include Franking:** Should default be `true` or `false`?
5. ✅ **Add Franking Adjustment param:** Should we add `franking_adjustment` with default `1.0`?

Once you confirm, I'll:
1. Update parameters table if needed
2. Create the `EnhancedMetricsService` using these parameters
3. Build the API endpoint
4. Test end-to-end

