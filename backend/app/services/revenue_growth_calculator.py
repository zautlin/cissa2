# ============================================================================
# Calculator for Revenue Growth Metrics
# ============================================================================
import logging
from typing import List, Optional
from uuid import UUID

from ..models.ratio_metrics import MetricDefinition

logger = logging.getLogger(__name__)


class RevenueGrowthCalculator:
    """Builds SQL queries for revenue growth calculations with rolling averages and year-shift logic"""
    
    def __init__(self, metric_def: MetricDefinition, temporal_window: str):
        """
        Initialize the calculator.
        
        Args:
            metric_def: MetricDefinition for revenue_growth
            temporal_window: "1Y", "3Y", "5Y", or "10Y"
        """
        self.metric_def = metric_def
        self.temporal_window = temporal_window
        self.rows_between = self._calculate_rows_between(temporal_window)
        logger.info(f"RevenueGrowthCalculator initialized with window={temporal_window}, rows_between={self.rows_between}")
    
    def build_query(
        self,
        tickers: List[str],
        dataset_id: UUID,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> tuple[str, dict]:
        """
        Build parameterized SQL query for revenue growth.
        
        Args:
            tickers: List of ticker symbols
            dataset_id: Dataset UUID
            start_year: Optional start year filter
            end_year: Optional end year filter
        
        Returns:
            Tuple of (sql_query, params_dict)
        """
        # Build the base SQL query with CTEs
        sql_query = """
        WITH revenue_data AS (
          SELECT
            ticker,
            fiscal_year,
            numeric_value AS revenue
          FROM cissa.fundamentals
          WHERE dataset_id = :dataset_id
            AND metric_name = :metric_name
            AND ticker = ANY(:tickers)
        ),
        revenue_rolling AS (
          SELECT
            ticker,
            fiscal_year,
            AVG(revenue) OVER (
              PARTITION BY ticker 
              ORDER BY fiscal_year 
              ROWS BETWEEN :rows_between PRECEDING AND CURRENT ROW
            ) AS revenue_rolling_avg
          FROM revenue_data
        ),
        revenue_with_lag AS (
          SELECT
            ticker,
            fiscal_year,
            revenue_rolling_avg,
            LAG(revenue_rolling_avg) OVER (
              PARTITION BY ticker 
              ORDER BY fiscal_year
            ) AS prior_year_avg_revenue
          FROM revenue_rolling
        )
        SELECT
          ticker,
          fiscal_year,
          CASE
            WHEN prior_year_avg_revenue IS NULL THEN NULL
            WHEN ABS(prior_year_avg_revenue) = 0 THEN NULL
            ELSE (revenue_rolling_avg - prior_year_avg_revenue) / ABS(prior_year_avg_revenue)
          END AS revenue_growth
        FROM revenue_with_lag
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
            "metric_name": self.metric_def.metric_name or "REVENUE",
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
