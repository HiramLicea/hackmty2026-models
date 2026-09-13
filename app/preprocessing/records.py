"""Pure preprocessing helpers that never mutate caller-owned records."""

from collections.abc import Sequence
from datetime import date, datetime
from typing import Literal, cast

MAX_RECORDS_PER_REQUEST = 10_000


def normalize_transaction_direction(value: object) -> Literal["debit", "credit"]:
    """Normalize a transaction direction to the engine's two canonical values."""
    if not isinstance(value, str):
        raise ValueError("transaction direction must be debit or credit")
    normalized = value.strip().lower()
    if normalized not in {"debit", "credit"}:
        raise ValueError("transaction direction must be debit or credit")
    return cast(Literal["debit", "credit"], normalized)


def normalize_cash_flow_direction(value: object) -> Literal["income", "expense"]:
    """Normalize a scheduled cash-flow direction."""
    if not isinstance(value, str):
        raise ValueError("cash-flow direction must be income or expense")
    normalized = value.strip().lower()
    if normalized not in {"income", "expense"}:
        raise ValueError("cash-flow direction must be income or expense")
    return cast(Literal["income", "expense"], normalized)


def signed_transaction_amount(amount: float, direction: object) -> float:
    """Apply the invariant credit=positive and debit=negative."""
    return amount if normalize_transaction_direction(direction) == "credit" else -amount


def signed_cash_flow_amount(amount: float, direction: object) -> float:
    """Apply the invariant income=positive and expense=negative."""
    return amount if normalize_cash_flow_direction(direction) == "income" else -amount


def ensure_datetimes_chronological(values: Sequence[datetime]) -> None:
    """Reject input whose timestamps move backwards; never sort caller input."""
    if any(current < previous for previous, current in zip(values, values[1:], strict=False)):
        raise ValueError("records must be ordered chronologically")


def ensure_dates_chronological(values: Sequence[date]) -> None:
    """Reject input whose dates move backwards; never sort caller input."""
    if any(current < previous for previous, current in zip(values, values[1:], strict=False)):
        raise ValueError("records must be ordered chronologically")


def ensure_history_not_after(values: Sequence[datetime], as_of: datetime) -> None:
    """Ensure the inference cutoff is at or after every historical record."""
    if any(value > as_of for value in values):
        raise ValueError("historical records cannot occur after as_of")


def ensure_record_limit(*groups: Sequence[object]) -> None:
    """Bound the total request size across all normalized record collections."""
    if sum(len(group) for group in groups) > MAX_RECORDS_PER_REQUEST:
        raise ValueError(f"requests accept at most {MAX_RECORDS_PER_REQUEST} records")
