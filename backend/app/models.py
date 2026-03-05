# ============================================================================
# Pydantic Request/Response Models
# ============================================================================
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class CalculateMetricsRequest(BaseModel):
    """Request to calculate a metric"""
    dataset_id: UUID = Field(..., description="UUID of the dataset to calculate metrics for")
    metric_name: str = Field(..., description="Name of the metric to calculate (e.g., 'Calc MC', 'Calc Assets')")


class MetricResultItem(BaseModel):
    """Single metric result (ticker, fiscal_year, value)"""
    ticker: str
    fiscal_year: int
    value: float


class CalculateMetricsResponse(BaseModel):
    """Response from metric calculation"""
    dataset_id: UUID
    metric_name: str
    results_count: int
    results: list[MetricResultItem] = Field(default_factory=list)
    status: str = Field(default="success", description="Status: 'success' or 'error'")
    message: Optional[str] = Field(default=None, description="Error message if status is 'error'")


class MetricsHealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(default="ok")
    message: str = Field(default="Metrics service is running")
    database: str = Field(default="connected")
