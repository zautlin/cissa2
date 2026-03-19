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
DROP FUNCTION IF EXISTS cissa.fn_calc_economic_equity(UUID, UUID) CASCADE;
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
     CASE
       WHEN mo.output_metric_value IS NULL THEN 0
       ELSE (mo.output_metric_value + COALESCE(f.numeric_value, 0))
     END AS non_div_ecf
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

CREATE OR REPLACE FUNCTION cissa.fn_calc_economic_equity(p_dataset_id UUID, p_param_set_id UUID)
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
      AND mo_ecf.param_set_id = p_param_set_id
      AND mo_ecf.output_metric_name = 'Calc ECF'
    WHERE
      f_te.dataset_id = p_dataset_id
      AND f_te.metric_name = 'TOTAL_EQUITY'
  )
  SELECT
    eec.ticker,
    eec.fiscal_year,
    CASE
      WHEN eec.fiscal_year < eec.begin_year THEN NULL
      WHEN eec.ee_comp IS NULL THEN NULL
      ELSE SUM(eec.ee_comp) OVER (PARTITION BY eec.ticker ORDER BY eec.fiscal_year ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
    END AS ee_cumsum
  FROM ee_component eec
  ORDER BY eec.ticker, eec.fiscal_year;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION cissa.fn_calc_economic_equity(UUID, UUID) IS
'Calculate Economic Equity (EE) cumulative sum with inception year logic.
Returns all 11,000 records (500 companies × 22 years) for consistent schema.
For inception year (fiscal_year = begin_year): EE = TOTAL_EQUITY - MINORITY_INTEREST
For post-inception years (fiscal_year > begin_year): EE = PAT - ECF (then cumsum, IGNORE NULLS)
For pre-inception years (fiscal_year < begin_year): Returns NULL
NULL values in any component return NULL for that year.
Cumulative sum is calculated per ticker in fiscal_year order, skipping NULLs.
Parameter-sensitive: uses param_set_id to match ECF values from metrics_outputs.
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

-- ============================================================================
-- GROUP 7: 3Y_FV_ECF (3-Year Forward Value ECF) - Parameter-Sensitive Temporal Metric
-- ============================================================================

CREATE OR REPLACE FUNCTION cissa.fn_calc_3y_fv_ecf(p_dataset_id UUID, p_param_set_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  fv_ecf_3y NUMERIC
) AS $$
DECLARE
  v_dataset_id UUID := p_dataset_id;
  v_param_set_id UUID := p_param_set_id;
BEGIN
  RETURN QUERY
  WITH param_config AS (
    SELECT
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
    FROM cissa.parameter_sets ps
    LEFT JOIN cissa.parameters p1 ON p1.parameter_name = 'include_franking_credits_tsr'
    LEFT JOIN cissa.parameters p2 ON p2.parameter_name = 'tax_rate_franking_credits'
    LEFT JOIN cissa.parameters p3 ON p3.parameter_name = 'value_of_franking_credits'
    WHERE ps.param_set_id = v_param_set_id
  ),
  company_years AS (
    SELECT DISTINCT
      c.ticker,
      c.begin_year,
      fy.fiscal_year
    FROM cissa.companies c
    CROSS JOIN (
      SELECT DISTINCT fiscal_year FROM cissa.metrics_outputs 
      WHERE dataset_id = v_dataset_id
    ) fy
  ),
  year_data AS (
    SELECT
      cy.ticker,
      cy.begin_year,
      cy.fiscal_year,
      -- Get Non Div ECF for years Y-2, Y-1, Y
      MAX(CASE WHEN mo1.fiscal_year = cy.fiscal_year - 2 THEN mo1.output_metric_value END) AS non_div_ecf_y_minus_2,
      MAX(CASE WHEN mo2.fiscal_year = cy.fiscal_year - 1 THEN mo2.output_metric_value END) AS non_div_ecf_y_minus_1,
      MAX(CASE WHEN mo3.fiscal_year = cy.fiscal_year THEN mo3.output_metric_value END) AS non_div_ecf_y,
      -- Get DIVIDENDS for years Y-2, Y-1, Y
      MAX(CASE WHEN f1.fiscal_year = cy.fiscal_year - 2 THEN f1.numeric_value END) AS div_y_minus_2,
      MAX(CASE WHEN f2.fiscal_year = cy.fiscal_year - 1 THEN f2.numeric_value END) AS div_y_minus_1,
      MAX(CASE WHEN f3.fiscal_year = cy.fiscal_year THEN f3.numeric_value END) AS div_y,
      -- Get FRANKING for years Y-2, Y-1, Y
      MAX(CASE WHEN fk1.fiscal_year = cy.fiscal_year - 2 THEN fk1.numeric_value END) AS franking_y_minus_2,
      MAX(CASE WHEN fk2.fiscal_year = cy.fiscal_year - 1 THEN fk2.numeric_value END) AS franking_y_minus_1,
      MAX(CASE WHEN fk3.fiscal_year = cy.fiscal_year THEN fk3.numeric_value END) AS franking_y,
      -- Get Calc KE for year Y-1 (Calc Open KE for year Y)
      MAX(CASE WHEN mo_ke.fiscal_year = cy.fiscal_year - 1 THEN mo_ke.output_metric_value END) AS calc_ke_y_minus_1
    FROM company_years cy
    LEFT JOIN cissa.metrics_outputs mo1 ON cy.ticker = mo1.ticker AND mo1.dataset_id = v_dataset_id AND mo1.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo2 ON cy.ticker = mo2.ticker AND mo2.dataset_id = v_dataset_id AND mo2.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo3 ON cy.ticker = mo3.ticker AND mo3.dataset_id = v_dataset_id AND mo3.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.fundamentals f1 ON cy.ticker = f1.ticker AND f1.dataset_id = v_dataset_id AND f1.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f2 ON cy.ticker = f2.ticker AND f2.dataset_id = v_dataset_id AND f2.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f3 ON cy.ticker = f3.ticker AND f3.dataset_id = v_dataset_id AND f3.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals fk1 ON cy.ticker = fk1.ticker AND fk1.dataset_id = v_dataset_id AND fk1.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk2 ON cy.ticker = fk2.ticker AND fk2.dataset_id = v_dataset_id AND fk2.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk3 ON cy.ticker = fk3.ticker AND fk3.dataset_id = v_dataset_id AND fk3.metric_name = 'FRANKING'
    LEFT JOIN cissa.metrics_outputs mo_ke ON cy.ticker = mo_ke.ticker AND mo_ke.dataset_id = v_dataset_id AND mo_ke.output_metric_name = 'Calc KE'
    GROUP BY cy.ticker, cy.begin_year, cy.fiscal_year
  )
  SELECT
    yd.ticker,
    yd.fiscal_year,
    CASE
      -- Years before begin_year: NULL
      WHEN yd.fiscal_year < yd.begin_year THEN NULL
      -- Years begin_year through begin_year+2: NULL
      WHEN yd.fiscal_year <= yd.begin_year + 2 THEN NULL
      -- Years begin_year+3 onwards: Apply discounting formula
      WHEN yd.fiscal_year > yd.begin_year + 2 AND yd.calc_ke_y_minus_1 IS NOT NULL THEN
        CASE
          WHEN (SELECT pc.incl_franking FROM param_config pc LIMIT 1) = TRUE THEN
            (COALESCE(yd.div_y_minus_2, 0) + COALESCE(yd.div_y_minus_2, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_2, 0) + COALESCE(yd.non_div_ecf_y_minus_2, 0)) * POWER(1 + yd.calc_ke_y_minus_1, 2) +
            (COALESCE(yd.div_y_minus_1, 0) + COALESCE(yd.div_y_minus_1, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_1, 0) + COALESCE(yd.non_div_ecf_y_minus_1, 0)) * POWER(1 + yd.calc_ke_y_minus_1, 1) +
            (COALESCE(yd.div_y, 0) + COALESCE(yd.div_y, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y, 0) + COALESCE(yd.non_div_ecf_y, 0)) * POWER(1 + yd.calc_ke_y_minus_1, 0)
          ELSE
            (COALESCE(yd.div_y_minus_2, 0) + COALESCE(yd.non_div_ecf_y_minus_2, 0)) * POWER(1 + yd.calc_ke_y_minus_1, 2) +
            (COALESCE(yd.div_y_minus_1, 0) + COALESCE(yd.non_div_ecf_y_minus_1, 0)) * POWER(1 + yd.calc_ke_y_minus_1, 1) +
            (COALESCE(yd.div_y, 0) + COALESCE(yd.non_div_ecf_y, 0)) * POWER(1 + yd.calc_ke_y_minus_1, 0)
        END
      ELSE NULL
    END AS fv_ecf_3y
  FROM year_data yd
  ORDER BY yd.ticker, yd.fiscal_year;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION cissa.fn_calc_3y_fv_ecf(UUID, UUID) IS
'Calculate 3-Year Forward Value ECF with discounting and franking adjustment.
For fiscal_year < begin_year+3: Returns NULL
For fiscal_year >= begin_year+3: Applies 3-year discounting formula with exponential decay
Uses Calc KE from prior year as discount rate (Calc Open KE)
Handles franking credit adjustments based on parameters. REQ-A7.';

-- ============================================================================
-- GROUP 8: 5Y_FV_ECF (5-Year Forward Value ECF) - Parameter-Sensitive Temporal Metric
-- ============================================================================

CREATE OR REPLACE FUNCTION cissa.fn_calc_5y_fv_ecf(p_dataset_id UUID, p_param_set_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  fv_ecf_5y NUMERIC
) AS $$
  WITH param_config AS (
    SELECT
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
    FROM cissa.parameter_sets ps
    LEFT JOIN cissa.parameters p1 ON p1.parameter_name = 'include_franking_credits_tsr'
    LEFT JOIN cissa.parameters p2 ON p2.parameter_name = 'tax_rate_franking_credits'
    LEFT JOIN cissa.parameters p3 ON p3.parameter_name = 'value_of_franking_credits'
    WHERE ps.param_set_id = p_param_set_id
  ),
  company_years AS (
    SELECT DISTINCT
      c.ticker,
      c.begin_year,
      fy.fiscal_year
    FROM cissa.companies c
    CROSS JOIN (
      SELECT DISTINCT fiscal_year FROM cissa.metrics_outputs 
      WHERE dataset_id = p_dataset_id
    ) fy
  ),
  year_data AS (
    SELECT
      cy.ticker,
      cy.begin_year,
      cy.fiscal_year,
      MAX(CASE WHEN mo1.fiscal_year = cy.fiscal_year - 4 THEN mo1.output_metric_value END) AS non_div_ecf_y_minus_4,
      MAX(CASE WHEN mo2.fiscal_year = cy.fiscal_year - 3 THEN mo2.output_metric_value END) AS non_div_ecf_y_minus_3,
      MAX(CASE WHEN mo3.fiscal_year = cy.fiscal_year - 2 THEN mo3.output_metric_value END) AS non_div_ecf_y_minus_2,
      MAX(CASE WHEN mo4.fiscal_year = cy.fiscal_year - 1 THEN mo4.output_metric_value END) AS non_div_ecf_y_minus_1,
      MAX(CASE WHEN mo5.fiscal_year = cy.fiscal_year THEN mo5.output_metric_value END) AS non_div_ecf_y,
      MAX(CASE WHEN f1.fiscal_year = cy.fiscal_year - 4 THEN f1.numeric_value END) AS div_y_minus_4,
      MAX(CASE WHEN f2.fiscal_year = cy.fiscal_year - 3 THEN f2.numeric_value END) AS div_y_minus_3,
      MAX(CASE WHEN f3.fiscal_year = cy.fiscal_year - 2 THEN f3.numeric_value END) AS div_y_minus_2,
      MAX(CASE WHEN f4.fiscal_year = cy.fiscal_year - 1 THEN f4.numeric_value END) AS div_y_minus_1,
      MAX(CASE WHEN f5.fiscal_year = cy.fiscal_year THEN f5.numeric_value END) AS div_y,
      MAX(CASE WHEN fk1.fiscal_year = cy.fiscal_year - 4 THEN fk1.numeric_value END) AS franking_y_minus_4,
      MAX(CASE WHEN fk2.fiscal_year = cy.fiscal_year - 3 THEN fk2.numeric_value END) AS franking_y_minus_3,
      MAX(CASE WHEN fk3.fiscal_year = cy.fiscal_year - 2 THEN fk3.numeric_value END) AS franking_y_minus_2,
      MAX(CASE WHEN fk4.fiscal_year = cy.fiscal_year - 1 THEN fk4.numeric_value END) AS franking_y_minus_1,
      MAX(CASE WHEN fk5.fiscal_year = cy.fiscal_year THEN fk5.numeric_value END) AS franking_y,
      MAX(CASE WHEN mo_ke.fiscal_year = cy.fiscal_year - 5 THEN mo_ke.output_metric_value END) AS calc_ke_y_minus_5
    FROM company_years cy
    LEFT JOIN cissa.metrics_outputs mo1 ON cy.ticker = mo1.ticker AND mo1.dataset_id = p_dataset_id AND mo1.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo2 ON cy.ticker = mo2.ticker AND mo2.dataset_id = p_dataset_id AND mo2.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo3 ON cy.ticker = mo3.ticker AND mo3.dataset_id = p_dataset_id AND mo3.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo4 ON cy.ticker = mo4.ticker AND mo4.dataset_id = p_dataset_id AND mo4.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo5 ON cy.ticker = mo5.ticker AND mo5.dataset_id = p_dataset_id AND mo5.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.fundamentals f1 ON cy.ticker = f1.ticker AND f1.dataset_id = p_dataset_id AND f1.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f2 ON cy.ticker = f2.ticker AND f2.dataset_id = p_dataset_id AND f2.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f3 ON cy.ticker = f3.ticker AND f3.dataset_id = p_dataset_id AND f3.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f4 ON cy.ticker = f4.ticker AND f4.dataset_id = p_dataset_id AND f4.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f5 ON cy.ticker = f5.ticker AND f5.dataset_id = p_dataset_id AND f5.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals fk1 ON cy.ticker = fk1.ticker AND fk1.dataset_id = p_dataset_id AND fk1.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk2 ON cy.ticker = fk2.ticker AND fk2.dataset_id = p_dataset_id AND fk2.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk3 ON cy.ticker = fk3.ticker AND fk3.dataset_id = p_dataset_id AND fk3.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk4 ON cy.ticker = fk4.ticker AND fk4.dataset_id = p_dataset_id AND fk4.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk5 ON cy.ticker = fk5.ticker AND fk5.dataset_id = p_dataset_id AND fk5.metric_name = 'FRANKING'
    LEFT JOIN cissa.metrics_outputs mo_ke ON cy.ticker = mo_ke.ticker AND mo_ke.dataset_id = p_dataset_id AND mo_ke.output_metric_name = 'Calc KE'
    GROUP BY cy.ticker, cy.begin_year, cy.fiscal_year
  )
  SELECT
    yd.ticker,
    yd.fiscal_year,
    CASE
      WHEN yd.fiscal_year < yd.begin_year THEN NULL
      WHEN yd.fiscal_year <= yd.begin_year + 4 THEN NULL
      WHEN yd.fiscal_year > yd.begin_year + 4 AND yd.calc_ke_y_minus_5 IS NOT NULL THEN
        CASE
          WHEN (SELECT pc.incl_franking FROM param_config pc LIMIT 1) = TRUE THEN
            (-COALESCE(yd.div_y_minus_4, 0) - COALESCE(yd.div_y_minus_4, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_4, 0) + COALESCE(yd.non_div_ecf_y_minus_4, 0)) * POWER(1 + yd.calc_ke_y_minus_5, 4) +
            (-COALESCE(yd.div_y_minus_3, 0) - COALESCE(yd.div_y_minus_3, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_3, 0) + COALESCE(yd.non_div_ecf_y_minus_3, 0)) * POWER(1 + yd.calc_ke_y_minus_5, 3) +
            (-COALESCE(yd.div_y_minus_2, 0) - COALESCE(yd.div_y_minus_2, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_2, 0) + COALESCE(yd.non_div_ecf_y_minus_2, 0)) * POWER(1 + yd.calc_ke_y_minus_5, 2) +
            (-COALESCE(yd.div_y_minus_1, 0) - COALESCE(yd.div_y_minus_1, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_1, 0) + COALESCE(yd.non_div_ecf_y_minus_1, 0)) * POWER(1 + yd.calc_ke_y_minus_5, 1) +
            (-COALESCE(yd.div_y, 0) - COALESCE(yd.div_y, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y, 0) + COALESCE(yd.non_div_ecf_y, 0)) * POWER(1 + yd.calc_ke_y_minus_5, 0)
          ELSE
            (-COALESCE(yd.div_y_minus_4, 0) + COALESCE(yd.non_div_ecf_y_minus_4, 0)) * POWER(1 + yd.calc_ke_y_minus_5, 4) +
            (-COALESCE(yd.div_y_minus_3, 0) + COALESCE(yd.non_div_ecf_y_minus_3, 0)) * POWER(1 + yd.calc_ke_y_minus_5, 3) +
            (-COALESCE(yd.div_y_minus_2, 0) + COALESCE(yd.non_div_ecf_y_minus_2, 0)) * POWER(1 + yd.calc_ke_y_minus_5, 2) +
            (-COALESCE(yd.div_y_minus_1, 0) + COALESCE(yd.non_div_ecf_y_minus_1, 0)) * POWER(1 + yd.calc_ke_y_minus_5, 1) +
            (-COALESCE(yd.div_y, 0) + COALESCE(yd.non_div_ecf_y, 0)) * POWER(1 + yd.calc_ke_y_minus_5, 0)
        END
      ELSE NULL
    END AS fv_ecf_5y
  FROM year_data yd
  ORDER BY yd.ticker, yd.fiscal_year;
$$ LANGUAGE SQL IMMUTABLE;

COMMENT ON FUNCTION cissa.fn_calc_5y_fv_ecf(UUID, UUID) IS
'Calculate 5-Year Forward Value ECF with discounting and franking adjustment.
For fiscal_year <= begin_year+4: Returns NULL
For fiscal_year > begin_year+4: Applies 5-year discounting formula with KE[Y-5] and exponents 4,3,2,1,0
Uses negative dividends: -DIV[Y-N] + NonDivECF[Y-N]
Handles franking credit adjustments based on parameters.';

-- ============================================================================
-- GROUP 9: 10Y_FV_ECF (10-Year Forward Value ECF) - Parameter-Sensitive Temporal Metric
-- ============================================================================

CREATE OR REPLACE FUNCTION cissa.fn_calc_10y_fv_ecf(p_dataset_id UUID, p_param_set_id UUID)
RETURNS TABLE (
  ticker TEXT,
  fiscal_year INTEGER,
  fv_ecf_10y NUMERIC
) AS $$
  WITH param_config AS (
    SELECT
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
    FROM cissa.parameter_sets ps
    LEFT JOIN cissa.parameters p1 ON p1.parameter_name = 'include_franking_credits_tsr'
    LEFT JOIN cissa.parameters p2 ON p2.parameter_name = 'tax_rate_franking_credits'
    LEFT JOIN cissa.parameters p3 ON p3.parameter_name = 'value_of_franking_credits'
    WHERE ps.param_set_id = p_param_set_id
  ),
  company_years AS (
    SELECT DISTINCT
      c.ticker,
      c.begin_year,
      fy.fiscal_year
    FROM cissa.companies c
    CROSS JOIN (
      SELECT DISTINCT fiscal_year FROM cissa.metrics_outputs 
      WHERE dataset_id = p_dataset_id
    ) fy
  ),
  year_data AS (
    SELECT
      cy.ticker,
      cy.begin_year,
      cy.fiscal_year,
      MAX(CASE WHEN mo1.fiscal_year = cy.fiscal_year - 9 THEN mo1.output_metric_value END) AS non_div_ecf_y_minus_9,
      MAX(CASE WHEN mo2.fiscal_year = cy.fiscal_year - 8 THEN mo2.output_metric_value END) AS non_div_ecf_y_minus_8,
      MAX(CASE WHEN mo3.fiscal_year = cy.fiscal_year - 7 THEN mo3.output_metric_value END) AS non_div_ecf_y_minus_7,
      MAX(CASE WHEN mo4.fiscal_year = cy.fiscal_year - 6 THEN mo4.output_metric_value END) AS non_div_ecf_y_minus_6,
      MAX(CASE WHEN mo5.fiscal_year = cy.fiscal_year - 5 THEN mo5.output_metric_value END) AS non_div_ecf_y_minus_5,
      MAX(CASE WHEN mo6.fiscal_year = cy.fiscal_year - 4 THEN mo6.output_metric_value END) AS non_div_ecf_y_minus_4,
      MAX(CASE WHEN mo7.fiscal_year = cy.fiscal_year - 3 THEN mo7.output_metric_value END) AS non_div_ecf_y_minus_3,
      MAX(CASE WHEN mo8.fiscal_year = cy.fiscal_year - 2 THEN mo8.output_metric_value END) AS non_div_ecf_y_minus_2,
      MAX(CASE WHEN mo9.fiscal_year = cy.fiscal_year - 1 THEN mo9.output_metric_value END) AS non_div_ecf_y_minus_1,
      MAX(CASE WHEN mo10.fiscal_year = cy.fiscal_year THEN mo10.output_metric_value END) AS non_div_ecf_y,
      MAX(CASE WHEN f1.fiscal_year = cy.fiscal_year - 9 THEN f1.numeric_value END) AS div_y_minus_9,
      MAX(CASE WHEN f2.fiscal_year = cy.fiscal_year - 8 THEN f2.numeric_value END) AS div_y_minus_8,
      MAX(CASE WHEN f3.fiscal_year = cy.fiscal_year - 7 THEN f3.numeric_value END) AS div_y_minus_7,
      MAX(CASE WHEN f4.fiscal_year = cy.fiscal_year - 6 THEN f4.numeric_value END) AS div_y_minus_6,
      MAX(CASE WHEN f5.fiscal_year = cy.fiscal_year - 5 THEN f5.numeric_value END) AS div_y_minus_5,
      MAX(CASE WHEN f6.fiscal_year = cy.fiscal_year - 4 THEN f6.numeric_value END) AS div_y_minus_4,
      MAX(CASE WHEN f7.fiscal_year = cy.fiscal_year - 3 THEN f7.numeric_value END) AS div_y_minus_3,
      MAX(CASE WHEN f8.fiscal_year = cy.fiscal_year - 2 THEN f8.numeric_value END) AS div_y_minus_2,
      MAX(CASE WHEN f9.fiscal_year = cy.fiscal_year - 1 THEN f9.numeric_value END) AS div_y_minus_1,
      MAX(CASE WHEN f10.fiscal_year = cy.fiscal_year THEN f10.numeric_value END) AS div_y,
      MAX(CASE WHEN fk1.fiscal_year = cy.fiscal_year - 9 THEN fk1.numeric_value END) AS franking_y_minus_9,
      MAX(CASE WHEN fk2.fiscal_year = cy.fiscal_year - 8 THEN fk2.numeric_value END) AS franking_y_minus_8,
      MAX(CASE WHEN fk3.fiscal_year = cy.fiscal_year - 7 THEN fk3.numeric_value END) AS franking_y_minus_7,
      MAX(CASE WHEN fk4.fiscal_year = cy.fiscal_year - 6 THEN fk4.numeric_value END) AS franking_y_minus_6,
      MAX(CASE WHEN fk5.fiscal_year = cy.fiscal_year - 5 THEN fk5.numeric_value END) AS franking_y_minus_5,
      MAX(CASE WHEN fk6.fiscal_year = cy.fiscal_year - 4 THEN fk6.numeric_value END) AS franking_y_minus_4,
      MAX(CASE WHEN fk7.fiscal_year = cy.fiscal_year - 3 THEN fk7.numeric_value END) AS franking_y_minus_3,
      MAX(CASE WHEN fk8.fiscal_year = cy.fiscal_year - 2 THEN fk8.numeric_value END) AS franking_y_minus_2,
      MAX(CASE WHEN fk9.fiscal_year = cy.fiscal_year - 1 THEN fk9.numeric_value END) AS franking_y_minus_1,
      MAX(CASE WHEN fk10.fiscal_year = cy.fiscal_year THEN fk10.numeric_value END) AS franking_y,
      MAX(CASE WHEN mo_ke.fiscal_year = cy.fiscal_year - 10 THEN mo_ke.output_metric_value END) AS calc_ke_y_minus_10
    FROM company_years cy
    LEFT JOIN cissa.metrics_outputs mo1 ON cy.ticker = mo1.ticker AND mo1.dataset_id = p_dataset_id AND mo1.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo2 ON cy.ticker = mo2.ticker AND mo2.dataset_id = p_dataset_id AND mo2.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo3 ON cy.ticker = mo3.ticker AND mo3.dataset_id = p_dataset_id AND mo3.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo4 ON cy.ticker = mo4.ticker AND mo4.dataset_id = p_dataset_id AND mo4.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo5 ON cy.ticker = mo5.ticker AND mo5.dataset_id = p_dataset_id AND mo5.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo6 ON cy.ticker = mo6.ticker AND mo6.dataset_id = p_dataset_id AND mo6.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo7 ON cy.ticker = mo7.ticker AND mo7.dataset_id = p_dataset_id AND mo7.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo8 ON cy.ticker = mo8.ticker AND mo8.dataset_id = p_dataset_id AND mo8.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo9 ON cy.ticker = mo9.ticker AND mo9.dataset_id = p_dataset_id AND mo9.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.metrics_outputs mo10 ON cy.ticker = mo10.ticker AND mo10.dataset_id = p_dataset_id AND mo10.output_metric_name = 'Non Div ECF'
    LEFT JOIN cissa.fundamentals f1 ON cy.ticker = f1.ticker AND f1.dataset_id = p_dataset_id AND f1.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f2 ON cy.ticker = f2.ticker AND f2.dataset_id = p_dataset_id AND f2.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f3 ON cy.ticker = f3.ticker AND f3.dataset_id = p_dataset_id AND f3.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f4 ON cy.ticker = f4.ticker AND f4.dataset_id = p_dataset_id AND f4.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f5 ON cy.ticker = f5.ticker AND f5.dataset_id = p_dataset_id AND f5.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f6 ON cy.ticker = f6.ticker AND f6.dataset_id = p_dataset_id AND f6.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f7 ON cy.ticker = f7.ticker AND f7.dataset_id = p_dataset_id AND f7.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f8 ON cy.ticker = f8.ticker AND f8.dataset_id = p_dataset_id AND f8.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f9 ON cy.ticker = f9.ticker AND f9.dataset_id = p_dataset_id AND f9.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals f10 ON cy.ticker = f10.ticker AND f10.dataset_id = p_dataset_id AND f10.metric_name = 'DIVIDENDS'
    LEFT JOIN cissa.fundamentals fk1 ON cy.ticker = fk1.ticker AND fk1.dataset_id = p_dataset_id AND fk1.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk2 ON cy.ticker = fk2.ticker AND fk2.dataset_id = p_dataset_id AND fk2.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk3 ON cy.ticker = fk3.ticker AND fk3.dataset_id = p_dataset_id AND fk3.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk4 ON cy.ticker = fk4.ticker AND fk4.dataset_id = p_dataset_id AND fk4.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk5 ON cy.ticker = fk5.ticker AND fk5.dataset_id = p_dataset_id AND fk5.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk6 ON cy.ticker = fk6.ticker AND fk6.dataset_id = p_dataset_id AND fk6.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk7 ON cy.ticker = fk7.ticker AND fk7.dataset_id = p_dataset_id AND fk7.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk8 ON cy.ticker = fk8.ticker AND fk8.dataset_id = p_dataset_id AND fk8.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk9 ON cy.ticker = fk9.ticker AND fk9.dataset_id = p_dataset_id AND fk9.metric_name = 'FRANKING'
    LEFT JOIN cissa.fundamentals fk10 ON cy.ticker = fk10.ticker AND fk10.dataset_id = p_dataset_id AND fk10.metric_name = 'FRANKING'
    LEFT JOIN cissa.metrics_outputs mo_ke ON cy.ticker = mo_ke.ticker AND mo_ke.dataset_id = p_dataset_id AND mo_ke.output_metric_name = 'Calc KE'
    GROUP BY cy.ticker, cy.begin_year, cy.fiscal_year
  )
  SELECT
    yd.ticker,
    yd.fiscal_year,
    CASE
      WHEN yd.fiscal_year < yd.begin_year THEN NULL
      WHEN yd.fiscal_year <= yd.begin_year + 9 THEN NULL
      WHEN yd.fiscal_year > yd.begin_year + 9 AND yd.calc_ke_y_minus_10 IS NOT NULL THEN
        CASE
          WHEN (SELECT pc.incl_franking FROM param_config pc LIMIT 1) = TRUE THEN
            (-COALESCE(yd.div_y_minus_9, 0) - COALESCE(yd.div_y_minus_9, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_9, 0) + COALESCE(yd.non_div_ecf_y_minus_9, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 9) +
            (-COALESCE(yd.div_y_minus_8, 0) - COALESCE(yd.div_y_minus_8, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_8, 0) + COALESCE(yd.non_div_ecf_y_minus_8, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 8) +
            (-COALESCE(yd.div_y_minus_7, 0) - COALESCE(yd.div_y_minus_7, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_7, 0) + COALESCE(yd.non_div_ecf_y_minus_7, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 7) +
            (-COALESCE(yd.div_y_minus_6, 0) - COALESCE(yd.div_y_minus_6, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_6, 0) + COALESCE(yd.non_div_ecf_y_minus_6, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 6) +
            (-COALESCE(yd.div_y_minus_5, 0) - COALESCE(yd.div_y_minus_5, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_5, 0) + COALESCE(yd.non_div_ecf_y_minus_5, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 5) +
            (-COALESCE(yd.div_y_minus_4, 0) - COALESCE(yd.div_y_minus_4, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_4, 0) + COALESCE(yd.non_div_ecf_y_minus_4, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 4) +
            (-COALESCE(yd.div_y_minus_3, 0) - COALESCE(yd.div_y_minus_3, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_3, 0) + COALESCE(yd.non_div_ecf_y_minus_3, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 3) +
            (-COALESCE(yd.div_y_minus_2, 0) - COALESCE(yd.div_y_minus_2, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_2, 0) + COALESCE(yd.non_div_ecf_y_minus_2, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 2) +
            (-COALESCE(yd.div_y_minus_1, 0) - COALESCE(yd.div_y_minus_1, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y_minus_1, 0) + COALESCE(yd.non_div_ecf_y_minus_1, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 1) +
            (-COALESCE(yd.div_y, 0) - COALESCE(yd.div_y, 0) / (1 - (SELECT frank_tax_rate FROM param_config LIMIT 1)) * (SELECT frank_tax_rate FROM param_config LIMIT 1) * (SELECT value_franking_cr FROM param_config LIMIT 1) * COALESCE(yd.franking_y, 0) + COALESCE(yd.non_div_ecf_y, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 0)
          ELSE
            (-COALESCE(yd.div_y_minus_9, 0) + COALESCE(yd.non_div_ecf_y_minus_9, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 9) +
            (-COALESCE(yd.div_y_minus_8, 0) + COALESCE(yd.non_div_ecf_y_minus_8, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 8) +
            (-COALESCE(yd.div_y_minus_7, 0) + COALESCE(yd.non_div_ecf_y_minus_7, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 7) +
            (-COALESCE(yd.div_y_minus_6, 0) + COALESCE(yd.non_div_ecf_y_minus_6, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 6) +
            (-COALESCE(yd.div_y_minus_5, 0) + COALESCE(yd.non_div_ecf_y_minus_5, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 5) +
            (-COALESCE(yd.div_y_minus_4, 0) + COALESCE(yd.non_div_ecf_y_minus_4, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 4) +
            (-COALESCE(yd.div_y_minus_3, 0) + COALESCE(yd.non_div_ecf_y_minus_3, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 3) +
            (-COALESCE(yd.div_y_minus_2, 0) + COALESCE(yd.non_div_ecf_y_minus_2, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 2) +
            (-COALESCE(yd.div_y_minus_1, 0) + COALESCE(yd.non_div_ecf_y_minus_1, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 1) +
            (-COALESCE(yd.div_y, 0) + COALESCE(yd.non_div_ecf_y, 0)) * POWER(1 + yd.calc_ke_y_minus_10, 0)
        END
      ELSE NULL
    END AS fv_ecf_10y
  FROM year_data yd
  ORDER BY yd.ticker, yd.fiscal_year;
$$ LANGUAGE SQL IMMUTABLE;

COMMENT ON FUNCTION cissa.fn_calc_10y_fv_ecf(UUID, UUID) IS
'Calculate 10-Year Forward Value ECF with discounting and franking adjustment.
For fiscal_year <= begin_year+9: Returns NULL
For fiscal_year > begin_year+9: Applies 10-year discounting formula with KE[Y-10] and exponents 9,8,7,6,5,4,3,2,1,0
Uses negative dividends: -DIV[Y-N] + NonDivECF[Y-N]
Handles franking credit adjustments based on parameters.';

