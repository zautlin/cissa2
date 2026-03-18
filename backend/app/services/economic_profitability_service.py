# ============================================================================
# Phase 6: Economic Profitability (EP) Metrics Service
# ============================================================================
# Calculates: Calc EP (intermediate metric, annual only)
# This is the building block for final EP calculations with temporal windows
# Uses vectorized Pandas + batch database inserts
# ============================================================================

import pandas as pd
import numpy as np
from decimal import Decimal
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json
import time

from ..core.config import get_logger

logger = get_logger(__name__)


def to_float(value):
    """Convert Decimal or float to float, handling NaN."""
    if value is None:
        return np.nan
    if isinstance(value, Decimal):
        return float(value)
    if pd.isna(value):
        return np.nan
    return float(value)


class EconomicProfitabilityService:
    """
    Economic Profitability Service (Phase 6)
    
    Calculates:
    - Calc EP: Adjusted Profit After Tax - (Calc Open Ke × Calc Open EE)
    
    Formula:
    Calc EP = Adj PAT - (Calc Open Ke × Calc Open EE)
    
    Where:
    - Adj PAT = PROFIT_AFTER_TAX from fundamentals
    - Calc Open Ke = LAG(Calc KE, 1 year) from metrics_outputs
    - Calc Open EE = LAG(Calc EE, 1 year) from metrics_outputs
    - Calc Incl = Validation flag (set EP to NULL if flag = 0)
    
    Key optimizations:
    - Fetches Adj PAT from fundamentals (PROFIT_AFTER_TAX)
    - Creates lagged versions of Calc KE and Calc EE via LEFT JOIN
    - Vectorized Pandas operations (no row-by-row iteration)
    - Batch database inserts
    - No NULL rows generated (only calculates where data exists)
    
    Prerequisites:
    - Phase 3 Cost of Equity (Calc KE in metrics_outputs)
    - Phase 2 Equity (Calc EE in metrics_outputs)
    - Fundamentals data with PROFIT_AFTER_TAX
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate_economic_profitability(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
    ) -> dict:
        """
        Calculate Phase 6 Economic Profitability (Calc EP) metric.
        
        Args:
            dataset_id: Dataset version ID
            param_set_id: Parameter set ID
        
        Returns:
            {
                'status': 'success|error',
                'records_calculated': int,
                'records_inserted': int,
                'message': str,
                'calculation_time_ms': float
            }
        """
        start_time = time.time()
        logger.info(f"[EP] Starting Economic Profitability calculation for dataset={dataset_id}, param_set={param_set_id}")
        
        try:
            # Step 1: Fetch Calc KE
            logger.info("[EP] Step 1: Fetching Calc KE from metrics_outputs...")
            calc_ke = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc KE',
                param_set_id=param_set_id
            )
            logger.info(f"[EP]   - Fetched {len(calc_ke)} Calc KE records")
            
            # Step 2: Fetch Calc EE
            logger.info("[EP] Step 2: Fetching Calc EE from metrics_outputs...")
            calc_ee = await self._fetch_metric(
                dataset_id=dataset_id,
                metric_name='Calc EE',
                param_set_id=param_set_id
            )
            logger.info(f"[EP]   - Fetched {len(calc_ee)} Calc EE records")
            
            # Step 3: Fetch Adj PAT from fundamentals
            logger.info("[EP] Step 3: Fetching PROFIT_AFTER_TAX from fundamentals...")
            adj_pat = await self._fetch_adj_pat(dataset_id)
            logger.info(f"[EP]   - Fetched {len(adj_pat)} Adj PAT records")
            
            # Step 4: Merge data and create lagged versions
            logger.info("[EP] Step 4: Merging data and creating lagged versions...")
            merged_df = await self._prepare_data_with_lagged_values(
                calc_ke=calc_ke,
                calc_ee=calc_ee,
                adj_pat=adj_pat
            )
            logger.info(f"[EP]   - Merged data: {len(merged_df)} records")
            
            if merged_df.empty:
                logger.warning("[EP] No merged data available for calculation")
                return {
                    'status': 'error',
                    'records_calculated': 0,
                    'records_inserted': 0,
                    'message': 'No data available after merging',
                    'calculation_time_ms': (time.time() - start_time) * 1000
                }
            
            # Step 5: Calculate Calc EP
            logger.info("[EP] Step 5: Calculating Calc EP...")
            ep_df = self._calculate_ep_vectorized(merged_df)
            logger.info(f"[EP]   - Calculated Calc EP: {len(ep_df)} records")
            
            if ep_df.empty:
                logger.warning("[EP] No EP values calculated")
                return {
                    'status': 'error',
                    'records_calculated': 0,
                    'records_inserted': 0,
                    'message': 'No valid EP values calculated',
                    'calculation_time_ms': (time.time() - start_time) * 1000
                }
            
            # Step 6: Insert results
            logger.info("[EP] Step 6: Inserting Calc EP into metrics_outputs...")
            records_inserted = await self._insert_ep_batch(
                ep_df=ep_df,
                dataset_id=dataset_id,
                param_set_id=param_set_id
            )
            logger.info(f"[EP]   - Inserted {records_inserted} records")
            
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"[EP] ✓ Economic Profitability calculation complete in {elapsed_ms:.0f}ms")
            
            return {
                'status': 'success',
                'records_calculated': len(ep_df),
                'records_inserted': records_inserted,
                'message': f'Calculated and stored {records_inserted} Calc EP records',
                'calculation_time_ms': elapsed_ms
            }
        
        except Exception as e:
            logger.error(f"[EP] ✗ Error: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'records_calculated': 0,
                'records_inserted': 0,
                'message': str(e),
                'calculation_time_ms': (time.time() - start_time) * 1000
            }
    
    # ========================================================================
    # Data Fetching
    # ========================================================================
    
    async def _fetch_metric(
        self,
        dataset_id: UUID,
        metric_name: str,
        param_set_id: UUID
    ) -> pd.DataFrame:
        """Fetch metric from metrics_outputs."""
        query = text("""
            SELECT 
                ticker,
                fiscal_year,
                output_metric_value
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
              AND param_set_id = :param_set_id
              AND output_metric_name = :metric_name
            ORDER BY ticker, fiscal_year
        """)
        
        result = await self.session.execute(query, {
            "dataset_id": str(dataset_id),
            "param_set_id": str(param_set_id),
            "metric_name": metric_name
        })
        rows = result.fetchall()
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows, columns=["ticker", "fiscal_year", "metric_value"])
        df["metric_value"] = df["metric_value"].apply(to_float)
        return df
    
    async def _fetch_adj_pat(self, dataset_id: UUID) -> pd.DataFrame:
        """Fetch PROFIT_AFTER_TAX from fundamentals."""
        query = text("""
            SELECT 
                ticker,
                fiscal_year,
                numeric_value
            FROM cissa.fundamentals
            WHERE dataset_id = :dataset_id
              AND metric_name = 'PROFIT_AFTER_TAX'
            ORDER BY ticker, fiscal_year
        """)
        
        result = await self.session.execute(query, {
            "dataset_id": str(dataset_id)
        })
        rows = result.fetchall()
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows, columns=["ticker", "fiscal_year", "adj_pat"])
        df["adj_pat"] = df["adj_pat"].apply(to_float)
        return df
    
    async def _prepare_data_with_lagged_values(
        self,
        calc_ke: pd.DataFrame,
        calc_ee: pd.DataFrame,
        adj_pat: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Prepare data by merging current and lagged values.
        
        Creates lagged versions (previous year) and LEFT JOINs to current data.
        Only keeps rows where current year data exists.
        """
        # Merge current KE and EE
        current_df = calc_ke.merge(
            calc_ee,
            on=['ticker', 'fiscal_year'],
            how='inner',
            suffixes=('_ke', '_ee')
        )
        current_df.rename(columns={
            'metric_value_ke': 'ke',
            'metric_value_ee': 'ee'
        }, inplace=True)
        
        # Add Adj PAT
        current_df = current_df.merge(
            adj_pat,
            on=['ticker', 'fiscal_year'],
            how='inner'
        )
        
        logger.info(f"[EP]   - Current year data: {len(current_df)} records (ticker-year)")
        
        # Create lagged versions (open = prior year)
        lagged_df = current_df.copy()
        lagged_df['fiscal_year'] = lagged_df['fiscal_year'] + 1
        lagged_df = lagged_df.rename(columns={
            'ke': 'ke_open',
            'ee': 'ee_open'
        })
        lagged_df = lagged_df[['ticker', 'fiscal_year', 'ke_open', 'ee_open']]
        
        # LEFT JOIN: keep all current rows, add open values from prior years
        # For first year of data, open values will be NaN
        merged_df = current_df.merge(
            lagged_df,
            on=['ticker', 'fiscal_year'],
            how='left'
        )
        
        valid_records = merged_df.dropna(subset=['ke_open', 'ee_open']).shape[0]
        logger.info(f"[EP]   - After LEFT JOIN with lagged data: {len(merged_df)} total records")
        logger.info(f"[EP]   - Records with complete lagged data: {valid_records}")
        
        return merged_df
    
    # ========================================================================
    # Calculation (Vectorized)
    # ========================================================================
    
    def _calculate_ep_vectorized(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Calc EP using vectorized Pandas operations.
        
        Formula:
        Calc EP = Adj PAT - (Calc Open Ke × Calc Open EE)
        
        Only calculates for rows where both ke_open and ee_open are non-NaN.
        """
        result_df = df.copy()
        
        # Calculate EP: only for rows with complete lagged data
        result_df['ep'] = np.where(
            result_df['ke_open'].notna() & result_df['ee_open'].notna(),
            result_df['adj_pat'] - (result_df['ke_open'] * result_df['ee_open']),
            np.nan
        )
        
        # Keep only rows with calculated EP
        result_df = result_df[result_df['ep'].notna()]
        result_df = result_df[['ticker', 'fiscal_year', 'ep']]
        
        logger.info(f"[EP]   - Calc EP: {len(result_df)} non-NaN values")
        if len(result_df) > 0:
            logger.info(f"[EP]   - Range: [{result_df['ep'].min():.2f}, {result_df['ep'].max():.2f}]")
        
        return result_df
    
    # ========================================================================
    # Storage (Batch Insert)
    # ========================================================================
    
    async def _insert_ep_batch(
        self,
        ep_df: pd.DataFrame,
        dataset_id: UUID,
        param_set_id: UUID
    ) -> int:
        """Insert Calc EP metric in batches."""
        if ep_df.empty:
            return 0
        
        batch_size = 1000
        total_inserted = 0
        
        insert_query = text("""
            INSERT INTO cissa.metrics_outputs 
            (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata, created_at)
            VALUES (:dataset_id, :param_set_id, :ticker, :fiscal_year, :output_metric_name, :output_metric_value, :metadata, now())
            ON CONFLICT (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name) 
            DO UPDATE SET output_metric_value = EXCLUDED.output_metric_value, created_at = now()
        """)
        
        metadata = json.dumps({"metric_level": "L2", "calculation_source": "economic_profitability_service"})
        
        # Prepare records for insert
        records_to_insert = []
        for _, row in ep_df.iterrows():
            if pd.notna(row['ep']):
                records_to_insert.append({
                    "dataset_id": str(dataset_id),
                    "param_set_id": str(param_set_id),
                    "ticker": str(row["ticker"]),
                    "fiscal_year": int(row["fiscal_year"]),
                    "output_metric_name": "Calc EP",
                    "output_metric_value": float(row["ep"]),
                    "metadata": metadata
                })
        
        logger.info(f"[EP]   - Prepared {len(records_to_insert)} records for insert")
        
        # Insert in batches
        for i in range(0, len(records_to_insert), batch_size):
            batch = records_to_insert[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            try:
                for record in batch:
                    await self.session.execute(insert_query, record)
                
                await self.session.commit()
                total_inserted += len(batch)
                logger.debug(f"[EP]   - Batch {batch_num}: inserted {len(batch)} records")
            except Exception as e:
                logger.error(f"[EP]   - Batch {batch_num} error: {str(e)}", exc_info=True)
                await self.session.rollback()
                raise
        
        return total_inserted
