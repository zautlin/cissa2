# Temporal Capability Documentation Index

## Overview

This document set provides comprehensive analysis of **"temporal capability"** in CISSA - the ability to calculate metrics using rolling time-series windows across different time horizons (1Y, 3Y, 5Y, 10Y).

---

## Document Descriptions

### 1. **TEMPORAL_CAPABILITY_ANALYSIS.md** (23 KB, 698 lines)
**Comprehensive Deep Dive** - Start here for complete understanding

**Contains:**
- Executive summary of what temporal capability means
- Detailed implementation by metric type:
  - Beta (60-month rolling OLS)
  - Risk-Free Rate (12-month rolling geometric mean)
  - Cost of Equity (pre-computed combination)
  - Ratio Metrics (multi-window support)
  - Revenue & EE Growth (rolling averages)
- Complete database schema analysis
- Shared utilities and base classes
- Concrete calculation examples for each metric type
- Parameter effects on temporal calculations
- Pre-computed vs runtime metric patterns
- Summary comparison table of all metrics

**Best for:**
- Architects understanding full system design
- Developers implementing new temporal metrics
- Data engineers optimizing temporal queries
- Technical documentation and reference

**Key Sections:**
- Section 1: Definition of temporal capability
- Section 2: Metric-by-metric temporal implementation
- Section 3: Database schema for temporal data
- Section 4: Shared utilities and calculators
- Section 5: Examples of calculations at different periods
- Section 6: How parameters affect temporal calculation
- Section 7: Pre-computed vs runtime patterns
- Section 8: Summary table
- Section 9: Key takeaways

---

### 2. **TEMPORAL_CAPABILITY_QUICK_REFERENCE.md** (7.9 KB, 231 lines)
**Quick Lookup Guide** - Use for quick facts and lookups

**Contains:**
- One-line definition of temporal capability
- Metrics comparison table (window type, calculation, storage, timing)
- Core database fields reference
- Key service classes with locations
- SQL window function pattern (generic template)
- Parameter effect tables
- Pre-computed vs runtime patterns (brief)
- Temporal metadata JSON examples
- 3Y rolling MB ratio example
- API endpoint examples
- Key distinctions table
- Files to read for more details

**Best for:**
- Quick lookup while coding
- Answering "how does this metric handle time?"
- API documentation reference
- Team onboarding and quick education
- Status meetings and presentations

**Key Tables:**
- Metrics Temporal Patterns (one-line summary per metric)
- Key Service Classes (quick location reference)
- Parameter Effects (what affects temporal calculation)
- Pre-Computed vs Runtime (key differences)

---

### 3. **TEMPORAL_CAPABILITY_VISUAL_GUIDE.md** (33 KB, 451 lines)
**Visual Architecture** - Use for understanding flow and relationships

**Contains:**
- ASCII diagrams showing:
  1. Timeline of temporal data flow (ingestion to query)
  2. Rolling window sizes (visual representation of 1Y, 3Y, 5Y, 10Y)
  3. Service layer temporal routing (multi-window dispatch)
  4. Pre-computed vs runtime execution model (side-by-side)
  5. Temporal dimension in database (fundamentals vs metrics_outputs)
  6. Temporal window calculation flow (3Y revenue growth example)
  7. Metric lifecycle (raw data → user response)
  8. Parameter effect on temporal calculation
  9. Uniqueness constraint and temporal aggregation

**Best for:**
- Understanding data flow without reading code
- Presentations to stakeholders
- Whiteboarding discussions
- Visualizing complex temporal patterns
- Teaching new team members

**Key Diagrams:**
- Data flow from raw data to user response
- Rolling window size comparison
- Service routing decision tree
- Execution timeline (ingestion vs runtime)
- Table structure evolution (many rows → one row)

---

## Reading Paths

### Path 1: "I want to understand temporal capability (quick)"
1. Read QUICK_REFERENCE.md (5 min)
2. Look at the Metrics Temporal Patterns table
3. Check out a specific metric section

**Time: ~20 minutes**

---

### Path 2: "I need to implement a new temporal metric"
1. Skim ANALYSIS.md Sections 1-2 (understand the concept)
2. Read ANALYSIS.md Section 4 (shared utilities)
3. Study QUICK_REFERENCE.md Service Classes table
4. Look at source files:
   - `backend/app/services/ratio_metrics_calculator.py` (window mapping)
   - `backend/app/services/revenue_growth_calculator.py` (pattern)
5. Implement following the pattern
6. Reference ANALYSIS.md Section 5 for calculation examples

**Time: ~1-2 hours**

---

### Path 3: "I need to understand the full system architecture"
1. Start with VISUAL_GUIDE.md (understand flow)
2. Read ANALYSIS.md Section 1 (definition)
3. Read ANALYSIS.md Sections 2-3 (implementations and schema)
4. Read ANALYSIS.md Sections 6-7 (parameters and patterns)
5. Study the source code:
   - `backend/database/schema/schema.sql` (database structure)
   - `backend/app/services/beta_precomputation_service.py` (Phase 07)
   - `backend/app/services/risk_free_rate_service.py` (Phase 08)
   - `backend/app/services/ratio_metrics_calculator.py` (SQL pattern)
