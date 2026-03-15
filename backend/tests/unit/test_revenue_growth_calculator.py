"""
Unit tests for Revenue Growth SQL query generation

Tests the RevenueGrowthCalculator without requiring database connection.
"""
import pytest
from uuid import UUID
from backend.app.services.revenue_growth_calculator import RevenueGrowthCalculator
from backend.app.models.ratio_metrics import MetricDefinition, MetricSource


# Sample metric definition for revenue_growth
REVENUE_GROWTH_METRIC = MetricDefinition(
    id="revenue_growth",
    display_name="Revenue Growth",
    description="Year-over-year revenue growth",
    formula_type="revenue_growth",
    metric_name="REVENUE",
    metric_source=MetricSource.FUNDAMENTALS,
    data_source="fundamentals",
    data_source_field="numeric_value",
    parameter_dependent=False,
    requires_prior_year=True,
    operation="growth",
    null_handling="skip_year",
    negative_handling="use_absolute"
)

TEST_DATASET_ID = UUID("12345678-1234-5678-1234-567812345678")


class TestRevenueGrowthCalculator:
    """Test SQL query generation for revenue growth"""
    
    def test_calculator_initialization_1y(self):
        """Test calculator initializes correctly for 1Y window"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "1Y")
        assert calc.temporal_window == "1Y"
        assert calc.rows_between == "0"
    
    def test_calculator_initialization_3y(self):
        """Test calculator initializes correctly for 3Y window"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "3Y")
        assert calc.temporal_window == "3Y"
        assert calc.rows_between == "2"
    
    def test_calculator_initialization_5y(self):
        """Test calculator initializes correctly for 5Y window"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "5Y")
        assert calc.temporal_window == "5Y"
        assert calc.rows_between == "4"
    
    def test_calculator_initialization_10y(self):
        """Test calculator initializes correctly for 10Y window"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "10Y")
        assert calc.temporal_window == "10Y"
        assert calc.rows_between == "9"
    
    def test_build_query_1y_single_ticker(self):
        """Test SQL query generation for 1Y with single ticker"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=TEST_DATASET_ID
        )
        
        # Verify query structure (normalize whitespace)
        sql_normalized = " ".join(sql.split())
        assert "WITH revenue_data AS" in sql_normalized
        assert "revenue_rolling AS" in sql_normalized
        assert "revenue_with_lag AS" in sql_normalized
        assert "LAG(revenue_rolling_avg) OVER" in sql_normalized
        assert "ROWS BETWEEN" in sql_normalized
        assert "ORDER BY ticker, fiscal_year" in sql_normalized
        
        # Verify parameters
        assert params["dataset_id"] == str(TEST_DATASET_ID)
        assert params["metric_name"] == "REVENUE"
        assert params["tickers"] == ["CSL"]
        assert params["rows_between"] == 0  # 1Y = no preceding rows
    
    def test_build_query_3y_multiple_tickers(self):
        """Test SQL query generation for 3Y with multiple tickers"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "3Y")
        sql, params = calc.build_query(
            tickers=["CSL", "XYZ", "ABC"],
            dataset_id=TEST_DATASET_ID
        )
        
        # Verify rolling average for 3Y (normalize whitespace)
        sql_normalized = " ".join(sql.split())
        assert "ROWS BETWEEN :rows_between PRECEDING AND CURRENT ROW" in sql_normalized
        
        # Verify parameters
        assert params["rows_between"] == 2  # 3Y = 2 preceding rows
        assert params["tickers"] == ["CSL", "XYZ", "ABC"]
    
    def test_build_query_with_year_filtering(self):
        """Test SQL query generation with year range filtering"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=TEST_DATASET_ID,
            start_year=2010,
            end_year=2020
        )
        
        # Verify WHERE clause is added
        assert "WHERE fiscal_year >= :start_year AND fiscal_year <= :end_year" in sql
        
        # Verify parameters
        assert params["start_year"] == 2010
        assert params["end_year"] == 2020
    
    def test_build_query_with_start_year_only(self):
        """Test SQL query generation with only start_year"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=TEST_DATASET_ID,
            start_year=2015
        )
        
        assert "WHERE fiscal_year >= :start_year" in sql
        assert params["start_year"] == 2015
        assert "end_year" not in params
    
    def test_build_query_with_end_year_only(self):
        """Test SQL query generation with only end_year"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=TEST_DATASET_ID,
            end_year=2020
        )
        
        assert "WHERE fiscal_year <= :end_year" in sql
        assert params["end_year"] == 2020
        assert "start_year" not in params
    
    def test_query_includes_null_handling(self):
        """Test that query includes proper NULL handling"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=TEST_DATASET_ID
        )
        
        # Verify NULL checks for prior year
        assert "WHEN prior_year_avg_revenue IS NULL THEN NULL" in sql
        
        # Verify zero denominator check
        assert "WHEN ABS(prior_year_avg_revenue) = 0 THEN NULL" in sql
        
        # Verify growth calculation
        assert "(revenue_rolling_avg - prior_year_avg_revenue) / ABS(prior_year_avg_revenue)" in sql
    
    def test_query_uses_fundamentals_table(self):
        """Test that query correctly sources from fundamentals"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=TEST_DATASET_ID
        )
        
        # Verify fundamentals table is used
        assert "FROM cissa.fundamentals" in sql
        assert "metric_name = :metric_name" in sql
    
    def test_query_lag_function_usage(self):
        """Test that LAG function is correctly used for year-shift"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=TEST_DATASET_ID
        )
        
        # Verify LAG is used for year-shift (normalize whitespace)
        sql_normalized = " ".join(sql.split())
        assert "LAG(revenue_rolling_avg) OVER" in sql_normalized
        assert "PARTITION BY ticker" in sql_normalized
    
    def test_query_partition_by_ticker(self):
        """Test that window functions properly partition by ticker"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["CSL", "XYZ"],
            dataset_id=TEST_DATASET_ID
        )
        
        # Verify PARTITION BY ticker in window functions
        assert "PARTITION BY ticker" in sql
        # Should appear at least twice (once in AVG OVER, once in LAG OVER)
        assert sql.count("PARTITION BY ticker") >= 2
    
    def test_query_ordering(self):
        """Test that final results are properly ordered"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=TEST_DATASET_ID
        )
        
        # Verify final ordering
        assert "ORDER BY ticker, fiscal_year" in sql


class TestRevenueGrowthSQLStructure:
    """Test the overall SQL structure for correctness"""
    
    def test_complete_cte_chain(self):
        """Test that all CTEs are present and in correct order"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=TEST_DATASET_ID
        )
        
        # Find positions of each CTE
        data_pos = sql.find("WITH revenue_data AS")
        rolling_pos = sql.find("revenue_rolling AS")
        lag_pos = sql.find("revenue_with_lag AS")
        
        # Verify order
        assert data_pos > -1, "revenue_data CTE missing"
        assert rolling_pos > data_pos, "revenue_rolling CTE out of order"
        assert lag_pos > rolling_pos, "revenue_with_lag CTE out of order"
    
    def test_query_syntax_valid(self):
        """Test that generated query has valid SQL syntax structure"""
        calc = RevenueGrowthCalculator(REVENUE_GROWTH_METRIC, "1Y")
        sql, params = calc.build_query(
            tickers=["CSL"],
            dataset_id=TEST_DATASET_ID
        )
        
        # Basic syntax checks
        assert sql.count("SELECT") >= 3, "Should have at least 3 SELECT statements"
        assert ";" in sql, "Query should end with semicolon"
        assert sql.strip().endswith(";"), "Query should end with semicolon"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
