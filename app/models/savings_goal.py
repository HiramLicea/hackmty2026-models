"""Contracts for stateless savings-goal predictions."""

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from app.models.common import (
    CommonPredictionRequest,
    CommonPredictionResponse,
    Confidence,
    StrictModel,
)
from app.models.inputs import NormalizedTransaction, SavingsContribution, SavingsGoalInput
from app.preprocessing import (
    ensure_datetimes_chronological,
    ensure_history_not_after,
    ensure_record_limit,
)
from app.preprocessing.records import MAX_RECORDS_PER_REQUEST


class SavingsGoalPredictionRequest(CommonPredictionRequest):
    goal: SavingsGoalInput
    contributions: list[SavingsContribution] = Field(
        default_factory=list,
        max_length=MAX_RECORDS_PER_REQUEST,
    )
    cash_flow_history: list[NormalizedTransaction] = Field(
        default_factory=list,
        max_length=MAX_RECORDS_PER_REQUEST,
    )

    @model_validator(mode="after")
    def validate_records(self) -> "SavingsGoalPredictionRequest":
        ensure_record_limit(self.contributions, self.cash_flow_history)
        contribution_times = [record.contributed_at for record in self.contributions]
        cash_flow_times = [record.occurred_at for record in self.cash_flow_history]
        ensure_datetimes_chronological(contribution_times)
        ensure_datetimes_chronological(cash_flow_times)
        ensure_history_not_after(contribution_times, self.as_of)
        ensure_history_not_after(cash_flow_times, self.as_of)
        if self.goal.target_date < self.as_of.date():
            raise ValueError("goal target_date cannot be before as_of")
        return self


class SavingsGoalSummary(StrictModel):
    currency: str = Field(min_length=3, max_length=3)
    target_amount: float = Field(gt=0)
    current_amount: float = Field(ge=0)
    probability_of_success: Confidence
    conservative_completion_date: date | None
    expected_completion_date: date | None
    optimistic_completion_date: date | None
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


class SavingsGoalPredictionResponse(
    CommonPredictionResponse[SavingsGoalSummary, SavingsGoalPoint, SavingsGoalPoint]
):
    model_name: Literal["predict_savings_goal"] = "predict_savings_goal"
    summary: SavingsGoalSummary
    series: list[SavingsGoalPoint]
