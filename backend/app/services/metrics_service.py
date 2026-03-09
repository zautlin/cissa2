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
    
    async def _execute_sql_function(
        self,
        metric_name: str,
        dataset_id: UUID
    ) -> int:
        """
        Execute a single L1 metric SQL function and insert results into metrics_outputs.
        
        Args:
            metric_name: Key from METRIC_FUNCTIONS dict (e.g., "Calc MC", "Calc Assets")
            dataset_id: UUID of the dataset
            
        Returns:
            int: Number of rows inserted
        """
        if metric_name not in METRIC_FUNCTIONS:
            logger.warning(f"Unknown metric: {metric_name}")
            return 0
        
        function_name, column_name = METRIC_FUNCTIONS[metric_name]
        
        try:
            # Call the SQL function to get calculated results
            logger.info(f"Executing L1 metric: {metric_name} (via {function_name})")
            
            query = text(f"""
                SELECT ticker, fiscal_year, {column_name} AS value
                FROM cissa.{function_name}(:dataset_id)
            """)
            
            result = await self.session.execute(query, {"dataset_id": str(dataset_id)})
            rows = result.fetchall()
            
            logger.info(f"Function {function_name} returned {len(rows)} rows")
            
            # Convert rows to MetricResultItem objects
            results = [
                MetricResultItem(
                    ticker=row[0],
                    fiscal_year=row[1],
                    value=float(row[2]) if row[2] is not None else 0.0
                )
                for row in rows
            ]
            
            # Insert results into metrics_outputs table with L1 metadata
            await self._insert_metric_results_with_metadata(
                dataset_id=dataset_id,
                metric_name=metric_name,
                results=results,
                metadata={"metric_level": "L1"}
            )
            
            logger.info(f"Successfully calculated L1 metric: {metric_name} ({len(results)} records)")
            return len(results)
        
        except Exception as e:
            logger.error(f"Error calculating L1 metric {metric_name}: {str(e)}")
            return 0
    
    async def _insert_metric_results_with_metadata(
        self,
        dataset_id: UUID,
        metric_name: str,
        results: List[MetricResultItem],
        metadata: Dict[str, Any]
    ) -> None:
        """
        Insert calculated metric results into metrics_outputs table with custom metadata.
        
        Args:
            dataset_id: UUID of the dataset
            metric_name: Name of the metric
            results: List of MetricResultItem objects
            metadata: Dict to store in metadata column (e.g., {"metric_level": "L1"})
        """
        
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
            import json
            metadata_str = json.dumps(metadata)
            values = [
                {
                    "dataset_id": str(dataset_id),
                    "param_set_id": param_set_id,
                    "ticker": item.ticker,
                    "fiscal_year": item.fiscal_year,
                    "output_metric_name": metric_name,
                    "output_metric_value": item.value,
                    "metadata": metadata_str
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
    
    async def calculate_all_l1_metrics(
        self,
        dataset_id: UUID
    ) -> Dict[str, Any]:
        """
        Calculate all 15 L1 metrics for a dataset in dependency order.
        
        L1 metrics are fundamental calculations that form the foundation for higher-level metrics.
        This method executes them in the correct dependency order to ensure data availability.
        
        Dependency order:
        1. Calc MC (base)
        2. Calc Assets (base, needed by Calc OA and ROA)
        3. Calc OA (depends on Calc Assets)
        4. Calc Op Cost (base)
        5. Calc Non Op Cost (base)
        6. Calc Tax Cost (base)
        7. Calc XO Cost (base)
        8. Profit Margin (base)
        9. Op Cost Margin % (base)
        10. Non-Op Cost Margin % (base)
        11. Eff Tax Rate (base)
        12. XO Cost Margin % (base)
        13. FA Intensity (base)
        14. Book Equity (base)
        15. ROA (depends on Calc Assets)
        
        Args:
            dataset_id: UUID of the dataset
            
        Returns:
            Dict with status, calculated count, failed count, and any errors
        """
        logger.info(f"Starting L1 metrics calculation for dataset {dataset_id}")
        
        # Define metrics in dependency order
        l1_metrics_order = [
            "Calc MC",
            "Calc Assets",
            "Calc OA",
            "Calc Op Cost",
            "Calc Non Op Cost",
            "Calc Tax Cost",
            "Calc XO Cost",
            "Profit Margin",
            "Op Cost Margin %",
            "Non-Op Cost Margin %",
            "Eff Tax Rate",
            "XO Cost Margin %",
            "FA Intensity",
            "Book Equity",
            "ROA",
        ]
        
        calculated = 0
        failed = 0
        errors = []
        
        for metric_name in l1_metrics_order:
            try:
                row_count = await self._execute_sql_function(metric_name, dataset_id)
                if row_count > 0:
                    calculated += 1
                else:
                    failed += 1
                    error_msg = f"{metric_name}: No rows calculated"
                    errors.append(error_msg)
                    logger.warning(f"L1 metric {metric_name} returned 0 rows")
            except Exception as e:
                failed += 1
                error_msg = f"{metric_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Error calculating L1 metric {metric_name}: {str(e)}")
        
        # Determine overall status
        if failed == 0:
            status = "success"
        elif calculated > 0:
            status = "partial"
        else:
            status = "error"
        
        result = {
            "status": status,
            "total_metrics": len(l1_metrics_order),
            "calculated": calculated,
            "failed": failed,
            "errors": errors
        }
        
        logger.info(f"L1 metrics calculation complete: {calculated}/{len(l1_metrics_order)} successful, {failed} failed")
        
        return result
