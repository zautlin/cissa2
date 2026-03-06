# ============================================================================
# L2 Metrics Service Layer
# ============================================================================
import pandas as pd
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from ..core.config import get_logger
from ..repositories.metrics_repository import MetricsRepository
from ..models.metrics_output import MetricsOutput

logger = get_logger(__name__)


class L2MetricsService:
    """
    Service layer for L2 metrics calculation.
    
    Orchestrates:
    1. Fetch L1 metrics from database
    2. Fetch fundamentals from database
    3. Call pure calculation function
    4. Insert results into database
    """
    
    def __init__(self, session: AsyncSession):
        """Initialize with async database session."""
        self.session = session
        self.repo = MetricsRepository(session)
    
    async def calculate_l2_metrics(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        inputs: dict,
    ) -> dict:
        """
        Calculate L2 metrics for a dataset and parameter set.
        
        Args:
            dataset_id: UUID of the dataset
            param_set_id: UUID of the parameter set
            inputs: Dict with calculation parameters (country, risk_premium, etc.)
        
        Returns:
            Dict with calculation results:
            - status: 'success' or 'error'
            - results_count: number of records inserted
            - message: success or error message
        """
        try:
            logger.info(f"Starting L2 metrics calculation for dataset={dataset_id}, param_set={param_set_id}")
            
            # Step 1: Fetch L1 metrics from database
            logger.info("Fetching L1 metrics from database...")
            l1_metrics_df = await self.repo.get_l1_metrics(dataset_id, param_set_id)
            
            if l1_metrics_df.empty:
                logger.warning(f"No L1 metrics found for dataset={dataset_id}, param_set={param_set_id}")
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": "No L1 metrics found - L2 requires L1 to be calculated first"
                }
            
            logger.info(f"Fetched {len(l1_metrics_df)} L1 metric records")
            
            # Step 2: Fetch fundamentals data from database
            logger.info("Fetching fundamentals from database...")
            fundamentals_df = await self._fetch_fundamentals(dataset_id)
            
            if fundamentals_df.empty:
                logger.warning(f"No fundamentals found for dataset={dataset_id}")
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": "No fundamentals found for dataset"
                }
            
            logger.info(f"Fetched {len(fundamentals_df)} fundamental records")
            
            # Step 3: Call pure calculation function
            logger.info("Running L2 metrics calculation...")
            results_df = await self._calculate_l2_metrics_pure(
                l1_metrics_df, 
                fundamentals_df, 
                inputs
            )
            
            if results_df.empty:
                logger.warning("Calculation returned empty results")
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": "Calculation produced no results"
                }
            
            logger.info(f"Calculation produced {len(results_df)} result records")
            
            # Step 4: Insert results into database
            logger.info("Inserting results into database...")
            inserted_count = await self._insert_l2_results(
                dataset_id,
                param_set_id,
                results_df
            )
            
            logger.info(f"Successfully inserted {inserted_count} L2 metrics records")
            
            return {
                "status": "success",
                "results_count": inserted_count,
                "message": f"L2 metrics calculated and inserted for {inserted_count} records"
            }
        
        except Exception as e:
            logger.error(f"Error calculating L2 metrics: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "results_count": 0,
                "message": f"Error during calculation: {str(e)}"
            }
    
    async def _fetch_fundamentals(self, dataset_id: UUID) -> pd.DataFrame:
        """
        Fetch fundamentals for a dataset.
        
        Returns DataFrame with columns needed for L2 calculation:
        - ticker, fiscal_year, ke_open, ee_open, etc.
        """
        # Query fundamentals table joined with dataset
        query = text("""
            SELECT 
                f.ticker,
                f.fiscal_year,
                f.ke_open,
                f.ee_open,
                f.pat,
                f.patxo,
                f.dividend,
                f.price,
                f.shrouts
            FROM cissa.fundamentals f
            WHERE f.dataset_id = :dataset_id
            ORDER BY f.ticker, f.fiscal_year
        """)
        
        result = await self.session.execute(query, {"dataset_id": str(dataset_id)})
        rows = result.fetchall()
        
        df = pd.DataFrame(
            rows,
            columns=[
                "ticker", "fiscal_year", "ke_open", "ee_open", "pat", 
                "patxo", "dividend", "price", "shrouts"
            ]
        )
        
        return df
    
    async def _calculate_l2_metrics_pure(
        self,
        l1_metrics_df: pd.DataFrame,
        fundamentals_df: pd.DataFrame,
        inputs: dict
    ) -> pd.DataFrame:
        """
        Pure L2 metrics calculation function.
        
        Takes DataFrames as input, performs calculation, returns results DataFrame.
        This is business logic extracted from calculation.py - no database access.
        
        Args:
            l1_metrics_df: L1 metrics with columns [ticker, fiscal_year, output_metric_name, output_metric_value]
            fundamentals_df: Fundamentals with columns [ticker, fiscal_year, ke_open, ee_open, ...]
            inputs: Calculation parameters
        
        Returns:
            DataFrame with calculated L2 metrics: [ticker, fiscal_year, metric_name, metric_value]
        """
        # Pivot L1 metrics to get one column per metric
        l1_pivot = l1_metrics_df.pivot_table(
            index=["ticker", "fiscal_year"],
            columns="output_metric_name",
            values="output_metric_value",
            aggfunc="first"
        ).reset_index()
        
        # Merge L1 + fundamentals
        merged_df = pd.merge(
            l1_pivot,
            fundamentals_df,
            on=["ticker", "fiscal_year"],
            how="inner"
        )
        
        if merged_df.empty:
            logger.warning("No matching rows after merging L1 and fundamentals")
            return pd.DataFrame()
        
        # Calculate L2 metrics from merged data
        # Example: calculated metrics based on ke_open, ee_open, pat, etc.
        results_records = []
        
        for _, row in merged_df.iterrows():
            ticker = row["ticker"]
            fiscal_year = row["fiscal_year"]
            
            # Example L2 calculations (can be extended)
            # These are placeholder calculations - real L2 involves complex regressions
            
            # ke_exposure = ke_open * ee_open if not null else 0
            if pd.notna(row.get("ke_open")) and pd.notna(row.get("ee_open")):
                ke_exposure = row["ke_open"] * row["ee_open"]
                results_records.append({
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "KE_EXPOSURE",
                    "output_metric_value": ke_exposure,
                })
            
            # economic_profit = pat - (ke_open * ee_open)
            if pd.notna(row.get("pat")) and pd.notna(row.get("ke_open")) and pd.notna(row.get("ee_open")):
                economic_profit = row["pat"] - (row["ke_open"] * row["ee_open"])
                results_records.append({
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "ECONOMIC_PROFIT",
                    "output_metric_value": economic_profit,
                })
            
            # roe = pat / ee_open if ee_open > 0
            if pd.notna(row.get("pat")) and pd.notna(row.get("ee_open")) and row["ee_open"] != 0:
                roe = row["pat"] / row["ee_open"]
                results_records.append({
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "ROE",
                    "output_metric_value": roe,
                })
        
        return pd.DataFrame(results_records)
    
    async def _insert_l2_results(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        results_df: pd.DataFrame
    ) -> int:
        """
        Insert L2 metrics results into database.
        
        Args:
            dataset_id: UUID of dataset
            param_set_id: UUID of parameter set
            results_df: DataFrame with columns [ticker, fiscal_year, output_metric_name, output_metric_value]
        
        Returns:
            Number of records inserted
        """
        if results_df.empty:
            return 0
        
        # Convert DataFrame rows to dict records for repository
        records = []
        for _, row in results_df.iterrows():
            records.append({
                "dataset_id": dataset_id,
                "param_set_id": param_set_id,
                "ticker": row["ticker"],
                "fiscal_year": int(row["fiscal_year"]),
                "output_metric_name": row["output_metric_name"],
                "output_metric_value": float(row["output_metric_value"]),
                "metadata": {"metric_level": "L2"},
            })
        
        # Batch insert via repository
        inserted_count = await self.repo.create_metric_outputs_batch(records)
        
        # Commit the transaction
        await self.session.commit()
        
        return inserted_count
