# CISSA Planning Documentation

**Last Updated:** March 9, 2026  
**Current Phase Status:** Phase 04-05 complete, planning alignment with legacy metrics

---

## 📋 Four Essential Documents

### 1. **LEGACY_METRICS_COMPLETE.md** ⭐ START HERE
**Complete inventory of all metrics in the legacy system**

Contains:
- 📊 Comprehensive metrics inventory (7 tiers)
- ✅ Tier 1: L1 Basic Metrics (12 implemented, 5 temporal missing)
- ✅ Tier 2: L2 Derived Metrics (6 implemented)
- ❌ Tier 3: Aggregated Ratios (14 metrics × 4 intervals = 56 missing)
- ❌ Tier 4: Beta Calculation (1 missing)
- ❌ Tier 5: Risk-Free Rate & Market Returns (2 missing)
- ❌ Tier 6: Sector Aggregations (missing)
- 🐛 Known bugs in legacy code

**Use this to understand what needs to be migrated and in what priority.**

---

### 2. **SYSTEM_STATE_REVIEW.md**
**Current state of backend architecture**

Contains:
- ✅ What's already done (Phase 04-05)
- ❌ What still needs migration (Beta, Rates, TSR, Sector, temporal metrics)
- 📊 Architecture overview (FastAPI + PostgreSQL)
- 🗂️ Code organization and file structure

**Reference this to understand current backend capabilities.**

---

### 3. **PROCESS_CHANGES_ANALYSIS.md**
**Key architectural decisions made in Phase 04-05**

Contains:
- 🔧 Decision 1: Auto-trigger L1 metrics at ingestion end
- ♻️ Decision 2: Rename L2 metrics (removed L2_ prefix)
- 📐 Decision 3: L1 vs L3 ROA difference analysis

**Reference for understanding recent changes and why they were made.**

---

### 4. **README.md** (this file)
**Documentation index and navigation guide**

---

## 🎯 Quick Start: Align Backend with Legacy

1. **Understand what exists** (5 min)
   - Read LEGACY_METRICS_COMPLETE.md → Summary section
   - See what's implemented vs. missing

2. **Choose your priorities** (10 min)
   - Decide which metrics tier(s) to implement
   - Reference LEGACY_METRICS_COMPLETE.md → Questions section
   - Ask yourself: Do I need temporal metrics? Aggregated ratios? Beta? Rates? Sector?

3. **Review current state** (5 min)
   - Skim SYSTEM_STATE_REVIEW.md to understand backend structure
   - Skim PROCESS_CHANGES_ANALYSIS.md to understand recent decisions

4. **Plan implementation** (decide next phase)
   - Wait for user to specify metrics priorities
   - Create phase plans for chosen metrics

---

## 🏗️ Current Architecture

Your system has multiple metric levels:

```
Phase 1 (DONE) ✅
├─ 15 SQL functions in PostgreSQL
├─ Calculate L1 core metrics (MC, Op Assets, Costs, Ratios)
├─ Auto-triggered at end of data ingestion
└─ Stored in: metrics_outputs table

Phase 2 (DONE) ✅
├─ L2 metrics (6 metrics)
├─ Derived from L1 using Python service
├─ API: POST /api/v1/metrics/calculate-l2
└─ Stored in: metrics_outputs table with metadata

Phase 3 (PLANNING) 🔄
├─ Temporal L1 metrics (ECF, EE, FY_TSR, FY_TSR_PREL) ← Missing
├─ Aggregated ratios (14 metrics × 4 intervals) ← Missing
├─ Beta calculation ← Missing
├─ Risk-Free Rate & Market Returns ← Missing
├─ Sector aggregations ← Missing
└─ TBD: Which to implement?
```

---

## 📁 Documentation Files

**In .planning/ directory:**
- `.planning/README.md` — This file
- `.planning/LEGACY_METRICS_COMPLETE.md` — Master metrics reference ⭐
- `.planning/SYSTEM_STATE_REVIEW.md` — Current backend state
- `.planning/PROCESS_CHANGES_ANALYSIS.md` — Phase 04-05 decisions

**Phase directories:**
- `.planning/phases/04-auto-trigger-l1/` — Phase 04 (completed)
  - `04-01-PLAN.md` — Phase plan
  - `04-01-SUMMARY.md` — Execution summary
  
