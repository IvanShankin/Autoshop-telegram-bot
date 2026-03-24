from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from src.database.models.categories import (
    DeletedAccounts,
)
from src.read_models import DeletedAccountsDTO
from src.repository.database.base import DatabaseBase


class DeletedAccountsRepository(DatabaseBase):

    async def get_by_id(self, deleted_account_id: int) -> Optional[DeletedAccountsDTO]:
        result = await self.session_db.execute(
            select(DeletedAccounts).where(
                DeletedAccounts.deleted_account_id == deleted_account_id
            )
        )
        deleted = result.scalar_one_or_none()
        return DeletedAccountsDTO.model_validate(deleted) if deleted else None

    async def create_deleted(self, **values) -> DeletedAccountsDTO:
        created = await super().create(DeletedAccounts, **values)
        return DeletedAccountsDTO.model_validate(created)

    async def get_by_account_storage_id(
        self,
        account_storage_id: int,
    ) -> Optional[DeletedAccountsDTO]:
        result = await self.session_db.execute(
            select(DeletedAccounts).where(
                DeletedAccounts.account_storage_id == account_storage_id
            )
        )
        deleted = result.scalar_one_or_none()
        return DeletedAccountsDTO.model_validate(deleted) if deleted else None
