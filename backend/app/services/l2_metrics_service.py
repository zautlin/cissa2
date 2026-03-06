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
            
            # Step 1: Fetch L1 metrics from database using raw SQL (avoids ORM FK validation issues)
            logger.info("Fetching L1 metrics from database...")
            l1_metrics_df = await self._fetch_l1_metrics_raw(dataset_id, param_set_id)
            
            if l1_metrics_df.empty:
                logger.warning(f"No L1 metrics found for dataset={dataset_id}, param_set={param_set_id}")
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": "No L1 metrics found - L2 requires L1 to be calculated first"
                }
            
            logger.info(f"Fetched {len(l1_metrics_df)} L1 metric records")
            
            # Step 2: Fetch L1 metrics pivoted to columns (Calc MC, ROA, Book Equity, etc.)
            logger.info("Fetching L1 metrics pivoted to columns...")
            l1_metrics_pivoted = await self._fetch_l1_metrics_pivoted(dataset_id, param_set_id)
            
            if l1_metrics_pivoted.empty:
                logger.warning(f"No L1 metrics found for pivoting")
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": "No L1 metrics found for pivoting"
                }
            
            logger.info(f"Fetched {len(l1_metrics_pivoted)} L1 metrics (pivoted)")
            
            # Step 3: Fetch fundamentals data from database (for raw financial data)
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
            
            # Step 4: Call pure calculation function
            logger.info("Running L2 metrics calculation...")
            results_df = await self._calculate_l2_metrics_pure(
                l1_metrics_pivoted,
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
            
            # Step 5: Insert results into database
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
    
    async def _fetch_l1_metrics_raw(self, dataset_id: UUID, param_set_id: UUID) -> pd.DataFrame:
        """
        Fetch L1 metrics using raw SQL (avoids ORM FK validation).
        
        Returns DataFrame with columns: ticker, fiscal_year, output_metric_name, output_metric_value
        """
        query = text("""
            SELECT 
                ticker,
                fiscal_year,
                output_metric_name,
                output_metric_value
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
              AND param_set_id = :param_set_id
            ORDER BY ticker, fiscal_year, output_metric_name
        """)
        
        result = await self.session.execute(query, {
            "dataset_id": str(dataset_id),
            "param_set_id": str(param_set_id)
        })
        rows = result.fetchall()
        
        df = pd.DataFrame(
            rows,
            columns=["ticker", "fiscal_year", "output_metric_name", "output_metric_value"]
        )
        
        return df
    
    async def _fetch_fundamentals(self, dataset_id: UUID) -> pd.DataFrame:
        """
        Fetch fundamentals for a dataset.
        
        Returns DataFrame with columns needed for L2 calculation.
        Pivots fundamentals table so each metric_name becomes a column.
        """
        # Query fundamentals table and pivot metrics to columns
        query = text("""
            SELECT 
                ticker,
                fiscal_year,
                MAX(CASE WHEN metric_name = 'PROFIT_AFTER_TAX' THEN numeric_value END) as pat,
                MAX(CASE WHEN metric_name = 'PROFIT_AFTER_TAX_EX' THEN numeric_value END) as patxo,
                MAX(CASE WHEN metric_name = 'DIVIDENDS' THEN numeric_value END) as dividend,
                MAX(CASE WHEN metric_name = 'SHARE_PRICE' THEN numeric_value END) as price,
                MAX(CASE WHEN metric_name = 'SPOT_SHARES' THEN numeric_value END) as shrouts,
                MAX(CASE WHEN metric_name = 'MARKET_CAP' THEN numeric_value END) as market_cap,
                MAX(CASE WHEN metric_name = 'TOTAL_ASSETS' THEN numeric_value END) as total_assets,
                MAX(CASE WHEN metric_name = 'CASH' THEN numeric_value END) as cash,
                MAX(CASE WHEN metric_name = 'FIXED_ASSETS' THEN numeric_value END) as fixed_assets,
                MAX(CASE WHEN metric_name = 'GOODWILL' THEN numeric_value END) as goodwill,
                MAX(CASE WHEN metric_name = 'TOTAL_EQUITY' THEN numeric_value END) as total_equity,
                MAX(CASE WHEN metric_name = 'MINORITY_INTEREST' THEN numeric_value END) as minority_interest,
                MAX(CASE WHEN metric_name = 'REVENUE' THEN numeric_value END) as revenue,
                MAX(CASE WHEN metric_name = 'OPERATING_INCOME' THEN numeric_value END) as operating_income,
                MAX(CASE WHEN metric_name = 'PROFIT_BEFORE_TAX' THEN numeric_value END) as pbt,
                MAX(CASE WHEN metric_name = 'FY_TSR' THEN numeric_value END) as fy_tsr,
                MAX(CASE WHEN metric_name = 'COMPANY_TSR' THEN numeric_value END) as company_tsr,
                MAX(CASE WHEN metric_name = 'INDEX_TSR' THEN numeric_value END) as index_tsr,
                MAX(CASE WHEN metric_name = 'RISK_FREE_RATE' THEN numeric_value END) as risk_free_rate
            FROM cissa.fundamentals
            WHERE dataset_id = :dataset_id
            GROUP BY ticker, fiscal_year
            ORDER BY ticker, fiscal_year
        """)
        
        result = await self.session.execute(query, {"dataset_id": str(dataset_id)})
        rows = result.fetchall()
        
        df = pd.DataFrame(
            rows,
            columns=[
                "ticker", "fiscal_year", "pat", "patxo", "dividend", "price", "shrouts",
                "market_cap", "total_assets", "cash", "fixed_assets", "goodwill",
                "total_equity", "minority_interest", "revenue", "operating_income", "pbt",
                "fy_tsr", "company_tsr", "index_tsr", "risk_free_rate"
            ]
        )
        
        return df
    
    async def _fetch_l1_metrics_pivoted(self, dataset_id: UUID, param_set_id: UUID) -> pd.DataFrame:
        """
        Fetch L1 metrics and pivot them to columns for use in L2 calculations.
        
        Returns DataFrame with columns like "Calc MC", "ROA", "Book Equity", etc.
        """
        query = text("""
            SELECT 
                ticker,
                fiscal_year,
                output_metric_name,
                output_metric_value
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
              AND param_set_id = :param_set_id
            ORDER BY ticker, fiscal_year, output_metric_name
        """)
        
        result = await self.session.execute(query, {
            "dataset_id": str(dataset_id),
            "param_set_id": str(param_set_id)
        })
        rows = result.fetchall()
        
        df = pd.DataFrame(rows, columns=["ticker", "fiscal_year", "output_metric_name", "output_metric_value"])
        
        # Pivot so metric names become columns
        l1_pivot = df.pivot_table(
            index=["ticker", "fiscal_year"],
            columns="output_metric_name",
            values="output_metric_value",
            aggfunc="first"
        ).reset_index()
        
        logger.info(f"Fetched L1 metrics: {len(l1_pivot)} rows with columns: {list(l1_pivot.columns)}")
        
        return l1_pivot
    
    async def _calculate_l2_metrics_pure(
        self,
        l1_metrics_pivoted: pd.DataFrame,
        fundamentals_df: pd.DataFrame,
        inputs: dict
    ) -> pd.DataFrame:
        """
        Pure L2 metrics calculation function.
        
        Takes DataFrames as input, performs calculation, returns results DataFrame.
        This is business logic extracted from calculation.py - no database access.
        
        Args:
            l1_metrics_pivoted: L1 metrics pivoted with columns [ticker, fiscal_year, Calc MC, ROA, Book Equity, ...]
            fundamentals_df: Fundamentals with columns [ticker, fiscal_year, pat, price, shrouts, ...]
            inputs: Calculation parameters (country, risk_premium, etc.)
        
        Returns:
            DataFrame with calculated L2 metrics: [ticker, fiscal_year, metric_name, metric_value]
        """
        # Merge L1 metrics (pivoted) + fundamentals
        merged_df = pd.merge(
            l1_metrics_pivoted,
            fundamentals_df,
            on=["ticker", "fiscal_year"],
            how="inner"
        )
        
        if merged_df.empty:
            logger.warning("No matching rows after merging L1 metrics and fundamentals")
            logger.info(f"L1 metrics shape: {l1_metrics_pivoted.shape}, Fundamentals shape: {fundamentals_df.shape}")
            return pd.DataFrame()
        
        logger.info(f"Merged L1 + fundamentals: {len(merged_df)} rows with columns: {list(merged_df.columns)}")
        
        # Calculate L2 metrics from merged data
        # Using available L1 metrics and fundamentals to create meaningful L2 metrics
        results_records = []
        
        for _, row in merged_df.iterrows():
            ticker = row["ticker"]
            fiscal_year = int(row["fiscal_year"])
            
            # L2 metrics are derived from L1 metrics and fundamentals
            # These create secondary-level analysis metrics
            
            # 1. ROA (already in L1, but we can use it as L2 base)
            if pd.notna(row.get("ROA")):
                results_records.append({
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "L2_ROA_BASE",
                    "output_metric_value": float(row["ROA"]),
                })
            
            # 2. Asset Efficiency = Calc MC / Calc Assets
            if pd.notna(row.get("Calc MC")) and pd.notna(row.get("Calc Assets")) and row.get("Calc Assets", 0) != 0:
                asset_efficiency = float(row["Calc MC"]) / float(row["Calc Assets"])
                results_records.append({
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "L2_ASSET_EFFICIENCY",
                    "output_metric_value": asset_efficiency,
                })
            
            # 3. Operating Leverage = Calc Op Cost / Revenue
            if pd.notna(row.get("Calc Op Cost")) and pd.notna(row.get("revenue")) and row.get("revenue", 0) != 0:
                op_leverage = float(row["Calc Op Cost"]) / float(row["revenue"])
                results_records.append({
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "L2_OPERATING_LEVERAGE",
                    "output_metric_value": op_leverage,
                })
            
            # 4. Tax Burden = Calc Tax Cost / Profit Before Tax
            if pd.notna(row.get("Calc Tax Cost")) and pd.notna(row.get("pbt")) and row.get("pbt", 0) != 0:
                tax_burden = float(row["Calc Tax Cost"]) / float(row["pbt"])
                results_records.append({
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "L2_TAX_BURDEN",
                    "output_metric_value": tax_burden,
                })
            
            # 5. Capital Intensity = Book Equity / Calc MC
            if pd.notna(row.get("Book Equity")) and pd.notna(row.get("Calc MC")) and row.get("Calc MC", 0) != 0:
                capital_intensity = float(row["Book Equity"]) / float(row["Calc MC"])
                results_records.append({
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "L2_CAPITAL_INTENSITY",
                    "output_metric_value": capital_intensity,
                })
            
            # 6. Dividend Payout Ratio = Dividends / PAT
            if pd.notna(row.get("dividend")) and pd.notna(row.get("pat")) and row.get("pat", 0) != 0:
                dividend_payout = float(row["dividend"]) / float(row["pat"])
                results_records.append({
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "L2_DIVIDEND_PAYOUT_RATIO",
                    "output_metric_value": dividend_payout,
                })
        
        logger.info(f"Generated {len(results_records)} L2 metric records")
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
