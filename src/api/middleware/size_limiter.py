from __future__ import annotations

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.config import config
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class SizeLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            size = int(content_length)
            if size > config.max_request_size:
                logger.warning(
                    "Request body too large: %d bytes (max: %d)",
                    size,
                    config.max_request_size,
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": "Request body exceeds maximum allowed size",
                            "details": {
                                "max_size_bytes": config.max_request_size,
                                "received_bytes": size,
                            },
                        }
                    },
                )

        return await call_next(request)