6. Review ANALYSIS.md Section 9 (summary)

**Time: ~3-4 hours**

---

### Path 4: "I'm debugging temporal metric issues"
1. Go to QUICK_REFERENCE.md Metrics Temporal Patterns table
2. Find your metric
3. Go to ANALYSIS.md Section 2 for detailed implementation
4. Check ANALYSIS.md Section 6 for parameter effects
5. Review ANALYSIS.md Section 5 for calculation examples
6. Check source files in quick reference guide

**Time: ~30-60 minutes**

---

### Path 5: "I'm in a presentation/meeting and need facts"
1. Use QUICK_REFERENCE.md for one-liners and tables
2. Use VISUAL_GUIDE.md Section 2 for rolling window visualization
3. Use VISUAL_GUIDE.md Section 4 for execution model comparison
4. Use ANALYSIS.md Section 8 for summary comparison table

**Time: ~10 minutes of lookup**

---

## Key Concepts Quick Summary

### What is Temporal Capability?
**Rolling window calculations across multiple fiscal years to smooth volatility and capture different trend horizons.**

### The Four Window Sizes
```
1Y = Current year only (no rolling average)
3Y = Average of current + 2 prior years
5Y = Average of current + 4 prior years
10Y = Average of current + 9 prior years
```

### Two Execution Patterns

**Pre-Computed (param_set_id = NULL)**
- Calculated at data ingestion time (once per dataset)
- Metrics: Beta, Rf, KE
- Stored permanently in metrics_outputs
- O(1) retrieval time

**Runtime (param_set_id specified)**
- Calculated on-demand when user queries
- Metrics: Ratio metrics, Revenue/EE Growth
- Not stored (in-flight calculation)
- SQL window functions with ROWS BETWEEN clause

### Core Database Dimension
**fiscal_year** - Present in every row, the temporal aggregation point

---

## Source File References

| File | Purpose | Temporal Pattern |
|------|---------|-----------------|
| `schema.sql` | Database structure | fiscal_year as core dimension |
| `beta_precomputation_service.py` | Phase 07: Beta | 60-month rolling OLS |
| `risk_free_rate_service.py` | Phase 08: Rf | 12-month rolling geometric mean |
| `cost_of_equity_service.py` | Phase 09: KE | Combines Beta + Rf |
| `ratio_metrics_calculator.py` | Ratio metric builder | Window function template |
| `revenue_growth_calculator.py` | Revenue growth | Rolling avg + growth calculation |
| `ee_growth_calculator.py` | EE growth | Same pattern as revenue growth |
| `ratio_metrics_service.py` | Orchestration | Single/multi-window routing |
| `endpoints/metrics.py` | API | Temporal window query parameter |

---

## Frequently Asked Questions

**Q: Is temporal capability real-time?**
A: No, all calculations are batch-based and historical retrospective.

**Q: What's the finest granularity?**
A: Monthly (monthly TSR data), aggregated to fiscal years for storage.

**Q: Can I calculate at arbitrary dates?**
A: No, all aggregation points align to fiscal year ends.

**Q: How many window sizes are supported?**
A: Four: 1Y (spot), 3Y, 5Y, 10Y (rolling averages).

**Q: Are metrics stored for each window?**
A: Pre-computed metrics (Beta, Rf, KE) are stored once. Runtime metrics (Ratio, Growth) are not stored.

**Q: How are parameters handled?**
A: Beta rounding and cost_of_equity_approach affect temporal calculation. Window selection is purely API-level.

**Q: What's the temporal aggregation point?**
A: fiscal_year - one row per (dataset, ticker, fiscal_year, metric) in metrics_outputs.

---

## Document Maintenance

These documents are based on codebase scan completed March 17, 2026.

**Key files analyzed:**
- 15+ service classes
- 5+ SQL window function patterns
- 3 calculator utilities
- Database schema (2 primary temporal tables)
- 25+ test files
- 1+ full ETL pipeline implementation

**Coverage:**
- All core temporal metrics (Beta, Rf, KE, Ratio, Growth)
- Both pre-computed and runtime patterns
- Parameter effects and behaviors
- Complete database schema
- API endpoints and response structures

---

## Navigation Quick Links

| Need | Document | Section |
|------|----------|---------|
| One-liner definition | QUICK_REFERENCE | Top |
| Metric comparison | QUICK_REFERENCE | Metrics Temporal Patterns table |
| Detailed metric info | ANALYSIS | Section 2 (by metric) |
| Database structure | ANALYSIS | Section 3 |
| Implementation examples | ANALYSIS | Section 5 |
| Data flow diagram | VISUAL_GUIDE | Section 1 |
| Rolling window sizes | VISUAL_GUIDE | Section 2 |
| Service routing | VISUAL_GUIDE | Section 3 |
| Execution models | VISUAL_GUIDE | Section 4 |
| Parameter effects | ANALYSIS | Section 6 |
| Pre vs Runtime | ANALYSIS | Section 7 |

