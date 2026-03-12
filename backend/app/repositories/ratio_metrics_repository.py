# ============================================================================
# Repository Layer for Ratio Metrics
# ============================================================================
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict, Any
from ..core.config import get_logger

logger = get_logger(__name__)


class RatioMetricsRepository:
    """Data access layer for ratio metrics calculations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def execute_ratio_query(self, sql_query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Execute a raw SQL query for ratio metric calculation.
        
        Args:
            sql_query: Parameterized SQL query
            params: Query parameters (dict of key-value pairs)
        
        Returns:
            List of dictionaries with keys: ticker, fiscal_year, value
        """
        try:
            query = text(sql_query)
            result = await self.session.execute(query, params or {})
            rows = result.fetchall()
            
            logger.debug(f"Query executed, returned {len(rows)} rows")
            
            # Convert rows to dictionaries
            results = []
            for row in rows:
                # Try to access by column name first (for named columns), fall back to index
                try:
                    ticker = row["ticker"]
                    fiscal_year = row["fiscal_year"]
                    value = row["ratio_value"]
                except (TypeError, KeyError):
                    # Fall back to positional access
                    ticker = row[0]
                    fiscal_year = row[1]
                    value = row[2]
                
                results.append({
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "value": value
                })
            
            logger.info(f"Ratio query returned {len(results)} rows")
            return results
            
        except Exception as e:
            logger.error(f"Error executing ratio query: {str(e)}", exc_info=True)
            raise
