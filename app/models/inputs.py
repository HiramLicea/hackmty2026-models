"""Reusable normalized financial records accepted by the inference engine."""

from datetime import UTC, date, datetime
from enum import StrEnum

from pydantic import AwareDatetime, Field, field_validator

from app.models.common import OpaqueId, StrictModel
from app.preprocessing import (
    normalize_cash_flow_direction,
    normalize_transaction_direction,
    signed_cash_flow_amount,
    signed_transaction_amount,
)


class TransactionDirection(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class CashFlowDirection(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class NormalizedTransaction(StrictModel):
    transaction_id: OpaqueId
    amount: float = Field(gt=0)
    direction: TransactionDirection
    category: str = Field(min_length=1, max_length=100)
    merchant: str | None = Field(default=None, min_length=1, max_length=200)
    occurred_at: AwareDatetime

    @field_validator("direction", mode="before")
    @classmethod
    def normalize_direction(cls, value: object) -> str:
        return normalize_transaction_direction(value)

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    def signed_amount(self) -> float:
        """Derive, but never accept, the signed amount used by model pipelines."""
        return signed_transaction_amount(self.amount, self.direction)


class ScheduledCashFlow(StrictModel):
    cash_flow_id: OpaqueId
    name: str = Field(min_length=1, max_length=160)
    amount: float = Field(gt=0)
    direction: CashFlowDirection
    scheduled_date: date

    @field_validator("direction", mode="before")
    @classmethod
    def normalize_direction(cls, value: object) -> str:
        return normalize_cash_flow_direction(value)

    def signed_amount(self) -> float:
        """Derive the signed scheduled amount without mutating input."""
        return signed_cash_flow_amount(self.amount, self.direction)


class SavingsGoalInput(StrictModel):
    goal_id: OpaqueId
    target_amount: float = Field(gt=0)
    target_date: date
    current_saved_amount: float = Field(ge=0)


class SavingsContribution(StrictModel):
    contribution_id: OpaqueId | None = None
    amount: float = Field(gt=0)
    contributed_at: AwareDatetime

    @field_validator("contributed_at")
    @classmethod
    def normalize_contributed_at(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)
