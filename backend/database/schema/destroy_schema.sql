-- ============================================================================
-- ⚠️  SCHEMA DESTRUCTION SCRIPT - USE WITH CAUTION
-- ============================================================================
-- THIS SCRIPT WILL PERMANENTLY DELETE ALL TABLES AND DATA
-- There is no undo operation. All financial data will be lost.
--
-- TABLES THAT WILL BE DESTROYED:
--  1. optimization_outputs
--  2. metrics_outputs
--  3. parameter_sets
--  4. parameters
--  5. imputation_audit_trail
--  6. fundamentals
--  7. raw_data
--  8. dataset_versions
--  9. fiscal_year_mapping
-- 10. metric_units
-- 11. companies
--
-- FUNCTIONS/TRIGGERS THAT WILL BE DROPPED:
--  - update_dataset_versions_timestamp()
--  - update_parameters_timestamp()
--  - update_parameter_sets_timestamp()
--  - update_optimization_outputs_timestamp()
--  - update_metric_units_timestamp()
--  - All associated triggers
--
-- ============================================================================
-- CONFIRMATION HANDLED VIA schema_manager.py
-- ============================================================================
-- The Python schema_manager.py handles user confirmation interactively.
-- When --confirm flag is used, the user has already been warned.
-- This SQL script proceeds directly to destruction.

-- ============================================================================
-- DROP TABLES IN DEPENDENCY ORDER (Reverse of creation)
-- ============================================================================

DROP TABLE IF EXISTS optimization_outputs CASCADE;
DROP TABLE IF EXISTS metrics_outputs CASCADE;
DROP TABLE IF EXISTS parameter_sets CASCADE;
DROP TABLE IF EXISTS parameters CASCADE;
DROP TABLE IF EXISTS imputation_audit_trail CASCADE;
DROP TABLE IF EXISTS fundamentals CASCADE;
DROP TABLE IF EXISTS raw_data CASCADE;
DROP TABLE IF EXISTS dataset_versions CASCADE;
DROP TABLE IF EXISTS fiscal_year_mapping CASCADE;
DROP TABLE IF EXISTS metric_units CASCADE;
DROP TABLE IF EXISTS companies CASCADE;

-- ============================================================================
-- DROP TRIGGERS
-- ============================================================================

DROP TRIGGER IF EXISTS trigger_dataset_versions_updated ON dataset_versions;
DROP TRIGGER IF EXISTS trigger_parameters_updated ON parameters;
DROP TRIGGER IF EXISTS trigger_parameter_sets_updated ON parameter_sets;
DROP TRIGGER IF EXISTS trigger_optimization_outputs_updated ON optimization_outputs;
DROP TRIGGER IF EXISTS trigger_metric_units_updated ON metric_units;

-- ============================================================================
-- DROP FUNCTIONS
-- ============================================================================

DROP FUNCTION IF EXISTS update_dataset_versions_timestamp() CASCADE;
DROP FUNCTION IF EXISTS update_parameters_timestamp() CASCADE;
DROP FUNCTION IF EXISTS update_parameter_sets_timestamp() CASCADE;
DROP FUNCTION IF EXISTS update_optimization_outputs_timestamp() CASCADE;
DROP FUNCTION IF EXISTS update_metric_units_timestamp() CASCADE;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 'Schema destruction complete. All 11 tables, triggers, and functions have been dropped.' AS status;

-- ============================================================================
-- END OF DESTRUCTION SCRIPT
-- ============================================================================
