# ============================================================================
# Risk-Free Rate Calculation Service (Quick Task 01)
# ============================================================================
# Calculates: Risk-free rate (Rf, Rf_1Y, Rf_1Y_Raw) using geometric mean
#             of monthly bond yields from GACGB10 Index (Australian 10-year bonds)
# Stores results in cissa.metrics_outputs table
# Replicates legacy rates.py algorithm with async/await patterns
# ============================================================================

import pandas as pd
import numpy as np
import json
from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..core.config import get_logger

logger = get_logger(__name__)


class RiskFreeRateCalculationService:
    """
    Service for Quick Task 01 risk-free rate calculation.
    
    Calculates risk-free rate using geometric mean of 12 monthly bond yields.
    Replicates legacy rates.py algorithm exactly.
    
    Algorithm:
    1. Fetch monthly RISK_FREE_RATE for bond index (GACGB10 Index)
    2. Group by fiscal_year (12 months per year)
    3. Calculate geometric mean: Rf_1Y_Raw = (∏monthly_rates)^(1/12) - 1
    4. Apply rounding: Rf_1Y = round((Rf_1Y_Raw / beta_rounding), 0) * beta_rounding
    5. Apply approach:
       - If FIXED: Rf = benchmark - risk_premium
       - If Floating: Rf = Rf_1Y
    6. Store 3 metrics in metrics_outputs: Rf_1Y_Raw, Rf_1Y, Rf
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = get_logger(__name__)
    
    async def calculate_risk_free_rate_async(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
    ) -> dict:
        """
        Main orchestration method for risk-free rate calculation.
        
        Args:
            dataset_id: Dataset ID for the calculation
            param_set_id: Parameter set ID (defines rf parameters)
        
        Returns:
            {
                "status": "success|error|cached",
                "results_count": N,
                "message": "..."
            }
        """
        try:
            self.logger.info(f"Starting risk-free rate calculation: dataset={dataset_id}, param_set={param_set_id}")
            
            # 1. Load parameters
            self.logger.info("Loading parameters...")
            params = await self._load_parameters_from_db(param_set_id)
            self.logger.info(f"Parameters loaded: bond_index={params['bond_ticker']}, "
                           f"rounding={params['beta_rounding']}, approach={params['cost_of_equity_approach']}")
            
            # 2. Check if results already exist (upsert logic)
            existing_count = await self._count_existing_rf_results(dataset_id, param_set_id)
            if existing_count > 0:
                self.logger.info(f"Risk-free rate results already exist ({existing_count} records) - returning cached")
                return {
                    "status": "cached",
                    "results_count": existing_count,
                    "message": f"Using cached results for dataset={dataset_id}, param_set={param_set_id}"
                }
            
            # 3. Fetch monthly bond yields
            self.logger.info(f"Fetching monthly bond yields for {params['bond_ticker']}...")
            monthly_rf_df = await self._fetch_monthly_bond_yields(dataset_id, params['bond_ticker'])
            
            if monthly_rf_df.empty:
                self.logger.warning(f"No monthly bond yield data found for {params['bond_ticker']}")
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": f"No monthly bond yield data found for {params['bond_ticker']}"
                }
            
            self.logger.info(f"Fetched {len(monthly_rf_df)} monthly bond yield records")
            
            # 4. Get all unique tickers that need Rf calculation
            self.logger.info("Fetching list of tickers from metrics_outputs (L1 metrics)...")
            company_tickers = await self._fetch_company_tickers(dataset_id, param_set_id)
            self.logger.info(f"Found {len(company_tickers)} unique tickers for Rf calculation")
            
            # 5. Calculate geometric mean for each fiscal year
            self.logger.info("Calculating geometric mean (Rf_1Y_Raw)...")
            rf_raw_df = self._calculate_geometric_mean(monthly_rf_df)
            self.logger.info(f"Calculated geometric mean for {len(rf_raw_df)} fiscal years")
            
            # 6. Apply rounding and approach logic
            self.logger.info(f"Applying rounding (beta_rounding={params['beta_rounding']}) and approach ({params['cost_of_equity_approach']})...")
            rf_final_df = self._apply_rounding_and_approach(
                rf_raw_df,
                params['beta_rounding'],
                params['cost_of_equity_approach'],
                params['benchmark'],
                params['risk_premium']
            )
            
            self.logger.info(f"Risk-free rate calculation complete: {len(rf_final_df)} fiscal years processed")
            
            # 7. Expand to all companies × fiscal years
            self.logger.info("Expanding Rf to all companies...")
            rf_expanded_df = self._expand_to_all_companies(rf_final_df, company_tickers)
            self.logger.info(f"Expanded to {len(rf_expanded_df)} company-fiscal year combinations")
            
            # 8. Format and store results
            self.logger.info("Storing results in metrics_outputs...")
            results_to_store = self._format_results_for_storage(
                rf_expanded_df,
                dataset_id,
                param_set_id
            )
            
            # Store results using raw SQL to avoid ORM foreign key validation issues
            stored_count = await self._store_results_raw_sql(results_to_store)
            await self.session.commit()
            
            self.logger.info(f"Risk-free rate calculation complete: {stored_count} results stored out of {len(rf_expanded_df)} rows")
            
            return {
                "status": "success",
                "results_count": stored_count,
                "message": f"Calculated risk-free rate for {len(company_tickers)} tickers across {len(rf_raw_df)} fiscal years ({stored_count} total records)"
            }
            
        except Exception as e:
            self.logger.error(f"Risk-free rate calculation failed: {type(e).__name__}: {e}")
            await self.session.rollback()
            return {
                "status": "error",
                "results_count": 0,
                "message": f"Risk-free rate calculation failed: {str(e)}"
            }
    
    async def _load_parameters_from_db(self, param_set_id: UUID) -> dict:
        """Load risk-free rate related parameters from database with overrides."""
        try:
            # Load defaults from parameters table
            query = text("""
                SELECT parameter_name, default_value
                FROM cissa.parameters
                WHERE parameter_name IN (
                    'bond_index_by_country', 'beta_rounding', 
                    'cost_of_equity_approach', 'fixed_benchmark_return_wealth_preservation',
                    'equity_risk_premium'
                )
            """)
            
            result = await self.session.execute(query)
            rows = result.fetchall()
            
            params = {
                'bond_index_by_country': '{"Australia": "GACGB10 Index"}',
                'beta_rounding': '0.1',
                'cost_of_equity_approach': 'Floating',
                'fixed_benchmark_return_wealth_preservation': '7.5',
                'equity_risk_premium': '5.0'
            }
            
            for row in rows:
                param_name = row[0]
                value = row[1]
                
                if param_name == 'bond_index_by_country':
                    params[param_name] = value
                elif param_name == 'beta_rounding':
                    params[param_name] = str(float(value))
                elif param_name == 'cost_of_equity_approach':
                    params[param_name] = value
                elif param_name == 'fixed_benchmark_return_wealth_preservation':
                    params[param_name] = str(float(value))
                elif param_name == 'equity_risk_premium':
                    params[param_name] = str(float(value))
            
            # Load overrides from parameter_set
            override_query = text("""
                SELECT param_overrides
                FROM cissa.parameter_sets
                WHERE param_set_id = :param_set_id
            """)
            
            override_result = await self.session.execute(override_query, {"param_set_id": str(param_set_id)})
            override_row = override_result.fetchone()
            
            if override_row and override_row[0]:
                overrides = override_row[0]
                for key, value in overrides.items():
                    if key in params:
                        params[key] = str(value) if not isinstance(value, str) else value
            
            # Parse bond index mapping (Australia only)
            bond_indices_json = params['bond_index_by_country']
            if isinstance(bond_indices_json, str):
                bond_indices = json.loads(bond_indices_json)
            else:
                bond_indices = bond_indices_json
            
            bond_ticker = bond_indices.get('Australia', 'GACGB10 Index')
            
            return {
                'bond_ticker': bond_ticker,
                'beta_rounding': float(params['beta_rounding']),
                'cost_of_equity_approach': params['cost_of_equity_approach'],
                'benchmark': float(params['fixed_benchmark_return_wealth_preservation']),
                'risk_premium': float(params['equity_risk_premium'])
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load parameters: {e}")
            raise
    
    async def _count_existing_rf_results(self, dataset_id: UUID, param_set_id: UUID) -> int:
        """Count existing risk-free rate results for upsert logic."""
        try:
            query = text("""
                SELECT COUNT(*)
                FROM cissa.metrics_outputs
                WHERE dataset_id = :dataset_id
                AND param_set_id = :param_set_id
                AND output_metric_name IN ('Rf', 'Rf_1Y', 'Rf_1Y_Raw')
            """)
            
            result = await self.session.execute(query, {
                "dataset_id": str(dataset_id),
                "param_set_id": str(param_set_id)
            })
            
            return result.scalar() or 0
            
        except Exception as e:
            self.logger.error(f"Failed to count existing results: {e}")
            return 0
    
    async def _fetch_monthly_bond_yields(self, dataset_id: UUID, bond_ticker: str) -> pd.DataFrame:
        """Fetch monthly RISK_FREE_RATE for bond index from fundamentals table."""
        try:
            query = text("""
                SELECT
                    fiscal_year,
                    fiscal_month,
                    numeric_value as rf_monthly
                FROM cissa.fundamentals
                WHERE dataset_id = :dataset_id
                AND metric_name = 'RISK_FREE_RATE'
                AND ticker = :ticker
                AND period_type = 'MONTHLY'
                ORDER BY fiscal_year, fiscal_month
            """)
            
            result = await self.session.execute(query, {
                "dataset_id": str(dataset_id),
                "ticker": bond_ticker
            })
            rows = result.fetchall()
            
            df = pd.DataFrame(
                rows,
                columns=["fiscal_year", "fiscal_month", "rf_monthly"]
            )
            
            # Convert to numeric
            df["rf_monthly"] = pd.to_numeric(df["rf_monthly"], errors="coerce")
            df["fiscal_year"] = pd.to_numeric(df["fiscal_year"], errors="coerce").astype(int)
            df["fiscal_month"] = pd.to_numeric(df["fiscal_month"], errors="coerce").astype(int)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to fetch monthly bond yields: {e}")
            raise
    
    async def _fetch_company_tickers(self, dataset_id: UUID, param_set_id: UUID) -> list:
        """Fetch all unique tickers from L1 metrics already calculated."""
        try:
            query = text("""
                SELECT DISTINCT ticker
                FROM cissa.metrics_outputs
                WHERE dataset_id = :dataset_id
                AND param_set_id = :param_set_id
                AND metadata->>'metric_level' = 'L1'
                ORDER BY ticker
            """)
            
            result = await self.session.execute(query, {
                "dataset_id": str(dataset_id),
                "param_set_id": str(param_set_id)
            })
            
            tickers = [row[0] for row in result.fetchall()]
            return tickers
            
        except Exception as e:
            self.logger.error(f"Failed to fetch company tickers: {e}")
            raise
    
    def _calculate_geometric_mean(self, monthly_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate geometric mean of 12 monthly bond yields per fiscal year.
        
        Geometric mean formula: (∏x_i)^(1/n) - 1
        Where x_i = 1 + rf_monthly/100 (convert percentage to growth rate)
        
        Returns DataFrame with columns: fiscal_year, rf_1y_raw
        """
        try:
            # Group by fiscal year and calculate geometric mean
            def geom_mean(group):
                # Convert percentages to decimal (3.551 → 0.03551)
                rates_decimal = group["rf_monthly"] / 100.0
                # Add 1 to get growth rates (0.03551 → 1.03551)
                growth_rates = 1 + rates_decimal
                # Calculate geometric mean: (∏growth_rates)^(1/n) - 1
                product = np.prod(growth_rates)
                n = len(growth_rates)
                geom_mean_value = np.power(product, 1/n) - 1
                return geom_mean_value
            
            result_df = monthly_df.groupby("fiscal_year").apply(geom_mean).reset_index()
            result_df.columns = ["fiscal_year", "rf_1y_raw"]
            
            return result_df
            
        except Exception as e:
            self.logger.error(f"Failed to calculate geometric mean: {e}")
            raise
    
    def _apply_rounding_and_approach(
        self,
        rf_raw_df: pd.DataFrame,
        beta_rounding: float,
        approach: str,
        benchmark: float,
        risk_premium: float
    ) -> pd.DataFrame:
        """
        Apply rounding and approach logic to risk-free rate.
        
        Rounding: Rf_1Y = round((Rf_1Y_Raw / beta_rounding), 0) * beta_rounding
        Approach:
            - FIXED: Rf = benchmark - risk_premium
            - Floating: Rf = Rf_1Y
        """
        try:
            df = rf_raw_df.copy()
            
            # Apply rounding
            df["rf_1y"] = (df["rf_1y_raw"] / beta_rounding).round(0) * beta_rounding
            
            # Apply approach
            if approach == 'FIXED':
                df["rf"] = benchmark - risk_premium
            else:  # 'Floating' or default
                df["rf"] = df["rf_1y"]
            
            return df[["fiscal_year", "rf_1y_raw", "rf_1y", "rf"]]
            
        except Exception as e:
            self.logger.error(f"Failed to apply rounding and approach: {e}")
            raise
    
    def _expand_to_all_companies(
        self,
        rf_by_year_df: pd.DataFrame,
        company_tickers: list
    ) -> pd.DataFrame:
        """
        Expand annual risk-free rate (one value per fiscal year) to all companies.
        
        Creates a row for each (company_ticker, fiscal_year) combination.
        """
        try:
            # Create cartesian product of companies × fiscal years
            expanded_records = []
            for ticker in company_tickers:
                for _, row in rf_by_year_df.iterrows():
                    expanded_records.append({
                        'ticker': ticker,
                        'fiscal_year': row['fiscal_year'],
                        'rf_1y_raw': row['rf_1y_raw'],
                        'rf_1y': row['rf_1y'],
                        'rf': row['rf']
                    })
            
            return pd.DataFrame(expanded_records)
            
        except Exception as e:
            self.logger.error(f"Failed to expand to all companies: {e}")
            raise
    
    def _format_results_for_storage(
        self,
        rf_df: pd.DataFrame,
        dataset_id: UUID,
        param_set_id: UUID
    ) -> list[dict]:
        """
        Format results for storage in metrics_outputs table.
        
        Creates 3 rows per company-fiscal year: Rf_1Y_Raw, Rf_1Y, Rf
        """
        try:
            records = []
            
            for _, row in rf_df.iterrows():
                ticker = row['ticker']
                fiscal_year = int(row['fiscal_year'])
                
                # Rf_1Y_Raw
                records.append({
                    "dataset_id": dataset_id,
                    "param_set_id": param_set_id,
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "Rf_1Y_Raw",
                    "output_metric_value": float(row['rf_1y_raw']) if pd.notna(row['rf_1y_raw']) else None,
                    "metadata": {"metric_level": "L1"}
                })
                
                # Rf_1Y
                records.append({
                    "dataset_id": dataset_id,
                    "param_set_id": param_set_id,
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "Rf_1Y",
                    "output_metric_value": float(row['rf_1y']) if pd.notna(row['rf_1y']) else None,
                    "metadata": {"metric_level": "L1"}
                })
                
                # Rf
                records.append({
                    "dataset_id": dataset_id,
                    "param_set_id": param_set_id,
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "Rf",
                    "output_metric_value": float(row['rf']) if pd.notna(row['rf']) else None,
                    "metadata": {"metric_level": "L1"}
                })
            
            return records
            
        except Exception as e:
            self.logger.error(f"Failed to format results: {e}")
            raise
    
    async def _store_results_raw_sql(self, records: list[dict]) -> int:
        """Store results using raw SQL INSERT to avoid ORM foreign key validation.
        
        Returns:
            Count of records inserted.
        """
        try:
            if not records:
                return 0
            
            # Filter out records with NULL output_metric_value
            valid_records = [r for r in records if r["output_metric_value"] is not None]
            
            if not valid_records:
                self.logger.warning("No valid results to store (all values are NULL)")
                return 0
            
            # Prepare values for bulk insert
            values = []
            for record in valid_records:
                values.append((
                    str(record["dataset_id"]),
                    str(record["param_set_id"]),
                    record["ticker"],
                    record["fiscal_year"],
                    record["output_metric_name"],
                    record["output_metric_value"],
                    json.dumps(record["metadata"])
                ))
            
            # Bulk insert using raw SQL
            query = text("""
                INSERT INTO cissa.metrics_outputs 
                (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata)
                VALUES (:dataset_id, :param_set_id, :ticker, :fiscal_year, :output_metric_name, :output_metric_value, :metadata)
                ON CONFLICT (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
                DO NOTHING
            """)
            
            for value_tuple in values:
                await self.session.execute(query, {
                    "dataset_id": value_tuple[0],
                    "param_set_id": value_tuple[1],
                    "ticker": value_tuple[2],
                    "fiscal_year": value_tuple[3],
                    "output_metric_name": value_tuple[4],
                    "output_metric_value": value_tuple[5],
                    "metadata": value_tuple[6]
                })
            
            self.logger.info(f"Inserted {len(valid_records)} valid records out of {len(records)} total (skipped {len(records) - len(valid_records)} NULL values)")
            
            return len(valid_records)
            
        except Exception as e:
            self.logger.error(f"Failed to store results: {e}")
            raise
