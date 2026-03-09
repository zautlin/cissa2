# PHASE 07: BETA CALCULATION - EXECUTIVE SUMMARY

**Research Completion Date:** March 9, 2026  
**Document Location:** `/home/ubuntu/cissa/.planning/PHASE_07_BETA_FINDINGS.md` (1096 lines)

---

## FINDINGS OVERVIEW

Complete analysis of beta calculation requirements reveals:

- **Data Availability:** ✅ Monthly returns data (Company TSR, Index TSR) exists in backend
- **Calculation Logic:** ⚠️ 60-month rolling OLS + 4-tier fallback partially understood
- **Infrastructure:** ⚠️ Backend service structure ready, but statsmodels not yet integrated
- **Critical Gap:** ❌ Index ticker identifier needs verification before implementation

---

## KEY FINDINGS AT A GLANCE

### 1. Legacy Implementation (Lines 1.1-1.6)
- **File:** `example-calculations/src/executors/beta.py` (104 lines)
- **Input:** Monthly Company TSR + Index TSR data
- **Calculation:** Rolling OLS (60-month window) with slope adjustment
- **Fallback:** 4-tier logic (ticker → sector → ticker_avg → NaN)
- **Output:** Beta metric with sector_slope and fallback_tier metadata

### 2. Backend Data Availability (Lines 2.1-2.4)
- **Storage:** `cissa.fundamentals` table with period_type='MONTHLY'
- **Metrics:** 
  - `Company TSR (Monthly)` - equity returns
  - `Index TSR (Monthly)` - market index returns
  - `Risk-Free Rate (Monthly)` - risk-free rates
- **Structure:** (ticker, fiscal_year, fiscal_month, fiscal_day) indexed
- **Gaps:**
  - ❌ Index ticker naming unknown (legacy: "%AS30%", backend: ?)
  - ⚠️ 60+ months per ticker not verified
  - ⚠️ Sector data completeness not verified

### 3. Backend Service Structure (Lines 3.1-3.5)
- **Service:** `EnhancedMetricsService` (406 lines)
- **Current Beta:** Stub returning 1.0 for all tickers (Line 270)
- **Pattern:** AsyncSession for fetching, batch insertion to metrics_outputs
- **Ready:** Parameter loading, data fetching, batch insertion patterns exist
- **Needs:** OLS regression implementation + 4-tier fallback logic

### 4. Parameter Handling (Lines 3.4 & 8)
- **Parameters Table:** 13 baseline parameters defined
- **Beta Parameters:**
  - `beta_rounding`: 0.1 (rounded to nearest 0.1) ✅ CLEAR
  - `beta_relative_error_tolerance`: 40.0 (stored as percentage) ⚠️ UNCLEAR
- **Issue:** Backend stores as percentage (40.0), legacy expects decimal (0.8)
- **Conversion:** Needs clarification (40.0 / 100 = 0.4 ≠ 0.8)

### 5. Calculation Gaps (Lines 4.2)
| Component | Status | Impact |
|-----------|--------|--------|
| Rolling OLS | ❌ NOT IMPLEMENTED | Critical |
| Slope adjustment (×2/3 + 1/3) | ❌ NOT IMPLEMENTED | Critical |
| Error tolerance check | ❌ NOT USED | Critical |
| 4-tier fallback | ❌ NOT IMPLEMENTED | Critical |
| Sector aggregation | ❌ NOT IMPLEMENTED | Critical |
| Ticker aggregation | ❌ NOT IMPLEMENTED | Critical |

---

## CRITICAL DECISIONS NEEDED

### Decision 1: Index Ticker Identification
**Current State:** Unknown identifier in fundamentals table  
**Legacy Used:** `TICKER LIKE '%AS30%'` pattern  
**Options:**
1. Query companies.parent_index for pattern matching
2. Search fundamentals for known index ticker patterns
3. Add flag to companies table to mark index vs. company rows

**Recommendation:** Option 2 (search fundamentals) - quick validation without schema changes

### Decision 2: Parameter Semantics
**Current State:** Backend beta_relative_error_tolerance = 40.0  
**Legacy Default:** error_tolerance = 0.8 (80% threshold)  
**Issue:** 40.0 / 100 = 0.4, but expected is 0.8

**Options:**
1. Assume backend value wrong; use: `param_value / 100` = 0.4
2. Assume backend correct; update legacy understanding to 40%
3. Query actual parameter intent from requirements document

**Recommendation:** Option 3 (clarify with requirements owner before proceeding)

