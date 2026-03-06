#!/usr/bin/env python3
# ============================================================================
# CLI Script for L2 Metrics Calculation
# ============================================================================
"""
Run L2 metrics calculation for a dataset and parameter set.

This is the simplest test point for the L2 metrics system.

Usage:
    python -m backend.app.cli.run_l2_metrics --dataset-id <uuid> --param-set-id <uuid>

Example:
    python -m backend.app.cli.run_l2_metrics \
        --dataset-id 550e8400-e29b-41d4-a716-446655440000 \
        --param-set-id 660e8400-e29b-41d4-a716-446655440001
"""

import asyncio
import argparse
import sys
from uuid import UUID

# Add the backend app to the path
sys.path.insert(0, "/home/ubuntu/cissa")

from backend.app.core.database import async_session_factory
from backend.app.services.l2_metrics_service import L2MetricsService
from backend.app.core.config import get_logger

logger = get_logger(__name__)


async def run_l2_calculation(dataset_id: UUID, param_set_id: UUID) -> int:
    """
    Run L2 metrics calculation for a dataset.
    
    Returns:
        0 if successful, 1 if error
    """
    try:
        logger.info(f"Starting L2 metrics calculation")
        logger.info(f"  Dataset ID: {dataset_id}")
        logger.info(f"  Param Set ID: {param_set_id}")
        
        # Create a session
        async with async_session_factory() as session:
            async with session.begin():
                # Create service
                service = L2MetricsService(session)
                
                # Run calculation with default parameters
                # (In production, these would come from the parameter set)
                inputs = {
                    "country": "AU",
                    "risk_premium": 0.06,
                }
                
                logger.info(f"Calling L2 metrics calculation service...")
                result = await service.calculate_l2_metrics(
                    dataset_id=dataset_id,
                    param_set_id=param_set_id,
                    inputs=inputs
                )
        
        # Log results
        if result["status"] == "success":
            logger.info(f"✓ Calculation successful!")
            logger.info(f"  Records inserted: {result['results_count']}")
            logger.info(f"  Message: {result['message']}")
            return 0
        else:
            logger.error(f"✗ Calculation failed!")
            logger.error(f"  Error: {result['message']}")
            return 1
    
    except Exception as e:
        logger.error(f"✗ Unexpected error: {str(e)}", exc_info=True)
        return 1


def main():
    """Parse arguments and run calculation."""
    parser = argparse.ArgumentParser(
        description="Calculate L2 metrics for a dataset"
    )
    
    parser.add_argument(
        "--dataset-id",
        type=str,
        required=True,
        help="UUID of the dataset"
    )
    
    parser.add_argument(
        "--param-set-id",
        type=str,
        required=True,
        help="UUID of the parameter set"
    )
    
    args = parser.parse_args()
    
    # Validate UUIDs
    try:
        dataset_id = UUID(args.dataset_id)
        param_set_id = UUID(args.param_set_id)
    except ValueError as e:
        logger.error(f"Invalid UUID format: {str(e)}")
        return 1
    
    # Run the async calculation
    return asyncio.run(run_l2_calculation(dataset_id, param_set_id))


if __name__ == "__main__":
    sys.exit(main())
