"""Authenticated HTTP adapters for the four prediction contracts."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_anomaly_detection_service,
    get_cash_balance_service,
    get_recurring_charges_service,
    get_savings_goal_service,
)
from app.core.security import require_mcp_api_key
from app.models.anomalies import AnomalyDetectionRequest, AnomalyDetectionResponse
from app.models.cash_balance import CashBalanceForecastRequest, CashBalanceForecastResponse
from app.models.operational import ErrorResponse
from app.models.recurring_charges import RecurringChargesRequest, RecurringChargesResponse
from app.models.savings_goal import SavingsGoalPredictionRequest, SavingsGoalPredictionResponse
from app.services import (
    AnomalyDetectionService,
    CashBalanceForecastService,
    RecurringChargesForecastService,
    SavingsGoalPredictionService,
)

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}

router = APIRouter(
    prefix="/v1/predictions",
    tags=["predictions"],
    dependencies=[Depends(require_mcp_api_key)],
)


@router.post(
    "/cash-balance",
    response_model=CashBalanceForecastResponse,
    responses=ERROR_RESPONSES,
)
async def forecast_cash_balance(
    request: CashBalanceForecastRequest,
    service: Annotated[CashBalanceForecastService, Depends(get_cash_balance_service)],
) -> CashBalanceForecastResponse:
    return await service.predict(request)


@router.post(
    "/savings-goal",
    response_model=SavingsGoalPredictionResponse,
    responses=ERROR_RESPONSES,
)
async def predict_savings_goal(
    request: SavingsGoalPredictionRequest,
    service: Annotated[SavingsGoalPredictionService, Depends(get_savings_goal_service)],
) -> SavingsGoalPredictionResponse:
    return await service.predict(request)


@router.post(
    "/recurring-charges",
    response_model=RecurringChargesResponse,
    responses=ERROR_RESPONSES,
)
async def forecast_recurring_charges(
    request: RecurringChargesRequest,
    service: Annotated[
        RecurringChargesForecastService,
        Depends(get_recurring_charges_service),
    ],
) -> RecurringChargesResponse:
    return await service.predict(request)


@router.post(
    "/anomalies",
    response_model=AnomalyDetectionResponse,
    responses=ERROR_RESPONSES,
)
async def detect_transaction_anomalies(
    request: AnomalyDetectionRequest,
    service: Annotated[AnomalyDetectionService, Depends(get_anomaly_detection_service)],
) -> AnomalyDetectionResponse:
    return await service.predict(request)
