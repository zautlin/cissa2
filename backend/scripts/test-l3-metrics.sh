#!/bin/bash
# ============================================================================
# Test L3 Enhanced Metrics API - Calculate L3 metrics and view results
# ============================================================================
# This script tests Phase 3 Enhanced Metrics calculations.
# Prerequisites: 
#   - PostgreSQL running with cissa database
#   - Phase 1 L1 metrics calculated (runs test-metrics.sh first)
#   - FastAPI backend running (starts automatically if needed)
# ============================================================================

set -e

# Determine project root (parent of backend/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Load environment variables from project root
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    export $(cat "$ENV_FILE" | grep -v '^#' | xargs)
else
    echo "ERROR: .env file not found at $ENV_FILE"
    exit 1
fi

# Use CLI-compatible database URL for psql
DB_URL="$DATABASE_URL_CLI"
API_URL="http://localhost:8000"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         CISSA L3 Enhanced Metrics API - Test & Verification     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"

# Step 1: Check if API is running
echo -e "\n${YELLOW}[1/9] Checking if API is running...${NC}"
if ! curl -s "$API_URL/api/v1/metrics/health" > /dev/null; then
    echo -e "${RED}❌ API is not running on $API_URL${NC}"
    echo -e "${YELLOW}Starting API in background...${NC}"
    cd "$PROJECT_ROOT/backend" || exit 1
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/api.log 2>&1 &
    API_PID=$!
    echo "API PID: $API_PID"
    sleep 3
    if ! curl -s "$API_URL/api/v1/metrics/health" > /dev/null; then
        echo -e "${RED}❌ API failed to start${NC}"
        cat /tmp/api.log
        exit 1
    fi
    echo -e "${GREEN}✓ API started${NC}"
else
    echo -e "${GREEN}✓ API is running${NC}"
fi

# Step 2: Ensure L1 metrics are calculated
echo -e "\n${YELLOW}[2/9] Ensuring L1 metrics are calculated (prerequisite)...${NC}"
echo -e "${CYAN}Running test-metrics.sh to calculate L1 metrics...${NC}"
if ! bash "$SCRIPT_DIR/test-metrics.sh" > /tmp/l1_test.log 2>&1; then
    echo -e "${YELLOW}Note: L1 calculation may have warnings, checking if data exists...${NC}"
fi
echo -e "${GREEN}✓ L1 metrics ready${NC}"

