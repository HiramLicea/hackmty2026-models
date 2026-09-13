"""Small numerical feature builders with no persistence or network access."""

from collections import Counter, defaultdict
from datetime import datetime
from math import cos, log1p, pi, sin
from typing import Any

import numpy as np

CASH_FEATURES = [
    "current_balance",
    "horizon_days",
    "daily_net_mean_30",
    "daily_net_std_30",
    "daily_income_mean_30",
    "daily_expense_mean_30",
    "expense_trend",
    "weekday",
    "month",
    "history_days",
    "scheduled_net",
    "scheduled_income",
    "scheduled_expense",
]
SAVINGS_FEATURES = [
    "remaining",
    "days_to_target",
    "current_saved",
    "target_amount",
    "progress",
    "monthly_contribution_mean",
    "monthly_contribution_std",
    "contribution_count",
    "monthly_free_cash_mean",
    "monthly_free_cash_std",
    "cash_history_days",
]
ANOMALY_FEATURES = [
    "log_amount",
    "is_credit",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
    "category_amount_ratio",
    "merchant_amount_ratio",
    "merchant_frequency",
    "category_frequency",
    "days_since_previous",
    "transactions_last_24h",
    "is_new_merchant",
]


def _field(record: Any, name: str) -> Any:
    return getattr(record, name) if hasattr(record, name) else record[name]


def _signed(record: Any) -> float:
    direction = str(_field(record, "direction")).lower()
    amount = float(_field(record, "amount"))
    return amount if direction in {"credit", "income"} else -amount


def _time(record: Any) -> datetime:
    value = _field(record, "occurred_at")
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))


def cash_features(
    transactions: list[Any],
    current_balance: float,
    as_of: datetime,
    horizon_days: int,
    scheduled: list[Any],
) -> np.ndarray:
    cutoff = as_of.timestamp() - 30 * 86400
    recent = [record for record in transactions if _time(record).timestamp() >= cutoff]
    daily: dict[str, list[float]] = defaultdict(list)
    for record in recent:
        daily[_time(record).date().isoformat()].append(_signed(record))
    values = np.array([sum(day) for day in daily.values()] or [0.0], dtype=float)
    income = np.array([max(_signed(record), 0.0) for record in recent] or [0.0])
    expenses = np.array([max(-_signed(record), 0.0) for record in recent] or [0.0])
    half = max(1, len(values) // 2)
    trend = float(values[-half:].mean() - values[:half].mean())
    scheduled_values = [_signed(record) for record in scheduled]
    history_days = max(1, (as_of - _time(transactions[0])).days) if transactions else 0
    return np.array(
        [
            [
                current_balance,
                horizon_days,
                values.mean(),
                values.std(),
                income.sum() / 30,
                expenses.sum() / 30,
                trend,
                as_of.weekday(),
                as_of.month,
                history_days,
                sum(scheduled_values),
                sum(max(x, 0) for x in scheduled_values),
                sum(max(-x, 0) for x in scheduled_values),
            ]
        ],
        dtype=float,
    )


def savings_features(
    goal: Any,
    contributions: list[Any],
    cash_history: list[Any],
    as_of: datetime,
) -> np.ndarray:
    target = float(_field(goal, "target_amount"))
    current = float(_field(goal, "current_saved_amount"))
    target_date = _field(goal, "target_date")
    if not hasattr(target_date, "toordinal"):
        target_date = datetime.fromisoformat(str(target_date)).date()
    monthly: dict[tuple[int, int], list[float]] = defaultdict(list)
    for item in contributions:
        when = _field(item, "contributed_at")
        if not isinstance(when, datetime):
            when = datetime.fromisoformat(str(when))
        monthly[(when.year, when.month)].append(float(_field(item, "amount")))
    contribution_values = np.array([sum(value) for value in monthly.values()] or [0.0])
    cash_monthly: dict[tuple[int, int], list[float]] = defaultdict(list)
    for item in cash_history:
        when = _time(item)
        cash_monthly[(when.year, when.month)].append(_signed(item))
    cash_values = np.array([sum(value) for value in cash_monthly.values()] or [0.0])
    history_days = max(1, (as_of - _time(cash_history[0])).days) if cash_history else 0
    return np.array(
        [
            [
                max(0.0, target - current),
                max(1, (target_date - as_of.date()).days),
                current,
                target,
                min(2.0, current / target),
                contribution_values.mean(),
                contribution_values.std(),
                len(contributions),
                cash_values.mean(),
                cash_values.std(),
                history_days,
            ]
        ],
        dtype=float,
    )


def anomaly_features(history: list[Any], candidates: list[Any]) -> np.ndarray:
    merchant_counts = Counter(str(_field(x, "merchant") or "unknown").lower() for x in history)
    category_counts = Counter(str(_field(x, "category")).lower() for x in history)
    merchant_amounts: dict[str, list[float]] = defaultdict(list)
    category_amounts: dict[str, list[float]] = defaultdict(list)
    for item in history:
        merchant = str(_field(item, "merchant") or "unknown").lower()
        category = str(_field(item, "category")).lower()
        merchant_amounts[merchant].append(abs(_signed(item)))
        category_amounts[category].append(abs(_signed(item)))
    seen_times = [_time(item) for item in history]
    rows: list[list[float]] = []
    for item in candidates:
        denominator = max(1, sum(merchant_counts.values()))
        amount = abs(_signed(item))
        when = _time(item)
        merchant = str(_field(item, "merchant") or "unknown").lower()
        category = str(_field(item, "category")).lower()
        merchant_median = float(np.median(merchant_amounts.get(merchant, [amount])))
        category_median = float(np.median(category_amounts.get(category, [amount])))
        rows.append(
            [
                log1p(amount),
                float(_signed(item) > 0),
                sin(2 * pi * when.hour / 24),
                cos(2 * pi * when.hour / 24),
                sin(2 * pi * when.weekday() / 7),
                cos(2 * pi * when.weekday() / 7),
                amount / max(1.0, category_median),
                amount / max(1.0, merchant_median),
                merchant_counts[merchant] / denominator,
                category_counts[category] / denominator,
                max(0.0, (when - seen_times[-1]).total_seconds() / 86400) if seen_times else 365.0,
                sum(0 <= (when - previous).total_seconds() <= 86400 for previous in seen_times),
                float(merchant_counts[merchant] == 0),
            ]
        )
        merchant_counts[merchant] += 1
        category_counts[category] += 1
        merchant_amounts[merchant].append(amount)
        category_amounts[category].append(amount)
        seen_times.append(when)
    return np.asarray(rows, dtype=float).reshape((-1, len(ANOMALY_FEATURES)))
