from __future__ import annotations

import time
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.config import config
from src.infrastructure.logging import get_logger
from src.infrastructure.metrics import metrics

logger = get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next
    ) -> Response:
        start_time = time.monotonic()

        if request.url.path.startswith(
            ("/health", "/docs", "/openapi.json", "/api/v1/auth")
        ):
            response = await call_next(request)
            return response

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            if request.url.path.startswith("/api/v1"):
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "details": {},
                        }
                    },
                )

        response = await call_next(request)
        metrics.record_latency(
            "request_duration",
            time.monotonic() - start_time,
            {"method": request.method, "path": request.url.path},
        )
        return response
