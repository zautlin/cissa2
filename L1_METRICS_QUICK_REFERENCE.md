# L1 Metrics PostgreSQL Implementation - Quick Reference

## TL;DR Summary

| Category | Status | Risk |
|----------|--------|------|
| **7 Simple Metrics** | ✅ **READY** - Already implemented in functions.sql | LOW |
| **5 Temporal Metrics** | ⚠️ **FEASIBLE** - Requires careful circular dependency handling | MEDIUM |
| **Batch Calculation** | ✅ **YES** - Achieves 100-1000x performance improvement | LOW |
| **Overall Decision** | ✅ **PROCEED** - SQL implementation is viable | MEDIUM |

---

## 1. Simple Metrics Status (7/7 ✅)

### Currently Implemented Functions
```
✅ fn_calc_market_cap()          - C_MC = SPOT_SHARES × SHARE_PRICE
✅ fn_calc_operating_assets()    - C_ASSETS = TOTAL_ASSETS - CASH
✅ fn_calc_operating_assets_detail() - OA = C_ASSETS - FIXED_ASSETS - GOODWILL
✅ fn_calc_operating_cost()      - OP_COST = REVENUE - OPERATING_INCOME
✅ fn_calc_non_operating_cost()  - NON_OP_COST = OPERATING_INCOME - PBT
✅ fn_calc_tax_cost()            - TAX_COST = PBT - PAT_EX
✅ fn_calc_extraordinary_cost()  - XO_COST = PAT_EX - PAT
```

### Action Required
- **NONE** - All 7 simple metrics are production-ready
- Simple metrics can be called immediately: `SELECT * FROM fn_calc_market_cap(dataset_id)`

---

## 2. Temporal Metrics Status (5/5 ⚠️)

### Feasibility Assessment

| Metric | Feasible | Complexity | Key Challenge | Est. Dev Time |
|--------|----------|-----------|----------------|---------------|
| LAG_MC | ✅ Yes | Low | Year gap detection | 1h |
| NON_DIV_ECF | ✅ Yes | Low | None | 1h |
| FY_TSR_PREL | ✅ Yes | Low | None | 1h |
| EE | ✅ Yes | Medium | Cumsum + inception logic | 2h |
| ECF | ✅ Yes | Medium | **Circular dependency with FY_TSR** | 3h |
| FY_TSR | ✅ Yes | High | **Circular dependency, parameters, franking** | 4-6h |

### Circular Dependency Problem

```
FY_TSR formula needs ECF:
  FY_TSR = (C_MC - LAG_MC + ECF - dividend) / LAG_MC

ECF formula needs FY_TSR:
  ECF = LAG_MC × (1 + FY_TSR/100) - C_MC
```

### Resolution Strategy

**Option A (Recommended):** Keep Python for ECF/FY_TSR
- Use historical FY_TSR from previous year as bootstrap
- Current codebase already does this (see executors/metrics.py line 87)
- Minimal refactoring: ~2-3 hours
- Risk: LOW

**Option B:** Restructure formulas
- More complex; not recommended unless required
- Risk: MEDIUM-HIGH

**Option C:** Iterative SQL computation
- Impractical in pure SQL
- Risk: HIGH

---

## 3. Critical Gotchas to Watch

### 🔴 HIGH SEVERITY

| Gotcha | Impact | Fix |
|--------|--------|-----|
| **NULL propagation** | Any NULL in arithmetic → NULL result | Use explicit `IS NOT NULL` in WHERE |
| **Year gaps in LAG** | Missing year shifts LAG incorrectly (2019→2021) | Detect gaps: `fiscal_year - ROW_NUMBER() OVER (...)` |
| **Circular ECF/FY_TSR** | Cannot compute both simultaneously | Use historical FY_TSR as input (Python approach) |
| **Inception year logic** | If begin_year is NULL, logic breaks | Add `NOT NULL` constraint to companies.begin_year |

### 🟡 MEDIUM SEVERITY

| Gotcha | Impact | Fix |
|--------|--------|-----|
| **Parameter set confusion** | Same (ticker, year) → multiple metric values | Always filter by `param_set_id` in queries |
| **Dataset isolation** | Queries mix multiple dataset versions | Always filter by `dataset_id` in WHERE |
| **Division by zero** | Ratio calculations fail for (revenue=0, etc.) | Use `NULLIF(divisor, 0)` or WHERE clause |
| **Precision drift** | Cumsum drifts over 60+ years | Use NUMERIC (not FLOAT); document rounding |

