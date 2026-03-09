---
phase: 06
plan: "Task 02: Review & Update parameter_sets Table"
subsystem: "L1 Metrics Alignment - Parameter Configuration"
tags: [parameters, franking, documentation]
dependency_graph:
  requires: [Phase 05 completion, schema.sql initialization]
  provides: [parameter mapping documentation, parameter sensitivity guidance]
  affects: [Task 3 (SQL function implementation), Task 4 (API integration)]
tech_stack:
  added: []
  patterns: [JSONB param_overrides, parameter resolution, tax parameter mapping]
key_files:
  created: [".planning/06-L1-Metrics-Alignment/PARAMETER_MAPPING.md"]
  modified: ["backend/database/schema/schema.sql (analysis only - no changes required)"]
decisions:
  - "Parameters already defined in schema: include_franking_credits_tsr, tax_rate_franking_credits, value_of_franking_credits ✅"
  - "base_case parameter_set confirmed as is_default=true ✅"
  - "No database schema changes needed - parameters properly initialized ✅"
  - "Legacy code parameter mapping documented for Task 3 SQL function implementation"
  - "Australian tax defaults confirmed: 30% tax rate, 75% franking credit valuation"
metrics:
  duration_minutes: 1
  start_time: "2026-03-09T05:12:15Z"
  end_time: "2026-03-09T05:13:31Z"
  completed_date: "2026-03-09"
---

# Phase 06 Task 02: Parameter Configuration Documentation — SUMMARY

**Objective:** Research parameter_sets table structure and franking parameters; document required configuration for FY_TSR calculation.

**Status:** ✅ **COMPLETE** — All acceptance criteria met

---

## What Was Done

### 1. Research Current State (Database Schema Analysis)

**Findings:**
- ✅ `parameters` table exists with 13 baseline parameters pre-initialized
- ✅ `parameter_sets` table exists with "base_case" entry
- ✅ All 3 required franking parameters already defined:
  - `include_franking_credits_tsr` (BOOLEAN, default: 'false')
  - `tax_rate_franking_credits` (NUMERIC, default: '30.0')
  - `value_of_franking_credits` (NUMERIC, default: '75.0')
- ✅ "base_case" is marked `is_default=true` with empty `param_overrides` '{}'

**Key Discovery:** Parameters were properly initialized in schema.sql (lines 409-430) during initial database creation. No schema changes required.

### 2. Research Legacy Parameter Handling

**Legacy Code Analysis** (example-calculations/src/executors/metrics.py):

```python
def calculate_fy_tsr(row, inputs):
    incl_franking = inputs['incl_franking']          # String: "Yes" or "No"
    frank_tax_rate = inputs['frank_tax_rate']        # Decimal: 0.30 for 30%
    value_franking_cr = inputs['value_franking_cr']  # Decimal: 0.75 for 75%
    ...
    if incl_franking == "Yes":
        div = row['dividend'] / (1 - frank_tax_rate)
        change_in_cap = row['C_MC'] - row['LAG_MC'] + row['ECF'] - div
        adjusted_change = change_in_cap * frank_tax_rate * value_franking_cr
        fy_tsr = adjusted_change / lag_mc
    ...
```

**Key Finding:** Legacy code uses variable names that differ from database parameter names. Mapping required:
- `incl_franking` ← database: `include_franking_credits_tsr` (needs type conversion)
- `frank_tax_rate` ← database: `tax_rate_franking_credits` (needs divide by 100)
- `value_franking_cr` ← database: `value_of_franking_credits` (needs divide by 100)

### 3. Created PARAMETER_MAPPING.md Documentation

**Comprehensive documentation includes:**

✅ **parameters table schema** (13 baseline parameters)
- Table structure, purpose, current parameter definitions
- Franking parameters with display names and defaults
- Australian tax context (30% company tax rate, 75% franking valuation)

✅ **parameter_sets table schema**
- Structure and purpose
- Current state verification (base_case exists, is_default=true)
- JSONB param_overrides structure with examples

✅ **JSONB param_overrides examples**
- Conservative valuation: higher tax rate (45%), lower franking value (50%)
- Aggressive valuation: lower tax rate (30%), higher franking value (100%)
- No franking scenario: include_franking_credits_tsr: false
- Mixed scenarios with multiple parameter overrides

✅ **Legacy to database parameter mapping**
- Parameter resolution algorithm (baseline + overrides)
- Type conversions needed (BOOLEAN → string, NUMERIC percentage → decimal)
- FY_TSR calculation using parameters

✅ **Query patterns for parameter-sensitive metrics**
- Get default FY_TSR values (filter by is_default=true)
- Compare FY_TSR across multiple parameter sets
- Verify parameter set configuration
- Get parameter default values
- Create new parameter set (SQL example for DBA)

✅ **Parameter sensitivity implications**
- UNIQUE constraint allows multiple FY_TSR values per (ticker, fiscal_year)
- One row per param_set_id
- Query implications: must always filter by param_set_id to avoid ambiguity
- Example: CBA 2020 has 4 different FY_TSR values (one per parameter_set)

