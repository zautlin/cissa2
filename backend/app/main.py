# ============================================================================
# FastAPI Main Application
# ============================================================================
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .core.config import get_settings, get_logger
from .core.database import get_db_manager
from .api.v1 import router
from .api.v2 import router as router_v2

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup/shutdown events.
    
    Startup:
    - Initialize database connections
    
    Shutdown:
    - Close database connections
    """
    # Startup
    logger.info("Starting FastAPI application")
    db_manager = get_db_manager()
    await db_manager.initialize()
    logger.info("Database initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI application")
    await db_manager.close()
    logger.info("Database closed successfully")


# Create FastAPI app with lifespan
app = FastAPI(
    title="CISSA Metrics API",
    description="FastAPI backend for Phase 1 metric calculations from PostgreSQL",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include v1 router
app.include_router(router.router)
# Include v2 router
app.include_router(router_v2.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "CISSA Metrics API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/metrics/health"
    }


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=(settings.fastapi_env == "development"),
        workers=settings.workers
    )
