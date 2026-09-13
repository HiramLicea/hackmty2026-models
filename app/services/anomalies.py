"""Placeholder anomaly-detection service."""

from app.models.anomalies import AnomalyDetectionRequest, AnomalyDetectionResponse
from app.repositories.accounts import AccountOwnershipRepository
from app.services.base import ArtifactLoader, ModelNotReadyError, require_artifact


class AnomalyDetectionService:
    """Future Isolation Forest plus explainable-rule implementation."""

    def __init__(
        self,
        artifacts: ArtifactLoader | None = None,
        accounts: AccountOwnershipRepository | None = None,
    ) -> None:
        self._artifacts = artifacts
        self._accounts = accounts

    async def predict(self, request: AnomalyDetectionRequest) -> AnomalyDetectionResponse:
        await require_artifact(self._artifacts, "detect_transaction_anomalies")
        if request.account_id is not None and self._accounts is not None:
            await self._accounts.require_owned_account(request.user_id, request.account_id)
        raise ModelNotReadyError("detect_transaction_anomalies")