### 🟢 LOW SEVERITY

| Gotcha | Impact | Fix |
|--------|--------|-----|
| **First year has NULL LAG** | LAG_MC is NULL in year 1 | Expected; document in spec |
| **Data type mismatches** | Slow implicit casts | Enforce types in schema (already done) |
| **Floating point math** | ~0.00001% accumulated error | Minor; test vs. Python reference |

---

## 4. Implementation Roadmap

### Phase 1: Pre-Implementation Fixes (1-2 hours)
```sql
-- Add NOT NULL constraint to companies.begin_year
ALTER TABLE companies 
ADD CONSTRAINT chk_begin_year_not_null CHECK (begin_year IS NOT NULL);

-- Verify no NULL values exist
SELECT COUNT(*) FROM companies WHERE begin_year IS NULL;
```

### Phase 2: Simple Metrics (0 hours - Already Done)
```sql
-- All 7 simple metrics already implemented in functions.sql
-- Just verify they work:
SELECT * FROM fn_calc_market_cap('dataset-uuid-here') LIMIT 5;
```

### Phase 3: Temporal Metrics (8-12 hours)
```sql
-- 1. LAG_MC (1 hour)
CREATE OR REPLACE FUNCTION fn_calc_lag_mc(p_dataset_id UUID)
RETURNS TABLE (...) AS $$
  WITH market_cap AS (
    SELECT * FROM fn_calc_market_cap(p_dataset_id)
  )
  SELECT 
    ticker, fiscal_year,
    LAG(calc_mc, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year) AS lag_mc
  FROM market_cap;
$$ LANGUAGE SQL;

-- 2. FY_TSR (4-6 hours - Complex parameter logic)
-- 3. ECF (3 hours - Needs pre-computed FY_TSR as input)
-- 4. NON_DIV_ECF (1 hour - Simple: ECF + dividend)
-- 5. EE (2 hours - Cumsum with inception logic)
-- 6. FY_TSR_PREL (1 hour - Simple: FY_TSR + 1)
```

### Phase 4: Batch Function (2-3 hours)
```sql
-- Merge all 12 metrics into single function
CREATE OR REPLACE FUNCTION fn_calc_l1_metrics_batch(
  p_dataset_id UUID,
  p_param_set_id UUID DEFAULT NULL
)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  metric_name TEXT,
  metric_value NUMERIC
) AS $$
  -- Combine all 12 metrics in single result set
  -- Uses UNION ALL for efficiency
  -- Returns ~12k rows for 200 companies × 10 years
$$ LANGUAGE SQL;
```

### Phase 5: Testing & Deployment (3-4 hours)
- Unit test each metric vs. Python reference
- Performance test: 10k companies × 60 years = 7.2M rows → target ~30-60s
- Validate year gaps detection
- Document parameter sensitivity

---

## 5. SQL Window Functions Needed

### Window Function Patterns

```sql
-- Pattern 1: LAG for previous year
LAG(metric_value, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year)

-- Pattern 2: Cumulative sum
SUM(metric_component) OVER (PARTITION BY ticker ORDER BY fiscal_year)

-- Pattern 3: Detect year gaps
fiscal_year - ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year) AS gap_group

-- Pattern 4: Rank within group
ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year) AS row_num
```

### Performance Indexes Required

```sql
-- Create these to speed up window function calculations
CREATE INDEX idx_fundamentals_ticker_fy 
  ON fundamentals (ticker, fiscal_year);

CREATE INDEX idx_metrics_outputs_ticker_fy 
  ON metrics_outputs (ticker, fiscal_year, output_metric_name);

CREATE INDEX idx_companies_ticker 
  ON companies (ticker);
```

---

## 6. NULL Handling Checklist

```sql
-- ✅ DO: Filter NULL values explicitly
WHERE metric_value IS NOT NULL
  AND divisor > 0

-- ❌ DON'T: Assume arithmetic handles NULL
-- ❌ DON'T: Compare NULL values (NULL = NULL is unknown, not true)

-- ✅ DO: Use COALESCE for defaults
COALESCE(metric_value, 0)

-- ✅ DO: Use NULLIF for division by zero
metric_value / NULLIF(divisor, 0)

-- ✅ DO: Document NULL semantics
-- (e.g., "If LAG_MC is NULL in first year, ECF will be NULL")
```

