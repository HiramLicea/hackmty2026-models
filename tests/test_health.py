"""Tests for public operational endpoints."""

import asyncio

from httpx import ASGITransport, AsyncClient

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


def test_ready_is_sanitized_and_false_without_artifacts(configured_app: None) -> None:
    del configured_app

    async def request_ready() -> tuple[int, dict[str, object], str]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/ready")
        return response.status_code, response.json(), response.text

    status_code, body, raw_body = asyncio.run(request_ready())

    assert status_code == 200
    assert body["ready"] is False
    assert body["status"] == "not_ready"
    assert "test-only-mcp-key" not in raw_body
    assert "manifest.json" not in raw_body
