# ============================================================================
# Metrics Calculation Service Layer
# ============================================================================
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from uuid import UUID
from typing import List, Dict, Any, Optional
from ..models import MetricResultItem, CalculateMetricsResponse
from ..core.config import get_logger

logger = get_logger(__name__)


# Mapping of metric names to SQL function names and return column names
# Format: "Display Name" → (function_name, output_column_name, requires_param_set_id)
# L1 Metrics (14 total):
#   - 7 Simple metrics: no parameter_set_id needed
#   - 5 Temporal metrics: Calc ECF, Non Div ECF (base), Calc EE, Calc FY TSR, Calc FY TSR PREL (3 need param)
#   - 2 Derived metrics (used by L2): Book Equity, ROA
METRIC_FUNCTIONS = {
    # L1 Simple Metrics (7)
    "Calc MC": ("fn_calc_market_cap", "calc_mc", False),
    "Calc Assets": ("fn_calc_operating_assets", "calc_assets", False),
    "Calc OA": ("fn_calc_operating_assets_detail", "calc_oa", False),
    "Calc Op Cost": ("fn_calc_operating_cost", "calc_op_cost", False),
    "Calc Non Op Cost": ("fn_calc_non_operating_cost", "calc_non_op_cost", False),
    "Calc Tax Cost": ("fn_calc_tax_cost", "calc_tax_cost", False),
    "Calc XO Cost": ("fn_calc_extraordinary_cost", "calc_xo_cost", False),
    
    # L1 Temporal Metrics (5)
    # Note: These must match the SQL function lookups for Non Div ECF and Calc FY TSR PREL
    # which query metrics_outputs by output_metric_name
    "Calc ECF": ("fn_calc_ecf", "ecf", False),
    "Non Div ECF": ("fn_calc_non_div_ecf", "non_div_ecf", False),
    "Calc EE": ("fn_calc_economic_equity", "ee", True),       # Requires param_set_id for ECF lookup
    "Calc FY TSR": ("fn_calc_fy_tsr", "fy_tsr", True),      # Requires param_set_id
    "Calc FY TSR PREL": ("fn_calc_fy_tsr_prel", "fy_tsr_prel", True),  # Requires param_set_id
    
    # L1 Derived Metrics (2)
    # These are calculated from other L1 metrics and used by L2 service
    "Book Equity": ("fn_calc_book_equity", "book_equity", False),
    "ROA": ("fn_calc_roa", "roa", False),
}


