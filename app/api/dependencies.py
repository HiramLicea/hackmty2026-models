"""Composition root for request-scoped API dependencies."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends
from supabase import create_client

from app.artifacts.store import ArtifactStore
from app.core.config import Settings, get_settings
from app.core.errors import DataSourceUnavailableError
from app.repositories.accounts import (
    AccountOwnershipRepository,
    SupabaseAccountOwnershipRepository,
)
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


class UnavailableAccountOwnershipRepository:
    """Fail closed when server-side Supabase configuration is incomplete."""

    async def require_owned_account(self, user_id: Any, account_id: Any) -> None:
        del user_id, account_id
        raise DataSourceUnavailableError("Supabase configuration is unavailable")


def get_account_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccountOwnershipRepository:
    """Create an ownership repository without querying Supabase during startup."""
    key = settings.supabase_service_role_key
    if not settings.supabase_url or key is None or not key.get_secret_value():
        return UnavailableAccountOwnershipRepository()
    client = create_client(settings.supabase_url, key.get_secret_value())
    return SupabaseAccountOwnershipRepository(client)


def get_cash_balance_service(
    artifacts: Annotated[ArtifactStore, Depends(get_artifact_store)],
    accounts: Annotated[AccountOwnershipRepository, Depends(get_account_repository)],
) -> CashBalanceForecastService:
    return CashBalanceForecastService(artifacts, accounts)


def get_savings_goal_service(
    artifacts: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> SavingsGoalPredictionService:
    return SavingsGoalPredictionService(artifacts)


def get_recurring_charges_service(
    artifacts: Annotated[ArtifactStore, Depends(get_artifact_store)],
    accounts: Annotated[AccountOwnershipRepository, Depends(get_account_repository)],
) -> RecurringChargesForecastService:
    return RecurringChargesForecastService(artifacts, accounts)


def get_anomaly_detection_service(
    artifacts: Annotated[ArtifactStore, Depends(get_artifact_store)],
    accounts: Annotated[AccountOwnershipRepository, Depends(get_account_repository)],
) -> AnomalyDetectionService:
    return AnomalyDetectionService(artifacts, accounts)
