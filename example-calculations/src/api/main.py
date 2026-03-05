"""CISSA FastAPI application with versioning endpoints."""

import asyncio
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from uuid import UUID
import logging

from . import handlers
from . import models
from src.services.metrics_worker import create_metrics_worker
from src.config.parameters import USER, SERVER, PORT, DB

# Build database URL from config
DATABASE_URL = f"postgresql://{USER}:postgres@{SERVER}:{PORT}/{DB}"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global worker instance
metrics_worker = None
worker_task = None


# ============ Lifespan Events ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown logic.
    
    Startup:
    - Verify database connection
    - Start metrics worker for async job processing
    - Log service start
    
    Shutdown:
    - Stop metrics worker gracefully
    - Log service stop
    """
    global metrics_worker, worker_task
    
    # STARTUP
    logger.info("CISSA API service starting...")
    try:
        db_ok = await handlers.handle_health_check()
        logger.info(f"Database health: {db_ok['database']}")
    except Exception as e:
        logger.warning(f"Database connection warning during startup: {e}")
    
    # Start metrics worker
    try:
        from src.config.parameters import DATABASE_URL
        metrics_worker = create_metrics_worker(DATABASE_URL, poll_interval=5)
        worker_task = asyncio.create_task(metrics_worker.start())
        logger.info("Metrics worker started")
    except Exception as e:
        logger.error(f"Failed to start metrics worker: {e}")
        # Continue anyway - API can function without worker for testing
    
    yield
    
    # SHUTDOWN
    logger.info("CISSA API service shutting down...")
    
    # Stop metrics worker
    if metrics_worker:
        try:
            await metrics_worker.stop()
            if worker_task:
                await asyncio.wait_for(worker_task, timeout=10)
            logger.info("Metrics worker stopped")
        except asyncio.TimeoutError:
            logger.warning("Metrics worker did not stop within timeout")
        except Exception as e:
            logger.error(f"Error stopping metrics worker: {e}")


# ============ FastAPI Application ============

app = FastAPI(
    title="CISSA Versioning API",
    description="Data upload and metrics calculation with full audit trail and versioning",
    version="2.0.0",
    lifespan=lifespan
)

# ============ CORS Middleware ============

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in Phase 3 with proper auth
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ Routes ============

@app.get("/api/v1/health", response_model=models.HealthStatus)
async def health_check():
    """
    Check API and database health.
    
    Returns:
        HealthStatus with overall status and database status
    """
    return await handlers.handle_health_check()


@app.post("/api/v1/data/upload", response_model=models.UploadDataResponse)
async def upload_data(request: models.UploadDataRequest):
    """
    Upload Bloomberg data file with optional override file.
    
    This endpoint creates a versioned data upload job that:
    1. Calculates file hash for deduplication
    2. Creates data_versions entry
    3. Optionally creates override_versions entry
    4. Runs data quality checks
    5. Populates input tables with dq_id traceability
    
    Args:
        request: UploadDataRequest with file_path and optional override_file_path
    
    Returns:
        UploadDataResponse with job_id and status
    """
    return await handlers.handle_upload_data(request.file_path, request.override_file_path)


@app.post("/api/v1/metrics/calculate", response_model=models.CalculateMetricsResponse)
async def calculate_metrics(request: models.CalculateMetricsRequest):
    """
    Calculate L1 metrics with parameter deduplication and caching.
    
    This endpoint creates a metrics calculation job that:
    1. Validates dq_id exists in data_quality table
    2. Deduplicates parameters via canonical JSON
    3. Checks cache for existing calculation with same dq_id + params
    4. If cache hit: returns cached results immediately
    5. If cache miss: runs calculation and caches results
    6. Returns metrics with full traceability (calc_id)
    
    Args:
        request: CalculateMetricsRequest with dq_id and parameters dict
    
    Returns:
        CalculateMetricsResponse with job_id, status, and cache flag
    """
    return await handlers.handle_calculate_metrics(request.dq_id, request.parameters)


@app.get("/api/v1/jobs/{job_id}/status", response_model=models.JobStatus)
async def get_job_status(job_id: str):
    """
    Get status of an upload or metrics calculation job.
    
    Returns real-time progress updates and results for async jobs.
    
    Args:
        job_id: UUID of the job to check
    
    Returns:
        JobStatus with current status, progress, and results
    
    Raises:
        HTTPException: 404 if job_id not found
    """
    return await handlers.handle_get_job_status(job_id)


# ============ Phase 3: Metrics Calculation with dq_id ============

@app.post("/api/v1/metrics/calculate", response_model=models.MetricsCalculateResponse)
async def calculate_metrics_phase3(request: models.MetricsCalculateRequest):
    """
    Calculate L1 and L2 metrics for specific data version (dq_id).
    
    Creates a metrics calculation job that:
    1. Validates dq_id exists in data_quality table
    2. Canonicalizes parameters (keys sorted)
    3. Checks cache for existing calculation with same (dq_id, param_id)
    4. If cache hit: returns cached calc_id immediately
    5. If cache miss: creates metric_runs entry with status='pending'
    6. Worker service processes job asynchronously
    
    Args:
        request: MetricsCalculateRequest with dq_id and parameters dict
    
    Returns:
        MetricsCalculateResponse with calc_id and status
    
    Raises:
        HTTPException: 400 if dq_id invalid or calculation fails
    """
    return await handlers.handle_calculate_metrics_phase3(
        request.dq_id, request.parameters
    )


@app.get("/api/v1/metrics/{calc_id}", response_model=models.MetricsStatusResponse)
async def get_metrics_status(calc_id: UUID):
    """
    Get status of a metrics calculation job.
    
    Args:
        calc_id: UUID of the metrics calculation run
    
    Returns:
        MetricsStatusResponse with current status and timestamps
    
    Raises:
        HTTPException: 404 if calc_id not found
    """
    return await handlers.handle_get_metrics_status(calc_id)


@app.get("/api/v1/metrics/{calc_id}/results", response_model=models.MetricsResultsResponse)
async def get_metrics_results(
    calc_id: UUID,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(100, ge=1, le=1000, description="Results per page")
):
    """
    Get calculated metrics results for a completed calculation.
    
    Returns paginated results from metric_results table.
    Supports filtering by ticker, key, and fiscal year via query params.
    
    Args:
        calc_id: UUID of the metrics calculation run
        page: Page number for pagination (default: 1)
        page_size: Results per page (default: 100, max: 1000)
    
    Returns:
        MetricsResultsResponse with paginated results
    
    Raises:
        HTTPException: 400 if calculation not completed or 404 if not found
    """
    return await handlers.handle_get_metrics_results(calc_id, page, page_size)


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint redirects to documentation."""
    return {"message": "CISSA API v2.0. See /docs for Swagger UI"}


# ============ Error Handlers ============

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with consistent response format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


# ============ Swagger/OpenAPI Documentation ============
# Automatically available at:
# - /docs (Swagger UI)
# - /redoc (ReDoc)
# - /openapi.json (OpenAPI schema)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
