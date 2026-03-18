"""
Unit tests for EP Growth SQL query generation

Tests the EPGrowthCalculator without requiring database connection.
"""
import pytest
from uuid import UUID
from backend.app.services.ep_growth_calculator import EPGrowthCalculator
from backend.app.models.ratio_metrics import MetricDefinition, MetricSource


# Sample metric definition for ep_growth
EP_GROWTH_METRIC = MetricDefinition(
    id="ep_growth",
    display_name="EP Growth",
    description="Year-over-year EP growth",
    formula_type="ep_growth",
    metric_name="Calc EP",
    metric_source=MetricSource.METRICS_OUTPUTS,
    data_source="metrics_outputs",
    data_source_field="output_metric_value",
    parameter_dependent=True,
    requires_prior_year=True,
    operation="growth",
    null_handling="skip_year",
    negative_handling="use_absolute"
)

TEST_DATASET_ID = UUID("12345678-1234-5678-1234-567812345678")
TEST_PARAM_SET_ID = UUID("87654321-4321-8765-4321-876543218765")


class TestEPGrowthCalculator:
    """Test SQL query generation for EP growth"""
    
    def test_calculator_initialization_1y(self):
        """Test calculator initializes correctly for 1Y window"""
        calc = EPGrowthCalculator(EP_GROWTH_METRIC, "1Y")
        assert calc.temporal_window == "1Y"
        assert calc.rows_between == "0"
    
    def test_calculator_initialization_3y(self):
        """Test calculator initializes correctly for 3Y window"""
        calc = EPGrowthCalculator(EP_GROWTH_METRIC, "3Y")
        assert calc.temporal_window == "3Y"
        assert calc.rows_between == "2"
    
    def test_calculator_initialization_5y(self):
        """Test calculator initializes correctly for 5Y window"""
        calc = EPGrowthCalculator(EP_GROWTH_METRIC, "5Y")
        assert calc.temporal_window == "5Y"
        assert calc.rows_between == "4"
    
    def test_calculator_initialization_10y(self):
        """Test calculator initializes correctly for 10Y window"""
        calc = EPGrowthCalculator(EP_GROWTH_METRIC, "10Y")
        assert calc.temporal_window == "10Y"
        assert calc.rows_between == "9"
    
    def test_build_query_1y_single_ticker(self):
        """Test SQL query generation for 1Y with single ticker"""
        calc = EPGrowthCalculator(EP_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["BHP"],
            dataset_id=TEST_DATASET_ID,
            param_set_id=TEST_PARAM_SET_ID
        )
        
        # Verify query structure (normalize whitespace)
        sql_normalized = " ".join(sql.split())
        assert "WITH ep_data AS" in sql_normalized
        assert "ee_data AS" in sql_normalized
        assert "ep_rolling AS" in sql_normalized
        assert "ee_with_lag AS" in sql_normalized
        assert "ee_rolling_lag AS" in sql_normalized
        assert "ep_with_prior_ee AS" in sql_normalized
        assert "LAG(ee) OVER" in sql_normalized
        assert "ROWS BETWEEN" in sql_normalized
        assert "ORDER BY ticker, fiscal_year" in sql_normalized
        
        # Verify parameters
        assert params["dataset_id"] == str(TEST_DATASET_ID)
        assert params["param_set_id"] == str(TEST_PARAM_SET_ID)
        assert params["ep_metric_name"] == "Calc EP"
        assert params["ee_metric_name"] == "Calc EE"
        assert params["tickers"] == ["BHP"]
        assert params["rows_between"] == 0  # 1Y = no preceding rows
    
    def test_build_query_3y_multiple_tickers(self):
        """Test SQL query generation for 3Y with multiple tickers"""
        calc = EPGrowthCalculator(EP_GROWTH_METRIC, "3Y")
        sql, params = calc.build_query(
            tickers=["BHP", "CSL", "MQG"],
            dataset_id=TEST_DATASET_ID,
            param_set_id=TEST_PARAM_SET_ID
        )
        
        # Verify rolling average for 3Y (normalize whitespace)
        sql_normalized = " ".join(sql.split())
        assert "ROWS BETWEEN :rows_between PRECEDING AND CURRENT ROW" in sql_normalized
        
        # Verify parameters
        assert params["rows_between"] == 2  # 3Y = 2 preceding rows
        assert params["tickers"] == ["BHP", "CSL", "MQG"]
    
    def test_build_query_with_year_filters(self):
        """Test SQL query generation with year filtering"""
        calc = EPGrowthCalculator(EP_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["BHP"],
            dataset_id=TEST_DATASET_ID,
            param_set_id=TEST_PARAM_SET_ID,
            start_year=2005,
            end_year=2010
        )
        
        # Verify year filtering is in query
        sql_normalized = " ".join(sql.split())
        assert "fiscal_year >= :start_year" in sql_normalized
        assert "fiscal_year <= :end_year" in sql_normalized
        
        # Verify year parameters
        assert params["start_year"] == 2005
        assert params["end_year"] == 2010
    
    def test_build_query_5y_window(self):
        """Test SQL query generation for 5Y window"""
        calc = EPGrowthCalculator(EP_GROWTH_METRIC, "5Y")
        sql, params = calc.build_query(
            tickers=["BHP"],
            dataset_id=TEST_DATASET_ID,
            param_set_id=TEST_PARAM_SET_ID
        )
        
        # Verify 5Y rolling window
        assert params["rows_between"] == 4  # 5Y = 4 preceding rows
        sql_normalized = " ".join(sql.split())
        assert "ROWS BETWEEN 4 PRECEDING AND CURRENT ROW" in sql_normalized or ":rows_between" in sql_normalized
    
    def test_build_query_10y_window(self):
        """Test SQL query generation for 10Y window"""
        calc = EPGrowthCalculator(EP_GROWTH_METRIC, "10Y")
        sql, params = calc.build_query(
            tickers=["BHP"],
            dataset_id=TEST_DATASET_ID,
            param_set_id=TEST_PARAM_SET_ID
        )
        
        # Verify 10Y rolling window
        assert params["rows_between"] == 9  # 10Y = 9 preceding rows
    
    def test_query_formula_structure(self):
        """Test that query includes proper EP growth formula"""
        calc = EPGrowthCalculator(EP_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["BHP"],
            dataset_id=TEST_DATASET_ID,
            param_set_id=TEST_PARAM_SET_ID
        )
        
        # Verify the EP growth formula is present
        sql_normalized = " ".join(sql.split())
        # Formula: ep_rolling_avg / ABS(prior_year_avg_ee)
        assert "ep_rolling_avg / ABS(prior_year_avg_ee)" in sql_normalized
        # NULL handling
        assert "WHEN prior_year_avg_ee IS NULL THEN NULL" in sql_normalized
        assert "WHEN ABS(prior_year_avg_ee) = 0 THEN NULL" in sql_normalized
    
    def test_query_left_join_for_ee_data(self):
        """Test that query uses LEFT JOIN for EE data (optional for Calc Incl check)"""
        calc = EPGrowthCalculator(EP_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["BHP"],
            dataset_id=TEST_DATASET_ID,
            param_set_id=TEST_PARAM_SET_ID
        )
        
        # Verify LEFT JOIN is used to handle missing EE values
        sql_normalized = " ".join(sql.split())
        assert "LEFT JOIN ee_rolling" in sql_normalized


