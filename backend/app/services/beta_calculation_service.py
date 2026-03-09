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
            
            # 4. Fetch sector data
            self.logger.info("Fetching sector information...")
            sector_map = await self._fetch_sector_map()
            self.logger.info(f"Loaded {len(sector_map)} ticker-sector mappings")
            
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
            
            # 7. Annualize slopes
            self.logger.info("Annualizing slopes by fiscal_year...")
            annual_df = self._annualize_slopes(transformed_df, sector_map)
            self.logger.info(f"Annualized to {annual_df['fiscal_year'].nunique()} fiscal years")
            
            # 8. Generate sector slopes
            self.logger.info("Calculating sector average slopes...")
            sector_slopes = self._generate_sector_slopes(annual_df)
            self.logger.info(f"Calculated sector slopes for {sector_slopes['sector'].nunique()} sectors")
            
            # 9. Apply 4-tier fallback logic
            self.logger.info("Applying 4-tier fallback logic...")
            spot_betas = self._apply_4tier_fallback(annual_df, sector_slopes)
            
            # 10. Apply approach_to_ke
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
                AND output_metric_name = 'Beta'
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
        """Fetch COMPANY_TSR and INDEX_TSR from fundamentals table."""
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
    
    async def _fetch_sector_map(self) -> dict:
        """Fetch ticker to sector mapping from companies table."""
        try:
            query = text("SELECT ticker, sector FROM cissa.companies")
            result = await self.session.execute(query)
            rows = result.fetchall()
            
            return {row[0]: row[1] for row in rows}
            
        except Exception as e:
            self.logger.error(f"Failed to fetch sector map: {e}")
            return {}
    
    def _calculate_rolling_ols(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate rolling OLS slopes for each ticker."""
        try:
            from statsmodels.regression.rolling import RollingOLS
            
            results = []
            
            for ticker, ticker_group in df.groupby('ticker'):
                ticker_group = ticker_group.sort_values(['fiscal_year', 'fiscal_month']).reset_index(drop=True)
                
                # Convert TSR % to growth factors
                x = ticker_group['index_tsr'] / 100.0 + 1.0
                y = ticker_group['company_tsr'] / 100.0 + 1.0
                
                # Dynamic window
                window = min(60, len(x))
                
                if window < 2:
                    self.logger.warning(f"Ticker {ticker} has <2 months of data, skipping")
                    continue
                
                try:
                    model = RollingOLS(y, x, window=window)
                    result = model.fit()
                    
                    # Extract results
                    slopes = result.params.values
                    stderrs = result.bse.values
                    
                    # Handle dimension
                    if slopes.ndim > 1:
                        slopes = slopes[:, 0]
                    if stderrs.ndim > 1:
                        stderrs = stderrs[:, 0]
                    
                    rolling_result = pd.DataFrame({
                        'ticker': ticker,
                        'fiscal_year': ticker_group['fiscal_year'].values[-len(slopes):],
                        'fiscal_month': ticker_group['fiscal_month'].values[-len(slopes):],
                        'slope': slopes,
                        'std_err': stderrs
                    })
                    
                    results.append(rolling_result)
                    
                except Exception as e:
                    self.logger.warning(f"OLS regression failed for {ticker}: {e}")
                    continue
            
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
                lambda x: np.round((x['slope_transformed'] / beta_rounding), 4) * beta_rounding
                if error_tolerance >= x['rel_std_err']
                else np.nan,
                axis=1
            )
            
            return df[['ticker', 'fiscal_year', 'fiscal_month', 'slope', 'std_err', 'rel_std_err', 'adjusted_slope']]
            
        except Exception as e:
            self.logger.error(f"Failed to transform slopes: {e}")
            raise
    
    def _annualize_slopes(self, beta_df: pd.DataFrame, sector_map: dict) -> pd.DataFrame:
        """Annualize slopes by taking last month of each fiscal year."""
        try:
            annual_beta = (
                beta_df
                .sort_values(['ticker', 'fiscal_year', 'fiscal_month'])
                .drop_duplicates(['ticker', 'fiscal_year'], keep='last')
            )
            
            # Add sector information
            annual_beta['sector'] = annual_beta['ticker'].map(sector_map)
            
            return annual_beta[['ticker', 'fiscal_year', 'sector', 'adjusted_slope', 'slope', 'std_err', 'rel_std_err']]
            
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
        """Apply 4-tier fallback logic."""
        try:
            spot_betas = annual_beta.merge(
                sector_slopes,
                on=['sector', 'fiscal_year'],
                how='inner'
            )
            
            spot_betas['spot_slope'] = spot_betas['adjusted_slope'].fillna(spot_betas['sector_slope'])
            
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
        """Apply approach_to_ke logic to calculate final beta."""
        try:
            spot_betas = spot_betas.copy()
            
            if approach_to_ke == 'FIXED':
                spot_betas['beta'] = spot_betas.apply(
                    lambda x: np.round(x['ticker_avg'] / beta_rounding, 4) * beta_rounding
                    if pd.notna(x['ticker_avg'])
                    else np.nan,
                    axis=1
                )
            else:
                spot_betas['beta'] = spot_betas.apply(
                    lambda x: np.round(x['spot_slope'] / beta_rounding, 4) * beta_rounding
                    if pd.notna(x['spot_slope'])
                    else np.nan,
                    axis=1
                )
            
            return spot_betas[['ticker', 'fiscal_year', 'beta']]
            
        except Exception as e:
            self.logger.error(f"Failed to apply approach_to_ke: {e}")
            raise
    
    def _format_results_for_storage(self, final_betas: pd.DataFrame, dataset_id: UUID, param_set_id: UUID) -> list[dict]:
        """Format results for storage in metrics_outputs table."""
        try:
            records = []
            
            for _, row in final_betas.iterrows():
                record = {
                    "dataset_id": dataset_id,
                    "param_set_id": param_set_id,
                    "ticker": row['ticker'],
                    "fiscal_year": int(row['fiscal_year']),
                    "output_metric_name": "Beta",
                    "output_metric_value": float(row['beta']) if pd.notna(row['beta']) else None,
                    "metadata": {}
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