### Decision 3: Data Validation Scope
**Needed Queries:**
1. Count months per ticker (need 60+ consecutive)
2. Identify index ticker(s) in fundamentals
3. Verify sector coverage in companies table
4. Check for sparse data/gaps in time series

**Recommendation:** Run before Day 1 of implementation (1 hour query set)

---

## IMPLEMENTATION ROADMAP

### Phase 07 Components (Estimated Effort)

| Component | Effort | Dependencies | Priority |
|-----------|--------|--------------|----------|
| Data validation queries | 4h | None | P0 |
| Clarify parameter semantics | 2h | Requirements owner | P0 |
| Fetch monthly returns | 8h | Data validation | P1 |
| OLS regression wrapper | 12h | statsmodels integration | P1 |
| 4-tier fallback logic | 16h | OLS wrapper | P1 |
| FY alignment & sector calc | 8h | OLS wrapper | P1 |
| Integration & testing | 16h | All above | P2 |
| Documentation | 8h | All above | P2 |
| **TOTAL** | **74 hours (~10 days)** | - | - |

### Dependency Chain
```
Data Validation (Day 1)
    ↓
Parameter Clarification (Day 1-2)
    ↓
Data Fetching & Transform (Day 2-3)
    ↓
OLS Regression (Day 3-4)
    ├─ statsmodels import
    ├─ RollingOLS wrapper
    └─ Error handling
    ↓
4-Tier Fallback (Day 4-5)
    ├─ Sector aggregation
    ├─ Ticker aggregation
    └─ Tier cascade logic
    ↓
Integration (Day 5-6)
    ├─ EnhancedMetricsService.calculate_beta()
    ├─ Async flow patterns
    └─ Parameter loading
    ↓
Testing & Documentation (Day 6-7)
```

---

## SPECIFIC IMPLEMENTATION COMPONENTS

### Required Code Changes

**1. In `requirements.txt` (Backend):**
```
statsmodels>=0.14.0  # For RollingOLS regression
```

**2. In `EnhancedMetricsService` (Lines 269-286):**
Replace stub `_calculate_beta()` with full implementation:
- `_fetch_monthly_returns()` - Query fundamentals for TSR data
- `_pivot_returns_for_ols()` - Transform to (re, rm) columns
- `_calculate_rolling_ols()` - Run statsmodels RollingOLS
- `_calculate_beta_with_fallback()` - Implement 4-tier fallback

**3. Data Query (New):**
```python
async def _fetch_monthly_returns(self, dataset_id: UUID) -> pd.DataFrame:
    """Fetch Company TSR + Index TSR from fundamentals."""
    query = text("""
        SELECT ticker, fiscal_year, fiscal_month, fiscal_day,
               metric_name, numeric_value
        FROM cissa.fundamentals
        WHERE dataset_id = :dataset_id
          AND period_type = 'MONTHLY'
          AND metric_name IN ('Company TSR (Monthly)', 'Index TSR (Monthly)')
        ORDER BY ticker, fiscal_year, fiscal_month, fiscal_day
    """)
    # ... execute and return DataFrame
```

**4. OLS Regression (New):**
```python
def _calculate_rolling_ols(self, ticker_data: pd.DataFrame, window: int = 60):
    """Run rolling OLS on (re, rm) columns."""
    from statsmodels.regression.rolling import RollingOLS
    
    # re = Company TSR / 100 + 1 (equity return)
    # rm = Index TSR / 100 + 1 (market return)
    model = RollingOLS(endog=ticker_data['rm'], 
                       exog=ticker_data['re'], 
                       window=window)
    result = model.fit()
    # Extract params (slope) and bse (std_err)
    # Calculate adjusted_slope = (slope × 2/3) + 1/3
    # Calculate rel_std_err = abs(std_err) / adjusted_slope
    # Return results DataFrame
```

**5. Fallback Logic (New):**
```python
def _calculate_beta_with_fallback(self, ticker_betas, sector_betas, 
                                   ticker_avg_betas, error_tolerance, beta_rounding):
    """4-tier fallback: ticker_slope → sector_avg → ticker_avg → NaN"""
    # For each (ticker, year):
    #   Tier 1: adjusted_slope (if rel_std_err <= error_tolerance)
    #   Tier 2: sector_slope (if Tier 1 fails)
    #   Tier 3: ticker_avg_slope (if Tier 2 fails)
    #   Tier 4: NaN (if all tiers fail)
    # Round to beta_rounding
    # Return [ticker, fiscal_year, Beta, fallback_tier]
```

---

## METRIC NAMES & QUERY PATTERNS