class TestEPGrowthCalculatorEdgeCases:
    """Test edge cases for EP growth calculator"""
    
    def test_invalid_temporal_window_defaults_to_1y(self):
        """Test that invalid window defaults to 1Y behavior"""
        calc = EPGrowthCalculator(EP_GROWTH_METRIC, "INVALID")
        # Should default to "0" (1Y equivalent)
        assert calc.rows_between == "0"
    
    def test_uuid_conversion_to_string(self):
        """Test that UUIDs are properly converted to strings in params"""
        calc = EPGrowthCalculator(EP_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["BHP"],
            dataset_id=TEST_DATASET_ID,
            param_set_id=TEST_PARAM_SET_ID
        )
        
        # Verify UUIDs are strings
        assert isinstance(params["dataset_id"], str)
        assert isinstance(params["param_set_id"], str)
        assert params["dataset_id"] == str(TEST_DATASET_ID)
        assert params["param_set_id"] == str(TEST_PARAM_SET_ID)
    
    def test_rows_between_is_integer_in_params(self):
        """Test that rows_between is converted to integer for SQL"""
        calc = EPGrowthCalculator(EP_GROWTH_METRIC, "3Y")
        sql, params = calc.build_query(
            tickers=["BHP"],
            dataset_id=TEST_DATASET_ID,
            param_set_id=TEST_PARAM_SET_ID
        )
        
        # Verify rows_between is integer (for SQL parameter binding)
        assert isinstance(params["rows_between"], int)
        assert params["rows_between"] == 2
