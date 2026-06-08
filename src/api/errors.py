from __future__ import annotations

from typing import Any, Optional


class AppError(Exception):
    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"
    details: Optional[dict[str, Any]] = None

    def __init__(
        self,
        message: Optional[str] = None,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        if message:
            self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details or {},
            }
        }


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Resource not found"


class ValidationError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "Validation failed"


class AuthenticationError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    message = "Authentication required"


class AuthorizationError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "Insufficient permissions"


class RateLimitError(AppError):
    status_code = 429
    code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "Resource conflict"


class BadRequestError(AppError):
    status_code = 400
    code = "BAD_REQUEST"
    message = "Bad request"
