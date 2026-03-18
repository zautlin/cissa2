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
from typing import Optional
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
    
    async def calculate_fv_ecf_for_runtime(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        parameter_id: Optional[UUID] = None,
    ) -> dict:
        """
        Calculate FV_ECF metrics for runtime orchestration (Phase 4).
        
        This is the runtime variant of calculate_fv_ecf_metrics() that:
        - Loads parameters from param_set_id (franking treatment, tax rates)
        - Fetches lagged KE from Phase 3 Calc KE results
        - Handles partial results on error (log and continue)
        
        Args:
            dataset_id: Dataset version ID
            param_set_id: Parameter set ID for storing results
            parameter_id: Optional parameter ID (for fallback, not used in runtime)
        
        Returns:
            {
                "status": "success|error",
                "total_inserted": N,
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
            logger.info(f"[Phase 4] Starting FV_ECF runtime calculation (dataset={dataset_id}, param_set={param_set_id})")
            
            # Step 1: Load parameters from param_set_id
            logger.info("[Phase 4] Step 1: Loading parameters from param_set...")
            params = await self._load_parameters_from_param_set(param_set_id)
            logger.info(f"[Phase 4]   - Include franking: {params.get('incl_franking', 'No')}")
            logger.info(f"[Phase 4]   - Franking tax rate: {params.get('frank_tax_rate', 0.30):.4f}")
            logger.info(f"[Phase 4]   - Value franking CR: {params.get('value_franking_cr', 0.75):.4f}")
            
            # Step 2: Fetch fundamentals data (DIVIDENDS, FRANKING, Non Div ECF)
            logger.info("[Phase 4] Step 2: Fetching fundamentals data...")
            fundamentals_df = await self._fetch_fundamentals_data(dataset_id)
            
            if fundamentals_df.empty:
                logger.warning("[Phase 4] No fundamentals data found - returning empty result")
                return {
                    "status": "success",
                    "total_inserted": 0,
                    "intervals_summary": {"1Y": 0, "3Y": 0, "5Y": 0, "10Y": 0},
                    "duration_seconds": 0,
                    "message": "No fundamentals data found"
                }
            
            logger.info(f"[Phase 4]   - Fetched {len(fundamentals_df)} ticker-year records")
            
            # Step 3: Fetch lagged KE from Phase 3 results
            logger.info("[Phase 4] Step 3: Fetching lagged KE from Phase 3 results...")
            ke_df = await self._fetch_lagged_ke_for_runtime(dataset_id, param_set_id)
            
            if ke_df.empty:
                logger.warning("[Phase 4] No KE data found - returning empty result")
                return {
                    "status": "success",
                    "total_inserted": 0,
                    "intervals_summary": {"1Y": 0, "3Y": 0, "5Y": 0, "10Y": 0},
                    "duration_seconds": 0,
                    "message": "No KE data found"
                }
            
            logger.info(f"[Phase 4]   - Fetched {len(ke_df)} ticker-year records")
            
            # Step 4: Join fundamentals + lagged KE
            logger.info("[Phase 4] Step 4: Joining fundamentals + lagged KE...")
            merged_df = self._join_data(fundamentals_df, ke_df)
            
            if merged_df.empty:
                logger.warning("[Phase 4] No matching data after join - returning empty result")
                return {
                    "status": "success",
                    "total_inserted": 0,
                    "intervals_summary": {"1Y": 0, "3Y": 0, "5Y": 0, "10Y": 0},
                    "duration_seconds": 0,
                    "message": "No matching data after join"
                }
            
            logger.info(f"[Phase 4]   - Merged data: {len(merged_df)} records")
            
            # Step 5: Calculate FV_ECF for all 4 intervals
            logger.info("[Phase 4] Step 5: Calculating FV_ECF (all 4 intervals)...")
            all_fv_ecf = []
            intervals_count = {"1Y": 0, "3Y": 0, "5Y": 0, "10Y": 0}
            
            for interval in [1, 3, 5, 10]:
                interval_key = f"{interval}Y"
                fv_ecf_df = self._calculate_fv_ecf_for_interval(
                    merged_df, interval, params
                )
                all_fv_ecf.append(fv_ecf_df)
                intervals_count[interval_key] = len(fv_ecf_df)
                logger.info(f"[Phase 4]   - Interval {interval}Y: {len(fv_ecf_df)} records calculated")
            
            # Combine all intervals
            fv_ecf_combined = pd.concat(all_fv_ecf, ignore_index=True)
            logger.info(f"[Phase 4]   - Total records ready to insert: {len(fv_ecf_combined)}")
            
            # Step 6: Insert results in batches
            logger.info("[Phase 4] Step 6: Inserting into metrics_outputs...")
            inserted = await self._insert_fv_ecf_batch(dataset_id, param_set_id, fv_ecf_combined)
            logger.info(f"[Phase 4]   - Inserted {inserted} records")
            
            duration = time.time() - start_time
            logger.info(f"[Phase 4] ✓ Complete: {inserted} FV_ECF metrics stored ({duration:.2f}s)")
            
            return {
                "status": "success",
                "total_inserted": inserted,
                "intervals_summary": intervals_count,
                "duration_seconds": round(duration, 2),
                "message": f"Successfully calculated and stored {inserted} FV_ECF metric values"
            }
        
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[Phase 4] ✗ Error: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "total_inserted": 0,
                "intervals_summary": {"1Y": 0, "3Y": 0, "5Y": 0, "10Y": 0},
                "duration_seconds": round(duration, 2),
                "message": f"FV_ECF calculation error: {str(e)}"
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
    
    async def _load_parameters_from_param_set(self, param_set_id: UUID) -> dict:
        """
        Load runtime parameters from param_set_id (parameter_sets table).
        
        Maps parameter_set param_overrides JSONB fields to FV_ECF parameters:
        - include_franking_credits_tsr → incl_franking ("Yes"/"No")
        - tax_rate_franking_credits → frank_tax_rate
        - value_of_franking_credits → value_franking_cr
        
        Falls back to defaults if any parameter is missing.
        
        Returns:
            {
                "incl_franking": "Yes"|"No",
                "frank_tax_rate": float,
                "value_franking_cr": float
            }
        """
        params = {
            'incl_franking': 'No',  # Default
            'frank_tax_rate': 0.30,
            'value_franking_cr': 0.75
        }
        
        try:
            query = text("""
                SELECT param_overrides
                FROM cissa.parameter_sets
                WHERE param_set_id = :param_set_id
            """)
            
            result = await self.session.execute(query, {"param_set_id": str(param_set_id)})
            row = result.fetchone()
            
            if row and row[0]:
                overrides = row[0]
                
                # Map include_franking_credits_tsr → incl_franking
                if 'include_franking_credits_tsr' in overrides:
                    include_franking = overrides.get('include_franking_credits_tsr')
                    params['incl_franking'] = 'Yes' if include_franking else 'No'
                
                # Map tax_rate_franking_credits → frank_tax_rate
                if 'tax_rate_franking_credits' in overrides:
                    tax_rate = float(overrides.get('tax_rate_franking_credits', 0.30))
                    params['frank_tax_rate'] = tax_rate / 100.0 if tax_rate > 1 else tax_rate
                
                # Map value_of_franking_credits → value_franking_cr
                if 'value_of_franking_credits' in overrides:
                    value_fr = float(overrides.get('value_of_franking_credits', 0.75))
                    params['value_franking_cr'] = value_fr / 100.0 if value_fr > 1 else value_fr
            
            logger.debug(f"Loaded parameters from param_set {param_set_id}: {params}")
            return params
        
        except Exception as e:
            logger.warning(f"Error loading parameters from param_set {param_set_id}: {str(e)}. Using defaults.", exc_info=False)
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
    
    async def _fetch_lagged_ke_for_runtime(self, dataset_id: UUID, param_set_id: UUID) -> pd.DataFrame:
        """
        Fetch lagged KE from Phase 3 results for runtime orchestration.
        
        This is the runtime variant that:
        - Fetches Calc KE from metrics_outputs for a specific param_set_id
        - Creates lagged values (fiscal_year-1) within each ticker group
        - Handles missing lagged values gracefully (returns NaN)
        
        Returns DataFrame with columns:
        - ticker, fiscal_year
        - ke_open (KE from prior fiscal year)
        """
        query = text("""
            SELECT 
                ticker,
                fiscal_year,
                output_metric_value AS ke_current
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
              AND param_set_id = :param_set_id
              AND output_metric_name = 'Calc KE'
            ORDER BY ticker, fiscal_year
        """)
        
        result = await self.session.execute(query, {
            "dataset_id": str(dataset_id),
            "param_set_id": str(param_set_id)
        })
        rows = result.fetchall()
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows, columns=["ticker", "fiscal_year", "ke_current"])
        df["ke_current"] = df["ke_current"].apply(to_float)
        
        # Create lagged KE within each ticker group
        # For each row, ke_open = KE from (fiscal_year - 1) in same ticker
        df['ke_open'] = df.groupby('ticker')['ke_current'].shift(1)
        
        # Select only needed columns
        df = df[['ticker', 'fiscal_year', 'ke_open']]
        
        logger.debug(f"Fetched lagged KE for {len(df)} rows (dataset={dataset_id}, param_set={param_set_id})")
        
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
    # Calculation (Year-by-Year Lookback)
    # ========================================================================
    
    def _validate_temporal_window(
        self,
        ticker_data: pd.DataFrame,
        interval: int
    ) -> pd.DataFrame:
        """
        Filter DataFrame to only include rows with sufficient historical data.
        
        For interval N, we need to look back (N-1) years. This means:
        - 1Y: Can calculate starting from row 1 (position 0 is first year)
        - 3Y: Need rows at [current, current-1, current-2], so start from row 3
        - 5Y: Need rows at [current, ..., current-4], so start from row 5
        - 10Y: Need rows at [current, ..., current-9], so start from row 10
        
        Args:
            ticker_data: Single ticker's rows, sorted by fiscal_year ascending
            interval: Window size (1, 3, 5, or 10)
        
        Returns:
            Filtered DataFrame with only valid rows (indices >= interval-1)
        """
        if ticker_data.empty:
            return ticker_data
        
        # For interval N, skip first (N-1) rows to ensure sufficient history
        # iloc[interval-1:] keeps all rows from position (interval-1) onwards
        return ticker_data.iloc[interval - 1:].reset_index(drop=True)
    
    def _calculate_ecf_base_value(
        self,
        dividend: float,
        franking: float,
        non_div_ecf: float,
        params: dict
    ) -> float:
        """
        Calculate ECF_base for a single year.
        
        ECF_base = -DIVIDENDS - franking_adjustment + Non_Div_ECF
        
        Where franking_adjustment is only applied if incl_franking="Yes":
        franking_adjustment = (DIVIDENDS / (1 - tax_rate)) 
                            * tax_rate 
                            * franking_credit_value 
                            * FRANKING
        
        Args:
            dividend: Dividend value for year
            franking: Franking ratio for year
            non_div_ecf: Non-dividend ECF for year
            params: Dict with keys: incl_franking, frank_tax_rate, value_franking_cr
        
        Returns:
            float: ECF_base value (or NaN if inputs are NaN)
        """
        # Handle NaN inputs
        if pd.isna(dividend) or pd.isna(non_div_ecf):
            return np.nan
        
        incl_franking = params.get('incl_franking', 'No')
        
        # Start with base: -dividend + non_div_ecf
        ecf_base = -dividend + non_div_ecf
        
        # Add franking adjustment if applicable
        if incl_franking.upper() == 'YES' and not pd.isna(franking):
            frank_tax_rate = params.get('frank_tax_rate', 0.30)
            value_franking_cr = params.get('value_franking_cr', 0.75)
            
            # franking_adjustment = (dividend / (1 - tax_rate)) * tax_rate * franking_cr * franking
            if frank_tax_rate < 1.0:  # Avoid division issues
                franking_adjustment = (
                    (dividend / (1 - frank_tax_rate))
                    * frank_tax_rate
                    * value_franking_cr
                    * franking
                )
                ecf_base -= franking_adjustment
        
        return float(ecf_base)
    
    def _calculate_fv_ecf_single_year(
        self,
        ticker_data: pd.DataFrame,
        current_idx: int,
        interval: int,
        params: dict
    ) -> float:
        """
        Calculate FV_ECF for a single year using year-by-year lookback.
        
        Correct Formula:
        FV_ECF[t] = sum(
            ECF_base[t-i] * (1 + ke_open[t])^(interval - 1 - i)
            for i in range(0, interval)
        )
        
        Where:
        - t is the current year (current_idx)
        - i iterates from 0 (current) to interval-1 (oldest year in window)
        - power = interval - 1 - i (goes from interval-1 down to 0)
        - All terms use the same ke_open[t] (current year's prior-year KE)
        
        Args:
            ticker_data: Single ticker's rows, sorted by fiscal_year ascending
            current_idx: Current row index to calculate for
            interval: Window size (1, 3, 5, or 10)
            params: Parameter dict (incl_franking, tax rates)
        
        Returns:
            float: FV_ECF value (or NaN if insufficient data or ke_open invalid)
        
        Example for 3Y at current_idx=5:
            ke_open = ticker_data.iloc[5]['ke_open']
            term1 = ECF_base[5] * (1 + ke_open)^2  (i=0, power=2)
            term2 = ECF_base[4] * (1 + ke_open)^1  (i=1, power=1)
            term3 = ECF_base[3] * (1 + ke_open)^0  (i=2, power=0)
            return term1 + term2 + term3
        """
        # Check if current row has valid ke_open
        current_row = ticker_data.iloc[current_idx]
        ke_open = current_row['ke_open']
        
        if pd.isna(ke_open):
            return np.nan
        
        # scale_by: Only calculate if ke_open > 0, otherwise return 0
        if ke_open <= 0:
            return 0.0
        
        fv_ecf = 0.0
        
        # Sum terms for each year in the lookback window
        for lookback in range(0, interval):
            lookback_idx = current_idx - lookback
            
            # Check if we have sufficient historical data
            if lookback_idx < 0:
                return np.nan
            
            # Get row for this year
            row = ticker_data.iloc[lookback_idx]
            
            # Calculate ECF_base for this year
            ecf_base = self._calculate_ecf_base_value(
                row['dividend'],
                row['franking'],
                row['non_div_ecf'],
                params
            )
            
            # If any year in the lookback has NaN ECF_base, return NaN
            if pd.isna(ecf_base):
                return np.nan
            
            # Calculate power: interval - 1 - lookback
            # For 3Y: lookback=0 -> power=2, lookback=1 -> power=1, lookback=2 -> power=0
            power = interval - 1 - lookback
            
            # Calculate term and add to sum
            term = ecf_base * ((1 + ke_open) ** power)
            fv_ecf += term
        
        return float(fv_ecf)
    
    def _calculate_fv_ecf_for_interval(
        self,
        df: pd.DataFrame,
        interval: int,
        params: dict
    ) -> pd.DataFrame:
        """
        Calculate FV_ECF for a specific interval (1, 3, 5, or 10 years).
        
        New Algorithm (Year-by-Year Lookback):
        For each ticker's data:
          1. Filter rows with sufficient historical data (temporal window validation)
          2. For each valid row (current_idx):
             a. Get ke_open[current_idx] (prior year's KE)
             b. For each lookback year (0 to interval-1):
                - Calculate ECF_base[current_idx - lookback]
                - Multiply by (1 + ke_open[current_idx])^(interval - 1 - lookback)
                - Sum all terms
             c. Return FV_ECF[current_idx]
        
        Correct Formulas:
        - 1Y:  ECF_base[t] * (1 + ke_open[t])^0
        - 3Y:  ECF_base[t] * (1 + ke_open[t])^2 +
               ECF_base[t-1] * (1 + ke_open[t])^1 +
               ECF_base[t-2] * (1 + ke_open[t])^0
        - 5Y:  Sum of 5 terms with powers 4, 3, 2, 1, 0
        - 10Y: Sum of 10 terms with powers 9, 8, ..., 1, 0
        
        Returns:
            DataFrame with columns: ticker, fiscal_year, FV_ECF_Y, FV_ECF_TYPE
        """
        result_rows = []
        
        # Group by ticker to process each company separately
        for ticker, group in df.groupby('ticker', sort=False):
            # Sort by fiscal_year ascending (oldest to newest)
            group = group.sort_values('fiscal_year').reset_index(drop=True)
            
            # Validate temporal window: filter rows with sufficient historical data
            valid_group = self._validate_temporal_window(group, interval)
            
            if valid_group.empty:
                continue  # No valid rows for this ticker at this interval
            
            # Calculate FV_ECF for each valid row
            for valid_idx, valid_row in valid_group.iterrows():
                # Note: valid_idx is index in valid_group, we need index in original group
                # Since valid_group is a slice of group, we can use valid_idx + (interval - 1)
                current_idx = valid_idx + (interval - 1)
                
                # Calculate FV_ECF for this row using year-by-year lookback
                fv_ecf = self._calculate_fv_ecf_single_year(
                    group,
                    current_idx,
                    interval,
                    params
                )
                
                # Only add rows with valid (non-NaN) FV_ECF values
                if pd.notna(fv_ecf):
                    result_rows.append({
                        'ticker': ticker,
                        'fiscal_year': int(valid_row['fiscal_year']),
                        'FV_ECF_Y': float(fv_ecf),
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
