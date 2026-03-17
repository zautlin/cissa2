# ============================================================================
# Statistics Endpoint
# ============================================================================
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, Union
from pydantic import BaseModel

from app.core.database import get_db
from app.models.statistics import DatasetStatistics, AllDatasetsStatistics
from app.services.statistics_service import StatisticsService
from app.repositories.metrics_repository import MetricsRepository
from app.core.config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/metrics", tags=["statistics"])


class MetricsExistResponse(BaseModel):
    """Response model for metrics existence check"""
    exists: bool


@router.get("/statistics", response_model=Union[DatasetStatistics, AllDatasetsStatistics])
async def get_dataset_statistics(
    dataset_id: Optional[UUID] = Query(None, description="Dataset ID (optional - omit to get stats for all datasets)"),
    db: AsyncSession = Depends(get_db)
) -> Union[DatasetStatistics, AllDatasetsStatistics]:
    """
    Get dataset statistics - supports both single dataset and all datasets.
    
    **Two modes of operation:**
    
    **Mode 1: Single Dataset Statistics**
    - Provide `dataset_id` query parameter
    - Returns comprehensive statistics for that dataset
    
    **Mode 2: All Datasets Statistics**
    - Omit `dataset_id` query parameter
    - Returns statistics for all datasets keyed by dataset_id
    - Uses parallel execution for efficiency
    
    **Statistics Included:**
    - Number of distinct companies (tickers)
    - Number of distinct sectors
    - Number of distinct raw metrics (metric names)
    - Data coverage (min and max fiscal years)
    - Dataset creation date
    - Country/geography
    
    **Caching:**
    - Results are cached per dataset for 1 hour
    - Cache is dataset-specific
    
    **Example Requests:**
    ```
    # Single dataset
    GET /api/v1/metrics/statistics?dataset_id=550e8400-e29b-41d4-a716-446655440000
    
    # All datasets
    GET /api/v1/metrics/statistics
    ```
    
    **Example Response (Single Dataset):**
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "dataset_created_at": "2026-03-12T10:15:30Z",
        "country": "Australia",
        "companies": {"count": 250},
        "sectors": {"count": 12},
        "data_coverage": {"min_year": 2002, "max_year": 2023},
        "raw_metrics": {"count": 15}
    }
    ```
    
    **Example Response (All Datasets):**
    ```json
    {
        "datasets": {
            "550e8400-e29b-41d4-a716-446655440000": {
                "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
                "dataset_created_at": "2026-03-12T10:15:30Z",
                "country": "Australia",
                "companies": {"count": 250},
                "sectors": {"count": 12},
                "data_coverage": {"min_year": 2002, "max_year": 2023},
                "raw_metrics": {"count": 15}
            },
            "550e8400-e29b-41d4-a716-446655440001": {...}
        }
    }
    ```
    
    **Error Handling:**
    - Returns NULL values for missing data (graceful degradation)
    - Logs warnings but doesn't fail
    - Frontend can safely handle NULL values for initialization
    """
    
    try:
        service = StatisticsService(db)
        
        # If dataset_id provided, get single dataset stats
        if dataset_id:
            logger.info(f"Fetching statistics for dataset {dataset_id}")
            stats = await service.get_statistics(dataset_id)
            logger.info(f"Successfully retrieved statistics for dataset {dataset_id}")
            return stats
        
        # Otherwise, get stats for all datasets
        logger.info("Fetching statistics for all datasets")
        all_stats = await service.get_all_statistics()
        logger.info(f"Successfully retrieved statistics for all datasets")
        return all_stats
        
    except Exception as e:
        error_msg = f"Error retrieving statistics: {str(e)}"
        if dataset_id:
            error_msg = f"Error retrieving statistics for dataset {dataset_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.get("/exists", response_model=MetricsExistResponse)
async def check_metrics_exist(
    dataset_id: UUID = Query(..., description="Dataset ID"),
    parameter_set_id: UUID = Query(..., description="Parameter Set ID"),
    db: AsyncSession = Depends(get_db)
) -> MetricsExistResponse:
    """
    Check if metrics exist for a given dataset and parameter set combination.
    
    **Query Parameters:**
    - `dataset_id`: UUID of the dataset
    - `parameter_set_id`: UUID of the parameter set
    
    **Response:**
    - `exists`: Boolean indicating whether metrics exist for this combination
    
    **Example Request:**
    ```
    GET /api/v1/metrics/exists?dataset_id=550e8400-e29b-41d4-a716-446655440000&parameter_set_id=660e8400-e29b-41d4-a716-446655440001
    ```
    
    **Example Response:**
    ```json
    {
        "exists": true
    }
    ```
    
    **Error Handling:**
    - Returns 500 if there's a database error
    """
    try:
        logger.info(f"Checking if metrics exist for dataset {dataset_id} and parameter_set {parameter_set_id}")
        repo = MetricsRepository(db)
        exists = await repo.exists_by_dataset_and_param_set(dataset_id, parameter_set_id)
        logger.info(f"Metrics exist check completed: {exists}")
        return MetricsExistResponse(exists=exists)
    except Exception as e:
        error_msg = f"Error checking metrics existence for dataset {dataset_id} and parameter_set {parameter_set_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )
