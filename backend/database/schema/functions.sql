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

-- ============================================================================
-- PHASE 2: TEMPORAL METRIC CALCULATION FUNCTIONS
-- PostgreSQL Stored Functions for Temporal Metrics with Window Functions
-- ============================================================================
-- These functions calculate temporal L1 metrics that require LAG window functions
-- and inception year logic (fiscal_year > companies.begin_year).
-- ============================================================================

-- ============================================================================
-- GROUP 1: LAG_MC (Helper - Previous Year Market Cap)
-- ============================================================================

-- Helper: Calculate LAG(Market Cap) using window function
-- This is not stored as a metric in metrics_outputs, but used internally
CREATE OR REPLACE FUNCTION fn_calc_lag_mc(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  lag_mc NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  WITH market_caps AS (
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
      AND f2.numeric_value IS NOT NULL
  )
  SELECT
    ticker,
    fiscal_year,
    LAG(calc_mc, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year) AS lag_mc
  FROM market_caps
  ORDER BY ticker, fiscal_year;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_lag_mc(UUID) IS
'Calculate LAG(Market Cap) using window function.
Formula: LAG(C_MC, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year)
Output: (ticker, fiscal_year, lag_mc)
Note: Returns NULL for first fiscal year per ticker (no prior year).
This is a helper function; results not directly stored in metrics_outputs.
Used internally by ECF, FY_TSR, and other temporal metrics.';

-- ============================================================================
-- GROUP 2: ECF (Economic Cash Flow) - Temporal Metric
-- ============================================================================

CREATE OR REPLACE FUNCTION fn_calc_ecf(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  ecf NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  WITH market_caps AS (
    SELECT
      f1.ticker,
      f1.fiscal_year,
      f1.dataset_id,
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
      AND f2.numeric_value IS NOT NULL
  ),
  lag_mc_calc AS (
    SELECT
      ticker,
      fiscal_year,
      dataset_id,
      calc_mc,
      LAG(calc_mc, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year) AS lag_mc
    FROM market_caps
  )
  SELECT
    lmc.ticker,
    lmc.fiscal_year,
    CASE
      WHEN c.begin_year IS NULL THEN NULL
      WHEN lmc.fiscal_year > c.begin_year AND lmc.lag_mc IS NOT NULL AND lmc.lag_mc > 0 THEN
        lmc.lag_mc * (1 + f_tsr.numeric_value / 100.0) - lmc.calc_mc
      ELSE NULL
    END AS ecf
  FROM lag_mc_calc lmc
  INNER JOIN cissa.companies c ON lmc.ticker = c.ticker
  LEFT JOIN cissa.fundamentals f_tsr
    ON lmc.ticker = f_tsr.ticker
    AND lmc.fiscal_year = f_tsr.fiscal_year
    AND lmc.dataset_id = f_tsr.dataset_id
    AND f_tsr.metric_name = 'FY_TSR'
  ORDER BY lmc.ticker, lmc.fiscal_year;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_ecf(UUID) IS
'Calculate Economic Cash Flow (ECF) using window function and inception logic.
Formula: IF (fiscal_year > companies.begin_year) THEN ECF = LAG_MC × (1 + fytsr/100) - C_MC ELSE NULL
Output metric name: Calc ECF

Key features:
  - Uses LAG window function to access previous year''s market cap
  - Only calculates when fiscal_year > companies.begin_year (inception logic)
  - Returns NULL for inception year (no LAG_MC available)
  - fytsr is INPUT data from Bloomberg fundamentals (not calculated)
  - Handles division by 100 for percentage conversion

Window Function Pattern:
  LAG(C_MC, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year)
  Returns NULL for first year per ticker.

Year Gap Gotcha:
  LAG is ROW-BASED, not YEAR-BASED. If fiscal years have gaps (e.g., 2015, 2016, 2017, 2020),
  LAG(2020) will return 2017''s value, not 2019''s. This causes ECF for 2020 to calculate
  3-year return as 1-year. See GAP_DETECTION.md for mitigation strategy.

Edge Cases:
  - If LAG_MC IS NULL: ECF = NULL (first year per ticker)
  - If LAG_MC = 0: ECF = NULL (handled by LAG_MC > 0 check)
  - If fytsr IS NULL: ECF = NULL (fundamentals join returns NULL)
  - If begin_year IS NULL: ECF = NULL (conservative handling)';

-- ============================================================================
-- GROUP 3: NON_DIV_ECF (Economic Cash Flow + Dividends) - Temporal Metric
-- ============================================================================

CREATE OR REPLACE FUNCTION fn_calc_non_div_ecf(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  non_div_ecf NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    mo.ticker,
    mo.fiscal_year,
    (mo.output_metric_value + COALESCE(f.numeric_value, 0)) AS non_div_ecf
  FROM cissa.metrics_outputs mo
  LEFT JOIN cissa.fundamentals f
    ON mo.ticker = f.ticker
    AND mo.fiscal_year = f.fiscal_year
    AND mo.dataset_id = f.dataset_id
    AND f.metric_name = 'DIVIDENDS'
  WHERE
    mo.dataset_id = p_dataset_id
    AND mo.output_metric_name = 'Calc ECF'
  ORDER BY mo.ticker, mo.fiscal_year;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_non_div_ecf(UUID) IS
'Calculate Non-Dividend Economic Cash Flow (ECF + Dividends).
Formula: NON_DIV_ECF = ECF + DIVIDENDS
Output metric name: Calc Non Div ECF

Key features:
  - Depends on ECF metric being calculated and inserted first
  - Adds dividend payments to ECF
  - Inherits NULL behavior from ECF
  - Uses LEFT JOIN to handle missing dividend data (treats as 0)

Interpretation:
  NON_DIV_ECF includes full dividend payments in economic cash flow calculation;
  reflects complete shareholder returns including distributions.

Dependencies:
  - Requires fn_calc_ecf() to have been executed and results inserted into metrics_outputs';

-- ============================================================================
-- GROUP 4: EE (Economic Equity) - Temporal Cumulative Metric
-- ============================================================================

CREATE OR REPLACE FUNCTION fn_calc_economic_equity(p_dataset_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  ee NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  WITH ee_component AS (
    SELECT
      f_te.ticker,
      f_te.fiscal_year,
      f_te.dataset_id,
      CASE
        WHEN c.begin_year IS NULL THEN NULL
        WHEN f_te.fiscal_year <= c.begin_year THEN 
          (f_te.numeric_value - COALESCE(f_mi.numeric_value, 0))
        ELSE
          (COALESCE(f_pat.numeric_value, 0) - COALESCE(mo_ecf.output_metric_value, 0))
      END AS ee_comp
    FROM cissa.fundamentals f_te
    INNER JOIN cissa.companies c ON f_te.ticker = c.ticker
    LEFT JOIN cissa.fundamentals f_mi
      ON f_te.ticker = f_mi.ticker
      AND f_te.fiscal_year = f_mi.fiscal_year
      AND f_te.dataset_id = f_mi.dataset_id
      AND f_mi.metric_name = 'MINORITY_INTEREST'
    LEFT JOIN cissa.fundamentals f_pat
      ON f_te.ticker = f_pat.ticker
      AND f_te.fiscal_year = f_pat.fiscal_year
      AND f_te.dataset_id = f_pat.dataset_id
      AND f_pat.metric_name = 'PROFIT_AFTER_TAX'
    LEFT JOIN cissa.metrics_outputs mo_ecf
      ON f_te.ticker = mo_ecf.ticker
      AND f_te.fiscal_year = mo_ecf.fiscal_year
      AND f_te.dataset_id = mo_ecf.dataset_id
      AND mo_ecf.output_metric_name = 'Calc ECF'
    WHERE
      f_te.dataset_id = p_dataset_id
      AND f_te.metric_name = 'TOTAL_EQUITY'
  )
  SELECT
    ticker,
    fiscal_year,
    SUM(ee_comp) OVER (PARTITION BY ticker ORDER BY fiscal_year) AS ee_cumsum
  FROM ee_component
  WHERE ee_comp IS NOT NULL
  ORDER BY ticker, fiscal_year;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_economic_equity(UUID) IS
'Calculate Economic Equity (EE) with cumulative sum and inception logic.
Formula (component): IF fiscal_year <= begin_year THEN EE = TOTAL_EQUITY - MINORITY_INTEREST
                      ELSE IF fiscal_year > begin_year THEN EE = PROFIT_AFTER_TAX - ECF
Formula (cumulative): EE_cumulative = SUM(EE_component) OVER (PARTITION BY ticker ORDER BY fiscal_year)
Output metric name: Calc EE

Key features:
  - Two-stage calculation: component-level, then cumulative sum
  - Inception year logic: Uses equity method for inception year, change method for post-inception
  - Cumulative sum resets per ticker (PARTITION BY ticker only, not dataset_id)
  - Uses NUMERIC(18,2) to maintain precision over 60+ years
  - Filters NULL components to ensure valid cumsum

Window Function Pattern:
  SUM(...) OVER (PARTITION BY ticker ORDER BY fiscal_year)
  Accumulates values from first row to current row within each ticker''s history.

Interpretation:
  EE tracks cumulative economic equity over company''s history.
  Starting point: book equity (year 0), then accumulates annual changes (profit - ECF).

Edge Cases:
  - If begin_year IS NULL: Returns NULL (handled in component calculation)
  - If MINORITY_INTEREST IS NULL: Treated as 0 in equity method
  - If ECF IS NULL: Returns NULL (post-inception years without ECF)
  - NUMERIC precision maintained despite 60+ year accumulation

Dependencies:
  - Requires fn_calc_ecf() to have been executed and results inserted into metrics_outputs
  - Requires companies.begin_year NOT NULL (add NOT NULL constraint in Task 3)';

-- ============================================================================
-- GROUP 5: FY_TSR (Total Shareholder Return) - Parameter-Sensitive Temporal Metric
-- ============================================================================

CREATE OR REPLACE FUNCTION fn_calc_fy_tsr(p_dataset_id UUID, p_param_set_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  fy_tsr NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  WITH market_caps AS (
    SELECT
      f1.ticker,
      f1.fiscal_year,
      f1.dataset_id,
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
      AND f2.numeric_value IS NOT NULL
  ),
  lag_mc_calc AS (
    SELECT
      ticker,
      fiscal_year,
      dataset_id,
      calc_mc,
      LAG(calc_mc, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year) AS lag_mc
    FROM market_caps
  ),
  with_params AS (
    SELECT
      lmc.ticker,
      lmc.fiscal_year,
      lmc.lag_mc,
      lmc.calc_mc,
      c.begin_year,
      mo_ecf.output_metric_value AS ecf_val,
      f_div.numeric_value AS dividend_val,
      CASE 
        WHEN ps.param_overrides ? 'include_franking_credits_tsr' THEN
          (ps.param_overrides ->> 'include_franking_credits_tsr')::BOOLEAN
        ELSE
          (p.default_value::BOOLEAN) 
      END AS incl_franking,
      CASE 
        WHEN ps.param_overrides ? 'tax_rate_franking_credits' THEN
          (ps.param_overrides ->> 'tax_rate_franking_credits')::NUMERIC / 100.0
        ELSE
          (p.default_value::NUMERIC / 100.0)
      END AS frank_tax_rate,
      CASE 
        WHEN ps.param_overrides ? 'value_of_franking_credits' THEN
          (ps.param_overrides ->> 'value_of_franking_credits')::NUMERIC / 100.0
        ELSE
          (p.default_value::NUMERIC / 100.0)
      END AS value_franking_cr
    FROM lag_mc_calc lmc
    INNER JOIN cissa.companies c ON lmc.ticker = c.ticker
    INNER JOIN cissa.parameter_sets ps ON ps.param_set_id = p_param_set_id
    LEFT JOIN cissa.parameters p ON p.parameter_name = 'tax_rate_franking_credits'
    LEFT JOIN cissa.metrics_outputs mo_ecf
      ON lmc.ticker = mo_ecf.ticker
      AND lmc.fiscal_year = mo_ecf.fiscal_year
      AND lmc.dataset_id = mo_ecf.dataset_id
      AND mo_ecf.output_metric_name = 'Calc ECF'
      AND mo_ecf.param_set_id = p_param_set_id
    LEFT JOIN cissa.fundamentals f_div
      ON lmc.ticker = f_div.ticker
      AND lmc.fiscal_year = f_div.fiscal_year
      AND lmc.dataset_id = f_div.dataset_id
      AND f_div.metric_name = 'DIVIDENDS'
  )
  SELECT
    ticker,
    fiscal_year,
    CASE
      WHEN begin_year IS NULL THEN NULL
      WHEN lag_mc IS NULL OR lag_mc <= 0 THEN NULL
      WHEN fiscal_year <= begin_year THEN NULL
      WHEN incl_franking = TRUE THEN
        ((calc_mc - lag_mc + COALESCE(ecf_val, 0) - 
          COALESCE(dividend_val, 0) / (1 - frank_tax_rate)) * 
         frank_tax_rate * value_franking_cr) / lag_mc
      ELSE
        (calc_mc - lag_mc + COALESCE(ecf_val, 0)) / lag_mc
    END AS fy_tsr
  FROM with_params
  ORDER BY ticker, fiscal_year;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_fy_tsr(UUID, UUID) IS
'Calculate Fiscal Year Total Shareholder Return (FY_TSR) with parameter-sensitive franking.
Formula: IF LAG_MC > 0 AND fiscal_year > begin_year THEN
           IF incl_franking = "Yes" THEN
             adjusted_change = (C_MC - LAG_MC + ECF - dividend/(1 - frank_tax_rate)) × frank_tax_rate × value_franking_cr
             FY_TSR = adjusted_change / LAG_MC
           ELSE
             change_in_cap = C_MC - LAG_MC + ECF
             FY_TSR = change_in_cap / LAG_MC
         ELSE NULL
Output metric name: Calc FY TSR

Parameters:
  - p_dataset_id: Dataset UUID for metric calculation
  - p_param_set_id: Parameter set UUID (determines franking parameters)

Key features:
  - Parameter-sensitive: Same (ticker, fiscal_year) produces different FY_TSR per param_set_id
  - Requires LAG_MC > 0 (division guard)
  - Only calculates for fiscal_year > begin_year (inception logic)
  - Converts franking parameters from database percentages to decimals
  - Handles missing ECF and DIVIDENDS data gracefully

Parameter Resolution:
  For each franking parameter:
    1. Check param_overrides JSONB in parameter_sets row
    2. If key exists: use override value
    3. If key missing: use parameter.default_value
  
  Parameters (from database):
    - include_franking_credits_tsr: BOOLEAN (default: false)
    - tax_rate_franking_credits: NUMERIC % (default: 30.0 = 30%)
    - value_of_franking_credits: NUMERIC % (default: 75.0 = 75%)

Window Function Pattern:
  LAG(C_MC, 1) OVER (PARTITION BY ticker ORDER BY fiscal_year)

Interpretation:
  FY_TSR = total shareholder return (capital appreciation + economic cash flow) / prior year market cap
  Franking adjustment inflates returns when franking credits are valued.

Edge Cases:
  - LAG_MC NULL or <= 0: Returns NULL (first year, zero prior value)
  - ECF NULL: Uses 0 (added to sum)
  - DIVIDENDS NULL: Uses 0 (added to sum)
  - (1 - frank_tax_rate) = 0: Potential division error (mitigated by parameter constraints)

Dependencies:
  - Requires fn_calc_ecf() to have been executed
  - Requires parameter_sets table configured with franking parameters
  - parameter_set_id must exist in parameter_sets table';

-- ============================================================================
-- GROUP 6: FY_TSR_PREL (Preliminary TSR) - Parameter-Sensitive Temporal Metric
-- ============================================================================

CREATE OR REPLACE FUNCTION fn_calc_fy_tsr_prel(p_dataset_id UUID, p_param_set_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  fy_tsr_prel NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    mo.ticker,
    mo.fiscal_year,
    (mo.output_metric_value + 1) AS fy_tsr_prel
  FROM cissa.metrics_outputs mo
  WHERE
    mo.dataset_id = p_dataset_id
    AND mo.param_set_id = p_param_set_id
    AND mo.output_metric_name = 'Calc FY TSR'
  ORDER BY mo.ticker, mo.fiscal_year;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION fn_calc_fy_tsr_prel(UUID, UUID) IS
'Calculate Preliminary Fiscal Year TSR (FY_TSR + 1).
Formula: FY_TSR_PREL = FY_TSR + 1 (when FY_TSR is not NULL)
Output metric name: Calc FY TSR Prel

Key features:
  - Simple arithmetic: adds 1 to FY_TSR
  - Converts from return format (0.05 = 5% return) to growth factor format (1.05 = value grows to 105%)
  - Inherits NULL behavior from FY_TSR
  - Parameter-sensitive: Different results per param_set_id

Dependencies:
  - Requires fn_calc_fy_tsr() to have been executed and results inserted into metrics_outputs
  - Requires param_set_id to match the FY_TSR calculation param_set_id';

-- ============================================================================
-- END OF TEMPORAL METRIC FUNCTIONS
-- ============================================================================
