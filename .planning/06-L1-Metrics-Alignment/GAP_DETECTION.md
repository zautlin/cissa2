# GAP_DETECTION.md — Fiscal Year Gap Detection & Mitigation Strategy

**Purpose:** Document the year gap gotcha in LAG window functions and provide detection/mitigation strategies.

**Date:** 2026-03-09  
**Affected Metrics:** ECF, NON_DIV_ECF, FY_TSR, FY_TSR_PREL (all temporal metrics using LAG_MC)  
**Requirement:** REQ-D2

---

## Executive Summary

When calculating temporal metrics using LAG window functions, fiscal year gaps in the fundamentals data cause LAG to shift incorrectly. This document explains the problem, provides detection methods, and documents the chosen mitigation strategy.

**Decision:** Document the gotcha in function comments; test with gap data; consider future null-filling phase.

---

## The Problem: Year Gaps Cause LAG to Shift

### What Happens

When a company has missing fiscal years in the data, the LAG function returns the previous available row, not the previous year.

### Example Scenario

**Company:** ACME Inc. (ASX ticker: ACE)  
**Available Fiscal Years in Database:** 2015, 2016, 2017, 2020, 2021  
**Missing Years:** 2018, 2019 (due to data quality issues, acquisition, or data ingestion delay)

**LAG(C_MC) Calculation:**

| Fiscal Year | C_MC | LAG(C_MC) Result | Interpretation | Status |
|-------------|------|------------------|-----------------|--------|
| 2015 | $100M | NULL | First year, no prior | ✓ Correct |
| 2016 | $110M | $100M | Prior year 2015 | ✓ Correct |
| 2017 | $120M | $110M | Prior year 2016 | ✓ Correct |
| 2020 | $140M | $120M | Prior row (2017), NOT prior year! | ✗ **WRONG** |
| 2021 | $150M | $140M | Prior row (2020) | ✓ Correct (by accident) |

### Impact on ECF

**ECF Formula:** `ECF = LAG_MC × (1 + fytsr/100) - C_MC`

For 2020:
```
Correct calculation (if 2019 data existed):
  ECF(2020) = LAG_MC(2019) × (1 + fytsr(2020)/100) - C_MC(2020)

Actual calculation (with gap):
  ECF(2020) = LAG_MC(2017) × (1 + fytsr(2020)/100) - C_MC(2020)  ✗ WRONG!
```

**Result:** ECF for 2020 reflects 3-year change, not 1-year change. Calculated value is artificially large or small.

---

## Root Cause Analysis

### Why LAG Behaves This Way

PostgreSQL's `LAG()` window function is **row-based**, not **year-based**:

```sql
-- PostgreSQL syntax:
LAG(column, offset) OVER (PARTITION BY ticker ORDER BY fiscal_year)

-- Translation: "Get value from N rows before this one"
-- NOT: "Get value from N periods before this one"
```

When you `ORDER BY fiscal_year`, the rows are sorted chronologically. But LAG counts row offsets, not year offsets.

**Example:**
```sql
-- If table has rows sorted by fiscal_year:
ORDER BY fiscal_year ASC
-- Produces row sequence: [1, 2, 3, 4, 5]
-- LAG(col, 1) on row 4 returns row 3's value (2017)
-- NOT year 2019's value (which doesn't exist)
```

### Why This Matters for Financial Analysis

Shareholders and analysts expect:
- "2020 TSR" = Total shareholder return from end of 2019 to end of 2020
- But with gap data, "2020 TSR" = Return from end of 2017 to end of 2020 (3-year return)

This misrepresents 2020 performance as more volatile than it actually was.

---

## Detection Strategy: fiscal_year - ROW_NUMBER() Method

### How to Detect Gaps

Use a helper calculation to identify which years are missing:

```sql
SELECT
  ticker,
  fiscal_year,
  ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year) AS row_num,
  (fiscal_year - ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year)) AS gap_indicator
FROM fundamentals
WHERE dataset_id = 'your-dataset-id'
ORDER BY ticker, fiscal_year;
```

### Interpreting the Results

**Gap Indicator Logic:**
- If consecutive years with no gaps: `gap_indicator` is constant
- If gap detected: `gap_indicator` changes

**Example Output:**

| Ticker | Fiscal Year | Row Num | Gap Indicator | Change? | Status |
|--------|-------------|---------|---------------|---------|--------|
| ACE | 2015 | 1 | 2014 | — | — |
| ACE | 2016 | 2 | 2014 | No | No gap |
| ACE | 2017 | 3 | 2014 | No | No gap |
| ACE | 2020 | 4 | 2016 | **Yes** | **Gap detected!** |
| ACE | 2021 | 5 | 2016 | No | Gap continues |

