# Backend Integration Context

**Source Repository:** `/Users/jparnell/rozettatechnology/basos-ds/backend`  
**Target Repository:** `/Users/jparnell/rozettatechnology/cissa`  
**Analysis Date:** 2026-03-02

## Existing Backend Overview

The basos-ds backend is a fully functional system for implementing the CISSA methodology. It has:

### Core Architecture

**Technology Stack:**
- Language: Python (3.14 required)
- Database: PostgreSQL 15.13 (containerized via Docker)
- API Framework: FastAPI 0.104.1
- Data Processing: pandas 3.0.1, numpy 2.4.2, scipy 1.17.0
- Testing: pytest 9.0.2

**Key Dependencies (18 total):**
- Data: pandas, openpyxl, xlwings
- DB: psycopg2-binary 2.9.11, sqlalchemy 2.0.46
- Scientific: statsmodels 0.14.6, numpy, scipy
- Visualization: matplotlib 3.10.8, plotly 6.5.2, dash 4.0.0
- API: FastAPI, uvicorn, pydantic 2.5.0
- Cloud: boto3 1.42.53
- Testing: pytest 9.0.2

### Database Architecture

**PostgreSQL Schema (`USR` schema):**
- 18+ core tables organized in layers:
  - **Reference:** country (ISO codes)
  - **Versioning:** data_versions, override_versions, adjusted_data, data_quality
  - **Input Data:** company, monthly_data, annual_data, fy_dates, user_defined_data
  - **Calculations:** metrics, config, parameter_scenarios, metric_runs
  - **Scenarios:** scenarios, scenario_runs
  - **Optimization:** optimization_results, bw_outputs
  - **Operations:** jobs, data_quality tracking

**Infrastructure:**
- Docker Compose setup with PostgreSQL + Atlas migration manager
- Single authoritative schema file: `000_complete_schema.sql` (906 lines)
- Automatic initialization and migration on container startup
- Health checks and volume persistence

### Source Code Organization

**`src/` directory structure:**
- `config/` - Configuration and parameters (DEPLOYMENT_MODE, database settings, column mappings)
- `engine/` - Core calculation and data processing
  - `xls.py` - Excel file reading and data upload
  - `sql.py` - SQL operations and database interactions (33KB)
  - `calculation.py` - Metric calculation logic
  - `aggregators.py` - Data aggregation functions
  - `curation.py` - Data quality and curation
  - `optimizer.py` - Optimization algorithms
  - `loaders.py` - Data loading utilities
  - `formatters.py` - Output formatting
  - `stateorganizer.py` - State management
- `api/` - FastAPI endpoints (in progress)
- `services/` - Service layer (incomplete)
- `executors/` - Execution logic (incomplete)
- `utils/` - Shared utilities
- `backtesting/` - Portfolio backtesting suite
- `sowc/` - SOWC (State of World Corporates) analysis tools
- `scripts/` - Standalone scripts

**Runnable Modules:**
```
python -m src.upload_data_to_db          # Load Bloomberg + user data
python -m src.generate_l1_metrics        # Calculate company-level metrics
python -m src.generate_l2_metrics        # Calculate sector aggregations
python -m src.generate_sector_metrics    # Sector-specific metrics
python -m src.run_bw_generation_model    # Portfolio optimization
```

### Data Pipeline

**Input:** Excel files (Bloomberg Download data.xlsx, user_defined.xlsx)

**Processing:**
1. Upload Bloomberg data → company, monthly_data, annual_data tables
2. Upload user-defined data → user_defined_data, parameter_scenarios tables
3. Generate L1 metrics → metrics table (company-level calculations)
4. Generate L2 metrics → sector-level aggregations
5. Run BW generation model → optimization_results table

**Output:** Metrics, optimized portfolio allocations, reports

### Testing

- Test framework: pytest
- Test location: `test/` directory
- Phase 3 tests: API integration tests
- Coverage: Partial (framework set up, tests incomplete)

## What Needs Integration

**Database Setup:**
- [ ] Copy `db/` directory to cissa repo
- [ ] Update environment variables (POSTGRES_DB, POSTGRES_USER, etc.)
- [ ] Verify Docker Compose works in new repo

