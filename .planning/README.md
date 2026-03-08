# CISSA System Review - Documentation Index

**Date Created:** March 8, 2026  
**Purpose:** Help you migrate legacy metrics calculation code into the FastAPI backend

---

## 📋 Three Essential Documents

### 1. **SYSTEM_STATE_REVIEW.md** (9.6 KB)
**Read This First** — Understand the current state of your system

Contains:
- ✅ What's already done (Phase 1 + Phase 2 metrics)
- ❌ What still needs migration (Beta, Rates, TSR, Sector)
- 📊 Migration status matrix (quick reference table)
- 🏗️ Architecture overview (FastAPI + PostgreSQL)
- 🗂️ Code organization (backend structure vs. legacy structure)
- 🛣️ Recommended 4-week migration path
- ❓ Key questions to answer before starting

**Start here to understand what you have and what needs to be done.**

---

### 2. **MIGRATION_EXAMPLES.md** (20 KB)
**Read This Second** — See concrete code examples

Contains:
- **Example 1: Beta Service Migration**
  - Legacy code from `executors/beta.py`
  - Full FastAPI service implementation (copy-paste ready)
  - API endpoint example
  - How to handle 4-tier fallback logic

- **Example 2: Risk-Free Rate Service**
  - Precomputed table lookup pattern
  - Fallback to default when missing
  - Lagged calculation

- **Example 3: TSR & Franking Credits**
  - Complex formula with conditions
  - Franking credit adjustment
  - Inception year handling

- **Example 4: Pydantic Schemas**
  - Request/response schemas for all metrics
  - Proper Pydantic v2 patterns
  - Type hints and validation

- **Best Practices**
  - Separate pure calculation from I/O
  - Batch operations for performance
  - Type hints and logging

**Use this as a template for creating each new service.**

---

### 3. **PHASE3_NEXT_STEPS.md** (12 KB)
**Read This Third** — Get step-by-step implementation guide

Contains:
- ❓ Pre-work questions (4 key decisions before you start)
- 🚀 **Quickstart: First Beta Service (Day 1-2)**
  - Step 0: Verify prerequisites
  - Step 1: Create service file
  - Step 2: Create Pydantic models
  - Step 3: Create API endpoint
  - Step 4: Test with curl
  - Step 5: Compare against legacy
  
- 📅 **Full 4-Week Roadmap**
  - Week 1: Beta Service (3-4 hours)
  - Week 2: Risk-Free Rate Service (2-3 hours)
  - Week 3: TSR & Franking Service (3-4 hours)
  - Week 4: Sector Aggregations (3-4 hours)

- 📚 Documentation to review first
- 🔧 Key files to keep updated
- 🛠️ Development workflow for each service
- 🆘 Troubleshooting guide
- ✅ Success criteria for Phase 3

**Follow this day-by-day to implement each service.**

---

## 🎯 Quick Start (Next 30 Minutes)

1. **Read** `SYSTEM_STATE_REVIEW.md` (10 min)
   - Understand Phase 1, 2, 3 status
   - See what's already built

2. **Skim** `MIGRATION_EXAMPLES.md` (10 min)
   - Focus on "Example 1: Beta Service"
   - Understand the pattern

3. **Answer** 4 questions in `PHASE3_NEXT_STEPS.md` (10 min)
   - Which metrics are priority?
   - Do you have data sources?
   - API or batch mode?
   - Need result validation?

4. **Pick** one metric to start (suggest: Beta)
   - Follow "Quickstart: First Beta Service"

---

## 🏗️ Architecture Summary

Your system has three layers:

```
Phase 1 (DONE) ✅
├─ 15 SQL functions in PostgreSQL
├─ Calculate core metrics (MC, Op Assets, Ratios)
├─ API: POST /api/v1/metrics/calculate
└─ Store in: metrics_outputs table

Phase 2 (DONE) ✅
├─ FastAPI service layer
├─ Calculate L2 metrics using L1 as input
├─ API: POST /api/v1/metrics/calculate-l2
└─ CLI: run_l2_metrics.py

Phase 3 (TO DO) ⏳
├─ Beta Calculation Service
├─ Risk-Free Rate Service
├─ TSR & Franking Service
├─ Sector Aggregations Service
└─ 4 new API endpoints + 4 new services
```

