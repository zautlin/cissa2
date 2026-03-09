# Codebase Concerns

**Analysis Date:** 2026-03-09

## Tech Debt

**Hardcoded Configuration Values:**
- Issue: Critical parameters are hardcoded directly in API endpoint code
- Files: `backend/app/api/v1/endpoints/metrics.py` (lines 147-148)
- Impact: Cannot adjust risk premium or country without code changes; parameter set contains this data but isn't used
- Fix approach: Fetch `country` and `risk_premium` from parameter_set table during L2 calculation initialization; make these configurable per parameter set

**Unimplemented Repository Method:**
- Issue: `MetricsRepository.get_fundamentals()` is a stub method (line 67 in `backend/app/repositories/metrics_repository.py`)
- Files: `backend/app/repositories/metrics_repository.py` (lines 54-67)
- Impact: Repository pattern is incomplete; L2 metrics service directly queries database with raw SQL instead of using repository
- Fix approach: Implement `get_fundamentals()` to query the fundamentals table and return DataFrame; refactor L2MetricsService to use it

**Overly Permissive CORS Configuration:**
- Issue: CORS allows all origins (`["*"]`) with TODO to restrict in Phase 3
- Files: `example-calculations/src/api/main.py` (line 95)
- Impact: Security vulnerability - any web origin can make requests; should be restricted to known frontend domains
- Fix approach: Phase 3 implementation should require OAuth2/Keycloak auth and restrict `allow_origins` to configured domains

**Incomplete Data Recovery in Processing Pipeline:**
- Issue: Excel extraction and denormalization timeouts use hard 300-second limit without retry logic
- Files: `backend/database/etl/pipeline.py` (lines 204, 229, 258, 288)
- Impact: Long-running extractions on large files fail silently; no recovery mechanism or exponential backoff
- Fix approach: Implement retry logic with exponential backoff; allow timeout configuration via environment variable; log intermediate progress

## Known Bugs

**NumPy NaN Arithmetic Issue in FVECF Calculation:**
- Symptoms: Scalar multiplication with NaN produces numeric values instead of NaN (e.g., `1 * np.nan` returns number instead of NaN)
- Files: `example-calculations/src/executors/fvecf.py` (line 12)
- Trigger: When calculating future value with NaN interest rates or growth factors
- Workaround: Explicitly check for NaN before arithmetic operations; use `np.where(pd.isna(x), np.nan, calculation)` pattern
- Note: This is a Python/NumPy behavior quirk; fix is to validate input data has no NaN before calculation

## Security Considerations

