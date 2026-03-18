# FV ECF Parameter Dependencies - Documentation Index

## Overview

This documentation package provides a complete analysis of FV ECF (Future Value Economic Cash Flow) parameter dependencies in the CISSA codebase. It answers all questions about what parameters are needed, where they come from, and whether they can be pre-calculated.

---

## Documents in This Package

### 1. **FV_ECF_QUICK_SUMMARY.md** (187 lines, 5.9 KB)
**Start here if you want a quick answer**

Contains:
- Quick answer to all 5 questions
- Parameter matrix (simple table)
- Status of each parameter
- "Calc Incl" explained
- Pre-calculation feasibility (yes/no)
- Critical blocker identified

**Read time:** 5-10 minutes

---

### 2. **FV_ECF_PARAMETER_DEPENDENCIES.md** (350 lines, 14 KB)
**Read this for comprehensive technical details**

Contains:
- Section 1: ALL FV ECF input parameters (parameters + data inputs)
- Section 2: Source & dependency matrix (where each comes from)
- Section 3: Dependent metrics analysis (DIVIDENDS, Non Div ECF, Calc KE lagged, etc.)
- Section 4: FV_ECF formula components (Excel formula structure)
- Section 5: FV_ECF calculation requirements (prerequisites)
- Section 6: Alternative formulas (PAT_EX analysis)
- Section 7: Pre-calculation feasibility analysis
- Section 8: Complete input parameter matrix
- Section 9: Critical implementation blocker
- Section 10: Summary table (where each component comes from)

**Read time:** 15-20 minutes

---

### 3. **FV_ECF_DEPENDENCY_DIAGRAM.md** (299 lines, 18 KB)
**Read this for visual understanding**

Contains:
- ASCII architecture diagrams
- Input sources flow diagram
- FV_ECF calculation flow (3 steps)
- Data dependency tree
- Parameter resolution chain
- Critical blocker visualization

**Read time:** 10-15 minutes

---

### 4. **FV_ECF_ANALYSIS_COMPLETE.md** (352 lines, 15 KB)
**Read this for comprehensive reference**

Contains:
- Executive summary with all answers
- Question 1: All parameters (7 total)
- Question 2: Parameter properties matrix
- Question 3: Dependent metrics status
- Question 4: PAT_EX analysis (NO, not needed)
- Question 5: "Calc Incl" meaning (incl_franking parameter)
- Complete FV ECF input matrix (formatted table)
- Pre-calculation feasibility (detailed analysis)
- Critical blocker details
- Summary by question
- Documentation hierarchy
- Source files reference
- Next steps

**Read time:** 20-25 minutes

---

## Quick Navigation

### If you want to know...

**"What parameters does FV_ECF need?"**
→ Start with FV_ECF_QUICK_SUMMARY.md (Question 1)

**"Where does each parameter come from?"**
→ FV_ECF_PARAMETER_DEPENDENCIES.md (Section 2)

**"Are they pre-calculated or runtime?"**
→ FV_ECF_ANALYSIS_COMPLETE.md (Question 2 matrix)

**"Can FV_ECF be fully pre-calculated?"**
→ FV_ECF_QUICK_SUMMARY.md or FV_ECF_PARAMETER_DEPENDENCIES.md (Section 7)

**"What does 'Calc Incl' mean?"**
→ FV_ECF_QUICK_SUMMARY.md (Critical Finding section) or FV_ECF_ANALYSIS_COMPLETE.md (Question 5)

**"What about the 3Y/5Y/10Y formulas?"**
→ FV_ECF_QUICK_SUMMARY.md (The 3Y/5Y/10Y Formulas section)

**"Does it need PAT_EX data?"**
→ FV_ECF_ANALYSIS_COMPLETE.md (Question 4)

**"What's blocking FV_ECF right now?"**
→ FV_ECF_QUICK_SUMMARY.md (Critical Blocker section)

**"Show me the architecture"**
→ FV_ECF_DEPENDENCY_DIAGRAM.md (full visual diagrams)

**"I need everything for reference"**
→ FV_ECF_ANALYSIS_COMPLETE.md (comprehensive)

---

## Key Findings Summary

### All 5 Original Questions Answered

| Question | Answer | Location |
|----------|--------|----------|
| 1. What parameters? | 7 total: 3 parameters + 4 data inputs | Quick Summary, Q1 |
| 2. Where from? | Parameters table, param_sets, fundamentals, metrics_outputs | Dependencies doc, Section 2 |
| 3. Dependent metrics? | DIV ready, Non Div ECF missing, KE ready, ECF missing | Analysis Complete, Q3 |
| 4. Need PAT_EX? | NO - not used by FV_ECF | Analysis Complete, Q4 |
| 5. What is Calc Incl? | It's incl_franking parameter (YES/NO), not a metric | Analysis Complete, Q5 |

### Critical Facts

| Fact | Status | Impact |
|------|--------|--------|
| incl_franking parameter | ✓ Ready | Can control franking adjustments |
| frank_tax_rate parameter | ✓ Ready | Default 0.30, can override |
| value_franking_cr parameter | ✓ Ready | Default 0.75, can override |
| DIVIDENDS (fundamentals) | ✓ Ready | Input data available |
| FRANKING (fundamentals) | ✓ Ready | Input data available |
| Calc KE (lagged) | ✓ Ready | Phase 09 pre-calculated |
| **Non Div ECF** | ✗ **MISSING** | **BLOCKS FV_ECF** |
| **Calc ECF** | ✗ **MISSING** | Needed for Non Div ECF |

