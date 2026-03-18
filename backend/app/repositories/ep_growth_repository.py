# ============================================================================
# Repository for EP Growth Calculations
# ============================================================================
import logging
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class EPGrowthRepository:
    """Data access layer for EP growth calculations from metrics_outputs table"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def execute_ep_growth_query(self, sql: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute EP growth SQL query and return results.
        
        Args:
            sql: Parameterized SQL query string
            params: Dictionary of parameters for the query
        
        Returns:
            List of dictionaries with ticker, fiscal_year, and ep_growth
        
        Raises:
            Exception: If query execution fails
        """
        try:
            result = await self.session.execute(text(sql), params)
            rows = result.fetchall()
            
            # Convert Row objects to dictionaries
            return [
                {
                    "ticker": row.ticker,
                    "fiscal_year": row.fiscal_year,
                    "ep_growth": row.ep_growth
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error executing EP growth query: {str(e)}")
            raise
