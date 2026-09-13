"""Shared isolated configuration for API tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.artifacts.store import ArtifactStore
from app.core.config import Settings, get_settings
from app.main import app
from scripts.train_all import train_all

TEST_API_KEY = "test-only-inference-key"


@pytest.fixture(scope="session")
def trained_artifact_store(tmp_path_factory: pytest.TempPathFactory) -> ArtifactStore:
    root = tmp_path_factory.mktemp("trained")
    artifacts = root / "artifacts"
    train_all(2026, 8, 6, root / "data", artifacts)
    return ArtifactStore(artifacts, artifacts / "manifest.json")


@pytest.fixture
def configured_app(tmp_path: Path) -> Iterator[None]:
    """Configure authentication while keeping artifacts offline."""
    settings = Settings(
        _env_file=None,
        app_env="test",
        inference_api_key=TEST_API_KEY,
        model_artifact_dir=tmp_path / "artifacts",
        model_manifest_path=tmp_path / "artifacts" / "manifest.json",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        yield
    finally:
        app.dependency_overrides.clear()