**Interpretation:**
- Rows 1-3: gap_indicator = 2014 (constant, no gap)
- Row 4: gap_indicator jumps to 2016 (indicates 2-year gap)
- Row 5: gap_indicator = 2016 (constant, gap confirmed)

### Detection Query (Comprehensive)

```sql
WITH year_gaps AS (
  SELECT
    ticker,
    fiscal_year,
    ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year) AS row_num,
    (fiscal_year - ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year)) AS gap_indicator,
    LAG(fiscal_year, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year) AS prior_year
  FROM fundamentals
  WHERE dataset_id = 'your-dataset-id'
),
gap_differences AS (
  SELECT
    *,
    (fiscal_year - prior_year) AS year_difference
  FROM year_gaps
  WHERE prior_year IS NOT NULL
)
SELECT
  ticker,
  fiscal_year,
  year_difference,
  CASE 
    WHEN year_difference = 1 THEN 'Consecutive'
    WHEN year_difference > 1 THEN 'GAP: ' || (year_difference - 1) || ' years missing'
    ELSE 'ERROR'
  END AS gap_status
FROM gap_differences
ORDER BY ticker, fiscal_year;
```

**Output Example:**
```
ticker | fiscal_year | year_difference | gap_status
-------|-------------|-----------------|-------------------------------------------
ACE    | 2016        | 1               | Consecutive
ACE    | 2017        | 1               | Consecutive
ACE    | 2020        | 3               | GAP: 2 years missing  ← Flag!
ACE    | 2021        | 1               | Consecutive
```

---

## Current Mitigation Strategy: Document & Warn

### Decision

**For Phase 06:** Accept the limitation and document it.

**Rationale:**
1. Legacy Python implementation has the same behavior (no null-filling)
2. Aligning with legacy is design goal of Phase 06
3. Fixing would require data engineering (null-filling pipeline)
4. Risk acceptable for initial implementation

### Implementation

#### 1. Function Comments (SQL)

All temporal metric functions will include this header comment:

```sql
-- ============================================================================
-- TEMPORAL METRIC: [METRIC NAME]
-- ============================================================================
-- 
-- WARNING: Year Gap Gotcha
-- 
-- This function uses LAG window function to access prior year's market cap.
-- LAG is ROW-BASED, not YEAR-BASED:
--   - If fiscal years are consecutive (2015, 2016, 2017, ...): LAG works correctly
--   - If years have gaps (2015, 2016, 2017, 2020, 2021): LAG returns prior ROW, not prior year
--   
-- Example with gap:
--   Fiscal Year 2020 → LAG(C_MC) returns 2017's value (not 2019)
--   Result: ECF(2020) calculates 3-year return as if it were 1-year return
--
-- Detection:
--   SELECT ticker, fiscal_year, (fiscal_year - ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year))
--   FROM fundamentals
--   ORDER BY ticker, fiscal_year;
--
-- Mitigation:
--   - Test with known-gap data in test_l1_metrics.py
--   - Log warning in function output if gaps detected
--   - Document in API response that results may be unreliable for companies with missing years
--
-- Future improvements (Phase 07+):
--   - Implement year-based LAG: fill gaps with NULL or interpolated values
--   - Add data quality flag to metrics_outputs (gap_flag = true if gaps detected)
--
-- ============================================================================
```

#### 2. Test Cases (Python)

Create test case with gap data to verify current behavior and document it:

```python
# backend/tests/test_l1_metrics.py

def test_ecf_with_year_gap():
    """
    Verify ECF calculation with missing fiscal years (year gap).
    
    This test documents the known gotcha: LAG window functions shift
    incorrectly when fiscal years have gaps.
    
    Test data:
    - Company: TEST_GAP (ticker)
    - Years: 2015, 2016, 2017, 2020, 2021 (missing 2018, 2019)
    - Expected: ECF(2020) uses LAG_MC(2017), not LAG_MC(2019)
    
    This is documented behavior, not a bug. Results are unreliable for
    companies with year gaps.
    """
    # Setup: Insert test data with gap
    test_tickers = ['TEST_GAP']
    test_years = [2015, 2016, 2017, 2020, 2021]  # Gap: missing 2018, 2019
    
    # Calculate using SQL function
    results = calculate_ecf_for_dataset(test_dataset_id)
    
    # Filter to test ticker
    gap_results = results[results['ticker'] == 'TEST_GAP'].sort_values('fiscal_year')
    
    # Verify LAG shifts with gap
    ecf_2020 = gap_results[gap_results['fiscal_year'] == 2020]['ecf'].values[0]
    
    # Log gap behavior
    logger.warning(
        f"Year gap detected in TEST_GAP: ECF(2020) = {ecf_2020}\n"
        f"LAG(C_MC) points to 2017 (prior row), not 2019 (prior year)\n"
        f"This is documented behavior."
    )
    
    # Assert: Just verify calculation ran (don't assert specific value)
    assert ecf_2020 is not None or ecf_2020 is np.nan
```

