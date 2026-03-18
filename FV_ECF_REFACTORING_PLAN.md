# FV ECF Service Refactoring Plan

**Status:** Planning Phase  
**Date:** March 18, 2026  
**Scope:** Phase B of FV ECF & Non Div ECF implementation  

---

## Executive Summary

The FV ECF (Future Value Economic Cash Flow) service currently implements **incorrect formulas** for calculating 3Y, 5Y, and 10Y metrics. This plan outlines a systematic refactoring to implement the correct Excel-based formulas while maintaining code quality and performance.

### Key Issues
1. **Formula Error:** Current code uses wrong power calculations for multi-year intervals
2. **Data Dependencies:** Correctly fetches Non Div ECF from metrics_outputs (already fixed)
3. **Missing Validation:** No temporal window validation (need N years of prior data)
4. **Temporal Logic:** Uses complicated shifting logic instead of simple year-by-year lookback

### Correct Formula Structure
- **1Y:** `ECF_base[t] * (1 + Calc_Open_Ke[t])^0` (power = 0)
- **3Y:** Sum of 3 terms with powers ^2, ^1, ^0 (all using same Calc_Open_Ke[t])
- **5Y:** Sum of 5 terms with powers ^4, ^3, ^2, ^1, ^0
- **10Y:** Sum of 10 terms with powers ^9, ^8, ..., ^1, ^0

---

## Current Code Structure Analysis

### File: `/backend/app/services/fv_ecf_service.py` (598 lines)

#### Key Methods
| Method | Purpose | Status | Action |
|--------|---------|--------|--------|
| `calculate_fv_ecf_metrics()` | Main orchestrator | ✓ Working | Update logging, docs |
| `_fetch_fundamentals_data()` | Fetch DIVIDENDS, FRANKING, Non Div ECF | ✓ Correct | No changes needed |
| `_fetch_lagged_ke()` | Fetch prior year KE (Calc_Open_Ke) | ✓ Correct | Verify, add docs |
| `_join_data()` | Merge fundamentals + KE | ⚠️ Partial | Update for 3 sources |
| `_calculate_fv_ecf_for_interval()` | **Core calculation** | ✗ **WRONG FORMULA** | **Complete rewrite** |
| `_insert_fv_ecf_batch()` | Batch database insert | ✓ Working | No changes |

#### Data Flow (Current)
```
1. Load parameters (incl_franking, tax rates, etc.)
2. Fetch fundamentals (dividend, franking) + Non Div ECF ✓
3. Fetch lagged KE (ke_open) ✓
4. Join all data ⚠️ (only 2 sources merged)
5. Calculate FV_ECF for intervals [1, 3, 5, 10] ✗ WRONG FORMULA
6. Insert results in batches
```

---

## Phase B1: Analysis of Current Formula Implementation

### Lines 425-524: Current `_calculate_fv_ecf_for_interval()`

#### What It Currently Does
```python
for seq in range(interval, 0, -1):
    fv_interval = (seq - 1) * (-1)  # Calculates shift amount
    power = interval + fv_interval - 1  # INCORRECT power calculation
    
    # For interval=3: powers become 2, 1, 0 ✓ (accidental correctness)
    # For interval=5: powers become 4, 3, 2, 1, 0 ✓ (accidental correctness)
    # For interval=10: powers become 9, 8, ..., 1, 0 ✓ (accidental correctness)
```

**Finding:** The power calculation is actually correct by accident! But the logic is overly complex.

#### What's Actually Wrong
1. **Franking formula:** Uses confusing shift logic
2. **Non-franking case:** Uses unshifted dividend on every iteration (should shift)
3. **Temporal validation:** No check for sufficient historical data
4. **Final shift:** Shifts result by (interval-1) at the end - purpose unclear

#### Algorithm Issues (Lines 484-499)
```python
# Current approach for non-franking case
for seq in range(interval, 0, -1):
    # Uses unshifted dividend repeatedly
    temp_col = (
        (group['dividend'] + group['non_div_ecf'])  # NOT SHIFTED
        * np.power(1 + group['ke_open'], fv_interval)
        * group['scale_by']
    )
```

