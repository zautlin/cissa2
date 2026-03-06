#!/bin/bash
# ============================================================================
# Test Metrics API - Calculate metrics and view results
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
DATASET_ID=$(psql "$DB_URL" -t -c "
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

# Step 3: Calculate all 15 L1 metrics
echo -e "\n${YELLOW}[3/7] Calculating all 15 L1 metrics...${NC}"

METRICS=(
    "Calc MC"
    "Calc Assets"
    "Calc OA"
    "Calc Op Cost"
    "Calc Non Op Cost"
    "Calc Tax Cost"
    "Calc XO Cost"
    "Profit Margin"
    "Op Cost Margin %"
    "Non-Op Cost Margin %"
    "Eff Tax Rate"
    "XO Cost Margin %"
    "FA Intensity"
    "Book Equity"
    "ROA"
)

for i in "${!METRICS[@]}"; do
    metric="${METRICS[$i]}"
    current=$((i + 1))
    total=${#METRICS[@]}
    echo -e "${YELLOW}  [$current/$total] Calculating $metric...${NC}"
    
    RESPONSE=$(curl -s -X POST "$API_URL/api/v1/metrics/calculate" \
      -H "Content-Type: application/json" \
      -d "{
        \"dataset_id\": \"$DATASET_ID\",
        \"metric_name\": \"$metric\"
      }")
    
    # Check if response has error status
    if echo "$RESPONSE" | grep -q '"status":"error"'; then
        echo -e "${RED}  ✗ Failed: $metric${NC}"
        echo "$RESPONSE" | python3 -m json.tool
    else
        RESULTS_COUNT=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('results_count', 0))" 2>/dev/null || echo "?")
        echo -e "${GREEN}  ✓ $metric ($RESULTS_COUNT records)${NC}"
    fi
done

# Step 4: Check metrics_outputs table
echo -e "\n${YELLOW}[4/7] Checking metrics_outputs table (all L1 metrics)...${NC}"
psql "$DB_URL" << EOF
SELECT 
  output_metric_name,
  COUNT(*) as count,
  MIN(output_metric_value) as min_value,
  MAX(output_metric_value) as max_value,
  AVG(output_metric_value) as avg_value
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
GROUP BY output_metric_name
ORDER BY output_metric_name;
EOF

# Step 5: Show sample data for each metric
echo -e "\n${YELLOW}[5/7] Sample of inserted metrics_outputs records (first 3 metrics)...${NC}"
psql "$DB_URL" << EOF
SELECT 
  ticker,
  fiscal_year,
  output_metric_name,
  output_metric_value,
  created_at
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
ORDER BY output_metric_name, ticker, fiscal_year
LIMIT 30;
EOF

# Step 6: Get param_set_id for L2 calculation
echo -e "\n${YELLOW}[6/7] Getting param_set_id for L2 calculation...${NC}"
PARAM_SET_ID=$(psql "$DB_URL" -t -c "
    SELECT param_set_id 
    FROM cissa.parameter_sets 
    WHERE param_set_name = 'base_case' 
    LIMIT 1;
" 2>/dev/null | xargs)

if [ -z "$PARAM_SET_ID" ]; then
    echo -e "${RED}❌ No base_case parameter set found${NC}"
else
    echo -e "${GREEN}✓ Found param_set_id: $PARAM_SET_ID${NC}"
    
    # Step 7: Try to calculate L2 metrics
    echo -e "\n${YELLOW}[7/7] Attempting L2 metrics calculation...${NC}"
    L2_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/metrics/calculate-l2" \
      -H "Content-Type: application/json" \
      -d "{
        \"dataset_id\": \"$DATASET_ID\",
        \"param_set_id\": \"$PARAM_SET_ID\"
      }")
    
    echo "$L2_RESPONSE" | python3 -m json.tool
    
    # Check if L2 succeeded
    if echo "$L2_RESPONSE" | grep -q '"status":"success"'; then
        echo -e "\n${YELLOW}L2 Metrics Results in Database:${NC}"
        psql "$DB_URL" << EOF
SELECT 
  output_metric_name,
  COUNT(*) as count,
  MIN(output_metric_value) as min_value,
  MAX(output_metric_value) as max_value,
  AVG(output_metric_value) as avg_value
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND output_metric_name NOT IN ('Calc MC', 'Calc Assets', 'Calc OA', 'Calc Op Cost', 
                                  'Calc Non Op Cost', 'Calc Tax Cost', 'Calc XO Cost',
                                  'Profit Margin', 'Op Cost Margin %', 'Non-Op Cost Margin %',
                                  'Eff Tax Rate', 'XO Cost Margin %', 'FA Intensity', 
                                  'Book Equity', 'ROA')
GROUP BY output_metric_name
ORDER BY output_metric_name;
EOF
    fi
fi

echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    ✓ Test Complete!                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
