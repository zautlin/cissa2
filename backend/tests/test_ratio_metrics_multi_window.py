# ============================================================================
# Test Suite for Multi-Window Ratio Metrics
# ============================================================================
import pytest
from uuid import UUID
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ratio_metrics import (
    MetricDefinition,
    RatioMetricsResponse,
    RatioMetricsMultiWindowResponse,
    TickerData,
    TimeSeries,
    MetricComponent,
    MetricSource,
    WindowData
)
from app.services.ratio_metrics_service import RatioMetricsService


@pytest.mark.asyncio
class TestRatioMetricsMultiWindow:
    """Test multi-window ratio metrics calculation"""
    
    async def test_calculate_ratio_metric_multi_window(self):
        """Test multi-window metric calculation"""
        
        # Create mock session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create service
        service = RatioMetricsService(mock_session)
        
        # Mock metric config
        metric_def = MetricDefinition(
            id="mb_ratio",
            display_name="MB Ratio",
            description="Market-to-Book Ratio",
            formula_type="ratio",
            numerator=MetricComponent(
                metric_name="Calc MC",
                metric_source=MetricSource.METRICS_OUTPUTS,
                parameter_dependent=False
            ),
            denominator=MetricComponent(
                metric_name="Calc EE",
                metric_source=MetricSource.METRICS_OUTPUTS,
                parameter_dependent=False
            ),
            operation="divide",
            null_handling="skip_year",
            negative_handling="return_null"
        )
        service.metric_config = {"mb_ratio": metric_def}
        
        # Mock single-window responses for each window
        mock_single_response = RatioMetricsResponse(
            metric="mb_ratio",
            display_name="MB Ratio",
            temporal_window="1Y",
            data=[
                TickerData(
                    ticker="AAPL",
                    time_series=[
                        TimeSeries(year=2020, value=1.5),
                        TimeSeries(year=2021, value=1.6)
                    ]
                )
            ]
        )
        
        # Patch calculate_ratio_metric to return mock response
        with patch.object(service, 'calculate_ratio_metric', new_callable=AsyncMock) as mock_calc:
            mock_calc.return_value = mock_single_response
            
            # Call multi-window method
            result = await service.calculate_ratio_metric_multi_window(
                metric_id="mb_ratio",
                tickers=["AAPL"],
                dataset_id=UUID("12345678-1234-5678-1234-567812345678"),
                temporal_windows=["1Y", "3Y"],
                param_set_id=None
            )
        
        # Verify result structure
        assert isinstance(result, RatioMetricsMultiWindowResponse)
        assert result.metric == "mb_ratio"
        assert result.display_name == "MB Ratio"
        assert set(result.temporal_windows) == {"1Y", "3Y"}
        assert len(result.data) == 2
        
        # Verify window data structure
        for window_data in result.data:
            assert isinstance(window_data, WindowData)
            assert window_data.temporal_window in ["1Y", "3Y"]
            assert len(window_data.tickers) > 0
    
    async def test_multi_window_with_invalid_windows(self):
        """Test that invalid windows are skipped and logged"""
        
        # Create mock session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create service
        service = RatioMetricsService(mock_session)
        
        # Mock metric config
        metric_def = MetricDefinition(
            id="mb_ratio",
            display_name="MB Ratio",
            description="Market-to-Book Ratio",
            formula_type="ratio",
            numerator=MetricComponent(
                metric_name="Calc MC",
                metric_source=MetricSource.METRICS_OUTPUTS,
                parameter_dependent=False
            ),
            denominator=MetricComponent(
                metric_name="Calc EE",
                metric_source=MetricSource.METRICS_OUTPUTS,
                parameter_dependent=False
            ),
            operation="divide",
            null_handling="skip_year",
            negative_handling="return_null"
        )
        service.metric_config = {"mb_ratio": metric_def}
        
        # Mock single-window response
        mock_single_response = RatioMetricsResponse(
            metric="mb_ratio",
            display_name="MB Ratio",
            temporal_window="1Y",
            data=[
                TickerData(
                    ticker="AAPL",
                    time_series=[
                        TimeSeries(year=2020, value=1.5)
                    ]
                )
            ]
        )
        
        # Patch calculate_ratio_metric
        with patch.object(service, 'calculate_ratio_metric', new_callable=AsyncMock) as mock_calc:
            mock_calc.return_value = mock_single_response
            
            # Call with mixed valid and invalid windows
            result = await service.calculate_ratio_metric_multi_window(
                metric_id="mb_ratio",
                tickers=["AAPL"],
                dataset_id=UUID("12345678-1234-5678-1234-567812345678"),
                temporal_windows=["1Y", "2Y", "3Y", "invalid"],  # 2Y and invalid are invalid
                param_set_id=None
            )
        
        # Verify only valid windows are in result
        assert set(result.temporal_windows) == {"1Y", "3Y"}
        assert len(result.data) == 2
    
    async def test_multi_window_error_handling(self):
        """Test error handling when all windows fail"""
        
        # Create mock session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create service
        service = RatioMetricsService(mock_session)
        
        # Mock metric config
        metric_def = MetricDefinition(
            id="mb_ratio",
            display_name="MB Ratio",
            description="Market-to-Book Ratio",
            formula_type="ratio",
            numerator=MetricComponent(
                metric_name="Calc MC",
                metric_source=MetricSource.METRICS_OUTPUTS,
                parameter_dependent=False
            ),
            denominator=MetricComponent(
                metric_name="Calc EE",
                metric_source=MetricSource.METRICS_OUTPUTS,
                parameter_dependent=False
            ),
            operation="divide",
            null_handling="skip_year",
            negative_handling="return_null"
        )
        service.metric_config = {"mb_ratio": metric_def}
        
        # Patch calculate_ratio_metric to raise exception
        with patch.object(service, 'calculate_ratio_metric', new_callable=AsyncMock) as mock_calc:
            mock_calc.side_effect = Exception("Database error")
            
            # Call multi-window method - should raise ValueError since all windows fail
            with pytest.raises(ValueError, match="Failed to calculate"):
                await service.calculate_ratio_metric_multi_window(
                    metric_id="mb_ratio",
                    tickers=["AAPL"],
                    dataset_id=UUID("12345678-1234-5678-1234-567812345678"),
                    temporal_windows=["1Y", "3Y"],
                    param_set_id=None
                )
