# ============================================================================
# SQL Query Builder for Ratio Metrics
# ============================================================================
from typing import List, Optional, Dict, Any
from uuid import UUID
from ..models.ratio_metrics import MetricDefinition, MetricSource, MetricComponent
from ..core.config import get_logger

logger = get_logger(__name__)


class RatioMetricsCalculator:
    """Builds SQL queries for ratio metric calculations"""
    
    def __init__(self, metric_def: MetricDefinition, temporal_window: str = "1Y"):
        self.metric_def = metric_def
        self.temporal_window = temporal_window
        self.rows_between, self.min_years_required = self._calculate_rows_between(temporal_window)
    
    @staticmethod
    def _calculate_rows_between(temporal_window: str) -> tuple[str, int]:
        """
        Convert temporal window to SQL ROWS BETWEEN clause and minimum year requirement.
        
        Returns:
            (sql_rows_between, min_years_required)
            - sql_rows_between: SQL window function clause
            - min_years_required: Minimum prior fiscal years needed (used to calculate threshold as min_years_required + 1 = year_rank >= threshold)
        
        Logic for year_rank threshold calculation:
        - year_rank 1 = 2002 (first year)
        - To get first result in 2003 (year_rank 2): need threshold = 2 = min_years_required + 1, so min_years_required = 1
        - To get first result in 2005 (year_rank 4): need threshold = 4 = min_years_required + 1, so min_years_required = 3
        - To get first result in 2007 (year_rank 6): need threshold = 6 = min_years_required + 1, so min_years_required = 5
        - To get first result in 2012 (year_rank 11): need threshold = 11 = min_years_required + 1, so min_years_required = 10
        """
        mapping = {
            "1Y": ("ROWS BETWEEN 0 PRECEDING AND CURRENT ROW", 1),
            "3Y": ("ROWS BETWEEN 2 PRECEDING AND CURRENT ROW", 3),
            "5Y": ("ROWS BETWEEN 4 PRECEDING AND CURRENT ROW", 5),
            "10Y": ("ROWS BETWEEN 9 PRECEDING AND CURRENT ROW", 10)
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
        
        Example: MB Ratio = Calc MC / Calc EE (both from metrics_outputs)
        Example: Profit Margin = PAT_EX / REVENUE (both from fundamentals)
        """
        numerator = self.metric_def.numerator
        denominator = self.metric_def.denominator
        
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
        
        # Determine which table to query from
        numerator_table = "cissa.metrics_outputs" if numerator.metric_source == MetricSource.METRICS_OUTPUTS else "cissa.fundamentals"
        denominator_table = "cissa.metrics_outputs" if denominator.metric_source == MetricSource.METRICS_OUTPUTS else "cissa.fundamentals"
        
        # Build numerator CTE with appropriate column name and table
        if numerator.metric_source == MetricSource.METRICS_OUTPUTS:
            # For metrics_outputs, conditionally include param_set_id filter only if parameter_dependent
            param_filter = ""
            if numerator.parameter_dependent:
                param_filter = "\n                AND param_set_id = :param_set_id"
            
            numerator_cte = f"""
        numerator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(output_metric_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS numerator_value,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year) AS year_rank
            FROM {numerator_table}
            WHERE dataset_id = :dataset_id{param_filter}
                AND output_metric_name = :numerator_metric
                AND ticker IN ({ticker_placeholders})
        )"""
        else:  # fundamentals
            numerator_cte = f"""
        numerator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(numeric_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS numerator_value,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year) AS year_rank
            FROM {numerator_table}
            WHERE dataset_id = :dataset_id
                AND metric_name = :numerator_metric
                AND ticker IN ({ticker_placeholders})
        )"""
        
        # Build denominator CTE with appropriate column name and table
        if denominator.metric_source == MetricSource.METRICS_OUTPUTS:
            # For metrics_outputs, conditionally include param_set_id filter only if parameter_dependent
            param_filter = ""
            if denominator.parameter_dependent:
                param_filter = "\n                AND param_set_id = :param_set_id"
            
            denominator_cte = f"""
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
            FROM {denominator_table}
            WHERE dataset_id = :dataset_id{param_filter}
                AND output_metric_name = :denominator_metric
                AND ticker IN ({ticker_placeholders})
        )"""
        else:  # fundamentals
            denominator_cte = f"""
        denominator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(numeric_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS denominator_value
            FROM {denominator_table}
            WHERE dataset_id = :dataset_id
                AND metric_name = :denominator_metric
                AND ticker IN ({ticker_placeholders})
        )"""
        
        query = f"""
        WITH {numerator_cte},
             {denominator_cte}
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
        WHERE m.ticker IS NOT NULL 
            AND m.year_rank >= :min_year_threshold {year_filter}
        ORDER BY m.ticker, m.fiscal_year;
        """
        
        params = {
            "dataset_id": str(dataset_id),
            "numerator_metric": numerator.metric_name,
            "denominator_metric": denominator.metric_name,
            "min_year_threshold": self.min_years_required + 1,
            **ticker_params
        }
        
        # Only add param_set_id if either metric requires it
        if numerator.parameter_dependent or denominator.parameter_dependent:
            params["param_set_id"] = str(param_set_id)
        
        return query, params
    
    def _build_complex_ratio_query(
        self,
        tickers: List[str],
        dataset_id: UUID,
        param_set_id: UUID,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build query for complex ratio with year shifting and mixed data sources.
        
        Example: ROEE = PAT_EX (from fundamentals, 1Y/3Y/5Y/10Y avg) 
                      / Calc EE (from metrics_outputs, shifted by 1 year, 1Y/3Y/5Y/10Y avg)
        
        The denominator is shifted so that year N-1's Calc EE becomes year N's EE_Open.
        This allows calculating ROEE(N) = PAT_EX(N) / EE_Open(N) where EE_Open is prior year's EE.
        """
        numerator = self.metric_def.numerator
        denominator = self.metric_def.denominator
        
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
        
        # Build numerator CTE (from fundamentals)
        numerator_cte = f"""
        numerator_raw AS (
            SELECT
                ticker,
                fiscal_year,
                numeric_value AS pat_ex_value
            FROM cissa.fundamentals
            WHERE dataset_id = :dataset_id
                AND metric_name = :numerator_metric
                AND ticker IN ({ticker_placeholders})
        ),
        numerator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(pat_ex_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS numerator_value,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year) AS year_rank
            FROM numerator_raw
        )
        """
        
        # Build denominator CTE (from metrics_outputs, with year shift)
        year_shift = denominator.year_shift
        denominator_cte = f"""
        denominator_raw AS (
            SELECT
                ticker,
                fiscal_year,
                output_metric_value
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
                AND param_set_id = :param_set_id
                AND output_metric_name = :denominator_metric
                AND ticker IN ({ticker_placeholders})
        ),
        denominator_shifted AS (
            SELECT
                ticker,
                fiscal_year + {year_shift} AS fiscal_year,
                output_metric_value AS ee_open_value
            FROM denominator_raw
        ),
        denominator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(ee_open_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS denominator_value
            FROM denominator_shifted
        )
        """
        
        query = f"""
        WITH {numerator_cte},
             {denominator_cte}
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
        WHERE m.ticker IS NOT NULL 
            AND m.year_rank >= :min_year_threshold {year_filter}
        ORDER BY m.ticker, m.fiscal_year;
        """
        
        params = {
            "dataset_id": str(dataset_id),
            "param_set_id": str(param_set_id),
            "numerator_metric": numerator.metric_name,
            "denominator_metric": denominator.metric_name,
            "min_year_threshold": self.min_years_required + 1,  # year_shift doesn't affect threshold, only data filtering
            **ticker_params
        }
        
        return query, params
