#!/bin/bash
# ============================================================================
# Clear Metrics Outputs - Prepare database for fresh metric calculations
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

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║       Clear cissa.metrics_outputs Table                        ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════╝${NC}"

# Show current record count
echo -e "\n${YELLOW}Current metrics_outputs records:${NC}"
CURRENT_COUNT=$(psql "$DB_URL" -t -c "SELECT COUNT(*) FROM cissa.metrics_outputs;" 2>/dev/null | xargs)
echo "  Total records: $CURRENT_COUNT"

# Show breakdown by metric
echo -e "\n${YELLOW}Records by metric:${NC}"
psql "$DB_URL" << EOF
SELECT 
  output_metric_name,
  COUNT(*) as count
FROM cissa.metrics_outputs
GROUP BY output_metric_name
ORDER BY output_metric_name;
EOF

# Confirm before deletion
echo -e "\n${RED}⚠️  WARNING: This will DELETE all records from cissa.metrics_outputs${NC}"
read -p "Are you sure? Type 'yes' to continue: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Cancelled.${NC}"
    exit 0
fi

# Clear the table
echo -e "\n${YELLOW}Clearing cissa.metrics_outputs...${NC}"
psql "$DB_URL" -c "TRUNCATE TABLE cissa.metrics_outputs;" 2>/dev/null

# Verify
NEW_COUNT=$(psql "$DB_URL" -t -c "SELECT COUNT(*) FROM cissa.metrics_outputs;" 2>/dev/null | xargs)

if [ "$NEW_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✓ Successfully cleared! Deleted $CURRENT_COUNT records${NC}"
    echo -e "${GREEN}✓ Table is ready for fresh metric calculations${NC}"
else
    echo -e "${RED}❌ Error: Table still has $NEW_COUNT records${NC}"
    exit 1
fi

echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    ✓ Clear Complete!                           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
