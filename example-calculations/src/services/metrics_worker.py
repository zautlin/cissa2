"""
Phase 3: Metrics Calculation Worker Service

Background worker that polls metric_runs table for pending calculations
and executes L1/L2 metrics calculations with dq_id traceability.
"""

import asyncio
import logging
from datetime import datetime
from uuid import UUID
from sqlalchemy import create_engine, text

from src.calculate_metrics_with_dq import calculate_metrics_with_dq
from src.engine import sql
from src.engine.loaders import store_metrics_with_calc_id

logger = logging.getLogger(__name__)


class MetricsWorker:
    """
    Background worker for executing pending metrics calculations.
    
    Polls metric_runs table every N seconds for jobs with status='pending',
    executes L1 and L2 metrics calculations, and updates results.
    
    Single job at a time (per specification, no concurrency).
    """
    
    def __init__(self, db_url: str, poll_interval: int = 5):
        """
        Initialize metrics worker.
        
        Args:
            db_url: Database connection string (SQLAlchemy format)
            poll_interval: Seconds between polling (default: 5)
        """
        self.db_url = db_url
        self.poll_interval = poll_interval
        self.running = False
        self.engine = None
        self.task = None
    
    async def start(self) -> None:
        """
        Start the worker polling loop.
        
        Runs continuously until stop() is called.
        Catches and logs errors to prevent worker crash.
        """
        self.running = True
        self.engine = create_engine(self.db_url, pool_pre_ping=True)
        logger.info(
            f"MetricsWorker started (poll_interval={self.poll_interval}s)"
        )
        
        try:
            while self.running:
                try:
                    await self._process_pending_jobs()
                except Exception as e:
                    logger.error(
                        f"Error processing pending jobs: {e}",
                        exc_info=True
                    )
                
                # Sleep before next poll
                await asyncio.sleep(self.poll_interval)
        
        except asyncio.CancelledError:
            logger.info("MetricsWorker cancelled")
        except Exception as e:
            logger.error(
                f"Unexpected error in worker loop: {e}",
                exc_info=True
            )
        finally:
            if self.engine:
                self.engine.dispose()
                logger.info("MetricsWorker database engine disposed")
    
    async def stop(self) -> None:
        """
        Stop the worker loop gracefully.
        
        Sets running flag to False, causing loop to exit on next iteration.
        """
        logger.info("Stopping MetricsWorker")
        self.running = False
    
    async def _process_pending_jobs(self) -> None:
        """
        Poll for pending jobs and process one at a time.
        
        Gets list of pending metric_runs entries and processes each,
        one at a time, in order of creation (FIFO).
        """
        try:
            with self.engine.connect() as conn:
                # Get all pending jobs
                pending_jobs = sql.get_pending_metric_runs(conn)
                
                if pending_jobs:
                    logger.debug(
                        f"Found {len(pending_jobs)} pending jobs"
                    )
                
                # Process one at a time (no concurrency)
                for job in pending_jobs:
                    if not self.running:
                        break
                    
                    await self._execute_job(job, conn)
        
        except Exception as e:
            logger.error(
                f"Error in _process_pending_jobs: {e}",
                exc_info=True
            )
    
    async def _execute_job(self, job: dict, conn) -> None:
        """
        Execute a single metrics calculation job.
        
        Args:
            job: Dict with keys: {calc_id, dq_id, param_id, parameters}
            conn: Database connection
        """
        calc_id = job['calc_id']
        dq_id = job['dq_id']
        param_id = job['param_id']
        parameters = job['parameters']
        
        # Convert string UUIDs to UUID objects if needed
        if isinstance(calc_id, str):
            calc_id = UUID(calc_id)
        if isinstance(dq_id, str):
            dq_id = UUID(dq_id)
        if isinstance(param_id, str):
            param_id = UUID(param_id)
        
        try:
            logger.info(
                f"Starting calculation {calc_id} for dq_id={dq_id}"
            )
            
            # Update status to 'running'
            sql.update_metric_run_status(
                conn,
                calc_id,
                'running',
                started_at=datetime.utcnow()
            )
            
            # Execute metrics calculation
            results_dict, results_list = calculate_metrics_with_dq(
                dq_id=dq_id,
                calc_id=calc_id,
                parameters=parameters,
                db_connection=conn
            )
            
            # Store results in metric_results table
            store_metrics_with_calc_id(
                results_list, calc_id, param_id, dq_id
            )
            
            # Update status to 'completed'
            sql.update_metric_run_status(
                conn,
                calc_id,
                'completed',
                completed_at=datetime.utcnow()
            )
            
            logger.info(
                f"Calculation {calc_id} completed successfully "
                f"({len(results_list)} results stored)"
            )
        
        except Exception as e:
            logger.error(
                f"Calculation {calc_id} failed: {e}",
                exc_info=True
            )
            error_msg = str(e)
            
            try:
                # Update status to 'failed' with error message
                sql.update_metric_run_status(
                    conn,
                    calc_id,
                    'failed',
                    completed_at=datetime.utcnow(),
                    error_message=error_msg
                )
                logger.info(f"Updated {calc_id} status to failed")
            except Exception as update_error:
                logger.error(
                    f"Failed to update metric_run {calc_id} status: "
                    f"{update_error}",
                    exc_info=True
                )


def create_metrics_worker(db_url: str, poll_interval: int = 5) -> MetricsWorker:
    """
    Factory function to create a MetricsWorker instance.
    
    Args:
        db_url: Database connection string
        poll_interval: Seconds between polls
    
    Returns:
        MetricsWorker instance
    """
    return MetricsWorker(db_url, poll_interval)
