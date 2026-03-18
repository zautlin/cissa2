# ============================================================================
# Statistics Repository - Data Access Layer
# ============================================================================
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from uuid import UUID
from typing import Optional

from app.core.config import get_logger

logger = get_logger(__name__)


class StatisticsRepository:
    """Repository for dataset statistics queries"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_company_count(self, dataset_id: UUID) -> Optional[int]:
        """
        Get count of distinct companies (tickers) in a dataset.
        
        Since companies table doesn't have dataset_id, we get tickers
        from fundamentals table where dataset_id matches.
        """
        try:
            query = text("""
                SELECT COUNT(DISTINCT ticker)
                FROM cissa.fundamentals
                WHERE dataset_id = :dataset_id and period_type = 'FISCAL'
            """)
            result = await self.db.execute(query, {"dataset_id": str(dataset_id)})
            count = result.scalar()
            return count if count is not None else 0
        except Exception as e:
            logger.error(f"Error getting company count: {str(e)}")
            return None
    
    async def get_sector_count(self, dataset_id: UUID) -> Optional[int]:
        """
        Get count of distinct sectors.
        
        Gets sectors from companies table for tickers that appear
        in the specified dataset.
        """
        try:
            query = text("""
                SELECT COUNT(DISTINCT c.sector)
                FROM cissa.companies c
                WHERE c.ticker IN (
                    SELECT DISTINCT ticker
                    FROM cissa.fundamentals
                    WHERE dataset_id = :dataset_id and period_type = 'FISCAL'
                )
            """)
            result = await self.db.execute(query, {"dataset_id": str(dataset_id)})
            count = result.scalar()
            return count if count is not None else 0
        except Exception as e:
            logger.error(f"Error getting sector count: {str(e)}")
            return None
    
    async def get_raw_metrics_count(self, dataset_id: UUID) -> Optional[int]:
        """Get count of distinct raw metric names in fundamentals"""
        try:
            query = text("""
                SELECT COUNT(DISTINCT metric_name)
                FROM cissa.fundamentals
                WHERE dataset_id = :dataset_id
            """)
            result = await self.db.execute(query, {"dataset_id": str(dataset_id)})
            count = result.scalar()
            return count if count is not None else 0
        except Exception as e:
            logger.error(f"Error getting raw metrics count: {str(e)}")
            return None
    
    async def get_data_coverage(self, dataset_id: UUID) -> tuple[Optional[int], Optional[int]]:
        """Get min and max fiscal years for dataset"""
        try:
            query = text("""
                SELECT MIN(fiscal_year), MAX(fiscal_year)
                FROM cissa.fundamentals
                WHERE dataset_id = :dataset_id and period_type = 'FISCAL'
            """)
            # The above is the hack way to only consider annual data, rather than considering monthly data back to 1981.
            result = await self.db.execute(query, {"dataset_id": str(dataset_id)})
            row = result.fetchone()
            if row:
                return row[0], row[1]
            return None, None
        except Exception as e:
            logger.error(f"Error getting data coverage: {str(e)}")
            return None, None
    
    async def get_parent_index(self, dataset_id: UUID) -> Optional[str]:
        """
        Get the distinct parent_index value for a dataset.
        
        Returns the first (and should be only) parent_index value from the companies table
        for tickers that appear in the dataset.
        Uses LIMIT 1 to ensure only one value is returned.
        """
        try:
            query = text("""
                SELECT DISTINCT c.parent_index
                FROM cissa.companies c
                WHERE c.ticker IN (
                    SELECT DISTINCT ticker
                    FROM cissa.fundamentals
                    WHERE dataset_id = :dataset_id and period_type = 'FISCAL'
                )
                LIMIT 1
            """)
            result = await self.db.execute(query, {"dataset_id": str(dataset_id)})
            parent_index = result.scalar()
            return parent_index if parent_index is not None else None
        except Exception as e:
            logger.error(f"Error getting parent_index: {str(e)}")
            return None
    
    async def get_dataset_info(self, dataset_id: UUID) -> tuple[Optional[str], Optional[str]]:
        """
        Get dataset creation date and country.
        
        Returns (created_at, country) where country comes from companies
        table for tickers in the dataset.
        """
        try:
            # Get dataset created_at
            query_created = text("""
                SELECT created_at
                FROM cissa.dataset_versions
                WHERE dataset_id = :dataset_id
                LIMIT 1
            """)
            result_created = await self.db.execute(query_created, {"dataset_id": str(dataset_id)})
            created_at = result_created.scalar()
            
            # Get country (assuming all companies in a dataset are from same country)
            query_country = text("""
                SELECT DISTINCT c.country
                FROM cissa.companies c
                WHERE c.ticker IN (
                    SELECT DISTINCT ticker
                    FROM cissa.fundamentals
                    WHERE dataset_id = :dataset_id and period_type = 'FISCAL'
                )
                LIMIT 1
            """)
            result_country = await self.db.execute(query_country, {"dataset_id": str(dataset_id)})
            country = result_country.scalar()
            
            return created_at, country
        except Exception as e:
            logger.error(f"Error getting dataset info: {str(e)}")
            return None, None
    
    async def get_all_dataset_ids(self) -> list[UUID]:
        """
        Get all dataset IDs from dataset_versions table.
        
        Used to fetch statistics for all datasets.
        """
        try:
            query = text("""
                SELECT dataset_id
                FROM cissa.dataset_versions
                ORDER BY created_at DESC
            """)
            result = await self.db.execute(query)
            rows = result.fetchall()
            
            # Handle both string and UUID objects from asyncpg
            dataset_ids = []
            for row in rows:
                dataset_id = row[0]
                if isinstance(dataset_id, UUID):
                    dataset_ids.append(dataset_id)
                else:
                    dataset_ids.append(UUID(dataset_id))
            return dataset_ids
        except Exception as e:
            logger.error(f"Error getting all dataset IDs: {str(e)}")
            return []
    
    async def get_companies_list(
        self, 
        dataset_id: UUID,
        ticker_filter: Optional[str] = None,
        company_name_filter: Optional[str] = None,
        sector_filter: Optional[str] = None
    ) -> list[dict]:
        """
        Get list of companies (ticker, name, sector) for a dataset.
        
        Returns list of dicts with keys: ticker, company_name, sector.
        Supports optional case-insensitive filtering.
        """
        try:
            # Build base query
            query_str = """
                SELECT DISTINCT c.ticker, c.name, c.sector
                FROM cissa.companies c
                WHERE c.ticker IN (
                    SELECT DISTINCT ticker
                    FROM cissa.fundamentals
                    WHERE dataset_id = :dataset_id and period_type = 'FISCAL'
                )
            """
            
            params = {"dataset_id": str(dataset_id)}
            
            # Add optional filters (case-insensitive for text fields)
            filters = []
            if ticker_filter:
                filters.append("LOWER(c.ticker) LIKE LOWER(:ticker_filter)")
                params["ticker_filter"] = f"%{ticker_filter}%"
            
            if company_name_filter:
                filters.append("LOWER(c.name) LIKE LOWER(:company_name_filter)")
                params["company_name_filter"] = f"%{company_name_filter}%"
            
            if sector_filter:
                # Sector filter is case-insensitive exact match
                filters.append("LOWER(c.sector) = LOWER(:sector_filter)")
                params["sector_filter"] = sector_filter
            
            if filters:
                query_str += " AND " + " AND ".join(filters)
            
            # Order by ticker for consistency
            query_str += " ORDER BY c.ticker ASC"
            
            query = text(query_str)
            result = await self.db.execute(query, params)
            rows = result.fetchall()
            
            # Convert to list of dicts
            companies = []
            for row in rows:
                companies.append({
                    "ticker": row[0],
                    "company_name": row[1],
                    "sector": row[2]
                })
            
            logger.debug(f"Retrieved {len(companies)} companies for dataset {dataset_id}")
            return companies
        except Exception as e:
            logger.error(f"Error getting companies list: {str(e)}")
            return []
    
    async def get_sectors_list(
        self,
        dataset_id: UUID,
        sector_filter: Optional[str] = None
    ) -> list[dict]:
        """
        Get list of sectors with company counts for a dataset.
        
        Returns list of dicts with keys: name, company_count.
        Supports optional case-insensitive filtering.
        """
        try:
            # Build base query
            query_str = """
                SELECT DISTINCT c.sector, COUNT(DISTINCT c.ticker) as company_count
                FROM cissa.companies c
                WHERE c.ticker IN (
                    SELECT DISTINCT ticker
                    FROM cissa.fundamentals
                    WHERE dataset_id = :dataset_id and period_type = 'FISCAL'
                )
            """
            
            params = {"dataset_id": str(dataset_id)}
            
            # Add optional filter (case-insensitive)
            if sector_filter:
                query_str += " AND LOWER(c.sector) = LOWER(:sector_filter)"
                params["sector_filter"] = sector_filter
            
            # Group by sector and order by name
            query_str += " GROUP BY c.sector ORDER BY c.sector ASC"
            
            query = text(query_str)
            result = await self.db.execute(query, params)
            rows = result.fetchall()
            
            # Convert to list of dicts
            sectors = []
            for row in rows:
                sectors.append({
                    "name": row[0],
                    "company_count": row[1]
                })
            
            logger.debug(f"Retrieved {len(sectors)} sectors for dataset {dataset_id}")
            return sectors
        except Exception as e:
            logger.error(f"Error getting sectors list: {str(e)}")
            return []
