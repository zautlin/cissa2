# Beta Rounding Sensitivity Analysis - Document Index

**Analysis Date:** March 16, 2026  
**Status:** COMPLETE  
**Scope:** Comprehensive sensitivity analysis of Beta rounding parameter in CISSA  
**Confidence Level:** HIGH (based on code review + mathematical analysis)

---

## Documents Included

### 1. BETA_SENSITIVITY_ANALYSIS.md (823 lines, 25KB)
**Complete comprehensive analysis with all technical details**

**Contents:**
- Executive summary with key findings
- Current rounding configuration (formula, strategy, examples)
- Impact analysis (locations, ranges, variations, sensitivity)
- Downstream effects on KE calculations
- Quantitative impact analysis (3 scenarios)
- Specific examples with actual Beta values
- Recommendations
- Sensitivity dashboard metrics
- Detailed conclusions

**Best for:** Technical deep-dive, code review, architectural decisions

**Key Sections:**
- Section 2: Exact line numbers where Beta is rounded (641, 741, 877)
- Section 3: KE sensitivity analysis with tables
- Section 4: Quantitative scenarios (0.1→0.01, no rounding, 0.1→0.2)
- Section 5: Real examples from codebase

---

### 2. BETA_ROUNDING_SUMMARY.txt (303 lines, 13KB)
**Executive summary for stakeholders and managers**

**Contents:**
- Current configuration summary
- All 3 rounding locations with line numbers
- Quantitative impact tables
- Most sensitive components (ranked)
- Scenario analysis
- Impact summary table
- Recommendations section
- Key findings (5 main findings)
- Technical references
- Quick reference for rounding changes

**Best for:** Management presentations, stakeholder updates, decision-making

**Key Sections:**
- Section 7: Impact summary table (severity × max change)
- Section 8: Primary recommendation (keep 0.1)
- Section 10: 5 key findings
- Section 12: Quick reference comparison table

---

### 3. BETA_ROUNDING_QUICK_REFERENCE.txt (199 lines, 19KB)
**One-page reference card for operations and support**

**Contents:**
- Current setting box
- Rounding errors summary
- Where rounded (3 locations)
- Sensitivity ranking (4 levels)
- Cost of Equity impact table
- Real example (BHP AU Equity)
- Scenario analysis (3 alternatives)
- Critical thresholds
- Monitoring checklist
- Decisions & actions
- Impact summary table
- References

**Best for:** Daily operations, monitoring setup, quick lookups

**Use Cases:**
- Help desk reference
- Operations dashboard setup
- Daily monitoring checklist
- Alert thresholds
- Decision trees

---

## Quick Navigation

### For Different Audiences:

**Executive Leadership:**
→ Read: BETA_ROUNDING_SUMMARY.txt (Sections 1, 7, 8)  
→ Time: 10 minutes  
→ Focus: Impact magnitude, recommendation, cost-benefit

**Technical Team:**
→ Read: BETA_SENSITIVITY_ANALYSIS.md (Full document)  
→ Time: 45 minutes  
→ Focus: Implementation details, code locations, scenarios

**Operations/Support:**
→ Read: BETA_ROUNDING_QUICK_REFERENCE.txt  
→ Time: 5 minutes  
→ Focus: Monitoring checklist, alert thresholds, reference cards

**Risk Management:**
→ Read: BETA_SENSITIVITY_ANALYSIS.md (Sections 3, 4, 6, 7)  
→ Time: 30 minutes  
→ Focus: Sensitivity analysis, threshold risks, fallback logic

---

## Key Findings Summary

### 1. Current Configuration
- Parameter: `beta_rounding = 0.1`
- Location: `cissa.parameters` table
- Effect: Rounds Beta to nearest 0.1 increment
- Possible values: {0.6, 0.7, 0.8, ..., 2.0} = 15 discrete values

### 2. Rounding Error Magnitude
- Individual Beta: ±0.05 (±5% at typical values)
- Sector Slope: ±0.03 (compounded from averaging)
- KE Impact: ±0.25% (at 5% risk premium)
- Large-cap Valuation: ±$2.5B per $100B market cap

### 3. Three Rounding Locations
1. **Line 641** - Slope transformation (PRIMARY)
2. **Line 741** - Sector average (COMPOUNDS)
3. **Line 877** - Floating beta (STEP FUNCTION)

### 4. Sensitivity Ranking
1. **Floating Beta** - VERY HIGH (step function, stickiness)
2. **Sector Average** - HIGH (compounds errors)
3. **Fixed Approach** - MODERATE (single rounding)
4. **Transformation** - LOW (built-in mean reversion)

### 5. Recommendation
**PRIMARY:** Keep beta_rounding = 0.1
- Clear communication
- Acceptable precision
- Matches legacy system
- KE error < 0.3% typically

**ALTERNATIVE:** Consider 0.05 (test first)
- 50% error reduction
- 2x more values (harder to manage)

**DO NOT:** Remove rounding or increase to 0.2

---

## Critical Thresholds to Monitor

### Tier 2 Fallback Activation
- **Trigger:** When Tier 1 rejected due to high error
- **Risk:** All 5-30 companies in sector receive biased slope
- **Alert:** If Tier 2 > 30% of companies

