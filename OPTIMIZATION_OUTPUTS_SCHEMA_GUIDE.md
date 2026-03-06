# Optimization Outputs Schema Guide

**Updated:** March 6, 2026  
**Status:** Schema refactored; awaiting application code updates

---

## Summary of Changes

### Removed
- ❌ `metrics_output_id BIGINT FK` — Was ambiguous (one ticker has N metrics)
- ❌ Index on `metrics_output_id`

### Modified
- 📝 `result_summary` JSONB structure (now hierarchical by base_year)
- 📝 Comments and documentation

### Added
- ✅ Natural key index: `(dataset_id, param_set_id, ticker, created_at DESC)`
- ✅ GIN indexes on `result_summary` and `metadata` JSONB fields
- ✅ Column comments for `result_summary` and `metadata`

---

## Table Definition

```sql
CREATE TABLE optimization_outputs (
  optimization_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES dataset_versions(dataset_id) ON DELETE CASCADE,
  param_set_id UUID NOT NULL REFERENCES parameter_sets(param_set_id),
  ticker TEXT NOT NULL,
  
  result_summary JSONB NOT NULL DEFAULT '{}',  -- {base_year: {metric: {year: value}}}
  metadata JSONB NOT NULL DEFAULT '{}',        -- {convergence_status, iterations, ...}
  
  created_by TEXT NOT NULL DEFAULT 'admin',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## Data Structure Examples

### `result_summary` JSONB Format

**Purpose:** Hierarchical storage by base_year for efficient multi-year charting

```json
{
  "2000": {
    "ep": {
      "2001": -0.0004,
      "2002": -0.0003,
      "2003": -0.0002,
      ...
      "2062": 0.0001
    },
    "growth_in_equity": {
      "2001": 0.03,
      "2002": 0.03,
      ...
      "2062": 0.025
    },
    "market_value_equity": {
      "2001": 285000000000,
      "2002": 290000000000,
      ...
      "2062": 450000000000
    },
    "book_value_equity": {...},
    "dividend": {...},
    "pat": {...},
    "return_on_equity": {...},
    "economic_profit": {...},
    "profit_after_tax": {...},
    "equity_free_cash_flow": {...},
    "proportion_franked_dividend": {...},
    "franking_credits_distributed": {...},
    "net_capital_distribution": {...},
    "present_value_factor": {...},
    "discount_adjusted_equity_free_cash_flow": {...},
    "change_in_equity": {...},
    "equity_free_cash_flow_fc": {...},
    "value_created": {...}
  },
  "2001": {
    ... [same structure, different base_year]
  },
  ...
  "2026": {
    ... [most recent base_year with current FY data]
  }
}
```

**18 Derived Metrics per base_year:**
1. `ep` — economic_profitability (optimization variable)
2. `growth_in_equity`
3. `pat` — profit_after_tax
4. `return_on_equity`
5. `book_value_equity`
6. `profit_after_tax` (duplicate from optimizer)
7. `equity_free_cash_flow`
8. `proportion_franked_dividend`
9. `dividend`
10. `franking_credits_distributed`
11. `net_capital_distribution`
12. `present_value_factor`
13. `discount_adjusted_equity_free_cash_flow`
14. `market_value_equity` (optimization target)
15. `change_in_equity`
16. `equity_free_cash_flow_fc`
17. `value_created`
18. `economic_profit`

---

### `metadata` JSONB Format

**Purpose:** Convergence tracking, debugging, validation

```json
{
  "convergence_status": "converged",
  "convergence_horizon": 60,
  "initial_ep": -0.0004,
  "optimal_ep": -0.000387,
  "solver": "scipy.optimize.basinhopping",
  "iterations": 1247,
  "residual": 2.3e-12,
  "observed_market_value": 285000000000,
  "calculated_market_value": 285000000000,
  "errors": null
}
```

**Key Fields:**
- `convergence_status`: "converged" | "diverged" | "max_iterations_reached"
- `convergence_horizon`: Number of projection years (typically 60)
- `initial_ep`, `optimal_ep`: Economic profitability before/after optimization
- `solver`: Which scipy solver used
- `iterations`: Number of function evaluations
- `residual`: Final convergence value (|calc_mkt_val - obs_mkt_val|²)
- `observed_market_value`: Target market cap from fundamentals
- `calculated_market_value`: Result after optimization
- `errors`: NULL if successful; error message string if diverged

---

## Query Patterns

### 1. Get All Optimizations for a Metrics Run

```sql
SELECT optimization_id, ticker, created_at, metadata ->> 'convergence_status' AS status
FROM optimization_outputs 
WHERE dataset_id = :dataset_id AND param_set_id = :param_set_id
ORDER BY ticker, created_at DESC;
```

### 2. Get Latest Optimization for a Ticker

```sql
SELECT * FROM optimization_outputs 
WHERE dataset_id = :dataset_id 
  AND param_set_id = :param_set_id 
  AND ticker = :ticker
