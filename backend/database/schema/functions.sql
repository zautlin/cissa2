-- ============================================================================
-- PHASE 1: METRIC CALCULATION FUNCTIONS
-- PostgreSQL Stored Functions for Simple (Non-Temporal) Metrics
-- ============================================================================
-- These functions calculate Level 1 metrics from cissa.fundamentals data.
-- Each function:
--   1. Takes a dataset_id (UUID) as parameter
--   2. Joins fundamentals table to get input metrics
--   3. Performs SQL calculation
--   4. Returns (ticker, fiscal_year, metric_value) tuples
--   5. Results inserted into cissa.metrics_outputs by FastAPI service
-- ============================================================================

SET search_path TO cissa;

-- ============================================================================
-- GROUP 1: CORE MARKET/EQUITY METRICS
-- ============================================================================

-- 1.1 Market Cap = Spot Shares × Share Price
-- Template function for all Phase 1 metrics
CREATE OR REPLACE FUNCTION fn_calc_market_cap(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  calc_mc NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    f1.ticker,
    f1.fiscal_year,
    (f1.numeric_value * f2.numeric_value) AS calc_mc
  FROM cissa.fundamentals f1
  INNER JOIN cissa.fundamentals f2
    ON f1.ticker = f2.ticker
    AND f1.fiscal_year = f2.fiscal_year
    AND f1.dataset_id = f2.dataset_id
  WHERE
    f1.dataset_id = p_dataset_id
    AND f1.metric_name = 'SPOT_SHARES'
    AND f2.metric_name = 'SHARE_PRICE'
    AND f1.numeric_value IS NOT NULL
    AND f2.numeric_value IS NOT NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_market_cap(UUID) IS
'Calculate Market Cap from Spot Shares and Share Price.
Formula: Spot Shares × Share Price
Output metric name: Calc MC
Handles NULL values gracefully by filtering in WHERE clause.';

-- 1.2 Operating Assets = Total Assets - Cash
CREATE OR REPLACE FUNCTION fn_calc_operating_assets(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  calc_assets NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    f1.ticker,
    f1.fiscal_year,
    (f1.numeric_value - f2.numeric_value) AS calc_assets
  FROM cissa.fundamentals f1
  INNER JOIN cissa.fundamentals f2
    ON f1.ticker = f2.ticker
    AND f1.fiscal_year = f2.fiscal_year
    AND f1.dataset_id = f2.dataset_id
  WHERE
    f1.dataset_id = p_dataset_id
    AND f1.metric_name = 'TOTAL_ASSETS'
    AND f2.metric_name = 'CASH'
    AND f1.numeric_value IS NOT NULL
    AND f2.numeric_value IS NOT NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_operating_assets(UUID) IS
'Calculate Operating Assets from Total Assets and Cash.
Formula: Total Assets - Cash
Output metric name: Calc Assets';

-- 1.3 Operating Assets Detail = Calc Assets - Fixed Assets - Goodwill
-- Note: This depends on fn_calc_operating_assets output being inserted first
CREATE OR REPLACE FUNCTION fn_calc_operating_assets_detail(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  calc_oa NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    mo.ticker,
    mo.fiscal_year,
    (mo.output_metric_value - f1.numeric_value - f2.numeric_value) AS calc_oa
  FROM cissa.metrics_outputs mo
  INNER JOIN cissa.fundamentals f1
    ON mo.ticker = f1.ticker
    AND mo.fiscal_year = f1.fiscal_year
    AND mo.dataset_id = f1.dataset_id
  INNER JOIN cissa.fundamentals f2
    ON mo.ticker = f2.ticker
    AND mo.fiscal_year = f2.fiscal_year
    AND mo.dataset_id = f2.dataset_id
  WHERE
    mo.dataset_id = p_dataset_id
    AND mo.output_metric_name = 'Calc Assets'
    AND f1.metric_name = 'FIXED_ASSETS'
    AND f2.metric_name = 'GOODWILL'
    AND mo.output_metric_value IS NOT NULL
    AND f1.numeric_value IS NOT NULL
    AND f2.numeric_value IS NOT NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_operating_assets_detail(UUID) IS
'Calculate Operating Assets Detail from Calc Assets, Fixed Assets, and Goodwill.
Formula: Calc Assets - Fixed Assets - Goodwill
Output metric name: Calc OA
DEPENDENCY: Requires fn_calc_operating_assets() to have been executed first.';

-- ============================================================================
-- GROUP 2: COST STRUCTURE METRICS
-- ============================================================================

-- 2.1 Operating Cost = Revenue - Operating Income
CREATE OR REPLACE FUNCTION fn_calc_operating_cost(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  calc_op_cost NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    f1.ticker,
    f1.fiscal_year,
    (f1.numeric_value - f2.numeric_value) AS calc_op_cost
  FROM cissa.fundamentals f1
  INNER JOIN cissa.fundamentals f2
    ON f1.ticker = f2.ticker
    AND f1.fiscal_year = f2.fiscal_year
    AND f1.dataset_id = f2.dataset_id
  WHERE
    f1.dataset_id = p_dataset_id
    AND f1.metric_name = 'REVENUE'
    AND f2.metric_name = 'OPERATING_INCOME'
    AND f1.numeric_value IS NOT NULL
    AND f2.numeric_value IS NOT NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_operating_cost(UUID) IS
'Calculate Operating Cost from Revenue and Operating Income.
Formula: Revenue - Operating Income
Output metric name: Calc Op Cost';

-- 2.2 Non-Operating Cost = Operating Income - PBT
CREATE OR REPLACE FUNCTION fn_calc_non_operating_cost(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  calc_non_op_cost NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    f1.ticker,
    f1.fiscal_year,
    (f1.numeric_value - f2.numeric_value) AS calc_non_op_cost
  FROM cissa.fundamentals f1
  INNER JOIN cissa.fundamentals f2
    ON f1.ticker = f2.ticker
    AND f1.fiscal_year = f2.fiscal_year
    AND f1.dataset_id = f2.dataset_id
  WHERE
    f1.dataset_id = p_dataset_id
    AND f1.metric_name = 'OPERATING_INCOME'
    AND f2.metric_name = 'PROFIT_BEFORE_TAX'
    AND f1.numeric_value IS NOT NULL
    AND f2.numeric_value IS NOT NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_non_operating_cost(UUID) IS
'Calculate Non-Operating Cost from Operating Income and PBT.
Formula: Operating Income - PBT
Output metric name: Calc Non Op Cost';

-- 2.3 Tax Cost = PBT - PAT (Extraordinary)
CREATE OR REPLACE FUNCTION fn_calc_tax_cost(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  calc_tax_cost NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    f1.ticker,
    f1.fiscal_year,
    (f1.numeric_value - f2.numeric_value) AS calc_tax_cost
  FROM cissa.fundamentals f1
  INNER JOIN cissa.fundamentals f2
    ON f1.ticker = f2.ticker
    AND f1.fiscal_year = f2.fiscal_year
    AND f1.dataset_id = f2.dataset_id
  WHERE
    f1.dataset_id = p_dataset_id
    AND f1.metric_name = 'PROFIT_BEFORE_TAX'
    AND f2.metric_name = 'PROFIT_AFTER_TAX_EX'
    AND f1.numeric_value IS NOT NULL
    AND f2.numeric_value IS NOT NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_tax_cost(UUID) IS
'Calculate Tax Cost from PBT and PAT (Extraordinary).
Formula: PBT - PAT (Extraordinary)
Output metric name: Calc Tax Cost';

-- 2.4 Extraordinary Items Cost = PAT (Extraordinary) - PAT
CREATE OR REPLACE FUNCTION fn_calc_extraordinary_cost(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  calc_xo_cost NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    f1.ticker,
    f1.fiscal_year,
    (f1.numeric_value - f2.numeric_value) AS calc_xo_cost
  FROM cissa.fundamentals f1
  INNER JOIN cissa.fundamentals f2
    ON f1.ticker = f2.ticker
    AND f1.fiscal_year = f2.fiscal_year
    AND f1.dataset_id = f2.dataset_id
  WHERE
    f1.dataset_id = p_dataset_id
    AND f1.metric_name = 'PROFIT_AFTER_TAX_EX'
    AND f2.metric_name = 'PROFIT_AFTER_TAX'
    AND f1.numeric_value IS NOT NULL
    AND f2.numeric_value IS NOT NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_extraordinary_cost(UUID) IS
'Calculate Extraordinary Items Cost from PAT (Extraordinary) and PAT.
Formula: PAT (Extraordinary) - PAT
Output metric name: Calc XO Cost';

-- ============================================================================
-- GROUP 3: RATIO METRICS
-- ============================================================================

-- 3.2 Profit Margin = PAT / Revenue
CREATE OR REPLACE FUNCTION fn_calc_profit_margin(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  profit_margin NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    f1.ticker,
    f1.fiscal_year,
    (f1.numeric_value / f2.numeric_value) AS profit_margin
  FROM cissa.fundamentals f1
  INNER JOIN cissa.fundamentals f2
    ON f1.ticker = f2.ticker
    AND f1.fiscal_year = f2.fiscal_year
    AND f1.dataset_id = f2.dataset_id
  WHERE
    f1.dataset_id = p_dataset_id
    AND f1.metric_name = 'PROFIT_AFTER_TAX'
    AND f2.metric_name = 'REVENUE'
    AND f1.numeric_value IS NOT NULL
    AND f2.numeric_value IS NOT NULL
    AND f2.numeric_value != 0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_profit_margin(UUID) IS
'Calculate Profit Margin from PAT and Revenue.
Formula: PAT / Revenue
Output metric name: Profit Margin
Note: Filters out zero revenue to avoid division errors.';

-- 3.3 Operating Cost Margin = Calc Op Cost / Revenue
CREATE OR REPLACE FUNCTION fn_calc_operating_cost_margin(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  op_cost_margin NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    mo.ticker,
    mo.fiscal_year,
    (mo.output_metric_value / f.numeric_value) AS op_cost_margin
  FROM cissa.metrics_outputs mo
  INNER JOIN cissa.fundamentals f
    ON mo.ticker = f.ticker
    AND mo.fiscal_year = f.fiscal_year
    AND mo.dataset_id = f.dataset_id
  WHERE
    mo.dataset_id = p_dataset_id
    AND mo.output_metric_name = 'Calc Op Cost'
    AND f.metric_name = 'REVENUE'
    AND mo.output_metric_value IS NOT NULL
    AND f.numeric_value IS NOT NULL
    AND f.numeric_value != 0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_operating_cost_margin(UUID) IS
'Calculate Operating Cost Margin from Calc Op Cost and Revenue.
Formula: Calc Op Cost / Revenue
Output metric name: Op Cost Margin %
DEPENDENCY: Requires fn_calc_operating_cost() to have been executed first.';

-- 3.4 Non-Operating Cost Margin = Calc Non Op Cost / Revenue
CREATE OR REPLACE FUNCTION fn_calc_non_operating_cost_margin(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  non_op_cost_margin NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    mo.ticker,
    mo.fiscal_year,
    (mo.output_metric_value / f.numeric_value) AS non_op_cost_margin
  FROM cissa.metrics_outputs mo
  INNER JOIN cissa.fundamentals f
    ON mo.ticker = f.ticker
    AND mo.fiscal_year = f.fiscal_year
    AND mo.dataset_id = f.dataset_id
  WHERE
    mo.dataset_id = p_dataset_id
    AND mo.output_metric_name = 'Calc Non Op Cost'
    AND f.metric_name = 'REVENUE'
    AND mo.output_metric_value IS NOT NULL
    AND f.numeric_value IS NOT NULL
    AND f.numeric_value != 0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_non_operating_cost_margin(UUID) IS
'Calculate Non-Operating Cost Margin from Calc Non Op Cost and Revenue.
Formula: Calc Non Op Cost / Revenue
Output metric name: Non-Op Cost Margin %
DEPENDENCY: Requires fn_calc_non_operating_cost() to have been executed first.';

-- 3.5 Effective Tax Rate = Calc Tax Cost / PBT
CREATE OR REPLACE FUNCTION fn_calc_effective_tax_rate(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  eff_tax_rate NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    mo.ticker,
    mo.fiscal_year,
    (mo.output_metric_value / f.numeric_value) AS eff_tax_rate
  FROM cissa.metrics_outputs mo
  INNER JOIN cissa.fundamentals f
    ON mo.ticker = f.ticker
    AND mo.fiscal_year = f.fiscal_year
    AND mo.dataset_id = f.dataset_id
  WHERE
    mo.dataset_id = p_dataset_id
    AND mo.output_metric_name = 'Calc Tax Cost'
    AND f.metric_name = 'PROFIT_BEFORE_TAX'
    AND mo.output_metric_value IS NOT NULL
    AND f.numeric_value IS NOT NULL
    AND f.numeric_value != 0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_effective_tax_rate(UUID) IS
'Calculate Effective Tax Rate from Calc Tax Cost and PBT.
Formula: Calc Tax Cost / PBT
Output metric name: Eff Tax Rate
DEPENDENCY: Requires fn_calc_tax_cost() to have been executed first.';

-- 3.6 Extraordinary Items Margin = Calc XO Cost / Revenue
CREATE OR REPLACE FUNCTION fn_calc_extraordinary_cost_margin(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  xo_cost_margin NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    mo.ticker,
    mo.fiscal_year,
    (mo.output_metric_value / f.numeric_value) AS xo_cost_margin
  FROM cissa.metrics_outputs mo
  INNER JOIN cissa.fundamentals f
    ON mo.ticker = f.ticker
    AND mo.fiscal_year = f.fiscal_year
    AND mo.dataset_id = f.dataset_id
  WHERE
    mo.dataset_id = p_dataset_id
    AND mo.output_metric_name = 'Calc XO Cost'
    AND f.metric_name = 'REVENUE'
    AND mo.output_metric_value IS NOT NULL
    AND f.numeric_value IS NOT NULL
    AND f.numeric_value != 0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_extraordinary_cost_margin(UUID) IS
'Calculate Extraordinary Items Margin from Calc XO Cost and Revenue.
Formula: Calc XO Cost / Revenue
Output metric name: XO Cost Margin %
DEPENDENCY: Requires fn_calc_extraordinary_cost() to have been executed first.';

-- 3.7 Fixed Asset Intensity = Fixed Assets / Revenue
CREATE OR REPLACE FUNCTION fn_calc_fixed_asset_intensity(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  fa_intensity NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    f1.ticker,
    f1.fiscal_year,
    (f1.numeric_value / f2.numeric_value) AS fa_intensity
  FROM cissa.fundamentals f1
  INNER JOIN cissa.fundamentals f2
    ON f1.ticker = f2.ticker
    AND f1.fiscal_year = f2.fiscal_year
    AND f1.dataset_id = f2.dataset_id
  WHERE
    f1.dataset_id = p_dataset_id
    AND f1.metric_name = 'FIXED_ASSETS'
    AND f2.metric_name = 'REVENUE'
    AND f1.numeric_value IS NOT NULL
    AND f2.numeric_value IS NOT NULL
    AND f2.numeric_value != 0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_fixed_asset_intensity(UUID) IS
'Calculate Fixed Asset Intensity from Fixed Assets and Revenue.
Formula: Fixed Assets / Revenue
Output metric name: FA Intensity';

-- ============================================================================
-- GROUP 4: EQUITY METRICS
-- ============================================================================

-- 4.2 Book Equity = Total Equity - Minority Interest
CREATE OR REPLACE FUNCTION fn_calc_book_equity(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  book_equity NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    f1.ticker,
    f1.fiscal_year,
    (f1.numeric_value - f2.numeric_value) AS book_equity
  FROM cissa.fundamentals f1
  INNER JOIN cissa.fundamentals f2
    ON f1.ticker = f2.ticker
    AND f1.fiscal_year = f2.fiscal_year
    AND f1.dataset_id = f2.dataset_id
  WHERE
    f1.dataset_id = p_dataset_id
    AND f1.metric_name = 'TOTAL_EQUITY'
    AND f2.metric_name = 'MINORITY_INTEREST'
    AND f1.numeric_value IS NOT NULL
    AND f2.numeric_value IS NOT NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_book_equity(UUID) IS
'Calculate Book Equity from Total Equity and Minority Interest.
Formula: Total Equity - Minority Interest
Output metric name: Book Equity
Note: Intermediate metric used in other calculations.';

-- ============================================================================
-- GROUP 5: RETURN ON ASSETS
-- ============================================================================

-- 5.1 Return on Operating Assets (ROA) = PAT / Calc Assets
CREATE OR REPLACE FUNCTION fn_calc_roa(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  roa NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    mo.ticker,
    mo.fiscal_year,
    (f.numeric_value / mo.output_metric_value) AS roa
  FROM cissa.metrics_outputs mo
  INNER JOIN cissa.fundamentals f
    ON mo.ticker = f.ticker
    AND mo.fiscal_year = f.fiscal_year
    AND mo.dataset_id = f.dataset_id
  WHERE
    mo.dataset_id = p_dataset_id
    AND mo.output_metric_name = 'Calc Assets'
    AND f.metric_name = 'PROFIT_AFTER_TAX'
    AND mo.output_metric_value IS NOT NULL
    AND f.numeric_value IS NOT NULL
    AND mo.output_metric_value != 0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_roa(UUID) IS
'Calculate Return on Operating Assets from PAT and Calc Assets.
Formula: PAT / Calc Assets
Output metric name: ROA
DEPENDENCY: Requires fn_calc_operating_assets() to have been executed first.';

-- ============================================================================
-- END OF FUNCTIONS
-- ============================================================================
