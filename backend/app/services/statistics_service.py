# ============================================================================
# Statistics Service - Business Logic Layer with Caching
# ============================================================================
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from functools import lru_cache
from datetime import datetime, timedelta
from typing import Optional, Tuple
import asyncio

from app.models.statistics import (
    DatasetStatistics,
    AllDatasetsStatistics,
    Company,
    CompaniesStats,
    Sector,
    SectorsStats,
    DataCoverage,
    RawMetricsStats,
    ParentIndexStats,
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
    
    async def get_statistics(
        self, 
        dataset_id: UUID,
        ticker_filter: Optional[str] = None,
        company_name_filter: Optional[str] = None,
        sector_filter: Optional[str] = None
    ) -> DatasetStatistics:
        """
        Get statistics for a dataset with caching.
        
        Returns cached result if available (not expired).
        Otherwise queries database and caches result.
        
        Supports optional filtering on companies (case-insensitive).
        """
        # Check cache first (only if no filters applied)
        if not any([ticker_filter, company_name_filter, sector_filter]):
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
        parent_index = await self.repo.get_parent_index(dataset_id)
        
        # Get companies and sectors lists with optional filtering
        companies_data = await self.repo.get_companies_list(
            dataset_id,
            ticker_filter=ticker_filter,
            company_name_filter=company_name_filter,
            sector_filter=sector_filter
        )
        sectors_data = await self.repo.get_sectors_list(
            dataset_id,
            sector_filter=sector_filter
        )
        
        # Build Company objects from raw data
        companies_list = [
            Company(
                ticker=c["ticker"],
                company_name=c["company_name"],
                sector=c["sector"]
            )
            for c in companies_data
        ]
        
        # Build Sector objects from raw data
        sectors_list = [
            Sector(
                name=s["name"],
                company_count=s["company_count"]
            )
            for s in sectors_data
        ]
        
        # Build response
        stats = DatasetStatistics(
            dataset_id=str(dataset_id),
            dataset_created_at=created_at,
            country=country,
            companies=CompaniesStats(count=company_count, items=companies_list),
            sectors=SectorsStats(count=sector_count, items=sectors_list),
            data_coverage=DataCoverage(min_year=min_year, max_year=max_year),
            raw_metrics=RawMetricsStats(count=metrics_count),
            parent_index=ParentIndexStats(value=parent_index),
        )
        
        # Cache the result (only if no filters applied)
        if not any([ticker_filter, company_name_filter, sector_filter]):
            self._set_cache(dataset_id, stats)
        
        return stats
    
    async def get_all_statistics(self) -> AllDatasetsStatistics:
        """
        Get statistics for all datasets with parallel execution.
        
        Fetches all dataset IDs, then queries statistics for each in parallel.
        Results are cached individually per dataset (no special cache for "all").
        """
        logger.info("Fetching statistics for all datasets")
        
        # Get all dataset IDs
        dataset_ids = await self.repo.get_all_dataset_ids()
        logger.info(f"Found {len(dataset_ids)} datasets")
        
        # Fetch statistics for all datasets in parallel
        tasks = [self.get_statistics(dataset_id) for dataset_id in dataset_ids]
        stats_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build response dict, filtering out exceptions
        datasets_dict = {}
        for dataset_id, stats in zip(dataset_ids, stats_list):
            if isinstance(stats, Exception):
                logger.error(f"Error fetching statistics for dataset {dataset_id}: {str(stats)}")
                # Include dataset with null/empty stats on error
                datasets_dict[str(dataset_id)] = DatasetStatistics(
                    dataset_id=str(dataset_id),
                    dataset_created_at=None,
                    country=None,
                    companies=CompaniesStats(count=None, items=[]),
                    sectors=SectorsStats(count=None, items=[]),
                    data_coverage=DataCoverage(min_year=None, max_year=None),
                    raw_metrics=RawMetricsStats(count=None),
                    parent_index=ParentIndexStats(value=None),
                )
            else:
                datasets_dict[str(dataset_id)] = stats
        
        logger.info(f"Successfully retrieved statistics for {len(datasets_dict)} datasets")
        return AllDatasetsStatistics(datasets=datasets_dict)
    
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
