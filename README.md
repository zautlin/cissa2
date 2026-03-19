# CISSA™ Digital Platform

Corporate Governance & Sustainable Wealth Creation Platform.

## Repository Structure

```
cissa2/
├── backend/                  # FastAPI backend (Python) — unchanged
│   ├── app/
│   │   ├── api/v1/endpoints/ # REST endpoints (metrics, parameters, statistics, orchestration)
│   │   ├── services/         # Business logic (EP, beta, cost of equity, L1/L2 metrics)
│   │   ├── repositories/     # Data access layer (SQLAlchemy async)
│   │   ├── models/           # Pydantic schemas + SQLAlchemy ORM models
│   │   └── core/             # Config, database connection pooling
│   ├── database/
│   │   ├── etl/              # ETL pipeline: ingest → validate → impute → load
│   │   └── schema/           # PostgreSQL schema SQL + migration scripts
│   └── tests/                # Unit, integration, validation tests
├── frontend/                 # React dashboard (TypeScript + Vite)
│   ├── src/
│   │   ├── pages/            # Dashboard, Principles 1 & 2, Outputs, Reports, Underlying Data
│   │   ├── components/       # Sidebar, Topbar, UI components
│   │   ├── data/             # Chart.js datasets (mock data, replace with API calls)
│   │   └── lib/api.ts        # Typed API client → FastAPI backend
│   └── README.md             # Frontend setup & build instructions
├── input-data/               # Raw Bloomberg data + ETL extraction scripts
├── example-calculations/     # Reference calculation scripts & backtesting
└── requirements.txt          # Python dependencies
```

## Quick Start

### 1. Backend

```bash
# Install Python dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env: set DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/cissa

# Run database schema
psql $DATABASE_URL -f backend/database/schema/schema.sql
psql $DATABASE_URL -f backend/database/schema/functions.sql

# Start API server
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# API docs → http://localhost:8000/docs
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# Dashboard → http://localhost:3000
# Proxies /api/* → FastAPI on port 8000
```

### 3. Production (serve frontend from FastAPI)

```bash
# Build frontend
cd frontend && npm run build

# Add to backend/app/main.py:
# from fastapi.staticfiles import StaticFiles
# app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
```

## API Reference

The FastAPI backend exposes:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/metrics/health` | Health check |
| GET | `/api/v1/metrics/statistics` | Companies, sectors, data coverage |
| GET | `/api/v1/metrics/get_metrics/` | Retrieve computed metrics |
| POST | `/api/v1/metrics/calculate` | Calculate L1 metric |
| POST | `/api/v1/metrics/calculate-l2` | Calculate L2 metrics |
| POST | `/api/v1/metrics/beta/calculate-from-precomputed` | Beta (fast path) |
| POST | `/api/v1/metrics/cost-of-equity/calculate` | Cost of Equity (Ke) |
| POST | `/api/v1/metrics/rates/calculate` | Risk-free rate |
| GET | `/api/v1/parameters/active` | Active parameter set |
| GET | `/api/v1/metrics/statistics` | Dataset statistics |

Full interactive docs at `http://localhost:8000/docs` (Swagger UI).

## Tech Stack

**Backend:** Python 3.10+, FastAPI, SQLAlchemy 2 (async), PostgreSQL 16, Pandas, AsyncPG

**Frontend:** React 18, TypeScript, Vite 5, Tailwind CSS 3, Chart.js 4, Wouter

**ETL:** Bloomberg Excel → raw_data → fundamentals → metrics_outputs (PostgreSQL)
