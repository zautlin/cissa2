# CODE FLOW DIAGRAMS: `approach_to_ke` Parameter Impact

---

## DIAGRAM 1: Overall Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       BETA CALCULATION SERVICE                             │
│                    (Lines 95-222 main orchestration)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
            ┌───────▼────────┐              ┌──────────▼──────────┐
            │ EARLY STAGES   │              │ PARAMETER LOADING  │
            │ (Lines 134-192)│              │ (Line 119)         │
            │                │              │                    │
            │ 1. Fetch TSR   │              │ Determine:         │
            │ 2. OLS (60mo)  │              │ - approach_to_ke   │
            │ 3. Transform   │              │ - beta_rounding    │
            │ 4. Annualize   │              │ - error_tolerance  │
            │ 5. Sectors     │              └────────────────────┘
            │ 6. Fallback    │                         │
            │ 7. Scaffold    │                         │
            └───────┬────────┘                         │
                    │                                   │
                    └───────────────────┬───────────────┘
                                        │
                        ┌───────────────▼──────────────┐
                        │ 4-TIER FALLBACK              │
                        │ (Lines 191-192)              │
                        │                              │
                        │ Creates spot_slope:          │
                        │ - Tier 1: individual β       │
                        │ - Tier 2: sector β           │
                        │ - Tier 3: global average     │
                        │ - Tier 4: 1.0 fallback       │
                        │                              │
                        │ Also calculates ticker_avg:  │
                        │ ticker_avg = mean(spot_slope)│
                        │ (used by FIXED approach)     │
                        └───────────────┬──────────────┘
                                        │
                        ┌───────────────▼──────────────┐
                        │ APPROACH SELECTION           │
                        │ (Line 196)                   │
                        │                              │
                        │ Call _apply_approach_to_ke() │
                        │ Pass: approach_to_ke param   │
                        └───────────────┬──────────────┘
                                        │
                ┌───────────────────────┼───────────────────────┐
                │                       │                       │
        ┌───────▼──────────┐  ┌────────▼────────┐  ┌──────────▼────────┐
        │ FIXED PATH       │  │ FLOATING PATH   │  │ OTHER PATHS       │
        │ (Lines 833-840)  │  │ (Lines 841-881) │  │ (treated as       │
        │                  │  │                  │  │  Floating by      │
        │ Select:          │  │ Select:          │  │  default)         │
        │ ticker_avg       │  │ floating_beta    │  │                   │
        │                  │  │ (cumulative)     │  │ Select:           │
        │ (same all years) │  │                  │  │ floating_beta     │
        │                  │  │ (different each  │  │                   │
        │ Apply rounding   │  │  year)           │  │ Apply rounding    │
        └────────┬─────────┘  │                  │  └──────────┬────────┘
                 │            │ Apply rounding   │             │
                 │            └─────────┬────────┘             │
                 │                      │                      │
                 └──────────────┬───────┴──────────────┬────────┘
                                │                      │
                        ┌───────▼──────────────────────▼────────┐
                        │ OUTPUT                                │
                        │ (Lines 887, 906-922)                  │
                        │                                       │
                        │ Returns: (ticker, fiscal_year, beta)  │
                        │ - FIXED: Same beta for all years      │
                        │ - Floating: Different beta per year   │
                        └──────────────────────────────────────┘