---

## 📁 File Locations

**New Documentation:**
- `.planning/SYSTEM_STATE_REVIEW.md` ← Start here
- `.planning/MIGRATION_EXAMPLES.md` ← Code templates
- `.planning/PHASE3_NEXT_STEPS.md` ← Implementation guide

**Existing Code:**
- `backend/app/main.py` — FastAPI app entry point
- `backend/app/services/metrics_service.py` — Phase 1 service (reference)
- `backend/app/services/l2_metrics_service.py` — Phase 2 service (reference)
- `backend/app/api/v1/endpoints/metrics.py` — API endpoints
- `example-calculations/src/executors/metrics.py` — Legacy source (to migrate)
- `example-calculations/src/executors/beta.py` — Beta logic (to migrate)
- `example-calculations/src/executors/rates.py` — Rate logic (to migrate)

---

## ✅ What You'll Get

After following these guides and implementing Phase 3:

**API Endpoints:**
```bash
POST /api/v1/metrics/calculate-beta      # New in Phase 3
POST /api/v1/metrics/calculate-rf        # New in Phase 3
POST /api/v1/metrics/calculate-returns   # New in Phase 3
POST /api/v1/metrics/calculate-sector    # New in Phase 3
```

**Services:**
```
backend/app/services/beta_service.py      # New
backend/app/services/rate_service.py      # New
backend/app/services/returns_service.py   # New
backend/app/services/sector_service.py    # New
```

**Database:**
- All results stored in `cissa.metrics_outputs` table
- Comparable with legacy output for validation

---

## 📊 Estimated Time

| Service | Files | Lines | Est. Time |
|---------|-------|-------|-----------|
| Beta | 3 | 250 | 3-4 hours |
| Risk-Free Rate | 3 | 200 | 2-3 hours |
| TSR & Franking | 3 | 250 | 3-4 hours |
| Sector Aggregations | 3 | 200 | 3-4 hours |
| **TOTAL Phase 3** | 12 | 900 | **12-15 hours** |

**That's about 3-4 hours per week for a month.**

---

## 🔑 Key Concepts

### Service Layer Pattern (Repeat for Each Metric)
```python
class [Feature]Service:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate(self, dataset_id: UUID, ...) -> Response:
        # 1. Fetch data
        # 2. Calculate
        # 3. Store results
        # 4. Return response
```

### API Endpoint Pattern (Repeat for Each Service)
```python
@router.post("/api/v1/metrics/calculate-{feature}")
async def calculate_{feature}(request, db):
    service = [Feature]Service(db)
    return await service.calculate(...)
```

### Testing Pattern (Same for All)
```bash
1. Start API: ./start-api.sh
2. Call endpoint: curl -X POST http://localhost:8000/api/v1/metrics/calculate-{feature}
3. Check results: psql -c "SELECT * FROM metrics_outputs WHERE metric_name = '...'"
4. Compare: legacy output vs. new output
```

**Once you do the first service (Beta), the others follow the same pattern.**

---

## ❓ Common Questions Answered

**Q: Which metric should I start with?**  
A: Beta. It's complex enough to be representative, but doesn't depend on other Phase 3 metrics.

**Q: Do I have to do all 4 services?**  
A: No. Do whatever's most valuable to your business. We recommend prioritizing based on usage.

**Q: Can I do them in parallel?**  
A: Not recommended. Do them sequentially so you can reuse patterns and learn as you go.

**Q: How do I validate results?**  
A: Compare new results against legacy output. See "Comparison" section in PHASE3_NEXT_STEPS.md.

**Q: What if results don't match?**  
A: Check formula translation, NULL handling, and data types. See troubleshooting guide.

**Q: Do I need to change Phase 1 or Phase 2?**  
A: No. Phase 3 is purely additive. No breaking changes.

---

## 🚀 Ready to Start?

1. Open `.planning/SYSTEM_STATE_REVIEW.md` and read it
2. Open `.planning/MIGRATION_EXAMPLES.md` and review the Beta example
3. Open `.planning/PHASE3_NEXT_STEPS.md` and follow the Quickstart
4. Create your first service file: `backend/app/services/beta_service.py`
5. Test it!

**Good luck! Your system is well-designed and the migration is straightforward.** 🎯
