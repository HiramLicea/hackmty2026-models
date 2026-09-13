"""Contracts for explainable transaction-anomaly detection."""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from app.models.common import CommonPredictionRequest, CommonPredictionResponse, StrictModel


class AnomalySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnomalyDetectionRequest(CommonPredictionRequest):
    account_id: UUID | None = None
    lookback_days: int = Field(default=180, ge=30, le=730)
    contamination: float = Field(default=0.02, gt=0, le=0.5)


class AnomalySummary(StrictModel):
    transactions_analyzed: int = Field(ge=0)
    anomalies_detected: int = Field(ge=0)


class AnomalyPoint(StrictModel):
    transaction_id: UUID
    occurred_at: AwareDatetime
    signed_amount: float
    anomaly_score: float
    severity: AnomalySeverity
    reasons: list[str] = Field(min_length=1)


class AnomalyDetectionResponse(CommonPredictionResponse[AnomalySummary, AnomalyPoint]):
    model_name: Literal["detect_transaction_anomalies"] = "detect_transaction_anomalies"
    summary: AnomalySummary
    series: list[AnomalyPoint]
