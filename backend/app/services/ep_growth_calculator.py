# ============================================================================
# Calculator for EP Growth Metrics
# ============================================================================
import logging
from typing import List, Optional
from uuid import UUID

from ..models.ratio_metrics import MetricDefinition

logger = logging.getLogger(__name__)


class EPGrowthCalculator:
    """Builds SQL queries for EP growth calculations with rolling averages and year-shift logic"""
    
    def __init__(self, metric_def: MetricDefinition, temporal_window: str):
        """
        Initialize the calculator.
        
        Args:
            metric_def: MetricDefinition for ep_growth
            temporal_window: "1Y", "3Y", "5Y", or "10Y"
        """
        self.metric_def = metric_def
        self.temporal_window = temporal_window
        self.rows_between = self._calculate_rows_between(temporal_window)
        logger.info(f"EPGrowthCalculator initialized with window={temporal_window}, rows_between={self.rows_between}")
    
    def build_query(
        self,
        tickers: List[str],
        dataset_id: UUID,
        param_set_id: UUID,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> tuple[str, dict]:
        """
        Build parameterized SQL query for EP growth.
        
        Formula: EP Growth = Calc EP / ABS(Open EE)
        Where:
        - Calc EP is current year Economic Profitability
        - Open EE is prior year's Economic Equity (via LAG from Calc EE)
        
        Args:
            tickers: List of ticker symbols
            dataset_id: Dataset UUID
            param_set_id: Parameter set UUID
            start_year: Optional start year filter
            end_year: Optional end year filter
        
        Returns:
            Tuple of (sql_query, params_dict)
        """
        # Build the base SQL query with CTEs
        sql_query = """
         WITH ep_data AS (
           SELECT
             ticker,
             fiscal_year,
             output_metric_value AS ep
           FROM cissa.metrics_outputs
           WHERE dataset_id = :dataset_id
             AND param_set_id = :param_set_id
             AND output_metric_name = :ep_metric_name
             AND ticker = ANY(:tickers)
         ),
        ee_data AS (
          SELECT
            ticker,
            fiscal_year,
            output_metric_value AS ee
          FROM cissa.metrics_outputs
          WHERE dataset_id = :dataset_id
            AND param_set_id = :param_set_id
            AND output_metric_name = :ee_metric_name
            AND ticker = ANY(:tickers)
        ),
        ep_rolling AS (
          SELECT
            ticker,
            fiscal_year,
            AVG(ep) OVER (
              PARTITION BY ticker 
              ORDER BY fiscal_year 
              ROWS BETWEEN :rows_between PRECEDING AND CURRENT ROW
            ) AS ep_rolling_avg
          FROM ep_data
        ),
         ee_with_lag AS (
           SELECT
             ticker,
             fiscal_year,
             LAG(ee) OVER (
               PARTITION BY ticker 
               ORDER BY fiscal_year
             ) AS prior_year_ee
           FROM ee_data
         ),
        ee_rolling_lag AS (
           SELECT
             ticker,
             fiscal_year,
             AVG(prior_year_ee) OVER (
               PARTITION BY ticker 
               ORDER BY fiscal_year 
               ROWS BETWEEN :rows_between PRECEDING AND CURRENT ROW
             ) AS prior_year_avg_ee
           FROM ee_with_lag
         ),
         ep_with_prior_ee AS (
           SELECT
             ep.ticker,
             ep.fiscal_year,
             ep.ep_rolling_avg,
             ee.prior_year_avg_ee
           FROM ep_rolling ep
           LEFT JOIN ee_rolling_lag ee 
             ON ep.ticker = ee.ticker 
             AND ep.fiscal_year = ee.fiscal_year
         )
         SELECT
           ticker,
           fiscal_year,
           CASE
             WHEN prior_year_avg_ee IS NULL THEN NULL
             WHEN ABS(prior_year_avg_ee) = 0 THEN NULL
             ELSE ep_rolling_avg / ABS(prior_year_avg_ee)
           END AS ep_growth
         FROM ep_with_prior_ee
        """
        
        # Add year filtering if provided
        where_conditions = []
        if start_year is not None:
            where_conditions.append("fiscal_year >= :start_year")
        if end_year is not None:
            where_conditions.append("fiscal_year <= :end_year")
        
        if where_conditions:
            sql_query += "\n        WHERE " + " AND ".join(where_conditions)
        
        sql_query += "\n        ORDER BY ticker, fiscal_year;"
        
        # Prepare parameters dictionary
        params = {
            "dataset_id": str(dataset_id),
            "param_set_id": str(param_set_id),
            "ep_metric_name": "Calc EP",
            "ee_metric_name": "Calc EE",
            "tickers": tickers,
            "rows_between": int(self.rows_between)  # Convert to int for SQL
        }
        
        if start_year is not None:
            params["start_year"] = start_year
        if end_year is not None:
            params["end_year"] = end_year
        
        logger.debug(f"Built query for {len(tickers)} tickers with window={self.temporal_window}")
        return sql_query, params
    
    def _calculate_rows_between(self, temporal_window: str) -> str:
        """
        Convert temporal window to SQL ROWS BETWEEN clause.
        
        Args:
            temporal_window: "1Y", "3Y", "5Y", or "10Y"
        
        Returns:
            Number of preceding rows (as string)
        """
        mapping = {
            "1Y": "0",   # Current year only (no rolling average)
            "3Y": "2",   # 3-year rolling average (current + 2 prior)
            "5Y": "4",   # 5-year rolling average (current + 4 prior)
            "10Y": "9"   # 10-year rolling average (current + 9 prior)
        }
        
        result = mapping.get(temporal_window, "0")
        logger.debug(f"Mapped temporal_window={temporal_window} to rows_between={result}")
        return result
