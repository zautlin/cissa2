# Placeholder Metrics for UI Development

## Overview

Placeholder metrics have been inserted into `cissa.metrics_outputs` to allow UI development to proceed while actual metric calculation logic is being implemented.

## Data Details

- **Company**: CSL AU Equity
- **Time Period**: 2003-2022 (20 years of actual data)
- **Year Range**: 2002-2022 (but 2002 values are skipped as None)
- **Temporal Window**: 1Y only
- **Total Records**: 300 (15 metrics × 20 years)
- **Status**: All marked as "temporary" in metadata

### Data Characteristics

**All Metrics (1-15):**
- **Data Years**: 2003-2022 (20 years)
- **Year Configuration**: 2002 value is None and skipped during insertion
- **Type**: Mix of percentage values (metrics 1-10) and absolute numeric values (metrics 11-15)
- **No NULL values**: Database constraint requires values, so 2002 entries are skipped entirely

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
| Calc EP | Absolute | -1 to 2,748 | Earnings Per Share |
| Calc PAT_Ex | Absolute | 70 to 3,136 | PAT Excluding |
| Calc XO_Cost_Ex | Absolute | -253 to 0 | Extraordinary Cost Excluding |
| Calc FC | Absolute | 0 | Free Cash Flow |
| Calc 1Y FV ECF | Absolute | -1,316 to 2,037 | 1-Year Forward Value ECF |

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

- All metrics span 2003-2022 (20 years of inserted data)
- Year 2002 was defined in the data structure but is skipped (None values not inserted)
- Percentage values (metrics 1-10) stored as decimals (e.g., 0.454 = 45.4%)
- Absolute values (metrics 11-15) stored as integers/floats
- Negative values are represented as negative numbers (not parentheses)
- Metadata includes creation timestamp and notes about placeholder status
- All records marked with `metadata->>'type' = 'temporary'` for easy identification
- **Database Constraint**: `output_metric_value` column is NOT NULL, so 2002 entries could not be inserted

