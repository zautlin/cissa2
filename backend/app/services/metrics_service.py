# ============================================================================
# Metrics Calculation Service Layer
# ============================================================================
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from uuid import UUID
from typing import List, Dict, Any
from ..models import MetricResultItem, CalculateMetricsResponse
from ..core.config import get_logger

logger = get_logger(__name__)


# Mapping of metric names to SQL function names and return column names
METRIC_FUNCTIONS = {
    "Calc MC": ("fn_calc_market_cap", "calc_mc"),
    "Calc Assets": ("fn_calc_operating_assets", "calc_assets"),
    "Calc OA": ("fn_calc_operating_assets_detail", "calc_oa"),
    "Calc Op Cost": ("fn_calc_operating_cost", "calc_op_cost"),
    "Calc Non Op Cost": ("fn_calc_non_operating_cost", "calc_non_op_cost"),
    "Calc Tax Cost": ("fn_calc_tax_cost", "calc_tax_cost"),
    "Calc XO Cost": ("fn_calc_extraordinary_cost", "calc_xo_cost"),
    "Profit Margin": ("fn_calc_profit_margin", "profit_margin"),
    "Op Cost Margin %": ("fn_calc_operating_cost_margin", "op_cost_margin"),
    "Non-Op Cost Margin %": ("fn_calc_non_operating_cost_margin", "non_op_cost_margin"),
    "Eff Tax Rate": ("fn_calc_effective_tax_rate", "eff_tax_rate"),
    "XO Cost Margin %": ("fn_calc_extraordinary_cost_margin", "xo_cost_margin"),
    "FA Intensity": ("fn_calc_fixed_asset_intensity", "fa_intensity"),
    "Book Equity": ("fn_calc_book_equity", "book_equity"),
    "ROA": ("fn_calc_roa", "roa"),
}


class MetricsService:
    """Service layer for metric calculations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate_metric(
        self,
        dataset_id: UUID,
        metric_name: str
    ) -> CalculateMetricsResponse:
        """
        Calculate a metric for a dataset.
        
        1. Validate metric name
        2. Call SQL function to calculate
        3. Insert results into metrics_outputs
        4. Return response
        """
        
        # Validate metric name
        if metric_name not in METRIC_FUNCTIONS:
            return CalculateMetricsResponse(
                dataset_id=dataset_id,
                metric_name=metric_name,
                results_count=0,
                status="error",
                message=f"Unknown metric: {metric_name}. Available metrics: {', '.join(METRIC_FUNCTIONS.keys())}"
            )
        
        function_name, column_name = METRIC_FUNCTIONS[metric_name]
        
        try:
            # Call the SQL function to get calculated results
            logger.info(f"Calling {function_name} for dataset {dataset_id}")
            
            query = text(f"""
                SELECT ticker, fiscal_year, {column_name} AS value
                FROM cissa.{function_name}(:dataset_id)
            """)
            
            result = await self.session.execute(query, {"dataset_id": str(dataset_id)})
            rows = result.fetchall()
            
            logger.info(f"Function returned {len(rows)} rows")
            
            # Convert rows to MetricResultItem objects
            results = [
                MetricResultItem(
                    ticker=row[0],
                    fiscal_year=row[1],
                    value=float(row[2]) if row[2] is not None else 0.0
                )
                for row in rows
            ]
            
            # Insert results into metrics_outputs table
            await self._insert_metric_results(
                dataset_id=dataset_id,
                metric_name=metric_name,
                results=results
            )
            
            logger.info(f"Successfully calculated {metric_name} for {len(results)} records")
            
            return CalculateMetricsResponse(
                dataset_id=dataset_id,
                metric_name=metric_name,
                results_count=len(results),
                results=results,
                status="success"
            )
        
        except Exception as e:
            logger.error(f"Error calculating {metric_name}: {str(e)}")
            return CalculateMetricsResponse(
                dataset_id=dataset_id,
                metric_name=metric_name,
                results_count=0,
                status="error",
                message=f"Error calculating metric: {str(e)}"
            )
    
    async def _insert_metric_results(
        self,
        dataset_id: UUID,
        metric_name: str,
        results: List[MetricResultItem]
    ) -> None:
        """Insert calculated metric results into metrics_outputs table"""
        
        if not results:
            return
        
        # Get the default parameter set (base_case)
        param_set_query = text("""
            SELECT param_set_id FROM cissa.parameter_sets 
            WHERE param_set_name = 'base_case' LIMIT 1
        """)
        param_result = await self.session.execute(param_set_query)
        param_row = param_result.fetchone()
        
        if not param_row:
            logger.error("No base_case parameter set found in database")
            return
        
        param_set_id = str(param_row[0])
        
        # Prepare batch insert statement
        insert_query = text("""
            INSERT INTO cissa.metrics_outputs 
            (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata, created_at)
            VALUES (:dataset_id, :param_set_id, :ticker, :fiscal_year, :output_metric_name, :output_metric_value, :metadata, now())
            ON CONFLICT (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name) 
            DO UPDATE SET output_metric_value = EXCLUDED.output_metric_value
        """)
        
        # Batch insert in groups to avoid overly large queries
        batch_size = 1000
        for i in range(0, len(results), batch_size):
            batch = results[i:i + batch_size]
            
            # Prepare values for batch
            values = [
                {
                    "dataset_id": str(dataset_id),
                    "param_set_id": param_set_id,
                    "ticker": item.ticker,
                    "fiscal_year": item.fiscal_year,
                    "output_metric_name": metric_name,
                    "output_metric_value": item.value,
                    "metadata": '{"metric_level": "L1"}'
                }
                for item in batch
            ]
            
            # Execute batch insert
            for value_dict in values:
                await self.session.execute(insert_query, value_dict)
            
            logger.info(f"Inserted batch of {len(batch)} metric results")
        
        # Commit the transaction
        await self.session.commit()
        logger.info(f"Committed {len(results)} metric results for {metric_name}")
