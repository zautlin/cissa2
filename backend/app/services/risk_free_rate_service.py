# ============================================================================
# Risk-Free Rate Calculation Service (Phase 08)
# ============================================================================
# Calculates: Risk-free rate (Rf, Rf_1Y, Rf_1Y_Raw) using ROLLING 12-MONTH 
#             geometric mean of monthly bond yields from bond index
# Stores results in cissa.metrics_outputs table
# Implements legacy rates.py algorithm with rolling window calculation
# ============================================================================

import pandas as pd
import numpy as np
import json
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..core.config import get_logger

logger = get_logger(__name__)


class RiskFreeRateCalculationService:
    """
    Service for Phase 08 risk-free rate calculation.
    
    Calculates risk-free rate using ROLLING 12-MONTH geometric mean of monthly bond yields.
    Implements legacy rates.py algorithm with per-calendar-month rolling window.
    
    Key features:
    - Calculates Rf ONLY for the bond index (e.g., GACGB10 Index for Australia)
    - Each calendar month gets a 12-month rolling geometric mean
    - Jan 2002 uses Feb 2001 - Jan 2002 (prior 12 months including current)
    - Stores only December value for each year in metrics_outputs
    - Stores all 12 monthly values in metadata for reference
    
    Algorithm:
    1. Fetch monthly RISK_FREE_RATE for bond index - full history
    2. For each calendar month in the data:
       - Calculate rolling 12-month geometric mean: (∏rf_prel)^(1/12) - 1
       - Apply rounding: round((result / beta_rounding), 0) * beta_rounding
    3. Extract December value for each year
    4. Store with metadata containing all 12 monthly values
    5. Create 3 metrics per year: Rf_1Y_Raw, Rf_1Y, Rf
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = get_logger(__name__)
        self.fiscal_year_definitions = {
            'AU': (7, 6),   # Australia: Jul-Jun fiscal year
            'US': (1, 12),  # US: Jan-Dec fiscal year
        }
    
    async def calculate_risk_free_rate_async(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        country_code: str = 'AU',
    ) -> dict:
        """
        Main orchestration method for risk-free rate calculation.
        
        Uses ROLLING 12-MONTH geometric mean approach for accurate monthly Rf values.
        Stores only December values for each year.
        
        Args:
            dataset_id: Dataset ID for the calculation
            param_set_id: Parameter set ID (defines rf parameters)
            country_code: Country code for fiscal year definition (default: 'AU')
        
        Returns:
            {
                "status": "success|error",
                "results_count": N,
                "message": "..."
            }
        """
        try:
            self.logger.info(f"Starting risk-free rate calculation (Phase 08): dataset={dataset_id}, param_set={param_set_id}, country={country_code}")
            
            # 1. Load parameters
            self.logger.info("Loading parameters...")
            params = await self._load_parameters_from_db(param_set_id)
            self.logger.info(f"Parameters loaded: bond_ticker={params['bond_ticker']}, "
                           f"rounding={params['beta_rounding']}, approach={params['cost_of_equity_approach']}")
            
            # 2. Get bond index ticker from dataset
            self.logger.info("Fetching bond index ticker from dataset...")
            bond_ticker = await self._get_bond_ticker_from_dataset(dataset_id)
            if not bond_ticker:
                bond_ticker = params['bond_ticker']
            self.logger.info(f"Using bond ticker: {bond_ticker}")
            
            # 3. Check if results already exist and clear them
            existing_count = await self._count_existing_rf_results(bond_ticker, param_set_id)
            if existing_count > 0:
                self.logger.info(f"Risk-free rate results already exist ({existing_count} records) - clearing")
                await self._clear_existing_rf_results(bond_ticker, param_set_id)
            
            # 4. Fetch monthly bond yields (full history)
            self.logger.info(f"Fetching monthly bond yields for {bond_ticker}...")
            monthly_rf_df = await self._fetch_monthly_bond_yields(bond_ticker)
            
            if monthly_rf_df.empty:
                self.logger.warning(f"No monthly bond yield data found for {bond_ticker}")
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": f"No monthly bond yield data found for {bond_ticker}"
                }
            
            self.logger.info(f"Fetched {len(monthly_rf_df)} monthly bond yield records")
            
            # 5. Calculate ROLLING 12-month geometric mean for each calendar month
            self.logger.info("Calculating rolling 12-month geometric mean (Rf_1Y_Raw)...")
            rf_monthly_df = self._calculate_rolling_geometric_mean(monthly_rf_df)
            self.logger.info(f"Calculated rolling geometric mean for {len(rf_monthly_df)} calendar months")
            
            # 6. Apply rounding and approach logic
            self.logger.info(f"Applying rounding (beta_rounding={params['beta_rounding']}) and approach ({params['cost_of_equity_approach']})...")
            rf_monthly_final_df = self._apply_rounding_and_approach(
                rf_monthly_df,
                params['beta_rounding'],
                params['cost_of_equity_approach'],
                params['benchmark'],
                params['risk_premium']
            )
            
            # 7. Extract December values for each year
            self.logger.info("Extracting December values for each year...")
            rf_yearly_df = self._extract_december_values(rf_monthly_final_df)
            self.logger.info(f"Extracted {len(rf_yearly_df)} yearly values (December only)")
            
            # 8. Build metadata with all 12 monthly values
            self.logger.info("Building metadata with all 12 monthly values...")
            rf_yearly_with_metadata = self._build_yearly_with_metadata(
                rf_yearly_df,
                rf_monthly_final_df
            )
            
            # 9. Format and store results
            self.logger.info("Storing results in metrics_outputs...")
            results_to_store = self._format_results_for_storage(
                rf_yearly_with_metadata,
                bond_ticker,
                dataset_id,
                param_set_id
            )
            
            # Store results using raw SQL
            stored_count = await self._store_results_raw_sql(results_to_store)
            await self.session.commit()
            
            self.logger.info(f"Risk-free rate calculation complete: {stored_count} results stored for {bond_ticker}")
            
            return {
                "status": "success",
                "results_count": stored_count,
                "message": f"Calculated risk-free rate for {bond_ticker} using rolling 12-month geometric mean ({stored_count} total records)"
            }
            
        except Exception as e:
            self.logger.error(f"Risk-free rate calculation failed: {e}", exc_info=True)
            return {
                "status": "error",
                "results_count": 0,
                "message": f"Calculation failed: {str(e)}"
            }
    
    async def _load_parameters_from_db(self, param_set_id: UUID) -> dict:
        """Load calculation parameters from database (from param_overrides JSONB)."""
        try:
            query = text("""
                SELECT param_overrides
                FROM cissa.parameter_sets
                WHERE param_set_id = :param_set_id
                LIMIT 1
            """)
            
            result = await self.session.execute(query, {"param_set_id": param_set_id})
            row = result.fetchone()
            
            # Default parameters
            defaults = {
                "bond_ticker": "GACGB10 Index",
                "beta_rounding": 0.005,
                "cost_of_equity_approach": "FLOATING",
                "benchmark": 0.0,
                "risk_premium": 0.0
            }
            
            if row and row[0]:
                overrides = row[0]
                # Merge overrides with defaults
                params = {**defaults}
                
                if isinstance(overrides, dict):
                    for key in defaults.keys():
                        if key in overrides:
                            params[key] = overrides[key]
                
                # Convert to proper types
                params["beta_rounding"] = float(params.get("beta_rounding", 0.005))
                params["benchmark"] = float(params.get("benchmark", 0.0))
                params["risk_premium"] = float(params.get("risk_premium", 0.0))
                
                return params
            else:
                return defaults
        except Exception as e:
            self.logger.error(f"Failed to load parameters: {e}")
            raise
    
    async def _get_bond_ticker_from_dataset(self, dataset_id: UUID) -> str:
        """Try to detect bond ticker from dataset metadata."""
        try:
            query = text("""
                SELECT metadata->>'bond_ticker'
                FROM cissa.datasets
                WHERE dataset_id = :dataset_id
                LIMIT 1
            """)
            
            result = await self.session.execute(query, {"dataset_id": dataset_id})
            row = result.fetchone()
            return row[0] if row and row[0] else None
        except Exception as e:
            self.logger.warning(f"Could not get bond ticker from dataset: {e}")
            # Clear the transaction on error to allow further operations
            await self.session.rollback()
            return None
    
    async def _count_existing_rf_results(self, bond_ticker: str, param_set_id: UUID) -> int:
        """Count existing Rf results for this bond ticker."""
        try:
            query = text("""
                SELECT COUNT(*) as count
                FROM cissa.metrics_outputs
                WHERE ticker = :ticker
                AND param_set_id = :param_set_id
                AND output_metric_name IN ('Rf', 'Rf_1Y', 'Rf_1Y_Raw')
            """)
            
            result = await self.session.execute(query, {
                "ticker": bond_ticker,
                "param_set_id": param_set_id
            })
            row = result.fetchone()
            return row[0] if row else 0
        except Exception as e:
            self.logger.error(f"Failed to count existing results: {e}")
            return 0
    
    async def _clear_existing_rf_results(self, bond_ticker: str, param_set_id: UUID) -> int:
        """Delete existing Rf results before recalculation."""
        try:
            query = text("""
                DELETE FROM cissa.metrics_outputs
                WHERE ticker = :ticker
                AND param_set_id = :param_set_id
                AND output_metric_name IN ('Rf', 'Rf_1Y', 'Rf_1Y_Raw')
            """)
            
            result = await self.session.execute(query, {
                "ticker": bond_ticker,
                "param_set_id": param_set_id
            })
            
            deleted = result.rowcount
            self.logger.info(f"Deleted {deleted} existing Rf results for {bond_ticker}")
            return deleted
        except Exception as e:
            self.logger.error(f"Failed to clear existing results: {e}")
            raise
    
    async def _fetch_monthly_bond_yields(self, bond_ticker: str) -> pd.DataFrame:
        """Fetch FULL HISTORY of monthly bond yields (RISK_FREE_RATE)."""
        try:
            query = text("""
                SELECT
                    fiscal_year,
                    fiscal_month,
                    numeric_value as rf_monthly
                FROM cissa.fundamentals
                WHERE metric_name = 'RISK_FREE_RATE'
                AND ticker = :ticker
                AND period_type = 'MONTHLY'
                ORDER BY fiscal_year ASC, fiscal_month ASC
            """)
            
            result = await self.session.execute(query, {"ticker": bond_ticker})
            rows = result.fetchall()
            
            df = pd.DataFrame(
                rows,
                columns=["fiscal_year", "fiscal_month", "rf_monthly"]
            )
            
            # Convert to numeric
            df["rf_monthly"] = pd.to_numeric(df["rf_monthly"], errors="coerce")
            df["fiscal_year"] = pd.to_numeric(df["fiscal_year"], errors="coerce").astype(int)
            df["fiscal_month"] = pd.to_numeric(df["fiscal_month"], errors="coerce").astype(int)
            
            # Sort by year and month
            df = df.sort_values(["fiscal_year", "fiscal_month"]).reset_index(drop=True)
            
            self.logger.info(f"Loaded {len(df)} monthly records from {df['fiscal_year'].min()} to {df['fiscal_year'].max()}")
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to fetch monthly bond yields: {e}")
            raise
    
    def _calculate_rolling_geometric_mean(self, monthly_rf_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate rolling 12-month geometric mean for each calendar month.
        
        For each month, uses the prior 12 months (including current month) to calculate
        the geometric mean.
        
        Formula: Rf_1Y_Raw = (∏rf_prel)^(1/12) - 1
        where rf_prel = (rf_monthly / 100) + 1
        """
        try:
            if monthly_rf_df.empty:
                self.logger.warning("Empty monthly data provided to rolling mean calculation")
                return pd.DataFrame()
            
            df = monthly_rf_df.copy()
            
            # Convert Rf % to growth rate (rf_prel)
            # rf_prel = (rf_monthly / 100) + 1
            df["rf_prel"] = (df["rf_monthly"] / 100) + 1
            
            # Calculate rolling 12-month geometric mean
            # Using rolling window of 12 rows
            df["rf_1y_raw"] = df["rf_prel"].rolling(window=12).apply(
                lambda x: np.power(np.prod(x), 1/12) - 1 if len(x) == 12 else np.nan,
                raw=False
            )
            
            # First 11 months will be NaN - fill with the first valid value
            first_valid = df[df["rf_1y_raw"].notna()]["rf_1y_raw"].iloc[0] if df["rf_1y_raw"].notna().any() else 0
            df["rf_1y_raw"] = df["rf_1y_raw"].fillna(first_valid)
            
            self.logger.info(f"Rolling geometric mean calculated: {df['rf_1y_raw'].min():.6f} to {df['rf_1y_raw'].max():.6f}")
            
            # Keep only necessary columns
            result_df = df[["fiscal_year", "fiscal_month", "rf_1y_raw"]].copy()
            
            return result_df
            
        except Exception as e:
            self.logger.error(f"Failed to calculate rolling geometric mean: {e}")
            raise
    
    def _apply_rounding_and_approach(
        self,
        rf_monthly_df: pd.DataFrame,
        beta_rounding: float,
        cost_of_equity_approach: str,
        benchmark: float = 0.0,
        risk_premium: float = 0.0
    ) -> pd.DataFrame:
        """
        Apply rounding and approach logic to Rf_1Y_Raw values.
        
        Rounding formula: Rf_1Y = ROUND(Rf_1Y_Raw / beta_rounding, 0) * beta_rounding
        
        Approach:
        - FIXED: Rf = benchmark - risk_premium
        - FLOATING: Rf = Rf_1Y (market-based)
        """
        try:
            df = rf_monthly_df.copy()
            
            # Apply rounding
            df["rf_1y"] = np.round(df["rf_1y_raw"] / beta_rounding, 0) * beta_rounding
            
            # Apply approach
            if cost_of_equity_approach == "FIXED":
                df["rf"] = benchmark - risk_premium
                self.logger.info(f"Applied FIXED approach: Rf = {benchmark} - {risk_premium} = {df['rf'].iloc[0]}")
            else:  # FLOATING (default)
                df["rf"] = df["rf_1y"]
                self.logger.info(f"Applied FLOATING approach: Rf = Rf_1Y (market-based)")
            
            # Ensure reasonable bounds (0-1 or 0-100% range)
            # If values are in percentage form (0-100), cap at 100%; if decimal (0-1), cap at 1
            max_val = df[["rf_1y", "rf"]].max().max()
            if max_val > 1:
                # Values are in percentage form, cap at 100%
                df["rf"] = df["rf"].clip(upper=1.0)
                df["rf_1y"] = df["rf_1y"].clip(upper=1.0)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to apply rounding and approach: {e}")
            raise
    
    def _extract_december_values(self, rf_monthly_df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract December (month 12) values for each fiscal year.
        
        Returns one row per year containing the December Rf values.
        """
        try:
            # Filter for December only (fiscal_month = 12)
            december_df = rf_monthly_df[rf_monthly_df["fiscal_month"] == 12].copy()
            
            if december_df.empty:
                self.logger.warning("No December data found in monthly Rf data")
                return pd.DataFrame()
            
            # Group by fiscal_year and keep December values
            result_df = december_df[["fiscal_year", "rf_1y_raw", "rf_1y", "rf"]].copy()
            result_df = result_df.sort_values("fiscal_year").reset_index(drop=True)
            
            self.logger.info(f"Extracted {len(result_df)} December values (fiscal years {result_df['fiscal_year'].min()}-{result_df['fiscal_year'].max()})")
            
            return result_df
            
        except Exception as e:
            self.logger.error(f"Failed to extract December values: {e}")
            raise
    
    def _build_yearly_with_metadata(
        self,
        rf_yearly_df: pd.DataFrame,
        rf_monthly_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Build yearly dataframe with metadata containing all 12 monthly values.
        
        Metadata structure:
        {
            "metric_level": "L1",
            "monthly_values": [
                {"month": 1, "rf_1y_raw": 0.0589, "rf_1y": 0.060, "rf": 0.100},
                ...
                {"month": 12, "rf_1y_raw": 0.0612, "rf_1y": 0.061, "rf": 0.100}
            ]
        }
        """
        try:
            result_records = []
            
            for _, yearly_row in rf_yearly_df.iterrows():
                fiscal_year = int(yearly_row['fiscal_year'])
                
                # Get all 12 months for this year
                yearly_monthly = rf_monthly_df[rf_monthly_df['fiscal_year'] == fiscal_year]
                
                # Build monthly values array
                monthly_values = []
                for _, monthly_row in yearly_monthly.iterrows():
                    monthly_values.append({
                        "month": int(monthly_row['fiscal_month']),
                        "rf_1y_raw": round(float(monthly_row['rf_1y_raw']), 4),
                        "rf_1y": round(float(monthly_row['rf_1y']), 4),
                        "rf": round(float(monthly_row['rf']), 4)
                    })
                
                # Build metadata
                metadata = {
                    "metric_level": "L1",
                    "monthly_values": monthly_values
                }
                
                # Create record with metadata
                result_records.append({
                    "fiscal_year": fiscal_year,
                    "rf_1y_raw": round(float(yearly_row['rf_1y_raw']), 4),
                    "rf_1y": round(float(yearly_row['rf_1y']), 4),
                    "rf": round(float(yearly_row['rf']), 4),
                    "metadata": metadata
                })
            
            result_df = pd.DataFrame(result_records)
            self.logger.info(f"Built metadata for {len(result_df)} yearly records")
            
            return result_df
            
        except Exception as e:
            self.logger.error(f"Failed to build yearly metadata: {e}")
            raise
    
    def _format_results_for_storage(
        self,
        rf_df: pd.DataFrame,
        bond_ticker: str,
        dataset_id: UUID,
        param_set_id: UUID
    ) -> list[dict]:
        """
        Format results for storage in metrics_outputs table.
        
        Creates 3 rows per fiscal year: Rf_1Y_Raw, Rf_1Y, Rf
        Each row includes the metadata with all 12 monthly values.
        """
        try:
            records = []
            
            for _, row in rf_df.iterrows():
                fiscal_year = int(row['fiscal_year'])
                metadata = row['metadata']
                
                # Rf_1Y_Raw
                records.append({
                    "dataset_id": dataset_id,
                    "param_set_id": param_set_id,
                    "ticker": bond_ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "Rf_1Y_Raw",
                    "output_metric_value": float(row['rf_1y_raw']) if pd.notna(row['rf_1y_raw']) else None,
                    "metadata": metadata
                })
                
                # Rf_1Y
                records.append({
                    "dataset_id": dataset_id,
                    "param_set_id": param_set_id,
                    "ticker": bond_ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "Rf_1Y",
                    "output_metric_value": float(row['rf_1y']) if pd.notna(row['rf_1y']) else None,
                    "metadata": metadata
                })
                
                # Rf
                records.append({
                    "dataset_id": dataset_id,
                    "param_set_id": param_set_id,
                    "ticker": bond_ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "Rf",
                    "output_metric_value": float(row['rf']) if pd.notna(row['rf']) else None,
                    "metadata": metadata
                })
            
            self.logger.info(f"Formatted {len(records)} records for storage ({len(rf_df)} years × 3 metrics)")
            
            return records
            
        except Exception as e:
            self.logger.error(f"Failed to format results: {e}")
            raise
    
    async def _store_results_raw_sql(self, results: list[dict]) -> int:
        """
        Store results using raw SQL with UPSERT logic.
        
        Uses DO UPDATE clause to handle conflicts on (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name).
        """
        try:
            if not results:
                self.logger.warning("No results to store")
                return 0
            
            # Prepare data for bulk insert
            insert_query = text("""
                INSERT INTO cissa.metrics_outputs 
                (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata)
                VALUES (:dataset_id, :param_set_id, :ticker, :fiscal_year, :output_metric_name, :output_metric_value, :metadata)
                ON CONFLICT (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
                DO UPDATE SET
                    output_metric_value = EXCLUDED.output_metric_value,
                    metadata = EXCLUDED.metadata
            """)
            
            # Insert records in batches
            batch_size = 1000
            for i in range(0, len(results), batch_size):
                batch = results[i:i+batch_size]
                
                for record in batch:
                    await self.session.execute(insert_query, {
                        "dataset_id": record["dataset_id"],
                        "param_set_id": record["param_set_id"],
                        "ticker": record["ticker"],
                        "fiscal_year": record["fiscal_year"],
                        "output_metric_name": record["output_metric_name"],
                        "output_metric_value": record["output_metric_value"],
                        "metadata": json.dumps(record["metadata"])
                    })
            
            self.logger.info(f"Stored {len(results)} records")
            return len(results)
            
        except Exception as e:
            self.logger.error(f"Failed to store results: {e}")
            raise
