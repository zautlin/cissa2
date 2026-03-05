# ============================================================================
# Metrics API Endpoints
# ============================================================================
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from ....core.database import get_db
from ....models import (
    CalculateMetricsRequest,
    CalculateMetricsResponse,
    MetricsHealthResponse
)
from ....services.metrics_service import MetricsService
from ....core.config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.get("/health", response_model=MetricsHealthResponse)
async def health_check():
    """Health check endpoint"""
    return MetricsHealthResponse(
        status="ok",
        message="Metrics service is running",
        database="connected"
    )


@router.post("/calculate", response_model=CalculateMetricsResponse)
async def calculate_metric(
    request: CalculateMetricsRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate a metric for a dataset.
    
    **Example Request:**
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "metric_name": "Calc MC"
    }
    ```
    
    **Supported Metrics:**
    - Calc MC (Market Cap = Spot Shares × Share Price)
    - Calc Assets (Operating Assets = Total Assets - Cash)
    - Calc OA (Operating Assets Detail)
    - Calc Op Cost (Operating Cost = Revenue - Op Income)
    - Calc Non Op Cost (Non-Operating Cost)
    - Calc Tax Cost (Tax Cost = PBT - PAT XO)
    - Calc XO Cost (Extraordinary Items Cost)
    - Profit Margin (PAT / Revenue)
    - Op Cost Margin % (Op Cost / Revenue)
    - Non-Op Cost Margin % (Non-Op Cost / Revenue)
    - Eff Tax Rate (Tax Cost / PBT)
    - XO Cost Margin % (XO Cost / Revenue)
    - FA Intensity (Fixed Assets / Revenue)
    - Book Equity (Total Equity - Minority Interest)
    - ROA (Return on Operating Assets = PAT / Calc Assets)
    """
    
    service = MetricsService(db)
    response = await service.calculate_metric(request.dataset_id, request.metric_name)
    
    if response.status == "error":
        raise HTTPException(status_code=400, detail=response.message)
    
    return response


@router.get("/dataset/{dataset_id}/metrics/{metric_name}", response_model=CalculateMetricsResponse)
async def get_metric(
    dataset_id: UUID,
    metric_name: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get or calculate a metric for a dataset (GET endpoint for convenience).
    
    This endpoint:
    1. Checks if metric exists in metrics_outputs
    2. If not, calculates it
    3. Returns the results
    """
    
    service = MetricsService(db)
    response = await service.calculate_metric(dataset_id, metric_name)
    
    if response.status == "error":
        raise HTTPException(status_code=400, detail=response.message)
    
    return response