**Source Code:**
- [ ] Copy `src/` directory to cissa repo
- [ ] Update imports (references to `src.*`)
- [ ] Reconcile with existing cissa package structure (if any)
- [ ] Update configuration for deployment modes

**Testing:**
- [ ] Copy `test/` directory to cissa repo
- [ ] Ensure all tests pass in new environment

**Requirements & Setup:**
- [ ] Merge requirements.txt
- [ ] Create setup.py or pyproject.toml (cissa currently missing)
- [ ] Update cissa's empty requirements.txt

**Data Files:**
- [ ] Copy sample data files if needed (Bloomberg Download data.xlsx, user_defined.xlsx)
- [ ] Or document where to source them

## Known Gaps/Issues to Reconcile

**From code review:**

1. **Configuration:** Parameters.py has hardcoded production values mixed with env var logic
   - Lines 54-57 override env vars with hardcoded RDS endpoint
   - Need to consolidate to pure env-var based configuration

2. **Incomplete Services:**
   - `src/api/` exists but FastAPI endpoints incomplete
   - `src/services/` layer exists but underdeveloped
   - `src/executors/` exists but not integrated into main workflows

3. **Data Ingestion Workflow:**
   - `upload_data_to_db.py` calls `xls.upload_bbg_data_to_postgres(execute=True)`
   - Excel file reading logic in `engine/xls.py` needs to be tested end-to-end
   - Workflow assumes Excel files exist in `./data/` directory

4. **Error Handling:**
   - Logging set up in scripts but not centralized
   - No validation layer before database writes
   - Need data quality checks before metric calculations

5. **Testing Coverage:**
   - Phase 3 tests exist but incomplete
   - No tests for core calculation logic
   - No test fixtures for sample data

## Recommendations for Integration

**Phase 1 (Backend Infrastructure) should:**
1. Copy database setup (docker-compose, migrations)
2. Copy core src modules (engine/, config/)
3. Copy all dependencies to cissa requirements.txt
4. Create setup.py for package installation
5. Fix configuration issues (env vars, hardcoded values)
6. Create basic data validation
7. Set up test infrastructure

**Phase 2 (After Database Works):**
1. Integrate data ingestion workflow
2. Test end-to-end data pipeline
3. Complete API layer
4. Add service layer integration
5. Implement error handling and validation

**Phase 3:**
1. Portfolio optimization integration
2. Advanced features (backtesting, SOWC analysis)
3. CI/CD setup
4. Production deployment

## Files to Integrate

**Database:**
- `db/docker-compose.yml` → `cissa/db/docker-compose.yml`
- `db/schema/migrations/000_complete_schema.sql` → `cissa/db/schema/migrations/000_complete_schema.sql`
- `db/.env.local` → `cissa/db/.env.local`

**Source Code:**
- `src/config/` → `cissa/src/config/`
- `src/engine/` → `cissa/src/engine/`
- `src/api/` → `cissa/src/api/` (currently incomplete)
- `src/services/` → `cissa/src/services/`
- `src/executors/` → `cissa/src/executors/`
- `src/utils/` → `cissa/src/utils/`
- `src/__init__.py` → `cissa/src/__init__.py`

**Top-level Modules:**
- `src/upload_data_to_db.py` → `cissa/src/upload_data_to_db.py`
- `src/generate_l1_metrics.py` → `cissa/src/generate_l1_metrics.py`
- `src/generate_l2_metrics.py` → `cissa/src/generate_l2_metrics.py`
- `src/calculate_metrics.py` → `cissa/src/calculate_metrics.py`

**Testing & Configuration:**
- `test/` → `cissa/test/`
- `requirements.txt` → merge into `cissa/requirements.txt`
- Create `setup.py` (currently missing from basos-ds)
- Create `pyproject.toml` (currently missing from basos-ds)

**Optional (can defer):**
- `src/backtesting/` → Phase 2+
- `src/sowc/` → Phase 2+
- `src/scripts/` → Phase 2+

---

*Integration audit complete. Ready for planning.*
