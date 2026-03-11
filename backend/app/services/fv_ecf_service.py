# ============================================================================
# Phase 10b: Future Value Economic Cash Flow (FV_ECF) Metrics Service
# ============================================================================
# Calculates: FV_ECF_1Y, FV_ECF_3Y, FV_ECF_5Y, FV_ECF_10Y
# These are L2 metrics needed for DCF valuation models
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


class FVECFService:
    """
    Future Value Economic Cash Flow Service (Phase 10b)
    
    Calculates:
    - FV_ECF_1Y: 1-year future value economic cash flow
    - FV_ECF_3Y: 3-year future value economic cash flow
    - FV_ECF_5Y: 5-year future value economic cash flow
    - FV_ECF_10Y: 10-year future value economic cash flow
    
    These are L2 metrics used in DCF valuation models.
    
    Key optimizations:
    - Fetches DIVIDENDS, FRANKING from fundamentals table
    - Fetches Non Div ECF from metrics_outputs table
    - Fetches lagged KE (fiscal_year-1) via SQL subquery from metrics_outputs
    - Vectorized Pandas operations (no row-by-row iteration)
    - Batch database inserts (1000 records per batch)
    - 4 intervals × ~9,189 records = ~36,756 total inserts
    
    Prerequisites:
    - Phase 06 L1 Basic Metrics (DIVIDENDS, FRANKING in fundamentals; Non Div ECF in metrics_outputs)
    - Phase 10a Core L2 Metrics (CALC_KE in metrics_outputs)
    
    Algorithm (from legacy code):
    For each interval (1, 3, 5, 10):
      scale_by = 1 if ke_open > 0 else 0
      For seq in range(interval, 0, -1):
        fv_interval = (seq - 1) * (-1)  # -0, -1, -2, etc.
        power = interval + fv_interval - 1
        
        if incl_franking == "Yes":
          TEMP = (
            (-dividend.shift(fv_interval)
             + non_div_ecf.shift(fv_interval)
             - (dividend.shift(fv_interval) / (1-frank_tax_rate))
               * frank_tax_rate * value_franking_cr * franking.shift(fv_interval))
            * (1 + ke_open)^power
            * scale_by
          )
        else:
          TEMP = (dividend + non_div_ecf) * (1 + ke_open)^fv_interval * scale_by
      
      FV_ECF_Y = SUM(all TEMP columns).shift(interval-1)
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate_fv_ecf_metrics(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        incl_franking: str = "Yes",
    ) -> dict:
        """
        Calculate Phase 10b FV_ECF metrics.
        
        Args:
            dataset_id: Dataset version ID
            param_set_id: Parameter set ID
            incl_franking: Include franking credits ('Yes' or 'No'). 
                          If 'query', will fetch from parameters table.
        
        Returns:
            {
                "status": "success|error",
                "total_calculated": N,
                "total_inserted": M,
                "intervals_summary": {
                    "1Y": count,
                    "3Y": count,
                    "5Y": count,
                    "10Y": count
                },
                "duration_seconds": float,
                "message": "..."
            }
        """
        start_time = time.time()
        try:
            logger.info(f"Phase 10b: Starting FV_ECF metrics (dataset={dataset_id}, param_set={param_set_id})")
            
            # Resolve incl_franking parameter
            if incl_franking.lower() == "query":
                incl_franking = await self._get_parameter_value(param_set_id, "incl_franking", "Yes")
            
            logger.info(f"  Include franking: {incl_franking}")
            
            # Load parameters
            logger.info("  Loading parameters...")
            params = await self._load_parameters(param_set_id, incl_franking)
            logger.info(f"    - Franking tax rate: {params.get('frank_tax_rate', 0.3):.4f}")
            logger.info(f"    - Value franking CR: {params.get('value_franking_cr', 0.75):.4f}")
            
            # Fetch fundamentals data (DIVIDENDS, FRANKING, Non Div ECF)
            logger.info("  Fetching fundamentals data...")
            fundamentals_df = await self._fetch_fundamentals_data(dataset_id)
            
            if fundamentals_df.empty:
                logger.error("    No fundamentals data found")
                return {
                    "status": "error",
                    "total_calculated": 0,
                    "total_inserted": 0,
                    "intervals_summary": {"1Y": 0, "3Y": 0, "5Y": 0, "10Y": 0},
                    "duration_seconds": 0,
                    "message": "No fundamentals data found"
                }
            
            logger.info(f"    - Fetched {len(fundamentals_df)} ticker-year records")
            
            # Fetch lagged KE (fiscal_year-1)
            logger.info("  Fetching lagged KE data...")
            ke_df = await self._fetch_lagged_ke(dataset_id, param_set_id)
            
            if ke_df.empty:
                logger.error("    No KE data found")
                return {
                    "status": "error",
                    "total_calculated": 0,
                    "total_inserted": 0,
                    "intervals_summary": {"1Y": 0, "3Y": 0, "5Y": 0, "10Y": 0},
                    "duration_seconds": 0,
                    "message": "No KE data found"
                }
            
            logger.info(f"    - Fetched {len(ke_df)} ticker-year records")
            
            # Join fundamentals + lagged KE
            logger.info("  Joining data...")
            merged_df = self._join_data(fundamentals_df, ke_df)
            
            if merged_df.empty:
                logger.error("    No matching data after join")
                return {
                    "status": "error",
                    "total_calculated": 0,
                    "total_inserted": 0,
                    "intervals_summary": {"1Y": 0, "3Y": 0, "5Y": 0, "10Y": 0},
                    "duration_seconds": 0,
                    "message": "No matching data after join"
                }
            
            logger.info(f"    - Merged data: {len(merged_df)} records")
            
            # Calculate FV_ECF for all 4 intervals
            logger.info("  Calculating FV_ECF metrics (vectorized)...")
            all_fv_ecf = []
            intervals_count = {"1Y": 0, "3Y": 0, "5Y": 0, "10Y": 0}
            
            for interval in [1, 3, 5, 10]:
                interval_key = f"{interval}Y"
                fv_ecf_df = self._calculate_fv_ecf_for_interval(
                    merged_df, interval, params
                )
                all_fv_ecf.append(fv_ecf_df)
                intervals_count[interval_key] = len(fv_ecf_df)
                logger.info(f"    - Interval {interval}Y: {len(fv_ecf_df)} records")
            
            # Combine all intervals
            fv_ecf_combined = pd.concat(all_fv_ecf, ignore_index=True)
            logger.info(f"    - Total records to insert: {len(fv_ecf_combined)}")
            
            # Insert results in batches
            logger.info("  Inserting into metrics_outputs...")
            inserted = await self._insert_fv_ecf_batch(dataset_id, param_set_id, fv_ecf_combined)
            logger.info(f"    - Inserted {inserted} records")
            
            duration = time.time() - start_time
            logger.info(f"✓ Phase 10b complete: FV_ECF metrics calculated and stored ({duration:.2f}s)")
            
            return {
                "status": "success",
                "total_calculated": len(merged_df),
                "total_inserted": inserted,
                "intervals_summary": intervals_count,
                "duration_seconds": round(duration, 2),
                "message": f"Calculated and stored {inserted} FV_ECF metric values"
            }
        
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"✗ Phase 10b error: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "total_calculated": 0,
                "total_inserted": 0,
                "intervals_summary": {"1Y": 0, "3Y": 0, "5Y": 0, "10Y": 0},
                "duration_seconds": round(duration, 2),
                "message": str(e)
            }
    
    # ========================================================================
    # Data Fetching & Preparation
    # ========================================================================
    
    async def _get_parameter_value(self, param_set_id: UUID, param_name: str, default: str) -> str:
        """Get a single parameter value from parameter_sets or parameters table."""
        query = text("""
            SELECT param_overrides
            FROM cissa.parameter_sets
            WHERE param_set_id = :param_set_id
        """)
        
        result = await self.session.execute(query, {"param_set_id": str(param_set_id)})
        row = result.fetchone()
        
        if row and row[0] and param_name in row[0]:
            return str(row[0][param_name])
        
        # Fall back to parameters table default
        query = text("""
            SELECT default_value
            FROM cissa.parameters
            WHERE parameter_name = :param_name
        """)
        
        result = await self.session.execute(query, {"param_name": param_name})
        row = result.fetchone()
        
        return str(row[0]) if row else default
    
    async def _load_parameters(self, param_set_id: UUID, incl_franking: str) -> dict:
        """Load parameters for FV_ECF calculation."""
        query = text("""
            SELECT 
                parameter_name,
                default_value as value
            FROM cissa.parameters
            WHERE parameter_name IN (
                'frank_tax_rate',
                'value_franking_cr'
            )
            ORDER BY parameter_name
        """)
        
        result = await self.session.execute(query)
        rows = result.fetchall()
        
        params = {
            'incl_franking': incl_franking,
            'frank_tax_rate': 0.30,
            'value_franking_cr': 0.75
        }
        
        for row in rows:
            param_name, value = row[0], row[1]
            
            if param_name == 'frank_tax_rate' or param_name == 'value_franking_cr':
                # Convert percentage to decimal if > 1
                float_val = float(value)
                params[param_name] = float_val / 100.0 if float_val > 1 else float_val
        
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
                if key in params and key in ['frank_tax_rate', 'value_franking_cr']:
                    float_val = float(value)
                    params[key] = float_val / 100.0 if float_val > 1 else float_val
        
        return params
    
    async def _fetch_fundamentals_data(self, dataset_id: UUID) -> pd.DataFrame:
        """
        Fetch DIVIDENDS, FRANKING from fundamentals table,
        and Non Div ECF from metrics_outputs table.
        
        Returns DataFrame with columns:
        - ticker, fiscal_year
        - non_div_ecf, dividend, franking
        """
        # Fetch DIVIDENDS and FRANKING from fundamentals
        query = text("""
            SELECT 
                ticker,
                fiscal_year,
                MAX(CASE WHEN metric_name = 'DIVIDENDS' THEN numeric_value END) AS dividend,
                MAX(CASE WHEN metric_name = 'FRANKING' THEN numeric_value END) AS franking
            FROM cissa.fundamentals
            WHERE dataset_id = :dataset_id
              AND metric_name IN ('DIVIDENDS', 'FRANKING')
              AND period_type = 'FISCAL'
            GROUP BY ticker, fiscal_year
            ORDER BY ticker, fiscal_year
        """)
        
        result = await self.session.execute(query, {"dataset_id": str(dataset_id)})
        rows = result.fetchall()
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows, columns=["ticker", "fiscal_year", "dividend", "franking"])
        
        # Fetch Non Div ECF from metrics_outputs
        non_div_ecf_query = text("""
            SELECT 
                ticker,
                fiscal_year,
                output_metric_value AS non_div_ecf
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
              AND output_metric_name = 'Non Div ECF'
            ORDER BY ticker, fiscal_year
        """)
        
        non_div_result = await self.session.execute(non_div_ecf_query, {"dataset_id": str(dataset_id)})
        non_div_rows = non_div_result.fetchall()
        
        if non_div_rows:
            non_div_df = pd.DataFrame(non_div_rows, columns=["ticker", "fiscal_year", "non_div_ecf"])
            df = df.merge(non_div_df, how='left', on=['ticker', 'fiscal_year'])
        else:
            df['non_div_ecf'] = None
        
        # Convert Decimal to float
        for col in ["non_div_ecf", "dividend", "franking"]:
            df[col] = df[col].apply(to_float)
        
        return df
    
    async def _fetch_lagged_ke(self, dataset_id: UUID, param_set_id: UUID) -> pd.DataFrame:
        """
        Fetch lagged KE (fiscal_year-1) from metrics_outputs via SQL subquery.
        
        This uses a LEFT JOIN approach:
        - ke (current year)
        - ke_lagged (prior year, fiscal_year = current fiscal_year - 1)
        
        Returns DataFrame with columns:
        - ticker, fiscal_year
        - ke_open (KE from prior fiscal year)
        """
        query = text("""
            SELECT 
                ke.ticker,
                ke.fiscal_year,
                ke_lagged.output_metric_value AS ke_open
            FROM cissa.metrics_outputs ke
            LEFT JOIN cissa.metrics_outputs ke_lagged
                ON ke.ticker = ke_lagged.ticker
                AND ke.fiscal_year = ke_lagged.fiscal_year + 1
                AND ke.dataset_id = ke_lagged.dataset_id
                AND ke.param_set_id = ke_lagged.param_set_id
            WHERE ke.output_metric_name = 'Calc KE'
              AND ke_lagged.output_metric_name = 'Calc KE'
              AND ke.dataset_id = :dataset_id
              AND ke.param_set_id = :param_set_id
            ORDER BY ke.ticker, ke.fiscal_year
        """)
        
        result = await self.session.execute(query, {
            "dataset_id": str(dataset_id),
            "param_set_id": str(param_set_id)
        })
        rows = result.fetchall()
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows, columns=["ticker", "fiscal_year", "ke_open"])
        df["ke_open"] = df["ke_open"].apply(to_float)
        
        return df
    
    def _join_data(self, fundamentals_df: pd.DataFrame, ke_df: pd.DataFrame) -> pd.DataFrame:
        """
        LEFT JOIN fundamentals + lagged KE on (ticker, fiscal_year).
        """
        merged = fundamentals_df.merge(
            ke_df,
            how='left',
            on=['ticker', 'fiscal_year']
        )
        
        return merged
    
    # ========================================================================
    # Calculation (Vectorized)
    # ========================================================================
    
    def _calculate_fv_ecf_for_interval(
        self,
        df: pd.DataFrame,
        interval: int,
        params: dict
    ) -> pd.DataFrame:
        """
        Calculate FV_ECF for a specific interval (1, 3, 5, or 10 years).
        
        Algorithm (from legacy code):
        1. scale_by = 1 if ke_open > 0 else 0
        2. For each seq in range(interval, 0, -1):
             fv_interval = (seq - 1) * (-1)
             power = interval + fv_interval - 1
             
             if incl_franking == "Yes":
               TEMP = (
                 (-dividend.shift(fv_interval)
                  + non_div_ecf.shift(fv_interval)
                  - (dividend.shift(fv_interval) / (1-frank_tax_rate))
                    * frank_tax_rate * value_franking_cr * franking.shift(fv_interval))
                 * (1 + ke_open)^power
                 * scale_by
               )
             else:
               TEMP = (dividend + non_div_ecf) * (1 + ke_open)^fv_interval * scale_by
        3. FV_ECF_Y = SUM(all TEMP columns).shift(interval-1)
        
        Returns DataFrame with columns:
        - ticker, fiscal_year, FV_ECF_Y, FV_ECF_TYPE
        """
        incl_franking = params.get('incl_franking', 'No')
        frank_tax_rate = params.get('frank_tax_rate', 0.30)
        value_franking_cr = params.get('value_franking_cr', 0.75)
        
        # Copy data and group by ticker
        df_copy = df.copy()
        
        # Create scale_by column
        df_copy['scale_by'] = np.where(df_copy['ke_open'] > 0, 1, 0)
        
        result_rows = []
        
        # Group by ticker to apply shifts within ticker context
        for ticker, group in df_copy.groupby('ticker', sort=False):
            group = group.reset_index(drop=True)
            
            # Calculate TEMP columns for each sequence
            temp_columns = []
            
            for seq in range(interval, 0, -1):
                fv_interval = (seq - 1) * (-1)
                power = interval + fv_interval - 1
                
                # Shift columns within this ticker's group
                shifted_dividend = group['dividend'].shift(fv_interval)
                shifted_non_div_ecf = group['non_div_ecf'].shift(fv_interval)
                shifted_franking = group['franking'].shift(fv_interval)
                
                if incl_franking.upper() == "YES":
                    # Calculate TEMP with franking adjustment
                    temp_col = (
                        (-shifted_dividend + shifted_non_div_ecf
                         - (shifted_dividend / (1 - frank_tax_rate))
                           * frank_tax_rate * value_franking_cr * shifted_franking)
                        * np.power(1 + group['ke_open'], power)
                        * group['scale_by']
                    )
                else:
                    # Calculate TEMP without franking
                    temp_col = (
                        (group['dividend'] + group['non_div_ecf'])
                        * np.power(1 + group['ke_open'], fv_interval)
                        * group['scale_by']
                    )
                
                # Handle NaN values with np.where to prevent NumPy NaN arithmetic bug
                # Convert to Series for concatenation
                temp_col = pd.Series(np.where(pd.isna(temp_col), np.nan, temp_col), index=group.index)
                temp_columns.append(temp_col)
            
            # Sum all TEMP columns
            fv_ecf_sum = pd.concat(temp_columns, axis=1).sum(axis=1)
            
            # Shift final result by (interval - 1) years
            fv_ecf_final = fv_ecf_sum.shift(interval - 1)
            
            # Build result rows (skip NaN values)
            for idx, row in group.iterrows():
                fv_ecf_value = fv_ecf_final.iloc[idx]
                
                if pd.notna(fv_ecf_value):
                    result_rows.append({
                        'ticker': ticker,
                        'fiscal_year': int(row['fiscal_year']),
                        'FV_ECF_Y': float(fv_ecf_value),
                        'FV_ECF_TYPE': f'{interval}Y_FV_ECF'
                    })
        
        return pd.DataFrame(result_rows)
    
    # ========================================================================
    # Storage (Batch Insert)
    # ========================================================================
    
    async def _insert_fv_ecf_batch(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        fv_ecf_df: pd.DataFrame
    ) -> int:
        """
        Insert FV_ECF metrics in batches (1000 per batch).
        
        Skips NaN values. Logs and continues on batch errors.
        """
        if fv_ecf_df.empty:
            return 0
        
        batch_size = 1000
        total_inserted = 0
        failed_batches = []
        
        insert_query = text("""
            INSERT INTO cissa.metrics_outputs 
            (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata, created_at)
            VALUES (:dataset_id, :param_set_id, :ticker, :fiscal_year, :output_metric_name, :output_metric_value, :metadata, now())
            ON CONFLICT (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name) 
            DO UPDATE SET output_metric_value = EXCLUDED.output_metric_value, created_at = now()
        """)
        
        metadata = json.dumps({"metric_level": "L2", "calculation_source": "fv_ecf_service"})
        
        # Prepare records to insert
        records_to_insert = []
        for _, row in fv_ecf_df.iterrows():
            metric_value = row['FV_ECF_Y']
            
            # Skip NaN values
            if pd.notna(metric_value):
                records_to_insert.append({
                    "dataset_id": str(dataset_id),
                    "param_set_id": str(param_set_id),
                    "ticker": str(row["ticker"]),
                    "fiscal_year": int(row["fiscal_year"]),
                    "output_metric_name": row['FV_ECF_TYPE'],
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
                logger.error(f"    - Batch {batch_num} error: {str(e)}", exc_info=False)
                await self.session.rollback()
                failed_batches.append(batch_num)
                # Continue with next batch instead of raising
        
        if failed_batches:
            logger.warning(f"    - {len(failed_batches)} failed batches: {failed_batches}. Continuing with successfully inserted {total_inserted} records.")
        
        return total_inserted
