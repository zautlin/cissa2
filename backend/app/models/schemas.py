# ============================================================================
# Pydantic Request/Response Models (Schemas)
# ============================================================================
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any
from uuid import UUID
from datetime import datetime


# ============================================================================
# L1 Metrics (existing)
# ============================================================================

class CalculateMetricsRequest(BaseModel):
    """Request to calculate a metric"""
    dataset_id: UUID = Field(..., description="UUID of the dataset to calculate metrics for")
    metric_name: str = Field(..., description="Name of the metric to calculate (e.g., 'Calc MC', 'Calc ECF', 'Calc FY TSR')")
    param_set_id: Optional[UUID] = Field(None, description="Optional parameter set ID for parameter-sensitive metrics (Calc FY TSR, Calc FY TSR PREL). If not provided, uses default.")


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
    """Response from enhanced metrics calculation (runtime or pre-computed)."""
    model_config = ConfigDict(from_attributes=True)
    
    dataset_id: UUID
    param_set_id: UUID
    # For runtime calculation
    value: Optional[float] = Field(default=None, description="Calculated metric value (runtime mode)")
    # For pre-computed mode (legacy)
    results_count: Optional[int] = Field(default=None, description="Number of records calculated (pre-compute mode)")
    metrics_calculated: list[str] = Field(default_factory=list)
    status: str = Field(default="success")
    message: Optional[str] = Field(default=None)
    timestamp: Optional[datetime] = Field(default=None, description="Calculation timestamp (runtime mode)")


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


# ============================================================================
# Quick Task 01: Risk-Free Rate Calculation
# ============================================================================

class CalculateRiskFreeRateRequest(BaseModel):
    """Request to calculate risk-free rate (Rf, Rf_1Y, Rf_1Y_Raw) for a dataset and parameter set."""
    dataset_id: UUID = Field(..., description="UUID of the dataset to calculate risk-free rate for")
    param_set_id: UUID = Field(
        ..., 
        description="UUID of the parameter set (defines bond index, rounding, approach, etc.)"
    )


class RiskFreeRateResultItem(BaseModel):
    """Single risk-free rate result (ticker, fiscal_year, metric_name, value)."""
    ticker: str
    fiscal_year: int
    metric_name: str  # 'Rf', 'Rf_1Y', or 'Rf_1Y_Raw'
    value: float


class CalculateRiskFreeRateResponse(BaseModel):
    """Response from risk-free rate calculation (runtime or pre-computed)."""
    model_config = ConfigDict(from_attributes=True)
    
    dataset_id: UUID
    param_set_id: UUID
    # For runtime calculation
    value: Optional[float] = Field(default=None, description="Calculated Rf value (runtime mode)")
    # For pre-computed mode (legacy)
    results_count: Optional[int] = Field(default=None, description="Number of records calculated (pre-compute mode)")
    results: list[RiskFreeRateResultItem] = Field(default_factory=list)
    status: str = Field(default="success", description="Status: 'success', 'error', or 'cached'")
    message: Optional[str] = Field(default=None, description="Message or error detail")
    timestamp: Optional[datetime] = Field(default=None, description="Calculation timestamp (runtime mode)")


# ============================================================================
# Metrics Query/Retrieval
# ============================================================================

class MetricRecord(BaseModel):
    """
    Single metric record returned from metrics query endpoint.
    
    Represents one row from metrics_outputs with unit information joined from metric_units.
    Formatted as a flat array for easy filtering and charting in the UI.
    """
    model_config = ConfigDict(from_attributes=True)
    
    dataset_id: UUID
    parameter_set_id: UUID
    ticker: str
    fiscal_year: int
    metric_name: str
    value: Optional[float] = Field(None, description="Metric value. None if insufficient data or marked as NULL.")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g., 'USD', '%', 'dimensionless'). None if not defined in metric_units table.")


class GetMetricsResponse(BaseModel):
    """Response from metrics query endpoint (/api/v1/metrics/get_metrics/)."""
    model_config = ConfigDict(from_attributes=True)
    
    dataset_id: UUID
    parameter_set_id: UUID
    results_count: int
    results: list[MetricRecord] = Field(default_factory=list)
    filters_applied: dict = Field(default_factory=dict, description="Summary of filters applied to the query")
    status: str = Field(default="success", description="Status: 'success' or 'error'")
    message: Optional[str] = Field(default=None, description="Message or warning detail")


# ============================================================================
# Parameters Management
# ============================================================================

class ParameterUpdateRequest(BaseModel):
    """Request to update one or more parameters."""
    parameters: dict[str, Any] = Field(..., description="Key-value pairs of parameters to update (e.g., {'tax_rate_franking_credits': 0.35, 'beta_rounding': 3})")
    set_as_active: bool = Field(default=False, description="If true, set this parameter set as active")
    set_as_default: bool = Field(default=False, description="If true, set this parameter set as default")


class ParameterSetResponse(BaseModel):
    """Response with merged parameter values (baseline + overrides)."""
    model_config = ConfigDict(from_attributes=True)
    
    param_set_id: UUID = Field(..., description="UUID of the parameter set")
    param_set_name: Optional[str] = Field(None, description="Name of the parameter set")
    is_active: bool = Field(..., description="Whether this is the currently active parameter set")
    is_default: bool = Field(..., description="Whether this is the default parameter set")
    created_at: datetime = Field(..., description="When this parameter set was created")
    updated_at: datetime = Field(..., description="When this parameter set was last updated")
    parameters: dict[str, Any] = Field(..., description="All parameters with merged values (baseline + overrides)")
    status: str = Field(default="success", description="Status: 'success' or 'error'")
    message: Optional[str] = Field(default=None, description="Error message if status is 'error'")


class ParameterSetListResponse(BaseModel):
    """Response with list of parameter sets."""
    model_config = ConfigDict(from_attributes=True)
    
    results_count: int
    results: list[ParameterSetResponse] = Field(default_factory=list)
    status: str = Field(default="success", description="Status: 'success' or 'error'")
    message: Optional[str] = Field(default=None, description="Message or error detail")
