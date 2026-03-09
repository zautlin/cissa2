# STATE.md — Phase 06 Technical State

**Current Status:** Execution Phase (Task 02 Complete)  
**Last Updated:** 2026-03-09 (Task 02 completion)  
**Project:** CISSA Financial Data Pipeline

---

## Key Technical Facts

### Metrics Calculation Strategy
- **Architecture:** PostgreSQL stored procedures (pure SQL)
- **Current state:** 7/12 L1 metrics implemented (simple metrics only)
- **Missing:** 5 temporal metrics require window functions
- **Approach:** No circular dependencies (fytsr is INPUT, not calculated)

### Critical Discovery: fytsr is INPUT Data
```
Legacy code (line 87):
  ecf = row['LAG_MC'] * (1 + row["fytsr"] / 100) - row['C_MC']
  
Analysis:
  - fytsr comes from fundamentals table (Bloomberg input data)
  - NOT a calculated metric
  - Eliminates circular dependency between ECF and FY_TSR
  - Pure SQL solution is feasible
```

**Impact:** ECF formula uses historical fytsr as-is; no recalculation needed.

---

## Current Implementation Status

### Simple Metrics (7/7 COMPLETE)
| Metric | Status | Location | Output Count |
|--------|--------|----------|--------------|
| C_MC | ✅ DONE | functions.sql | 11,000 |
| C_ASSETS | ✅ DONE | functions.sql | 11,000 |
| OA | ✅ DONE | functions.sql | 11,000 |
| OP_COST | ✅ DONE | functions.sql | 11,000 |
| NON_OP_COST | ✅ DONE | functions.sql | 11,000 |
| TAX_COST | ✅ DONE | functions.sql | 11,000 |
| XO_COST | ✅ DONE | functions.sql | 11,000 |

**Total:** 77,000 records in metrics_outputs

### Temporal Metrics (0/5 MISSING)
| Metric | Status | Blocker | Requires |
|--------|--------|---------|----------|
| ECF | ❌ MISSING | Window function + inception logic | LAG_MC, fytsr, companies.begin_year |
| NON_DIV_ECF | ❌ MISSING | Depends on ECF | ECF + DIVIDENDS |
| EE | ❌ MISSING | Cumulative sum window function | Inception logic, ECF |
| FY_TSR | ❌ MISSING | Complex params + window function | LAG_MC, parameters, parameter_sets |
| FY_TSR_PREL | ❌ MISSING | Depends on FY_TSR | FY_TSR |

**Total:** 0 records (need to create 55,000+ rows)

### API/Service Integration (7/12 COMPLETE)
| Task | Status | Location |
|------|--------|----------|
| METRIC_FUNCTIONS mapping | ⚠️ PARTIAL | services/metrics_service.py |
| Temporal metrics in mapping | ❌ MISSING | Add ECF, NON_DIV_ECF, EE, FY_TSR, FY_TSR_PREL |
| Parameter set resolution | ⚠️ PARTIAL | Needs franking parameters |
| Batch insert | ✅ DONE | Uses 1000/batch size |

### Configuration (20/31 COMPLETE)
| Component | Status | Count |
|-----------|--------|-------|
| metric_units.json (input) | ✅ DONE | 20 entries |
| metric_units.json (output) | ❌ PARTIAL | 2/12 defined (C_MC, FY_TSR) |
| parameters table | ✅ PARTIAL | 13 baseline parameters; missing franking-specific |
| parameter_sets | ⚠️ CONFIGURED | "base_case" exists, but param_overrides needs franking |

---

## Database Schema State

### Key Tables
| Table | Rows | Key Indexes | Status |
|-------|------|------------|--------|
| companies | ~1000 | ticker, sector, country | ✅ Ready; begin_year sometimes NULL ⚠️ |
| fundamentals | ~187k | dataset_id, ticker, metric_name, fiscal_year | ✅ Ready; has fytsr input data |
| metrics_outputs | 77k | dataset_id, param_set_id, ticker, fiscal_year, output_metric_name | ⚠️ Partial (7/12 metrics) |
| parameters | 13 | parameter_name | ✅ Ready; needs franking entries |
| parameter_sets | 1 | is_default, is_active | ✅ "base_case" exists |
| metric_units | 20 | metric_name | ⚠️ Partial (20/31) |

### Critical Constraints
| Constraint | Table | Status | Issue |
|-----------|--------|--------|-------|
| NOT NULL on begin_year | companies | ❌ MISSING | NULL inception years will break temporal metrics |
| UNIQUE | metrics_outputs | ✅ OK | (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name) enforced |

---

## Known Issues & Gotchas

