"""Deterministic synthetic financial histories; never reads external or banking data."""

import hashlib
import json
import random
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

ARCHETYPES = (
    "stable_income",
    "variable_income",
    "comfortable_balance",
    "tight_balance",
    "seasonal_spending",
    "growing_expenses",
    "consistent_saving",
    "irregular_saving",
    "subscription_heavy",
    "high_variability",
    "simulated_unemployment",
    "extraordinary_expenses",
)
EXPENSES = (
    ("groceries", "mercado norte", 0.060),
    ("transport", "movilidad urbana", 0.030),
    ("dining", "cafe central", 0.025),
    ("shopping", "tienda local", 0.035),
    ("health", "farmacia bienestar", 0.018),
    ("entertainment", "cine plaza", 0.015),
)


def _iso(day: date, hour: int = 12) -> str:
    return datetime.combine(day, time(hour, 0), UTC).isoformat()


def _transaction(
    profile_id: str,
    index: int,
    day: date,
    amount: float,
    direction: str,
    category: str,
    merchant: str,
    hour: int = 12,
) -> dict[str, Any]:
    return {
        "transaction_id": f"{profile_id}-txn-{index:05d}",
        "amount": round(max(1.0, amount), 2),
        "direction": direction,
        "category": category,
        "merchant": merchant,
        "occurred_at": _iso(day, hour),
    }