**Problem:** Uses current year's dividend for all 3 terms in 3Y calculation. Should use lagged values.

---

## Phase B2: Correct Formula Implementation Strategy

### New Algorithm Structure

#### Step 1: Temporal Window Validation
```python
def _validate_temporal_window(ticker_data: pd.DataFrame, interval: int) -> pd.DataFrame:
    """
    Filter rows where we have sufficient prior years of data.
    
    For 3Y: Need rows where we can look back 2 years (t, t-1, t-2)
    For 5Y: Need rows where we can look back 4 years (t, t-1, ..., t-4)
    For 10Y: Need rows where we can look back 9 years
    
    Approach:
    - Sort by fiscal_year ascending
    - Mark first (interval-1) rows as invalid (not enough history)
    - Only keep rows from position (interval-1) onwards
    """
```

#### Step 2: Year-by-Year Lookback Calculation
```python
def _calculate_fv_ecf_for_year(
    ticker_data: pd.DataFrame,
    current_row_index: int,
    interval: int,
    params: dict
) -> float:
    """
    Calculate FV_ECF for a single row using lookback approach.
    
    For interval=3 at index=5:
      - Fetch rows at indices: 5 (t), 4 (t-1), 3 (t-2)
      - Powers: 2, 1, 0
      - Use ke_open[5] (current year's prior-year KE) for all terms
      - Return: sum of (ECF_base[i] * (1 + ke_open[5])^power[i])
    
    For interval=1 at index=5:
      - Fetch row at index: 5 (t only)
      - Power: 0
      - Return: ECF_base[5] * (1 + ke_open[5])^0 = ECF_base[5]
    """
```

#### Step 3: ECF Base Calculation
```python
def _calculate_ecf_base(dividend, franking, non_div_ecf, params) -> float:
    """
    Base formula for ECF components.
    
    ECF_base = -DIVIDENDS - franking_adjustment + Non_Div_ECF
    
    Where:
      franking_adjustment = (DIVIDENDS / (1 - tax_rate)) 
                          * tax_rate 
                          * franking_credit_value 
                          * FRANKING
                          (only if incl_franking = "Yes")
    """
```

---

## Phase B3: Detailed Implementation Steps

### Step 1: Create New Helper Methods (Lines to add: ~150)

#### 1.1 `_validate_temporal_window()`
**Location:** Insert before `_calculate_fv_ecf_for_interval()`

```python
def _validate_temporal_window(
    self,
    df: pd.DataFrame,
    interval: int
) -> pd.DataFrame:
    """
    Filter DataFrame to only include rows with sufficient historical data.
    
    Args:
        df: Grouped data by ticker (already sorted by fiscal_year)
        interval: Window size (1, 3, 5, or 10)
    
    Returns:
        Filtered DataFrame with only valid rows
    
    Logic:
        - For interval N, skip first (N-1) rows per ticker
        - This ensures we have rows [t, t-1, t-2, ..., t-(N-1)]
    """
```

#### 1.2 `_calculate_ecf_base_value()`
**Location:** Insert before `_calculate_fv_ecf_for_interval()`

```python
def _calculate_ecf_base_value(
    self,
    dividend: float,
    franking: float,
    non_div_ecf: float,
    params: dict
) -> float:
    """
    Calculate single ECF_base value.
    
    ECF_base = -dividend - franking_adjustment + non_div_ecf
    """
```

#### 1.3 `_calculate_fv_ecf_single_year()`
**Location:** Insert before `_calculate_fv_ecf_for_interval()`

```python
def _calculate_fv_ecf_single_year(
    self,
    ticker_data: pd.DataFrame,
    current_idx: int,
    interval: int,
    params: dict
) -> float:
    """
    Calculate FV_ECF for single year using lookback approach.
    
    Args:
        ticker_data: Single ticker's rows (sorted by fiscal_year)
        current_idx: Current row index to calculate for
        interval: Window size (1, 3, 5, 10)
        params: Parameter dict (tax_rate, franking_cr_value, incl_franking)
    
    Returns:
        float: FV_ECF value (or NaN if insufficient data)
    
    Algorithm:
        ke_open = ticker_data.iloc[current_idx]['ke_open']
        fv_ecf = 0.0
        
        for lookback in range(0, interval):
            lookback_idx = current_idx - lookback
            
            if lookback_idx < 0:
                return NaN  # Not enough historical data
            
            row = ticker_data.iloc[lookback_idx]
            ecf_base = _calculate_ecf_base_value(
                row['dividend'],
                row['franking'],
                row['non_div_ecf'],
                params
            )
            
            power = interval - 1 - lookback
            term = ecf_base * ((1 + ke_open) ** power)
            fv_ecf += term
        
        return fv_ecf
    """
```

