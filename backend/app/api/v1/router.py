# ============================================================================
# API v1 Router - Aggregates all endpoints
# ============================================================================
from fastapi import APIRouter
from .endpoints import metrics, parameters, orchestration, statistics

router = APIRouter()
router.include_router(metrics.router)
router.include_router(parameters.router)
router.include_router(orchestration.router)
router.include_router(statistics.router)
