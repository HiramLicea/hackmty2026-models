"""Contracts for stateless recurring-charge forecasts."""

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from app.models.common import (
    CommonPredictionRequest,
    CommonPredictionResponse,
    Confidence,
    StrictModel,
)
from app.models.inputs import NormalizedTransaction
from app.preprocessing import (
    ensure_datetimes_chronological,
    ensure_history_not_after,
    ensure_record_limit,
)
from app.preprocessing.records import MAX_RECORDS_PER_REQUEST


class RecurringChargesRequest(CommonPredictionRequest):
    forecast_days: int = Field(default=30, ge=7, le=365)
    transactions: list[NormalizedTransaction] = Field(
        default_factory=list,
        max_length=MAX_RECORDS_PER_REQUEST,
    )

    @model_validator(mode="after")
    def validate_records(self) -> "RecurringChargesRequest":
        ensure_record_limit(self.transactions)
        timestamps = [record.occurred_at for record in self.transactions]
        ensure_datetimes_chronological(timestamps)
        ensure_history_not_after(timestamps, self.as_of)
        return self


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
    CommonPredictionResponse[RecurringChargesSummary, RecurringChargePoint, RecurringChargePoint]
):
    model_name: Literal["forecast_recurring_charges"] = "forecast_recurring_charges"
    summary: RecurringChargesSummary
    series: list[RecurringChargePoint] = Field(default_factory=list)
    items: list[RecurringChargePoint]
