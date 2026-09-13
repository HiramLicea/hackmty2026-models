"""Contracts for stateless cash-balance forecasts."""

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from app.models.common import CommonPredictionRequest, CommonPredictionResponse, StrictModel
from app.models.inputs import NormalizedTransaction, ScheduledCashFlow
from app.preprocessing import (
    ensure_dates_chronological,
    ensure_datetimes_chronological,
    ensure_history_not_after,
    ensure_record_limit,
)
from app.preprocessing.records import MAX_RECORDS_PER_REQUEST


class CashBalanceForecastRequest(CommonPredictionRequest):
    current_balance: float
    horizon_days: Literal[7, 15, 30] = 30
    transactions: list[NormalizedTransaction] = Field(
        default_factory=list,
        max_length=MAX_RECORDS_PER_REQUEST,
    )
    scheduled_cash_flows: list[ScheduledCashFlow] = Field(
        default_factory=list,
        max_length=MAX_RECORDS_PER_REQUEST,
    )

    @model_validator(mode="after")
    def validate_records(self) -> "CashBalanceForecastRequest":
        ensure_record_limit(self.transactions, self.scheduled_cash_flows)
        transaction_times = [record.occurred_at for record in self.transactions]
        ensure_datetimes_chronological(transaction_times)
        ensure_history_not_after(transaction_times, self.as_of)
        scheduled_dates = [record.scheduled_date for record in self.scheduled_cash_flows]
        ensure_dates_chronological(scheduled_dates)
        if any(value < self.as_of.date() for value in scheduled_dates):
            raise ValueError("scheduled cash flows cannot occur before as_of")
        return self


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


class CashBalanceForecastResponse(
    CommonPredictionResponse[CashBalanceSummary, CashBalancePoint, CashBalancePoint]
):
    model_name: Literal["forecast_cash_balance"] = "forecast_cash_balance"
    summary: CashBalanceSummary
    series: list[CashBalancePoint]
