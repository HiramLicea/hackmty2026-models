"""Shared isolated configuration for API tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.config import Settings, get_settings
from app.main import app

TEST_API_KEY = "test-only-mcp-key"


@pytest.fixture
def configured_app(tmp_path: Path) -> Iterator[None]:
    """Configure authentication while keeping Supabase and artifacts offline."""
    settings = Settings(
        _env_file=None,
        app_env="test",
        mcp_api_key=TEST_API_KEY,
        model_artifact_dir=tmp_path / "artifacts",
        model_manifest_path=tmp_path / "artifacts" / "manifest.json",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        yield
    finally:
        app.dependency_overrides.clear()
