# Complete Legacy Metrics Inventory

**Purpose:** Comprehensive list of ALL metrics calculated in the legacy system to align backend implementation

---

## TIER 1: L1 BASIC METRICS (15 metrics)

### Location: `example-calculations/src/executors/metrics.py` lines 9-44

All L1 metrics are calculated per ticker per year from fundamental data.

| # | Metric | Formula | Input Columns | Type | Notes |
|----|--------|---------|---------------|------|-------|
| 1 | **C_MC** | shrouts × price | shrouts, price | Basic | Market capitalization |
| 2 | **C_ASSETS** | assets - cash | assets, cash | Basic | Calculated assets |
| 3 | **OA** | C_ASSETS - fixedassets - goodwill | fixedassets, goodwill | Basic | Operating assets |
| 4 | **OP_COST** | revenue - opincome | revenue, opincome | Basic | Operating costs |
| 5 | **NON_OP_COST** | opincome - pbt | pbt | Basic | Non-operating costs |
| 6 | **TAX_COST** | pbt - patxo | patxo | Basic | Tax costs |
| 7 | **XO_COST** | patxo - pat | pat | Basic | Extraordinary costs |
| 8 | **ECF** | Conditional (see below) | LAG_MC, C_MC | Temporal | Economic cash flow - **TEMPORAL** |
| 9 | **NON_DIV_ECF** | ECF + dividend | ECF, dividend | Temporal | Non-dividend ECF - **TEMPORAL** |
| 10 | **EE** | Cumulative (see below) | eqiity, mi, pat, ECF | Temporal | Economic equity - **TEMPORAL** |
| 11 | **FY_TSR** | Conditional formula (see below) | LAG_MC, C_MC, ECF, dividend | Temporal | Total shareholder return - **TEMPORAL** |
| 12 | **FY_TSR_PREL** | FY_TSR + 1 | FY_TSR | Temporal | TSR preliminary - **TEMPORAL** |

**Note:** Only 12 of 15 are in backend. ECF, NON_DIV_ECF, EE, FY_TSR_PREL are MISSING.

### L1 Temporal Metrics Details

#### ECF (Economic Cash Flow)
```
IF INCEPTION_IND == 1:
  ECF = LAG_MC * (1 + fytsr/100) - C_MC
ELSE:
  ECF = NaN
```
**Requires:** Previous year market cap (LAG_MC), fytsr from fundamentals
**Status:** ❌ NOT in backend (needs window function)

#### NON_DIV_ECF (Non-Dividend Economic Cash Flow)
```
NON_DIV_ECF = ECF + dividend
```
**Depends on:** ECF
**Status:** ❌ NOT in backend (depends on ECF)

#### EE (Economic Equity)
```
IF INCEPTION_IND == 0:
  EE = eqiity - mi
ELIF INCEPTION_IND == 1:
  EE = pat - ECF
THEN: cumsum(EE) by ticker
```
**Depends on:** ECF, inception_year logic
**Status:** ❌ NOT in backend (complex cumulative logic)

#### FY_TSR (Fiscal Year Total Shareholder Return)
```
IF LAG_MC > 0 AND INCEPTION_IND == 1:
  IF incl_franking == "Yes":
    div = dividend / (1 - frank_tax_rate)
    change_in_cap = C_MC - LAG_MC + ECF - div
    adjusted_change = change_in_cap * frank_tax_rate * value_franking_cr
    FY_TSR = adjusted_change / LAG_MC
  ELSE:
    change_in_cap = C_MC - LAG_MC + ECF
    FY_TSR = change_in_cap / LAG_MC
ELSE:
  FY_TSR = NaN
```
**Requires:** LAG_MC, franking parameters (incl_franking, frank_tax_rate, value_franking_cr)
**Status:** ❌ NOT in backend (temporal + complex logic)

#### FY_TSR_PREL (FY TSR Preliminary)
```
IF INCEPTION_IND == 1:
  FY_TSR_PREL = FY_TSR + 1
ELSE:
  FY_TSR_PREL = NaN
```
**Depends on:** FY_TSR
**Status:** ❌ NOT in backend

---

## TIER 2: AGGREGATED RATIO METRICS (14 metrics × 4 intervals = 56 total columns)

### Location: `example-calculations/src/engine/aggregators.py` lines 149-183

**Key Point:** These are NOT L1 metrics in legacy system. They are aggregated metrics calculated AFTER L1 and at FOUR intervals: 1Y, 3Y, 5Y, 10Y.

Each metric gets 4 versions: `{metric_name}_1_Y`, `{metric_name}_3_Y`, `{metric_name}_5_Y`, `{metric_name}_10_Y`

