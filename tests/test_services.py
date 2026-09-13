"""Phase-one placeholders fail loudly instead of returning fabricated predictions."""

import asyncio
from uuid import UUID

import pytest

from app.models.anomalies import AnomalyDetectionRequest
from app.models.cash_balance import CashBalanceForecastRequest
from app.models.recurring_charges import RecurringChargesRequest
from app.models.savings_goal import SavingsGoalPredictionRequest
from app.services import (
    AnomalyDetectionService,
    CashBalanceForecastService,
    ModelNotReadyError,
    RecurringChargesForecastService,
    SavingsGoalPredictionService,
)

USER_ID = UUID("c1a3797d-b335-5a9d-98a1-402311f82c7a")
RESOURCE_ID = UUID("799bb0e5-b590-56b6-b30a-8f89538b65df")


@pytest.mark.parametrize(
    ("service", "prediction_request", "model_name"),
    [
        (
            CashBalanceForecastService(),
            CashBalanceForecastRequest(user_id=USER_ID, account_id=RESOURCE_ID),
            "forecast_cash_balance",
        ),
        (
            SavingsGoalPredictionService(),
            SavingsGoalPredictionRequest(user_id=USER_ID, goal_id=RESOURCE_ID),
            "predict_savings_goal",
        ),
        (
            RecurringChargesForecastService(),
            RecurringChargesRequest(user_id=USER_ID),
            "forecast_recurring_charges",
        ),
        (
            AnomalyDetectionService(),
            AnomalyDetectionRequest(user_id=USER_ID),
            "detect_transaction_anomalies",
        ),
    ],
)
def test_phase_one_services_are_explicit_placeholders(
    service: object,
    prediction_request: object,
    model_name: str,
) -> None:
    async def invoke() -> None:
        await service.predict(prediction_request)  # type: ignore[attr-defined]

    with pytest.raises(ModelNotReadyError) as raised:
        asyncio.run(invoke())

    assert raised.value.model_name == model_name
