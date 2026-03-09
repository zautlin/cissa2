# PARAMETER_MAPPING.md — Parameter Configuration for FY_TSR Calculation

**Phase:** 06 — L1 Metrics Alignment  
**Document Version:** 1.0  
**Last Updated:** 2026-03-09  
**Author:** Phase Execution  

---

## Overview

This document defines the parameter structure required for L1 metric calculations, particularly FY_TSR which depends on three franking-related parameters. The parameter system uses a two-table design: `parameters` (baseline definitions) and `parameter_sets` (named bundles with optional overrides).

---

## Table 1: `parameters` Table

### Schema Definition

```sql
CREATE TABLE parameters (
  parameter_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parameter_name TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  value_type TEXT,
  default_value TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Purpose

- **Master list** of all tunable parameters for metric calculations
- **Baseline defaults** applied when parameter_sets uses empty `param_overrides` (e.g., "base_case")
- **13 baseline parameters** defined during schema initialization

### Current Parameters (13 total)

| parameter_name | display_name | value_type | default_value | Purpose |
|---|---|---|---|---|
| country | Country | TEXT | Australia | Geographic context for calculations |
| currency_notation | Currency Notation | TEXT | A$m | Display format for currency amounts |
| cost_of_equity_approach | Cost of Equity Approach | TEXT | Floating | Method for calculating cost of equity |
| **include_franking_credits_tsr** | **Include Franking Credits (TSR)** | **BOOLEAN** | **false** | **Whether to include franking credits in FY_TSR** |
| fixed_benchmark_return_wealth_preservation | Fixed Benchmark Return (Wealth Preservation) | NUMERIC | 7.5 | Baseline return assumption |
| equity_risk_premium | Equity Risk Premium | NUMERIC | 5.0 | Risk premium component |
| **tax_rate_franking_credits** | **Tax Rate (Franking Credits)** | **NUMERIC** | **30.0** | **Australian tax rate (30% = 0.30)** |
| **value_of_franking_credits** | **Value of Franking Credits** | **NUMERIC** | **75.0** | **Valuation of franking credits (75% = 0.75)** |
| risk_free_rate_rounding | Risk-Free Rate Rounding | NUMERIC | 0.5 | Rounding increment |
| beta_rounding | Beta Rounding | NUMERIC | 0.1 | Beta rounding precision |
| last_calendar_year | Last Calendar Year | NUMERIC | 2019 | Reference year for calculations |
| beta_relative_error_tolerance | Beta Relative Error Tolerance | NUMERIC | 40.0 | Tolerance threshold for beta calculations |
| terminal_year | Terminal Year | NUMERIC | 60 | Convergence horizon for projections |

### Key Findings: Franking Parameters

**✅ Already Defined in Database:**

1. **include_franking_credits_tsr** (parameter_name)
   - Display: "Include Franking Credits (TSR)"
   - Type: BOOLEAN
   - Default: 'false'
   - **Mapping to legacy code:** `incl_franking`
   - **Legacy values:** "Yes" or "No" (string)
   - **Database default:** 'false' (BOOLEAN)
   - **Note:** Legacy code expects string "Yes"/"No", but parameter stored as BOOLEAN. Conversion needed.

2. **tax_rate_franking_credits** (parameter_name)
   - Display: "Tax Rate (Franking Credits)"
   - Type: NUMERIC
   - Default: '30.0'
   - **Mapping to legacy code:** `frank_tax_rate`
   - **Legacy usage:** `1 - frank_tax_rate` → expects decimal (0.30)
   - **Database value:** '30.0' (stored as NUMERIC, represents percentage)
   - **Conversion:** 30.0 → 0.30 (divide by 100)

3. **value_of_franking_credits** (parameter_name)
   - Display: "Value of Franking Credits"
   - Type: NUMERIC
   - Default: '75.0'
   - **Mapping to legacy code:** `value_franking_cr`
   - **Legacy usage:** Used directly in calculation: `adjusted_change * frank_tax_rate * value_franking_cr`
   - **Database value:** '75.0' (stored as NUMERIC, represents percentage)
   - **Conversion:** 75.0 → 0.75 (divide by 100)

---

## Table 2: `parameter_sets` Table

### Schema Definition

```sql
CREATE TABLE parameter_sets (
  param_set_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  param_set_name TEXT NOT NULL UNIQUE,
  description TEXT,
  is_default BOOLEAN NOT NULL DEFAULT false,
  is_active BOOLEAN NOT NULL DEFAULT true,
  param_overrides JSONB NOT NULL DEFAULT '{}',
  created_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Purpose

- **Named bundles** of parameter configurations for reproducibility
- **Optional overrides** for specific scenarios (conservative valuation, aggressive, etc.)
- **One "base_case"** marked `is_default=true` uses empty `param_overrides` (all 13 baseline defaults)
- **Multiple alternative** parameter sets can exist with different overrides

### Current Parameter Sets

| param_set_name | is_default | is_active | param_overrides | purpose |
|---|---|---|---|---|
| base_case | true | true | {} | Default scenario; uses all 13 baseline parameters |

### Current State Verification

✅ **"base_case" parameter set exists**
- is_default: **true** ✅
- is_active: true ✅
- param_overrides: {} (empty) → uses all baseline defaults ✅
- Created by: admin

---

## JSONB param_overrides Structure

The `param_overrides` column stores JSONB structure for custom parameter scenarios. Unlike "base_case" which uses baseline defaults (empty JSON), alternative parameter sets override specific parameters.

### Structure

```json
{
  "parameter_name": value,
  "parameter_name": value,
  ...
}
```

### Types

- **TEXT values:** `{"country": "USA"}`
- **BOOLEAN values:** `{"include_franking_credits_tsr": true}`
- **NUMERIC values:** `{"tax_rate_franking_credits": 45.0, "value_of_franking_credits": 50.0}`

### Examples

**Example 1: Conservative Valuation (Higher Tax Rate, Lower Franking Value)**
```json
{
  "param_set_name": "conservative_valuation",
  "param_overrides": {
    "include_franking_credits_tsr": true,
    "tax_rate_franking_credits": 45.0,
    "value_of_franking_credits": 50.0
  }
}
```

**Example 2: Aggressive Valuation (Lower Tax Rate, Higher Franking Value)**
```json
{
  "param_set_name": "aggressive_valuation",
  "param_overrides": {
    "include_franking_credits_tsr": true,
    "tax_rate_franking_credits": 30.0,
    "value_of_franking_credits": 100.0
  }
}
```

**Example 3: No Franking (Exclude Franking Credits)**
```json
{
  "param_set_name": "no_franking",
  "param_overrides": {
    "include_franking_credits_tsr": false
  }
}
```

**Example 4: Mixed Scenario**
```json
{
  "param_set_name": "custom_scenario",
  "param_overrides": {
    "country": "USA",
    "tax_rate_franking_credits": 37.0,
    "cost_of_equity_approach": "Fixed"
  }
}
```

---

## Franking Parameters: Legacy to Database Mapping

### Parameter Resolution Algorithm

When FY_TSR calculation executes with a specific `param_set_id`:

1. **Load parameter_sets row** with matching `param_set_id`
2. **Get param_overrides** JSONB
3. **For each of 3 franking parameters:**
   - If key exists in `param_overrides`: **use override value**
   - If key missing from `param_overrides`: **use `parameters.default_value`** for that parameter
4. **Convert values** for legacy code compatibility:
   - `include_franking_credits_tsr` → `incl_franking` (BOOLEAN 'false'/'true' → string 'No'/'Yes')
   - `tax_rate_franking_credits` → `frank_tax_rate` (NUMERIC '30.0' → decimal 0.30)
   - `value_of_franking_credits` → `value_franking_cr` (NUMERIC '75.0' → decimal 0.75)

### FY_TSR Calculation Using Parameters

**Legacy formula (from metrics.py lines 47-63):**
```python
def calculate_fy_tsr(row, inputs):
    incl_franking = inputs['incl_franking']
    frank_tax_rate = inputs['frank_tax_rate']
    value_franking_cr = inputs['value_franking_cr']
    fy_tsr = np.nan
    lag_mc = row['LAG_MC']
    if lag_mc > 0:
        if row["INCEPTION_IND"] == 1:
            if incl_franking == "Yes":
                div = row['dividend'] / (1 - frank_tax_rate)
                change_in_cap = row['C_MC'] - row['LAG_MC'] + row['ECF'] - div
                adjusted_change = change_in_cap * frank_tax_rate * value_franking_cr
                fy_tsr = adjusted_change / lag_mc
            else:
                change_in_cap = row['C_MC'] - row['LAG_MC'] + row['ECF']
                fy_tsr = change_in_cap / lag_mc
    return fy_tsr
```

**Database parameter mapping:**
- `incl_franking` ← resolve `include_franking_credits_tsr` parameter
- `frank_tax_rate` ← resolve `tax_rate_franking_credits` / 100
- `value_franking_cr` ← resolve `value_of_franking_credits` / 100

**Key observation:** The formula needs decimal values (0.30, 0.75), but database stores percentages (30.0, 75.0). SQL functions must perform the conversion.

---

## Query Patterns for Parameter-Sensitive Metrics

### Pattern 1: Get Default FY_TSR Values

```sql
SELECT 
  m.ticker,
  m.fiscal_year,
  m.output_metric_value as fy_tsr
FROM metrics_outputs m
WHERE m.output_metric_name = 'FY_TSR'
  AND m.param_set_id = (SELECT param_set_id FROM parameter_sets WHERE is_default = true)
  AND m.dataset_id = 'your-dataset-id'
ORDER BY m.ticker, m.fiscal_year;
```

### Pattern 2: Compare FY_TSR Across Multiple Parameter Sets

```sql
SELECT 
  ps.param_set_name,
  m.ticker,
  m.fiscal_year,
  m.output_metric_value as fy_tsr
FROM metrics_outputs m
JOIN parameter_sets ps ON m.param_set_id = ps.param_set_id
WHERE m.output_metric_name = 'FY_TSR'
  AND m.dataset_id = 'your-dataset-id'
ORDER BY m.ticker, m.fiscal_year, ps.param_set_name;
```

### Pattern 3: Verify Parameter Set Configuration

```sql
SELECT 
  param_set_name,
  is_default,
  is_active,
  param_overrides,
  created_at
FROM parameter_sets
WHERE is_active = true
ORDER BY is_default DESC, created_at;
```

### Pattern 4: Get Parameter Default Values

```sql
SELECT 
  parameter_name,
  display_name,
  value_type,
  default_value
FROM parameters
WHERE parameter_name IN (
  'include_franking_credits_tsr',
  'tax_rate_franking_credits',
  'value_of_franking_credits'
)
ORDER BY parameter_name;
```

### Pattern 5: Create New Parameter Set (SQL for DBA)

```sql
INSERT INTO parameter_sets (param_set_name, description, is_default, is_active, param_overrides, created_by)
VALUES (
  'high_franking_valuation',
  'Aggressive scenario: 37% tax rate, 100% franking value',
  false,
  true,
  '{"tax_rate_franking_credits": 37.0, "value_of_franking_credits": 100.0}'::jsonb,
  'analyst'
)
ON CONFLICT (param_set_name) DO NOTHING;
```

---

## Parameter Sensitivity: Same Ticker/Year, Different Results

### Key Architectural Insight

The `metrics_outputs` table has a UNIQUE constraint:
```sql
UNIQUE (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
```

This explicitly **allows multiple FY_TSR values** for the same (ticker, fiscal_year) pair, **one per param_set_id**.

### Example Scenario

**Company: CBA (Commonwealth Bank), Fiscal Year: 2020**

| param_set_id | param_set_name | incl_franking | frank_tax_rate | value_franking_cr | FY_TSR |
|---|---|---|---|---|---|
| ps-1 | base_case | false | 0.30 | 0.75 | 12.45% |
| ps-2 | high_franking | true | 0.30 | 0.75 | 14.32% |
| ps-3 | no_franking | false | N/A | N/A | 12.45% |
| ps-4 | conservative | true | 0.45 | 0.50 | 11.87% |

### Query Implications

**❌ WRONG:** Query without filtering param_set_id returns multiple rows
```sql
SELECT * FROM metrics_outputs 
WHERE ticker = 'CBA' AND fiscal_year = 2020 AND output_metric_name = 'FY_TSR'
-- Returns 4 rows (one per parameter_set)
```

**✅ CORRECT:** Always filter by param_set_id
```sql
SELECT * FROM metrics_outputs 
WHERE ticker = 'CBA' AND fiscal_year = 2020 AND output_metric_name = 'FY_TSR'
  AND param_set_id = (SELECT param_set_id FROM parameter_sets WHERE is_default = true)
-- Returns 1 row (default parameter set only)
```

---

## Default Values for Australian Context

Based on analysis of legacy system defaults and Australian tax environment:

| Parameter | Database Default | Rationale |
|---|---|---|
| **include_franking_credits_tsr** | false (BOOLEAN) | Conservative: exclude franking by default; requires explicit opt-in |
| **tax_rate_franking_credits** | 30.0 (NUMERIC) | Australian company tax rate (30% as of 2026) |
| **value_of_franking_credits** | 75.0 (NUMERIC) | Conservative: 75% of face value (not 100% due to capital gains tax discount) |

### Context

- **Australian tax rate:** 30% company tax rate (stable since 2015)
- **Franking credit valuation:** Full face value is 42.86% (= 30% / (100% - 30%)), but investors typically value at 75% due to:
  - Capital gains tax discounts for individuals (50%)
  - Tax loss carryforwards limiting credit utilization
  - Timing differences in dividend receipt
- **Conservative default:** `is_default=false` means "base_case" explicitly excludes franking credits unless overridden

---

## Summary of Findings

### ✅ Verified State

| Component | Status | Location |
|---|---|---|
| **parameters table** | ✅ Created with 13 baseline parameters | schema.sql lines 409-424 |
| **include_franking_credits_tsr** | ✅ Defined (BOOLEAN) | parameters table, default: 'false' |
| **tax_rate_franking_credits** | ✅ Defined (NUMERIC) | parameters table, default: '30.0' |
| **value_of_franking_credits** | ✅ Defined (NUMERIC) | parameters table, default: '75.0' |
| **parameter_sets table** | ✅ Created with "base_case" | schema.sql lines 427-430 |
| **base_case (is_default)** | ✅ Set to true | parameter_sets, param_overrides='{}' |
| **UNIQUE constraint** | ✅ Enforced on metrics_outputs | metrics_outputs: (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name) |

### ⚠️ Important Notes

1. **Parameter naming mismatch:** Database parameter names differ from legacy code variable names:
   - `include_franking_credits_tsr` ≠ `incl_franking` (needs mapping in SQL functions)
   - `tax_rate_franking_credits` ≠ `frank_tax_rate` (needs conversion: 30.0 → 0.30)
   - `value_of_franking_credits` ≠ `value_franking_cr` (needs conversion: 75.0 → 0.75)

2. **Type conversions:** SQL functions must handle type conversions for legacy code compatibility:
   - BOOLEAN 'false' → string 'No'; 'true' → 'Yes'
   - NUMERIC percentages → decimal fractions (divide by 100)

3. **Parameter set queries:** All FY_TSR queries must include `param_set_id` filter to avoid ambiguity

4. **"base_case" is default:** When no param_set_id specified, use `base_case` (is_default=true)

---

## Implementation Checklist

- [x] Verify parameters table schema (13 baseline parameters)
- [x] Verify parameter_sets table schema
- [x] Confirm "base_case" exists with is_default=true
- [x] Document franking parameter defaults (Australian context)
- [x] Document param_overrides JSONB structure with examples
- [x] Document parameter resolution algorithm (baseline defaults + overrides)
- [x] Document query patterns for parameter-sensitive metrics
- [x] Document parameter sensitivity implications (multiple rows per ticker/year)
- [x] Provide mapping from legacy code to database parameters

---

## Related Documentation

- **Legacy Code:** `example-calculations/src/executors/metrics.py` (lines 47-63: calculate_fy_tsr)
- **Database Schema:** `backend/database/schema/schema.sql` (lines 251-430: parameters + parameter_sets)
- **Phase Context:** `.planning/06-L1-Metrics-Alignment/PROJECT.md` (section: Parameter Set Configuration)

---

## Next Steps (Phase 06 Implementation)

1. **Task 3:** Implement SQL functions for all 12 L1 metrics (including FY_TSR parameter handling)
2. **Task 4:** Add parameter mapping logic to SQL functions (convert database JSONB to legacy variable names)
3. **Verification:** Compare SQL FY_TSR output to legacy Python reference for all parameter_sets
4. **API Layer:** Update metrics_service.py to handle parameter_set_id selection + pass through to SQL functions
