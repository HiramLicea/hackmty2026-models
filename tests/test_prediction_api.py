"""Authentication, routing, errors, schemas, and stateless ASGI integration."""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.api.dependencies import (
    get_anomaly_detection_service,
    get_artifact_store,
    get_cash_balance_service,
    get_recurring_charges_service,
    get_savings_goal_service,
)
from app.artifacts.store import ArtifactStore
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

REQUEST_ID = UUID("25c00a42-822b-49a7-9c50-0fe913242977")
TEST_API_KEY = "test-only-inference-key"
AS_OF = datetime(2026, 9, 13, tzinfo=UTC)
GENERATED_AT = datetime(2026, 9, 13, 0, 0, 1, tzinfo=UTC)


async def post(
    path: str,
    body: dict[str, Any],
    token: str | None,
    scheme: str = "Bearer",
) -> tuple[int, dict[str, Any]]:
    headers = {"Authorization": f"{scheme} {token}"} if token is not None else {}
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(path, json=body, headers=headers)
    return response.status_code, response.json()


def common_request() -> dict[str, Any]:
    return {"request_id": str(REQUEST_ID), "as_of": AS_OF.isoformat(), "currency": "MXN"}


def cash_request() -> dict[str, Any]:
    return common_request() | {
        "current_balance": 15420.75,
        "horizon_days": 30,
        "transactions": [],
        "scheduled_cash_flows": [],
    }


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


def test_prediction_with_non_bearer_scheme_is_401(configured_app: None) -> None:
    del configured_app
    status, body = asyncio.run(
        post("/v1/predictions/cash-balance", cash_request(), TEST_API_KEY, scheme="Basic")
    )
    assert status == 401
    assert body["error"]["code"] == "INVALID_API_KEY"


def test_invalid_request_id_is_stable_422(configured_app: None) -> None:
    del configured_app
    body = cash_request() | {"request_id": "not-a-uuid"}
    status, response = asyncio.run(post("/v1/predictions/cash-balance", body, TEST_API_KEY))
    assert status == 422
    assert response["error"]["code"] == "VALIDATION_ERROR"
    assert "not-a-uuid" not in str(response)


def test_missing_model_is_stable_503(configured_app: None) -> None:
    del configured_app
    status, body = asyncio.run(post("/v1/predictions/cash-balance", cash_request(), TEST_API_KEY))
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
        "request_id": REQUEST_ID,
        "model_version": "0.1.0",
        "trained_until": AS_OF,
        "generated_at": GENERATED_AT,
        "confidence": 0.8,
    }
    recurring_item = RecurringChargePoint(
        normalized_merchant="Example service",
        next_expected_date=date(2026, 10, 1),
        expected_amount=199,
        interval_days=30,
        confidence=0.9,
        observations=4,
    )
    anomaly_item = AnomalyPoint(
        transaction_id="txn-candidate-1",
        occurred_at=AS_OF,
        signed_amount=-250,
        anomaly_score=0.9,
        severity=AnomalySeverity.HIGH,
        reasons=["unusual amount for category"],
    )
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
            ),
        ),
        (
            "/v1/predictions/savings-goal",
            common_request()
            | {
                "goal": {
                    "goal_id": "goal-1",
                    "target_amount": 5000,
                    "target_date": "2027-03-01",
                    "current_saved_amount": 1000,
                },
                "contributions": [],
                "cash_flow_history": [],
            },
            get_savings_goal_service,
            SavingsGoalPredictionResponse(
                **common,
                summary=SavingsGoalSummary(
                    currency="MXN",
                    target_amount=5000,
                    current_amount=1000,
                    probability_of_success=0.7,
                    conservative_completion_date=date(2027, 2, 1),
                    expected_completion_date=date(2027, 1, 1),
                    optimistic_completion_date=date(2026, 12, 1),
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
            ),
        ),
        (
            "/v1/predictions/recurring-charges",
            common_request() | {"forecast_days": 30, "transactions": []},
            get_recurring_charges_service,
            RecurringChargesResponse(
                **common,
                summary=RecurringChargesSummary(
                    currency="MXN", patterns_detected=1, expected_total=199
                ),
                items=[recurring_item],
            ),
        ),
        (
            "/v1/predictions/anomalies",
            common_request() | {"historical_transactions": [], "candidate_transactions": []},
            get_anomaly_detection_service,
            AnomalyDetectionResponse(
                **common,
                summary=AnomalySummary(transactions_analyzed=20, anomalies_detected=1),
                items=[anomaly_item],
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
    assert body["request_id"] == str(REQUEST_ID)
    assert body["model_version"] == "0.1.0"
    assert "user_id" not in body
    assert "visualization_hint" not in body


def test_all_prediction_contracts_are_in_openapi_without_identity_or_ui_fields() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    assert {
        "/v1/predictions/cash-balance",
        "/v1/predictions/savings-goal",
        "/v1/predictions/recurring-charges",
        "/v1/predictions/anomalies",
    }.issubset(paths)
    serialized = str(schema)
    assert "user_id" not in serialized
    assert "visualization_hint" not in serialized
    assert "a2ui" not in serialized.lower()


def test_success_responses_contain_no_personal_identity_fields() -> None:
    forbidden = {"user_id", "email", "full_name", "session_token", "access_token"}
    for _, _, _, response in response_cases():
        assert isinstance(response, BaseModel)
        serialized = str(response.model_dump(mode="json"))
        assert all(field not in serialized for field in forbidden)


def test_logs_do_not_contain_token_or_financial_body(
    configured_app: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    del configured_app
    private_marker = "private-person-or-transaction-value"
    body = cash_request() | {"email": private_marker, "amount": 987654.32}
    with caplog.at_level(logging.INFO):
        asyncio.run(post("/v1/predictions/cash-balance", body, TEST_API_KEY))
    assert TEST_API_KEY not in caplog.text
    assert private_marker not in caplog.text
    assert "987654.32" not in caplog.text


def test_async_http_consumer_reaches_stateless_fastapi(configured_app: None) -> None:
    del configured_app
    request = common_request() | {
        "historical_transactions": [],
        "candidate_transactions": [],
    }
    status, body = asyncio.run(post("/v1/predictions/anomalies", request, TEST_API_KEY))
    assert status == 503
    assert body["error"]["code"] == "MODEL_NOT_READY"


def test_all_http_predictions_are_200_with_real_artifacts(
    configured_app: None, trained_artifact_store: ArtifactStore
) -> None:
    del configured_app
    app.dependency_overrides[get_artifact_store] = lambda: trained_artifact_store
    requests = [
        ("/v1/predictions/cash-balance", cash_request()),
        (
            "/v1/predictions/savings-goal",
            common_request()
            | {
                "goal": {
                    "goal_id": "goal-1",
                    "target_amount": 5000,
                    "target_date": "2027-03-01",
                    "current_saved_amount": 1000,
                },
                "contributions": [],
                "cash_flow_history": [],
            },
        ),
        (
            "/v1/predictions/recurring-charges",
            common_request() | {"forecast_days": 30, "transactions": []},
        ),
        (
            "/v1/predictions/anomalies",
            common_request() | {"historical_transactions": [], "candidate_transactions": []},
        ),
    ]
    for path, request in requests:
        status, body = asyncio.run(post(path, request, TEST_API_KEY))
        assert status == 200
        assert body["model_version"] == "0.1.0"
        assert body["trained_until"] == "2026-08-31T23:59:59Z"