### Fundamentals Table Structure
```sql
SELECT * FROM cissa.fundamentals WHERE period_type = 'MONTHLY' LIMIT 5;

-- Returns (sample):
-- ticker | fiscal_year | fiscal_month | fiscal_day | metric_name              | numeric_value
-- CBA    | 1998        | 11           | 30         | Company TSR (Monthly)    | 1.5
-- AS30   | 1998        | 11           | 30         | Index TSR (Monthly)      | 1.2
```

### Metric Mapping
| Legacy | Backend | Purpose |
|--------|---------|---------|
| "Company TSR" | "Company TSR (Monthly)" | Equity returns (re) |
| "Index TSR" (where TICKER LIKE '%AS30%') | "Index TSR (Monthly)" | Market returns (rm) |
| "Rf" | "Risk-Free Rate (Monthly)" | Risk-free rate (for future phases) |

---

## VALIDATION CHECKLIST BEFORE IMPLEMENTATION

### Data Validation (Run Week 1 - Day 1)
- [ ] Query: Count months per ticker (goal: 60+)
- [ ] Query: Identify index ticker patterns in fundamentals
- [ ] Query: Verify sector coverage in companies table
- [ ] Query: Check data continuity (no gaps > 1 month)
- [ ] Query: Verify monthly data volume (min rows expected)

### Parameter Clarification (Complete Week 1 - Day 2)
- [ ] Confirm beta_relative_error_tolerance semantics (percentage vs. basis points)
- [ ] Verify legacy default conversion (0.8 vs. 40.0)
- [ ] Document parameter_set override mechanism
- [ ] Test parameter loading with sample values

### Infrastructure Readiness (Verify Week 1 - End)
- [ ] statsmodels dependency added to requirements
- [ ] EnhancedMetricsService async patterns validated
- [ ] metrics_outputs table insertion patterns tested
- [ ] Parameter loading and conversion patterns verified

---

## CRITICAL SUCCESS FACTORS

1. **Index Ticker Identification** - Must solve before starting OLS
2. **60+ Month Data Availability** - OLS requires sufficient history
3. **Sector Data Completeness** - Fallback logic depends on sector groupings
4. **Parameter Semantics** - Error tolerance must be correctly interpreted
5. **Async/Await Patterns** - Must follow backend async conventions

---

## REFERENCES & DOCUMENTATION

**Full Technical Analysis:** `/home/ubuntu/cissa/.planning/PHASE_07_BETA_FINDINGS.md`

**Sections:**
- Section 1: Legacy beta.py detailed analysis (Lines 1.1-1.6)
- Section 2: Current data availability audit (Lines 2.1-2.4)
- Section 3: Backend infrastructure analysis (Lines 3.1-3.5)
- Section 4: Gap analysis (Lines 4.1-4.4)
- Section 5: Implementation solutions (Lines 5.1-5.5)
- Section 6: Implementation challenges (Lines 6.1-6.5)
- Appendices: Detailed code references, SQL queries, data flow diagrams

**Legacy Files:**
- `/home/ubuntu/cissa/example-calculations/src/executors/beta.py` (104 lines)
- `/home/ubuntu/cissa/example-calculations/src/engine/sql.py` (lines 259-280)
- `/home/ubuntu/cissa/example-calculations/src/config/parameters.py` (lines 25-26)

**Backend Files:**
- `/home/ubuntu/cissa/backend/app/services/enhanced_metrics_service.py` (lines 20-406)
- `/home/ubuntu/cissa/backend/app/repositories/metrics_repository.py` (lines 13-175)
- `/home/ubuntu/cissa/backend/database/schema/schema.sql` (lines 162-208)
- `/home/ubuntu/cissa/backend/database/config/metric_units.json` (lines 105-121)

---

## NEXT IMMEDIATE ACTIONS

**Week 1 - Day 1:**
1. ✅ Read full findings document (Section 1-4)
2. Run data validation queries (see Validation Checklist)
3. Identify index ticker in fundamentals
4. Count months per ticker
5. Schedule parameter semantics clarification meeting

**Week 1 - Day 2:**
6. Resolve parameter semantics decision
7. Complete data validation checklist
8. Prepare implementation environment (statsmodels, testing setup)

**Week 1 - Day 3+:**
9. Begin implementation following roadmap phases
10. Reference Section 5 for implementation code templates

---

**Status:** READY FOR PHASE 07 DETAILED PLANNING & IMPLEMENTATION  
**Confidence Level:** HIGH (detailed analysis with specific line numbers)  
**Next Step:** Execute data validation queries to confirm availability
