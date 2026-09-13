"""Contracts for statistical recurring-charge forecasts."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.models.common import (
    CommonPredictionRequest,
    CommonPredictionResponse,
    Confidence,
    StrictModel,
)


class RecurringChargesRequest(CommonPredictionRequest):
    account_id: UUID | None = None
    lookback_days: int = Field(default=365, ge=90, le=730)
    forecast_days: int = Field(default=90, ge=7, le=365)


class RecurringChargesSummary(StrictModel):
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    patterns_detected: int = Field(ge=0)
    expected_total: float = Field(ge=0)


class RecurringChargePoint(StrictModel):
    normalized_merchant: str = Field(min_length=1, max_length=200)
    next_expected_date: date
    expected_amount: float = Field(gt=0)
    interval_days: float = Field(gt=0)
    confidence: Confidence
    observations: int = Field(ge=2)


class RecurringChargesResponse(
    CommonPredictionResponse[RecurringChargesSummary, RecurringChargePoint]
):
    model_name: Literal["forecast_recurring_charges"] = "forecast_recurring_charges"
    summary: RecurringChargesSummary
    series: list[RecurringChargePoint]
