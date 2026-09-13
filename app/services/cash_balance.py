"""Quantile cash-balance inference plus deterministic scheduled cash flows."""

import asyncio
from datetime import timedelta
from typing import cast

from sklearn.base import RegressorMixin, TransformerMixin

from app.ml.features import cash_features
from app.models.cash_balance import (
    CashBalanceForecastRequest,
    CashBalanceForecastResponse,
    CashBalancePoint,
    CashBalanceSummary,
)
from app.models.common import ModelName, PredictionDriver
from app.services.base import ArtifactLoader, require_artifact, require_descriptor

MODEL_NAME: ModelName = "forecast_cash_balance"


class CashBalanceForecastService:
    def __init__(self, artifacts: ArtifactLoader | None = None) -> None:
        self._artifacts = artifacts

    async def predict(self, request: CashBalanceForecastRequest) -> CashBalanceForecastResponse:
        loaded = await asyncio.gather(
            *(
                require_artifact(self._artifacts, MODEL_NAME, key)
                for key in ("preprocessor", "forecast_p10", "forecast_p50", "forecast_p90")
            )
        )
        scaler = cast(TransformerMixin, loaded[0])
        models = [cast(RegressorMixin, model) for model in loaded[1:]]
        descriptor = require_descriptor(self._artifacts, MODEL_NAME)
        points: list[CashBalancePoint] = []
        for day_number in range(1, request.horizon_days + 1):
            day = request.as_of.date() + timedelta(days=day_number)
            known = [flow for flow in request.scheduled_cash_flows if flow.scheduled_date <= day]
            scheduled_net = sum(flow.signed_amount() for flow in known)
            feature = scaler.transform(
                cash_features(
                    request.transactions, request.current_balance, request.as_of, day_number, []
                )
            )
            residuals = sorted(float(model.predict(feature)[0]) for model in models)
            values = [request.current_balance + scheduled_net + residual for residual in residuals]
            points.append(
                CashBalancePoint(
                    date=day,
                    lower_bound=round(values[0], 2),
                    expected=round(values[1], 2),
                    upper_bound=round(values[2], 2),
                )
            )
        income = sum(
            flow.amount
            for flow in request.scheduled_cash_flows
            if flow.direction == "income" and flow.scheduled_date <= points[-1].date
        )
        expenses = sum(
            flow.amount
            for flow in request.scheduled_cash_flows
            if flow.direction == "expense" and flow.scheduled_date <= points[-1].date
        )
        raw_coverage = descriptor.metrics.get("interval_coverage_p10_p90", 0.7)
        coverage = float(raw_coverage) if isinstance(raw_coverage, int | float) else 0.7
        return CashBalanceForecastResponse(
            request_id=request.request_id,
            model_version=descriptor.model_version,
            trained_until=descriptor.trained_until,
            confidence=max(0.25, min(0.95, coverage)),
            summary=CashBalanceSummary(
                currency=request.currency,
                starting_balance=request.current_balance,
                expected_ending_balance=points[-1].expected,
                expected_minimum_balance=min(point.expected for point in points),
                scheduled_income=round(income, 2),
                scheduled_expenses=round(expenses, 2),
            ),
            series=points,
            drivers=[
                PredictionDriver(
                    name="recent_cash_flow",
                    description=(
                        "Recent signed income and expenses inform the learned residual forecast."
                    ),
                ),
                PredictionDriver(
                    name="scheduled_cash_flows",
                    impact=round(income - expenses, 2),
                    description=(
                        "Caller-provided scheduled flows are applied exactly on their dates."
                    ),
                ),
            ],
            limitations=descriptor.limitations,
        )
