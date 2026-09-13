"""Normalized input, temporal, privacy, and response contract invariants."""

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.models.anomalies import AnomalyDetectionRequest
from app.models.cash_balance import CashBalanceForecastRequest, CashBalancePoint
from app.models.inputs import NormalizedTransaction, ScheduledCashFlow
from app.models.recurring_charges import RecurringChargesRequest
from app.models.savings_goal import SavingsGoalPredictionRequest
from app.preprocessing import ensure_record_limit

REQUEST_ID = UUID("25c00a42-822b-49a7-9c50-0fe913242977")
AS_OF = datetime(2026, 9, 13, tzinfo=UTC)


def transaction(
    transaction_id: str = "txn-1",
    amount: float = 850.5,
    direction: str = "debit",
    occurred_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "transaction_id": transaction_id,
        "amount": amount,
        "direction": direction,
        "category": "groceries",
        "merchant": "HEB",
        "occurred_at": (occurred_at or AS_OF - timedelta(days=1)).isoformat(),
    }


def common_request() -> dict[str, object]:
    return {"request_id": str(REQUEST_ID), "as_of": AS_OF.isoformat(), "currency": "mxn"}


def test_amounts_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        NormalizedTransaction.model_validate(transaction(amount=-1))
    with pytest.raises(ValidationError):
        ScheduledCashFlow(
            cash_flow_id="flow-1",
            name="Rent",
            amount=-1,
            direction="expense",
            scheduled_date=date(2026, 9, 15),
        )


def test_directions_normalize_and_derive_signed_amounts() -> None:
    debit = NormalizedTransaction.model_validate(transaction(direction=" DEBIT "))
    credit = NormalizedTransaction.model_validate(transaction(direction="Credit"))
    income = ScheduledCashFlow(
        cash_flow_id="income-1",
        name="Payroll",
        amount=100,
        direction="INCOME",
        scheduled_date=date(2026, 9, 15),
    )
    expense = ScheduledCashFlow(
        cash_flow_id="expense-1",
        name="Rent",
        amount=100,
        direction=" expense ",
        scheduled_date=date(2026, 9, 16),
    )

    assert debit.direction == "debit" and debit.signed_amount() == -850.5
    assert credit.direction == "credit" and credit.signed_amount() == 850.5
    assert income.direction == "income" and income.signed_amount() == 100
    assert expense.direction == "expense" and expense.signed_amount() == -100


def test_cash_balance_validates_history_order_cutoff_and_does_not_mutate_input() -> None:
    payload = common_request() | {
        "current_balance": 15420.75,
        "horizon_days": 30,
        "transactions": [
            transaction("txn-1", occurred_at=AS_OF - timedelta(days=2)),
            transaction("txn-2", occurred_at=AS_OF - timedelta(days=1)),
        ],
        "scheduled_cash_flows": [],
    }
    original = deepcopy(payload)
    request = CashBalanceForecastRequest.model_validate(payload)
    assert payload == original
    assert request.currency == "MXN"

    reversed_payload = deepcopy(payload)
    reversed_transactions = reversed_payload["transactions"]
    assert isinstance(reversed_transactions, list)
    reversed_payload["transactions"] = list(reversed(reversed_transactions))
    with pytest.raises(ValidationError, match="chronologically"):
        CashBalanceForecastRequest.model_validate(reversed_payload)

    future_payload = deepcopy(payload)
    future_payload["transactions"] = [transaction(occurred_at=AS_OF + timedelta(seconds=1))]
    with pytest.raises(ValidationError, match="after as_of"):
        CashBalanceForecastRequest.model_validate(future_payload)


def test_record_limit_is_enforced_across_collections() -> None:
    with pytest.raises(ValueError, match="10000"):
        ensure_record_limit([object()] * 5_001, [object()] * 5_000)


def test_user_identity_fields_are_forbidden_from_all_requests() -> None:
    requests = (
        CashBalanceForecastRequest,
        SavingsGoalPredictionRequest,
        RecurringChargesRequest,
        AnomalyDetectionRequest,
    )
    for request_model in requests:
        assert "user_id" not in request_model.model_fields
        assert "email" not in request_model.model_fields


def test_cash_balance_bounds_must_contain_expected_value() -> None:
    with pytest.raises(ValidationError):
        CashBalancePoint(
            date=date(2026, 9, 13),
            expected=100,
            lower_bound=110,
            upper_bound=120,
        )