def generate_profile(seed: int, index: int, months: int, end_date: date) -> dict[str, Any]:
    rng = random.Random(seed * 100_003 + index)
    profile_id = f"syn-profile-{index:04d}"
    archetype = ARCHETYPES[index % len(ARCHETYPES)]
    start_date = end_date - timedelta(days=round(months * 30.44) - 1)
    monthly_income = rng.uniform(12_000, 65_000)
    volatility = {
        "variable_income": 0.38,
        "high_variability": 0.45,
        "seasonal_spending": 0.35,
        "stable_income": 0.08,
    }.get(archetype, 0.18)
    savings_rate = 0.22 if archetype == "consistent_saving" else rng.uniform(0.04, 0.17)
    records: list[dict[str, Any]] = []
    anomaly_ids: list[str] = []
    recurring_truth: list[dict[str, Any]] = []
    cursor = start_date
    txn_index = 0
    rent = monthly_income * rng.uniform(0.18, 0.30)
    subscription = rng.uniform(99, 399)
    utility = rng.uniform(450, 1600)
    while cursor <= end_date:
        # Salaries and fixed charges produce observable, realistic periodicity.
        unemployed = archetype == "simulated_unemployment" and start_date + timedelta(
            days=150
        ) <= cursor <= start_date + timedelta(days=240)
        if cursor.day in {1, 15} and not unemployed:
            income = monthly_income / 2 * rng.uniform(1 - volatility, 1 + volatility)
            records.append(
                _transaction(
                    profile_id,
                    txn_index,
                    cursor,
                    income,
                    "credit",
                    "income",
                    "synthetic employer",
                    9,
                )
            )
            txn_index += 1
        if cursor.day == 3:
            records.append(
                _transaction(
                    profile_id,
                    txn_index,
                    cursor,
                    rent,
                    "debit",
                    "housing",
                    "arrendamiento hogar",
                    8,
                )
            )
            txn_index += 1
        if cursor.day == 12 and not (
            archetype == "subscription_heavy" and cursor > start_date + timedelta(days=420)
        ):
            merchant_variant = rng.choice(
                ("stream plus mx", "STREAM-PLUS PAYMENT", "stream plus 1234")
            )
            records.append(
                _transaction(
                    profile_id,
                    txn_index,
                    cursor,
                    subscription * rng.uniform(0.96, 1.04),
                    "debit",
                    "subscription",
                    merchant_variant,
                    6,
                )
            )
            txn_index += 1
        if cursor.day == 8:
            records.append(
                _transaction(
                    profile_id,
                    txn_index,
                    cursor,
                    utility * rng.uniform(0.92, 1.08),
                    "debit",
                    "utilities",
                    "energia hogar",
                    10,
                )
            )
            txn_index += 1
        if cursor.month == 1 and cursor.day == 25:
            records.append(
                _transaction(
                    profile_id,
                    txn_index,
                    cursor,
                    monthly_income * 0.08,
                    "debit",
                    "insurance",
                    "seguro anual",
                    11,
                )
            )
            txn_index += 1
        if cursor.weekday() == 0:
            records.append(
                _transaction(
                    profile_id,
                    txn_index,
                    cursor,
                    rng.uniform(180, 420),
                    "debit",
                    "transport",
                    "movilidad semanal",
                    7,
                )
            )
            txn_index += 1
        count = rng.choices((0, 1, 2, 3), weights=(8, 45, 35, 12), k=1)[0]
        for _ in range(count):
            category, merchant, fraction = rng.choice(EXPENSES)
            amount = monthly_income * fraction * rng.lognormvariate(-1.9, 0.45)
            progress = (cursor - start_date).days / max(1, (end_date - start_date).days)
            if archetype == "growing_expenses":
                amount *= 1.0 + 0.8 * progress
            if archetype == "seasonal_spending" and cursor.month in {11, 12}:
                amount *= 1.7
            records.append(
                _transaction(
                    profile_id,
                    txn_index,
                    cursor,
                    amount,
                    "debit",
                    category,
                    merchant,
                    rng.randrange(7, 23),
                )
            )
            txn_index += 1
        cursor += timedelta(days=1)
    recurring_truth.extend(
        [
            {"merchant": "arrendamiento hogar", "interval_days": 30.44},
            {"merchant": "stream plus", "interval_days": 30.44},
            {"merchant": "movilidad semanal", "interval_days": 7.0},
            {"merchant": "energia hogar", "interval_days": 30.44},
            {"merchant": "seguro anual", "interval_days": 365.0},
        ]
    )
    # Rare labeled events are injected only after normal behavior exists.
    anomaly_count = max(3, round(len(records) * 0.015))
    for anomaly_number in range(anomaly_count):
        day = start_date + timedelta(days=rng.randrange(max(1, (end_date - start_date).days)))
        amount = monthly_income * rng.uniform(0.7, 1.8)
        item = _transaction(
            profile_id,
            txn_index,
            day,
            amount,
            "debit",
            "shopping",
            f"unseen merchant {anomaly_number}",
            3,
        )
        records.append(item)
        anomaly_ids.append(item["transaction_id"])
        txn_index += 1
    # A controlled rapid burst represents sudden frequency and several operations in minutes.
    burst_day = start_date + timedelta(
        days=rng.randrange(60, max(61, (end_date - start_date).days))
    )
    for minute in range(4):
        item = _transaction(
            profile_id,
            txn_index,
            burst_day,
            monthly_income * rng.uniform(0.12, 0.25),
            "debit",
            "transfer",
            f"unseen burst merchant {index}",
            2,
        )
        item["occurred_at"] = datetime.combine(burst_day, time(2, minute * 3), UTC).isoformat()
        records.append(item)
        anomaly_ids.append(item["transaction_id"])
        txn_index += 1
    records.sort(key=lambda item: (item["occurred_at"], item["transaction_id"]))
    # Keep the requested density stable without altering recurrent/anomaly truth.
    while len(records) < 300:
        day = start_date + timedelta(days=rng.randrange(max(1, (end_date - start_date).days)))
        category, merchant, fraction = rng.choice(EXPENSES)
        records.append(
            _transaction(
                profile_id,
                txn_index,
                day,
                monthly_income * fraction * rng.uniform(0.05, 0.25),
                "debit",
                category,
                merchant,
            )
        )
        txn_index += 1
    if len(records) > 600:
        protected = set(anomaly_ids)
        retained = [item for item in records if item["transaction_id"] in protected]
        ordinary = [item for item in records if item["transaction_id"] not in protected]
        slots = 600 - len(retained)
        sampled = [ordinary[int(position * len(ordinary) / slots)] for position in range(slots)]
        records = retained + sampled
    records.sort(key=lambda item: (item["occurred_at"], item["transaction_id"]))
    monthly_contribution = monthly_income * savings_rate
    goal_states = ("completed", "completed_late", "active_on_track", "at_risk", "abandoned")
    goal_status = goal_states[index % len(goal_states)]
    contributions: list[dict[str, Any]] = []
    contribution_cursor = date(start_date.year, start_date.month, 20)
    contribution_index = 0
    while contribution_cursor <= end_date:
        if goal_status == "abandoned" and contribution_cursor > start_date + timedelta(
            days=(end_date - start_date).days // 2
        ):
            break
        if archetype == "irregular_saving" and rng.random() < 0.35:
            contribution_cursor = _add_month(contribution_cursor)
            continue
        contributions.append(
            {
                "contribution_id": f"{profile_id}-contribution-{contribution_index:03d}",
                "amount": round(monthly_contribution * rng.uniform(0.7, 1.3), 2),
                "contributed_at": _iso(contribution_cursor, 18),
            }
        )
        contribution_index += 1
        contribution_cursor = _add_month(contribution_cursor)
    current_saved = round(
        sum(item["amount"] for item in contributions) * rng.uniform(0.45, 0.85), 2
    )
    target_amount = round(max(current_saved * rng.uniform(1.3, 2.8), monthly_income * 2), 2)
    target_date = end_date + timedelta(days=rng.randrange(120, 540))
    goal = {
        "goal_id": f"{profile_id}-goal-001",
        "target_amount": target_amount,
        "target_date": target_date.isoformat(),
        "current_saved_amount": current_saved,
    }
    actual_completion = None
    if goal_status == "completed":
        actual_completion = (end_date - timedelta(days=rng.randrange(1, 90))).isoformat()
    if goal_status == "completed_late":
        actual_completion = (target_date + timedelta(days=rng.randrange(1, 90))).isoformat()
    scheduled = [
        {
            "cash_flow_id": f"{profile_id}-scheduled-income",
            "name": "next salary",
            "amount": round(monthly_income / 2, 2),
            "direction": "income",
            "scheduled_date": (end_date + timedelta(days=7)).isoformat(),
        },
        {
            "cash_flow_id": f"{profile_id}-scheduled-utility",
            "name": "expected utility",
            "amount": round(utility, 2),
            "direction": "expense",
            "scheduled_date": (end_date + timedelta(days=8)).isoformat(),
        },
        {
            "cash_flow_id": f"{profile_id}-scheduled-tuition",
            "name": "expected tuition",
            "amount": round(monthly_income * 0.10, 2),
            "direction": "expense",
            "scheduled_date": (end_date + timedelta(days=14)).isoformat(),
        },
        {
            "cash_flow_id": f"{profile_id}-scheduled-payment",
            "name": "expected payment",
            "amount": round(monthly_income * 0.04, 2),
            "direction": "expense",
            "scheduled_date": (end_date + timedelta(days=21)).isoformat(),
        },
        {
            "cash_flow_id": f"{profile_id}-scheduled-rent",
            "name": "next rent",
            "amount": round(rent, 2),
            "direction": "expense",
            "scheduled_date": (end_date + timedelta(days=3)).isoformat(),
        },
    ]
    scheduled.sort(key=lambda item: item["scheduled_date"])
    return {
        "profile_id": profile_id,
        "archetype": archetype,
        "currency": "MXN",
        "generated_start": start_date.isoformat(),
        "generated_end": end_date.isoformat(),
        "monthly_income": round(monthly_income, 2),
        "transactions": records,
        "scheduled_cash_flows": scheduled,
        "savings_goal": goal,
        "contributions": contributions,
        "evaluation": {
            "anomaly_transaction_ids": anomaly_ids,
            "recurring_patterns": recurring_truth,
            "goal_status": goal_status,
            "actual_completion_date": actual_completion,
            "actual_amount_at_completion": (
                target_amount if actual_completion is not None else current_saved
            ),
        },
    }


