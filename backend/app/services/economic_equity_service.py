# ============================================================================
# Economic Equity (Calc EE) Calculation Service
# ============================================================================
"""
Service for calculating Economic Equity with recursive logic:

Formula:
- Year = begin_year: EE = TOTAL_EQUITY - MINORITY_INTEREST
- Year > begin_year: EE = PROFIT_AFTER_TAX - CALC_ECF + EE(previous_year)

This represents the cumulative economic equity where:
- First year uses actual balance sheet equity
- Subsequent years track equity changes through retained earnings (PAT - ECF)
"""

import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class EconomicEquityService:
    """Service for calculating Economic Equity (Calc EE) with recursive/cumulative logic"""

    @staticmethod
    async def calculate_economic_equity(
        session: AsyncSession,
        dataset_id: UUID,
        param_set_id: UUID,
        tickers: Optional[List[str]] = None,
    ) -> Dict[str, any]:
        """
        Calculate Calc EE for all tickers in dataset using recursive formula.

        Formula:
        - Year = begin_year: EE = TOTAL_EQUITY - MINORITY_INTEREST
        - Year > begin_year: EE = PROFIT_AFTER_TAX - CALC_ECF + EE(previous_year)

        Args:
            session: Async database session
            dataset_id: Dataset UUID
            param_set_id: Parameter set UUID for ECF lookup
            tickers: Optional list of tickers to process; if None, processes all

        Returns:
            Dict with:
            - calculated_records: List of (ticker, fiscal_year, calc_ee) tuples
            - summary: Processing summary
        """
        logger.info(
            f"Starting Economic Equity calculation for dataset {dataset_id}, param_set {param_set_id}"
        )

        # Fetch raw data
        raw_data = await EconomicEquityService._fetch_raw_data(
            session, dataset_id, param_set_id, tickers
        )
        logger.info(f"Fetched {len(raw_data)} raw data records")

        # Group by ticker and calculate
        calculated_records = []
        ticker_groups = raw_data.groupby("ticker")

        for ticker, ticker_data in ticker_groups:
            logger.debug(f"Processing ticker: {ticker}")

            # Sort by fiscal year
            ticker_data = ticker_data.sort_values("fiscal_year").reset_index(drop=True)

            # Get begin_year from first record
            begin_year = ticker_data.iloc[0]["begin_year"]
            logger.debug(f"  Begin year: {begin_year}")

            # Calculate EE recursively
            ee_values = []
            prior_ee = None

            for idx, row in ticker_data.iterrows():
                fiscal_year = row["fiscal_year"]

                # Skip years before begin_year
                if fiscal_year < begin_year:
                    logger.debug(f"  Year {fiscal_year}: Skipped (before begin_year)")
                    continue

                if fiscal_year == begin_year:
                    # Year 1: Use balance sheet equity
                    total_equity = row["total_equity"]
                    minority_interest = row["minority_interest"]

                    if pd.isna(total_equity) or pd.isna(minority_interest):
                        logger.debug(
                            f"  Year {fiscal_year}: Skipped (missing source data)"
                        )
                        ee = None
                    else:
                        ee = float(float(total_equity) - float(minority_interest))
                        logger.debug(
                            f"  Year {fiscal_year}: EE = TE({total_equity}) - MI({minority_interest}) = {ee}"
                        )

                else:
                    # Year > begin_year: Cumulative formula
                    if prior_ee is None:
                        logger.debug(
                            f"  Year {fiscal_year}: Skipped (prior_ee is None)"
                        )
                        ee = None
                    else:
                        profit_after_tax = row["profit_after_tax"]
                        calc_ecf = row["calc_ecf"]

                        if pd.isna(profit_after_tax) or pd.isna(calc_ecf):
                            logger.debug(
                                f"  Year {fiscal_year}: Skipped (missing PAT or ECF)"
                            )
                            ee = None
                        else:
                            ee = float(prior_ee + float(profit_after_tax) - float(calc_ecf))
                            logger.debug(
                                f"  Year {fiscal_year}: EE = {prior_ee} + PAT({profit_after_tax}) - ECF({calc_ecf}) = {ee}"
                            )

                if ee is not None:
                    ee_values.append((ticker, fiscal_year, ee))
                    prior_ee = ee
                else:
                    prior_ee = None

            logger.info(f"  Calculated {len(ee_values)} EE values for {ticker}")
            calculated_records.extend(ee_values)

        logger.info(f"Total calculated EE records: {len(calculated_records)}")

        return {
            "calculated_records": calculated_records,
            "summary": {
                "total_records": len(calculated_records),
                "unique_tickers": len(ticker_groups),
            },
        }

    @staticmethod
    async def insert_economic_equity(
        session: AsyncSession,
        dataset_id: UUID,
        param_set_id: UUID,
        calculated_records: List[Tuple[str, int, float]],
    ) -> Dict[str, any]:
        """
        Insert calculated Calc EE values into metrics_outputs table.

        Args:
            session: Async database session
            dataset_id: Dataset UUID
            param_set_id: Parameter set UUID
            calculated_records: List of (ticker, fiscal_year, calc_ee) tuples

        Returns:
            Dict with insertion summary
        """
        logger.info(f"Inserting {len(calculated_records)} Calc EE records")

        # Clear existing Calc EE records for this dataset/param_set
        delete_query = text("""
            DELETE FROM cissa.metrics_outputs
            WHERE dataset_id = :dataset_id
                AND param_set_id = :param_set_id
                AND output_metric_name = 'Calc EE'
        """)

        result = await session.execute(
            delete_query,
            {
                "dataset_id": str(dataset_id),
                "param_set_id": str(param_set_id),
            },
        )
        deleted_count = result.rowcount
        logger.info(f"Deleted {deleted_count} existing Calc EE records")

        # Prepare insertion data
        insert_data = [
            {
                "ticker": ticker,
                "fiscal_year": fiscal_year,
                "output_metric_name": "Calc EE",
                "output_metric_value": calc_ee,
                "dataset_id": str(dataset_id),
                "param_set_id": str(param_set_id),
            }
            for ticker, fiscal_year, calc_ee in calculated_records
        ]

        # Batch insert
        batch_size = 500
        for i in range(0, len(insert_data), batch_size):
            batch = insert_data[i : i + batch_size]

            insert_query = text("""
                INSERT INTO cissa.metrics_outputs
                (ticker, fiscal_year, output_metric_name, output_metric_value, 
                 dataset_id, param_set_id)
                VALUES (:ticker, :fiscal_year, :output_metric_name, :output_metric_value,
                        :dataset_id, :param_set_id)
            """)

            for record in batch:
                await session.execute(insert_query, record)

        await session.commit()
        logger.info(f"Inserted {len(insert_data)} Calc EE records successfully")

        return {
            "inserted": len(insert_data),
            "deleted": deleted_count,
        }

    @staticmethod
    async def _fetch_raw_data(
        session: AsyncSession,
        dataset_id: UUID,
        param_set_id: UUID,
        tickers: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Fetch raw data needed for Calc EE calculation.

        Returns DataFrame with columns:
        - ticker, fiscal_year, begin_year, total_equity, minority_interest,
          profit_after_tax, calc_ecf
        """
        query = text("""
            SELECT
                c.ticker,
                c.begin_year,
                f_te.fiscal_year,
                f_te.numeric_value as total_equity,
                f_mi.numeric_value as minority_interest,
                f_pat.numeric_value as profit_after_tax,
                mo_ecf.output_metric_value as calc_ecf
            FROM cissa.companies c
            LEFT JOIN cissa.fundamentals f_te
                ON c.ticker = f_te.ticker
                AND f_te.dataset_id = :dataset_id
                AND f_te.metric_name = 'TOTAL_EQUITY'
            LEFT JOIN cissa.fundamentals f_mi
                ON c.ticker = f_mi.ticker
                AND f_mi.fiscal_year = f_te.fiscal_year
                AND f_mi.dataset_id = f_te.dataset_id
                AND f_mi.metric_name = 'MINORITY_INTEREST'
            LEFT JOIN cissa.fundamentals f_pat
                ON c.ticker = f_pat.ticker
                AND f_pat.fiscal_year = f_te.fiscal_year
                AND f_pat.dataset_id = f_te.dataset_id
                AND f_pat.metric_name = 'PROFIT_AFTER_TAX'
            LEFT JOIN cissa.metrics_outputs mo_ecf
                ON c.ticker = mo_ecf.ticker
                AND mo_ecf.fiscal_year = f_te.fiscal_year
                AND mo_ecf.dataset_id = f_te.dataset_id
                AND mo_ecf.param_set_id = :param_set_id
                AND mo_ecf.output_metric_name = 'Calc ECF'
            WHERE f_te.dataset_id = :dataset_id
                AND f_te.metric_name = 'TOTAL_EQUITY'
        """)

        params = {
            "dataset_id": str(dataset_id),
            "param_set_id": str(param_set_id),
        }

        if tickers:
            query = text(str(query) + " AND c.ticker = ANY(:tickers)")
            params["tickers"] = tickers

        result = await session.execute(query, params)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())

        return df
