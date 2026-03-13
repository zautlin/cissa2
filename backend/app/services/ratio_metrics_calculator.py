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
            ticker_params["start_year"] = str(start_year)
        if end_year is not None:
            year_filter += f" AND m.fiscal_year <= :end_year"
            ticker_params["end_year"] = str(end_year)
        
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
        
        Example: ETR = Calc Tax Cost (from metrics_outputs, 1Y/3Y/5Y/10Y avg)
                    / ABS(PAT_EX (from fundamentals) + Calc XO Cost (from metrics_outputs))
        
        The denominator can be simple (single metric with optional year shift) or
        composite (multiple metrics combined with operation, optionally wrapped in ABS).
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
            ticker_params["start_year"] = str(start_year)
        if end_year is not None:
            year_filter += f" AND m.fiscal_year <= :end_year"
            ticker_params["end_year"] = str(end_year)
        
        # Build numerator CTE (flexible: can be from metrics_outputs or fundamentals)
        if numerator.metric_source == MetricSource.METRICS_OUTPUTS:
            # From metrics_outputs - use output_metric_value and output_metric_name
            param_filter = ""
            if numerator.parameter_dependent:
                param_filter = "\n                AND param_set_id = :param_set_id"
            
            year_shift = numerator.year_shift or 0
            
            if year_shift != 0:
                # When year_shift is applied to metrics_outputs numerator, calculate year_rank BEFORE shifting
                # so the threshold filtering works correctly
                numerator_cte = f"""
        numerator_raw AS (
            SELECT
                ticker,
                fiscal_year,
                output_metric_value AS numerator_raw_value,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year) AS year_rank
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id{param_filter}
                AND output_metric_name = :numerator_metric
                AND ticker IN ({ticker_placeholders})
        ),
        numerator_shifted AS (
            SELECT
                ticker,
                fiscal_year + {year_shift} AS fiscal_year,
                numerator_raw_value,
                year_rank
            FROM numerator_raw
        ),
        numerator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(numerator_raw_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS numerator_value,
                year_rank
            FROM numerator_shifted
        )
        """
            else:
                numerator_cte = f"""
        numerator_raw AS (
            SELECT
                ticker,
                fiscal_year,
                output_metric_value AS numerator_raw_value
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id{param_filter}
                AND output_metric_name = :numerator_metric
                AND ticker IN ({ticker_placeholders})
        ),
        numerator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(numerator_raw_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS numerator_value,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year) AS year_rank
            FROM numerator_raw
        )
        """
        else:  # fundamentals
            # Handle year_shift for numerator from fundamentals
            year_shift = numerator.year_shift or 0
            
            if year_shift != 0:
                # When year_shift is applied, calculate year_rank BEFORE shifting
                # so the threshold filtering works correctly
                numerator_cte = f"""
        numerator_raw AS (
            SELECT
                ticker,
                fiscal_year,
                numeric_value AS numerator_raw_value,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year) AS year_rank
            FROM cissa.fundamentals
            WHERE dataset_id = :dataset_id
                AND metric_name = :numerator_metric
                AND ticker IN ({ticker_placeholders})
        ),
        numerator_shifted AS (
            SELECT
                ticker,
                fiscal_year + {year_shift} AS fiscal_year,
                numerator_raw_value,
                year_rank
            FROM numerator_raw
        ),
        numerator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(numerator_raw_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS numerator_value,
                year_rank
            FROM numerator_shifted
        )
        """
            else:
                numerator_cte = f"""
        numerator_raw AS (
            SELECT
                ticker,
                fiscal_year,
                numeric_value AS numerator_raw_value
            FROM cissa.fundamentals
            WHERE dataset_id = :dataset_id
                AND metric_name = :numerator_metric
                AND ticker IN ({ticker_placeholders})
        ),
        numerator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(numerator_raw_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS numerator_value,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY fiscal_year) AS year_rank
            FROM numerator_raw
        )
        """
        
        # Check if denominator is composite (has operand_metric_name or operands list)
        has_operands = denominator.operands is not None and len(denominator.operands) > 0
        has_legacy_operand = denominator.operation is not None and denominator.operand_metric_name is not None
        
        if has_operands or has_legacy_operand:
            # Composite denominator (e.g., ETR: ABS(PAT_EX + Calc XO Cost + Calc Tax Cost))
            denominator_cte = self._build_composite_denominator_cte(
                ticker_placeholders, ticker_params, denominator
            )
        else:
            # Simple denominator (e.g., ROEE: Calc EE with year shift, or FA Intensity: REVENUE with year shift)
            year_shift = denominator.year_shift or 0
            apply_abs = denominator.apply_absolute_value or False
            abs_wrapper = "ABS(" if apply_abs else ""
            abs_closer = ")" if apply_abs else ""
            
            if denominator.metric_source == MetricSource.METRICS_OUTPUTS:
                # Denominator from metrics_outputs (e.g., ROEE: Calc EE, or Econ Eq Mult: ABS(Calc EE))
                param_filter = ""
                if denominator.parameter_dependent:
                    param_filter = "\n                AND param_set_id = :param_set_id"
                
                if year_shift != 0:
                    denominator_cte = f"""
        denominator_raw AS (
            SELECT
                ticker,
                fiscal_year,
                {abs_wrapper}output_metric_value{abs_closer} AS denominator_raw_value
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id{param_filter}
                AND output_metric_name = :denominator_metric
                AND ticker IN ({ticker_placeholders})
        ),
        denominator_shifted AS (
            SELECT
                ticker,
                fiscal_year + {year_shift} AS fiscal_year,
                denominator_raw_value
            FROM denominator_raw
        ),
        denominator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(denominator_raw_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS denominator_value
            FROM denominator_shifted
        )
        """
                else:
                    denominator_cte = f"""
        denominator_raw AS (
            SELECT
                ticker,
                fiscal_year,
                {abs_wrapper}output_metric_value{abs_closer} AS denominator_raw_value
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id{param_filter}
                AND output_metric_name = :denominator_metric
                AND ticker IN ({ticker_placeholders})
        ),
        denominator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(denominator_raw_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS denominator_value
            FROM denominator_raw
        )
        """
            else:
                # Denominator from fundamentals (e.g., FA Intensity: REVENUE, or future ABS(metric))
                if year_shift != 0:
                    denominator_cte = f"""
        denominator_raw AS (
            SELECT
                ticker,
                fiscal_year,
                {abs_wrapper}numeric_value{abs_closer} AS denominator_raw_value
            FROM cissa.fundamentals
            WHERE dataset_id = :dataset_id
                AND metric_name = :denominator_metric
                AND ticker IN ({ticker_placeholders})
        ),
        denominator_shifted AS (
            SELECT
                ticker,
                fiscal_year + {year_shift} AS fiscal_year,
                denominator_raw_value
            FROM denominator_raw
        ),
        denominator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(denominator_raw_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS denominator_value
            FROM denominator_shifted
        )
        """
                else:
                    denominator_cte = f"""
        denominator_raw AS (
            SELECT
                ticker,
                fiscal_year,
                {abs_wrapper}numeric_value{abs_closer} AS denominator_raw_value
            FROM cissa.fundamentals
            WHERE dataset_id = :dataset_id
                AND metric_name = :denominator_metric
                AND ticker IN ({ticker_placeholders})
        ),
        denominator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(denominator_raw_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS denominator_value
            FROM denominator_raw
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
        
        # Calculate adjusted threshold if numerator has year_shift
        # When numerator is year-shifted forward, we need to reduce the threshold
        # to account for the shifted data starting earlier than the original data
        numerator_year_shift = numerator.year_shift or 0
        adjusted_threshold = max(1, (self.min_years_required + 1) - numerator_year_shift)
        
        params = {
            "dataset_id": str(dataset_id),
            "numerator_metric": numerator.metric_name,
            "min_year_threshold": adjusted_threshold,
            **ticker_params
        }
        
        # Add param_set_id if needed by numerator or denominator components
        needs_param_set_id = (
            numerator.parameter_dependent or 
            denominator.parameter_dependent or 
            (denominator.operation and denominator.operand_parameter_dependent) or
            (denominator.operands is not None and any(op.parameter_dependent for op in denominator.operands))
        )
        if needs_param_set_id:
            params["param_set_id"] = str(param_set_id)
        
        # Add denominator metric names
        # Check if using new multi-operand format or legacy format
        has_operands = denominator.operands is not None and len(denominator.operands) > 0
        has_legacy_operand = denominator.operation is not None and denominator.operand_metric_name is not None
        
        if has_operands or has_legacy_operand:
            # Composite denominator
            params["denominator_metric"] = denominator.metric_name
            
            if has_operands and denominator.operands:
                # New format: multiple operands
                for i, operand in enumerate(denominator.operands):
                    params[f"operand_metric_{i}"] = operand.metric_name
            else:
                # Legacy format: single operand
                params["operand_metric_0"] = denominator.operand_metric_name or ""
        else:
            # Simple denominator
            params["denominator_metric"] = denominator.metric_name
        
        return query, params
    
    def _build_composite_denominator_cte(
        self,
        ticker_placeholders: str,
        ticker_params: Dict[str, Any],
        denominator: MetricComponent
    ) -> str:
        """
        Build CTE for composite denominator (e.g., ABS(PAT + Calc XO Cost + Calc Tax Cost)).
        
        Handles:
        - Multiple metric sources (fundamentals + metrics_outputs)
        - Multiple operands with composite operations (add, subtract)
        - Optional absolute value wrapping
        
        Supports both legacy single-operand format and new multi-operand format.
        """
        # Check if using new operands format or legacy format
        has_operands = denominator.operands is not None and len(denominator.operands) > 0
        has_legacy_operand = denominator.operation is not None and denominator.operand_metric_name is not None
        
        if not has_operands and not has_legacy_operand:
            raise ValueError("Composite denominator requires either 'operands' list or legacy 'operation'/'operand_metric_name'")
        
        # Build main metric CTE
        if denominator.metric_source == MetricSource.METRICS_OUTPUTS:
            main_cte = f"""
        denominator_main_raw AS (
             SELECT
                ticker,
                fiscal_year,
                output_metric_value AS value_0
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
                AND param_set_id = :param_set_id
                AND output_metric_name = :denominator_metric
                AND ticker IN ({ticker_placeholders})
        )"""
        else:  # fundamentals
            main_cte = f"""
        denominator_main_raw AS (
            SELECT
                ticker,
                fiscal_year,
                numeric_value AS value_0
            FROM cissa.fundamentals
            WHERE dataset_id = :dataset_id
                AND metric_name = :denominator_metric
                AND ticker IN ({ticker_placeholders})
        )"""
        
        # Build operand CTEs
        operand_ctes = []
        operand_list: List[Any] = []
        
        if has_operands and denominator.operands:
            operand_list = denominator.operands
        elif has_legacy_operand:
            # Convert legacy format to new format
            class LegacyOperand:
                def __init__(self, name: str, source: MetricSource, param_dep: bool, op: str):
                    self.metric_name = name
                    self.metric_source = source
                    self.parameter_dependent = param_dep
                    self.operation = op
            
            operand_name = denominator.operand_metric_name or ""
            operand_source = denominator.operand_metric_source or MetricSource.METRICS_OUTPUTS
            operand_param_dep = denominator.operand_parameter_dependent or False
            operand_op = denominator.operation or "add"
            
            operand_list = [LegacyOperand(operand_name, operand_source, operand_param_dep, operand_op)]
        
        for i, operand in enumerate(operand_list):
            if operand.metric_source == MetricSource.METRICS_OUTPUTS:
                param_filter = ""
                if operand.parameter_dependent:
                    param_filter = "\n                AND param_set_id = :param_set_id"
                
                operand_cte = f"""
        denominator_operand_{i}_raw AS (
            SELECT
                ticker,
                fiscal_year,
                output_metric_value AS value_{i+1}
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id{param_filter}
                AND output_metric_name = :operand_metric_{i}
                AND ticker IN ({ticker_placeholders})
        )"""
            else:  # fundamentals
                operand_cte = f"""
        denominator_operand_{i}_raw AS (
            SELECT
                ticker,
                fiscal_year,
                numeric_value AS value_{i+1}
            FROM cissa.fundamentals
            WHERE dataset_id = :dataset_id
                AND metric_name = :operand_metric_{i}
                AND ticker IN ({ticker_placeholders})
        )"""
            operand_ctes.append(operand_cte)
        
        # Build the combined expression with all operands
        # Start with main_value and apply operations in order
        num_operands = len(operand_list)
        combined_expression = "COALESCE(m.value_0, 0)"
        
        join_clauses = []
        for i, operand in enumerate(operand_list):
            op = operand.operation.lower()
            
            op_map = {"add": "+", "subtract": "-"}
            if op not in op_map:
                raise ValueError(f"Unknown operation: {op}. Must be one of: {', '.join(op_map.keys())}")
            
            sql_op = op_map[op]
            combined_expression += f" {sql_op} COALESCE(o{i}.value_{i+1}, 0)"
            join_clauses.append(f"LEFT JOIN denominator_operand_{i}_raw o{i} ON m.ticker = o{i}.ticker AND m.fiscal_year = o{i}.fiscal_year")
        
        # Wrap with ABS if needed
        abs_wrapper = "ABS(" if denominator.apply_absolute_value else ""
        abs_closer = ")" if denominator.apply_absolute_value else ""
        
        combined_cte = f"""
        denominator_combined AS (
            SELECT
                m.ticker,
                m.fiscal_year,
                {abs_wrapper}{combined_expression}{abs_closer} AS combined_value
            FROM denominator_main_raw m
            {chr(10).join(join_clauses)}
        ),
        denominator_rolling AS (
            SELECT
                ticker,
                fiscal_year,
                AVG(combined_value) 
                    OVER (
                        PARTITION BY ticker 
                        ORDER BY fiscal_year 
                        {self.rows_between}
                    ) AS denominator_value
            FROM denominator_combined
        )
        """
        
        all_ctes = [main_cte] + operand_ctes + [combined_cte]
        return ",\n".join(all_ctes)
