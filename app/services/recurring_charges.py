"""Placeholder recurring-charge service."""

from app.models.recurring_charges import RecurringChargesRequest, RecurringChargesResponse
from app.repositories.accounts import AccountOwnershipRepository
from app.services.base import ArtifactLoader, ModelNotReadyError, require_artifact


class RecurringChargesForecastService:
    """Future explainable statistical periodicity detector."""

    def __init__(
        self,
        artifacts: ArtifactLoader | None = None,
        accounts: AccountOwnershipRepository | None = None,
    ) -> None:
        self._artifacts = artifacts
        self._accounts = accounts

    async def predict(self, request: RecurringChargesRequest) -> RecurringChargesResponse:
        await require_artifact(self._artifacts, "forecast_recurring_charges")
        if request.account_id is not None and self._accounts is not None:
            await self._accounts.require_owned_account(request.user_id, request.account_id)
        raise ModelNotReadyError("forecast_recurring_charges")
