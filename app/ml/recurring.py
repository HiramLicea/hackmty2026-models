"""Explainable merchant-periodicity detector used in training and inference."""

import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np


def _field(record: Any, name: str) -> Any:
    return getattr(record, name) if hasattr(record, name) else record[name]


def normalize_merchant(value: str | None) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", (value or "unknown").lower())
    text = re.sub(r"\b(?:mx|mex|payment|pago|online|\d+)\b", " ", text)
    return " ".join(text.split()) or "unknown"


def detect_patterns(
    transactions: list[Any], as_of: date, forecast_days: int, config: dict[str, Any]
) -> list[dict[str, Any]]:
    groups: dict[str, list[Any]] = defaultdict(list)
    for item in transactions:
        direction = str(_field(item, "direction")).lower()
        merchant = _field(item, "merchant")
        if direction == "debit" and merchant:
            groups[normalize_merchant(str(merchant))].append(item)
    results: list[dict[str, Any]] = []
    for merchant, items in groups.items():
        items.sort(key=lambda item: str(_field(item, "occurred_at")))
        dates = [_as_datetime(item).date() for item in items]
        if len(dates) < int(config["min_observations"]):
            continue
        intervals = np.diff([value.toordinal() for value in dates]).astype(float)
        median_interval = float(np.median(intervals))
        if median_interval <= 0:
            continue
        mad = float(np.median(np.abs(intervals - median_interval)))
        allowed = max(
            float(config["absolute_tolerance_days"]),
            median_interval * float(config["relative_tolerance"]),
        )
        confidence = min(1.0, len(items) / 6) * max(0.0, 1.0 - mad / max(1.0, allowed))
        if mad > allowed or confidence < float(config["min_confidence"]):
            continue
        next_date = dates[-1] + timedelta(days=max(1, round(median_interval)))
        while next_date <= as_of:
            next_date += timedelta(days=max(1, round(median_interval)))
        if next_date > as_of + timedelta(days=forecast_days):
            continue
        amounts = [float(_field(item, "amount")) for item in items]
        results.append(
            {
                "normalized_merchant": merchant,
                "next_expected_date": next_date,
                "expected_amount": round(float(np.median(amounts)), 2),
                "interval_days": round(median_interval, 2),
                "confidence": round(confidence, 4),
                "observations": len(items),
            }
        )
    return sorted(results, key=lambda row: (row["next_expected_date"], row["normalized_merchant"]))


def _as_datetime(item: Any) -> datetime:
    value = _field(item, "occurred_at")
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
