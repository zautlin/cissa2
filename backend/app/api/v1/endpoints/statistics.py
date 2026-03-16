# ============================================================================
# Statistics Endpoint
# ============================================================================
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.models.statistics import DatasetStatistics
from app.services.statistics_service import StatisticsService
from app.core.config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/metrics", tags=["statistics"])


@router.get("/statistics", response_model=DatasetStatistics)
async def get_dataset_statistics(
    dataset_id: UUID = Query(..., description="Dataset ID"),
    db: AsyncSession = Depends(get_db)
) -> DatasetStatistics:
    """
    Get comprehensive statistics for a dataset.
    
    **Statistics Included:**
    - Number of distinct companies (tickers)
    - Number of distinct sectors
    - Number of distinct raw metrics (metric names)
    - Data coverage (min and max fiscal years)
    - Dataset creation date
    - Country/geography
    
    **Caching:**
    - Results are cached for 1 hour
    - Cache is invalidated per dataset
    - Useful for UI initialization and metadata displays
    
    **Example Request:**
    ```
    GET /api/v1/metrics/statistics?dataset_id=550e8400-e29b-41d4-a716-446655440000
    ```
    
    **Example Response:**
    ```json
    {
        "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
        "dataset_created_at": "2026-03-12T10:15:30Z",
        "country": "Australia",
        "companies": {
            "count": 250
        },
        "sectors": {
            "count": 12
        },
        "data_coverage": {
            "min_year": 2002,
            "max_year": 2023
        },
        "raw_metrics": {
            "count": 15
        }
    }
    ```
    
    **Error Handling:**
    - Returns NULL values for missing data (e.g., if dataset not found)
    - Logs warnings but doesn't fail
    - Frontend can safely handle NULL values for initialization
    """
    
    try:
        logger.info(f"Fetching statistics for dataset {dataset_id}")
        
        service = StatisticsService(db)
        stats = await service.get_statistics(dataset_id)
        
        logger.info(f"Successfully retrieved statistics for dataset {dataset_id}")
        return stats
        
    except Exception as e:
        logger.error(f"Error retrieving statistics for dataset {dataset_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )
