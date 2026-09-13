"""Composition root for request-scoped API dependencies."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from app.artifacts.store import ArtifactStore
from app.core.config import Settings, get_settings
from app.services import (
    AnomalyDetectionService,
    CashBalanceForecastService,
    RecurringChargesForecastService,
    SavingsGoalPredictionService,
)


@lru_cache
def build_artifact_store(root: str, manifest_path: str) -> ArtifactStore:
    """Keep one artifact cache per resolved configuration in a warm instance."""
    return ArtifactStore(Path(root), Path(manifest_path))


def get_artifact_store(settings: Annotated[Settings, Depends(get_settings)]) -> ArtifactStore:
    """Resolve the configured read-only artifact store."""
    return build_artifact_store(
        str(settings.model_artifact_dir),
        str(settings.model_manifest_path),
    )


def get_cash_balance_service(
    artifacts: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> CashBalanceForecastService:
    return CashBalanceForecastService(artifacts)


def get_savings_goal_service(
    artifacts: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> SavingsGoalPredictionService:
    return SavingsGoalPredictionService(artifacts)


def get_recurring_charges_service(
    artifacts: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> RecurringChargesForecastService:
    return RecurringChargesForecastService(artifacts)


def get_anomaly_detection_service(
    artifacts: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> AnomalyDetectionService:
    return AnomalyDetectionService(artifacts)