### Floating Beta Stickiness
- **Observation:** Beta gets stuck at rounded boundary
- **Duration:** Can last 3+ consecutive years
- **Expected:** Step function behavior
- **Alert:** If same rounded value > 3 years

### Sector Slope Volatility
- **Measurement:** Sector average rounding error
- **Typical:** ±3% (from individual ±5% errors)
- **Alert:** If sector slope changes > 5% year-over-year

---

## Implementation Locations (Code References)

**Main File:** `/home/ubuntu/cissa/backend/app/services/beta_calculation_service.py`

| Location | Line | Function | Effect | Sensitivity |
|----------|------|----------|--------|-------------|
| Transformation | 641 | `_transform_slopes()` | Primary rounding | Foundation |
| Sector Average | 741 | `_generate_sector_slopes()` | Compounds error | HIGH |
| Floating Beta | 877 | `_apply_approach_to_ke()` | Step function | VERY HIGH |

**Related Files:**
- KE Calculation: `cost_of_equity_service.py` (line 297)
- Schema: `schema.sql` (line 420)
- Tests: `test_beta_calculation.py`

---

## Scenario Comparison

| Scenario | Error | Values | Communication | Status |
|----------|-------|--------|-----------------|--------|
| Current (0.1) | ±0.05 | 15 | Clear | ✓ RECOMMENDED |
| Finer (0.01) | ±0.005 | 140 | Complex | Test first |
| Coarser (0.2) | ±0.1 | 8 | Very simple | NOT REC |
| No rounding | 0 | ∞ | Confusing | NOT REC |

**Recommendation:** Keep 0.1, test 0.05 if precision becomes priority

---

## Cost of Equity (KE) Sensitivity

**Formula:** KE = Rf + Beta × RP

**At 5% Risk Premium:**
- Beta ±0.01 → KE ±0.05% (negligible)
- Beta ±0.05 → KE ±0.25% (noticeable)
- Beta ±0.10 → KE ±0.50% (material)
- Beta ±0.20 → KE ±1.00% (significant)

**Real Example (BHP AU Equity):**
- Raw Beta: 0.8647
- Rounded: 0.9 (+3.9% error)
- KE increase: 8.78% → 9.00% (+0.22%)
- Valuation impact: ~2.5% on $100B+ market cap

---

## Monitoring Checklist

### Daily
- [ ] Max/min Beta rounding error across portfolio
- [ ] Tier distribution (% T1/T2/T3)
- [ ] Alert if Tier 2 > 30% or any error > 5%

### Weekly
- [ ] Floating beta stickiness (consecutive same value)
- [ ] Sector slope changes (> 5%)
- [ ] KE range (min to max)

### Monthly
- [ ] Portfolio KE stability (std deviation)
- [ ] Sector-by-sector impact analysis
- [ ] Floating beta convergence rate
- [ ] Fallback tier transition frequency

---

## Document Usage Guide

```
START HERE:
├─ Quick question? 
│  └─ Read: BETA_ROUNDING_QUICK_REFERENCE.txt (5 min)
│
├─ Need to brief management?
│  └─ Read: BETA_ROUNDING_SUMMARY.txt Section 7-8 (10 min)
│
├─ Implementing monitoring?
│  └─ Read: BETA_ROUNDING_QUICK_REFERENCE.txt Section 9 (5 min)
│
├─ Code review?
│  └─ Read: BETA_SENSITIVITY_ANALYSIS.md Section 2 (15 min)
│
├─ Full technical understanding?
│  └─ Read: BETA_SENSITIVITY_ANALYSIS.md Complete (45 min)
│
└─ Decision on parameter change?
   └─ Read: BETA_SENSITIVITY_ANALYSIS.md Section 4-6 (30 min)
```

---

## Key Takeaways

1. **Current setting is appropriate** - 0.1 rounding balances precision with communication
2. **Rounding error is measurable** - ±0.05 individual, ±0.25% KE impact
3. **Sector fallback most sensitive** - Monitor Tier 2 activation (>30% alert)
4. **Floating beta exhibits step function** - Expected behavior, gets stuck at boundaries
5. **Large-cap impact is material** - ±$2.5B per $100B market cap
6. **Monitor not change** - Current setting optimal, consider 0.05 only if precision critical

---

## Related Documentation

- **Phase 07 Beta Implementation:** `.planning/PHASE_07_BETA_FINDINGS.md`
- **Quick Reference Guide:** `QUICK_REFERENCE.md`
- **Backend README:** `backend/README.md`
- **Schema Documentation:** `backend/database/schema/schema.sql`

---

## Report Metadata

| Item | Value |
|------|-------|
| Generated | 2026-03-16 |
| Author | Analysis System |
| Status | COMPLETE |
| Confidence | HIGH |
| Review Cycle | Quarterly |
| Last Updated | 2026-03-16 |

---

## Next Steps

1. **Immediate:** Review BETA_ROUNDING_SUMMARY.txt (management)
2. **This Week:** Implement monitoring checklist from quick reference
3. **This Month:** Review code locations (developers)
4. **This Quarter:** Monitor key metrics, prepare dashboard
5. **Next Quarter:** Quarterly sensitivity review

---

**For questions or updates, refer to the full BETA_SENSITIVITY_ANALYSIS.md document.**

