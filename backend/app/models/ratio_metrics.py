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


class OperandComponent(BaseModel):
    """Represents an operand in a composite metric operation"""
    metric_name: str = Field(..., description="Name of the operand metric")
    metric_source: MetricSource = Field(
        default=MetricSource.METRICS_OUTPUTS,
        description="Source table (metrics_outputs or fundamentals)"
    )
    parameter_dependent: bool = Field(
        default=False,
        description="Whether metric depends on param_set_id"
    )
    operation: str = Field(..., description="Operation to apply (add, subtract)")


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
    # Composite operation support (for metrics like Effective Tax Rate)
    operands: Optional[List[OperandComponent]] = Field(
        default=None,
        description="List of operands for composite operations (e.g., ['+Calc XO Cost', '+Calc Tax Cost'])"
    )
    apply_absolute_value: bool = Field(
        default=False,
        description="Whether to apply ABS() to the final component value (for composite results)"
    )
    
    # Legacy single-operand support (deprecated, for backward compatibility)
    operation: Optional[str] = Field(
        default=None,
        description="[DEPRECATED] Operation to combine with operand_metric (use operands list instead)"
    )
    operand_metric_name: Optional[str] = Field(
        default=None,
        description="[DEPRECATED] Second metric name (use operands list instead)"
    )
    operand_metric_source: Optional[MetricSource] = Field(
        default=None,
        description="[DEPRECATED] Source of the operand metric (use operands list instead)"
    )
    operand_parameter_dependent: Optional[bool] = Field(
        default=False,
        description="[DEPRECATED] Whether operand metric depends on param_set_id (use operands list instead)"
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
