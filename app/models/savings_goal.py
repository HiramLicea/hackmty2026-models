"""Contracts for future savings-goal predictions."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.common import (
    CommonPredictionRequest,
    CommonPredictionResponse,
    Confidence,
    StrictModel,
)


class SavingsGoalPredictionRequest(CommonPredictionRequest):
    goal_id: UUID
    simulations: int = Field(default=1_000, ge=100, le=100_000)


class SavingsGoalSummary(StrictModel):
    currency: str = Field(min_length=3, max_length=3)
    target_amount: float = Field(gt=0)
    current_amount: float = Field(ge=0)
    probability_of_success: Confidence
    expected_completion_date: date | None
    recommended_monthly_contribution: float = Field(ge=0)


class SavingsGoalPoint(StrictModel):
    date: date
    conservative: float
    expected: float
    optimistic: float

    @model_validator(mode="after")
    def quantiles_are_ordered(self) -> "SavingsGoalPoint":
        if not self.conservative <= self.expected <= self.optimistic:
            raise ValueError("scenario values must be ordered")
        return self


class SavingsGoalPredictionResponse(CommonPredictionResponse[SavingsGoalSummary, SavingsGoalPoint]):
    model_name: Literal["predict_savings_goal"] = "predict_savings_goal"
    summary: SavingsGoalSummary
    series: list[SavingsGoalPoint]