### Step 2: Rewrite `_calculate_fv_ecf_for_interval()` (Lines 425-524)

**Current:** 100 lines of complex shifting logic  
**New:** ~80 lines of clear year-by-year logic

```python
def _calculate_fv_ecf_for_interval(
    self,
    df: pd.DataFrame,
    interval: int,
    params: dict
) -> pd.DataFrame:
    """
    Calculate FV_ECF for specific interval (1, 3, 5, or 10 years).
    
    Uses year-by-year lookback approach (clearer, easier to verify).
    
    Returns:
        DataFrame with columns: ticker, fiscal_year, FV_ECF_Y
    """
    
    result_rows = []
    
    for ticker, group in df.groupby('ticker', sort=False):
        group = group.reset_index(drop=True)
        
        # Validate temporal window first
        valid_group = self._validate_temporal_window(group, interval)
        
        if valid_group.empty:
            continue  # No valid rows for this ticker
        
        # Calculate FV_ECF for each valid row
        for idx, row in valid_group.iterrows():
            fv_ecf = self._calculate_fv_ecf_single_year(
                group,  # Pass full group so we can look back
                idx,    # Current position in group
                interval,
                params
            )
            
            if pd.notna(fv_ecf):
                result_rows.append({
                    'ticker': ticker,
                    'fiscal_year': int(row['fiscal_year']),
                    'FV_ECF_Y': float(fv_ecf),
                    'FV_ECF_TYPE': f'{interval}Y_FV_ECF'
                })
    
    return pd.DataFrame(result_rows)
```

### Step 3: Update Data Join Logic (Optional, Lines 409-423)

**Current:** Only joins fundamentals + KE  
**Assessment:** Actually correct, since `_fetch_fundamentals_data()` already includes Non Div ECF

**Action:** Add comment documenting the 3 sources being merged

```python
def _join_data(self, fundamentals_df: pd.DataFrame, ke_df: pd.DataFrame) -> pd.DataFrame:
    """
    Join fundamentals (dividend, franking, non_div_ecf) with lagged KE.
    
    Data sources:
    1. fundamentals_df: dividend, franking (from fundamentals table)
                       + non_div_ecf (from metrics_outputs)
    2. ke_df: ke_open (prior year's Calc KE from metrics_outputs)
    
    Join: on (ticker, fiscal_year)
    """
```

---

## Phase B4: Validation & Testing Strategy

### Unit Tests for New Methods

#### Test 1: `_validate_temporal_window()`
```python
def test_validate_temporal_window_3y():
    # Create mock ticker data: years 2001-2005
    # Expect: first 2 rows filtered out, 3 rows remaining
```

#### Test 2: `_calculate_ecf_base_value()`
```python
def test_ecf_base_with_franking():
    # dividend=100, franking=0.5, non_div_ecf=50
    # tax_rate=0.30, franking_cr=0.75, incl_franking="Yes"
    # Expected = -100 - (100/(1-0.30))*0.30*0.75*0.5 + 50
```

#### Test 3: `_calculate_fv_ecf_single_year()`
```python
def test_fv_ecf_1y():
    # Single year, power=0
    # Result should be ECF_base * (1 + ke)^0 = ECF_base

def test_fv_ecf_3y():
    # 3 years of data
    # Verify powers are 2, 1, 0
    # Verify all terms use same ke_open[current]
```

### Integration Tests

#### Test 4: Full pipeline with reference data
```python
# Once user provides reference data:
# - Create test dataset with known values
# - Run FV ECF calculation
# - Compare output against Excel reference
```

---

## Implementation Checklist

