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
-- GROUP 3: EQUITY METRICS
-- ============================================================================

-- 3.1 Book Equity = Total Equity - Minority Interest
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
-- GROUP 4: RETURN ON ASSETS
-- ============================================================================

-- 4.1 Return on Operating Assets (ROA) = PAT / Calc Assets
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
SET search_path TO cissa;

-- Drop old functions if they exist
DROP FUNCTION IF EXISTS cissa.fn_calc_lag_mc(UUID) CASCADE;
DROP FUNCTION IF EXISTS cissa.fn_calc_ecf(UUID) CASCADE;
DROP FUNCTION IF EXISTS cissa.fn_calc_non_div_ecf(UUID) CASCADE;
DROP FUNCTION IF EXISTS cissa.fn_calc_economic_equity(UUID) CASCADE;
DROP FUNCTION IF EXISTS cissa.fn_calc_fy_tsr(UUID, UUID) CASCADE;
DROP FUNCTION IF EXISTS cissa.fn_calc_fy_tsr_prel(UUID, UUID) CASCADE;

-- ============================================================================
-- GROUP 1: LAG_MC (Helper - Previous Year Market Cap)
-- ============================================================================

CREATE OR REPLACE FUNCTION cissa.fn_calc_lag_mc(p_dataset_id UUID)
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
    mc.ticker,
    mc.fiscal_year,
    LAG(mc.calc_mc, 1) OVER (PARTITION BY mc.ticker ORDER BY mc.fiscal_year) AS lag_mc
  FROM market_caps mc
  ORDER BY mc.ticker, mc.fiscal_year;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION cissa.fn_calc_lag_mc(UUID) IS
'Calculate LAG(Market Cap) using window function. REQ-A1.';

-- ============================================================================
-- GROUP 2: ECF (Economic Cash Flow) - Temporal Metric
-- ============================================================================

CREATE OR REPLACE FUNCTION cissa.fn_calc_ecf(p_dataset_id UUID)
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
      mc.ticker,
      mc.fiscal_year,
      mc.dataset_id,
      mc.calc_mc,
      LAG(mc.calc_mc, 1) OVER (PARTITION BY mc.ticker ORDER BY mc.fiscal_year) AS lag_mc
    FROM market_caps mc
  )
  SELECT
    lmc.ticker,
    lmc.fiscal_year,
    CASE
      WHEN c.begin_year IS NULL THEN NULL
      WHEN lmc.fiscal_year > c.begin_year AND lmc.lag_mc IS NOT NULL AND lmc.lag_mc > 0 THEN
        lmc.lag_mc * (1 + COALESCE(f_tsr.numeric_value, 0) / 100.0) - lmc.calc_mc
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

COMMENT ON FUNCTION cissa.fn_calc_ecf(UUID) IS
'Calculate Economic Cash Flow (ECF) with window function. REQ-A2.';

-- ============================================================================
-- GROUP 3: NON_DIV_ECF (Economic Cash Flow + Dividends) - Temporal Metric
-- ============================================================================

CREATE OR REPLACE FUNCTION cissa.fn_calc_non_div_ecf(p_dataset_id UUID)
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
    (COALESCE(mo.output_metric_value, 0) + COALESCE(f.numeric_value, 0)) AS non_div_ecf
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

COMMENT ON FUNCTION cissa.fn_calc_non_div_ecf(UUID) IS
'Calculate Non-Dividend ECF (ECF + Dividends). REQ-A3.';

-- ============================================================================
-- GROUP 4: EE (Economic Equity) - Temporal Cumulative Metric
-- ============================================================================

CREATE OR REPLACE FUNCTION cissa.fn_calc_economic_equity(p_dataset_id UUID)
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
      c.begin_year,
      CASE
        WHEN c.begin_year IS NULL THEN NULL
        WHEN f_te.fiscal_year = c.begin_year THEN 
          (f_te.numeric_value - f_mi.numeric_value)
        WHEN f_te.fiscal_year > c.begin_year THEN
          (f_pat.numeric_value - mo_ecf.output_metric_value)
        ELSE NULL
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
    eec.ticker,
    eec.fiscal_year,
    SUM(eec.ee_comp) OVER (PARTITION BY eec.ticker ORDER BY eec.fiscal_year) AS ee_cumsum
  FROM ee_component eec
  WHERE eec.ee_comp IS NOT NULL
    AND eec.fiscal_year >= eec.begin_year
  ORDER BY eec.ticker, eec.fiscal_year;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION cissa.fn_calc_economic_equity(UUID) IS
'Calculate Economic Equity (EE) cumulative sum with inception year logic.
For inception year (fiscal_year = begin_year): EE = TOTAL_EQUITY - MINORITY_INTEREST
For post-inception years (fiscal_year > begin_year): EE = PAT - ECF (then cumsum)
For pre-inception years: Returns NULL (invalid data).
NULL values in any component return NULL for that year (no COALESCE).
Cumulative sum is calculated per ticker in fiscal_year order.
REQ-A4.';

