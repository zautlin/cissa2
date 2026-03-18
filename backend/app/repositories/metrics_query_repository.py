# ============================================================================
# Metrics Query Repository - Retrieves metrics data from database
# ============================================================================
from uuid import UUID
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.metrics_output import MetricsOutput


class MetricsQueryRepository:
    """Repository for querying and retrieving metrics_outputs data.
    
    Handles filtering by dataset_id, parameter_set_id, ticker, and metric_name
    with support for case-insensitive matching.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        """Initialize with async database session."""
        self._session = session
    
    async def get_metrics(
        self,
        dataset_id: UUID,
        parameter_set_id: UUID,
        ticker: str | None = None,
        metric_name: str | None = None,
    ) -> list[dict]:
        """
        Query metrics from the database with flexible filtering.
        
        Args:
            dataset_id: UUID of the dataset (required)
            parameter_set_id: UUID of the parameter set (required)
            ticker: Optional ticker to filter by (case-insensitive)
            metric_name: Optional metric name to filter by (case-insensitive)
        
        Returns:
            List of dictionaries containing metric data with units, ordered by:
            - ticker (ascending)
            - fiscal_year (ascending)
            - metric_name (ascending)
        
        Example:
            >>> records = await repo.get_metrics(
            ...     dataset_id=UUID("..."),
            ...     parameter_set_id=UUID("..."),
            ...     ticker="AAPL"
            ... )
            >>> # Returns list of dicts with keys:
            >>> # {dataset_id, parameter_set_id, ticker, fiscal_year, metric_name, value, unit}
        """
        # Build WHERE clause based on parameters
        where_clauses = [
            f"mo.dataset_id = '{str(dataset_id)}'",
            f"mo.param_set_id = '{str(parameter_set_id)}'",
        ]
        
        if ticker is not None:
            where_clauses.append(f"LOWER(mo.ticker) = LOWER('{ticker.replace(chr(39), chr(39)+chr(39))}')")
        
        if metric_name is not None:
            where_clauses.append(
                f"LOWER(mo.output_metric_name) = LOWER('{metric_name.replace(chr(39), chr(39)+chr(39))}')"
            )
        
        where_clause = " AND ".join(where_clauses)
        
        # Raw SQL query with LEFT JOIN to metric_units
        query_sql = f"""
            SELECT 
                mo.dataset_id,
                mo.param_set_id,
                mo.ticker,
                mo.fiscal_year,
                mo.output_metric_name,
                mo.output_metric_value,
                mu.unit
            FROM cissa.metrics_outputs mo
            LEFT JOIN cissa.metric_units mu 
                ON LOWER(mo.output_metric_name) = LOWER(mu.metric_name)
            WHERE {where_clause}
            ORDER BY mo.ticker ASC, mo.fiscal_year ASC, mo.output_metric_name ASC
        """
        
        try:
            result = await self._session.execute(text(query_sql))
            rows = result.fetchall()
            
            # Convert rows to dictionaries
            records = []
            for row in rows:
                records.append({
                    "dataset_id": row[0],
                    "parameter_set_id": row[1],
                    "ticker": row[2],
                    "fiscal_year": row[3],
                    "metric_name": row[4],
                    "value": float(row[5]) if row[5] is not None else None,
                    "unit": row[6],  # Can be None if not in metric_units table
                })
            
            return records
            
        except Exception as e:
            # Log error and return empty list
            from ..core.config import get_logger
            logger = get_logger(__name__)
            logger.error(f"Error querying metrics: {str(e)}")
            return []
