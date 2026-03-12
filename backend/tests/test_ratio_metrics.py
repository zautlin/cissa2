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
        
        # Verify parameters (converted to strings for SQL)
        assert params["start_year"] == "2015"
        assert params["end_year"] == "2023"
    
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

    def test_non_op_cost_margin_mixed_source_query_generation(self):
        """Test SQL query generation for mixed-source simple ratio (Non-Operating Cost Margin)"""
        metric_def = MetricDefinition(
            id="non_op_cost_margin",
            display_name="Non-Operating Cost Margin",
            description="Test",
            formula_type="ratio",
            numerator=MetricComponent(
                metric_name="Calc Non Op Cost",
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
        assert params["numerator_metric"] == "Calc Non Op Cost"
        assert params["denominator_metric"] == "REVENUE"
        assert params["ticker_0"] == "BHP"
        
        # Verify param_set_id is in SQL (for numerator from metrics_outputs)
        assert "param_set_id = :param_set_id" in sql

    def test_etr_composite_denominator_query_generation(self):
        """Test SQL query generation for Effective Tax Rate with composite denominator"""
        metric_def = MetricDefinition(
            id="etr",
            display_name="Effective Tax Rate",
            description="Test",
            formula_type="complex_ratio",
            numerator=MetricComponent(
                metric_name="Calc Tax Cost",
                metric_source=MetricSource.METRICS_OUTPUTS,
                parameter_dependent=True
            ),
            denominator=MetricComponent(
                metric_name="PROFIT_AFTER_TAX_EX",
                metric_source=MetricSource.FUNDAMENTALS,
                parameter_dependent=False,
                operation="add",
                operand_metric_name="Calc XO Cost",
                operand_metric_source=MetricSource.METRICS_OUTPUTS,
                operand_parameter_dependent=True,
                apply_absolute_value=True
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
        
        # Verify SQL structure for composite denominator
        assert "denominator_main_raw" in sql
        assert "denominator_operand_raw" in sql
        assert "denominator_combined" in sql
        assert "denominator_rolling" in sql
        
        # Verify composite operation (add)
        assert "+" in sql  # Addition operator
        assert "ABS(" in sql  # Absolute value wrapper
        
        # Verify multiple CTEs are used
        assert "numerator_rolling" in sql
        assert "FULL OUTER JOIN" in sql
        
        # Verify both fundamentals and metrics_outputs are queried
        assert "cissa.fundamentals" in sql
        assert "cissa.metrics_outputs" in sql
        
        # Verify column names from different sources
        assert "output_metric_value" in sql  # From metrics_outputs
        assert "numeric_value" in sql  # From fundamentals
        assert "output_metric_name" in sql  # numerator metric name
        assert "metric_name" in sql  # denominator metric name
        
        # Verify parameters
        assert params["dataset_id"] == str(dataset_id)
        assert params["param_set_id"] == str(param_set_id)
        assert params["numerator_metric"] == "Calc Tax Cost"
        assert params["denominator_metric"] == "PROFIT_AFTER_TAX_EX"
        assert params["operand_metric"] == "Calc XO Cost"
        assert params["ticker_0"] == "BHP"
        
        # Verify param_set_id is in SQL at least once (for operand: Calc XO Cost from metrics_outputs)
        # Note: numerator is Calc Tax Cost from metrics_outputs, and operand is Calc XO Cost from metrics_outputs
        # Both should use param_set_id, so we should see it in the operand_raw CTE
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
