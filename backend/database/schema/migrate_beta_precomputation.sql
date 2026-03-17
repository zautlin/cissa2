-- Migration: Make param_set_id nullable and add pre-computed metrics support
-- Date: 2026-03-16
-- Purpose: Enable pre-computed metrics storage with param_set_id = NULL

-- Step 1: Remove old "Calc Beta" records (legacy runtime-calculated)
DELETE FROM cissa.metrics_outputs 
WHERE output_metric_name = 'Calc Beta';

-- Step 2: Drop old unique index
DROP INDEX IF EXISTS cissa.idx_metrics_outputs_unique;

-- Step 3: Alter table to make param_set_id nullable
ALTER TABLE cissa.metrics_outputs 
ALTER COLUMN param_set_id DROP NOT NULL;

-- Step 4: Drop foreign key constraint and recreate with ON DELETE CASCADE
ALTER TABLE cissa.metrics_outputs
DROP CONSTRAINT IF EXISTS metrics_outputs_param_set_id_fkey,
ADD CONSTRAINT metrics_outputs_param_set_id_fkey 
  FOREIGN KEY (param_set_id) 
  REFERENCES cissa.parameter_sets(param_set_id) 
  ON DELETE CASCADE;

-- Step 5: Create new unique index that handles NULL values
CREATE UNIQUE INDEX idx_metrics_outputs_unique 
ON cissa.metrics_outputs (dataset_id, COALESCE(param_set_id, '00000000-0000-0000-0000-000000000000'::UUID), ticker, fiscal_year, output_metric_name);

-- Step 6: Create index for efficient pre-computed metrics retrieval
CREATE INDEX idx_metrics_outputs_precomputed 
ON cissa.metrics_outputs (dataset_id, ticker, fiscal_year, output_metric_name) 
WHERE param_set_id IS NULL;

-- Step 7: Add monitoring alert configuration (if not exists)
INSERT INTO cissa.parameters (parameter_name, parameter_label, parameter_type, parameter_value)
VALUES ('beta_precomputation_timeout_seconds', 'Beta Pre-computation Timeout (seconds)', 'INTEGER', '120')
ON CONFLICT (parameter_name) DO NOTHING;

INSERT INTO cissa.parameters (parameter_name, parameter_label, parameter_type, parameter_value)
VALUES ('beta_precomputation_alert_threshold_seconds', 'Beta Pre-computation Alert Threshold (seconds)', 'INTEGER', '120')
ON CONFLICT (parameter_name) DO NOTHING;

-- Verify migration
SELECT 'Migration complete. Summary:' as status;
SELECT COUNT(*) as remaining_calc_beta_records FROM cissa.metrics_outputs WHERE output_metric_name = 'Calc Beta';
SELECT COUNT(*) as precomputed_records FROM cissa.metrics_outputs WHERE param_set_id IS NULL;