-- ============================================================================
-- GROUP 5: FY_TSR (Total Shareholder Return) - Parameter-Sensitive Temporal Metric
-- ============================================================================

CREATE OR REPLACE FUNCTION cissa.fn_calc_fy_tsr(p_dataset_id UUID, p_param_set_id UUID)
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
      mc.ticker,
      mc.fiscal_year,
      mc.dataset_id,
      mc.calc_mc,
      LAG(mc.calc_mc, 1) OVER (PARTITION BY mc.ticker ORDER BY mc.fiscal_year) AS lag_mc
    FROM market_caps mc
  ),
  with_params AS (
    SELECT
      lmc.ticker,
      lmc.fiscal_year,
      lmc.lag_mc,
      lmc.calc_mc,
      c.begin_year,
      COALESCE(mo_ecf.output_metric_value, 0) AS ecf_val,
      COALESCE(f_div.numeric_value, 0) AS dividend_val,
      CASE 
        WHEN ps.param_overrides ? 'include_franking_credits_tsr' THEN
          (ps.param_overrides ->> 'include_franking_credits_tsr')::BOOLEAN
        ELSE
          (p1.default_value::BOOLEAN) 
      END AS incl_franking,
      CASE 
        WHEN ps.param_overrides ? 'tax_rate_franking_credits' THEN
          (ps.param_overrides ->> 'tax_rate_franking_credits')::NUMERIC / 100.0
        ELSE
          (p2.default_value::NUMERIC / 100.0)
      END AS frank_tax_rate,
      CASE 
        WHEN ps.param_overrides ? 'value_of_franking_credits' THEN
          (ps.param_overrides ->> 'value_of_franking_credits')::NUMERIC / 100.0
        ELSE
          (p3.default_value::NUMERIC / 100.0)
      END AS value_franking_cr
    FROM lag_mc_calc lmc
    INNER JOIN cissa.companies c ON lmc.ticker = c.ticker
    INNER JOIN cissa.parameter_sets ps ON ps.param_set_id = p_param_set_id
    LEFT JOIN cissa.parameters p1 ON p1.parameter_name = 'include_franking_credits_tsr'
    LEFT JOIN cissa.parameters p2 ON p2.parameter_name = 'tax_rate_franking_credits'
    LEFT JOIN cissa.parameters p3 ON p3.parameter_name = 'value_of_franking_credits'
     LEFT JOIN cissa.metrics_outputs mo_ecf
        ON lmc.ticker = mo_ecf.ticker
        AND lmc.fiscal_year = mo_ecf.fiscal_year
        AND lmc.dataset_id = mo_ecf.dataset_id
        AND mo_ecf.output_metric_name = 'Calc ECF'
     LEFT JOIN cissa.fundamentals f_div
      ON lmc.ticker = f_div.ticker
      AND lmc.fiscal_year = f_div.fiscal_year
      AND lmc.dataset_id = f_div.dataset_id
      AND f_div.metric_name = 'DIVIDENDS'
  )
  SELECT
    wp.ticker,
    wp.fiscal_year,
    CASE
      WHEN wp.begin_year IS NULL THEN NULL
      WHEN wp.lag_mc IS NULL OR wp.lag_mc <= 0 THEN NULL
      WHEN wp.fiscal_year <= wp.begin_year THEN NULL
      WHEN wp.incl_franking = TRUE THEN
        ((wp.calc_mc - wp.lag_mc + wp.ecf_val - 
          wp.dividend_val / (1 - wp.frank_tax_rate)) * 
         wp.frank_tax_rate * wp.value_franking_cr) / wp.lag_mc
      ELSE
        (wp.calc_mc - wp.lag_mc + wp.ecf_val) / wp.lag_mc
    END AS fy_tsr
  FROM with_params wp
  ORDER BY wp.ticker, wp.fiscal_year;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION cissa.fn_calc_fy_tsr(UUID, UUID) IS
'Calculate FY_TSR with parameter franking. REQ-A5.';

-- ============================================================================
-- GROUP 6: FY_TSR_PREL (Preliminary TSR) - Parameter-Sensitive Temporal Metric
-- ============================================================================

CREATE OR REPLACE FUNCTION cissa.fn_calc_fy_tsr_prel(p_dataset_id UUID, p_param_set_id UUID)
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
    (COALESCE(mo.output_metric_value, 0) + 1) AS fy_tsr_prel
   FROM cissa.metrics_outputs mo
    WHERE
      mo.dataset_id = p_dataset_id
      AND mo.param_set_id = p_param_set_id
      AND mo.output_metric_name = 'Calc FY TSR'
    ORDER BY mo.ticker, mo.fiscal_year;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION cissa.fn_calc_fy_tsr_prel(UUID, UUID) IS
'Calculate FY_TSR + 1 (growth factor form). REQ-A6.';

