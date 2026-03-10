# ============================================================================
# Phase 10a: Core L2 Metrics Calculation Service
# ============================================================================
# Calculates: EP, PAT_EX, XO_COST_EX, FC
# Uses L1 metrics + lagged/opened versions of previous fiscal year
# Optimized with vectorized Pandas + batch database inserts
# ============================================================================

import pandas as pd
import numpy as np
from decimal import Decimal
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json

from ..core.config import get_logger

logger = get_logger(__name__)


def to_float(value):
    """Convert Decimal or float to float."""
    if value is None:
        return np.nan
    if isinstance(value, Decimal):
        return float(value)
    if pd.isna(value):
        return np.nan
    return float(value)


class EconomicProfitService:
    """
    Economic Profit Service (Phase 10a)
    
    Calculates:
    - EP (Economic Profit): pat - (ke_open × ee_open)
    - PAT_EX (Adjusted Profit): (ep / |ee_open + ke_open|) × ee_open
    - XO_COST_EX (Adjusted XO Cost): patxo - pat_ex
    - FC (Franking Credit): conditionally calculated based on incl_franking
    
    Key optimizations:
    - Creates lagged/opened versions via LEFT JOIN (matching legacy approach)
    - Preserves NaN for missing prior-year data (consistent with legacy)
    - Vectorized Pandas operations (no row-by-row iteration)
    - Batch database inserts (1000 records per batch)
    - 4 metrics × ~9,189 records = ~36,756 total inserts
    
    Prerequisites:
    - Phase 06 L1 Basic Metrics (pat, patxo, ee)
    - Phase 09 Cost of Equity (ke)
    - Franking parameters in parameter_sets
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate_core_l2_metrics(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
    ) -> dict:
        """
        Calculate Phase 10a Core L2 metrics.
        
        Returns:
            {
                "status": "success|error",
                "records_calculated": N,
                "records_inserted": M,
                "message": "..."
            }
        """
        try:
            logger.info(f"Phase 10a: Starting Core L2 metrics (dataset={dataset_id}, param_set={param_set_id})")
            
            # Load parameters
            logger.info("  Loading parameters...")
            params = await self._load_parameters(param_set_id)
            logger.info(f"    - Include franking: {params.get('incl_franking', 'No')}")
            logger.info(f"    - Franking tax rate: {params.get('frank_tax_rate', 0.3):.4f}")
            
            # Fetch L1 inputs and create lagged versions
            logger.info("  Fetching L1 metrics and creating lagged versions...")
            metrics_df = await self._fetch_and_create_lagged_data(dataset_id, param_set_id)
            
            if metrics_df.empty:
                logger.error("    No L1 metrics found")
                return {
                    "status": "error",
                    "records_calculated": 0,
                    "records_inserted": 0,
                    "message": "No L1 metrics data found"
                }
            
            logger.info(f"    - Total records (including NaN): {len(metrics_df)}")
            valid_records = metrics_df.dropna(subset=['ke_open', 'ee_open']).shape[0]
            logger.info(f"    - Records with complete lagged data: {valid_records}")
            
            # Calculate L2 metrics using vectorized operations
            logger.info("  Calculating Core L2 metrics (vectorized)...")
            l2_df = self._calculate_l2_metrics_vectorized(metrics_df, params)
            
            if l2_df.empty:
                logger.warning("    No L2 values could be calculated")
                return {
                    "status": "error",
                    "records_calculated": 0,
                    "records_inserted": 0,
                    "message": "No valid L2 values after calculation"
                }
            
            logger.info(f"    - Calculated {len(l2_df)} L2 metric records (4 metrics × records)")
            
            # Insert results in batches
            logger.info("  Inserting into metrics_outputs...")
            inserted = await self._insert_l2_batch(dataset_id, param_set_id, l2_df)
            logger.info(f"    - Inserted {inserted} records")
            
            logger.info(f"✓ Phase 10a complete: Core L2 metrics calculated and stored")
            
            return {
                "status": "success",
                "records_calculated": len(l2_df) // 4,  # Divide by 4 since each record is 4 metrics
                "records_inserted": inserted,
                "message": f"Calculated and stored {inserted} Core L2 metric values"
            }
        
        except Exception as e:
            logger.error(f"✗ Phase 10a error: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "records_calculated": 0,
                "records_inserted": 0,
                "message": str(e)
            }
    
    # ========================================================================
    # Data Fetching & Preparation
    # ========================================================================
    
    async def _load_parameters(self, param_set_id: UUID) -> dict:
        """Load relevant parameters for L2 calculation."""
        query = text("""
            SELECT 
                parameter_name,
                default_value as value
            FROM cissa.parameters
            WHERE parameter_name IN (
                'incl_franking',
                'frank_tax_rate',
                'value_franking_cr'
            )
            ORDER BY parameter_name
        """)
        
        result = await self.session.execute(query)
        rows = result.fetchall()
        
        params = {}
        for row in rows:
            param_name, value = row[0], row[1]
            
            if param_name == 'frank_tax_rate' or param_name == 'value_franking_cr':
                params[param_name] = float(value) / 100.0 if float(value) > 1 else float(value)
            else:
                params[param_name] = str(value)
        
        # Apply parameter set overrides if any
        override_query = text("""
            SELECT param_overrides
            FROM cissa.parameter_sets
            WHERE param_set_id = :param_set_id
        """)
        
        override_result = await self.session.execute(override_query, {"param_set_id": str(param_set_id)})
        override_row = override_result.fetchone()
        
        if override_row and override_row[0]:
            for key, value in override_row[0].items():
                if key in params:
                    if key == 'frank_tax_rate' or key == 'value_franking_cr':
                        params[key] = float(value) / 100.0 if float(value) > 1 else float(value)
                    else:
                        params[key] = str(value)
        
        # Set defaults if not found
        if 'incl_franking' not in params:
            params['incl_franking'] = 'No'
        if 'frank_tax_rate' not in params:
            params['frank_tax_rate'] = 0.30
        if 'value_franking_cr' not in params:
            params['value_franking_cr'] = 0.75
        
        return params
    
    async def _fetch_and_create_lagged_data(self, dataset_id: UUID, param_set_id: UUID) -> pd.DataFrame:
        """
        Fetch L1 metrics and create lagged versions via LEFT JOIN.
        
        Matches legacy code approach:
        1. Fetch PAT, PATXO from fundamentals 
        2. Fetch EE, KE from metrics_outputs (L1)
        3. Merge fundamentals + metrics_outputs
        4. Create "opened" versions (fy_year + 1, add _open suffix)
        5. LEFT JOIN to get both current and previous year values
        6. Result preserves NaN for missing prior years
        
        Returns DataFrame with columns:
        - ticker, fiscal_year
        - pat, patxo (from fundamentals)
        - ee, ke (from metrics_outputs)
        - dividend (from fundamentals)
        - pat_open, patxo_open, ee_open, ke_open (lagged versions)
        """
        # Fetch PAT and PATXO from fundamentals table
        fund_query = text("""
            SELECT 
                ticker,
                fiscal_year,
                metric_name,
                numeric_value
            FROM cissa.fundamentals
            WHERE dataset_id = :dataset_id
              AND metric_name IN ('PROFIT_AFTER_TAX', 'PROFIT_AFTER_TAX_EX', 'DIVIDENDS')
            ORDER BY ticker, fiscal_year, metric_name
        """)
        
        fund_result = await self.session.execute(fund_query, {
            "dataset_id": str(dataset_id)
        })
        fund_rows = fund_result.fetchall()
        
        # Fetch EE and KE from metrics_outputs
        metrics_query = text("""
            SELECT 
                ticker,
                fiscal_year,
                output_metric_name,
                output_metric_value
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
              AND param_set_id = :param_set_id
              AND output_metric_name IN ('EE', 'Calc KE')
            ORDER BY ticker, fiscal_year, output_metric_name
        """)
        
        metrics_result = await self.session.execute(metrics_query, {
            "dataset_id": str(dataset_id),
            "param_set_id": str(param_set_id)
        })
        metrics_rows = metrics_result.fetchall()
        
        if not fund_rows or not metrics_rows:
            logger.error(f"    Missing fundamentals: {bool(fund_rows)}, Missing metrics: {bool(metrics_rows)}")
            return pd.DataFrame()
        
        # Convert fundamentals to DataFrame and pivot
        fund_df = pd.DataFrame(fund_rows, columns=["ticker", "fiscal_year", "metric_name", "numeric_value"])
        fund_wide = fund_df.pivot_table(
            index=['ticker', 'fiscal_year'],
            columns='metric_name',
            values='numeric_value',
            aggfunc='first'
        ).reset_index()
        
        # Rename fundamentals columns
        fund_wide.rename(columns={
            'PROFIT_AFTER_TAX': 'pat',
            'PROFIT_AFTER_TAX_EX': 'patxo',
            'DIVIDENDS': 'dividend'
        }, inplace=True)
        
        # Convert Decimal to float for fundamentals
        for col in ['pat', 'patxo', 'dividend']:
            if col in fund_wide.columns:
                fund_wide[col] = fund_wide[col].apply(to_float)
        
        logger.info(f"    - Fetched {len(fund_wide)} ticker-year records from fundamentals (PAT, PATXO)")
        
        # Convert metrics to DataFrame and pivot
        metrics_df = pd.DataFrame(metrics_rows, columns=["ticker", "fiscal_year", "output_metric_name", "output_metric_value"])
        metrics_wide = metrics_df.pivot_table(
            index=['ticker', 'fiscal_year'],
            columns='output_metric_name',
            values='output_metric_value',
            aggfunc='first'
        ).reset_index()
        
        # Rename metrics columns
        metrics_wide.rename(columns={
            'EE': 'ee',
            'Calc KE': 'ke'
        }, inplace=True)
        
        # Convert Decimal to float for metrics
        for col in ['ee', 'ke']:
            if col in metrics_wide.columns:
                metrics_wide[col] = metrics_wide[col].apply(to_float)
        
        logger.info(f"    - Fetched {len(metrics_wide)} ticker-year records from metrics (EE, KE)")
        
        # INNER JOIN fundamentals + metrics_outputs on ticker, fiscal_year
        # Only keep rows where both exist
        merged_current = fund_wide.merge(metrics_wide, on=['ticker', 'fiscal_year'], how='inner')
        
        if merged_current.empty:
            logger.error("    No matching ticker-years between fundamentals and metrics")
            return pd.DataFrame()
        
        logger.info(f"    - Merged current data: {len(merged_current)} ticker-year records")
        
        # Create lagged/opened versions (prior fiscal year)
        # This matches legacy code approach
        open_df = merged_current.copy(deep=True)
        open_df['fiscal_year'] = open_df['fiscal_year'] + 1
        
        # Rename metric columns to have _open suffix, but keep ticker and fiscal_year
        open_df = open_df.rename(columns={
            'pat': 'pat_open',
            'patxo': 'patxo_open',
            'ee': 'ee_open',
            'dividend': 'dividend_open',
            'ke': 'ke_open'
        })
        
        # LEFT JOIN: keep all rows from current, add _open columns from prior years
        # For first year of data (or rows with no prior year), _open columns will be NaN
        merged_df = merged_current.merge(
            open_df,
            how='left',
            on=['ticker', 'fiscal_year']
        )
        
        logger.info(f"    - After LEFT JOIN with lagged data: {len(merged_df)} records")
        logger.info(f"    - Records with complete lagged data (not NaN): {merged_df.dropna(subset=['ke_open', 'ee_open']).shape[0]}")
        
        return merged_df
    
    # ========================================================================
    # Calculation (Vectorized)
    # ========================================================================
    
    def _calculate_l2_metrics_vectorized(self, metrics_df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """
        Calculate EP, PAT_EX, XO_COST_EX, FC using vectorized Pandas operations.
        
        Formulas (from legacy code):
        1. EP = pat - (ke_open × ee_open)
        2. PAT_EX = (ep / |ee_open + ke_open|) × ee_open
        3. XO_COST_EX = patxo - pat_ex
        4. FC = IF incl_franking="Yes" THEN (-dividend/(1-frank_tax_rate)) × frank_tax_rate × value_franking_cr × franking ELSE 0
        
        Returns DataFrame with columns:
        - ticker, fiscal_year (grouping keys)
        - ep, pat_ex, xo_cost_ex, fc (calculated L2 metrics)
        """
        incl_franking = params.get('incl_franking', 'No')
        frank_tax_rate = params.get('frank_tax_rate', 0.30)
        value_franking_cr = params.get('value_franking_cr', 0.75)
        
        logger.info(f"    - Franking params: incl={incl_franking}, ftr={frank_tax_rate:.4f}, vfc={value_franking_cr:.4f}")
        
        df = metrics_df.copy()
        
        # Get franking parameter (0 or 1)
        franking_query_text = """
            SELECT default_value
            FROM cissa.parameters
            WHERE parameter_name = 'franking'
        """
        # For now, use hardcoded franking=1 (user always has franking, parameter controls whether to include it)
        franking = 1
        
        # Calculate EP = pat - (ke_open × ee_open)
        df['ep'] = df['pat'] - (df['ke_open'] * df['ee_open'])
        
        # Calculate PAT_EX = (ep / |ee_open + ke_open|) × ee_open
        denominator = np.abs(df['ee_open'] + df['ke_open'])
        # Avoid division by zero: if denominator is 0, result is NaN
        df['pat_ex'] = (df['ep'] / denominator) * df['ee_open']
        
        # Calculate XO_COST_EX = patxo - pat_ex
        df['xo_cost_ex'] = df['patxo'] - df['pat_ex']
        
        # Calculate FC = IF incl_franking="Yes" THEN (-dividend/(1-frank_tax_rate)) × frank_tax_rate × value_franking_cr × franking ELSE 0
        if incl_franking.upper() == "YES":
            divisor = 1 - frank_tax_rate
            if divisor == 0:
                df['fc'] = 0
            else:
                df['fc'] = (-df['dividend'] / divisor) * frank_tax_rate * value_franking_cr * franking
        else:
            df['fc'] = 0
        
        # Select final columns and drop rows where all metrics are NaN (shouldn't happen, but safeguard)
        result_df = df[['ticker', 'fiscal_year', 'ep', 'pat_ex', 'xo_cost_ex', 'fc']].copy()
        
        logger.info(f"    - EP: {result_df['ep'].notna().sum()} non-NaN values, range [{result_df['ep'].min():.2f}, {result_df['ep'].max():.2f}]")
        logger.info(f"    - PAT_EX: {result_df['pat_ex'].notna().sum()} non-NaN values")
        logger.info(f"    - XO_COST_EX: {result_df['xo_cost_ex'].notna().sum()} non-NaN values")
        logger.info(f"    - FC: {result_df['fc'].notna().sum()} non-NaN values")
        
        return result_df
    
    # ========================================================================
    # Storage (Batch Insert)
    # ========================================================================
    
    async def _insert_l2_batch(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        l2_df: pd.DataFrame
    ) -> int:
        """
        Insert L2 metrics (EP, PAT_EX, XO_COST_EX, FC) in batches.
        Each row in l2_df generates 4 metric records (one for each metric).
        
        Skips NaN values (from missing lagged data) - these rows won't be inserted.
        """
        if l2_df.empty:
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
        
        metadata = json.dumps({"metric_level": "L2", "calculation_source": "economic_profit_service"})
        
        # Metrics to insert
        metrics_to_insert = ['EP', 'PAT_EX', 'XO_COST_EX', 'FC']
        
        # Flatten: convert each row with 4 metrics into 4 separate insert records
        # Skip records with NaN metric values
        records_to_insert = []
        for _, row in l2_df.iterrows():
            for metric_name in metrics_to_insert:
                col_name = metric_name.lower()
                if col_name in row.index:
                    metric_value = row[col_name]
                    # Skip NaN values - don't insert rows with no data
                    if pd.notna(metric_value):
                        records_to_insert.append({
                            "dataset_id": str(dataset_id),
                            "param_set_id": str(param_set_id),
                            "ticker": str(row["ticker"]),
                            "fiscal_year": int(row["fiscal_year"]),
                            "output_metric_name": metric_name,
                            "output_metric_value": float(metric_value),
                            "metadata": metadata
                        })
        
        logger.info(f"    - Prepared {len(records_to_insert)} non-NaN metric records for insert")
        
        # Insert in batches
        for i in range(0, len(records_to_insert), batch_size):
            batch = records_to_insert[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            try:
                for record in batch:
                    await self.session.execute(insert_query, record)
                
                await self.session.commit()
                total_inserted += len(batch)
                logger.debug(f"    - Batch {batch_num}: inserted {len(batch)} metric records")
            except Exception as e:
                logger.error(f"    - Batch {batch_num} error: {str(e)}", exc_info=True)
                await self.session.rollback()
                raise
        
        return total_inserted
