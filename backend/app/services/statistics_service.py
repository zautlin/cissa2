# ============================================================================
# Statistics Service - Business Logic Layer with Caching
# ============================================================================
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from functools import lru_cache
from datetime import datetime, timedelta
from typing import Optional, Tuple

from app.models.statistics import (
    DatasetStatistics,
    CompaniesStats,
    SectorsStats,
    DataCoverage,
    RawMetricsStats,
)
from app.repositories.statistics_repository import StatisticsRepository
from app.core.config import get_logger

logger = get_logger(__name__)


class CachedStatistics:
    """Simple cache wrapper with TTL support"""
    
    def __init__(self, data: DatasetStatistics, created_at: datetime):
        self.data = data
        self.created_at = created_at
    
    def is_expired(self, ttl_seconds: int = 3600) -> bool:
        """Check if cache entry has expired (default 1 hour)"""
        return datetime.utcnow() - self.created_at > timedelta(seconds=ttl_seconds)


class StatisticsService:
    """Service for dataset statistics with 1-hour caching"""
    
    # Simple dict-based cache: {dataset_id: CachedStatistics}
    _cache: dict[str, CachedStatistics] = {}
    _cache_ttl_seconds = 3600  # 1 hour
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = StatisticsRepository(db)
    
    def _get_from_cache(self, dataset_id: UUID) -> Optional[DatasetStatistics]:
        """Get statistics from cache if available and not expired"""
        cache_key = str(dataset_id)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if not cached.is_expired(self._cache_ttl_seconds):
                logger.info(f"Returning cached statistics for dataset {dataset_id}")
                return cached.data
            else:
                # Remove expired entry
                del self._cache[cache_key]
        return None
    
    def _set_cache(self, dataset_id: UUID, stats: DatasetStatistics) -> None:
        """Store statistics in cache"""
        cache_key = str(dataset_id)
        self._cache[cache_key] = CachedStatistics(stats, datetime.utcnow())
        logger.info(f"Cached statistics for dataset {dataset_id}")
    
    async def get_statistics(self, dataset_id: UUID) -> DatasetStatistics:
        """
        Get statistics for a dataset with caching.
        
        Returns cached result if available (not expired).
        Otherwise queries database and caches result.
        """
        # Check cache first
        cached_result = self._get_from_cache(dataset_id)
        if cached_result is not None:
            return cached_result
        
        logger.info(f"Calculating statistics for dataset {dataset_id}")
        
        # Query all statistics
        company_count = await self.repo.get_company_count(dataset_id)
        sector_count = await self.repo.get_sector_count(dataset_id)
        metrics_count = await self.repo.get_raw_metrics_count(dataset_id)
        min_year, max_year = await self.repo.get_data_coverage(dataset_id)
        created_at, country = await self.repo.get_dataset_info(dataset_id)
        
        # Build response
        stats = DatasetStatistics(
            dataset_id=str(dataset_id),
            dataset_created_at=created_at,
            country=country,
            companies=CompaniesStats(count=company_count),
            sectors=SectorsStats(count=sector_count),
            data_coverage=DataCoverage(min_year=min_year, max_year=max_year),
            raw_metrics=RawMetricsStats(count=metrics_count),
        )
        
        # Cache the result
        self._set_cache(dataset_id, stats)
        
        return stats
    
    @classmethod
    def clear_cache(cls, dataset_id: Optional[UUID] = None) -> None:
        """
        Clear cache for specific dataset or all datasets.
        
        Useful after data imports to refresh statistics.
        """
        if dataset_id is None:
            cls._cache.clear()
            logger.info("Cleared all statistics cache")
        else:
            cache_key = str(dataset_id)
            if cache_key in cls._cache:
                del cls._cache[cache_key]
                logger.info(f"Cleared cache for dataset {dataset_id}")
