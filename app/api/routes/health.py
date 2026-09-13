"""Public liveness and sanitized readiness endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
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

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Minimal response that does not disclose infrastructure details."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    service: Literal["hackmty2026-models"] = "hackmty2026-models"
    version: str = __version__


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report process liveness without requiring Supabase."""
    return HealthResponse()


@router.get("/ready", response_model=ReadinessResponse)
async def ready(
    settings: Annotated[Settings, Depends(get_settings)],
    artifacts: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> ReadinessResponse:
    """Report configuration and file availability without testing external connectivity."""
    artifact_status = artifacts.inspect()
    key = settings.supabase_service_role_key
    configuration = ReadinessConfiguration(
        mcp_api_key=bool(settings.mcp_api_key and settings.mcp_api_key.get_secret_value()),
        supabase=bool(settings.supabase_url and key and key.get_secret_value()),
    )
    artifact_checks = ReadinessArtifacts(
        manifest=artifact_status.manifest_valid,
        models={name: artifact_status.models.get(name, False) for name in MODEL_NAMES},
    )
    is_ready = configuration.mcp_api_key and configuration.supabase and artifact_status.ready
    return ReadinessResponse(
        ready=is_ready,
        status="ready" if is_ready else "not_ready",
        checks=ReadinessChecks(
            configuration=configuration,
            artifacts=artifact_checks,
        ),
    )
