# ============================================================================
# SQL Query Builder for Ratio Metrics
# ============================================================================
from typing import List, Optional, Dict, Any
from uuid import UUID
from ..models.ratio_metrics import MetricDefinition
from ..core.config import get_logger

logger = get_logger(__name__)


class RatioMetricsCalculator:
    """Builds SQL queries for ratio metric calculations"""
    
    def __init__(self, metric_def: MetricDefinition, temporal_window: str = "1Y"):
        self.metric_def = metric_def
        self.temporal_window = temporal_window
        self.rows_between = self._calculate_rows_between(temporal_window)
    
    @staticmethod
    def _calculate_rows_between(temporal_window: str) -> str:
        """Convert temporal window to SQL ROWS BETWEEN clause"""
        mapping = {
            "1Y": "ROWS BETWEEN 0 PRECEDING AND CURRENT ROW",
            "3Y": "ROWS BETWEEN 2 PRECEDING AND CURRENT ROW",
            "5Y": "ROWS BETWEEN 4 PRECEDING AND CURRENT ROW",
            "10Y": "ROWS BETWEEN 9 PRECEDING AND CURRENT ROW"
        }
        if temporal_window not in mapping:
            raise ValueError(f"Invalid temporal window: {temporal_window}. Must be one of: 1Y, 3Y, 5Y, 10Y")
        return mapping[temporal_window]
    
    def build_query(
        self,
        tickers: List[str],
        dataset_id: UUID,
        param_set_id: UUID,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build parameterized SQL query for ratio metric.
        
        Returns:
            (sql_query, params) tuple
        """
        if self.metric_def.formula_type == "ratio":
            return self._build_simple_ratio_query(tickers, dataset_id, param_set_id, start_year, end_year)
        elif self.metric_def.formula_type == "complex_ratio":
            return self._build_complex_ratio_query(tickers, dataset_id, param_set_id, start_year, end_year)
        else:
            raise ValueError(f"Unknown formula type: {self.metric_def.formula_type}")
    
    def _build_simple_ratio_query(
        self,
        tickers: List[str],
        dataset_id: UUID,
        param_set_id: UUID,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build query for simple ratio (numerator / denominator).
        
        Example: MB Ratio = Calc MC / Calc EE
        """
        numerator_metric = self.metric_def.numerator["metric_name"]
        denominator_metric = self.metric_def.denominator["metric_name"]
        
        # Build ticker list for IN clause
        ticker_placeholders = ", ".join([f":ticker_{i}" for i in range(len(tickers))])
        ticker_params = {f"ticker_{i}": t for i, t in enumerate(tickers)}
        
        # Build year filter
        year_filter = ""
        if start_year is not None:
            year_filter += f" AND m.fiscal_year >= :start_year"
            ticker_params["start_year"] = start_year
        if end_year is not None:
            year_filter += f" AND m.fiscal_year <= :end_year"
            ticker_params["end_year"] = end_year
        
        sql = f"""
        WITH numerator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(output_metric_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS numerator_value
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
                AND param_set_id = :param_set_id
                AND output_metric_name = :numerator_metric
                AND ticker IN ({ticker_placeholders})
        ),
        denominator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(output_metric_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS denominator_value
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
                AND param_set_id = :param_set_id
                AND output_metric_name = :denominator_metric
                AND ticker IN ({ticker_placeholders})
        )
        SELECT
            m.ticker,
            m.fiscal_year,
            CASE
                WHEN d.denominator_value IS NULL THEN NULL
                WHEN d.denominator_value = 0 THEN NULL
                WHEN m.numerator_value IS NULL THEN NULL
                ELSE m.numerator_value / d.denominator_value
            END AS ratio_value
        FROM numerator_rolling m
        FULL OUTER JOIN denominator_rolling d 
            ON m.ticker = d.ticker AND m.fiscal_year = d.fiscal_year
        WHERE m.ticker IS NOT NULL {year_filter}
        ORDER BY m.ticker, m.fiscal_year;
        """
        
        params = {
            "dataset_id": str(dataset_id),
            "param_set_id": str(param_set_id),
            "numerator_metric": numerator_metric,
            "denominator_metric": denominator_metric,
            **ticker_params
        }
        
        return sql, params
    
    def _build_complex_ratio_query(
        self,
        tickers: List[str],
        dataset_id: UUID,
        param_set_id: UUID,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build query for complex ratio with multiple components in numerator/denominator.
        
        Example: Effective Tax Rate = Tax Cost / |PAT + XO Cost|
        """
        # This will be implemented for more complex ratios
        # For now, raise NotImplementedError
        raise NotImplementedError("Complex ratio queries not yet implemented")
