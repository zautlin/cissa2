# FV ECF Parameter Dependencies - Quick Summary

## The 3 Questions You Asked

### 1. What are ALL the parameters FV ECF needs?

| Parameter | Type | Source | Pre-Calc? |
|-----------|------|--------|-----------|
| `incl_franking` | String (Yes/No) | Endpoint query param | Yes |
| `frank_tax_rate` | Numeric (0-1) | parameters table | Yes |
| `value_franking_cr` | Numeric (0-1) | parameters table | Yes |

**Plus 4 data inputs:**
| Data Input | Source | Pre-Calc? |
|-----------|--------|-----------|
| DIVIDENDS | fundamentals table | No (input data) |
| FRANKING | fundamentals table | No (input data) |
| Non Div ECF | metrics_outputs | **NOT YET IMPLEMENTED** |
| Calc KE (lagged -1Y) | metrics_outputs + SQL JOIN | Yes (Phase 09) |

---

### 2. For each parameter, is it pre-calculated/parameter-dependent/constant/from fundamentals?

**Parameters (3):**
- `incl_franking` - Parameter-set dependent (endpoint query or overrides)
- `frank_tax_rate` - Parameter-set dependent (defaults to 0.30)
- `value_franking_cr` - Parameter-set dependent (defaults to 0.75)

**Fundamentals (2):**
- `DIVIDENDS` - From fundamentals (metric_name='DIVIDENDS')
- `FRANKING` - From fundamentals (metric_name='FRANKING')

**Pre-Calculated Metrics (2):**
- `Non Div ECF` - Should be from metrics_outputs (NOT YET CALCULATED)
- `Calc KE (lagged)` - From metrics_outputs via SQL LEFT JOIN (READY)

---

### 3. What about dependent metrics?

| Metric | Status | Source | Formula |
|--------|--------|--------|---------|
| DIVIDENDS | ✓ Ready | fundamentals | Raw data (input) |
| Non Div ECF | ✗ **NOT IMPLEMENTED** | Should be metrics_outputs | Calc ECF + DIVIDENDS |
| Calc Open KE (lagged) | ✓ Ready | metrics_outputs + SQL JOIN | KE from fiscal_year-1 |
| Calc ECF | ✗ Missing (needed for Non Div ECF) | Should be metrics_outputs | LAG_MC×(1+fytsr) - C_MC |

---

## Critical Finding: "Calc Incl" Explained

**"Calc Incl" in the Excel formula = `incl_franking` parameter**

NOT a pre-calculated metric. It's a simple YES/NO parameter that controls whether franking adjustment is applied:

```
IF incl_franking == "Yes" THEN:
  Apply franking adjustment: - (DIVIDENDS / (1 - frank_tax_rate)) × frank_tax_rate × value_franking_cr × FRANKING
ELSE:
  Skip franking adjustment
```

---

## The 3Y, 5Y, 10Y Formulas

They use **multiple years of data** (current + prior years):

```
For interval in [1, 3, 5, 10]:
  For each year in the past [0, -1, -2, ..., -(interval-1)]:
    Calculate TEMP for that year, shifted and raised to power
  Sum all TEMP values
  Shift final result by (interval - 1)
```

**Do we need PROFIT_AFTER_TAX_EX data?**
- **NO** - FV_ECF does NOT use PAT_EX or PROFIT_AFTER_TAX
- Those are for Phase 10a (Economic Profit) calculations only
- FV_ECF only uses: DIVIDENDS + Non Div ECF + Calc KE

---

## Can FV_ECF Be Pre-Calculated?

**Answer:** Partially.

**CAN pre-calculate:**
- ✓ Parameters (already in parameter_sets table)
- ✓ Fundamentals (already in fundamentals table)
- ✓ Lagged KE (via SQL JOIN)

**CANNOT pre-calculate (requires runtime):**
- ✗ Year shifts (.shift() operations - depends on ticker sequence)
- ✗ Power calculations (varies by interval/sequence/ke_open value)
- ✗ Final sums/shifts (requires sequential context per ticker)

**Current implementation:** Service fetches data + calculates at runtime (10-15 seconds)

---

## The Complete Input Matrix

```
FV_ECF Calculation Inputs:

Parameters (pre-calculated, parameter-set dependent):
  ├─ incl_franking (endpoint query param)
  ├─ frank_tax_rate (from parameters table, default 0.30)
  └─ value_franking_cr (from parameters table, default 0.75)

Fundamentals (from input data):
  ├─ DIVIDENDS (metric_name='DIVIDENDS', period_type='FISCAL')
  └─ FRANKING (metric_name='FRANKING', period_type='FISCAL')

Pre-Calculated Metrics (from metrics_outputs):
  ├─ Non Div ECF (NOT YET IMPLEMENTED) ← BLOCKER
  │   Formula: Calc ECF + DIVIDENDS
  └─ Calc KE (ready, from Phase 09)
      Lagged: KE from fiscal_year-1 via SQL LEFT JOIN

Computed at Runtime:
  ├─ ke_open = Calc KE from prior year (SQL JOIN)
  ├─ scale_by = IF(ke_open > 0, 1, 0)
  ├─ TEMP columns = multiple shifted calculations
  └─ FV_ECF_Y = SUM(all TEMP).shift(interval-1)
```

---

## Critical Blocker

**Non Div ECF is NOT being calculated**

Current fetch query (line 339-348 of fv_ecf_service.py):
```python
non_div_ecf_query = text("""
    SELECT ticker, fiscal_year, output_metric_value AS non_div_ecf
    FROM cissa.metrics_outputs
    WHERE dataset_id = :dataset_id
      AND output_metric_name = 'Non Div ECF'
""")
```

If not found:
```python
df['non_div_ecf'] = None  # Results in NaN values → skipped in INSERT
```

**Solution:** Implement Phase 06 (L1 Basic Metrics):
1. Calculate Calc ECF
2. Calculate Non Div ECF = Calc ECF + DIVIDENDS
3. Store in metrics_outputs
4. Then FV_ECF can run

---

## Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `/backend/app/services/fv_ecf_service.py` | Main FV_ECF implementation | 598 |
| `/backend/app/api/v1/endpoints/metrics.py` | API endpoint (POST /l2-fv-ecf/calculate) | 760-850 |
| `/backend/database/schema/schema.sql` | 13 baseline parameters | ~300-350 |
| `/example-calculations/src/executors/fvecf.py` | Legacy reference implementation | 63 |

---

## Parameter Resolution Flow

```
User calls:
  POST /api/v1/metrics/l2-fv-ecf/calculate?
    dataset_id=<UUID>&param_set_id=<UUID>&incl_franking=Yes

Parameter loading:
  1. incl_franking = "Yes" (from query param)
  2. Query parameters table: SELECT default_value WHERE parameter_name IN ('frank_tax_rate', 'value_franking_cr')
  3. Apply overrides: SELECT param_overrides FROM parameter_sets WHERE param_set_id = <UUID>
  4. Final params = defaults + overrides
```

Parameter fallbacks:
- If param_overrides is empty: use parameters table defaults
- If parameters table has no value: use hardcoded defaults (0.30, 0.75)