ORDER BY created_at DESC
LIMIT 1;
```

### 3. Extract Specific Metric Across All Base Years (For Charting)

```sql
WITH metric_data AS (
  SELECT 
    optimization_id,
    ticker,
    jsonb_each_text(result_summary) AS (base_year, metrics),
    jsonb_each_text((metrics::jsonb -> 'market_value_equity')) AS (proj_year, value)
  FROM optimization_outputs 
  WHERE dataset_id = :dataset_id 
    AND param_set_id = :param_set_id 
    AND ticker = :ticker
  ORDER BY created_at DESC LIMIT 1
)
SELECT base_year, proj_year, value::NUMERIC AS market_value
FROM metric_data
ORDER BY base_year::INTEGER, proj_year::INTEGER;
```

### 4. Join Back to Metrics for Input Validation

```sql
SELECT 
  o.optimization_id,
  o.ticker,
  m.output_metric_name,
  m.output_metric_value,
  o.result_summary -> '2023' ->> 'market_value_equity' AS optimization_result
FROM optimization_outputs o
JOIN metrics_outputs m 
  ON o.dataset_id = m.dataset_id 
  AND o.param_set_id = m.param_set_id
  AND o.ticker = m.ticker
WHERE o.dataset_id = :dataset_id AND o.param_set_id = :param_set_id
ORDER BY o.ticker, m.output_metric_name;
```

### 5. Find Failed Optimizations (Convergence Issues)

```sql
SELECT optimization_id, ticker, created_at, metadata -> 'errors' AS error_msg
FROM optimization_outputs 
WHERE dataset_id = :dataset_id 
  AND param_set_id = :param_set_id
  AND metadata ->> 'convergence_status' != 'converged'
ORDER BY created_at DESC;
```

---

## Indexes

| Index Name | Columns | Purpose |
|---|---|---|
| `idx_optimization_outputs_natural_key` | `(dataset_id, param_set_id, ticker, created_at DESC)` | Primary query pattern; enables "latest optimization" queries |
| `idx_optimization_outputs_dataset` | `(dataset_id)` | Filter by dataset |
| `idx_optimization_outputs_param_set` | `(param_set_id)` | Filter by parameter set |
| `idx_optimization_outputs_ticker` | `(ticker)` | Filter by ticker |
| `idx_optimization_outputs_result_summary_gin` | `result_summary` (GIN) | JSONB containment queries (e.g., metric extraction) |
| `idx_optimization_outputs_metadata_gin` | `metadata` (GIN) | JSONB metadata queries (e.g., convergence_status filtering) |

---

## Application Code Changes Needed

### 1. Update Optimizer Output Transformation

**File:** `example-calculations/src/engine/optimizer.py` → `process_arrays()`

**Current:** Outputs long format (1,116 rows per ticker)
```python
# Current: Returns DataFrame with columns [year, base_year, ticker, key, value]
final_df = pd.concat(dfs)  # Long format
```

**Needed:** Output hierarchical JSONB by base_year
```python
# New: Returns dict with structure {base_year: {metric: {year: value}}}
result_summary = {
    "2000": {"ep": {...}, "market_value_equity": {...}, ...},
    "2001": {...},
    ...
}
```

### 2. Update Database Save Logic

**File:** `example-calculations/src/engine/sql.py` → `save_goal_seek_output()`

**Current:**
```python
def save_goal_seek_output(dataset):
    execute_batch_update(dataset, 'model_outputs')
