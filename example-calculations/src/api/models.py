"""Pydantic request/response models for API endpoints."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


# ============ Upload Endpoint ============

class UploadDataRequest(BaseModel):
    """POST /api/v1/data/upload request body."""
    file_path: str = Field(..., description="Path to Bloomberg Excel file")
    override_file_path: Optional[str] = Field(None, description="Path to plug/override Excel file")
    description: Optional[str] = Field(None, description="Upload description")


class UploadDataResponse(BaseModel):
    """POST /api/v1/data/upload response."""
    job_id: str = Field(..., description="UUID of upload job")
    status: str = Field(..., description="Job status: queued, in_progress, completed, failed")
    dq_id: Optional[str] = Field(None, description="UUID of data quality check entry")
    file_hash: Optional[str] = Field(None, description="SHA-256 hash of uploaded file")
    message: str = Field(..., description="Status message")


# ============ Metrics Calculation Endpoint ============

class CalculateMetricsRequest(BaseModel):
    """POST /api/v1/metrics/calculate request body."""
    dq_id: str = Field(..., description="UUID of data quality check result")
    parameters: Dict[str, Any] = Field(
        ..., 
        description="Metric calculation parameters (e.g., error_tolerance, approach_to_ke)"
    )
    description: Optional[str] = Field(None, description="Calculation description")


class CalculateMetricsResponse(BaseModel):
    """POST /api/v1/metrics/calculate response."""
    job_id: str = Field(..., description="UUID of metrics calculation job")
    status: str = Field(..., description="Job status: queued, in_progress, completed, failed")
    cached: bool = Field(..., description="True if results were fetched from cache")
    calc_id: Optional[str] = Field(None, description="UUID of metric calculation run")
    message: str = Field(..., description="Status message")


# ============ Job Status Endpoint ============

class JobStatus(BaseModel):
    """Job status response."""
    job_id: str = Field(..., description="UUID of job")
    job_type: str = Field(..., description="Type of job: upload, metrics")
    status: str = Field(..., description="Job status: queued, in_progress, completed, failed")
    created_at: datetime = Field(..., description="Timestamp when job was created")
    updated_at: datetime = Field(..., description="Timestamp of last update")
    started_at: Optional[datetime] = Field(None, description="Timestamp when job started execution")
    ended_at: Optional[datetime] = Field(None, description="Timestamp when job completed/failed")
    progress_percent: int = Field(default=0, description="Progress percentage (0-100)")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result data (dq_id, calc_id, etc.)")
    error_message: Optional[str] = Field(None, description="Error message if job failed")


# ============ Health Check Endpoint ============

class HealthStatus(BaseModel):
    """GET /api/v1/health response."""
    status: str = Field(..., description="Overall status: healthy, degraded, unhealthy")
    database: str = Field(..., description="Database status: ok, error")
    timestamp: datetime = Field(..., description="Current server timestamp")


# ============ Phase 3: Metrics Calculation with dq_id ============

class MetricsCalculateRequest(BaseModel):
    """POST /api/v1/metrics/calculate request body (Phase 3)."""
    dq_id: UUID = Field(..., description="UUID of data quality check result")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metric calculation parameters"
    )


class MetricsCalculateResponse(BaseModel):
    """POST /api/v1/metrics/calculate response (Phase 3)."""
    calc_id: UUID = Field(..., description="UUID of calculation run")
    status: str = Field(..., description="Status: pending or completed (if cached)")
    dq_id: UUID = Field(..., description="Data quality ID")
    param_id: UUID = Field(..., description="Parameter scenario ID")
    created_at: datetime = Field(..., description="When calculation was created")
    started_at: Optional[datetime] = Field(None, description="When calculation started")
    completed_at: Optional[datetime] = Field(None, description="When calculation completed")


class MetricsStatusResponse(BaseModel):
    """GET /api/v1/metrics/{calc_id} response (Phase 3)."""
    calc_id: UUID = Field(..., description="Calculation run ID")
    status: str = Field(..., description="Status: pending, running, completed, failed")
    dq_id: UUID = Field(..., description="Data quality ID")
    param_id: UUID = Field(..., description="Parameter scenario ID")
    started_at: Optional[datetime] = Field(None, description="When calculation started")
    completed_at: Optional[datetime] = Field(None, description="When calculation completed")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class MetricResultItem(BaseModel):
    """Single metric result row."""
    ticker: str = Field(..., description="Stock ticker")
    fx_currency: Optional[str] = Field(None, description="Currency code")
    fy_year: Optional[int] = Field(None, description="Fiscal year")
    key: str = Field(..., description="Metric name (e.g., C_MC, EP)")
    value: Optional[float] = Field(None, description="Metric value")


class MetricsResultsResponse(BaseModel):
    """GET /api/v1/metrics/{calc_id}/results response (Phase 3)."""
    calc_id: UUID = Field(..., description="Calculation run ID")
    results: List[MetricResultItem] = Field(..., description="Calculated metrics")
    total: int = Field(..., description="Total number of results")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Results per page")
    status: str = Field(default="completed", description="Calculation status")
