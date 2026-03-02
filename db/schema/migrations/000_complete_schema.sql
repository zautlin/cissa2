-- ============================================================================
-- CISSA DATABASE SCHEMA: Complete & Authoritative Definition
-- ============================================================================
-- 
-- OVERVIEW:
-- This is the single authoritative schema definition for the CISSA platform.
-- All tables, views, and functions are defined here and applied once during
-- database initialization.
--
-- BUILD DATE: 2026-03-02
-- VERSION: 1.0 (Consolidated from 5 incremental migrations)
--
-- MIGRATION STRATEGY (Post-Consolidation):
-- Future schema changes should be created as numbered migrations (001_, 002_, etc.)
-- and applied AFTER this script. This keeps the initial schema clean and makes
-- it clear what has changed over time.
--
-- TABLE CREATION ORDER:
-- 1. Schema + reference tables (country)
-- 2. Versioning layer (data_versions, override_versions, adjusted_data, data_quality)
-- 3. Core data tables (company, monthly_data, annual_data, fy_dates, user_defined_data)
-- 4. Metrics/Calculations layer (parameter_scenarios, metric_runs, metric_results)
-- 5. Scenarios layer (scenarios, scenario_runs)
-- 6. Optimization layer (optimization_results, bw_outputs)
-- 7. Async operations (jobs)
-- 8. Foreign key constraints (added after all tables exist)
-- 9. Views and Functions
--
-- ============================================================================


-- ============================================================================
-- SCHEMA CREATION
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS "USR"
    AUTHORIZATION postgres;


-- ============================================================================
-- REFERENCE DATA TABLES
-- ============================================================================

-- Table: USR.country
-- Purpose: Reference data for company domicile lookups
-- Records: ~13 countries (static reference)
CREATE TABLE IF NOT EXISTS "USR".country (
    code character(5) COLLATE pg_catalog."default" NOT NULL,
    country character varying(50) COLLATE pg_catalog."default",
    CONSTRAINT country_pkey PRIMARY KEY (code)
);

ALTER TABLE IF EXISTS "USR".country OWNER to postgres;
COMMENT ON TABLE "USR".country IS 'Reference data: ISO country codes and names for company domicile';


-- ============================================================================
-- VERSIONING & DATA QUALITY TABLES (LAYER 1)
-- These tables are created first because core tables will reference them
-- ============================================================================

-- Table: USR.data_versions
-- Purpose: Track Bloomberg data file uploads with hash-based deduplication
-- Keys: raw_id (UUID, PK), file_hash (UNIQUE)
-- Purpose: Prevent duplicate uploads of same file
-- Records: Growth as new Bloomberg files are uploaded
CREATE TABLE IF NOT EXISTS "USR"."data_versions" (
    raw_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_name VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64) NOT NULL UNIQUE,
    file_path VARCHAR(512),
    metadata JSONB,
    uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL DEFAULT 'admin'
);

CREATE INDEX idx_data_versions_file_hash ON "USR"."data_versions"(file_hash);
CREATE INDEX idx_data_versions_uploaded_at ON "USR"."data_versions"(uploaded_at DESC);

ALTER TABLE IF EXISTS "USR"."data_versions" OWNER to postgres;
COMMENT ON TABLE "USR"."data_versions" IS 'Bloomberg data file uploads with hash-based deduplication';
COMMENT ON COLUMN "USR"."data_versions".file_hash IS 'SHA256 hash of file; UNIQUE constraint prevents duplicate uploads';


-- Table: USR.override_versions
-- Purpose: Track optional override/plug files (must match Bloomberg structure)
-- FK: raw_id → data_versions
-- Records: Growth as overrides are uploaded
CREATE TABLE IF NOT EXISTS "USR"."override_versions" (
    plug_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_id UUID NOT NULL REFERENCES "USR"."data_versions"(raw_id),
    version_name VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64) NOT NULL UNIQUE,
    file_path VARCHAR(512),
    metadata JSONB,
    uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL DEFAULT 'admin'
);

CREATE INDEX idx_override_versions_raw_id ON "USR"."override_versions"(raw_id);
CREATE INDEX idx_override_versions_file_hash ON "USR"."override_versions"(file_hash);
CREATE INDEX idx_override_versions_uploaded_at ON "USR"."override_versions"(uploaded_at DESC);

ALTER TABLE IF EXISTS "USR"."override_versions" OWNER to postgres;
COMMENT ON TABLE "USR"."override_versions" IS 'Optional override/plug files for data corrections (must match Bloomberg structure)';


