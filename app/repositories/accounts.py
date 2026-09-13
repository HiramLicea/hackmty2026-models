"""Account ownership queries with mandatory user isolation."""

import asyncio
from typing import Any, Protocol, cast
from uuid import UUID

from app.core.errors import AccountNotFoundError, DataSourceUnavailableError


class AccountOwnershipRepository(Protocol):
    """Boundary used before any account-scoped financial read."""

    async def require_owned_account(self, user_id: UUID, account_id: UUID) -> None:
        """Reject accounts that do not belong to the verified user."""
        ...


class SupabaseAccountOwnershipRepository:
    """Resolve ownership using the confirmed accounts.id/accounts.user_id contract."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def require_owned_account(self, user_id: UUID, account_id: UUID) -> None:
        """Select only a row matching both resource identity and verified ownership."""
        try:
            found = await asyncio.to_thread(self._owned_account_exists, user_id, account_id)
        except Exception as error:
            raise DataSourceUnavailableError("account ownership lookup failed") from error
        if not found:
            raise AccountNotFoundError(account_id)

    def _owned_account_exists(self, user_id: UUID, account_id: UUID) -> bool:
        response: Any = (
            self._client.table("accounts")
            .select("id")
            .eq("user_id", str(user_id))
            .eq("id", str(account_id))
            .limit(1)
            .execute()
        )
        rows = cast(list[dict[str, object]], response.data or [])
        return bool(rows)
