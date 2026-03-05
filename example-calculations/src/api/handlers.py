"""Handler functions for API endpoints."""

import logging
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import HTTPException

# Database connection
from sqlalchemy import create_engine, text
from src.config.parameters import DB_SCHEMA, USER, SERVER, PORT, DB
from src.engine import xls, sql
from src.utils import json_utils

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Helper class for database operations."""
    
    def __init__(self):
        """Initialize database connection."""
        # Try local development first, fall back to AWS secrets in production
        try:
            # Try local PostgreSQL first (Docker development)
            try:
                connection_string = f"postgresql://{USER}:postgres@localhost:5432/{DB}"
                self.engine = create_engine(connection_string)
                # Test connection
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    logger.info("Database connection successful (localhost)")
            except Exception:
                # Fall back to config server
                connection_string = f"postgresql://{USER}:postgres@{SERVER}:{PORT}/{DB}"
                self.engine = create_engine(connection_string)
                # Test connection
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    logger.info("Database connection successful (config server)")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            self.engine = None
    
    def execute_query(self, query: str, params: Dict[str, Any] = None):
        """Execute a query and return results."""
        if not self.engine:
            raise RuntimeError("Database connection not available")
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                conn.commit()
                return result.fetchall() if result.returns_rows else None
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def check_connection(self) -> bool:
        """Check if database is accessible."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            return False


# Global database connection
db = DatabaseConnection()


# ============ Health Check Handler ============

async def handle_health_check():
    """Check API and database health."""
    db_ok = db.check_connection() if db.engine else False
    
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "timestamp": datetime.now().isoformat()
    }


# ============ Upload Data Handler ============

