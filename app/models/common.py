"""Shared Pydantic inference contracts."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, field_validator

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
OpaqueId = Annotated[str, Field(min_length=1, max_length=200)]
ModelName = Literal[
    "forecast_cash_balance",
    "predict_savings_goal",
    "forecast_recurring_charges",
    "detect_transaction_anomalies",
]


def utc_now() -> datetime:
    """Return an aware UTC timestamp for response metadata."""
    return datetime.now(UTC)


class StrictModel(BaseModel):
    """Reject unknown fields, non-finite numbers, and accidental contract drift."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        allow_inf_nan=False,
        str_strip_whitespace=True,
    )


class PredictionDriver(StrictModel):
    """One explainable factor contributing to a prediction."""

    name: str = Field(min_length=1, max_length=160)
    impact: float | None = None
    description: str = Field(min_length=1, max_length=500)
    details: dict[str, JsonValue] = Field(default_factory=dict)


class CommonPredictionRequest(StrictModel):
    """Stateless request metadata supplied by a trusted HTTP consumer."""

    request_id: UUID
    as_of: AwareDatetime
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")

    @field_validator("as_of")
    @classmethod
    def normalize_as_of_to_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class CommonPredictionResponse[
    SummaryT: BaseModel,
    SeriesT: BaseModel,
    ItemT: BaseModel,
](StrictModel):
    """Stable, presentation-neutral response shared by all predictions."""

    request_id: UUID
    model_name: ModelName
    model_version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
    trained_until: AwareDatetime
    generated_at: AwareDatetime = Field(default_factory=utc_now)
    confidence: Confidence
    summary: SummaryT
    series: list[SeriesT]
    items: list[ItemT] = Field(default_factory=list)
    drivers: list[PredictionDriver] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("trained_until", "generated_at")
    @classmethod
    def normalize_response_datetimes_to_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)
