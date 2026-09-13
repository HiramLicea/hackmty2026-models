"""Stable, sanitized HTTP error translation."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse

from app.artifacts.store import ArtifactNotReadyError, InvalidManifestError
from app.core.errors import (
    InvalidApiKeyError,
    ModelVersionMismatchError,
    ServiceNotConfiguredError,
)
from app.services.base import ModelNotReadyError

logger = logging.getLogger("hackmty2026_models.api")


@dataclass(frozen=True)
class ErrorSpec:
    status_code: int
    code: str
    message: str


ERROR_SPECS: dict[type[Exception], ErrorSpec] = {
    InvalidApiKeyError: ErrorSpec(401, "INVALID_API_KEY", "Missing or invalid API key"),
    ServiceNotConfiguredError: ErrorSpec(
        503, "SERVICE_NOT_CONFIGURED", "Protected service configuration is incomplete"
    ),
    ModelVersionMismatchError: ErrorSpec(
        409, "MODEL_VERSION_MISMATCH", "Model artifact version is incompatible"
    ),
    ModelNotReadyError: ErrorSpec(503, "MODEL_NOT_READY", "Requested model is not ready"),
    ArtifactNotReadyError: ErrorSpec(503, "MODEL_NOT_READY", "Requested model is not ready"),
    InvalidManifestError: ErrorSpec(503, "MODEL_NOT_READY", "Requested model is not ready"),
}


def request_id(request: Request) -> str:
    """Return the server-generated identifier attached by middleware."""
    return str(getattr(request.state, "request_id", "unavailable"))


def error_response(request: Request, spec: ErrorSpec) -> JSONResponse:
    """Build the common error envelope without exception internals."""
    headers = {"WWW-Authenticate": "Bearer"} if spec.status_code == 401 else None
    return JSONResponse(
        status_code=spec.status_code,
        headers=headers,
        content={
            "error": {
                "code": spec.code,
                "message": spec.message,
                "request_id": request_id(request),
            }
        },
    )


async def known_error_handler(request: Request, error: Exception) -> JSONResponse:
    """Translate a known domain error to its stable public representation."""
    return error_response(request, ERROR_SPECS[type(error)])


async def validation_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    """Avoid echoing request values while preserving a stable validation response."""
    del error
    return error_response(
        request,
        ErrorSpec(422, "VALIDATION_ERROR", "Request validation failed"),
    )


async def internal_error_handler(request: Request, error: Exception) -> JSONResponse:
    """Log an opaque diagnostic and never return a stack trace to callers."""
    logger.exception("unhandled request error request_id=%s", request_id(request), exc_info=error)
    return error_response(request, ErrorSpec(500, "INTERNAL_ERROR", "Internal server error"))


ExceptionHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]
