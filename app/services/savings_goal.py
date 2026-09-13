"""Placeholder savings-goal service."""

from app.models.savings_goal import SavingsGoalPredictionRequest, SavingsGoalPredictionResponse
from app.services.base import ArtifactLoader, ModelNotReadyError, require_artifact


class SavingsGoalPredictionService:
    """Future quantile baseline and Monte Carlo implementation."""

    def __init__(self, artifacts: ArtifactLoader | None = None) -> None:
        self._artifacts = artifacts

    async def predict(self, request: SavingsGoalPredictionRequest) -> SavingsGoalPredictionResponse:
        del request
        await require_artifact(self._artifacts, "predict_savings_goal")
        raise ModelNotReadyError("predict_savings_goal")
