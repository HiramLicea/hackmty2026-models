"""Contracts for stateless transaction-anomaly detection."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.models.common import (
    CommonPredictionRequest,
    CommonPredictionResponse,
    OpaqueId,
    StrictModel,
)
from app.models.inputs import NormalizedTransaction
from app.preprocessing import (
    ensure_datetimes_chronological,
    ensure_history_not_after,
    ensure_record_limit,
)
from app.preprocessing.records import MAX_RECORDS_PER_REQUEST


class AnomalySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnomalyDetectionRequest(CommonPredictionRequest):
    historical_transactions: list[NormalizedTransaction] = Field(
        default_factory=list,
        max_length=MAX_RECORDS_PER_REQUEST,
    )
    candidate_transactions: list[NormalizedTransaction] = Field(
        default_factory=list,
        max_length=MAX_RECORDS_PER_REQUEST,
    )

    @model_validator(mode="after")
    def validate_records(self) -> "AnomalyDetectionRequest":
        ensure_record_limit(self.historical_transactions, self.candidate_transactions)
        historical_times = [record.occurred_at for record in self.historical_transactions]
        candidate_times = [record.occurred_at for record in self.candidate_transactions]
        ensure_datetimes_chronological(historical_times)
        ensure_datetimes_chronological(candidate_times)
        ensure_history_not_after(historical_times, self.as_of)
        ensure_history_not_after(candidate_times, self.as_of)
        if historical_times and candidate_times and candidate_times[0] < historical_times[-1]:
            raise ValueError("candidate transactions cannot precede historical transactions")
        return self


class AnomalySummary(StrictModel):
    transactions_analyzed: int = Field(ge=0)
    anomalies_detected: int = Field(ge=0)


class AnomalyPoint(StrictModel):
    transaction_id: OpaqueId
    occurred_at: AwareDatetime
    signed_amount: float
    anomaly_score: float
    severity: AnomalySeverity
    reasons: list[str] = Field(min_length=1)

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class AnomalyDetectionResponse(
    CommonPredictionResponse[AnomalySummary, AnomalyPoint, AnomalyPoint]
):
    model_name: Literal["detect_transaction_anomalies"] = "detect_transaction_anomalies"
    summary: AnomalySummary
    series: list[AnomalyPoint] = Field(default_factory=list)
    items: list[AnomalyPoint]
