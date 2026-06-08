from __future__ import annotations

import time

from fastapi import APIRouter

from src.config import config

router = APIRouter(tags=["Health"])

_start_time = time.time()


@router.get("/health")
async def health_check() -> dict:
    return {
        "status": "ok",
        "version": config.version,
        "uptime": int(time.time() - _start_time),
        "service": config.service_name,
        "environment": config.environment.value,
    }


@router.get("/api/v1/health")
async def health_check_v1() -> dict:
    return await health_check()
