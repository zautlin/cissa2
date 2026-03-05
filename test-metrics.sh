#!/bin/bash
# ============================================================================
# Test Metrics API - Calculate metrics and view results
# ============================================================================

set -e

# Load database URL from .env
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

API_URL="http://localhost:8000"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         CISSA Metrics API - Test & Verification Script         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"

# Step 1: Check if API is running
echo -e "\n${YELLOW}[1/5] Checking if API is running...${NC}"
if ! curl -s "$API_URL/api/v1/metrics/health" > /dev/null; then
    echo -e "${RED}❌ API is not running on $API_URL${NC}"
    echo "Start it with: ./start-api.sh"
    exit 1
fi
echo -e "${GREEN}✓ API is running${NC}"

# Step 2: Get a dataset_id
echo -e "\n${YELLOW}[2/5] Getting a dataset_id from fundamentals...${NC}"
DATASET_ID=$(psql "$DATABASE_URL" -t -c "
    SELECT DISTINCT dataset_id 
    FROM cissa.fundamentals 
    WHERE metric_name = 'SPOT_SHARES' 
    LIMIT 1;
" 2>/dev/null | xargs)

if [ -z "$DATASET_ID" ]; then
    echo -e "${RED}❌ No datasets found in fundamentals table${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found dataset_id: $DATASET_ID${NC}"

# Step 3: Calculate Market Cap
echo -e "\n${YELLOW}[3/5] Calculating Market Cap (Calc MC)...${NC}"
RESPONSE=$(curl -s -X POST "$API_URL/api/v1/metrics/calculate" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"metric_name\": \"Calc MC\"
  }")

echo "$RESPONSE" | python3 -m json.tool

# Step 4: Check metrics_outputs table
echo -e "\n${YELLOW}[4/5] Checking metrics_outputs table...${NC}"
psql "$DATABASE_URL" << EOF
SELECT 
  metric_name,
  COUNT(*) as count,
  MIN(metric_value) as min_value,
  MAX(metric_value) as max_value,
  AVG(metric_value) as avg_value
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
GROUP BY metric_name
ORDER BY metric_name;
EOF

# Step 5: Show sample data
echo -e "\n${YELLOW}[5/5] Sample of inserted metrics_outputs records...${NC}"
psql "$DATABASE_URL" << EOF
SELECT 
  ticker,
  fiscal_year,
  metric_name,
  metric_value,
  created_at
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND metric_name = 'Calc MC'
LIMIT 10;
EOF

echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    ✓ Test Complete!                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
