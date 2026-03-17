-- ============================================================================
-- FINANCIAL DATA PIPELINE SCHEMA
-- PostgreSQL 16+
-- Created: 2026-03-03
-- Purpose: Bloomberg ASX financial data + analysis outputs
-- Schema: cissa (separate from public schema)
-- ============================================================================
-- This script creates all 12 tables, constraints, indexes, and triggers
-- for the three-stage financial data pipeline in the 'cissa' schema.
-- ============================================================================

-- ============================================================================
-- CREATE SCHEMA
-- ============================================================================
-- Create the cissa schema if it doesn't exist. All pipeline tables will be
-- created in this schema to keep them separate from other database objects.
CREATE SCHEMA IF NOT EXISTS cissa;
SET search_path TO cissa;
COMMENT ON SCHEMA cissa IS 'Financial data pipeline schema - Contains all Bloomberg ASX data, processing tables, and analysis outputs';

-- ============================================================================
-- PHASE 1: REFERENCE TABLES (Immutable Lookup Data)
-- ============================================================================

-- Companies: Master list from Base.csv
CREATE TABLE companies (
  company_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  sector TEXT,
  bics_level_1 TEXT,
  bics_level_2 TEXT,
  bics_level_3 TEXT,
  bics_level_4 TEXT,
  currency TEXT NOT NULL DEFAULT 'AUD',
  country TEXT NOT NULL DEFAULT 'Australia',
  parent_index TEXT,
  fy_report_month DATE,
  begin_year INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_companies_ticker ON companies (ticker);
CREATE INDEX idx_companies_sector ON companies (sector);
CREATE INDEX idx_companies_country ON companies (country);
CREATE INDEX idx_companies_parent_index ON companies (parent_index);
COMMENT ON TABLE companies IS 'Master list of companies from Base.csv. One-to-many base for all financial data. Includes country (Australia/US/UK), parent_index (ASX200 for top 200 by market cap), fiscal year end month, and first year of data availability.';

-- Fiscal Year Mapping: FY dates from FY Dates.csv
-- Maps (ticker, fiscal_year) → fy_period_date for alignment
CREATE TABLE fiscal_year_mapping (
  fy_mapping_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ticker TEXT NOT NULL,
  fiscal_year INTEGER NOT NULL,
  fy_period_date DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_fy_mapping_unique ON fiscal_year_mapping (ticker, fiscal_year);
CREATE INDEX idx_fy_mapping_ticker ON fiscal_year_mapping (ticker);
COMMENT ON TABLE fiscal_year_mapping IS 'Maps (ticker, fiscal_year) to fiscal period end date. Used for FY alignment during processing.';

-- Metric Units: Lookup table for metric measurement units
-- Maps each metric name to its unit (e.g., "Revenue" → "millions", "FY TSR" → "%")
-- Populated during schema initialization from metric_units.json configuration
CREATE TABLE metric_units (
  metric_units_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  metric_name TEXT NOT NULL UNIQUE,
  unit TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_metric_units_name ON metric_units (metric_name);
COMMENT ON TABLE metric_units IS 'Reference table mapping metric names to their units. Units: "millions" (AUD/currency), "%", "number of shares". Populated from backend/database/config/metric_units.json during schema initialization.';
COMMENT ON COLUMN metric_units.metric_name IS 'Unique metric identifier (e.g., "Revenue", "Company TSR (Monthly)", "Spot Shares")';
COMMENT ON COLUMN metric_units.unit IS 'Unit of measurement for the metric (e.g., "millions", "%", "number of shares")';

-- Auto-update trigger for metric_units.updated_at
CREATE OR REPLACE FUNCTION update_metric_units_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_metric_units_updated
BEFORE UPDATE ON metric_units
FOR EACH ROW
EXECUTE FUNCTION update_metric_units_timestamp();

-- ============================================================================
-- PHASE 2: VERSIONING & TRACKING
-- ============================================================================

-- Dataset Versions: Master audit table for each data ingestion
CREATE TABLE dataset_versions (
  dataset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_name TEXT NOT NULL,
  version_number INTEGER NOT NULL,
  source_file TEXT NOT NULL,
  source_file_hash TEXT NOT NULL,
  
  metadata JSONB NOT NULL DEFAULT '{}',
  
  created_by TEXT NOT NULL DEFAULT 'admin',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_dataset_versions_unique ON dataset_versions (dataset_name, source_file_hash);
CREATE INDEX idx_dataset_versions_created ON dataset_versions (created_at);
COMMENT ON TABLE dataset_versions IS 'Master audit table tracking each data ingestion run. Stores dataset_name (auto-calculated), version_number (increments per hash change), source_file_hash (for duplicate detection), and metadata (ingestion/processing stats).';

-- Auto-update trigger for dataset_versions.updated_at
CREATE OR REPLACE FUNCTION update_dataset_versions_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_dataset_versions_updated
BEFORE UPDATE ON dataset_versions
FOR EACH ROW
EXECUTE FUNCTION update_dataset_versions_timestamp();

-- ============================================================================
-- PHASE 3: RAW DATA (Staging)
-- ============================================================================

-- Raw Data: Immutable raw ingestion (all rows from source)
-- Stores all values from CSV as-is (no filtering or validation)
CREATE TABLE raw_data (
  raw_data_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  dataset_id UUID NOT NULL REFERENCES dataset_versions(dataset_id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  period TEXT NOT NULL,
  period_type TEXT NOT NULL CHECK (period_type IN ('FISCAL', 'MONTHLY')),
  
  -- Original value from CSV
  raw_string_value TEXT NOT NULL,
  
  -- Parsed numeric value
  numeric_value NUMERIC NOT NULL,
  
  currency TEXT,
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_raw_data_dataset ON raw_data (dataset_id);
CREATE INDEX idx_raw_data_ticker ON raw_data (ticker);
CREATE INDEX idx_raw_data_metric ON raw_data (metric_name);
CREATE UNIQUE INDEX idx_raw_data_unique ON raw_data (dataset_id, ticker, metric_name, period);
COMMENT ON TABLE raw_data IS 'Immutable raw ingestion table. Source of truth for all financial data. Stores all rows from input CSV exactly as-is.';

-- ============================================================================
-- PHASE 4: CLEANED DATA (Fact Table)
-- ============================================================================

-- Fundamentals: THE final cleaned, aligned, imputed fact table
-- This is the single source of truth for all downstream analysis
CREATE TABLE fundamentals (
  fundamentals_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  dataset_id UUID NOT NULL REFERENCES dataset_versions(dataset_id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  fiscal_year INTEGER NOT NULL,
  fiscal_month INTEGER,
  fiscal_day INTEGER,
  
  -- Cleaned, aligned, imputed value
  numeric_value NUMERIC NOT NULL,
  currency TEXT,
  
  -- Period type: tracks whether data is FISCAL or MONTHLY
  -- FISCAL: fiscal_year populated, fiscal_month/fiscal_day are NULL
  -- MONTHLY: all three populated from calendar date
  period_type TEXT NOT NULL CHECK (period_type IN ('FISCAL', 'MONTHLY')) DEFAULT 'FISCAL',
  
  -- Quality tracking
  imputed BOOLEAN NOT NULL DEFAULT false,
  metadata JSONB NOT NULL DEFAULT '{}',
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Uniqueness: one row per (dataset, ticker, metric, fiscal_year, fiscal_month, fiscal_day)
-- Uses COALESCE to treat NULL as 0 so FISCAL records (with NULL month/day) don't conflict
CREATE UNIQUE INDEX idx_fundamentals_unique 
ON fundamentals (dataset_id, ticker, metric_name, fiscal_year, COALESCE(fiscal_month, 0), COALESCE(fiscal_day, 0));

-- Access patterns
CREATE INDEX idx_fundamentals_dataset ON fundamentals (dataset_id);
CREATE INDEX idx_fundamentals_ticker ON fundamentals (ticker);
CREATE INDEX idx_fundamentals_metric ON fundamentals (metric_name);
CREATE INDEX idx_fundamentals_fiscal_year ON fundamentals (fiscal_year);
CREATE INDEX idx_fundamentals_period_type ON fundamentals (period_type);

-- Composite indexes for common queries
CREATE INDEX idx_fundamentals_dataset_ticker_fy 
ON fundamentals (dataset_id, ticker, fiscal_year);
CREATE INDEX idx_fundamentals_ticker_metric_fy 
ON fundamentals (ticker, metric_name, fiscal_year);
CREATE INDEX idx_fundamentals_ticker_period_type 
ON fundamentals (ticker, period_type);

COMMENT ON TABLE fundamentals IS 'Final cleaned, FY-aligned, imputed fact table. Single source of truth for all downstream analysis. One row per (dataset, ticker, metric, fiscal_year, fiscal_month, fiscal_day). Stores both FISCAL (month/day NULL) and MONTHLY (all components populated) records. metadata tracks imputation_step and confidence_level.';

-- Imputation Audit Trail: Detailed audit of imputation decisions
-- One row per imputed (ticker, fiscal_year, metric); raw data rows have no entry
 CREATE TABLE imputation_audit_trail (
   audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
   dataset_id UUID NOT NULL REFERENCES dataset_versions(dataset_id) ON DELETE CASCADE,
   ticker TEXT NOT NULL,
   metric_name TEXT NOT NULL,
   fiscal_year INTEGER,  -- Nullable for data quality issues without clear fiscal year mapping
   
   -- Imputation or data quality issue details
   imputation_step TEXT NOT NULL CHECK (imputation_step IN (
     'FORWARD_FILL',
     'BACKWARD_FILL',
     'INTERPOLATE',
     'SECTOR_MEDIAN',
     'MARKET_MEDIAN',
     'MISSING',
     'DATA_QUALITY_DUPLICATE',
     'DATA_QUALITY_INVALID_VALUE',
     'DATA_QUALITY_MISSING'
   )),
   original_value NUMERIC,
   imputed_value NUMERIC NOT NULL,
   
   -- Metadata: stores period/date and other context as JSON
   -- For duplicates: {"period": "2023-09-29", "num_occurrences": 2}
   metadata JSONB DEFAULT '{}',
   
   created_at TIMESTAMPTZ NOT NULL DEFAULT now()
 );
CREATE INDEX idx_imputation_audit_dataset ON imputation_audit_trail (dataset_id);
CREATE INDEX idx_imputation_audit_ticker_fy ON imputation_audit_trail (ticker, fiscal_year);
CREATE INDEX idx_imputation_audit_step ON imputation_audit_trail (imputation_step);
COMMENT ON TABLE imputation_audit_trail IS 'Audit trail of imputation decisions and data quality issues. Records imputations (forward fill, interpolation, etc.) and raw data quality issues (duplicates, invalid values). For duplicates, metadata contains the period/date where issue was found.';

-- ============================================================================
-- PHASE 5: CONFIGURATION & PARAMETERS
-- ============================================================================

-- Parameters: Master list of tunable parameters for metric calculations
-- Source of truth for baseline parameters; parameter_sets reference these via overrides
CREATE TABLE parameters (
  parameter_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parameter_name TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  value_type TEXT,
  default_value TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_parameters_name ON parameters (parameter_name);

-- Auto-update trigger for parameters.updated_at
CREATE OR REPLACE FUNCTION update_parameters_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_parameters_updated
BEFORE UPDATE ON parameters
FOR EACH ROW
EXECUTE FUNCTION update_parameters_timestamp();

COMMENT ON TABLE parameters IS 'Master list of tunable parameters for metric calculations and optimizations. 13 baseline parameters defined. Update default_value when parameters change; create new parameter_set with overrides.';

-- Parameter Sets: Named bundles of parameter configurations
CREATE TABLE parameter_sets (
  param_set_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  param_set_name TEXT NOT NULL UNIQUE,
  description TEXT,
  is_default BOOLEAN NOT NULL DEFAULT false,
  is_active BOOLEAN NOT NULL DEFAULT true,
  param_overrides JSONB NOT NULL DEFAULT '{}',
  created_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_parameter_sets_default ON parameter_sets (is_default);
CREATE INDEX idx_parameter_sets_active ON parameter_sets (is_active);

-- Auto-update trigger for parameter_sets.updated_at
CREATE OR REPLACE FUNCTION update_parameter_sets_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_parameter_sets_updated
BEFORE UPDATE ON parameter_sets
FOR EACH ROW
EXECUTE FUNCTION update_parameter_sets_timestamp();

COMMENT ON TABLE parameter_sets IS 'Named bundles of parameter configurations for reproducibility (e.g., "conservative_valuation", "base_case").';

-- ============================================================================
-- PHASE 6: DOWNSTREAM OUTPUTS
-- ============================================================================

-- Metrics Outputs: Computed metrics from fundamentals + parameters
 CREATE TABLE metrics_outputs (
   metrics_output_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
   dataset_id UUID NOT NULL REFERENCES dataset_versions(dataset_id) ON DELETE CASCADE,
   param_set_id UUID REFERENCES parameter_sets(param_set_id) ON DELETE CASCADE,
   ticker TEXT NOT NULL,
   fiscal_year INTEGER NOT NULL,
   
   output_metric_name TEXT NOT NULL,
   output_metric_value NUMERIC NOT NULL,
   
   metadata JSONB NOT NULL DEFAULT '{}',
   
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Unique constraint for ON CONFLICT upserts
    -- Required by metrics calculation service for idempotent inserts
    UNIQUE (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
  );

  -- Uniqueness: one row per (dataset, params, ticker, fiscal_year, metric)
  -- When param_set_id is NULL (pre-computed metrics), allow only one row
  CREATE UNIQUE INDEX idx_metrics_outputs_unique 
  ON metrics_outputs (dataset_id, COALESCE(param_set_id, '00000000-0000-0000-0000-000000000000'::UUID), ticker, fiscal_year, output_metric_name);

 -- Index for pre-computed metrics (param_set_id IS NULL)
 CREATE INDEX idx_metrics_outputs_precomputed 
 ON metrics_outputs (dataset_id, ticker, fiscal_year, output_metric_name) 
 WHERE param_set_id IS NULL;

-- Access patterns
CREATE INDEX idx_metrics_outputs_dataset ON metrics_outputs (dataset_id);
CREATE INDEX idx_metrics_outputs_param_set ON metrics_outputs (param_set_id);
CREATE INDEX idx_metrics_outputs_ticker_fy ON metrics_outputs (ticker, fiscal_year);

COMMENT ON TABLE metrics_outputs IS 'Computed metric outputs derived from fundamentals + parameter sets. One row per (dataset, param_set, ticker, fiscal_year, metric).';

-- Optimization Outputs: Results from optimization algorithms
-- Stores hierarchical projection results organized by base_year for efficient multi-year charting
-- One optimization per (dataset_id, param_set_id, ticker) combination
-- Allows multiple optimizations (re-runs) with different timestamps
CREATE TABLE optimization_outputs (
  optimization_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES dataset_versions(dataset_id) ON DELETE CASCADE,
  param_set_id UUID NOT NULL REFERENCES parameter_sets(param_set_id),
  ticker TEXT NOT NULL,
  
  -- Results: hierarchical structure {base_year: {metric: {projected_year: value}}}
  -- Example: {"2000": {"ep": {"2001": -0.0004, ...}, "market_value_equity": {...}}, "2001": {...}, ...}
  -- Enables efficient multi-base-year queries for UI charting
  result_summary JSONB NOT NULL DEFAULT '{}',
  
  -- Metadata: convergence status, iterations, solver info, residuals
  -- Example: {convergence_status: "converged", iterations: 1247, residual: 2.3e-12, initial_ep: -0.0004, optimal_ep: -0.000387, solver: "scipy.optimize.basinhopping"}
  metadata JSONB NOT NULL DEFAULT '{}',
  
  created_by TEXT NOT NULL DEFAULT 'admin',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Natural key index for efficient queries (allows re-optimizations)
-- Composite index ordered by created_at DESC for "latest optimization" queries
CREATE INDEX idx_optimization_outputs_natural_key 
ON optimization_outputs (dataset_id, param_set_id, ticker, created_at DESC);

-- Access patterns for filtering
CREATE INDEX idx_optimization_outputs_dataset ON optimization_outputs (dataset_id);
CREATE INDEX idx_optimization_outputs_param_set ON optimization_outputs (param_set_id);
CREATE INDEX idx_optimization_outputs_ticker ON optimization_outputs (ticker);

-- GIN index for JSONB containment queries on result_summary and metadata
CREATE INDEX idx_optimization_outputs_result_summary_gin 
ON optimization_outputs USING GIN (result_summary);
CREATE INDEX idx_optimization_outputs_metadata_gin 
ON optimization_outputs USING GIN (metadata);

-- Auto-update trigger for optimization_outputs.updated_at
CREATE OR REPLACE FUNCTION update_optimization_outputs_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_optimization_outputs_updated
BEFORE UPDATE ON optimization_outputs
FOR EACH ROW
EXECUTE FUNCTION update_optimization_outputs_timestamp();

COMMENT ON TABLE optimization_outputs IS 'Results from optimization algorithms. One row per optimization run for (dataset_id, param_set_id, ticker). Allows multiple optimizations (re-runs) with different timestamps. result_summary stores hierarchical projections {base_year:{metric:{year:value}}} for efficient multi-base-year charting. metadata tracks convergence_status, iterations, residual, initial_ep, optimal_ep, and solver info. Enables traceability: optimization → (dataset, param_set) → metrics_outputs → fundamentals → raw_data.';
COMMENT ON COLUMN optimization_outputs.result_summary IS 'Hierarchical JSONB organized by base_year: {base_year: {metric_name: {projected_year: value, ...}, ...}, ...}. Contains 18 derived metrics (ep, market_value_equity, dividend, pat, return_on_equity, book_value_equity, growth_in_equity, economic_profit, etc.) across all projected years (typically 62 years = convergence_horizon + 2). Optimized for UI charting of multiple base years.';
COMMENT ON COLUMN optimization_outputs.metadata IS 'Optimization execution metadata: {convergence_status, convergence_horizon, iterations, residual, initial_ep, optimal_ep, observed_market_value, calculated_market_value, solver, errors}. convergence_status: "converged" | "diverged" | "max_iterations_reached".';

-- ============================================================================
-- OPTIONAL: VALIDATION AUDIT LOG
-- ============================================================================

-- ============================================================================
-- PHASE 7: BASELINE PARAMETERS & DEFAULT PARAMETER SET
-- ============================================================================
-- Initialize 13 baseline parameters and create default "base_case" parameter set
-- This is run as part of schema creation to ensure complete initialization

-- Insert 13 baseline parameters (if not already present)
INSERT INTO parameters (parameter_name, display_name, value_type, default_value)
VALUES
  ('country', 'Country', 'TEXT', 'Australia'),
  ('currency_notation', 'Currency Notation', 'TEXT', 'A$m'),
  ('cost_of_equity_approach', 'Cost of Equity Approach', 'TEXT', 'Floating'),
  ('include_franking_credits_tsr', 'Include Franking Credits (TSR)', 'BOOLEAN', 'false'),
  ('fixed_benchmark_return_wealth_preservation', 'Fixed Benchmark Return (Wealth Preservation)', 'NUMERIC', '7.5'),
  ('equity_risk_premium', 'Equity Risk Premium', 'NUMERIC', '5.0'),
  ('tax_rate_franking_credits', 'Tax Rate (Franking Credits)', 'NUMERIC', '30.0'),
  ('value_of_franking_credits', 'Value of Franking Credits', 'NUMERIC', '75.0'),
  ('risk_free_rate_rounding', 'Risk-Free Rate Rounding', 'NUMERIC', '0.5'),
  ('beta_rounding', 'Beta Rounding', 'NUMERIC', '0.1'),
  ('last_calendar_year', 'Last Calendar Year', 'NUMERIC', '2019'),
  ('beta_relative_error_tolerance', 'Beta Relative Error Tolerance', 'NUMERIC', '40.0'),
  ('terminal_year', 'Terminal Year', 'NUMERIC', '60')
ON CONFLICT (parameter_name) DO NOTHING;

-- Create default parameter_set "base_case" (if not already present)
INSERT INTO parameter_sets (param_set_name, description, is_default, is_active, param_overrides, created_by)
VALUES
  ('base_case', 'Default parameter set using all 13 baseline parameters', true, true, '{}', 'admin')
ON CONFLICT (param_set_name) DO NOTHING;

-- ============================================================================
-- SUMMARY
-- ============================================================================
-- Total tables created: 11
-- - Reference: 2 (companies, fiscal_year_mapping)
-- - Versioning: 1 (dataset_versions)
-- - Raw Data: 1 (raw_data)
-- - Cleaned Data: 2 (fundamentals, imputation_audit_trail)
-- - Configuration: 2 (parameters, parameter_sets)
-- - Downstream: 2 (metrics_outputs, optimization_outputs)
-- - Removed: metrics_catalog, raw_data_validation_log (errors tracked in dataset_versions.metadata)
--
-- Total indexes: 25+
-- Total triggers: 4 (auto-update timestamps)
-- Baseline parameters: 13 (initialized on schema creation)
-- Default parameter_set: 1 (base_case, created on schema creation)
-- ============================================================================