| # | Metric | Formula | Intervals | Notes |
|----|--------|---------|-----------|-------|
| 1 | **mb_ratio** | c_mc / ee | 1,3,5,10Y | Market-to-book ratio |
| 2 | **ep_pct** | ep / ee_open | 1,3,5,10Y | Economic profit % |
| 3 | **roee** | pat_ex / ee_open | 1,3,5,10Y | Return on equity equity |
| 4 | **roa** | pat_ex / c_assets | 1,3,5,10Y | Return on assets |
| 5 | **profit_margin** | pat_ex / revenue | 1,3,5,10Y | Net profit margin |
| 6 | **op_cost_margin** | op_cost / revenue | 1,3,5,10Y | Operating cost margin |
| 7 | **non_op_cost_margin** | op_cost / non_op_cost | 1,3,5,10Y | **BUG:** Should be `non_op_cost / revenue` |
| 8 | **ef_tax_rate** | tax_cost / (pat + xo_cost) | 1,3,5,10Y | Effective tax rate |
| 9 | **xo_cost_margin** | xo_cost / revenue | 1,3,5,10Y | Extraordinary cost margin |
| 10 | **fa_intensity** | xo_cost / fixedassets_open | 1,3,5,10Y | **BUG:** Should be `fixedassets_open / revenue` |
| 11 | **gw_intensity** | goodwill_open / revenue | 1,3,5,10Y | Goodwill intensity |
| 12 | **oa_intensity** | oa_open / revenue | 1,3,5,10Y | Operating assets intensity |
| 13 | **assets_intensity** | c_assets_open / revenue | 1,3,5,10Y | Assets intensity |
| 14 | **econ_eq_mult** | c_assets_open / ee_open | 1,3,5,10Y | Economic equity multiplier |

### Aggregated Metrics Processing
- **Calculated on:** Rolling windows (mean, shift, product)
- **Source columns:** Defined in `src/config/parameters.py`
  - `COL_ROLLING_MEANS` - columns to calculate rolling mean
  - `COL_ROLLING_SHIFTS` - columns to shift (lagged values)
  - `COL_ROLLING_PROD` - columns for rolling product
- **Intervals:** 1Y, 3Y, 5Y, 10Y (backward-looking rolling windows)

### Bugs Found in Legacy Code
1. **Line 162-163:** `non_op_cost_margin = op_cost / non_op_cost`
   - ❌ WRONG: Dividing op_cost by itself
   - ✅ SHOULD BE: `op_cost / revenue` (not by non_op_cost)

2. **Line 169-170:** `fa_intensity = xo_cost / fixedassets_open`
   - ❌ WRONG: Using xo_cost as numerator
   - ✅ SHOULD BE: `fixedassets_open / revenue` (standard fixed asset intensity)

---

## TIER 3: L2 DERIVED METRICS (6 metrics)

### Location: `example-calculations/src/generate_l2_metrics.py` (calls L2MetricsService internally)

**Key Point:** L2 metrics are derived from L1 metrics, NOT calculated independently.

| # | Metric | Dependencies | Formula | Status |
|----|--------|--------------|---------|--------|
| 1 | **ROA_BASE** | PAT, Calc Assets | PAT / Calc Assets | ✅ In backend as "ROA" |
| 2 | **ASSET_EFFICIENCY** | C_ASSETS, Revenue | C_ASSETS / Revenue | ✅ In backend |
| 3 | **OPERATING_LEVERAGE** | OP_COST, Revenue | OP_COST / Revenue | ✅ In backend |
| 4 | **TAX_BURDEN** | TAX_COST, PAT | TAX_COST / PAT | ✅ In backend |
| 5 | **CAPITAL_INTENSITY** | Fixed Assets, Revenue | Fixed Assets / Revenue | ✅ In backend |
| 6 | **DIVIDEND_PAYOUT_RATIO** | Dividend, PAT | Dividend / PAT | ✅ In backend |

**Status:** ✅ All 6 implemented in backend (newly renamed without L2_ prefix in Phase 05)

---

## TIER 4: BETA CALCULATION (1 metric)

### Location: `example-calculations/src/executors/beta.py`

Calculates Beta using rolling OLS regression on monthly returns data.

| # | Metric | Formula | Type | Inputs |
|----|--------|---------|------|--------|
| 1 | **BETA** | Rolling OLS slope with fallback logic | Statistical | monthly returns (re, rm) |

**Process:**
1. Calculate rolling OLS regression (60-month window)
2. Adjust slope: `(slope × 2/3) + 1/3`
3. Round to nearest beta_rounding (default 0.1)
4. **4-Tier Fallback Logic:**
   - Tier 1: Ticker-specific adjusted_slope (if passes error tolerance)
   - Tier 2: Sector average (if Tier 1 fails)
   - Tier 3: Ticker average (if Tier 2 fails)
   - Tier 4: Default/NaN (if all tiers fail)

