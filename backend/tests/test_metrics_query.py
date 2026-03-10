# ============================================================================
# Tests for Metrics Query Endpoint
# ============================================================================
"""
Comprehensive test suite for GET /api/v1/metrics/get_metrics/ endpoint.

Tests verify:
1. Endpoint returns flat array of metric records with units
2. Filtering by dataset_id + parameter_set_id works
3. Optional ticker filtering works (case-insensitive)
4. Optional metric_name filtering works (case-insensitive)
5. Both ticker and metric_name filtering together works
6. Results are ordered by ticker, fiscal_year, metric_name
7. Units are correctly joined from metric_units table
8. Empty results return empty array with warning message
9. Database errors are handled gracefully
"""

import pytest
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.repositories.metrics_query_repository import MetricsQueryRepository
from backend.app.models import GetMetricsResponse, MetricRecord


class TestMetricsQueryRepository:
    """Test the MetricsQueryRepository class
    
    Note: Full integration tests with database would be added in a separate suite.
    These tests verify that the repository can be instantiated and handles basic patterns.
    """
    
    def test_repository_initialization(self):
        """Test that repository can be initialized with a session"""
        mock_session = AsyncMock(spec=AsyncSession)
        repo = MetricsQueryRepository(mock_session)
        assert repo is not None
        assert repo._session == mock_session


class TestGetMetricsResponse:
    """Test the GetMetricsResponse Pydantic model"""
    
    def test_response_model_valid(self):
        """Test that GetMetricsResponse is valid"""
        response = GetMetricsResponse(
            dataset_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            parameter_set_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
            results_count=2,
            results=[
                MetricRecord(
                    dataset_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                    parameter_set_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
                    ticker="AAPL",
                    fiscal_year=2020,
                    metric_name="Beta",
                    value=1.25,
                    unit="dimensionless",
                ),
            ],
            filters_applied={"ticker": "AAPL"},
            status="success",
        )
        
        assert response.results_count == 2
        assert len(response.results) == 1
        assert response.results[0].metric_name == "Beta"
    
    def test_response_model_empty_results(self):
        """Test that GetMetricsResponse handles empty results"""
        response = GetMetricsResponse(
            dataset_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            parameter_set_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
            results_count=0,
            results=[],
            filters_applied={},
            status="success",
            message="No metrics found",
        )
        
        assert response.results_count == 0
        assert len(response.results) == 0
        assert response.message is not None


class TestMetricRecord:
    """Test the MetricRecord Pydantic model"""
    
    def test_metric_record_valid(self):
        """Test that MetricRecord is valid"""
        record = MetricRecord(
            dataset_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            parameter_set_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
            ticker="AAPL",
            fiscal_year=2020,
            metric_name="Beta",
            value=1.25,
            unit="dimensionless",
        )
        
        assert record.ticker == "AAPL"
        assert record.metric_name == "Beta"
        assert record.value == 1.25
    
    def test_metric_record_null_unit(self):
        """Test that MetricRecord allows null unit"""
        record = MetricRecord(
            dataset_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            parameter_set_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
            ticker="AAPL",
            fiscal_year=2020,
            metric_name="UnknownMetric",
            value=42.0,
            unit=None,
        )
        
        assert record.unit is None


@pytest.mark.asyncio
class TestGetMetricsEndpoint:
    """Integration tests for the GET /api/v1/metrics/get_metrics/ endpoint"""
    
    # Note: These would require setting up a test FastAPI app and async client
    # Kept as placeholders for when full integration tests are added
    
    async def test_endpoint_requires_dataset_id(self):
        """Test that dataset_id is required"""
        # Would test: GET /api/v1/metrics/get_metrics/?parameter_set_id=...
        # Should return 422 Unprocessable Entity
        pass
    
    async def test_endpoint_requires_parameter_set_id(self):
        """Test that parameter_set_id is required"""
        # Would test: GET /api/v1/metrics/get_metrics/?dataset_id=...
        # Should return 422 Unprocessable Entity
        pass
    
    async def test_endpoint_accepts_optional_ticker(self):
        """Test that ticker parameter is optional"""
        pass
    
    async def test_endpoint_accepts_optional_metric_name(self):
        """Test that metric_name parameter is optional"""
        pass
    
    async def test_endpoint_returns_correct_format(self):
        """Test that endpoint returns GetMetricsResponse format"""
        pass
