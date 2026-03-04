# Post-Ingestion Validation Queries

Run these queries after you complete the data re-ingestion to verify the FISCAL/MONTHLY data flow is working correctly.

## 1. Period Type Distribution

Verify that both FISCAL and MONTHLY data made it through the pipeline:

```sql
SELECT period_type, COUNT(*) as count
FROM cissa.fundamentals
GROUP BY period_type
ORDER BY count DESC;
```

**Expected Results:**
- FISCAL: ~140,670 rows
- MONTHLY: ~133,188 rows
- Total: ~273,858 rows

---

## 2. ASX200 Parent Index Assignment

Verify that top 200 companies are marked as ASX200:

```sql
SELECT parent_index, COUNT(*) as count
FROM cissa.companies
GROUP BY parent_index
ORDER BY count DESC;
```

**Expected Results:**
- ASX200: exactly 200 companies
- NULL: ~300 companies (other ASX companies)

---

## 3. Sample FISCAL Data

Verify FISCAL records have NULL for fiscal_month and fiscal_day:

```sql
SELECT ticker, fiscal_year, fiscal_month, fiscal_day, metric_name, value
FROM cissa.fundamentals
WHERE period_type = 'FISCAL'
LIMIT 5;
```

**Expected Results:**
- fiscal_year: populated (e.g., 2002, 2003, etc.)
- fiscal_month: NULL
- fiscal_day: NULL
- Examples: BHP, RIO, CBA, CSL, NAB

---

## 4. Sample MONTHLY Data

Verify MONTHLY records have all three date components populated:

```sql
SELECT ticker, fiscal_year, fiscal_month, fiscal_day, metric_name, value
FROM cissa.fundamentals
WHERE period_type = 'MONTHLY'
LIMIT 5;
```

**Expected Results:**
- fiscal_year: populated (1981 onwards)
- fiscal_month: 1-12
- fiscal_day: 1-31
- Metric: "Company TSR (Monthly)"

---

## 5. Imputation Effectiveness

Verify no NULL values remain after imputation (all gaps filled):

```sql
SELECT 
    period_type,
    COUNT(*) as total_records,
    SUM(CASE WHEN value IS NOT NULL THEN 1 ELSE 0 END) as non_null_values,
    SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) as null_values
FROM cissa.fundamentals
GROUP BY period_type;
```

**Expected Results:**
- null_values: 0 for both FISCAL and MONTHLY
- non_null_values: equals total_records

---

## 6. Optimization FK Integrity

Verify no orphaned metrics records (all metrics are referenced by at least one optimization):

```sql
SELECT COUNT(*) as orphaned_metrics
FROM cissa.metrics_outputs mo
WHERE NOT EXISTS (
    SELECT 1 FROM cissa.optimization_outputs oo 
    WHERE oo.metrics_output_id = mo.id
);
```

**Expected Results:**
- orphaned_metrics: 0 (all metrics are correctly referenced)

---

## 7. Dataset Versions Status

Check that the dataset was properly versioned:

```sql
SELECT id, dataset_name, status, processed_at
FROM cissa.dataset_versions
ORDER BY processed_at DESC
LIMIT 1;
```

**Expected Results:**
- status: 'processed' or 'completed'
- processed_at: recent timestamp

---

## 8. Metric Diversity Check

Verify we have multiple metrics across both period types:

```sql
SELECT period_type, COUNT(DISTINCT metric_name) as unique_metrics
FROM cissa.fundamentals
GROUP BY period_type;
```

**Expected Results:**
- FISCAL: ~15-20 unique metrics
- MONTHLY: 1-2 unique metrics (e.g., "Company TSR (Monthly)")

---

## Debugging: If FISCAL count is low

If FISCAL rows are still missing, check for extraction failures in your application logs:

Look for these log messages:
- "FISCAL extracted: X" - successful extractions
- "FISCAL failed: X" - failed extractions
- "FISCAL regex no match" - periods that didn't match the regex
- "FISCAL extraction failures (sample)" - example problem cases

---

## Quick Summary Query

Get an overview of the entire pipeline:

```sql
SELECT 
    'Fundamentals' as table_name,
    COUNT(*) as total_records,
    COUNT(DISTINCT ticker) as unique_companies,
    COUNT(DISTINCT metric_name) as unique_metrics,
    COUNT(DISTINCT period_type) as period_types
FROM cissa.fundamentals

UNION ALL

SELECT 
    'Companies' as table_name,
    COUNT(*) as total_records,
    COUNT(DISTINCT parent_index) as unique_indexes,
    0 as unique_metrics,
    0 as period_types
FROM cissa.companies

UNION ALL

SELECT 
    'Optimization Outputs' as table_name,
    COUNT(*) as total_records,
    0 as unique_companies,
    0 as unique_metrics,
    0 as period_types
FROM cissa.optimization_outputs;
```