**Inputs from config:**
- `error_tolerance`: 0.8 (relative std error threshold)
- `beta_rounding`: 0.1 (rounding precision)

**Status:** ❌ NOT implemented in backend

---

## TIER 5: RISK-FREE RATE & MARKET RETURNS (2 metrics)

### Location: `example-calculations/src/executors/rates.py`

| # | Metric | Formula | Type | Inputs |
|----|--------|---------|------|--------|
| 1 | **RF (Risk-Free Rate)** | FIXED: benchmark - risk_premium OR FLOATING: from monthly rates | Lookup/Calculated | benchmark, risk_premium, monthly_rf |
| 2 | **RM (Market Return)** | Calculated from market index data | Lookup/Calculated | market index data |

**Process:**
1. Load monthly risk-free rates
2. **Approach to KE:**
   - FIXED: `RF = benchmark - risk_premium`
   - FLOATING: `RF = 12-month geometric mean of monthly rates, rounded`
3. Calculate excess returns: `RE_RF = RE - RF`
4. Annual rates derived from monthly rates aligned to fiscal year

**Inputs from config:**
- `approach_to_ke`: "FIXED" or "Floating"
- `benchmark`: 0.075 (7.5% for FIXED approach)
- `risk_premium`: 0.05 (5.0%)
- `beta_rounding`: 0.1

**Status:** ❌ NOT implemented in backend

---

## TIER 6: INTERMEDIARY CALCULATED METRICS

### Location: `example-calculations/src/engine/aggregators.py` lines 84-134

These are calculated during aggregation phase to support ratio calculations. NOT stored as output metrics.

| # | Metric | Calculation | Intervals | Purpose |
|----|--------|-------------|-----------|---------|
| 1 | **TER** | Geometric mean of TRTE values | 1,3,5,10Y | Total equity return |
| 2 | **TER_KE** | TER - KE | 1,3,5,10Y | Excess equity return |
| 3 | **RM** | Geometric mean of return margins | 1,3,5,10Y | Market returns |
| 4 | **RA_MM** | Market risk premium adjusted return | 1,3,5,10Y | Risk-adjusted return |
| 5 | **WP** | Wealth proxy | 1,3,5,10Y | Investor wealth proxy |
| 6 | **WC_TERA** | Wealth created with adjustment | 1,3,5,10Y | Wealth created (adjusted) |
| 7 | **WC** | Wealth created | 1,3,5,10Y | Wealth created |
| 8 | **TERA** | Total excess return adjusted | 1,3,5,10Y | Excess return adjustment |
| 9 | **rev_delta** | Revenue growth measure | 1,3,5,10Y | Revenue change |
| 10 | **ee_delta** | Equity growth measure | 1,3,5,10Y | Economic equity change |

**Note:** These are intermediate calculations used only during aggregation, not stored as final outputs.

---

## TIER 7: SECTOR AGGREGATIONS (Multiple metrics)

### Location: `example-calculations/src/generate_sector_metrics.py`

Groups metrics by sector and year, calculating:
- Average metrics by sector
- Sector benchmarks
- Sector returns

**Status:** ❌ NOT implemented in backend

---

## SUMMARY: Implementation Status

| Tier | Category | Count | Implemented | Missing |
|------|----------|-------|-------------|---------|
| L1 | Basic Metrics | 12 | ✅ 12 | ❌ 0 (aggregated metrics counted separately) |
| L1 | Temporal Metrics | 5 | ❌ 0 | ❌ 5 |
| L2 | Derived Metrics | 6 | ✅ 6 | ❌ 0 |
| L3 | Aggregated Ratios | 14×4 | ❌ 0 | ❌ 56 columns |
| L3 | Beta | 1 | ❌ 0 | ❌ 1 |
| L3 | Rates (RF/RM) | 2 | ❌ 0 | ❌ 2 |
| L3 | Sector Metrics | ? | ❌ 0 | ❌ ? |
| | **TOTAL** | **~40+** | **✅ 18** | **❌ 66+** |

---

## Questions for Alignment

1. **Temporal Metrics (ECF, EE, FY_TSR, FY_TSR_PREL):**
   - Are these required in backend?
   - Should they be implemented via SQL window functions or Python service?

2. **Aggregated Ratio Metrics (14×4 = 56 columns):**
   - Should backend calculate interval-based versions (1Y, 3Y, 5Y, 10Y)?
   - Or just single-year versions?

3. **Beta Calculation:**
   - Needed in backend?
   - How should 4-tier fallback logic be handled?

4. **Rates (RF/RM):**
   - Needed in backend?
   - Is there rate data source defined?

5. **Sector Aggregations:**
   - Needed in backend?
   - What metrics by sector?

6. **Bugs in Legacy:**
   - Should these be fixed?
   - Or replicated as-is in backend for backward compatibility?

