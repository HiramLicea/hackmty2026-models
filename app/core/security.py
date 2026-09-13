"""Reusable server-to-server authentication dependency."""

import secrets
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.errors import InvalidApiKeyError, ServiceNotConfiguredError

bearer_scheme = HTTPBearer(auto_error=False)


async def require_mcp_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Require the shared MCP bearer credential without exposing it to logs."""
    configured_secret = settings.mcp_api_key
    if configured_secret is None or not configured_secret.get_secret_value():
        raise ServiceNotConfiguredError("MCP_API_KEY is required for protected operations")

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise InvalidApiKeyError

    if not secrets.compare_digest(
        credentials.credentials,
        configured_secret.get_secret_value(),
    ):
        raise InvalidApiKeyError