class MetricsService:
    """Service layer for metric calculations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def _get_default_param_set_id(self) -> Optional[UUID]:
        """
        Get the default parameter set ID (base_case with is_default=true).
        
        Returns:
            UUID of default param_set, or None if not found
        """
        try:
            param_set_query = text("""
                SELECT param_set_id FROM cissa.parameter_sets 
                WHERE is_default = true LIMIT 1
            """)
            param_result = await self.session.execute(param_set_query)
            param_row = param_result.fetchone()
            
            if param_row:
                return param_row[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching default parameter set: {str(e)}")
            return None
    
    async def calculate_metric(
        self,
        dataset_id: UUID,
        metric_name: str,
        param_set_id: Optional[UUID] = None  # Optional for parameter-sensitive metrics
    ) -> CalculateMetricsResponse:
        """
        Calculate a metric for a dataset.
        
        1. Validate metric name
        2. Resolve param_set_id if needed (for Calc FY TSR, Calc FY TSR PREL)
        3. Call SQL function to calculate
        4. Insert results into metrics_outputs
        5. Return response
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
        
        function_name, column_name, needs_param_set = METRIC_FUNCTIONS[metric_name]
        
        # Resolve param_set_id if needed for parameter-sensitive metrics
        if needs_param_set:
            if not param_set_id:
                param_set_id = await self._get_default_param_set_id()
                if not param_set_id:
                    return CalculateMetricsResponse(
                        dataset_id=dataset_id,
                        metric_name=metric_name,
                        results_count=0,
                        status="error",
                        message="Metric requires param_set_id, but no default found"
                    )
        
        try:
            # Call the SQL function to get calculated results
            logger.info(f"Calling {function_name} for dataset {dataset_id}, param_set_id: {param_set_id}")
            
            if needs_param_set:
                query = text(f"""
                    SELECT ticker, fiscal_year, {column_name} AS value
                    FROM cissa.{function_name}(:dataset_id, :param_set_id)
                """)
                result = await self.session.execute(
                    query, 
                    {"dataset_id": str(dataset_id), "param_set_id": str(param_set_id)}
                )
            else:
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
        Handles both parameter-independent and parameter-sensitive metrics.
        
        Args:
            metric_name: Key from METRIC_FUNCTIONS dict (e.g., "Calc MC", "Calc Assets")
            dataset_id: UUID of the dataset
            
        Returns:
            int: Number of rows inserted
        """
        if metric_name not in METRIC_FUNCTIONS:
            logger.warning(f"Unknown metric: {metric_name}")
            return 0
        
        function_name, column_name, needs_param_set = METRIC_FUNCTIONS[metric_name]
        
        try:
            # Call the SQL function to get calculated results
            logger.info(f"Executing L1 metric: {metric_name} (via {function_name})")
            
            # Handle parameter-sensitive metrics
            if needs_param_set:
                param_set_id = await self._get_default_param_set_id()
                if not param_set_id:
                    error_msg = f"Metric {metric_name} requires param_set_id, but no default found"
                    logger.error(error_msg)
                    return 0
                
                query = text(f"""
                    SELECT ticker, fiscal_year, {column_name} AS value
                    FROM cissa.{function_name}(:dataset_id, :param_set_id)
                """)
                
                logger.info(f"Query: {query}")
                logger.info(f"Dataset ID param: {dataset_id}, Param Set ID: {param_set_id}")
                
                result = await self.session.execute(query, {
                    "dataset_id": str(dataset_id),
                    "param_set_id": str(param_set_id)
                })
            else:
                query = text(f"""
                    SELECT ticker, fiscal_year, {column_name} AS value
                    FROM cissa.{function_name}(:dataset_id)
                """)
                
                logger.info(f"Query: {query}")
                logger.info(f"Dataset ID param: {dataset_id}")
                
                result = await self.session.execute(query, {"dataset_id": str(dataset_id)})
            
            rows = result.fetchall()
            
            logger.info(f"Function {function_name} returned {len(rows)} rows")
            
            if len(rows) == 0:
                logger.warning(f"No rows returned from {function_name} for dataset {dataset_id}")
            
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
        Calculate all L1 metrics for a dataset in dependency order.
        
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
        8. Calc ECF (temporal base)
        9. Non Div ECF (depends on Calc ECF)
        10. Calc EE (temporal, optionally depends on Calc ECF)
        11. Calc FY TSR (temporal, parameter-sensitive)
        12. Calc FY TSR PREL (depends on Calc FY TSR)
        13. Book Equity (used by L2 metrics)
        14. ROA (depends on Calc Assets, used by L2 metrics)
        
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
            "Calc ECF",
            "Non Div ECF",
            "Calc EE",
            "Calc FY TSR",
            "Calc FY TSR PREL",
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
    
    async def calculate_batch_metrics(
        self,
        dataset_id: UUID,
        metric_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Calculate a batch of metrics using two-phase execution to handle dependencies.
        
        PHASE 1 (Base Metrics): Calculate metrics that read from fundamentals table
        - All 7 simple L1 metrics
        - Temporal base metrics: Calc ECF, Calc EE, Calc FY TSR, LAG_MC (depend on fundamentals only)
        
        PHASE 2 (Derived Metrics): Calculate metrics that depend on PHASE 1 results
        - Non Div ECF: reads Calc ECF from metrics_outputs
        - Calc FY TSR PREL: reads Calc FY TSR from metrics_outputs
        
        Between phases: Database commit ensures PHASE 1 results are persisted before PHASE 2 reads.
        
        Args:
            dataset_id: UUID of the dataset
            metric_names: Optional list of specific metrics to calculate. If None, calculates all 12 L1 metrics.
            
        Returns:
            Dict with status, calculated count, failed count, metrics breakdown, and errors
        """
        logger.info(f"Starting batch metrics calculation (two-phase) for dataset {dataset_id}")
        
        # Define all L1 metrics with their phase assignment
        # Format: metric_name → (phase_number, requires_param_set)
        L1_METRICS_PHASES = {
            # PHASE 1: Base metrics (read from fundamentals)
            "Calc MC": (1, False),
            "Calc Assets": (1, False),
            "Calc OA": (1, False),
            "Calc Op Cost": (1, False),
            "Calc Non Op Cost": (1, False),
            "Calc Tax Cost": (1, False),
            "Calc XO Cost": (1, False),
            "LAG_MC": (1, False),
            "Calc ECF": (1, False),
            "Calc EE": (1, False),
            "Calc FY TSR": (1, True),   # Parameter-sensitive but still base
            
            # PHASE 2: Derived metrics (read from metrics_outputs)
            "Non Div ECF": (2, False),     # Depends on Calc ECF being in metrics_outputs
            "Calc FY TSR PREL": (2, True),      # Depends on Calc FY TSR being in metrics_outputs, param-sensitive
        }
        
        # If specific metrics requested, validate they exist
        metrics_to_calculate = metric_names if metric_names else list(L1_METRICS_PHASES.keys())
        
        # Organize metrics by phase
        phase1_metrics = []
        phase2_metrics = []
        
        for metric_name in metrics_to_calculate:
            if metric_name not in L1_METRICS_PHASES:
                logger.warning(f"Unknown metric: {metric_name}, skipping")
                continue
            
            phase, needs_param = L1_METRICS_PHASES[metric_name]
            if phase == 1:
                phase1_metrics.append(metric_name)
            else:
                phase2_metrics.append(metric_name)
        
        calculated = 0
        failed = 0
        errors = []
        phase1_results = {}
        phase2_results = {}
        
        # ===============================
        # PHASE 1: Calculate base metrics
        # ===============================
        logger.info(f"PHASE 1: Calculating {len(phase1_metrics)} base metrics")
        
        for metric_name in phase1_metrics:
            try:
                row_count = await self._execute_sql_function(metric_name, dataset_id)
                phase1_results[metric_name] = row_count
                if row_count > 0:
                    calculated += 1
                    logger.info(f"✓ {metric_name}: {row_count} records")
                else:
                    failed += 1
                    error_msg = f"{metric_name}: 0 rows calculated"
                    errors.append(error_msg)
                    logger.warning(f"  {metric_name}: 0 rows")
            except Exception as e:
                failed += 1
                error_msg = f"{metric_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"  Error in {metric_name}: {str(e)}")
                phase1_results[metric_name] = 0
        
        logger.info(f"PHASE 1 complete: {calculated} successful, {failed} failed")
        logger.info(f"Database commit after PHASE 1 - metrics_outputs now contains base metric results")
        
        # ===============================
        # PHASE 2: Calculate derived metrics
        # ===============================
        if phase2_metrics:
            logger.info(f"PHASE 2: Calculating {len(phase2_metrics)} derived metrics (now reading from metrics_outputs)")
            
            for metric_name in phase2_metrics:
                try:
                    row_count = await self._execute_sql_function(metric_name, dataset_id)
                    phase2_results[metric_name] = row_count
                    if row_count > 0:
                        calculated += 1
                        logger.info(f"✓ {metric_name}: {row_count} records")
                    else:
                        failed += 1
                        error_msg = f"{metric_name}: 0 rows calculated (parent metric may not exist)"
                        errors.append(error_msg)
                        logger.warning(f"  {metric_name}: 0 rows")
                except Exception as e:
                    failed += 1
                    error_msg = f"{metric_name}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"  Error in {metric_name}: {str(e)}")
                    phase2_results[metric_name] = 0
            
            logger.info(f"PHASE 2 complete: derived metrics calculated")
        
        # Determine overall status
        total_metrics = len(phase1_metrics) + len(phase2_metrics)
        if failed == 0:
            status = "success"
        elif calculated > 0:
            status = "partial"
        else:
            status = "error"
        
        result = {
            "status": status,
            "total_metrics": total_metrics,
            "calculated": calculated,
            "failed": failed,
            "phase1": {
                "metrics": phase1_metrics,
                "results": phase1_results
            },
            "phase2": {
                "metrics": phase2_metrics,
                "results": phase2_results
            },
            "errors": errors
        }
        
        logger.info(f"Batch metrics calculation complete: {calculated}/{total_metrics} successful, {failed} failed")
        
        return result
