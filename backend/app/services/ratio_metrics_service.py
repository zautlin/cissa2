# ============================================================================
# Service Layer for Ratio Metrics
# ============================================================================
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..models.ratio_metrics import (
    MetricDefinition,
    RatioMetricsResponse,
    RatioMetricsMultiWindowResponse,
    TickerData,
    TimeSeries,
    WindowData
)
from ..repositories.ratio_metrics_repository import RatioMetricsRepository
from ..repositories.revenue_growth_repository import RevenueGrowthRepository
from ..repositories.ee_growth_repository import EEGrowthRepository
from ..repositories.ep_growth_repository import EPGrowthRepository
from ..services.ratio_metrics_calculator import RatioMetricsCalculator
from ..services.revenue_growth_calculator import RevenueGrowthCalculator
from ..services.ee_growth_calculator import EEGrowthCalculator
from ..services.ep_growth_calculator import EPGrowthCalculator
from ..core.config import get_logger

logger = get_logger(__name__)


class RatioMetricsService:
    """Service layer for calculating ratio metrics and revenue growth on-the-fly"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.ratio_repo = RatioMetricsRepository(session)
        self.revenue_growth_repo = RevenueGrowthRepository(session)
        self.ee_growth_repo = EEGrowthRepository(session)
        self.ep_growth_repo = EPGrowthRepository(session)
        self.metric_config = self._load_ratio_metrics_config()
    
    @staticmethod
    def _load_ratio_metrics_config() -> Dict[str, MetricDefinition]:
        """Load ratio metrics configuration from JSON file"""
        config_path = Path(__file__).parent.parent / "config" / "ratio_metrics.json"
        
        if not config_path.exists():
            logger.warning(f"Ratio metrics config not found at {config_path}")
            return {}
        
        try:
            with open(config_path, "r") as f:
                config_data = json.load(f)
            
            # Parse metrics into MetricDefinition objects
            metrics = {}
            for metric_data in config_data.get("metrics", []):
                metric_def = MetricDefinition(**metric_data)
                metrics[metric_def.id] = metric_def
            
            logger.info(f"Loaded {len(metrics)} ratio metric definitions")
            return metrics
        
        except Exception as e:
            logger.error(f"Error loading ratio metrics config: {str(e)}")
            return {}
    
    async def _get_default_param_set_id(self) -> Optional[UUID]:
        """Get the default parameter set ID"""
        try:
            param_set_query = text("""
                SELECT param_set_id FROM cissa.parameter_sets 
                WHERE is_default = true LIMIT 1
            """)
            result = await self.session.execute(param_set_query)
            row = result.fetchone()
            
            if row:
                return row[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching default parameter set: {str(e)}")
            return None
    
    async def calculate_ratio_metric(
        self,
        metric_id: str,
        tickers: List[str],
        dataset_id: UUID,
        temporal_window: str = "1Y",
        param_set_id: Optional[UUID] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> RatioMetricsResponse:
        """
        Calculate a ratio metric or revenue growth for given tickers and temporal window.
        
        Args:
            metric_id: Metric identifier (e.g., 'mb_ratio', 'revenue_growth')
            tickers: List of stock tickers
            dataset_id: Dataset UUID
            temporal_window: "1Y", "3Y", "5Y", or "10Y"
            param_set_id: Parameter set UUID (defaults to base_case for ratio metrics)
            start_year: Optional start year filter
            end_year: Optional end year filter
        
        Returns:
            RatioMetricsResponse with time-series data
        
        Raises:
            ValueError: If metric not found or parameters invalid
        """
        
        # Step 1: Validate metric exists
        if metric_id not in self.metric_config:
            raise ValueError(
                f"Unknown metric: {metric_id}. Available metrics: {', '.join(self.metric_config.keys())}"
            )
        
        metric_def = self.metric_config[metric_id]
        
        # Step 2: Validate temporal window
        if temporal_window not in ["1Y", "3Y", "5Y", "10Y"]:
            raise ValueError(f"Invalid temporal window: {temporal_window}. Must be 1Y, 3Y, 5Y, or 10Y")
        
        logger.info(f"Calculating {metric_id} for tickers {tickers}, window={temporal_window}")
        
        # Step 3: Route to appropriate calculator based on formula_type
        if metric_def.formula_type == "revenue_growth":
            return await self._calculate_revenue_growth(
                metric_def=metric_def,
                tickers=tickers,
                dataset_id=dataset_id,
                temporal_window=temporal_window,
                start_year=start_year,
                end_year=end_year
            )
        elif metric_def.formula_type == "ee_growth":
            return await self._calculate_ee_growth(
                metric_def=metric_def,
                tickers=tickers,
                dataset_id=dataset_id,
                temporal_window=temporal_window,
                param_set_id=param_set_id,
                start_year=start_year,
                end_year=end_year
            )
        elif metric_def.formula_type == "ep_growth":
            return await self._calculate_ep_growth(
                metric_def=metric_def,
                tickers=tickers,
                dataset_id=dataset_id,
                temporal_window=temporal_window,
                param_set_id=param_set_id,
                start_year=start_year,
                end_year=end_year
            )
        else:
            # Standard ratio metric (ratio or complex_ratio)
            return await self._calculate_ratio_metric_internal(
                metric_def=metric_def,
                tickers=tickers,
                dataset_id=dataset_id,
                temporal_window=temporal_window,
                param_set_id=param_set_id,
                start_year=start_year,
                end_year=end_year
            )
    
    async def calculate_ratio_metric_multi_window(
        self,
        metric_id: str,
        tickers: List[str],
        dataset_id: UUID,
        temporal_windows: List[str],
        param_set_id: Optional[UUID] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> RatioMetricsMultiWindowResponse:
        """
        Calculate a ratio metric for given tickers across multiple temporal windows.
        
        Args:
            metric_id: Metric identifier (e.g., 'mb_ratio', 'revenue_growth')
            tickers: List of stock tickers
            dataset_id: Dataset UUID
            temporal_windows: List of temporal windows (e.g., ["1Y", "3Y", "5Y"])
            param_set_id: Parameter set UUID (defaults to base_case for ratio metrics)
            start_year: Optional start year filter
            end_year: Optional end year filter
        
        Returns:
            RatioMetricsMultiWindowResponse with time-series data for each window
        
        Raises:
            ValueError: If metric not found or no valid windows provided
        """
        
        # Step 1: Validate metric exists
        if metric_id not in self.metric_config:
            raise ValueError(
                f"Unknown metric: {metric_id}. Available metrics: {', '.join(self.metric_config.keys())}"
            )
        
        metric_def = self.metric_config[metric_id]
        
        # Step 2: Validate and filter temporal windows
        valid_windows = ["1Y", "3Y", "5Y", "10Y"]
        requested_windows = [w.strip().upper() for w in temporal_windows]
        
        # Track invalid windows for logging
        invalid_windows = [w for w in requested_windows if w not in valid_windows]
        valid_requested_windows = [w for w in requested_windows if w in valid_windows]
        
        if invalid_windows:
            logger.warning(f"Skipping invalid temporal windows: {invalid_windows}")
        
        if not valid_requested_windows:
            raise ValueError(
                f"No valid temporal windows provided. Valid options: {', '.join(valid_windows)}"
            )
        
        logger.info(f"Calculating {metric_id} for tickers {tickers}, windows={valid_requested_windows}")
        
        # Step 3: Calculate metric for each valid window
        window_results = []
        
        for window in valid_requested_windows:
            try:
                # Reuse existing single-window calculation logic
                single_response = await self.calculate_ratio_metric(
                    metric_id=metric_id,
                    tickers=tickers,
                    dataset_id=dataset_id,
                    temporal_window=window,
                    param_set_id=param_set_id,
                    start_year=start_year,
                    end_year=end_year
                )
                
                # Extract ticker data from single-window response
                window_data = WindowData(
                    temporal_window=window,
                    tickers=single_response.data
                )
                window_results.append(window_data)
                
            except Exception as e:
                logger.error(f"Error calculating window {window} for {metric_id}: {str(e)}")
                # Continue with next window instead of failing entire request
                continue
        
        if not window_results:
            raise ValueError(f"Failed to calculate {metric_id} for any of the requested windows")
        
        # Step 4: Build multi-window response
        return RatioMetricsMultiWindowResponse(
            metric=metric_def.id,
            display_name=metric_def.display_name,
            temporal_windows=[w.temporal_window for w in window_results],
            data=window_results
        )
    
    async def _calculate_revenue_growth(
        self,
        metric_def: MetricDefinition,
        tickers: List[str],
        dataset_id: UUID,
        temporal_window: str,
        start_year: Optional[int],
        end_year: Optional[int]
    ) -> RatioMetricsResponse:
        """Calculate revenue growth metric"""
        
        # Build SQL query using revenue growth calculator
        calculator = RevenueGrowthCalculator(metric_def, temporal_window)
        sql_query, params = calculator.build_query(
            tickers=tickers,
            dataset_id=dataset_id,
            start_year=start_year,
            end_year=end_year
        )
        
        logger.debug(f"Revenue Growth SQL:\n{sql_query}")
        logger.debug(f"Revenue Growth params: {params}")
        
        # Execute query
        results = await self.revenue_growth_repo.execute_revenue_growth_query(sql_query, params)
        
        # Format results: convert revenue_growth -> value for consistent response format
        formatted_results = [
            {
                "ticker": row["ticker"],
                "fiscal_year": row["fiscal_year"],
                "value": row["revenue_growth"]
            }
            for row in results
        ]
        
        # Format response
        return self._format_response(metric_def, temporal_window, formatted_results)
    
    async def _calculate_ee_growth(
        self,
        metric_def: MetricDefinition,
        tickers: List[str],
        dataset_id: UUID,
        temporal_window: str,
        param_set_id: Optional[UUID],
        start_year: Optional[int],
        end_year: Optional[int]
    ) -> RatioMetricsResponse:
        """Calculate EE growth metric"""
        
        # Resolve param_set_id if needed
        if param_set_id is None:
            param_set_id = await self._get_default_param_set_id()
            if param_set_id is None:
                raise ValueError("No parameter set ID provided and no default parameter set found")
        
        # Build SQL query using EE growth calculator
        calculator = EEGrowthCalculator(metric_def, temporal_window)
        sql_query, params = calculator.build_query(
            tickers=tickers,
            dataset_id=dataset_id,
            param_set_id=param_set_id,
            start_year=start_year,
            end_year=end_year
        )
        
        logger.debug(f"EE Growth SQL:\n{sql_query}")
        logger.debug(f"EE Growth params: {params}")
        
        # Execute query
        results = await self.ee_growth_repo.execute_ee_growth_query(sql_query, params)
        
        # Format results: convert ee_growth -> value for consistent response format
        formatted_results = [
            {
                "ticker": row["ticker"],
                "fiscal_year": row["fiscal_year"],
                "value": row["ee_growth"]
            }
            for row in results
        ]
        
        # Format response
        return self._format_response(metric_def, temporal_window, formatted_results)
    
    async def _calculate_ep_growth(
        self,
        metric_def: MetricDefinition,
        tickers: List[str],
        dataset_id: UUID,
        temporal_window: str,
        param_set_id: Optional[UUID],
        start_year: Optional[int],
        end_year: Optional[int]
    ) -> RatioMetricsResponse:
        """Calculate EP growth metric"""
        
        # Resolve param_set_id if needed
        if param_set_id is None:
            param_set_id = await self._get_default_param_set_id()
            if param_set_id is None:
                raise ValueError("No parameter set ID provided and no default parameter set found")
        
        # Build SQL query using EP growth calculator
        calculator = EPGrowthCalculator(metric_def, temporal_window)
        sql_query, params = calculator.build_query(
            tickers=tickers,
            dataset_id=dataset_id,
            param_set_id=param_set_id,
            start_year=start_year,
            end_year=end_year
        )
        
        logger.debug(f"EP Growth SQL:\n{sql_query}")
        logger.debug(f"EP Growth params: {params}")
        
        # Execute query
        results = await self.ep_growth_repo.execute_ep_growth_query(sql_query, params)
        
        # Format results: convert ep_growth -> value for consistent response format
        formatted_results = [
            {
                "ticker": row["ticker"],
                "fiscal_year": row["fiscal_year"],
                "value": row["ep_growth"]
            }
            for row in results
        ]
        
        # Format response
        return self._format_response(metric_def, temporal_window, formatted_results)
    
    async def _calculate_ratio_metric_internal(
        self,
        metric_def: MetricDefinition,
        tickers: List[str],
        dataset_id: UUID,
        temporal_window: str,
        param_set_id: Optional[UUID],
        start_year: Optional[int],
        end_year: Optional[int]
    ) -> RatioMetricsResponse:
        """Calculate standard ratio metric"""
        
        # Resolve param_set_id if needed
        if param_set_id is None:
            param_set_id = await self._get_default_param_set_id()
            if param_set_id is None:
                raise ValueError("No parameter set ID provided and no default parameter set found")
        
        # Build SQL query
        calculator = RatioMetricsCalculator(metric_def, temporal_window)
        sql_query, params = calculator.build_query(
            tickers=tickers,
            dataset_id=dataset_id,
            param_set_id=param_set_id,
            start_year=start_year,
            end_year=end_year
        )
        
        logger.debug(f"Ratio Metric SQL:\n{sql_query}")
        
        # Execute query
        results = await self.ratio_repo.execute_ratio_query(sql_query, params)
        
        # Format response
        return self._format_response(metric_def, temporal_window, results)
    
    def _format_response(
        self,
        metric_def: MetricDefinition,
        temporal_window: str,
        results: List[Dict[str, Any]]
    ) -> RatioMetricsResponse:
        """Format raw query results into response object"""
        
        # Group results by ticker
        ticker_data_map: Dict[str, List[TimeSeries]] = {}
        
        for row in results:
            ticker = row["ticker"]
            fiscal_year = row["fiscal_year"]
            value = row["value"]
            
            if ticker not in ticker_data_map:
                ticker_data_map[ticker] = []
            
            ticker_data_map[ticker].append(
                TimeSeries(year=fiscal_year, value=value)
            )
        
        # Sort time-series data by year
        for ticker in ticker_data_map:
            ticker_data_map[ticker].sort(key=lambda x: x.year)
        
        # Build response
        data = [
            TickerData(ticker=ticker, time_series=time_series)
            for ticker, time_series in ticker_data_map.items()
        ]
        
        return RatioMetricsResponse(
            metric=metric_def.id,
            display_name=metric_def.display_name,
            temporal_window=temporal_window,
            data=data
        )
