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
    TickerData,
    TimeSeries
)
from ..repositories.ratio_metrics_repository import RatioMetricsRepository
from ..services.ratio_metrics_calculator import RatioMetricsCalculator
from ..core.config import get_logger

logger = get_logger(__name__)


class RatioMetricsService:
    """Service layer for calculating ratio metrics on-the-fly"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RatioMetricsRepository(session)
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
        Calculate a ratio metric for given tickers and temporal window.
        
        Args:
            metric_id: Metric identifier (e.g., 'mb_ratio')
            tickers: List of stock tickers
            dataset_id: Dataset UUID
            temporal_window: "1Y", "3Y", "5Y", or "10Y"
            param_set_id: Parameter set UUID (defaults to base_case)
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
        
        # Step 3: Resolve param_set_id if needed
        if param_set_id is None:
            param_set_id = await self._get_default_param_set_id()
            if param_set_id is None:
                raise ValueError("No parameter set ID provided and no default parameter set found")
        
        logger.info(f"Calculating {metric_id} for tickers {tickers}, window={temporal_window}")
        
        # Step 4: Build SQL query
        calculator = RatioMetricsCalculator(metric_def, temporal_window)
        sql_query, params = calculator.build_query(
            tickers=tickers,
            dataset_id=dataset_id,
            param_set_id=param_set_id,
            start_year=start_year,
            end_year=end_year
        )
        
        logger.debug(f"Generated SQL query:\n{sql_query}")
        
        # Step 5: Execute query
        results = await self.repo.execute_ratio_query(sql_query, params)
        
        # Step 6: Format response
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
