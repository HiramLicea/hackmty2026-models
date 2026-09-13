"""Placeholder cash-balance service."""

from app.models.cash_balance import CashBalanceForecastRequest, CashBalanceForecastResponse
from app.repositories.accounts import AccountOwnershipRepository
from app.services.base import ArtifactLoader, ModelNotReadyError, require_artifact


class CashBalanceForecastService:
    """Future SARIMAX plus deterministic cash-flow implementation."""

    def __init__(
        self,
        artifacts: ArtifactLoader | None = None,
        accounts: AccountOwnershipRepository | None = None,
    ) -> None:
        self._artifacts = artifacts
        self._accounts = accounts

    async def predict(self, request: CashBalanceForecastRequest) -> CashBalanceForecastResponse:
        await require_artifact(self._artifacts, "forecast_cash_balance")
        if self._accounts is not None:
            await self._accounts.require_owned_account(request.user_id, request.account_id)
        raise ModelNotReadyError("forecast_cash_balance")
