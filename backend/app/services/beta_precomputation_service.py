# ============================================================================
# Beta Pre-Computation Service
# ============================================================================
# Pre-computes Beta using rolling OLS regression on monthly returns.
# Stores BOTH unrounded approaches (FIXED + Floating) with param_set_id=NULL
# for later runtime rounding and approach selection.
# ============================================================================

import pandas as pd
import numpy as np
import time
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..core.config import get_logger
from ..repositories.metrics_repository import MetricsRepository
from .beta_calculation_service import (
    _calculate_single_ticker_ols,
    BetaCalculationService,
)

logger = get_logger(__name__)


class PreComputedBetaService(BetaCalculationService):
    """
    Service for pre-computing Beta values at data ingestion time.
    
    Extends BetaCalculationService to:
    - Skip rounding (store raw unrounded values)
    - Store BOTH approaches (FIXED and Floating)
    - Use param_set_id = NULL to indicate pre-computed metrics
    - Include comprehensive metadata for runtime rounding
    
    Algorithm:
    1. Fetch monthly COMPANY_TSR and INDEX_TSR from fundamentals
    2. Calculate 60-month rolling OLS slopes
    3. Transform slopes: adjusted = (slope * 2/3) + 1/3
    4. Filter by relative error tolerance (from parameters table)
    5. DON'T ROUND - store transformed value as-is
    6. Annualize: group by fiscal_year
    7. Calculate sector averages (raw, unrounded)
    8. Apply 4-tier fallback logic
    9. Calculate BOTH approaches (FIXED and Floating) without rounding
    10. Store with param_set_id=NULL and comprehensive metadata
    """

    async def precompute_beta_async(
        self,
        dataset_id: UUID,
    ) -> dict:
        """
        Pre-compute Beta for entire dataset with both approaches.
        Called from ETL pipeline after data ingestion.

        Args:
            dataset_id: Dataset ID for the calculation

        Returns:
            {
                "status": "success|error",
                "records_created": N,
                "time_seconds": T,
                "message": "...",
                "alert": True/False (if computation > 120s)
            }
        """
        start_time = time.time()
        try:
            self.logger.info(
                f"[PRE-COMPUTATION] Starting beta pre-computation: dataset={dataset_id}"
            )

            # Load fixed parameters (not user-selectable)
            params = await self._load_precomputation_parameters()
            self.logger.info(
                f"[PRE-COMPUTATION] Parameters loaded: error_tolerance={params['beta_relative_error_tolerance']}"
            )

            # Fetch monthly returns
            self.logger.info(
                "[PRE-COMPUTATION] Fetching monthly returns (COMPANY_TSR + INDEX_TSR)..."
            )
            monthly_df = await self._fetch_monthly_returns(dataset_id)

            if monthly_df.empty:
                self.logger.warning(
                    "[PRE-COMPUTATION] No monthly returns data found"
                )
                return {
                    "status": "error",
                    "records_created": 0,
                    "time_seconds": time.time() - start_time,
                    "message": "No monthly returns data found in fundamentals",
                    "alert": False,
                }

            self.logger.info(
                f"[PRE-COMPUTATION] Fetched {len(monthly_df)} monthly return records for {monthly_df['ticker'].nunique()} tickers"
            )

            # Fetch sector and fiscal month data
            self.logger.info(
                "[PRE-COMPUTATION] Fetching sector and fiscal month information..."
            )
            sector_map, fy_month_map = await self._fetch_sector_and_fiscal_month_map()
            self.logger.info(
                f"[PRE-COMPUTATION] Loaded {len(sector_map)} ticker-sector mappings"
            )

            # Fetch begin_year mappings
            self.logger.info(
                "[PRE-COMPUTATION] Fetching begin_year for all tickers..."
            )
            begin_year_map = await self._fetch_begin_years()
            global_min_begin_year = await self._fetch_global_min_begin_year()
            all_tickers = await self._fetch_all_tickers()

            # Calculate rolling OLS slopes
            self.logger.info(
                "[PRE-COMPUTATION] Calculating rolling OLS slopes (60-month window)..."
            )
            ols_df = self._calculate_rolling_ols(monthly_df)
            self.logger.info(
                f"[PRE-COMPUTATION] Calculated OLS slopes for {len(ols_df)} records"
            )

            # Transform slopes WITHOUT rounding (store raw values)
            self.logger.info("[PRE-COMPUTATION] Transforming slopes...")
            transformed_df = self._transform_slopes_no_rounding(
                ols_df, params["beta_relative_error_tolerance"]
            )

            # Annualize slopes
            self.logger.info("[PRE-COMPUTATION] Annualizing slopes...")
            annual_df = self._annualize_slopes(transformed_df, sector_map, fy_month_map)
            self.logger.info(
                f"[PRE-COMPUTATION] Annualized to {len(annual_df)} records"
            )

            # Generate sector slopes (unrounded)
            self.logger.info("[PRE-COMPUTATION] Calculating sector average slopes...")
            sector_slopes = self._generate_sector_slopes_raw(annual_df)

            # Scaffold and backfill
            self.logger.info("[PRE-COMPUTATION] Scaffolding and backfilling...")
            scaffolded_df = self._scaffold_and_backfill_betas(
                annual_df, sector_slopes, begin_year_map, global_min_begin_year, all_tickers
            )

            # Apply 4-tier fallback
            self.logger.info("[PRE-COMPUTATION] Applying 4-tier fallback logic...")
            spot_betas = self._apply_4tier_fallback(scaffolded_df, sector_slopes)

            # Calculate BOTH approaches WITHOUT rounding
            self.logger.info(
                "[PRE-COMPUTATION] Calculating both approaches (FIXED and Floating)..."
            )
            final_betas = self._calculate_both_approaches(spot_betas)

            # Format for storage with param_set_id=NULL
            self.logger.info("[PRE-COMPUTATION] Formatting results for storage...")
            records = self._format_precomputed_results_for_storage(
                final_betas, dataset_id
            )

            # Store in metrics_outputs
            self.logger.info(
                f"[PRE-COMPUTATION] Storing {len(records)} pre-computed Beta records..."
            )
            stored_count = await self._store_results_raw_sql(records)

            elapsed_time = time.time() - start_time
            alert = elapsed_time > 120  # Alert if > 2 minutes

            if alert:
                self.logger.warning(
                    f"[PRE-COMPUTATION] ⚠️  ALERT: Beta pre-computation took {elapsed_time:.1f}s (threshold: 120s)"
                )

            self.logger.info(
                f"[PRE-COMPUTATION] ✓ Completed: {stored_count} records in {elapsed_time:.1f}s"
            )

            return {
                "status": "success",
                "records_created": stored_count,
                "time_seconds": elapsed_time,
                "message": f"Pre-computed Beta: {stored_count} records in {elapsed_time:.1f}s",
                "alert": alert,
            }

        except Exception as e:
            elapsed_time = time.time() - start_time
            self.logger.error(
                f"[PRE-COMPUTATION] Failed to pre-compute beta: {e}", exc_info=True
            )
            return {
                "status": "error",
                "records_created": 0,
                "time_seconds": elapsed_time,
                "message": f"Beta pre-computation failed: {str(e)}",
                "alert": False,
            }

    async def _load_precomputation_parameters(self) -> dict:
        """Load parameters for pre-computation (uses fixed defaults, not user-selected)."""
        try:
            query = text(
                """
                SELECT parameter_name, parameter_value
                FROM cissa.parameters
                WHERE parameter_name IN (
                    'beta_relative_error_tolerance',
                    'cost_of_equity_approach'
                )
            """
            )
            result = await self.session.execute(query)
            rows = result.fetchall()

            params = {
                "beta_relative_error_tolerance": 40.0,  # default
                "cost_of_equity_approach": "Floating",  # default
            }

            for row in rows:
                if row[0] == "beta_relative_error_tolerance":
                    params["beta_relative_error_tolerance"] = float(row[1])
                elif row[0] == "cost_of_equity_approach":
                    params["cost_of_equity_approach"] = row[1]

            return params

        except Exception as e:
            self.logger.error(f"Failed to load pre-computation parameters: {e}")
            raise

    def _transform_slopes_no_rounding(
        self, df: pd.DataFrame, error_tolerance: float
    ) -> pd.DataFrame:
        """Transform slopes WITHOUT rounding - store raw transformed values."""
        try:
            df = df.copy()

            df["slope_transformed"] = (df["slope"] * 2 / 3) + 1 / 3
            df["rel_std_err"] = np.abs(df["std_err"]) / (
                np.abs(df["slope_transformed"]) + 1e-10
            )

            # Store raw transformed value if passes error check
            df["adjusted_slope"] = df.apply(
                lambda x: x["slope_transformed"] if error_tolerance >= x["rel_std_err"] else np.nan,
                axis=1,
            )

            return df[
                [
                    "ticker",
                    "fiscal_year",
                    "fiscal_month",
                    "slope",
                    "std_err",
                    "rel_std_err",
                    "adjusted_slope",
                ]
            ]

        except Exception as e:
            self.logger.error(f"Failed to transform slopes (no rounding): {e}")
            raise

    def _generate_sector_slopes_raw(self, annual_df: pd.DataFrame) -> pd.DataFrame:
        """Generate sector slopes WITHOUT rounding."""
        try:
            annual_df = annual_df.copy()

            sector_slopes = (
                annual_df.groupby(["sector", "fiscal_year"])
                .agg({"adjusted_slope": ["mean", "count"]})
                .reset_index()
            )
            sector_slopes.columns = ["sector", "fiscal_year", "slope_value", "count"]

            # Store raw unrounded sector slopes
            sector_slopes.rename(columns={"slope_value": "sector_slope"}, inplace=True)

            return sector_slopes[["sector", "fiscal_year", "sector_slope"]]

        except Exception as e:
            self.logger.error(f"Failed to generate sector slopes (raw): {e}")
            raise

    def _calculate_both_approaches(self, spot_betas: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate BOTH approaches (FIXED and Floating) WITHOUT rounding.
        Returns df with fixed_beta_raw and floating_beta_raw columns.
        """
        try:
            spot_betas = spot_betas.copy()

            # FIXED approach: Average across ALL years
            spot_betas["fixed_beta_raw"] = spot_betas.apply(
                lambda x: x["ticker_avg"] if pd.notna(x["ticker_avg"]) else np.nan,
                axis=1,
            )

            # Floating approach: Cumulative average
            spot_betas = spot_betas.sort_values(["ticker", "fiscal_year"]).reset_index(
                drop=True
            )

            cumulative_betas = []

            for ticker in spot_betas["ticker"].unique():
                ticker_data = spot_betas[spot_betas["ticker"] == ticker].copy()
                ticker_data = ticker_data.sort_values("fiscal_year").reset_index(
                    drop=True
                )

                cumulative_means = []
                for i in range(len(ticker_data)):
                    values_to_avg = ticker_data["spot_slope"].iloc[: i + 1]
                    if values_to_avg.notna().any():
                        cum_avg = values_to_avg.mean()
                    else:
                        cum_avg = np.nan
                    cumulative_means.append(cum_avg)

                ticker_data["floating_beta_raw"] = cumulative_means
                cumulative_betas.append(ticker_data)

            spot_betas = pd.concat(cumulative_betas, ignore_index=True)

            # Preserve monthly_raw_slopes if exists
            if "monthly_raw_slopes" not in spot_betas.columns:
                spot_betas["monthly_raw_slopes"] = None

            return spot_betas[
                [
                    "ticker",
                    "fiscal_year",
                    "fixed_beta_raw",
                    "floating_beta_raw",
                    "spot_slope",
                    "monthly_raw_slopes",
                    "fallback_tier_used",
                ]
            ]

        except Exception as e:
            self.logger.error(f"Failed to calculate both approaches: {e}")
            raise

    def _format_precomputed_results_for_storage(
        self, final_betas: pd.DataFrame, dataset_id: UUID
    ) -> list[dict]:
        """Format pre-computed results for storage with param_set_id=NULL."""
        try:
            records = []

            for _, row in final_betas.iterrows():
                metadata = {
                    "metric_level": "L1",
                    "fixed_beta_raw": float(row["fixed_beta_raw"])
                    if pd.notna(row["fixed_beta_raw"])
                    else None,
                    "floating_beta_raw": float(row["floating_beta_raw"])
                    if pd.notna(row["floating_beta_raw"])
                    else None,
                    "spot_slope_raw": float(row["spot_slope"])
                    if pd.notna(row["spot_slope"])
                    else None,
                    "fallback_tier_used": int(row["fallback_tier_used"])
                    if pd.notna(row["fallback_tier_used"])
                    else None,
                }

                # Add monthly raw slopes if available
                if "monthly_raw_slopes" in row and row["monthly_raw_slopes"] is not None:
                    monthly_slopes = row["monthly_raw_slopes"]
                    if isinstance(monthly_slopes, list):
                        monthly_slopes = [
                            float(s) if pd.notna(s) else None for s in monthly_slopes
                        ]
                        metadata["monthly_raw_slopes"] = monthly_slopes

                # Use fixed_beta_raw as the output_metric_value for storage
                output_value = (
                    float(row["fixed_beta_raw"])
                    if pd.notna(row["fixed_beta_raw"])
                    else None
                )

                record = {
                    "dataset_id": dataset_id,
                    "param_set_id": None,  # NULL for pre-computed
                    "ticker": row["ticker"],
                    "fiscal_year": int(row["fiscal_year"]),
                    "output_metric_name": "Calc Beta",
                    "output_metric_value": output_value,
                    "metadata": metadata,
                }
                records.append(record)

            return records

        except Exception as e:
            self.logger.error(f"Failed to format pre-computed results: {e}")
            raise

    async def _store_results_raw_sql(self, records: list[dict]) -> int:
        """Store results using raw SQL INSERT with param_set_id=NULL handling."""
        try:
            if not records:
                return 0

            # Filter out records with NULL output_metric_value
            valid_records = [r for r in records if r["output_metric_value"] is not None]

            if not valid_records:
                self.logger.warning(
                    "[PRE-COMPUTATION] No valid results to store (all values are NULL)"
                )
                return 0

            import json

            values = []
            for record in valid_records:
                values.append(
                    (
                        str(record["dataset_id"]),
                        (
                            str(record["param_set_id"])
                            if record["param_set_id"] is not None
                            else None
                        ),
                        record["ticker"],
                        record["fiscal_year"],
                        record["output_metric_name"],
                        record["output_metric_value"],
                        json.dumps(record["metadata"]),
                    )
                )

            # Bulk insert with ON CONFLICT handling
            query = text(
                """
                INSERT INTO cissa.metrics_outputs 
                (dataset_id, param_set_id, ticker, fiscal_year, output_metric_name, output_metric_value, metadata)
                VALUES (:dataset_id, :param_set_id, :ticker, :fiscal_year, :output_metric_name, :output_metric_value, :metadata)
                ON CONFLICT DO NOTHING
            """
            )

            for value_tuple in values:
                await self.session.execute(
                    query,
                    {
                        "dataset_id": value_tuple[0],
                        "param_set_id": value_tuple[1],
                        "ticker": value_tuple[2],
                        "fiscal_year": value_tuple[3],
                        "output_metric_name": value_tuple[4],
                        "output_metric_value": float(value_tuple[5]),
                        "metadata": value_tuple[6],
                    },
                )

            await self.session.commit()
            return len(valid_records)

        except Exception as e:
            self.logger.error(f"[PRE-COMPUTATION] Failed to store results: {e}", exc_info=True)
            await self.session.rollback()
            raise
