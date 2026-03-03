-- ============================================================================
-- FINANCIAL DATA PIPELINE SCHEMA
-- PostgreSQL 16+
-- Created: 2026-03-03
-- Purpose: Bloomberg ASX financial data + analysis outputs
-- ============================================================================
-- This script creates all 12 tables, constraints, indexes, and triggers
-- for the three-stage financial data pipeline.
-- ============================================================================

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
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_companies_ticker ON companies (ticker);
CREATE INDEX idx_companies_sector ON companies (sector);
COMMENT ON TABLE companies IS 'Master list of ASX companies from Base.csv. One-to-many base for all financial data.';

-- Metrics Catalog: All available metrics
CREATE TABLE metrics_catalog (
  metric_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  metric_name TEXT NOT NULL UNIQUE,
  display_name TEXT,
  metric_type TEXT NOT NULL CHECK (metric_type IN ('FISCAL', 'MONTHLY')),
  description TEXT,
  unit TEXT,
  data_type TEXT DEFAULT 'NUMERIC',
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_metrics_type ON metrics_catalog (metric_type);
CREATE INDEX idx_metrics_active ON metrics_catalog (active);
COMMENT ON TABLE metrics_catalog IS 'Catalog of all available metrics (Revenue, Cash, etc.) with their properties.';

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

-- ============================================================================
-- PHASE 2: VERSIONING & TRACKING
-- ============================================================================

-- Dataset Versions: Master audit table for each Bloomberg upload
CREATE TABLE dataset_versions (
  dataset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_name TEXT NOT NULL,
  version_number INTEGER NOT NULL,
  source_file TEXT,
  status TEXT NOT NULL DEFAULT 'PENDING' CHECK (
    status IN ('PENDING', 'INGESTING', 'INGESTED', 'PROCESSING', 'PROCESSED', 'ERROR')
  ),
  
  -- Ingestion stage (Stage 1)
  ingestion_timestamp TIMESTAMPTZ,
  ingestion_completed_at TIMESTAMPTZ,
  total_raw_rows INTEGER,
  validation_rejected_rows INTEGER,
  validation_reject_summary JSONB DEFAULT '{}',
  
  -- Processing stage (Stage 2: FY align + impute)
  processing_timestamp TIMESTAMPTZ,
  processing_completed_at TIMESTAMPTZ,
  quality_metadata JSONB DEFAULT '{}',
  
  -- Audit trail
  created_by TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_dataset_versions_unique ON dataset_versions (dataset_name, version_number);
CREATE INDEX idx_dataset_versions_status ON dataset_versions (status);
CREATE INDEX idx_dataset_versions_created ON dataset_versions (created_at);
COMMENT ON TABLE dataset_versions IS 'Master audit table tracking each Bloomberg data upload and its processing stages.';

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

-- Raw Data: Immutable raw ingestion with validation
-- Stores all values from Excel (even rejected ones) for audit trail
CREATE TABLE raw_data (
  raw_data_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  dataset_id UUID NOT NULL REFERENCES dataset_versions(dataset_id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  period TEXT NOT NULL,
  period_type TEXT NOT NULL CHECK (period_type IN ('FISCAL', 'MONTHLY')),
  
  -- Original value from Excel
  raw_string_value TEXT NOT NULL,
  
  -- Parsed numeric value (NULL if validation failed)
  numeric_value NUMERIC DEFAULT NULL,
  
  currency TEXT,
  
  -- Validation tracking
  validation_status TEXT NOT NULL DEFAULT 'VALID' CHECK (
    validation_status IN ('VALID', 'REJECTED', 'FLAGGED')
  ),
  rejection_reason TEXT,
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_raw_data_dataset ON raw_data (dataset_id);
CREATE INDEX idx_raw_data_ticker ON raw_data (ticker);
CREATE INDEX idx_raw_data_metric ON raw_data (metric_name);
CREATE UNIQUE INDEX idx_raw_data_unique ON raw_data (dataset_id, ticker, metric_name, period);
COMMENT ON TABLE raw_data IS 'Immutable raw ingestion table. Stores validated numeric values; non-numeric values stored as NULL with rejection reason.';

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
  
  -- Cleaned, aligned, imputed value
  value NUMERIC NOT NULL,
  currency TEXT,
  
  -- Quality metadata: where did this value come from?
  imputation_source TEXT NOT NULL CHECK (imputation_source IN (
    'RAW',                -- Valid value from raw data
    'FORWARD_FILL',       -- Carried forward from previous year
    'BACKWARD_FILL',      -- Filled from first known value
    'INTERPOLATED',       -- Linear interpolation between known values
    'SECTOR_MEDIAN',      -- Sector peer median for same fiscal year
    'MARKET_MEDIAN',      -- All companies median for same fiscal year
    'MISSING'             -- Could not be resolved; NULL value
  )),
  confidence_level TEXT,  -- 'HIGH' (raw), 'MEDIUM' (forward_fill), 'LOW' (market_median)
  data_quality_flags JSONB DEFAULT '{}',  -- e.g., {"estimated": true, "revised": false}
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Uniqueness: one row per (dataset, ticker, metric, fiscal_year)
CREATE UNIQUE INDEX idx_fundamentals_unique 
ON fundamentals (dataset_id, ticker, metric_name, fiscal_year);

-- Access patterns
CREATE INDEX idx_fundamentals_dataset ON fundamentals (dataset_id);
CREATE INDEX idx_fundamentals_ticker ON fundamentals (ticker);
CREATE INDEX idx_fundamentals_metric ON fundamentals (metric_name);
CREATE INDEX idx_fundamentals_fiscal_year ON fundamentals (fiscal_year);
CREATE INDEX idx_fundamentals_imputation_source ON fundamentals (imputation_source);

-- Composite indexes for common queries
CREATE INDEX idx_fundamentals_dataset_ticker_fy 
ON fundamentals (dataset_id, ticker, fiscal_year);
CREATE INDEX idx_fundamentals_ticker_metric_fy 
ON fundamentals (ticker, metric_name, fiscal_year);

COMMENT ON TABLE fundamentals IS 'Final cleaned, FY-aligned, imputed fact table. Single source of truth for all downstream analysis. One row per (dataset, ticker, metric, fiscal_year).';

-- Imputation Audit Trail: Optional detailed audit of imputation decisions
-- Can be queried to understand why a specific value was chosen
CREATE TABLE imputation_audit_trail (
  audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  dataset_id UUID NOT NULL REFERENCES dataset_versions(dataset_id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  fiscal_year INTEGER NOT NULL,
  
  -- What was found in raw data
  raw_value NUMERIC,
  raw_status TEXT CHECK (raw_status IN ('PRESENT', 'MISSING', 'INVALID')),
  
  -- Imputation journey
  imputation_steps_applied TEXT[],
  final_imputation_source TEXT,
  final_value NUMERIC,
  
  -- Peer references used (if applicable)
  peer_reference_data JSONB DEFAULT '{}',
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_imputation_audit_dataset ON imputation_audit_trail (dataset_id);
CREATE INDEX idx_imputation_audit_ticker_fy ON imputation_audit_trail (ticker, fiscal_year);
COMMENT ON TABLE imputation_audit_trail IS 'Optional detailed audit trail showing imputation decisions for each value.';

-- ============================================================================
-- PHASE 5: CONFIGURATION & PARAMETERS
-- ============================================================================

-- Parameters: Tunable parameters for analysis
CREATE TABLE parameters (
  parameter_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parameter_name TEXT NOT NULL UNIQUE,
  display_name TEXT,
  description TEXT,
  value_type TEXT NOT NULL CHECK (value_type IN ('NUMERIC', 'TEXT', 'BOOLEAN', 'JSONB')),
  default_value TEXT,
  current_value TEXT,
  unit TEXT,
  min_value NUMERIC,
  max_value NUMERIC,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_parameters_active ON parameters (active);

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

COMMENT ON TABLE parameters IS 'Tunable parameters for metric calculations and optimization (e.g., discount_rate, risk_free_rate).';

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

-- Metrics Outputs: Computed metrics based on fundamentals + parameters
CREATE TABLE metrics_outputs (
  metrics_output_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  dataset_id UUID NOT NULL REFERENCES dataset_versions(dataset_id) ON DELETE CASCADE,
  param_set_id UUID NOT NULL REFERENCES parameter_sets(param_set_id),
  ticker TEXT NOT NULL,
  fiscal_year INTEGER NOT NULL,
  
  -- Output metric
  output_metric_name TEXT NOT NULL,
  output_metric_value NUMERIC NOT NULL,
  confidence_interval_lower NUMERIC,
  confidence_interval_upper NUMERIC,
  
  -- Computation details
  computation_method TEXT,
  derivation_notes TEXT,
  metadata JSONB DEFAULT '{}',
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Uniqueness: one row per (dataset, params, ticker, fiscal_year, metric)
CREATE UNIQUE INDEX idx_metrics_outputs_unique 
ON metrics_outputs (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name);

-- Access patterns
CREATE INDEX idx_metrics_outputs_dataset ON metrics_outputs (dataset_id);
CREATE INDEX idx_metrics_outputs_param_set ON metrics_outputs (param_set_id);
CREATE INDEX idx_metrics_outputs_ticker_fy ON metrics_outputs (ticker, fiscal_year);

COMMENT ON TABLE metrics_outputs IS 'Computed metric outputs based on fundamentals + parameter sets. Allows comparing same dataset with different parameter assumptions.';

-- Optimization Outputs: Results from optimization algorithms
CREATE TABLE optimization_outputs (
  optimization_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES dataset_versions(dataset_id) ON DELETE CASCADE,
  param_set_id UUID NOT NULL REFERENCES parameter_sets(param_set_id),
  ticker TEXT NOT NULL,
  
  -- Optimization details
  optimization_type TEXT NOT NULL,
  objective_function TEXT,
  optimization_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (
    optimization_status IN ('PENDING', 'RUNNING', 'COMPLETED', 'ERROR')
  ),
  
  -- Results
  result_summary JSONB NOT NULL DEFAULT '{}',
  constraint_details JSONB DEFAULT '{}',
  solver_metadata JSONB DEFAULT '{}',
  error_message TEXT,
  
  -- Audit
  created_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Access patterns
CREATE INDEX idx_optimization_outputs_dataset ON optimization_outputs (dataset_id);
CREATE INDEX idx_optimization_outputs_param_set ON optimization_outputs (param_set_id);
CREATE INDEX idx_optimization_outputs_ticker ON optimization_outputs (ticker);
CREATE INDEX idx_optimization_outputs_status ON optimization_outputs (optimization_status);

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

COMMENT ON TABLE optimization_outputs IS 'Results from optimization algorithms (valuation, portfolio, risk). Tracks job status and allows async processing.';

-- ============================================================================
-- OPTIONAL: VALIDATION AUDIT LOG
-- ============================================================================

-- Raw Data Validation Log: Audit trail of validation failures
CREATE TABLE raw_data_validation_log (
  log_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  dataset_id UUID NOT NULL REFERENCES dataset_versions(dataset_id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  period TEXT NOT NULL,
  raw_value TEXT,
  rejection_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_validation_log_dataset ON raw_data_validation_log (dataset_id);
COMMENT ON TABLE raw_data_validation_log IS 'Audit trail of validation failures during ingestion for compliance and debugging.';

-- ============================================================================
-- SUMMARY
-- ============================================================================
-- Total tables created: 12
-- - Reference: 3 (companies, metrics_catalog, fiscal_year_mapping)
-- - Versioning: 1 (dataset_versions)
-- - Raw Data: 1 (raw_data) + 1 optional (raw_data_validation_log)
-- - Cleaned Data: 2 (fundamentals, imputation_audit_trail)
-- - Configuration: 2 (parameters, parameter_sets)
-- - Downstream: 2 (metrics_outputs, optimization_outputs)
--
-- Total indexes: 30+
-- Total triggers: 4 (auto-update timestamps)
-- ============================================================================
