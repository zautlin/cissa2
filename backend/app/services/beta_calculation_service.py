# ============================================================================
# Beta Calculation Service (Phase 07)
# ============================================================================
# Calculates: Beta using rolling OLS regression on monthly returns
# Stores results in cissa.metrics_outputs table
# Replicates legacy beta.py algorithm with async/await patterns
# ============================================================================

import pandas as pd
import numpy as np
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..core.config import get_logger
from ..repositories.metrics_repository import MetricsRepository

logger = get_logger(__name__)


class BetaCalculationService:
    """
    Service for Phase 07 beta calculation.
    
    Calculates beta using rolling OLS regression on monthly returns data.
    Replicates legacy beta.py algorithm exactly.
    
    Algorithm:
    1. Fetch monthly COMPANY_TSR and INDEX_TSR from fundamentals
    2. Calculate 60-month rolling OLS slopes
    3. Transform slopes: adjusted = (slope * 2/3) + 1/3
    4. Filter by relative error tolerance
    5. Round by beta_rounding
    6. Annualize: group by fiscal_year
    7. Calculate sector averages
    8. Apply 4-tier fallback logic
    9. Apply approach_to_ke logic (FIXED vs Floating)
    10. Store in metrics_outputs
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MetricsRepository(session)
        self.logger = get_logger(__name__)
    
    async def calculate_beta_async(
        self,
        dataset_id: UUID,
        param_set_id: UUID,
    ) -> dict:
        """
        Main orchestration method for beta calculation.
        
        Args:
            dataset_id: Dataset ID for the calculation
            param_set_id: Parameter set ID (defines beta parameters)
        
        Returns:
            {
                "status": "success|error|cached",
                "results_count": N,
                "message": "..."
            }
        """
        try:
            self.logger.info(f"Starting beta calculation: dataset={dataset_id}, param_set={param_set_id}")
            
            # 1. Load parameters
            self.logger.info("Loading parameters...")
            params = await self._load_parameters_from_db(param_set_id)
            self.logger.info(f"Parameters loaded: error_tolerance={params['beta_relative_error_tolerance']}, "
                           f"rounding={params['beta_rounding']}, approach={params['cost_of_equity_approach']}")
            
            # 2. Check if results already exist (upsert logic)
            existing_count = await self._count_existing_beta_results(dataset_id, param_set_id)
            if existing_count > 0:
                self.logger.info(f"Beta results already exist ({existing_count} records) - returning cached")
                return {
                    "status": "cached",
                    "results_count": existing_count,
                    "message": f"Using cached results for dataset={dataset_id}, param_set={param_set_id}"
                }
            
            # 3. Fetch monthly returns
            self.logger.info("Fetching monthly returns (COMPANY_TSR + INDEX_TSR)...")
            monthly_df = await self._fetch_monthly_returns(dataset_id)
            
            if monthly_df.empty:
                self.logger.warning("No monthly returns data found")
                return {
                    "status": "error",
                    "results_count": 0,
                    "message": "No monthly returns data found in fundamentals"
                }
            
            self.logger.info(f"Fetched {len(monthly_df)} monthly return records for {monthly_df['ticker'].nunique()} tickers")
            
            # 4. Fetch sector and fiscal month data
            self.logger.info("Fetching sector and fiscal month information...")
            sector_map, fy_month_map = await self._fetch_sector_and_fiscal_month_map()
            self.logger.info(f"Loaded {len(sector_map)} ticker-sector mappings with fiscal months")
            
            # 4b. Fetch begin_year mappings and global minimum
            self.logger.info("Fetching begin_year for all tickers and global minimum...")
            begin_year_map = await self._fetch_begin_years()
            global_min_begin_year = await self._fetch_global_min_begin_year()
            self.logger.info(f"Global minimum begin_year: {global_min_begin_year}")
            
            
            # 4c. Fetch ALL tickers from companies table for complete scaffold
            all_tickers = await self._fetch_all_tickers()
            self.logger.info(f"Loaded {len(all_tickers)} total tickers for scaffold")
            # 5. Calculate rolling OLS slopes
            self.logger.info("Calculating rolling OLS slopes (60-month window)...")
            ols_df = self._calculate_rolling_ols(monthly_df)
            self.logger.info(f"Calculated OLS slopes for {len(ols_df)} record(s)")
            
            # 6. Transform and filter slopes
            self.logger.info(f"Transforming slopes (error_tolerance={params['beta_relative_error_tolerance']})...")
            transformed_df = self._transform_slopes(
                ols_df,
                params['beta_relative_error_tolerance'],
                params['beta_rounding']
            )
            
            # 7. Annualize slopes (using ticker-specific fiscal months)
            self.logger.info("Annualizing slopes by ticker-specific fiscal month...")
            annual_df = self._annualize_slopes(transformed_df, sector_map, fy_month_map)
            self.logger.info(f"Annualized to {annual_df['fiscal_year'].nunique()} fiscal years with {len(annual_df)} records")
            
            # 8. Generate sector slopes
            self.logger.info("Calculating sector average slopes...")
            sector_slopes = self._generate_sector_slopes(annual_df)
            self.logger.info(f"Calculated sector slopes for {sector_slopes['sector'].nunique()} sectors")
            
            # 9. Scaffold and backfill: create complete (ticker, fiscal_year) coverage with fallback values
            self.logger.info(f"Creating complete (ticker, fiscal_year) scaffold ({global_min_begin_year}-2023) and backfilling missing years with fallback...")
            scaffolded_df = self._scaffold_and_backfill_betas(annual_df, sector_slopes, begin_year_map, global_min_begin_year, all_tickers)
            self.logger.info(f"Scaffolded to {len(scaffolded_df)} complete records ({len(annual_df)} calculated, {len(scaffolded_df) - len(annual_df)} backfilled)")
            
            # 10. Apply 4-tier fallback logic (now on complete scaffold)
            self.logger.info("Applying 4-tier fallback logic...")
            spot_betas = self._apply_4tier_fallback(scaffolded_df, sector_slopes)
            
            # 11. Apply approach_to_ke
            self.logger.info(f"Applying approach_to_ke: {params['cost_of_equity_approach']}...")
            final_betas = self._apply_approach_to_ke(
                spot_betas,
                params['cost_of_equity_approach'],
                params['beta_rounding']
            )
            
            self.logger.info(f"Final beta calculation complete: {len(final_betas)} records")
            
            # 11. Format and store results
            self.logger.info("Storing results in metrics_outputs...")
            results_to_store = self._format_results_for_storage(
                final_betas,
                dataset_id,
                param_set_id
            )
            
            # Store results using raw SQL to avoid ORM foreign key validation issues
            stored_count = await self._store_results_raw_sql(results_to_store)
            await self.session.commit()
            
            self.logger.info(f"Beta calculation complete: {stored_count} results stored out of {len(final_betas)} calculated")
            
            return {
                "status": "success",
                "results_count": stored_count,
                "message": f"Calculated beta for {len(final_betas)} records ({stored_count} with non-null values)"
            }
            
        except Exception as e:
            self.logger.error(f"Beta calculation failed: {type(e).__name__}: {e}")
            await self.session.rollback()
            return {
                "status": "error",
                "results_count": 0,
                "message": f"Beta calculation failed: {str(e)}"
            }
    
    async def _load_parameters_from_db(self, param_set_id: UUID) -> dict:
        """Load beta-related parameters from database with overrides."""
        try:
            # Load defaults from parameters table
            query = text("""
                SELECT parameter_name, default_value
                FROM cissa.parameters
                WHERE parameter_name IN ('beta_rounding', 'beta_relative_error_tolerance', 'cost_of_equity_approach')
            """)
            
            result = await self.session.execute(query)
            rows = result.fetchall()
            
            params = {}
            for row in rows:
                param_name = row[0]
                value = row[1]
                
                if param_name in ["beta_rounding", "beta_relative_error_tolerance"]:
                    params[param_name] = float(value)
                    if param_name == "beta_relative_error_tolerance":
                        params[param_name] = params[param_name] / 100.0
                else:
                    params[param_name] = value
            
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
                        if key in ["beta_rounding", "beta_relative_error_tolerance"]:
                            params[key] = float(value)
                            if key == "beta_relative_error_tolerance":
                                params[key] = params[key] / 100.0
                        else:
                            params[key] = value
            
            return params
            
        except Exception as e:
            self.logger.error(f"Failed to load parameters: {e}")
            raise
    
    async def _count_existing_beta_results(self, dataset_id: UUID, param_set_id: UUID) -> int:
        """Count existing beta results for upsert logic."""
        try:
            query = text("""
                SELECT COUNT(*)
                FROM cissa.metrics_outputs
                WHERE dataset_id = :dataset_id
                AND param_set_id = :param_set_id
                AND output_metric_name = 'Calc Beta'
            """)
            
            result = await self.session.execute(query, {
                "dataset_id": str(dataset_id),
                "param_set_id": str(param_set_id)
            })
            
            return result.scalar() or 0
            
        except Exception as e:
            self.logger.error(f"Failed to count existing results: {e}")
            return 0
    
    async def _fetch_monthly_returns(self, dataset_id: UUID) -> pd.DataFrame:
        """Fetch COMPANY_TSR and INDEX_TSR from fundamentals table.
        
        Excludes index tickers (e.g., 'AEX Index', 'DAX Index') which don't have
        meaningful fiscal year ends and are not actual companies.
        """
        try:
            query = text("""
                SELECT
                    c.ticker,
                    c.fiscal_year,
                    c.fiscal_month,
                    c.numeric_value as company_tsr,
                    i.numeric_value as index_tsr
                FROM cissa.fundamentals c
                INNER JOIN cissa.fundamentals i
                    ON c.fiscal_year = i.fiscal_year
                    AND c.fiscal_month = i.fiscal_month
                WHERE c.dataset_id = :dataset_id
                AND c.metric_name = 'COMPANY_TSR'
                AND c.period_type = 'MONTHLY'
                AND c.ticker NOT LIKE '%Index%'
                AND i.dataset_id = :dataset_id
                AND i.ticker = 'AS30 Index'
                AND i.metric_name = 'INDEX_TSR'
                AND i.period_type = 'MONTHLY'
                ORDER BY c.ticker, c.fiscal_year, c.fiscal_month
            """)
            
            result = await self.session.execute(query, {"dataset_id": str(dataset_id)})
            rows = result.fetchall()
            
            df = pd.DataFrame(
                rows,
                columns=["ticker", "fiscal_year", "fiscal_month", "company_tsr", "index_tsr"]
            )
            
            # Convert to numeric
            df["company_tsr"] = pd.to_numeric(df["company_tsr"], errors="coerce")
            df["index_tsr"] = pd.to_numeric(df["index_tsr"], errors="coerce")
            df["fiscal_year"] = pd.to_numeric(df["fiscal_year"], errors="coerce").astype(int)
            df["fiscal_month"] = pd.to_numeric(df["fiscal_month"], errors="coerce").astype(int)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to fetch monthly returns: {e}")
            raise
    
    async def _fetch_sector_and_fiscal_month_map(self) -> tuple[dict, dict]:
        """Fetch ticker to sector and fiscal month mapping from companies table.
        
        Returns:
            (sector_map, fy_month_map) where:
            - sector_map: {ticker: sector}
            - fy_month_map: {ticker: fy_report_month}
        """
        try:
            query = text("""
                SELECT ticker, sector, 
                       EXTRACT(MONTH FROM fy_report_month)::INTEGER as fy_month
                FROM cissa.companies
            """)
            result = await self.session.execute(query)
            rows = result.fetchall()
            
            sector_map = {}
            fy_month_map = {}
            
            for ticker, sector, fy_month in rows:
                sector_map[ticker] = sector
                if fy_month is None:
                    self.logger.error(f"Missing fy_report_month for ticker {ticker}")
                    raise ValueError(f"Ticker {ticker} has missing fy_report_month in companies table")
                fy_month_map[ticker] = fy_month
            
            self.logger.info(f"Loaded sector and fiscal month mappings for {len(sector_map)} tickers")
            return sector_map, fy_month_map
            
        except Exception as e:
            self.logger.error(f"Failed to fetch sector and fiscal month map: {e}")
            raise
    
    async def _fetch_inception_years(self, dataset_id: UUID) -> dict:
        """Fetch inception year (first available data year) for each ticker.
        
        Matches legacy behavior: inception = MIN(fiscal_year) where data is not null.
        """
        try:
            query = text("""
                SELECT 
                    ticker,
                    MIN(CAST(fiscal_year AS INTEGER)) as inception_year
                FROM cissa.fundamentals
                WHERE dataset_id = :dataset_id
                AND metric_name = 'COMPANY_TSR'
                AND period_type = 'MONTHLY'
                GROUP BY ticker
            """)
            
            result = await self.session.execute(query, {"dataset_id": str(dataset_id)})
            rows = result.fetchall()
            
            inception_map = {row[0]: row[1] for row in rows}
            self.logger.info(f"Loaded inception years for {len(inception_map)} tickers")
            return inception_map
            
        except Exception as e:
            self.logger.error(f"Failed to fetch inception years: {e}")
            return {}
    
    async def _fetch_begin_years(self) -> dict:
        """Fetch begin_year from companies table for all tickers.
        
        Returns:
            {ticker: begin_year} mapping
        """
        try:
            query = text("""
                SELECT ticker, begin_year
                FROM cissa.companies
                WHERE begin_year IS NOT NULL
            """)
            
            result = await self.session.execute(query)
            rows = result.fetchall()
            
            begin_year_map = {row[0]: row[1] for row in rows}
            self.logger.info(f"Loaded begin_year for {len(begin_year_map)} tickers")
            return begin_year_map
            
        except Exception as e:
            self.logger.error(f"Failed to fetch begin years: {e}")
            return {}
    
    async def _fetch_global_min_begin_year(self) -> int:
        """Fetch minimum begin_year across all companies in the dataset.
        
        Returns:
            The earliest begin_year value, or 1981 as fallback
        """
        try:
            query = text("""
                SELECT MIN(begin_year) as min_begin_year
                FROM cissa.companies
                WHERE begin_year IS NOT NULL
            """)
            
            result = await self.session.execute(query)
            row = result.fetchone()
            
            if row and row[0] is not None:
                min_year = int(row[0])
                self.logger.info(f"Global minimum begin_year: {min_year}")
                return min_year
            else:
                self.logger.warning("No valid begin_year found in companies table, using 1981 as fallback")
                return 1981
            
        except Exception as e:
            self.logger.error(f"Failed to fetch global min begin_year: {e}")
            return 1981    
    async def _fetch_all_tickers(self) -> list:
        """Fetch all tickers from companies table.
        
        Returns:
            List of all ticker symbols
        """
        try:
            query = text("""
                SELECT DISTINCT ticker
                FROM cissa.companies
                ORDER BY ticker
            """)
            
            result = await self.session.execute(query)
            rows = result.fetchall()
            
            tickers = [row[0] for row in rows]
            self.logger.info(f"Loaded {len(tickers)} total tickers from companies table")
            return tickers
            
        except Exception as e:
            self.logger.error(f"Failed to fetch all tickers: {e}")
            return []
     
    def _scaffold_and_backfill_betas(self, annual_df: pd.DataFrame, sector_slopes: pd.DataFrame, begin_year_map: dict, global_min_begin_year: int, all_tickers: list) -> pd.DataFrame:
        """Generate complete (ticker, fiscal_year) scaffold and fill missing years with fallback values.
        
        Algorithm:
        1. Create scaffold: all (ticker, fiscal_year) from global_min_begin_year to max(annual_df.fiscal_year)
           for ALL tickers, not just each ticker's individual begin_year
        2. Left-join calculated annual_df onto scaffold
        3. For rows with NaN adjusted_slope:
           - Try Tier 2: Use sector_slope if available
           - Try Tier 3: Use global average from all non-NaN adjusted_slopes
        4. Fill remaining NaN with 1.0 as ultimate fallback
        
        Args:
            annual_df: DataFrame with calculated annual slopes (only years with source data)
            sector_slopes: DataFrame with sector average slopes
            begin_year_map: Dict mapping ticker -> begin_year from companies table (not used for scaffolding)
            global_min_begin_year: Global minimum begin_year across all companies - used as universal start year
        
        Returns:
            Complete DataFrame with all (ticker, fiscal_year) combinations filled with calculated or fallback values
        """
        try:
            # Determine year range
            max_year = int(annual_df['fiscal_year'].max()) if len(annual_df) > 0 else 2023
            
            # Create complete scaffold: all (ticker, fiscal_year) from GLOBAL MIN begin_year to max_year
            # This ensures EVERY ticker has full coverage from the earliest begin_year in the dataset
            scaffold_rows = []
            for ticker in all_tickers:
                for year in range(global_min_begin_year, max_year + 1):
                    scaffold_rows.append({'ticker': ticker, 'fiscal_year': year})
            
            scaffold_df = pd.DataFrame(scaffold_rows)
            self.logger.info(f"Created scaffold with {len(scaffold_df)} (ticker, fiscal_year) combinations from {global_min_begin_year} to {max_year}")
            
            # Left-join calculated slopes onto scaffold
            # Keep all columns from annual_df
            merged_df = scaffold_df.merge(
                annual_df,
                on=['ticker', 'fiscal_year'],
                how='left'
            )
            
            # For rows without calculated adjusted_slope, apply fallback logic
            # First, merge with sector slopes to have sector_slope available
            merged_df = merged_df.merge(
                sector_slopes,
                on=['sector', 'fiscal_year'],
                how='left'
            )
            
            # Tier 2: Use sector_slope if adjusted_slope is NaN
            merged_df['adjusted_slope_with_fallback'] = merged_df['adjusted_slope'].fillna(merged_df['sector_slope'])
            
            # Calculate Tier 3 (global average) for remaining NaNs
            global_avg = annual_df['adjusted_slope'].dropna().mean()
            if pd.isna(global_avg):
                global_avg = 1.0
                self.logger.warning("No valid adjusted slopes found for Tier 3 fallback - using 1.0")
            
            # Tier 3: Use global average if both adjusted_slope and sector_slope are NaN
            merged_df['adjusted_slope_with_fallback'] = merged_df['adjusted_slope_with_fallback'].fillna(global_avg)
            
            # Track which tier was used
            merged_df['fallback_tier_used'] = merged_df.apply(
                lambda x: 1 if pd.notna(x['adjusted_slope'])
                          else (2 if pd.notna(x['sector_slope']) else 3),
                axis=1
            )
            
            # Update adjusted_slope to use fallback values
            merged_df['adjusted_slope'] = merged_df['adjusted_slope_with_fallback']
            
            # Keep original columns from annual_df plus fallback_tier_used
            result_columns = ['ticker', 'fiscal_year', 'sector', 'adjusted_slope', 'slope', 'std_err', 'rel_std_err', 'monthly_raw_slopes', 'fallback_tier_used']
            result_df = merged_df[[col for col in result_columns if col in merged_df.columns]]
            
            self.logger.info(f"Backfilled {(result_df['fallback_tier_used'] > 1).sum()} records with Tier 2/3 fallback values")
            
            return result_df
            
        except Exception as e:
            self.logger.error(f"Failed to scaffold and backfill betas: {e}")
            raise
     
    def _calculate_rolling_ols(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate rolling OLS slopes for each ticker using scipy.stats.linregress.
        
        Uses 60-month rolling window for each month to match Excel SLOPE() function.
        Stores all 12 monthly slopes per fiscal year for annualization step.
        """
        try:
            from scipy import stats
            
            results = []
            
            for ticker, ticker_group in df.groupby('ticker'):
                ticker_group = ticker_group.sort_values(['fiscal_year', 'fiscal_month']).reset_index(drop=True)
                
                # Convert TSR % to growth factors (PREL format)
                x = ticker_group['index_tsr'] / 100.0 + 1.0
                y = ticker_group['company_tsr'] / 100.0 + 1.0
                
                if len(x) < 2:
                    self.logger.warning(f"Ticker {ticker} has <2 months of data, skipping")
                    continue
                
                slopes = []
                stderrs = []
                fiscal_years = []
                fiscal_months = []
                
                # Calculate slope for each month using 60-month rolling window
                for i in range(len(x)):
                    # Get up to 60-month window ending at month i
                    window_size = min(60, i + 1)
                    start_idx = i - window_size + 1
                    
                    window_x = x.iloc[start_idx:i+1].values
                    window_y = y.iloc[start_idx:i+1].values
                    
                    if len(window_x) < 2:
                        slopes.append(np.nan)
                        stderrs.append(np.nan)
                    else:
                        try:
                            # Use scipy.stats.linregress to match Excel SLOPE() function
                            result = stats.linregress(window_x, window_y)
                            slopes.append(result.slope)
                            stderrs.append(result.stderr)
                        except Exception as e:
                            self.logger.debug(f"linregress failed for {ticker} at index {i}: {e}")
                            slopes.append(np.nan)
                            stderrs.append(np.nan)
                    
                    fiscal_years.append(ticker_group['fiscal_year'].iloc[i])
                    fiscal_months.append(ticker_group['fiscal_month'].iloc[i])
                
                rolling_result = pd.DataFrame({
                    'ticker': ticker,
                    'fiscal_year': fiscal_years,
                    'fiscal_month': fiscal_months,
                    'slope': slopes,
                    'std_err': stderrs
                })
                
                results.append(rolling_result)
            
            if results:
                return pd.concat(results, ignore_index=True)
            else:
                return pd.DataFrame()
            
        except Exception as e:
            self.logger.error(f"Failed to calculate rolling OLS: {e}")
            raise
    
    def _transform_slopes(self, df: pd.DataFrame, error_tolerance: float, beta_rounding: float) -> pd.DataFrame:
        """Transform slopes: apply formula, error filtering, rounding."""
        try:
            df = df.copy()
            
            df['slope_transformed'] = (df['slope'] * 2 / 3) + 1 / 3
            df['rel_std_err'] = np.abs(df['std_err']) / (np.abs(df['slope_transformed']) + 1e-10)
            
            df['adjusted_slope'] = df.apply(
                lambda x: np.round((x['slope_transformed'] / beta_rounding), 0) * beta_rounding
                if error_tolerance >= x['rel_std_err']
                else np.nan,
                axis=1
            )
            
            return df[['ticker', 'fiscal_year', 'fiscal_month', 'slope', 'std_err', 'rel_std_err', 'adjusted_slope']]
            
        except Exception as e:
            self.logger.error(f"Failed to transform slopes: {e}")
            raise
    
    def _annualize_slopes(self, beta_df: pd.DataFrame, sector_map: dict, fy_month_map: dict) -> pd.DataFrame:
        """Annualize slopes by taking ticker-specific fiscal month of each fiscal year.
        
        CRITICAL FIX: This method now uses ticker-specific fiscal year end months instead of
        assuming all tickers follow June fiscal year. This is essential because ASX companies
        have different fiscal year ends:
        - S32 AU Equity: fy_report_month = June (6)
        - RIO AU Equity: fy_report_month = December (12)
        - BHP AU Equity: fy_report_month = December (12)
        - etc.
        
        For each ticker, we filter monthly slopes to only include the month matching that
        ticker's fiscal year end. This ensures the annualized slope is always taken from
        the last month of that ticker's fiscal year, matching the logic in the Excel reference
        implementation.
        
        Also collects all 12 monthly raw slopes for metadata storage.
        
        Args:
            beta_df: DataFrame with columns [ticker, fiscal_year, fiscal_month, slope, ...]
            sector_map: Dict mapping ticker → sector (from companies table)
            fy_month_map: Dict mapping ticker → fy_report_month (from companies table)
        
        Returns:
            DataFrame with annualized data, one row per (ticker, fiscal_year)
        
        Raises:
            ValueError: If any ticker in fy_month_map is missing or has no data
        """
        try:
            # Collect all 12 monthly raw slopes per fiscal year before annualization
            monthly_slopes_by_fy = (
                beta_df
                .groupby(['ticker', 'fiscal_year'])
                .apply(lambda group: group['slope'].tolist(), include_groups=False)
                .reset_index()
                .rename(columns={0: 'monthly_raw_slopes'})
            )
            
            # For each ticker, filter to its specific fiscal month
            annual_betas = []
            
            for ticker in beta_df['ticker'].unique():
                if ticker not in fy_month_map:
                    self.logger.error(f"Ticker {ticker} not found in fy_month_map")
                    raise ValueError(f"Ticker {ticker} has no fiscal month information")
                
                fy_month = fy_month_map[ticker]
                self.logger.debug(f"Annualizing {ticker} using fiscal month {fy_month}")
                
                ticker_data = beta_df[beta_df['ticker'] == ticker]
                ticker_annual = ticker_data[ticker_data['fiscal_month'] == fy_month].copy()
                
                if ticker_annual.empty:
                    self.logger.warning(f"No data found for {ticker} in fiscal month {fy_month}")
                    continue
                
                ticker_annual = ticker_annual.drop_duplicates(['ticker', 'fiscal_year'], keep='first')
                annual_betas.append(ticker_annual)
            
            if not annual_betas:
                self.logger.warning("No annualized data available after fiscal month filtering")
                return pd.DataFrame()
            
            annual_beta = pd.concat(annual_betas, ignore_index=True)
            
            # Add sector information
            annual_beta['sector'] = annual_beta['ticker'].map(sector_map)
            
            # Merge in monthly slopes for metadata storage
            annual_beta = annual_beta.merge(
                monthly_slopes_by_fy,
                on=['ticker', 'fiscal_year'],
                how='left'
            )
            
            return annual_beta[['ticker', 'fiscal_year', 'sector', 'adjusted_slope', 'slope', 'std_err', 'rel_std_err', 'monthly_raw_slopes']]
            
        except Exception as e:
            self.logger.error(f"Failed to annualize slopes: {e}")
            raise
    
    def _generate_sector_slopes(self, annual_beta: pd.DataFrame) -> pd.DataFrame:
        """Calculate sector average adjusted_slope by fiscal_year."""
        try:
            sector_slopes = (
                annual_beta
                .groupby(['sector', 'fiscal_year'])
                .agg({'adjusted_slope': lambda x: x.mean(skipna=True)})
                .rename(columns={'adjusted_slope': 'sector_slope'})
                .reset_index()
            )
            
            return sector_slopes
            
        except Exception as e:
            self.logger.error(f"Failed to generate sector slopes: {e}")
            raise
    
    def _apply_4tier_fallback(self, annual_beta: pd.DataFrame, sector_slopes: pd.DataFrame) -> pd.DataFrame:
        """Apply 4-tier fallback logic to determine spot_slope for each record.
        
        Fallback order:
        1. Use individual Calc Adj Beta (adjusted_slope if available)
        2. Use sector average (sector_slope if adjusted_slope is NaN)
        3. Use global market average (if both adjusted_slope and sector_slope are NaN)
        4. Use 1.0 as ultimate fallback
        """
        try:
            spot_betas = annual_beta.merge(
                sector_slopes,
                on=['sector', 'fiscal_year'],
                how='left'
            )
            
            # Tier 1 & 2: Individual → Sector
            spot_betas['spot_slope'] = spot_betas['adjusted_slope'].fillna(spot_betas['sector_slope'])
            
            # Tier 3: Calculate global market average (average of all non-NaN adjusted slopes)
            global_avg = annual_beta['adjusted_slope'].dropna().mean()
            
            if pd.isna(global_avg):
                self.logger.warning("No valid adjusted slopes found to create global fallback - using 1.0 as ultimate fallback")
                global_avg = 1.0
            else:
                self.logger.info(f"Tier 3 global fallback calculated: {global_avg:.4f}")
            
            # Apply Tier 3 fallback for any remaining NaN values
            spot_betas['spot_slope'] = spot_betas['spot_slope'].fillna(global_avg)
            
            # Tier 4: Apply ultimate 1.0 fallback for any still-NaN values (safety net)
            spot_betas['spot_slope'] = spot_betas['spot_slope'].fillna(1.0)
            
            # Track which tier was used for audit trail (optional)
            spot_betas['fallback_tier_used'] = spot_betas.apply(
                lambda x: 1 if pd.notna(x['adjusted_slope'])
                          else (2 if pd.notna(x['sector_slope']) else (3 if x['spot_slope'] == global_avg else 4)),
                axis=1
            )
            
            # Calculate ticker average for FIXED approach
            ticker_avg = spot_betas.groupby('ticker')['spot_slope'].mean(skipna=False)
            
            spot_betas = spot_betas.merge(
                ticker_avg.rename('ticker_avg'),
                left_on='ticker',
                right_index=True
            )
            
            return spot_betas
            
        except Exception as e:
            self.logger.error(f"Failed to apply 4-tier fallback: {e}")
            raise
    
    def _apply_approach_to_ke(self, spot_betas: pd.DataFrame, approach_to_ke: str, beta_rounding: float) -> pd.DataFrame:
        """Apply approach_to_ke logic to calculate final beta.
        
        Args:
            spot_betas: DataFrame with spot_slope and ticker_avg columns
            approach_to_ke: 'FIXED' or 'Floating' (or any other)
            beta_rounding: Rounding factor (e.g., 0.1)
        
        Returns:
            DataFrame with ticker, fiscal_year, beta, monthly_raw_slopes columns
        
        Logic:
            - FIXED: Average across ALL years (same value for all years) = ticker_avg
            - Floating (DEFAULT): Cumulative average from inception year to each year
        """
        try:
            spot_betas = spot_betas.copy()
            
            # DEBUG: Log the exact approach value
            self.logger.info(f"DEBUG: approach_to_ke = '{approach_to_ke}' (type: {type(approach_to_ke).__name__}, len: {len(approach_to_ke) if isinstance(approach_to_ke, str) else 'N/A'})")
            self.logger.info(f"DEBUG: comparison result: approach_to_ke == 'FIXED' -> {approach_to_ke == 'FIXED'}")
            self.logger.info(f"DEBUG: spot_betas.shape = {spot_betas.shape}")
            self.logger.info(f"DEBUG: spot_betas columns = {list(spot_betas.columns)}")
            self.logger.info(f"DEBUG: spot_betas sample BHP (first 5): {spot_betas[spot_betas['ticker']=='BHP AU Equity'].head().to_dict()}")
            
            if approach_to_ke == 'FIXED':
                # FIXED: Use average across ALL years (same for all years)
                spot_betas['beta'] = spot_betas.apply(
                    lambda x: np.round(x['ticker_avg'] / beta_rounding, 0) * beta_rounding
                    if pd.notna(x['ticker_avg'])
                    else np.nan,
                    axis=1
                )
            else:
                # Floating (DEFAULT): Cumulative average from inception year to each year
                # Group by ticker and calculate cumulative mean within each ticker
                spot_betas = spot_betas.sort_values(['ticker', 'fiscal_year']).reset_index(drop=True)
                
                cumulative_betas = []
                
                for ticker in spot_betas['ticker'].unique():
                    ticker_data = spot_betas[spot_betas['ticker'] == ticker].copy()
                    
                    # Sort by fiscal_year to ensure cumulative calculation is chronological
                    ticker_data = ticker_data.sort_values('fiscal_year').reset_index(drop=True)
                    
                    # Calculate cumulative average of spot_slope from inception to each year
                    # Note: We use forward-filling cumulative mean (expanding window)
                    cumulative_means = []
                    for i in range(len(ticker_data)):
                        # Get all spot_slope values from inception (index 0) to current year (index i)
                        values_to_avg = ticker_data['spot_slope'].iloc[:i+1]
                        
                        # Calculate cumulative average (only non-NaN values)
                        if values_to_avg.notna().any():
                            cum_avg = values_to_avg.mean()  # pandas mean() skips NaN by default
                        else:
                            cum_avg = np.nan
                        
                        cumulative_means.append(cum_avg)
                    
                    ticker_data['floating_beta'] = cumulative_means
                    cumulative_betas.append(ticker_data)
                
                # Combine all tickers back
                spot_betas = pd.concat(cumulative_betas, ignore_index=True)
                
                # Apply floating beta with rounding
                spot_betas['beta'] = spot_betas.apply(
                    lambda x: np.round(x['floating_beta'] / beta_rounding, 0) * beta_rounding
                    if pd.notna(x['floating_beta'])
                    else np.nan,
                    axis=1
                )
            
            # Preserve monthly_raw_slopes if it exists, otherwise create empty list
            if 'monthly_raw_slopes' not in spot_betas.columns:
                spot_betas['monthly_raw_slopes'] = None
            
            return spot_betas[['ticker', 'fiscal_year', 'beta', 'monthly_raw_slopes']]
            
        except Exception as e:
            self.logger.error(f"Failed to apply approach_to_ke: {e}")
            raise
    
    def _format_results_for_storage(self, final_betas: pd.DataFrame, dataset_id: UUID, param_set_id: UUID) -> list[dict]:
        """Format results for storage in metrics_outputs table."""
        try:
            records = []
            
            for _, row in final_betas.iterrows():
                metadata = {"metric_level": "L1"}
                
                # Add monthly raw slopes if available
                if 'monthly_raw_slopes' in row and row['monthly_raw_slopes'] is not None:
                    monthly_slopes = row['monthly_raw_slopes']
                    # Handle both list and non-list cases
                    if isinstance(monthly_slopes, list):
                        # Convert NaN values to None for JSON serialization
                        monthly_slopes = [float(s) if pd.notna(s) else None for s in monthly_slopes]
                        metadata['monthly_raw_slopes'] = monthly_slopes
                
                record = {
                    "dataset_id": dataset_id,
                    "param_set_id": param_set_id,
                    "ticker": row['ticker'],
                    "fiscal_year": int(row['fiscal_year']),
                    "output_metric_name": "Calc Beta",
                    "output_metric_value": float(row['beta']) if pd.notna(row['beta']) else None,
                    "metadata": metadata
                }
                records.append(record)
            
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
            import json
            
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