```

**Needed:**
```python
def save_goal_seek_output(dataset_id, param_set_id, dataset):
    """
    Args:
        dataset_id: UUID from dataset_versions
        param_set_id: UUID from parameter_sets
        dataset: Dict with optimization results
    
    Transforms long-format optimization results into hierarchical JSONB
    and inserts into optimization_outputs table.
    """
    # Transform dataset (DataFrame) to hierarchical JSONB
    result_summary = transform_to_hierarchical_json(dataset)
    metadata = extract_convergence_metadata(dataset)
    
    sql = f"""
        INSERT INTO {DB_SCHEMA}.optimization_outputs 
        (dataset_id, param_set_id, ticker, result_summary, metadata, created_by)
        VALUES (:dataset_id, :param_set_id, :ticker, :result_summary, :metadata, 'admin')
    """
    # Execute insert for each unique ticker in dataset
```

### 3. Update Utility Functions

**File:** `example-calculations/src/executors/utility.py`

**Current:** Adds GUID and filters columns
```python
def save_goal_seek_output(guid, dataset):
    COLS = ['guid', 'year', 'base_year', 'ticker', 'key', 'value']
    dataset['guid'] = guid
    dataset = dataset[COLS]
    return sql.save_goal_seek_output(dataset)
```

**Needed:** Pass dataset_id and param_set_id instead of guid
```python
def save_goal_seek_output(dataset_id, param_set_id, dataset):
    """Passes versioning UUIDs instead of batch GUID"""
    return sql.save_goal_seek_output(dataset_id, param_set_id, dataset)
```

### 4. Update Main Runner

**File:** `example-calculations/src/run_bw_generation_model.py`

**Current:**
```python
inputs = {
    'country': 'AUS',
    'guid': GUID,  # Batch identifier
    'start': 2000,
    'end': 2023,
    'conv_horizon': 60
}
algo_dates = opt.run_optimizer(inputs)
utl.save_goal_seek_output(inputs['guid'], optimized_values)
```

**Needed:** Pass dataset_id and param_set_id
```python
inputs = {
    'country': 'AUS',
    'dataset_id': UUID,      # New
    'param_set_id': UUID,    # New
    'start': 2000,
    'end': 2023,
    'conv_horizon': 60
}
algo_dates = opt.run_optimizer(inputs)
utl.save_goal_seek_output(inputs['dataset_id'], inputs['param_set_id'], optimized_values)
```

---

## Migration Path (If Needed)

### Keep Legacy `model_outputs` Table
- Mark as read-only (stop writing new data)
- Keep for historical audit trail
- Document deprecation date (3 months out)
- Provide migration script for existing data

### Data Migration SQL (Optional)

```sql
-- Transform legacy model_outputs into new optimization_outputs format
-- (Only needed if you want to migrate historical data)

INSERT INTO optimization_outputs 
(dataset_id, param_set_id, ticker, result_summary, metadata, created_by, created_at)
SELECT 
  dataset_id,
  param_set_id,
  ticker,
  -- Transform long format to hierarchical JSONB
  jsonb_object_agg(
    base_year,
    jsonb_object_agg(key, metrics)
  ) AS result_summary,
  jsonb_build_object(
    'convergence_status', 'unknown',
    'errors', 'Migrated from legacy model_outputs'
  ) AS metadata,
  'system',
  created_at
FROM (
  SELECT 
    mo.dataset_id,
    mo.param_set_id,
    mo.ticker,
    mo.base_year::TEXT,
    mo.key,
    jsonb_object_agg(mo.year::TEXT, mo.value) AS metrics
  FROM model_outputs mo
  GROUP BY dataset_id, param_set_id, ticker, base_year, key
)
GROUP BY dataset_id, param_set_id, ticker, created_at;
```

---

## Traceability Path

```
optimization_outputs (1 row per ticker)
    ↓ (via dataset_id, param_set_id, ticker)
metrics_outputs (N rows per ticker, one per metric name)
    ↓ (via dataset_id, param_set_id, ticker)
fundamentals (N rows per ticker, one per metric per FY)
    ↓ (via dataset_id, ticker)
raw_data (raw ingestion rows)
```

---

## Status Checklist

- [x] Schema updated
- [ ] `optimizer.py` updated to output hierarchical JSONB
- [ ] `sql.py` updated to insert into `optimization_outputs`
- [ ] `utility.py` updated to pass dataset_id/param_set_id
- [ ] `run_bw_generation_model.py` updated with new parameters
- [ ] Application code tested end-to-end
- [ ] Database schema recreated with new table definition
- [ ] Migration completed (if needed)
- [ ] Legacy `model_outputs` deprecated/archived