async def handle_upload_data(file_path: str, override_file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Handle POST /api/v1/data/upload
    
    Integrates with Phase 2B versioning:
    - Creates data_versions entry for Bloomberg file
    - Optionally merges with override_versions
    - Creates adjusted_data and data_quality entries
    - Threads dq_id through pipeline
    
    Returns:
        Dict with job_id, status, dq_id, file_hash, record_count
    """
    job_id = str(uuid.uuid4())
    
    try:
        # Create job record in database
        insert_job_query = f"""
            INSERT INTO {DB_SCHEMA}."jobs" 
            (job_id, job_type, status, progress_percent)
            VALUES (:job_id, :job_type, :status, :progress)
        """
        db.execute_query(insert_job_query, {
            'job_id': job_id,
            'job_type': 'upload',
            'status': 'in_progress',
            'progress': 0
        })
        
        logger.info(f"Created upload job {job_id} for file {file_path}")
        
        # ===== Phase 2B: Versioning Integration =====
        
        # Determine upload type and execute versioned upload
        if override_file_path:
            # Upload with override
            dq_id = xls.upload_with_override(
                raw_data_path=file_path,
                override_data_path=override_file_path,
                version_name=f"Upload {job_id[:8]}",
                override_name=f"Override {job_id[:8]}",
                execute=True,
                created_by="api"
            )
        else:
            # Upload raw Bloomberg data only
            dq_id = xls.upload_bbg_data_with_versioning(
                file_path=file_path,
                version_name=f"Upload {job_id[:8]}",
                execute=True,
                created_by="api"
            )
        
        if not dq_id:
            raise RuntimeError("Failed to create versioning entries for upload")
        
        # Calculate file hash for result
        file_hash = sql.calculate_file_hash(file_path)
        
        # Update job with success result
        result_data = {
            "dq_id": str(dq_id),
            "file_hash": file_hash,
            "record_count": 0  # TODO: get actual record count from upload
        }
        
        update_job_query = f"""
            UPDATE {DB_SCHEMA}."jobs"
            SET status = :status, progress_percent = :progress, 
                result = :result, dq_id = :dq_id
            WHERE job_id = :job_id
        """
        db.execute_query(update_job_query, {
            'job_id': job_id,
            'status': 'completed',
            'progress': 100,
            'result': json.dumps(result_data),
            'dq_id': str(dq_id)
        })
        
        logger.info(f"Upload job {job_id} completed with dq_id {dq_id}")
        
        return {
            "job_id": job_id,
            "status": "completed",
            "dq_id": str(dq_id),
            "file_hash": file_hash,
            "message": f"Upload completed successfully. Data quality ID: {dq_id}"
        }
        
    except Exception as e:
        logger.error(f"Upload handler failed: {e}")
        # Update job as failed
        try:
            update_job_query = f"""
                UPDATE {DB_SCHEMA}."jobs"
                SET status = :status, error_message = :error
                WHERE job_id = :job_id
            """
            db.execute_query(update_job_query, {
                'job_id': job_id,
                'status': 'failed',
                'error': str(e)
            })
        except:
            pass  # Already logged the error
        
        raise HTTPException(status_code=500, detail=str(e))


# ============ Metrics Calculation Handler ============

async def handle_calculate_metrics(dq_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle POST /api/v1/metrics/calculate
    
    Integrates with Phase 2B versioning and Phase 2C caching:
    - Gets or creates parameter_scenarios entry (canonical JSON)
    - Checks for completed metric_runs with (dq_id, param_id) pair
    - If cache hit: returns calc_id directly
    - If cache miss: creates metric_runs entry with 'pending' status
    
    Returns:
        Dict with job_id, status, cached, calc_id, param_id, message
    """
    job_id = str(uuid.uuid4())
    
    try:
        # Validate dq_id exists
        dq_check_query = f"""
            SELECT dq_id FROM {DB_SCHEMA}."data_quality"
            WHERE dq_id = :dq_id
            LIMIT 1
        """
        result = db.execute_query(dq_check_query, {'dq_id': dq_id})
        
        if not result:
            raise ValueError(f"Invalid dq_id: {dq_id}")
        
        # Create job record
        insert_job_query = f"""
            INSERT INTO {DB_SCHEMA}."jobs" 
            (job_id, job_type, status, dq_id, progress_percent)
            VALUES (:job_id, :job_type, :status, :dq_id, :progress)
        """
        db.execute_query(insert_job_query, {
            'job_id': job_id,
            'job_type': 'metrics',
            'status': 'in_progress',
            'dq_id': dq_id,
            'progress': 0
        })
        
        logger.info(f"Created metrics job {job_id} for dq_id {dq_id}")
        
        # ===== Phase 2B/2C: Versioning & Caching Integration =====
        
        # Convert dq_id string to UUID
        from uuid import UUID
        dq_id_uuid = UUID(dq_id)
        
        # Step 1: Get or create parameter scenario (canonical JSON for deduplication)
        param_id = sql.get_or_create_parameter_scenario(
            params_dict=parameters,
            is_default=False,
            created_by="api"
        )
        
        logger.info(f"Metrics job {job_id}: Using param_id {param_id}")
        
        # Step 2: Check if this (dq_id, param_id) pair has been calculated before (cache check)
        cached_calc_id = sql.find_completed_metric_run(dq_id_uuid, param_id)
        
        if cached_calc_id:
            # CACHE HIT: Return existing results
            logger.info(f"Metrics job {job_id}: Cache hit, reusing calc_id {cached_calc_id}")
            
            result_data = {
                "calc_id": str(cached_calc_id),
                "cached": True,
                "param_id": str(param_id)
            }
            
            update_job_query = f"""
                UPDATE {DB_SCHEMA}."jobs"
                SET status = :status, progress_percent = :progress, 
                    result = :result, calc_id = :calc_id
                WHERE job_id = :job_id
            """
            db.execute_query(update_job_query, {
                'job_id': job_id,
                'status': 'completed',
                'progress': 100,
                'result': json.dumps(result_data),
                'calc_id': str(cached_calc_id)
            })
            
            return {
                "job_id": job_id,
                "status": "completed",
                "cached": True,
                "calc_id": str(cached_calc_id),
                "param_id": str(param_id),
                "message": f"Metrics calculation found in cache. Using calc_id {cached_calc_id}"
            }
        
        # CACHE MISS: Create new metric_runs entry for execution
        logger.info(f"Metrics job {job_id}: Cache miss, creating new metric_runs entry")
        
        calc_id = sql.create_metric_run(
            dq_id=dq_id_uuid,
            param_id=param_id,
            status="pending",
            created_by="api",
            metadata={"job_id": job_id, "parameters": parameters}
        )
        
        logger.info(f"Metrics job {job_id}: Created metric_runs with calc_id {calc_id}")
        
        result_data = {
            "calc_id": str(calc_id),
            "cached": False,
            "param_id": str(param_id)
        }
        
        update_job_query = f"""
            UPDATE {DB_SCHEMA}."jobs"
            SET status = :status, progress_percent = :progress, 
                result = :result, calc_id = :calc_id
            WHERE job_id = :job_id
        """
        db.execute_query(update_job_query, {
            'job_id': job_id,
            'status': 'completed',
            'progress': 50,
            'result': json.dumps(result_data),
            'calc_id': str(calc_id)
        })
        
        return {
            "job_id": job_id,
            "status": "queued",
            "cached": False,
            "calc_id": str(calc_id),
            "param_id": str(param_id),
            "message": f"Metrics calculation queued. Execution will use calc_id {calc_id}"
        }
        
    except Exception as e:
        logger.error(f"Metrics handler failed: {e}")
        # Update job as failed
        try:
            update_job_query = f"""
                UPDATE {DB_SCHEMA}."jobs"
                SET status = :status, error_message = :error
                WHERE job_id = :job_id
            """
            db.execute_query(update_job_query, {
                'job_id': job_id,
                'status': 'failed',
                'error': str(e)
            })
        except:
            pass  # Already logged the error
        
        raise HTTPException(status_code=500, detail=str(e))


# ============ Job Status Handler ============

async def handle_get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Handle GET /api/v1/jobs/{job_id}/status
    
    Returns:
        Job status record
    """
    try:
        query = f"""
            SELECT 
                job_id, job_type, status, created_at, updated_at,
                started_at, ended_at, progress_percent, result, error_message
            FROM {DB_SCHEMA}."jobs"
            WHERE job_id = :job_id
        """
        result = db.execute_query(query, {'job_id': job_id})
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        
        row = result[0]
        
        return {
            "job_id": str(row[0]),
            "job_type": row[1],
            "status": row[2],
            "created_at": row[3].isoformat() if row[3] else None,
            "updated_at": row[4].isoformat() if row[4] else None,
            "started_at": row[5].isoformat() if row[5] else None,
            "ended_at": row[6].isoformat() if row[6] else None,
            "progress_percent": row[7],
            "result": row[8],
            "error_message": row[9]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get job status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PHASE 3: Metrics Calculation Handler Functions
# ============================================================================

async def handle_calculate_metrics_phase3(dq_id: str, parameters: Dict[str, Any]):
    """
    Handler for POST /api/v1/metrics/calculate (Phase 3).
    
    Creates a metrics calculation job with dq_id threading and cache detection.
    
    Args:
        dq_id: Data quality ID (UUID string)
        parameters: Calculation parameters dict
    
    Returns:
        MetricsCalculateResponse with calc_id and status
    
    Raises:
        HTTPException: If dq_id invalid or DB error
    """
    db = DatabaseConnection()
    
    try:
        from uuid import UUID
        
        # Parse dq_id
        try:
            dq_id = UUID(dq_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid dq_id UUID format")
        
        # Verify dq_id exists and has data
        if not sql.verify_dq_id_has_data(dq_id):
            raise HTTPException(
                status_code=400,
                detail=f"dq_id {dq_id} not found or has no data"
            )
        
        # Canonicalize parameters (sort keys)
        canonical_params = json.dumps(parameters, sort_keys=True)
        params_obj = json.loads(canonical_params)
        
        with db.engine.connect() as conn:
            # Look up or create parameter scenario
            param_id = sql.find_or_create_parameter_scenario(conn, params_obj)
            
            # Check cache
            cached_calc_id = sql.find_completed_metric_run(conn, dq_id, param_id)
            
            if cached_calc_id:
                # Cache hit - return existing result
                logger.info(f"Cache hit for dq_id={dq_id}, param_id={param_id}")
                
                run_result = conn.execute(
                    text("""
                        SELECT calc_id, status, created_at, started_at, completed_at
                        FROM "USR"."metric_runs"
                        WHERE calc_id = :calc_id
                    """),
                    {'calc_id': str(cached_calc_id)}
                ).first()
                
                return {
                    "calc_id": str(cached_calc_id),
                    "status": "completed",
                    "dq_id": str(dq_id),
                    "param_id": str(param_id),
                    "created_at": run_result[2],
                    "started_at": run_result[3],
                    "completed_at": run_result[4]
                }
            
            # Cache miss - create new metric_runs entry
            calc_id = sql.create_metric_run(conn, dq_id, param_id)
            logger.info(f"Created new metric_runs {calc_id} for dq_id={dq_id}")
            
            return {
                "calc_id": str(calc_id),
                "status": "pending",
                "dq_id": str(dq_id),
                "param_id": str(param_id),
                "created_at": datetime.utcnow(),
                "started_at": None,
                "completed_at": None
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Metrics calculation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)}")


async def handle_get_metrics_status(calc_id):
    """
    Handler for GET /api/v1/metrics/{calc_id}.
    
    Returns current status of a metrics calculation job.
    
    Args:
        calc_id: Calculation run ID (UUID)
    
    Returns:
        MetricsStatusResponse with status and timestamps
    
    Raises:
        HTTPException: If calc_id not found
    """
    db = DatabaseConnection()
    
    try:
        from uuid import UUID
        
        with db.engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT calc_id, status, dq_id, param_id, 
                           started_at, completed_at, metadata
                    FROM "USR"."metric_runs"
                    WHERE calc_id = :calc_id
                """),
                {'calc_id': str(calc_id)}
            ).first()
            
            if not row:
                raise HTTPException(status_code=404, detail="Calculation not found")
            
            error_msg = None
            if row[6]:  # metadata column
                try:
                    metadata = json.loads(row[6])
                    error_msg = metadata.get('error')
                except:
                    pass
            
            return {
                "calc_id": str(row[0]),
                "status": row[1],
                "dq_id": str(row[2]),
                "param_id": str(row[3]),
                "started_at": row[4],
                "completed_at": row[5],
                "error_message": error_msg
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get metrics status failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get metrics status")


async def handle_get_metrics_results(calc_id, page: int = 1, page_size: int = 100):
    """
    Handler for GET /api/v1/metrics/{calc_id}/results.
    
    Returns paginated calculated metrics results.
    
    Args:
        calc_id: Calculation run ID (UUID)
        page: Page number (1-indexed)
        page_size: Results per page
    
    Returns:
        MetricsResultsResponse with paginated results
    
    Raises:
        HTTPException: If calc_id not found or calculation not completed
    """
    db = DatabaseConnection()
    
    try:
        from uuid import UUID
        
        with db.engine.connect() as conn:
            # Verify calc_id exists and is completed
            run_check = conn.execute(
                text("""
                    SELECT status FROM "USR"."metric_runs"
                    WHERE calc_id = :calc_id
                """),
                {'calc_id': str(calc_id)}
            ).first()
            
            if not run_check:
                raise HTTPException(status_code=404, detail="Calculation not found")
            
            if run_check[0] != 'completed':
                raise HTTPException(
                    status_code=400,
                    detail=f"Calculation status is '{run_check[0]}', not completed"
                )
            
            # Fetch total count
            count_row = conn.execute(
                text("""
                    SELECT COUNT(*) as total
                    FROM "USR"."metric_results"
                    WHERE calc_id = :calc_id
                """),
                {'calc_id': str(calc_id)}
            ).first()
            
            total = count_row[0] if count_row else 0
            
            # Fetch paginated results
            offset = (page - 1) * page_size
            
            rows = conn.execute(
                text("""
                    SELECT ticker, fx_currency, fy_year, key, value
                    FROM "USR"."metric_results"
                    WHERE calc_id = :calc_id
                    ORDER BY ticker, fy_year DESC, key
                    LIMIT :limit OFFSET :offset
                """),
                {
                    'calc_id': str(calc_id),
                    'limit': page_size,
                    'offset': offset
                }
            ).fetchall()
            
            results = [
                {
                    "ticker": row[0],
                    "fx_currency": row[1],
                    "fy_year": row[2],
                    "key": row[3],
                    "value": float(row[4]) if row[4] is not None else None
                }
                for row in rows
            ]
            
            return {
                "calc_id": str(calc_id),
                "results": results,
                "total": total,
                "page": page,
                "page_size": page_size,
                "status": "completed"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get metrics results failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics results")
