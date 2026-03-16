# Placeholder Metrics for UI Development

## Overview

Placeholder metrics have been inserted into `cissa.metrics_outputs` to allow UI development to proceed while actual metric calculation logic is being implemented.

## Data Details

- **Company**: CSL AU Equity
- **Time Period**: 2003-2022 (20 years)
- **Temporal Window**: 1Y only
- **Total Records**: 200 (10 metrics × 20 years)
- **Status**: All marked as "temporary" in metadata

## Metrics Included

| Metric | Type | Values | Notes |
|--------|------|--------|-------|
| TER | Percentage | -62.2% to 90.2% | Total Economic Return |
| TER-Ke | Percentage | -71.7% to 80.7% | TER minus Cost of Equity |
| TERA | Percentage | -65.4% to 70.9% | Total Economic Return Adjusted |
| TRTE | Absolute | -3,173 to 34,067 | Total Return To Equity |
| WP | Absolute | 2,093 to 103,757 | Weighted Price |
| WC | Absolute | -3,959 to 27,735 | Weighted Cost |
| WC TERA | Absolute | -3,338 to 35,740 | Weighted Cost TERA |
| RA MM | Percentage | -30.5% to 23.0% | Risk Adjusted Market Model |
| TSR | Percentage | -62.2% to 90.2% | Total Shareholder Return |
| EP PCT | Percentage | -3.8% to 58.7% | Earnings Per Share Percentage |

## Database Information

- **Dataset ID**: `13d1f4ca-6c72-4be2-9d21-b86bf685ceb2`
- **Parameter Set ID**: `15d7dc52-4e6f-44ec-9aff-0be42ff11031`
- **Table**: `cissa.metrics_outputs`
- **Identification**: All records have `metadata->>'type' = 'temporary'`

## Querying the Data

### Get all placeholder metrics for a specific year
```sql
SELECT output_metric_name, output_metric_value
FROM cissa.metrics_outputs
WHERE ticker = 'CSL AU Equity'
  AND fiscal_year = 2023
  AND metadata->>'type' = 'temporary'
ORDER BY output_metric_name;
```

### Get all years for a specific metric
```sql
SELECT fiscal_year, output_metric_value
FROM cissa.metrics_outputs
WHERE ticker = 'CSL AU Equity'
  AND output_metric_name = 'TSR'
  AND metadata->>'type' = 'temporary'
ORDER BY fiscal_year;
```

## Script Information

- **Script Location**: `/home/ubuntu/cissa/populate_placeholder_metrics.py`
- **Script Type**: Python async script using SQLAlchemy
- **Database Connection**: Uses `DATABASE_URL` from `.env`

## Next Steps

When actual calculation logic is implemented:

1. Keep these placeholder records or remove them based on requirements
2. Update metric calculation services to populate real data
3. Consider removing "temporary" status once actual data is live

## Notes

- All percentage values are stored as decimals (e.g., 15.5% = 0.155)
- All absolute values are stored as floats
- Negative values are represented as negative numbers (not parentheses)
- Metadata includes creation timestamp and notes about placeholder status

