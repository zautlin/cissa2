# Phase 3 Enhanced Metrics Service - Output Specification

## Database Insert Target: `cissa.metrics_outputs`

The service inserts 6 rows per ticker per fiscal_year:

```
dataset_id          | param_set_id        | ticker | fiscal_year | output_metric_name | output_metric_value | metadata                                              | created_at
550e8400-...        | 660e8400-...        | AAPL   | 2023        | Beta               | 1.0                 | {"metric_level":"L3", "calculation_source":"..."}    | 2026-03-08 12:00:00
550e8400-...        | 660e8400-...        | AAPL   | 2023        | Calc Rf            | 0.05                | {"metric_level":"L3", "calculation_source":"..."}    | 2026-03-08 12:00:00
550e8400-...        | 660e8400-...        | AAPL   | 2023        | Calc KE            | 0.10                | {"metric_level":"L3", "calculation_source":"..."}    | 2026-03-08 12:00:00
550e8400-...        | 660e8400-...        | AAPL   | 2023        | ROA                | 0.15                | {"metric_level":"L3", "calculation_source":"..."}    | 2026-03-08 12:00:00
550e8400-...        | 660e8400-...        | AAPL   | 2023        | ROE                | 0.22                | {"metric_level":"L3", "calculation_source":"..."}    | 2026-03-08 12:00:00
550e8400-...        | 660e8400-...        | AAPL   | 2023        | Profit Margin      | 0.18                | {"metric_level":"L3", "calculation_source":"..."}    | 2026-03-08 12:00:00
```

## Example Calculations

### Given Input Data:
```
Ticker: AAPL
Fiscal Year: 2023

FROM cissa.fundamentals:
- Share Price (price): 150.00
- Spot Shares (shrouts): 15,000,000,000
- Total Assets: $3,500,000,000,000
- Revenue: $380,000,000,000
- Profit After Tax (pat): $70,000,000,000
- Total Equity: $50,000,000,000

FROM cissa.metrics_outputs (L1 metrics):
- (Already calculated by Phase 1)
```

### Calculation Flow:

#### 1. Beta Calculation
```python
beta_rounding = 0.1  # from parameter set
beta = 1.0  # default (placeholder)
beta_rounded = round(1.0 / 0.1) * 0.1 = round(10) * 0.1 = 1.0

OUTPUT_METRIC_NAME = "Beta"
OUTPUT_METRIC_VALUE = 1.0
```

#### 2. Risk-Free Rate Calculation
```python
fixed_benchmark_return_wealth_preservation = 0.075  # from parameter set (7.5% converted)

OUTPUT_METRIC_NAME = "Calc Rf"
OUTPUT_METRIC_VALUE = 0.075
```

#### 3. Cost of Equity (KE) Calculation
```python
equity_risk_premium = 0.05  # from parameter set (5% converted)
KE = Rf + Beta × Risk Premium
KE = 0.075 + 1.0 × 0.05 = 0.125

OUTPUT_METRIC_NAME = "Calc KE"
OUTPUT_METRIC_VALUE = 0.125  # 12.5%
```

#### 4. ROA Calculation
```python
pat = 70,000,000,000
total_assets = 3,500,000,000,000
ROA = pat / total_assets
ROA = 70,000,000,000 / 3,500,000,000,000 = 0.02  # 2%

OUTPUT_METRIC_NAME = "ROA"
OUTPUT_METRIC_VALUE = 0.02
```

#### 5. ROE Calculation
```python
pat = 70,000,000,000
total_equity = 50,000,000,000
ROE = pat / total_equity
ROE = 70,000,000,000 / 50,000,000,000 = 1.4  # 140%

OUTPUT_METRIC_NAME = "ROE"
OUTPUT_METRIC_VALUE = 1.4
```

