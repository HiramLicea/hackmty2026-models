"""Real artifact-backed inference, determinism, ordering, and graceful failure."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from app.artifacts.store import ArtifactStore
from app.models.anomalies import AnomalyDetectionRequest
from app.models.cash_balance import CashBalanceForecastRequest
from app.models.inputs import (
    NormalizedTransaction,
    SavingsContribution,
    SavingsGoalInput,
    ScheduledCashFlow,
)
from app.models.recurring_charges import RecurringChargesRequest
from app.models.savings_goal import SavingsGoalPredictionRequest
from app.services import (
    AnomalyDetectionService,
    CashBalanceForecastService,
    ModelNotReadyError,
    RecurringChargesForecastService,
    SavingsGoalPredictionService,
)

REQUEST_ID = UUID("25c00a42-822b-49a7-9c50-0fe913242977")
AS_OF = datetime(2026, 8, 31, 23, 59, tzinfo=UTC)


def history() -> list[NormalizedTransaction]:
    rows: list[NormalizedTransaction] = []
    for month in range(1, 9):
        rows.extend(
            [
                NormalizedTransaction(
                    transaction_id=f"salary-{month}",
                    amount=20_000,
                    direction="credit",
                    category="income",
                    merchant="synthetic employer",
                    occurred_at=datetime(2026, month, 1, 9, tzinfo=UTC),
                ),
                NormalizedTransaction(
                    transaction_id=f"rent-{month}",
                    amount=7_000,
                    direction="debit",
                    category="housing",
                    merchant="arrendamiento hogar",
                    occurred_at=datetime(2026, month, 3, 9, tzinfo=UTC),
                ),
                NormalizedTransaction(
                    transaction_id=f"stream-{month}",
                    amount=199,
                    direction="debit",
                    category="subscription",
                    merchant="stream plus mx",
                    occurred_at=datetime(2026, month, 12, 9, tzinfo=UTC),
                ),
            ]
        )
    return sorted(rows, key=lambda item: item.occurred_at)


def test_missing_artifacts_fail_loudly() -> None:
    request = CashBalanceForecastRequest(
        request_id=REQUEST_ID, as_of=AS_OF, currency="MXN", current_balance=10_000
    )
    with pytest.raises(ModelNotReadyError):
        asyncio.run(CashBalanceForecastService().predict(request))


def test_cash_quantiles_are_ordered_and_scheduled_flow_is_exact(
    trained_artifact_store: ArtifactStore,
) -> None:
    base = dict(
        request_id=REQUEST_ID,
        as_of=AS_OF,
        currency="MXN",
        current_balance=10_000,
        horizon_days=7,
        transactions=history(),
    )
    without = asyncio.run(
        CashBalanceForecastService(trained_artifact_store).predict(
            CashBalanceForecastRequest(**base)
        )
    )
    flow = ScheduledCashFlow(
        cash_flow_id="flow-1",
        name="refund",
        amount=500,
        direction="income",
        scheduled_date=date(2026, 9, 3),
    )
    with_flow = asyncio.run(
        CashBalanceForecastService(trained_artifact_store).predict(
            CashBalanceForecastRequest(**base, scheduled_cash_flows=[flow])
        )
    )
    assert all(
        point.lower_bound <= point.expected <= point.upper_bound for point in with_flow.series
    )
    assert with_flow.series[-1].expected - without.series[-1].expected == 500
    assert with_flow.trained_until.tzinfo is not None


def test_savings_scenarios_are_deterministic_and_ordered(
    trained_artifact_store: ArtifactStore,
) -> None:
    contributions = [
        SavingsContribution(
            contribution_id=f"c-{month}",
            amount=1_500,
            contributed_at=datetime(2026, month, 20, tzinfo=UTC),
        )
        for month in range(1, 9)
    ]
    request = SavingsGoalPredictionRequest(
        request_id=REQUEST_ID,
        as_of=AS_OF,
        currency="MXN",
        goal=SavingsGoalInput(
            goal_id="goal-1",
            target_amount=40_000,
            target_date=date(2027, 8, 31),
            current_saved_amount=12_000,
        ),
        contributions=contributions,
        cash_flow_history=history(),
    )
    service = SavingsGoalPredictionService(trained_artifact_store)
    first = asyncio.run(service.predict(request))
    second = asyncio.run(service.predict(request))
    assert first.summary == second.summary
    assert all(point.conservative <= point.expected <= point.optimistic for point in first.series)
    assert 0 <= first.summary.probability_of_success <= 1


def test_recurring_and_anomaly_services_return_explainable_items(
    trained_artifact_store: ArtifactStore,
) -> None:
    recurring_request = RecurringChargesRequest(
        request_id=REQUEST_ID, as_of=AS_OF, currency="MXN", forecast_days=45, transactions=history()
    )
    recurring = asyncio.run(
        RecurringChargesForecastService(trained_artifact_store).predict(recurring_request)
    )
    assert recurring.items
    assert all(item.observations >= 3 for item in recurring.items)
    candidate_time = AS_OF - timedelta(minutes=1)
    candidates = [
        NormalizedTransaction(
            transaction_id="unusual-1",
            amount=50_000,
            direction="debit",
            category="shopping",
            merchant="brand new merchant",
            occurred_at=candidate_time,
        )
    ]
    anomaly_request = AnomalyDetectionRequest(
        request_id=REQUEST_ID,
        as_of=AS_OF,
        currency="MXN",
        historical_transactions=history(),
        candidate_transactions=candidates,
    )
    anomalies = asyncio.run(
        AnomalyDetectionService(trained_artifact_store).predict(anomaly_request)
    )
    assert anomalies.items
    assert anomalies.items[0].reasons
