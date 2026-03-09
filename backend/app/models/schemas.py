# ============================================================================
# Pydantic Request/Response Models (Schemas)
# ============================================================================
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime


# ============================================================================
# L1 Metrics (existing)
# ============================================================================

class CalculateMetricsRequest(BaseModel):
    """Request to calculate a metric"""
    dataset_id: UUID = Field(..., description="UUID of the dataset to calculate metrics for")
    metric_name: str = Field(..., description="Name of the metric to calculate (e.g., 'Calc MC', 'ECF', 'FY_TSR')")
    param_set_id: Optional[UUID] = Field(None, description="Optional parameter set ID for parameter-sensitive metrics (FY_TSR, FY_TSR_PREL). If not provided, uses default.")


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


# ============================================================================
# L2 Metrics (new)
# ============================================================================

class CalculateL2Request(BaseModel):
    """Request to calculate L2 metrics for a dataset and parameter set."""
    dataset_id: UUID = Field(..., description="UUID of the dataset to calculate L2 metrics for")
    param_set_id: UUID = Field(
        ..., 
        description="UUID of the parameter set (defines risk premium, country, etc.)"
    )


class L2MetricResultItem(BaseModel):
    """Single L2 metric result (ticker, fiscal_year, metric_name, value)."""
    ticker: str
    fiscal_year: int
    metric_name: str
    value: float


class CalculateL2Response(BaseModel):
    """Response from L2 metric calculation."""
    model_config = ConfigDict(from_attributes=True)
    
    dataset_id: UUID
    param_set_id: UUID
    results_count: int
    results: list[L2MetricResultItem] = Field(default_factory=list)
    status: str = Field(default="success", description="Status: 'success' or 'error'")
    message: Optional[str] = Field(default=None, description="Error message if status is 'error'")


class MetricsOutputResponse(BaseModel):
    """Response model for a single metrics_output record."""
    model_config = ConfigDict(from_attributes=True)
    
    metrics_output_id: int
    dataset_id: UUID
    param_set_id: UUID
    ticker: str
    fiscal_year: int
    output_metric_name: str
    output_metric_value: float
    created_at: datetime


# ============================================================================
# L3 Enhanced Metrics (Phase 3)
# ============================================================================

class CalculateEnhancedMetricsRequest(BaseModel):
    """Request to calculate enhanced metrics (Beta, Rf, KE, EP, TSR, ratios)."""
    dataset_id: UUID = Field(..., description="UUID of the dataset")
    param_set_id: UUID = Field(..., description="UUID of the parameter set")


class EnhancedMetricResultItem(BaseModel):
    """Single enhanced metric result."""
    ticker: str
    fiscal_year: int
    metric_name: str
    value: float


class CalculateEnhancedMetricsResponse(BaseModel):
    """Response from enhanced metrics calculation."""
    model_config = ConfigDict(from_attributes=True)
    
    dataset_id: UUID
    param_set_id: UUID
    results_count: int
    metrics_calculated: list[str] = Field(default_factory=list)
    status: str = Field(default="success")
    message: Optional[str] = Field(default=None)


# ============================================================================
# Phase 07: Beta Calculation (Phase 07)
# ============================================================================

class CalculateBetaRequest(BaseModel):
    """Request to calculate beta for a dataset and parameter set."""
    dataset_id: UUID = Field(..., description="UUID of the dataset to calculate beta for")
    param_set_id: UUID = Field(
        ..., 
        description="UUID of the parameter set (defines beta calculation parameters)"
    )


class BetaResultItem(BaseModel):
    """Single beta result (ticker, fiscal_year, value)."""
    ticker: str
    fiscal_year: int
    value: float


class CalculateBetaResponse(BaseModel):
    """Response from beta calculation."""
    model_config = ConfigDict(from_attributes=True)
    
    dataset_id: UUID
    param_set_id: UUID
    results_count: int
    results: list[BetaResultItem] = Field(default_factory=list)
    status: str = Field(default="success", description="Status: 'success', 'error', or 'cached'")
    message: Optional[str] = Field(default=None, description="Message or error detail")