**Overly Broad Exception Handling:**
- Risk: Generic `except Exception:` clauses swallow all errors including database connection failures, permission errors, and timeouts
- Files: `backend/database/etl/pipeline.py` (15 instances), `backend/database/schema/schema_manager.py` (6 instances), `backend/app/services/*.py` (multiple)
- Current mitigation: Errors are logged with `logger.error()`; messages returned to caller
- Recommendations: 
  - Catch specific exception types: `DatabaseError`, `OperationalError`, `IntegrityError` separately from application errors
  - Re-raise database connection errors immediately (don't continue pipeline)
  - Create custom exception hierarchy: `CissaError`, `DataValidationError`, `DatabaseError`, `ImputationError`
  - Log stack traces for unexpected errors; suppress stack traces for expected validation failures

**SQL Injection Risk in Dynamic Query Building:**
- Risk: Pipeline uses `text()` wrapper for SQL, which is safe; however, schema search_path is set via connection string parsing
- Files: `backend/database/etl/config.py` (line 62 - URL encoding search_path parameter)
- Current mitigation: Using SQLAlchemy `text()` with parameterized queries for data queries; schema is static ("cissa")
- Recommendations: 
  - Validate schema name against whitelist before use
  - Document that only untrusted data should go through parameterized queries
  - Audit all `execute()` calls for proper parameterization

**Async Context Mixing in Pipeline:**
- Risk: Pipeline uses `asyncio.run()` to call async metrics service from synchronous ETL pipeline (line 229 in `backend/database/etl/ingestion.py`)
- Current mitigation: `asyncio.run()` creates fresh event loop; no conflict with existing loops
- Recommendations:
  - Plan full async pipeline migration (refactor `pipeline.py`, `ingestion.py` to async)
  - This prevents integration with async frameworks in future
  - Create integration tests for sync→async bridge behavior under load

## Performance Bottlenecks

**Large File Operations Without Streaming:**
- Problem: Excel extraction loads entire Bloomberg file into memory via openpyxl; CSV denormalization loads all data into pandas DataFrame
- Files: `backend/database/etl/ingestion.py` (line 85 loads entire Base.csv into memory)
- Cause: No chunked processing or generator patterns; all 24 worksheets are extracted into separate CSVs in memory first
- Improvement path:
  - Implement chunked Excel reader (read sheets in blocks of 10k rows)
  - Process data in streaming fashion: extract → validate → insert without materializing full DataFrame
  - Profile memory usage; set warnings if >2GB heap allocated

**Imputation Cascade Recreates Wide DataFrame:**
- Problem: `ImputationCascade.impute()` creates source tracking DataFrame with same shape as data (~187k rows × 60+ metrics); memory-intensive
- Files: `backend/database/etl/imputation_engine.py` (lines 91-99 create source_wide DataFrame copy)
- Cause: Source tracking stored as separate DataFrame instead of JSONB column in database
- Improvement path:
  - Store imputation source in database during pipeline (single insert with source metadata)
  - Avoid recreating source DataFrame in memory
  - Reduces memory footprint 40-50% for large datasets

**Missing Connection Pool Tuning for Async:**
- Problem: Database connection pool set to `pool_size=10, max_overflow=20` fixed values; no tuning for concurrent async workloads
- Files: `backend/app/core/database.py` (lines 25-26)
- Cause: Defaults from SQLAlchemy docs; not profiled for actual workload
- Improvement path:
  - Profile concurrent API requests and ETL pipeline overlap
  - Implement dynamic pool sizing based on metrics (% exhaustion rate, queue time)
  - Log pool exhaustion warnings; alert when max_overflow is regularly hit

**L1 Metrics Recalculation Without Cache:**
- Problem: L1 metrics auto-calculated by SQL trigger on every ingestion; no caching or incremental calculation
- Files: `backend/database/etl/ingestion.py` (lines 331 call calculate_all_l1_metrics after every ingestion)
- Cause: Metrics stored in single metrics_outputs table with no separation of incremental vs. full recalc
- Improvement path:
  - Track which tickers/fiscal_years are new or updated during ingestion
  - Only recalculate L1 for changed data
  - Cache intermediate calculations in temp tables

## Fragile Areas

**Fiscal Year Alignment Logic:**
- Files: `backend/database/etl/fy_aligner.py` (entire file - 255 lines)
- Why fragile: Complex regex parsing of "FY XXXX" strings with no validation of actual calendar dates; assumes consistent Bloomberg format; fails silently on malformed dates
- Safe modification: 
  - Add unit tests for edge cases: "FY 2023", "FY2023" (no space), "H1 2023", "Q4 2023"
  - Validate extracted year is within reasonable range (1990-2050)
  - Log warnings for non-standard date formats instead of silent failure
- Test coverage: No unit tests found; only integration test via pipeline

**Imputation Cascade with Sector Lookup:**
- Files: `backend/database/etl/imputation_engine.py` (lines 160-227 - sector median imputation step)
- Why fragile: Depends on sector_map parameter being passed correctly; if sector is missing for a ticker, sector median imputation silently falls through to market median
- Safe modification:
  - Add explicit validation that all tickers in data have sector assignments
  - Log which tickers lack sectors; store this in audit trail
  - Make sector assignment mandatory before imputation begins
- Test coverage: Minimal; sector fallthrough behavior untested

**Dataset Versioning Update Logic:**
- Files: `backend/database/etl/ingestion.py` (lines 175-195 update dataset_versions with completion status)
- Why fragile: Uses timestamp-based status tracking without transaction boundaries; race condition possible if two pipelines ingest same dataset simultaneously
- Safe modification:
  - Add pessimistic locking: `SELECT ... FOR UPDATE` before status update
  - Create unique constraint on (dataset_id, version_number) to prevent duplicate versions
  - Add integration test simulating concurrent ingestion
- Test coverage: No concurrent ingestion tests

**L2 Metrics Service DataFrame Operations:**
- Files: `backend/app/services/l2_metrics_service.py` (entire file - 418 lines)
- Why fragile: Heavy pandas DataFrame manipulation with complex pivoting; no schema validation of returned DataFrames; assumes specific column order
- Safe modification:
  - Add defensive assertions at start of `_calculate_l2_metrics_pure()`: check DataFrame columns exist, no NaN in key fields
  - Implement DataFrame schema using pydantic-dataframe or pandera library
  - Add comprehensive DataFrame shape and content tests
- Test coverage: Unknown; service tests not found

## Scaling Limits

**Single Database Connection in ETL:**
- Current capacity: Pipeline runs serially; one Ingester instance at a time
- Limit: Cannot parallelize ingestion for multiple datasets; bottleneck at schema-level lock on fiscal_year_mapping updates
- Scaling path:
  - Implement queue-based job system (Celery/RQ) for parallel ingestions
  - Shard datasets by ticker ranges to allow parallel processing
  - Use application-level locking instead of table-level locks

**Memory Usage for Large Datasets:**
- Current capacity: ~187k rows × 60 metrics × 8 bytes (float) ≈ 90MB DataFrame in memory
- Limit: 500k+ rows × 150+ metrics causes OOM errors; no memory limit configuration
- Scaling path:
  - Implement chunked processing: process 50k rows at a time
  - Use sparse matrix representation for high-null metrics
  - Add memory profiling and automatic chunking based on available RAM

**API Connection Pool Exhaustion:**
- Current capacity: 10 base + 20 overflow = 30 concurrent connections
- Limit: 30+ simultaneous API requests cause queue backlog; no backpressure signaling
- Scaling path:
  - Implement circuit breaker for database access
  - Return 503 Service Unavailable when pool exhausted instead of hanging
  - Add metrics/monitoring for pool utilization

## Dependencies at Risk

**Outdated SQLAlchemy 2.0.48:**
- Risk: Version pinned to 2.0.48; newer 2.1.x versions have breaking changes to AsyncSession behavior
- Impact: Cannot upgrade without full testing of async patterns; async engine pool configuration changed
- Migration plan:
  - Create migration branch to test 2.1.x compatibility
  - Review release notes for breaking changes to AsyncSession
  - Test with actual workload before upgrading

**Pandas 3.0.1 with Known Breaking Changes:**
- Risk: Pandas 3.x removed MultiIndex.swaplevel() in favor of new API; imputation code may break
- Impact: Imputation cascade uses DataFrame operations that may not exist in future versions
- Migration plan:
  - Audit all pandas operations for 3.x compatibility
  - Add pandas version pinning upper bound
  - Consider migration to polars for better performance on large datasets

**Old fastapi (0.109.0) and uvicorn (0.27.0):**
- Risk: Versions from Jan 2024; multiple security patches in 0.110.0+
- Impact: Potential security vulnerabilities in CORS handling, form data parsing
- Migration plan:
  - Upgrade to 0.115.0+ for security patches
  - Test all API endpoints with new version
  - Check for breaking changes in middleware handling

## Missing Critical Features

**No Audit Trail for Data Modifications:**
- Problem: No mechanism to track which user/service modified metric data after initial ingestion
- Blocks: Cannot trace back calculation errors to source; no change history for metrics
- Database schema has `imputation_audit_trail` but no general-purpose audit table for later modifications

**No Metrics Validation After Calculation:**
- Problem: L1 and L2 metrics inserted without post-calculation validation (e.g., ROA should be -1 to +3 range; extreme values flagged as errors)
- Blocks: Garbage-in-garbage-out; bad calculations propagate downstream without detection
- Requires: Add validation rules table; post-calc validation step in metrics service

**No Incremental/Delta Ingestion:**
- Problem: Every ingestion processes entire Bloomberg file; no support for loading just new/changed records
- Blocks: Long ingestion times (5-10min) for small data changes; impossible to do frequent updates
- Requires: Track data fingerprint/hash per (ticker, period, metric); only reprocess changed records

**No Rollback Mechanism:**
- Problem: Pipeline stages cannot be partially rolled back if errors occur mid-pipeline
- Blocks: Corrupted data stuck in database; must do full schema destroy/recreate to reset
- Requires: Implement savepoints per stage; transaction-based rollback on stage failure

## Test Coverage Gaps

**No Tests for Fiscal Year Alignment:**
- What's not tested: Edge cases in date parsing (missing years, malformed date strings); fallback behavior when FY cannot be extracted
- Files: `backend/database/etl/fy_aligner.py` (entire module)
- Risk: Silent failures in date parsing cause data to be unaligned; billions of rows with wrong fiscal years stored
- Priority: **HIGH** - affects entire downstream pipeline

**No Tests for Imputation Logic:**
- What's not tested: Forward/backward fill across year boundaries; sector median when sector is missing; interpolation with gaps > 3 years
- Files: `backend/database/etl/imputation_engine.py`
- Risk: Silently produces incorrect imputations; no way to detect which records were damaged
- Priority: **HIGH** - core data quality logic

**No Tests for L2 Metrics Service:**
- What's not tested: DataFrame schema validation; NaN handling in calculations; empty result handling
- Files: `backend/app/services/l2_metrics_service.py`
- Risk: API returns partial/corrupted results; no error detection until business layer
- Priority: **HIGH** - metrics are consumed by end users

**No Integration Tests for Pipeline Stages:**
- What's not tested: Concurrent ingestion (two pipelines running simultaneously); database constraint violations; recovery from mid-pipeline failures
- Files: `backend/database/etl/pipeline.py`
- Risk: Race conditions in production; data corruption under concurrent load
- Priority: **MEDIUM** - only manifests under stress

**No API Contract Tests:**
- What's not tested: Request validation (invalid UUIDs, missing fields); response schema compliance; error response format
- Files: `backend/app/api/v1/endpoints/metrics.py`
- Risk: Frontend breaks when API response format changes unexpectedly
- Priority: **MEDIUM** - affects API stability

---

*Concerns audit: 2026-03-09*