```

---

## DIAGRAM 2: FIXED Approach - Detailed Flow

```
START: Line 833 (if approach_to_ke == 'FIXED': → TRUE)
       │
       │ INPUT:
       │  - spot_betas DataFrame with columns:
       │    • ticker (e.g., "BHP AU Equity")
       │    • fiscal_year (e.g., 2020, 2021, ...)
       │    • spot_slope (e.g., 1.1, 1.2, 1.0, ...)
       │    • ticker_avg (e.g., 1.1 for ALL rows of BHP)
       │    • fallback_tier_used
       │
       └──→ Line 835-840: Apply FIXED logic
           │
           │ FOR EACH ROW IN spot_betas:
           │   ├─ ticker = "BHP AU Equity"
           │   ├─ fiscal_year = 2020
           │   └─ ticker_avg = 1.05 (from line 794)
           │
           │ CALCULATION:
           │ ┌────────────────────────────────────────┐
           │ │ Step 1: Get ticker_avg                │
           │ │  value = 1.05                         │
           │ │                                       │
           │ │ Step 2: Divide by beta_rounding       │
           │ │  temp = 1.05 / 0.1 = 10.5            │
           │ │                                       │
           │ │ Step 3: Round to nearest integer      │
           │ │  rounded = ROUND(10.5, 0) = 10 or 11 │
           │ │           (banker's rounding: 10)     │
           │ │                                       │
           │ │ Step 4: Multiply by beta_rounding     │
           │ │  final_beta = 10 * 0.1 = 1.0          │
           │ │  (or 11 * 0.1 = 1.1)                 │
           │ └────────────────────────────────────────┘
           │
           │ RESULT FOR THIS ROW:
           │  beta = 1.0 (or 1.1)
           │
           │ IMPORTANT: Same value for EVERY fiscal year!
           │
           └──→ ALL ROWS PROCESSED
               │
               ├─ BHP year 2000 → beta = 1.0
               ├─ BHP year 2001 → beta = 1.0
               ├─ BHP year 2020 → beta = 1.0
               ├─ BHP year 2021 → beta = 1.0
               ├─ BHP year 2023 → beta = 1.0  ← Same value!
               │
               └──→ Line 887: RETURN result
                   │
                   └─ DataFrame with columns:
                       • ticker: "BHP AU Equity"
                       • fiscal_year: 2000, 2001, ..., 2023
                       • beta: 1.0, 1.0, ..., 1.0  (ALL SAME)
                       • monthly_raw_slopes: [...]
```

---

## DIAGRAM 3: Floating Approach - Detailed Flow

```
START: Line 841 (else: → Floating approach)
       │
       │ INPUT: spot_betas DataFrame (same as FIXED)
       │
       │ Step 1: Sort by (ticker, fiscal_year) chronologically
       │ └─ Line 844: ensure inception year comes first
       │
       │ Step 2: Process each ticker separately
       └──→ Line 846: FOR EACH TICKER:
           │
           │ Example: BHP AU Equity (inception 2002)
           │
           │ Line 849: FOR EACH FISCAL YEAR (chronological):
           │ ┌─────────────────────────────────────────────┐
           │ │ YEAR 0 (2002):                              │
           │ │  Line 859: values_to_avg = iloc[0:1]        │
           │ │           = [spot_slope_2002]               │
           │ │           = [1.1]                           │
           │ │  Line 863: cum_avg = mean([1.1]) = 1.1      │
           │ │  Line 867: cumulative_means = [1.1]         │
           │ │                                             │
           │ │ YEAR 1 (2003):                              │
           │ │  Line 859: values_to_avg = iloc[0:2]        │
           │ │           = [spot_slope_2002, spot_slope_2003]
           │ │           = [1.1, 1.2]                      │
           │ │  Line 863: cum_avg = mean([1.1, 1.2])       │
           │ │           = 1.15                            │
           │ │  Line 867: cumulative_means = [1.1, 1.15]   │
           │ │                                             │
           │ │ YEAR 2 (2004):                              │
           │ │  Line 859: values_to_avg = iloc[0:3]        │
           │ │           = [1.1, 1.2, 1.0]                 │
           │ │  Line 863: cum_avg = mean([1.1, 1.2, 1.0])  │
           │ │           = 1.1                             │
           │ │  Line 867: cumulative_means = [1.1, 1.15,   │
           │ │            1.1]                             │
           │ │  ...                                        │
           │ │ YEAR 18 (2020):                             │
           │ │  Line 859: values_to_avg = iloc[0:19]       │
           │ │           = [all spot_slopes from 2002-2020]│
           │ │  Line 863: cum_avg = mean(...)              │
           │ │           ≈ 1.11                            │
           │ │  Line 867: cumulative_means = [..., 1.11]   │
           │ └─────────────────────────────────────────────┘
           │
           │ Line 869: Add to ticker_data:
           │  ticker_data['floating_beta'] = [1.1, 1.15,
           │                                  1.1, ..., 1.11]
           │
           │ Line 870: cumulative_betas.append(ticker_data)
           │
           └──→ NEXT TICKER (e.g., RIO AU Equity)
               (same process, different inception year)
               │
               └──→ Line 873: Combine all tickers
                   spot_betas = concatenate(cumulative_betas)
                   │
                   └──→ Line 876-881: Apply rounding
                       │
                       FOR EACH ROW:
                       ├─ BHP 2002: floating_beta=1.1
                       │   → ROUND(1.1/0.1, 0)*0.1 = 1.1
                       │
                       ├─ BHP 2003: floating_beta=1.15
                       │   → ROUND(1.15/0.1, 0)*0.1 = 1.1 or 1.2
                       │
                       ├─ BHP 2004: floating_beta=1.1
                       │   → ROUND(1.1/0.1, 0)*0.1 = 1.1
                       │
                       └─ BHP 2020: floating_beta=1.11
                           → ROUND(1.11/0.1, 0)*0.1 = 1.1
                       │
                       └──→ Line 887: RETURN result
                           │
                           └─ DataFrame with columns:
                               • ticker: "BHP AU Equity"
                               • fiscal_year: 2002, 2003, ..., 2020
                               • beta: 1.1, 1.15, 1.1, ..., 1.1
                               •        (DIFFERENT for each year!)
                               • monthly_raw_slopes: [...]
```

---

## DIAGRAM 4: Pre-Computation Architecture (RECOMMENDED)

```
Current Implementation:
┌──────────────────────────────────────────────────────────────┐
│ Line 196: Call _apply_approach_to_ke()                       │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ IF approach == 'FIXED':                                 │ │
│  │  - Use ticker_avg (pre-computed at line 794)            │ │
│  │  - Skip floating_beta calculation                       │ │
│  │  - Apply rounding                                       │ │
│  │  - TIME: ~10ms                                          │ │
│  └─────────────────────────────────────────────────────────┘ │
│  OR                                                          │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ ELSE (Floating):                                        │ │
│  │  - Calculate floating_beta (on-the-fly)                 │ │
│  │  - Apply rounding                                       │ │
│  │  - TIME: ~50ms (loop over all years/tickers)            │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘

Proposed Pre-Computation:
┌──────────────────────────────────────────────────────────────┐
│ NEW STEP: Pre-compute BOTH approaches (before decision)      │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ PHASE 1: ticker_avg (already exists from line 794)      │ │
│  │  spot_betas['beta_fixed_unrounded'] = ticker_avg        │ │
│  │  TIME: ~1ms (already computed)                          │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ PHASE 2: floating_beta (new pre-computation)            │ │
│  │  spot_betas['beta_floating_unrounded'] = cumulative_avg │ │
│  │  (same calculation as current Floating path)            │ │
│  │  TIME: ~100ms                                           │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ Total pre-computation: ~101ms                               │
│                                                              │
│ Line 196: Call _apply_approach_to_ke()                      │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ PHASE 3: Runtime Selection + Rounding                   │ │
│  │                                                         │ │
│  │  IF approach == 'FIXED':                                │ │
│  │   - Select: spot_betas['beta_fixed_unrounded']          │ │
│  │   - Round: ROUND(selected / rounding, 0) * rounding     │ │
│  │   - TIME: ~5ms (vector operation)                       │ │
│  │  ELSE (Floating):                                       │ │
│  │   - Select: spot_betas['beta_floating_unrounded']       │ │
│  │   - Round: ROUND(selected / rounding, 0) * rounding     │ │
│  │   - TIME: ~5ms (vector operation)                       │ │
│  │                                                         │ │
│  │ Total runtime selection: ~5ms                           │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ Total time: Pre-compute (~101ms) + Select (~5ms) = ~106ms   │
│ vs Current: ~10ms (FIXED) or ~50ms (Floating)               │
│ Overhead: ~50ms for both approaches always available        │
└──────────────────────────────────────────────────────────────┘

Benefits:
✅ Both approaches always calculated (for audit trail)
✅ Can easily compare FIXED vs Floating on same data
✅ Enables A/B testing without recalculation
✅ Separates concerns: computation vs selection
✅ Backwards compatible (output format unchanged)
```

---

## DIAGRAM 5: Sector Fallback Independence

```
Timeline of Execution:
┌────────────────────────────────────────────────────────────────────┐
│ STEP 1: Calculate Annual Slopes (Line 177)                        │
│         - OLS transformation: (slope * 2/3) + 1/3                 │
│         - Error filtering applied                                  │
│         - Rounding applied                                         │
│         RESULT: adjusted_slope per (ticker, fiscal_year)          │
│         NOTE: No approach_to_ke involved yet                       │
└────────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────────┐
│ STEP 2: Generate Sector Slopes (Line 182)                         │
│         - Sector average of adjusted_slope                         │
│         RESULT: sector_slope per (sector, fiscal_year)            │
│         NOTE: Still no approach_to_ke                              │
└────────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────────┐
│ STEP 3: Apply 4-Tier Fallback (Line 192)                          │
│         Code (Line 752-806):                                       │
│                                                                    │
│  Tier 1: Use adjusted_slope (if available)                         │
│  Tier 2: Use sector_slope (if adjusted_slope is NaN)               │
│  Tier 3: Use global average (if both are NaN)                      │
│  Tier 4: Use 1.0 (if all else NaN)                                │
│                                                                    │
│  RESULT: spot_slope (with fallback applied)                       │
│  ALSO:   ticker_avg = mean(spot_slope) for each ticker            │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │ CRITICAL: This is BEFORE approach selection!             │     │
│  │ Both approaches will use this SAME spot_slope            │     │
│  │ Sector fallback is independent of approach              │     │
│  └──────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────────┘
                              ↓
                  ┌───────────┴───────────┐
                  │                       │
        ┌─────────▼──────────┐  ┌────────▼────────────┐
        │ FIXED APPROACH     │  │ FLOATING APPROACH   │
        │ (Line 833-840)     │  │ (Line 841-881)      │
        │                    │  │                     │
        │ SELECT:            │  │ SELECT:             │
        │ ticker_avg         │  │ cumulative_avg      │
        │ (from spot_slope)  │  │ (from spot_slope)   │
        │                    │  │                     │
        │ BOTH USE SAME      │  │ BOTH USE SAME       │
        │ spot_slope that    │  │ spot_slope that     │
        │ includes:          │  │ includes:           │
        │ - Tier 1: indiv.   │  │ - Tier 1: indiv.    │
        │ - Tier 2: sector   │  │ - Tier 2: sector    │
        │ - Tier 3: global   │  │ - Tier 3: global    │
        │ - Tier 4: 1.0      │  │ - Tier 4: 1.0       │
        └────────────────────┘  └─────────────────────┘
                  │                       │
                  └───────────┬───────────┘
                              │
                      ┌───────▼────────┐
                      │ CONCLUSION:    │
                      │ Sector fallback│
                      │ is completely  │
                      │ independent of │
                      │ approach_to_ke │
                      └────────────────┘

Proof:
✅ Sector calculation (Step 2) happens BEFORE approach decision
✅ Fallback logic (Step 3) happens BEFORE approach decision
✅ Both approaches use IDENTICAL spot_slope values
✅ Approach only determines HOW to aggregate (all years vs cumulative)
✅ If a sector value was used as fallback, it's used by BOTH approaches
```

---

## DIAGRAM 6: Rounding: When and Why

```
Question: Should rounding happen BEFORE or AFTER approach selection?

WRONG: Rounding BEFORE approach selection
┌──────────────────────────────────────────────────────────────────┐
│ 1. Pre-compute and round both approaches:                        │
│    beta_fixed = ROUND(ticker_avg / 0.1, 0) * 0.1 = 1.0           │
│    beta_floating[Y] = ROUND(cum_avg[Y] / 0.1, 0) * 0.1           │
│                                                                  │
│ 2. Then select based on approach:                                │
│    if approach == FIXED: use beta_fixed (1.0)                    │
│    else: use beta_floating (may be 1.1 or 1.2)                   │
│                                                                  │
│ PROBLEM:                                                         │
│  - Different rounding errors accumulate differently              │
│  - Cumulative average gets rounded repeatedly                    │
│  - Introduces bias in floating approach                          │
└──────────────────────────────────────────────────────────────────┘

CORRECT: Rounding AFTER approach selection (CURRENT)
┌──────────────────────────────────────────────────────────────────┐
│ 1. Calculate unrounded values:                                   │
│    beta_fixed_unrounded = ticker_avg = 1.05                      │
│    beta_floating_unrounded[Y] = cum_avg[Y] = 1.15               │
│                                                                  │
│ 2. Select based on approach:                                     │
│    if approach == FIXED:                                         │
│      selected = 1.05 (unrounded)                                 │
│    else:                                                         │
│      selected = 1.15 (unrounded)                                 │
│                                                                  │
│ 3. Apply rounding to FINAL value:                                │
│    beta = ROUND(selected / 0.1, 0) * 0.1                         │
│    FIXED: ROUND(1.05 / 0.1, 0) * 0.1 = 1.0                      │
│    Floating: ROUND(1.15 / 0.1, 0) * 0.1 = 1.1 or 1.2            │
│                                                                  │
│ CORRECT BECAUSE:                                                │
│  ✅ Rounding is applied consistently to final value              │
│  ✅ No intermediate rounding errors accumulate                   │
│  ✅ Same rounding logic for both approaches                      │
│  ✅ Rounding parameter is a true knob (can change scale)         │
└──────────────────────────────────────────────────────────────────┘

Implementation:
Line 835-836 (FIXED):
  spot_betas['beta'] = np.round(x['ticker_avg'] / beta_rounding, 0) * beta_rounding

Line 876-877 (Floating):
  spot_betas['beta'] = np.round(x['floating_beta'] / beta_rounding, 0) * beta_rounding

Both follow the SAME rounding pattern:
  ROUND(value / scaling_factor, 0) * scaling_factor

This is known as "precision rounding" and is the standard approach
for financial calculations.
```

---

## DIAGRAM 7: Parameter Flow Through System

```
┌──────────────────────────────────────────────────────────────────┐
│ DATABASE: cissa.parameters and cissa.parameter_sets             │
│                                                                  │
│ Parameters:                                                      │
│  - cost_of_equity_approach: 'FIXED' or 'Floating'              │
│  - beta_rounding: 0.1 (or other value)                          │
│  - beta_relative_error_tolerance: 20% (or other)               │
└──────────────────────────────────────────────────────────────────┘
                              ↓
                    (Line 119-122)
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ BetaCalculationService.calculate_beta_async()                   │
│                                                                  │
│  params = await _load_parameters_from_db(param_set_id)          │
│  params['cost_of_equity_approach'] → 'FIXED'                    │
│  params['beta_rounding'] → 0.1                                  │
│  params['beta_relative_error_tolerance'] → 0.2                  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
                ┌─────────────┴────────────┐
                │                          │
        ┌───────▼──────────┐      ┌───────▼──────────┐
        │ Line 169-173:    │      │ Line 196-200:    │
        │ _transform_slopes│      │ _apply_approach_ │
        │                  │      │ to_ke            │
        │ Uses:            │      │                  │
        │ - error_tol = 0.2│      │ Uses:            │
        │ - rounding = 0.1 │      │ - approach =     │
        │                  │      │   'FIXED'        │
        │ Produces:        │      │ - rounding = 0.1 │
        │ adjusted_slope   │      │                  │
        │ (filtered &      │      │ Produces:        │
        │ rounded)         │      │ final beta       │
        └──────────────────┘      │ (rounded again)  │
                                  └──────────────────┘

Important Note:
β is rounded TWICE in current implementation:
  1. Line 641: Rounding during transform_slopes (error filtering)
  2. Line 836: Rounding during apply_approach_to_ke

This is acceptable because:
  - First rounding filters out high-error estimates
  - Second rounding finalizes based on approach selection
  - Both use the same scaling factor
```

---

## DIAGRAM 8: Decision Matrix

```
┌────────────────────────────────────────────────────────────────┐
│ PARAMETER: approach_to_ke                                      │
│                                                                │
│  Value: 'FIXED'                                                │
│  ─────────────────────────────────────────────────────────────│
│  Path: Line 833 (if True)                                      │
│  Method: Line 835-840                                          │
│  Input: ticker_avg                                             │
│  Output: Same beta for ALL fiscal years                        │
│  Example: BHP 2000-2023 all get 1.0                            │
│  Use Case: Conservative, smooth KE                             │
│                                                                │
│  Value: 'Floating' (or any non-'FIXED' value)                 │
│  ─────────────────────────────────────────────────────────────│
│  Path: Line 841 (else clause)                                  │
│  Method: Line 841-881                                          │
│  Input: floating_beta (cumulative average)                     │
│  Output: Different beta for each fiscal year                   │
│  Example: BHP 2002=1.1, 2003=1.15, 2004=1.1, ..., 2020=1.11  │
│  Use Case: Responsive, evolving KE                             │
│                                                                │
│  Value: (any other string)                                     │
│  ─────────────────────────────────────────────────────────────│
│  Path: Line 841 (else clause, treated as Floating)            │
│  Method: Same as Floating                                      │
│  Note: Default behavior is Floating for safety                 │
└────────────────────────────────────────────────────────────────┘

Critical Line: 827-828 (Comparison)
┌────────────────────────────────────────────────────────────────┐
│ self.logger.info(f"DEBUG: approach_to_ke = '{approach_to_ke}'")│
│ self.logger.info(f"DEBUG: comparison = {approach_to_ke =='FIXED'}
│                                                                │
│ This is a STRING comparison (case-sensitive)                   │
│ 'FIXED' ≠ 'fixed' (would treat as Floating!)                   │
│ 'FIXED' ≠ 'Fixed' (would treat as Floating!)                   │
│                                                                │
│ Database values MUST be exactly: 'FIXED'                       │
└────────────────────────────────────────────────────────────────┘
```

---

## DIAGRAM 9: Impact on Downstream Services

```
Phase 07: Beta Calculation
┌──────────────────────────────────────────────────────────────┐
│ Output: Calc Beta (with approach_to_ke applied)              │
│ - FIXED: Stable beta per ticker                             │
│ - Floating: Evolving beta per (ticker, year)                │
└──────────────────────────────────────────────────────────────┘
                              ↓
        (stored in metrics_outputs table)
                              ↓
Phase 08: Risk-Free Rate Calculation
┌──────────────────────────────────────────────────────────────┐
│ Uses: same approach_to_ke parameter                          │
│                                                              │
│ If 'FIXED':                                                  │
│  rf = benchmark - risk_premium (constant)                    │
│  Example: rf = 0.075 - 0.05 = 0.025                         │
│                                                              │
│ If 'Floating':                                               │
│  rf = rf_1y (from market data, evolving)                    │
│  Example: 2002: 0.03, 2003: 0.025, 2004: 0.035             │
└──────────────────────────────────────────────────────────────┘
                              ↓
        (stored in metrics_outputs table)
                              ↓
Phase 09: Cost of Equity Calculation
┌──────────────────────────────────────────────────────────────┐
│ Inputs: Beta (Phase 07), Rf (Phase 08)                       │
│                                                              │
│ Formula: KE = Rf + Beta × RiskPremium                       │
│                                                              │
│ If approach = 'FIXED':                                       │
│  KE = 0.025 + 1.0 × 0.05 = 0.075 (constant)                │
│  Same KE for all years!                                      │
│                                                              │
│ If approach = 'Floating':                                    │
│  2002: KE = 0.03 + 1.1 × 0.05 = 0.085 (evolving)           │
│  2003: KE = 0.025 + 1.15 × 0.05 = 0.0825                   │
│  2004: KE = 0.035 + 1.1 × 0.05 = 0.090                     │
└──────────────────────────────────────────────────────────────┘

Impact Summary:
FIXED approach:
  ✅ Stable KE trajectory (easier to model)
  ✅ Less year-to-year volatility
  ❌ Ignores market evolution
  ❌ May not reflect current risk profile

Floating approach:
  ✅ Responsive to market changes
  ✅ Reflects evolving risk (cumulative basis)
  ❌ More volatile KE values
  ❌ More complex interpretation
```

---

## DIAGRAM 10: Summary Comparison Table

```
┌─────────────────────────────────────────────────────────────────────┐
│                 FIXED vs FLOATING Approach                         │
├──────────────────────────┬──────────────────┬──────────────────────┤
│ Aspect                   │ FIXED            │ Floating             │
├──────────────────────────┼──────────────────┼──────────────────────┤
│ Beta Value Source        │ ticker_avg       │ floating_beta        │
│                          │ (all years)      │ (cumulative)         │
├──────────────────────────┼──────────────────┼──────────────────────┤
│ Pre-computation Line     │ 794              │ 846-873 (on-the-fly) │
│                          │ (done earlier)   │ (in method)          │
├──────────────────────────┼──────────────────┼──────────────────────┤
│ Selection Line           │ 833              │ 841                  │
├──────────────────────────┼──────────────────┼──────────────────────┤
│ Rounding Line            │ 836              │ 877                  │
├──────────────────────────┼──────────────────┼──────────────────────┤
│ Beta Values per Ticker   │ 1 (same all      │ N (one per year)     │
│                          │  fiscal years)   │                      │
├──────────────────────────┼──────────────────┼──────────────────────┤
│ Example (BHP):           │                  │                      │
│  2000-2010              │ 1.0              │ 1.1→1.12→1.10→...   │
│  2011-2020              │ 1.0              │ ...→1.09→1.08→1.10  │
├──────────────────────────┼──────────────────┼──────────────────────┤
│ Rounding Impact          │ Applied once     │ Applied per year     │
│                          │ per ticker       │ per ticker           │
├──────────────────────────┼──────────────────┼──────────────────────┤
│ Sector Fallback Impact   │ Independent      │ Independent          │
│                          │ (applied before) │ (applied before)     │
├──────────────────────────┼──────────────────┼──────────────────────┤
│ KE Stability             │ Very Stable      │ More Volatile        │
│                          │ (by design)      │ (evolving)           │
├──────────────────────────┼──────────────────┼──────────────────────┤
│ Computation Cost         │ ~10ms            │ ~50ms (+ pre-compute │
│ (Phase 07)               │                  │ would be ~100ms)     │
├──────────────────────────┼──────────────────┼──────────────────────┤
│ Default Behavior         │ Only if          │ Used if not 'FIXED'  │
│ (if param not set)       │ explicitly set   │ (safe default)       │
└──────────────────────────┴──────────────────┴──────────────────────┘
```

