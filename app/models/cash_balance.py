"""Contracts for future cash-balance forecasts."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.common import CommonPredictionRequest, CommonPredictionResponse, StrictModel


class CashBalanceForecastRequest(CommonPredictionRequest):
    """Request a forecast for one account owned by the verified user."""

    account_id: UUID
    horizon_days: Literal[7, 15, 30] = 30


class CashBalanceSummary(StrictModel):
    currency: str = Field(min_length=3, max_length=3)
    starting_balance: float
    expected_ending_balance: float
    expected_minimum_balance: float
    scheduled_income: float = Field(ge=0)
    scheduled_expenses: float = Field(ge=0)


class CashBalancePoint(StrictModel):
    date: date
    expected: float
    lower_bound: float
    upper_bound: float

    @model_validator(mode="after")
    def bounds_contain_expected(self) -> "CashBalancePoint":
        if not self.lower_bound <= self.expected <= self.upper_bound:
            raise ValueError("expected must be within lower_bound and upper_bound")
        return self


class CashBalanceForecastResponse(CommonPredictionResponse[CashBalanceSummary, CashBalancePoint]):
    model_name: Literal["forecast_cash_balance"] = "forecast_cash_balance"
    summary: CashBalanceSummary
    series: list[CashBalancePoint]
