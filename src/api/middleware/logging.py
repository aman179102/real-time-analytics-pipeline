from __future__ import annotations

import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next
    ) -> Response:
        correlation_id = request.headers.get(
            "X-Correlation-ID", str(uuid.uuid4())
        )
        request.state.correlation_id = correlation_id

        start_time = time.monotonic()

        logger.info(
            "Request started",
            correlation_id=correlation_id,
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", ""),
            },
        )

        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(
                "Request failed",
                correlation_id=correlation_id,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                },
            )
            raise

        elapsed = time.monotonic() - start_time

        logger.info(
            "Request completed",
            correlation_id=correlation_id,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "elapsed_ms": round(elapsed * 1000, 2),
            },
        )

        response.headers["X-Correlation-ID"] = correlation_id
        return response
