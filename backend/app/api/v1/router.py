# ============================================================================
# API v1 Router - Aggregates all endpoints
# ============================================================================
from fastapi import APIRouter
from .endpoints import metrics

router = APIRouter()
router.include_router(metrics.router)
