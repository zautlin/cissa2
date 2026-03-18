#!/usr/bin/env python3
"""
Script to recalculate Economic Profitability (Calc EP) after Calc EE is corrected.

Usage:
  python recalculate_economic_profitability.py --dataset-id <uuid> --param-set-id <uuid>
"""

import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

import click
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.economic_profitability_service import EconomicProfitabilityService
from app.core.config import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main(dataset_id: UUID, param_set_id: UUID):
    """Recalculate Calc EP for specified dataset and parameter set"""
    settings = Settings()

    # Create async engine and session
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with async_session() as session:
            logger.info(f"Starting Economic Profitability recalculation")
            logger.info(f"  Dataset ID: {dataset_id}")
            logger.info(f"  Param Set ID: {param_set_id}")

            service = EconomicProfitabilityService(session)

            # Calculate Calc EP
            logger.info("Calculating Economic Profitability...")
            result = await service.calculate_economic_profitability(
                dataset_id, param_set_id
            )

            logger.info(f"Result status: {result['status']}")
            logger.info(f"Records calculated: {result['records_calculated']}")
            logger.info(f"Records inserted: {result['records_inserted']}")
            logger.info(f"Message: {result['message']}")
            logger.info(f"Calculation time: {result['calculation_time_ms']:.2f} ms")

            if result['status'] == 'success':
                logger.info("Economic Profitability recalculation completed successfully!")
            else:
                logger.error(f"Economic Profitability recalculation failed: {result['message']}")
                sys.exit(1)

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
def cli(dataset_id: str, param_set_id: str):
    """Recalculate Economic Profitability with corrected Calc EE values"""
    try:
        dataset_uuid = UUID(dataset_id)
        param_set_uuid = UUID(param_set_id)

        asyncio.run(main(dataset_uuid, param_set_uuid))

    except ValueError as e:
        logger.error(f"Invalid UUID: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
