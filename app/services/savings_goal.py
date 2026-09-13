"""Quantile and Monte Carlo savings-goal inference."""

import asyncio
import hashlib
from datetime import timedelta
from typing import cast

import numpy as np
from sklearn.base import RegressorMixin, TransformerMixin

from app.ml.features import savings_features
from app.models.common import ModelName, PredictionDriver
from app.models.savings_goal import (
    SavingsGoalPoint,
    SavingsGoalPredictionRequest,
    SavingsGoalPredictionResponse,
    SavingsGoalSummary,
)
from app.services.base import (
    ArtifactLoader,
    require_artifact,
    require_descriptor,
    require_json_artifact,
)

MODEL_NAME: ModelName = "predict_savings_goal"


class SavingsGoalPredictionService:
    def __init__(self, artifacts: ArtifactLoader | None = None) -> None:
        self._artifacts = artifacts

    async def predict(self, request: SavingsGoalPredictionRequest) -> SavingsGoalPredictionResponse:
        loaded = await asyncio.gather(
            *(
                require_artifact(self._artifacts, MODEL_NAME, key)
                for key in ("preprocessor", "goal_days_p10", "goal_days_p50", "goal_days_p90")
            )
        )
        config = await require_json_artifact(self._artifacts, MODEL_NAME, "simulation_config")
        descriptor = require_descriptor(self._artifacts, MODEL_NAME)
        transformed = cast(TransformerMixin, loaded[0]).transform(
            savings_features(
                request.goal, request.contributions, request.cash_flow_history, request.as_of
            )
        )
        days = sorted(
            max(1, round(float(cast(RegressorMixin, model).predict(transformed)[0])))
            for model in loaded[1:]
        )
        seed = int(hashlib.sha256(str(request.request_id).encode()).hexdigest()[:8], 16) + int(
            config["seed_offset"]
        )
        samples = np.random.default_rng(seed).normal(
            days[1], float(config["residual_std_days"]), int(config["samples"])
        )
        available = (request.goal.target_date - request.as_of.date()).days
        probability = float(np.mean(samples <= available))
        remaining = max(0.0, request.goal.target_amount - request.goal.current_saved_amount)
        months = max(1.0, available / 30.44)
        recommended = remaining / months
        recent = [item.amount for item in request.contributions[-6:]]
        recent_monthly = float(np.mean(recent)) if recent else recommended
        series: list[SavingsGoalPoint] = []
        for month in range(1, min(24, max(1, int(np.ceil(months)))) + 1):
            point_date = min(
                request.goal.target_date,
                request.as_of.date() + timedelta(days=round(month * 30.44)),
            )
            base = request.goal.current_saved_amount
            conservative = min(request.goal.target_amount, base + recent_monthly * 0.75 * month)
            expected = min(
                request.goal.target_amount, base + max(recent_monthly, recommended) * month
            )
            optimistic = min(
                request.goal.target_amount, base + max(recent_monthly * 1.25, recommended) * month
            )
            series.append(
                SavingsGoalPoint(
                    date=point_date,
                    conservative=round(conservative, 2),
                    expected=round(max(conservative, expected), 2),
                    optimistic=round(max(expected, optimistic), 2),
                )
            )
            if point_date == request.goal.target_date:
                break
        return SavingsGoalPredictionResponse(
            request_id=request.request_id,
            model_version=descriptor.model_version,
            trained_until=descriptor.trained_until,
            confidence=max(
                0.25, min(0.95, 1.0 - float(config["residual_std_days"]) / max(30.0, available))
            ),
            summary=SavingsGoalSummary(
                currency=request.currency,
                target_amount=request.goal.target_amount,
                current_amount=request.goal.current_saved_amount,
                probability_of_success=round(probability, 4),
                conservative_completion_date=request.as_of.date() + timedelta(days=days[2]),
                expected_completion_date=request.as_of.date() + timedelta(days=days[1]),
                optimistic_completion_date=request.as_of.date() + timedelta(days=days[0]),
                recommended_monthly_contribution=round(recommended, 2),
            ),
            series=series,
            drivers=[
                PredictionDriver(
                    name="remaining_amount",
                    impact=round(remaining, 2),
                    description="Amount still needed to reach the target.",
                ),
                PredictionDriver(
                    name="recent_contributions",
                    impact=round(recent_monthly, 2),
                    description="Recent contribution pace used for scenario paths.",
                ),
            ],
            limitations=descriptor.limitations,
        )
