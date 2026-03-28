from __future__ import annotations

from typing import Iterable

from sqlalchemy import update, delete, select

from src.database.models.categories import PurchaseRequestAccount
from src.repository.database.base import DatabaseBase


class PurchaseRequestAccountsRepository(DatabaseBase):

    async def create_many(
        self,
        purchase_request_id: int,
        account_storage_ids: Iterable[int],
    ) -> None:
        for storage_id in account_storage_ids:
            self.session_db.add(
                PurchaseRequestAccount(
                    purchase_request_id=purchase_request_id,
                    account_storage_id=storage_id,
                )
            )

    async def update_account_storage_id(
        self,
        purchase_request_id: int,
        old_storage_id: int,
        new_storage_id: int,
    ) -> None:
        await self.session_db.execute(
            update(PurchaseRequestAccount)
            .where(
                (PurchaseRequestAccount.purchase_request_id == purchase_request_id)
                & (PurchaseRequestAccount.account_storage_id == old_storage_id)
            )
            .values(account_storage_id=new_storage_id)
        )

    async def delete_by_request_id(self, purchase_request_id: int) -> None:
        await self.session_db.execute(
            delete(PurchaseRequestAccount)
            .where(PurchaseRequestAccount.purchase_request_id == purchase_request_id)
        )

    async def get_storage_ids_by_request_id(self, purchase_request_id: int) -> list[int]:
        result = await self.session_db.execute(
            select(PurchaseRequestAccount.account_storage_id)
            .where(PurchaseRequestAccount.purchase_request_id == purchase_request_id)
        )
        return list(result.scalars().all())
