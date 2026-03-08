# Quick Start: Testing Phase 3 L3 Enhanced Metrics

## One-Line Test (After Prerequisites)

```bash
# From project root
./backend/scripts/test-l3-metrics.sh
```

## Prerequisites Check

```bash
# 1. PostgreSQL running?
sudo systemctl status postgresql

# 2. API running?
curl http://localhost:8000/api/v1/metrics/health

# 3. Data exists?
psql -U postgres -d cissa -c "SELECT COUNT(*) FROM cissa.fundamentals;"
```

## If Prerequisites Missing

```bash
# Start PostgreSQL
sudo systemctl start postgresql

# Start API (in another terminal)
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Then run test
./backend/scripts/test-l3-metrics.sh
```

## What The Test Does

1. ✓ Verifies API is running
2. ✓ Runs Phase 1 L1 metrics (prerequisite)
3. ✓ Gets dataset_id and parameter_set_id from database
4. ✓ **Calculates L3 Enhanced Metrics** via API
5. ✓ Shows results summary by metric type
6. ✓ Displays sample data (first 18 records)
7. ✓ Runs data quality checks

## Success Criteria

You should see:

```
✓ API is running
✓ L1 metrics ready
✓ Found dataset_id: 550e8400-...
✓ Found param_set_id: 660f9500-...
✓ L3 metrics calculated successfully
  - Records inserted: 1500
  - Metrics calculated: Beta, Calc Rf, Calc KE, ROA, ROE, Profit Margin
```

And a table showing 6 L3 metrics (Beta, Calc Rf, Calc KE, ROA, ROE, Profit Margin) with counts and statistics.

## Sample Output Table

```
 output_metric_name | count | min_value | max_value | avg_value
--------------------|-------|-----------|-----------|----------
 Beta               |  1250 |       1.0 |       1.0 | 1.000000
 Calc KE            |  1250 |     0.125 |     0.125 | 0.125000
 Calc Rf            |  1250 |     0.075 |     0.075 | 0.075000
 Profit Margin      |  1250 |     -0.12 |     0.684 | 0.142000
 ROA                |  1250 |     -0.05 |     0.150 | 0.025000
 ROE                |  1250 |     -0.50 |     2.100 | 0.650000
```

## Verify Results Manually

```bash
# Count L3 metrics in database
psql -U postgres -d cissa -c "
SELECT COUNT(*) 
FROM cissa.metrics_outputs 
WHERE metadata->>'metric_level' = 'L3';"

# Show sample L3 records
psql -U postgres -d cissa -c "
SELECT ticker, fiscal_year, output_metric_name, output_metric_value
FROM cissa.metrics_outputs
WHERE metadata->>'metric_level' = 'L3'
ORDER BY ticker, fiscal_year, output_metric_name
LIMIT 20;"
```

## Expected Data Volume

- **Tickers:** 250 (or count of distinct tickers in fundamentals)
- **Fiscal Years:** ~5 years per ticker
- **Metrics per ticker-year:** 6 (Beta, Calc Rf, Calc KE, ROA, ROE, Profit Margin)
- **Total L3 Records:** ~7,500 (250 × 5 × 6)

## Understanding L3 Metrics

| Metric | Calculation | Data Type | Notes |
|--------|-----------|-----------|-------|
| Beta | 1.0 | Placeholder | Ready for rolling OLS implementation |
| Calc Rf | From parameter set | % (decimal) | Example: 0.075 = 7.5% |
| Calc KE | Rf + Beta × Risk Premium | % (decimal) | Example: 0.125 = 12.5% |
| ROA | PAT / Total Assets | % (decimal) | Example: 0.025 = 2.5% |
| ROE | PAT / Total Equity | % (decimal) | Example: 0.65 = 65% |
| Profit Margin | PAT / Revenue | % (decimal) | Example: 0.184 = 18.4% |

**All values stored as decimals** (not percentages). Multiply by 100 to display as percentages.

## Troubleshooting

### "API is not running"
```bash
# Start in new terminal
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### "No datasets found"
```bash
# Check data load
psql -U postgres -d cissa -c "SELECT COUNT(*) FROM cissa.fundamentals;"
# Should be > 0
```

### "L3 metric calculation failed"
```bash
# Check error logs
grep -i 'error\|enhanced' /tmp/api.log | tail -30
```

### "No parameter sets found"
```bash
# Create one
psql -U postgres -d cissa -c "
INSERT INTO cissa.parameter_sets (param_set_name) 
VALUES ('base_case');"
```

## Next Steps After Success

1. **Review results:** Check `.planning/PHASE3_OUTPUT_EXAMPLE.md`
2. **Plan Phase 4:** `gsd-plan-phase 04-phase-name` (if exists)
3. **Future enhancements:**
   - Port Beta rolling OLS calculation
   - Implement Economic Profit
   - Add TSR with Franking Credits

## Files Created

```
backend/scripts/
├── test-l3-metrics.sh    ← Main test script (THIS ONE!)
├── test-l2-metrics.sh    ← Phase 2 test (prerequisite)
├── test-metrics.sh       ← Phase 1 test (prerequisite)
└── README.md             ← Full documentation
```

---

**Ready?** Run: `./backend/scripts/test-l3-metrics.sh`