### Issue 1: begin_year NOT NULL Constraint Missing
**Severity:** MEDIUM  
**Impact:** Inception logic breaks if companies.begin_year is NULL  
**Status:** Identified in feasibility analysis  
**Fix:** Add NOT NULL constraint: `ALTER TABLE companies ADD CONSTRAINT chk_begin_year_not_null CHECK (begin_year IS NOT NULL)`  
**Timeline:** Task 3, Day 4

### Issue 2: Year Gaps in Fiscal Years
**Severity:** HIGH (data quality)  
**Impact:** LAG(C_MC) shifts incorrectly if ticker missing data for certain years  
**Example:** Company has years [2015, 2016, 2017, 2020, 2021] → LAG(2020) incorrectly points to 2017 instead of closest valid year  
**Current state:** Not detected; legacy Python handles row-by-row but SQL window function doesn't care  
**Detection:** Use `fiscal_year - ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year)` to find gaps  
**Fix:** Document warning in function comments; test with sample gap data

### Issue 3: Parameter Sensitivity in FY_TSR
**Severity:** MEDIUM (expected behavior)  
**Impact:** Same (ticker, fiscal_year) produces different FY_TSR values for different parameter_sets  
**Status:** By design (metrics_outputs UNIQUE allows this per param_set_id)  
**Gotcha:** Queries MUST filter by param_set_id or get multiple rows  
**Fix:** Document in API spec; add example queries

### Issue 4: NUMERIC Precision Over 60+ Years
**Severity:** LOW  
**Impact:** EE cumulative sum accumulates rounding errors over 60 years of data  
**Status:** Expected but manageable  
**Mitigation:** Use NUMERIC (not FLOAT); round to 2 decimals if needed  
**Testing:** Compare cumsum to Python reference; log acceptable error threshold

### Issue 5: Franking Parameters Not in Database
**Severity:** MEDIUM  
**Impact:** FY_TSR calculation can't apply franking adjustments  
**Status:** ✅ RESOLVED (Task 02 Complete) — All parameters already exist in database  
**Resolution:** Task 02 research confirmed:
  - `include_franking_credits_tsr` (BOOLEAN, default: 'false')
  - `tax_rate_franking_credits` (NUMERIC, default: '30.0')
  - `value_of_franking_credits` (NUMERIC, default: '75.0')
  - Documented in PARAMETER_MAPPING.md with legacy code mapping and query patterns
**Defaults:** Australian tax defaults confirmed (30% tax rate, 75% franking credit value)
**Documentation:** PARAMETER_MAPPING.md (447 lines) created with complete parameter mapping

### Issue 6: metric_units.json Missing 11 Entries
**Severity:** LOW  
**Impact:** API responses lack unit metadata for 11 L1 output metrics  
**Status:** Identified in code review  
**Fix:** Add all 11 to metric_units.json during Task 1

---

## Dependency Decisions

### Decision 1: Pure SQL vs. Hybrid Python
**Choice:** Pure SQL (PostgreSQL stored procedures)  
**Rationale:**
- Circular dependency between ECF and FY_TSR resolved (fytsr is input)
- Window functions (LAG, SUM OVER) are native PostgreSQL
- Performance: 100-1000x faster than Python row-by-row
- All 12 metrics calculable in single function call

**Not chosen:** Hybrid (Python for ECF, SQL for others)  
- Complexity: Two implementations to maintain
- Performance: Python slower; defeats purpose
- Risk: Data sync issues between layers

### Decision 2: Parameter Structure (JSONB vs. normalized tables)
**Choice:** JSONB param_overrides in parameter_sets table  
**Rationale:**
- Flexible structure (different param_sets have different parameters)
- Query-friendly (WHERE ... ->> operator)
- Single parameter_sets row per scenario
- Example: `{"incl_franking": "Yes", "frank_tax_rate": 0.30, "value_franking_cr": 0.75}`

**Not chosen:** Normalized parameter_set_parameters table  
- Overhead: Extra join for each query
- Complexity: 3 tables instead of 2

### Decision 3: Batch Calculation (one query vs. individual)
**Choice:** Batch calculation (single SQL function returns all 12 metrics)  
**Rationale:**
- Window functions naturally process all rows at once
- Single function call replaces 12 individual calls
- Transaction consistency: All metrics insert together or none
- Performance: 10-20 seconds for 132,000 records vs. 60+ seconds row-by-row

**Not chosen:** Individual function calls  
- N+1 problem: 12 separate queries
- Window function redundancy: Re-sorts data for each metric

---

## Technical Debt & Risks

