"""Authentication, routing, errors, schemas, and MCP-style ASGI integration."""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import (
    get_anomaly_detection_service,
    get_cash_balance_service,
    get_recurring_charges_service,
    get_savings_goal_service,
)
from app.main import app
from app.models.anomalies import (
    AnomalyDetectionResponse,
    AnomalyPoint,
    AnomalySeverity,
    AnomalySummary,
)
from app.models.cash_balance import (
    CashBalanceForecastResponse,
    CashBalancePoint,
    CashBalanceSummary,
)
from app.models.common import VisualizationHint
from app.models.recurring_charges import (
    RecurringChargePoint,
    RecurringChargesResponse,
    RecurringChargesSummary,
)
from app.models.savings_goal import (
    SavingsGoalPoint,
    SavingsGoalPredictionResponse,
    SavingsGoalSummary,
)
USER_ID = UUID("c1a3797d-b335-5a9d-98a1-402311f82c7a")
RESOURCE_ID = UUID("799bb0e5-b590-56b6-b30a-8f89538b65df")
TEST_API_KEY = "test-only-mcp-key"
GENERATED_AT = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
TRAINED_UNTIL = datetime(2026, 9, 12, 23, 59, tzinfo=UTC)


async def post(path: str, body: dict[str, Any], token: str | None) -> tuple[int, dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(path, json=body, headers=headers)
    return response.status_code, response.json()


def cash_request() -> dict[str, str]:
    return {"user_id": str(USER_ID), "account_id": str(RESOURCE_ID)}


def test_prediction_without_token_is_401(configured_app: None) -> None:
    del configured_app
    status, body = asyncio.run(post("/v1/predictions/cash-balance", cash_request(), None))
    assert status == 401
    assert body["error"]["code"] == "INVALID_API_KEY"
    assert body["error"]["request_id"]


def test_prediction_with_wrong_token_is_401(configured_app: None) -> None:
    del configured_app
    status, body = asyncio.run(post("/v1/predictions/cash-balance", cash_request(), "wrong"))
    assert status == 401
    assert body["error"]["code"] == "INVALID_API_KEY"


def test_invalid_uuid_is_stable_422(configured_app: None) -> None:
    del configured_app
    body = {"user_id": "not-a-uuid", "account_id": str(RESOURCE_ID)}
    status, response = asyncio.run(post("/v1/predictions/cash-balance", body, TEST_API_KEY))
    assert status == 422
    assert response["error"]["code"] == "VALIDATION_ERROR"
    assert "not-a-uuid" not in str(response)


def test_missing_model_is_stable_503(configured_app: None) -> None:
    del configured_app
    status, body = asyncio.run(
        post("/v1/predictions/cash-balance", cash_request(), TEST_API_KEY)
    )
    assert status == 503
    assert body["error"]["code"] == "MODEL_NOT_READY"


class StubService:
    def __init__(self, response: object) -> None:
        self.response = response
        self.called = False

    async def predict(self, request: object) -> object:
        del request
        self.called = True
        return self.response


def response_cases() -> list[tuple[str, dict[str, Any], Callable[..., object], object]]:
    common = {
        "model_version": "0.1.0",
        "user_id": USER_ID,
        "generated_at": GENERATED_AT,
        "trained_until": TRAINED_UNTIL,
        "confidence": 0.8,
    }
    return [
        (
            "/v1/predictions/cash-balance",
            cash_request(),
            get_cash_balance_service,
            CashBalanceForecastResponse(
                **common,
                summary=CashBalanceSummary(
                    currency="MXN",
                    starting_balance=1000,
                    expected_ending_balance=1200,
                    expected_minimum_balance=900,
                    scheduled_income=500,
                    scheduled_expenses=300,
                ),
                series=[
                    CashBalancePoint(
                        date=date(2026, 9, 14),
                        expected=1050,
                        lower_bound=950,
                        upper_bound=1150,
                    )
                ],
                visualization_hint=VisualizationHint(type="area_chart"),
            ),
        ),
        (
            "/v1/predictions/savings-goal",
            {"user_id": str(USER_ID), "goal_id": str(RESOURCE_ID)},
            get_savings_goal_service,
            SavingsGoalPredictionResponse(
                **common,
                summary=SavingsGoalSummary(
                    currency="MXN",
                    target_amount=5000,
                    current_amount=1000,
                    probability_of_success=0.7,
                    expected_completion_date=date(2027, 1, 1),
                    recommended_monthly_contribution=800,
                ),
                series=[
                    SavingsGoalPoint(
                        date=date(2026, 10, 1),
                        conservative=1200,
                        expected=1400,
                        optimistic=1600,
                    )
                ],
                visualization_hint=VisualizationHint(type="area_chart"),
            ),
        ),
        (
            "/v1/predictions/recurring-charges",
            {"user_id": str(USER_ID)},
            get_recurring_charges_service,
            RecurringChargesResponse(
                **common,
                summary=RecurringChargesSummary(
                    currency="MXN", patterns_detected=1, expected_total=199
                ),
                series=[
                    RecurringChargePoint(
                        normalized_merchant="Example service",
                        next_expected_date=date(2026, 10, 1),
                        expected_amount=199,
                        interval_days=30,
                        confidence=0.9,
                        observations=4,
                    )
                ],
                visualization_hint=VisualizationHint(type="area_chart"),
            ),
        ),
        (
            "/v1/predictions/anomalies",
            {"user_id": str(USER_ID)},
            get_anomaly_detection_service,
            AnomalyDetectionResponse(
                **common,
                summary=AnomalySummary(transactions_analyzed=20, anomalies_detected=1),
                series=[
                    AnomalyPoint(
                        transaction_id=RESOURCE_ID,
                        occurred_at=GENERATED_AT,
                        signed_amount=-250,
                        anomaly_score=0.9,
                        severity=AnomalySeverity.HIGH,
                        reasons=["sanitized example"],
                    )
                ],
                visualization_hint=VisualizationHint(type="heatmap_chart"),
            ),
        ),
    ]


@pytest.mark.parametrize(("path", "request_body", "dependency", "expected"), response_cases())
def test_authenticated_routes_reach_service_and_validate_response(
    configured_app: None,
    path: str,
    request_body: dict[str, Any],
    dependency: Callable[..., object],
    expected: object,
) -> None:
    del configured_app
    stub = StubService(expected)
    app.dependency_overrides[dependency] = lambda: stub
    status, body = asyncio.run(post(path, request_body, TEST_API_KEY))
    assert status == 200
    assert stub.called is True
    assert body["user_id"] == str(USER_ID)
    assert body["model_version"] == "0.1.0"


def test_all_prediction_routes_are_in_openapi() -> None:
    paths = app.openapi()["paths"]
    assert {
        "/v1/predictions/cash-balance",
        "/v1/predictions/savings-goal",
        "/v1/predictions/recurring-charges",
        "/v1/predictions/anomalies",
    }.issubset(paths)


def test_logs_do_not_contain_token_or_financial_body(
    configured_app: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    del configured_app
    token = "do-not-log-this-api-key"
    financial_marker = "private-transaction-description"
    body = cash_request() | {"description": financial_marker, "amount": 987654.32}
    with caplog.at_level(logging.INFO):
        asyncio.run(post("/v1/predictions/cash-balance", body, token))
    assert token not in caplog.text
    assert financial_marker not in caplog.text
    assert "987654.32" not in caplog.text


def test_mcp_async_client_integration_reaches_fastapi(configured_app: None) -> None:
    del configured_app
    status, body = asyncio.run(
        post("/v1/predictions/anomalies", {"user_id": str(USER_ID)}, TEST_API_KEY)
    )
    assert status == 503
    assert body["error"]["code"] == "MODEL_NOT_READY"
