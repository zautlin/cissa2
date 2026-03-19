# CISSA™ Dashboard — Frontend

React + TypeScript + Tailwind CSS dashboard for the CISSA Digital Platform.

## Stack
- **React 18** with TypeScript
- **Vite 5** (dev server + build)
- **Tailwind CSS v3**
- **Chart.js 4** + react-chartjs-2 (EP Bow Wave charts, KPI charts)
- **Wouter** (hash-based SPA routing)
- **chartjs-plugin-annotation** (T₀ dashed lines, wealth labels)

## Pages
| Route | Page |
|---|---|
| `/#/` | Dashboard Home — EP Bow Wave hero, KPI cards, ROE-Ke chart |
| `/#/principles/1` | Principle 1 — Economic Measures |
| `/#/principles/2` | Principle 2 — EP Bow Wave (interactive, company selector) |
| `/#/outputs` | Outputs — Wealth Creation Analysis |
| `/#/underlying-data` | Underlying Data — sortable metric table |
| `/#/reports` | Reports & Research — filterable report library |

## Backend API
All API calls proxy to the FastAPI backend (`/api/v1/*`).
See `src/lib/api.ts` for the full typed client.

Key endpoints used:
- `GET /api/v1/metrics/health` — health check
- `GET /api/v1/metrics/statistics` — companies, sectors, data coverage
- `GET /api/v1/parameters/active` — active parameter set
- `GET /api/v1/metrics/get_metrics/` — fetch computed metrics
- `POST /api/v1/metrics/calculate` — trigger L1 metric calculation

## Development

```bash
# From this directory:
npm install
npm run dev
# Dashboard → http://localhost:3000
# Proxies /api/* → http://localhost:8000 (FastAPI)
```

## Production Build

```bash
npm run build
# Output: frontend/dist/
```

Serve `dist/` as static files. Example with FastAPI:

```python
# In backend/app/main.py — add after existing routes:
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
```

Or serve via nginx pointing to `frontend/dist/index.html`.

## Environment

No `.env` needed for the frontend — API calls are relative (`/api/v1/...`)
and proxied by Vite in dev, or served same-origin in production.

The backend requires a `DATABASE_URL` environment variable — see `backend/README.md`.
