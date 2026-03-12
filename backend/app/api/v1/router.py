# ============================================================================
# API v1 Router - Aggregates all endpoints
# ============================================================================
from fastapi import APIRouter
from .endpoints import metrics, parameters

router = APIRouter()
router.include_router(metrics.router)
router.include_router(parameters.router)
