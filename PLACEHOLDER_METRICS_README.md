# Placeholder Metrics for UI Development

## Overview

Placeholder metrics have been inserted into `cissa.metrics_outputs` to allow UI development to proceed while actual metric calculation logic is being implemented.

## Data Details

- **Company**: BHP AU Equity
- **Time Period**: 2003-2022 (20 years)
- **Temporal Window**: 1Y only
- **Total Records**: 180 (9 metrics × 20 years)
- **Status**: All marked as "temporary" in metadata

## Metrics Included

| Metric | Type | Values | Notes |
|--------|------|--------|-------|
| TER | Percentage | -27.7% to 62.8% | Total Economic Return |
| TER-Ke | Percentage | -37.2% to 51.8% | TER minus Cost of Equity |
| TERA | Percentage | -33.1% to 48.1% | Total Economic Return Adjusted |
| TRTE | Absolute | -61,003 to 69,018 | Total Return To Equity |
| WP | Absolute | 39,407 to 272,370 | Weighted Price |
| WC | Absolute | -86,647 to 56,930 | Weighted Cost |
| WC TERA | Absolute | -57,883 to 95,327 | Weighted Cost TERA |
| RA MM | Percentage | -33.2% to 28.2% | Risk Adjusted Market Model |
| TSR | Percentage | -27.7% to 62.8% | Total Shareholder Return |

## Database Information

- **Dataset ID**: `523eeffd-9220-4d27-927b-e418f9c21d8a`
- **Parameter Set ID**: `71a0caa6-b52c-4c5e-b550-1048b7329719`
- **Table**: `cissa.metrics_outputs`
- **Identification**: All records have `metadata->>'type' = 'temporary'`

## Querying the Data

### Get all placeholder metrics for a specific year
```sql
SELECT output_metric_name, output_metric_value
FROM cissa.metrics_outputs
WHERE ticker = 'BHP AU Equity'
  AND fiscal_year = 2023
  AND metadata->>'type' = 'temporary'
ORDER BY output_metric_name;
```

### Get all years for a specific metric
```sql
SELECT fiscal_year, output_metric_value
FROM cissa.metrics_outputs
WHERE ticker = 'BHP AU Equity'
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

