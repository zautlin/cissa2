# ============================================================================
# Metrics Repository Layer
# ============================================================================
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import pandas as pd

from ..models.metrics_output import MetricsOutput


class MetricsRepository:
    """Repository for metrics_outputs table access."""
    
    def __init__(self, session: AsyncSession) -> None:
        """Initialize with async database session."""
        self._session = session
    
    async def get_l1_metrics(
        self, 
        dataset_id: UUID, 
        param_set_id: UUID,
    ) -> pd.DataFrame:
        """
        Fetch L1 metrics for a dataset and parameter set.
        
        Returns a DataFrame with columns:
        - ticker, fiscal_year, output_metric_name, output_metric_value
        
        L1 metrics have metric_level='L1' or specific metric names like 'Calc MC', 'Calc Assets', etc.
        """
        query = select(
            MetricsOutput.ticker,
            MetricsOutput.fiscal_year,
            MetricsOutput.output_metric_name,
            MetricsOutput.output_metric_value,
        ).where(
            MetricsOutput.dataset_id == dataset_id,
            MetricsOutput.param_set_id == param_set_id,
        )
        
        result = await self._session.execute(query)
        rows = result.fetchall()
        
        # Convert to DataFrame for easier manipulation in calculation
        df = pd.DataFrame(
            rows,
            columns=["ticker", "fiscal_year", "output_metric_name", "output_metric_value"]
        )
        
        return df
    
    async def get_fundamentals(
        self,
        dataset_id: UUID,
    ) -> pd.DataFrame:
        """
        Fetch fundamentals for a dataset.
        
        Returns DataFrame with columns needed for L2 calculation.
        This queries the fundamentals table (not metrics_outputs).
        """
        # This is a placeholder - actual implementation will query fundamentals table
        # For now, we'll focus on metrics_outputs repository
        # Fundamentals access will be in a separate repository
        pass
    
    async def create_metric_output(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        ticker: str,
        fiscal_year: int,
        metric_name: str,
        metric_value: float,
        metadata: dict | None = None,
    ) -> MetricsOutput:
        """
        Create a single metric output record.
        
        Returns the created MetricsOutput model instance.
        """
        metric_output = MetricsOutput(
            dataset_id=dataset_id,
            param_set_id=param_set_id,
            ticker=ticker,
            fiscal_year=fiscal_year,
            output_metric_name=metric_name,
            output_metric_value=metric_value,
            metadata=metadata or {},
        )
        
        self._session.add(metric_output)
        await self._session.flush()
        await self._session.refresh(metric_output)
        
        return metric_output
    
    async def create_metric_outputs_batch(
        self,
        records: list[dict],
    ) -> int:
        """
        Batch insert metric output records.
        
        Args:
            records: List of dicts with keys:
                - dataset_id: UUID
                - param_set_id: UUID
                - ticker: str
                - fiscal_year: int
                - output_metric_name: str
                - output_metric_value: float
                - metadata: dict (optional)
        
        Returns:
            Count of inserted records.
        """
        if not records:
            return 0
        
        # Convert dicts to MetricsOutput instances
        instances = [
            MetricsOutput(
                dataset_id=record["dataset_id"],
                param_set_id=record["param_set_id"],
                ticker=record["ticker"],
                fiscal_year=record["fiscal_year"],
                output_metric_name=record["output_metric_name"],
                output_metric_value=record["output_metric_value"],
                metadata=record.get("metadata", {}),
            )
            for record in records
        ]
        
        # Bulk add
        self._session.add_all(instances)
        await self._session.flush()
        
        return len(instances)
    
    async def get_by_id(self, metrics_output_id: int) -> MetricsOutput | None:
        """Get a single metric output by primary key."""
        query = select(MetricsOutput).where(
            MetricsOutput.metrics_output_id == metrics_output_id
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()
    
    async def list_by_dataset_and_param_set(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        metric_name: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[MetricsOutput]:
        """
        List metric outputs for a dataset and parameter set.
        
        Optionally filter by metric_name.
        """
        query = select(MetricsOutput).where(
            MetricsOutput.dataset_id == dataset_id,
            MetricsOutput.param_set_id == param_set_id,
        )
        
        if metric_name:
            query = query.where(MetricsOutput.output_metric_name == metric_name)
        
        query = query.offset(offset).limit(limit)
        
        result = await self._session.execute(query)
        return list(result.scalars().all())
    
    async def exists_by_dataset_and_param_set(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
    ) -> bool:
        """
        Check if any metrics exist for a dataset and parameter set combination.
        
        Returns True if at least one metric record exists, False otherwise.
        """
        query = select(MetricsOutput).where(
            MetricsOutput.dataset_id == dataset_id,
            MetricsOutput.param_set_id == param_set_id,
        ).limit(1)
        
        result = await self._session.execute(query)
        return result.scalar_one_or_none() is not None
