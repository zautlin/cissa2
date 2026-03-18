#!/usr/bin/env python3
"""
Script to recalculate Economic Equity (Calc EE) using corrected recursive formula.

Usage:
  python recalculate_economic_equity.py --dataset-id <uuid> --param-set-id <uuid> [--tickers TICKER1 TICKER2 ...]
"""

import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID
from typing import Optional, List

import click
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.economic_equity_service import EconomicEquityService
from app.core.config import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main(
    dataset_id: UUID,
    param_set_id: UUID,
    tickers: Optional[List[str]] = None,
):
    """Recalculate Calc EE for specified dataset and parameter set"""
    settings = Settings()

    # Create async engine and session
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with async_session() as session:
            logger.info(f"Starting Economic Equity recalculation")
            logger.info(f"  Dataset ID: {dataset_id}")
            logger.info(f"  Param Set ID: {param_set_id}")
            if tickers:
                logger.info(f"  Tickers: {', '.join(tickers)}")

            # Calculate Calc EE
            logger.info("Step 1: Calculating Economic Equity...")
            result = await EconomicEquityService.calculate_economic_equity(
                session, dataset_id, param_set_id, tickers
            )

            calc_records = result["calculated_records"]
            summary = result["summary"]

            logger.info(f"  Calculated {summary['total_records']} records across {summary['unique_tickers']} tickers")

            # Show sample results
            if calc_records:
                logger.info("  Sample results:")
                for ticker, fiscal_year, calc_ee in calc_records[:5]:
                    logger.info(f"    {ticker} {fiscal_year}: {calc_ee:.2f}")

            # Insert into database
            logger.info("Step 2: Inserting into database...")
            insert_result = await EconomicEquityService.insert_economic_equity(
                session, dataset_id, param_set_id, calc_records
            )

            logger.info(f"  Inserted: {insert_result['inserted']} records")
            logger.info(f"  Deleted: {insert_result['deleted']} records")

            logger.info("Economic Equity recalculation completed successfully!")

    finally:
        await engine.dispose()


@click.command()
@click.option(
    "--dataset-id",
    type=str,
    required=True,
    help="Dataset UUID",
)
@click.option(
    "--param-set-id",
    type=str,
    required=True,
    help="Parameter Set UUID",
)
@click.option(
    "--tickers",
    type=str,
    multiple=True,
    help="Specific tickers to process (optional)",
)
def cli(dataset_id: str, param_set_id: str, tickers: tuple):
    """Recalculate Economic Equity with correct recursive formula"""
    try:
        dataset_uuid = UUID(dataset_id)
        param_set_uuid = UUID(param_set_id)
        ticker_list = list(tickers) if tickers else None

        asyncio.run(main(dataset_uuid, param_set_uuid, ticker_list))

    except ValueError as e:
        logger.error(f"Invalid UUID: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
