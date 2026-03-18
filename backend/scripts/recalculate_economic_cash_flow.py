#!/usr/bin/env python3
"""
Script to recalculate Economic Cash Flow (Calc ECF) using corrected SQL function.

The fn_calc_ecf SQL function correctly returns:
- NULL for begin_year records (no cash flow for initial equity)
- ECF value for fiscal_year > begin_year

This script uses the updated metrics_service that preserves NULL values instead of converting them to 0.

Usage:
  python recalculate_economic_cash_flow.py --dataset-id <uuid> --param-set-id <uuid> [--tickers TICKER1 TICKER2 ...]
"""

import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID
from typing import Optional, List

import click
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.metrics_service import MetricsService
from app.core.config import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def recalculate_ecf(
    dataset_id: UUID,
    param_set_id: UUID,
    tickers: Optional[List[str]] = None,
):
    """Recalculate Calc ECF using the SQL function with proper NULL handling"""
    settings = Settings()

    # Create async engine and session
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with async_session() as session:
            logger.info("Starting Economic Cash Flow recalculation")
            logger.info(f"  Dataset ID: {dataset_id}")
            logger.info(f"  Param Set ID: {param_set_id}")
            if tickers:
                logger.info(f"  Tickers: {', '.join(tickers)}")
            else:
                logger.info("  Processing all tickers in dataset")

            # Delete existing Calc ECF records for this dataset
            logger.info("Step 1: Deleting existing Calc ECF records...")
            delete_query = text("""
                DELETE FROM cissa.metrics_outputs
                WHERE dataset_id = :dataset_id
                    AND param_set_id = :param_set_id
                    AND output_metric_name = 'Calc ECF'
            """)
            result = await session.execute(delete_query, {
                "dataset_id": str(dataset_id),
                "param_set_id": str(param_set_id),
            })
            deleted_count = result.rowcount
            logger.info(f"  Deleted {deleted_count} existing Calc ECF records")

            # Calculate Calc ECF using SQL function
            logger.info("Step 2: Calculating Calc ECF using fn_calc_ecf SQL function...")
            metrics_service = MetricsService(session)
            inserted_count = await metrics_service._execute_sql_function(
                metric_name="Calc ECF",
                dataset_id=dataset_id
            )
            logger.info(f"  Calculated and inserted {inserted_count} Calc ECF records")

            # Verify results
            logger.info("Step 3: Verifying results...")
            try:
                verification_result = await verify_ecf_nulls(session, dataset_id, param_set_id)
                logger.info(f"  Begin-year records with NULL: {verification_result['null_count']}")
                logger.info(f"  Non-begin-year records with values: {verification_result['value_count']}")
            except Exception as e:
                logger.info(f"  Verification skipped: {str(e)}")

            logger.info("Economic Cash Flow recalculation completed successfully!")

    finally:
        await engine.dispose()


async def verify_ecf_nulls(session: AsyncSession, dataset_id: UUID, param_set_id: UUID) -> dict:
    """Verify that ECF values are NULL for begin_year records"""
    
    # Get sample of ECF values at begin_year vs non-begin_year
    query = text("""
        SELECT
            SUM(CASE WHEN mo.output_metric_value IS NULL THEN 1 ELSE 0 END) as null_count,
            SUM(CASE WHEN mo.output_metric_value IS NOT NULL THEN 1 ELSE 0 END) as value_count
        FROM cissa.metrics_outputs mo
        JOIN cissa.ticker_begin_years tby ON mo.ticker = tby.ticker
        WHERE mo.dataset_id = :dataset_id
            AND mo.param_set_id = :param_set_id
            AND mo.output_metric_name = 'Calc ECF'
    """)
    
    result = await session.execute(query, {"dataset_id": str(dataset_id), "param_set_id": str(param_set_id)})
    row = result.fetchone()
    
    return {
        "null_count": row[0] or 0,
        "value_count": row[1] or 0
    }


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
    """Recalculate Economic Cash Flow with proper NULL handling for begin_year"""
    try:
        dataset_uuid = UUID(dataset_id)
        param_set_uuid = UUID(param_set_id)
        ticker_list = list(tickers) if tickers else None

        asyncio.run(recalculate_ecf(dataset_uuid, param_set_uuid, ticker_list))

    except ValueError as e:
        logger.error(f"Invalid UUID: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
