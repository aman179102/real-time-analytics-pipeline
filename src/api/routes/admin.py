from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.dependencies import (
    get_analytics_service,
    get_retention_manager,
    require_role,
    verify_token,
)
from src.core.analytics_service import AnalyticsService
from src.core.retention import RetentionManager
from src.domain.models import UserRole
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.post("/retention/apply")
async def apply_retention(
    retention_manager: RetentionManager = Depends(get_retention_manager),
    token: dict = Depends(require_role(UserRole.ADMIN)),
) -> dict:
    results = await retention_manager.apply_retention_policy()
    return {
        "status": "completed",
        "results": results,
    }


@router.get("/retention/summary")
async def get_retention_summary(
    retention_manager: RetentionManager = Depends(get_retention_manager),
    token: dict = Depends(require_role(UserRole.ADMIN)),
) -> dict:
    return await retention_manager.get_retention_summary()


@router.get("/metrics/snapshot")
async def get_metrics_snapshot(
    token: dict = Depends(require_role(UserRole.ADMIN)),
) -> dict:
    from src.infrastructure.metrics import metrics
    return metrics.snapshot()


@router.get("/sampling/stats")
async def get_sampling_stats(
    token: dict = Depends(require_role(UserRole.ADMIN)),
) -> dict:
    from src.core.sampling import Sampler
    sampler = Sampler()
    return sampler.get_sampling_stats()
