from __future__ import annotations

from typing import Iterable

from sqlalchemy import update, delete, select

from src.database.models.categories import PurchaseRequestUniversal
from src.repository.database.base import DatabaseBase


class PurchaseRequestUniversalRepository(DatabaseBase):

    async def create_many(
        self,
        purchase_request_id: int,
        universal_storage_ids: Iterable[int],
    ) -> None:
        for storage_id in universal_storage_ids:
            self.session_db.add(
                PurchaseRequestUniversal(
                    purchase_request_id=purchase_request_id,
                    universal_storage_id=storage_id,
                )
            )

    async def update_universal_storage_id(
        self,
        purchase_request_id: int,
        old_storage_id: int,
        new_storage_id: int,
    ) -> None:
        await self.session_db.execute(
            update(PurchaseRequestUniversal)
            .where(
                (PurchaseRequestUniversal.purchase_request_id == purchase_request_id)
                & (PurchaseRequestUniversal.universal_storage_id == old_storage_id)
            )
            .values(universal_storage_id=new_storage_id)
        )

    async def delete_by_request_id(self, purchase_request_id: int) -> None:
        await self.session_db.execute(
            delete(PurchaseRequestUniversal)
            .where(PurchaseRequestUniversal.purchase_request_id == purchase_request_id)
        )

    async def get_storage_ids_by_request_id(self, purchase_request_id: int) -> list[int]:
        result = await self.session_db.execute(
            select(PurchaseRequestUniversal.universal_storage_id)
            .where(PurchaseRequestUniversal.purchase_request_id == purchase_request_id)
        )
        return list(result.scalars().all())
