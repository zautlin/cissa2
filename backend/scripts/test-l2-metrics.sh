#!/bin/bash
# ============================================================================
# Test L2 Metrics API - Calculate L2 metrics and view results
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
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         CISSA L2 Metrics API - Test & Verification Script      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"

# Step 1: Check if API is running
echo -e "\n${YELLOW}[1/6] Checking if API is running...${NC}"
if ! curl -s "$API_URL/api/v1/metrics/health" > /dev/null; then
    echo -e "${RED}❌ API is not running on $API_URL${NC}"
    echo "Start it with: ./start-api.sh"
    exit 1
fi
echo -e "${GREEN}✓ API is running${NC}"

# Step 2: Get a dataset_id
echo -e "\n${YELLOW}[2/6] Getting a dataset_id from fundamentals...${NC}"
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

# Step 3: Get a param_set_id
echo -e "\n${YELLOW}[3/6] Getting a param_set_id...${NC}"
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

# Step 4: Calculate L1 metrics first (dependency)
echo -e "\n${YELLOW}[4/6] Ensuring L1 metrics are calculated (prerequisite)...${NC}"
L1_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/metrics/calculate" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"metric_name\": \"Calc MC\"
  }")

if echo "$L1_RESPONSE" | grep -q '"status":"error"'; then
    echo -e "${RED}❌ L1 metric calculation failed${NC}"
    echo "$L1_RESPONSE" | python3 -m json.tool
    exit 1
fi

L1_COUNT=$(echo "$L1_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('results_count', 0))" 2>/dev/null || echo "0")
echo -e "${GREEN}✓ L1 metrics ready ($L1_COUNT records)${NC}"

# Step 5: Calculate L2 metrics
echo -e "\n${YELLOW}[5/6] Calculating L2 metrics...${NC}"
L2_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/metrics/calculate-l2" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"param_set_id\": \"$PARAM_SET_ID\"
  }")

echo "$L2_RESPONSE" | python3 -m json.tool

if echo "$L2_RESPONSE" | grep -q '"status":"error"'; then
    echo -e "${RED}❌ L2 metric calculation failed${NC}"
    exit 1
fi

L2_COUNT=$(echo "$L2_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('results_count', 0))" 2>/dev/null || echo "0")
echo -e "${GREEN}✓ L2 metrics calculated ($L2_COUNT results)${NC}"

# Step 6: Show sample data
echo -e "\n${YELLOW}[6/6] Sample of inserted L2 metrics_outputs records...${NC}"
psql "$DB_URL" << EOF
SELECT 
  ticker,
  fiscal_year,
  output_metric_name,
  output_metric_value,
  created_at
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND param_set_id = '$PARAM_SET_ID'
ORDER BY created_at DESC
LIMIT 15;
EOF

echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    ✓ L2 Test Complete!                         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
