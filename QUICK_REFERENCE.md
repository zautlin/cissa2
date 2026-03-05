# Testing Quick Reference

## 4-Step Workflow

### 1. Start the API
```bash
./start-api.sh
```

### 2. Test Automatically
```bash
./test-metrics.sh
```

### 3. View Results
```bash
psql postgresql://postgres:5VbL7dK4jM8sN6cE2fG@localhost:5432/rozetta -c \
  "SELECT metric_name, COUNT(*) FROM cissa.metrics_outputs GROUP BY metric_name;"
```

### 4. Clear for Next Test
```bash
./clear-metrics.sh
```

---

## Manual Testing with curl

Get a dataset:
```bash
DATASET_ID=$(psql postgresql://postgres:5VbL7dK4jM8sN6cE2fG@localhost:5432/rozetta \
  -t -c "SELECT DISTINCT dataset_id FROM cissa.fundamentals LIMIT 1;" | xargs)
```

Calculate a metric:
```bash
curl -X POST http://localhost:8000/api/v1/metrics/calculate \
  -H "Content-Type: application/json" \
  -d "{\"dataset_id\": \"$DATASET_ID\", \"metric_name\": \"Calc MC\"}"
```

---

## Browse API Interactively

Open in browser: **http://localhost:8000/docs**

- All endpoints visible
- "Try it out" to test
- See responses in real-time

---

## View in Database

```bash
psql postgresql://postgres:5VbL7dK4jM8sN6cE2fG@localhost:5432/rozetta << EOF
SELECT 
  ticker,
  fiscal_year,
  metric_name,
  metric_value
FROM cissa.metrics_outputs
WHERE metric_name = 'Calc MC'
LIMIT 20;
EOF
```

---

## Database Connection

```
postgresql://postgres:5VbL7dK4jM8sN6cE2fG@localhost:5432/rozetta
Schema: cissa
Main tables:
  - cissa.fundamentals (input)
  - cissa.metrics_outputs (results)
```

---

## Supported Metrics (15 total)

- Calc MC
- Calc Assets
- Calc OA
- Calc Op Cost
- Calc Non Op Cost
- Calc Tax Cost
- Calc XO Cost
- Profit Margin
- Op Cost Margin %
- Non-Op Cost Margin %
- Eff Tax Rate
- XO Cost Margin %
- FA Intensity
- Book Equity
- ROA

---

See **TESTING_GUIDE.md** for detailed instructions.
