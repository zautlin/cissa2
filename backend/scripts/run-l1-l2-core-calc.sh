#!/bin/bash
# ============================================================================
# L2 Core Metrics Calculation - Phase 10a (EP, PAT_EX, XO_COST_EX, FC)
# ============================================================================
# This script calculates core Level 2 metrics using L1 data and lagged versions.
#
# Metrics Calculated:
#   - EP: Economic Profit = pat - (ke_open × ee_open)
#   - PAT_EX: Adjusted Profit = (ep / |ee_open + ke_open|) × ee_open
#   - XO_COST_EX: Adjusted XO Cost = patxo - pat_ex
#   - FC: Franking Credit (conditional on incl_franking parameter)
#
# Prerequisites:
#   - Phase 06 (L1 Basic Metrics: PAT, PATXO, EE) must be completed
#   - Phase 09 (Cost of Equity: KE) must be completed
#
# Usage:
#   ./run-l1-l2-core-calc.sh                    # Uses default parameter set
#   ./run-l1-l2-core-calc.sh --param-set-id <uuid>  # Uses specified parameter set
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
echo -e "${BLUE}║    CISSA L2 Core Metrics Calculation - Phase 10a              ║${NC}"
echo -e "${BLUE}║              (EP, PAT_EX, XO_COST_EX, FC)                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"

# Step 1: Check if API is running
echo -e "\n${YELLOW}[1/9] Checking if API is running...${NC}"
if ! curl -s "$API_URL/api/v1/metrics/health" > /dev/null; then
    echo -e "${RED}❌ API is not running on $API_URL${NC}"
    echo "Start it with: ./start-api.sh"
    exit 1
fi
echo -e "${GREEN}✓ API is running${NC}"

# Step 2: Get a dataset_id
echo -e "\n${YELLOW}[2/9] Getting a dataset_id from fundamentals...${NC}"
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
echo -e "\n${YELLOW}[3/9] Resolving parameter set ID...${NC}"
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

# Step 4: Verify prerequisites (L1 metrics and KE exist)
echo -e "\n${YELLOW}[4/9] Verifying prerequisites...${NC}"

