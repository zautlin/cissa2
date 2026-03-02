# CISSA Project Roadmap

**Project:** CISSA (Company Integrated Systematic Sustainability Analysis)  
**Objective:** Implement the CISSA methodology for company valuation and portfolio optimization  
**Status:** MVP Phase in Progress

## Phase 1: Backend Infrastructure ✍️ [Currently Planning]

**Goal:** Integrate database infrastructure and API framework from basos-ds legacy project.

**Requirements:** INFRA-01

**Plans:** 1 plan

### Plan 1-01: Database & API Integration
- **Objective:** Set up PostgreSQL database with 18 tables, copy API framework
- **Files:** requirements.txt, setup.py, db/docker-compose.yml, src/config/, src/api/, data/
- **Status:** Planned - Ready for execution
- Checklist:
  - [ ] requirements.txt with all dependencies
  - [ ] setup.py for package installation
  - [ ] Docker PostgreSQL with complete schema
  - [ ] API framework with FastAPI
  - [ ] Configuration using environment variables
  - [ ] Sample Bloomberg data file

---

## Phase 2: Data Ingestion Pipeline [Planned]

**Goal:** Implement data upload workflow to populate database tables from Excel files.

**Requirements:** [To be determined]

**Plans:** TBD

**Dependencies:** Phase 1 (needs working database)

---

## Phase 3: Metrics Calculation Engine [Planned]

**Goal:** Implement CISSA valuation methodology calculations.

**Requirements:** [To be determined]

**Plans:** TBD

**Dependencies:** Phase 2 (needs populated data)

---

## Phase 4: Portfolio Optimization [Planned]

**Goal:** Implement portfolio optimization using CISSA valuations.

**Requirements:** [To be determined]

**Plans:** TBD

**Dependencies:** Phase 3 (needs calculated metrics)

---

## Phase 5: Advanced Features [Planned]

**Goal:** Add backtesting, analysis tools, and reporting.

**Requirements:** [To be determined]

**Plans:** TBD

**Dependencies:** Phase 4

---

## Success Criteria

### Phase 1 (Backend Infrastructure)
- [x] Architecture documented
- [x] Technology stack documented
- [x] Integration analysis completed
- [ ] Code integrated into cissa repo
- [ ] PostgreSQL running with all tables
- [ ] API server starts and responds to health checks
- [ ] Sample data present and ready for ingestion

### Overall MVP
- Database with CISSA data
- Working API for metrics queries
- CLI for data pipeline execution
- Basic test coverage
- Production deployment capability

---

**Last Updated:** 2026-03-02
