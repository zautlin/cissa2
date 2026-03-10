#!/bin/bash
# ============================================================================
# Phase 10b FV_ECF Metrics Calculation Script
# ============================================================================
# This script calculates Future Value Economic Cash Flow (FV_ECF) metrics
# for a specified dataset and parameter set.
#
# Usage:
#   ./run-l2-fv-ecf-calc.sh <dataset_id> <param_set_id> [incl_franking]
#
# Parameters:
#   dataset_id      - UUID of dataset to process (required)
#   param_set_id    - UUID of parameter set to use (required)
#   incl_franking   - Include franking credits: "Yes" or "No" (default: "Yes")
#
# Example:
#   ./run-l2-fv-ecf-calc.sh \
#     550e8400-e29b-41d4-a716-446655440000 \
#     660e8400-e29b-41d4-a716-446655440001 \
#     Yes
# ============================================================================

set -euo pipefail

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
ENDPOINT="/api/v1/metrics/l2-fv-ecf/calculate"

# Function to display usage
usage() {
    echo "Usage: $0 <dataset_id> <param_set_id> [incl_franking]"
    echo ""
    echo "Parameters:"
    echo "  dataset_id    - UUID of dataset to process"
    echo "  param_set_id  - UUID of parameter set to use"
    echo "  incl_franking - Include franking: 'Yes' (default) or 'No'"
    echo ""
    echo "Example:"
    echo "  $0 550e8400-e29b-41d4-a716-446655440000 660e8400-e29b-41d4-a716-446655440001 Yes"
    exit 1
}

# Parse arguments
if [ $# -lt 2 ]; then
    usage
fi

DATASET_ID="$1"
PARAM_SET_ID="$2"
INCL_FRANKING="${3:-Yes}"

# Validate parameters
if [ -z "$DATASET_ID" ] || [ -z "$PARAM_SET_ID" ]; then
    echo "Error: dataset_id and param_set_id are required"
    usage
fi

# Validate incl_franking
if [[ ! "$INCL_FRANKING" =~ ^(Yes|No)$ ]]; then
    echo "Error: incl_franking must be 'Yes' or 'No', got: $INCL_FRANKING"
    exit 1
fi

# Display configuration
echo "========================================================="
echo "Phase 10b: FV_ECF Metrics Calculation"
echo "========================================================="
echo "API URL:        $API_BASE_URL"
echo "Endpoint:       $ENDPOINT"
echo "Dataset ID:     $DATASET_ID"
echo "Param Set ID:   $PARAM_SET_ID"
echo "Include Franking: $INCL_FRANKING"
echo "========================================================="
echo ""

# Construct URL with query parameters
FULL_URL="${API_BASE_URL}${ENDPOINT}?dataset_id=${DATASET_ID}&param_set_id=${PARAM_SET_ID}&incl_franking=${INCL_FRANKING}"

# Make API call
echo "Calling: POST $FULL_URL"
echo ""

RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  "$FULL_URL")

# Parse and display response
echo "Response:"
echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"

echo ""
echo "========================================================="

# Extract status
STATUS=$(echo "$RESPONSE" | jq -r '.status // "unknown"' 2>/dev/null)

if [ "$STATUS" == "success" ]; then
    echo "✓ FV_ECF calculation successful"
    
    # Extract and display summary
    TOTAL_INSERTED=$(echo "$RESPONSE" | jq -r '.total_inserted // 0' 2>/dev/null)
    DURATION=$(echo "$RESPONSE" | jq -r '.duration_seconds // 0' 2>/dev/null)
    
    echo ""
    echo "Summary:"
    echo "  Total inserted: $TOTAL_INSERTED records"
    echo "  Duration: ${DURATION}s"
    
    # Display intervals summary
    INTERVALS=$(echo "$RESPONSE" | jq -r '.intervals_summary // {}' 2>/dev/null)
    if [ -n "$INTERVALS" ] && [ "$INTERVALS" != "{}" ]; then
        echo ""
        echo "Breakdown by interval:"
        echo "$INTERVALS" | jq -r 'to_entries[] | "  \(.key): \(.value) records"' 2>/dev/null || true
    fi
    
    exit 0
elif [ "$STATUS" == "error" ]; then
    echo "✗ FV_ECF calculation failed"
    ERROR_MSG=$(echo "$RESPONSE" | jq -r '.message // "Unknown error"' 2>/dev/null)
    echo ""
    echo "Error: $ERROR_MSG"
    exit 1
else
    echo "⚠ Unexpected response status: $STATUS"
    exit 1
fi
