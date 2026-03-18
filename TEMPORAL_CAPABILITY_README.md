# Temporal Capability Documentation Suite

This directory contains comprehensive documentation of CISSA's **temporal capability** - the system's ability to calculate financial metrics using rolling time-series windows across different time horizons.

## Start Here: Quick Navigation

**Choose your path based on your need:**

### If you have 10 minutes:
1. Read: `TEMPORAL_CAPABILITY_INDEX.md` - Definitions and FAQ
2. Look at: Key Concepts Quick Summary section

### If you have 20 minutes:
1. Read: `TEMPORAL_CAPABILITY_QUICK_REFERENCE.md` - One-page lookup guide
2. Scan: `TEMPORAL_CAPABILITY_VISUAL_GUIDE.md` sections 1-2

### If you have 1-2 hours:
1. Read: `TEMPORAL_CAPABILITY_ANALYSIS.md` sections 1-2
2. Study: `TEMPORAL_CAPABILITY_VISUAL_GUIDE.md` all sections
3. Reference source files from quick reference

### If you have 3-4 hours:
1. Read: Complete `TEMPORAL_CAPABILITY_ANALYSIS.md`
2. Study: Complete `TEMPORAL_CAPABILITY_VISUAL_GUIDE.md`
3. Reference: All source files linked in quick reference
4. Review: `TEMPORAL_CAPABILITY_INDEX.md` for reading paths

---

## The Four Documents

### 1. TEMPORAL_CAPABILITY_ANALYSIS.md
**A comprehensive technical reference** (23 KB, 698 lines)

What's inside:
- Complete definition and context
- 5 metric types with detailed temporal implementations
- Database schema breakdown
- Shared utilities and patterns
- 4 detailed calculation examples
- Parameter effects analysis
- Pre-computed vs runtime patterns
- Summary comparison table
- Key takeaways

Use this for:
- Understanding complete system architecture
- Implementing new temporal metrics
- Database query optimization
- Architecture reviews

---

### 2. TEMPORAL_CAPABILITY_QUICK_REFERENCE.md
**A fast lookup guide** (7.9 KB, 231 lines)

What's inside:
- One-line definition
- Metrics comparison table
- Core database fields reference
- Service classes quick index
- SQL window function template
- Parameter effect tables
- 3Y example calculation
- API endpoint examples
- Key distinctions
- Files to read for details

Use this for:
- Quick fact lookup while coding
- API documentation
- Team onboarding
- Status meetings
- Quick reference during reviews

---

### 3. TEMPORAL_CAPABILITY_VISUAL_GUIDE.md
**Architecture diagrams and flows** (33 KB, 451 lines)

What's inside:
- Data flow timeline (ingestion to query)
- Rolling window size visualization
- Service layer routing diagram
- Pre-computed vs runtime execution models
- Database table structure evolution
- Calculation flow example (3Y revenue growth)
- Metric lifecycle (7 stages)
- Parameter effect diagram
- Temporal aggregation visualization

Use this for:
- Presentations and stakeholder meetings
- Whiteboarding and discussions
- Teaching new team members
- Understanding data flow
- Visualizing temporal patterns

---

### 4. TEMPORAL_CAPABILITY_INDEX.md
**Navigation and learning paths** (This document)

What's inside:
- Document descriptions
- 5 different reading paths
- Key concepts summary
- Source file references
- Frequently asked questions
- Navigation quick links
- Document maintenance notes

Use this for:
- Choosing your learning path
- Finding specific information
- Understanding coverage
- Reference while reading

---

## One-Minute Summary

**Temporal capability** = Rolling window calculations across fiscal years

**Key points:**
- **1Y, 3Y, 5Y, 10Y windows**: Smooth volatility and capture trend horizons
- **Two patterns**:
  - Pre-computed: Beta, Rf, KE (calculated once at ingestion)
  - Runtime: Ratio metrics, Growth metrics (calculated on-demand)
- **Core database dimension**: `fiscal_year` (one row per year per metric)
- **Not real-time**: All batch-based, historical calculations

---

## Learning Paths at a Glance

| Role | Path | Time | Documents |
|------|------|------|-----------|
| **Developer** | Quick understanding + implement | 1-2h | Quick Ref + Analysis 2-4 |
| **Architect** | Full system understanding | 3-4h | All documents + source code |
| **Analyst** | Understand metric calculations | 1h | Visual Guide + Quick Ref |
| **Manager** | High-level overview | 20m | Quick Ref + Visual Guide 1-2 |
| **QA/Tester** | Debugging specific metrics | 30m | Quick Ref 2 + Analysis 5-6 |

---

## Key Files in Codebase

Referenced throughout documentation:

**Database:**
- `backend/database/schema/schema.sql` - Table structures

**Services:**
- `backend/app/services/beta_precomputation_service.py` - Phase 07
- `backend/app/services/risk_free_rate_service.py` - Phase 08
- `backend/app/services/cost_of_equity_service.py` - Phase 09
- `backend/app/services/ratio_metrics_calculator.py` - SQL templates
- `backend/app/services/revenue_growth_calculator.py` - Growth pattern
- `backend/app/services/ee_growth_calculator.py` - Growth pattern
- `backend/app/services/ratio_metrics_service.py` - Orchestration

