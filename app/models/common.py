"""Shared Pydantic prediction contracts."""

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
SummaryT = TypeVar("SummaryT", bound=BaseModel)
SeriesT = TypeVar("SeriesT", bound=BaseModel)
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
    """Base contract that rejects accidental or unversioned fields."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class VisualizationType(StrEnum):
    """Presentation-neutral hints understood by upstream callers."""

    AREA_CHART = "area_chart"
    HEATMAP_CHART = "heatmap_chart"


class VisualizationHint(StrictModel):
    """A semantic visualization suggestion, never an A2UI component tree."""

    type: VisualizationType
    x_field: str | None = None
    y_fields: list[str] = Field(default_factory=list)


class PredictionDriver(StrictModel):
    """One explainable factor contributing to a prediction."""

    name: str = Field(min_length=1, max_length=160)
    impact: float | None = None
    description: str = Field(min_length=1, max_length=500)
    details: dict[str, JsonValue] = Field(default_factory=dict)


class CommonPredictionRequest(StrictModel):
    """Fields supplied to every prediction service by a trusted internal caller."""

    user_id: UUID
    as_of: date | None = None


class CommonPredictionResponse(StrictModel, Generic[SummaryT, SeriesT]):
    """Stable metadata and extension points shared by all predictions."""

    model_name: ModelName
    model_version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
    user_id: UUID
    generated_at: datetime = Field(default_factory=utc_now)
    trained_until: datetime | None
    confidence: Confidence
    summary: SummaryT
    series: list[SeriesT]
    drivers: list[PredictionDriver] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    visualization_hint: VisualizationHint

    @field_validator("generated_at", "trained_until")
    @classmethod
    def require_aware_datetime(cls, value: datetime | None) -> datetime | None:
        """Reject ambiguous datetimes and normalize accepted timestamps to UTC."""
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must include a timezone")
        return value.astimezone(UTC)
