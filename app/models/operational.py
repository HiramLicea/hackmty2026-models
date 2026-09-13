"""Sanitized health, readiness, and error response contracts."""

from typing import Literal

from app.models.common import ModelName, StrictModel


class ReadinessConfiguration(StrictModel):
    mcp_api_key: bool
    supabase: bool


class ReadinessArtifacts(StrictModel):
    manifest: bool
    models: dict[ModelName, bool]


class ReadinessChecks(StrictModel):
    configuration: ReadinessConfiguration
    artifacts: ReadinessArtifacts


class ReadinessResponse(StrictModel):
    ready: bool
    status: Literal["ready", "not_ready"]
    checks: ReadinessChecks


class ErrorDetail(StrictModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(StrictModel):
    error: ErrorDetail
