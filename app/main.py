"""FastAPI application factory and Vercel entrypoint."""

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app import __version__
from app.api.errors import (
    ERROR_SPECS,
    internal_error_handler,
    known_error_handler,
    validation_error_handler,
)
from app.api.routes.health import router as health_router
from app.api.routes.predictions import router as predictions_router
from app.core.config import get_settings

logger = logging.getLogger("hackmty2026_models.requests")


def create_app() -> FastAPI:
    """Create the service application without connecting to external systems."""
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    logging.basicConfig(level=settings.log_level)

    @application.middleware("http")
    async def request_observability(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request.state.request_id = str(uuid4())
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request.state.request_id
            return response
        finally:
            logger.info(
                "request completed request_id=%s method=%s path=%s status=%s",
                request.state.request_id,
                request.method,
                request.url.path,
                status_code,
            )

    for error_type in ERROR_SPECS:
        application.add_exception_handler(error_type, known_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(Exception, internal_error_handler)
    application.include_router(health_router)
    application.include_router(predictions_router)
    return application


app = create_app()
