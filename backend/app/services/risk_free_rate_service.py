# ============================================================================
# Risk-Free Rate Calculation Service (Phase 08)
# ============================================================================
# Calculates: Calc Rf (final risk-free rate metric) using ROLLING 12-MONTH 
#             geometric mean of monthly bond yields from bond index
# Stores results in cissa.metrics_outputs table
# Implements legacy rates.py algorithm with rolling window calculation
# Algorithm:
#   1. Calculate Rf_1Y_Raw (12-month rolling geometric mean, unrounded)
#   2. Calculate Rf_1Y (rounded to nearest beta_rounding)
#   3. Apply approach logic to get Calc Rf:
#      - Fixed: Calc Rf = Benchmark - Risk Premium (static)
#      - Floating: Calc Rf = Rf_1Y (dynamic, year-specific)
#   4. Store only Calc Rf (one value per fiscal year)
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
    
    Calculates Calc Rf (final metric) using legacy rates.py algorithm:
    1. Calculate Rf_1Y_Raw: rolling 12-month geometric mean (unrounded)
    2. Calculate Rf_1Y: rounded to nearest beta_rounding (0.5%)
    3. Apply approach logic:
       - Fixed: Calc Rf = Benchmark - Risk Premium (static, same all years)
       - Floating: Calc Rf = Rf_1Y (dynamic, varies by year)
    4. Store ONLY Calc Rf in metrics_outputs (one row per fiscal year)
    
    Key features:
    - Calculates for bond index (e.g., GACGB10 Index for Australia)
    - Each calendar month gets 12-month rolling geometric mean
    - Extracts December value for each fiscal year
    - Stores single Calc Rf metric (not intermediate values)
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
        Main orchestration method for risk-free rate calculation with ticker-specific FY end dates.
        
        Flow:
        1. Load parameters (approach, rounding, benchmark, risk_premium)
        2. Determine currency from country (AU -> AUD)
        3. Fetch bond ticker for currency (AUD -> GACGB10 Index)
        4. Fetch monthly bond yields for bond index
        5. Calculate rolling 12-month geometric mean (Rf_1Y_Raw)
        6. Apply approach logic to get Calc Rf (Fixed or Floating)
        7. Fetch all company tickers for the currency
        8. Fetch FY end dates for each company ticker
        9. Extract Calc Rf values using each ticker's specific FY end date
        10. Format and store results (~21,000 records)
        
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
            self.logger.info(f"Starting risk-free rate calculation with ticker-specific FY dates (Phase 08): dataset={dataset_id}, param_set={param_set_id}, country={country_code}")
            
            # Determine currency from country code
            currency_map = {'AU': 'AUD', 'US': 'USD', 'UK': 'GBP'}
            currency = currency_map.get(country_code, 'AUD')
            self.logger.info(f"Using currency: {currency}")
            
            # 1. Load parameters
            self.logger.info("Loading parameters...")
            params = await self._load_parameters_from_db(param_set_id)
            self.logger.info(f"Parameters loaded: approach={params['cost_of_equity_approach']}, "
                           f"rounding={params['beta_rounding']}")
            
            # 2. Fetch bond ticker for currency (e.g., AUD -> GACGB10 Index)
            self.logger.info(f"Fetching bond ticker for currency {currency}...")
            bond_ticker = await self._fetch_bond_ticker_by_currency(currency)
            if not bond_ticker:
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": f"No bond ticker found for currency {currency}"
                }
            self.logger.info(f"Using bond ticker: {bond_ticker}")
            
            # 3. Fetch all company tickers for currency
            self.logger.info(f"Fetching all company tickers for currency {currency}...")
            all_tickers = await self._fetch_all_company_tickers_by_currency(currency)
            if not all_tickers:
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": f"No company tickers found for currency {currency}"
                }
            
            # 4. Clear existing results for all company tickers
            existing_count = await self._clear_all_company_rf_results(all_tickers, param_set_id)
            if existing_count > 0:
                self.logger.info(f"Cleared {existing_count} existing Rf results for {len(all_tickers)} company tickers")
            
            # 5. Fetch monthly bond yields (full history)
            self.logger.info(f"Fetching monthly bond yields for {bond_ticker}...")
            monthly_rf_df = await self._fetch_monthly_bond_yields(bond_ticker)
            
            if monthly_rf_df.empty:
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": f"No monthly bond yield data found for {bond_ticker}"
                }
            
            self.logger.info(f"Fetched {len(monthly_rf_df)} monthly bond yield records")
            
            # 6. Calculate ROLLING 12-month geometric mean for each calendar month
            self.logger.info("Calculating rolling 12-month geometric mean (Rf_1Y_Raw)...")
            rf_monthly_df = self._calculate_rolling_geometric_mean(monthly_rf_df)
            self.logger.info(f"Calculated rolling geometric mean for {len(rf_monthly_df)} calendar months")
            
            # 7. Calculate Calc Rf (apply approach logic: Fixed or Floating)
            self.logger.info(f"Calculating Calc Rf with approach ({params['cost_of_equity_approach']})...")
            rf_monthly_calc_df = self._calculate_calc_rf(
                rf_monthly_df,
                params['cost_of_equity_approach'],
                params['benchmark'],
                params['risk_premium'],
                params['beta_rounding']
            )
            
            # 8. Fetch FY end dates for all company tickers
            self.logger.info(f"Fetching FY end dates for {len(all_tickers)} company tickers...")
            fy_dates_dict = await self._fetch_fy_end_dates_for_tickers(all_tickers)
            self.logger.info(f"Fetched FY end dates for {len(fy_dates_dict)} tickers")
            
            # 9. Extract Calc Rf using each ticker's specific FY end date
            self.logger.info("Extracting Calc Rf by ticker-specific FY end dates...")
            rf_expanded_df = self._extract_rf_by_fy_end_date(rf_monthly_calc_df, fy_dates_dict)
            
            if rf_expanded_df.empty:
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": "Failed to extract Calc Rf by FY end dates"
                }
            
            self.logger.info(f"Extracted {len(rf_expanded_df)} Calc Rf values for company tickers")
            
            # 10. Format and store results
            self.logger.info("Formatting and storing results in metrics_outputs...")
            results_to_store = self._format_results_for_storage(
                rf_expanded_df,
                dataset_id,
                param_set_id
            )
            
            # Store results using raw SQL
            stored_count = await self._store_results_raw_sql(results_to_store)
            await self.session.commit()
            
            self.logger.info(f"Risk-free rate calculation complete: {stored_count} results stored for company tickers")
            
            return {
                "status": "success",
                "results_count": stored_count,
                "message": f"Calculated Calc Rf for {len(all_tickers)} tickers using ticker-specific FY end dates ({stored_count} total records)"
            }
        
        except Exception as e:
            self.logger.error(f"Risk-free rate calculation failed: {e}", exc_info=True)
            return {
                "status": "error",
                "results_count": 0,
                "message": f"Calculation failed: {str(e)}"
            }
    
    async def calculate_risk_free_rate_runtime(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        country_code: str = 'AU',
    ) -> float:
        """
        Calculate risk-free rate at runtime (returns single value for a ticker/year).
        
        Used by Cost of Equity service when calculating KE at runtime.
        
        Args:
            dataset_id: Dataset ID
            param_set_id: Parameter set ID (for approach and rounding)
            country_code: Country code for fiscal year definitions
            
        Returns:
            float: Calculated risk-free rate value
            
        Raises:
            Exception: If calculation fails
        """
        try:
            self.logger.info(f"Starting runtime risk-free rate calculation: dataset={dataset_id}, param_set={param_set_id}")
            
            # Determine currency from country code
            currency_map = {'AU': 'AUD', 'US': 'USD', 'UK': 'GBP'}
            currency = currency_map.get(country_code, 'AUD')
            
            # Load parameters
            params = await self._load_parameters_from_db(param_set_id)
            approach = params.get('cost_of_equity_approach', 'FLOATING').upper()
            rounding = params.get('beta_rounding', 0.005)
            benchmark = params.get('benchmark', 0.0)
            risk_premium = params.get('risk_premium', 0.0)
            
            self.logger.info(f"Rf calculation params: approach={approach}, rounding={rounding}, benchmark={benchmark}")
            
            # Fetch bond ticker
            bond_ticker = await self._fetch_bond_ticker_by_currency(currency)
            if not bond_ticker:
                raise ValueError(f"No bond ticker found for currency {currency}")
            
            # Fetch monthly bond yields
            monthly_rf_df = await self._fetch_monthly_bond_yields(bond_ticker)
            if monthly_rf_df.empty:
                raise ValueError(f"No bond yield data found for {bond_ticker}")
            
            # Calculate rolling 12-month geometric mean
            rf_monthly_df = self._calculate_rolling_geometric_mean(monthly_rf_df)
            
            # Get the most recent value (latest fiscal year end)
            rf_monthly_calc_df = self._calculate_calc_rf(rf_monthly_df, params)
            
            if rf_monthly_calc_df.empty:
                raise ValueError("No risk-free rate values calculated")
            
            # Extract the most recent December value (or FY end)
            latest_value = rf_monthly_calc_df.iloc[-1]['calc_rf']
            
            self.logger.info(f"✓ Runtime Rf calculation complete: {latest_value:.6f}")
            return float(latest_value)
        
        except Exception as e:
            self.logger.error(f"Runtime risk-free rate calculation failed: {e}", exc_info=True)
            raise


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
                AND output_metric_name = 'Calc Rf'
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
                AND output_metric_name = 'Calc Rf'
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

    async def _fetch_bond_ticker_by_currency(self, currency: str) -> str:
        """Fetch bond ticker for a given currency from fundamentals."""
        try:
            query = text("""
                SELECT DISTINCT ticker
                FROM cissa.fundamentals
                WHERE metric_name = 'RISK_FREE_RATE'
                AND currency = :currency
                LIMIT 1
            """)
            
            result = await self.session.execute(query, {"currency": currency})
            row = result.fetchone()
            
            if row:
                ticker = row[0]
                self.logger.info(f"Found bond ticker for currency {currency}: {ticker}")
                return ticker
            else:
                self.logger.warning(f"No bond ticker found for currency {currency}")
                return None
        except Exception as e:
            self.logger.error(f"Failed to fetch bond ticker by currency: {e}")
            raise
    
    async def _fetch_all_company_tickers_by_currency(self, currency: str) -> list:
        """Fetch all company tickers for a given currency."""
        try:
            query = text("""
                SELECT DISTINCT ticker
                FROM cissa.companies
                WHERE currency = :currency
                ORDER BY ticker
            """)
            
            result = await self.session.execute(query, {"currency": currency})
            rows = result.fetchall()
            tickers = [row[0] for row in rows]
            
            self.logger.info(f"Fetched {len(tickers)} company tickers for currency {currency}")
            return tickers
        except Exception as e:
            self.logger.error(f"Failed to fetch company tickers by currency: {e}")
            raise
    
    async def _clear_all_company_rf_results(self, tickers: list, param_set_id: UUID) -> int:
        """Delete existing Rf results for all company tickers before recalculation."""
        try:
            if not tickers:
                return 0
            
            # Create placeholders for SQL IN clause
            placeholders = ', '.join([f"'{ticker}'" for ticker in tickers])
            
            query = text(f"""
                DELETE FROM cissa.metrics_outputs
                WHERE ticker IN ({placeholders})
                AND param_set_id = :param_set_id
                AND output_metric_name = 'Calc Rf'
            """)
            
            result = await self.session.execute(query, {"param_set_id": param_set_id})
            
            deleted = result.rowcount
            self.logger.info(f"Deleted {deleted} existing Rf results for {len(tickers)} company tickers")
            return deleted
        except Exception as e:
            self.logger.error(f"Failed to clear existing company results: {e}")
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
            
            # Keep necessary columns including rf_prel for later use
            result_df = df[["fiscal_year", "fiscal_month", "rf_prel", "rf_1y_raw"]].copy()
            
            return result_df
            
        except Exception as e:
            self.logger.error(f"Failed to calculate rolling geometric mean: {e}")
            raise
    
    def _calculate_calc_rf(
        self,
        rf_monthly_df: pd.DataFrame,
        cost_of_equity_approach: str,
        benchmark: float = 0.0,
        risk_premium: float = 0.0,
        beta_rounding: float = 0.005
    ) -> pd.DataFrame:
        """
        Calculate final Calc Rf by applying approach logic.
        
        Implements legacy rates.py logic:
        - Calculates Rf_1Y: ROUND(Rf_1Y_Raw / beta_rounding, 0) * beta_rounding
        - Applies approach:
          - Fixed: Calc Rf = Benchmark - Risk Premium (static, same all years)
          - Floating: Calc Rf = Rf_1Y (rolling geometric mean, varies by year)
        
        Args:
            rf_monthly_df: DataFrame with rf_1y_raw column
            cost_of_equity_approach: 'FIXED' or 'FLOATING'
            benchmark: Benchmark rate (e.g., 0.075 for 7.5%)
            risk_premium: Risk premium (e.g., 0.050 for 5.0%)
            beta_rounding: Rounding factor (e.g., 0.005 for 0.5%)
        
        Returns:
            DataFrame with calc_rf column (final metric)
        """
        try:
            df = rf_monthly_df.copy()
            
            # Step 1: Calculate Rf_1Y (rounded 12-month geometric mean)
            df["rf_1y"] = np.round(df["rf_1y_raw"] / beta_rounding, 0) * beta_rounding
            
            # Step 2: Apply approach logic to get Calc Rf
            if cost_of_equity_approach.upper() == "FIXED":
                # Fixed approach: static value = Benchmark - Risk Premium
                fixed_rf = benchmark - risk_premium
                df["calc_rf"] = np.round(fixed_rf / beta_rounding, 0) * beta_rounding
                self.logger.info(f"Fixed approach: Calc Rf = {fixed_rf:.6f} (Benchmark {benchmark:.6f} - Premium {risk_premium:.6f})")
            else:
                # Floating approach: Calc Rf = Rf_1Y (rounded geometric mean)
                df["calc_rf"] = df["rf_1y"]
                self.logger.info(f"Floating approach: Calc Rf varies by year (using Rf_1Y)")
            
            # Return only necessary columns
            return df[["fiscal_year", "fiscal_month", "calc_rf"]]
            
        except Exception as e:
            self.logger.error(f"Failed to calculate Calc Rf: {e}")
            raise
    
    def _extract_december_values(self, rf_monthly_df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract December (month 12) Calc Rf value for each fiscal year.
        
        Returns one row per year containing:
        - fiscal_year: The fiscal year
        - calc_rf: The final Calc Rf metric value (either static or rolling)
        """
        try:
            # Filter for December only (fiscal_month = 12)
            december_df = rf_monthly_df[rf_monthly_df["fiscal_month"] == 12].copy()
            
            if december_df.empty:
                self.logger.warning("No December data found in monthly Rf data")
                return pd.DataFrame()
            
            # Keep only fiscal_year and calc_rf columns
            result_df = december_df[["fiscal_year", "calc_rf"]].copy()
            result_df = result_df.sort_values("fiscal_year").reset_index(drop=True)
            
            self.logger.info(f"Extracted {len(result_df)} December Calc Rf values (fiscal years {result_df['fiscal_year'].min()}-{result_df['fiscal_year'].max()})")
            
            return result_df
            
        except Exception as e:
            self.logger.error(f"Failed to extract December values: {e}")
            raise

    async def _fetch_fy_end_dates_for_tickers(self, tickers: list) -> dict:
        """
        Fetch fiscal year end dates for all company tickers.
        
        Returns:
            dict: {ticker: {fiscal_year: fy_period_date (date object)}}
            Example: {'BHP AU Equity': {2002: date(2002, 6, 30), 2003: date(2003, 6, 30), ...}, ...}
        """
        try:
            if not tickers:
                return {}
            
            # Create placeholders for SQL IN clause
            placeholders = ', '.join([f"'{ticker}'" for ticker in tickers])
            
            query = text(f"""
                SELECT ticker, fiscal_year, fy_period_date
                FROM cissa.fiscal_year_mapping
                WHERE ticker IN ({placeholders})
                ORDER BY ticker, fiscal_year
            """)
            
            result = await self.session.execute(query)
            rows = result.fetchall()
            
            # Build dictionary structure
            fy_dates_dict = {}
            for row in rows:
                ticker, fiscal_year, fy_period_date = row
                if ticker not in fy_dates_dict:
                    fy_dates_dict[ticker] = {}
                fy_dates_dict[ticker][int(fiscal_year)] = fy_period_date
            
            self.logger.info(f"Fetched FY end dates for {len(fy_dates_dict)} tickers with {sum(len(v) for v in fy_dates_dict.values())} total entries")
            return fy_dates_dict
            
        except Exception as e:
            self.logger.error(f"Failed to fetch FY end dates for tickers: {e}")
            raise

    def _extract_rf_by_fy_end_date(self, rf_monthly_calc_df: pd.DataFrame, fy_dates_dict: dict) -> pd.DataFrame:
        """
        Extract Calc Rf values using each ticker's specific FY end date.
        
        For each ticker and fiscal_year, extracts the Calc Rf value for the month matching the FY end date.
        
        Args:
            rf_monthly_calc_df: DataFrame with columns [fiscal_year, fiscal_month, calc_rf]
            fy_dates_dict: dict structure {ticker: {fiscal_year: fy_period_date}}
        
        Returns:
            DataFrame with columns [ticker, fiscal_year, calc_rf]
            Returns NULL for calc_rf if the required month has no data
        """
        try:
            extracted_records = []
            
            for ticker, fy_years_dict in fy_dates_dict.items():
                for fiscal_year, fy_period_date in fy_years_dict.items():
                    # Extract month from the FY period date
                    fy_month = fy_period_date.month
                    
                    # Find matching row in rf_monthly_calc_df
                    matching_rows = rf_monthly_calc_df[
                        (rf_monthly_calc_df['fiscal_year'] == fiscal_year) &
                        (rf_monthly_calc_df['fiscal_month'] == fy_month)
                    ]
                    
                    if not matching_rows.empty:
                        calc_rf = float(matching_rows.iloc[0]['calc_rf'])
                    else:
                        # No data for this month - set to NULL
                        calc_rf = None
                    
                    extracted_records.append({
                        "ticker": ticker,
                        "fiscal_year": int(fiscal_year),
                        "calc_rf": calc_rf
                    })
            
            result_df = pd.DataFrame(extracted_records)
            
            # Log statistics
            total_records = len(result_df)
            null_records = result_df['calc_rf'].isna().sum()
            valid_records = total_records - null_records
            
            self.logger.info(f"Extracted {total_records} Calc Rf records by FY end date:")
            self.logger.info(f"  - Valid records: {valid_records}")
            self.logger.info(f"  - NULL records: {null_records}")
            
            return result_df
            
        except Exception as e:
            self.logger.error(f"Failed to extract Calc Rf by FY end date: {e}")
            raise

    def _scaffold_and_replicate_calc_rf(self, rf_yearly_df: pd.DataFrame, all_tickers: list) -> pd.DataFrame:
        """
        Scaffold Calc Rf across all company tickers for all fiscal years.
        
        Creates a complete (ticker, fiscal_year) matrix by replicating the
        bond index Calc Rf value to all company tickers.
        
        Input: rf_yearly_df with columns [fiscal_year, calc_rf] (one row per year)
        Output: DataFrame with columns [fiscal_year, calc_rf, ticker] replicated to all tickers
        
        Example:
          Input:  fiscal_year=2023, calc_rf=0.0525
          Output: fiscal_year=2023, calc_rf=0.0525, ticker=BHP AU Equity
                  fiscal_year=2023, calc_rf=0.0525, ticker=CBA AU Equity
                  ... (500+ tickers)
        """
        try:
            if rf_yearly_df.empty or not all_tickers:
                self.logger.warning("No fiscal years or tickers to scaffold")
                return pd.DataFrame()
            
            # Create scaffold: replicate each (fiscal_year, calc_rf) pair for all tickers
            scaffolded_records = []
            
            for _, row in rf_yearly_df.iterrows():
                fiscal_year = int(row['fiscal_year'])
                calc_rf = float(row['calc_rf'])
                
                # Replicate this Calc Rf value to all company tickers
                for ticker in all_tickers:
                    scaffolded_records.append({
                        "fiscal_year": fiscal_year,
                        "calc_rf": calc_rf,
                        "ticker": ticker
                    })
            
            result_df = pd.DataFrame(scaffolded_records)
            self.logger.info(f"Scaffolded Calc Rf to {len(result_df)} (ticker, fiscal_year) combinations")
            self.logger.info(f"  - Fiscal years: {result_df['fiscal_year'].min()}-{result_df['fiscal_year'].max()}")
            self.logger.info(f"  - Company tickers: {len(all_tickers)}")
            
            return result_df
            
        except Exception as e:
            self.logger.error(f"Failed to scaffold and replicate Calc Rf: {e}")
            raise

    def _format_results_for_storage(
        self,
        rf_df: pd.DataFrame,
        dataset_id: UUID,
        param_set_id: UUID
    ) -> list[dict]:
        """
        Format results for storage in metrics_outputs table.
        
        Creates 1 row per (ticker, fiscal_year) containing only the final Calc Rf metric.
        rf_df should have columns: [fiscal_year, calc_rf, ticker]
        Simple metadata structure: {"metric_level": "L1"}
        """
        try:
            records = []
            
            for _, row in rf_df.iterrows():
                fiscal_year = int(row['fiscal_year'])
                calc_rf = float(row['calc_rf']) if pd.notna(row['calc_rf']) else None
                ticker = str(row['ticker'])
                
                records.append({
                    "dataset_id": dataset_id,
                    "param_set_id": param_set_id,
                    "ticker": ticker,
                    "fiscal_year": fiscal_year,
                    "output_metric_name": "Calc Rf",
                    "output_metric_value": calc_rf,
                    "metadata": {"metric_level": "L1"}
                })
            
            self.logger.info(f"Formatted {len(records)} records for storage ({len(rf_df)} ticker-year combinations)")
            
            return records
            
        except Exception as e:
            self.logger.error(f"Failed to format results: {e}")
            raise

    async def _store_results_raw_sql(self, results: list[dict]) -> int:
        """
        Store results using PostgreSQL multi-row INSERT with UPSERT logic.
        
        Uses DO UPDATE clause to handle conflicts on (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name).
        Multi-row INSERT replaces individual INSERTs for much better performance.
        """
        try:
            if not results:
                self.logger.warning("No results to store")
                return 0
            
            # Insert records in batches using multi-row INSERT
            batch_size = 1000
            for i in range(0, len(results), batch_size):
                batch = results[i:i+batch_size]
                
                # Build multi-row VALUES clause for all records in batch
                rows_sql = ", ".join([
                    f"('{record['dataset_id']}', '{record['param_set_id']}', '{record['ticker']}', {record['fiscal_year']}, '{record['output_metric_name']}', {record['output_metric_value']}, '{json.dumps(record['metadata'])}')"
                    for record in batch
                ])
                
                # Execute multi-row INSERT with ON CONFLICT UPSERT (single statement for entire batch)
                multi_row_insert = text(f"""
                    INSERT INTO cissa.metrics_outputs 
                    (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata)
                    VALUES {rows_sql}
                    ON CONFLICT (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
                    DO UPDATE SET
                        output_metric_value = EXCLUDED.output_metric_value,
                        metadata = EXCLUDED.metadata
                """)
                
                await self.session.execute(multi_row_insert)
            
            self.logger.info(f"Stored {len(results)} records (multi-row INSERT)")
            return len(results)
             
        except Exception as e:
            self.logger.error(f"Failed to store results: {e}")
            raise

    async def calculate_risk_free_rate_runtime_batch(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
        parameter_id: UUID,
        country_code: str = 'AU',
    ) -> dict:
        """
        Batch runtime version: Calculate Rf and batch insert results (~11k records).
        
        Extracts parameters from parameter_overrides (JSONB) using parameter_id.
        Batch inserts results (1000-2000 records per insert).
        
        Args:
            dataset_id: Dataset ID
            param_set_id: Parameter set ID (for storage)
            parameter_id: Parameter ID (used to fetch parameters from parameter_sets)
            country_code: Country code for fiscal year definitions (default: 'AU')
        
        Returns:
            {
                "status": "success|error",
                "results_count": N,
                "message": "...",
            }
        """
        try:
            import time
            start_time = time.time()
            
            self.logger.info(
                f"[RF-BATCH] Starting batch risk-free rate calculation: dataset={dataset_id}, param_set={param_set_id}, parameter={parameter_id}"
            )
            
            # Step 1: Determine currency from country code
            currency_map = {'AU': 'AUD', 'US': 'USD', 'UK': 'GBP'}
            currency = currency_map.get(country_code, 'AUD')
            self.logger.info(f"[RF-BATCH] Using currency: {currency}")
            
            # Step 2: Load parameters from parameter_sets
            params = await self._load_parameters_from_parameter_set(parameter_id)
            self.logger.info(
                f"[RF-BATCH] Parameters loaded: approach={params.get('cost_of_equity_approach', 'Floating')}, "
                f"rounding={params.get('beta_rounding', 0.005)}"
            )
            
            # Step 3: Fetch bond ticker for currency
            bond_ticker = await self._fetch_bond_ticker_by_currency(currency)
            if not bond_ticker:
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": f"No bond ticker found for currency {currency}",
                }
            self.logger.info(f"[RF-BATCH] Using bond ticker: {bond_ticker}")
            
            # Step 4: Fetch all company tickers for currency
            all_tickers = await self._fetch_all_company_tickers_by_currency(currency)
            if not all_tickers:
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": f"No company tickers found for currency {currency}",
                }
            self.logger.info(f"[RF-BATCH] Found {len(all_tickers)} company tickers")
            
            # Step 5: Fetch monthly bond yields
            monthly_rf_df = await self._fetch_monthly_bond_yields(bond_ticker)
            if monthly_rf_df.empty:
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": f"No monthly bond yield data found for {bond_ticker}",
                }
            self.logger.info(f"[RF-BATCH] Fetched {len(monthly_rf_df)} monthly bond yield records")
            
            # Step 6: Calculate rolling 12-month geometric mean
            rf_monthly_df = self._calculate_rolling_geometric_mean(monthly_rf_df)
            
            # Step 7: Calculate Calc Rf with approach logic
            rf_monthly_calc_df = self._calculate_calc_rf_batch(rf_monthly_df, params)
            
            # Step 8: Fetch FY end dates for all company tickers
            fy_dates_dict = await self._fetch_fy_end_dates_for_tickers(all_tickers)
            self.logger.info(f"[RF-BATCH] Fetched FY end dates for {len(fy_dates_dict)} tickers")
            
            # Step 9: Extract Calc Rf by ticker-specific FY end date
            rf_expanded_df = self._extract_rf_by_fy_end_date(rf_monthly_calc_df, fy_dates_dict)
            if rf_expanded_df.empty:
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": "Failed to extract Calc Rf by FY end dates",
                }
            self.logger.info(f"[RF-BATCH] Extracted {len(rf_expanded_df)} Calc Rf values")
            
            # Step 10: Format and batch insert results
            results_to_store = self._format_results_for_storage(
                rf_expanded_df, dataset_id, param_set_id
            )
            
            stored_count = await self._store_results_batch(results_to_store, batch_size=1000)
            
            elapsed_time = time.time() - start_time
            self.logger.info(
                f"[RF-BATCH] ✓ Batch risk-free rate calculation complete: {stored_count} records stored in {elapsed_time:.2f}s"
            )
            
            return {
                "status": "success",
                "results_count": stored_count,
                "message": f"Calculated Calc Rf for {len(all_tickers)} tickers: {stored_count} total records",
            }
        
        except Exception as e:
            self.logger.error(f"[RF-BATCH] Batch risk-free rate calculation failed: {e}", exc_info=True)
            return {
                "status": "error",
                "results_count": 0,
                "message": f"Batch calculation failed: {str(e)}",
            }

    async def _load_parameters_from_parameter_set(self, parameter_id: UUID) -> dict:
        """
        Load parameters from parameter_sets table (JSONB param_overrides).
        
        Args:
            parameter_id: parameter_id (which is param_set_id in parameter_sets table)
        
        Returns:
            {
                "cost_of_equity_approach": "Floating",
                "beta_rounding": 0.005,
                "benchmark": 0.0,
                "risk_premium": 0.0,
                ...
            }
        """
        try:
            query = text(
                """
                SELECT param_overrides
                FROM cissa.parameter_sets
                WHERE param_set_id = :parameter_id
                LIMIT 1
            """
            )
            result = await self.session.execute(query, {"parameter_id": str(parameter_id)})
            row = result.fetchone()
            
            # Default parameters
            defaults = {
                "cost_of_equity_approach": "Floating",
                "beta_rounding": 0.005,
                "benchmark": 0.0,
                "risk_premium": 0.0,
            }
            
            if not row:
                self.logger.warning(f"[RF-BATCH] Parameter set not found: {parameter_id}")
                return defaults
            
            param_overrides = row[0]
            if isinstance(param_overrides, str):
                param_overrides = json.loads(param_overrides)
            elif param_overrides is None:
                param_overrides = {}
            
            # Merge with defaults
            result = {**defaults}
            result.update(param_overrides)
            
            return result
        
        except Exception as e:
            self.logger.error(f"[RF-BATCH] Failed to load parameters: {e}")
            raise

    def _calculate_calc_rf_batch(self, rf_monthly_df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """
        Calculate Calc Rf based on approach (Fixed or Floating).
        
        Same as _calculate_calc_rf but accepts params dict instead of individual args.
        """
        try:
            approach = params.get('cost_of_equity_approach', 'Floating').upper()
            rounding = params.get('beta_rounding', 0.005)
            benchmark = params.get('benchmark', 0.0)
            risk_premium = params.get('risk_premium', 0.0)
            
            return self._calculate_calc_rf(
                rf_monthly_df,
                approach,
                benchmark,
                risk_premium,
                rounding
            )
        
        except Exception as e:
            self.logger.error(f"[RF-BATCH] Failed to calculate Calc Rf: {e}")
            raise

    async def _store_results_batch(self, results: list[dict], batch_size: int = 1000) -> int:
        """
        Batch insert results in groups (batch_size per insert).
        
        Args:
            results: List of result dicts
            batch_size: Number of records per batch insert (default 1000)
        
        Returns:
            Total number of records inserted
        """
        try:
            if not results:
                return 0
            
            total_inserted = 0
            
            # Process results in batches
            for i in range(0, len(results), batch_size):
                batch = results[i : i + batch_size]
                
                # Build multi-row VALUES clause
                rows_sql = ", ".join([
                    f"('{record['dataset_id']}', '{record['param_set_id']}', '{record['ticker']}', {record['fiscal_year']}, '{record['output_metric_name']}', {record['output_metric_value']}, '{json.dumps(record['metadata'])}')"
                    for record in batch
                ])
                
                # Execute multi-row INSERT with ON CONFLICT UPSERT
                multi_row_insert = text(f"""
                    INSERT INTO cissa.metrics_outputs 
                    (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata)
                    VALUES {rows_sql}
                    ON CONFLICT (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name)
                    DO UPDATE SET
                        output_metric_value = EXCLUDED.output_metric_value,
                        metadata = EXCLUDED.metadata
                """)
                
                await self.session.execute(multi_row_insert)
                await self.session.commit()
                total_inserted += len(batch)
                self.logger.info(f"[RF-BATCH] Inserted batch of {len(batch)} records ({total_inserted}/{len(results)} total)")
            
            self.logger.info(f"[RF-BATCH] Batch insert complete: {total_inserted} records")
            return total_inserted
        
        except Exception as e:
            self.logger.error(f"[RF-BATCH] Failed to batch insert results: {e}", exc_info=True)
            await self.session.rollback()
            raise
