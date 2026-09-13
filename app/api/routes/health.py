"""Public liveness and sanitized readiness endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict

from app import __version__
from app.api.dependencies import get_artifact_store
from app.artifacts.manifest import MODEL_NAMES
from app.artifacts.store import ArtifactStore
from app.core.config import Settings, get_settings
from app.models.operational import (
    ReadinessArtifacts,
    ReadinessChecks,
    ReadinessConfiguration,
    ReadinessResponse,
)
from app.services import INFERENCE_IMPLEMENTED

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Minimal response that does not disclose infrastructure details."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    service: Literal["hackmty2026-models"] = "hackmty2026-models"
    version: str = __version__


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report process liveness without loading artifacts or calling external systems."""
    return HealthResponse()


@router.get("/ready", response_model=ReadinessResponse)
async def ready(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    artifacts: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> ReadinessResponse:
    """Report configuration and file availability without testing external connectivity."""
    artifact_status = artifacts.inspect()
    configuration = ReadinessConfiguration(
        inference_api_key=bool(
            settings.inference_api_key and settings.inference_api_key.get_secret_value()
        ),
    )
    loadable = (
        artifacts.check_loadable() if artifact_status.ready else dict.fromkeys(MODEL_NAMES, False)
    )
    artifact_checks = ReadinessArtifacts(
        manifest=artifact_status.manifest_valid,
        models={name: artifact_status.models.get(name, False) for name in MODEL_NAMES},
        loadable={name: loadable.get(name, False) for name in MODEL_NAMES},
    )
    is_ready = (
        configuration.inference_api_key
        and artifact_status.ready
        and all(loadable.values())
        and INFERENCE_IMPLEMENTED
    )
    response.status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        ready=is_ready,
        status="ready" if is_ready else "not_ready",
        checks=ReadinessChecks(
            configuration=configuration,
            artifacts=artifact_checks,
            inference_implemented=INFERENCE_IMPLEMENTED,
        ),
    )
