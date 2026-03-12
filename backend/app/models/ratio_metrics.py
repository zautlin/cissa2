# ============================================================================
# Pydantic Models for Ratio Metrics
# ============================================================================
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from enum import Enum


class TimeSeries(BaseModel):
    """Single time-series data point"""
    year: int = Field(..., description="Fiscal year")
    value: Optional[float] = Field(None, description="Metric value (NULL if insufficient data)")


class TickerData(BaseModel):
    """Time-series data for a single ticker"""
    ticker: str = Field(..., description="Stock ticker symbol")
    time_series: List[TimeSeries] = Field(..., description="List of annual values")


class RatioMetricsResponse(BaseModel):
    """Response for ratio metrics calculation"""
    metric: str = Field(..., description="Metric ID (e.g., 'mb_ratio')")
    display_name: str = Field(..., description="Human-readable metric name")
    temporal_window: str = Field(..., description="Temporal window (1Y, 3Y, 5Y, 10Y)")
    data: List[TickerData] = Field(..., description="Time-series data per ticker")


class MetricSource(str, Enum):
    """Source of metric data"""
    METRICS_OUTPUTS = "metrics_outputs"
    FUNDAMENTALS = "fundamentals"


class MetricComponent(BaseModel):
    """Represents numerator or denominator component in a ratio"""
    metric_name: str = Field(..., description="Name of the metric")
    metric_source: MetricSource = Field(
        default=MetricSource.METRICS_OUTPUTS,
        description="Source table (metrics_outputs or fundamentals)"
    )
    parameter_dependent: bool = Field(
        default=False,
        description="Whether metric depends on param_set_id"
    )
    year_shift: int = Field(
        default=0,
        description="Number of years to shift (for year-shift ratios like ROEE)"
    )


class MetricDefinition(BaseModel):
    """Metric configuration schema"""
    id: str = Field(..., description="Unique metric identifier")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Metric documentation")
    formula_type: Literal["ratio", "complex_ratio"] = Field(..., description="Formula type")
    numerator: MetricComponent = Field(..., description="Numerator metric")
    denominator: MetricComponent = Field(..., description="Denominator metric")
    operation: str = Field(..., description="Operation to perform (divide, etc.)")
    null_handling: Literal["skip_year", "use_zero"] = Field(..., description="How to handle NULL values")
    negative_handling: Literal["skip_year", "return_null", "use_absolute"] = Field(..., description="How to handle negative values")
