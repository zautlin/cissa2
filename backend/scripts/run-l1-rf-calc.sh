#!/bin/bash
# ============================================================================
# L1 Risk-Free Rate Calculation - Phase 08 Risk-Free Rate from Market Data
# ============================================================================
# This script calculates Risk-Free Rate metrics:
#   - Calc Rf: Final metric using Fixed or Floating approach
#
# Calculation Method:
#   - 12-month rolling geometric mean of monthly Rf rates
#   - Rf_1Y: Rounded to nearest 0.5% (default rounding)
#   - Fixed approach: Calc Rf = Benchmark - Risk Premium (static, same all years)
#   - Floating approach: Calc Rf = Rf_1Y (dynamic, varies by year)
#
# Usage:
#   ./run-l1-rf-calc.sh                    # Uses default parameter set
#   ./run-l1-rf-calc.sh --param-set-id <uuid>  # Uses specified parameter set
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
echo -e "${BLUE}║     CISSA L1 Risk-Free Rate Calculation - Phase 08 Rf          ║${NC}"
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
    WHERE metric_name = 'SPOT_SHARES' 
    LIMIT 1;
" 2>/dev/null | xargs)

if [ -z "$DATASET_ID" ]; then
    echo -e "${RED}❌ No datasets found in fundamentals table${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found dataset_id: $DATASET_ID${NC}"

# Step 3: Resolve parameter set ID
echo -e "\n${YELLOW}[3/6] Resolving parameter set ID...${NC}"
if [ -z "$PARAM_SET_ID" ]; then
    # Use default parameter set (is_default = true)
    PARAM_SET_ID=$(psql "$DB_URL" -t -c "
        SELECT param_set_id FROM cissa.parameter_sets 
        WHERE is_default = true LIMIT 1;
    " 2>/dev/null | xargs)
    
    if [ -z "$PARAM_SET_ID" ]; then
        echo -e "${RED}❌ No default parameter set found${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Using parameter set: $PARAM_SET_ID${NC}"

# Step 4: Show parameter details
echo -e "\n${YELLOW}[4/6] Parameter Set Details...${NC}"
psql "$DB_URL" << EOF
SELECT 
  param_set_id,
  param_set_name,
  is_default,
  created_at
FROM cissa.parameter_sets
WHERE param_set_id = '$PARAM_SET_ID';
EOF

# Step 5: Calculate Risk-Free Rate
echo -e "\n${YELLOW}[5/6] Calculating Risk-Free Rate (Phase 08 - Rolling Geometric Mean)...${NC}"
echo -e "${CYAN}Calling: POST /api/v1/metrics/rates/calculate${NC}"

RF_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/metrics/rates/calculate" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"param_set_id\": \"$PARAM_SET_ID\"
  }")

echo -e "${CYAN}API Response:${NC}"
echo "$RF_RESPONSE" | python3 -m json.tool

if echo "$RF_RESPONSE" | grep -q '"status":"error"'; then
    echo -e "${RED}❌ Risk-Free Rate calculation failed${NC}"
    exit 1
fi

RF_COUNT=$(echo "$RF_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('results_count', 0))" 2>/dev/null || echo "0")

echo -e "\n${GREEN}✓ Risk-Free Rate calculation successful${NC}"
echo -e "${GREEN}  - Records inserted: $RF_COUNT${NC}"

# Step 6: Show Rf metrics summary
echo -e "\n${YELLOW}[6/6] Risk-Free Rate Metrics Summary...${NC}"
psql "$DB_URL" << EOF
SELECT 
  output_metric_name,
  COUNT(*) as count,
  MIN(output_metric_value) as min_rf,
  MAX(output_metric_value) as max_rf,
  ROUND(AVG(output_metric_value)::numeric, 6) as avg_rf
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND param_set_id = '$PARAM_SET_ID'
  AND output_metric_name = 'Calc Rf'
GROUP BY output_metric_name
ORDER BY output_metric_name;
EOF

echo -e "\n${GREEN}Sample Risk-Free Rate Records (first 15):${NC}"
psql "$DB_URL" << EOF
SELECT 
  ticker,
  fiscal_year,
  output_metric_name,
  ROUND(output_metric_value::numeric, 6) as rf_value,
  metadata->>'metric_level' as metric_level
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND param_set_id = '$PARAM_SET_ID'
  AND output_metric_name = 'Calc Rf'
ORDER BY ticker, fiscal_year, output_metric_name
LIMIT 15;
EOF

# Summary
echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            ✓ Risk-Free Rate Calculation Complete!              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${CYAN}Summary:${NC}"
echo -e "  Dataset ID:     $DATASET_ID"
echo -e "  Param Set ID:   $PARAM_SET_ID"
echo -e "  Records:        $RF_COUNT"
echo -e "  Status:         ${GREEN}✓ Success${NC}"

echo -e "\n${CYAN}Next Steps:${NC}"
echo -e "  1. Calculate Cost of Equity (KE):"
echo -e "     ./run-l1-cost-of-equity-calc.sh"
echo -e ""
echo -e "  2. Review Calc Rf metrics in database:"
echo -e "     SELECT * FROM cissa.metrics_outputs WHERE output_metric_name = 'Calc Rf' LIMIT 10;"
echo -e ""
echo -e "  3. Check calculation logs:"
echo -e "     grep -i 'risk.free' /tmp/api.log | tail -20"
echo -e ""