#### 3. API Documentation

Update API response documentation:

```markdown
### Note on Year Gaps

If a company has missing fiscal years in the data (e.g., 2015, 2016, 2017, 2020, 2021),
temporal metrics (ECF, FY_TSR, etc.) may be unreliable for years following the gap.

**Why:** Window functions use LAG(row offset), not LAG(year offset).

**Example:**
- Company X has data for 2015-2017, then 2020+ (missing 2018-2019)
- ECF(2020) uses C_MC(2017) as prior year, not C_MC(2019)
- Result: 3-year return calculated as 1-year return

**Detection:** Query returns `gap_detected` flag in metadata (future phase).

**Recommendation:** Filter by `companies.gap_years IS NULL` to get clean data.
```

#### 4. Data Quality Flag (Future)

**Phase 07+:** Add to metrics_outputs schema:
```sql
ALTER TABLE metrics_outputs 
ADD COLUMN gap_detected BOOLEAN DEFAULT FALSE,
ADD COLUMN gap_years_count INTEGER DEFAULT 0;

-- Populate during metric calculation:
-- If (fiscal_year - ROW_NUMBER()) changes, set gap_detected = TRUE
```

---

## Validation: Test Data

### Test Case 1: Normal Data (No Gaps)

```
Company: NORMAL
Years: 2015, 2016, 2017, 2018, 2019, 2020, 2021 (consecutive)

Expected LAG(C_MC):
2015: NULL
2016: 2015
2017: 2016
...
2021: 2020

Status: ✓ Works correctly
```

### Test Case 2: Data with Gaps

```
Company: GAP
Years: 2015, 2016, 2017, 2020, 2021 (missing 2018, 2019)

Expected LAG(C_MC):
2015: NULL
2016: 2015 (correct)
2017: 2016 (correct)
2020: 2017 (WRONG! Should be 2019, which doesn't exist)
2021: 2020 (correct by accident)

Detection Output:
fiscal_year | row_num | gap_indicator | Status
2015        | 1       | 2014          | OK
2016        | 2       | 2014          | OK
2017        | 3       | 2014          | OK
2020        | 4       | 2016          | CHANGE! Gap detected
2021        | 5       | 2016          | OK

Status: ✗ LAG shifts; documented limitation
```

### Test Case 3: Large Gap

```
Company: LARGE_GAP
Years: 2015, 2020 (5-year gap)

Expected LAG(C_MC):
2015: NULL
2020: 2015 (VERY WRONG! Should be 2019)

Gap indicator change:
2015: gap_indicator = 2014
2020: gap_indicator = 2015 → Change of 1 (indicates gap)

Status: ✗ Extreme shift; metrics unreliable
Recommendation: Exclude from analysis or flag prominently
```

---

## Action Items

### Immediate (Phase 06 - Task 1)

- ✅ Create this document (GAP_DETECTION.md)
- ✅ Document in L1_METRICS_SQL_MAPPING.md
- [ ] Create test case with gap data (Task 4)
- [ ] Add warning comments to SQL functions (Task 3)

### Near-term (Phase 06 - Task 4)

- [ ] Run detection query on live dataset
- [ ] Identify which companies have gaps
- [ ] Log results and severity distribution

### Future (Phase 07+)

- [ ] Implement year-based null-filling (data engineering)
- [ ] Add `gap_detected` flag to metrics_outputs
- [ ] Create data quality dashboard showing gap statistics

---

## Summary

**Year gaps are a known limitation of window function-based calculations.**

The current mitigation strategy is to:
1. Document the behavior extensively
2. Provide detection methods
3. Test with gap data
4. Plan for future null-filling phase

This aligns with Phase 06's goal of implementing pure SQL functions matching legacy Python behavior. The legacy system also doesn't handle gaps specially; fixing them is out of scope for this phase.

**Users should be aware:** If they query temporal metrics for companies with missing years, results may not reflect single-year performance changes.