| Risk | Severity | Mitigation | Owner |
|------|----------|-----------|-------|
| **Year gaps in LAG** | HIGH | Detect; document; test with gap data | Task 3 |
| **NULL begin_year** | MEDIUM | Add NOT NULL constraint; validate data | Task 3 |
| **Franking params undefined** | MEDIUM | Research Australian tax defaults; Task 2 | Task 2 |
| **Precision drift (EE)** | LOW | Test cumsum vs. Python; acceptable tolerance | Task 4 |
| **Missing unit definitions** | LOW | Add to metric_units.json | Task 1 |
| **Parameter sensitivity confusion** | MEDIUM | Document in API spec; examples | Task 4 |

---

## Testing Strategy

### Unit Test Framework
- **File:** `backend/tests/test_l1_metrics.py`
- **Coverage:** All 12 SQL functions
- **Approach:** Compare SQL output to legacy Python reference

### Test Categories
1. **Simple metrics** (7 tests)
   - Sample 10 (ticker, fiscal_year) pairs
   - Compare to legacy Python output
   - Verify NUMERIC precision

2. **Temporal metrics** (5 tests)
   - LAG_MC: First year NULL, subsequent years correct
   - ECF: NULL for inception year, correct formula after
   - NON_DIV_ECF: NULL propagation correct
   - EE: Cumulative sum correct; reset per ticker
   - FY_TSR: Matches legacy formula; parameter sensitivity tested

3. **Edge cases** (5 tests)
   - Year gaps: Verify LAG behavior documented
   - NULL inception year: Graceful handling
   - Zero LAG_MC: FY_TSR returns NULL
   - Division by zero: Handled in CASE statement
   - Large dataset: Performance < 2 seconds for 132k rows

### Verification Against Legacy
```python
# Pseudocode: compare SQL to Python
for ticker, year in sample_pairs:
    sql_result = query_metric_from_sql(ticker, year)
    python_result = legacy_calculate_metric(ticker, year)
    assert abs(sql_result - python_result) < 0.01  # 2 decimal places
```

---

## Performance Baselines

### Expected Performance
| Operation | Dataset Size | Expected Time | Status |
|-----------|--------------|---------------|--------|
| Single metric function (C_MC) | 11,000 | < 500ms | ✅ Known good |
| All 7 simple metrics | 77,000 | 2-3s | ✅ Known good |
| All 12 metrics (with 5 temporal) | 132,000 | 5-10s | ⚠️ To be verified |
| Batch insert (1000/batch) | 132,000 | 10-20s | ⚠️ To be verified |

### Indexes Needed
- `idx_fundamentals_dataset_ticker_fy` (exists)
- `idx_fundamentals_ticker_metric_fy` (exists)
- `idx_metrics_outputs_ticker_fy` (exists)
- `idx_companies_ticker` (exists)

---

## Data Availability & Quality

### Input Data Status
| Data | Source | Status | Quality |
|------|--------|--------|---------|
| SPOT_SHARES, SHARE_PRICE | fundamentals | ✅ Complete | 11,000/11,000 |
| REVENUE, OPERATING_INCOME, etc. | fundamentals | ✅ Complete | 95%+ coverage |
| **fytsr** | fundamentals | ✅ Complete | INPUT data |
| DIVIDENDS | fundamentals | ✅ Complete | ~95% coverage |
| companies.begin_year | companies | ⚠️ PARTIAL | Some NULL ⚠️ |

### Assumed Data Characteristics
- 1000 companies × 10-20 fiscal years average = ~11,000 ticker-year combinations
- Metrics aligned to fiscal years (monthly data not used for L1)
- No major gaps in years (except identified year gap issue)

---

## Version Control & Git History

### Recent Commits
- Phase 05 complete: Renamed L2 metrics (✅)
- Phase 04 complete: Auto-trigger L1 metrics (✅)
- Phase 03: Imputation cascade (✅)

### Current Branch
- Working branch: (TBD during execution)
- Main branch: Latest phases committed
- Uncommitted changes: None (planning phase only)

---

## Next Steps (Execution Readiness)

✅ **Ready to start Phase 06 when:**
1. This STATE.md reviewed and confirmed
2. REQUIREMENTS.md and ROADMAP.md approved
3. Project stakeholder signs off on 12-day timeline
4. Developer ready to execute 4 tasks (Days 1-12)

⚠️ **Blockers identified:**
- Companies.begin_year needs NOT NULL constraint (minor, fixable Day 4)
- Franking parameters need definition (Task 2, Days 1-2)
- Year gap mitigation needs documentation (Task 1, Days 1-3)

All blockers have clear mitigation; no show-stoppers.
