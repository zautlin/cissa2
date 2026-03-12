#!/bin/bash
# ============================================================================
# L1 Cost of Equity Calculation - Phase 09 Advanced Metrics KE
# ============================================================================
# This script calculates Cost of Equity (KE) using Beta and Risk-Free Rate.
#
# Calculation Method:
#   - Supports FIXED and FLOATING approaches (via cost_of_equity_approach parameter)
#   - FIXED: Rf = benchmark - risk_premium (deterministic)
#   - FLOATING: Rf = Rf_1Y (1-year rolling geometric mean)
#   - Formula (both): KE = Rf + Beta × RiskPremium
#
# Prerequisites:
#   - Phase 07 (Beta) must be completed
#   - Phase 08 (Risk-Free Rate) must be completed
#
# Usage:
#   ./run-l1-cost-of-equity-calc.sh                    # Uses default parameter set
#   ./run-l1-cost-of-equity-calc.sh --param-set-id <uuid>  # Uses specified parameter set
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
echo -e "${BLUE}║       CISSA L1 Cost of Equity Calculation - Phase 09 KE        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"

# Step 1: Check if API is running
echo -e "\n${YELLOW}[1/8] Checking if API is running...${NC}"
if ! curl -s "$API_URL/api/v1/metrics/health" > /dev/null; then
    echo -e "${RED}❌ API is not running on $API_URL${NC}"
    echo "Start it with: ./start-api.sh"
    exit 1
fi
echo -e "${GREEN}✓ API is running${NC}"

# Step 2: Get a dataset_id
echo -e "\n${YELLOW}[2/8] Getting a dataset_id from fundamentals...${NC}"
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
echo -e "\n${YELLOW}[3/8] Resolving parameter set ID...${NC}"
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

# Step 4: Verify prerequisites (Beta and Rf exist)
echo -e "\n${YELLOW}[4/8] Verifying prerequisites...${NC}"