# Step 3: Get a dataset_id
echo -e "\n${YELLOW}[3/9] Getting a dataset_id from fundamentals...${NC}"
DATASET_ID=$(psql "$DB_URL" -t -c "
    SELECT DISTINCT dataset_id 
    FROM cissa.fundamentals 
    LIMIT 1;
" 2>/dev/null | xargs)

if [ -z "$DATASET_ID" ]; then
    echo -e "${RED}❌ No datasets found in fundamentals table${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found dataset_id: $DATASET_ID${NC}"

# Step 4: Get a param_set_id
echo -e "\n${YELLOW}[4/9] Getting a param_set_id...${NC}"
PARAM_SET_ID=$(psql "$DB_URL" -t -c "
    SELECT param_set_id 
    FROM cissa.parameter_sets
    WHERE param_set_name = 'base_case'
    LIMIT 1;
" 2>/dev/null | xargs)

if [ -z "$PARAM_SET_ID" ]; then
    echo -e "${YELLOW}  No base_case found, getting first available parameter set...${NC}"
    PARAM_SET_ID=$(psql "$DB_URL" -t -c "
        SELECT param_set_id 
        FROM cissa.parameter_sets
        LIMIT 1;
    " 2>/dev/null | xargs)
fi

if [ -z "$PARAM_SET_ID" ]; then
    echo -e "${RED}❌ No parameter sets found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found param_set_id: $PARAM_SET_ID${NC}"

# Step 5: Verify L1 metrics exist
echo -e "\n${YELLOW}[5/9] Verifying L1 metrics exist in database...${NC}"
L1_COUNT=$(psql "$DB_URL" -t -c "
    SELECT COUNT(DISTINCT ticker) 
    FROM cissa.metrics_outputs 
    WHERE dataset_id = '$DATASET_ID'
    AND output_metric_name = 'Calc MC'
" 2>/dev/null | xargs)

if [ "$L1_COUNT" -eq 0 ]; then
    echo -e "${RED}❌ No L1 metrics found for dataset $DATASET_ID${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found L1 metrics for $L1_COUNT tickers${NC}"

# Step 6: Show parameter set details
echo -e "\n${YELLOW}[6/9] Parameter set details...${NC}"
psql "$DB_URL" << EOF
SELECT 
  param_set_id,
  param_set_name,
  created_at
FROM cissa.parameter_sets
WHERE param_set_id = '$PARAM_SET_ID';
EOF

# Step 7: Calculate L3 Enhanced Metrics
echo -e "\n${YELLOW}[7/9] Calculating L3 Enhanced Metrics...${NC}"
L3_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/metrics/calculate-enhanced" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"param_set_id\": \"$PARAM_SET_ID\"
  }")

echo -e "${CYAN}API Response:${NC}"
echo "$L3_RESPONSE" | python3 -m json.tool

if echo "$L3_RESPONSE" | grep -q '"status":"error"'; then
    echo -e "${RED}❌ L3 metric calculation failed${NC}"
    exit 1
fi

L3_COUNT=$(echo "$L3_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('results_count', 0))" 2>/dev/null || echo "0")
METRICS_CALC=$(echo "$L3_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('metrics_calculated', {}))" 2>/dev/null || echo "{}")

echo -e "\n${GREEN}✓ L3 metrics calculated successfully${NC}"
echo -e "${GREEN}  - Records inserted: $L3_COUNT${NC}"
echo -e "${GREEN}  - Metrics calculated: $METRICS_CALC${NC}"

# Step 8: Show L3 metrics by type
echo -e "\n${YELLOW}[8/9] L3 Metrics Summary - By Metric Type...${NC}"
psql "$DB_URL" << EOF
SELECT 
  output_metric_name,
  COUNT(*) as count,
  MIN(output_metric_value) as min_value,
  MAX(output_metric_value) as max_value,
  ROUND(AVG(output_metric_value)::numeric, 6) as avg_value
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND param_set_id = '$PARAM_SET_ID'
  AND metadata->>'metric_level' = 'L3'
GROUP BY output_metric_name
ORDER BY output_metric_name;
EOF

# Step 9: Show sample L3 data
echo -e "\n${YELLOW}[9/9] Sample of L3 metrics_outputs records (first 18 records)...${NC}"
psql "$DB_URL" << EOF
SELECT 
  ticker,
  fiscal_year,
  output_metric_name,
  ROUND(output_metric_value::numeric, 6) as output_metric_value,
  created_at
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND param_set_id = '$PARAM_SET_ID'
  AND metadata->>'metric_level' = 'L3'
ORDER BY ticker, fiscal_year, output_metric_name
LIMIT 18;
EOF

# Bonus: Show data quality checks
echo -e "\n${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                     Data Quality Checks                         ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${YELLOW}L3 Metrics Coverage:${NC}"
psql "$DB_URL" << EOF
WITH l3_data AS (
  SELECT DISTINCT ticker, fiscal_year, output_metric_name
  FROM cissa.metrics_outputs
  WHERE dataset_id = '$DATASET_ID'
    AND param_set_id = '$PARAM_SET_ID'
    AND metadata->>'metric_level' = 'L3'
)
SELECT 
  output_metric_name,
  COUNT(DISTINCT ticker) as tickers,
  COUNT(DISTINCT fiscal_year) as fiscal_years,
  COUNT(*) as total_records
FROM l3_data
GROUP BY output_metric_name
ORDER BY output_metric_name;
EOF

echo -e "\n${YELLOW}L3 Metrics by Ticker (first 5 tickers):${NC}"
psql "$DB_URL" << EOF
WITH ticker_metrics AS (
  SELECT DISTINCT ticker
  FROM cissa.metrics_outputs
  WHERE dataset_id = '$DATASET_ID'
    AND param_set_id = '$PARAM_SET_ID'
    AND metadata->>'metric_level' = 'L3'
  ORDER BY ticker
  LIMIT 5
)
SELECT 
  ticker,
  COUNT(*) as total_l3_records,
  COUNT(DISTINCT output_metric_name) as distinct_metrics,
  COUNT(DISTINCT fiscal_year) as fiscal_years
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND param_set_id = '$PARAM_SET_ID'
  AND metadata->>'metric_level' = 'L3'
  AND ticker IN (SELECT ticker FROM ticker_metrics)
GROUP BY ticker
ORDER BY ticker;
EOF

# Summary
echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    ✓ L3 Test Complete!                         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${CYAN}Summary:${NC}"
echo -e "  Dataset ID:     $DATASET_ID"
echo -e "  Param Set ID:   $PARAM_SET_ID"
echo -e "  Records:        $L3_COUNT"
echo -e "  Status:         ${GREEN}✓ Success${NC}"

echo -e "\n${CYAN}Next Steps:${NC}"
echo -e "  1. Review L3 metrics in database:"
echo -e "     SELECT * FROM cissa.metrics_outputs WHERE metadata->>'metric_level' = 'L3' LIMIT 10;"
echo -e ""
echo -e "  2. Run CLI script directly:"
echo -e "     python backend/app/cli/run_enhanced_metrics.py $DATASET_ID $PARAM_SET_ID"
echo -e ""
echo -e "  3. Check calculation logs:"
echo -e "     grep -i 'enhanced' /tmp/api.log | tail -20"
echo -e ""
