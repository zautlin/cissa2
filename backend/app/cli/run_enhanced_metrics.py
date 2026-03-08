#!/usr/bin/env python3
# ============================================================================
# CLI Script: Run Enhanced Metrics Calculation
# ============================================================================
# Usage: python run_enhanced_metrics.py <dataset_id> <param_set_id>
# ============================================================================

import asyncio
import sys
from uuid import UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.services.enhanced_metrics_service import EnhancedMetricsService
from app.core.config import get_logger, settings

logger = get_logger(__name__)


async def main():
    """Main entry point for CLI."""
    if len(sys.argv) != 3:
        print("Usage: python run_enhanced_metrics.py <dataset_id> <param_set_id>")
        print("\nExample:")
        print("  python run_enhanced_metrics.py 550e8400-e29b-41d4-a716-446655440000 660e8400-e29b-41d4-a716-446655440001")
        sys.exit(1)
    
    dataset_id_str = sys.argv[1]
    param_set_id_str = sys.argv[2]
    
    try:
        dataset_id = UUID(dataset_id_str)
        param_set_id = UUID(param_set_id_str)
    except ValueError as e:
        print(f"Error: Invalid UUID format. {e}")
        sys.exit(1)
    
    # Create async engine and session
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True
    )
    
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        logger.info(f"Starting enhanced metrics calculation")
        logger.info(f"  Dataset ID: {dataset_id}")
        logger.info(f"  Param Set ID: {param_set_id}")
        
        service = EnhancedMetricsService(session)
        result = await service.calculate_enhanced_metrics(dataset_id, param_set_id)
        
        # Print results
        print("\n" + "="*60)
        print("ENHANCED METRICS CALCULATION RESULTS")
        print("="*60)
        print(f"Status: {result['status'].upper()}")
        print(f"Message: {result['message']}")
        print(f"Records Inserted: {result['results_count']}")
        print(f"Metrics Calculated: {', '.join(result['metrics_calculated'])}")
        print("="*60 + "\n")
        
        if result['status'] == 'error':
            sys.exit(1)
        else:
            sys.exit(0)
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
