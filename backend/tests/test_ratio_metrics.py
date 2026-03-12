# ============================================================================
# Test Suite for Ratio Metrics
# ============================================================================
import pytest
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.models.ratio_metrics import (
    MetricDefinition,
    RatioMetricsResponse,
    TimeSeries,
    MetricComponent,
    MetricSource
)
from app.services.ratio_metrics_service import RatioMetricsService
from app.services.ratio_metrics_calculator import RatioMetricsCalculator


class TestRatioMetricsCalculator:
    """Test SQL query generation"""
    
    def test_rows_between_mapping(self):
        """Test temporal window to SQL conversion"""
        metric_def = MetricDefinition(
            id="mb_ratio",
            display_name="MB Ratio",
            description="Test",
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
        
        # Test 1Y
        calc = RatioMetricsCalculator(metric_def, "1Y")
        assert "ROWS BETWEEN 0 PRECEDING AND CURRENT ROW" in calc.rows_between
        
        # Test 3Y
        calc = RatioMetricsCalculator(metric_def, "3Y")
        assert "ROWS BETWEEN 2 PRECEDING AND CURRENT ROW" in calc.rows_between
        
        # Test 5Y
        calc = RatioMetricsCalculator(metric_def, "5Y")
        assert "ROWS BETWEEN 4 PRECEDING AND CURRENT ROW" in calc.rows_between
        
        # Test 10Y
        calc = RatioMetricsCalculator(metric_def, "10Y")
        assert "ROWS BETWEEN 9 PRECEDING AND CURRENT ROW" in calc.rows_between
        
        # Test invalid
        with pytest.raises(ValueError):
            RatioMetricsCalculator(metric_def, "2Y")
    
    def test_simple_ratio_query_generation(self):
        """Test SQL query generation for simple ratio"""
        metric_def = MetricDefinition(
            id="mb_ratio",
            display_name="MB Ratio",
            description="Test",
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
        
        calc = RatioMetricsCalculator(metric_def, "3Y")
        
        tickers = ["AAPL", "MSFT"]
        dataset_id = UUID("12345678-1234-1234-1234-123456789012")
        param_set_id = UUID("87654321-4321-4321-4321-210987654321")
        
        sql, params = calc.build_query(tickers, dataset_id, param_set_id)
        
        # Verify SQL structure
        assert "numerator_rolling" in sql
        assert "denominator_rolling" in sql
        assert "FULL OUTER JOIN" in sql
        assert "CASE" in sql
        assert "ROWS BETWEEN 2 PRECEDING AND CURRENT ROW" in sql
        
        # Verify parameters
        assert params["dataset_id"] == str(dataset_id)
        # param_set_id should NOT be in params for MB Ratio since both metrics have parameter_dependent=False
        assert "param_set_id" not in params
        assert params["numerator_metric"] == "Calc MC"
        assert params["denominator_metric"] == "Calc EE"
        assert params["ticker_0"] == "AAPL"
        assert params["ticker_1"] == "MSFT"
    
    def test_query_with_year_filters(self):
        """Test SQL query with start/end year filters"""
        metric_def = MetricDefinition(
            id="mb_ratio",
            display_name="MB Ratio",
            description="Test",
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
        
        calc = RatioMetricsCalculator(metric_def, "1Y")
        
        tickers = ["AAPL"]
        dataset_id = UUID("12345678-1234-1234-1234-123456789012")
        param_set_id = UUID("87654321-4321-4321-4321-210987654321")
        
        sql, params = calc.build_query(
            tickers, dataset_id, param_set_id,
            start_year=2015, end_year=2023
        )
        
        # Verify year filters in query
        assert ">= :start_year" in sql
        assert "<= :end_year" in sql
        
        # Verify parameters
        assert params["start_year"] == 2015
        assert params["end_year"] == 2023
    
    def test_op_cost_margin_mixed_source_query_generation(self):
        """Test SQL query generation for mixed-source simple ratio (Op Cost Margin)"""
        metric_def = MetricDefinition(
            id="op_cost_margin",
            display_name="Operating Cost Margin",
            description="Test",
            formula_type="ratio",
            numerator=MetricComponent(
                metric_name="Calc Op Cost",
                metric_source=MetricSource.METRICS_OUTPUTS,
                parameter_dependent=True
            ),
            denominator=MetricComponent(
                metric_name="REVENUE",
                metric_source=MetricSource.FUNDAMENTALS,
                parameter_dependent=False
            ),
            operation="divide",
            null_handling="skip_year",
            negative_handling="return_null"
        )
        
        calc = RatioMetricsCalculator(metric_def, "1Y")
        
        tickers = ["BHP"]
        dataset_id = UUID("12345678-1234-1234-1234-123456789012")
        param_set_id = UUID("87654321-4321-4321-4321-210987654321")
        
        sql, params = calc.build_query(tickers, dataset_id, param_set_id)
        
        # Verify SQL structure
        assert "numerator_rolling" in sql
        assert "denominator_rolling" in sql
        assert "FULL OUTER JOIN" in sql
        
        # Verify numerator uses metrics_outputs
        assert "cissa.metrics_outputs" in sql
        # Verify denominator uses fundamentals
        assert "cissa.fundamentals" in sql
        
        # Verify mixed column names
        assert "output_metric_value" in sql  # numerator from metrics_outputs
        assert "numeric_value" in sql  # denominator from fundamentals
        assert "output_metric_name" in sql  # numerator metric name
        assert "metric_name" in sql  # denominator metric name (also in fundamentals)
        
        # Verify parameters
        assert params["dataset_id"] == str(dataset_id)
        # param_set_id SHOULD be in params because numerator is parameter_dependent
        assert params["param_set_id"] == str(param_set_id)
        assert params["numerator_metric"] == "Calc Op Cost"
        assert params["denominator_metric"] == "REVENUE"
        assert params["ticker_0"] == "BHP"
        
        # Verify param_set_id is in SQL (for numerator from metrics_outputs)
        assert "param_set_id = :param_set_id" in sql


class TestRatioMetricsService:
    """Test service layer (requires async context)"""
    
    def test_metric_config_loading(self):
        """Test that ratio metrics config loads correctly"""
        # This would require a mock session
        # For now, just verify the config file exists
        from pathlib import Path
        config_path = Path(__file__).parent.parent / "app" / "config" / "ratio_metrics.json"
        assert config_path.exists(), "ratio_metrics.json config file not found"
    
    def test_invalid_metric_raises_error(self):
        """Test that invalid metric ID raises ValueError"""
        import asyncio
        from unittest.mock import AsyncMock
        
        # Mock session
        mock_session = AsyncMock(spec=AsyncSession)
        service = RatioMetricsService(mock_session)
        
        with pytest.raises(ValueError, match="Unknown metric"):
            asyncio.run(service.calculate_ratio_metric(
                metric_id="invalid_metric",
                tickers=["AAPL"],
                dataset_id=UUID("12345678-1234-1234-1234-123456789012")
            ))
    
    def test_invalid_temporal_window_raises_error(self):
        """Test that invalid temporal window raises ValueError"""
        import asyncio
        from unittest.mock import AsyncMock
        
        # Mock session
        mock_session = AsyncMock(spec=AsyncSession)
        service = RatioMetricsService(mock_session)
        
        with pytest.raises(ValueError, match="Invalid temporal window"):
            asyncio.run(service.calculate_ratio_metric(
                metric_id="mb_ratio",
                tickers=["AAPL"],
                dataset_id=UUID("12345678-1234-1234-1234-123456789012"),
                temporal_window="2Y"
            ))


# Integration test (requires running database)
@pytest.mark.asyncio
async def test_mb_ratio_integration():
    """Integration test for MB Ratio calculation against real database"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    # This would connect to actual database and test the full flow
    # Requires DATABASE_URL to be set in .env
    # For now, just document the test structure
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
