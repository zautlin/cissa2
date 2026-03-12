# MB Ratio API - Quick Reference

## Overview
This API calculates financial ratio metrics on-the-fly with rolling averages (1Y/3Y/5Y/10Y temporal windows).

## Endpoint
```
GET /api/v1/metrics/ratio-metrics
```

## Query Parameters

| Param | Type | Required | Default | Example |
|-------|------|----------|---------|---------|
| `metric` | string | YES | - | `mb_ratio` |
| `tickers` | string | YES | - | `AAPL,MSFT,GOOGL` |
| `dataset_id` | UUID | YES | - | `e5e7c8a0-...` |
| `temporal_window` | string | NO | `1Y` | `3Y`, `5Y`, `10Y` |
| `param_set_id` | UUID | NO | base_case | `a1b2c3d4-...` |
| `start_year` | int | NO | - | `2015` |
| `end_year` | int | NO | - | `2023` |

## Available Metrics

### MB Ratio (Market-to-Book)
```
metric=mb_ratio
```
**Formula:** Market Cap / Economic Equity  
**Numerator:** Calc MC  
**Denominator:** Calc EE  
**Unit:** Ratio (dimensionless)

## Temporal Windows

- **1Y (Annual)**: Current year values only
  - Data available from first year of fundamentals data
  - Example: 2001, 2002, 2003, ...

- **3Y (3-Year Rolling Avg)**: Average of current year + prior 2 years
  - Data available from 3rd year onwards
  - Example: 2003 (avg of 2001-2003), 2004 (avg of 2002-2004), ...

- **5Y (5-Year Rolling Avg)**: Average of current year + prior 4 years
  - Data available from 5th year onwards
  - Example: 2005 (avg of 2001-2005), 2006 (avg of 2002-2006), ...

- **10Y (10-Year Rolling Avg)**: Average of current year + prior 9 years
  - Data available from 10th year onwards
  - Example: 2010 (avg of 2001-2010), 2011 (avg of 2002-2011), ...

## Example Requests

### Simple Request (1 ticker, annual)
```bash
curl "http://localhost:8000/api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=AAPL&dataset_id=e5e7c8a0-1234-5678-1234-567890123456"
```

### Multiple Tickers with 3-Year Window
```bash
curl "http://localhost:8000/api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=AAPL,MSFT,GOOGL&dataset_id=e5e7c8a0-1234-5678-1234-567890123456&temporal_window=3Y"
```

### With Year Filter
```bash
curl "http://localhost:8000/api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=AAPL&dataset_id=e5e7c8a0-1234-5678-1234-567890123456&temporal_window=5Y&start_year=2015&end_year=2023"
```

### With Custom Parameter Set
```bash
curl "http://localhost:8000/api/v1/metrics/ratio-metrics?metric=mb_ratio&tickers=AAPL&dataset_id=e5e7c8a0-1234-5678-1234-567890123456&param_set_id=a1b2c3d4-5678-1234-5678-123456789abc"
```

## Response Format

### Success (200 OK)
```json
{
  "metric": "mb_ratio",
  "display_name": "MB Ratio",
  "temporal_window": "3Y",
  "data": [
    {
      "ticker": "AAPL",
      "time_series": [
        {"year": 2003, "value": 2.45},
        {"year": 2004, "value": 2.67},
        {"year": 2005, "value": 2.89}
      ]
    },
    {
      "ticker": "MSFT",
      "time_series": [
        {"year": 2003, "value": 1.92},
        {"year": 2004, "value": 2.15},
        {"year": 2005, "value": 2.38}
      ]
    }
  ]
}
```

### Errors

#### Invalid Metric (400 Bad Request)
```json
{
  "detail": "Unknown metric: invalid_metric. Available metrics: mb_ratio"
}
```

#### Invalid Temporal Window (400 Bad Request)
```json
{
  "detail": "Invalid temporal window: 2Y. Must be 1Y, 3Y, 5Y, 10Y"
}
```

#### Invalid Tickers (400 Bad Request)
```json
{
  "detail": "Invalid ticker list"
}
```

#### Database Error (500 Internal Server Error)
```json
{
  "detail": "Failed to calculate ratio metric: ..."
}
```

## Performance

Expected response times:
- **1 ticker, 1Y window**: <50ms
- **1 ticker, 3Y window**: <75ms
- **5 tickers, 3Y window**: <100ms
- **5 tickers, 10Y window**: <150ms

## Data Notes

### NULL Values
- Returns `"value": null` for a year if:
  - Required metric data is missing
  - Denominator is zero
  - Insufficient years for rolling average window

### Null Handling Policy
- **MB Ratio**: Skips year if denominator (Calc EE) is zero or null
- **MB Ratio**: Returns null if numerator (Calc MC) is missing

### Limitations
- Only works with metrics in `cissa.metrics_outputs` table
- Requires `dataset_id` to exist in `cissa.dataset_versions`
- Parameter set must exist (defaults to "base_case")

## Implementation Notes

### How Rolling Averages Work

```
Data: AAPL Calc MC values for years 2001-2005
2001: 100
2002: 110
2003: 120
2004: 130
2005: 140

3-Year Rolling Average:
2003: (100 + 110 + 120) / 3 = 110.00
2004: (110 + 120 + 130) / 3 = 120.00
2005: (120 + 130 + 140) / 3 = 130.00
```

### Why Empty Result?
- Ticker not in database for given dataset
- Metric doesn't exist for the ticker/years
- Year range filtered out all available data

## Adding New Metrics

To add a new ratio metric (e.g., PE Ratio):

1. Edit `backend/app/config/ratio_metrics.json`
2. Add entry:
```json
{
  "id": "pe_ratio",
  "display_name": "P/E Ratio",
  "description": "Price-to-Earnings Ratio",
  "formula_type": "ratio",
  "numerator": {"metric_name": "Calc MC", "parameter_dependent": false},
  "denominator": {"metric_name": "PROFIT_AFTER_TAX", "parameter_dependent": false},
  "operation": "divide",
  "null_handling": "skip_year",
  "negative_handling": "return_null"
}
```

3. Done! API automatically discovers and serves the new metric.

## Python Example (Using requests library)

```python
import requests
import json

url = "http://localhost:8000/api/v1/metrics/ratio-metrics"
params = {
    "metric": "mb_ratio",
    "tickers": "AAPL,MSFT",
    "dataset_id": "e5e7c8a0-1234-5678-1234-567890123456",
    "temporal_window": "3Y"
}

response = requests.get(url, params=params)

if response.status_code == 200:
    data = response.json()
    
    # Extract AAPL MB Ratio data
    for ticker_data in data["data"]:
        if ticker_data["ticker"] == "AAPL":
            for point in ticker_data["time_series"]:
                print(f"{point['year']}: {point['value']:.2f}")
else:
    print(f"Error: {response.status_code}")
    print(response.json())
```

## Troubleshooting

### Empty result set
- Verify dataset_id exists
- Check that metrics (Calc MC, Calc EE) are in metrics_outputs
- Try 1Y window first (simplest case)

### Slow response (>200ms)
- Database indexes may be missing
- Try filtering by year range (start_year/end_year)
- Verify param_set_id exists

### Wrong values
- Verify temporal_window matches expected calculation
- Check for NULL values in source metrics (Calc MC, Calc EE)
- Confirm dataset has data for those years

## Support

For issues or questions:
1. Check this Quick Reference
2. Review MB_RATIO_IMPLEMENTATION_SUMMARY.md
3. Check RATIO_METRICS_IMPLEMENTATION_PLAN.md for architecture details
