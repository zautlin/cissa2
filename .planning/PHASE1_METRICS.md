# Phase 1: Simple SQL-Only Metrics

All metrics below can be computed directly from `cissa.fundamentals` with NO temporal dependencies.
Each metric = one SQL function that can be created, tested, and deployed independently.

## Group 1: Core Market/Equity Metrics (3 functions)

### 1.1 Market Cap
**Formula:** `Spot Shares × Share Price`
**Input metrics:** `Spot Shares`, `Share Price`
**Output name:** `Calc MC`

```sql
CREATE OR REPLACE FUNCTION cissa.fn_calc_market_cap(p_dataset_id UUID)
RETURNS TABLE (ticker TEXT, fiscal_year INTEGER, calc_mc NUMERIC) AS $$
...
```

### 1.2 Operating Assets
**Formula:** `Total Assets - Cash`
**Input metrics:** `Total Assets`, `Cash`
**Output name:** `Calc Assets`

```sql
CREATE OR REPLACE FUNCTION cissa.fn_calc_operating_assets(p_dataset_id UUID)
RETURNS TABLE (ticker TEXT, fiscal_year INTEGER, calc_assets NUMERIC) AS $$
...
```

### 1.3 Operating Assets (Detail)
**Formula:** `Operating Assets - Fixed Assets - Goodwill`
**Input metrics:** `Calc Assets` (from 1.2), `Fixed Assets`, `Goodwill`
**Output name:** `Calc OA`
**Note:** Depends on fn_calc_operating_assets() output

---

## Group 2: Cost Structure (4 functions)

These decompose the income statement into cost components.

### 2.1 Operating Cost
**Formula:** `Revenue - Operating Income`
**Input metrics:** `Revenue`, `Op Income`
**Output name:** `Calc Op Cost`

### 2.2 Non-Operating Cost
**Formula:** `Operating Income - PBT`
**Input metrics:** `Op Income`, `PBT`
**Output name:** `Calc Non Op Cost`

### 2.3 Tax Cost
**Formula:** `PBT - PAT (Extraordinary)`
**Input metrics:** `PBT`, `PAT XO`
**Output name:** `Calc Tax Cost`

### 2.4 Extraordinary Items Cost
**Formula:** `PAT (Extraordinary) - PAT`
**Input metrics:** `PAT XO`, `PAT`
**Output name:** `Calc XO Cost`

---

## Group 3: Ratio Metrics (6+ functions)

These are percentages/ratios derived from fundamentals. No interdependencies.

### 3.1 Return on Equity (ROEE)
**Formula:** `PAT / Opening Economic Equity`
**Input metrics:** `PAT`, `Calc EE` (from Phase 2)
**Note:** Depends on Phase 2 — DEFER to Phase 2

### 3.2 Profit Margin
**Formula:** `PAT / Revenue`
**Input metrics:** `PAT`, `Revenue`
**Output name:** `Profit Margin`

### 3.3 Operating Cost Margin
**Formula:** `Op Cost / Revenue`
**Input metrics:** `Calc Op Cost` (from 2.1), `Revenue`
**Output name:** `Op Cost Margin %`

### 3.4 Non-Operating Cost Margin
**Formula:** `Non-Op Cost / Revenue`
**Input metrics:** `Calc Non Op Cost` (from 2.2), `Revenue`
**Output name:** `Non-Op Cost Margin %`

### 3.5 Effective Tax Rate
**Formula:** `Tax Cost / PBT`
**Input metrics:** `Calc Tax Cost` (from 2.3), `PBT`
**Output name:** `Eff Tax Rate`

### 3.6 Extraordinary Items Margin
**Formula:** `XO Cost / Revenue`
**Input metrics:** `Calc XO Cost` (from 2.4), `Revenue`
**Output name:** `XO Cost Margin %`

### 3.7 Fixed Asset Intensity
**Formula:** `Fixed Assets / Revenue`
**Input metrics:** `Fixed Assets`, `Revenue`
**Output name:** `FA Intensity`

---

## Group 4: Market Book Ratios (2 functions)

### 4.1 Market-to-Book (MB) Ratio
**Formula:** `Market Cap / Economic Equity`
**Input metrics:** `Calc MC` (from 1.1), `Calc EE` (Phase 2)
**Note:** Depends on Phase 2 — DEFER to Phase 2

### 4.2 Equity (Book Value) - from fundamentals
**Formula:** `Total Equity - Minority Interest`
**Input metrics:** `Total Equity`, `Minority Interest`
**Output name:** `Book Equity`
**Note:** Used as intermediate for other calculations

---

## Group 5: Return on Assets (1 function)

### 5.1 Return on Operating Assets (ROA)
**Formula:** `PAT / Operating Assets`
**Input metrics:** `PAT`, `Calc Assets` (from 1.2)
**Output name:** `ROA`

---

## SUMMARY: Phase 1 Breakdown

**Total functions to create: 13**

| Group | Count | Notes |
|-------|-------|-------|
| Core Metrics | 3 | Market Cap, Assets, Asset Detail |
| Cost Structure | 4 | Op, Non-Op, Tax, XO costs |
| Ratio Metrics | 7 | Margins, FA Intensity, etc. |
| Return Ratios | 1 | ROA |

**Dependencies within Phase 1:**
- `Calc OA` depends on `Calc Assets` (1.2)
- Margin ratios (3.3-3.6) depend on cost functions (2.1-2.4)
- All others are independent

**Execution order** (can parallelize within groups):
1. Create Group 1 (1.1-1.2) in parallel
2. Create Group 2 (2.1-2.4) in parallel
3. Create Group 3 (ratios) using outputs from 1,2
4. Create Group 4 (ROA)

**Estimated effort:** ~80 lines SQL per function × 13 = ~1,000 lines total
**Estimated time:** 1-2 weeks (with testing)

---

## Phase 2 Prerequisites (Deferral List)

These CANNOT be Phase 1 (require temporal logic):

| Metric | Why Deferred | Dependencies |
|--------|-------------|--------------|
| Economic Cash Flow (ECF) | Needs LAG(Market Cap) | Phase 1 MC |
| Economic Equity (EE) | Needs cumsum(PAT - ECF) | Phase 1 + temporal |
| Cost of Equity (Ke) | Needs Beta + Risk Premium | External + Phase 2 |
| Economic Profit (EP) | Needs LAG(Ke) × LAG(EE) | Phase 2 + parameters |
| Return on Equity (ROEE) | Needs LAG(EE) | Phase 2 |
| Market-to-Book (MB) | Needs EE | Phase 2 |
| Various TSR calculations | Needs historical returns | Phase 2 |
