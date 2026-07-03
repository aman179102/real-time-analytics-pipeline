from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.config import config
from src.api.errors import RateLimitError
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next
    ) -> Response:
        if not config.rate_limit.enabled:
            return await call_next(request)

        if request.url.path in ("/health", "/metrics"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        bucket_key = f"{client_ip}:{request.url.path}"

        now = time.monotonic()
        window_start = now - 60.0

        timestamps = self._buckets[bucket_key]
        timestamps[:] = [t for t in timestamps if t > window_start]

        if len(timestamps) >= config.rate_limit.requests_per_minute:
            logger.warning("Rate limit exceeded for %s", client_ip)
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests",
                        "details": {
                            "retry_after_seconds": 60,
                            "limit": config.rate_limit.requests_per_minute,
                            "window_seconds": 60,
                        },
                    }
                },
                headers={
                    "X-RateLimit-Limit": str(config.rate_limit.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + 60)),
                    "Retry-After": "60",
                },
            )
            return response

        timestamps.append(now)
        remaining = config.rate_limit.requests_per_minute - len(timestamps)

        response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(
            config.rate_limit.requests_per_minute
        )
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int(now + 60))

        return response