# Check PAT (from Phase 06)
PAT_COUNT=$(psql "$DB_URL" -t -c "
    SELECT COUNT(*) FROM cissa.metrics_outputs
    WHERE dataset_id = '$DATASET_ID'
      AND param_set_id = '$PARAM_SET_ID'
      AND output_metric_name = 'PAT';
" 2>/dev/null | xargs)

if [ "$PAT_COUNT" -eq 0 ]; then
    echo -e "${RED}❌ PAT data not found. Phase 06 (L1 Basic Metrics) required${NC}"
    exit 1
fi
echo -e "${GREEN}✓ L1 Basic Metrics (PAT, PATXO, EE) found ($PAT_COUNT records)${NC}"

# Check KE (from Phase 09)
KE_COUNT=$(psql "$DB_URL" -t -c "
    SELECT COUNT(*) FROM cissa.metrics_outputs
    WHERE dataset_id = '$DATASET_ID'
      AND param_set_id = '$PARAM_SET_ID'
      AND output_metric_name = 'Calc KE';
" 2>/dev/null | xargs)

if [ "$KE_COUNT" -eq 0 ]; then
    echo -e "${RED}❌ Cost of Equity (KE) data not found. Run: ./run-l1-cost-of-equity-calc.sh${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Phase 09 Cost of Equity data found ($KE_COUNT records)${NC}"

# Step 5: Show parameter set and Franking configuration
echo -e "\n${YELLOW}[5/9] Parameter Set & Franking Configuration...${NC}"
psql "$DB_URL" << EOF
SELECT 
  p.param_set_id,
  p.param_set_name,
  p.is_default,
  p.created_at
FROM cissa.parameter_sets p
WHERE p.param_set_id = '$PARAM_SET_ID';
EOF

echo -e "\n${CYAN}Franking & L2 Metrics Parameters:${NC}"
psql "$DB_URL" << EOF
SELECT 
  parameter_name,
  default_value as current_value
FROM cissa.parameters
WHERE parameter_name IN (
  'incl_franking',
  'frank_tax_rate', 
  'value_franking_cr',
  'franking'
)
ORDER BY parameter_name;
EOF

# Step 6: Calculate Core L2 Metrics
echo -e "\n${YELLOW}[6/9] Calculating Core L2 Metrics (Phase 10a)...${NC}"
echo -e "${CYAN}Calling: POST /api/v1/metrics/l2-core/calculate${NC}"

L2_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/metrics/l2-core/calculate" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"param_set_id\": \"$PARAM_SET_ID\"
  }")

echo -e "${CYAN}API Response:${NC}"
echo "$L2_RESPONSE" | python3 -m json.tool

if echo "$L2_RESPONSE" | grep -q '"status":"error"'; then
    echo -e "${RED}❌ Core L2 metrics calculation failed${NC}"
    exit 1
fi

L2_COUNT=$(echo "$L2_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('results_count', 0))" 2>/dev/null || echo "0")

echo -e "\n${GREEN}✓ Core L2 metrics calculation successful${NC}"
echo -e "${GREEN}  - Base records (per metric): $L2_COUNT${NC}"
echo -e "${GREEN}  - Total records inserted: $((L2_COUNT * 4)) (4 metrics × $L2_COUNT records)${NC}"

# Step 7: Show L2 metrics summary
echo -e "\n${YELLOW}[7/9] Core L2 Metrics Summary...${NC}"
psql "$DB_URL" << EOF
SELECT 
  output_metric_name,
  COUNT(*) as count,
  MIN(output_metric_value::numeric) as min_value,
  MAX(output_metric_value::numeric) as max_value,
  ROUND(AVG(output_metric_value::numeric), 6) as avg_value
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND param_set_id = '$PARAM_SET_ID'
  AND output_metric_name IN ('EP', 'PAT_EX', 'XO_COST_EX', 'FC')
GROUP BY output_metric_name
ORDER BY output_metric_name;
EOF

# Step 8: Show sample L2 metrics data
echo -e "\n${YELLOW}[8/9] Sample Core L2 Records (first 20 ticker-years, all 4 metrics):${NC}"
psql "$DB_URL" << EOF
SELECT 
  ticker,
  fiscal_year,
  output_metric_name,
  ROUND(output_metric_value::numeric, 4) as metric_value,
  metadata->>'metric_level' as metric_level
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND param_set_id = '$PARAM_SET_ID'
  AND output_metric_name IN ('EP', 'PAT_EX', 'XO_COST_EX', 'FC')
ORDER BY ticker, fiscal_year, output_metric_name
LIMIT 20;
EOF

# Bonus: Verification - Show EP calculation components
echo -e "\n${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              Verification: EP Calculation Details              ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${CYAN}Sample EP Calculation Verification (first 10 tickers):${NC}"
echo -e "${CYAN}Formula: EP = pat - (ke_open × ee_open)${NC}"
echo -e "${CYAN}Where _open = prior fiscal year value${NC}\n"

psql "$DB_URL" << EOF
WITH ep_verification AS (
  SELECT 
    ticker, fiscal_year,
    MAX(CASE WHEN output_metric_name = 'EP' THEN output_metric_value END) as ep,
    MAX(CASE WHEN output_metric_name = 'PAT' THEN output_metric_value END) as pat,
    MAX(CASE WHEN output_metric_name = 'Calc KE' THEN output_metric_value END) as ke,
    MAX(CASE WHEN output_metric_name = 'EE' THEN output_metric_value END) as ee
  FROM cissa.metrics_outputs
  WHERE dataset_id = '$DATASET_ID'
    AND param_set_id = '$PARAM_SET_ID'
    AND output_metric_name IN ('EP', 'PAT', 'Calc KE', 'EE')
  GROUP BY ticker, fiscal_year
  ORDER BY ticker, fiscal_year
  LIMIT 10
)
SELECT 
  ticker,
  fiscal_year,
  ROUND(pat::numeric, 2) as pat,
  ROUND(ke::numeric, 4) as ke,
  ROUND(ee::numeric, 2) as ee,
  ROUND(ep::numeric, 2) as ep_actual,
  '(Note: _open values needed for full verification)' as note
FROM ep_verification
ORDER BY ticker, fiscal_year;
EOF

# Step 9: Summary and next steps
echo -e "\n${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        Verification: Lagged Data & Missing Values              ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${CYAN}Checking for NaN values (missing prior year data):${NC}"
psql "$DB_URL" << EOF
SELECT 
  output_metric_name,
  COUNT(*) as total_records,
  COUNT(*) FILTER (WHERE output_metric_value IS NOT NULL) as non_null,
  COUNT(*) FILTER (WHERE output_metric_value IS NULL) as null_count
FROM cissa.metrics_outputs
WHERE dataset_id = '$DATASET_ID'
  AND param_set_id = '$PARAM_SET_ID'
  AND output_metric_name IN ('EP', 'PAT_EX', 'XO_COST_EX', 'FC')
GROUP BY output_metric_name
ORDER BY output_metric_name;
EOF

# Final summary
echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ✓ Phase 10a Core L2 Metrics Complete!               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${CYAN}Summary:${NC}"
echo -e "  Dataset ID:       $DATASET_ID"
echo -e "  Param Set ID:     $PARAM_SET_ID"
echo -e "  Base Records:     $L2_COUNT"
echo -e "  Total Inserted:   $((L2_COUNT * 4)) (4 metrics)"
echo -e "  Status:           ${GREEN}✓ Success${NC}"

echo -e "\n${CYAN}Metrics Calculated:${NC}"
echo -e "  1. EP: Economic Profit = pat - (ke_open × ee_open)"
echo -e "  2. PAT_EX: Adjusted Profit = (ep / |ee_open + ke_open|) × ee_open"
echo -e "  3. XO_COST_EX: Adjusted XO Cost = patxo - pat_ex"
echo -e "  4. FC: Franking Credit (conditional on incl_franking)"

echo -e "\n${CYAN}Next Steps:${NC}"
echo -e "  1. Review Core L2 metrics in database:"
echo -e "     SELECT * FROM cissa.metrics_outputs WHERE output_metric_name IN ('EP', 'PAT_EX', 'XO_COST_EX', 'FC') LIMIT 20;"
echo -e ""
echo -e "  2. Calculate Phase 10b metrics (FV ECF):"
echo -e "     (Coming in next phase)"
echo -e ""
echo -e "  3. Check calculation logs:"
echo -e "     grep -i 'phase.10a\\|core.l2' /tmp/api.log | tail -30"
echo -e ""
