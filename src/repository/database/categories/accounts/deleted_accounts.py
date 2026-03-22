from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from src.database.models.categories import (
    DeletedAccounts,
)
from src.repository.database.base import DatabaseBase


class DeletedAccountsRepository(DatabaseBase):

    async def get_by_id(self, deleted_account_id: int) -> Optional[DeletedAccounts]:
        result = await self.session_db.execute(
            select(DeletedAccounts).where(
                DeletedAccounts.deleted_account_id == deleted_account_id
            )
        )
        return result.scalar_one_or_none()

    async def create_deleted(self, **values) -> DeletedAccounts:
        return await super().create(DeletedAccounts, **values)

    async def get_by_account_storage_id(
        self,
        account_storage_id: int,
    ) -> Optional[DeletedAccounts]:
        result = await self.session_db.execute(
            select(DeletedAccounts).where(
                DeletedAccounts.account_storage_id == account_storage_id
            )
        )
        return result.scalar_one_or_none()