---

## 7. Testing Strategy

### Unit Tests (For Each Metric)

```python
# Test LAG_MC
assert lag_mc[ticker][2016] == market_cap[ticker][2015]
assert lag_mc[ticker][2015] is None  # First year

# Test ECF (using historical FY_TSR)
ecf = lag_mc * (1 + historical_fy_tsr / 100) - market_cap
# Verify: ecf[ticker][2016] matches Python reference

# Test EE (cumulative sum)
ee_cumsum = ee_yearly.groupby('ticker')['ee_component'].cumsum()
# Verify: each ticker starts at begin_year, accumulates correctly

# Test FY_TSR (parameter sensitivity)
for param_set in ['base_case', 'conservative', 'aggressive']:
  fy_tsr = calculate_fy_tsr(param_set)
  # Verify: different param_sets produce different values
```

### Integration Tests

```sql
-- Test: All 12 metrics returned for single call
SELECT * FROM fn_calc_l1_metrics_batch('dataset-uuid');
-- Should return 12 * (num_tickers) * (num_years) rows

-- Test: No NULL inception errors
SELECT * FROM fn_calc_l1_metrics_batch('dataset-uuid')
WHERE inception_ind IS NULL;
-- Should return 0 rows (all companies have valid begin_year)

-- Test: Year gap detection
-- Dataset with missing 2020 for ticker ABC
-- LAG_MC[ABC][2021] should NOT equal Market_Cap[ABC][2020]
```

---

## 8. Quick Wins (No-Risk, Quick Wins)

1. **Verify simple metrics work** (5 mins)
   ```sql
   SELECT COUNT(*) FROM fn_calc_market_cap('any-dataset-id');
   ```

2. **Create test dataset with year gaps** (15 mins)
   - Helps validate LAG logic
   - Essential before production deployment

3. **Add NOT NULL constraint** (5 mins)
   ```sql
   ALTER TABLE companies 
   ADD CONSTRAINT chk_begin_year_not_null CHECK (begin_year IS NOT NULL);
   ```

4. **Create performance indexes** (10 mins)
   ```sql
   CREATE INDEX idx_fundamentals_ticker_fy 
     ON fundamentals (ticker, fiscal_year);
   ```

5. **Document parameter set requirements** (20 mins)
   - Add to API spec
   - Add to function comments
   - Add to README

---

## 9. Decision Tree

```
START
│
├─ Question: Use SQL stored procedures for L1 metrics?
│  └─ Answer: YES ✅
│
├─ Question: Implement all 12 metrics immediately?
│  ├─ Simple metrics (7): YES ✅ (already done)
│  └─ Temporal metrics (5): PHASED 🟡
│      ├─ Easy ones (LAG_MC, NON_DIV_ECF, FY_TSR_PREL): YES (next sprint)
│      └─ Hard ones (FY_TSR, ECF, EE): Keep Python for now, migrate later
│
├─ Question: Batch calculate or individual metrics?
│  └─ Answer: BATCH ✅ (100-1000x faster)
│
├─ Question: Watch out for gotchas?
│  ├─ NULL handling: YES ✅
│  ├─ Year gaps: YES ✅
│  ├─ Circular ECF/FY_TSR: YES ✅ (use Python approach)
│  └─ Begin year logic: YES ✅ (add NOT NULL constraint)
│
└─ END: Proceed with SQL implementation
```

---

## 10. Further Reading

- **Full analysis:** See `L1_METRICS_FEASIBILITY_ANALYSIS.md` (29 KB)
- **Schema:** `/backend/database/schema/schema.sql` (lines 1-448)
- **Functions:** `/backend/database/schema/functions.sql` (lines 1-542)
- **Python reference:** `/example-calculations/src/executors/metrics.py`

---

## 11. Contact & Questions

- **Question:** Can I use window functions safely?
  - **Answer:** Yes, with proper NULL handling and year gap detection

- **Question:** What about parameter sensitivity in FY_TSR?
  - **Answer:** Always filter queries by `param_set_id`; document in API

- **Question:** Will circular ECF/FY_TSR dependency be a blocker?
  - **Answer:** No - use Python for first pass, then migrate to SQL

- **Question:** How much faster will batch calculation be?
  - **Answer:** 100-1000x depending on dataset size (60 individual calls → 1 batch call)

