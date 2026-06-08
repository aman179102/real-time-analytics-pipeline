from __future__ import annotations

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi

from src.api.errors import AppError
from src.api.middleware.auth import AuthMiddleware
from src.api.middleware.cors import setup_cors
from src.api.middleware.logging import LoggingMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.routes.health import router as health_router
from src.api.routes.auth import router as auth_router
from src.api.routes.events import router as events_router
from src.api.routes.analytics import router as analytics_router
from src.api.routes.dashboards import router as dashboards_router
from src.api.routes.admin import router as admin_router
from src.api.websocket.handlers import router as ws_router
from src.config import config
from src.infrastructure.database.session import init_db, close_db
from src.infrastructure.logging import get_logger
from src.infrastructure.metrics import metrics
from src.infrastructure.tracing import tracer

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "Starting %s v%s in %s mode",
        config.service_name,
        config.version,
        config.environment.value,
    )

    await init_db()
    await metrics.initialize()
    await tracer.initialize()

    yield

    logger.info("Shutting down %s", config.service_name)
    await close_db()
    await metrics.shutdown()
    await tracer.shutdown()


app = FastAPI(
    title="Real-Time Analytics Pipeline",
    description=(
        "Enterprise-grade real-time analytics pipeline with async processing, "
        "event ingestion via Redis Streams/Kafka, time-series storage, "
        "WebSocket real-time dashboards, and comprehensive observability."
    ),
    version=config.version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


setup_cors(app)
app.add_middleware(AuthMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
        headers={
            "X-Error-Code": exc.code,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.error(
        "Unhandled exception: %s",
        str(exc),
        extra={"path": request.url.path, "method": request.method},
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {},
            }
        },
    )


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(events_router)
app.include_router(analytics_router)
app.include_router(dashboards_router)
app.include_router(admin_router)
app.include_router(ws_router)


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Real-Time Analytics Pipeline API",
        version=config.version,
        description=(
            "Enterprise-grade real-time analytics pipeline API. "
            "Supports event ingestion, analytics queries, dashboard management, "
            "and real-time WebSocket streaming."
        ),
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    for path in openapi_schema["paths"].values():
        for method in path.values():
            if method.get("operationId") not in [
                "health_check_health_get",
                "health_check_v1_api_v1_health_get",
            ]:
                method.setdefault("security", [{"bearerAuth": []}])

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


def handle_signal(sig: int, frame: object = None) -> None:
    logger.info("Received signal %d, initiating graceful shutdown", sig)
    sys.exit(0)


def main() -> None:
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    uvicorn.run(
        "src.main:app",
        host=config.host,
        port=config.port,
        workers=config.workers,
        log_level=config.log_level.value.lower(),
        reload=config.debug,
    )


if __name__ == "__main__":
    main()