def _add_month(value: date) -> date:
    year = value.year + int(value.month == 12)
    month = 1 if value.month == 12 else value.month + 1
    return date(year, month, min(value.day, 28))


def generate_dataset(seed: int, users: int, months: int, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    end_date = date(2026, 8, 31)
    profiles = [generate_profile(seed, index, months, end_date) for index in range(users)]
    path = output_dir / "profiles.jsonl"
    payload = "".join(
        json.dumps(profile, separators=(",", ":"), sort_keys=True) + "\n" for profile in profiles
    )
    path.write_text(payload, encoding="utf-8", newline="\n")
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()
    counts = [len(profile["transactions"]) for profile in profiles]
    summary = {
        "schema_version": "1",
        "seed": seed,
        "users": users,
        "months": months,
        "start_date": profiles[0]["generated_start"] if profiles else None,
        "end_date": end_date.isoformat(),
        "transactions": sum(counts),
        "transactions_per_profile": {
            "minimum": min(counts, default=0),
            "maximum": max(counts, default=0),
            "mean": round(sum(counts) / max(1, len(counts)), 2),
        },
        "archetypes": dict(Counter(profile["archetype"] for profile in profiles)),
        "labeled_anomalies": sum(
            len(profile["evaluation"]["anomaly_transaction_ids"]) for profile in profiles
        ),
        "dataset_fingerprint": fingerprint,
        "data_file": "profiles.jsonl",
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def load_profiles(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
