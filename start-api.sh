#!/bin/bash
# ============================================================================
# FastAPI Backend Startup Script
# ============================================================================
# This script:
# 1. Installs dependencies from requirements.txt
# 2. Ensures PostgreSQL schema functions are loaded
# 3. Starts the FastAPI server

set -e

echo "===== CISSA Metrics API Startup ====="

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "ERROR: .env file not found in /home/ubuntu/cissa"
    exit 1
fi

# Use CLI-compatible database URL for psql
DB_URL="$DATABASE_URL_CLI"

# Step 1: Install Python dependencies
echo ""
echo "[1/4] Installing Python dependencies..."
cd /home/ubuntu/cissa
pip install -r requirements.txt > /dev/null 2>&1 || pip install -r requirements.txt

# Step 2: Check PostgreSQL connection
echo ""
echo "[2/4] Checking PostgreSQL connection..."
if ! command -v psql &> /dev/null; then
    echo "WARNING: psql not found. Install postgresql-client or ensure DB is accessible"
else
    psql "$DB_URL" -c "\dt cissa.fundamentals" > /dev/null 2>&1 || {
        echo "ERROR: Cannot connect to database. Ensure PostgreSQL is running and .env DATABASE_URL is correct."
        exit 1
    }
    echo "✓ PostgreSQL connection successful"
fi

# Step 3: Load SQL functions (if not already loaded)
echo ""
echo "[3/4] Loading SQL functions into database..."
if ! psql "$DB_URL" -c "SELECT 1 FROM information_schema.routines WHERE routine_name = 'fn_calc_market_cap'" 2>/dev/null | grep -q 1; then
    echo "  Loading functions.sql..."
    psql "$DB_URL" -f /home/ubuntu/cissa/backend/database/schema/functions.sql > /dev/null 2>&1
    echo "  ✓ Functions loaded"
else
    echo "  ✓ Functions already loaded"
fi

# Step 4: Start FastAPI server
echo ""
echo "[4/4] Starting FastAPI server..."
echo "  Server running at: http://localhost:8000"
echo "  API Docs at: http://localhost:8000/docs"
echo ""

cd /home/ubuntu/cissa/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
