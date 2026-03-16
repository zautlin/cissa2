# ============================================================================
# Phase 09: Cost of Equity Calculation Service
# ============================================================================
# Efficiently calculates KE = Rf + Beta × RiskPremium
# Uses existing Beta (Phase 07) and Rf (Phase 08) outputs
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


class CostOfEquityService:
    """
    Cost of Equity Calculation Service (Phase 09)
    
    Calculates: KE = Rf + Beta × RiskPremium
    
    Key optimizations:
    - Uses existing Calc Beta and Calc Rf from metrics_outputs (no recalculation)
    - Vectorized Pandas operations (no row-by-row iteration)
    - Batch database inserts (1000 records per batch)
    
    Prerequisites:
    - Phase 07 Beta results in metrics_outputs
    - Phase 08 Rf results in metrics_outputs
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def calculate_cost_of_equity(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
    ) -> dict:
        """
        Calculate Cost of Equity using existing Calc Beta and Calc Rf.
        
        Returns:
            {
                "status": "success|error",
                "records_calculated": N,
                "records_inserted": M,
                "message": "..."
            }
        """
        try:
            logger.info(f"Phase 09: Starting KE calculation (dataset={dataset_id}, param_set={param_set_id})")
            
            # Load parameters
            logger.info("  Loading parameters...")
            params = await self._load_parameters(param_set_id)
            logger.info(f"    - KE approach: {params.get('cost_of_equity_approach', 'Floating')}")
            logger.info(f"    - Risk premium: {params.get('equity_risk_premium', 0.05):.4f}")
            
            # Fetch existing Calc Beta and Calc Rf from metrics_outputs
            logger.info("  Fetching Calc Beta and Calc Rf from metrics_outputs...")
            beta_df, rf_df = await self._fetch_ke_inputs(dataset_id, param_set_id)
            
            if beta_df.empty and rf_df.empty:
                logger.error("    No Calc Beta/Calc Rf data found")
                return {
                    "status": "error",
                    "records_calculated": 0,
                    "records_inserted": 0,
                    "message": "No Calc Beta or Calc Rf data found in metrics_outputs"
                }
            
            logger.info(f"    - Calc Beta records: {len(beta_df)}")
            logger.info(f"    - Calc Rf records: {len(rf_df)}")
            
            # Calculate KE using vectorized operations
            logger.info("  Calculating KE = Rf + Beta × RiskPremium (vectorized)...")
            ke_df = self._calculate_ke_vectorized(beta_df, rf_df, params)
            
            if ke_df.empty:
                logger.warning("    No KE values could be calculated")
                return {
                    "status": "error",
                    "records_calculated": 0,
                    "records_inserted": 0,
                    "message": "No valid KE values after calculation"
                }
            
            logger.info(f"    - Calculated {len(ke_df)} KE values")
            logger.info(f"    - KE range: {ke_df['ke'].min():.4f} to {ke_df['ke'].max():.4f}")
            logger.info(f"    - KE mean: {ke_df['ke'].mean():.4f}")
            
            # Insert results in batches
            logger.info("  Inserting into metrics_outputs...")
            inserted = await self._insert_ke_batch(dataset_id, param_set_id, ke_df)
            logger.info(f"    - Inserted {inserted} records")
            
            logger.info(f"✓ Phase 09 complete: {len(ke_df)} KE values calculated and stored")
            
            return {
                "status": "success",
                "records_calculated": len(ke_df),
                "records_inserted": inserted,
                "message": f"Calculated and stored {inserted} Cost of Equity values"
            }
        
        except Exception as e:
            logger.error(f"✗ Phase 09 error: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "records_calculated": 0,
                "records_inserted": 0,
                "message": str(e)
            }
    
    # ========================================================================
    # Data Fetching
    # ========================================================================
    
    async def _load_parameters(self, param_set_id: UUID) -> dict:
        """Load relevant parameters for KE calculation."""
        query = text("""
            SELECT 
                parameter_name,
                default_value as value
            FROM cissa.parameters
            WHERE parameter_name IN (
                'cost_of_equity_approach',
                'equity_risk_premium',
                'fixed_benchmark_return_wealth_preservation'
            )
            ORDER BY parameter_name
        """)
        
        result = await self.session.execute(query)
        rows = result.fetchall()
        
        params = {}
        for row in rows:
            param_name, value = row[0], row[1]
            
            # Convert percentages to decimals
            if param_name in ["equity_risk_premium", "fixed_benchmark_return_wealth_preservation"]:
                params[param_name] = float(value) / 100.0
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
                    if key in ["equity_risk_premium", "fixed_benchmark_return_wealth_preservation"]:
                        params[key] = float(value) / 100.0
                    else:
                        params[key] = str(value)
        
        return params
    
    async def _fetch_ke_inputs(self, dataset_id: UUID, param_set_id: UUID) -> tuple:
        """
        Fetch Calc Beta and Calc Rf from metrics_outputs separately.
        
        Returns: (beta_df, rf_df) where each has columns: ticker, fiscal_year, value
        """
        beta_query = text("""
            SELECT ticker, fiscal_year, output_metric_value as value
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
              AND param_set_id = :param_set_id
              AND output_metric_name = 'Calc Beta'
            ORDER BY ticker, fiscal_year
        """)
        
        rf_query = text("""
            SELECT ticker, fiscal_year, output_metric_value as value
            FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
              AND param_set_id = :param_set_id
              AND output_metric_name = 'Calc Rf'
            ORDER BY ticker, fiscal_year
        """)
        
        # Fetch Beta
        beta_result = await self.session.execute(beta_query, {
            "dataset_id": str(dataset_id),
            "param_set_id": str(param_set_id)
        })
        beta_rows = beta_result.fetchall()
        beta_df = pd.DataFrame(
            beta_rows,
            columns=["ticker", "fiscal_year", "value"]
        ) if beta_rows else pd.DataFrame()
        
        # Fetch Rf_1Y
        rf_result = await self.session.execute(rf_query, {
            "dataset_id": str(dataset_id),
            "param_set_id": str(param_set_id)
        })
        rf_rows = rf_result.fetchall()
        rf_df = pd.DataFrame(
            rf_rows,
            columns=["ticker", "fiscal_year", "value"]
        ) if rf_rows else pd.DataFrame()
        
        # Convert Decimal to float
        if not beta_df.empty:
            beta_df["value"] = beta_df["value"].apply(to_float)
            beta_df.rename(columns={"value": "beta"}, inplace=True)
        
        if not rf_df.empty:
            rf_df["value"] = rf_df["value"].apply(to_float)
            rf_df.rename(columns={"value": "rf_1y"}, inplace=True)
        
        return beta_df, rf_df
    
    # ========================================================================
    # Calculation (Vectorized)
    # ========================================================================
    
    def _calculate_ke_vectorized(self, beta_df: pd.DataFrame, rf_df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """
        Calculate KE using vectorized Pandas operations.
        
        KE = Rf + Beta × RiskPremium
        
        Supports two approaches:
        - FIXED: Rf = benchmark - risk_premium (deterministic)
        - FLOATING: Rf = Rf_1Y (from Phase 08)
        """
        approach = params.get("cost_of_equity_approach", "Floating").upper()
        risk_premium = params.get("equity_risk_premium", 0.05)
        
        logger.info(f"    - Using {approach} approach with RP={risk_premium:.4f}")
        
        # Merge Beta and Rf on ticker and fiscal_year (INNER join to get only matching records)
        merged_df = beta_df.merge(rf_df, on=["ticker", "fiscal_year"], how="inner")
        
        if merged_df.empty:
            logger.warning("    No matching Beta-Rf pairs found")
            return pd.DataFrame()
        
        logger.info(f"    - Matching ticker-year pairs: {len(merged_df)}")
        
        # Determine Rf based on approach
        if approach == "FIXED":
            benchmark = params.get("fixed_benchmark_return_wealth_preservation", 0.075)
            rf = benchmark - risk_premium
            logger.info(f"    - FIXED: benchmark={benchmark:.4f}, Rf={rf:.4f}")
            merged_df["rf"] = rf
        else:
            # FLOATING: use Rf_1Y as-is
            merged_df["rf"] = merged_df["rf_1y"]
        
        # Calculate KE = Rf + Beta × RiskPremium (vectorized)
        merged_df["ke"] = merged_df["rf"] + merged_df["beta"] * risk_premium
        
        # Select final columns
        result_df = merged_df[["ticker", "fiscal_year", "ke"]].copy()
        
        return result_df
    
    # ========================================================================
    # Storage (Batch Insert)
    # ========================================================================
    
    async def _insert_ke_batch(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        ke_df: pd.DataFrame
    ) -> int:
        """
        Insert KE values in batches of 1000 using PostgreSQL multi-row INSERT for performance.
        """
        if ke_df.empty:
            return 0
        
        batch_size = 1000
        total_inserted = 0
        
        metadata = json.dumps({"metric_level": "L1", "calculation_source": "cost_of_equity_service"})
        
        for i in range(0, len(ke_df), batch_size):
            batch = ke_df.iloc[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            try:
                # Build multi-row VALUES clause for all rows in batch
                rows_sql = ", ".join([
                    f"('{str(dataset_id)}', '{str(param_set_id)}', '{str(row['ticker'])}', {int(row['fiscal_year'])}, 'Calc KE', {float(row['ke'])}, '{metadata}', now())"
                    for _, row in batch.iterrows()
                ])
                
                # Execute multi-row INSERT with ON CONFLICT UPSERT (single statement for entire batch)
                multi_row_insert = text(f"""
                    INSERT INTO cissa.metrics_outputs 
                    (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata, created_at)
                    VALUES {rows_sql}
                    ON CONFLICT (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name) 
                    DO UPDATE SET output_metric_value = EXCLUDED.output_metric_value, created_at = now()
                """)
                
                await self.session.execute(multi_row_insert)
                await self.session.commit()
                total_inserted += len(batch)
                logger.debug(f"    - Batch {batch_num}: inserted {len(batch)} records (multi-row INSERT)")
            except Exception as e:
                logger.error(f"    - Batch {batch_num} error: {str(e)}", exc_info=True)
                await self.session.rollback()
                raise
        
        return total_inserted