### Phase B1: Code Preparation
- [ ] Review current implementation (DONE - analysis complete)
- [ ] Identify all dependencies and call sites
- [ ] Document current behavior in code comments

### Phase B2: New Methods Implementation
- [ ] Create `_validate_temporal_window()` method
- [ ] Create `_calculate_ecf_base_value()` method  
- [ ] Create `_calculate_fv_ecf_single_year()` method
- [ ] Add comprehensive docstrings with formulas
- [ ] Add inline comments explaining powers and lookback logic

### Phase B3: Core Method Refactoring
- [ ] Rewrite `_calculate_fv_ecf_for_interval()` method
- [ ] Update comments in `_join_data()` method
- [ ] Update logging in `calculate_fv_ecf_metrics()` if needed

### Phase B4: Testing
- [ ] Unit tests for each new helper method
- [ ] Integration test for all 4 intervals [1, 3, 5, 10]
- [ ] Edge case testing (missing data, NaN values, single row)
- [ ] Performance verification (should be faster than current shifting)

### Phase B5: Documentation
- [ ] Update method docstrings with correct formulas
- [ ] Add inline comments explaining key decisions
- [ ] Update IMPLEMENTATION_PLAN_FV_ECF_NON_DIV_ECF.md with implementation details
- [ ] Create test documentation with expected results

### Phase B6: Validation
- [ ] Verify output counts match expectations per interval
- [ ] Test with user's reference data (once provided)
- [ ] Compare output against Excel calculations
- [ ] Performance benchmarking

---

## Risk Assessment

### Low Risk Areas
- ✓ Data fetching (already correct)
- ✓ Batch insertion (no changes)
- ✓ Parameter loading (no changes)

### Medium Risk Areas
- ⚠️ Formula translation (complex math, easy to get powers wrong)
- ⚠️ Edge cases (missing data, temporal windows)

### High Risk Areas
- ✗ Backward compatibility (output values will change)
- ✗ Validation (need reference data to verify correctness)

### Mitigation Strategy
1. **Keep old code as reference** (comment out, don't delete)
2. **Extensive unit tests** (test each component separately)
3. **Integration tests** (test all intervals together)
4. **User validation** (compare against provided reference data)
5. **Gradual rollout** (test in isolation before production use)

---

## Estimated Effort

### By Phase
| Phase | Task | Hours | Complexity |
|-------|------|-------|-----------|
| B1 | Analysis | 0.5 | Low |
| B2 | New methods (3) | 2 | Medium |
| B3 | Refactoring | 1.5 | Medium |
| B4 | Testing | 2 | High |
| B5 | Documentation | 1 | Low |
| B6 | Validation | 2-4 | High |
| **Total** | | **9-11 hours** | |

### Critical Path
1. Implement new methods (1.5 hrs)
2. Rewrite core method (1.5 hrs)
3. Unit test all methods (1 hr)
4. Integration test (1 hr)
5. User validation with reference data (2-4 hrs)

---

## Success Criteria

1. **Code Quality**
   - [ ] New methods are <50 lines each (clarity)
   - [ ] All methods have docstrings with formulas
   - [ ] No deprecated shifting logic remains

2. **Correctness**
   - [ ] Unit tests pass for all helper methods
   - [ ] Integration tests pass for all 4 intervals
   - [ ] Output matches Excel calculations (within 0.01% tolerance)
   - [ ] Powers are correct: 1Y(0), 3Y(2,1,0), 5Y(4,3,2,1,0), 10Y(9,...,0)

3. **Data Validation**
   - [ ] Temporal windows enforced correctly
   - [ ] Row counts match: 1Y > 3Y > 5Y > 10Y (expected distribution)
   - [ ] NaN values only appear where insufficient history exists
   - [ ] No negative fiscal_year values

4. **Performance**
   - [ ] Execution time < 5 minutes for 11,000 records × 4 intervals
   - [ ] No memory leaks (monitor during batch inserts)

---

## Next Steps

1. **User Review:** Review this plan and approve approach
2. **Implementation:** Proceed with Phase B1-B3 code changes
3. **Testing:** Comprehensive unit and integration tests
4. **User Validation:** Wait for reference data, validate against Excel
5. **Deployment:** Once validated, integrate into runtime-metrics pipeline