✅ **Default values for Australian context**
- include_franking_credits_tsr: false (conservative: opt-in required)
- tax_rate_franking_credits: 30.0 (Australian company tax rate)
- value_of_franking_credits: 75.0 (conservative: 75% not 100%)

### 4. Verification

**Database schema verification:**
```sql
-- 13 baseline parameters initialized
INSERT INTO parameters (parameter_name, display_name, value_type, default_value)
VALUES
  ...
  ('include_franking_credits_tsr', 'Include Franking Credits (TSR)', 'BOOLEAN', 'false'),
  ...
  ('tax_rate_franking_credits', 'Tax Rate (Franking Credits)', 'NUMERIC', '30.0'),
  ('value_of_franking_credits', 'Value of Franking Credits', 'NUMERIC', '75.0'),
  ...

-- "base_case" parameter_set created with is_default=true
INSERT INTO parameter_sets (param_set_name, description, is_default, is_active, param_overrides, created_by)
VALUES
  ('base_case', 'Default parameter set using all 13 baseline parameters', true, true, '{}', 'admin')
```

**Findings:**
- ✅ Schema properly initialized
- ✅ All 13 baseline parameters present
- ✅ base_case marked as default
- ✅ No database changes required

---

## Acceptance Criteria Met

- [x] **PARAMETER_MAPPING.md created** with complete documentation
  - parameters table schema explained
  - parameter_sets table schema explained
  - param_overrides JSONB structure documented with 4 examples
  - Franking parameters documented with Australian tax context

- [x] **Franking parameters identified and mapped**
  - incl_franking ← include_franking_credits_tsr
  - frank_tax_rate ← tax_rate_franking_credits (30.0%)
  - value_franking_cr ← value_of_franking_credits (75.0%)

- [x] **parameter_sets table verified**
  - "base_case" exists ✅
  - is_default=true ✅
  - param_overrides='{}' (empty) ✅
  - Uses all 13 baseline parameter defaults ✅

- [x] **Query patterns documented**
  - Default FY_TSR queries (filter by is_default)
  - Parameter set comparison
  - Parameter verification
  - Parameter set creation (SQL DBA template)

- [x] **Parameter sensitivity documented**
  - Same (ticker, fiscal_year) → multiple FY_TSR values (one per param_set)
  - UNIQUE constraint allows this: (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
  - Query implications: always filter by param_set_id

- [x] **All changes committed atomically**
  - Commit: 742b59d (PARAMETER_MAPPING.md created)

---

## Deviations from Plan

### Summary
None - plan executed exactly as written. Database already properly initialized; no schema changes required.

---

## Key Insights for Task 3 Implementation

**When implementing temporal metrics SQL functions (Task 3):**

1. **Parameter resolution in SQL:** Functions will need to:
   - Accept param_set_id as parameter
   - Query parameter_sets for param_overrides JSONB
   - Extract individual parameters with COALESCE(override, baseline)
   - Convert types for legacy formula compatibility

2. **Type conversions needed:**
   ```sql
   -- BOOLEAN to string conversion
   CASE WHEN (param_overrides->>'include_franking_credits_tsr')::BOOLEAN 
        THEN 'Yes' ELSE 'No' END
   
   -- NUMERIC percentage to decimal conversion
   (param_overrides->>'tax_rate_franking_credits')::NUMERIC / 100 AS frank_tax_rate,
   (param_overrides->>'value_of_franking_credits')::NUMERIC / 100 AS value_franking_cr
   ```

3. **Query template for baseline + overrides:**
   ```sql
   SELECT COALESCE(
     (ps.param_overrides->>'parameter_name')::TEXT,
     p.default_value
   ) as param_value
   FROM parameter_sets ps
   JOIN parameters p ON p.parameter_name = 'parameter_name'
   WHERE ps.param_set_id = $1
   ```

4. **FY_TSR function signature:**
   - Input: dataset_id, param_set_id
   - Retrieve parameters for that param_set_id
   - Apply legacy formula with parameter conversion
   - Output: (ticker, fiscal_year, fy_tsr_value)

---

## Related Documentation

- **Legacy Code Reference:** `example-calculations/src/executors/metrics.py` (lines 47-63: calculate_fy_tsr)
- **Database Schema:** `backend/database/schema/schema.sql` (lines 251-430: parameters + parameter_sets)
- **Phase Context:** `.planning/06-L1-Metrics-Alignment/PROJECT.md` (section: Parameter Set Configuration)
- **Phase Technical State:** `.planning/06-L1-Metrics-Alignment/STATE.md` (Issue 5: Franking Parameters)

---

## Files Created/Modified

**Created:**
- `.planning/06-L1-Metrics-Alignment/PARAMETER_MAPPING.md` (447 lines)

**Modified (analysis only):**
- `backend/database/schema/schema.sql` (analyzed lines 251-430, no changes made)

**No database changes required** ✅

---

## Task Completion

✅ Task 02 complete - all deliverables met, documentation comprehensive and actionable for Task 3 implementation

**Next Task:** Task 03 - Implement SQL functions for all 12 L1 metrics (including parameter handling for temporal metrics)
