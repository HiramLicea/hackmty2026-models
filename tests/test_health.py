"""Tests for public liveness and stateless readiness."""

import asyncio
import socket
from typing import Any, cast

from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_artifact_store
from app.artifacts.manifest import MODEL_NAMES
from app.artifacts.store import ArtifactStatus, ArtifactStore
from app.main import app


def test_health() -> None:
    async def request_health() -> tuple[int, dict[str, str]]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        return response.status_code, response.json()

    status_code, body = asyncio.run(request_health())
    assert status_code == 200
    assert body == {
        "status": "ok",
        "service": "hackmty2026-models",
        "version": "0.1.0",
    }


def test_ready_is_sanitized_false_and_makes_no_connection(
    configured_app: None,
    monkeypatch: object,
) -> None:
    del configured_app

    def fail_connection(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("readiness attempted an outbound connection")

    monkeypatch.setattr(socket, "create_connection", fail_connection)  # type: ignore[attr-defined]

    async def request_ready() -> tuple[int, dict[str, object], str]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/ready")
        return response.status_code, response.json(), response.text

    status_code, body, raw_body = asyncio.run(request_ready())
    assert status_code == 503
    assert body["ready"] is False
    assert body["status"] == "not_ready"
    assert body["checks"]["configuration"]["inference_api_key"] is True  # type: ignore[index]
    assert "test-only-inference-key" not in raw_body
    assert "manifest.json" not in raw_body


def test_ready_checks_that_verified_artifacts_can_be_loaded(configured_app: None) -> None:
    del configured_app

    class LoadableStore:
        loadability_checked = False

        def inspect(self) -> ArtifactStatus:
            return ArtifactStatus(manifest_valid=True, models=dict.fromkeys(MODEL_NAMES, True))

        def check_loadable(self) -> dict[str, bool]:
            self.loadability_checked = True
            return dict.fromkeys(MODEL_NAMES, True)

    store = LoadableStore()
    app.dependency_overrides[get_artifact_store] = lambda: store

    async def request_ready() -> dict[str, object]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/ready")
        assert response.status_code == 200
        return cast(dict[str, object], response.json())

    body = asyncio.run(request_ready())
    assert store.loadability_checked is True
    assert body["ready"] is True
    checks = cast(dict[str, Any], body["checks"])
    assert all(checks["artifacts"]["loadable"].values())


def test_ready_is_http_200_with_real_trained_artifacts(
    configured_app: None, trained_artifact_store: ArtifactStore
) -> None:
    del configured_app
    app.dependency_overrides[get_artifact_store] = lambda: trained_artifact_store

    async def request_ready() -> tuple[int, dict[str, object]]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/ready")
        return response.status_code, response.json()

    status_code, body = asyncio.run(request_ready())
    assert status_code == 200
    assert body["ready"] is True