#### 6. Profit Margin Calculation
```python
pat = 70,000,000,000
revenue = 380,000,000,000
Profit Margin = pat / revenue
Profit Margin = 70,000,000,000 / 380,000,000,000 = 0.184  # 18.4%

OUTPUT_METRIC_NAME = "Profit Margin"
OUTPUT_METRIC_VALUE = 0.184
```

## Database Query to Verify Output

After running the service:

```sql
-- Check all L3 metrics for AAPL 2023
SELECT 
  ticker,
  fiscal_year,
  output_metric_name,
  output_metric_value,
  metadata
FROM cissa.metrics_outputs
WHERE metadata->>'metric_level' = 'L3'
  AND ticker = 'AAPL'
  AND fiscal_year = 2023
ORDER BY output_metric_name;

-- Results:
-- ticker | fiscal_year | output_metric_name | output_metric_value | metadata
-- -------|-------------|-------------------|---------------------|----------------------------------
-- AAPL   | 2023        | Beta               | 1.0                 | {"metric_level":"L3",...}
-- AAPL   | 2023        | Calc KE            | 0.125               | {"metric_level":"L3",...}
-- AAPL   | 2023        | Calc Rf            | 0.075               | {"metric_level":"L3",...}
-- AAPL   | 2023        | Profit Margin      | 0.184               | {"metric_level":"L3",...}
-- AAPL   | 2023        | ROA                | 0.02                | {"metric_level":"L3",...}
-- AAPL   | 2023        | ROE                | 1.4                 | {"metric_level":"L3",...}
```

## Count Summary

```sql
-- How many records per metric type
SELECT 
  output_metric_name,
  COUNT(*) as count
FROM cissa.metrics_outputs
WHERE metadata->>'metric_level' = 'L3'
GROUP BY output_metric_name
ORDER BY output_metric_name;

-- Results (example):
-- output_metric_name | count
-- ------------------|--------
-- Beta               | 250
-- Calc KE            | 250
-- Calc Rf            | 250
-- Profit Margin      | 248
-- ROA                | 248
-- ROE                | 248
-- (Total: ~1,490 records if 250 stocks × 5-6 years)
```

## API Response Example

```json
{
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "param_set_id": "660e8400-e29b-41d4-a716-446655440001",
  "results_count": 1490,
  "metrics_calculated": [
    "Beta",
    "Calc Rf",
    "Calc KE",
    "ROA",
    "ROE",
    "Profit Margin"
  ],
  "status": "success",
  "message": "Calculated 6 metric types"
}
```

## CLI Output Example

```bash
$ python backend/app/cli/run_enhanced_metrics.py \
    550e8400-e29b-41d4-a716-446655440000 \
    660e8400-e29b-41d4-a716-446655440001

============================================================
ENHANCED METRICS CALCULATION RESULTS
============================================================
Status: SUCCESS
Message: Calculated 6 metric types
Records Inserted: 1490
Metrics Calculated: Beta, Calc Rf, Calc KE, ROA, ROE, Profit Margin
============================================================
```

## Data Type Summary

| Metric | Type | Range | Notes |
|--------|------|-------|-------|
| Beta | float | 0.0-3.0 | Currently 1.0 (placeholder) |
| Calc Rf | float | 0.0-0.2 | Decimal percentage (e.g., 0.05 = 5%) |
| Calc KE | float | 0.0-0.3 | Decimal percentage |
| ROA | float | -∞ to +∞ | Decimal percentage |
| ROE | float | -∞ to +∞ | Can exceed 1.0 (100%+) |
| Profit Margin | float | -∞ to +∞ | Can be negative |

## Important Notes

1. **Decimal Format**: All percentages stored as decimals (0.05 = 5%), not integers
2. **Null Handling**: Ratios skipped if denominator is 0 or null
3. **Conflict Resolution**: If metric already exists, value is updated (ON CONFLICT DO UPDATE)
4. **Metadata**: All L3 metrics tagged with `metric_level: "L3"` for filtering
5. **Per-Stock**: Each metric calculated separately for each ticker/fiscal_year combo