-- Table: USR.adjusted_data
-- Purpose: Merged datasets combining Bloomberg (raw_id) and optional overrides (plug_id)
-- FK: raw_id → data_versions, plug_id → override_versions
-- Constraint: UNIQUE(raw_id, plug_id) prevents duplicate adjusted versions
-- Records: Growth as adjustments are made
CREATE TABLE IF NOT EXISTS "USR"."adjusted_data" (
    adj_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_id UUID NOT NULL REFERENCES "USR"."data_versions"(raw_id),
    plug_id UUID REFERENCES "USR"."override_versions"(plug_id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL DEFAULT 'admin',
    metadata JSONB
);

CREATE UNIQUE INDEX idx_adjusted_data_raw_plug_unique ON "USR"."adjusted_data"(raw_id, plug_id);
CREATE INDEX idx_adjusted_data_raw_id ON "USR"."adjusted_data"(raw_id);
CREATE INDEX idx_adjusted_data_plug_id ON "USR"."adjusted_data"(plug_id);
CREATE INDEX idx_adjusted_data_created_at ON "USR"."adjusted_data"(created_at DESC);

ALTER TABLE IF EXISTS "USR"."adjusted_data" OWNER to postgres;
COMMENT ON TABLE "USR"."adjusted_data" IS 'Merged datasets combining Bloomberg + optional overrides';
COMMENT ON COLUMN "USR"."adjusted_data".plug_id IS 'FK to override_versions; NULL if no overrides were applied';


-- Table: USR.data_quality
-- Purpose: Data quality checks and approval status for adjusted datasets
-- FK: adj_id → adjusted_data
-- Status: passed | failed | warnings
-- Records: One per adjusted_data (grows as new versions are checked)
CREATE TABLE IF NOT EXISTS "USR"."data_quality" (
    dq_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    adj_id UUID NOT NULL REFERENCES "USR"."adjusted_data"(adj_id),
    status VARCHAR(50) NOT NULL CHECK (status IN ('passed', 'failed', 'warnings')),
    checked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL DEFAULT 'admin',
    metadata JSONB
);

CREATE INDEX idx_data_quality_adj_id ON "USR"."data_quality"(adj_id);
CREATE INDEX idx_data_quality_status ON "USR"."data_quality"(status);
CREATE INDEX idx_data_quality_checked_at ON "USR"."data_quality"(checked_at DESC);

ALTER TABLE IF EXISTS "USR"."data_quality" OWNER to postgres;
COMMENT ON TABLE "USR"."data_quality" IS 'Data quality checks and approval status; dq_id is referenced by core tables for traceability';
COMMENT ON COLUMN "USR"."data_quality".status IS 'passed | failed | warnings; Core tables link to dq_id for approval traceability';


-- ============================================================================
-- CORE DATA TABLES (LAYER 2)
-- Now we can safely create these tables with FKs to data_quality
-- ============================================================================

-- Table: USR.company
-- Purpose: Master data for all companies in analysis
-- FK: dq_id → data_quality (data quality check that approved this record)
--     domicile_country → country
-- Records: ~50-100 companies
CREATE TABLE IF NOT EXISTS "USR".company (
    id integer NOT NULL,
    ticker character(15) COLLATE pg_catalog."default" NOT NULL,
    name character varying(50) COLLATE pg_catalog."default" NOT NULL,
    fy_report_month date,
    fx_currency character(4) COLLATE pg_catalog."default",
    begin_year text COLLATE pg_catalog."default",
    sector character varying(50) COLLATE pg_catalog."default",
    bics_name character varying(80) COLLATE pg_catalog."default",
    bics_1 character varying(50) COLLATE pg_catalog."default",
    bics_2 character varying(50) COLLATE pg_catalog."default",
    bics_3 character varying(50) COLLATE pg_catalog."default",
    bics_4 character varying(50) COLLATE pg_catalog."default",
    domicile_country character varying(10) COLLATE pg_catalog."default",
    dq_id UUID REFERENCES "USR"."data_quality"(dq_id),
    CONSTRAINT company_pkey PRIMARY KEY (id)
);

ALTER TABLE IF EXISTS "USR".company OWNER to postgres;
COMMENT ON TABLE "USR".company IS 'Master data: Companies with data quality traceability via dq_id FK';
COMMENT ON COLUMN "USR".company.dq_id IS 'FK to data_quality: Data quality check that approved this company record';


-- Table: USR.monthly_data
-- Purpose: Monthly return data (TSR, Rf, Index TSR)
-- FK: id → company, dq_id → data_quality
-- Records: ~10,000+ monthly data points
CREATE TABLE IF NOT EXISTS "USR".monthly_data (
    id integer NOT NULL,
    ticker character(15) COLLATE pg_catalog."default" NOT NULL,
    date date,
    fx_currency character(4) COLLATE pg_catalog."default",
    key character(50) COLLATE pg_catalog."default",
    value text COLLATE pg_catalog."default",
    dq_id UUID REFERENCES "USR"."data_quality"(dq_id)
);

ALTER TABLE IF EXISTS "USR".monthly_data OWNER to postgres;
COMMENT ON TABLE "USR".monthly_data IS 'Monthly return data with data quality traceability via dq_id FK';
COMMENT ON COLUMN "USR".monthly_data.dq_id IS 'FK to data_quality: Data quality check that approved this monthly data';


-- Table: USR.annual_data
-- Purpose: Annual financial data (revenue, assets, PAT, etc.)
-- FK: id → company, dq_id → data_quality
-- Records: ~5,000+ annual data points
CREATE TABLE IF NOT EXISTS "USR".annual_data (
    id integer NOT NULL,
    ticker character(15) COLLATE pg_catalog."default" NOT NULL,
    fy_year text COLLATE pg_catalog."default",
    fx_currency character(4) COLLATE pg_catalog."default",
    key character(50) COLLATE pg_catalog."default",
    value text COLLATE pg_catalog."default",
    dq_id UUID REFERENCES "USR"."data_quality"(dq_id)
);

ALTER TABLE IF EXISTS "USR".annual_data OWNER to postgres;
COMMENT ON TABLE "USR".annual_data IS 'Annual financial data with data quality traceability via dq_id FK';
COMMENT ON COLUMN "USR".annual_data.dq_id IS 'FK to data_quality: Data quality check that approved this annual data';


-- Table: USR.fy_dates
-- Purpose: Fiscal year mappings and dates
-- FK: id → company, dq_id → data_quality
-- Records: ~100-500 fiscal year mappings
CREATE TABLE IF NOT EXISTS "USR".fy_dates (
    id integer NOT NULL,
    ticker character(15) COLLATE pg_catalog."default" NOT NULL,
    fy_year text COLLATE pg_catalog."default",
    fx_currency character(4) COLLATE pg_catalog."default",
    key character(50) COLLATE pg_catalog."default",
    value text COLLATE pg_catalog."default",
    dq_id UUID REFERENCES "USR"."data_quality"(dq_id)
);

ALTER TABLE IF EXISTS "USR".fy_dates OWNER to postgres;
COMMENT ON TABLE "USR".fy_dates IS 'Fiscal year mappings with data quality traceability via dq_id FK';
COMMENT ON COLUMN "USR".fy_dates.dq_id IS 'FK to data_quality: Data quality check that approved this fiscal year mapping';


-- Table: USR.user_defined_data
-- Purpose: Custom assumptions per company (user input)
-- FK: id → company
-- Records: ~1,000+ custom data points
CREATE TABLE IF NOT EXISTS "USR".user_defined_data (
    id bigint,
    date text COLLATE pg_catalog."default",
    ticker text COLLATE pg_catalog."default",
    "FY_Year" bigint,
    key text COLLATE pg_catalog."default",
    value double precision
);

ALTER TABLE IF EXISTS "USR".user_defined_data OWNER to postgres;
COMMENT ON TABLE "USR".user_defined_data IS 'Custom assumptions per company (user-defined inputs)';


-- ============================================================================
-- CORE TABLE FOREIGN KEY CONSTRAINTS
-- ============================================================================

-- FK: annual_data → company
ALTER TABLE IF EXISTS "USR".annual_data
    ADD CONSTRAINT annual_data_id_fkey FOREIGN KEY (id)
    REFERENCES "USR".company (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION;

-- FK: company → country (domicile)
ALTER TABLE IF EXISTS "USR".company
    ADD CONSTRAINT fk_country FOREIGN KEY (domicile_country)
    REFERENCES "USR".country (code) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION;

-- FK: monthly_data → company
ALTER TABLE IF EXISTS "USR".monthly_data
    ADD CONSTRAINT monthly_data_id_fkey FOREIGN KEY (id)
    REFERENCES "USR".company (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION;

-- FK: user_defined_data → company
ALTER TABLE IF EXISTS "USR".user_defined_data
    ADD CONSTRAINT user_defined_data_id_fkey FOREIGN KEY (id)
    REFERENCES "USR".company (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION;


-- ============================================================================
-- METRICS CALCULATION TABLES (LAYER 3)
-- ============================================================================

-- Table: USR.parameter_scenarios
-- Purpose: Unique parameter combinations for metric calculations
-- Constraint: UNIQUE(parameters) enables parameter deduplication
-- IMPORTANT: parameters JSONB must be canonicalized (keys sorted) before insert
-- Records: Growth as new parameter combinations are used
CREATE TABLE IF NOT EXISTS "USR"."parameter_scenarios" (
    param_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parameters JSONB NOT NULL UNIQUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL DEFAULT 'admin'
);

CREATE INDEX idx_parameter_scenarios_created_at ON "USR"."parameter_scenarios"(created_at DESC);

ALTER TABLE IF EXISTS "USR"."parameter_scenarios" OWNER to postgres;
COMMENT ON TABLE "USR"."parameter_scenarios" IS 'Unique parameter combinations (UNIQUE constraint enables deduplication)';
COMMENT ON COLUMN "USR"."parameter_scenarios".parameters IS 'JSONB with sorted keys; UNIQUE constraint prevents duplicate parameter sets';


-- Table: USR.metric_runs
-- Purpose: Tracks metric calculation executions with deduplication
-- FK: dq_id → data_quality, param_id → parameter_scenarios
-- Constraint: Composite index on (dq_id, param_id, status) for efficient queries
-- Status: pending | running | completed | failed
-- Records: Growth as metrics are calculated
CREATE TABLE IF NOT EXISTS "USR"."metric_runs" (
    calc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dq_id UUID NOT NULL REFERENCES "USR"."data_quality"(dq_id),
    param_id UUID NOT NULL REFERENCES "USR"."parameter_scenarios"(param_id),
    status VARCHAR(50) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL DEFAULT 'admin',
    metadata JSONB
);

CREATE INDEX idx_metric_runs_dq_param ON "USR"."metric_runs"(dq_id, param_id);
CREATE INDEX idx_metric_runs_dq_param_status ON "USR"."metric_runs"(dq_id, param_id, status);
CREATE INDEX idx_metric_runs_status ON "USR"."metric_runs"(status);
CREATE INDEX idx_metric_runs_created_at ON "USR"."metric_runs"(created_at DESC);

ALTER TABLE IF EXISTS "USR"."metric_runs" OWNER to postgres;
COMMENT ON TABLE "USR"."metric_runs" IS 'Metric calculation executions with deduplication by (dq_id, param_id)';
COMMENT ON COLUMN "USR"."metric_runs".status IS 'pending | running | completed | failed; reflects calculation execution state';


-- Table: USR.metric_results
-- Purpose: L1 metrics output from calculation runs (time-series data for charting)
-- FK: calc_id → metric_runs, param_id → parameter_scenarios
-- Records: ~10,000+ time-series points per calc_id
CREATE TABLE IF NOT EXISTS "USR"."metric_results" (
    result_id BIGSERIAL PRIMARY KEY,
    calc_id UUID NOT NULL REFERENCES "USR"."metric_runs"(calc_id),
    param_id UUID NOT NULL REFERENCES "USR"."parameter_scenarios"(param_id),
    ticker VARCHAR(20) NOT NULL,
    fx_currency VARCHAR(3),
    fy_year INTEGER,
    key VARCHAR(255) NOT NULL,
    value NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_metric_results_calc_id ON "USR"."metric_results"(calc_id);
CREATE INDEX idx_metric_results_ticker_key ON "USR"."metric_results"(ticker, key);
CREATE INDEX idx_metric_results_ticker_fy_year ON "USR"."metric_results"(ticker, fy_year);

ALTER TABLE IF EXISTS "USR"."metric_results" OWNER to postgres;
COMMENT ON TABLE "USR"."metric_results" IS 'L1 metrics output (time-series data for charting)';


-- ============================================================================
-- SCENARIOS TABLES (LAYER 4)
-- ============================================================================

-- Table: USR.scenarios
-- Purpose: Groups multiple metric runs together for comparison analysis
-- Records: Growth as users create scenario comparisons
CREATE TABLE IF NOT EXISTS "USR"."scenarios" (
    scenario_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL DEFAULT 'admin'
);

CREATE INDEX idx_scenarios_created_at ON "USR"."scenarios"(created_at DESC);

ALTER TABLE IF EXISTS "USR"."scenarios" OWNER to postgres;
COMMENT ON TABLE "USR"."scenarios" IS 'Groups multiple metric runs together for comparison analysis';


-- Table: USR.scenario_runs
-- Purpose: Junction table linking multiple metric runs to scenarios (many-to-many)
-- FK: scenario_id → scenarios, calc_id → metric_runs
-- Records: Many-to-many relationships between scenarios and metric runs
CREATE TABLE IF NOT EXISTS "USR"."scenario_runs" (
    scenario_id UUID NOT NULL REFERENCES "USR"."scenarios"(scenario_id) ON DELETE CASCADE,
    calc_id UUID NOT NULL REFERENCES "USR"."metric_runs"(calc_id),
    PRIMARY KEY (scenario_id, calc_id)
);

CREATE INDEX idx_scenario_runs_calc_id ON "USR"."scenario_runs"(calc_id);

ALTER TABLE IF EXISTS "USR"."scenario_runs" OWNER to postgres;
COMMENT ON TABLE "USR"."scenario_runs" IS 'Junction table: many-to-many between scenarios and metric runs';


-- ============================================================================
-- OPTIMIZATION TABLES (LAYER 5)
-- ============================================================================

-- Table: USR.optimization_results
-- Purpose: Optimization execution tracking and raw output storage
-- FK: calc_id → metric_runs (UNIQUE means one optimization per metric run)
-- Status: pending | running | completed | failed
-- Records: ~1 per metric_run that undergoes optimization
CREATE TABLE IF NOT EXISTS "USR"."optimization_results" (
    opt_result_id BIGSERIAL PRIMARY KEY,
    calc_id UUID NOT NULL UNIQUE REFERENCES "USR"."metric_runs"(calc_id),
    status VARCHAR(50) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    output_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL DEFAULT 'admin',
    metadata JSONB
);

CREATE INDEX idx_optimization_results_calc_id ON "USR"."optimization_results"(calc_id);
CREATE INDEX idx_optimization_results_status ON "USR"."optimization_results"(status);
CREATE INDEX idx_optimization_results_created_at ON "USR"."optimization_results"(created_at DESC);

ALTER TABLE IF EXISTS "USR"."optimization_results" OWNER to postgres;
COMMENT ON TABLE "USR"."optimization_results" IS 'Optimization execution tracking (one per metric run)';


-- Table: USR.bw_outputs
-- Purpose: Final processed optimization results (ready for charting/display)
-- FK: opt_result_id → optimization_results
-- Records: ~1 per optimization_results
CREATE TABLE IF NOT EXISTS "USR"."bw_outputs" (
    bw_output_id BIGSERIAL PRIMARY KEY,
    opt_result_id BIGSERIAL NOT NULL REFERENCES "USR"."optimization_results"(opt_result_id),
    output_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_bw_outputs_opt_result_id ON "USR"."bw_outputs"(opt_result_id);

ALTER TABLE IF EXISTS "USR"."bw_outputs" OWNER to postgres;
COMMENT ON TABLE "USR"."bw_outputs" IS 'Final processed optimization results (ready for charting)';


-- ============================================================================
-- ASYNC OPERATIONS TABLE (LAYER 6)
-- ============================================================================

-- Table: USR.jobs
-- Purpose: Track async operations (uploads, metrics calculations, optimizations)
-- FK: dq_id → data_quality, calc_id → metric_runs
-- Job Types: upload | metrics
-- Status: queued | in_progress | completed | failed
-- Records: ~1 per upload or metrics request
CREATE TABLE IF NOT EXISTS "USR"."jobs" (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type VARCHAR(50) NOT NULL CHECK (job_type IN ('upload', 'metrics')),
    status VARCHAR(50) NOT NULL DEFAULT 'queued' 
        CHECK (status IN ('queued', 'in_progress', 'completed', 'failed')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    progress_percent INT DEFAULT 0 CHECK (progress_percent >= 0 AND progress_percent <= 100),
    result JSONB,
    error_message TEXT,
    dq_id UUID REFERENCES "USR"."data_quality"(dq_id) ON DELETE SET NULL,
    calc_id UUID REFERENCES "USR"."metric_runs"(calc_id) ON DELETE SET NULL
);

CREATE INDEX idx_jobs_job_type ON "USR"."jobs"(job_type);
CREATE INDEX idx_jobs_status ON "USR"."jobs"(status);
CREATE INDEX idx_jobs_created_at ON "USR"."jobs"(created_at DESC);
CREATE INDEX idx_jobs_dq_id ON "USR"."jobs"(dq_id);
CREATE INDEX idx_jobs_calc_id ON "USR"."jobs"(calc_id);

ALTER TABLE IF EXISTS "USR"."jobs" OWNER to postgres;
COMMENT ON TABLE "USR"."jobs" IS 'Async operation tracking (uploads, metrics, optimizations)';
COMMENT ON COLUMN "USR"."jobs".result IS 'Upload: {dq_id, file_hash, record_count}. Metrics: {calc_id, cached}. Optimization: {opt_result_id}';


-- ============================================================================
-- JOBS TRIGGER: Auto-update timestamp on modification
-- ============================================================================

CREATE OR REPLACE FUNCTION "USR".update_jobs_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_jobs_update_timestamp
BEFORE UPDATE ON "USR"."jobs"
FOR EACH ROW
EXECUTE FUNCTION "USR".update_jobs_timestamp();

COMMENT ON FUNCTION "USR".update_jobs_timestamp() IS 'Trigger function: auto-update jobs.updated_at on modification';


-- ============================================================================
-- INITIAL REFERENCE DATA
-- ============================================================================

-- Country codes: Essential reference data for company domicile lookups
-- These are static and rarely change, but can be updated if new countries are added
INSERT INTO "USR".country (code, country) VALUES 
    ('AUS', 'Australia'),
    ('US', 'United States'),
    ('GB', 'Great Britain'),
    ('IE', 'Ireland'),
    ('NZ', 'New Zealand'),
    ('ZA', 'South Africa'),
    ('MY', 'Malaysia'),
    ('ID', 'Indonesia'),
    ('SG', 'Singapore'),
    ('PG', 'Papua New Guinea'),
    ('HK', 'Hong Kong'),
    ('BM', 'Bermuda'),
    ('CA', 'Canada')
ON CONFLICT DO NOTHING;


-- ============================================================================
-- ANALYTICAL VIEWS
-- ============================================================================

-- Note: These views reference the legacy 'metrics', 'config', and 'metrics_config'
-- tables which should exist from the legacy data pipeline.
-- If they don't exist, these views will fail on execution (not creation).

-- View: USR.l1_wide_metrics
-- Purpose: L1 metrics in wide format (one row per ticker/fy_year/currency)
-- Uses FILTER clause to pivot metric keys into columns
CREATE OR REPLACE VIEW "USR".l1_wide_metrics AS
 SELECT fy_year,
    ticker,
    fx_currency,
    guid,
    max(value) FILTER (WHERE key = 'C_ASSETS'::bpchar)::double precision AS c_assets,
    max(value) FILTER (WHERE key = 'ECF'::bpchar)::double precision AS ecf,
    max(value) FILTER (WHERE key = 'C_MC'::bpchar)::double precision AS c_mc,
    max(value) FILTER (WHERE key = 'NON_CUM_EE'::bpchar)::double precision AS non_cum_ee,
    max(value) FILTER (WHERE key = 'EE'::bpchar)::double precision AS ee,
    max(value) FILTER (WHERE key = 'NON_DIV_ECF'::bpchar)::double precision AS non_div_ecf,
    max(value) FILTER (WHERE key = 'NON_OP_COST'::bpchar)::double precision AS non_op_cost,
    max(value) FILTER (WHERE key = 'OA'::bpchar)::double precision AS oa,
    max(value) FILTER (WHERE key = 'OP_COST'::bpchar)::double precision AS op_cost,
    max(value) FILTER (WHERE key = 'TAX_COST'::bpchar)::double precision AS tax_cost,
    max(value) FILTER (WHERE key = 'XO_COST'::bpchar)::double precision AS xo_cost,
    max(value) FILTER (WHERE key = 'beta'::bpchar)::double precision AS beta,
    max(value) FILTER (WHERE key = 'ke'::bpchar)::double precision AS ke,
    max(value) FILTER (WHERE key = 'rf'::bpchar)::double precision AS rf,
    max(value) FILTER (WHERE key = 'rm'::bpchar)::double precision AS rm,
    max(value) FILTER (WHERE key = 'p_eq_growth'::bpchar)::double precision AS p_eq_growth,
    max(value) FILTER (WHERE key = 't_eq_growth'::bpchar)::double precision AS t_eq_growth,
    max(value) FILTER (WHERE key = 'sector_slope'::bpchar)::double precision AS sector_slope,
    max(value) FILTER (WHERE key = 'FY_TSR'::bpchar)::double precision AS fy_tsr,
    max(value) FILTER (WHERE key = 'FY_TSR_PREL'::bpchar)::double precision AS fy_tsr_prel
   FROM "USR".metrics
  GROUP BY fy_year, ticker, fx_currency, guid
  ORDER BY ticker, fy_year, fx_currency;

ALTER VIEW "USR".l1_wide_metrics OWNER TO postgres;
COMMENT ON VIEW "USR".l1_wide_metrics IS 'L1 metrics in wide format (one row per ticker/fy_year/currency)';


-- View: USR.fin_annual_wide
-- Purpose: Annual financial data in wide format
CREATE OR REPLACE VIEW "USR".fin_annual_wide AS
 SELECT fy_year,
    ticker,
    fx_currency,
    max(value) FILTER (WHERE key = 'Share Price'::bpchar)::double precision AS price,
    max(value) FILTER (WHERE key = 'REVENUE'::bpchar)::double precision AS revenue,
    max(value) FILTER (WHERE key = 'Spot Shares'::bpchar)::double precision AS shrouts,
    max(value) FILTER (WHERE key = 'Total Assets'::bpchar)::double precision AS assets,
    max(value) FILTER (WHERE key = 'FY TSR'::bpchar)::double precision AS fytsr,
    max(value) FILTER (WHERE key = 'MC'::bpchar)::double precision AS mc,
    max(value) FILTER (WHERE key = 'Cash'::bpchar)::double precision AS cash,
    max(value) FILTER (WHERE key = 'PBT'::bpchar)::double precision AS pbt,
    max(value) FILTER (WHERE key = 'MI'::bpchar)::double precision AS mi,
    max(value) FILTER (WHERE key = 'DIST'::bpchar)::double precision AS dist,
    max(value) FILTER (WHERE key = 'DIV'::bpchar)::double precision AS dividend,
    max(value) FILTER (WHERE key = 'PAT'::bpchar)::double precision AS pat,
    max(value) FILTER (WHERE key = 'FA'::bpchar)::double precision AS fixedassets,
    max(value) FILTER (WHERE key = 'Total Equity'::bpchar)::double precision AS eqiity,
    max(value) FILTER (WHERE key = 'INJ'::bpchar)::double precision AS cap_injection,
    max(value) FILTER (WHERE key = 'GW'::bpchar)::double precision AS goodwill,
    max(value) FILTER (WHERE key = 'PAT XO'::bpchar)::double precision AS patxo,
    max(value) FILTER (WHERE key = 'OP INCOME'::bpchar)::double precision AS opincome
   FROM "USR".annual_data
  GROUP BY fy_year, ticker, fx_currency
  ORDER BY ticker, fy_year, fx_currency;

ALTER VIEW "USR".fin_annual_wide OWNER TO postgres;
COMMENT ON VIEW "USR".fin_annual_wide IS 'Annual financial data in wide format';


-- View: USR.fin_monthly_wide
-- Purpose: Monthly financial data in wide format with TSR/Rf/Index calculations
CREATE OR REPLACE VIEW "USR".fin_monthly_wide AS
 WITH monthly_wide AS (
        SELECT monthly_data.date,
           monthly_data.ticker,
           monthly_data.fx_currency,
           max(monthly_data.value) FILTER (WHERE TRIM(BOTH FROM monthly_data.key) = 'Company TSR'::bpchar::text)::double precision AS re,
           max(monthly_data.value) FILTER (WHERE TRIM(BOTH FROM monthly_data.key) = 'Rf'::bpchar::text)::double precision AS rf,
           max(monthly_data.value) FILTER (WHERE TRIM(BOTH FROM monthly_data.key) = 'Index TSR'::bpchar::text)::double precision AS rm
          FROM "USR".monthly_data
         GROUP BY monthly_data.date, monthly_data.ticker, monthly_data.fx_currency
         ORDER BY monthly_data.ticker, monthly_data.date, monthly_data.fx_currency
       )
 SELECT ticker,
    date,
    fx_currency,
    round(re::numeric / 100::numeric + 1::numeric, 4) AS re,
    round(rm::numeric / 100::numeric + 1::numeric, 4) AS rm,
    round(rf::numeric / 100::numeric + 1::numeric, 4) AS rf
   FROM monthly_wide;

ALTER VIEW "USR".fin_monthly_wide OWNER TO postgres;
COMMENT ON VIEW "USR".fin_monthly_wide IS 'Monthly financial data in wide format';


-- View: USR.metrics_for_aggregation
-- Purpose: Metrics filtered for 10Y/5Y/3Y/1Y period analysis with open values
CREATE OR REPLACE VIEW "USR".metrics_for_aggregation AS
 SELECT metrics.guid,
    metrics.ticker,
    metrics.fy_year::integer AS fy_year,
    metrics.fx_currency,
    metrics.key,
    metrics.value::numeric AS value
   FROM "USR".metrics
  WHERE metrics.key = ANY (ARRAY['x_open_beta_10_Y'::bpchar, 'x_open_beta_5_Y'::bpchar, 'x_open_beta_3_Y'::bpchar, 'x_open_beta_1_Y'::bpchar, 'c_assets_10_Y'::bpchar, 'c_assets_5_Y'::bpchar, 'c_assets_3_Y'::bpchar, 'c_assets_1_Y'::bpchar, 'ecf_10_Y'::bpchar, 'ecf_5_Y'::bpchar, 'ecf_3_Y'::bpchar, 'ecf_1_Y'::bpchar, 'pat_10_Y'::bpchar, 'pat_5_Y'::bpchar, 'pat_3_Y'::bpchar, 'pat_1_Y'::bpchar, 'xo_cost_10_Y'::bpchar, 'xo_cost_5_Y'::bpchar, 'xo_cost_3_Y'::bpchar, 'xo_cost_1_Y'::bpchar, 'c_mc_10_Y'::bpchar, 'c_mc_5_Y'::bpchar, 'c_mc_3_Y'::bpchar, 'c_mc_1_Y'::bpchar, 'ee_10_Y'::bpchar, 'ee_5_Y'::bpchar, 'ee_3_Y'::bpchar, 'ee_1_Y'::bpchar, 'goodwill_10_Y'::bpchar, 'goodwill_5_Y'::bpchar, 'goodwill_3_Y'::bpchar, 'goodwill_1_Y'::bpchar, 'fixedassets_10_Y'::bpchar, 'fixedassets_5_Y'::bpchar, 'fixedassets_3_Y'::bpchar, 'fixedassets_1_Y'::bpchar, 'WC_TERA_10_Y'::bpchar, 'WC_TERA_5_Y'::bpchar, 'WC_TERA_3_Y'::bpchar, 'WC_TERA_1_Y'::bpchar, 'WC_10_Y'::bpchar, 'WC_5_Y'::bpchar, 'WC_3_Y'::bpchar, 'WC_1_Y'::bpchar, 'WP_10_Y'::bpchar, 'WP_5_Y'::bpchar, 'WP_3_Y'::bpchar, 'WP_1_Y'::bpchar, 'c_mc_open_10_Y'::bpchar, 'c_mc_open_5_Y'::bpchar, 'c_mc_open_3_Y'::bpchar, 'c_mc_open_1_Y'::bpchar, 'ep_10_Y'::bpchar, 'ep_5_Y'::bpchar, 'ep_3_Y'::bpchar, 'ep_1_Y'::bpchar, 'ee_open_10_Y'::bpchar, 'ee_open_5_Y'::bpchar, 'ee_open_3_Y'::bpchar, 'ee_open_1_Y'::bpchar, 'c_assets_open_10_Y'::bpchar, 'c_assets_open_5_Y'::bpchar, 'c_assets_open_3_Y'::bpchar, 'c_assets_open_1_Y'::bpchar, 'oa_open_10_Y'::bpchar, 'oa_open_5_Y'::bpchar, 'oa_open_3_Y'::bpchar, 'oa_open_1_Y'::bpchar, 'goodwill_open_10_Y'::bpchar, 'goodwill_open_5_Y'::bpchar, 'goodwill_open_3_Y'::bpchar, 'goodwill_open_1_Y'::bpchar, 'fixedassets_open_10_Y'::bpchar, 'fixedassets_open_5_Y'::bpchar, 'fixedassets_open_3_Y'::bpchar, 'fixedassets_open_1_Y'::bpchar, 'pat_ex_10_Y'::bpchar, 'pat_ex_5_Y'::bpchar, 'pat_ex_3_Y'::bpchar, 'pat_ex_1_Y'::bpchar, 'xo_cost_ex_10_Y'::bpchar, 'xo_cost_ex_5_Y'::bpchar, 'xo_cost_ex_3_Y'::bpchar, 'xo_cost_ex_1_Y'::bpchar, 'c_assets_ex_10_Y'::bpchar, 'c_assets_ex_5_Y'::bpchar, 'c_assets_ex_3_Y'::bpchar, 'c_assets_ex_1_Y'::bpchar, 'oa_ex_10_Y'::bpchar, 'oa_ex_5_Y'::bpchar, 'oa_ex_3_Y'::bpchar, 'oa_ex_1_Y'::bpchar, 'goodwill_ex_10_Y'::bpchar, 'goodwill_ex_5_Y'::bpchar, 'goodwill_ex_3_Y'::bpchar, 'goodwill_ex_1_Y'::bpchar, 'fixedassets_ex_10_Y'::bpchar, 'fixedassets_ex_5_Y'::bpchar, 'fixedassets_ex_3_Y'::bpchar, 'fixedassets_ex_1_Y'::bpchar])
 UNION ALL
 SELECT metrics.guid,
    metrics.ticker,
    metrics.fy_year::integer + 1 AS fy_year,
    metrics.fx_currency,
    concat('open_', TRIM(BOTH FROM metrics.key)) AS key,
    metrics.value::numeric AS value
   FROM "USR".metrics
  WHERE metrics.key = ANY (ARRAY['rf_10_Y'::bpchar, 'rf_5_Y'::bpchar, 'rf_3_Y'::bpchar, 'rf_1_Y'::bpchar])
  ORDER BY 2, 3, 4;

ALTER VIEW "USR".metrics_for_aggregation OWNER TO postgres;
COMMENT ON VIEW "USR".metrics_for_aggregation IS 'Metrics filtered for 10Y/5Y/3Y/1Y period analysis';


-- View: USR.lvl1_metrics
-- Purpose: Calculated L1 metrics (calc_mc, calc_ecf, calc_assets, calc_oa, calc_ee, non_div_ecf)
CREATE OR REPLACE VIEW "USR".lvl1_metrics AS
 WITH lvl1_metrics AS (
         SELECT a.fy_year,
            a.ticker,
            a.fx_currency,
            a.price,
            a.revenue,
            a.shrouts,
            a.assets,
            a.fytsr,
            a.mc,
            a.cash,
            a.pbt,
            a.mi,
            a.dist,
            a.dividend,
            a.pat,
            a.fixedassets,
            a.eqiity,
            a.cap_injection,
            a.goodwill,
            a.patxo,
            a.opincome,
            a.price * a.shrouts AS calc_mc,
            a.assets - a.cash AS calc_assets,
            a.assets - a.cash - a.fixedassets AS calc_oa,
            a.eqiity - a.mi AS calc_ee
           FROM "USR".fin_annual_wide a
        ), lvl2_metrics AS (
         SELECT b.fy_year,
            b.ticker,
            b.fx_currency,
            b.price,
            b.revenue,
            b.shrouts,
            b.assets,
            b.fytsr,
            b.mc,
            b.cash,
            b.pbt,
            b.mi,
            b.dist,
            b.dividend,
            b.pat,
            b.fixedassets,
            b.eqiity,
            b.cap_injection,
            b.goodwill,
            b.patxo,
            b.opincome,
            b.calc_mc,
            b.calc_assets,
            b.calc_oa,
            b.calc_ee,
            lag(b.calc_mc, 1) OVER (ORDER BY b.ticker, b.fy_year) * (1::double precision + b.fytsr / 100::double precision) - b.calc_mc AS calc_ecf
           FROM lvl1_metrics b
        ), lvl3_metrics AS (
         SELECT c.ticker,
            c.fx_currency,
            c.fy_year,
            c.calc_mc,
            c.calc_ecf,
            c.calc_assets,
            c.calc_oa,
            c.calc_ee,
            c.calc_ecf - c.dividend AS non_div_ecf
           FROM lvl2_metrics c
        )
 SELECT ticker,
    fx_currency,
    fy_year,
    calc_mc,
    calc_ecf,
    calc_assets,
    calc_oa,
    calc_ee,
    non_div_ecf
   FROM lvl3_metrics;

ALTER VIEW "USR".lvl1_metrics OWNER TO postgres;
COMMENT ON VIEW "USR".lvl1_metrics IS 'Calculated L1 metrics (market cap, ECF, assets, equity, etc.)';


-- View: USR.l1_wide_metrics_c
-- Purpose: L1 metrics in wide format (excluding TSR columns)
CREATE OR REPLACE VIEW "USR".l1_wide_metrics_c AS
 SELECT fy_year,
    ticker,
    fx_currency,
    guid,
    max(value) FILTER (WHERE key = 'C_ASSETS'::bpchar)::double precision AS c_assets,
    max(value) FILTER (WHERE key = 'ECF'::bpchar)::double precision AS ecf,
    max(value) FILTER (WHERE key = 'C_MC'::bpchar)::double precision AS c_mc,
    max(value) FILTER (WHERE key = 'NON_CUM_EE'::bpchar)::double precision AS non_cum_ee,
    max(value) FILTER (WHERE key = 'EE'::bpchar)::double precision AS ee,
    max(value) FILTER (WHERE key = 'NON_DIV_ECF'::bpchar)::double precision AS non_div_ecf,
    max(value) FILTER (WHERE key = 'NON_OP_COST'::bpchar)::double precision AS non_op_cost,
    max(value) FILTER (WHERE key = 'OA'::bpchar)::double precision AS oa,
    max(value) FILTER (WHERE key = 'OP_COST'::bpchar)::double precision AS op_cost,
    max(value) FILTER (WHERE key = 'TAX_COST'::bpchar)::double precision AS tax_cost,
    max(value) FILTER (WHERE key = 'XO_COST'::bpchar)::double precision AS xo_cost,
    max(value) FILTER (WHERE key = 'beta'::bpchar)::double precision AS beta,
    max(value) FILTER (WHERE key = 'ke'::bpchar)::double precision AS ke,
    max(value) FILTER (WHERE key = 'rf'::bpchar)::double precision AS rf,
    max(value) FILTER (WHERE key = 'rm'::bpchar)::double precision AS rm,
    max(value) FILTER (WHERE key = 'p_eq_growth'::bpchar)::double precision AS p_eq_growth,
    max(value) FILTER (WHERE key = 't_eq_growth'::bpchar)::double precision AS t_eq_growth,
    max(value) FILTER (WHERE key = 'sector_slope'::bpchar)::double precision AS sector_slope
   FROM "USR".metrics
  GROUP BY fy_year, ticker, fx_currency, guid
  ORDER BY ticker, fy_year, fx_currency;

ALTER VIEW "USR".l1_wide_metrics_c OWNER TO postgres;
COMMENT ON VIEW "USR".l1_wide_metrics_c IS 'L1 metrics in wide format (excluding TSR columns)';


-- ============================================================================
-- PL/pgSQL FUNCTIONS
-- ============================================================================

-- Function: USR.get_param_for_goal_seek
-- Purpose: Retrieve parameters needed for goal-seeking calculations
-- Used in: Optimization workflows
CREATE OR REPLACE FUNCTION "USR".get_param_for_goal_seek (
    country text,
    input_id text,
    start_yr bigint,
    end_yr bigint
)
RETURNS TABLE (
    ticker CHAR(15),
    begin_year text,
    fy_year bigint,
    book_equity DOUBLE PRECISION,
    obs_mkt_val DOUBLE PRECISION,
    ke DOUBLE PRECISION,
    t_eq_growth DOUBLE PRECISION,
    p_eq_growth DOUBLE PRECISION,
    tax_rate DOUBLE PRECISION,
    franking_ratio DOUBLE PRECISION,
    risk_premium DOUBLE PRECISION,
    value_of_fr_credits DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    WITH tickerlist AS (
        SELECT DISTINCT c.ticker,
                        c.begin_year
        FROM "USR".company AS c
        WHERE c.domicile_country = country
    ),
    ticker_with_fy AS (
        SELECT a.*
        FROM (
            SELECT *
            FROM tickerlist AS e
            CROSS JOIN LATERAL generate_series(start_yr, end_yr, 1) AS fy_year
        ) AS a
        ORDER BY a.ticker
    ),
    latest_usr_defined AS (
        SELECT c.guid,
               max(c.value) FILTER (WHERE trim(c.KEY) = 'frank_tax_rate') AS tax_rate,
               max(c.value) FILTER (WHERE trim(c.KEY) = 'franking') AS franking_ratio,
               max(c.value) FILTER (WHERE trim(c.KEY) = 'risk_premium ') AS risk_premium
        FROM "USR".config AS c
        GROUP BY c.guid
        HAVING c.guid = input_id
    ),
    calculated_metrics AS (
        SELECT DISTINCT c.ticker,
                        c.guid,
                        c.fy_year,
                        c.c_mc AS obs_mkt_val,
                        c.ee AS book_equity,
                        c.ke,
                        c.t_eq_growth,
                        c.p_eq_growth
        FROM "USR".l1_wide_metrics AS c
        WHERE c.guid = input_id
    ),
    all_input_var AS (
        SELECT b.ticker,
               b.begin_year,
               b.fy_year,
               c.book_equity,
               c.obs_mkt_val,
               c.ke,
               CAST(0.05 AS DOUBLE PRECISION) AS t_eq_growth,
               CAST(0.1 AS DOUBLE PRECISION) AS p_eq_growth,
               CAST(a.tax_rate AS DOUBLE PRECISION) AS tax_rate,
               CAST(a.franking_ratio AS DOUBLE PRECISION) AS franking_ratio,
               CAST(a.risk_premium AS DOUBLE PRECISION) AS risk_premium,
               CAST(0.75 AS DOUBLE PRECISION) AS value_of_fr_credits
        FROM latest_usr_defined AS a
        INNER JOIN calculated_metrics AS c ON a.guid = c.guid
        INNER JOIN ticker_with_fy AS b ON c.ticker = b.ticker
            AND CAST(c.fy_year AS bigint) = CAST(b.fy_year AS bigint)
    )
    SELECT *
    FROM all_input_var;
END
$$ LANGUAGE plpgsql;

ALTER FUNCTION "USR".get_param_for_goal_seek(text, text, bigint, bigint) OWNER TO postgres;
COMMENT ON FUNCTION "USR".get_param_for_goal_seek(text, text, bigint, bigint) IS 'Retrieve parameters for goal-seeking calculations';


-- ============================================================================
-- SCHEMA VALIDATION CHECKLIST (For verification after setup)
-- ============================================================================
--
-- Run these queries to verify the schema is complete and correct:
--
-- 1. Check all tables exist:
--    SELECT COUNT(*) FROM information_schema.tables 
--    WHERE table_schema = 'USR' AND table_type = 'BASE TABLE';
--    Expected: 19 tables
--
-- 2. Check all views exist:
--    SELECT COUNT(*) FROM information_schema.views 
--    WHERE table_schema = 'USR';
--    Expected: 6 views (config_wide and report_parameters omitted; they reference deprecated tables)
--
-- 3. Check all functions exist:
--    SELECT COUNT(*) FROM information_schema.routines 
--    WHERE routine_schema = 'USR' AND routine_type = 'FUNCTION';
--    Expected: 2 functions (get_param_for_goal_seek + update_jobs_timestamp)
--
-- 4. Check country data loaded:
--    SELECT COUNT(*) FROM "USR".country;
--    Expected: 13 countries
--
-- 5. Check foreign key constraints:
--    SELECT COUNT(*) FROM information_schema.referential_constraints 
--    WHERE constraint_schema = 'USR';
--    Expected: 12 FK constraints
--
-- 6. Check indexes created:
--    SELECT COUNT(*) FROM information_schema.statistics 
--    WHERE table_schema = 'USR' AND index_name LIKE 'idx_%';
--    Expected: 31 indexes
--
-- ============================================================================