BETA_COUNT=$(psql "$DB_URL" -t -c "
    SELECT COUNT(*) FROM cissa.metrics_outputs
    WHERE dataset_id = '$DATASET_ID'
      AND param_set_id = '$PARAM_SET_ID'
      AND output_metric_name = 'Calc Beta';
" 2>/dev/null | xargs)

if [ "$BETA_COUNT" -eq 0 ]; then
    echo -e "${RED}❌ Beta data not found. Run: ./run-l1-beta-calc.sh${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Beta data found ($BETA_COUNT records)${NC}"

RF_COUNT=$(psql "$DB_URL" -t -c "
    SELECT COUNT(*) FROM cissa.metrics_outputs
    WHERE dataset_id = '$DATASET_ID'
      AND param_set_id = '$PARAM_SET_ID'
      AND output_metric_name IN ('Calc Rf');
" 2>/dev/null | xargs)

if [ "$RF_COUNT" -eq 0 ]; then
    echo -e "${RED}❌ Risk-Free Rate data not found. Run: ./run-l1-rf-calc.sh${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Risk-Free Rate data found ($RF_COUNT records)${NC}"

# Step 5: Show parameter set and KE approach details
echo -e "\n${YELLOW}[5/8] Parameter Set & Cost of Equity Configuration...${NC}"
psql "$DB_URL" << EOF
SELECT 
  p.param_set_id,
  p.param_set_name,
  p.is_default,
  p.created_at
FROM cissa.parameter_sets p
WHERE p.param_set_id = '$PARAM_SET_ID';
EOF

echo -e "\n${CYAN}Cost of Equity Parameters:${NC}"
psql "$DB_URL" << EOF
SELECT 
  parameter_name,
  default_value as current_value
FROM cissa.parameters
WHERE parameter_name IN (
  'cost_of_equity_approach',
  'equity_risk_premium', 
  'fixed_benchmark_return_wealth_preservation'
)
ORDER BY parameter_name;
EOF

# Step 6: Calculate Cost of Equity
echo -e "\n${YELLOW}[6/8] Calculating Cost of Equity (Phase 09 - KE = Rf + Beta × RP)...${NC}"
echo -e "${CYAN}Calling: POST /api/v1/metrics/cost-of-equity/calculate${NC}"

KE_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/metrics/cost-of-equity/calculate" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"param_set_id\": \"$PARAM_SET_ID\"
  }")

echo -e "${CYAN}API Response:${NC}"
echo "$KE_RESPONSE" | python3 -m json.tool

if echo "$KE_RESPONSE" | grep -q '"status":"error"'; then
    echo -e "${RED}❌ Cost of Equity calculation failed${NC}"
    exit 1
fi

KE_COUNT=$(echo "$KE_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('results_count', 0))" 2>/dev/null || echo "0")

echo -e "\n${GREEN}✓ Cost of Equity calculation successful${NC}"
echo -e "${GREEN}  - Records inserted: $KE_COUNT${NC}"

# Step 7: Show Cost of Equity metrics summary
echo -e "\n${YELLOW}[7/8] Cost of Equity Metrics Summary...${NC}"
psql "$DB_URL" << EOF
SELECT 
  output_metric_name,
  COUNT(*) as count,
  MIN(output_metric_value) as min_ke,
  MAX(output_metric_value) as max_ke,
  ROUND(AVG(output_metric_value)::numeric, 6) as avg_ke
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND param_set_id = '$PARAM_SET_ID'
  AND output_metric_name = 'Calc KE'
GROUP BY output_metric_name;
EOF

# Step 8: Show sample Cost of Equity data
echo -e "\n${YELLOW}[8/8] Sample Cost of Equity Records (first 15):${NC}"
psql "$DB_URL" << EOF
SELECT 
  ticker,
  fiscal_year,
  output_metric_name,
  ROUND(output_metric_value::numeric, 4) as ke_value,
  metadata->>'metric_level' as metric_level
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND param_set_id = '$PARAM_SET_ID'
  AND output_metric_name = 'Calc KE'
ORDER BY ticker, fiscal_year
LIMIT 15;
EOF

# Bonus: Show KE with Beta and Rf for verification
echo -e "\n${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                 Verification: KE with Components               ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${CYAN}Sample KE Calculation Verification (first 10 tickers):${NC}"
psql "$DB_URL" << EOF
WITH ke_data AS (
  SELECT 
    ticker, fiscal_year,
    MAX(CASE WHEN output_metric_name = 'Calc KE' THEN output_metric_value END) as ke,
    MAX(CASE WHEN output_metric_name = 'Calc Beta' THEN output_metric_value END) as beta,
    MAX(CASE WHEN output_metric_name = 'Calc Rf' THEN output_metric_value END) as rf_1y
  FROM cissa.metrics_outputs
  WHERE dataset_id = '$DATASET_ID'
    AND param_set_id = '$PARAM_SET_ID'
    AND output_metric_name IN ('Calc KE', 'Calc Beta', 'Calc Rf')
  GROUP BY ticker, fiscal_year
  LIMIT 10
)
SELECT 
  ticker,
  fiscal_year,
  ROUND(rf_1y::numeric, 4) as rf_1y,
  ROUND(beta::numeric, 4) as beta,
  ROUND(ke::numeric, 4) as ke_actual
FROM ke_data
ORDER BY ticker, fiscal_year;
EOF

# Summary
echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ✓ Cost of Equity Calculation Complete!               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${CYAN}Summary:${NC}"
echo -e "  Dataset ID:     $DATASET_ID"
echo -e "  Param Set ID:   $PARAM_SET_ID"
echo -e "  Records:        $KE_COUNT"
echo -e "  Status:         ${GREEN}✓ Success${NC}"

echo -e "\n${CYAN}Next Steps:${NC}"
echo -e "  1. Review Cost of Equity metrics in database:"
echo -e "     SELECT * FROM cissa.metrics_outputs WHERE output_metric_name = 'Calc KE' LIMIT 10;"
echo -e ""
echo -e "  2. Calculate all L1 metrics in sequence:"
echo -e "     ./run-l1-beta-calc.sh && ./run-l1-rf-calc.sh && ./run-l1-cost-of-equity-calc.sh"
echo -e ""
echo -e "  3. Check calculation logs:"
echo -e "     grep -i 'cost.of.equity\\|calc.ke' /tmp/api.log | tail -30"
echo -e ""
