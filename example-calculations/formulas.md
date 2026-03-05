# BASOS EP Formulas (Source Code Truth)

This document maps the exact formulas and logic used in the Python backend and PostgreSQL views back to their original Excel worksheet equivalents.

*Note: This replaces the legacy `formula_metadata` DB table with truth extracted directly from `calc_engine.py`, `eeai_engine.py`, and the SQL schema views.*

---

## 1. Core Calc Engine Metrics (`calc_engine.py`)
These are computed by the Pandas engine (`backend/ep/engine/calc_engine.py`) and saved to `calculated_metrics`.

### Risk Free Rate (Rf)
- **Excel Sheet:** `Calc Rf` / `Calc Open Rf`
- **Python Implementation:** 
  ```python
  # Calc Rf: uses Adj Rf if available. Fallback to raw Rf, then fallback to default parameter (e.g. 5.0%)
  df['Calc Rf'] = df['_rf_aligned'].combine_first(df['_rf_raw']).fillna(default_rf)
  # Calc Open Rf: Shifted by 1 year per ticker
  df['Calc Open Rf'] = df.groupby('ticker')['Calc Rf'].shift(1)
  ```

### Beta
- **Excel Sheet:** `Calc Spot Beta` / `Calc Beta` / `Calc Open Beta`
- **Python Implementation:**
  ```python
  # Calc Spot Beta: 4-tier fallback
  df['Calc Spot Beta'] = (
      df['Calc Adj Beta']                     # Tier 1: Company Adj
      .combine_first(df['_sector_beta'])      # Tier 2: Precomputed load sector
      .combine_first(df['_sector_avg_beta'])  # Tier 3: Computed active sector average
      .fillna(1.0)                            # Tier 4: Market 1.0
  )
  # Calc Beta: Rolling average of Spot Beta rounded to beta_step
  expanding_avg = group['Calc Spot Beta'].expanding().mean()
  df['Calc Beta'] = (expanding_avg / beta_step).round(0) * beta_step
  ```

### Cost of Equity (Ke)
- **Excel Sheet:** `Calc Ke` / `Calc Open Ke`
- **Python Implementation:**
  ```python
  df['Calc Ke'] = df['Calc Rf'] + df['Calc Beta'] * mrp
  df['Calc Open Ke'] = df.groupby('ticker')['Calc Ke'].shift(1)
  ```

### Market Capitalisation (MC)
- **Excel Sheet:** `Calc MC`
- **Python Implementation:**
  ```python
  df['Calc MC'] = df['Spot Shares'] * df['Share Price']
  ```

### Economic Cash Flow (ECF) & Non-Div ECF
- **Excel Sheet:** `Calc ECF` / `Non Div ECF`
- **Python Implementation:**
  ```python
  # ECF = Prior MC * FY TSR
  df['Calc ECF'] = df['_Open MC'] * (df['FY TSR'] / 100.0)
  df['Non Div ECF'] = df['Calc ECF'] - df['Div'].fillna(0)
  ```

### Economic Equity (EE)
- **Excel Sheet:** `Calc EE` / `Calc Open EE`
- **Python Implementation:**
  ```python
  # Base year (first visible year):
  EE = Total Equity - MI
  # Subsequent years:
  EE = Prior EE + Adj PAT - Calc ECF
  ```

### Operating Assets (OA)
- **Excel Sheet:** `Calc Assets` / `Calc OA`
- **Python Implementation:**
  ```python
  df['Calc Assets'] = df['Total Assets'] - df['Cash']
  df['Calc OA'] = df['Calc Assets'] - df['FA'] - df['GW']
  ```

### Cost Structure (Op / Non-Op / Tax / XO)
- **Python Implementation:**
  ```python
  df['Calc Op Cost']     = df['Revenue'] - df['Op Income']
  df['Calc Non Op Cost'] = df['Op Income'] - df['PBT']
  df['Calc Tax Cost']    = df['PBT'] - df['PAT XO']
  df['Calc XO Cost']     = df['PAT XO'] - df['PAT']
  ```