- `.planning/phases/05-rename-l2-metrics/` — Phase 05 (completed)
  - `05-01-PLAN.md` — Phase plan
  - `05-01-SUMMARY.md` — Execution summary

---

## 💾 Codebase Structure

**Backend Services:**
- `backend/app/services/metrics_service.py` — L1 metrics calculation (Phase 04-05)
- `backend/app/services/l2_metrics_service.py` — L2 metrics derivation (Phase 05)
- `backend/app/services/enhanced_metrics_service.py` — L3 metrics (Beta, Rates, Cost of Equity)
- `backend/app/api/v1/endpoints/metrics.py` — API endpoints

**Database:**
- `backend/database/schema/functions.sql` — 15 L1 metric SQL functions
- `backend/database/schema/schema.sql` — Table definitions

**Legacy Sources (to migrate from):**
- `example-calculations/src/executors/metrics.py` — L1 metrics (15 basic + temporal)
- `example-calculations/src/executors/beta.py` — Beta calculation
- `example-calculations/src/executors/rates.py` — Risk-free rate & market returns
- `example-calculations/src/generate_sector_metrics.py` — Sector aggregations
- `example-calculations/src/engine/aggregators.py` — Aggregated ratio metrics

---

## ❓ What to Do Next

**Option 1: Plan Phase 06 (Implement missing metrics)**
- Decide which metrics from LEGACY_METRICS_COMPLETE.md you need
- I'll create executable phase plans
- Execute phases to migrate the metrics

**Option 2: Continue with current system**
- Current Phase 04-05 deliverables are complete
- L1 basic metrics + L2 derived metrics working
- Legacy metrics not yet migrated (optional)

---

## 🧹 Recent Changes

**March 9, 2026 - Codebase Cleanup**
- ✅ Removed 10 outdated/superseded documentation files
- ✅ Kept 4 active reference documents
- ✅ Created LEGACY_METRICS_COMPLETE.md for comprehensive metrics inventory
- ✅ Updated README.md to reflect current state

**Files deleted (outdated):**
- INVESTIGATION.md, L1_METRICS_VERIFICATION.md, PHASE1_METRICS.md
- PHASE3_IMPLEMENTATION_SUMMARY.md, PHASE3_MIGRATION_PLAN.md, PHASE3_NEXT_STEPS.md
- PHASE3_OUTPUT_EXAMPLE.md, STEP_2_RISK_FREE_RATE_ANALYSIS.md
- PARAMETER_MAPPING.md, MIGRATION_EXAMPLES.md

---

## ✅ Summary: Completed Work

| Phase | Area | Status | Details |
|-------|------|--------|---------|
| 04 | L1 Auto-Trigger | ✅ Done | L1 metrics auto-calculate at ingestion end |
| 05 | L2 Renaming | ✅ Done | Removed L2_ prefix, consistent naming |
| — | L1 Basic (12) | ✅ Done | 12 L1 metrics in SQL functions |
| — | L2 Derived (6) | ✅ Done | 6 L2 metrics in Python service |
| — | L1 Temporal (5) | ❌ Missing | ECF, NON_DIV_ECF, EE, FY_TSR, FY_TSR_PREL |
| — | Agg Ratios (56) | ❌ Missing | 14 metrics × 4 intervals |
| — | Beta (1) | ❌ Missing | OLS regression with fallback |
| — | Rates (2) | ❌ Missing | RF & RM calculation |
| — | Sector (?) | ❌ Missing | Sector aggregations |

---

## 🚀 Next Steps

1. **Read LEGACY_METRICS_COMPLETE.md** (15 min)
   - Understand all metrics tiers and what's missing
   - Review the 6 critical questions at the end

2. **Decide priorities** (10 min)
   - Which metrics do you need?
   - Temporal metrics? Aggregated ratios? Beta? Rates? Sector?
   - Reference the implementation status table

3. **Specify requirements** (to me)
   - Tell me which tier(s) from the Legacy Metrics document
   - I'll create phase plans for implementation

4. **Execute phases**
   - I'll create executable PLAN.md files
   - Follow GSD execute-phase workflow
   - Deploy metric calculations

---

**Need help deciding? Look at LEGACY_METRICS_COMPLETE.md Questions section!** 🎯
