from __future__ import annotations

from typing import Optional, Dict, List


class VectorlessError(Exception):
    """Base exception for all Vectorless SDK errors."""

    def __init__(
        self,
        message: str,
        status: int,
        code: str,
        request_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.request_id = request_id


class AuthenticationError(VectorlessError):
    """401 — Missing or invalid API key."""

    def __init__(self, message: str, request_id: Optional[str] = None) -> None:
        super().__init__(message, 401, "authentication_error", request_id)


class PermissionDeniedError(VectorlessError):
    """403 — Valid credentials but insufficient permissions."""

    def __init__(self, message: str, request_id: Optional[str] = None) -> None:
        super().__init__(message, 403, "permission_denied", request_id)


class NotFoundError(VectorlessError):
    """404 — Document or section not found."""

    def __init__(self, message: str, request_id: Optional[str] = None) -> None:
        super().__init__(message, 404, "not_found", request_id)


class ValidationError(VectorlessError):
    """400 — Invalid request parameters."""

    def __init__(
        self,
        message: str,
        field_errors: Optional[Dict[str, List[str]]] = None,
        request_id: Optional[str] = None,
    ) -> None:
        super().__init__(message, 400, "validation_error", request_id)
        self.field_errors = field_errors


class ConflictError(VectorlessError):
    """409 — Conflict (e.g. duplicate idempotency key)."""

    def __init__(self, message: str, request_id: Optional[str] = None) -> None:
        super().__init__(message, 409, "conflict", request_id)


class RateLimitError(VectorlessError):
    """429 — Rate limit exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[float] = None,
        request_id: Optional[str] = None,
    ) -> None:
        super().__init__(message, 429, "rate_limit_exceeded", request_id)
        self.retry_after = retry_after


class TimeoutError(VectorlessError):
    """408 / 504 — Request or gateway timeout."""

    def __init__(self, message: str, request_id: Optional[str] = None) -> None:
        super().__init__(message, 408, "timeout", request_id)


class ServerError(VectorlessError):
    """500+ — Internal server error."""

    def __init__(self, message: str, request_id: Optional[str] = None) -> None:
        super().__init__(message, 500, "server_error", request_id)


class DocumentFailedError(VectorlessError):
    """Document failed to process during ingestion."""

    def __init__(self, message: str, request_id: Optional[str] = None) -> None:
        super().__init__(message, 422, "document_failed", request_id)


class StreamError(VectorlessError):
    """Streaming connection was interrupted or reset."""

    def __init__(self, message: str, request_id: Optional[str] = None) -> None:
        super().__init__(message, 0, "stream_error", request_id)