### Pre-Calculation Feasibility

| Component | Can Pre-Calculate? |
|-----------|-------------------|
| Parameters | ✓ Yes (in database) |
| Fundamentals | ✓ Yes (in database) |
| Lagged KE | ✓ Yes (SQL JOIN) |
| Year shifts | ✗ No (ticker-specific) |
| Power calculations | ✗ No (interval-dependent) |
| Final sums/shifts | ✗ No (sequential context) |
| **Overall** | **Partial - runtime needed** |

---

## Source Code Reference

### Main Implementation File
- **Location:** `/backend/app/services/fv_ecf_service.py`
- **Lines:** 598 total
- **Key Methods:**
  - `calculate_fv_ecf_metrics()` (line 83) - Main orchestrator
  - `_fetch_fundamentals_data()` (line 306) - Gets DIVIDENDS, FRANKING, Non Div ECF
  - `_fetch_lagged_ke()` (line 365) - Gets lagged KE via SQL LEFT JOIN
  - `_calculate_fv_ecf_for_interval()` (line 425) - Vectorized calculation
  - `_insert_fv_ecf_batch()` (line 530) - Batch INSERT

### API Endpoint
- **Location:** `/backend/app/api/v1/endpoints/metrics.py`
- **Lines:** 760-850
- **Endpoint:** `POST /api/v1/metrics/l2-fv-ecf/calculate`

### Database Schema
- **Location:** `/backend/database/schema/schema.sql`
- **Parameters section:** ~310-350
- **13 baseline parameters** including franking-related

### Related Services
- `EconomicProfitService` (for EP, PAT_EX, XO_COST_EX, FC)
- `MetricsService` (for metric routing)
- `CostOfEquityService` (for Calc KE)

---

## Parameter Resolution Flow

```
POST /l2-fv-ecf/calculate?incl_franking=Yes&dataset_id=X&param_set_id=Y
                          │
                          ├─→ incl_franking = "Yes" (from query)
                          │
                          └─→ Query parameter_sets table
                              └─→ Get param_overrides JSON
                                 ├─→ frank_tax_rate override (if exists)
                                 └─→ value_franking_cr override (if exists)
                                    │
                                    └─→ If not in overrides, query parameters table
                                        ├─→ frank_tax_rate default = 0.30
                                        └─→ value_franking_cr default = 0.75

Final parameters passed to calculation:
  incl_franking = "Yes"
  frank_tax_rate = 0.30 (or overridden)
  value_franking_cr = 0.75 (or overridden)
```

---

## Implementation Checklist

### To Unblock FV_ECF
- [ ] Implement Calc ECF (Phase 06)
  - [ ] Formula: LAG_MC × (1 + Calc FY TSR) - Calc MC
  - [ ] Store in metrics_outputs (output_metric_name='Calc ECF')
  
- [ ] Implement Non Div ECF (Phase 06)
  - [ ] Formula: Calc ECF + DIVIDENDS
  - [ ] Store in metrics_outputs (output_metric_name='Non Div ECF')
  
- [ ] Test FV_ECF endpoint
  - [ ] Verify Non Div ECF is populated
  - [ ] Run: POST /api/v1/metrics/l2-fv-ecf/calculate
  - [ ] Check results in metrics_outputs

### To Optimize FV_ECF
- [ ] Pre-cache lagged KE (if performance becomes issue)
- [ ] Verify batch INSERT optimization (already done - 1000/batch)
- [ ] Monitor vectorized Pandas operations
- [ ] Consider materialized view for ke_open

---

## Document Structure

Each document is organized for different needs:

1. **Quick Summary** - Executives, quick answers
2. **Parameter Dependencies** - Developers, comprehensive details
3. **Dependency Diagram** - Visual learners, architecture
4. **Analysis Complete** - Reference, all information

---

## Contact Points

### For Questions About...

**FV_ECF formula logic**
→ See `/backend/app/services/fv_ecf_service.py` (algorithm in docstring)

**Parameter resolution**
→ See `_load_parameters()` method (line 257)

**Data fetching**
→ See `_fetch_fundamentals_data()` (line 306) and `_fetch_lagged_ke()` (line 365)

**Database schema**
→ See `/backend/database/schema/schema.sql` (parameters section)

**Missing metrics**
→ Search for Non Div ECF calculation in Phase 06 L1 metrics

---

## Version Information

- **Created:** March 18, 2026
- **Codebase analyzed:** CISSA financial metrics pipeline
- **Python version:** 3.12 (based on imports)
- **Database:** PostgreSQL (based on SQL syntax)
- **Key framework:** SQLAlchemy async, Pandas, NumPy

---

## Last Updated

All analysis complete and verified against:
- `/backend/app/services/fv_ecf_service.py` (598 lines)
- `/backend/app/services/metrics_service.py` 
- `/backend/app/api/v1/endpoints/metrics.py`
- `/backend/database/schema/schema.sql`
- `/example-calculations/src/executors/fvecf.py`