**API:**
- `backend/app/api/v1/endpoints/metrics.py` - Query parameters

**Tests:**
- `backend/tests/test_ratio_metrics_multi_window.py` - Examples

---

## Frequently Asked Questions

**Q: What is temporal capability?**
A: The ability to calculate metrics using rolling windows (1Y, 3Y, 5Y, 10Y) across fiscal years.

**Q: Is it real-time?**
A: No, all calculations are batch-based and historical.

**Q: What's the finest granularity?**
A: Monthly (monthly TSR data), aggregated to fiscal years for storage.

**Q: What window sizes are supported?**
A: Four: 1Y (spot), 3Y, 5Y, 10Y (rolling averages).

**Q: Are all metrics stored?**
A: Pre-computed metrics (Beta, Rf, KE) are stored. Runtime metrics (Ratio, Growth) are not.

**Q: What affects temporal calculation?**
A: Window selection, parameters (rounding, approach), and metric type.

**Q: What's the core database dimension?**
A: fiscal_year - one row per (dataset, ticker, fiscal_year, metric).

---

## Quick Reference Tables

### Metrics at a Glance

| Metric | Window | Timing | Storage | Granularity |
|--------|--------|--------|---------|-------------|
| Beta | 60-month rolling OLS | Pre-computed | Stored | Monthly → Annual |
| Calc Rf | 12-month rolling geometric | Pre-computed | Stored | Monthly → Annual |
| Calc KE | Combines Beta + Rf | Pre-computed | Stored | Annual |
| Ratio Metrics | Dynamic 1Y/3Y/5Y/10Y | Runtime | Not stored | Annual |
| Revenue Growth | Dynamic 1Y/3Y/5Y/10Y | Runtime | Not stored | Annual |
| EE Growth | Dynamic 1Y/3Y/5Y/10Y | Runtime | Not stored | Annual |
| L2 Metrics | Multi-period | Pre-computed | Stored | Annual |

### Execution Patterns

| Pattern | Pre-Computed | Runtime | Hybrid |
|---------|--------------|---------|--------|
| **When** | Ingestion | Query time | Ingestion + Query |
| **Metrics** | Beta, Rf, KE | Ratio, Growth | Cost of Equity |
| **Calculation** | Once per dataset | On-demand | Pre-computed inputs |
| **Storage** | Permanent | Not stored | New metrics_outputs |
| **Speed** | O(1) lookup | 0.5-5 seconds | Very fast |

---

## Document Statistics

- **Total size**: 64 KB
- **Total lines**: 1,380
- **Diagrams**: 9 major ASCII diagrams
- **Tables**: 15+ comparison tables
- **Code examples**: 20+ SQL/Python examples
- **Learning paths**: 5 different paths
- **Metrics analyzed**: 7 complete implementations
- **Service classes**: 6+ detailed breakdowns
- **Database tables**: 2 primary temporal tables

---

## Using These Documents

### For Architecture Reviews
- Start with VISUAL_GUIDE.md
- Reference ANALYSIS.md sections 2-3
- Use QUICK_REFERENCE.md Section 8 for comparison table

### For Code Implementation
- QUICK_REFERENCE.md for service class locations
- ANALYSIS.md Sections 4-5 for patterns and examples
- Source files linked in quick reference

### For Team Onboarding
- QUICK_REFERENCE.md for quick facts
- VISUAL_GUIDE.md for understanding flows
- INDEX.md reading path for learner's level

### For Documentation/Wiki
- All 4 documents are markdown
- Copy directly to wiki or GitHub
- Use INDEX.md as landing page

---

## Coverage Summary

**What's covered:**
- All core temporal metrics (Beta, Rf, KE, Ratio, Growth)
- Both pre-computed and runtime execution patterns
- Complete database schema for temporal data
- Parameter effects and configurations
- SQL window function patterns
- Service layer architecture
- API endpoints and responses
- Examples and calculation flows

**What's out of scope:**
- Real-time data processing (not applicable)
- Intraday or sub-monthly granularity (not supported)
- Optimization algorithms (separate module)
- Machine learning components (separate module)

---

## Maintenance Notes

**Created:** March 17, 2026
**Based on:** Complete codebase analysis
**Scope:** Temporal capability across all metrics and modules

**Key files analyzed:**
- 15+ service classes
- 5+ SQL window function patterns
- Database schema.sql
- 25+ test files
- API endpoints

**Update frequency:** As temporal capabilities change

---

## Next Steps

1. **Choose your reading path** in TEMPORAL_CAPABILITY_INDEX.md
2. **Start with the document** for your role/need
3. **Reference QUICK_REFERENCE.md** as you work
4. **Check source files** linked in quick reference
5. **Use VISUAL_GUIDE.md** for architecture discussions

---

## Questions or Feedback?

These documents are designed to be comprehensive yet accessible. Each reading path takes a different approach:
- **Quick reference**: One-page lookup
- **Visual guide**: Diagrams and flows  
- **Comprehensive analysis**: Complete deep-dive
- **Index guide**: Navigation and learning paths

Choose what works for you!

