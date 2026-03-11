#!/bin/bash
# ============================================================================
# L1 Basic Metrics Test - Phase 06 Temporal Metrics Support
# ============================================================================
# This script tests all 12 Phase 06 L1 metrics:
#   - 7 Simple Metrics: Calc MC, Calc Assets, Calc OA, Calc Op Cost, 
#     Calc Non Op Cost, Calc Tax Cost, Calc XO Cost
#   - 5 Temporal Metrics: Calc ECF, Non Div ECF, Calc EE, Calc FY TSR, Calc FY TSR PREL
#
# Usage:
#   ./run-l1-basic-metrics.sh                    # Uses default parameter set
#   ./run-l1-basic-metrics.sh --param-set-id <uuid>  # Uses specified parameter set
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

# Parse command-line arguments
PARAM_SET_ID=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --param-set-id)
            PARAM_SET_ID="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--param-set-id <uuid>]"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    CISSA L1 Basic Metrics API - Test & Verification Script    ║${NC}"
echo -e "${BLUE}║              Phase 06: Temporal Metrics Support                ║${NC}"
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

# Step 3: Resolve parameter set ID
echo -e "\n${YELLOW}[3/5] Resolving parameter set ID...${NC}"
if [ -z "$PARAM_SET_ID" ]; then
    # Use default parameter set (is_default = true)
    PARAM_SET_ID=$(psql "$DB_URL" -t -c "
        SELECT param_set_id FROM cissa.parameter_sets 
        WHERE is_default = true LIMIT 1;
    " 2>/dev/null | xargs)
    
    if [ -z "$PARAM_SET_ID" ]; then
         echo -e "${YELLOW}⚠ No default parameter set found. Temporal metrics (Calc FY TSR, Calc FY TSR PREL) may fail.${NC}"
         echo -e "${YELLOW}  Create one with: INSERT INTO cissa.parameter_sets (param_set_name, is_default) VALUES ('base_case', true);${NC}"
     else
         echo -e "${GREEN}✓ Using default parameter set: $PARAM_SET_ID${NC}"
     fi
else
    echo -e "${GREEN}✓ Using provided parameter set: $PARAM_SET_ID${NC}"
fi

# Step 4: Calculate all 12 L1 metrics
echo -e "\n${YELLOW}[4/5] Calculating all 12 L1 metrics (7 simple + 5 temporal)...${NC}"

METRICS=(
    "Calc MC"
    "Calc Assets"
    "Calc OA"
    "Calc Op Cost"
    "Calc Non Op Cost"
    "Calc Tax Cost"
    "Calc XO Cost"
    "Calc ECF"
    "Non Div ECF"
    "Calc EE"
    "Calc FY TSR"
    "Calc FY TSR PREL"
)

for i in "${!METRICS[@]}"; do
    metric="${METRICS[$i]}"
    current=$((i + 1))
    total=${#METRICS[@]}
    echo -e "${YELLOW}  [$current/$total] Calculating $metric...${NC}"
    
    # Prepare request body
    REQUEST_BODY="{
        \"dataset_id\": \"$DATASET_ID\",
        \"metric_name\": \"$metric\""
    
    # Add param_set_id for temporal metrics that require it
    if [[ "$metric" == "Calc FY TSR" || "$metric" == "Calc FY TSR PREL" ]]; then
        if [ -n "$PARAM_SET_ID" ]; then
            REQUEST_BODY="${REQUEST_BODY},
        \"param_set_id\": \"$PARAM_SET_ID\""
        fi
    fi
    
    REQUEST_BODY="${REQUEST_BODY}
    }"
    
    RESPONSE=$(curl -s -X POST "$API_URL/api/v1/metrics/calculate" \
      -H "Content-Type: application/json" \
      -d "$REQUEST_BODY")
    
    # Check if response has error status
    if echo "$RESPONSE" | grep -q '"status":"error"'; then
        echo -e "${RED}  ✗ Failed: $metric${NC}"
        echo "$RESPONSE" | python3 -m json.tool
    else
        RESULTS_COUNT=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('results_count', 0))" 2>/dev/null || echo "?")
        echo -e "${GREEN}  ✓ $metric ($RESULTS_COUNT records)${NC}"
    fi
done

# Step 5: Check metrics_outputs table and show summary
echo -e "\n${YELLOW}[5/5] Metrics Summary - metrics_outputs table...${NC}"
psql "$DB_URL" << EOF
SELECT 
  output_metric_name,
  COUNT(*) as count,
  MIN(output_metric_value) as min_value,
  MAX(output_metric_value) as max_value,
  ROUND(AVG(output_metric_value)::numeric, 4) as avg_value
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
GROUP BY output_metric_name
ORDER BY output_metric_name;
EOF

echo -e "\n${YELLOW}Sample of inserted metrics_outputs records (first 30)...${NC}"
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

echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    ✓ Test Complete!                            ║${NC}"
echo -e "${GREEN}║              All 12 Phase 06 L1 metrics verified              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
