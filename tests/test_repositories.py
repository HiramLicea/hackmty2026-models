"""Ownership isolation tests for Supabase repository queries."""

import asyncio
from types import SimpleNamespace
from typing import Self
from uuid import UUID

import pytest

from app.core.errors import AccountNotFoundError
from app.repositories.accounts import SupabaseAccountOwnershipRepository

USER_ID = UUID("c1a3797d-b335-5a9d-98a1-402311f82c7a")
ACCOUNT_ID = UUID("799bb0e5-b590-56b6-b30a-8f89538b65df")


class FakeQuery:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.filters: list[tuple[str, str]] = []
        self.table_name = ""

    def select(self, columns: str) -> Self:
        assert columns == "id"
        return self

    def eq(self, column: str, value: str) -> Self:
        self.filters.append((column, value))
        return self

    def limit(self, count: int) -> Self:
        assert count == 1
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.rows)


class FakeClient:
    def __init__(self, query: FakeQuery) -> None:
        self.query = query

    def table(self, name: str) -> FakeQuery:
        self.query.table_name = name
        return self.query


def test_account_query_always_includes_verified_user_id() -> None:
    query = FakeQuery([{"id": str(ACCOUNT_ID)}])
    repository = SupabaseAccountOwnershipRepository(FakeClient(query))

    asyncio.run(repository.require_owned_account(USER_ID, ACCOUNT_ID))

    assert query.table_name == "accounts"
    assert ("user_id", str(USER_ID)) in query.filters
    assert ("id", str(ACCOUNT_ID)) in query.filters


def test_foreign_account_is_rejected() -> None:
    query = FakeQuery([])
    repository = SupabaseAccountOwnershipRepository(FakeClient(query))

    with pytest.raises(AccountNotFoundError):
        asyncio.run(repository.require_owned_account(USER_ID, ACCOUNT_ID))