### Economic Profit (EP) & PAT!
- **Excel Sheet:** `Calc EP` / `Calc PAT!`
- **Python Implementation:**
  ```python
  df['Calc EP'] = df['PAT'] - (df['Calc Open Ke'] * df['Calc Open EE'])
  
  open_ee_abs = df['Calc Open EE'].abs()
  df['Calc PAT!'] = ((df['Calc EP'] / open_ee_abs + df['Calc Open Ke']) * open_ee_abs)
  ```

### FY Total Shareholder Return (FY TSR) & Franking
- **Excel Sheet:** `Calc FY TSR` / `Calc FC`
- **Python Implementation:**
  ```python
  # If Franking is enabled:
  frank_credit = (df['Div'] / (1 - tax_rate)) * tax_rate * frank_payout
  df['Calc FY TSR'] = (df['Calc ECF'] - frank_credit) / df['_Open MC']
  df['Calc FC'] = -frank_credit * df['Franking']
  ```

---

## 2. Ratio Metrics (`v_ratio_metrics` SQL View)
Computed in `backend/ep/sql/schema/06_ratio_metrics.sql` using data from `mv_calc_wide`.

| Excel Sheet | SQL Formula |
|-------------|-------------|
| `EP% (Select)` | `calc_ep / ABS(calc_open_ee)` |
| `MB Ratio (Select)` | `calc_mc / calc_ee` |
| `ROEE (Select)` | `adj_pat / ABS(calc_open_ee)` |
| `ROA (Select)` | `adj_pat / ABS(calc_open_assets)` |
| `Profit Margin (Select)` | `adj_pat / adj_revenue` |
| `Op Cost Margin (Select)` | `calc_op_cost / adj_revenue` |
| `Non Op Cost Margin (Select)` | `calc_non_op_cost / adj_revenue` |
| `Eff Tax Rate (Select)` | `calc_tax_cost / adj_pbt` |
| `XO Cost Margin (Select)`| `calc_xo_cost / adj_revenue` |
| `FA Intensity (Select)` | `calc_open_fa / adj_revenue` |
| `TER (Select)` | `(adj_div + (calc_mc - calc_open_mc)) / ABS(calc_open_ee)` |
| `TER-Ke (Select)` | `TER - calc_ke` |
| `TERA (Select)` | `((adj_div * (1 + calc_rf)) + (calc_mc - calc_open_mc)) / ABS(calc_open_ee)` |
| `MC Diff` | `BW_implied_epy * calc_open_ee - calc_mc` |
| `Equity Diff` | `BW_implied_epy * calc_open_ee - calc_ee` |

---

## 3. BW Derived Metrics (`eeai_engine.py`)
Computed by the Pandas engine (`backend/ep/bw_outputs/eeai_engine.py`) after BW optimisation.

### 3Y Average EP%
- **Python Implementation:**
  ```python
  df['3Y Av EP%'] = df['ep_pct'].rolling(3, min_periods=1).mean()
  ```

### EEAI
- **Python Implementation:**
  ```python
  raw_eeai = (100 - (df['implied_epy'] - df['3Y Av EP%']) * eeai_scale).round(0)
  df['EEAI'] = raw_eeai.clip(lower=0, upper=200)
  ```

### EP Delivered & EP Required
- **Python Implementation:**
  ```python
  df['EP Delivered'] = df['3Y Av EP%'] * df['calc_open_ee']
  df['EP Required']  = df['implied_epy'] * df['calc_open_ee']
  ```

---

## 4. Sector & Index Aggregations (`v_sector_metrics`, `v_select_index_metrics`)

Aggregations follow two primary rules:
1. **Dollar Metrics** (e.g. `$Revenue (Sector)`, `#EE (Select)`) are simple `SUM()` across the grouping.
2. **Rate Metrics** (e.g. `#Open Rf (Sector)`, `#Open Beta (Select)`) are weighted by the absolute value of Open EE so that larger companies exert more influence.

**SQL Example for Rate Aggregation:**
```sql
SUM(calc_rf * ABS(calc_open_ee)) / SUM(ABS(calc_open_ee)) AS wavg_open_rf
```
