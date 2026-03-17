# Backend Documentation

Complete documentation for the CISSA FastAPI backend, including architecture, implementation guides, and quick references.

## Documentation Files

### [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)
Complete guide for understanding, maintaining, and extending the metrics calculation system. Covers:
- System architecture
- How metrics are calculated, stored, and served
- Adding new metrics
- Troubleshooting and debugging

### [ARCHITECTURE.md](./ARCHITECTURE.md)
Database schema and API structure analysis, including:
- Complete database schema overview
- 11 tables with relationships
- API endpoint structure
- Service architecture and data flows

### [ORCHESTRATOR.md](./ORCHESTRATOR.md)
L1 Metrics Orchestrator implementation guide:
- Performance optimization (8-10 minutes → 40-60 seconds)
- Parallelized execution strategy
- Batch INSERT optimization
- Retry logic and error handling

### [QUICK_REFERENCE.md](./QUICK_REFERENCE.md)
Codebase quick reference for developers:
- File locations and organization
- Key functions and patterns
- Common tasks and workflows
- Directory structure guide

### [API_QUICK_REFERENCE.md](./API_QUICK_REFERENCE.md)
API endpoints and architecture quick reference:
- Complete endpoint list organized by category
- Database table overview
- Key response models
- Configuration and environment variables

---

## Getting Started

1. **New to the backend?** Start with [ARCHITECTURE.md](./ARCHITECTURE.md) for an overview
2. **Need to add a metric?** See [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md) - "Adding a New Metric" section
3. **Looking for an API endpoint?** Check [API_QUICK_REFERENCE.md](./API_QUICK_REFERENCE.md)
4. **Understanding the code?** Use [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) for file locations

---

## Backend Structure

```
backend/
├── app/
│   ├── api/v1/
│   │   ├── router.py
│   │   └── endpoints/ (metrics, parameters, orchestration)
│   ├── services/ (business logic)
│   ├── repositories/ (data access)
│   ├── models/ (Pydantic & ORM)
│   ├── core/ (config, database)
│   └── main.py (FastAPI app)
├── database/
│   ├── schema/ (SQL schema & functions)
│   ├── etl/ (ingestion pipeline)
│   └── docs/ (database documentation)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── scripts/ (CLI utilities)
└── docs/ (this directory)
```

---

## Key Commands

### Start the API Server
```bash
./start-api.sh
# or
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Run Tests
```bash
cd backend && pytest tests/
```

### Access Swagger UI
```
http://localhost:8000/docs
```

---

## See Also

- [Main Project README](../../README.md) - Project overview
- [Project Roadmap](../../ROADMAP.md) - Feature roadmap
- [Database Documentation](../database/README.md) - Database-specific docs
